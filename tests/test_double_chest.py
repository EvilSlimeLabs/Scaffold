"""A double chest: which half a chest block is, and how each half is drawn."""
import os
import unittest

from PIL import Image

from scaffold import core, paths
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import structure_reader
from tools.textures import chests as fronts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Grid:
    """A structure reader with blocks at a few cells and nothing else."""

    origin = (100, 0, 200)

    def __init__(self, blocks, size=(4, 1, 4)):
        self.blocks = blocks
        self.size = size

    def get_size(self):
        return self.size

    def get_block(self, x, y, z):
        return self.blocks.get((x, z), {"name": "minecraft:air", "states": {}})


def chest(facing, name="minecraft:chest"):
    return {"name": name, "states": {"minecraft:cardinal_direction": facing}}


def entity(x, z):
    """A chest's entity naming its partner at cell (x, z) of a Grid."""
    return {"id": "Chest", "pairx": Grid.origin[0] + x, "pairz": Grid.origin[2] + z}


class PairTests(unittest.TestCase):

    def side(self, facing, here, there, partner=None):
        grid = Grid({here: chest(facing), there: partner or chest(facing)})
        return core.paired(grid, here[0], 0, here[1], chest(facing),
                           entity(*there)).get("pair")

    def test_each_facing(self):
        ## the left half, seen from in front, has its partner on its right
        for facing, (dx, dz) in core.LEFT_HAND.items():
            with self.subTest(facing=facing):
                self.assertEqual(self.side(facing, (1, 1), (1 + dx, 1 + dz)), "right")
                self.assertEqual(self.side(facing, (1, 1), (1 - dx, 1 - dz)), "left")

    def test_a_partner_in_line_with_the_front_is_not_a_pair(self):
        self.assertIsNone(self.side("north", (1, 1), (1, 2)))

    def test_a_missing_partner_draws_a_single_chest(self):
        grid = Grid({(1, 1): chest("north")})
        self.assertIsNone(core.paired(grid, 1, 0, 1, chest("north"),
                                      entity(2, 1)).get("pair"))

    def test_a_partner_outside_the_structure_draws_a_single_chest(self):
        grid = Grid({(0, 1): chest("north")})
        self.assertIsNone(core.paired(grid, 0, 0, 1, chest("north"),
                                      entity(-1, 1)).get("pair"))

    def test_a_different_chest_beside_it_is_not_its_partner(self):
        self.assertIsNone(self.side("north", (1, 1), (2, 1),
                                    chest("north", "minecraft:trapped_chest")))

    def test_an_entity_that_names_no_pair_is_left_alone(self):
        alone = {"id": "Chest"}
        self.assertIs(core.paired(Grid({}), 0, 0, 0, chest("north"), alone), alone)

    def test_a_saved_pair(self):
        ## a structure saved by the game, holding fourteen double chests
        found = []
        s = structure_reader.StructureFile(os.path.join(
            ROOT, "test_structures", "01-6xSingleItemSortes.mcstructure"))
        for fields in s.block_entities.values():
            if fields.get("id") != "Chest":
                continue
            x, y, z = (int(fields[k]) - int(s.origin[i]) for i, k in enumerate("xyz"))
            found.append(core.paired(s, x, y, z, s.get_block(x, y, z), fields).get("pair"))
        self.assertEqual(found.count("left"), found.count("right"))
        self.assertGreater(found.count("left"), 0)
        self.assertNotIn(None, found)


class FormTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.geo = asgc.ArmorStandGeo("test")

    def test_each_half_is_its_own_form(self):
        states = {"minecraft:cardinal_direction": "north"}
        for side in ("left", "right"):
            self.assertEqual(self.geo.choose("chest", states, {"pair": side})[0], side)
        self.assertEqual(self.geo.choose("chest", states, {})[0], "default")

    def test_the_halves_meet(self):
        ## the left half reaches the high side of its cell and the right half
        ## starts at the low side of its own, so the two touch across the seam
        shapes = self.geo.block_shapes["chest"]
        left_at, left_size = shapes["left"]["offsets"][0][0], shapes["left"]["size"][0][0]
        right_at = shapes["right"]["offsets"][0][0]
        self.assertAlmostEqual(left_at + left_size, 1.0)
        self.assertAlmostEqual(right_at, 0.0)

    def test_every_pairing_chest_draws_both_halves(self):
        for block in ("chest", "trapped_chest", "copper_chest",
                      "waxed_oxidized_copper_chest"):
            with self.subTest(block=block):
                for side in ("left", "right"):
                    self.geo.make_block(0, 0, 0, block, states={
                        "minecraft:cardinal_direction": "north"}, entity={"pair": side})


class FrontTests(unittest.TestCase):

    def double(self):
        """A double chest entity sheet whose front pixels each name their column."""
        sheet = Image.new("RGBA", (128, 64))
        for x in range(30):
            for y in list(range(14, 19)) + list(range(33, 43)):
                sheet.putpixel((14 + x, y), (x, 0, 200, 255))
        return sheet

    def test_the_single_front_is_still_the_top_left_tile(self):
        single = Image.new("RGBA", (16, 16))
        for x in range(16):
            for y in range(16):
                single.putpixel((x, y), (x * 16, y * 16, 0, 255))
        sheet = fronts.sheet(single, self.double())
        self.assertEqual(sheet.size, (48, 16))
        self.assertEqual(list(sheet.crop((0, 0, 16, 16)).getdata()), list(single.getdata()))

    def test_the_halves_are_the_double_front_with_the_latch_on_the_seam(self):
        single = Image.new("RGBA", (16, 16))
        left, right = fronts.halves(single, self.double())
        ## the outer edges are the double front's own first and last columns
        self.assertEqual(left.getpixel((0, 15))[0], 0)
        self.assertEqual(right.getpixel((15, 15))[0], 29)
        ## and no column of it appears twice in a row more than scaling makes
        row = [left.getpixel((x, 15))[0] for x in range(16)] +               [right.getpixel((x, 15))[0] for x in range(16)]
        self.assertEqual(row, sorted(row), "a column of the front is repeated out of place")
        ## the latch is painted over the seam from the single front
        latch = Image.new("RGBA", (16, 16))
        for x in range(16):
            for y in range(16):
                latch.putpixel((x, y), (255, 255, 255, 255))
        left, right = fronts.halves(latch, self.double())
        self.assertEqual(left.getpixel((15, 2))[:3], (255, 255, 255))
        self.assertEqual(right.getpixel((0, 2))[:3], (255, 255, 255))

    def test_every_front_ships_widened(self):
        for name in fronts.FRONTS:
            with self.subTest(name=name):
                path = "{}/textures/blocks/{}.png".format(paths.vanilla_pack(), name)
                self.assertEqual(Image.open(path).size, (48, 16))


if __name__ == "__main__":
    unittest.main()
