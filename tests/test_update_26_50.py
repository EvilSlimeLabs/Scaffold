"""The blocks Minecraft 26.50 added, and the states it added to old ones.

The update brought 121 blocks: wool and concrete in slab, double slab and stair
form, a poplar wood set, and three that are new shapes rather than new materials
-- the shelf mushroom, the straw bed and the red shrub. It also gave stairs a
`minecraft:corner` state and fences, panes and bars a `minecraft:connection_*`
one, neither of which Scaffold reads.

The cushion is here only as far as 26.50 is concerned. It is an entity rather
than a block -- a .mcstructure keeps it in `structure.entities` with a position,
a rotation and a colour of its own, and nothing in `block_indices` marks the
space it stands in -- so it reaches a pack through the entity pipeline instead.
`tests/test_entities.py` covers that; `CushionTests` below covers the half that
belongs to the update.
"""
import json
import os
import re
import unittest

import nbtlib

from tools.blocks import tables
from scaffold import block_list, paths
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import structure_reader
from scaffold import lookup


STRUCTURE = os.path.join("test_structures", "All Blocks World",
                         "26.50_update.mcstructure")

COLOURS = ("black", "blue", "brown", "cyan", "gray", "green", "light_blue",
           "light_gray", "lime", "magenta", "orange", "pink", "purple", "red",
           "white", "yellow")

## the wood set a modern wood comes in, and the family that draws each part
POPLAR = {
    "poplar_button": "button", "poplar_door": "door",
    "poplar_double_slab": "cube", "poplar_fence": "fence",
    "poplar_fence_gate": "fence_gate", "poplar_hanging_sign": "hanging_sign",
    "poplar_log": "tree", "poplar_planks": "cube",
    "poplar_pressure_plate": "pressure_plate",
    "poplar_sapling": "cross_texture", "poplar_shelf": "shelf",
    "poplar_slab": "slab", "poplar_stairs": "stairs",
    "poplar_standing_sign": "standing_sign", "poplar_trapdoor": "trapdoor",
    "poplar_wall_sign": "wall_sign", "poplar_wood": "cube",
    "stripped_poplar_log": "tree", "stripped_poplar_wood": "cube",
    "orange_poplar_leaves": "cube", "red_poplar_leaves": "cube",
    "yellow_poplar_leaves": "cube",
}


## the three tables a family's geometry is written in, which are read the way
## the family was authored: a family turned to Minecraft's rest pose as it was
## written is turned back, so what is checked here is the layout its generator
## describes. What a block looks like once drawn is `make_block`'s, and the
## tests that need that call it.
GEOMETRY = ("block_shapes", "block_uv", "block_rotation")


def load(name):
    # through paths, so the suite does not depend on where it was run from
    if name in GEOMETRY:
        return tables.load({"block_shapes": tables.SHAPES, "block_uv": tables.UV,
                            "block_rotation": tables.ROTATION}[name])
    with open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return lookup.unwrap(name + ".json", json.load(f))


class DefinitionTests(unittest.TestCase):
    """Every new block points at a family, and at the right one."""

    @classmethod
    def setUpClass(cls):
        cls.defs = load("block_definition")

    def test_the_wool_and_concrete_shapes_are_all_there(self):
        missing = []
        for colour in COLOURS:
            for material in ("wool", "concrete"):
                for shape, family in (("slab", "slab"),
                                      ("double_slab", "cube"),
                                      ("stairs", "stairs")):
                    block = "%s_%s_%s" % (colour, material, shape)
                    if self.defs.get(block) != family:
                        missing.append("%s -> %r, wanted %r"
                                       % (block, self.defs.get(block), family))
        self.assertEqual(missing, [])

    def test_poplar_is_shaped_like_every_other_modern_wood(self):
        for block, family in POPLAR.items():
            with self.subTest(block):
                self.assertEqual(self.defs.get(block), family)

    def test_poplar_matches_cherry_part_for_part(self):
        # a wood set gaining or losing a part is worth noticing, and cherry is
        # the set poplar was written from
        cherry = {name.replace("cherry", "poplar"): family
                  for name, family in self.defs.items()
                  if re.match(r"^(stripped_)?cherry_", name)}
        poplar = {name: family for name, family in self.defs.items()
                  if re.match(r"^(stripped_)?poplar_", name)}
        ## cherry has plain leaves and poplar has three autumn colours instead
        cherry.pop("poplar_leaves", None)
        for colour in ("orange", "red", "yellow"):
            poplar.pop("%s_poplar_leaves" % colour, None)
        self.assertEqual(poplar, cherry)

    def test_the_three_new_shapes_have_families_of_their_own(self):
        self.assertEqual(self.defs.get("shelf_mushroom"), "shelf_mushroom")
        self.assertEqual(self.defs.get("straw_bed"), "straw_bed")
        ## a shrub is two crossed planes, geometry.cross in Mojang's own block
        self.assertEqual(self.defs.get("red_shrub"), "cross_texture")


