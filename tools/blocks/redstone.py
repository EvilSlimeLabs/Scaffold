"""The families Clearer Redstone draws with, written into each option's folder.

    python -m tools.blocks.redstone

Each Clearer Redstone option is staged as a tweak folder (see
`scaffold/tweaks.py`). `tools/vendor/redstone.py` puts its textures there, from
Redstone Tweaks; this writes what reads them: `geometry.json`, the families the
option draws with, `definition.json`, the blocks it points at a family of its
own, and `rotation.json`, the turns of any family it adds.

**Every family here is a copy of Scaffold's own with its faces re-pointed.** A
composter is still the composter family, with the outer sides of each fill
level reading a numbered side; a note block is the plain cube, one form per
pitch. A face is matched by the texture file it reads today, whether it names
the file, a slot or nothing, so the overlay follows whatever the base family
draws, and `tools/generate.py` runs this after every other block generator so
the copies are never older than what they copy.

The marks -- a container's count, a crafter's locked slots -- are families of
their own, drawn at the same position as the block by `scaffold/marks.py`.

Nothing here is needed at run time.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scaffold import block_geometry, marks, tweaks
from scaffold.pack import armor_stand_geo_class as asgc

STAGED = os.path.join(ROOT, "scaffold", "tweakpacks")
PREFIX = "textures/clearer_redstone"
T = 0.95 / 16                        # a texel of a block drawn 0.95 across
DUST_LIFT = 0.01                     # how far above the floor the dust lies


def texture(option, name):
    return "%s/%s/%s" % (PREFIX, option, name)


class Reader:
    """What each face of each block reads today, as a texture file."""

    def __init__(self):
        self.geo = asgc.ArmorStandGeo("redstone")
        self.families = block_geometry.read(block_geometry.GEOMETRY)["families"]
        self.rotations = block_geometry.read(block_geometry.ROTATION)["families"]

    def declared(self, block):
        return self.geo.get_block_texture_paths(block)

    def file(self, block, face, entry):
        """The file one face reads, without its window or turn."""
        found = entry.get("texture") or {}
        if "texture" in found:
            return found["texture"]
        slot = found.get("slot", face)
        return self.declared(block).get(slot)


def retextured(reader, family, block, pick, forms=None):
    """A copy of a family whose faces read what `pick` says.

    `pick(form, face, file)` answers the texture a face of that form should read
    now, or None to leave it. Only the forms named in `forms` are kept when it
    is given, which is how a plain cube becomes a family of one form per state.
    The rules are kept; a simpler form is re-pointed the same way.
    """
    entry = copy.deepcopy(reader.families[family])
    for section in ("forms", "low"):
        if section not in entry:
            continue
        source = entry[section]
        names = forms if forms is not None else {name: name for name in source}
        made = {}
        for name, base in names.items():
            if base not in source:
                continue
            body = copy.deepcopy(source[base])
            for cube in body["cubes"]:
                for face, read in cube["faces"].items():
                    now = pick(name, face, reader.file(block, face, read))
                    if now is None:
                        continue
                    old = {k: v for k, v in (read.get("texture") or {}).items()
                           if k not in ("slot", "texture")}
                    read["texture"] = dict({"texture": now}, **old)
            made[name] = body
        entry[section] = made
    return entry


def stem(path):
    return (path or "").rsplit("/", 1)[-1]


# --- the options ----------------------------------------------------------------

def dust(reader, option):
    """Scaffold's dust, every way it joins, reading a picture per signal.

    The family's forms are how the dust joins, so the signal picks the picture
    instead: the option declares the dust's top, its cross, and its sides, its
    line, as lists of sixteen, one per signal, and `texture_by` reads
    `redstone_signal` as the index. A number is a quad of its own over the
    middle, reading the down slot, declared the same way."""
    entry = copy.deepcopy(reader.families["red_dust"])
    entry["texture_by"] = {"state": "redstone_signal"}
    ## Scaffold's own dust reads the game's grey pictures, tinted by its power;
    ## the option's are already drawn per signal, so they are read untinted
    ## from the slots it declares them on
    from tools.blocks import dust as plain_dust
    slots = {plain_dust.READ["texture"]: "up", plain_dust.LINE["texture"]: "north"}
    for section in ("forms", "low"):
        for form in entry.get(section, {}).values():
            for cube in form["cubes"]:
                for face in cube["faces"].values():
                    found = face.get("texture") or {}
                    if found.get("texture") in slots:
                        face["texture"] = dict(
                            {"slot": slots[found["texture"]]},
                            **{k: v for k, v in found.items() if k not in ("texture", "tint")})
    names = {"up": "%s_dust" % option, "side": "%s_line" % option}
    terrain = {names["up"]: {"textures": [texture(option, "dust_%d" % p) for p in range(16)]},
               names["side"]: {"textures": [texture(option, "line_%d" % p) for p in range(16)]}}
    if option == "redstone_dust_numbers":
        names["down"] = "%s_number" % option
        terrain[names["down"]] = {"textures": [texture(option, "number_%d" % p)
                                               for p in range(16)]}
        ## the number floats over the middle four texels of the wire, as its own
        ## quad at four times the wire's resolution, the way the pack draws it,
        ## read backwards both ways so its top is to the north
        for section in ("forms", "low"):
            for form in entry.get(section, {}).values():
                form["cubes"].append(flat(
                    [0.25, 0, 0.25], [0.375, DUST_LIFT + LIFT, 0.375],
                    {"uv": [1, 1], "size": [-1, -1], "texture": {"slot": "down"}}))
    blocks = {"format_version": "1.21.40",
              "redstone_wire": {"sound": "stone", "textures": names}}
    return {"families": {"red_dust": entry}, "blocks": blocks,
            "terrain": {"resource_pack_name": "vanilla", "texture_name": "atlas.terrain",
                        "texture_data": terrain}}


def composter(reader, option):
    entry = retextured(reader, "composter", "composter", lambda form, face, f:
                       texture(option, "composter_%s" % ("0" if form == "default" else form))
                       if stem(f) == "composter_side" else None)
    return {"families": {"composter": entry}}


def cauldron(reader, option):
    def pick(form, face, f):
        if stem(f) != "cauldron_side":
            return None
        liquid, _, level = form.rpartition("-")
        if form == "default" or level in ("", "0"):
            return texture(option, "cauldron_0")
        liquid = "water" if liquid == "dyed" else liquid
        return texture(option, "cauldron_%s_%s" % (liquid, level))
    return {"families": {"cauldron": retextured(reader, "cauldron", "cauldron", pick)}}


def snow(reader, option):
    def pick(form, face, f):
        if face != "up" or stem(f) != "snow":
            return None
        height = 0 if form == "default" else int(form)
        return texture(option, "snow_%d" % (height + 1))
    return {"families": {"top_snow": retextured(reader, "top_snow", "snow_layer", pick)}}


def respawn_anchor(reader, option):
    def pick(form, face, f):
        charge = "0" if form == "default" else form
        name = stem(f)
        if name.startswith("respawn_anchor_top"):
            return texture(option, "top_" + charge)
        if name.startswith("respawn_anchor_side"):
            return texture(option, "side_" + charge)
        if name.startswith("respawn_anchor_bottom"):
            return texture(option, "bottom")
        return None
    forms = dict({str(n): "default" for n in range(5)}, default="default")
    entry = retextured(reader, "cube", "respawn_anchor", pick, forms)
    entry = {"data": {"number": ["respawn_anchor_charge"]}, "forms": entry["forms"]}
    return {"families": {"clearer_respawn_anchor": entry},
            "definition": {"respawn_anchor": "clearer_respawn_anchor"}}


def honey(reader, option):
    families, definition, rotation = {}, {}, {}
    for block in ("beehive", "bee_nest"):
        def pick(form, face, f, block=block):
            level = "0" if form == "default" else form
            name = stem(f)
            if name.startswith(block + "_front"):
                return texture(option, "%s_front_%s" % (block, level))
            if name == block + "_top":
                if face == "down" and block == "beehive":
                    return texture(option, "beehive_end")
                return texture(option, "%s_top_%s" % (block, level))
            if name == block + "_side":
                return texture(option, block + "_side")
            if name == "bee_nest_bottom":
                return texture(option, "bee_nest_bottom")
            return None
        forms = dict({str(n): "default" for n in range(6)}, default="default")
        entry = retextured(reader, "hive", block, pick, forms)
        entry["data"] = {"number": ["honey_level"]}
        family = "clearer_" + block
        families[family] = entry
        definition[block] = family
        rotation[family] = reader.rotations["hive"]
    return {"families": families, "definition": definition, "rotation": rotation}


def note_block(reader, option):
    """A note block numbered by its pitch, the pitch read from its entity.

    Each pitch's picture is a whole face at twice a block's resolution, so every
    face is four quads, each reading a quarter of it; the plain block, with no
    pitch to show, is the cube reading the pack's own plain face.
    """
    forms = {"default": "default"}
    entry = retextured(reader, "cube", "noteblock",
                       lambda form, face, f: texture(option, "note"), forms)
    for n in range(25):
        picture = texture(option, "note_%d" % n)
        entry["forms"][str(n)] = {"center": [0.5, 0.5, 0.5],
                                  "cubes": quartered(GHOST, picture, GHOST_INSET)}
    entry = {"data": {"entity": "note"}, "forms": entry["forms"]}
    return {"families": {"clearer_note_block": entry},
            "definition": {"noteblock": "clearer_note_block"}}


def quartered(across, picture, start=0.0):
    """Every face of a box `across` wide from `start` on every axis, as four
    quads, each reading a quarter of a picture twice a block's resolution, so
    the picture keeps its pixels.

    The picture's top left is the top left of each side seen from in front of
    it, and on the top the far left corner seen from the north.
    """
    half = across / 2
    out = []
    for i in (0, 1):            # across the picture, left to right
        for j in (0, 1):        # down the picture, top to bottom
            read = {"uv": [0, 0], "size": [1, 1],
                    "texture": {"texture": picture, "window": [16 * i, 16 * j]}}
            near, far = i * half, across - (i + 1) * half
            y = across - (j + 1) * half
            made = [
                standing([half, half, 0], [near, y, 0], "north", copy.deepcopy(read)),
                standing([half, half, 0], [far, y, across], "south", copy.deepcopy(read)),
                standing([0, half, half], [0, y, far], "east", copy.deepcopy(read)),
                standing([0, half, half], [across, y, near], "west", copy.deepcopy(read)),
                flat([half, 0, half], [near, across, across - (j + 1) * half],
                     copy.deepcopy(read)),
                below([half, 0, half], [near, 0, j * half], copy.deepcopy(read)),
            ]
            for cube in made:
                cube["offset"] = [round(v + start, 6) for v in cube["offset"]]
            out += made
    return out


def jukebox(reader, option):
    def pick(form, face, f):
        suffix = "_record" if form == "record" else ""
        return texture(option, ("top" if face == "up" else "side") + suffix)
    entry = retextured(reader, "cube", "jukebox", pick,
                       {"default": "default", "record": "default"})
    entry = {"data": {"instead": [["RecordItem", "record"]]}, "forms": entry["forms"]}
    return {"families": {"clearer_jukebox": entry},
            "definition": {"jukebox": "clearer_jukebox"}}


def observer(reader, option):
    files = {"observer_front": "front", "observer_back": "back", "observer_side": "side",
             "observer_top": "top", "observer_top_mirror": "top_mirror"}
    entry = retextured(reader, "observer", "observer", lambda form, face, f:
                       texture(option, files[stem(f)]) if stem(f) in files else None)
    ## Redstone Tweaks draws a side's arrow pointing left, the other way from
    ## the picture the plain family turns for, so its arrows point to the back
    ## on the east side as they are and on the west side turned half round
    for section in ("forms", "low"):
        for form in entry.get(section, {}).values():
            for cube in form["cubes"]:
                for face, turn in (("east", None), ("west", 180)):
                    read = cube["faces"].get(face, {}).get("texture")
                    if isinstance(read, dict):
                        read.pop("turn", None)
                        if turn:
                            read["turn"] = turn
    return {"families": {"observer": entry}}


def head(reader, arm, sticky, option):
    """A piston's head as Redstone Tweaks draws it: its front the piston's top,
    its back the plain top, its rim the piston's side and the shaft behind it
    the plain side. The head's own family reads Bedrock's arm sheet, which
    Redstone Tweaks has no picture for."""
    entry = copy.deepcopy(reader.families[arm])
    for section in ("forms", "low"):
        for form in entry.get(section, {}).values():
            for index, cube in enumerate(form["cubes"]):
                for face, read in cube["faces"].items():
                    if not isinstance(read.get("texture"), dict):
                        continue
                    if index:
                        name = "side"
                    else:
                        name = {"north": "top" + sticky, "south": "top"}.get(face, "side" + sticky)
                    turn = read["texture"].get("turn")
                    read["texture"] = dict({"texture": texture(option, name)},
                                           **({"turn": turn} if turn else {}))
    return entry


def pistons(reader, option):
    families = {}
    for family, sticky in (("piston", ""), ("sticky_piston", "_sticky")):
        files = {"piston_side": "side" + sticky, "piston_bottom": "bottom" + sticky,
                 "piston_top_normal": "top", "piston_top_sticky": "top_sticky"}
        ## an extended piston, any form but the retracted 0, shows its back
        ## with the indicator lit
        def pick(form, face, f, files=files, sticky=sticky):
            if stem(f) == "piston_bottom" and form not in ("0", "default"):
                return texture(option, "bottom_extended" + sticky)
            return texture(option, files[stem(f)]) if stem(f) in files else None
        families[family] = retextured(reader, family, family, pick)
        ## and the head the piston pushes out, which wears the same pictures
        arm = family + "_arm"
        families[arm] = head(reader, arm, sticky, option)
    return {"families": families}


## Every arrow points at the hole. Redstone Tweaks draws the top's arrow up the
## picture and the side's pointing left, with the side's stone band along the
## bottom. At rest the hole faces north: a top already points north, read
## backwards both ways, and a bottom is turned half round; the west side points
## north as it is and the east side read mirrored, which keeps its band along
## the bottom.
LEVEL_TURNS = {"up": None, "down": 180, "east": None, "west": None}
MIRRORED = {"uv": [1, 0], "size": [-1, 1]}
## Facing up or down, the four faces round the hole wear the top's picture, as
## Redstone Tweaks' own vertical model does, so no stone band runs across them,
## and the far end its top with the indicator lit
UPRIGHT_TURNS = {"east": 90, "west": 270, "up": None, "down": 180}


def aim(entry, block, option):
    """Point a dispenser's arrows at its hole, and give one facing up or down
    its top picture round the sides and its indicator at the far end."""
    for section in ("forms", "low"):
        for name, form in entry.get(section, {}).items():
            vertical = name.startswith("vertical")
            turns = UPRIGHT_TURNS if vertical else LEVEL_TURNS
            for cube in form["cubes"]:
                for face, read in cube["faces"].items():
                    if not any(read.get("size", [1])):
                        continue
                    if vertical and face == "south":
                        read["texture"] = {"texture": texture(option, block + "_back_vertical")}
                        continue
                    if face not in turns:
                        continue
                    if vertical:
                        read["texture"] = {"texture": texture(option, block + "_top")}
                    elif face == "east":
                        read.update(MIRRORED)
                    current = read.get("texture")
                    if isinstance(current, dict):
                        current.pop("turn", None)
                        if turns[face]:
                            current["turn"] = turns[face]


def launchers(reader, option):
    families, definition, rotation = {}, {}, {}
    for block in ("dispenser", "dropper"):
        def pick(form, face, f, block=block):
            name = stem(f)
            if name == "furnace_side":
                return texture(option, block + ("_back" if face == "south" else "_side"))
            if name == "furnace_top":
                return texture(option, block + "_top")
            if name == block + "_front_horizontal":
                return texture(option, block + "_front")
            if name == block + "_front_vertical":
                return texture(option, block + "_front_vertical")
            return None
        family = "clearer_" + block
        entry = retextured(reader, "dispenser", block, pick)
        aim(entry, block, option)
        families[family] = entry
        definition[block] = family
        rotation[family] = reader.rotations["dispenser"]
    return {"families": families, "definition": definition, "rotation": rotation}


def hopper(reader, option):
    def pick(form, face, f):
        mount = "side" if form.startswith("side") else "down"
        lock = "locked" if form.endswith("-1") else "unlocked"
        if stem(f) == "hopper_outside":
            return texture(option, "side_" + lock)
        if stem(f) == "hopper_top":
            return texture(option, "top_%s_%s" % (mount, lock))
        return None
    return {"families": {"hopper": retextured(reader, "hopper", "hopper", pick)}}


## Redstone Tweaks draws the top of a lever's base at twice its resolution, the
## six by eight top as twelve by sixteen in the corner of its picture, and paints
## nothing for the base's sides, which keep their cobblestone
LEVER_BASE_TOP = {"uv": [0.75, 1.0], "size": [-0.75, -1.0]}


def lever(reader, option):
    def pick(form, face, f):
        if stem(f) == "cobblestone" and face in ("up", "down"):
            return texture(option, "base_on" if form.startswith("on") else "base")
        if stem(f) == "lever":
            return texture(option, "lever")
        return None
    entry = retextured(reader, "lever", "lever", pick)
    for section in ("forms", "low"):
        for form in entry.get(section, {}).values():
            for face in ("up", "down"):
                read = form["cubes"][0]["faces"].get(face, {})
                if "/lever/base" in str(read.get("texture")):
                    read.update(LEVER_BASE_TOP)
    return {"families": {"lever": entry}}


## where each of a crafter's nine slots is painted on its top, in texels of its
## sixteen: three rows of three two-texel squares
CRAFTER_CELLS = [(x, y) for y in (4, 7, 10) for x in (4, 7, 10)]
## how far above a face a mark floats, so the two are never one plane and do
## not flicker against each other at a distance
LIFT = 0.01
## a whole block's ghost: a shade under full size and centred in its cell, so
## it runs from GHOST_INSET to GHOST_TOP on every axis
GHOST = 0.95
GHOST_INSET = round((1 - GHOST) / 2, 6)
GHOST_TOP = round(1 - GHOST_INSET, 6)


def flat(size, at, up, rest=None):
    """A cube with no height, so only its top is seen."""
    nothing = rest or {"uv": [0, 0], "size": [0, 0], "texture": up["texture"]}
    faces = {face: copy.deepcopy(nothing) for face in block_geometry.FACES}
    faces["up"] = up
    return {"size": [round(v, 6) for v in size], "offset": [round(v, 6) for v in at],
            "faces": faces}


def below(size, at, read):
    """A cube with no height, so only its underside is seen."""
    nothing = {"uv": [0, 0], "size": [0, 0], "texture": read["texture"]}
    faces = {face: copy.deepcopy(nothing) for face in block_geometry.FACES}
    faces["down"] = read
    return {"size": [round(v, 6) for v in size], "offset": [round(v, 6) for v in at],
            "faces": faces}


def standing(size, at, face, read):
    """A cube with no depth along one axis, so only `face` is seen."""
    nothing = {"uv": [0, 0], "size": [0, 0], "texture": read["texture"]}
    faces = {other: copy.deepcopy(nothing) for other in block_geometry.FACES}
    faces[face] = read
    return {"size": [round(v, 6) for v in size], "offset": [round(v, 6) for v in at],
            "faces": faces}


def sides(across, top, first, second, wide, narrow, window, narrow_window=None,
          tall=None, start=0.0):
    """Two quads at the top left of each side of a box `across` wide from
    `start`, as seen from in front of that side: the first `wide` across
    reading `first`, the second `narrow` across beside it reading `second`."""
    tall = tall or wide
    narrow_window = narrow_window or window
    a = dict(window, texture=first)
    b = dict(narrow_window, texture=second)
    y = top - tall
    out = []
    for face, lay in (
            ## seen from the north, left is east, the low side of x
            ("north", lambda s, at: ([s, tall, 0], [at, y, -LIFT])),
            ## from the south, left is west, the high side of x
            ("south", lambda s, at: ([s, tall, 0], [across - at - s, y, across + LIFT])),
            ## from the east, the low side of x, left is south, the high side of z
            ("east", lambda s, at: ([0, tall, s], [-LIFT, y, across - at - s])),
            ## from the west, left is north, the low side of z
            ("west", lambda s, at: ([0, tall, s], [across + LIFT, y, at]))):
        for size, at, read in ((wide, 0, a), (narrow, wide, b)):
            cube = standing(*lay(size, at), face, copy.deepcopy(read))
            cube["offset"] = [round(cube["offset"][0] + start, 6), cube["offset"][1],
                              round(cube["offset"][2] + start, 6)]
            out.append(cube)
    return out


def crafter_slots(reader, option):
    red = {"texture": texture(option, "locked")}
    forms = {}
    for slot, (x, y) in enumerate(CRAFTER_CELLS):
        ## the top's v runs toward -z, so a cell near the top of the picture is
        ## near the south edge of the block
        at = [GHOST_INSET + x * T, GHOST_TOP + LIFT, GHOST_INSET + (16 - y - 2) * T]
        forms[str(slot)] = {"center": [0.5, 0.5, 0.5], "cubes": [
            flat([2 * T, 0, 2 * T], at, {"uv": [0, 0], "size": [1, 1], "texture": red})]}
    forms["default"] = forms["0"]
    turning = {key: value for key, value in reader.geo.block_rotations["cube"].items()
               if "_" in key and key.split("_")[0] in ("up", "down", "north", "south",
                                                       "east", "west")}
    entry = {"data": {"number": ["slot"]}, "turn_by": [{"state": "orientation"}],
             "forms": forms}
    return {"families": {"clearer_crafter_slot": entry},
            "definition": {marks.CRAFTER_SLOT: "clearer_crafter_slot"},
            "rotation": {"clearer_crafter_slot": turning}}


## Where a count goes on each kind of container: the height of the top it lies
## on, the low x edge it starts from, the back edge it runs against, and the
## pivot the family turns about, all as the container's own family has them.
TOPS = {"chest": (0.9375, 0.125, 1.0, 0.5), "chest_left": (0.9375, 0.0625, 1.0, 0.5),
        "block": (GHOST_TOP, GHOST_INSET, GHOST_TOP, 0.5)}
## the slot counts each kind is drawn for
MOUNTS = {"chest": (27,), "chest_left": (54,), "block": (9, 27), "hopper": (5,),
          "pot": (1,)}
## a decorated pot's body: where it starts, how wide it is, and its top
POT_BODY = (0.0625, 0.875, 0.75)
## the hopper's bowl: its top, and how tall one line of a count is on its side
BOWL_TOP = 1.0
LINE = 0.25


def count_quads(option, slots, strength, mount):
    """The two quads a count is drawn on, at the corner a reader starts at.

    The first is half a block wide and reads the left 16 pixels of the count's
    row, the second a quarter wide and reads the next 8, both at twice a
    block's resolution. On a top, the corner is the far left one seen from in
    front; on a hopper's side, the top left of every side.
    """
    sheet = texture(option, "fill_%d" % slots)
    row = 16 * strength
    first = {"texture": sheet, "window": [0, row]}
    second = {"texture": sheet, "window": [16, row]}
    if mount in TOPS:
        top, left, back, _pivot = TOPS[mount]
        y = top + LIFT
        return [flat([0.5, 0, LINE], [left, y, back - LINE],
                     {"uv": [0, 0], "size": [1, 0.5], "texture": first}),
                flat([0.25, 0, LINE], [left + 0.5, y, back - LINE],
                     {"uv": [0, 0], "size": [0.5, 0.5], "texture": second})]
    if mount == "pot":
        start, across, top = POT_BODY
        return sides(across, top, first, second, 0.5, 0.25,
                     {"uv": [0, 0], "size": [1, 0.5]}, {"uv": [0, 0], "size": [0.5, 0.5]},
                     LINE, start=start)
    return sides(1.0, BOWL_TOP, first, second, 0.5, 0.25,
                 {"uv": [0, 0], "size": [1, 0.5]}, {"uv": [0, 0], "size": [0.5, 0.5]},
                 LINE)


def container_fill(reader, option):
    forms = {}
    for mount, counts in MOUNTS.items():
        pivot = TOPS[mount][3] if mount in TOPS else 0.5
        for slots in counts:
            for strength in range(16):
                forms["%s-%d-%d" % (mount, slots, strength)] = {
                    "center": [pivot, 0.5, pivot],
                    "cubes": count_quads(option, slots, strength, mount)}
    forms["default"] = forms["block-9-0"]
    entry = {"pick": [{"when": {"mount": m}, "form": m} for m in MOUNTS],
             "data": {"join": ["slots", "signal"]},
             "turn_by": [{"state": "minecraft:cardinal_direction"}],
             "forms": forms}
    return {"families": {"clearer_fill": entry},
            "definition": {marks.FILL: "clearer_fill"},
            "rotation": {"clearer_fill": "minecraft:cardinal_direction"}}


OPTIONS = {
    "redstone_dust_shades": dust,
    "redstone_dust_numbers": dust,
    "composter_numbers": composter,
    "cauldron_levels": cauldron,
    "snow_layers": snow,
    "respawn_anchor_charges": respawn_anchor,
    "bee_honey": honey,
    "note_block_pitch": note_block,
    "jukebox_record": jukebox,
    "observer_unpowered": observer,
    "piston_corners": pistons,
    "dispenser_directions": launchers,
    "hopper_directions": hopper,
    "lever": lever,
    "crafter_slots": crafter_slots,
    "container_fill": container_fill,
}


def _write(path, document):
    text = json.dumps(document, indent="\t", ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")


def main():
    print("writing the Clearer Redstone families")
    reader = Reader()
    for option, make in OPTIONS.items():
        folder = os.path.join(STAGED, option)
        if not os.path.isdir(folder):
            print("   %-24s not staged" % option)
            continue
        made = make(reader, option)
        _write(os.path.join(folder, tweaks.GEOMETRY), {"families": made["families"]})
        for key, name in (("definition", tweaks.DEFINITION), ("rotation", tweaks.ROTATION),
                          ("blocks", tweaks.BLOCKS), ("terrain", tweaks.TERRAIN)):
            path = os.path.join(folder, name)
            if key in made:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                _write(path, {"families": made[key]} if key == "rotation" else made[key])
            elif os.path.exists(path):
                os.remove(path)
        print("   %-24s %s" % (option, ", ".join(sorted(made["families"]))))


# --- the pictures the window shows -----------------------------------------------

## what each option's icon draws: the block, its states, any marks beside it,
## and the view
ICONS = {
    "redstone_dust_shades": ("redstone_wire", {"redstone_signal": 9}, (), "up"),
    "redstone_dust_numbers": ("redstone_wire", {"redstone_signal": 7}, (), "up"),
    "composter_numbers": ("composter", {"composter_fill_level": 5}, (), "up-nw"),
    "cauldron_levels": ("cauldron", {"fill_level": 4, "cauldron_liquid": "water"}, (), "up-nw"),
    "snow_layers": ("snow_layer", {"height": 2}, (), "up-nw"),
    "respawn_anchor_charges": ("respawn_anchor", {"respawn_anchor_charge": 3}, (), "up-nw"),
    "bee_honey": ("beehive", {"honey_level": 5, "direction": 2}, (), "up-nw"),
    "note_block_pitch": ("noteblock", {}, (), "up-nw"),
    "jukebox_record": ("jukebox", {}, (), "up-nw"),
    "observer_unpowered": ("observer", {"minecraft:facing_direction": "north"}, (), "up-nw"),
    "piston_corners": ("sticky_piston", {"facing_direction": 1}, (), "up-nw"),
    "dispenser_directions": ("dispenser", {"facing_direction": 2}, (), "up-nw"),
    "hopper_directions": ("hopper", {"facing_direction": 2, "toggle_bit": 1}, (), "up-nw"),
    "lever": ("lever", {"lever_direction": "up_north_south", "open_bit": True}, (), "up-nw"),
    "crafter_slots": ("crafter", {"orientation": "north_up"},
                      tuple((marks.CRAFTER_SLOT, {"slot": s, "orientation": "north_up"})
                            for s in (0, 2, 4, 6, 8)), "up"),
    "container_fill": ("chest", {"minecraft:cardinal_direction": "north"},
                       ((marks.FILL, {"mount": "chest", "slots": 27, "signal": 9,
                                      "minecraft:cardinal_direction": "north"}),), "up-nw"),
}
## entity fields an icon's block needs, for the forms a block entity chooses
ICON_ENTITIES = {"note_block_pitch": {"note": 12},
                 "jukebox_record": {"RecordItem": {"Name": "minecraft:music_disc_cat"}}}
ICON_SIZE = 90


def icons():
    """Draw each option's picture for the window, with the option applied."""
    from PIL import Image
    from tools.checks import render
    print("drawing the Clearer Redstone icons")
    for option, (block, states, extra, view) in ICONS.items():
        folder = os.path.join(STAGED, option)
        if not os.path.isdir(folder):
            continue
        geo = asgc.ArmorStandGeo("icon", offsets=[0, 0, 0], tweaks=[option])
        quads, atlas = render.mesh(block, geo=geo, also=extra, states=states,
                                   entity=ICON_ENTITIES.get(option))
        picture = render.draw(quads, atlas, view, 8, (0, 0, 0), render._frame(quads))
        picture = picture.convert("RGBA")
        ## the background drawn black is made see-through, so the window's own
        ## colour shows round the block
        pixels = picture.load()
        for y in range(picture.height):
            for x in range(picture.width):
                if pixels[x, y][:3] == (0, 0, 0):
                    pixels[x, y] = (0, 0, 0, 0)
        ## cropped to what was drawn, so a small block such as a lever fills
        ## its cell the way a whole one does
        picture = picture.crop(picture.getbbox() or (0, 0) + picture.size)
        side = max(picture.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(picture, ((side - picture.width) // 2, (side - picture.height) // 2))
        square.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS).save(
            os.path.join(folder, tweaks.ICON))
        print("   %s" % option)


if __name__ == "__main__":
    main()
