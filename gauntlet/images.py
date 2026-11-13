# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Deterministic, dependency-free generator for the gauntlet's illustrations,
thumbnails, posters and hero image. Output is PNG only, rasterised from flat
shapes with the standard library."""

import hashlib
import math
import os
import pathlib
import random
import shutil
import struct
import tempfile
import zlib

APP_COUNTS = {
    "stay": 12, "room": 6, "studio": 6, "community": 4, "social": 8, "paper": 1,
    "garden": 1, "solar": 1, "train": 1, "workshop": 1, "street": 1, "library": 1, "coast": 1,
}
APP_AVATAR_COLORS = (
    "#c6d5c1", "#d8c1b2", "#becbd5", "#d3bfd0", "#d1d4ad", "#dabca7",
    "#b5ccc3", "#d6c9a8", "#c5bed9", "#b6cdcb", "#d8c9bd", "#c8d2b4",
)
VIDEO_AVATAR_COLORS = ("#a0bfae", "#d5b58e", "#8fa9ba", "#c2aaad", "#b4bd8e", "#d0ad92", "#a6b6b2", "#d1c28d")
SCALES = ((1, ""), (2, "@2x"))


def _rgb(color):
    if isinstance(color, tuple):
        return bytes(max(0, min(255, round(v))) for v in color)
    return bytes.fromhex(color.lstrip("#"))


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


class Canvas:
    """Flat-colour rasteriser; coordinates are logical and multiplied by scale."""

    def __init__(self, width, height, background, scale=1):
        self.scale = scale
        self.width = round(width * scale)
        self.height = round(height * scale)
        self.rows = [bytearray(_rgb(background) * self.width) for _ in range(self.height)]

    def _span(self, y, x0, x1, color):
        x0 = max(0, x0)
        x1 = min(self.width, x1)
        if 0 <= y < self.height and x1 > x0:
            self.rows[y][x0 * 3:x1 * 3] = color * (x1 - x0)

    def rect(self, box, color):
        color = _rgb(color)
        s = self.scale
        x0, y0, x1, y1 = (round(v * s) for v in box)
        for y in range(max(0, y0), min(self.height, y1)):
            self._span(y, x0, x1, color)

    def ellipse(self, box, color):
        color = _rgb(color)
        s = self.scale
        x0, y0, x1, y1 = (v * s for v in box)
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        if rx <= 0 or ry <= 0:
            return
        for y in range(max(0, math.floor(y0)), min(self.height, math.ceil(y1))):
            d = (y + 0.5 - cy) / ry
            if abs(d) < 1:
                half = rx * math.sqrt(1 - d * d)
                self._span(y, round(cx - half), round(cx + half), color)

    def rounded(self, box, radius, color):
        x0, y0, x1, y1 = box
        r = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
        self.rect((x0 + r, y0, x1 - r, y1), color)
        self.rect((x0, y0 + r, x1, y1 - r), color)
        for cx in (x0, x1 - 2 * r):
            for cy in (y0, y1 - 2 * r):
                self.ellipse((cx, cy, cx + 2 * r, cy + 2 * r), color)

    def polygon(self, points, color, xclip=None):
        color = _rgb(color)
        s = self.scale
        pts = [(x * s, y * s) for x, y in points]
        ys = [y for _, y in pts]
        low, high = max(0, math.floor(min(ys))), min(self.height, math.ceil(max(ys)))
        count = len(pts)
        for y in range(low, high):
            sample = y + 0.5
            crossings = []
            for i in range(count):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % count]
                if (ya <= sample < yb) or (yb <= sample < ya):
                    crossings.append(xa + (sample - ya) * (xb - xa) / (yb - ya))
            crossings.sort()
            for i in range(0, len(crossings) - 1, 2):
                x0, x1 = round(crossings[i]), round(crossings[i + 1])
                if xclip:
                    x0, x1 = max(x0, round(xclip[0] * s)), min(x1, round(xclip[1] * s))
                self._span(y, x0, x1, color)

    def line(self, points, color, width=3):
        half = width / 2
        for (xa, ya), (xb, yb) in zip(points, points[1:]):
            length = math.hypot(xb - xa, yb - ya) or 1
            nx, ny = -(yb - ya) / length * half, (xb - xa) / length * half
            self.polygon([(xa + nx, ya + ny), (xb + nx, yb + ny), (xb - nx, yb - ny), (xa - nx, ya - ny)], color)

    def speckle(self, seed, count, amount, size=2):
        rng = random.Random(seed)
        for _ in range(count):
            x, y = int(rng.random() * self.width), int(rng.random() * self.height)
            row = self.rows[y]
            base = row[x * 3:x * 3 + 3]
            if len(base) < 3:
                continue
            shift = int(rng.random() * (2 * amount + 1)) - amount
            color = bytes(max(0, min(255, v + shift)) for v in base)
            for dy in range(int(rng.random() * size) + 1):
                if y + dy < self.height:
                    self._span(y + dy, x, x + int(rng.random() * size) + 1, color)

    def png(self):
        raw = b"".join(b"\x00" + bytes(row) for row in self.rows)
        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b"")


def illustration(kind, seed, scale=1):
    cv = Canvas(1280, 800, "#ffffff", scale)
    palettes=[('#e3d7be','#cad1ba','#466757','#b47554'),('#dad5c4','#c1cfc9','#536f6c','#c2956e'),('#e6d9c5','#c2c3a2','#5c714e','#aa735a'),('#e3d0c3','#b9c7bb','#557b6d','#cb9b6d')]
    paper,sky,green,clay=palettes[seed%4]
    rect=cv.rect;ellipse=cv.ellipse;poly=cv.polygon;ellipse2=cv.ellipse;rounded=cv.rounded
    def line(points,color,w=3):cv.line(points,color,w)
    def plant(x,y,size=100,pot=True):
        if pot:poly([(x-size*.22,y),(x+size*.22,y),(x+size*.15,y+size*.35),(x-size*.15,y+size*.35)],clay)
        line([(x,y),(x,y-size)],green,5)
        for j in range(6):
            yy=y-size*.15-j*size*.15;side=-1 if j%2 else 1
            poly([(x,yy),(x+side*size*.36,yy-size*.24),(x+side*size*.47,yy-size*.1),(x,yy+size*.05)],green)
    def window(x,y,w=110,h=155):
        rect((x-7,y-7,x+w+7,y+h+7),'#d9c8ab');rect((x,y,x+w,y+h),'#6b817a')
        rect((x+10,y+10,x+w*.42,y+h*.43),'#a9bdb3');rect((x+w*.56,y+10,x+w-10,y+h*.43),'#c1ccc0')
        line([(x+w/2,y),(x+w/2,y+h)],'#dfcfb8',5);line([(x,y+h/2),(x+w,y+h/2)],'#dfcfb8',5)
    rect((0,0,1280,500),sky)
    if kind in ('stay','street','coast','library','train'):
        rect((0,500,1280,800),'#c1c0a4')
        for i in range(16):
            x=i*90-20;y=510+(i%3)*30
            line([(x,y),(x+200,800)],'#d5d0b8',3)
        if kind=='coast':
            rect((0,400,1280,590),'#91aaa2');line([(0,560),(1280,555)],'#b9c6b7',7)
        for i in range(3):
            x=120+i*360;y=230-(seed+i)%3*30
            color=('#e9dcc4','#cfb298','#d9c9ac')[(seed+i)%3]
            rect((x,y,x+310,620),color)
            poly([(x-25,y),(x+155,y-125),(x+335,y)],('#6d6a55','#7e7360','#a78264')[(seed+i)%3])
            for j in range(2):
                for k in range(2):window(x+38+j*145,y+38+k*170,90,125)
            rect((x+118,510,x+198,620),'#63756b');ellipse((x+183,562,x+189,568),'#e4cf9e')
            if i==1:rect((x-7,y+157,x+317,y+178),'#bfa98a')
        for i in range(10):plant(i*145-20,650+i%3*20,130+(i%3)*45,False)
        rect((0,720,1280,800),'#aaa98b')
        if kind=='train':
            rect((80,445,1190,650),'#b0baa0');rect((80,580,1190,630),'#4b7160');rect((100,430,1160,455),'#d7d4be')
            for i in range(9):window(120+i*113,465,82,85)
            for x in (250,900):ellipse((x,620,x+80,700),'#4c554b')
        if kind=='library':
            rect((440,615,700,770),'#b48d68');rect((420,590,720,620),'#9d785d')
            for i in range(12):rect((455+i*18,635,467+i*18,735-i%3*10),('#b1bca0','#d9bb8d','#8b9d92')[i%3])
    elif kind in ('studio','workshop','room'):
        rect((0,0,1280,590),'#b9ac92' if kind!='room' else '#d7c9b2')
        rect((90,65,520,470),'#7f9b8d');rect((110,85,500,450),'#bbccbb')
        for x in (235,375):line([(x,85),(x,450)],'#e9ddc4',12)
        line([(110,265),(500,265)],'#e9ddc4',12)
        for i in range(7):plant(120+i*52,450,100+i%3*25,False)
        rect((0,590,1280,800),'#9b8e72')
        for i in range(9):line([(0,600+i*25),(1280,600+i*25)],'#b0a080',3)
        rect((780,80,1195,410),'#95836b')
        for row in range(3):
            rect((780,160+row*110,1195,172+row*110),'#6a6653')
            for j in range(7):
                x=805+j*52;y=100+row*110
                if (j+seed)%3:rect((x,y,x+26,y+58),'#beab88');ellipse((x-5,y+45,x+31,y+65),'#beab88')
                else:plant(x+12,y+54,40)
        if kind=='room':
            rect((350,450,1020,750),'#dfd7c4');poly([(350,450),(520,345),(1120,345),(1020,450)],'#eee7d4')
            rect((360,495,1010,700),'#849a88')
            for i in range(2):rounded((450+i*235,370,640+i*235,470),20,'#e8e1cf')
            rect((1050,540,1220,570),'#8c7961');plant(1115,510,90)
        else:
            poly([(100,550),(1080,505),(1240,680),(220,750)],'#b88a5e')
            line([(240,750),(240,800)],'#675a44',22);line([(1160,690),(1160,800)],'#675a44',22)
            for i in range(5):
                x=360+i*155;y=550+i%2*35
                ellipse((x-45,y-13,x+45,y+18),'#8c795f');rect((x-40,y-75,x+40,y),'#bd916e');ellipse((x-40,y-88,x+40,y-65),'#d1ad85');ellipse((x-31,y-83,x+31,y-69),'#705d49')
            ellipse((680,595,880,685),'#d6c09c');ellipse((700,608,860,672),'#b3a184')
            plant(160,540,130)
        poly([(650,0),(615,120),(705,120)],'#4d5a4c');ellipse((610,104,710,130),'#ddd0a9')
        line([(660,0),(660,60)],'#4d5a4c',4)
    else:
        rect((0,380,1280,800),'#aebc98')
        for y in (500,650):
            poly([(80,y),(1020,y-60),(1190,y+60),(240,y+120)],'#9c8160')
            for i in range(10):
                x=200+i*85
                plant(x,y+(i%2)*12,80+(i%3)*20,False)
        if kind=='solar':
            for i in range(4):
                x=70+i*290
                poly([(x,360),(x+220,330),(x+290,500),(x+40,535)],'#5c7981')
                for j in range(1,5):line([(x+j*45,355),(x+40+j*50,530)],'#91a9a5',2)
                for j in range(1,4):line([(x+j*10,360+j*38),(x+230+j*15,330+j*38)],'#91a9a5',2)
        elif kind=='paper':
            rect((150,90,1100,720),'#ede5cf')
            for i in range(5):
                for j in range(4):rect((240+i*145,200+j*100,360+i*145,270+j*100),('#9fb18b','#b9c19e','#c1af8a')[(i+j)%3])
            for i in range(5):plant(280+i*145,230,45,False)
        else:
            rect((860,190,1050,435),'#c5b18d');poly([(840,190),(955,100),(1070,190)],'#7d765d');window(890,235,130,130)
        for i in range(7):
            x=(i*211+seed*23)%1280
            ellipse((x-90,140+i%3*70,x+90,380+i%3*70),green)
            line([(x,300),(x+10,520+i%3*40)],'#7d805d',10)
        if kind=='social':
            rect((400,575,940,610),'#d0b68d');line([(440,600),(425,750)],'#8a795c',15);line([(900,600),(920,750)],'#8a795c',15)
            for i in range(3):ellipse((530+i*130,545,590+i*130,590),'#e9dfc4')
    return cv


def avatar(color, hair, size, scale=1):
    cv = Canvas(size, size, color, scale)
    k = size / 80
    cv.ellipse((27 * k, 15 * k, 53 * k, 43 * k), hair)
    cv.ellipse((14 * k, 46 * k, 66 * k, 100 * k), hair)
    return cv


def landscape(seed, width, height, scale=1, texture=0):
    palettes = ((132, 174, 178), (178, 181, 154), (169, 181, 187), (205, 171, 138))
    sky = palettes[seed % 4]
    rng = random.Random(seed)
    cv = Canvas(width, height, sky, scale)
    for y in range(round(height * scale)):
        shade = y / (height * scale) * 24
        cv._span(y, 0, cv.width, _rgb(tuple(c + shade for c in sky)))
    for layer in range(6):
        anchors = [rng.uniform(-0.10, 0.10) for _ in range(14)]
        points = []
        steps = 48
        for i in range(steps + 1):
            u = i / steps
            position = u * 13
            lo = min(12, int(position))
            value = anchors[lo] + (anchors[lo + 1] - anchors[lo]) * (position - lo)
            ridge = value + 0.27 + layer * 0.115 + 0.07 * math.sin(u * 8 + seed + layer)
            points.append((u * width, ridge * height))
        base = (95 - layer * 12, 135 - layer * 12, 134 - layer * 13)
        for band in range(8):
            light = 4 * math.sin(band / 8 * 11 + layer)
            cv.polygon(points + [(width, height), (0, height)], tuple(c + light for c in base),
                       xclip=(band * width / 8, (band + 1) * width / 8))
    if seed % 4 == 1:
        pts = [(width * (0.58 + 0.16 * math.sin(v / 40 * 7)) - (v / 40 - 0.34) * width * 0.0375, v / 40 * height) for v in range(18, 41)]
        pts += [(width * (0.58 + 0.16 * math.sin(v / 40 * 7)) + (v / 40 - 0.34) * width * 0.0375, v / 40 * height) for v in range(40, 17, -1)]
        cv.polygon(pts, (173, 189, 174))
    if seed % 4 == 2:
        cx, cy = width * 0.69, height * 0.66
        cv.rect((cx - width * 0.06, cy, cx + width * 0.06, cy + height * 0.13), "#a88e6d")
        cv.polygon(((cx - width * 0.08, cy), (cx, cy - height * 0.08), (cx + width * 0.08, cy)), "#384b48")
        cv.rect((cx + width * 0.015, cy + height * 0.03, cx + width * 0.045, cy + height * 0.08), "#edcc85")
    if texture:
        cv.speckle(seed, texture, 9)
    return cv


def hero(seed=2084388):
    width, height = 1600, 900
    rng = random.Random(seed)
    cv = Canvas(width, height, "#2d649e")
    for y in range(570):
        cv._span(y, 0, width, _rgb((45 + y * 0.21, 100 + y * 0.16, 158 + y * 0.10)))
    for layer in range(4):
        points = []
        for i in range(81):
            x = i * width / 80
            noise = rng.random() * 135
            points.append((x, 245 + layer * 62 + math.sin(x / (180 + layer * 33) + layer) * 68 + noise))
        color = (142 - layer * 21, 151 - layer * 20, 158 - layer * 23)
        cv.polygon(points + [(width, 570), (0, 570)], color)
        if layer < 3:
            cv.polygon([(x, y) for x, y in points] + [(x, y + 40 + rng.random() * 50) for x, y in reversed(points)],
                       (208, 215, 223), xclip=(0, width))
    for y in range(570, height):
        cv._span(y, 0, width, _rgb((29 + (y - 570) * 0.04, 62 + (y - 570) * 0.05, 71 + (y - 570) * 0.05)))
    shore = [(0, 840)] + [(i * width / 40, 815 + math.sin(i * width / 40 / 500) * 24 + rng.random() * 60) for i in range(41)] + [(width, height), (0, height)]
    cv.polygon(shore, (96, 92, 70))
    cv.speckle(seed, 45000, 14, 3)
    return cv


def _write(path, canvas):
    path.write_bytes(canvas.png())


def generate_all(destination):
    """Writes every generated image under destination, mirroring the URL layout:
    images/hero.png, apps/images/*, video/images/*."""
    destination = pathlib.Path(destination)
    apps = destination / "apps" / "images"
    video = destination / "video" / "images"
    for directory in (apps, video, destination / "images"):
        directory.mkdir(parents=True, exist_ok=True)
    for kind, count in APP_COUNTS.items():
        for index in range(count):
            scene = "garden" if kind == "community" else kind
            for scale, suffix in SCALES:
                _write(apps / f"{kind}-{index}{suffix}.png", illustration(scene, index + len(kind) * 19, scale))
    for index, color in enumerate(APP_AVATAR_COLORS):
        _write(apps / f"avatar-{index}.png", avatar(color, "#706d5c", 80))
    for index in range(24):
        _write(video / f"thumb-{index}.png", landscape(4800 + index, 480, 270))
    for index in range(4):
        _write(video / f"poster-{index}.png", landscape(4800 + index, 1600, 900, texture=40000))
    for index, color in enumerate(VIDEO_AVATAR_COLORS):
        _write(video / f"avatar-{index}.png", avatar(color, "#43564d", 64))
    _write(destination / "images" / "hero.png", hero())


def _generator_version():
    return hashlib.sha1(pathlib.Path(__file__).read_bytes()).hexdigest()[:12]


def ensure_images(fallback_parent, image_cache=None):
    """Returns a directory holding the generated images, generating them if the
    cache is cold. The cache lives under ~/.mozbuild when writable, else under
    fallback_parent."""
    name = f"images-{_generator_version()}"
    candidates = [pathlib.Path(image_cache)] if image_cache else [pathlib.Path(os.path.expanduser("~/.mozbuild/navigation-gauntlet/cache"))]
    for parent in candidates + [pathlib.Path(fallback_parent)]:
        final = parent / name
        if (final / ".complete").exists():
            return final
        try:
            parent.mkdir(parents=True, exist_ok=True)
            staging = pathlib.Path(tempfile.mkdtemp(prefix=name + ".", dir=parent))
        except OSError:
            continue
        try:
            generate_all(staging)
            (staging / ".complete").write_text("")
            try:
                os.replace(staging, final)
            except OSError:
                shutil.rmtree(staging, ignore_errors=True)
                if not (final / ".complete").exists():
                    raise
            return final
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
    raise RuntimeError("Unable to generate navigation gauntlet images")
