"""The geometry tables, format 2, and the columns the geometry builder reads.

`lookups/block_geometry.json` describes every shape family:

    {"format": 2, "minecraft": "26.50",
     "families": {
        "<family>": {
            "forms": {"<form>": FORM, ...},
            "low":   {"<form>": FORM, ...}          the simpler forms, optional
        }}}

    FORM    {"center": [x, y, z], "cubes": [CUBE, ...]}
    CUBE    {"size": [x, y, z], "offset": [x, y, z], "rotation": [x, y, z],
             "faces": {"north": FACE, "south": FACE, ... all six}}
    FACE    {"uv": [u, v], "size": [w, h], "texture": TEXTURE}
    TEXTURE {"slot": "<face>"} or {"texture": "<path>"},
            with "window": [x, y], "turn": 90 and "tint": true when wanted

Everything is in blocks, from the low corner of the cell, in the coordinates a
Bedrock `.geo.json` uses: a block rests facing north. A face's `uv` and `size`
are the window it reads, in fractions of its texture's tile. A face with no
`texture` reads what the block declares for that face in `blocks.json`; `slot`
reads what it declares for another face, `texture` names a file outright,
`window` is the corner of the 16 by 16 piece of a larger sheet to take, `turn`
turns that piece clockwise, and `tint` multiplies it by the block's own colour.

`lookups/state_rotations.json` holds the turn Minecraft gives each value of a
state that turns a block, and `lookups/block_rotation.json` gives each family
that turns either the name of one of those states or a table of its own.

The geometry builder still thinks in the two tables this format replaced,
`block_shapes` and `block_uv`, a family each with lists per cube. `columns`
turns format 2 into those, and `from_columns` turns them back, which is how the
generators that write those columns keep working.
"""
import io
import json

from scaffold import paths
from scaffold import lookup

FORMAT = 2
FACES = ("north", "south", "east", "west", "up", "down")
LOW_SUFFIX = "__low"

GEOMETRY = "block_geometry.json"
ROTATION = "block_rotation.json"
STATES = "state_rotations.json"

TURN_MARK = "^"
WINDOW_MARK = "#"
TINT_WANTED = "~tint"


## the rules a family may carry beside its forms; see "Choosing a form"
RULES = ("pick", "data", "turn_by", "texture_by")


# --- choosing a form ------------------------------------------------------------
#
# A family says, beside its forms, how a block's states and block entity choose
# between them, which state turns it, and which state picks its textures:
#
#   "pick":       [{"when": {state: value or [values]}, "form": name}, ...]
#                 the first rule every one of whose states matches names the
#                 block's mounting; with none, the mounting is "default"
#   "data":       where the block's other value comes from:
#                   "number": [states]   the last of these present, as a number
#                   "join":   [states]   those present, joined with "-"
#                   "entity": field      a field of the block entity, instead
#                   "entity_add": field  a field of the block entity, after a "-"
#                   "instead": [[field, form or {value: form}], ...]
#                                        a field that names a form outright
#                   "tinted": [from, to] renames a form whose liquid is dyed
#                 with none, the value is "0"
#   "turn_by":    [{"state": name, "when": {...}}, ...] the first present whose
#                 condition holds is the state the block turns by; or
#                 {"entity": field}, a field of the block entity
#   "texture_by": {"state": name, "values": {value: index}} which entry of a
#                 texture list the block's faces read; with no values the
#                 state's own number is the index. Or {"join": [states],
#                 "values": {...}}, keyed by their values joined with "-"
#
# The form drawn is the first of "<mounting>-<value>", "<value>", "<mounting>"
# and "default" the family has.

def plain(value):
    """A state's value, as the text a rule is matched with."""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value)
    if "(" in text and text.endswith(")"):
        text = text[text.index("(") + 1:-1]
    return text.strip("'\"")


def _matches(states, when):
    for state, wanted in when.items():
        if state not in states:
            return False
        have = plain(states[state])
        wanted = wanted if isinstance(wanted, list) else [wanted]
        if have not in [plain(w) for w in wanted]:
            return False
    return True


def mounting(rules, states):
    for rule in rules.get("pick", ()):
        if _matches(states, rule["when"]):
            return rule["form"]
    return "default"


def value(rules, states, entity=None):
    """The block's value, which names a form on its own or after its mounting."""
    spec = rules.get("data", {})
    found = "0"
    for state in spec.get("number", ()):
        if state in states:
            found = str(int(states[state]))
    present = [plain(states[state]) for state in spec.get("join", ()) if state in states]
    if present:
        found = "-".join(present)
    if entity:
        field = spec.get("entity")
        if field and field in entity:
            found = plain(entity[field])
        field = spec.get("entity_add")
        if field and field in entity:
            found = "%s-%s" % (found, plain(entity[field]))
        for field, named in spec.get("instead", ()):
            if field not in entity:
                continue
            held = entity[field]
            if isinstance(named, dict):
                form = named.get(plain(held))
            elif len(held) if hasattr(held, "__len__") else held:
                form = named
            else:
                form = None
            if form is not None:
                found = form
                break
        tinted = spec.get("tinted")
        if tinted and "CustomColor" in entity and found.startswith(tinted[0]):
            found = tinted[1] + found[len(tinted[0]):]
    return found


