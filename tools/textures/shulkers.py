"""A shulker box's three faces, each one tile, cut from its entity sheet.

    python -m tools.textures.shulkers

A closed shulker box is the lid's twelve rows over the four rows of base that
show beneath it, and is a whole block. Drawn as the entity draws it, a lid over
a base, the two overlap and have to be pulled apart to stop them flickering,
which leaves a seam. Drawn as one box it needs one picture per face, and the
sheet does not hold one: the lid's sides and the base's are in different places
on it. So each colour gets three tiles, `shulker_box_<colour>_side`, `_top` and
`_bottom`, written into the vanilla pack.

The sheet is the entity's, 64 by 64: the lid is a box sixteen by twelve by
sixteen at the sheet's corner, the base sixteen by eight by sixteen at y28, each
laid out the way Bedrock lays a box out.

Nothing here is needed at run time.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image

from tools.blocks.containers import COLOURS, EXTRA

PACK = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures")
SHEET = os.path.join(PACK, "entity", "shulker", "shulker_%s.png")
OUT = os.path.join(PACK, "blocks", "shulker_box_%s_%s.png")

## where each piece is on the sheet, as (left, top, right, bottom). The lid is
## twelve rows from the block's top and the base eight from its bottom, so the
## two cross in the four rows between: the lid's bottom four are open in the
## middle, and the base's top four show through them.
LID_TOP = (16, 0, 32, 16)
LID_SIDE = (16, 16, 32, 28)
BASE_SIDE = (16, 44, 32, 52)
BASE_BOTTOM = (32, 28, 48, 44)
BASE_AT = 8


def faces(sheet):
    """(side, top, bottom) for one sheet."""
    side = Image.new("RGBA", (16, 16))
    side.paste(sheet.crop(BASE_SIDE), (0, BASE_AT))
    lid = Image.new("RGBA", (16, 16))
    lid.paste(sheet.crop(LID_SIDE), (0, 0))
    side.alpha_composite(lid)
    return side, sheet.crop(LID_TOP), sheet.crop(BASE_BOTTOM)


def colours():
    return list(COLOURS) + sorted(set(EXTRA.values()))


def main():
    print("writing the shulker box faces")
    for colour in colours():
        sheet = Image.open(SHEET % colour).convert("RGBA")
        for name, image in zip(("side", "top", "bottom"), faces(sheet)):
            image.save(OUT % (colour, name))
    print("   %d colours" % len(colours()))


if __name__ == "__main__":
    main()
