"""Put together what Structura's developer needs to take Scaffold's tables.

    python -m tools.export.handoff
    python -m tools.export.handoff --output <folder>

Writes `handoff/structura/`, which git ignores, from the tree as it is now:

  README.md                the guide: what changed and the two ways to take it
  Lookup Format 2.md       the specification, docs/Lookup Format 2.md
  From Structura 1.7.md    what is particular to Structura, tools/export/From Structura 1.7.md
  lookups/                 the format 2 tables and their schemas
  converter/               converts format 2 to Structura 1.7's tables, alone

**The converter runs without a Scaffold checkout.** It is
`tools/export/structura.py` with what it draws through: the `scaffold` package
less its window, the gallery and the renderer it reads its cases from, and two
small data files in place of what a checkout reads from elsewhere. Mojang's
block list comes from `bedrock-samples`, a submodule, and the states each block
is commonly saved with come from scanning the test structures, fifty megabytes
of them; both are written out here as JSON and the converter reads those.

Run it again after the tables change: the handoff is a copy, not a link.
Not shipped.
"""
import argparse
import io
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools import sources

OUT = os.path.join(ROOT, "handoff", "structura")
## the format 2 tables Structura would read, and their schemas
TABLES = ("block_geometry.json", "block_rotation.json", "state_rotations.json",
          "block_definition.json", "block_upgrades.json", "dust_connections.json")
## what the converter draws through; the window and its art are left out
PACKAGE_LEAVES_OUT = ("ui", "fonts", "images", "__pycache__", "tweakpacks", "techpack")
TOOLS = ("tools/__init__.py", "tools/sources.py", "tools/checks/__init__.py",
         "tools/checks/gallery.py",
         "tools/checks/render.py", "tools/checks/worldfile.py", "tools/checks/trials.py",
         "tools/checks/tweak_blocks.py", "tools/export/__init__.py",
         "tools/export/structura.py")

CONVERT = '''"""Convert Scaffold's format 2 tables to Structura 1.7's.

    python convert.py <out>
    python convert.py <out> --report

Writes a `lookups/` and a `Vanilla_Resource_Pack/` in 1.7's own format into
<out>, to copy over a Structura 1.7 checkout. `--report` also lists every case
1.7's code cannot draw the way Scaffold does. Needs Python 3.11 or newer, with
numpy, Pillow and nbtlib: `pip install numpy pillow nbtlib`.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tools.checks import gallery

## what a Scaffold checkout reads from a submodule and from its test
## structures, written out when this folder was made
gallery.MOJANG = os.path.join(HERE, "data", "mojang-blocks.json")
with open(os.path.join(HERE, "data", "observed.json"), encoding="utf-8") as f:
    _observed = json.load(f)
gallery.observed = lambda: (_observed["states"], _observed["newest"])

from tools.export import structura

if __name__ == "__main__":
    sys.exit(structura.main(sys.argv[1:]))
'''

