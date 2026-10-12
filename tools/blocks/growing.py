"""Give a block the form and the face it has at each stage of its life.

    python -m tools.blocks.growing

A crop is not one block. Wheat has eight textures, one per stage of growth, and
a lookup that names only the last of them draws a field of seedlings as a field
ready to harvest. The same is true of a sweet berry bush, and of a composter,
which fills up. Cocoa, turtle eggs, the dripleaves and the pitcher crop are
drawn from Java's models, in `tools/blocks/models.py`.

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

from tools.blocks import java
from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build, px
from tools.blocks import tables as _tables

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
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
    """Point block ids at a shape family."""
    _tables.define(blocks, family)


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


# --- the four planes of a crop ----------------------------------------------------
#
# Wheat, carrots, potatoes, beetroot and nether wart are Java's `crop`: four
# planes in a hash, two along each axis, four pixels in from the edges and sunk
# a pixel into the farmland. Seagrass is the same four standing on the floor,
# and a cactus the same four a pixel in, with a top and a bottom. Each plane
# shows the whole tile from both sides, the far side read backwards.

def planes(inset, low=0, along_x="#plant", along_z="#plant", tall=16):
    """Four planes `inset` pixels in from each side, from `low` up, as Java
    elements: two along x, reading `along_x`, and two along z."""
    near, far = inset, 16 - inset
    forward, backward = [0, 0, 16, 16], [16, 0, 0, 16]
    top = low + tall
    return [
        {"from": [near, low, 0], "to": [near, top, 16], "faces": {
            "west": {"uv": forward, "texture": along_z},
            "east": {"uv": backward, "texture": along_z}}},
        {"from": [far, low, 0], "to": [far, top, 16], "faces": {
            "west": {"uv": backward, "texture": along_z},
            "east": {"uv": forward, "texture": along_z}}},
        {"from": [0, low, near], "to": [16, top, near], "faces": {
            "north": {"uv": forward, "texture": along_x},
            "south": {"uv": backward, "texture": along_x}}},
        {"from": [0, low, far], "to": [16, top, far], "faces": {
            "north": {"uv": backward, "texture": along_x},
            "south": {"uv": forward, "texture": along_x}}},
    ]


def painted_with(**named):
    """A texture lookup for Java elements: each variable a file of its own."""
    return lambda name: {"texture": BLOCKS % named[name]} if name in named else None


CROP = planes(4, low=-1)


def planted(stages):
    """One form per stage of a crop, its planes wearing that stage's tile."""
    forms = {str(stage): java.form(CROP, painted_with(plant=name))
             for stage, name in enumerate(stages)}
    forms["default"] = forms[str(len(stages) - 1)]
    return forms


## the crops drawn as Java's `crop`; the rest of CROPS stay crossed
HASHED = ("wheat", "carrots", "potatoes", "beetroot", "nether_wart")

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


# --- composter --------------------------------------------------------------
#
# A box open at the top with compost rising inside it. The walls are the block's
# own sides, the floor its bottom, and the compost reads the second and third
# textures of `composter_top`, which is a list of three: the empty top, the
# compost, and the compost ready to take out.
COMPOST = BLOCKS % "compost"
READY = BLOCKS % "compost_ready"
## **The floor of the box needs its own picture on top.** `composter_top` is the
## rim seen from above and is clear through the middle, which is the opening.
## Given to the floor's upper face as well, an empty composter could be seen
## straight through to the sky. `composter_bottom` is what the game puts inside
## an empty one, and is the same picture as its underside.
FLOOR_ART = dict({face: "default" for face in FACES}, up="@down")

