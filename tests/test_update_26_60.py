"""What Minecraft 26.60 changed that Scaffold reads.

The update added no block with art of its own: the ice crystal and the icicle
are experimental, and the disc press has no texture and no name. What it did
change is what a structure records. Chorus plants, fire and redstone dust now
save which sides they join, and a structure exported from the game is
compressed. Chorus plants are drawn from their joins here; dust is covered by
`tests/test_dust.py` and the compression by `tests/test_structure_reader.py`.
Fire's joins are not drawn: they need Java's fire models, which Scaffold does
not carry.
"""
import os
import unittest

from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import structure_reader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = ("north", "east", "south", "west", "up", "down")


def joins(*joined):
    return {"minecraft:connection_" + side: side in joined for side in SIDES}


class ChorusPlantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = asgc.ArmorStandGeo("chorus", offsets=[0, 0, 0])

    def form(self, states):
        return self.geo.choose("chorus_plant", states)[0]

    def test_a_joined_plant_is_drawn_from_its_joins(self):
        self.assertEqual(self.form(joins("north", "up")), "1-0-0-0-1-0")
        self.assertEqual(self.form(joins()), "0-0-0-0-0-0")

    def test_every_combination_has_a_form(self):
        forms = self.geo.block_shapes["chorus_plant"]
        self.assertEqual(sum(1 for name in forms if name != "default"), 64)

    def test_a_plant_saved_before_26_60_is_its_whole_core(self):
        # it carries no joins, and is drawn as it always was
        self.assertEqual(self.form({}), "default")

    def test_an_arm_reaches_the_side_it_joins(self):
        # the up arm reaches the top of the block, and nothing reaches the
        # bottom when the plant joins nothing below
        shapes = self.geo.block_shapes["chorus_plant"]["0-0-0-0-1-0"]
        tops = [o[1] + s[1] for o, s in zip(shapes["offsets"], shapes["size"])]
        bottoms = [o[1] for o in shapes["offsets"]]
        self.assertAlmostEqual(max(tops), 1.0)
        self.assertGreater(min(bottoms), 0.0)


class StructureTests(unittest.TestCase):
    """The structure saved by the 26.60 preview reads and builds whole."""

    def test_it_reads(self):
        found = structure_reader.StructureFile(
            os.path.join(ROOT, "test_structures", "26_60test.mcstructure"))
        self.assertEqual(int(found.NBTfile["compression"]), 1)
        self.assertGreater(len(found.get_block_list()), 5)


if __name__ == "__main__":
    unittest.main()
