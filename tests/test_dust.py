"""Redstone dust is joined from the blocks round it, by the rules table."""
import os
import unittest

from scaffold import core, dust
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack.structure_reader import StructureFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = ("north", "east", "south", "west")


def joins(found):
    short = {"none": ".", "side": "s", "up": "U"}
    return "".join(short[found[dust.STATE % side]] for side in SIDES)


class DustStructureTests(unittest.TestCase):
    """`test_structures/redstone_dust.mcstructure`: a square, lines that join and
    end, and a dot, all on one level."""

    @classmethod
    def setUpClass(cls):
        cls.found = StructureFile(os.path.join(ROOT, "test_structures", "redstone_dust.mcstructure"))
        cls.geo = asgc.ArmorStandGeo("dust", offsets=[0, 0, 0])
        cls.rules = dust.Connections()

    def at(self, x, z):
        return joins(self.rules.sides(lambda *a: core.block_at(self.found, *a), x, 0, z,
                                      lambda b: core.whole_cube(self.geo, b)))

    def test_a_corner_joins_its_two_neighbours(self):
        self.assertEqual(self.at(0, 0), ".ss.")

    def test_a_dot_joins_nothing(self):
        self.assertEqual(self.at(0, 4), "....")

    def test_a_short_line_joins_each_end(self):
        self.assertEqual(self.at(0, 6), ".s..")
        self.assertEqual(self.at(1, 6), "...s")


class FacingTests(unittest.TestCase):
    def setUp(self):
        self.rules = dust.Connections()

    def test_a_piston_draws_dust_to_its_back_and_sides(self):
        ## a piston pointing north, by a piston's own numbering
        piston = {"name": "minecraft:piston", "states": {"facing_direction": 3}}
        self.assertEqual(self.rules.faces(piston), {"south", "east", "west", "up", "down"})

    def test_a_facing_read_from_a_structure_is_matched(self):
        ## a structure hands states over as NBT, whose numbers print as Int(3)
        import nbtlib
        piston = {"name": "minecraft:piston", "states": {"facing_direction": nbtlib.Int(3)}}
        self.assertIn("south", self.rules.faces(piston))

    def test_a_repeater_draws_dust_to_its_ends_only(self):
        repeater = {"name": "minecraft:unpowered_repeater",
                    "states": {"minecraft:cardinal_direction": "east"}}
        self.assertEqual(self.rules.faces(repeater), {"east", "west"})

    def test_an_added_rule_is_read_first(self):
        block = {"name": "addon:widget", "states": {}}
        self.assertEqual(self.rules.faces(block), set())
        self.rules.add({"blocks": ["addon:widget"], "faces": ["north"]})
        self.assertEqual(self.rules.faces(block), {"north"})


if __name__ == "__main__":
    unittest.main()
