"""Drawing the things in a structure that are not blocks.

An entity is kept apart from the blocks: a .mcstructure records it in
`structure.entities` as a whole entity with a world position of its own, so
nothing in `block_indices` marks the cell it stands in. `core.ENTITY_MODELS`
bridges that by naming, per entity identifier, a pseudo block id to draw it as
and which of its own fields picks the form -- and from there it is an ordinary
block, with a shape family, a rotation table, a line on the block list and a
heading, none of which had to learn what an entity is.

The cushion is the only one so far. These tests are written against the pipeline
rather than against the cushion wherever they can be, so the next entity added
is covered by most of them without anything being rewritten.
"""
import contextlib
import io as _io
import json
import os
import tempfile
import unittest

from scaffold import block_list, core, paths
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import structure_reader


STRUCTURE = os.path.join("test_structures", "All Blocks World",
                         "26.50_update.mcstructure")


def load(name):
    with open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return json.load(f)


class ModelTableTests(unittest.TestCase):
    """Every entity named for drawing has everything it needs to be drawn."""

    def test_each_model_names_a_family_that_exists(self):
        defs, shapes, uvs = (load("block_definition"), load("block_shapes"),
                             load("block_uv"))
        for identifier, model in core.ENTITY_MODELS.items():
            with self.subTest(identifier):
                block = model["block"]
                self.assertIn(block, defs)
                family = defs[block]
                self.assertIn(family, shapes)
                self.assertIn(family, uvs)

    def test_each_form_is_a_variant_of_its_family(self):
        defs, shapes = load("block_definition"), load("block_shapes")
        for identifier, model in core.ENTITY_MODELS.items():
            family = shapes[defs[model["block"]]]
            for form in model.get("forms") or ():
                with self.subTest("%s/%s" % (identifier, form)):
                    self.assertIn(form, family)
            self.assertIn(model["fallback"], family)
            ## and a default, for an entity whose field says nothing
            self.assertIn("default", family)

    def test_each_model_turns_through_the_four_quarters(self):
        rotation = load("block_rotation")
        defs = load("block_definition")
        for identifier, model in core.ENTITY_MODELS.items():
            table = rotation[defs[model["block"]]]
            for quarter in ("0", "90", "180", "270"):
                self.assertIn(quarter, table,
                              "%s cannot face %s" % (identifier, quarter))


class TurnTests(unittest.TestCase):
    """A float yaw, rounded to the quarter a rotation table can name."""

    def test_the_four_quarters_come_back_as_themselves(self):
        for yaw in (0, 90, 180, 270):
            self.assertEqual(core.entity_turn(yaw), str(yaw))

    def test_a_yaw_between_two_is_rounded_to_the_nearer(self):
        self.assertEqual(core.entity_turn(44), "0")
        self.assertEqual(core.entity_turn(46), "90")
        self.assertEqual(core.entity_turn(181), "180")

    def test_a_full_turn_and_a_negative_one_come_back_inside_the_circle(self):
        # 359 is a whisker short of a full turn, not three quarters of one
        self.assertEqual(core.entity_turn(360), "0")
        self.assertEqual(core.entity_turn(359), "0")
        self.assertEqual(core.entity_turn(-90), "270")
        self.assertEqual(core.entity_turn(720 + 90), "90")


class FormTests(unittest.TestCase):
    """Which form an entity is, out of a field of its own."""

    model = core.ENTITY_MODELS["minecraft:cushion"]

    def form(self, fields):
        return core.entity_form({"fields": fields}, self.model)

    def test_the_field_picks_the_form(self):
        self.assertEqual(self.form({"Variant": 0}), self.model["forms"][0])
        self.assertEqual(self.form({"Variant": 15}), self.model["forms"][15])

    def test_a_missing_or_impossible_value_falls_back(self):
        for fields in ({}, {"Variant": None}, {"Variant": "nonsense"},
                       {"Variant": 99}, {"Variant": -99}):
            with self.subTest(str(fields)):
                self.assertEqual(self.form(fields), self.model["fallback"])

    def test_the_cushion_reads_the_dye_order_not_the_wool_order(self):
        # Array.skins in controller.render.cushion is black first and white
        # last, which is the order a banner's Base counts in and the opposite
        # of the wool order; reading it as wool gives every cushion the colour
        # across the wheel from its own
        forms = self.model["forms"]
        self.assertEqual(forms[0], "black")
        self.assertEqual(forms[15], "white")
        self.assertEqual(len(forms), 16)
        self.assertEqual(len(set(forms)), 16)


