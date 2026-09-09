"""Recolour the bed's six tiles, once per dye, so a bed is its own colour.

    python -m tools.textures.beds

A bed's colour is not in its block states. It is in the block entity beside the
block, and the game holds one model per colour rather than tinting anything, so
there is nothing for a ghost block to tint at run time. The pack carries the red
bed's six terrain tiles and nothing else, so the sixteen sets are made here:
`bed_<colour>_<part>_<face>.png` beside the originals.

**Only the blanket is recoloured.** A bed tile carries three things: the blanket,
the white sheet at the head, and the wooden legs under it. The blanket is the
only strongly red part, so a pixel is taken for blanket when its red is at least
twice its green and twice its blue, which leaves the sheet and the legs alone.

**It is a recolour, not a tint.** The tiles are red to begin with, so multiplying
them by a dye gives mud. Each blanket pixel keeps how bright it is against a
blanket pixel of ordinary brightness in its own tile, and that fraction of the
dye is what it becomes.

The dyes are read out of the pack's own wool textures, the same way
`tools/textures/banners.py` reads them, so they are the colours this pack
actually uses. Nothing here is needed at run time; re-run
`tools/blocks/furniture.py` afterwards if the list of colours changes.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                      "textures", "blocks")

## Bedrock's dye order, which the block entity's colour counts in
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "silver", "cyan", "purple", "blue", "brown", "green", "red",
           "black"]
PARTS = ["feet", "head"]
FACES = ["top", "side", "end"]


def dye(colour):
    """The colour of a wool block, which is the dye the game uses."""
    from tools.textures.banners import dye as wool

    return wool(colour)


def blanket(pixel):
    """Whether a pixel is the blanket rather than the sheet or the legs."""
    red, green, blue, alpha = pixel
    return alpha > 8 and red >= 2 * green and red >= 2 * blue


def recolour(tile, colour):
    """The tile with its blanket in `colour` and everything else as it was."""
    out = tile.copy()
    pixels = list(out.getdata())
    lit = [sum(p[:3]) for p in pixels if blanket(p)]
    if not lit:
        return out
    ## the dye is what a blanket pixel of ordinary brightness becomes, so the
    ## middle of the tile is the reference rather than its brightest pixel:
    ## against the brightest, every other pixel comes out darker than vanilla
    ordinary = sorted(lit)[len(lit) // 2]
    scale = dye(colour)
    made = []
    for pixel in pixels:
        if not blanket(pixel):
            made.append(pixel)
            continue
        share = sum(pixel[:3]) / float(ordinary)
        made.append(tuple(min(255, int(band * share)) for band in scale)
                    + (pixel[3],))
    out.putdata(made)
    return out


def main():
    print("recolouring the bed")
    written = 0
    for part in PARTS:
        for face in FACES:
            source = os.path.join(BLOCKS, "bed_%s_%s.png" % (part, face))
            tile = Image.open(source).convert("RGBA")
            for colour in COLOURS:
                made = recolour(tile, colour)
                made.save(os.path.join(
                    BLOCKS, "bed_%s_%s_%s.png" % (colour, part, face)))
                written += 1
        print("   %-6s %s" % (part, ", ".join(FACES)))
    print("%d tiles, %d colours" % (written, len(COLOURS)))
    print("now re-run tools/blocks/furniture.py")


if __name__ == "__main__":
    main()
