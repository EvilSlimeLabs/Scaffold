"""The Bedrock Tweaks a pack can be built with.

Bedrock Tweaks (https://bedrocktweaks.net) publishes small resource packs that
each change one thing about how Minecraft looks -- a border around ores, a
cleaner redstone dust, an observer you can tell the front of. Applying one to a
world is a matter of putting its pack above the others. A Scaffold pack has no
"above": every texture it uses is baked into one atlas as the pack is built, so
a tweak has to be applied at that moment instead.

**A tweak is an overlay on the vanilla pack.** `scaffold/tweakpacks/<id>/` is a
staged copy of one of their packs, cut down to what a build can read, and
`overlay()` returns the chosen ones in the order they were asked for.
`armor_stand_geo_class` then looks for every texture in those folders before it
looks in `Vanilla_Resource_Pack`, and reads `blocks.json` and
`terrain_texture.json` merged the same way, which is what lets a tweak name a
texture the vanilla pack has never heard of.

**Two of them draw their art on the carried block.** Minecraft can tell a waxed
copper block from an unwaxed one only in the inventory, so Bedrock Tweaks puts
those textures in `carried_textures` and leaves the placed block alone. A ghost
block is the placed block and there is no inventory anywhere near it, so those
two packs are read the other way round: `carried` on an entry here means the
`carried_textures` a block declares are taken as its `textures`. That is the
whole of why "Visual Waxed Copper" can be offered at all.

**Some pairs cannot both be on, and those share one control.** Sus Sand and
Gravel and Suspicious Sand & Gravel Borders write the same eight files, so
whichever came last would silently win. `chosen()` drops the earlier of a
conflicting pair rather than letting that happen. In the window they are not two
switches that fight but one slider with three positions -- off, and one per
tweak -- which is what `controls()` is for: a `control` on an entry here puts it
in a group, and the group is one slider whose positions run in the table's
order. Everything else is a group of one, which is an ordinary two-position
slider.

**The table's order is the window's order.** The dialog fills three columns of
four from it, top to bottom and then across, so moving an entry here moves the
cell. There is no separate layout anywhere.

**Clearer Redstone is in the same table, on a tab of its own, and wins.** Its
options are applied after every Bedrock Tweak whatever order they were asked
for in, so where both change one block the redstone option is what is drawn;
nothing on one tab switches anything on the other off.

Its options are Redstone Tweaks' art, converted by `tools/vendor/redstone.py`, and an entry
with `"tab": "redstone"` is one of them. Several need more than a texture: a
note block drawn by its pitch, a composter numbered by how full it is. So a
staged folder may also carry `geometry.json`, whole shape families in format 2
that replace the ones of the same name, `definition.json`, block ids pointed at
a family, and `rotation.json`, a rotation for a family the overlay adds.
`tables()` merges those the way `overlay()` merges the rest.

Nothing here reads the `bedrock_tweaks/` submodule; that is
`tools/vendor/tweaks.py`'s business, and it runs long before a build does.
"""
import json
import os

from scaffold import jsonc
from scaffold import lookup
from scaffold import paths

## the name of the table, the two files a tweak may carry that are merged
## rather than overlaid, and the picture the window shows beside its name
TABLE = "tweaks.json"
BLOCKS = "blocks.json"
TERRAIN = os.path.join("textures", "terrain_texture.json")
ICON = "pack_icon.png"

## the files a staged folder may carry beside its textures, which change the
## geometry tables rather than the art
GEOMETRY = "geometry.json"
DEFINITION = "definition.json"
ROTATION = "rotation.json"

## the tabs the window shows, in order; an entry with no `tab` is on the first
TABS = ("tweaks", "redstone")

## the credit the licence asks to travel with the files
CREDIT_LINKS = ("https://vanillatweaks.net", "https://bedrocktweaks.net")
## the credit text Bedrock Tweaks' licence names, word for word, for every
## credits.txt that carries their files
CREDIT_LINES = ("Vanilla Tweaks: https://vanillatweaks.net/",
                "Bedrock Tweaks: https://bedrocktweaks.net/")

## and the credit Redstone Tweaks' licence asks for, CC BY-NC-SA 4.0
REDSTONE_CREDIT_LINKS = ("https://modrinth.com/resourcepack/redstone-tweaks",
                         "https://creativecommons.org/licenses/by-nc-sa/4.0/")

_table = None


def offered(reload=False):
    """Every tweak this build offers, as {id: entry}, in the table's order."""
    global _table
    if _table is None or reload:
        _table = lookup.entries(TABLE)
    return _table


