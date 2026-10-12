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
from tools.blocks.geometry import Cube, on_sheet, unwrap_south as unwrap


# --- shulker boxes ----------------------------------------------------------
#
# The sheet is the entity one: the lid's top sits at x16 y0, the lid's sides run
# across y16, and the base's sides across y36. The box is drawn as the two parts
# it has, so the lid's art is on the lid and the base's on the base.
SHULKER = "textures/entity/shulker/shulker_%s"

## The dyes that name a block, then below them the id that names no colour and
## the one whose sheet is spelled differently: Bedrock calls the block light
## gray and the sheet silver, and there is no silver_shulker_box to define. An
## older structure's `shulker_box` with a `color` arrives already split into
## these by `block_upgrade`.
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]
EXTRA = {"undyed_shulker_box": "undyed", "light_gray_shulker_box": "silver"}


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


## A closed shulker box is drawn as one box, a shade under a whole block, each
## face reading its own tile from `tools/textures/shulkers.py`. It rests lid up,
## and turns by the `facing` its block entity keeps, the way the game numbers a
## facing: 0 down, 1 up, 2 north, 3 south, 4 west, 5 east.
FACE_TILE = "textures/blocks/shulker_box_%s_%s"
FACING = {"0": [180, 0, 0], "1": [0, 0, 0], "2": [90, 0, 0], "3": [270, 0, 0],
          "4": [0, 0, 270], "5": [0, 0, 90]}


def shulker(colour):
    """One box, its sides, top and bottom each a tile of its own."""
    side, top, bottom = (FACE_TILE % (colour, part) for part in ("side", "top", "bottom"))
    art = {"north": side, "south": side, "east": side, "west": side,
           "up": top, "down": bottom}
    return {"default": [Cube((15.2, 15.2, 15.2), (0.4, 0.4, 0.4), texture=art,
                             window={face: (0, 0, 16, 16) for face in art})]}


def main():
    print("writing the shulker boxes")
    for colour in COLOURS:
        family = "shulker_box_%s" % colour
        tables.write(family, shulker(colour), center=(8, 7.6, 8))
        tables.rules(family, turn_by=[{"entity": "facing"}])
        tables.turns(family, FACING)
        tables.define(["%s_shulker_box" % colour], family)
    for block, colour in EXTRA.items():
        family = "shulker_box_%s" % colour
        tables.write(family, shulker(colour), center=(8, 7.6, 8))
        tables.rules(family, turn_by=[{"entity": "facing"}])
        tables.turns(family, FACING)
        tables.define([block], family)
    print("   %d colours" % (len(COLOURS) + 1))


if __name__ == "__main__":
    main()
