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

## A quad is a plane: thin enough to have no edge worth seeing. The same
## hundredth of a block the tables have always given a plant.
THIN = 0.16

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
    return [Cube((THIN, tall, LONG), (8 - THIN / 2.0, 0, 8 - LONG / 2.0),
                 texture, window=window, rotation=(0, TURN, 0)),
            Cube((LONG, tall, THIN), (8 - LONG / 2.0, 0, 8 - THIN / 2.0),
                 texture, window=window, rotation=(0, TURN, 0))]


# --- the plants that are only their cross ------------------------------------
#
# Seventy-odd blocks share `cross_texture`: flowers, saplings, mushrooms, grass,
# and everything else the game draws as a plant. They read whatever the block
# declares rather than naming a texture, which is what lets one family serve all
# of them.
CROSS_TEXTURE = {"default": crossed("default")}

# --- the two block tall flowers ----------------------------------------------
#
# A lower half and an upper half, each its own block, told apart by
# `upper_block_bit`. `tools/blocks/faces.py` pins the lower half to the down
# texture and the upper to the up one, because Bedrock puts something else
# entirely on side -- for a lilac the side texture is the sunflower's back.
DOUBLE_PLANT = {"default": crossed("default"), "top": crossed("default")}


# --- the sunflower, which has a face ------------------------------------------
#
# Every other double plant is its cross and nothing else. A sunflower carries a
# flower head as well: a plane of its own leaning back off the stem, yellow on
# the side it faces and green behind. Bedrock keeps the two pictures in
# `sunflower_additional`, a list of two, and a block reads a list by its variant
# -- which for a sunflower is the one index that means "sunflower". There is no
# variant that reaches the second entry, so the head names both outright.
#
# It is a family of its own for the same reason: the head belongs to one variant
# of `double_plant` and a shape family cannot vary by variant, only by state. The
# flattened block id `sunflower` is what modern structures carry, and
# `blocks.json` gives it its own textures. A structure written before the
# flattening holds `double_plant` with `double_plant_type`, and that keeps the
# plain cross.
SUN = BLOCKS % "double_plant_sunflower_%s"

## Where the head sits: a plane standing from y4 to y20, so the flower finishes
## above its own block the way the game draws it, and squarely on the block's
## north-south middle.
HEAD_TALL = 16
HEAD_WIDE = 16
HEAD_FOOT = 4

## **And a little east of the stem, so the two do not cross.** The stem is a
## two pixel column up the middle of the block and the flower's disc is the
## middle eight pixels of its own tile, so a head on the middle line puts green
## through the bottom of the flower.
##
## **East is the low side of x here, because a cube's offset inside its block is
## not mirrored and the block itself is.** `armor_stand_geo_class` writes a
## cube's origin as `-1*(x + offsets[0]) + xoff`: the block's place in the grid
## is negated, which is what turns structure x into Bedrock's model x, and the
## cube's own offset within the block is added to that untouched. So a cube
## written east of the middle of its block comes out west of it in game, while
## the picture on its faces stays where the table put it. Ten read as two pixels
## west; six is two pixels east.
HEAD_EAST = 6

## **It leans back, and the yellow face looks upward.** A quarter of a right
## angle about the north-south axis.
##
## **The sign is positive for the same reason east is the low side of x.** The
## block is mirrored in x on its way into the model, and a mirror reverses every
## turn about y and about z. `spun` and `tools/checks/render.py` both work in the
## table's own space, where this reads as leaning the wrong way; in game it is
## the lean the flower wants. A negative angle here puts the flower's face at the
## floor.
HEAD_LEAN = 22.5

## **The two sides of the head read the picture opposite ways.** A plane's faces
## run their windows in opposite directions, so the back takes a window that
## starts at the far edge and runs back -- which is how Bedrock reads a picture
## mirrored -- and the front takes the plain one. The other four faces are the
## head's rim, a fifth of a pixel thick.
HEAD_ART = dict(WHOLE_TILE, west=(16, 0, -16, 16))
HEAD_FACES = dict({face: SUN % "front" for face in FACES}, west=SUN % "back")


def head():
    """The flower itself: a plane facing east and leaning back over the stem.

    Turned about its own middle, which is where Bedrock turns a cube carrying a
    rotation and no pivot of its own, so the plane stays exactly where it is
    written here and only tilts. Turning it about the middle of the block
    instead would drag it off the stem by an amount nobody reading this could
    predict.
    """
    return Cube((THIN, HEAD_TALL, HEAD_WIDE),
                (HEAD_EAST - THIN / 2.0, HEAD_FOOT, 8 - HEAD_WIDE / 2.0),
                HEAD_FACES, window=HEAD_ART, rotation=(0, 0, HEAD_LEAN))


## **The upper stem stops where the flower starts.** `double_plant_sunflower_top`
## is empty above its eighth row -- the stalk only reaches the flower's underside
## -- and the flower's own disc starts at y8. Left a full sixteen tall, the empty
## top half of each stem quad crossed the flower and blanked the parts of it
## behind, because a transparent texel still takes the depth it stands at.
## Cropped to eight, the stalk meets the disc exactly and the two never cross.
STEM_TALL = 8

SUNFLOWER = {"default": crossed("@down"),
             "top": crossed("@up", tall=STEM_TALL) + [head()]}


def main():
    print("writing the plants")
    tables.write("cross_texture", CROSS_TEXTURE)
    ## the turn is in the shape now, so the table that tried to say it would be
    ## applied a second time -- and only where a caller happened to pass a
    ## rotation, which is the renderer and never the game
    tables.unturn("cross_texture")

    tables.write("double_plant", DOUBLE_PLANT)

    tables.write("sunflower", SUNFLOWER)
    tables.define(["sunflower"], "sunflower")

    print("now re-run tools/blocks/faces.py and tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
