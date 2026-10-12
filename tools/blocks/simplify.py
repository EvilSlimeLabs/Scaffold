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

The forms are written into `lookups/block_geometry.json`
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

SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
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


def simple_form(form, source):
    """One form's box, for both tables, or None when it has nothing in it.

    **The box turns about the detailed form's pivot, not its own middle.** The
    simpler form is turned by the family's rotation table like the detailed one,
    and a box pivoting anywhere else would swing round to somewhere the block
    is not.
    """
    low, high = box_of(form)
    size = [round(high[i] - low[i], 6) for i in range(3)]
    if min(size) <= 0:
        return None

    shape = {
        "size": [tidy(size)],
        "offsets": [tidy([round(v, 6) for v in low])],
        "center": tidy(list(form["center"])),
    }

    windows = window(low, high)
    entry = {
        "uv_sizes": {face: [tidy([round(v, 6) for v in windows[face][1]])]
                     for face in FACES},
        "offset": {face: [tidy([round(v, 6) for v in windows[face][0]])]
                   for face in FACES},
    }

    ## **The box reads the windows of the cube whose texture it carries**,
    ## stretched to the box, rather than windows measured from where the box
    ## stands. A cube reading part of a sheet, a hanging sign's board, a statue's
    ## body, reads the part it was drawn with; measured from the box, it read
    ## whatever of the sheet lay there, clear strips included.
    index = biggest(form)
    if source.get("uv_sizes"):
        entry = {
            "uv_sizes": {face: [list(source["uv_sizes"][face][index])] for face in FACES},
            "offset": {face: [list(source["offset"][face][index])] for face in FACES},
        }

    ## The block keeps the texture of whichever cube made up most of it: a
    ## flower pot simplified to its pot rather than to the soil inside it.
    if "overwrite" in source:
        carried = {}
        for face, names in source["overwrite"].items():
            if index < len(names) and names[index] != "default":
                carried[face] = [names[index]]
        if carried:
            entry["overwrite"] = carried
    return shape, entry


def simplify(family, shapes, uvs):
    """The simpler form of a family, for both tables, or None.

    A family is simplified when its default form is busy, and then every form
    gets a simpler one, so a bell on a wall or an open gate is drawn as its own
    box rather than as the default's. A form that is already cheap is kept as
    it is.
    """
    detailed = shapes[family].get("default")
    if not detailed or len(detailed["size"]) < BUSY:
        return None
    ## a default that is flat, a fan of planes, has no box to stand in for it
    if simple_form(detailed, {}) is None:
        return None

    shape, uv = {}, {}
    for name, form in shapes[family].items():
        source = uvs.get(family, {}).get(name) or uvs.get(family, {}).get(
            "default", {})
        made = simple_form(form, source) if len(form["size"]) >= BUSY else None
        if made is None:
            made = (form, source)
        shape[name], uv[name] = made
    if "default" not in uv or not uv["default"]:
        return None
    return shape, uv


# --- forms written for a family -----------------------------------------------------
#
# Some families are simplified by hand, in format 2, after the boxes above.

## Drawn as a whole block wearing the block's inventory picture in a slot on
## every face, read through the `item` slot, which `tools/textures/item_icons.py`
## fills.
ICON_FAMILIES = (
    "sea_pickle", "big_dripleaf", "small_dripleaf", "azalea", "spore_blossom",
    "wheat", "carrots", "potatoes", "beetroot", "nether_wart", "torchflower_crop",
    "pitcher_crop", "sweet_berry_bush", "cocoa", "pumpkin_stem", "melon_stem",
    "cross_texture", "double_plant", "sunflower", "flowerbed", "seagrass", "kelp",
    "coral_fan", "coral_fan_wall", "cave_vines_berries", "cave_vines_head_berries",
    "tripwire_hook",
    "skull_dragon", "skull_piglin", "bell", "anvil", "chipped_anvil", "damaged_anvil",
    "beacon", "campfire", "cake", "brewing_stand", "lectern", "dried_ghast")
## drawn as they are, with no simpler form
NO_LOW = ("hopper", "comparator", "comparator_on", "repeater", "repeater_on", "red_dust")
## every form drawn as one of the family's detailed forms, whatever it joins: a
## fence or a wall as its post, a pane or bars as the cross joined all four
## ways, since a lone pane's post is a sliver nobody can see; and a composter
## as it is empty
AS_FORM = {"pane": "1-1-1-1", "bars": "1-1-1-1", "fence": "default", "wall": "default"}
## a bowl drawn as planes, each wall flat at the block's edge, so what is in
## it still shows
FLATTENED = ("cauldron", "composter")
NOTHING = {"uv": [0, 0], "size": [0, 0]}
WHOLE = {"uv": [0, 0], "size": [1, 1]}
GEOMETRY_FACES = ("north", "south", "east", "west", "up", "down")