def form(rules, forms, states, entity=None):
    """The form a block with these states and this block entity is drawn in."""
    mount = mounting(rules, states)
    found = value(rules, states, entity)
    for name in ("%s-%s" % (mount, found), found, mount):
        if name in forms:
            return name
    return "default"


def turn(rules, states, entity=None):
    """The value of the state the block turns by, or None.

    A rule may name a field of the block entity, `{"entity": field}`, for a
    block that keeps its facing there rather than in its states.
    """
    for rule in rules.get("turn_by", ()):
        if "entity" in rule:
            if entity and rule["entity"] in entity:
                text = plain(entity[rule["entity"]])
                try:
                    return int(text)
                except ValueError:
                    return text
            continue
        state = rule["state"]
        if state in states and _matches(states, rule.get("when", {})):
            text = plain(states[state])
            try:
                return int(text)
            except ValueError:
                return text
    return None


def texture_index(rules, states):
    """Which entry of a texture list the block's faces read, or None.

    The rule names one state, or `join`s several, the way `data` does: a copper
    bulb's picture is one of four, by `lit` and `powered_bit` together.
    """
    rule = rules.get("texture_by")
    if not rule:
        return None
    if "join" in rule:
        present = [plain(states[state]) for state in rule["join"] if state in states]
        if not present:
            return None
        return rule["values"].get("-".join(present))
    if rule["state"] not in states:
        return None
    text = plain(states[rule["state"]])
    if "values" in rule:
        return rule["values"][text]
    return int(text)


# --- textures -----------------------------------------------------------------

def texture_object(written):
    """A face's texture, from the marks the columns write it with."""
    if written in (None, "default"):
        return None
    found = {}
    if written.endswith(TINT_WANTED):
        found["tint"] = True
        written = written[:-len(TINT_WANTED)]
    written, mark, turn = written.partition(TURN_MARK)
    if mark:
        found["turn"] = int(turn)
    written, mark, window = written.partition(WINDOW_MARK)
    if mark:
        across, _, down = window.partition(",")
        found["window"] = [int(across), int(down)]
    if written.startswith("@"):
        found = dict({"slot": written[1:]}, **found)
    else:
        found = dict({"texture": written}, **found)
    return found


def texture_marks(found):
    """A face's texture, as the marks the columns write it with."""
    if not found:
        return "default"
    written = "@" + found["slot"] if "slot" in found else found["texture"]
    if "window" in found:
        written += "%s%d,%d" % (WINDOW_MARK, found["window"][0], found["window"][1])
    if found.get("turn"):
        written += "%s%d" % (TURN_MARK, found["turn"])
    if found.get("tint"):
        written += TINT_WANTED
    return written


# --- format 2 and the columns -------------------------------------------------

def form_from_columns(shape, uv):
    """One form, from its entry in each of the two column tables."""
    count = len(shape["size"])
    offsets = shape.get("offsets") or [[0, 0, 0]] * count
    rotations = shape.get("rotation")
    windows = len(uv["uv_sizes"]["up"])
    overwrite = uv.get("overwrite", {})
    cubes = []
    for i in range(count):
        ## a cube past the end of the window lists reads the last of them,
        ## and past the end of a face's textures reads what the block declares
        w = min(i, windows - 1)
        faces = {}
        for face in FACES:
            entry = {"uv": list(uv["offset"][face][w]),
                     "size": list(uv["uv_sizes"][face][w])}
            names = overwrite.get(face, [])
            texture = texture_object(names[i] if i < len(names) else None)
            if texture:
                entry["texture"] = texture
            faces[face] = entry
        cube = {"size": list(shape["size"][i]), "offset": list(offsets[i])}
        if rotations is not None and rotations[i] and any(rotations[i]):
            cube["rotation"] = list(rotations[i])
        cube["faces"] = faces
        cubes.append(cube)
    return {"center": list(shape["center"]), "cubes": cubes}


def columns_from_form(form):
    """One form, as its entry in each of the two column tables."""
    cubes = form["cubes"]
    shape = {"size": [c["size"] for c in cubes],
             "offsets": [c["offset"] for c in cubes],
             "center": form["center"]}
    if any(c.get("rotation") for c in cubes):
        shape["rotation"] = [c.get("rotation", [0, 0, 0]) for c in cubes]
    uv = {"uv_sizes": {f: [c["faces"][f]["size"] for c in cubes] for f in FACES},
          "offset": {f: [c["faces"][f]["uv"] for c in cubes] for f in FACES}}
    overwrite = {}
    for face in FACES:
        names = [texture_marks(c["faces"][face].get("texture")) for c in cubes]
        while names and names[-1] == "default":
            names.pop()
        if names:
            overwrite[face] = names
    if overwrite:
        uv["overwrite"] = overwrite
    return shape, uv