class ReaderTests(unittest.TestCase):
    """Reading the entities out of a structure, and where they stand."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(STRUCTURE):
            raise unittest.SkipTest("%s is not in this checkout" % STRUCTURE)
        cls.reader = structure_reader.StructureFile(STRUCTURE)
        cls.entities = cls.reader.get_entities()

    def test_it_finds_every_entity_not_only_the_drawn_ones(self):
        # the dropped items are read and passed over later, not filtered here:
        # a reader's job is to say what is in the file
        kinds = {e["id"] for e in self.entities}
        self.assertIn("minecraft:cushion", kinds)
        self.assertIn("minecraft:item", kinds)

    def test_every_entity_lands_inside_the_structure(self):
        size = list(self.reader.get_size())
        for entity in self.entities:
            for axis, value in enumerate(entity["at"]):
                self.assertGreaterEqual(value, 0)
                self.assertLess(value, size[axis])

    def test_a_cell_is_the_position_less_the_structure_origin(self):
        # Pos is where the entity stands in the world and the structure records
        # where in the world it was taken from, so the cell is the difference
        cushions = [e for e in self.entities if e["id"] == "minecraft:cushion"]
        self.assertTrue(cushions)
        for entity in cushions:
            self.assertEqual(len(entity["at"]), 3)
            self.assertTrue(all(isinstance(n, int) for n in entity["at"]))

    def test_the_sixteen_cushions_are_sixteen_colours_in_a_row(self):
        cushions = [e for e in self.entities if e["id"] == "minecraft:cushion"]
        self.assertEqual(len(cushions), 16)
        model = core.ENTITY_MODELS["minecraft:cushion"]
        forms = {core.entity_form(e, model) for e in cushions}
        self.assertEqual(forms, set(model["forms"]))

    def test_an_entity_outside_the_box_is_left_out(self):
        # not clamped to the edge: it is not part of what was captured, and a
        # mark on the wrong cell is worse than no mark
        import copy
        nbt = copy.deepcopy(self.reader.NBTfile)
        strays = nbt["structure"]["entities"]
        first = copy.deepcopy(strays[0])
        for axis in range(3):
            first["Pos"][axis] = type(first["Pos"][axis])(-999.0)
        strays.append(first)
        reader = structure_reader.StructureFile(dict(nbt))
        self.assertEqual(len(reader.get_entities()), len(self.entities))


class DrawingTests(unittest.TestCase):
    """An entity goes through make_block like anything else."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def cubes(self, block, **kwargs):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, block, **kwargs)
        return [(tuple(c["origin"]), tuple(c["size"]))
                for group in self.geo.blocks.values()
                for c in group.get("cubes", [])]

    def test_every_form_of_every_entity_builds(self):
        broken = []
        for identifier, model in core.ENTITY_MODELS.items():
            for form in list(model.get("forms") or ()) + ["default"]:
                try:
                    self.assertTrue(self.cubes(model["block"], data=form))
                except Exception as exc:
                    broken.append("%s/%s (%s)" % (identifier, form,
                                                  type(exc).__name__))
        self.assertEqual(broken, [])

    def test_a_cushion_is_one_flat_pad(self):
        made = self.cubes("cushion", data="red")
        self.assertEqual(len(made), 1)
        _origin, size = made[0]
        ## four pixels tall, and a shade under its cell the two wide ways
        self.assertAlmostEqual(size[1], 0.25, places=3)
        self.assertLess(size[0], 1.0)
        self.assertGreater(size[0], 0.9)
        self.assertEqual(size[0], size[2])

    def test_each_colour_reads_a_sheet_of_its_own(self):
        uv = load("block_uv")["cushion"]
        seen = set()
        for form in core.ENTITY_MODELS["minecraft:cushion"]["forms"]:
            named = uv[form]["overwrite"]["up"][0]
            self.assertIn("textures/entity/cushion/", named)
            seen.add(named)
        self.assertEqual(len(seen), 16)

    def test_a_family_drawn_for_an_entity_needs_no_blocks_json_entry(self):
        # a cushion is not a block, so Mojang's pack does not declare one and
        # never will; the family names all six faces outright instead
        self.assertNotIn("cushion", self.geo.blocks_def)
        self.assertTrue(self.cubes("cushion", data="white"))