def _bounds(cubes):
    low = [min(c["offset"][i] for c in cubes) for i in range(3)]
    high = [max(c["offset"][i] + c["size"][i] for c in cubes) for i in range(3)]
    return low, high


def _plane(size, offset, shows, read):
    faces = {face: dict(NOTHING) for face in GEOMETRY_FACES}
    for face in shows:
        faces[face] = dict(read)
    return {"size": [round(v, 6) for v in size], "offset": [round(v, 6) for v in offset],
            "faces": faces}


## the box a picture block is drawn as, and where its faces stand
SLOT_BOX = 0.95
SLOT_NEAR = (1 - SLOT_BOX) / 2
SLOT_MID = 0.5
## each face of the box as four quads, a quarter of the slot each: the axis
## the face lies across, where, and for the picture's left column and top row,
## which half of each of its two other axes they stand in (True for the high
## half). A side reads its picture the right way round from outside; the top
## and bottom read theirs backwards both ways, the picture's top to the north
SLOT_FACES = {
    "north": (2, SLOT_NEAR, {0: False, 1: True}),
    "south": (2, 1 - SLOT_NEAR, {0: True, 1: True}),
    "east": (0, SLOT_NEAR, {2: True, 1: True}),
    "west": (0, 1 - SLOT_NEAR, {2: False, 1: True}),
    "up": (1, 1 - SLOT_NEAR, {0: True, 2: False}),
    "down": (1, SLOT_NEAR, {0: True, 2: False}),
}


def icon_form(form):
    """A whole block, drawn a shade under full size like every other, with the
    block's inventory slot on all six faces, read through the `item` slot.

    The slot is drawn at twice a block's resolution, thirty two pixels square,
    so each face is four quads side by side, each reading sixteen pixels of it.
    They tile the face and the slot has no clear texel, so nothing on the box
    flickers against anything else on it."""
    cubes = []
    half = SLOT_BOX / 2
    for face, (axis, at, first) in SLOT_FACES.items():
        across = [a for a in (0, 1, 2) if a != axis]
        ## the picture's columns run along the first of the two other axes
        ## named, and its rows along the second
        column_axis, row_axis = list(first)
        for column in (0, 1):
            for row in (0, 1):
                size = [SLOT_BOX] * 3
                offset = [0.0] * 3
                size[axis] = 0
                offset[axis] = at
                for a, index in ((column_axis, column), (row_axis, row)):
                    high = first[a] != bool(index)
                    size[a] = half
                    offset[a] = SLOT_MID if high else SLOT_NEAR
                read = {"uv": [0, 0], "size": [1, 1],
                        "texture": {"slot": "item", "window": [16 * column, 16 * row]}}
                if face in ("up", "down"):
                    read.update(uv=[1, 1], size=[-1, -1])
                cubes.append(_plane([round(v, 6) for v in size],
                                    [round(v, 6) for v in offset], (face,), read))
        del across
    return {"center": form["center"], "cubes": cubes}


def _box_of(cubes, faces_from):
    """One box round some cubes, its faces those of `faces_from`."""
    import copy
    low, high = _bounds(cubes)
    made = copy.deepcopy(faces_from)
    made.pop("rotation", None)
    made["offset"] = [round(v, 6) for v in low]
    made["size"] = [round(high[i] - low[i], 6) for i in range(3)]
    return made


def _touch(a, b, gap=0.01):
    return all(a["offset"][i] <= b["offset"][i] + b["size"][i] + gap and
               b["offset"][i] <= a["offset"][i] + a["size"][i] + gap for i in range(3))


def _clusters(cubes):
    """Cubes grouped by whether they touch, one group per piece."""
    groups = []
    for cube in cubes:
        joined = [g for g in groups if any(_touch(cube, other) for other in g)]
        merged = [cube] + [c for g in joined for c in g]
        groups = [g for g in groups if g not in joined] + [merged]
    return groups


## the side of a block a wall on the low or high side of an axis is on
OUTER = {(0, False): "east", (0, True): "west", (2, False): "north", (2, True): "south"}
OPPOSITE = {"east": "west", "west": "east", "north": "south", "south": "north"}


