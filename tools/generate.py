"""Run every generator, in the order they have to run in.

    python -m tools.generate              all of it
    python -m tools.generate --list       what would run, and in what order
    python -m tools.generate blocks       only the steps whose name starts here

Scaffold's lookup tables and half of its textures are generated rather than
written by hand, and a table generated from an older version of the script that
writes it is the kind of thing nobody notices until a block is wrong in game. So
`build.py` runs this before it freezes anything, and what ships is always the
current generation of every table.

**The order is not alphabetical and it matters.** `blocks.simplify` reads the
shape families and writes a simplified form of each, so it has to run after
everything that writes one; run it earlier and the low geometry still outlines
the shapes as they were. `blocks.faces` copies the plain cube family for the
blocks it gives a texture per cube, so it wants the families settled too.

**What is deliberately not here.** `app.screenshots` needs a window on screen
and refuses to save unless its own is in front, so it cannot run unattended.
`vendor.tech_pack` and `vendor.vanilla_pack` copy out of the git submodules,
which are not part of a release build and whose diffs are meant to be read
before they are applied. `checks.*` ask questions rather than change anything.
All four are run by hand.
"""
import argparse
import importlib
import sys
import time

## Every generator, in the order it has to run. The text beside each is what it
## writes, for the line printed as it runs.
STEPS = [
    ("tools.blocks.mounted", "bells, signs, doors, campfires, pots"),
    ("tools.blocks.growing", "crops, eggs, compost, coral"),
    ("tools.blocks.crossed", "fire, dripstone, sulfur spikes"),
    ("tools.blocks.furniture", "beds, lecterns, conduits"),
    ("tools.blocks.heads", "the mob heads"),
    ("tools.blocks.containers", "the shulker boxes"),
    ("tools.blocks.banners", "standing and wall banners"),
    ("tools.blocks.bookshelf", "the bookshelf's sixty-four states"),
    ("tools.blocks.statues", "the copper golem's four poses"),
    ("tools.blocks.faces", "a texture per cube, per face"),
    ("tools.textures.banners", "the dyed banner sheets"),
    ("tools.textures.beds", "the recoloured beds"),
    ("tools.textures.string", "a string a ghost can be seen with"),
    ## after every shape family, because it reads them
    ("tools.blocks.simplify", "the simplified forms"),
    ("tools.app.icon", "the pack icon and the desktop icon"),
    ("tools.app.fonts", "the bundled typefaces"),
    ("tools.app.languages", "the generated languages"),
]


def chosen(prefixes):
    if not prefixes:
        return STEPS
    picked = [step for step in STEPS
              if any(step[0][len("tools."):].startswith(p) for p in prefixes)]
    if not picked:
        sys.exit("Nothing matches %s. Try --list." % ", ".join(prefixes))
    return picked


def run(steps):
    started = time.time()
    ## Some generators take arguments of their own and read `sys.argv` to find
    ## them. Called from here they would read this script's arguments instead
    ## and refuse to start, so each is given an argv with nothing in it but its
    ## own name, which is what it sees when it is run on its own with no
    ## options.
    mine = sys.argv
    for number, (module, writes) in enumerate(steps, 1):
        print("\n[%d/%d] %s -- %s" % (number, len(steps), module, writes))
        try:
            sys.argv = [module]
            importlib.import_module(module).main()
        except SystemExit as stopped:
            if stopped.code:
                sys.exit("\nGeneration stopped in %s: %s" % (module, stopped.code))
        finally:
            sys.argv = mine
    print("\n%d generated in %.1fs" % (len(steps), time.time() - started))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("only", nargs="*", metavar="PREFIX",
                        help="run only the steps whose name starts with this")
    parser.add_argument("--list", action="store_true",
                        help="print the steps in order and stop")
    args = parser.parse_args(argv)

    steps = chosen(args.only)
    if args.list:
        for number, (module, writes) in enumerate(steps, 1):
            print("%2d  %-26s %s" % (number, module[len("tools."):], writes))
        return 0
    run(steps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
