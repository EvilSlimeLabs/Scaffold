"""Find something in the tables by any of the names it might have.

    python -m tools.find banner                 blocks, which is what it assumes
    python -m tools.find block "Raw Iron"
    python -m tools.find block '*_slab'
    python -m tools.find texture planks

Things in this project have more than one name, and which one you remember is
not usually the one the tables are keyed by. A banner is `standing_banner` to
`block_definition.json`, "Banner" to a block list, and `standing_banner` again
as a shape family. A plank texture is `planks_oak` in the pack Bedrock ships and
`oak_planks` everywhere a person would look for it.

Each search is one entry in `KINDS`. Adding another is writing a function that
takes a search and returns rows, and naming it there; the dispatching, the
ranking and the printing are already here.

Nothing here is needed at run time.
"""
import argparse
import difflib
import fnmatch
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scaffold import paths
## the one list of blocks no pack ships textures for, borrowed rather than
## written again: a third copy of it would be a third thing to keep in step
from tools.checks.render import UNRESOLVABLE

## A block with this family is declared so a structure holding one is named
## rather than mysterious, and is not drawn at all.
IGNORED = "ignore"

## What a texture search will open. The pack is nearly all PNG; a few legacy
## files are TGA and `extend_uv_image` falls back to one when a PNG is missing.
PICTURES = (".png", ".tga")


def _ordered(variants):
    """Variants in the order somebody reads them.

    Sorted as text, a banner's sixteen colours run 0, 1, 10, 11, 2 -- correct
    and unreadable. Numbers go first and in numeric order, names after them in
    alphabetical order, because a family is usually a run of numbered states
    with a handful of named ones on the end.
    """
    return sorted(variants,
                  key=lambda name: (0, int(name), "") if name.isdigit()
                  else (1, 0, name))


def _read(name):
    with io.open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _patterned(search):
    """Whether a search is a shell pattern rather than a piece of text."""
    return any(mark in search for mark in "*?[")


def _rank(search, fields):
    """How well a row answers a search, or None for not at all.

    Lower is better. Being what was typed beats starting with it, which beats
    containing it, and the first field beats the second: somebody typing
    `lectern` wants the lectern before every block whose *name* happens to hold
    those letters. `fields` is therefore in the order they are worth.
    """
    for depth, values in enumerate(fields):
        values = [value.lower() for value in values if value]
        if any(value == search for value in values):
            return depth * 3
        if any(value.startswith(search) for value in values):
            return depth * 3 + 1
        if any(search in value for value in values):
            return depth * 3 + 2
    return None


# --- blocks ------------------------------------------------------------------

def blocks(search):
    """Every block whose id, list name or shape family answers the search."""
    families, shapes, names = (_read("block_definition"), _read("block_shapes"),
                               _read("block_list")["names"])
    ## `minecraft:lectern` and `lectern` should find the same block, since one
    ## is what the game prints and the other is what the tables hold
    if search.startswith("minecraft:"):
        search = search[len("minecraft:"):]

    found = []
    for block, family in families.items():
        shown = sorted({label for label
                        in names.get("minecraft:" + block, {}).values()})
        if _patterned(search):
            rank = 0 if fnmatch.fnmatchcase(block, search) else None
        else:
            rank = _rank(search, ([block], shown, [family]))
        if rank is None:
            continue
        drawn = family != IGNORED and not UNRESOLVABLE.match(block)
        found.append((rank, block, {
            "called": ", ".join(shown) or "-",
            "family": family if family != block else None,
            ## Labelled with the flag they go to rather than "variants", which
            ## is the trap: `make_block` picks a form by matching `str(data)`
            ## against these keys, so they are `--data` values. `--variant` is a
            ## different axis entirely -- which texture to take out of a
            ## terrain_texture list -- and passing one of these to it silently
            ## draws the default.
            "--data": _ordered(list(shapes.get(family, {}))),
            "draw": ("python -m tools.render " + block) if drawn else
                    ("not drawn: " +
                     ("declared `ignore`, so it is named but never drawn"
                      if family == IGNORED else
                      "no vanilla pack ships a texture for it")),
        }))
    return found


def block_neighbours(search):
    families = _read("block_definition")
    names = _read("block_list")["names"]
    words = set(families)
    for labels in names.values():
        words.update(label.lower() for label in labels.values())
    return difflib.get_close_matches(search, sorted(words), n=6, cutoff=0.6)


# --- textures ----------------------------------------------------------------

def textures(search):
    """Every picture in the vanilla pack whose path answers the search.

    What a `block_uv.json` overwrite entry names is a path under the pack with
    no extension -- `textures/blocks/planks_oak` -- so that is what this prints,
    ready to paste. The size comes with it because it decides how the entry has
    to be written: only the top left sixteen square of a file becomes a tile, so
    anything bigger needs a window and anything saved at the wrong scale is a
    hole in the model rather than a blurry block.
    """
    pack = paths.vanilla_pack()
    found = []
    for here, _dirs, files in os.walk(os.path.join(pack, "textures")):
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() not in PICTURES:
                continue
            full = os.path.join(here, name)
            ## the name an entry writes: pack relative, forward slashes, no
            ## extension, which is what `split_window` hands to the atlas
            named = os.path.relpath(full, pack).replace(os.sep, "/")
            named = named[:-len(ext)]
            if _patterned(search):
                rank = 0 if (fnmatch.fnmatchcase(stem, search)
                             or fnmatch.fnmatchcase(named, search)) else None
            else:
                rank = _rank(search, ([stem], [named]))
            if rank is None:
                continue
            found.append((rank, named, {"size": _measured(full)}))
    return found


