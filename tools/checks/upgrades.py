"""Check lookups/block_upgrades.json against PocketMine's upgrade schema.

    python -m tools.checks.upgrades --schema <folder>

`<folder>` is a local clone of https://github.com/pmmp/BedrockBlockUpgradeSchema.
It is not a submodule and nothing from it is copied into this repository: the
schema is LGPL-3 and Scaffold is MIT, so it is read here to check Scaffold's own
table and never shipped or used to build one.

PocketMine's schemas are generated from Mojang's dedicated server, one Minecraft
version at a time, and say what the server makes of a block saved at an older
version. Two sets of blocks are compared:

1. every palette entry in the test structures, upgraded from the version it was
   saved at
2. for every rule, old blocks built from the rule's own values, upgraded from
   the version just before the first schema that mentions their id

**A state PocketMine adds that a block never had is not a difference.** A stair
from before `minecraft:corner` existed gains `none`, a fence gains its four
connections; Scaffold leaves a state a block never carried absent, and every
lookup table reads an absent state as the default form.

**Differences that are expected**, and why, so a clean run is recognisable:

  * Scaffold renames and splits ids before it renames states, so a rule for a
    state names the id the block has *become*. An anvil split by `damage` still
    carries its numeric `direction`, and an old `skull` renamed to
    `skeleton_skull` still carries `no_drop_bit`. PocketMine's history never
    produced either combination, so the synthetic check reports them.
  * A block saved at exactly a schema's version number. PocketMine applies the
    schema anyway, since Mojang has shipped changes without bumping it, and for
    a rule that remaps *values* that is wrong: `sculk_vein` and the mushroom
    blocks in the test structures were saved already in the new form.
"""
import argparse
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import nbtlib

from scaffold import block_upgrade
from scaffold.pack import structure_reader


def schema_version(data):
    return ((data["maxVersionMajor"] << 24) | (data["maxVersionMinor"] << 16)
            | (data["maxVersionPatch"] << 8) | data["maxVersionRevision"])


def load_schemas(folder):
    files = sorted(glob.glob(os.path.join(folder, "nbt_upgrade_schema", "*.json")))
    ## a schema not yet filed under nbt_upgrade_schema sits at the top level
    files += sorted(glob.glob(os.path.join(folder, "0*.json")))
    found = []
    for path in files:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        found.append((schema_version(data), os.path.basename(path), data))
    return sorted(found, key=lambda item: (item[0], item[1]))


def tagged(value):
    (kind, raw), = value.items()
    return bool(raw) if kind == "byte" and raw in (0, 1) else raw


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        try:
            return int(a) == int(b)
        except (TypeError, ValueError):
            return False
    return a == b


def flattened(rule, value):
    text = str(int(value)) if isinstance(value, bool) else str(value)
    text = rule.get("flattenedValueRemaps", {}).get(text, text)
    return rule["prefix"] + text + rule["suffix"]


def step(schema, name, states):
    """One schema applied to one block, the way PocketMine's upgrader does:
    a remapped state first and alone, otherwise every other kind of change,
    each indexed by the old id and the old property names."""
    for rule in schema.get("remappedStates", {}).get(name, ()):
        wanted = rule.get("oldState") or {}
        if all(key in states and same(states[key], tagged(v)) for key, v in wanted.items()):
            made = {k: tagged(v) for k, v in (rule.get("newState") or {}).items()}
            for key in rule.get("copiedState", ()):
                if key in states:
                    made[key] = states[key]
            if "newName" in rule:
                return rule["newName"], made
            flat = rule["newFlattenedName"]
            return flattened(flat, states.get(flat["flattenedProperty"])), made
    states = dict(states)
    for key, value in schema.get("addedProperties", {}).get(name, {}).items():
        states.setdefault(key, tagged(value))
    for key in schema.get("removedProperties", {}).get(name, ()):
        states.pop(key, None)
    for key, index in schema.get("remappedPropertyValues", {}).get(name, {}).items():
        if key in states:
            for pair in schema.get("remappedPropertyValuesIndex", {}).get(index, ()):
                if same(states[key], tagged(pair["old"])):
                    states[key] = tagged(pair["new"])
                    break
    new_name = name
    flat = schema.get("flattenedProperties", {}).get(name)
    if flat and flat["flattenedProperty"] in states:
        new_name = flattened(flat, states.pop(flat["flattenedProperty"]))
    elif name in schema.get("renamedIds", {}):
        new_name = schema["renamedIds"][name]
    for old, new in schema.get("renamedProperties", {}).get(name, {}).items():
        if old in states:
            states[new] = states.pop(old)
    return new_name, states


