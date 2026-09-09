"""What a block list calls each block, and which heading it goes under.

A block list is the shopping list for a build, so it is read by somebody
standing at a chest deciding what to gather. Two things make that readable, and
both of them are in one file rather than in the code:

  * **a name**, because `minecraft:polished_deepslate_double_slab` is not what
    the game calls it and not what anyone would say out loud
  * **a heading**, because forty lines in the order the palette happened to be
    in is a list you read twice

`lookups/block_list.json` holds names and `lookups/block_categories.json` holds
categories. `names` is a block id to the name shown, one entry per variant where
a block has variants; `categories` is an ordered list, each with the patterns
that fall under it, and the first one that matches wins.

**A user can supply their own, and it is looked for where the settings file is
looked for.** Beside the executable first, which makes it portable, then the
home directory. Nothing is ever written to either: the file is Scaffold's to
read and the user's to write, and a program that rewrites the file somebody is
editing is a program that loses their work.

**What is found is merged over what ships, not swapped for it.** `names` is a
dictionary, so an entry given for one block replaces that block's and leaves the
other thousand alone: renaming one thing is a four-line file. `categories` is an
ordered list and order is the whole meaning of it, so a file that carries any
categories at all replaces the list outright. Half a list of categories, merged
by name into another, is not something anyone could predict the result of.
"""
import io
import json
import os
import re

from scaffold import paths

## What the file is called wherever a user puts one. The same name in both
## places, the way `.scaffold` is, so there is one thing to remember.
OVERRIDE_CAT_NAME = ".scaffold-blocks.json"
## and what ships, which is the fallback and the worked example
CAT_NAME = "block_categories.json"
BLOCK_NAME = "block_list.json"

## the heading anything unmatched ends up under, so nothing is ever dropped
LEFTOVERS = "Other"

_cached = None


def override_files():
    """Where a user's own file is looked for, best first.

    The same two places as the settings file. Beside the executable only makes
    sense for a compiled build: an installed package sits in site-packages,
    which is shared between everyone using that interpreter.
    """
    found = []
    if paths.frozen():
        found.append(os.path.join(paths.beside_executable(), OVERRIDE_CAT_NAME))
    found.append(os.path.join(os.path.expanduser("~"), OVERRIDE_CAT_NAME))
    return found


def _read(path):
    """One file, or None if it is not there or is not readable as JSON."""
    try:
        with io.open(path, encoding="utf-8-sig") as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def table(reload=False):
    """The names and the categories, with any override merged over the top."""
    global _cached
    if _cached is not None and not reload:
        return _cached

    found_cat = _read(paths.lookup(CAT_NAME)) or {}
    found_list = _read(paths.lookup(BLOCK_NAME)) or {}
    names = dict(found_list.get("names") or {})
    categories = list(found_cat.get("categories") or [])
    ## nearest last, so the one nearest the user has the final say
    for path in reversed(override_files()):
        theirs = _read(path)
        if not theirs:
            continue
        for block, told in (theirs.get("names") or {}).items():
            if isinstance(told, dict):
                names.setdefault(block, {}).update(told)
            else:
                ## a bare string is the shorthand for "whatever variant"
                names.setdefault(block, {})["default"] = told
        if theirs.get("categories"):
            categories = list(theirs["categories"])

    _cached = {"names": names, "categories": categories}
    return _cached


def split(key):
    """A block list key, as the id and the variant it was counted under.

    Two variants of one block are two lines on a list -- a sunflower and a
    peony are both `minecraft:double_plant` and nobody is gathering "double
    plant" -- so the variant travels with the id and is split off here.
    """
    block, slash, variant = str(key).partition("/")
    return block, (variant if slash else "default")


def name_of(key):
    """What to call this block, or the id itself when nothing names it."""
    block, variant = split(key)
    told = table()["names"].get(block) or {}
    return (told.get(variant) or told.get("default")
            or block.replace("minecraft:", ""))


def _matches(pattern, block):
    """A category pattern against a block id, or against an id and a variant.

    Shell-style: `*` stands for any run of characters and nothing else is
    special, which is enough for `*_stairs` and `*copper*` and short enough to
    write by hand. The `minecraft:` on the front is optional, because nobody
    wants to type it forty times.

    **A star does not cross the slash.** That is what makes `*/quartz` mean "a
    quartz one of anything" rather than "anything ending in quartz": without it
    `*/brick` would match `stone_block_slab/nether_brick` by letting the star
    swallow the separator and half the variant with it.
    """
    wanted = str(pattern)
    if ":" not in wanted:
        wanted = "minecraft:" + wanted.lstrip(":")
    parts = [re.escape(piece) for piece in wanted.split("*")]
    return re.fullmatch("[^/]*".join(parts), block) is not None


def category_of(key):
    """The heading this block goes under. The first match wins.

    Matched against the id, and against the id and variant together, because
    some blocks keep what they are made of in the variant rather than in the
    id: every stone slab Bedrock wrote before the names were flattened is a
    `stone_block_slab`, and only the variant says whether it is quartz or
    sandstone or cobblestone.
    """
    block, variant = split(key)
    both = "%s/%s" % (block, variant) if variant != "default" else None
    for entry in table()["categories"]:
        for pattern in entry.get("match") or ():
            if _matches(pattern, block) or (both and _matches(pattern, both)):
                return entry.get("name") or LEFTOVERS
    return LEFTOVERS


def order():
    """The headings in the order the file puts them, leftovers last."""
    told = [entry.get("name") or LEFTOVERS
            for entry in table()["categories"]]
    seen = []
    for name in told + [LEFTOVERS]:
        if name not in seen:
            seen.append(name)
    return seen


def grouped(counts):
    """A block list as headings, each with what goes under it.

    Returns `[(heading, [(name, count), ...]), ...]`, headings in the file's
    order and empty ones left out.

    **Counts are summed by the name, not by the id.** Several ids can be one
    thing to gather -- a double slab and a slab are both slabs, and the table
    calls them the same -- and splitting them across two lines is asking
    somebody to add up in their head at a chest.
    """
    piles = {}
    for key, count in counts.items():
        heading = category_of(key)
        under = piles.setdefault(heading, {})
        name = name_of(key)
        under[name] = under.get(name, 0) + count
    return [(heading, sorted(piles[heading].items()))
            for heading in order() if piles.get(heading)]
