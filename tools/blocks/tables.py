"""Change one family in a lookup table, and nothing else.

The generators think in the columns the geometry tables used to be kept in: a
family's shapes, `SHAPES`, and the windows its faces read, `UV`, each a list per
cube. Both live in `lookups/block_geometry.json` now (see
`scaffold/block_geometry.py`), so `put` and `load` translate: a generator puts
one column and the other is read back from the file, or from what the same run
put a moment ago, and the family is written whole. The file is written in one
fixed layout, so a change to one family changes only that family's lines.

`ROTATION` is `lookups/block_rotation.json`, and a generator hands it
Minecraft's own angles, or the name of a state in `lookups/state_rotations.json`
whose angles the family turns by. A table that is exactly one of those states'
own is written as that state's name, and `load` reads the name back as the table.

Every generator writes its families in Minecraft's frame: resting facing north,
in the coordinates a Bedrock `.geo.json` uses. Nothing here turns anything.

Not shipped. The generated pack reads the tables, never this.
"""
import io
import json
import os

from scaffold import block_geometry as geometry
from scaffold import lookup

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
GEOMETRY = os.path.join(LOOKUPS, geometry.GEOMETRY)
STATES = os.path.join(LOOKUPS, geometry.STATES)
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, geometry.ROTATION)
## the two columns a family's geometry is put and read in; both are kept in
## GEOMETRY, and neither is a file of its own
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")

## the columns this run has put, family by family, so the second of a pair is
## matched with the first rather than with what the file held before either
_put = {}


def _kind(path):
    """Which of the three geometry tables a path is, if any."""
    here = os.path.normcase(os.path.abspath(path))
    for table, kind in ((SHAPES, "shapes"), (UV, "uv"), (ROTATION, "rotation")):
        if here == os.path.normcase(os.path.abspath(table)):
            return kind
    return None


def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _states():
    return _read(STATES)["states"]


def _family(name):
    """The family a column entry belongs to, and which of its sections."""
    if name.endswith(geometry.LOW_SUFFIX):
        return name[:-len(geometry.LOW_SUFFIX)], "low"
    return name, "forms"


def _columns(document):
    return geometry.columns(document["families"])


def _write_geometry(document):
    text = geometry.render_geometry(document)
    io.open(GEOMETRY, "w", encoding="utf-8", newline="").write(text)
    ## a malformed edit should fail here rather than in a build weeks later
    json.loads(io.open(GEOMETRY, encoding="utf-8").read())


def _write_rotation(document):
    text = geometry.render_table(document, "families")
    io.open(ROTATION, "w", encoding="utf-8", newline="").write(text)
    json.loads(io.open(ROTATION, encoding="utf-8").read())


def _same_turns(table, standard):
    if set(table) != set(standard):
        return False
    for key, turn in table.items():
        for a, b in zip(turn, standard[key]):
            gap = (float(a) - float(b)) % 360
            if min(gap, 360 - gap) > 1e-6:
                return False
    return True


def named_state(table):
    """The state whose own turns a table is exactly, or None."""
    for state, standard in _states().items():
        if _same_turns(table, standard):
            return state
    return None


def load(path):
    """A whole table, as the columns the generators write."""
    kind = _kind(path)
    if kind in ("shapes", "uv"):
        shapes, uvs = _columns(_read(GEOMETRY))
        return shapes if kind == "shapes" else uvs
    if kind == "rotation":
        states = _states()
        return {family: (dict(states[value]) if isinstance(value, str) else value)
                for family, value in _read(ROTATION)["families"].items()}
    return _read(path)


def put(path, name, value, tight=False):
    """Replace a family if the table has it, or add it if it does not.

    `tight` is kept for the generators that pass it; the layout is fixed.
    """
    kind = _kind(path)
    if kind is None:
        raise ValueError("%s is not a table this writes" % path)
    if kind == "rotation":
        document = _read(ROTATION)
        what = "replaced" if name in document["families"] else "added"
        ## a state's name stands for that state's own turns
        document["families"][name] = value if isinstance(value, str)             else named_state(value) or value
        _write_rotation(document)
        return what

    document = _read(GEOMETRY)
    shapes, uvs = _columns(document)
    held = _put.setdefault(name, {})
    held[kind] = value
    shape = held.get("shapes", shapes.get(name))
    windows = held.get("uv", uvs.get(name))
    family, section = _family(name)
    what = "replaced" if family in document["families"] and \
        section in document["families"][family] else "added"
    if shape is None or windows is None:
        ## the first half of a new family: written once the other half is put
        return "held"
    forms, problems = geometry.family_from_columns(shape, windows)
    if problems and "shapes" in held and "uv" in held:
        raise ValueError("%s: %s" % (name, "; ".join(problems)))
    document["families"].setdefault(family, {})[section] = forms
    _write_geometry(document)
    return what


def drop(path, name):
    """Remove a family, if it is there."""
    kind = _kind(path)
    _put.pop(name, None)
    if kind == "rotation":
        document = _read(ROTATION)
        if name not in document["families"]:
            return False
        del document["families"][name]
        _write_rotation(document)
        return True
    document = _read(GEOMETRY)
    family, section = _family(name)
    entry = document["families"].get(family)
    if not entry or section not in entry:
        return False
    del entry[section]
    ## rules with no forms left to choose between are nothing
    if "forms" not in entry:
        del document["families"][family]
    _write_geometry(document)
    return True


def rules(family, **found):
    """Set a family's rules for choosing a form, a turn and a texture.

    Each keyword is one of `pick`, `data`, `turn_by` and `texture_by`, as
    `scaffold/block_geometry.py` reads them; one given as None is removed. The
    family has to have been written first.
    """
    document = _read(GEOMETRY)
    entry = document["families"][family]
    for key, value in found.items():
        if key not in geometry.RULES:
            raise ValueError("%s is not a rule" % key)
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
    _write_geometry(document)


def definitions():
    """Every block id and the family it is drawn with."""
    return lookup.unwrap("block_definition.json", lookup.load(DEFINITION))


def define(blocks, family):
    """Point block ids at a family, leaving the rest of the file alone."""
    table = definitions()
    for block in blocks:
        table[block] = family
    lookup.save_entries(DEFINITION, table)


def forms(family, written, section="forms"):
    """Replace one family's forms, given whole in format 2.

    For a family simple enough to be written as it is read, with no columns in
    between. Its rules are kept.
    """
    document = _read(GEOMETRY)
    _put.pop(family, None)
    document["families"].setdefault(family, {})[section] = written
    _write_geometry(document)
    print("   %-18s %s" % (family, ", ".join(written)))


def write(family, forms, center=(8, 8, 8)):
    """Replace one family's shapes and UV windows, one variant at a time."""
    from tools.blocks.geometry import build

    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes, center)
    put(SHAPES, family, shapes, tight=True)
    put(UV, family, uvs, tight=True)
    print("   %-18s %s" % (family, ", ".join(forms)))


def turns(family, table):
    """Replace one family's rotation table."""
    put(ROTATION, family, table, tight=True)


def unturn(family):
    """Take away a rotation table, for a family that reads no rotation state.

    A family with no facing of its own never has one looked up: `rot` comes back
    None and `_add_blocks_to_geo` does not ask. An entry left in the table is
    dead weight that reads as though it did something.
    """
    return drop(ROTATION, family)
