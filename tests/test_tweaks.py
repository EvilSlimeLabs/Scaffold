"""Bedrock Tweaks: the table, the overlay, and what a pack says about them."""
import os
import unittest
import zipfile

from scaffold import lang_parse
from scaffold import settings
from scaffold import tweaks
from scaffold.core import scaffold
from scaffold.pack import manifest
from scaffold.pack.armor_stand_geo_class import ArmorStandGeo


class TableTests(unittest.TestCase):
    def test_every_tweak_named_in_the_table_actually_shipped(self):
        for key in tweaks.offered():
            with self.subTest(tweak=key):
                where = tweaks.folder(key)
                self.assertIsNotNone(
                    where, "%s is in the table but not in scaffold/tweakpacks/" % key)
                self.assertTrue(os.listdir(where), "%s shipped empty" % key)

    def test_every_tweak_has_a_name_in_english(self):
        english = lang_parse.parse()["en_US"]
        for key in tweaks.offered():
            with self.subTest(tweak=key):
                self.assertIn("tweak " + key, english)

    def test_a_conflict_is_declared_from_both_ends(self):
        ## a one-sided conflict would be settled or not depending on which of
        ## the pair somebody switched on first
        for key in tweaks.offered():
            for other in tweaks.conflicts(key):
                with self.subTest(tweak=key, against=other):
                    self.assertIn(key, tweaks.conflicts(other))

    def test_every_tweak_has_the_picture_the_window_shows(self):
        ## the dialog is a grid of pictures, so one missing is a blank cell
        for key in tweaks.offered():
            with self.subTest(tweak=key):
                self.assertIsNotNone(tweaks.icon(key))

    def test_the_grid_is_three_columns_of_four(self):
        """The dialog fills three columns of four from the table's order, so
        the table has to hold exactly twelve controls."""
        self.assertEqual(len(tweaks.controls()), 12)

    def test_the_tweaks_that_conflict_are_the_ones_sharing_a_control(self):
        ## two switches that turned each other off would read as a fault, so a
        ## conflicting pair is one slider instead; the two have to agree
        for name, keys in tweaks.controls():
            with self.subTest(control=name):
                if len(keys) > 1:
                    for key in keys:
                        self.assertEqual(sorted(tweaks.conflicts(key)),
                                         sorted(k for k in keys if k != key))
                else:
                    self.assertEqual(tweaks.conflicts(keys[0]), ())

    def test_every_control_has_a_name_in_english(self):
        english = lang_parse.parse()["en_US"]
        for name, _keys in tweaks.controls():
            with self.subTest(control=name):
                self.assertIn("tweak control " + name, english)

    def test_every_tweak_belongs_to_exactly_one_control(self):
        seen = [key for _name, keys in tweaks.controls() for key in keys]

        self.assertEqual(sorted(seen), sorted(tweaks.offered()))

    def test_the_licence_ships_beside_the_files(self):
        ## Bedrock Tweaks' licence asks for the credit to travel with the files
        beside = os.path.dirname(tweaks.folder(next(iter(tweaks.offered()))))
        self.assertTrue(os.path.isfile(os.path.join(beside, "LICENSE")))


class ChoosingTests(unittest.TestCase):
    def test_a_name_nothing_offers_is_dropped(self):
        self.assertEqual(tweaks.chosen(["ore_borders", "nonsense"]),
                         ["ore_borders"])

    def test_of_a_conflicting_pair_the_later_one_wins(self):
        pair = ["sus_sand_and_gravel", "suspicious_sand_and_gravel_borders"]
        self.assertEqual(tweaks.chosen(pair), pair[1:])
        self.assertEqual(tweaks.chosen(list(reversed(pair))), pair[:1])

    def test_nothing_chosen_is_nothing_applied(self):
        self.assertEqual(tweaks.chosen(None), [])
        self.assertEqual(tweaks.chosen([]), [])


