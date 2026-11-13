# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import shutil
import json
import pathlib
import re
import struct
import subprocess
import tempfile
import urllib.parse
import zlib

from .scenarios import ASSET, SCENARIOS, scenario_page, expand_recipe_template

SCENARIOS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scenarios"

# Origin 0 serves the scenario pages; origins 1-4 emulate third-party hosts.
NUM_ORIGINS = 5
CACHEABLE = "public, max-age=3600"
MAX_DELAY_MS = 10000
MAX_KB = 4096
MAX_IMG_DIM = 2560
# Number of .gN classes styled by /gen/css?match=N and used by generated markup.
STYLE_CLASSES = 32

TEXT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
}

WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim minim veniam quis "
    "nostrud exercitation ullamco laboris nisi aliquip commodo consequat"
).split()

GEN_URL_RE = re.compile(r"/gen/[a-z]+\?[^\"'`\s<>]+")
GEN_MARKUP_RE = re.compile(r"<!--gen:(\w+)((?:\s+\w+=\S+?)*)\s*-->")


def substitute_origins(value, origins):
    """Replace {originN} tokens in a string, or recursively in a list."""
    if isinstance(value, list):
        return [substitute_origins(v, origins) for v in value]
    if not isinstance(value, str):
        return value
    for i, origin in enumerate(origins):
        value = value.replace(f"{{origin{i}}}", origin)
    return value


class _Rng:
    """64-bit LCG; only the high 32 bits of the state are used."""

    def __init__(self, seed):
        self.state = zlib.crc32(seed.encode("utf-8"))

    def next(self, bound):
        self.state = (
            self.state * 6364136223846793005 + 1442695040888963407
        ) & 0xFFFFFFFFFFFFFFFF
        return (self.state >> 32) % bound

    def words(self, count):
        return " ".join(WORDS[self.next(len(WORDS))] for _ in range(count))


def _clean_seed(seed):
    return re.sub(r"[^A-Za-z0-9_-]", "", seed)[:64] or "0"


def _pad(body, target):
    filler = target - len(body) - len("/**/\n")
    if filler <= 0:
        return body
    return body + "/*" + "x" * filler + "*/\n"


def generate_js(kb, work, seed):
    """~kb KiB of small functions that all run once, then work*1000 xorshift
    iterations. The result is stored on self.__gen[seed]."""
    seed = _clean_seed(seed)
    rng = _Rng(seed)
    target = kb * 1024
    footer = (
        "var acc=0;for(var j=0;j<M.length;j++){acc=(acc+M[j]())|0;}\n"
        f"var x={zlib.crc32(seed.encode()) | 1};"
        f"for(var k=0;k<{work * 1000};k++){{x^=x<<13;x^=x>>>17;x^=x<<5;}}\n"
        f'(self.__gen=self.__gen||{{}})["{seed}"]=acc^x;\n'
        "})();\n"
    )
    parts = ["(function(){var M=[];\n"]
    size = len(parts[0]) + len(footer)
    i = 0
    while size < target - 200:
        nums = ",".join(str(rng.next(100000)) for _ in range(16))
        text = "".join(WORDS[rng.next(len(WORDS))][0] for _ in range(32))
        module = (
            f'M.push(function m{i}(){{var a=[{nums}];var s="{text}";var t={i};'
            "for(var i=0;i<a.length;i++){t=(t*31+a[i]+s.charCodeAt(i))|0;}"
            "return t;});\n"
        )
        parts.append(module)
        size += len(module)
        i += 1
    parts.append(footer)
    return _pad("".join(parts), target).encode("utf-8")


def generate_css(kb, seed, match):
    """Rules for the first `match` .gN classes used by generated markup, then
    filler rules that don't match anything, up to ~kb KiB."""
    seed = _clean_seed(seed)
    rng = _Rng(seed)
    target = kb * 1024
    parts = []
    for n in range(min(match, STYLE_CLASSES)):
        a, b = rng.next(0xFFFFFF), rng.next(0xFFFFFF)
        parts.append(
            f".g{n}{{background:linear-gradient({rng.next(360)}deg,#{a:06x}22,#{b:06x}44);"
            f"border-radius:{2 + rng.next(8)}px;"
            f"box-shadow:0 {1 + rng.next(4)}px {2 + rng.next(10)}px #{a:06x}55;"
            f"text-shadow:0 1px 1px #{b:06x}33;color:#{rng.next(0x7FFFFF):06x}}}\n"
            f".g{n}:nth-child(3n) span,.g{n} b{{letter-spacing:.{rng.next(9)}px;"
            f"border-bottom:1px solid #{b:06x}66}}\n"
        )
    size = sum(len(p) for p in parts)
    i = 0
    while size < target - 200:
        rule = (
            f".x-{seed}-{i} .c{rng.next(1000)}>span{{color:#{rng.next(0xFFFFFF):06x};"
            f"margin:{rng.next(20)}px {rng.next(20)}px;padding:{rng.next(12)}px;"
            f"border:1px solid #{rng.next(0xFFFFFF):06x}}}\n"
        )
        parts.append(rule)
        size += len(rule)
        i += 1
    return _pad("".join(parts), target).encode("utf-8")


