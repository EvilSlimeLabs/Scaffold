"""The geometry tables are format 2, and say what their schemas say they say."""
import io
import json
import os
import unittest

from scaffold import block_geometry, paths
from scaffold import lookup

SCHEMAS = os.path.join(os.path.dirname(paths.lookup(block_geometry.GEOMETRY)), "schema")

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:          # the dev extra brings it
    jsonschema = None


def read(name):
    with io.open(paths.lookup(name), encoding="utf-8") as f:
        return json.load(f)


@unittest.skipIf(jsonschema is None, "jsonschema is not installed; pip install -e .[dev]")
class SchemaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        schemas = {}
        for name in os.listdir(SCHEMAS):
            with io.open(os.path.join(SCHEMAS, name), encoding="utf-8") as f:
                schemas[name] = json.load(f)
        cls.schemas = schemas
        cls.registry = Registry().with_resources(
            (name, Resource.from_contents(body)) for name, body in schemas.items())

    def check(self, table, schema):
        validator = jsonschema.Draft202012Validator(
            self.schemas[schema], registry=self.registry)
        problems = sorted(validator.iter_errors(read(table)),
                          key=lambda e: list(e.absolute_path))
        self.assertEqual(
            [], ["%s: %s" % ("/".join(map(str, e.absolute_path)), e.message)
                 for e in problems[:10]])

    def test_the_geometry_is_what_its_schema_describes(self):
        self.check(block_geometry.GEOMETRY, "block_geometry.schema.json")

    def test_the_state_turns_are_what_their_schema_describes(self):
        self.check(block_geometry.STATES, "state_rotations.schema.json")

    def test_the_rotation_table_is_what_its_schema_describes(self):
        self.check(block_geometry.ROTATION, "block_rotation.schema.json")


class FormatTests(unittest.TestCase):

    def test_every_table_is_format_2_and_says_which_minecraft(self):
        for name in (block_geometry.GEOMETRY, block_geometry.STATES,
                     block_geometry.ROTATION):
            body = read(name)
            self.assertEqual(body["format"], 2, name)
            self.assertTrue(body["minecraft"], name)

    def test_a_family_turned_by_a_state_names_one_there_is(self):
        states = read(block_geometry.STATES)["states"]
        for family, turns in read(block_geometry.ROTATION)["families"].items():
            if isinstance(turns, str):
                self.assertIn(turns, states, family)

    def test_every_block_points_at_a_family_there_is(self):
        families = read(block_geometry.GEOMETRY)["families"]
        with io.open(paths.lookup("block_definition.json"), encoding="utf-8") as f:
            for block, family in lookup.unwrap("block_definition.json", json.load(f)).items():
                if family != "ignore":
                    self.assertIn(family, families, block)

    def test_every_family_has_a_default_and_its_simpler_forms_match(self):
        for family, entry in read(block_geometry.GEOMETRY)["families"].items():
            self.assertIn("default", entry["forms"], family)
            for form in entry.get("low", {}):
                self.assertIn(form, entry["forms"], "%s low %s" % (family, form))

    def test_a_texture_round_trips_through_the_marks_the_builder_reads(self):
        for written in ("default", "@north", "@north#0,12", "@up^90",
                        "textures/blocks/bell_side#0,7^180",
                        "textures/blocks/water_still_grey~tint"):
            self.assertEqual(block_geometry.texture_marks(
                block_geometry.texture_object(written)), written)



class HeaderTests(unittest.TestCase):
    """Every table opens with the same header, in the same order."""

    def tables(self):
        folder = os.path.dirname(paths.lookup("block_definition.json"))
        for name in sorted(os.listdir(folder)):
            ## a Bedrock model kept beside the tables is Bedrock's own format
            if name.endswith(".json") and not name.endswith(".geo.json"):
                yield name, lookup.read(name)

    def test_every_table_opens_with_the_header(self):
        for name, document in self.tables():
            with self.subTest(table=name):
                self.assertEqual(document.get("format"), lookup.FORMAT)
                self.assertTrue(document.get("about"))
                keys = [k for k in document if k in lookup.HEADER]
                self.assertEqual(keys, [k for k in lookup.HEADER if k in document])
                self.assertEqual(list(document)[:len(keys)], keys)

    def test_a_one_key_table_holds_its_entries_under_its_key(self):
        for name, key in lookup.ENTRIES.items():
            with self.subTest(table=name):
                self.assertIn(key, lookup.read(name))
                self.assertIsInstance(lookup.entries(name), dict)

    def test_every_table_names_the_game_version_the_sources_are_from(self):
        ## a table that names a Minecraft version names the one the game's own
        ## files in the submodule are from; when the submodule moves to a new
        ## release, this fails until the tables are checked against it and
        ## their version moved with it
        from tools import sources
        current = sources.game_version()
        if current is None:
            self.skipTest("the game's version file is not checked out")
        for name, document in self.tables():
            if "minecraft" in document:
                with self.subTest(table=name):
                    self.assertEqual(document["minecraft"], current,
                                     "%s is checked against %s; the game's files are %s"
                                     % (name, document["minecraft"], current))
        ## and the version a table written from scratch is given
        self.assertEqual(lookup.MINECRAFT, current)

    def test_a_table_written_before_the_header_is_read_as_it_is(self):
        flat = {"stone": "cube", "dirt": "cube"}
        self.assertEqual(lookup.unwrap("block_definition.json", flat), flat)


if __name__ == "__main__":
    unittest.main()
