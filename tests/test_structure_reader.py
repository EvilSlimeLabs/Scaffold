"""Reading a .mcstructure, at both versions of the file format.

Minecraft 26.50 added version 2 of the format. It stores each `block_indices`
layer as a single IntArray rather than a list of Int tags, and leaves the
second layer out entirely when nothing is waterlogged. A version 1 file still
loads, and is rewritten as version 2 the next time the game saves it, so both
have to read the same for as long as anyone has old files.

The structures here are built in memory rather than read off disk, because the
point is that two files carrying the same blocks in different tags give the
same answer, and no pair of recorded files is identical enough to prove that.
"""
import os
import tempfile
import unittest

import nbtlib
from nbtlib import Compound, Int, IntArray, List, String

from scaffold.pack import structure_reader


SIZE = (2, 2, 2)
PALETTE = ["minecraft:air", "minecraft:stone", "minecraft:oak_planks"]
INDICES = [0, 1, 2, 1, 2, 0, 1, 1]          # x outermost, then y, then z
EXTRA = [-1] * 8                            # nothing in the waterlogging layer


def palette_entry(name):
    return Compound({"name": String(name),
                     "states": Compound({}),
                     "version": Int(18168865)})


def structure(version, layers):
    """A whole .mcstructure as nbtlib tags, at the given format version."""
    return nbtlib.File({
        "format_version": Int(version),
        "size": List[Int]([Int(v) for v in SIZE]),
        "structure_world_origin": List[Int]([Int(0), Int(0), Int(0)]),
        "structure": Compound({
            "block_indices": List(layers),
            "entities": List[Compound]([]),
            "palette": Compound({"default": Compound({
                "block_palette": List[Compound](
                    [palette_entry(n) for n in PALETTE]),
                "block_position_data": Compound({}),
            })}),
        }),
    })


def version_one():
    return structure(1, [List[Int]([Int(v) for v in INDICES]),
                         List[Int]([Int(v) for v in EXTRA])])


def version_two(second_layer=True):
    layers = [IntArray(INDICES)]
    if second_layer:
        layers.append(IntArray(EXTRA))
    return structure(2, layers)


def read(nbt):
    """Save the tags and read them back the way a build does."""
    handle, path = tempfile.mkstemp(suffix=".mcstructure")
    os.close(handle)
    try:
        nbt.save(path, byteorder="little")
        reader = structure_reader.StructureFile(path)
        blocks = {(x, y, z): str(reader.get_block(x, y, z)["name"])
                  for x in range(SIZE[0])
                  for y in range(SIZE[1])
                  for z in range(SIZE[2])}
        return blocks, {str(k): int(v) for k, v in reader.get_block_list().items()}
    finally:
        os.remove(path)


class FormatVersionTests(unittest.TestCase):
    def test_version_two_reads_the_same_as_version_one(self):
        self.assertEqual(read(version_one()), read(version_two()))

    def test_the_second_layer_is_optional_in_version_two(self):
        # 26.50 leaves it out when the extra block layer holds nothing, which
        # is most structures; the reader never asks for it
        self.assertEqual(read(version_two(second_layer=False)),
                         read(version_two()))

    def test_the_blocks_are_where_the_indices_put_them(self):
        blocks, counts = read(version_two())
        self.assertEqual(blocks[(0, 0, 0)], "minecraft:air")
        self.assertEqual(blocks[(0, 0, 1)], "minecraft:stone")
        self.assertEqual(blocks[(0, 1, 0)], "minecraft:oak_planks")
        self.assertEqual(counts["minecraft:stone"], 4)
        self.assertEqual(counts["minecraft:oak_planks"], 2)
        self.assertNotIn("minecraft:air", counts)


class RecordedStructureTests(unittest.TestCase):
    """The pair of files recorded from the same build, before and after 26.50.

    They are not identical -- the blocks needing support fell off between the
    two saves -- so what is checked here is that both read, that the version 2
    one carries the block states 26.50 added, and that neither leaves the
    reader with an empty structure.
    """

    folder = os.path.join("test_structures", "All Blocks World")

    def recorded(self, name):
        path = os.path.join(self.folder, name)
        if not os.path.isfile(path):
            self.skipTest("%s is not in this checkout" % name)
        return structure_reader.StructureFile(path)

    def test_both_recorded_files_read(self):
        for name, version in (("lottablocksv1.mcstructure", 1),
                              ("lottablocksv2.mcstructure", 2)):
            with self.subTest(name):
                reader = self.recorded(name)
                self.assertEqual(int(reader.NBTfile["format_version"]), version)
                self.assertEqual(list(reader.size), [32, 35, 32])
                self.assertGreater(len(reader.get_block_list()), 900)

    def test_the_states_26_50_added_do_not_become_variants(self):
        # minecraft:corner on stairs and minecraft:connection_* on fences,
        # panes and bars are new in 26.50. Nothing in nbt_defs.json names
        # them, so they must not reach a block list entry as a variant.
        reader = self.recorded("lottablocksv2.mcstructure")
        states = {str(k) for entry in reader.palette[1:]
                  for k in entry["states"].keys()}
        self.assertIn("minecraft:corner", states)
        self.assertIn("minecraft:connection_north", states)
        for name in reader.get_block_list():
            self.assertNotIn("corner", str(name))
            self.assertNotIn("connection_", str(name))


if __name__ == "__main__":
    unittest.main()