def flattened_form(form):
    """A bowl, a cauldron or a composter, as planes: each wall flat on the
    block's edge, its outside picture outward and its inside picture in, the
    floor flat at the height of its top, and what is in the bowl as it is."""
    import copy
    cubes = form["cubes"]
    walls = [c for c in cubes if c["size"][1] >= 0.5 and min(c["size"][0], c["size"][2]) <= 0.2]
    floors = [c for c in cubes if c["size"][1] < 0.25 and c["size"][0] >= 0.9 and c["size"][2] >= 0.9]
    rest = [c for c in cubes if c not in walls and c not in floors]
    if not walls:
        return copy.deepcopy(form)
    ## the outside picture of the longest wall, which spans the whole side
    longest = max(walls, key=lambda c: max(c["size"][0], c["size"][2]))
    long_axis = 0 if longest["size"][0] <= longest["size"][2] else 2
    outside = copy.deepcopy(longest["faces"][OUTER[(long_axis, longest["offset"][long_axis] >= 0.5)]])
    made = []
    for wall in walls:
        axis = 0 if wall["size"][0] <= wall["size"][2] else 2
        high = wall["offset"][axis] >= 0.5
        out = OUTER[(axis, high)]
        faces = {face: dict(NOTHING) for face in GEOMETRY_FACES}
        faces[out] = copy.deepcopy(outside)
        faces[OPPOSITE[out]] = copy.deepcopy(wall["faces"][OPPOSITE[out]])
        size = [1.0, wall["size"][1], 1.0]
        offset = [0.0, wall["offset"][1], 0.0]
        size[axis] = 0
        offset[axis] = 1.0 if high else 0.0
        made.append({"size": size, "offset": offset, "faces": faces})
    for floor in floors:
        faces = {face: dict(NOTHING) for face in GEOMETRY_FACES}
        faces["up"] = copy.deepcopy(floor["faces"]["up"])
        faces["down"] = copy.deepcopy(floor["faces"]["down"])
        made.append({"size": [floor["size"][0], 0, floor["size"][2]],
                     "offset": [floor["offset"][0], round(floor["offset"][1] + floor["size"][1], 6),
                                floor["offset"][2]], "faces": faces})
    return {"center": form["center"], "cubes": made + copy.deepcopy(rest)}


def gate_form(form):
    """A gate's two posts as they are, and one box for each piece of the rails
    between them: one shut, two open."""
    posts = [c for c in form["cubes"] if c["size"][1] >= 10 / 16.0]
    rails = [c for c in form["cubes"] if c not in posts]
    return {"center": form["center"],
            "cubes": posts + [_box_of(g, g[0]) for g in _clusters(rails)]}


def grindstone_form(form):
    """The wheel, and one box for the legs reaching into it."""
    cubes = form["cubes"]
    wheel = max(cubes, key=lambda c: c["size"][0] * c["size"][1] * c["size"][2])
    rest = [c for c in cubes if c is not wheel]
    return {"center": form["center"], "cubes": [wheel] + ([_box_of(rest, rest[0])] if rest else [])}


def first_cube_form(form):
    """The form's first cube alone: a sculk sensor's base, an enchanting
    table's body."""
    return {"center": form["center"], "cubes": [form["cubes"][0]]}


def pot_form(form):
    """The pot's outline, dressed as its wall, not its soil."""
    walls = [c for c in form["cubes"] if "dirt" not in str(c["faces"])]
    return {"center": form["center"], "cubes": [_box_of(form["cubes"], walls[0])]}


## the part of a cactus side picture that is the body, between the spines
CACTUS_BODY = (1 / 16.0, 14 / 16.0)


def cactus_form(form):
    """The body, without the spines that stand out of it: a box fourteen
    pixels square whose sides read only the body's fourteen columns of the
    side picture. A form that is one cube already, a potted cactus, is kept."""
    import copy
    if len(form["cubes"]) == 1:
        return copy.deepcopy(form)
    ## the spines are thin planes round the body, and the top and bottom a box
    side = min(form["cubes"], key=lambda c: min(c["size"][0], c["size"][2]))
    body = [c for c in form["cubes"] if c is not side
            and min(c["size"][0], c["size"][2]) > 2 / 16.0]
    made = {"size": [14 / 16.0, 1, 14 / 16.0], "offset": [1 / 16.0, 0, 1 / 16.0], "faces": {}}
    for face in ("north", "south", "east", "west"):
        read = copy.deepcopy(next(v for v in side["faces"].values() if any(v["size"])))
        start, wide = CACTUS_BODY
        read["uv"][0] = start if read["size"][0] > 0 else 1 - start
        read["size"][0] = wide if read["size"][0] > 0 else -wide
        made["faces"][face] = read
    top = body[0] if body else form["cubes"][-1]
    for face in ("up", "down"):
        read = copy.deepcopy(top["faces"][face])
        ## the top picture has a clear ring a pixel wide round the body too
        start, wide = CACTUS_BODY
        for i in (0, 1):
            backwards = read["size"][i] < 0
            read["uv"][i] = 1 - start if backwards else start
            read["size"][i] = -wide if backwards else wide
        made["faces"][face] = read
    return {"center": form["center"], "cubes": [made]}


