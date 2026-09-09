"""What Scaffold silently drops when it builds the bundled test structures.

test_structures/ is the regression suite: between them the files name several
hundred distinct block ids across every shape family, so a lookup change that
breaks a family shows up here as blocks moving into the skipped list.

    python -m tools.checks.coverage                 build everything, report
    python -m tools.checks.coverage --verbose        name the structures too
    python -m tools.checks.coverage --limit 20       first 20 structures only

This drives the real pipeline rather than reimplementing it, so the block states
are translated exactly as a user's build would translate them and the answer is
whatever `get_skipped()` says. A block that fails to resolve is not an error:
`make_block` raises, `_add_blocks_to_geo` catches it, and the block is recorded
as unsupported. That is why a missing lookup entry produces a quietly
incomplete model instead of a crash, and why this report is the only place it
becomes visible.

Nothing is written outside the temporary build directories, which are removed
on the way out.
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scaffold import core
def structures():
    return sorted(glob.glob(os.path.join("test_structures", "*.mcstructure")))


def survey(paths, quiet=True):
    """Generate against each structure and collect what it could not build.

    Returns (skipped, built, unreadable) where skipped maps a block id to
    {variant: {"count": n, "files": {name}}}.
    """
    skipped = collections.defaultdict(
        lambda: collections.defaultdict(lambda: {"count": 0, "files": set()}))
    unreadable, built = [], 0
    devnull = open(os.devnull, "w")
    for path in paths:
        name = os.path.basename(path)
        pack = None
        stdout = sys.stdout
        try:
            pack = core.scaffold(os.path.join("coverage_probe"))
            pack.add_model("probe", path)
            pack.set_model_offset("probe", [0, 0, 0])
            if quiet:
                sys.stdout = devnull          # the pipeline narrates its progress
            pack.generate_with_nametags()
            sys.stdout = stdout
            for block, variants in pack.get_skipped(write_file=False).items():
                for variant, count in variants.items():
                    entry = skipped[block][variant]
                    entry["count"] += count
                    entry["files"].add(name)
            built += 1
        except Exception as exc:
            sys.stdout = stdout
            unreadable.append((name, "%s: %s" % (type(exc).__name__, exc)))
        finally:
            sys.stdout = stdout
            if pack is not None:
                pack.cleanup()
            for leftover in glob.glob("coverage_probe*"):
                if os.path.isfile(leftover):
                    os.remove(leftover)
    devnull.close()
    return skipped, built, unreadable


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", action="store_true",
                    help="name the structures each skipped block appears in")
    ap.add_argument("--limit", type=int, default=0,
                    help="only build the first N structures")
    args = ap.parse_args()

    paths = structures()
    if args.limit:
        paths = paths[:args.limit]

    skipped, built, unreadable = survey(paths)

    total = sum(e["count"] for v in skipped.values() for e in v.values())
    print("structures built  : %d of %d" % (built, len(paths)))
    print("blocks skipped    : %d distinct, %d placed" % (len(skipped), total))

    if unreadable:
        print("\n=== COULD NOT BUILD (%d) ===" % len(unreadable))
        for name, exc in unreadable:
            print("   %-46s %s" % (name, exc))

    if skipped:
        print("\n=== SKIPPED BLOCKS (%d) ===" % len(skipped))
        ranked = sorted(skipped.items(),
                        key=lambda kv: -sum(e["count"] for e in kv[1].values()))
        for block, variants in ranked:
            count = sum(e["count"] for e in variants.values())
            files = set().union(*(e["files"] for e in variants.values()))
            names = ", ".join(sorted(v for v in variants if v != "default"))
            print("   %-38s %6d placed  %2d structures%s" %
                  (block, count, len(files), ("  [%s]" % names) if names else ""))
            if args.verbose:
                for f in sorted(files):
                    print("        %s" % f)
    else:
        print("\nEvery block in the bundled structures builds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
