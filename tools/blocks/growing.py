"""Give a block the form and the face it has at each stage of its life.

    python -m tools.blocks.growing

A crop is not one block. Wheat has eight textures, one per stage of growth, and
a lookup that names only the last of them draws a field of seedlings as a field
ready to harvest. The same is true of a cocoa pod, which changes size as well as
texture, of a sweet berry bush, of a turtle egg clutch, and of a composter,
which fills up.

Each of these is written here as a family of its own with one variant per state
value, because the shared `cross_texture` family cannot carry them: a variant
named "3" on that family would answer for every cross shaped block in the game
that happened to be in state 3.

The stage textures are named directly rather than through `terrain_texture.json`,
which mostly has no entry for them: `wheat_stage_0` is a file in the pack and
nothing points at it. A literal path in an `overwrite` is read as given.

Nothing here is needed at run time. Re-run `tools/blocks/simplify.py`
afterwards if any of these gains a third cube.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build, px

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")

BLOCKS = "textures/blocks/%s"


def load(path):
    return json.load(io.open(path, encoding="utf-8"))


def write(family, forms, center=(8, 8, 8)):
    """Replace one family's shapes and UV windows."""
    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes, center)
    lookup_writer.put(SHAPES, family, shapes, tight=True)
    lookup_writer.put(UV, family, uvs, tight=True)
    print("   %-22s %d forms" % (family, len(forms)))


def define(blocks, family):
    """Point block ids at a family, leaving the rest of the file alone."""
    table = load(DEFINITION)
    for block in blocks:
        table[block] = family
    ## the file is one key a line, tab indented, with no space after the colon;
    ## writing it any other way reformats three thousand lines
    body = json.dumps(table, indent="\t", ensure_ascii=False,
                      separators=(",", ":"))
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(body + "\n")


# --- the plants that grow where they stand ----------------------------------
#
# A crop is two crossed panes, the same pair `cross_texture` draws every plant
# in the game with, and the only thing that changes as it grows is the texture
# they wear. Each pane reads the whole tile, as a plant texture is drawn to be
# seen whole rather than mapped onto a box.
WHOLE_TILE = {face: (0, 0, 16, 16) for face in FACES}
CROSS = [((0.16, 16, 16), (8, 0, 0)), ((16, 16, 0.16), (0, 0, 8))]


def growing(stages):
    """One form per stage, the panes wearing that stage's texture."""
    forms = {}
    for stage, name in enumerate(stages):
        painted = BLOCKS % name
        forms[str(stage)] = [Cube(size, at, painted, window=WHOLE_TILE)
                             for size, at in CROSS]
    forms["default"] = forms[str(len(stages) - 1)]
    return forms


## Bedrock counts a crop's growth in `growth`, which runs to 7 for the ones that
## take eight steps and to 3 for the ones that take four. A stage with no
## texture of its own repeats the one before it, the way the game does.
CROPS = {
    "wheat": ["wheat_stage_%d" % n for n in range(8)],
    "carrots": ["carrots_stage_%d" % n for n in (0, 0, 1, 1, 2, 2, 2, 3)],
    "potatoes": ["potatoes_stage_%d" % n for n in (0, 0, 1, 1, 2, 2, 2, 3)],
    "beetroot": ["beetroots_stage_%d" % n for n in (0, 0, 1, 1, 2, 2, 3, 3)],
    "nether_wart": ["nether_wart_stage_%d" % n for n in (0, 1, 1, 2)],
    "torchflower_crop": ["torchflower_crop_stage_0", "torchflower_crop_stage_1",
                         "torchflower_crop_stage_1"],
    "sweet_berry_bush": ["sweet_berry_bush_stage%d" % n for n in range(4)],
}


# --- cocoa ------------------------------------------------------------------
#
# A cocoa pod grows on the side of a jungle log and gets larger as it ripens,
# so both the box and the texture change. The sizes are vanilla's: 4, 6 and 8
# across, hanging from the top of the block and standing off the log it grew on.
#
# Each stage's tile holds three pictures rather than one: the pod's top in the
# corner, the pod's side to the right of it, and the stalk it hangs by drawn
# diagonally between them. A face working its own window out from where the pod
# sits reads across all three and comes out as bark, which is what a cocoa pod
# was drawn with.
#
# The corner and the side move as the pod grows, so each stage names its own.
COCOA_ART = {
    ## stage: the pod's top, then the pod's side
    "0": ((0, 0, 4, 4), (11, 4, 4, 5)),
    "1": ((0, 0, 6, 6), (9, 4, 6, 7)),
    "2": ((0, 0, 7, 7), (7, 4, 8, 9)),
}


def pod(size, at, stage):
    """One cocoa pod, its top and bottom off the corner of the tile and its
    four sides off the picture beside it."""
    cap, side = COCOA_ART[stage]
    return Cube(size, at, BLOCKS % ("cocoa_stage_%s" % stage), window={
        "up": cap, "down": cap,
        "north": side, "south": side, "east": side, "west": side})