def family_from_columns(shapes, uvs):
    """A family's forms, from its two column entries; forms the two tables
    do not agree on are answered separately rather than guessed at.

    A form with a shape and no window of its own reads the default's windows,
    which is what the geometry builder has always done with one. A form with
    windows and no shape can never be drawn, and is left out.
    """
    forms, problems = {}, []
    for name, shape in shapes.items():
        uv = uvs.get(name) or uvs.get("default")
        if uv is None:
            problems.append("form %r has a shape and no windows at all" % name)
            continue
        forms[name] = form_from_columns(shape, uv)
    for name in uvs:
        if name not in shapes:
            problems.append("form %r has windows and no shape" % name)
    return forms, problems


def columns(families):
    """The two column tables, with each simpler form as a family of its own."""
    shapes, uvs = {}, {}
    for family, entry in families.items():
        for section, name in (("forms", family), ("low", family + LOW_SUFFIX)):
            if section not in entry:
                continue
            shapes[name], uvs[name] = {}, {}
            for form, body in entry[section].items():
                shapes[name][form], uvs[name][form] = columns_from_form(body)
    return shapes, uvs


# --- reading and writing ------------------------------------------------------

def read(name):
    with io.open(paths.lookup(name), encoding="utf-8") as f:
        return json.load(f)


def load():
    """The two column tables the geometry builder reads."""
    return columns(read(GEOMETRY)["families"])


def rules():
    """Every family's rules for choosing a form, a turn and a texture."""
    return {family: {k: entry[k] for k in RULES if k in entry}
            for family, entry in read(GEOMETRY)["families"].items()}


_variants = None


def variant_state(block):
    """The state that names a block's variant, or None.

    It is the state the block's family picks a texture by, `texture_by`: a
    turtle egg's `cracked_state` is a different thing to gather at each value,
    and a block list counts each on a line of its own. `block` is an id, with
    or without `minecraft:`.
    """
    global _variants
    if _variants is None:
        definition = lookup.entries("block_definition.json")
        found = rules()
        _variants = {name: found.get(family, {}).get("texture_by", {}).get("state")
                     for name, family in definition.items()}
    return _variants.get(str(block).replace("minecraft:", ""))


def rotations():
    """Every family's rotation table, a reference to a state's standard turns
    replaced by those turns."""
    states = read(STATES)["states"]
    return {family: (dict(states[table]) if isinstance(table, str) else table)
            for family, table in read(ROTATION)["families"].items()}


def table(name):
    """A geometry table the way the columns had it, by its old name:
    `block_shapes`, `block_uv` or `block_rotation`, every turn spelled out."""
    if name == "block_rotation":
        return rotations()
    shapes, uvs = load()
    return {"block_shapes": shapes, "block_uv": uvs}[name]


## the keys every lookup table opens with, in order; see scaffold/lookup.py
HEADER = ("$schema", "format", "minecraft", "about")


def header(schema, minecraft, about=None):
    found = {"$schema": "schema/%s" % schema, "format": FORMAT, "minecraft": minecraft}
    if about:
        found["about"] = about
    return found


def _line(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def render_geometry(document):
    """block_geometry.json as text: a cube a line, so a change to one cube is a
    change to one line."""
    out = ["{"]
    for key in HEADER:
        if key in document:
            out.append("\t%s: %s," % (json.dumps(key), _line(document[key])))
    out.append('\t"families": {')
    families = document["families"]
    for f, family in enumerate(sorted(families)):
        out.append("\t\t%s: {" % json.dumps(family))
        ## the rules first, a line each, then the forms they choose between
        for rule in RULES:
            if rule in families[family]:
                out.append("\t\t\t%s: %s," % (json.dumps(rule),
                                              _line(families[family][rule])))
        sections = [s for s in ("forms", "low") if s in families[family]]
        for s, section in enumerate(sections):
            out.append("\t\t\t%s: {" % json.dumps(section))
            forms = families[family][section]
            for n, form in enumerate(forms):
                body = forms[form]
                out.append("\t\t\t\t%s: {" % json.dumps(form))
                out.append('\t\t\t\t\t"center": %s,' % _line(body["center"]))
                out.append('\t\t\t\t\t"cubes": [')
                for c, cube in enumerate(body["cubes"]):
                    out.append("\t\t\t\t\t\t%s%s" % (
                        _line(cube), "," if c < len(body["cubes"]) - 1 else ""))
                out.append("\t\t\t\t\t]")
                out.append("\t\t\t\t}%s" % ("," if n < len(forms) - 1 else ""))
            out.append("\t\t\t}%s" % ("," if s < len(sections) - 1 else ""))
        out.append("\t\t}%s" % ("," if f < len(families) - 1 else ""))
    out.append("\t}")
    out.append("}")
    return "\n".join(out) + "\n"


def render_table(document, key):
    """A table of families or states, one entry a line."""
    out = ["{"]
    for name in HEADER:
        if name in document:
            out.append("\t%s: %s," % (json.dumps(name), _line(document[name])))
    out.append("\t%s: {" % json.dumps(key))
    entries = document[key]
    for n, name in enumerate(sorted(entries)):
        out.append("\t\t%s: %s%s" % (json.dumps(name), _line(entries[name]),
                                     "," if n < len(entries) - 1 else ""))
    out.append("\t}")
    out.append("}")
    return "\n".join(out) + "\n"