class OverlayTests(unittest.TestCase):
    def test_a_tweak_texture_is_read_before_the_vanilla_one(self):
        plain = ArmorStandGeo("test")
        tweaked = ArmorStandGeo("test", tweaks=["ore_borders"])
        source = "textures/blocks/coal_ore"

        self.assertIn("Vanilla_Resource_Pack", plain.texture_file(source))
        self.assertIn("ore_borders", tweaked.texture_file(source))

    def test_a_texture_no_tweak_carries_still_comes_from_the_vanilla_pack(self):
        tweaked = ArmorStandGeo("test", tweaks=["ore_borders"])

        self.assertIn("Vanilla_Resource_Pack",
                      tweaked.texture_file("textures/blocks/planks_oak"))

    def test_a_tweak_may_ship_a_tga_where_the_pack_ships_a_png(self):
        tweaked = ArmorStandGeo("test", tweaks=["age_25_kelp"])

        self.assertTrue(
            tweaked.texture_file("textures/blocks/age_25_kelp").endswith(".tga"))

    def test_a_tweaks_own_terrain_entries_are_merged_over_the_vanilla_ones(self):
        plain = ArmorStandGeo("test")
        tweaked = ArmorStandGeo("test", tweaks=["age_25_kelp"])

        self.assertIsInstance(
            plain.terrain_texture["texture_data"]["kelp_top"]["textures"], str)
        self.assertIsInstance(
            tweaked.terrain_texture["texture_data"]["kelp_top"]["textures"],
            list)

    def test_a_carried_tweak_paints_the_placed_block(self):
        """Minecraft can only tell waxed copper apart in the inventory, so the
        art is in `carried_textures`; a ghost block is the placed block."""
        plain = ArmorStandGeo("test")
        tweaked = ArmorStandGeo("test", tweaks=["visual_waxed_copper"])

        self.assertEqual(plain.get_block_texture_paths("waxed_copper")["up"],
                         "textures/blocks/copper_block")
        self.assertEqual(tweaked.get_block_texture_paths("waxed_copper")["up"],
                         "textures/blocks/waxed_copper_block")

    def test_a_block_no_carried_tweak_names_is_painted_as_it_always_was(self):
        tweaked = ArmorStandGeo("test", tweaks=["visual_waxed_copper"])

        self.assertEqual(tweaked.get_block_texture_paths("copper_block")["up"],
                         "textures/blocks/copper_block")


class CreditTests(unittest.TestCase):
    """The licence allows this provided the credit goes with the files."""

    def test_a_pack_with_no_tweak_says_nothing_about_them(self):
        self.assertNotIn(manifest.TWEAKS_CREDIT,
                         manifest.build_description(tweaks=()))

    def test_a_pack_built_with_one_credits_it_in_the_description(self):
        self.assertIn(manifest.TWEAKS_CREDIT,
                      manifest.build_description(tweaks=("ore_borders",)))

    def test_a_built_pack_carries_credits_txt_only_when_it_has_to(self):
        import glob
        import shutil
        import tempfile

        source = sorted(glob.glob(os.path.join("test_structures",
                                               "*.mcstructure")))[0]
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)

        for label, chosen, wanted in (("plain", [], False),
                                      ("tweaked", ["ore_borders"], True)):
            pack = scaffold(os.path.join(folder, "Credit " + label))
            pack.set_tweaks(chosen)
            pack.add_model("", source)
            pack.set_model_offset("", [0, 0, 0])
            pack.generate_with_nametags()
            with zipfile.ZipFile(pack.compile_pack()) as archive:
                names = archive.namelist()
            with self.subTest(pack=label):
                self.assertEqual("credits.txt" in names, wanted)
                if wanted:
                    with zipfile.ZipFile(
                            os.path.join(folder, "Credit tweaked.mcpack")) as a:
                        text = a.read("credits.txt").decode("utf-8")
                    for link in tweaks.CREDIT_LINKS:
                        self.assertIn(link, text)


class FingerprintTests(unittest.TestCase):
    def test_two_packs_differing_only_by_a_tweak_are_different_packs(self):
        plain = scaffold("Fingerprint")
        tweaked = scaffold("Fingerprint")
        tweaked.set_tweaks(["ore_borders"])

        self.assertNotEqual(plain.fingerprint(), tweaked.fingerprint())

    def test_the_order_tweaks_were_chosen_in_is_part_of_the_pack(self):
        ## two tweaks touching one texture are applied in order, so the order
        ## is part of what the pack came out as
        one = scaffold("Fingerprint")
        two = scaffold("Fingerprint")
        one.set_tweaks(["ore_borders", "clean_redstone_dust"])
        two.set_tweaks(["clean_redstone_dust", "ore_borders"])

        self.assertNotEqual(one.fingerprint(), two.fingerprint())


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.stored = dict(settings.settings)
        self.addCleanup(settings.settings.update, self.stored)
        self.saved = settings.save
        settings.save = lambda: None
        self.addCleanup(setattr, settings, "save", self.saved)

    def test_the_switch_and_the_list_are_remembered_apart(self):
        ## turning the lot off for one pack must not forget which are liked
        settings.set_tweaks_on(["ore_borders", "clean_redstone_dust"])
        settings.set_tweaks(False)

        self.assertEqual(settings.chosen_tweaks(), [])
        self.assertEqual(settings.tweaks_on(),
                         ["ore_borders", "clean_redstone_dust"])

        settings.set_tweaks(True)
        self.assertEqual(settings.chosen_tweaks(),
                         ["ore_borders", "clean_redstone_dust"])

    def test_a_name_this_build_does_not_offer_is_read_past(self):
        ## a settings file written by a newer Scaffold still carries its
        ## choices back when this one is run again
        settings.settings["tweaks_on"] = ["ore_borders", "from_the_future"]

        self.assertEqual(settings.tweaks_on(), ["ore_borders"])


if __name__ == "__main__":
    unittest.main()