COCOA = {
    "0": [pod((4, 5, 4), (6, 7, 11), "0")],
    "1": [pod((6, 7, 6), (5, 5, 9), "1")],
    "2": [pod((8, 9, 8), (4, 3, 7), "2")],
}
COCOA["default"] = COCOA["2"]


# --- turtle eggs ------------------------------------------------------------
#
# One to four eggs in a clutch, and the count is a state of its own. A big egg
# is 4 by 7 by 4 and a small one 4 by 5 by 4; vanilla mixes them as the clutch
# grows. The cracking is the texture rather than the shape, and comes through
# `variants.json`, because turtle_egg's terrain texture is a list of three.
#
# The tile holds an egg drawn several times over rather than one picture: the
# side of one down the left of it, four across the top of that, and the smaller
# egg's own to the right. A face working its own window out from where the egg
# stands reads whichever eggs happen to line up with it, which is why a clutch
# came out as pale boxes with corners of other eggs on them. Every face takes an
# egg the size of that face instead.
#
# **And the two sizes are drawn in different corners of the tile.** The big
# egg's side is four across and seven down at (1, 4) and the small one's is four
# by five at (10, 10); the caps are four by four, the tops at (0, 0) and (6, 7)
# and the two undersides side by side along the bottom at (0, 11) and (4, 11).
# One window for both sizes takes the big egg's from a column that is empty for
# its first pixel and the small egg's from wherever seven rows down happens to
# land, which is what left eggs with a clear stripe up them.
BIG = (4, 7, 4)
SMALL = (4, 5, 4)
## side, top and underside, per size, all read straight out of the tile
EGG_ART = {
    BIG: {"side": (1, 4, 4, 7), "up": (0, 0, 4, 4), "down": (0, 11, 4, 4)},
    SMALL: {"side": (10, 10, 4, 5), "up": (6, 7, 4, 4), "down": (4, 11, 4, 4)},
}


def egg(size, at):
    """One egg, every face reading an egg rather than a slice of the block."""
    art = EGG_ART[size]
    side = art["side"]
    return Cube(size, at, window={
        "north": side, "south": side, "east": side, "west": side,
        "up": art["up"], "down": art["down"]})


TURTLE_EGGS = {
    "one_egg": [egg(BIG, (6, 0, 6))],
    "two_egg": [egg(BIG, (3, 0, 6)), egg(SMALL, (9, 0, 7))],
    "three_egg": [egg(BIG, (2, 0, 5)), egg(SMALL, (8, 0, 3)),
                  egg(SMALL, (7, 0, 9))],
    "four_egg": [egg(BIG, (2, 0, 5)), egg(SMALL, (8, 0, 3)),
                 egg(SMALL, (7, 0, 9)), egg(SMALL, (11, 0, 8))],
}
TURTLE_EGGS["default"] = TURTLE_EGGS["one_egg"]


# --- composter --------------------------------------------------------------
#
# A box open at the top with compost rising inside it. The walls are the block's
# own sides, the floor its bottom, and the compost reads the second and third
# textures of `composter_top`, which is a list of three: the empty top, the
# compost, and the compost ready to take out.
COMPOST = BLOCKS % "compost"
READY = BLOCKS % "compost_ready"
WALLS = [Cube((16, 2, 16), (0, 0, 0)),               # the floor
         Cube((16, 14, 2), (0, 2, 0)),               # and four walls
         Cube((16, 14, 2), (0, 2, 14)),
         Cube((2, 14, 12), (0, 2, 2)),
         Cube((2, 14, 12), (14, 2, 2))]

## how high the compost stands at each level, in pixels, and vanilla stops
## raising it at seven: level eight is the same height, ready to take out
FILL = {1: 3, 2: 5, 3: 7, 4: 8, 5: 10, 6: 12, 7: 13, 8: 13}


def composter():
    forms = {"0": list(WALLS), "default": list(WALLS)}
    for level, height in FILL.items():
        texture = READY if level == 8 else COMPOST
        forms[str(level)] = WALLS + [
            Cube((12, height - 2, 12), (2, 2, 2), texture)]
    return forms


# --- seagrass ---------------------------------------------------------------
#
# Short seagrass is one plant, and the tall kind is two blocks with a texture
# each for its bottom and its top. `sea_grass_type` says which of the three a
# block is, and without it every one of them wore the tall top.
def panes(first, second):
    """The crossed pair, each pane with a texture of its own."""
    return [Cube(size, at, BLOCKS % name, window=WHOLE_TILE)
            for (size, at), name in zip(CROSS, (first, second))]


SEAGRASS = {
    "default": panes("seagrass", "seagrass"),
    "double_bot": panes("seagrass_doubletall_bottom_a",
                        "seagrass_doubletall_bottom_b"),
    "double_top": panes("seagrass_doubletall_top_a",
                        "seagrass_doubletall_top_b"),
}


