import io
import json
import os
import shutil
import tempfile
import unittest

from scaffold import block_list
from scaffold import paths


class TableTests(unittest.TestCase):
    """The shipped file, and what it has to carry."""

    def setUp(self):
        block_list.table(reload=True)
        self.addCleanup(block_list.table, True)

    def test_the_file_ships_with_the_program(self):
        self.assertTrue(os.path.isfile(paths.lookup(block_list.CAT_NAME)))

    def test_it_carries_both_halves(self):
        found = block_list.table()
        self.assertTrue(found["names"], "no names")
        self.assertTrue(found["categories"], "no categories")

    def test_every_category_has_a_name_and_something_to_match(self):
        for entry in block_list.table()["categories"]:
            self.assertTrue(entry.get("name"), entry)
            self.assertTrue(entry.get("match"), entry)

    def test_a_block_nothing_names_is_still_listed(self):
        # a missing entry has to read as the id rather than vanish, because a
        # block left off a shopping list is a wall somebody cannot finish
        self.assertEqual(block_list.name_of("minecraft:zzz_nonsense"),
                         "zzz_nonsense")
        self.assertEqual(block_list.category_of("minecraft:zzz_nonsense"),
                         block_list.LEFTOVERS)

    def test_the_leftovers_heading_is_last(self):
        self.assertEqual(block_list.order()[-1], block_list.LEFTOVERS)


class KeyTests(unittest.TestCase):
    """A block list counts ids, and a variant travels with one."""

    def test_a_variant_is_split_back_off(self):
        self.assertEqual(block_list.split("minecraft:red_flower/poppy"),
                         ("minecraft:red_flower", "poppy"))
        self.assertEqual(block_list.split("minecraft:stone"),
                         ("minecraft:stone", "default"))

    def test_a_variant_is_named_as_itself(self):
        # a poppy and an allium are one block id and two things to gather
        self.assertEqual(block_list.name_of("minecraft:red_flower/poppy"),
                         "Poppy")
        self.assertEqual(block_list.name_of("minecraft:red_flower/allium"),
                         "Allium")

    def test_a_variant_nothing_names_falls_back_to_the_block(self):
        self.assertEqual(block_list.name_of("minecraft:red_flower/nonsense"),
                         block_list.name_of("minecraft:red_flower"))


class MatchTests(unittest.TestCase):
    def test_a_variant_can_be_matched_and_a_star_stops_at_the_slash(self):
        # some blocks keep what they are made of in the variant: every stone
        # slab from before the names were flattened is a `stone_block_slab`
        self.assertTrue(block_list._matches(
            "*/quartz", "minecraft:stone_block_slab/quartz"))
        # and without the star stopping at the slash, "*/brick" would swallow
        # the separator and half of "nether_brick" with it
        self.assertFalse(block_list._matches(
            "*/brick", "minecraft:stone_block_slab/nether_brick"))

    def test_a_legacy_slab_lands_with_the_stone_it_is_cut_from(self):
        self.assertEqual(
            block_list.category_of("minecraft:stone_block_slab/quartz"),
            "Quartz")
        self.assertEqual(
            block_list.category_of("minecraft:stone_block_slab/cobblestone"),
            "Cobblestone")

    def test_a_pattern_may_leave_the_namespace_off(self):
        self.assertTrue(block_list._matches("stone", "minecraft:stone"))
        self.assertTrue(block_list._matches("minecraft:stone", "minecraft:stone"))

    def test_a_star_stands_for_any_run_and_nothing_else_is_special(self):
        self.assertTrue(block_list._matches("*_stairs", "minecraft:oak_stairs"))
        self.assertFalse(block_list._matches("*_stairs", "minecraft:oak_slab"))
        # a dot is a dot, not "any character"
        self.assertFalse(block_list._matches("ston.", "minecraft:stone"))

    def test_a_pattern_matches_the_whole_id_not_a_piece_of_it(self):
        self.assertFalse(block_list._matches("stone", "minecraft:stone_brick"))


