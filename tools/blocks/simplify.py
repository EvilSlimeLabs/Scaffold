"""Generate the simplified form of every shape family that carries a lot of cubes.

    python -m tools.blocks.simplify

Scaffold draws each ghost block as real geometry, and Vibrant Visuals lights
every one of those shapes. A build made of blocks that each cost half a dozen
cubes is therefore markedly more expensive to display than one made of plain
cubes, which is what the low geometry setting is for.

A family's simpler form is named after it with a suffix, `bell__low` beside
`bell`, and is the box the detailed shape fits inside: one cube, textured with
the window that box covers on the tile. `armor_stand_geo_class` picks it up
automatically when a pack is built with low geometry, and a family with no such
form is drawn exactly as it always is. That is most of them, since a block that
is already a cube has nothing to simplify.

The forms are written into `lookups/block_shapes.json` and `lookups/block_uv.json`
beside the shapes they came from, so nothing here is needed at run time. Re-run
it after changing a detailed shape.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scaffold.pack import armor_stand_geo_class as asgc

from tools.blocks import tables as lookup_writer

SHAPES = os.path.join(ROOT, "scaffold", "lookups", "block_shapes.json")
UV = os.path.join(ROOT, "scaffold", "lookups", "block_uv.json")
FACES = ("up", "down", "north", "south", "east", "west")

## Below this a block is not worth simplifying: the saving is a cube or two and
## the shape is most of what the block looks like.
BUSY = 3


def tidy(value):
    """Whole numbers as integers, so the tables keep the style they are in."""
    if isinstance(value, list):
        return [tidy(item) for item in value]
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def box_of(shape):
    """The smallest box containing every cube of a shape."""
    sizes = shape["size"]
    offsets = shape.get("offsets") or [[0, 0, 0]] * len(sizes)
    low = [min(offsets[i][axis] for i in range(len(sizes))) for axis in range(3)]
    high = [max(offsets[i][axis] + sizes[i][axis] for i in range(len(sizes)))
            for axis in range(3)]
    return low, high


def biggest(shape):
    """Which cube contributes most of the block, by volume."""
    sizes = shape["size"]
    volumes = [size[0] * size[1] * size[2] for size in sizes]
    return volumes.index(max(volumes))


def window(low, high):
    """The texture window a box covers on each face of its tile.

    V grows downward, so a block sitting on the floor of its cell takes the
    lower part of the tile and its window starts at one minus the box's top.
    """
    x0, y0, z0 = low
    x1, y1, z1 = high
    wide, tall, deep = x1 - x0, y1 - y0, z1 - z0
    return {
        "up": ([x0, z0], [wide, deep]),
        "down": ([x0, z0], [wide, deep]),
        "north": ([x0, 1 - y1], [wide, tall]),
        "south": ([x0, 1 - y1], [wide, tall]),
        "east": ([z0, 1 - y1], [deep, tall]),
        "west": ([z0, 1 - y1], [deep, tall]),
    }


def simplify(family, shapes, uvs):
    """The one-cube form of a family, for both tables, or None."""
    detailed = shapes[family].get("default")
    if not detailed or len(detailed["size"]) < BUSY:
        return None

    low, high = box_of(detailed)
    size = [round(high[i] - low[i], 6) for i in range(3)]
    if min(size) <= 0:
        return None

    shape = {"default": {
        "size": [tidy(size)],
        "offsets": [tidy([round(v, 6) for v in low])],
        "center": tidy([round(low[i] + size[i] / 2.0, 6) for i in range(3)]),
    }}

    windows = window(low, high)
    entry = {
        "uv_sizes": {face: [tidy([round(v, 6) for v in windows[face][1]])]
                     for face in FACES},
        "offset": {face: [tidy([round(v, 6) for v in windows[face][0]])]
                   for face in FACES},
    }

    ## The block keeps the texture of whichever cube made up most of it: a
    ## flower pot simplified to its pot rather than to the soil inside it.
    source = uvs.get(family, {}).get("default", {})
    if "overwrite" in source:
        index = biggest(detailed)
        carried = {}
        for face, names in source["overwrite"].items():
            if index < len(names) and names[index] != "default":
                carried[face] = [names[index]]
        if carried:
            entry["overwrite"] = carried

    return shape, {"default": entry}


def main():
    shapes = json.load(io.open(SHAPES, encoding="utf-8"))
    uvs = json.load(io.open(UV, encoding="utf-8"))

    made = []
    for family in sorted(shapes):
        if family.endswith(asgc.LOW_SUFFIX):
            continue
        result = simplify(family, shapes, uvs)
        if result is None:
            continue
        shape, entry = result
        name = family + asgc.LOW_SUFFIX
        lookup_writer.put(SHAPES, name, shape)
        lookup_writer.put(UV, name, entry, tight=True)
        made.append((family, len(shapes[family]["default"]["size"])))

    print("simplified %d families:" % len(made))
    for family, cubes in sorted(made, key=lambda pair: -pair[1]):
        print("   %-26s %d cubes -> 1" % (family, cubes))


if __name__ == "__main__":
    main()