def _png_chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def generate_png(w, h, seed):
    tint = zlib.crc32(_clean_seed(seed).encode())
    channels = [bytes(x * amount // w for x in range(w)) for amount in (190, 40, 120)]
    lines = []
    for y in range(h):
        row = bytearray(w * 3)
        for channel, base in enumerate(channels):
            shift = ((tint >> (channel * 8)) & 63) + y * (30, 180, 120)[channel] // h
            row[channel::3] = base.translate(bytes((value + shift) % 256 for value in range(256)))
        lines.append(b"\x00" + row)
    header = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(lines), 3))
        + _png_chunk(b"IEND", b"")
    )


def encode_image(png, image_format):
    if image_format == "png":
        return png
    if image_format not in ("jpeg", "webp"):
        raise ValueError(f"Unsupported image format: {image_format}")
    try:
        from PIL import Image
    except ImportError:
        if image_format == "webp" and shutil.which("cwebp"):
            with tempfile.TemporaryDirectory() as directory:
                source = pathlib.Path(directory) / "source.png"
                destination = pathlib.Path(directory) / "image.webp"
                source.write_bytes(png)
                subprocess.run(
                    [shutil.which("cwebp"), "-quiet", "-q", "82", str(source), "-o", str(destination)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                )
                return destination.read_bytes()
        encoder = "mjpeg" if image_format == "jpeg" else "libwebp"
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(f"No encoder available for {image_format}")
        return subprocess.run(
            [ffmpeg, "-loglevel", "error", "-i", "pipe:0",
             "-frames:v", "1", "-c:v", encoder, "-f", "image2pipe", "pipe:1"],
            input=png, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout
    output = io.BytesIO()
    Image.open(io.BytesIO(png)).save(output, format=image_format.upper(), quality=82)
    return output.getvalue()


def generate_json(items, seed, img_w, img_h, img_delay_ms):
    seed = _clean_seed(seed)
    rng = _Rng(seed)
    out = []
    for i in range(items):
        img = f"/gen/img?w={img_w}&h={img_h}&seed={seed}-{i}"
        if img_delay_ms:
            img += f"&delay_ms={img_delay_ms}"
        images = {
            "img": img + "&format=webp",
            "img2x": img.replace(f"w={img_w}&h={img_h}", f"w={img_w * 2}&h={img_h * 2}") + "&format=webp",
            "jpeg": img + "&format=jpeg",
        }
        out.append({
            "id": i,
            "title": rng.words(4).title(),
            "blurb": rng.words(14),
            "price": f"{rng.next(500)}.{rng.next(100):02d}",
            "rating": rng.next(5) + 1,
            **images,
        })
    return json.dumps({"items": out}, separators=(",", ":")).encode("utf-8")


def _markup_table(seed, rows=50, cols=6):
    rng = _Rng(seed)
    head = "".join(f"<th>{rng.words(1).title()}</th>" for _ in range(int(cols)))
    body = []
    for r in range(int(rows)):
        cells = "".join(
            f'<td class="g{rng.next(STYLE_CLASSES)}"><span>{rng.words(2)}</span>'
            f" <b>{rng.next(10000) / 100:.2f}</b></td>"
            for _ in range(int(cols))
        )
        body.append(f"<tr>{cells}</tr>")
    return f'<table class="gt"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _markup_text(seed, paras=10):
    rng = _Rng(seed)
    out = []
    for _ in range(int(paras)):
        spans = " ".join(
            f'{rng.words(6)} <span class="g{rng.next(STYLE_CLASSES)}">{rng.words(3)}</span>'
            f" <em>{rng.words(2)}</em> <a href=\"#\">{rng.words(2)}</a>"
            for _ in range(4)
        )
        out.append(f"<p>{spans}.</p>")
    return "\n".join(out)


def _markup_cards(seed, n=12, w=240, h=160, delay=0, href="#", host=""):
    rng = _Rng(seed)
    out = []
    for i in range(int(n)):
        native_w, native_h = max(480, int(w)), max(320, int(h))
        img = f"{host}/gen/img?w={native_w}&h={native_h}&seed={seed}-{i}"
        large = img.replace(f"w={native_w}&h={native_h}", f"w={native_w * 2}&h={native_h * 2}")
        if int(delay):
            img += f"&delay_ms={delay}"
        out.append(
            f'<a class="gc g{i % STYLE_CLASSES}" id="card-{i}" href="{href.replace("ID", str(i))}">'
            f'<picture><source type="image/webp" srcset="{img}&format=webp {native_w}w, {large}&format=webp {native_w * 2}w" sizes="(min-width: 1100px) 33vw, 50vw">'
            f'<img src="{img}&format=jpeg" width="{w}" height="{h}" loading="{"eager" if i < 6 else "lazy"}" alt=""></picture>'
            f"<span>{rng.words(3).title()}</span><b>${20 + rng.next(480)}</b>"
            f"<small>{rng.words(10)}</small></a>"
        )
    return "\n".join(out)


MARKUP = {"table": _markup_table, "text": _markup_text, "cards": _markup_cards}


def expand_markup(html):
    """Replace <!--gen:KIND key=value ...--> directives with deterministic
    generated markup."""

    def replace(match):
        params = dict(p.split("=", 1) for p in match.group(2).split())
        seed = _clean_seed(params.pop("seed", "0"))
        return MARKUP[match.group(1)](seed, **params)

    return GEN_MARKUP_RE.sub(replace, html)


def _int_param(query, name, default, upper):
    try:
        value = int(query.get(name, [default])[0])
    except ValueError:
        value = default
    return max(0, min(value, upper))


class GauntletAssets:
    # Shared by all origins; generated bodies are deterministic.
    _cache = {}

    def __init__(self, origins):
        self.origins = origins

    def static(self, path):
        """Returns (body, content_type, cache_control), or None if the path
        isn't a scenario file."""
        try:
            candidate = (SCENARIOS_DIR / path.lstrip("/")).resolve()
            if SCENARIOS_DIR not in candidate.parents or not candidate.is_file():
                return None
            body = candidate.read_bytes()
        except (OSError, ValueError):
            return None
        suffix = candidate.suffix
        if suffix in (".html", ".js"):
            body = expand_recipe_template(path.lstrip("/"), body.decode("utf-8")).encode("utf-8")
        if suffix == ".html":
            body = expand_markup(body.decode("utf-8")).encode("utf-8")
        if suffix in (".html", ".css", ".js", ".json"):
            body = substitute_origins(body.decode("utf-8"), self.origins).encode(
                "utf-8"
            )
        content_type = "font/ttf" if suffix == ".ttf" else TEXT_TYPES.get(suffix, "application/octet-stream")
        cache_control = "no-store"
        return body, content_type, cache_control

    def prewarm(self):
        """Generate every /gen/ asset the scenarios reference, including the
        images listed in JSON responses, so generation never lands inside a
        measurement."""
        urls = {ASSET, "/gen/img?w=640&h=360&seed=scene"}
        for name in SCENARIOS:
            try:
                urls.update(GEN_URL_RE.findall(scenario_page(name, self.origins).decode()))
            except KeyError:
                pass
        for path in SCENARIOS_DIR.rglob("*"):
            if path.suffix in (".html", ".css", ".js", ".json"):
                text = expand_recipe_template(path.relative_to(SCENARIOS_DIR).as_posix(), path.read_text("utf-8"))
                urls.update(GEN_URL_RE.findall(expand_markup(text)))
        pending = sorted(urls)
        while pending:
            parsed = urllib.parse.urlparse(pending.pop())
            response = self.generate(parsed.path, urllib.parse.parse_qs(parsed.query))
            if response and parsed.path == "/gen/json":
                pending.extend(
                    item[key] for item in json.loads(response[0])["items"]
                    for key in ("img", "img2x", "jpeg")
                )

    def generate(self, path, query):
        key = (
            path,
            tuple(sorted((k, tuple(v)) for k, v in query.items() if k != "delay_ms")),
        )
        if key not in self._cache:
            self._cache[key] = self._generate(path, query)
        return self._cache[key]

    def _generate(self, path, query):
        seed = query.get("seed", ["0"])[0]
        if path == "/gen/js":
            kb = _int_param(query, "kb", 10, MAX_KB)
            work = _int_param(query, "work", 0, 10000000)
            return generate_js(kb, work, seed), TEXT_TYPES[".js"], "no-store"
        if path == "/gen/css":
            kb = _int_param(query, "kb", 10, MAX_KB)
            match = _int_param(query, "match", 0, STYLE_CLASSES)
            return generate_css(kb, seed, match), TEXT_TYPES[".css"], "no-store"
        if path == "/gen/img":
            w = max(1, _int_param(query, "w", 64, MAX_IMG_DIM))
            h = max(1, _int_param(query, "h", 64, MAX_IMG_DIM))
            image_format = query.get("format", ["png"])[0]
            if image_format not in ("png", "jpeg", "webp"):
                return None
            png_key = ("pixels", w, h, seed)
            if png_key not in self._cache:
                self._cache[png_key] = generate_png(w, h, seed)
            png = self._cache[png_key]
            try:
                return encode_image(png, image_format), f"image/{image_format}", "no-store"
            except (RuntimeError, subprocess.CalledProcessError):
                return png, "image/png", "no-store"
        if path == "/gen/json":
            body = generate_json(
                _int_param(query, "items", 10, 1000),
                seed,
                _int_param(query, "img_w", 320, MAX_IMG_DIM),
                _int_param(query, "img_h", 200, MAX_IMG_DIM),
                _int_param(query, "img_delay_ms", 0, MAX_DELAY_MS),
            )
            return body, TEXT_TYPES[".json"], "no-store"
        return None


