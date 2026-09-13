"""Flatten a cauldron's feet onto its inside, as one picture for the underside.

    python -m tools.textures.cauldron

`cauldron_bottom` is the block's underside and is opaque only at its four
corners: the feet, with the middle cut away because the game expects to see the
recessed floor of the pot through the gap. A ghost block cannot afford that. A
transparent texel still takes the depth it stands at, so the cut middle does not
show what is behind it, it blanks it, and a cauldron could be seen up through
from below and out of the top.

Standing a plate behind the gap fixed the seeing-through and left a cube in the
middle of the block for the liquid and the walls to trip over. One picture does
the same job: the inside of the pot with the feet drawn on top of it. The
underside then needs no geometry behind it at all.

Nothing here is needed at run time.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image

BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures",
                      "blocks")
INSIDE = "cauldron_inner"
FEET = "cauldron_bottom"
FLAT = "cauldron_bottom_flat"


def flattened():
    """The inside of the pot with the feet over it."""
    inside = Image.open(os.path.join(BLOCKS, INSIDE + ".png")).convert("RGBA")
    feet = Image.open(os.path.join(BLOCKS, FEET + ".png")).convert("RGBA")
    if feet.size != inside.size:
        feet = feet.resize(inside.size, Image.NEAREST)
    out = inside.copy()
    out.alpha_composite(feet)
    return out


def main():
    print("writing the cauldron's flattened underside")
    made = flattened()
    where = os.path.join(BLOCKS, FLAT + ".png")
    made.save(where)
    opaque = sum(1 for pixel in made.getdata() if pixel[3] == 255)
    print("   %-22s %dx%d, %d of %d texels opaque"
          % (FLAT + ".png", made.size[0], made.size[1], opaque,
             made.size[0] * made.size[1]))


if __name__ == "__main__":
    main()