GUIDE = '''# Scaffold's block tables, for Structura

Written for whoever maintains Structura. Scaffold grew out of Structura 1.7, and
its block tables started as Structura's `lookups/`. Since then they have been
rebuilt as **format 2**, and a great many blocks have been reshaped to match
the game. This folder has everything needed to take them, either way round.

Made from Scaffold {version}, tables checked against Minecraft {minecraft}.

## What is here

| | |
| --- | --- |
| `From Structura 1.7.md` | how the files map onto 1.7's, every breaking change, what reading format 2 directly would take, and what the converter cannot carry |
| `Lookup Format 2.md` | the specification: every file, every key, how a form is chosen, and what drawing a block needs beyond the tables |
| `lookups/` | the format 2 tables, and a JSON schema for each geometry file in `lookups/schema/` |
| `converter/` | converts the format 2 tables to 1.7's, with no Scaffold checkout needed |

## Two ways to take the tables

**1. Keep Structura 1.7's code and convert the tables.** Nothing in Structura
changes.

```
cd converter
pip install numpy pillow nbtlib
python convert.py <out>
```

`<out>` gets a `lookups/` and a `Vanilla_Resource_Pack/` in 1.7's own layout, to
copy over a Structura 1.7 checkout. Some blocks come out approximate, because
1.7's code cannot express them: words as data values, a second rotation state,
block entities. `python convert.py <out> --report` lists each one, and the last
section of `From Structura 1.7.md` says why.

The converter does not translate format 2 by rule. It draws every state of every
block through Scaffold's own code, which ships inside `converter/`, and files
what each would show under the key 1.7 would pick it by. So what it writes is
what Scaffold draws, as near as 1.7 can say it.

**2. Read format 2 directly.** The rules engine that picks a form is about
sixty lines. Around it Structura would also need to translate old blocks as a
structure is read, read the texture object on every face of every cube, lay
its texture sheet out as a grid, and read the block entity beside each block.
`Lookup Format 2.md` is the specification, and "What it would take for
Structura to read format 2" in `From Structura 1.7.md` walks through that work
piece by piece.
Scaffold's reference implementation is `scaffold/block_geometry.py`,
`scaffold/block_upgrade.py`, and `ArmorStandGeo.choose`, `make_block` and
`trim_plane` in `scaffold/pack/armor_stand_geo_class.py`, all MIT licensed like
Structura, and all inside `converter/` here.

Taken this way, with block entities read as well, every block comes out as
Scaffold draws it. Some of what the engine does is not in the tables and is
worth porting with it; "Drawing what the tables describe" in the
specification has each:

- **Draw order is the bones' names.** Every cutout seen in Scaffold's test
  worlds fits the game drawing a model's bones sorted by name, with only the
  order of cubes within one bone holding as the camera moves. Scaffold names
  its tiers so they sort (`slice_` for blocks, `tier1_` for planes, `tier2_`
  for water, `early_` before them all), and draws a
  block's water and a container's count in the block's own bone, after it.
- **Planes are cut to the painted part of their picture**, so their clear
  texels hide as little as they can.
- **Water is drawn in pieces**, sides after the block it stands in and its top
  before or after depending on that block.
- **Redstone dust's joins are worked out from its neighbours**, since Bedrock
  saves none, by the rules in `dust_connections.json`.

Without these a blended ghost shows holes where a clear texel hides what is
behind it, and holes that come and go as the camera moves.

## Things to know before starting

- **Current block ids only.** An old structure's ids and states are translated
  as it is read, through `block_upgrades.json`. A reader of format 2 has to do
  that too; the converter does it for 1.7 by writing tables for the old ids.
- **Minecraft's frame.** Blocks rest facing north, and rotation tables hold
  Minecraft's angles. A bone turns the other way about y and z, which is one
  conversion in one place.
- **Some states exist only in a structure saved by Minecraft 26.50 or newer**:
  stair corners, and the joins of fences, panes, bars and string. Older saves
  draw those blocks unjoined and straight.
- **The atlas is a grid**, 64 tiles wide, and must stay one: a single column of
  a thousand textures is taller than a graphics card holds.

## Questions

Scaffold's issue tracker is the place, and the tables' history is in its git
log.
'''


def observed():
    """The states each block is commonly saved with, from the test structures."""
    from tools.checks import gallery
    states, newest = gallery.observed()
    return {"states": states, "newest": newest}


def copy_tree(source, target, leave_out=()):
    def ignore(folder, names):
        return [n for n in names if n in leave_out or n.endswith(".pyc")]
    shutil.copytree(source, target, ignore=ignore)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=OUT)
    args = parser.parse_args(argv)
    out = args.output
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    from scaffold import version
    geometry = json.load(io.open(os.path.join(ROOT, "scaffold", "lookups", "block_geometry.json"),
                                 encoding="utf-8"))
    io.open(os.path.join(out, "README.md"), "w", encoding="utf-8").write(
        GUIDE.format(version=version.read(), minecraft=geometry.get("minecraft", "")))
    shutil.copy(os.path.join(ROOT, "docs", "Lookup Format 2.md"), out)
    shutil.copy(os.path.join(ROOT, "tools", "export", "From Structura 1.7.md"), out)

    lookups = os.path.join(out, "lookups")
    os.makedirs(lookups)
    for name in TABLES:
        shutil.copy(os.path.join(ROOT, "scaffold", "lookups", name), lookups)
    shutil.copytree(os.path.join(ROOT, "scaffold", "lookups", "schema"),
                    os.path.join(lookups, "schema"))

    converter = os.path.join(out, "converter")
    copy_tree(os.path.join(ROOT, "scaffold"), os.path.join(converter, "scaffold"),
              PACKAGE_LEAVES_OUT)
    for name in TOOLS:
        target = os.path.join(converter, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        source = os.path.join(ROOT, name)
        if os.path.isfile(source):
            shutil.copy(source, target)
        else:
            io.open(target, "w").close()
    shutil.copy(os.path.join(ROOT, "pyproject.toml"), converter)
    data = os.path.join(converter, "data")
    os.makedirs(data)
    shutil.copy(sources.metadata("vanilladata_modules",
                             "mojang-blocks.json"), data)
    json.dump(observed(), io.open(os.path.join(data, "observed.json"), "w", encoding="utf-8"),
              sort_keys=True)
    io.open(os.path.join(converter, "convert.py"), "w", encoding="utf-8").write(CONVERT)
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