# --- coral fans -------------------------------------------------------------
#
# A fan is a plant, not a block: crossed panes rather than the near cube both
# families were drawn as. The wall kind hangs off the side it grew on, which is
# what `coral_direction` says, and nothing was reading it.
CORAL_FAN = {"default": [Cube(size, at, window=WHOLE_TILE)
                         for size, at in CROSS]}
CORAL_WALL_FAN = {"default": [
    Cube((0.16, 16, 16), (8, 0, 2), window=WHOLE_TILE),
    Cube((16, 16, 0.16), (0, 0, 2), window=WHOLE_TILE)]}

## coral_direction on a wall fan, and coral_fan_direction on a ground one,
## which lies one of two ways round
CORAL_TURNS = {"0": [0, 0, 0], "1": [0, 90, 0], "2": [0, 180, 0],
               "3": [0, 270, 0]}


# --- big dripleaves ---------------------------------------------------------
#
# One block id is two different things. `big_dripleaf_head` says whether a block
# is the leaf you stand on or a length of the stalk holding one up, and nothing
# was reading it, so both were drawn as a near cube of whatever texture
# `blocks.json` happened to hand over.
#
# **Its faces are texture slots, not faces.** The entry reads `up:
# big_dripleaf_side2`, `down: big_dripleaf_side1`, `north: big_dripleaf_stem`
# and the leaf on the other three, because the game picks from those slots for
# its own model rather than painting them on the six sides of a cube. Taken
# literally, the leaf's top wears `side2`, which is four rows of edge profile
# over an empty tile, and the leaf is very nearly invisible from above. Every
# face here names the texture it wants outright.
LEAF_TOP = BLOCKS % "big_dripleaf_top"
LEAF_EDGE = BLOCKS % "big_dripleaf_side2"
LEAF_STEM = BLOCKS % "big_dripleaf_stem"

LEAF_THICK = 2
LEAF_AT = 13        # the surface you stand on, near the top of the block
STALK = 4           # the stalk is square and runs down the back of the leaf


def leaf():
    """The platform, textured top and bottom and edged with its own profile.

    The edge strip is the top four rows of `big_dripleaf_side2`; the rest of
    that tile is empty, so a face reading the whole of it shows nothing.
    """
    return Cube((16, LEAF_THICK, 16), (0, LEAF_AT, 0), texture={
        "up": LEAF_TOP, "down": LEAF_TOP,
        "north": LEAF_EDGE, "south": LEAF_EDGE,
        "east": LEAF_EDGE, "west": LEAF_EDGE}, window={
        "up": (0, 0, 16, 16), "down": (0, 0, 16, 16),
        "north": (0, 0, 16, LEAF_THICK), "south": (0, 0, 16, LEAF_THICK),
        "east": (0, 0, 16, LEAF_THICK), "west": (0, 0, 16, LEAF_THICK)})


def stalk(tall, at):
    """A length of stem, against the back of the block where the leaf hangs
    off it. A stalk block and the stub under a leaf stand in the same place, so
    a dripleaf several blocks tall lines up."""
    middle = (16 - STALK) // 2
    return Cube((STALK, tall, STALK), (middle, at, 0), texture=LEAF_STEM,
                window={face: (0, 0, 16, 16) for face in FACES})


BIG_DRIPLEAF = {
    ## big_dripleaf_head: the leaf, with a stub of stalk under it
    "1": [leaf(), stalk(LEAF_AT, 0)],
    ## and a plain length of the stalk
    "0": [stalk(16, 0)],
}
BIG_DRIPLEAF["default"] = BIG_DRIPLEAF["1"]

## minecraft:cardinal_direction, which the leaf hangs off the far side of
DRIPLEAF_TURNS = {"south": [0, 0, 0], "west": [0, 90, 0],
                  "north": [0, 180, 0], "east": [0, 270, 0],
                  "0": [0, 0, 0], "1": [0, 90, 0],
                  "2": [0, 180, 0], "3": [0, 270, 0]}


def turns(family, table):
    lookup_writer.put(os.path.join(LOOKUPS, "block_rotation.json"),
                      family, table, tight=True)


def main():
    print("writing the forms that change with a state")
    for family, stages in CROPS.items():
        write(family, growing(stages))
        ## every one of these is a block id as well as a family name
        define([family], family)

    write("cocoa", COCOA)
    write("turtle_egg", TURTLE_EGGS)
    write("composter", composter())
    define(["composter"], "composter")

    write("seagrass", SEAGRASS)
    ## only `seagrass`: blocks.json has no `sea_grass`, and a
    ## definition for a block the pack never declares raises
    define(["seagrass"], "seagrass")
    write("coral_fan", CORAL_FAN)
    write("coral_fan_wall", CORAL_WALL_FAN)
    turns("coral_fan", CORAL_TURNS)
    turns("coral_fan_wall", CORAL_TURNS)

    write("big_dripleaf", BIG_DRIPLEAF)
    turns("big_dripleaf", DRIPLEAF_TURNS)
    define(["big_dripleaf"], "big_dripleaf")
    print("re-run tools/blocks/simplify.py if any of these grew past two cubes")


if __name__ == "__main__":
    main()
