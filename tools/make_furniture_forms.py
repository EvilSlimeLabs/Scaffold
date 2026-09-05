"""Give the blocks that are furniture a shape worth the name.

    python tools/make_furniture_forms.py

A lectern is a stand with a sloped desk on it, an enchanting table is a slab
with a book floating above, a bed is a mattress on legs and a conduit is a small
cage hanging in the middle of its block. Drawn as full cubes, which is what a
lookup with one entry gives them, they read as stone blocks in a row and say
nothing about what they are.

These also carry the states that change what they look like. A bed is two
blocks, head and foot, and the two are not the same shape or the same texture. A
conduit is open when it is powered and closed when it is not. A daylight
detector has a second block id for its inverted form, with a top of its own.

Nothing here is needed at run time. Re-run `tools/make_low_geometry.py`
afterwards: most of these have more than two cubes and want a simple form.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import lookup_writer
from make_block_forms import Cube, FACES, build

LOOKUPS = os.path.join(ROOT, "structura", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")

BLOCKS = "textures/blocks/%s"


def write(family, forms, center=(8, 8, 8)):
    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes, center)
    lookup_writer.put(SHAPES, family, shapes, tight=True)
    lookup_writer.put(UV, family, uvs, tight=True)
    print("   %-22s %s" % (family, ", ".join(forms)))


def define(blocks, family):
    table = json.load(io.open(DEFINITION, encoding="utf-8"))
    for block in blocks:
        table[block] = family
    body = json.dumps(table, indent="\t", ensure_ascii=False,
                      separators=(",", ":"))
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(body + "\n")


def turns(family, table):
    """Give a family a rotation entry, numbers and words alike."""
    stored = json.load(io.open(ROTATION, encoding="utf-8"))
    stored[family] = table
    lookup_writer.put(ROTATION, family, table, tight=True)


## the four ways a block that faces one way can be turned, both as Bedrock's
## numbers and as the words newer versions write instead
FACING = {"0": [0, 0, 0], "1": [0, 90, 0], "2": [0, 180, 0], "3": [0, 270, 0],
          "south": [0, 0, 0], "west": [0, 90, 0], "north": [0, 180, 0],
          "east": [0, 270, 0]}


# --- daylight detector ------------------------------------------------------
#
# Three pixels tall, not a cube. The inverted detector is a block id of its own
# rather than a state, and the only thing that tells the two apart is the top:
# `daylight_detector_top` is a list of two, the plain one and the inverted.
DAYLIGHT = {"default": [Cube((16, 6, 16), (0, 0, 0))]}
DAYLIGHT_INVERTED = {"default": [Cube(
    (16, 6, 16), (0, 0, 0),
    texture={"up": BLOCKS % "daylight_detector_inverted_top",
             "down": "default", "north": "default", "south": "default",
             "east": "default", "west": "default"})]}


# --- spore blossom ----------------------------------------------------------
#
# It hangs from the ceiling: a small base against the block above and the
# blossom itself spread flat below it. Not a cube, which is what it was.
SPORE_BLOSSOM = {"default": [
    Cube((4, 3, 4), (6, 13, 6), BLOCKS % "spore_blossom_base"),
    Cube((14, 0.2, 14), (1, 12.8, 1), BLOCKS % "spore_blossom",
         window={face: (1, 1, 14, 14) for face in FACES})]}


# --- lectern ----------------------------------------------------------------
#
# A post on a base with a desk sloped over the top of it.
# The desk is one box leaning back.
LECTERN = {"default": [
    Cube((16, 2, 16), (0, 0, 0), BLOCKS % "lectern_base"),
    Cube((8, 10, 8), (4, 2, 4), BLOCKS % "lectern_front"),
    Cube((16, 4, 14), (0, 12, 1), texture={
        "up": BLOCKS % "lectern_top", "down": BLOCKS % "lectern_base",
        "north": BLOCKS % "lectern_sides", "south": BLOCKS % "lectern_sides",
        "east": BLOCKS % "lectern_sides", "west": BLOCKS % "lectern_sides"},
         rotation=(-22, 0, 0))]}


# --- enchanting table -------------------------------------------------------
#
# Three quarters of a block, with the book above it. The book is two leaves
# leaning together, drawn from the table's own top texture: the book's own
# texture is an entity sheet the trimmed pack does not carry.
ENCHANTING = {"default": [
    Cube((16, 12, 16), (0, 0, 0)),
    Cube((8, 0.2, 6), (4, 14, 5), BLOCKS % "enchanting_table_top",
         rotation=(0, 0, 20)),
    Cube((8, 0.2, 6), (4, 14, 5), BLOCKS % "enchanting_table_top",
         rotation=(0, 0, -20))]}


# --- conduit ----------------------------------------------------------------
#
# A small cage in the middle of the block.
#
# **The cage is `conduit_base` and neither of the two shells.** That file is
# 24x12, which is the unwrap of a box six by six by six laid out the way Bedrock
# lays one out: the top and the bottom across the first six rows, then the four
# walls in a strip under them. Six by six by six is the cage. The two 8x8 shells
# beside it are the eye that opens once the conduit is running, and a conduit in
# a structure is not running, so both of them were the wrong picture.
CONDUIT_BASE = BLOCKS % "conduit_base"
CLOSED = BLOCKS % "conduit_closed"
OPEN = BLOCKS % "conduit_open"
CAGE = 6
CAGE_ART = {"up": (CAGE, 0, CAGE, CAGE), "down": (CAGE * 2, 0, CAGE, CAGE),
            "west": (0, CAGE, CAGE, CAGE), "south": (CAGE, CAGE, CAGE, CAGE),
            "east": (CAGE * 2, CAGE, CAGE, CAGE),
            "north": (CAGE * 3, CAGE, CAGE, CAGE)}
SHELL = {face: (0, 0, 8, 8) for face in FACES}

CONDUIT = {
    "0": [Cube((CAGE, CAGE, CAGE), ((16 - CAGE) // 2,) * 3, CONDUIT_BASE,
               window=CAGE_ART)],
    "1": [Cube((CAGE, CAGE, CAGE), ((16 - CAGE) // 2,) * 3, CONDUIT_BASE,
               window=CAGE_ART),
          Cube((8, 8, 8), (4, 4, 4), OPEN, window=SHELL)],
}
CONDUIT["default"] = CONDUIT["0"]

## A conduit has no direction in its states, so nothing turns it today. The
## table is here so that a state which does turn up finds an entry rather than
## leaving the block unrotated and silent: both the four cardinals and the
## sixteen steps a sign uses.
CONDUIT_TURNS = dict(FACING)
CONDUIT_TURNS.update({str(n): [0, round(n * 22.5, 1), 0] for n in range(16)})


# --- beds -------------------------------------------------------------------
#
# Two blocks, head and foot, each a mattress on two legs. Bedrock tells the
# halves apart with `head_piece_bit`, which arrives as the shape variant.
#
# **A bed lies along x, with its head at x16.** The tiles say so: on
# `bed_head_top` and `bed_head_side` the pillow is the right half of the
# picture, and on `bed_head_side` the leg is the last three pixels of it, so the
# picture runs foot to head across its own width. A face's window runs along x
# on the top and along the block's own axis on the sides, so a bed lying along z
# has its pillow painted down one side of the mattress instead of across the
# head of it.
#
# **Two legs a block, not four.** `bed_feet_end` carries a leg at each corner,
# which is one end of the bed seen from outside, and `bed_feet_side` carries one,
# at the foot. Four to a block puts eight under a bed.
#
# The legs are drawn from the bed's own tile too, off the three by three patch
# under the mattress, rather than from planks.
BED_TALL = 6
BED_UP = 3
LEG = 3
# **The leg is drawn at the end of the tile the leg is at.** `bed_feet_side`
# carries it in the first three pixels and `bed_head_side` in the last three,
# because each picture runs foot to head. Both halves read the foot tile's
# corner, so the head's legs came out blank.
#
# **And one long side has to read its picture the other way round.** The two
# faces of a box opposite each other run their windows in opposite directions,
# so the pillow ends up at the head on one and at the foot on the other. A
# window that starts at the far edge and runs back is how Bedrock reads a
# picture mirrored.
BED_FACE = (0, 7, 16, BED_TALL)         # the mattress, on the side and the end
BED_BACK = (16, 7, -16, BED_TALL)       # the same, the other way round


## A bed's colour is in the block entity, not in its states, and there is one
## set of tiles per colour: `tools/make_bed_textures.py` recolours the red
## tiles the pack ships. `core.ENTITY_ADDS` joins the colour to the half, so a
## variant is named `<head_piece_bit>-<colour>`.
BED_COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime",
               "pink", "gray", "silver", "cyan", "purple", "blue", "brown",
               "green", "red", "black"]


def bed(part, head, colour):
    """One block of a bed: the mattress, and the two legs at its outer end.

    `head` says which end of the block the legs stand at, which is the end away
    from the other half, and which end of the tile their picture is at.
    """
    named = "bed_%s_%s_%%s" % (colour, part)
    top = BLOCKS % (named % "top")
    side = BLOCKS % (named % "side")
    end = BLOCKS % (named % "end")
    mattress = Cube((16, BED_TALL, 16), (0, BED_UP, 0), texture={
        "up": top, "down": BLOCKS % "planks_oak",
        ## the bed lies along x, so its ends are the x faces and its long sides
        ## the z ones
        "east": end, "west": end, "north": side, "south": side},
        window={"up": (0, 0, 16, 16), "down": (0, 0, 16, 16),
                "east": BED_FACE, "west": BED_FACE,
                "north": BED_FACE, "south": BED_BACK})
    leg_art = (head, 16 - LEG, LEG, LEG)
    legs = [Cube((LEG, BED_UP, LEG), (head, 0, z), side,
                 window={face: leg_art for face in FACES})
            for z in (0, 16 - LEG)]
    return [mattress] + legs


BEDS = {"%d-%d" % (half, number): bed(part, head, colour)
        for half, (part, head) in enumerate((("feet", 0), ("head", 16 - LEG)))
        for number, colour in enumerate(BED_COLOURS)}
## a bed with no entity beside it keeps its half and falls back to red, which is
## the colour the pack's own tiles are drawn in
BEDS["0"] = bed("feet", 0, "red")
BEDS["1"] = bed("head", 16 - LEG, "red")
BEDS["default"] = BEDS["0"]

## The model lies along x while the tables put a block at rest facing south, so
## every facing carries the quarter turn that takes +x round to +z.
BED_FACING = {name: [0, (turn[1] + 270) % 360, 0]
              for name, turn in FACING.items()}


def main():
    print("writing the furniture")
    write("daylight", DAYLIGHT)
    write("daylight_inverted", DAYLIGHT_INVERTED)
    define(["daylight_detector_inverted"], "daylight_inverted")

    write("spore_blossom", SPORE_BLOSSOM)
    define(["spore_blossom"], "spore_blossom")

    write("lectern", LECTERN)
    write("enchanting_table", ENCHANTING)
    write("conduit", CONDUIT)
    turns("conduit", CONDUIT_TURNS)
    write("bed", BEDS)
    ## a lectern and a bed both face somewhere; an enchanting table does not
    turns("lectern", FACING)
    turns("bed", BED_FACING)
    print("now re-run tools/make_low_geometry.py")


if __name__ == "__main__":
    main()
