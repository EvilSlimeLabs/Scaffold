"""Old blocks, named the way the current game names them.

A structure keeps every block the way the game described it on the day the
structure was saved, and Mojang has renamed a great deal since: `wool` with a
`color` is sixteen blocks now, a door's numeric `direction` became
`minecraft:cardinal_direction`, and every slab's `top_slot_bit` became
`minecraft:vertical_half`. Minecraft upgrades a block when it loads one. This
does the same, once per palette entry, as a structure is read, so every table
after it describes current blocks only and none has to carry an old name beside
a new one.

**Nothing is written back.** The structure file on disk is never touched; the
translation lives in the palette held in memory.

**A palette entry is translated, not each block.** A structure stores every
distinct block once in its palette and fills the grid with indices into it, so
this runs a few hundred times however large the build is.

The rules are data, in `lookups/block_upgrades.json`, and run top to bottom, each
seeing the block as the rules above it left it. There are three kinds:

  * `{"id", "becomes"}` gives an id a new name.
  * `{"id", "by", "into"}` splits one id into several by the value of the
    states in `by`, joined with "/" when there is more than one. The states it
    splits by are removed, unless `keep` says the new id still carries them. A
    value `into` does not name leaves the block as it was.
  * `{"state", ...}` renames a state (`becomes`), maps its values (`values`),
    or removes it (`drop`). A value `values` does not name leaves the state as
    it was. `id`, a name or a list of names, limits it to those blocks.

`set` on an id rule adds states the new id carries and the old one did not.

**`before` limits a rule to blocks saved at a lower block data version**, the
`version` every palette entry carries. Most rules do not need it, because an old
name never comes back once Mojang retires it. A rule that remaps *values* does:
the same number means one thing before the change and another after it, and
only the version says which a block was saved with. A block that carries no
version, like the plant held in a flower pot, is taken to be current.
"""
import io
import json

import nbtlib

from scaffold import paths

TABLE = "block_upgrades.json"

_rules = None


def rules():
    """The rules, in the order they run."""
    global _rules
    if _rules is None:
        with io.open(paths.lookup(TABLE), encoding="utf-8-sig") as handle:
            _rules = json.load(handle)["rules"]
    return _rules


def plain(value):
    """A state value as the string a rule is keyed by.

    nbtlib's Byte, Int and String are Python ints and strings underneath, so a
    boolean state reads "0" or "1" whichever way it was stored.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(int(value))
    return str(value)


def typed(value):
    """A value from the table as the NBT type a structure would have stored:
    true and false as a byte, a whole number as an int, text as a string."""
    if isinstance(value, bool):
        return nbtlib.Byte(int(value))
    if isinstance(value, int):
        return nbtlib.Int(value)
    return nbtlib.String(value)


def _applies(rule, name, version):
    if "before" in rule and (version is None or version >= rule["before"]):
        return False
    wanted = rule.get("id")
    if wanted is None:
        return True
    return name in (wanted if isinstance(wanted, list) else [wanted])


def list_key(block, variant="default"):
    """A block list key, as `(id, variant)`, the way the current game names it.

    A block list counts blocks as an id with a variant beside it, and somebody's
    own names file may have been written against an id Mojang has since split:
    `stone_block_slab` named for its `quartz` variant is `quartz_slab` now. Only
    id rules can be read here, because a key holds an id and one variant and no
    states. A variant that picks one block out of a split becomes that block's
    default name.
    """
    for rule in rules():
        if "state" in rule or "before" in rule:
            continue
        wanted = rule["id"]
        if block not in (wanted if isinstance(wanted, list) else [wanted]):
            continue
        if "becomes" in rule:
            block = rule["becomes"]
        elif len(rule["by"]) == 1 and variant in rule["into"]:
            block, variant = rule["into"][variant], "default"
    return block, variant


def upgrade(entry):
    """One palette entry as the current game would name it.

    An entry no rule touches is handed back as it came. One that changes comes
    back as a new mapping with `name`, `states` and `version`, and the entry it
    was made from under `was`, so a block reported as skipped can still be
    shown as the structure recorded it.
    """
    states = entry.get("states")
    if not hasattr(states, "items"):
        return entry
    name = str(entry["name"])
    states = dict(states)
    version = entry.get("version")
    version = int(version) if version is not None else None
    changed = False
    for rule in rules():
        if not _applies(rule, name, version):
            continue
        if "state" in rule:
            key = rule["state"]
            if key not in states:
                continue
            if rule.get("drop"):
                del states[key]
                changed = True
                continue
            value = states[key]
            if "values" in rule:
                told = rule["values"].get(plain(value))
                if told is None:
                    continue
                value = typed(told)
            del states[key]
            states[rule.get("becomes", key)] = value
            changed = True
            continue
        if "by" in rule:
            if any(key not in states for key in rule["by"]):
                continue
            target = rule["into"].get("/".join(plain(states[key]) for key in rule["by"]))
            if target is None:
                continue
            if not rule.get("keep"):
                for key in rule["by"]:
                    del states[key]
        else:
            target = rule["becomes"]
        name = target
        for key, value in rule.get("set", {}).items():
            states.setdefault(key, typed(value))
        changed = True
    if not changed:
        return entry
    return {"name": name, "states": states, "version": entry.get("version"), "was": entry}