class BuildTests(unittest.TestCase):
    """The new blocks come out of make_block as cubes rather than as errors."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def cubes(self, name, **kwargs):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, name, **kwargs)
        return [(tuple(c["origin"]), tuple(c["size"]))
                for group in self.geo.blocks.values()
                for c in group.get("cubes", [])]

    def test_every_new_block_builds(self):
        broken = []
        blocks = list(POPLAR) + ["shelf_mushroom", "straw_bed", "red_shrub"]
        for colour in COLOURS:
            for material in ("wool", "concrete"):
                blocks += ["%s_%s_%s" % (colour, material, shape)
                           for shape in ("slab", "double_slab", "stairs")]
        for block in blocks:
            try:
                self.assertTrue(self.cubes(block), "%s built nothing" % block)
            except Exception as exc:
                broken.append("%s (%s: %s)" % (block, type(exc).__name__, exc))
        self.assertEqual(broken, [])

    def test_a_wool_slab_is_half_a_block_and_its_double_is_whole(self):
        # a ghost block that fills its cell is drawn a shade under full size on
        # purpose, so the real block covers it rather than z-fighting with it;
        # a double slab is the plain cube family and comes out at 0.95
        slab = self.cubes("white_wool_slab")
        double = self.cubes("white_wool_double_slab")
        self.assertEqual(len(slab), 1)
        self.assertAlmostEqual(slab[0][1][1], 0.5, places=2)
        self.assertGreater(double[0][1][1], slab[0][1][1] * 1.5)
        self.assertLessEqual(double[0][1][1], 1.0)

    def test_a_wool_slab_sits_on_the_floor_and_its_top_form_does_not(self):
        low = self.cubes("white_wool_slab")[0][0][1]
        high = self.cubes("white_wool_slab", data="top")[0][0][1]
        self.assertLess(low, high)


class ShelfMushroomTests(unittest.TestCase):
    """Two sizes, mounted on a wall, drawn from Mojang's own block model."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def cubes(self, **kwargs):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "shelf_mushroom", **kwargs)
        return [(tuple(c["origin"]), tuple(c["size"]))
                for group in self.geo.blocks.values()
                for c in group.get("cubes", [])]

    def test_growth_picks_between_two_sizes(self):
        small, large = self.cubes(data="0"), self.cubes(data="1")
        self.assertEqual(len(small), 2)
        self.assertEqual(len(large), 2)
        self.assertNotEqual(small, large)
        ## the large one is wider and deeper than the small one, cap for cap
        self.assertGreater(large[0][1][0], small[0][1][0])
        self.assertGreater(large[0][1][2], small[0][1][2])

    def test_an_unstated_mushroom_is_the_small_one(self):
        self.assertEqual(self.cubes(), self.cubes(data="0"))

    def test_it_hangs_on_the_wall_behind_it(self):
        # a wall mounting reaches z 16 the way a wall sign does, so the wall is
        # the block behind it, to the south, and the mushroom looks north
        shapes = load("block_shapes")["shelf_mushroom"]
        for form in ("0", "1"):
            for size, at in zip(shapes[form]["size"], shapes[form]["offsets"]):
                self.assertAlmostEqual(at[2] + size[2], 1.0,
                                       msg="%s left the wall" % form)
                self.assertLess(size[2], 1.0)

    def test_the_two_growths_read_different_sheets(self):
        uv = load("block_uv")["shelf_mushroom"]
        small = uv["0"]["overwrite"]["south"][0]
        large = uv["1"]["overwrite"]["south"][0]
        self.assertIn("shelf_mushroom_small", small)
        self.assertIn("shelf_mushroom_large", large)

    def test_the_cap_reads_mojangs_own_rectangle(self):
        # Mojang's model faces north, as this family does, so the top and the
        # bottom read their rectangles as the model gives them, unturned.
        # Turned, the cap's pale front lip is drawn against the wall.
        uv = load("block_uv")["shelf_mushroom"]["0"]
        for face in ("up", "down"):
            for index, texture in enumerate(uv["overwrite"][face]):
                self.assertNotIn("^", texture, "%s is turned: %s" % (face, texture))
                self.assertTrue(all(n > 0 for n in uv["uv_sizes"][face][index]))

    def test_it_faces_the_way_a_shelf_does(self):
        rotation = load("block_rotation")
        self.assertEqual(rotation["shelf_mushroom"], rotation["shelf"])


