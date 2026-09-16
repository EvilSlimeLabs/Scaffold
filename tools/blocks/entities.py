"""The entities Scaffold draws, as shape families like any other.

    python -m tools.blocks.entities

An entity is not in a structure's `block_indices` at all. It is a whole record
in `structure.entities` with a world position of its own, so nothing in the
palette marks the cell it stands in and no lookup table could ever have reached
it. `scaffold.core.ENTITY_MODELS` is what bridges that: it names, per entity
identifier, the pseudo block id to draw and which of the entity's own fields
picks the form. From there an entity is an ordinary block -- it resolves through
`block_definition.json` into a family here, wears a shape and a UV window, is
turned by a rotation table, is counted on the block list and is simplified for
low geometry, all by the machinery that was already there.

**Only the cushion so far.** It is 26.50's first placeable entity that a builder
would want marked out, and it is the reason the pipeline exists; anything added
later is a `ENTITY_MODELS` entry and a family below.

Nothing here is needed at run time. Re-run `tools/blocks/simplify.py` afterwards
if a family here ever grows past two cubes.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

## the entity table is shipped code and both sides need it, so the colours are
## taken from the runtime rather than spelled again here
from scaffold.core import ENTITY_MODELS
from tools.blocks.geometry import Cube, FACES, on_sheet, unwrap
from tools.blocks.tables import define, turns, write


# --- cushions ---------------------------------------------------------------
#
# `models/entity/cushion.geo.json` in bedrock-samples is one box, sixteen across
# and four tall, on a 64x64 sheet at UV 0,0 with no per-face rectangles -- so it
# is laid out by Bedrock's own box unwrap and `unwrap` reproduces it exactly.
#
# **Its colour is a whole entity texture rather than a tile**, one file per dye
# under `textures/entity/cushion/`, which is why each of the sixteen is a form
# of its own here rather than a variant picked out of a terrain_texture list.
# The order is `controller.render.cushion`'s `Array.skins`, indexed by
# `query.variant`, which is the entity's own `Variant` field: black first and
# white last. That is the dye order rather than the wool order, the same way a
# banner's `Base` counts, so reading it as wool would give every cushion the
# colour across the wheel from its own.
CUSHION_SHEET = 64
CUSHION_TALL = 4

CUSHION = ENTITY_MODELS["minecraft:cushion"]
CUSHION_COLOURS = CUSHION["forms"]

## A ghost block that fills its cell is drawn a shade under it so the real thing
## covers the mark rather than flickering against it. A cushion fills its block
## across x and z and is four pixels tall, so only the two wide ways shrink.
CUSHION_WIDE = 15.2
CUSHION_INSET = (16 - CUSHION_WIDE) / 2


def cushion(colour):
    """One cushion, textured from its own entity sheet."""
    sheet = "textures/entity/cushion/%s_cushion" % colour
    ## the box the model draws, which is what the sheet is laid out for; the
    ## cube below is a shade smaller but reads the same rectangles
    rectangles = unwrap((0, 0), (16, CUSHION_TALL, 16))
    texture, window = {}, {}
    for face in FACES:
        texture[face], window[face] = on_sheet(sheet, rectangles[face],
                                               CUSHION_SHEET)
    return [Cube((CUSHION_WIDE, CUSHION_TALL, CUSHION_WIDE),
                 (CUSHION_INSET, 0, CUSHION_INSET),
                 texture=texture, window=window)]


## keyed by the colour rather than by the number the entity carries, because
## `core.entity_form` turns one into the other before it asks for a shape and a
## table nobody can read is a table nobody can check
CUSHIONS = {colour: cushion(colour) for colour in CUSHION_COLOURS}
## an entity with no Variant field, or one naming a colour that does not exist,
## is drawn in the colour the behaviour pack's own default value names
CUSHIONS["default"] = CUSHIONS[CUSHION["fallback"]]

## **A yaw, quantised, rather than a block state.** An entity is not placed on a
## grid of facings: it carries a float `Rotation` and `core.entity_turn` rounds
## it to the nearest quarter. Minecraft's yaw is 0 at south and climbs
## clockwise through west, so these are the four compass turns every other
## family here uses, keyed by the number the rounding produces.
CUSHION_TURNS = {"0": [0, 0, 0], "90": [0, 90, 0],
                 "180": [0, 180, 0], "270": [0, 270, 0]}


def main():
    print("writing the entity forms")
    write("cushion", CUSHIONS)
    turns("cushion", CUSHION_TURNS)
    define(["cushion"], "cushion")


if __name__ == "__main__":
    main()
