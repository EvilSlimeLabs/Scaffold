"""Give the blocks that are drawn as an X the X, and the right picture on it.

    python -m tools.blocks.crossed

Some blocks are not boxes at all. Fire is a sheet of flame the game hangs on
whatever is burning, and a pointed dripstone or a sulfur spike is a spike that
tapers to nothing. Drawn as a cube, which is what a lookup with one entry gives
them, fire is a solid block of flame and a spike is a stone box.

They are drawn here the way the pack draws a plant: two quads crossing at right
angles, so there is something to see from every side and nothing solid.

**A spike's picture is in its states, and the tables were reading its faces
instead.** `blocks.json` gives `pointed_dripstone` six textures -- tip, frustum,
middle, base and merge -- and hangs them on six texture slots. Those are slots
the engine picks from for a model of its own, not faces, so a block taking them
literally wears five different pictures at once and a different five depending
on which way it is looked at. Which one it should wear is `dripstone_thickness`,
and whether it points up or down is `hanging`; both are states, and both are in
the file name of the picture the pack already ships. So each form names its
texture outright.

A sulfur spike is the same block with a different quarry: the same two states,
the same five thicknesses, and its own ten pictures. Its merge is filed as
`tip_merge` and everything else matches.

Nothing here is needed at run time. Re-run `tools/blocks/simplify.py`
afterwards.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")

BLOCKS = "textures/blocks/%s"
## a quad is a plane, not a box: thin enough to have no edge worth seeing
THIN = 0.2


def write(family, forms):
    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes)
    lookup_writer.put(SHAPES, family, shapes, tight=True)
    lookup_writer.put(UV, family, uvs, tight=True)
    print("   %-20s %s" % (family, ", ".join(sorted(forms))))


def define(blocks, family):
    table = json.load(io.open(DEFINITION, encoding="utf-8"))
    for block in blocks:
        table[block] = family
    body = json.dumps(table, indent="\t", ensure_ascii=False,
                      separators=(",", ":"))
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(body + "\n")


def unturn(family):
    """Take away a rotation table, for a family that reads no rotation state.

    A cross has no facing of its own, so nothing ever looks one up: `rot` comes
    back None and `_add_blocks_to_geo` does not ask. An entry left in the table
    is dead weight that reads as though it did something.
    """
    lookup_writer.drop(ROTATION, family)


def cross(texture, window=None):
    """Two quads crossing at right angles, both wearing one picture.

    Square to the block, the way `cross_texture` draws every plant in the pack,
    so a spike and a sapling are the same shape of thing.
    """
    window = window or {face: (0, 0, 16, 16) for face in FACES}
    return [Cube((THIN, 16, 16), (8 - THIN / 2.0, 0, 0), texture,
                 window=window),
            Cube((16, 16, THIN), (0, 0, 8 - THIN / 2.0), texture,
                 window=window)]


# --- fire -------------------------------------------------------------------
#
# `fire_0` on every face. `blocks.json` puts `fire_1` on the underside, which is
# the second sheet of the animation rather than a different picture, and a quad
# has no underside worth painting differently.
#
# Both files are a strip of frames one tile wide, and only the top left tile of
# a texture is read, so what a ghost fire wears is the first frame.
FIRE = {"default": cross("@up")}


# --- pointed dripstone and sulfur spikes -------------------------------------
#
# Five thicknesses, each drawn one way up on the floor and the other hanging
# from the ceiling, so ten pictures and ten forms. `hanging` arrives as 0 or 1
# and joins `dripstone_thickness` the way core.py joins shape states, which
# sorts them by the name of the state: thickness first, then hanging.
THICKNESSES = ("tip", "frustum", "middle", "base", "merge")
## a spike hanging from the ceiling points down, and that is the picture filed
## under "down"
POINTING = {"1": "down", "0": "up"}
## sulfur files its merge under the name of the tip it merges into
SULFUR_NAMES = {"merge": "tip_merge"}


def spikes(prefix, names=None):
    """One form per thickness per way up, each naming its own picture."""
    names = names or {}
    forms = {}
    for thickness in THICKNESSES:
        for hanging, way in POINTING.items():
            drawn = names.get(thickness, thickness)
            texture = BLOCKS % ("%s_%s_%s" % (prefix, way, drawn))
            forms["%s-%s" % (thickness, hanging)] = cross(texture)
    forms["default"] = forms["tip-0"]
    return forms


DRIPSTONE = spikes("pointed_dripstone")
SULFUR = spikes("sulfur_spike", SULFUR_NAMES)


def main():
    print("writing the blocks drawn as a cross")
    write("fire", FIRE)
    unturn("fire")
    define(["fire", "soul_fire"], "fire")

    write("pointed_dripstone", DRIPSTONE)
    unturn("pointed_dripstone")
    define(["pointed_dripstone"], "pointed_dripstone")

    write("sulfur_spike", SULFUR)
    unturn("sulfur_spike")
    define(["sulfur_spike"], "sulfur_spike")
    print("now re-run tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
