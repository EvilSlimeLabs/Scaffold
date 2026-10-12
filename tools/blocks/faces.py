"""Put the right texture on each part of the blocks built from several cubes.

    python -m tools.blocks.faces

A block made of one cube can take the six textures Bedrock declares for it and
be right. A block made of several cannot, because every cube gets the same six,
so a beacon's glass shell, its core and its obsidian base are all painted alike.

`block_geometry.json` gives each face of each cube a texture of its own for
exactly this. A value written `@up` or `@down` means "whatever this block declares for
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
from tools.blocks import tables as _tables

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")
FACES = ("up", "down", "north", "south", "east", "west")

## A vault turns by Minecraft's own angles: its front, the north slot, rests on
## the north face, and its top and bottom read their tiles with the picture's
## top edge to the north.
FACING = "minecraft:cardinal_direction"


def load(path):
    return lookup_writer.load(path)


def define(blocks, family):
    """Point block ids at a shape family."""
    _tables.define(blocks, family)


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
    ## a face reading the slot of its own name is left to it
    revise("tripwire_hook", "default",
           {face: [("default" if slot == "@" + face else slot)
                   for slot in ("@down", "@north", "@east")] for face in FACES})
    changed.append("tripwire_hook")

    ## --- the two block tall flowers -----------------------------------------
    ## Bedrock declares the upper half on up, the lower on down, and something
    ## else entirely on side. For a lilac the side texture is the *sunflower's*
    ## back, so both halves have to be pinned to up and down instead.
    revise("double_plant", "default", all_faces(["@down", "@down"]))
    revise("double_plant", "top", all_faces(["@up", "@up"]),
           from_variant="top")
    changed.append("double_plant")

    ## --- carved pumpkins: the face was round the back ------------------------
    ## Its table was written a half turn out from every other block that carries
    ## `facing_direction`, so a pumpkin carved facing south looked north.
    ##
    ## **This is written out, not turned.** It used to read the table, add a
    ## half turn and write it back, which corrects it exactly once: run twice it
    ## is wrong again, and `build.py` regenerates everything before every
    ## compile. The pumpkin faced a different way on alternate releases and
    ## nothing said so, because the tables were valid either way. A generator
    ## has to say what a table *is*, never what to change it by.
    ##
    ## The words are the six `facing_direction` values and match `furnace` and
    ## `observer` exactly; the numbers are the four a pumpkin's own `direction`
    ## carries, which is a different state with its own numbering.
    ##
    ## The half turn is in these numbers rather than applied to them, and it is
    ## the *second* one this table has needed: written a half turn out, corrected
    ## to match `furnace` and `observer`, and still facing backwards in game.
    ## Those two carry their own tables and are right as they are, so this is not
    ## a shared fault to fix in one place. `lit_pumpkin` shares the family and so
    ## moves with it. A pumpkin carries `minecraft:cardinal_direction`, so the
    ## four words are all it can be turned by.
    ##
    ## Its geometry reads the declared front, the south slot, on the north face,
    ## where a block at rest looks, so it turns by Minecraft's own angles.
    lookup_writer.put(ROTATION, "carved_pumpkin", "minecraft:cardinal_direction",
                      tight=True)

    ## --- vault: a cube, but one with a front ---------------------------------
    ## A rotation table is keyed by shape family, and a vault shared `cube` with
    ## everything else that is a plain box. `cube`'s table describes the axis
    ## states a pillar carries and has no entry for half the cardinal
    ## directions, so a vault faced whichever way it was placed and drew its
    ## front southward regardless. It gets a family of its own, the same box
    ## with the four facings spelt out.
    shapes["vault"] = json.loads(json.dumps(shapes["cube"]))
    uv["vault"] = json.loads(json.dumps(uv["cube"]))
    vault = uv["vault"]["default"]
    vault.pop("overwrite", None)
    for face in ("up", "down"):
        vault["offset"][face] = [[1, 1]]
        vault["uv_sizes"][face] = [[-1, -1]]
    lookup_writer.put(SHAPES, "vault", shapes["vault"], tight=True)
    lookup_writer.put(ROTATION, "vault", FACING, tight=True)
    define(["vault"], "vault")
    changed.append("vault")

    for family in sorted(set(changed)):
        lookup_writer.put(UV, family, uv[family], tight=True)

    print("gave %d families a texture per cube:" % len(set(changed)))
    for family in sorted(set(changed)):
        print("   %s" % family)
    json.loads(io.open(lookup_writer.GEOMETRY, encoding="utf-8").read())
    print("both tables still parse")


if __name__ == "__main__":
    main()