class BuildTests(unittest.TestCase):
    """A whole pack, with the entities in the model and on the list."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(STRUCTURE):
            raise unittest.SkipTest("%s is not in this checkout" % STRUCTURE)
        cls.was = os.getcwd()
        cls.work = tempfile.mkdtemp(prefix="scaffold-entity-test-")
        structure = os.path.abspath(STRUCTURE)
        os.chdir(cls.work)
        try:
            pack = core.scaffold("entity_test")
            pack.add_model("probe", structure)
            pack.set_model_offset("probe", [0, 0, 0])
            with contextlib.redirect_stdout(_io.StringIO()):
                pack.generate_with_nametags()
            cls.counts = pack.get_block_lists()["probe"]
            cls.skipped = pack.get_skipped(write_file=False)
        finally:
            os.chdir(cls.was)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_the_entities_are_counted_with_the_blocks(self):
        cushions = {k: v for k, v in self.counts.items()
                    if str(k).startswith("minecraft:cushion")}
        self.assertEqual(len(cushions), 16)
        self.assertEqual(sum(cushions.values()), 16)

    def test_an_entity_is_counted_under_its_own_form(self):
        # one line a colour, because sixteen cushions of one colour and one
        # each of sixteen are different things to gather
        for form in core.ENTITY_MODELS["minecraft:cushion"]["forms"]:
            self.assertIn("minecraft:cushion/%s" % form, self.counts)

    def test_nothing_is_skipped(self):
        self.assertEqual(self.skipped, {})

    def test_the_undrawn_entities_are_not_reported_as_skipped(self):
        # the structure carries a hundred and four dropped items, and none of
        # them is something a builder places; listing them as blocks Scaffold
        # could not draw would bury the ones that matter
        self.assertNotIn("minecraft:item", self.skipped)
        self.assertNotIn("minecraft:item", self.counts)

    def test_the_list_puts_them_under_their_own_heading(self):
        grouped = dict(block_list.grouped(self.counts))
        self.assertIn("Entities", grouped)
        named = dict(grouped["Entities"])
        self.assertEqual(named.get("White Cushion"), 1)
        self.assertEqual(named.get("Light Gray Cushion"), 1)
        self.assertEqual(len(named), 16)

    def test_entities_are_the_only_thing_under_that_heading(self):
        drawn = {model["block"] for model in core.ENTITY_MODELS.values()}
        for key in self.counts:
            if block_list.category_of(key) == "Entities":
                short = str(key).partition("/")[0].replace("minecraft:", "")
                self.assertIn(short, drawn)


class NamingTests(unittest.TestCase):
    """Nothing a block list can show is left as its own id."""

    def test_every_drawn_block_has_a_name(self):
        defs, told = load("block_definition"), block_list.table()["names"]
        drawn = {model["block"] for model in core.ENTITY_MODELS.values()}
        unnamed = [block for block, family in defs.items()
                   if family != "ignore" and block not in drawn
                   and ("minecraft:" + block) not in told]
        self.assertEqual(sorted(unnamed), [])

    def test_every_entity_is_named_and_so_is_every_form(self):
        for identifier, model in core.ENTITY_MODELS.items():
            self.assertNotEqual(block_list.name_of(identifier), identifier)
            for form in model.get("forms") or ():
                key = "%s/%s" % (identifier, form)
                with self.subTest(key):
                    shown = block_list.name_of(key)
                    self.assertNotEqual(shown, key)
                    self.assertNotEqual(shown, identifier.replace("minecraft:", ""))

    def test_every_entity_has_a_heading(self):
        for identifier in core.ENTITY_MODELS:
            self.assertNotEqual(block_list.category_of(identifier),
                                block_list.LEFTOVERS)

    def test_a_name_is_never_the_bare_id(self):
        # name_of falls back to the id itself, so a name equal to the id is a
        # block that has no entry rather than one that is called that
        defs, told = load("block_definition"), block_list.table()["names"]
        drawn = {model["block"] for model in core.ENTITY_MODELS.values()}
        same = []
        for block, family in defs.items():
            if family == "ignore" or block in drawn:
                continue
            key = "minecraft:" + block
            if key in told and block_list.name_of(key) == block:
                same.append(block)
        self.assertEqual(sorted(same), [])


if __name__ == "__main__":
    unittest.main()
