"""Name everything a block list can show, out of Mojang's own language file.

    python -m tools.blocks.names
    python -m tools.blocks.names --report      say what is missing, write nothing

A block with no name in `block_list.json` is listed as its own id, which is what
somebody reads standing at a chest, and for a long time three hundred and fifty
of them were: every shelf, every wall, every candle, and every block an update
added that nobody went back to name by hand. Mojang ships the answer --
`texts/en_US.lang` in `bedrock-samples` carries a `tile.<id>.name` for thirteen
hundred blocks -- so the gap is filled from there rather than by title-casing
ids and hoping.

**Only gaps are filled.** A name already in the file is left exactly as it is,
whatever Mojang calls that block, because some of them are deliberate: a
standing sign and a wall sign are one thing to gather and share a name that
Mojang has no single key for. That also makes this idempotent, which
`tools/checks/generators.py` insists on.

Four things are tried for each block, in order:

1. **`tile.<id>.name`**, which covers most of them outright.
2. **A name whose value is this id.** Bedrock keeps the flattened ids' names
   under the id they were flattened from -- an andesite wall is
   `tile.cobblestone_wall.andesite.name` -- so every name is indexed by what its
   own text would be called as an id, and `andesite_wall` finds "Andesite Wall"
   without anybody writing that mapping down. It reaches the walls, the mob
   heads, the carpets and the pillars.
3. **`tile.<id>.<variant>.name`**, which gives a name per variant for the ids
   that keep their material in a state: every pre-flattening stone slab is a
   `stone_slab2` and only the variant says whether it is purpur or prismarine.
4. **The id, title-cased.** Nothing is left as a raw id. What reaches here is
   the Education Edition blocks, which no pack ships and Mojang's own texts do
   not name, and a handful that cannot be placed at all -- `movingBlock`,
   `pistonArmCollision`, `reserved6`.

**Entities are named here too**, from `core.ENTITY_MODELS`. A cushion is an
entity, so its name is `entity.cushion.name` and its sixteen colours are
`item.cushion.<colour>.name` -- under the old dye spellings, where light gray is
`silver`, which is why DYE_ALIASES exists.

Needs the `bedrock-samples` submodule. Without it nothing is written and the
names already in the file stand, which is why running a build on a checkout that
has not fetched it is safe.
"""
import argparse
import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scaffold.core import ENTITY_MODELS

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
BLOCK_LIST = os.path.join(LOOKUPS, "block_list.json")
LANG = os.path.join(ROOT, "bedrock-samples", "resource_pack", "texts", "en_US.lang")

## Bedrock's item texts still spell two dyes the way they were spelled before
## the colours were renamed, so a form named for the modern colour has to ask
## for the old one as well.
DYE_ALIASES = {"light_gray": ["silver", "lightGray"],
               "light_blue": ["lightBlue"]}

## a name with a placeholder in it is a template rather than a name: a player
## head is "%s's Head" until the game knows whose
TEMPLATE = re.compile(r"%[sd]")


def read_lang(path=LANG):
    """`key=value` a line, `#` a comment, the way a .lang file is read."""
    found = {}
    with io.open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#")[0].strip()
            if "=" in line:
                key, _, value = line.partition("=")
                found[key.strip()] = value.strip()
    return found


