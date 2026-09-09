"""Resolve every block Scaffold claims to support down to a texture file.

    python -m tools.checks.blocks             what is broken here
    python -m tools.checks.blocks --gaps      what the community pack has and this does not
    python -m tools.checks.blocks --tables    block_shapes / block_uv consistency

Bedrock reports none of this. A block whose texture cannot be resolved raises
inside `armorstandgeo.make_block`, `scaffold._add_blocks_to_geo` catches it,
and the block is quietly dropped from the model into the skipped list, so a
stale lookup table shows up as a build with holes in it, never as an error.
"""
import argparse
import os
import re
import sys

## jsonc lives at the repository root: the generated pack reads the
## submodule's JSONC at runtime too, so it is shipped code, not a tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scaffold import jsonc
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
## the data moved inside the package when the project became installable
PACKAGE = os.path.join(ROOT, "scaffold")
OURS = os.path.join(PACKAGE, "Vanilla_Resource_Pack")
COMM = os.path.join(ROOT, "CommunityVanillaResourcePack")

## Education Edition and other blocks that no vanilla pack ships textures for.
## They are declared so structures containing them do not surprise anyone, and
## they will never resolve.
UNRESOLVABLE = re.compile(r"^(element_\d+|chemistry_table|chemical_heat|hard_(stained_)?glass(_pane)?"
                          r"|colored_torch_\w+|underwater_torch|coral_(fan_)?pink_dead)$")


class Pack:
    def __init__(self, root):
        self.root = root
        self.blocks = jsonc.load(os.path.join(root, "blocks.json"))
        self.terrain = jsonc.load(os.path.join(root, "textures/terrain_texture.json"))["texture_data"]
        self.files = set()
        for dirpath, _, filenames in os.walk(os.path.join(root, "textures")):
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), root).replace("\\", "/")
                self.files.add(os.path.splitext(rel)[0])

    def texture_names(self, block):
        if block not in self.blocks:
            raise KeyError("no blocks.json entry")
        layout = self.blocks[block].get("textures")
        if layout is None:
            raise KeyError("blocks.json entry has no textures")
        if isinstance(layout, str):
            return [layout]
        if isinstance(layout, dict):
            return sorted({v for v in layout.values() if isinstance(v, str)})
        return []

    def problems(self, block):
        try:
            names = self.texture_names(block)
        except KeyError as exc:
            return [str(exc).strip("'")]
        found = []
        for name in names:
            if name not in self.terrain:
                found.append("terrain_texture has no '%s'" % name)
                continue
            entry = self.terrain[name]["textures"]
            for item in (entry if isinstance(entry, list) else [entry]):
                path = item["path"] if isinstance(item, dict) else item
                if path not in self.files:
                    found.append("no file for '%s'" % path)
        return found


def report_broken(defs, ours, comm):
    broken = {}
    for block, shape in defs.items():
        if shape == "ignore":
            continue
        problems = ours.problems(block)
        if problems:
            broken[block] = (shape, problems)

    expected = sorted(b for b in broken if UNRESOLVABLE.match(b))
    real = sorted(b for b in broken if not UNRESOLVABLE.match(b))

    declared = sum(1 for v in defs.values() if v != "ignore")
    print("declared blocks: %d   unresolved: %d" % (declared, len(broken)))
    print("\n=== UNRESOLVED (%d) ===" % len(real))
    if not real:
        print("   none")
    for block in real:
        shape, problems = broken[block]
        fixable = comm is not None and not comm.problems(block)
        print("   %-40s %-14s %s%s" % (block, shape, "; ".join(problems)[:70],
                                       "   [community pack has it]" if fixable else ""))
    print("\n=== EXPECTED UNRESOLVED (%d) ===" % len(expected))
    print("   Education Edition and unobtainable blocks; no vanilla pack ships these")
    return len(real)


def report_gaps(defs, comm):
    missing = sorted({k for k in comm.blocks if k != "format_version"} - set(defs))
    print("=== IN THE COMMUNITY PACK, NOT IN block_definition.json (%d) ===" % len(missing))
    print("   see docs/Block Notes.md for what a block needs\n")
    for block in missing:
        print("   " + block)


def report_tables(defs, shapes, uvs):
    used = {v for v in defs.values() if v != "ignore"}
    print("=== shape families with no block_shapes entry ===")
    print("   " + (", ".join(sorted(used - set(shapes))) or "none"))
    print("\n=== shape families with no block_uv entry ===")
    print("   " + (", ".join(sorted(used - set(uvs))) or "none"))
    print("\n=== block_shapes variants that fall back to the default UV ===")
    print("   Expected, not broken. Each of these variants either has no cubes at all")
    print("   or has the same cube sizes as its default in different positions, so the")
    print("   default UV window is the right one. A variant whose cubes are a different")
    print("   SIZE needs its own block_uv entry - that is the case worth catching.")
    found = False
    for shape in sorted(shapes):
        if shape not in uvs:
            continue
        extra = sorted(set(shapes[shape]) - set(uvs[shape]))
        if extra:
            found = True
            print("   %-20s missing %s" % (shape, extra if len(extra) < 8 else "%d variants" % len(extra)))
    if not found:
        print("   none")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gaps", action="store_true",
                        help="list blocks the community pack defines and Scaffold does not")
    parser.add_argument("--tables", action="store_true",
                        help="check block_shapes against block_uv")
    args = parser.parse_args()

    defs = jsonc.load(os.path.join(PACKAGE, "lookups/block_definition.json"))
    ours = Pack(OURS)
    comm = Pack(COMM) if os.path.isdir(COMM) and os.path.isfile(os.path.join(COMM, "blocks.json")) else None

    if args.gaps:
        if comm is None:
            sys.exit("CommunityVanillaResourcePack is not checked out.\n"
                     "  git submodule update --init CommunityVanillaResourcePack")
        report_gaps(defs, comm)
        return
    if args.tables:
        report_tables(defs,
                      jsonc.load(os.path.join(PACKAGE, "lookups/block_shapes.json")),
                      jsonc.load(os.path.join(PACKAGE, "lookups/block_uv.json")))
        return

    unresolved = report_broken(defs, ours, comm)
    sys.exit(1 if unresolved else 0)


if __name__ == "__main__":
    main()