def upgrade(schemas, name, states, version):
    """Every schema the block is not newer than, in order."""
    for number, _file, schema in schemas:
        if number >= version:
            name, states = step(schema, name, states)
    return name, states


def plain(value):
    kind = type(value).__name__
    if kind == "Byte":
        return bool(int(value)) if int(value) in (0, 1) else int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        return value if isinstance(value, bool) else str(value)
    return int(value)


def ours(name, states, version):
    got = block_upgrade.upgrade({"name": name, "version": version,
                                 "states": {k: block_upgrade.typed(v) for k, v in states.items()}})
    return str(got["name"]), {k: plain(v) for k, v in got["states"].items()}


def difference(original, mine, theirs):
    (mine_name, a), (their_name, b) = mine, theirs
    if mine_name != their_name:
        return "id %s, PocketMine %s" % (mine_name, their_name)
    notes = []
    for key in sorted(set(a) | set(b)):
        if key in a and key in b:
            if not same(a[key], b[key]):
                notes.append("%s=%r, PocketMine %r" % (key, a[key], b[key]))
        elif key in a:
            notes.append("%s only here" % key)
        elif key in original:
            notes.append("%s kept by PocketMine" % key)
    return "; ".join(notes)


def structure_entries():
    seen = {}
    for path in glob.glob(os.path.join(ROOT, "test_structures", "**", "*.mcstructure"), recursive=True):
        try:
            nbt = structure_reader.load(path)
        except Exception:
            continue
        for entry in nbt["structure"]["palette"]["default"]["block_palette"]:
            states = {k: plain(v) for k, v in entry["states"].items()}
            version = int(entry.get("version", 0))
            seen[json.dumps([str(entry["name"]), states, version], sort_keys=True)] = (
                str(entry["name"]), states, version)
    return list(seen.values())


def rule_blocks(schemas):
    """Old blocks made from each rule's own values."""
    first = {}
    before = 0
    for number, _file, schema in schemas:
        for section in schema.values():
            if isinstance(section, dict):
                for block in section:
                    first.setdefault(block, before)
        before = number
    for rule in block_upgrade.rules():
        wanted = rule.get("id")
        for block in wanted if isinstance(wanted, list) else ([wanted] if wanted else []):
            if "by" in rule:
                values = [dict(zip(rule["by"], key.split("/"))) for key in rule["into"]]
            elif "values" in rule:
                values = [{rule["state"]: key} for key in rule["values"]]
            elif "state" in rule:
                values = [{rule["state"]: "0"}]
            else:
                values = [{}]
            for states in values:
                states = {k: (bool(int(v)) if k.endswith("_bit") else int(v)) if v.isdigit() else v
                          for k, v in states.items()}
                yield block, states, first.get(block, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schema", required=True,
                        help="a local clone of pmmp/BedrockBlockUpgradeSchema")
    args = parser.parse_args()
    schemas = load_schemas(args.schema)
    if not schemas:
        print("no schemas found under %s" % args.schema)
        return 1

    found = collections.Counter()
    structures = structure_entries()
    for name, states, version in structures:
        why = difference(states, ours(name, states, version), upgrade(schemas, name, states, version))
        if why:
            found[("test structures", name, why)] += 1
    made = list(rule_blocks(schemas))
    for name, states, version in made:
        why = difference(states, ours(name, states, version), upgrade(schemas, name, states, version))
        if why:
            found[("rules", name + " " + json.dumps(states), why)] += 1

    print("%d palette entries from the test structures, %d blocks from the rules, "
          "%d differences" % (len(structures), len(made), sum(found.values())))
    for (where, what, why), count in sorted(found.items()):
        print("  %-15s %-60s %s%s" % (where, what, why, "  (x%d)" % count if count > 1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