def _measured(full):
    from PIL import Image

    try:
        with Image.open(full) as picture:
            wide, tall = picture.size
    except Exception as trouble:
        return "unreadable (%s)" % type(trouble).__name__
    note = ""
    if (wide, tall) == (16, 16):
        note = "  one tile"
    elif wide >= 16 and tall >= 16:
        note = "  bigger than a tile: needs a #x,y window"
    else:
        note = "  smaller than a tile"
    return "%dx%d%s" % (wide, tall, note)


def texture_neighbours(search):
    pack = os.path.join(paths.vanilla_pack(), "textures")
    stems = set()
    for _here, _dirs, files in os.walk(pack):
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() in PICTURES:
                stems.add(stem)
    return difflib.get_close_matches(search, sorted(stems), n=6, cutoff=0.6)


# --- the kinds, and the dispatch ---------------------------------------------

KINDS = {
    "block": {"search": blocks, "near": block_neighbours,
              "about": "block ids, block list names and shape families"},
    "texture": {"search": textures, "near": texture_neighbours,
                "about": "pictures in the vanilla pack, as an overwrite "
                         "entry would name them"},
}
DEFAULT_KIND = "block"


def report(found, search, kind, limit, out=sys.stdout):
    """Print what was found, likeliest first."""
    found.sort(key=lambda row: (row[0], row[1]))
    shown = found[:limit]
    for _rank, name, about in shown:
        print(name, file=out)
        for label, value in about.items():
            if not value:
                continue
            if isinstance(value, list):
                if value == ["default"]:
                    continue
                ## keep the end as well as the beginning. A family's numbered
                ## states run first and its named ones last, and the named ones
                ## are the whole reason to read this: nobody guesses `illager`
                ## from a list that stops at 11.
                if len(value) > 14:
                    value = value[:9] + ["..."] + value[-4:]
                value = ", ".join(value)
            print("    %-9s %s" % (label, value), file=out)
        print(file=out)

    left = len(found) - len(shown)
    if left:
        print("and %d more; -n to see further" % left, file=out)
    else:
        print("%d %s match%s" % (len(found), kind,
                                 "" if len(found) == 1 else "es"), file=out)


EXAMPLES = """\
Kinds:
%s
Examples:
  python -m tools.find banner                   a block, by whichever of its
                                                names you happen to remember
  python -m tools.find block "Raw Iron"         the name a block list prints
  python -m tools.find block '*_slab'           a shell pattern on the block id
  python -m tools.find block minecraft:lectern  the prefix is ignored
  python -m tools.find texture planks           a picture, named the way an
                                                overwrite entry has to name it
  python -m tools.find texture '*banner*' -n 5  five at a time
  python -m tools.find texture lectern --names  bare names, one per line

A search with no * or ? is a piece of text looked for in every name the kind
carries. One with them is a shell pattern, matched whole. Nothing found gets
you the nearest few. The exit status is 0 when something matched and 1 when
nothing did, so this can decide something in a script.
"""


def _kinds():
    """The kinds, laid out one per line for the help."""
    width = max(len(name) for name in KINDS)
    return "".join(
        "  %-*s  %s%s\n" % (width, name, what["about"],
                            " (the default)" if name == DEFAULT_KIND else "")
        for name, what in sorted(KINDS.items()))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python -m tools.find",
        usage="python -m tools.find [KIND] SEARCH [options]",
        description="Find a block, or a texture, by any of the names it might "
                    "have.",
        epilog=EXAMPLES % _kinds(),
        ## the examples are laid out on purpose and argparse would reflow them
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="*", metavar="WORDS",
                    help="what to look for, with the kind in front of it when "
                         "it is not a block")
    ap.add_argument("-n", "--limit", type=int, default=20,
                    help="how many to print (default 20)")
    ap.add_argument("--names", action="store_true",
                    help="just the names, one per line, for feeding to "
                         "something else")
    args = ap.parse_args(argv)

    ## Asked for nothing, show what there is to ask for. A bare "the following
    ## arguments are required" says what is missing and nothing about what would
    ## go there, which is the whole question when a tool is new.
    if not args.words:
        ap.print_help()
        return 1

    ## "find texture planks" names a kind, "find planks" does not, and "find
    ## block" is looking for the word block rather than naming a kind with
    ## nothing to look for
    words = list(args.words)
    if len(words) > 1 and words[0] in KINDS:
        kind = words.pop(0)
    else:
        kind = DEFAULT_KIND
    search = " ".join(words).strip().lower()

    what = KINDS[kind]
    found = what["search"](search)

    if args.names:
        for _rank, name, _about in sorted(found)[:args.limit]:
            print(name)
        return 0 if found else 1

    if not found:
        print("nothing in %ss matches %r" % (kind, search))
        maybe = what["near"](search)
        if maybe:
            print("did you mean: %s" % ", ".join(maybe))
        return 1

    report(found, search, kind, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