class GroupedTests(unittest.TestCase):
    def test_counts_are_summed_by_the_name_not_by_the_id(self):
        # several ids can be one thing to gather, and the table calls them the
        # same; two lines for one item is arithmetic at a chest
        found = dict(block_list.grouped({
            "minecraft:tuff_brick_slab": 3,
            "minecraft:tuff_brick_double_slab": 2,
        }))
        counted = dict(sum(found.values(), []))
        self.assertEqual(sum(counted.values()), 5)

    def test_headings_come_in_the_order_the_file_puts_them(self):
        found = block_list.grouped({"minecraft:oak_planks": 1,
                                    "minecraft:redstone_torch": 1})
        headings = [heading for heading, _ in found]
        wanted = [name for name in block_list.order() if name in headings]
        self.assertEqual(headings, wanted)

    def test_an_empty_heading_is_left_out(self):
        found = block_list.grouped({"minecraft:oak_planks": 1})
        self.assertEqual([heading for heading, _ in found], ["Oak"])

    def test_nothing_is_dropped(self):
        counts = {"minecraft:oak_planks": 4, "minecraft:zzz_nonsense": 7}
        total = sum(count for _heading, rows in block_list.grouped(counts)
                    for _name, count in rows)
        self.assertEqual(total, 11)


class OverrideTests(unittest.TestCase):
    """A file the user supplies, found where the settings file is found."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.path = os.path.join(self.folder, block_list.OVERRIDE_CAT_NAME)
        self.real = block_list.override_files
        block_list.override_files = lambda: [self.path]
        self.addCleanup(setattr, block_list, "override_files", self.real)
        self.addCleanup(block_list.table, True)

    def write(self, body):
        io.open(self.path, "w", encoding="utf-8").write(
            json.dumps(body, ensure_ascii=False))
        block_list.table(reload=True)

    def test_it_is_looked_for_where_the_settings_file_is(self):
        from scaffold import settings

        block_list.override_files = self.real
        looked = block_list.override_files()
        self.assertIn(os.path.dirname(settings.settings_file()),
                      [os.path.dirname(path) for path in looked])

    def test_renaming_one_block_leaves_the_others_alone(self):
        self.write({"names": {"minecraft:oak_planks": {"default": "Planks"}}})
        self.assertEqual(block_list.name_of("minecraft:oak_planks"), "Planks")
        self.assertEqual(block_list.name_of("minecraft:stone"), "Stone")

    def test_a_bare_string_is_the_shorthand_for_a_name(self):
        self.write({"names": {"minecraft:stone": "Rock"}})
        self.assertEqual(block_list.name_of("minecraft:stone"), "Rock")

    def test_categories_given_replace_the_list_rather_than_merging(self):
        # order is the whole meaning of the list, and half a list merged by
        # name into another is not something anyone could predict
        self.write({"categories": [{"name": "Everything", "match": ["*"]}]})
        self.assertEqual(block_list.order(), ["Everything",
                                              block_list.LEFTOVERS])
        self.assertEqual(block_list.category_of("minecraft:oak_planks"),
                         "Everything")

    def test_categories_left_out_keep_the_shipped_ones(self):
        self.write({"names": {"minecraft:stone": "Rock"}})
        self.assertIn("Oak", block_list.order())

    def test_a_broken_file_is_ignored_rather_than_fatal(self):
        io.open(self.path, "w", encoding="utf-8").write("{ not json")
        block_list.table(reload=True)
        self.assertEqual(block_list.name_of("minecraft:stone"), "Stone")

    def test_nothing_is_written_where_one_is_looked_for(self):
        # the file is Scaffold's to read and the user's to write; a program
        # that rewrites the file somebody is editing loses their work
        block_list.override_files = self.real
        block_list.table(reload=True)
        block_list.grouped({"minecraft:stone": 1})
        for path in block_list.override_files():
            self.assertFalse(os.path.exists(path),
                             "%s was created" % path)


if __name__ == "__main__":
    unittest.main()
