"""Big build mode: several structures drawn at their places in the world.

A big build reads its structures through `CombinedStructures` and draws them
with the same `make_block` an ordinary pack uses. What makes it big is outside
the blocks: the root bone half turns the whole model, and the animation keeps
it still in the world as the stand turns. So every block in a big build has to
be exactly the block an ordinary pack draws, before that turn; a block turned
or moved on its own is one that faces the wrong way in a big build only.
"""
import copy
import json
import os
import tempfile
import unittest

from scaffold import core
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import structure_reader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
## stairs, doors and fences are drawn from a form per facing rather than a turn,
## and a redstone build carries every kind of rotated block
STRUCTURES = ["26_60test.mcstructure", "efficient_stair_layout.mcstructure",
              "redstone_dust.mcstructure"]


def plain(block):
    """A block as its name and states, which is all a drawing reads."""
    if block is None:
        return None
    return str(block["name"]), {k: str(v) for k, v in dict(block.get("states") or {}).items()}


def path(name):
    return os.path.join(ROOT, "test_structures", name)


def drawn(build):
    """Every bone a build writes, as {name: bone}, without writing a pack."""
    found = []
    real = (asgc.ArmorStandGeo.export, asgc.ArmorStandGeo.export_big)

    def keep(self, *args, **kwargs):
        found.append(copy.deepcopy(self.blocks))

    asgc.ArmorStandGeo.export = asgc.ArmorStandGeo.export_big = keep
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        build()
    finally:
        os.chdir(cwd)
        asgc.ArmorStandGeo.export, asgc.ArmorStandGeo.export_big = real
    return found[-1]


class SameBlocksTests(unittest.TestCase):
    """One structure, built big and built ordinarily at the big build's
    offsets, draws the same bones, cube for cube."""

    def compare(self, name):
        def big():
            pack = core.scaffold("big")
            pack.add_model("", path(name))
            pack.make_big_model([0, 0, 0])

        def ordinary():
            pack = core.scaffold("ordinary")
            pack.add_model("", path(name))
            pack.set_model_offset("", list(asgc.BIG_OFFSETS))
            pack.generate_with_nametags()

        return drawn(big), drawn(ordinary)

    def test_every_block_is_the_ordinary_block(self):
        for name in STRUCTURES:
            with self.subTest(name):
                big, ordinary = self.compare(name)
                self.assertEqual(sorted(big), sorted(ordinary))
                for bone in big:
                    self.assertEqual(json.dumps(big[bone], sort_keys=True),
                                     json.dumps(ordinary[bone], sort_keys=True), bone)


class HalfTurnTests(unittest.TestCase):
    """The whole model is half turned by its root bone, and by nothing else."""

    def test_the_root_bone_turns_the_whole_model(self):
        geo = asgc.ArmorStandGeo("big", offsets=list(asgc.BIG_OFFSETS), size=[1, 1, 1])
        geo.make_layer(0)
        geo.make_block(0, 0, 0, "stone")
        folder = tempfile.mkdtemp()
        geo.export_big(folder)
        with open(os.path.join(folder, "models", "entity",
                               "armor_stand.ghost_blocks_big.geo.json")) as f:
            geometries = json.load(f)["minecraft:geometry"]
        roots = [bone for g in geometries[1:] for bone in g["bones"]
                 if bone["name"] == "ghost_blocks"]
        self.assertTrue(roots)
        for bone in roots:
            self.assertEqual(bone["rotation"], [0, 180, 0])
            self.assertEqual(bone["pivot"], [0, 0, 0])

    def test_the_corner_lands_where_the_animation_expects_it(self):
        # the grid's (0, 0, 0) cell, half turned about the origin, spans x 7.5
        # to 8.5 and z -8.5 to -7.5, which is where animation_class.export_big
        # puts the corner the window and the command line are given
        geo = asgc.ArmorStandGeo("big", offsets=list(asgc.BIG_OFFSETS), size=[1, 1, 1])
        geo.make_block(0, 0, 0, "stone")
        cube = [c for bone in geo.blocks.values() for c in bone["cubes"]][0]
        low = cube["origin"]
        high = [o + s for o, s in zip(low, cube["size"])]
        turned_x = sorted([-low[0], -high[0]])
        turned_z = sorted([-low[2], -high[2]])
        self.assertTrue(7.5 <= turned_x[0] < turned_x[1] <= 8.5, turned_x)
        self.assertTrue(-8.5 <= turned_z[0] < turned_z[1] <= -7.5, turned_z)


class CombinedReaderTests(unittest.TestCase):
    """A big build reads a structure exactly as an ordinary one does."""

    def test_one_structure_reads_the_same_either_way(self):
        for name in STRUCTURES:
            with self.subTest(name):
                single = structure_reader.StructureFile(path(name))
                combined = structure_reader.CombinedStructures([path(name)])
                self.assertEqual([int(n) for n in combined.get_size()],
                                 [int(n) for n in single.size])
                sx, sy, sz = single.size
                for x in range(sx):
                    for y in range(sy):
                        for z in range(sz):
                            at = (x, y, z)
                            self.assertEqual(plain(combined.get_block(*at)),
                                             plain(single.get_block(*at)), at)
                            self.assertEqual(dict(combined.get_block_entity(*at)),
                                             dict(single.get_block_entity(*at)), at)
                            self.assertEqual(plain(combined.get_liquid(*at)),
                                             plain(single.get_liquid(*at)), at)

    def test_the_origin_is_the_lowest_corner(self):
        combined = structure_reader.CombinedStructures([path(n) for n in STRUCTURES])
        lowest = None
        for name in STRUCTURES:
            origin = [int(n) for n in structure_reader.load(path(name))["structure_world_origin"]]
            lowest = origin if lowest is None else [min(a, b) for a, b in zip(lowest, origin)]
        self.assertEqual([int(n) for n in combined.origin], lowest)

    def test_a_structure_sits_at_its_own_place(self):
        combined = structure_reader.CombinedStructures([path(n) for n in STRUCTURES])
        for name in STRUCTURES:
            with self.subTest(name):
                single = structure_reader.StructureFile(path(name))
                corner = [int(a) - int(b) for a, b in zip(single.origin, combined.origin)]
                found = [(x, y, z) for x, y, z in
                         ((x, y, z) for x in range(single.size[0])
                          for y in range(single.size[1]) for z in range(single.size[2]))
                         if single.get_block(x, y, z)["name"] != "minecraft:air"][:20]
                for x, y, z in found:
                    self.assertEqual(
                        combined.get_block(x + corner[0], y + corner[1], z + corner[2])["name"],
                        single.get_block(x, y, z)["name"])


if __name__ == "__main__":
    unittest.main()