class StrawBedTests(unittest.TestCase):
    """One colour, two halves, and no block entity to ask about it."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def cubes(self, **kwargs):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "straw_bed", **kwargs)
        return [(tuple(c["origin"]), tuple(c["size"]))
                for group in self.geo.blocks.values()
                for c in group.get("cubes", [])]

    def test_the_foot_is_one_box_and_the_head_is_two(self):
        self.assertEqual(len(self.cubes(data="0")), 1)
        self.assertEqual(len(self.cubes(data="1")), 2)

    def test_the_pillow_is_the_taller_half_of_the_head(self):
        base, pillow = sorted(self.cubes(data="1"), key=lambda c: c[1][1])
        self.assertGreater(pillow[1][1], base[1][1])
        ## and they stand beside each other along the bed rather than stacked
        self.assertEqual(base[0][1], pillow[0][1])

    def test_it_lies_along_z_the_way_the_dyed_bed_does(self):
        # the two turn by their states' own angles, which only works if they
        # lie the same way: each half of the head is the whole of x and half a
        # block along z
        shapes = load("block_shapes")["straw_bed"]["1"]
        for size in shapes["size"]:
            self.assertAlmostEqual(size[0], 1.0, places=3)
            self.assertAlmostEqual(size[2], 0.5, places=3)

    def test_it_turns_with_the_dyed_bed(self):
        # a dyed bed carries a numbered `direction` and a straw bed the words,
        # counted from south the same way, and the two lie the same way round
        rotation = load("block_rotation")
        for number, word in enumerate(("south", "west", "north", "east")):
            with self.subTest(facing=word):
                self.assertEqual(rotation["straw_bed"][word],
                                 rotation["bed"][str(number)])

    def test_the_top_reads_the_straw_along_the_bed(self):
        # Mojang's model lies along z, as this one does, so no tile is turned;
        # turned a quarter, the straw runs across the mattress. The top reads
        # its rectangle backwards and the bottom forwards.
        uv = load("block_uv")["straw_bed"]["1"]
        for face in ("up", "down"):
            for index, texture in enumerate(uv["overwrite"][face]):
                self.assertNotIn("^", texture, "%s is turned: %s" % (face, texture))
                forwards = all(n > 0 for n in uv["uv_sizes"][face][index])
                self.assertEqual(forwards, face == "down")

    def test_the_frills_are_left_off(self):
        # Mojang hangs ten zero thickness planes of straw off the edges. Every
        # one would be another cube in a ghost block, and a transparent texel
        # still takes the depth it stands at, so they would cut holes in the
        # mattress rather than feather it.
        self.assertLessEqual(len(self.cubes(data="1")), 2)
        for _origin, size in self.cubes(data="1"):
            self.assertTrue(all(n > 0 for n in size), "a zero thickness cube")

    def test_it_is_the_whole_bed_without_a_block_entity(self):
        # a dyed bed takes its colour from the block entity beside it and falls
        # back to red; a straw bed carries no entity at all, so the half it is
        # told is the whole answer
        self.assertTrue(self.cubes(data="0"))
        self.assertTrue(self.cubes())


class NewStatesTests(unittest.TestCase):
    """26.50 gave old blocks new states, and the families that join read them."""

    def test_the_joining_families_read_the_new_states(self):
        from scaffold import block_geometry
        rules = block_geometry.rules()
        for family in ("fence", "pane", "bars", "tripwire"):
            read = json.dumps(rules[family])
            for side in ("north", "east", "south", "west"):
                with self.subTest(family=family, side=side):
                    self.assertIn('"minecraft:connection_%s"' % side, read)
        self.assertIn('"minecraft:corner"', json.dumps(rules["stairs"]))

    def test_a_stair_builds_whatever_corner_it_carries(self):
        geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])
        for corner in ("none", "inner_left", "inner_right",
                       "outer_left", "outer_right"):
            geo.blocks = {}
            geo.make_block(0, 0, 0, "poplar_stairs", rot=0)
            self.assertTrue(geo.blocks, "a %s stair built nothing" % corner)


class BlockListTests(unittest.TestCase):
    """A block with no name is listed as its own id, which nobody shops from."""

    def named(self, block):
        return block_list.name_of("minecraft:" + block)

    def test_every_new_block_is_named(self):
        blocks = list(POPLAR) + ["shelf_mushroom", "straw_bed", "red_shrub"]
        for colour in COLOURS:
            for material in ("wool", "concrete"):
                blocks += ["%s_%s_%s" % (colour, material, shape)
                           for shape in ("slab", "double_slab", "stairs")]
        unnamed = [b for b in blocks if self.named(b) == b]
        self.assertEqual(unnamed, [])

    def test_the_new_blocks_land_under_a_heading(self):
        wanted = {
            "white_wool_slab": "Wool", "white_wool_stairs": "Wool",
            "black_wool_double_slab": "Wool",
            "white_concrete_slab": "Concrete",
            "poplar_planks": "Poplar", "poplar_stairs": "Poplar",
            "stripped_poplar_log": "Poplar",
            ## gathered as an item, so the plant patterns take it first
            "orange_poplar_leaves": "Flowers and Plants",
            "poplar_sapling": "Flowers and Plants",
            "red_shrub": "Flowers and Plants",
            "shelf_mushroom": "Flowers and Plants",
        }
        for block, heading in wanted.items():
            with self.subTest(block):
                self.assertEqual(
                    block_list.category_of("minecraft:" + block), heading)

    def test_a_straw_bed_is_listed_beside_the_dyed_one(self):
        self.assertEqual(block_list.category_of("minecraft:straw_bed"),
                         block_list.category_of("minecraft:bed"))


class StructureTests(unittest.TestCase):
    """The recorded structure of the update, built the way a user would."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(STRUCTURE):
            raise unittest.SkipTest("%s is not in this checkout" % STRUCTURE)
        cls.reader = structure_reader.StructureFile(STRUCTURE)

    def test_it_is_a_version_two_file(self):
        self.assertEqual(int(self.reader.NBTfile["format_version"]), 2)

    def test_every_block_in_it_is_declared(self):
        defs = load("block_definition")
        placed = {str(k).partition("/")[0].replace("minecraft:", "")
                  for k in self.reader.get_block_list()}
        self.assertEqual(sorted(placed - set(defs)), [])

    def test_nothing_in_it_is_skipped(self):
        from scaffold import core
        pack = core.scaffold("test_26_50")
        pack.add_model("probe", STRUCTURE)
        pack.set_model_offset("probe", [0, 0, 0])
        import contextlib
        import io as _io
        with contextlib.redirect_stdout(_io.StringIO()):
            pack.generate_with_nametags()
        self.assertEqual(pack.get_skipped(write_file=False), {})


