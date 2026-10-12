"""The gallery world keeps every case in reach and every block where it was put."""
import os
import unittest

from tools.checks import gallery


@unittest.skipUnless(os.path.isfile(gallery.MOJANG), "bedrock-samples is not checked out")
class GalleryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        picked = gallery.choose(["door", "bed", "fence", "skull_player", "stairs", "cube", "slab"], False, False)
        cls.cases, cls.version = gallery.all_cases(picked)
        across, tiers, pitch, title, count = gallery.plan("test", len(cls.cases))[0]
        cls.grid = gallery.Grid(across, tiers, pitch, title)
        for family, case in cls.cases[:count]:
            cls.grid.add(family, case)

    def test_every_case_is_within_reach_of_the_stand(self):
        stand = self.grid.stand()
        for _family, _case, (x, y, z) in self.grid.key:
            far = ((x - stand[0]) ** 2 + (y + gallery.GHOST - stand[1]) ** 2
                   + (z - stand[2]) ** 2) ** 0.5
            self.assertLess(far + self.grid.pitch, gallery.REACH)

    def test_a_set_fits_a_structure_block(self):
        wide, tall, deep = self.grid.size
        self.assertLessEqual(wide, 64)
        self.assertLessEqual(deep, 64)
        self.assertLessEqual(tall, gallery.PLOT_TIERS * gallery.TIER)

    def test_a_cage_never_takes_a_blocks_place(self):
        cases = [pos for _f, _c, pos in self.grid.key]
        for pos in cases:
            self.assertNotEqual(self.grid.blocks[pos][0], "minecraft:barrier")

    def test_a_two_block_thing_gets_both_halves(self):
        doors = [pos for family, _c, pos in self.grid.key if family == "door"]
        self.assertTrue(doors, "the first plot holds no door")
        x, y, z = doors[0]
        self.assertTrue(self.grid.blocks[(x, y + 1, z)][1]["upper_block_bit"])

    def test_the_stand_and_the_labels_are_clear_of_every_case(self):
        stand = self.grid.stand()
        self.assertNotIn(stand, self.grid.blocks)
        self.assertNotIn((stand[0], stand[1] - 1, stand[2]), self.grid.blocks)
        # the labels hang on walls outside the set, on all four sides, and
        # every painting on a wall has the wall behind all of it
        for row, _motive in self.grid.labels():
            for along in (self.grid.wide // 2,):
                for wall, inward, outward in gallery.label_walls(self.grid.wide):
                    for facing in (inward, outward):
                        block, cells, _centre = gallery.painting(facing, wall, row, along)
                        for at in cells:
                            x, z = block[0] + at[0], block[2] + at[2]
                            self.assertFalse(0 <= x < self.grid.wide and 0 <= z < self.grid.wide)

    def test_every_state_is_one_the_block_has_today(self):
        # the game does not load a world holding a block with a state it does
        # not know, and the test structures the defaults come from are old
        # saves carrying states long since renamed
        own, _values = gallery.mojang()
        for _family, case in self.cases:
            self.assertLessEqual(set(case.states), set(own["minecraft:" + case.block]),
                                 case.block)

    def test_a_category_too_big_for_one_plot_is_spread_across_several(self):
        plots = gallery.plan("Many", 5000)
        self.assertGreater(len(plots), 1)
        self.assertEqual(sum(p[4] for p in plots), 5000)
        for across, tiers, pitch, title, count in plots:
            self.assertLessEqual(tiers, gallery.PLOT_TIERS)
            self.assertLessEqual(count, across * across * tiers)

    def test_a_plot_name_reads_the_right_way_from_both_sides(self):
        # every face reads correctly from outside, so the face looking out of
        # the plot and the face looking in each carry the words in the order
        # someone standing on that side reads them
        sides = {outer: (outer_way, inner, inner_way)
                 for _axis, _at, outer, outer_way, inner, inner_way
                 in gallery.name_sides(10)}
        self.assertEqual(sides["north"], (-1, "south", +1))
        self.assertEqual(sides["south"], (+1, "north", -1))
        self.assertEqual(sides["east"], (-1, "west", +1))
        self.assertEqual(sides["west"], (+1, "east", -1))

    def test_a_fence_is_not_caged(self):
        x, y, z = next(pos for family, _c, pos in self.grid.key if family == "fence")
        self.assertNotIn((x + 1, y, z), self.grid.blocks)


class WorldFileTests(unittest.TestCase):
    """The database is LevelDB's own log, which the game replays as it opens."""

    def test_the_checksum_is_crc32c(self):
        from tools.checks import worldfile
        self.assertEqual(worldfile.crc32c(b"123456789"), 0xE3069283)

    def test_a_record_longer_than_a_block_reads_back_whole(self):
        import struct
        from tools.checks import worldfile
        payload = bytes(range(256)) * 300
        log = worldfile.log_records([payload])
        got, at = b"", 0
        while at < len(log):
            room = worldfile.BLOCK - at % worldfile.BLOCK
            if room < 7:
                at += room
                continue
            crc, size, kind = struct.unpack("<IHB", log[at:at + 7])
            body = log[at + 7:at + 7 + size]
            self.assertEqual(crc, worldfile._masked(worldfile.crc32c(bytes([kind]) + body)))
            got += body
            at += 7 + size
        self.assertEqual(got, payload)


if __name__ == "__main__":
    unittest.main()
