"""Build the copper golem statue from the models the game draws it with.

    python -m tools.blocks.statues

A copper golem statue does not record its pose in a block state. It keeps it in
the block entity beside the block, the way a sign keeps its text, so a structure
holding four statues in four poses has a single palette entry for all of them and
the pose has to be read from `block_position_data`. `structure_reader` reads that
now and `scaffold.core` turns the `Pose` field into the shape variant, which is
what this table answers.

**The four poses are four geometry files**, not one shape leaned four ways. The
community submodule ships `copper_golem`, `copper_golem_sitting`,
`copper_golem_running` and `copper_golem_star`, and each is the golem's nine or
eleven cubes with the arms and the legs turned where that pose puts them. Built
from three boxes instead, the statue is a copper blob wearing terrain tiles.

The sheet is `textures/blocks/copper_golem.png`, which is a 64x64 entity sheet
rather than a tile, so every face names the corner of it that its own face was
drawn at. `terrain_texture.json` already points the block's declared name at it,
so the reference travels as `@up` and the eight oxidation stages all resolve to
the same sheet, which is what they did before.

The golem is **taller than the block it stands on**, twenty four pixels to the
top of the pompom, and is drawn at that size: shrinking it would put the ghost
somewhere the real statue will not be. The dragon head is the same case.

Writes into `lookups/block_shapes.json` and `lookups/block_uv.json`. Not needed
at run time. Re-run `tools/blocks/simplify.py` afterwards.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build, on_sheet, spun, unwrap
from scaffold import jsonc

SHAPES = os.path.join(ROOT, "scaffold", "lookups", "block_shapes.json")
UV = os.path.join(ROOT, "scaffold", "lookups", "block_uv.json")
GEOMETRY = os.path.join(ROOT, "CommunityVanillaResourcePack", "models", "entity")
FAMILY = "copper_golem_statue"

## the golem's own sheet, which the block already declares on every face
SHEET = "@up"
SHEET_WIDE = 64

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


def statue(name):
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
                texture[face], window[face] = on_sheet(SHEET, region,
                                                       SHEET_WIDE)
            ## an entity faces -z and a block faces +z, so the model is turned
            ## half about the middle of the block: its front ends up on the
            ## south face, where the rotation tables put a block at rest, and a
            ## turn the cube carries has its X and Z run the other way with it
            at = (8 - origin[0] - wide, origin[1], 8 - origin[2] - deep)
            spin = [-turn[0], turn[1], -turn[2]] if any(turn) else None
            made.append(Cube((wide, tall, deep), at, texture=texture,
                             window=window, rotation=spin))
    return made


def main():
    print("writing the copper golem's poses")
    shapes, uvs = {}, {}
    for pose, name in POSES.items():
        cubes = statue(name)
        shapes[pose], uvs[pose] = build(cubes)
        print("   %-8s %-24s %2d cubes, %d turned"
              % (pose, name, len(cubes),
                 sum(1 for cube in cubes if cube.rotation)))
    shapes["default"] = shapes["0"]
    uvs["default"] = uvs["0"]

    lookup_writer.put(SHAPES, FAMILY, shapes, tight=True)
    lookup_writer.put(UV, FAMILY, uvs, tight=True)
    for name in (SHAPES, UV):
        json.loads(io.open(name, encoding="utf-8").read())
    print("both tables still parse; now re-run tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
