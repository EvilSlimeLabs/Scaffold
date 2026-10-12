"""Clearer Redstone: the counts, the marks, and the families its options bring."""
import os
import tempfile
import unittest

from scaffold import marks, tweaks
from scaffold.pack import armor_stand_geo_class as asgc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REDSTONE = [key for key in tweaks.offered() if tweaks.tab(key) == "redstone"]


def item(name, count):
    return {"Name": "minecraft:" + name, "Count": count}


class CountTests(unittest.TestCase):

    def test_stack_sizes(self):
        self.assertEqual(marks.stack_size("minecraft:cobblestone"), 64)
        self.assertEqual(marks.stack_size("minecraft:ender_pearl"), 16)
        self.assertEqual(marks.stack_size("minecraft:oak_sign"), 16)
        self.assertEqual(marks.stack_size("minecraft:bucket"), 16)
        self.assertEqual(marks.stack_size("minecraft:water_bucket"), 1)
        self.assertEqual(marks.stack_size("minecraft:diamond_sword"), 1)

    def test_a_signal_is_what_a_comparator_reads(self):
        self.assertEqual(marks.signal([], 27), 0)
        self.assertEqual(marks.signal([item("dirt", 1)], 27), 1)
        ## a full container is fifteen, whatever fills it
        self.assertEqual(marks.signal([item("diamond_sword", 1)] * 9, 9), 15)
        self.assertEqual(marks.signal([item("dirt", 64)] * 5, 5), 15)
        ## half a stack of pearls and half a stack of stone count alike
        self.assertEqual(marks.signal([item("ender_pearl", 8)], 5),
                         marks.signal([item("stone", 32)], 5))

    def test_a_recipe_gives_back_its_own_signal_and_no_more(self):
        for slots in marks.SLOT_COUNTS:
            for strength in range(16):
                with self.subTest(slots=slots, signal=strength):
                    whole, loose = marks.recipe(strength, slots)
                    items = [item("stone", 64)] * whole + (
                        [item("stone", loose)] if loose else [])
                    self.assertEqual(marks.signal(items, slots), strength)
                    if loose:
                        ## one item fewer drops the signal, so it is the least
                        fewer = items[:-1] + ([item("stone", loose - 1)]
                                              if loose > 1 else [])
                        self.assertLess(marks.signal(fewer, slots), strength)

    def test_how_a_count_is_written(self):
        self.assertEqual(marks.text(0, 9), "0+0")
        self.assertEqual(marks.text(1, 27), "0+1")
        self.assertEqual(marks.text(15, 9), "9+0")


class Grid:
    origin = (0, 0, 0)

    def __init__(self, blocks, entities=None):
        self.blocks, self.entities = blocks, entities or {}

    def get_size(self):
        return (4, 1, 4)

    def get_block(self, x, y, z):
        return self.blocks.get((x, z), {"name": "minecraft:air", "states": {}})

    def get_block_entity(self, x, y, z):
        return self.entities.get((x, z), {})


