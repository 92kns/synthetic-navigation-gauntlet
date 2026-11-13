# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import hashlib
import ssl
import pathlib
import shutil


def create_certificates(directory):
    source = pathlib.Path(__file__).resolve().parents[1] / "certs"
    for name, target in (
        ("http2-cert.key", "key.pem"),
        ("navigation-gauntlet-ca.pem", "ca.pem"),
        ("navigation-gauntlet-cert.pem", "cert.pem"),
    ):
        shutil.copyfile(source / name, directory / target)


def certificate_spki_hash(path):
    der = ssl.PEM_cert_to_DER_cert(path.read_text())

    def field(offset):
        start = offset
        tag, length = der[offset:offset + 2]
        offset += 2
        if length & 0x80:
            count = length & 0x7f
            length = int.from_bytes(der[offset:offset + count], "big")
            offset += count
        return tag, offset, offset + length, start

    _, certificate, _, _ = field(0)
    _, offset, _, _ = field(certificate)
    if der[offset] == 0xa0:
        _, _, offset, _ = field(offset)
    for _ in range(5):
        _, _, offset, _ = field(offset)
    _, _, end, start = field(offset)
    return base64.b64encode(hashlib.sha256(der[start:end]).digest()).decode("ascii")