WALLS = [Cube((16, 2, 16), (0, 0, 0), texture=FLOOR_ART),   # the floor
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
SEAGRASS_PLANES = planes(4, along_x="#a", along_z="#b")
SEAGRASS = {
    "default": java.form(SEAGRASS_PLANES, painted_with(a="seagrass", b="seagrass")),
    "double_bot": java.form(SEAGRASS_PLANES, painted_with(
        a="seagrass_doubletall_bottom_a", b="seagrass_doubletall_bottom_b")),
    "double_top": java.form(SEAGRASS_PLANES, painted_with(
        a="seagrass_doubletall_top_a", b="seagrass_doubletall_top_b")),
}

## A cactus is the four planes a pixel in, wearing its declared side, with its
## top and bottom across the whole block, as Java's `cactus` is. The side tile
## is drawn to reach past where the green faces meet, which is where the spines
## are, so planes that cross leave no gap where boxes would.
CACTUS = {"default": java.form(planes(1, along_x="#side", along_z="#side") + [
    {"from": [0, 0, 0], "to": [16, 16, 16], "faces": {
        "up": {"uv": [0, 0, 16, 16], "texture": "#top"},
        "down": {"uv": [0, 0, 16, 16], "texture": "#bottom"}}}],
    lambda name: None)}


# --- coral fans -------------------------------------------------------------
#
# Java's `coral_fan` and `coral_wall_fan`. A fan on the floor is four blades
# spreading from its middle, each tilted up out of the ground; one on a wall is
# one blade tilted out from the wall, which `coral_direction` turns.
CORAL_FAN_BLADES = [
    {"from": [8, 0, 0], "to": [24, 0, 16],
     "rotation": {"origin": [8, 0, 0], "axis": "z", "angle": 22.5},
     "faces": {"up": {"uv": [0, 0, 16, 16], "rotation": 90},
               "down": {"uv": [0, 16, 16, 0], "rotation": 270}}},
    {"from": [-8, 0, 0], "to": [8, 0, 16],
     "rotation": {"origin": [8, 0, 0], "axis": "z", "angle": -22.5},
     "faces": {"up": {"uv": [0, 0, 16, 16], "rotation": 270},
               "down": {"uv": [0, 16, 16, 0], "rotation": 90}}},
    {"from": [0, 0, 8], "to": [16, 0, 24],
     "rotation": {"origin": [0, 0, 8], "axis": "x", "angle": -22.5},
     "faces": {"up": {"uv": [16, 16, 0, 0]}, "down": {"uv": [16, 0, 0, 16]}}},
    {"from": [0, 0, -8], "to": [16, 0, 8],
     "rotation": {"origin": [0, 0, 8], "axis": "x", "angle": 22.5},
     "faces": {"up": {"uv": [0, 0, 16, 16]}, "down": {"uv": [0, 16, 16, 0]}}},
]
## The wall fan: one blade tilted up out of the wall it grows on, the south
## side of its block, toward the north. Java's `coral_wall_fan` crosses a second
## blade tilted down through it; Bedrock draws the one, which a world showed.
CORAL_WALL_BLADES = [
    {"from": [0, 8, 0], "to": [16, 8, 16],
     "rotation": {"origin": [8, 8, 14], "axis": "x", "angle": 22.5, "rescale": True},
     "faces": {"up": {"uv": [0, 0, 16, 16]}, "down": {"uv": [16, 16, 0, 0]}}}]
## `coral_fan_direction` turns a floor fan a quarter. A wall fan's
## `coral_direction` names the way it faces, out from its wall: 0 west, 1 east,
## 2 north, 3 south, as PocketMine's schema reads it, turned by Minecraft's
## angles for those directions.
GROUND_CORAL_TURNS = {"0": [0, 0, 0], "1": [0, 270, 0]}
CORAL_TURNS = {"0": [0, 90, 0], "1": [0, 270, 0], "2": [0, 0, 0], "3": [0, 180, 0]}
CORAL_FAN = {"default": java.form(CORAL_FAN_BLADES, lambda name: None)}
CORAL_WALL_FAN = {"default": java.form(CORAL_WALL_BLADES, lambda name: None)}


# --- petals ------------------------------------------------------------------
#
# Pink petals and wildflowers are a bed of flowers lying on the ground, one to
# four quarters of the block filled as `growth` climbs: 0 is one quarter, 3 and
# above all four. The tile is the whole bed seen from above, so each quarter
# reads its own quarter of it, and the flat faces read it backwards both ways,
# which puts the tile's top left at the block's north west corner. Both blocks
# declare the bed first in a texture list whose second entry is the stem, and
# the list's first entry is what a block's own face reads.
#
# The order the quarters fill in, north west first and round to the east, is
# taken from the Java edition's models and has not been checked in a world.
# The stems are left off.
PETAL_THIN = 0.16
PETAL_UP = 2
## where each quarter is, (x, z), and where its picture is on the tile, (u, v)
PETAL_QUARTERS = [((8, 0), (0, 0)), ((8, 8), (0, 8)),
                  ((0, 8), (8, 8)), ((0, 0), (8, 0))]


def petals(count):
    made = []
    for (x, z), (u, v) in PETAL_QUARTERS[:count]:
        made.append(Cube((8, PETAL_THIN, 8), (x, PETAL_UP, z), window={
            "up": (u, v, 8, 8), "down": (u, v, 8, 8),
            "north": (u, v, 8, 1), "south": (u, v, 8, 1),
            "east": (u, v, 8, 1), "west": (u, v, 8, 1)}, behind=True))
    return made


PETALS = {str(growth): petals(min(growth + 1, 4)) for growth in range(8)}
PETALS["default"] = PETALS["0"]


def turns(family, table):
    """A family's rotation table, Minecraft's angles or the name of the state
    whose own angles it turns by."""
    lookup_writer.put(os.path.join(LOOKUPS, "block_rotation.json"),
                      family, table, tight=True)


def main():
    print("writing the forms that change with a state")
    for family, stages in CROPS.items():
        if family in HASHED:
            lookup_writer.forms(family, planted(stages))
        else:
            write(family, growing(stages))
        ## every one of these is a block id as well as a family name
        define([family], family)

    write("composter", composter())
    define(["composter"], "composter")

    lookup_writer.forms("seagrass", SEAGRASS)
    lookup_writer.forms("cactus", CACTUS)
    ## only `seagrass`: blocks.json has no `sea_grass`, and a
    ## definition for a block the pack never declares raises
    define(["seagrass"], "seagrass")
    lookup_writer.forms("coral_fan", CORAL_FAN)
    lookup_writer.forms("coral_fan_wall", CORAL_WALL_FAN)
    turns("coral_fan", GROUND_CORAL_TURNS)
    turns("coral_fan_wall", CORAL_TURNS)

    write("flowerbed", PETALS)
    lookup_writer.rules("flowerbed", data={"number": ["growth"]},
                        turn_by=[{"state": "minecraft:cardinal_direction"}])
    turns("flowerbed", "minecraft:cardinal_direction")
    define(["pink_petals", "wildflowers"], "flowerbed")

    ## a torchflower is a flower like any other
    define(["torchflower"], "cross_texture")
    print("re-run tools/blocks/simplify.py if any of these grew past two cubes")


if __name__ == "__main__":
    main()