class MarkTests(unittest.TestCase):

    def test_a_container_is_counted(self):
        block = {"name": "minecraft:dropper", "states": {"facing_direction": 4}}
        found = marks.made(Grid({}), 0, 0, 0, block,
                           {"id": "Dropper", "Items": [item("dirt", 64)] * 9})
        self.assertEqual(found, [{"name": marks.FILL, "states": {
            "mount": "block", "slots": 9, "signal": 15,
            "minecraft:cardinal_direction": "west"}}])

    def test_a_double_chest_is_counted_once_across_both_halves(self):
        chest = {"name": "minecraft:chest",
                 "states": {"minecraft:cardinal_direction": "north"}}
        grid = Grid({(1, 1): chest, (2, 1): chest},
                    {(2, 1): {"id": "Chest", "Items": [item("dirt", 64)] * 27}})
        left = marks.made(grid, 1, 0, 1, chest, {"id": "Chest", "pair": "left",
                                                 "pairx": 2, "pairz": 1, "Items": []})
        right = marks.made(grid, 2, 0, 1, chest, {"id": "Chest", "pair": "right",
                                                  "pairx": 1, "pairz": 1, "Items": []})
        self.assertEqual(right, [])
        self.assertEqual(left[0]["states"]["slots"], 54)
        self.assertEqual(left[0]["states"]["mount"], "chest_left")
        self.assertEqual(left[0]["states"]["signal"],
                         marks.signal([item("dirt", 64)] * 27, 54))

    def test_a_crafters_locked_slots_are_marked(self):
        block = {"name": "minecraft:crafter", "states": {"orientation": "north_up"}}
        found = marks.made(Grid({}), 0, 0, 0, block,
                           {"id": "Crafter", "disabled_slots": 0b100000101})
        self.assertEqual([m["states"]["slot"] for m in found], [0, 2, 8])

    def test_nothing_is_marked_without_a_block_entity(self):
        block = {"name": "minecraft:chest", "states": {}}
        self.assertEqual(marks.made(Grid({}), 0, 0, 0, block, {}), [])


class OverlayTests(unittest.TestCase):

    def test_every_option_shipped_with_its_families_and_picture(self):
        for key in REDSTONE:
            with self.subTest(option=key):
                where = tweaks.folder(key)
                self.assertIsNotNone(where)
                self.assertTrue(os.path.isfile(os.path.join(where, tweaks.GEOMETRY)))
                self.assertIsNotNone(tweaks.icon(key))

    def test_every_texture_an_option_names_shipped(self):
        ## a family pointing at a file the stager did not write fails the build
        for key in REDSTONE:
            geo = asgc.ArmorStandGeo("test", tweaks=[key])
            families, _defs, _turns = tweaks.tables([key])
            for entry in families.values():
                for section in ("forms", "low"):
                    for form in entry.get(section, {}).values():
                        for cube in form["cubes"]:
                            for read in cube["faces"].values():
                                name = (read.get("texture") or {}).get("texture", "")
                                if name.startswith("textures/clearer_redstone"):
                                    with self.subTest(option=key, texture=name):
                                        self.assertTrue(os.path.isfile(
                                            geo.texture_file(name)))

    def test_an_option_points_a_block_at_its_own_family(self):
        geo = asgc.ArmorStandGeo("test", tweaks=["note_block_pitch"])
        self.assertEqual(geo.defs["noteblock"], "clearer_note_block")
        self.assertEqual(geo.choose("noteblock", {}, {"note": 12})[0], "12")
        self.assertEqual(asgc.ArmorStandGeo("test").defs["noteblock"], "cube")

    def test_the_count_family_is_there_only_when_its_option_is_on(self):
        self.assertNotIn(marks.FILL, asgc.ArmorStandGeo("test").defs)
        geo = asgc.ArmorStandGeo("test", tweaks=["container_fill"])
        self.assertEqual(geo.choose(marks.FILL, {"mount": "chest_left", "slots": 54,
                                                 "signal": 7})[0], "chest_left-54-7")

    def test_redstone_is_laid_over_bedrock_tweaks(self):
        self.assertEqual(tweaks.chosen(["hopper_directions", "directional_hoppers"]),
                         ["directional_hoppers", "hopper_directions"])

    def test_every_option_builds_a_pack(self):
        from scaffold.core import Scaffold
        out = tempfile.mkdtemp()
        pack = Scaffold(os.path.join(out, "redstone"))
        pack.set_tweaks(REDSTONE)
        pack.add_model("", os.path.join(ROOT, "test_structures",
                                        "01-6xSingleItemSortes.mcstructure"))
        pack.set_model_offset("", [0, 0, 0])
        pack.generate_with_nametags()
        pack.compile_pack()
        self.assertEqual(pack.get_skipped(write_file=False), {})


if __name__ == "__main__":
    unittest.main()
