"""Draw a plant as the X the game draws it as, and give the sunflower its head.

    python -m tools.blocks.plants

A plant is not a box. The game draws it with `cross_texture`: two quads standing
on the block's **diagonals**, corner to corner, so the plant reads as something
with a front from wherever you walk up to it and never as a flat card.

**Scaffold drew a plus instead.** The two quads were square to the block, one in
the x-y plane and one in the y-z plane, which from above is a `+` rather than an
`X`. `cross_texture` carried a rotation table turning it forty-five degrees,
which looks like the missing half turn and is not: `make_block` only looks a
rotation up when the block hands it a rotation state, and a flower has none. So
`rot` came back None, nothing was looked up, and the table's entries were dead
weight -- except in `tools/checks/render.py`, which passes `rot=0` and so found
the `"0"` entry and drew the X the game never showed. That is why a poppy
rendered here as an X and in game as a plus.

**So the turn belongs in the shape.** Both quads are turned forty-five degrees
about the middle of the block as cubes, which needs no state and no table, and
the renderer and the game then agree. `double_plant` never had a rotation table
at all, which is why the two block tall flowers were a plus in both.

**And a turned quad has to be longer.** Sixteen across turned forty-five degrees
spans eleven and a bit, so the X sits well inside the block with a gap at every
corner. Vanilla stretches its quads as it turns them -- `rescale` in the Java
model -- and this does the same by writing the stretched length outright.

Nothing here is needed at run time. Re-run `tools/blocks/faces.py` and then
`tools/blocks/simplify.py` afterwards; `tools/generate.py` already does.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables
from tools.blocks.geometry import Cube, FACES

BLOCKS = "textures/blocks/%s"

## A quad is a plane, with no thickness and only its two faces drawn, which is
## also what lets a pack cut it down to the part of its picture with anything
## in it.
THIN = 0

## **How long a quad is once it is turned.** Vanilla runs its quads from 0.8 to
## 15.2 and stretches them as it turns them, so they finish on the block's
## diagonal rather than inside it. Fourteen and two fifths across the square is
## that much times root two across the diagonal.
SPAN = 14.4
LONG = round(SPAN * math.sqrt(2), 4)

## the turn that makes the plus an X. Square to the block the two quads are a
## plus; a quarter of a right angle each way is the pair of diagonals.
TURN = 45.0

## a plant texture is drawn to be seen whole rather than mapped onto a box, so
## every face reads the whole tile
WHOLE_TILE = {face: (0, 0, 16, 16) for face in FACES}


def crossed(texture, window=None, tall=16):
    """Two quads on the block's diagonals, both wearing one picture.

    `tall` crops the pair to the bottom of their tile, for a picture whose top
    rows are empty. **A quad that reaches past its own picture is not free.** A
    ghost block is drawn with blending rather than an alpha test, so a
    transparent texel still takes the depth it stands at and blanks whatever is
    behind it: an empty half-quad crossing another piece of the same block cuts
    a hole in it. The sunflower's stem is what showed that, by cutting pieces
    out of its own flower.
    """
    window = window or {face: (0, 16 - tall, 16, tall) for face in FACES}

    def only(faces):
        return {face: (window[face] if face in faces else (0, 0, 0, 0)) for face in FACES}
    return [Cube((THIN, tall, LONG), (8 - THIN / 2.0, 0, 8 - LONG / 2.0),
                 texture, window=only(("east", "west")), rotation=(0, TURN, 0)),
            Cube((LONG, tall, THIN), (8 - LONG / 2.0, 0, 8 - THIN / 2.0),
                 texture, window=only(("north", "south")), rotation=(0, TURN, 0))]


# --- the plants that are only their cross ------------------------------------
#
# Seventy-odd blocks share `cross_texture`: flowers, saplings, mushrooms, grass,
# and everything else the game draws as a plant. They read whatever the block
# declares rather than naming a texture, which is what lets one family serve all
# of them.
CROSS_TEXTURE = {"default": crossed("default")}

# --- the vines that carry glow berries ---------------------------------------
#
# **The berries are in the block id, not in a state.** `cave_vines` is a bare
# vine, and `cave_vines_body_with_berries` and `cave_vines_head_with_berries`
# are separate blocks. Their terrain_texture entries are lists of two -- the
# plain picture and the one with berries on it -- and a list is indexed by a
# *variant*, which is read off a block state. These blocks have no state that
# says so, so the plain first entry was drawn and a lit vine full of glow
# berries came out as a bare one.
#
# Naming the berry texture outright is what settles it, which is what a family
# of their own is for.
BERRY_BODY = "textures/blocks/cave_vines_body_berries"
BERRY_HEAD = "textures/blocks/cave_vines_head_berries"

CAVE_VINES_BERRIES = {"default": crossed(BERRY_BODY)}
CAVE_VINES_HEAD_BERRIES = {"default": crossed(BERRY_HEAD)}

# --- the two block tall flowers ----------------------------------------------
#
# A lower half and an upper half, each its own block, told apart by
# `upper_block_bit`. `tools/blocks/faces.py` pins the lower half to the down
# texture and the upper to the up one, because Bedrock puts something else
# entirely on side -- for a lilac the side texture is the sunflower's back.
DOUBLE_PLANT = {"default": crossed("default"), "top": crossed("default")}

# --- kelp ---------------------------------------------------------------------
#
# Kelp is the crossed planes, but the tip of a stalk reads `kelp_top_bulb`, a
# list with an entry per `kelp_age`, so it picks its picture by that state. Age
# 25 Kelp adds the flowering tip as the twenty-sixth.
KELP = {"default": crossed("default")}


def main():
    print("writing the plants")
    tables.write("cross_texture", CROSS_TEXTURE)
    ## the turn is in the shape now, so the table that tried to say it would be
    ## applied a second time -- and only where a caller happened to pass a
    ## rotation, which is the renderer and never the game
    tables.unturn("cross_texture")

    tables.write("double_plant", DOUBLE_PLANT)
    tables.write("kelp", KELP)
    tables.rules("kelp", texture_by={"state": "kelp_age"})
    tables.unturn("kelp")
    tables.define(["kelp"], "kelp")


    tables.write("cave_vines_berries", CAVE_VINES_BERRIES)
    tables.define(["cave_vines_body_with_berries"], "cave_vines_berries")
    tables.write("cave_vines_head_berries", CAVE_VINES_HEAD_BERRIES)
    tables.define(["cave_vines_head_with_berries"], "cave_vines_head_berries")

    print("now re-run tools/blocks/faces.py and tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