class CushionTests(unittest.TestCase):
    """A cushion is an entity, and reaches a pack through the entity pipeline.

    It is drawn and counted like a block, but nothing about it is in the block
    grid: `tests/test_entities.py` covers the pipeline itself, and what is here
    is the half of it that belongs to 26.50 -- that this is what the update
    shipped and what a structure records for it.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(STRUCTURE):
            raise unittest.SkipTest("%s is not in this checkout" % STRUCTURE)
        cls.nbt = nbtlib.load(STRUCTURE, byteorder="little")

    def test_the_structure_carries_cushions_as_entities(self):
        kinds = [str(e.get("identifier", "")) for e in self.nbt["structure"]["entities"]]
        self.assertIn("minecraft:cushion", kinds)

    def test_no_cushion_is_in_the_block_grid(self):
        # it has no blocks.json entry and no block id, so no palette can ever
        # name one; a block list gets its cushions from the entity pass instead
        reader = structure_reader.StructureFile(STRUCTURE)
        named = [str(k) for k in reader.get_block_list() if "cushion" in str(k)]
        self.assertEqual(named, [])

    def test_a_cushion_is_drawn_from_the_entity_list(self):
        from scaffold import core
        self.assertIn("minecraft:cushion", core.ENTITY_MODELS)
        reader = structure_reader.StructureFile(STRUCTURE)
        cushions = [e for e in reader.get_entities()
                    if e["id"] == "minecraft:cushion"]
        forms = core.ENTITY_MODELS["minecraft:cushion"]["forms"]
        self.assertTrue(cushions)
        self.assertEqual(len(cushions) % len(forms), 0,
                         "26.50 places a whole set of colours")


if __name__ == "__main__":
    unittest.main()
