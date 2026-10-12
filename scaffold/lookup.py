"""The lookup tables' common shape, and reading one whatever its age.

Every table in `lookups/` opens with the same header, in this order:

  "$schema"    the schema it is checked against, where there is one
  "format"     2, the shape of the tables this version of Scaffold reads
  "minecraft"  the Minecraft version it was checked against, where what it
               holds describes the game
  "about"      one line on what it holds

and then what it holds, under one key named for it or a few. `entries` hands
back what a one-key table holds. A table written before the header, a map at
the top level with nothing round it, is read as what it holds, so one somebody
has edited and dropped beside the executable keeps working.
"""
import io
import json

from scaffold import paths

FORMAT = 2
MINECRAFT = "26.50"
HEADER = ("$schema", "format", "minecraft", "about")
## the key each one-key table keeps what it holds under
ENTRIES = {
    "block_definition.json": "blocks",
    "item_icons.json": "icons",
    "language_colors.json": "languages",
    "tweaks.json": "tweaks",
    "stack_sizes.json": "stacks",
}


def load(path):
    """A table's whole document, read from `path`."""
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def read(name):
    """A shipped table's whole document, by its file name."""
    return load(paths.lookup(name))


def unwrap(name, document):
    """What a one-key table holds, from its whole document; a table with no
    header is what it holds."""
    key = ENTRIES.get(name)
    if key and isinstance(document, dict) and "format" in document and key in document:
        return document[key]
    return document


def entries(name):
    """What a shipped one-key table holds."""
    return unwrap(name, read(name))


def save(path, document):
    """A document written the way every table but the geometry tables is: tab
    indented, a key a line. The geometry tables keep a cube to a line, and
    `tools/blocks/tables.py` writes them."""
    body = json.dumps(document, indent="\t", ensure_ascii=False)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(body + "\n")


def save_entries(path, held):
    """Write what a one-key table holds, keeping the header it has."""
    import os
    name = os.path.basename(path)
    document = load(path) if os.path.isfile(path) else {}
    if not (isinstance(document, dict) and "format" in document):
        document = {"format": FORMAT}
    document[ENTRIES[name]] = held
    save(path, document)