def slug(text):
    """What a piece of text would be called as a block id."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")


def title(block):
    """An id as a name, for the blocks nothing else names."""
    return " ".join(word[:1].upper() + word[1:]
                    for word in re.sub(r"(?<=[a-z])(?=[A-Z])", "_", block).split("_"))


class Names:
    """Mojang's names, indexed the three ways this looks them up."""

    def __init__(self, lang):
        self.lang = lang
        self.direct = {}
        self.dotted = collections.defaultdict(dict)
        self.by_value = {}
        for key, value in lang.items():
            if not key.endswith(".name") or TEMPLATE.search(value):
                continue
            kind, _, rest = key.partition(".")
            if kind not in ("tile", "item"):
                continue
            body = rest[:-len(".name")]
            if kind == "tile":
                if "." in body:
                    block, _, variant = body.partition(".")
                    self.dotted[block][variant] = value
                else:
                    self.direct[body] = value
            ## first one wins, so a tile's name beats an item's for the same text
            self.by_value.setdefault(slug(value), value)

    def of(self, block):
        """Every name for one block, as the table writes them, or None."""
        if block in self.direct:
            return {"default": self.direct[block]}
        found = self.by_value.get(slug(block))
        if found:
            return {"default": found}
        if block in self.dotted:
            ## a variant name is only used when a block is placed in that
            ## variant, so an entry the states never produce simply goes unread
            told = dict(self.dotted[block])
            told.setdefault("default", title(block))
            return told
        return None


def entity_names(names):
    """A name per entity and per form, for the entities drawn as blocks."""
    out = {}
    for identifier, model in ENTITY_MODELS.items():
        short = identifier.replace("minecraft:", "")
        told = {"default": names.lang.get("entity.%s.name" % short)
                or title(short)}
        for form in model.get("forms") or ():
            for spelling in [form] + DYE_ALIASES.get(form, []):
                shown = names.lang.get("item.%s.%s.name" % (short, spelling))
                if shown:
                    told[form] = shown
                    break
            else:
                ## nothing names this form on its own, so it is described:
                ## "Orange Cushion" rather than the bare entity name
                told[form] = "%s %s" % (title(form), told["default"])
        out[identifier] = told
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", action="store_true",
                        help="say what would be added and write nothing")
    args = parser.parse_args()

    print("naming the blocks and entities")
    if not os.path.isfile(LANG):
        print("   bedrock-samples is not checked out; nothing written")
        print("   git submodule update --init bedrock-samples")
        return

    names = Names(read_lang())
    defs = json.load(io.open(DEFINITION, encoding="utf-8"))
    table = json.load(io.open(BLOCK_LIST, encoding="utf-8"),
                      object_pairs_hook=collections.OrderedDict)
    told = table["names"]

    ## the pseudo block ids the entities are drawn as. They are in
    ## block_definition like any other family, but they are named below with
    ## their own entity identifier and their own forms, not as blocks.
    pseudo = {model["block"] for model in ENTITY_MODELS.values()}

    added, guessed, defaulted = {}, [], []
    for block in sorted(defs):
        ## a block declared "ignore" is never drawn and never counted
        if defs[block] == "ignore" or block in pseudo:
            continue
        key = "minecraft:" + block
        if key in told:
            ## **An entry of variants with no default is still a gap.** The
            ## flattened ids -- carpet, red_flower, every stone_block_slab --
            ## are named a variant at a time because the id alone does not say
            ## what the block is made of, and one that ever turned up without
            ## its variant state would fall back to showing its own id. Filling
            ## the default costs a line and closes that.
            if isinstance(told[key], dict) and "default" not in told[key]:
                found = names.of(block) or {}
                told[key]["default"] = found.get("default") or title(block)
                defaulted.append(block)
            continue
        found = names.of(block)
        if found is None:
            found = {"default": title(block)}
            guessed.append(block)
        added[key] = found

    for identifier, found in entity_names(names).items():
        if identifier not in told:
            added[identifier] = found

    if args.report:
        print("   would add %d names (%d of them from the id itself) "
              "and %d missing defaults"
              % (len(added), len(guessed), len(defaulted)))
        for block in sorted(added)[:12]:
            print("      %-42s %s" % (block, json.dumps(added[block])[:60]))
        return

    for key in sorted(added):
        told[key] = added[key]
    io.open(BLOCK_LIST, "w", encoding="utf-8", newline="").write(
        json.dumps(table, indent="\t", ensure_ascii=False) + "\n")
    print("   %d added, %d of them from the id itself, %d defaults filled; "
          "%d named in all"
          % (len(added), len(guessed), len(defaulted), len(told)))


if __name__ == "__main__":
    main()