def folder(key):
    """Where one tweak's staged files are, or None if they did not ship."""
    where = paths.tweaks_pack(key)
    return where if os.path.isdir(where) else None


def conflicts(key):
    """The tweaks that cannot be on at the same time as this one."""
    return tuple(offered().get(key, {}).get("conflicts", ()))


def carried(key):
    """Whether this tweak's blocks are painted with their carried textures."""
    return bool(offered().get(key, {}).get("carried"))


def icon(key):
    """The pack icon Bedrock Tweaks draws for this one, or None.

    Staged beside the art by `tools/vendor/tweaks.py`. It is not read by a build
    -- nothing in a generated pack ever shows it -- only by the window, so that
    somebody picking a tweak is looking at what it does.
    """
    where = folder(key)
    if where is None:
        return None
    picture = os.path.join(where, ICON)
    return picture if os.path.isfile(picture) else None


def tab(key):
    """Which tab of the window this tweak is on."""
    return offered().get(key, {}).get("tab", TABS[0])


def controls(on=None):
    """The sliders the window draws, in the table's order.

    Each is `(name, [tweak, ...])`. A tweak with a `control` joins the group of
    that name and the group is one slider with a position per tweak and an off
    at the start; everything else is a group of its own, named for itself, which
    is an ordinary two-position slider. The group keeps the place of its first
    member, so the table's order is the order the cells are drawn in.
    """
    groups, seen = [], {}
    for key, entry in offered().items():
        if on is not None and entry.get("tab", TABS[0]) != on:
            continue
        name = entry.get("control", key)
        if name not in seen:
            seen[name] = []
            groups.append((name, seen[name]))
        seen[name].append(key)
    return groups


def control_of(key):
    """The name of the slider this tweak is one position of."""
    return offered().get(key, {}).get("control", key)


def chosen(keys):
    """The tweaks to actually apply, in order, with conflicts settled.

    Anything the table does not name is dropped, as is anything that did not
    ship. Of two that conflict the later one wins, because it is the one the
    caller asked for most recently.
    """
    out = []
    for key in keys or ():
        if key not in offered() or folder(key) is None:
            continue
        out = [kept for kept in out if kept not in conflicts(key)]
        if key not in out:
            out.append(key)
    ## Clearer Redstone is laid over Bedrock Tweaks: where both change one
    ## block, the redstone option is the one drawn
    return sorted(out, key=lambda key: TABS.index(tab(key)))


def overlay(keys):
    """What a build needs to apply these tweaks.

    Returns `(folders, blocks, terrain, carried)`:

      folders   where to look for a texture, before the vanilla pack
      blocks    `blocks.json` entries to merge over the vanilla ones
      terrain   `texture_data` entries to merge over the vanilla ones
      carried   the block ids whose `carried_textures` are their textures

    The dictionaries are merged here rather than by the caller so that two
    tweaks touching one block land in the order they were chosen.
    """
    folders, blocks, terrain, wearing = [], {}, {}, set()
    for key in chosen(keys):
        where = folder(key)
        folders.append(where)
        declared = _read(os.path.join(where, BLOCKS))
        for block, entry in declared.items():
            if block == "format_version":
                continue
            blocks[block] = entry
            if carried(key):
                wearing.add(block)
        named = _read(os.path.join(where, TERRAIN)).get("texture_data") or {}
        terrain.update(named)
    return folders, blocks, terrain, wearing


def tables(keys):
    """What these tweaks change in the geometry tables.

    Returns `(families, definitions, rotations)`: whole shape families in
    format 2, keyed by name, which replace a family of the same name; block ids
    pointed at a family; and a rotation, a state's name or a table, for each
    family that needs one. A later tweak wins a name two of them carry.
    """
    families, definitions, rotations = {}, {}, {}
    for key in chosen(keys):
        where = folder(key)
        families.update(_read(os.path.join(where, GEOMETRY)).get("families") or {})
        definitions.update(_read(os.path.join(where, DEFINITION)))
        rotations.update(_read(os.path.join(where, ROTATION)).get("families") or {})
    return families, definitions, rotations


def credits(keys):
    """Which credits a pack built with these tweaks carries: `tweaks` for
    Bedrock Tweaks' art, `redstone` for Redstone Tweaks'."""
    return sorted({tab(key) for key in chosen(keys)})


def _read(path):
    """One of a tweak's JSON files, or an empty one if it has none.

    Bedrock's own packs are read with the permissive parser, and a tweak is one
    of Bedrock's own packs: comments and trailing commas are ordinary there.
    """
    if not os.path.isfile(path):
        return {}
    try:
        found = jsonc.load(path)
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}
