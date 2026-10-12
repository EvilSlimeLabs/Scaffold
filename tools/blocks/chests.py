"""The chest, single and as either half of a double chest.

    python -m tools.blocks.chests

A double chest is two chest blocks whose block entities name each other with
`pairx` and `pairz`. `core.paired` works out which half a block is, seen from
in front, and hands it to the rules as the block entity's `pair` field, `left`
or `right`; the family draws each half as a box running from its outer edge to
the seam, so the two meet as one chest.

The front is one picture across both halves, with the latch on the seam: the
halves read it from the two tiles `tools/textures/chests.py` writes beside the
single front, through a `window` on the same slot, so the one family serves the
wooden, trapped and copper chests alike. The top, the bottom and the back are
the single chest's, less the border on the seam side.

Every chest family name, form and window here is in Minecraft's frame: the
chest rests with its front on the north face, and east is the low side of x, so
the left half, seen from in front, is the one on the low side.

Nothing here is needed at run time.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables
from tools.textures.chests import LEFT, RIGHT

FAMILY = "chest"
PX = 1 / 16

## the single chest: fourteen across and deep, fifteen tall, set two pixels back
## from the front
HEIGHT = 0.9375
DEPTH = 0.875
SINGLE = {"size": [0.875, HEIGHT, DEPTH], "offset": [0.125, 0, 0.125]}


def face(uv, size, slot, window=None):
    texture = {"slot": slot}
    if window:
        texture["window"] = list(window)
    return {"uv": list(uv), "size": list(size), "texture": texture}


def single():
    return {"center": [0.5, 0.5, 0.5], "cubes": [dict(SINGLE, faces={
        "north": face([0, 0], [1, 1], "south"),
        "south": face([0, 0], [1, 1], "north"),
        "east": face([0, 0], [1, 1], "west"),
        "west": face([0, 0], [1, 1], "east"),
        "up": {"uv": [1, 1], "size": [-1, -1]},
        "down": {"uv": [1, 1], "size": [-1, -1]}})]}


def half(side):
    """One half of a double chest, `left` or `right` seen from in front.

    The left half stands on the low side of x and reaches up to the seam at
    x 1; the right half runs from the seam at x 0. Each is a pixel in from its
    outer edge and fifteen wide, so the pair is thirty across.
    """
    left = side == "left"
    across = [PX, 0, 0.125] if left else [0, 0, 0.125]
    ## the top, the bottom and the back read their half of the double chest,
    ## beside the single picture on the same sheet
    return {"center": [0.5, 0.5, 0.5], "cubes": [{
        "size": [15 * PX, HEIGHT, DEPTH], "offset": across, "faces": {
            "north": face([0, 0], [1, 1], "south", LEFT if left else RIGHT),
            ## the back reads its half of the double back beside the single
            ## side, seen from behind, so the left half reads the right tile
            "south": face([0, 0], [1, 1], "north", RIGHT if left else LEFT),
            "east": face([0, 0], [1, 1], "west"),
            "west": face([0, 0], [1, 1], "east"),
            ## a top reads its window backwards across, so each half reads
            ## the other's tile and the outer border lands on the outside
            "up": face([1, 1], [-1, -1], "up", RIGHT if left else LEFT),
            "down": face([1, 1], [-1, -1], "down", RIGHT if left else LEFT)}}]}


def main():
    print("writing the chest")
    tables.forms(FAMILY, {"default": single(), "left": half("left"),
                          "right": half("right")})
    tables.rules(FAMILY, data={"entity": "pair"})


if __name__ == "__main__":
    main()
