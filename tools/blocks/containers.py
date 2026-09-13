"""Give a shulker box the two parts it has, and each part its own art.

    python -m tools.blocks.containers

A shulker box was a cube wearing its lid texture on all six faces, because the
only thing `blocks.json` names for it is `shulker_top_<colour>`. It is really a
base with a lid on top, and the whole box is one entity sheet, 64x64 per colour:
the lid's top sits at x16 y0, the lid's sides run across y16, and the base's
sides across y36.

Each colour is a family of its own. The sheet is the only thing that tells them
apart, and one family cannot carry seventeen sheets.

Nothing here is needed at run time.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables
from tools.blocks.geometry import Cube, on_sheet, unwrap


# --- shulker boxes ----------------------------------------------------------
#
# The sheet is the entity one: the lid's top sits at x16 y0, the lid's sides run
# across y16, and the base's sides across y36. The box is drawn as the two parts
# it has, so the lid's art is on the lid and the base's on the base.
SHULKER = "textures/entity/shulker/shulker_%s"

## The dyes that name a block, then below them the ids that name no colour and
## the one whose sheet is spelled differently: Bedrock calls the block light
## gray and the sheet silver, and there is no silver_shulker_box to define.
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]
EXTRA = {"undyed_shulker_box": "undyed", "shulker_box": "undyed",
         "light_gray_shulker_box": "silver"}


## **Where the two parts sit on the sheet, as the boxes the entity model draws
## them from.** The lid is sixteen by twelve by sixteen at the sheet's corner
## and the base sixteen by eight by sixteen at y28. `unwrap` turns each into the
## six rectangles Bedrock lays a box out as and `on_sheet` picks a tile corner
## for every one, so no face is measured off the picture by eye.
##
## They were measured that way before, and the base's underside was measured
## wrong: it read sixteen by twelve down from y48, but the base's own rows stop
## at y52 and what follows is the pale body of the shulker that lives inside the
## box. Every shulker box had a cream coloured bottom with part of a shulker on
## it.
LID_BOX = ((0, 0), (16, 12, 16))
BASE_BOX = ((0, 28), (16, 8, 16))
SHEET = 64


def parted(sheet, box):
    """One part of the box, as a texture and a window per face."""
    art, window = {}, {}
    for face, region in unwrap(*box).items():
        mark, fitted = on_sheet(sheet, region, SHEET)
        art[face] = mark
        window[face] = fitted
    return art, window


## **The two parts overlap, and have to.** The entity draws the base eight tall
## from the floor and the lid twelve tall from y4, which is sixteen in all and
## exactly a block. Where they cross, each fills what the other leaves out: the
## bottom four rows of the lid's side art are painted at the edges and clear
## through the middle, and the top four of the base's are the other way about.
## Stacked eight on eight instead, with the lid's twelve rows squashed onto
## eight, neither covers the other and a shulker box has a slot cut through
## every side of it.
BASE_TALL = 8
LID_TALL = 12
LID_AT = 4

## **The base is drawn a shade narrower than the lid.** Both are a full sixteen
## across in the entity's own model, so over the four rows they share every one
## of their side faces sat on the other's and the whole overlap flickered. A
## fifth of a pixel in on each side puts the base's walls inside the lid's, and
## the step below the lid is too small to read. The lid keeps the block's full
## width, since it is the part that has to line up with the block beside it.
BASE_INSET = 0.2


def shulker(colour):
    """A base with a lid over it, each reading its own part of the sheet."""
    sheet = SHULKER % colour
    base_art, base_window = parted(sheet, BASE_BOX)
    lid_art, lid_window = parted(sheet, LID_BOX)
    across = 16 - 2 * BASE_INSET
    return {"default": [
        Cube((across, BASE_TALL, across),
             (BASE_INSET, 0, BASE_INSET),
             texture=base_art, window=base_window),
        Cube((16, LID_TALL, 16), (0, LID_AT, 0),
             texture=lid_art, window=lid_window)]}


def main():
    print("writing the shulker boxes")
    for colour in COLOURS:
        family = "shulker_box_%s" % colour
        tables.write(family, shulker(colour))
        tables.define(["%s_shulker_box" % colour], family)
    for block, colour in EXTRA.items():
        family = "shulker_box_%s" % colour
        tables.write(family, shulker(colour))
        tables.define([block], family)
    print("   %d colours" % (len(COLOURS) + 1))


if __name__ == "__main__":
    main()
