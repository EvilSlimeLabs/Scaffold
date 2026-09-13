"""Give the mob heads a shape, so that they are drawn at all.

    python -m tools.blocks.heads

A head was `ignore`, which is the lookup for a block Scaffold leaves out on
purpose, so every skull in a build simply was not there and nothing said so.

Seven heads are built here: the skeleton, the wither skeleton, the zombie, the
creeper, the player, the piglin and the ender dragon. Each is a family of its
own, because the sheet it wears is the only thing that tells them apart and
`blocks.json` gives every one of them the same name for it, `skull`, which the
vanilla pack points at soul sand.

**The shapes come from the game's own entity geometry.** The community submodule
ships `models/entity/*.geo.json`, so a piglin's snout, its tusks and its ears,
and every one of the dragon's seven pieces, are the cubes and the UV corners
Mojang drew rather than something measured off a picture. `convert()` turns one
of those cubes into a Scaffold cube: it lays out the six faces the way Bedrock
unwraps a box, and turns the model half a turn about its own middle, because an
entity faces -z and a block faces +z.

The four skulls and the player have no geometry file, being drawn by the engine
rather than by a model, so they take the head box every humanoid skin has in the
top left corner of its sheet.

Only the top left 16x16 of a texture becomes a tile, so each face names the
window it reads. The sheets are copied out of the community submodule into
`textures/entity/`.

Nothing here is needed at run time.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, build, on_sheet, spun
from scaffold import jsonc

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")
COMMUNITY = os.path.join(ROOT, "CommunityVanillaResourcePack", "models")
GEOMETRY = os.path.join(COMMUNITY, "entity")
## the heads the game draws a skull block with, all four in one file
MOBS = os.path.join(COMMUNITY, "mobs.json")

## A head is drawn about its pivot, which sits at the middle of the block's
## floor: a mob head's cube runs from y24 to y32 and appears in the bottom half
## of its block, so the pivot's y24 is the floor. A head on a wall is the same
## model four pixels higher and four back.
PIVOT_Y = 24
WALL_LIFT = 4
WALL_BACK = 4


_SHEETS = {}


def measure(sheet):
    """How wide a sheet is, so a tile can be kept inside it."""
    if sheet not in _SHEETS:
        from PIL import Image

        path = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                            sheet + ".png")
        if not os.path.isfile(path):
            path = path[:-4] + ".tga"
        _SHEETS[sheet] = Image.open(path).size[0]
    return _SHEETS[sheet]


def on_its_own(cube, pivot, rotation):
    """A cube of a turned bone, as a cube that turns on its own.

    A bone turns its cubes about the bone's pivot; Scaffold turns a cube about
    the cube's own middle. Moving the middle to where the bone would have put it
    and keeping the same turn on the cube comes to the same thing, and it is
    what leaves the piglin's ears splayed out rather than flat against its head.
    """
    if not rotation or not any(rotation):
        return cube
    middle = [at + size / 2.0
              for at, size in zip(cube["origin"], cube["size"])]
    moved = spun(middle, pivot, rotation)
    turned = dict(cube)
    turned["origin"] = [at - size / 2.0
                        for at, size in zip(moved, cube["size"])]
    turned["rotation"] = list(rotation)
    return turned


def convert(sheet, cube, lift, back, scale=1.0):
    """One cube of an entity's head, as a cube of a block.

    Bedrock unwraps a box from its UV corner as two faces in a row above four
    in a strip: up and down across the top, then east, north, west and south.
    Each of those is a rectangle of the sheet, and each becomes the window its
    face reads.

    An entity faces -z and a block faces +z, so the model is turned half a turn
    about its middle on the way in: what was its front ends up on the block's
    south face, which is where the rotation tables put a block at rest.
    """
    ox, oy, oz = cube["origin"]
    w, h, d = cube["size"]
    u, v = cube.get("uv", [0, 0])

    ## The six rectangles of the sheet. Each becomes a tile of its own, named by
    ## the corner it starts at, because only a 16x16 window of a texture becomes
    ## one: a face of an entity sheet is nowhere near the top left of it.
    rectangles = {
        "south": (u + d, v + d, w, h),
        "north": (u + d + w + d, v + d, w, h),
        "west": (u, v + d, d, h),
        "east": (u + d + w, v + d, d, h),
        "up": (u + d, v, w, d),
        "down": (u + d + w, v, w, d),
    }
    ## The corner is pulled back far enough that the tile fits inside the
    ## sheet. A tile that runs off the edge is not cropped short: the loader
    ## drops the corner altogether and reads the sheet's own top left, which is
    ## how the piglin's right ear came out wearing the side of its head.
    texture, window = {}, {}
    for face, region in rectangles.items():
        texture[face], window[face] = on_sheet(sheet, region, measure(sheet))

    ## **and the box itself, shrunk about the pivot before it is placed.** Only
    ## the dragon asks for that, and the pivot is the middle of the block's
    ## floor, so a smaller head stays standing on the same spot and keeps its
    ## proportions. The picture is untouched: a face reads the same rectangle of
    ## the sheet whatever size the cube it lands on is.
    if scale != 1.0:
        ox, oz = ox * scale, oz * scale
        oy = (oy - PIVOT_Y) * scale + PIVOT_Y
        w, h, d = w * scale, h * scale, d * scale

    ## turned half about the middle of the block
    at = (8 - ox - w, oy - PIVOT_Y + lift, 8 - oz - d - back)
    ## a turn the cube carries has to be turned along with the model: after a
    ## half turn about Y its X and Z axes both run the other way
    spin = cube.get("rotation")
    if spin:
        spin = [-spin[0], spin[1], -spin[2]]
    return Cube((w, h, d), at, texture=texture, window=window, rotation=spin)


def from_mobs(identifier, bones=None):
    """The cubes of a geometry in models/mobs.json.

    That file is where the game keeps the models it draws a skull block with.
    `entity/skull.entity.json` names four of them, one per kind of head, so
    what is written here is the head the game itself puts on the block rather
    than a box measured off a picture.
    """
    stored = jsonc.load(MOBS)
    if identifier in stored:
        geo = stored[identifier]
    else:
        ## the newer format keeps one geometry to a file, and the piglin is
        ## there rather than in mobs.json
        path = os.path.join(GEOMETRY, "%s.geo.json"
                            % identifier[len("geometry."):])
        body = jsonc.load(path)
        geo = body["minecraft:geometry"][0]
    found = []
    for bone in geo["bones"]:
        if bones is not None and bone["name"] not in bones:
            continue
        for cube in bone.get("cubes", []):
            found.append(on_its_own(cube, bone.get("pivot"),
                                    bone.get("rotation")))
    return found


## The seven heads: the family, the sheet, the cubes and the block ids, each at
## the size the game draws it.
def heads():
    mob = from_mobs("geometry.mob_head")
    return {
        "skull_skeleton": ("textures/entity/skulls/skeleton", mob,
                           ["skeleton_skull", "skull"]),
        "skull_wither": ("textures/entity/skulls/wither_skeleton", mob,
                         ["wither_skeleton_skull"]),
        "skull_zombie": ("textures/entity/skulls/zombie", mob, ["zombie_head"]),
        "skull_creeper": ("textures/entity/skulls/creeper", mob,
                          ["creeper_head"]),
        ## a player head is always Steve: a skin is the player's own, and a
        ## resource pack cannot know it
        "skull_player": ("textures/entity/steve",
                         from_mobs("geometry.player_head"), ["player_head"]),
        ## the piglin keeps its snout, its tusks and its ears
        "skull_piglin": ("textures/entity/piglin/piglin",
                         from_mobs("geometry.piglin",
                                   {"head", "leftear", "rightear"}),
                         ["piglin_head"]),
        ## A dragon's head is bigger than the block it is placed on, with the
        ## snout out the front and the jaw hanging below the block's floor.
        "skull_dragon": ("textures/entity/dragon/dragon",
                         from_mobs("geometry.dragon_head"), ["dragon_head"]),
    }


## **The dragon is drawn smaller than its own model.** `geometry.dragon_head` is
## the head off a full sized ender dragon: sixteen across, twenty tall and thirty
## deep, which is two blocks of snout. The game does not draw the block at that
## size, and the ghost was swamping everything near it. Three quarters is the
## factor the game uses, and leaves the head about a block with the snout out
## the front. Every other head is already a block or less and is left alone.
SCALES = {"skull_dragon": 0.75}


def head(sheet, cubes, scale=1.0):
    """A head on the floor, and the same head against a wall.

    Both are the game's own model about its own pivot, and the pivot is the
    middle of the block's floor, so the two mountings are the same cubes moved
    rather than two shapes.

    **A head on the floor stands on the floor.** Every mob head's model sits
    neatly above its own pivot, but a dragon's jaw hangs below it, and a ghost
    block reaching down into the block underneath reads as belonging to that
    block rather than to this one. The floor form is lifted by however far its
    lowest cube falls short, which is nothing at all for every head but the
    dragon. The wall form is left where it is: a head on a wall is allowed to
    hang, and the game hangs one.
    """
    standing = [convert(sheet, cube, 0, 0, scale) for cube in cubes]
    lowest = min(cube.at[1] for cube in standing)
    lift = -lowest if lowest < 0 else 0
    return {"default": [convert(sheet, cube, lift, 0, scale) for cube in cubes],
            ## the wall form carries the same lift on top of its own, so a head
            ## that had to be raised off the floor is raised off the wall by as
            ## much. Without it the dragon sat six pixels lower on a wall than
            ## on the ground, which reads as two different blocks.
            "wall": [convert(sheet, cube, WALL_LIFT + lift, WALL_BACK, scale)
                     for cube in cubes]}


## facing_direction: 1 is a head standing on the floor and 2 to 5 name the wall
## it hangs on. The wall values are scoped to the wall form, because 2 means
## something different in the two numberings.
##
## A head on the floor can face any of sixteen ways, and that is in the block
## entity rather than the states, so `core.py` hands it over as `spinN`. Named
## apart from the facings so that the second step round is not read as the north
## wall. A floor head with no entity beside it keeps the plain 1.
##
## The entity's own numbering starts half a turn from the block convention: a
## block at rest faces south, and a skull whose Rotation is zero faces north, so
## every floor turn carries the extra half. The wall facings do not: those come
## from facing_direction, which names the way the head looks, and the wall form
## is already built sitting against the wall behind it.
FLOOR = 180
TURNS = {"1": [0, FLOOR, 0],
         "wall:2": [0, 180, 0], "wall:3": [0, 0, 0],
         "wall:4": [0, 90, 0], "wall:5": [0, 270, 0]}
TURNS.update({"spin%d" % n: [0, round((n * 22.5 + FLOOR) % 360, 1), 0]
              for n in range(16)})


def define(blocks, family):
    table = json.load(io.open(DEFINITION, encoding="utf-8"))
    for block in blocks:
        table[block] = family
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(
        json.dumps(table, indent="\t", ensure_ascii=False,
                   separators=(",", ":")) + "\n")


def main():
    print("writing the heads")
    for family, (sheet, cubes, blocks) in heads().items():
        forms = head(sheet, cubes, SCALES.get(family, 1.0))
        shapes, uvs = {}, {}
        for name, made in forms.items():
            shapes[name], uvs[name] = build(made)
        lookup_writer.put(SHAPES, family, shapes, tight=True)
        lookup_writer.put(UV, family, uvs, tight=True)
        lookup_writer.put(ROTATION, family, TURNS, tight=True)
        define(blocks, family)
        print("   %-16s %d cubes  %s" % (family, len(cubes), ", ".join(blocks)))
    print("now re-run tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
