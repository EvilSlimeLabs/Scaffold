"""Build the copper golem statue from the models the game draws it with.

    python -m tools.blocks.statues

A copper golem statue does not record its pose in a block state. It keeps it in
the block entity beside the block, the way a sign keeps its text, so a structure
holding four statues in four poses has a single palette entry for all of them and
the pose has to be read from `block_position_data`. `structure_reader` reads that
now and `scaffold.core` turns the `Pose` field into the shape variant, which is
what this table answers.

**The four poses are four geometry files**, not one shape leaned four ways. The
game's resource pack ships `copper_golem`, `copper_golem_sitting`,
`copper_golem_running` and `copper_golem_star`, and each is the golem's nine or
eleven cubes with the arms and the legs turned where that pose puts them. Built
from three boxes instead, the statue is a copper blob wearing terrain tiles.

The sheet is `textures/blocks/copper_golem.png`, which is a 64x64 entity sheet
rather than a tile, so every face names the corner of it that its own face was
drawn at. `terrain_texture.json` points the block's declared name at it, and
Bedrock declares that one sheet on all eight statues, so the unweathered family
reads it as `@up` and each later age is a family of its own naming its own
entity sheet. A waxed statue is drawn as the age it was waxed at.

The golem is **taller than the block it stands on**, twenty four pixels to the
top of the pompom, and is drawn at that size: shrinking it would put the ghost
somewhere the real statue will not be. The dragon head is the same case.

Writes into `lookups/block_geometry.json`. Not needed
at run time. Re-run `tools/blocks/simplify.py` afterwards.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools import sources

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build, on_sheet, spun, unwrap
from scaffold import jsonc

SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
GEOMETRY = sources.resource_pack("models", "entity")
FAMILY = "copper_golem_statue"

## the golem's own sheet, which the block declares on every face, and the sheet
## each age of copper wears instead. Each age is a family of its own, because
## Bedrock declares the unweathered sheet on all eight statues.
SHEET = "@up"
SHEET_WIDE = 64
AGES = {"": SHEET,
        "exposed": "textures/entity/copper_golem/copper_golem_exposed",
        "weathered": "textures/entity/copper_golem/copper_golem_weathered",
        "oxidized": "textures/entity/copper_golem/copper_golem_oxidized"}
## what a statue reads from its block entity, the same for every age
RULES = {"data": {"entity": "Pose"}, "turn_by": [{"state": "minecraft:cardinal_direction"}]}

## Which model each pose is drawn with, in the order the game numbers them.
POSES = {
    "0": "copper_golem",            # standing
    "1": "copper_golem_sitting",
    "2": "copper_golem_running",
    "3": "copper_golem_star",       # arms and legs thrown out
}


def model(name):
    """One geometry, as its bones keyed by name with their parents resolved."""
    body = jsonc.load(os.path.join(GEOMETRY, name + ".geo.json"))
    geo = body["minecraft:geometry"][0]
    return {bone["name"]: bone for bone in geo["bones"]}


def turns_on(bones, bone, cube):
    """Every turn that reaches one cube, innermost first.

    A cube may carry a turn of its own about a pivot of its own, and each bone
    above it may turn about its own pivot as well. They apply from the inside
    out, which is the order they come back in.
    """
    found = []
    if cube.get("rotation"):
        found.append((cube.get("pivot") or [0, 0, 0], cube["rotation"]))
    while bone is not None:
        if bone.get("rotation"):
            found.append((bone.get("pivot") or [0, 0, 0], bone["rotation"]))
        bone = bones.get(bone.get("parent"))
    return found


def settled(cube, turns):
    """A cube with every turn that reaches it already in it.

    Scaffold turns a cube about the cube's own middle, so the middle is moved
    to where the pivots would have put it and the angles are kept on the cube.
    Every model read here turns a cube and the bone above it about the same
    axis, so the angles add; anything else would need composing and this says so
    rather than quietly getting it wrong.
    """
    middle = [at + size / 2.0
              for at, size in zip(cube["origin"], cube["size"])]
    axes = {axis for _pivot, rotation in turns
            for axis, angle in enumerate(rotation) if angle}
    if len(turns) > 1 and len(axes) > 1:
        raise SystemExit("turns on more than one axis need composing: %s"
                         % turns)
    total = [0.0, 0.0, 0.0]
    for pivot, rotation in turns:
        middle = spun(middle, pivot, rotation)
        total = [a + b for a, b in zip(total, rotation)]
    return [m - size / 2.0 for m, size in zip(middle, cube["size"])], total


def statue(name, sheet=SHEET):
    """One pose, as the cubes of a block."""
    bones = model(name)
    made = []
    for bone in bones.values():
        for cube in bone.get("cubes", []):
            origin, turn = settled(cube, turns_on(bones, bone, cube))
            wide, tall, deep = cube["size"]
            texture, window = {}, {}
            for face, region in unwrap(cube.get("uv", [0, 0]),
                                       cube["size"]).items():
                texture[face], window[face] = on_sheet(sheet, region,
                                                       SHEET_WIDE)
            ## a model's coordinates are a block's, measured from the middle
            ## of its floor rather than its corner, and it faces north as a
            ## block at rest does, so it moves half a block and nothing turns
            at = (origin[0] + 8, origin[1], origin[2] + 8)
            spin = list(turn) if any(turn) else None
            made.append(Cube((wide, tall, deep), at, texture=texture,
                             window=window, rotation=spin))
    return made


def main():
    print("writing the copper golem's poses")
    for age, sheet in AGES.items():
        family = (age + "_" if age else "") + FAMILY
        shapes, uvs = {}, {}
        for pose, name in POSES.items():
            cubes = statue(name, sheet)
            shapes[pose], uvs[pose] = build(cubes)
        shapes["default"] = shapes["0"]
        uvs["default"] = uvs["0"]
        lookup_writer.put(SHAPES, family, shapes, tight=True)
        lookup_writer.put(UV, family, uvs, tight=True)
        lookup_writer.rules(family, **RULES)
        lookup_writer.turns(family, "minecraft:cardinal_direction")
        lookup_writer.define([(age + "_" if age else "") + FAMILY,
                              "waxed_" + (age + "_" if age else "") + FAMILY], family)
        print("   %s" % family)
    json.loads(io.open(lookup_writer.GEOMETRY, encoding="utf-8").read())


if __name__ == "__main__":
    main()
