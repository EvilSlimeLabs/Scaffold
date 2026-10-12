"""Old blocks translated to the names the current game uses.

`lookups/block_upgrades.json` is read by `scaffold/block_upgrade.py` as a
structure is read, so everything after it sees current ids and states only.
These hold the table to that: every block a rule produces has to be one the
lookups can draw, an id Mojang has retired must not still be in them, and each
kind of rule has to do what the module says it does.
"""
import json
import os
import tempfile
import unittest

import nbtlib
from nbtlib import Byte, Compound, Int, List, String

from scaffold import block_upgrade
from scaffold import paths
from scaffold.pack import structure_reader
from scaffold import lookup


def load(name):
    with open(paths.lookup(name), encoding="utf-8-sig") as handle:
        return lookup.unwrap(name, json.load(handle))


def ids(rule):
    wanted = rule.get("id")
    return wanted if isinstance(wanted, list) else ([wanted] if wanted else [])


def made_by(rule):
    return [rule["becomes"]] if "becomes" in rule else list(rule.get("into", {}).values())


class TableTests(unittest.TestCase):
    def setUp(self):
        self.rules = block_upgrade.rules()
        self.definitions = load("block_definition.json")

    def test_every_rule_is_one_of_the_three_kinds(self):
        for rule in self.rules:
            with self.subTest(rule=json.dumps(rule)[:80]):
                if "state" in rule:
                    self.assertTrue({"becomes", "values", "drop"} & set(rule),
                                    "a state rule that changes nothing")
                elif "by" in rule:
                    self.assertTrue(ids(rule), "a split names the id it splits")
                    self.assertTrue(rule["into"])
                else:
                    self.assertTrue(ids(rule))
                    self.assertIn("becomes", rule)

    def test_every_block_a_rule_makes_is_in_the_lookups(self):
        # a rule's result that no family draws would turn a block that used to
        # draw into a skipped one. A result that a later rule renames or splits
        # again is a step along the way, not a result.
        sources = {block for rule in self.rules if "state" not in rule for block in ids(rule)}
        for rule in self.rules:
            if "state" in rule:
                continue
            for block in made_by(rule):
                if block in sources:
                    continue
                with self.subTest(block=block):
                    self.assertIn(block.replace("minecraft:", ""), self.definitions)

    def test_no_retired_id_is_still_in_the_lookups(self):
        # once an id is always translated away, an entry for it is data nothing
        # can reach. A split that keeps one of its blocks under the old id (a
        # quartz_block of type default stays a quartz_block) is not retiring it.
        for rule in self.rules:
            if "state" in rule:
                continue
            for block in ids(rule):
                if block in made_by(rule):
                    continue
                if "into" in rule and "becomes" not in rule:
                    ## a split only retires the id when every value is covered;
                    ## the table cannot say that, so a split's source is checked
                    ## only against Mojang's own list when it is checked out
                    continue
                with self.subTest(block=block):
                    self.assertNotIn(block.replace("minecraft:", ""), self.definitions)


