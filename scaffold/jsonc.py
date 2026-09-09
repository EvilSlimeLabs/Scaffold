"""Tolerant loader for Bedrock pack JSON.

Vanilla's own packs are not strict JSON: they carry `//` and `/* */` comments,
the occasional trailing comma, and a UTF-8 BOM. `json.load` rejects all three,
so anything reading `CommunityVanillaResourcePack/blocks.json` or its
`terrain_texture.json` has to come through here.
"""
import json
import re

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def strip(text):
    """Remove comments and trailing commas, leaving string literals alone."""
    out = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(c)
        i += 1
    return _TRAILING_COMMA.sub(r"\1", "".join(out))


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.loads(strip(f.read()))
