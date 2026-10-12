"""The geometry tables describe a block the way Minecraft does.

A block rests facing north, its cubes sit where a Bedrock `.geo.json` puts
them, and a rotation table holds Minecraft's own angle for each state. Most of
what is checked here can be read off the tables; the rest is checked against
Mojang's own model where the submodule is there to read.
"""
import json
import os
import unittest

from scaffold import jsonc, paths
from scaffold.pack import armor_stand_geo_class as asgc
from tools.blocks import tables
from scaffold import lookup
from tools import sources

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOJANG = sources.resource_pack("models",
                      "blocks")


def load(name):
    if name in ("block_shapes", "block_uv", "block_rotation"):
        from scaffold import block_geometry
        return block_geometry.table(name)
    with open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return lookup.unwrap(name + ".json", json.load(f))


NORTH, WEST, SOUTH, EAST = [0, 0, 0], [0, 90, 0], [0, 180, 0], [0, 270, 0]
CARDINAL = {"north": NORTH, "west": WEST, "south": SOUTH, "east": EAST}
## `direction` on the blocks that still carry it, counted from south
DIRECTION = {"0": SOUTH, "1": WEST, "2": NORTH, "3": EAST}
## `facing_direction`, down and up then the four sides
FACING = {"0": [90, 0, 0], "1": [-90 % 360, 0, 0], "2": NORTH, "3": SOUTH,
          "4": WEST, "5": EAST}


class AnglesTests(unittest.TestCase):
    """A rotation table holds the angle Minecraft gives each state."""

    ## the families whose tables are exactly Minecraft's. The rest either carry
    ## a state that is not a facing -- a rail's shape, a log's axis -- or have
    ## a table that does not agree with Minecraft's numbering and is kept
    ## drawing what it drew until a world says otherwise: see `docs/Block
    ## Notes.md`.
    CARDINAL_FAMILIES = (
        "anvil", "big_dripleaf", "campfire", "carved_pumpkin", "chest",
        "comparator", "copper_golem_statue", "dried_ghast",
        "fence_gate", "furnace", "lit_furnace", "lectern", "portal_frame", "repeater",
        "shelf", "shelf_mushroom", "stonecutter_block", "straw_bed")
    ## cocoa is half a turn from these, which a world showed
    DIRECTION_FAMILIES = ("bed", "bell", "chiseled_bookshelf",
                          "decorated_pot", "grindstone", "hive", "loom",
                          "tripwire_hook")
    FACING_FAMILIES = ("barrel", "glazed_terracotta")

    def test_a_cardinal_direction_is_minecrafts_angle(self):
        turns = load("block_rotation")
        for family in self.CARDINAL_FAMILIES:
            with self.subTest(family=family):
                ## a "<form>:<value>" key is a form that turns differently
                plain = {k: v for k, v in turns[family].items() if ":" not in k}
                self.assertEqual(plain, CARDINAL)

    def test_a_numbered_direction_is_minecrafts_angle(self):
        turns = load("block_rotation")
        for family in self.DIRECTION_FAMILIES:
            with self.subTest(family=family):
                self.assertEqual(turns[family], DIRECTION)

    def test_a_facing_direction_is_minecrafts_angle(self):
        turns = load("block_rotation")
        for family in self.FACING_FAMILIES:
            with self.subTest(family=family):
                ## glazed terracotta facing down is drawn as facing up
                expected = dict(FACING, **{"0": FACING["1"]})                     if family == "glazed_terracotta" else FACING
                self.assertEqual(turns[family], expected)

    def test_a_head_on_the_floor_is_at_rest_and_on_a_wall_faces_out(self):
        turns = load("block_rotation")
        for family in (f for f in turns if f.startswith("skull_")):
            with self.subTest(family=family):
                self.assertEqual(turns[family],
                                 {"1": NORTH, "wall:2": NORTH,
                                  "wall:3": SOUTH, "wall:4": WEST,
                                  "wall:5": EAST})

    def test_a_bone_turns_the_other_way_about_y_and_z(self):
        # the model is the world mirrored in x, so a turn carrying north to
        # west in the world carries it to east in the model
        self.assertEqual(asgc.to_bone([0, 90, 0]), [0, 270, 0])
        self.assertEqual(asgc.to_bone([90, 0, 0]), [90, 0, 0])
        self.assertEqual(asgc.to_bone([0, 0, 90]), [0, 0, 270])
        self.assertEqual(asgc.to_bone([0, 0, 0]), [0, 0, 0])


