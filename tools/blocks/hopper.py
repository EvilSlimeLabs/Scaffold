"""The hopper, in its two mountings and locked or not.

A hopper is three boxes: the bowl across the top of its block, the neck under
it, and the spout the items leave by. Where the spout sits is the mounting --
under the middle for a hopper pointing down, out at one side for one pointing
into the block beside it -- and `armor_stand_geo_class.make_block` picks between
them from `facing_direction`, not from a state of its own.

**`blocks.json` gives the hopper `hopper_inside` on its down slot**, and that is
a slot rather than a face: the engine's own model uses it for the floor of the
basin, which is a dark plate, and read literally it puts that plate on the
underside of the block where the banded metal of `hopper_outside` belongs. Every
face here is named outright for that reason. The basin floor itself is not drawn
at all, because the bowl is a solid box and `hopper_top` already pictures the
recess.

**Each box reads the band of the tile it stands in.** The bowl is the top seven
rows of `hopper_outside`, the neck the six under that and the spout the rest,
which is how the block is painted in game. The family used to carry one window
for all three boxes, so the neck and the spout each wore a whole tile stretched
down to four pixels.

**`toggle_bit` is the lock.** A hopper wired to a redstone signal stops moving
items, and Bedrock records that as `toggle_bit` on the block. Vanilla draws no
difference, so the locked forms here are the unlocked ones' shapes under their
own names; what they buy is somewhere for a locked hopper to be drawn
differently, by a texture pack or by a later change here, without any of the
state plumbing having to be done again.

The forms are named the way every other joined form is: the mounting, then the
state's value. `make_block` reads `<mounting>-<value>` before it reads the value
on its own, so `side-1` is a locked hopper on a wall and a hopper carrying no
`toggle_bit` at all still lands on plain `side`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tools.blocks.geometry import Cube, FACES
from tools.blocks.tables import write

TOP = "textures/blocks/hopper_top"
OUTSIDE = "textures/blocks/hopper_outside"

BOWL = ((16, 7, 16), (0, 9, 0))          # the wide part, across the top
NECK = ((8, 6, 8), (4, 4, 4))            # the funnel under it
SPOUT = (4, 4, 4)                        # and the mouth items leave by

## where the mouth sits, which is the whole of the difference between a hopper
## pointing down and one pointing into the block beside it
SPOUTS = {"default": (6, 1, 6), "side": (1, 5, 6)}

## the value of `toggle_bit` that means the hopper is locked; the unlocked one
## is not written, so it falls back to the plain mounting
LOCKED = "1"


def boxes(mounting):
    """The three boxes of one mounting, each painted where it stands."""
    ## the bowl alone shows the rim, and only from above
    skin = {face: OUTSIDE for face in FACES}
    skin["up"] = TOP
    bowl = Cube(BOWL[0], BOWL[1], texture=skin)
    neck = Cube(NECK[0], NECK[1], texture=OUTSIDE)
    spout = Cube(SPOUT, SPOUTS[mounting], texture=OUTSIDE)
    return [bowl, neck, spout]


def main():
    print("writing the hopper")
    forms = {}
    for mounting in SPOUTS:
        for name in (mounting, "%s-%s" % (mounting, LOCKED)):
            forms[name] = boxes(mounting)
    write("hopper", forms)


if __name__ == "__main__":
    main()
