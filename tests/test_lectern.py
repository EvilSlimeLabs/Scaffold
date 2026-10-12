"""The book on a lectern, which is in the block entity and not in the states."""
import unittest

from nbtlib import Byte, Compound, String

from scaffold.pack.armor_stand_geo_class import ArmorStandGeo, LOW_SUFFIX


class LecternBookStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = ArmorStandGeo("test")

    def form(self, entity):
        return self.geo.choose("lectern", {}, entity)[0]

    def entity(self, **fields):
        return dict({"id": String("Lectern")}, **fields)

    def test_a_lectern_with_a_book_asks_for_the_book_form(self):
        self.assertEqual(self.form(self.entity(hasBook=Byte(1))), "book")

    def test_the_book_itself_answers_when_there_is_no_flag(self):
        book = Compound({"Name": String("minecraft:written_book")})
        self.assertEqual(self.form(self.entity(book=book)), "book")

    def test_a_lectern_that_says_it_is_empty_stays_empty(self):
        ## the flag is read before the book, so something left beside a lectern
        ## the game considers empty does not put a book back on it
        book = Compound({"Name": String("minecraft:written_book")})
        self.assertEqual(
            self.form(self.entity(hasBook=Byte(0), book=book)), "default")

    def test_a_lectern_with_no_block_entity_is_drawn_plain(self):
        self.assertEqual(self.form(None), "default")


class LecternBookShapeTests(unittest.TestCase):
    def setUp(self):
        self.geo = ArmorStandGeo("test")

    def test_the_book_form_is_the_plain_lectern_with_more_on_it(self):
        plain = self.geo.block_shapes["lectern"]["default"]
        book = self.geo.block_shapes["lectern"]["book"]

        self.assertEqual(book["size"][:len(plain["size"])], plain["size"])
        self.assertEqual(len(book["size"]), len(plain["size"]) + 4)

    def test_the_book_is_painted_from_the_entity_sheet(self):
        painted = self.geo.block_uv["lectern"]["book"]["overwrite"]["up"]

        self.assertTrue(any("enchanting_table_book" in name
                            for name in painted),
                        painted)

    def test_low_geometry_keeps_the_book_as_a_form_of_its_own(self):
        ## a simplified family has a simpler form for every form the detailed
        ## one has, so a lectern carrying a book is still told apart from one
        ## without when low geometry is on
        low = self.geo.block_shapes["lectern" + LOW_SUFFIX]
        detailed = self.geo.block_shapes["lectern"]

        self.assertEqual(sorted(low), sorted(detailed))
        ## and each is a box of quads wearing the lectern's inventory slot, four
        ## to a face
        for form in low:
            sizes = low[form]["size"]
            self.assertEqual(len(sizes), 24)
            self.assertTrue(all(min(size) == 0 for size in sizes))


if __name__ == "__main__":
    unittest.main()
