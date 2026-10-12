"""The locked hopper: the state is read, and it picks a form of its own."""
import unittest

from nbtlib import Byte, Int

from scaffold.pack.armor_stand_geo_class import ArmorStandGeo


class LockedHopperStateTests(unittest.TestCase):
    """`toggle_bit` picks the locked form of whichever mounting a hopper has."""

    @classmethod
    def setUpClass(cls):
        cls.geo = ArmorStandGeo("test")

    def form(self, states):
        return self.geo.choose("hopper", states)[0]

    def test_toggle_bit_picks_the_locked_form(self):
        self.assertEqual(self.form({"facing_direction": Int(0), "toggle_bit": Byte(1)}),
                         "default-1")
        self.assertEqual(self.form({"facing_direction": Int(2), "toggle_bit": Byte(1)}),
                         "side-1")
        self.assertEqual(self.form({"facing_direction": Int(0), "toggle_bit": Byte(0)}),
                         "default")

    def test_a_hopper_with_no_toggle_bit_is_drawn_unlocked(self):
        self.assertEqual(self.form({"facing_direction": Int(0)}), "default")


class LockedHopperShapeTests(unittest.TestCase):
    """A mounting and the lock join into one form name."""

    def setUp(self):
        self.geo = ArmorStandGeo("test")

    def forms(self):
        return self.geo.block_shapes["hopper"]

    def test_both_mountings_have_a_locked_form(self):
        for name in ("default", "default-1", "side", "side-1"):
            self.assertIn(name, self.forms())

    def test_the_locked_form_matches_the_mounting_it_belongs_to(self):
        ## the shapes are the same today because vanilla draws no difference;
        ## what matters is that the locked hopper is not drawn as the other
        ## mounting, which is what a bare "1" form would have done
        self.assertEqual(self.forms()["default-1"], self.forms()["default"])
        self.assertEqual(self.forms()["side-1"], self.forms()["side"])
        self.assertNotEqual(self.forms()["default"], self.forms()["side"])

    def test_an_unlocked_hopper_falls_back_to_its_plain_mounting(self):
        ## "default-0" and "side-0" are deliberately not written, so an unlocked
        ## hopper lands on the form a hopper has always been drawn with
        self.assertNotIn("default-0", self.forms())
        self.assertNotIn("side-0", self.forms())


class HopperPaintTests(unittest.TestCase):
    """`blocks.json` names the hopper's down slot `hopper_inside`, and that is
    the floor of the basin rather than the underside of the block."""

    def setUp(self):
        self.geo = ArmorStandGeo("test")

    def test_no_face_of_a_hopper_reads_the_basin_plate(self):
        for name, form in self.geo.block_uv["hopper"].items():
            for face, cubes in form["overwrite"].items():
                for texture in cubes:
                    with self.subTest(form=name, face=face):
                        self.assertNotIn("hopper_inside", texture)

    def test_only_the_bowl_is_topped_with_the_rim(self):
        bowl, neck, spout = self.geo.block_uv["hopper"]["default"]["overwrite"]["up"]

        ## the bowl's top reads the block's up slot, which is hopper_top, so a
        ## tweak that gives the hopper its own top is read
        self.assertTrue(bowl.startswith("@up"), bowl)
        self.assertIn("hopper_outside", neck)
        self.assertIn("hopper_outside", spout)


if __name__ == "__main__":
    unittest.main()
