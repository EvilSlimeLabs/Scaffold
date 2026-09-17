"""The book on a lectern, which is in the block entity and not in the states."""
import unittest

from nbtlib import Byte, Compound, String

from scaffold.core import scaffold
from scaffold.pack.armor_stand_geo_class import ArmorStandGeo, LOW_SUFFIX


class LecternBookStateTests(unittest.TestCase):
    def setUp(self):
        self.processor = scaffold.__new__(scaffold)

    def form(self, entity):
        block = {"name": "minecraft:lectern", "states": {}}
        ## [rot, top, variant, open_bit, data, hinge, tint]
        return self.processor._process_block(block, entity)[4]

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
        self.assertEqual(self.form(None), 0)


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

    def test_low_geometry_has_no_book_form_so_it_falls_back_to_the_plain_desk(self):
        ## a simplified family is one cube and one form, so a lectern built with
        ## low geometry on is drawn without its book and without anything here
        ## having to know that
        low = self.geo.block_shapes["lectern" + LOW_SUFFIX]

        self.assertEqual(list(low), ["default"])
        self.assertNotIn("book", low)


if __name__ == "__main__":
    unittest.main()
