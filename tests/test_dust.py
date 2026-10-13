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


class SavedJoinsTests(unittest.TestCase):
    """A structure saved by Minecraft 26.60 or later carries the joins the game
    draws a dust with, and they are read instead of worked out.

    `test_structures/26_60test.mcstructure` was saved by the 26.60 preview."""

    @classmethod
    def setUpClass(cls):
        cls.found = StructureFile(os.path.join(ROOT, "test_structures", "26_60test.mcstructure"))
        cls.geo = asgc.ArmorStandGeo("dust", offsets=[0, 0, 0])
        cls.rules = dust.Connections()

    def dusts(self):
        sx, sy, sz = self.found.size
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = self.found.get_block(x, y, z)
                    if self.rules.is_dust(block):
                        yield (x, y, z), block

    def test_every_dust_saved_its_joins(self):
        for at, block in self.dusts():
            with self.subTest(at):
                self.assertIsNotNone(dust.saved(block["states"]))

    def test_the_saved_joins_draw_what_the_worked_out_ones_do(self):
        # the game saves a lone dust as the cross and an end as a straight line,
        # and the family draws those exactly as it draws the joins worked out
        shapes = self.geo.block_shapes["red_dust"]
        windows = self.geo.block_uv["red_dust"]
        for at, block in self.dusts():
            with self.subTest(at):
                saved = dust.saved(block["states"])
                worked = self.rules.sides(lambda *a: core.block_at(self.found, *a), *at,
                                          lambda b: core.whole_cube(self.geo, b))
                name = lambda found: "-".join(found[dust.STATE % side] for side in SIDES)
                self.assertEqual(shapes[name(saved)], shapes[name(worked)])
                self.assertEqual(windows[name(saved)], windows[name(worked)])

    def test_a_structure_from_before_26_60_has_none(self):
        self.assertIsNone(dust.saved({"redstone_signal": 3}))

    def test_an_unknown_join_is_not_trusted(self):
        states = {"redstone_%s" % side: "side" for side in SIDES}
        states["redstone_east"] = "sideways"
        self.assertIsNone(dust.saved(states))


class PowerColourTests(unittest.TestCase):
    """Dust is tinted the colour Minecraft draws it at its power."""

    def test_unpowered_dust_is_dull_red(self):
        self.assertEqual(dust.colour(0), 0x4C0000)

    def test_full_power_is_bright_with_a_touch_of_green(self):
        self.assertEqual(dust.colour(15), 0xFF3300)

    def test_every_level_is_its_own_shade(self):
        self.assertEqual(len({dust.colour(p) for p in range(16)}), 16)

    def test_a_signal_out_of_range_is_held_to_it(self):
        self.assertEqual(dust.colour(40), dust.colour(15))
        self.assertEqual(dust.colour("not a number"), dust.colour(0))


if __name__ == "__main__":
    unittest.main()
