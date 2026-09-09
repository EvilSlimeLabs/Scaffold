"""Put the right texture on each part of the blocks built from several cubes.

    python -m tools.blocks.faces

A block made of one cube can take the six textures Bedrock declares for it and
be right. A block made of several cannot, because every cube gets the same six,
so a beacon's glass shell, its core and its obsidian base are all painted alike.

`block_uv.json` has an `overwrite` list for exactly this, a texture per cube per
face. A value written `@up` or `@down` means "whatever this block declares for
that face", so one entry serves every wood a block comes in and every state it
has, without naming a single texture file.

The families whose forms differ by how they are mounted are written by
`tools/blocks/mounted.py` instead, which owns their shapes as well as their
textures. Nothing here is needed at run time; it edits the lookup tables in
place.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")
FACES = ("up", "down", "north", "south", "east", "west")

## the four ways a block with a front can stand, as `minecraft:cardinal_direction`
## names them and as Bedrock's older numbering does. The turn runs the other
## way round from the compass: a vault built facing west needed the model spun
## the way "east" is written here.
FACING = {"0": [0, 0, 0], "1": [0, 270, 0], "2": [0, 180, 0], "3": [0, 90, 0],
          "south": [0, 0, 0], "west": [0, 270, 0], "north": [0, 180, 0],
          "east": [0, 90, 0]}


def load(path):
    return json.load(io.open(path, encoding="utf-8"))


def define(blocks, family):
    """Point block ids at a shape family."""
    table = json.load(io.open(DEFINITION, encoding="utf-8"))
    for block in blocks:
        table[block] = family
    body = json.dumps(table, indent="\t", ensure_ascii=False,
                      separators=(",", ":"))
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(body + "\n")


def all_faces(per_cube):
    """The same list of textures on every face of the block."""
    return {face: list(per_cube) for face in FACES}


def main():
    shapes = load(SHAPES)
    uv = load(UV)
    changed = []

    def revise(family, variant, overwrite, from_variant="default"):
        entry = json.loads(json.dumps(uv[family][from_variant]))
        entry["overwrite"] = overwrite
        uv[family][variant] = entry

    ## --- beacon: obsidian base, the beacon itself, then the glass shell -----
    ## Bedrock declares beacon_base as obsidian, beacon_shell as glass and
    ## beacon_core as the beacon texture, on down, side and up. Without an
    ## overwrite all three cubes take all three and the shell is not glass.
    revise("beacon", "default", all_faces(["@down", "@up", "@north"]))
    changed.append("beacon")

    ## --- tripwire hook: the plate, the hook, the wire -----------------------
    revise("tripwire_hook", "default",
           all_faces(["@down", "@north", "@east"]))
    changed.append("tripwire_hook")

    ## --- the two block tall flowers -----------------------------------------
    ## Bedrock declares the upper half on up, the lower on down, and something
    ## else entirely on side. For a lilac the side texture is the *sunflower's*
    ## back, so both halves have to be pinned to up and down instead.
    revise("double_plant", "default", all_faces(["@down", "@down"]))
    revise("double_plant", "top", all_faces(["@up", "@up"]),
           from_variant="top")
    changed.append("double_plant")

    ## --- azalea: a bush whose slots are not its faces ------------------------
    ## `blocks.json` gives an azalea six textures and only two of them are what
    ## the block looks like. `north` and `up` are the leaves; `south`, `east`
    ## and `west` are the potted bush's side, the plant inside a pot, and the
    ## pot's own plant, which the engine picks from for a model of its own. A
    ## block taking them literally is leaves on one side and crockery on three.
    ## All four sides read the leaves, and so does the underside, which is
    ## `potted_azalea_bush_top` otherwise.
    shapes["azalea"] = json.loads(json.dumps(shapes["cube"]))
    uv["azalea"] = json.loads(json.dumps(uv["cube"]))
    uv["azalea"]["default"]["overwrite"] = {
        "up": ["@up"], "down": ["@up"],
        "north": ["@north"], "south": ["@north"],
        "east": ["@north"], "west": ["@north"]}
    lookup_writer.put(SHAPES, "azalea", shapes["azalea"], tight=True)
    define(["azalea", "flowering_azalea"], "azalea")
    changed.append("azalea")

    ## --- carved pumpkins: the face was round the back ------------------------
    ## Its table was written a half turn out from every other block with a
    ## front: south read 180 where the convention is 0, so a pumpkin carved
    ## facing south looked north. Every entry turns half round.
    turned = {}
    for state, angles in load(ROTATION)["carved_pumpkin"].items():
        turned[state] = [angles[0], (angles[1] + 180) % 360, angles[2]]
    lookup_writer.put(ROTATION, "carved_pumpkin", turned, tight=True)

    ## --- vault: a cube, but one with a front ---------------------------------
    ## A rotation table is keyed by shape family, and a vault shared `cube` with
    ## everything else that is a plain box. `cube`'s table describes the axis
    ## states a pillar carries and has no entry for half the cardinal
    ## directions, so a vault faced whichever way it was placed and drew its
    ## front southward regardless. It gets a family of its own, the same box
    ## with the four facings spelt out.
    shapes["vault"] = json.loads(json.dumps(shapes["cube"]))
    uv["vault"] = json.loads(json.dumps(uv["cube"]))
    lookup_writer.put(SHAPES, "vault", shapes["vault"], tight=True)
    lookup_writer.put(ROTATION, "vault", FACING, tight=True)
    define(["vault"], "vault")
    changed.append("vault")

    for family in sorted(set(changed)):
        lookup_writer.put(UV, family, uv[family], tight=True)

    print("gave %d families a texture per cube:" % len(set(changed)))
    for family in sorted(set(changed)):
        print("   %s" % family)
    for path in (SHAPES, UV):
        json.loads(io.open(path, encoding="utf-8").read())
    print("both tables still parse")


if __name__ == "__main__":
    main()