@unittest.skipUnless(os.path.isdir(MOJANG), "bedrock-samples is not checked out")
class MojangModelTests(unittest.TestCase):
    """Where Mojang ships a block's model, the table is that model."""

    def test_the_shelf_mushroom_is_mojangs_small_mushroom(self):
        # a .geo.json is in pixels about the middle of the block's floor; the
        # tables are in blocks from its corner, and otherwise the same
        model = jsonc.load(os.path.join(MOJANG, "shelf_mushroom_small.geo.json"))
        theirs = sorted(
            (tuple((c["origin"][i] + (8 if i != 1 else 0)) / 16.0
                   for i in range(3)),
             tuple(v / 16.0 for v in c["size"]))
            for bone in model["minecraft:geometry"][0]["bones"]
            for c in bone.get("cubes", []))
        shape = load("block_shapes")["shelf_mushroom"]["0"]
        ours = sorted((tuple(at), tuple(size))
                      for at, size in zip(shape["offsets"], shape["size"]))
        self.assertEqual(ours, theirs)


class BehindTests(unittest.TestCase):
    """A cube read from behind: how the families resting north are painted."""

    def test_the_top_and_bottom_read_backwards(self):
        from tools.blocks.geometry import Cube
        cube = Cube((16, 8, 4), (0, 0, 12), behind=True)
        self.assertEqual(cube.uv("up"), ([1.0, 1.0], [-1.0, -0.25]))
        self.assertEqual(cube.uv("down"), ([1.0, 0.25], [-1.0, -0.25]))

    def test_a_side_measures_its_place_from_the_far_side(self):
        from tools.blocks.geometry import Cube
        cube = Cube((2, 16, 4), (0, 0, 12), behind=True)
        ## at the east edge, so seen from behind it is at the west one
        self.assertEqual(cube.uv("north")[0], [0.875, 0.0])
        self.assertEqual(cube.uv("east")[0], [0.0, 0.0])

    def test_a_side_left_to_itself_reads_the_opposite_slot(self):
        from tools.blocks.geometry import Cube
        cube = Cube((16, 16, 16), (0, 0, 0), behind=True)
        self.assertEqual(cube.paint("north"), "@south")
        self.assertEqual(cube.paint("up"), "default")
        self.assertEqual(Cube((16, 16, 16), (0, 0, 0), "@north",
                              behind=True).paint("north"), "default")


class LowGeometryTests(unittest.TestCase):
    """A simpler form turns with its family and wears its own textures."""

    def test_a_simpler_form_turns_like_the_detailed_one(self):
        for name, rot, data in (("bell", 1, "side"), ("fence_gate", "east", 0),
                                ("lectern", "west", 0), ("anvil", "east", 0)):
            turned = []
            for low in (False, True):
                geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0],
                                         low_geometry=low)
                geo.make_block(0, 0, 0, name, rot=rot, data=data)
                cubes = [c for g in geo.blocks.values() for c in g["cubes"]]
                turned.append({(tuple(c.get("rotation") or ()),
                                tuple(c.get("pivot") or ())) for c in cubes})
            with self.subTest(block=name):
                self.assertTrue(turned[1] <= turned[0],
                                "%s's simpler form turns some other way" % name)

    def test_a_simpler_form_has_every_form_the_detailed_one_has(self):
        shapes = load("block_shapes")
        for family in shapes:
            if not family.endswith(asgc.LOW_SUFFIX):
                continue
            detailed = family[:-len(asgc.LOW_SUFFIX)]
            with self.subTest(family=detailed):
                self.assertEqual(sorted(shapes[family]), sorted(shapes[detailed]))
                for form, body in shapes[family].items():
                    self.assertEqual(body["center"],
                                     shapes[detailed][form]["center"],
                                     "%s %s pivots somewhere else" % (detailed, form))


if __name__ == "__main__":
    unittest.main()