def banner_form(box, design):
    """A marked banner as the box a dyed banner is simplified to, its two broad
    faces wearing the whole design, drawn by `tools/textures/low.py`."""
    import copy
    made = copy.deepcopy(box)
    picture = dict(WHOLE, texture={"texture": "textures/blocks/scaffold_low_banner_" + design})
    for face in ("north", "south"):
        made["cubes"][0]["faces"][face] = dict(picture)
    return made


def statue_form(form, family):
    """The statue's outline, each side wearing the statue drawn from that side,
    by `tools/textures/low.py`."""
    low, high = _bounds(form["cubes"])
    faces = {}
    for face in GEOMETRY_FACES:
        view = "up" if face in ("up", "down") else face
        faces[face] = dict(WHOLE, texture={"texture": "textures/blocks/scaffold_low_%s_%s"
                                           % (family, view)})
    return {"center": form["center"], "cubes": [{
        "size": [round(high[i] - low[i], 6) for i in range(3)],
        "offset": [round(v, 6) for v in low], "faces": faces}]}


def written_forms(geometry):
    """{family: {form: low form}} for every family simplified by hand."""
    families = geometry["families"]
    found = {}

    def each(family, build):
        forms = families[family]["forms"]
        found[family] = {name: build(form) for name, form in forms.items()}

    for family in ICON_FAMILIES:
        if family in families:
            each(family, icon_form)
    for family, base in AS_FORM.items():
        if family in families:
            forms = families[family]["forms"]
            found[family] = {name: forms[base] for name in forms}
    each("fence_gate", gate_form)
    for family in FLATTENED:
        if family in families:
            each(family, flattened_form)
    each("grindstone", grindstone_form)
    for family in ("sculk_sensor", "calibrated_sculk_sensor"):
        each(family, first_cube_form)
    each("enchanting_table", lambda form: first_cube_form(form))
    each("flower_pot", pot_form)
    each("cactus", cactus_form)
    for family in ("copper_golem_statue", "exposed_copper_golem_statue",
                   "weathered_copper_golem_statue", "oxidized_copper_golem_statue"):
        each(family, lambda form, family=family: statue_form(form, family))
    ## a banner's marked forms, the dyed one's box with the design on it
    for family in ("standing_banner", "wall_banner"):
        banner = families.get(family, {})
        low = dict(banner.get("low", {}))
        if "default" not in low:
            continue
        for design in ("illager", "designed"):
            if design in banner["forms"]:
                low[design] = banner_form(low["default"], design)
        found[family] = low
    return found


def main():
    ## as the columns the generators write
    shapes = lookup_writer.load(SHAPES)
    uvs = lookup_writer.load(UV)

    made = []
    for family in sorted(shapes):
        if family.endswith(asgc.LOW_SUFFIX):
            continue
        result = simplify(family, shapes, uvs)
        if result is None:
            ## a family that has stopped being worth simplifying keeps no
            ## simpler form, or low geometry goes on drawing the old one
            name = family + asgc.LOW_SUFFIX
            if name in shapes:
                lookup_writer.drop(SHAPES, name)
                lookup_writer.drop(UV, name)
                print("   dropped %s" % name)
            continue
        shape, entry = result
        name = family + asgc.LOW_SUFFIX
        lookup_writer.put(SHAPES, name, shape)
        lookup_writer.put(UV, name, entry, tight=True)
        made.append((family, len(shapes[family]["default"]["size"])))

    print("simplified %d families:" % len(made))
    for family, cubes in sorted(made, key=lambda pair: -pair[1]):
        print("   %-26s %d cubes -> 1" % (family, cubes))

    ## the families with no simpler form, and those simplified by hand
    for family in NO_LOW:
        name = family + asgc.LOW_SUFFIX
        lookup_writer.drop(SHAPES, name)
        lookup_writer.drop(UV, name)
    geometry = json.loads(io.open(lookup_writer.GEOMETRY, encoding="utf-8").read())
    for family, forms in written_forms(geometry).items():
        lookup_writer.forms(family, forms, "low")


if __name__ == "__main__":
    main()