class RuleTests(unittest.TestCase):
    def entry(self, name, version=None, **states):
        found = {"name": "minecraft:" + name, "states": states}
        if version is not None:
            found["version"] = Int(version)
        return found

    def test_an_entry_no_rule_touches_comes_back_as_it_was(self):
        entry = self.entry("stone")
        self.assertIs(block_upgrade.upgrade(entry), entry)

    def test_an_id_is_renamed(self):
        got = block_upgrade.upgrade(self.entry("seaLantern"))
        self.assertEqual(got["name"], "minecraft:sea_lantern")

    def test_an_id_is_split_by_its_state_and_the_state_goes(self):
        got = block_upgrade.upgrade(self.entry("wool", color=String("silver")))
        self.assertEqual(got["name"], "minecraft:light_gray_wool")
        self.assertNotIn("color", got["states"])

    def test_a_split_can_read_two_states(self):
        got = block_upgrade.upgrade(self.entry("wood", wood_type=String("birch"),
                                               stripped_bit=Byte(1),
                                               pillar_axis=String("x")))
        self.assertEqual(got["name"], "minecraft:stripped_birch_wood")
        self.assertEqual(dict(got["states"]), {"pillar_axis": String("x")})

    def test_a_state_is_renamed_and_its_values_mapped(self):
        # Mojang's own numbering for a door's direction, which is not the
        # numbering most other blocks use
        got = block_upgrade.upgrade(self.entry("wooden_door", direction=Int(0),
                                               open_bit=Byte(1)))
        self.assertEqual(str(got["states"]["minecraft:cardinal_direction"]), "south")
        self.assertNotIn("direction", got["states"])
        self.assertEqual(int(got["states"]["open_bit"]), 1)

    def test_a_split_happens_before_the_states_of_what_it_made(self):
        # an old anvil carries both its damage and a numeric direction
        got = block_upgrade.upgrade(self.entry("anvil", damage=String("slightly_damaged"),
                                               direction=Int(3)))
        self.assertEqual(got["name"], "minecraft:chipped_anvil")
        self.assertEqual(str(got["states"]["minecraft:cardinal_direction"]), "east")

    def test_a_new_value_takes_the_type_a_structure_would_store(self):
        got = block_upgrade.upgrade(self.entry("stone_slab", stone_slab_type=String("quartz"),
                                               top_slot_bit=Byte(1)))
        half = got["states"]["minecraft:vertical_half"]
        self.assertIsInstance(half, String)
        self.assertEqual(str(half), "top")

    def test_a_value_nothing_names_is_left_alone(self):
        entry = self.entry("wool", color=String("chartreuse"))
        self.assertIs(block_upgrade.upgrade(entry), entry)

    def test_before_limits_a_remap_to_blocks_saved_before_the_change(self):
        # glow lichen's face bits were reordered in 1.18.10; the same number
        # means different faces either side of it
        old = block_upgrade.upgrade(self.entry("glow_lichen", 17959424,
                                               multi_face_direction_bits=Int(4)))
        self.assertEqual(int(old["states"]["multi_face_direction_bits"]), 16)
        new = self.entry("glow_lichen", 17959425, multi_face_direction_bits=Int(4))
        self.assertIs(block_upgrade.upgrade(new), new)
        no_version = self.entry("glow_lichen", multi_face_direction_bits=Int(4))
        self.assertIs(block_upgrade.upgrade(no_version), no_version)

    def test_what_the_structure_recorded_is_kept_beside_it(self):
        entry = self.entry("red_flower", flower_type=String("orchid"))
        self.assertIs(block_upgrade.upgrade(entry)["was"], entry)

    def test_a_block_list_key_is_read_as_the_block_it_became(self):
        self.assertEqual(block_upgrade.list_key("minecraft:stone_block_slab", "quartz"),
                         ("minecraft:quartz_slab", "default"))
        self.assertEqual(block_upgrade.list_key("minecraft:stone_slab", "quartz"),
                         ("minecraft:quartz_slab", "default"))
        self.assertEqual(block_upgrade.list_key("minecraft:stone"),
                         ("minecraft:stone", "default"))


class StructureTests(unittest.TestCase):
    """A structure is read through the translation, and nothing on disk moves."""

    def test_a_structure_is_read_as_the_current_game_names_it(self):
        nbt = nbtlib.File({
            "format_version": Int(1),
            "size": List[Int]([Int(1), Int(1), Int(2)]),
            "structure_world_origin": List[Int]([Int(0), Int(0), Int(0)]),
            "structure": Compound({
                "block_indices": List([List[Int]([Int(1), Int(2)]),
                                       List[Int]([Int(-1), Int(-1)])]),
                "entities": List[Compound]([]),
                "palette": Compound({"default": Compound({
                    "block_palette": List[Compound]([
                        Compound({"name": String("minecraft:air"),
                                  "states": Compound({}),
                                  "version": Int(18168865)}),
                        Compound({"name": String("minecraft:wool"),
                                  "states": Compound({"color": String("red")}),
                                  "version": Int(17959425)}),
                        Compound({"name": String("minecraft:stone"),
                                  "states": Compound({}),
                                  "version": Int(18168865)})]),
                    "block_position_data": Compound({}),
                })}),
            }),
        })
        handle, path = tempfile.mkstemp(suffix=".mcstructure")
        os.close(handle)
        self.addCleanup(os.remove, path)
        nbt.save(path, byteorder="little")
        before = open(path, "rb").read()

        reader = structure_reader.StructureFile(path)
        self.assertEqual(str(reader.get_block(0, 0, 0)["name"]), "minecraft:red_wool")
        self.assertEqual(str(reader.get_block(0, 0, 1)["name"]), "minecraft:stone")
        counted = {str(k): int(v) for k, v in reader.get_block_list().items()}
        self.assertEqual(counted, {"minecraft:red_wool": 1, "minecraft:stone": 1})
        self.assertEqual(open(path, "rb").read(), before, "the file was written to")


if __name__ == "__main__":
    unittest.main()
