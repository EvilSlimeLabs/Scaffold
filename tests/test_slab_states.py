import unittest

from nbtlib import Byte, String

from scaffold import block_upgrade
from scaffold.pack.armor_stand_geo_class import ArmorStandGeo


class SlabStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = ArmorStandGeo("test")

    def process(self, states, name="cut_copper_slab"):
        """(form, turn, texture) the slab is drawn with."""
        return self.geo.choose(name, states)

    def test_vertical_half_distinguishes_top_and_bottom_slabs(self):
        top = self.process({"minecraft:vertical_half": String("top")})
        bottom = self.process({"minecraft:vertical_half": String("bottom")})

        self.assertEqual(top[:2], ("top", None))
        self.assertEqual(bottom[:2], ("default", None))

    def test_boolean_top_states_still_work(self):
        top = self.process({"upper_block_bit": Byte(1)}, "wooden_door")
        bottom = self.process({"upper_block_bit": Byte(0)}, "wooden_door")
        self.assertEqual(top[0], "top")
        self.assertNotEqual(bottom[0], "top")
        ## a stair names its forms by facing, half and corner, so a stair
        ## turned over is a different form from one the right way up
        top = self.process({"upside_down_bit": Byte(1), "weirdo_direction": 0},
                           "oak_stairs")
        bottom = self.process({"upside_down_bit": Byte(0), "weirdo_direction": 0},
                              "oak_stairs")
        self.assertNotEqual(top[0], bottom[0])

    def test_an_old_top_slot_bit_arrives_as_the_vertical_half(self):
        # older slabs say which half they are in with a byte; a structure
        # translates that to the state every slab carries today
        for bit, expected in ((1, True), (0, False)):
            with self.subTest(bit=bit):
                block = block_upgrade.upgrade({"name": "minecraft:cut_copper_slab",
                                               "states": {"top_slot_bit": Byte(bit)}})
                form = self.process(block["states"])[0]
                self.assertEqual(form == "top", expected)


if __name__ == "__main__":
    unittest.main()
