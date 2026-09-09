import json
import unittest

from scaffold import paths
from scaffold import version
from scaffold.pack import manifest
class DisplayNameTests(unittest.TestCase):
    """Every pack this program builds groups together in the player's list."""

    def test_the_name_carries_the_prefix(self):
        self.assertEqual(manifest.display_name("Sorter"), "Scaffold: Sorter")

    def test_prefixing_twice_does_not_stack(self):
        once = manifest.display_name("Sorter")
        self.assertEqual(manifest.display_name(once), once)

    def test_the_derived_uuid_ignores_the_prefix(self):
        # the prefix is presentation, so it stays out of the UUID: folding it
        # in makes a pack built by a Scaffold without the prefix look like a
        # different pack to the game.
        self.assertEqual(manifest.derived_pack_uuids("Sorter"),
                         manifest.derived_pack_uuids("Sorter"))
        self.assertNotEqual(manifest.derived_pack_uuids("Sorter"),
                            manifest.derived_pack_uuids("Scaffold: Sorter"))


class PackIdentityTests(unittest.TestCase):
    """A pack is identified by everything that went into it.

    Deriving the UUID from the content means an unchanged rebuild really is the
    same pack and any change is a different one. The name alone cannot carry
    that: two builds of a changed pack would share a UUID, and share a version
    as well, because the version is the Scaffold version.
    """

    SAMPLE = "name=Sorter|opacity=0.35|model=a1b2"

    def test_the_same_content_gives_the_same_uuid(self):
        self.assertEqual(manifest.pack_uuids("Sorter", self.SAMPLE),
                         manifest.pack_uuids("Sorter", self.SAMPLE))

    def test_any_change_to_the_content_moves_it(self):
        base = manifest.pack_uuids("Sorter", self.SAMPLE)
        for changed in ("name=Sorter|opacity=0.50|model=a1b2",
                        "name=Sorter|opacity=0.35|model=c3d4",
                        "name=Other|opacity=0.35|model=a1b2",
                        self.SAMPLE + "|techpack=0.2.22"):
            with self.subTest(changed=changed):
                self.assertNotEqual(base, manifest.pack_uuids("Sorter", changed))

    def test_the_name_alone_does_not_decide_it(self):
        self.assertNotEqual(manifest.pack_uuids("Sorter", "content one"),
                            manifest.pack_uuids("Sorter", "content two"))

    def test_the_header_and_module_uuids_differ_from_each_other(self):
        header, module = manifest.pack_uuids("Sorter", "anything")
        self.assertNotEqual(header, module)


class DescriptionTests(unittest.TestCase):
    """The description is one field, so its parts are separated by newlines."""

    def test_the_credits_are_always_last(self):
        text = manifest.build_description()
        self.assertEqual(text.count("\n"), 0)
        self.assertTrue(text.startswith("Scaffold %s" % version.read()))

    def test_every_part_appears_in_order(self):
        text = manifest.build_description(("north", "south"), "floor 3", "0.2.22")
        lines = text.split("\n")
        self.assertEqual(lines[0], "floor 3")
        self.assertEqual(lines[1], "Nametags: north, south")
        self.assertEqual(lines[2], "TechPack 0.2.22 included")
        self.assertTrue(lines[3].startswith("Scaffold "))

    def test_the_techpack_line_is_absent_when_it_is_not_bundled(self):
        text = manifest.build_description(("north",), "note", None)
        self.assertNotIn("TechPack", text)

    def test_a_long_note_is_trimmed_rather_than_refused(self):
        text = manifest.build_description(user_text="x" * 200)
        self.assertEqual(text.split("\n")[0], "x" * manifest.DESCRIPTION_LIMIT)

    def test_the_maintainer_is_slime_green_and_the_others_keep_their_colours(self):
        line = manifest.credits_line()
        self.assertIn(manifest.GREEN + "EvilSlimeLabs", line)
        self.assertIn(manifest.ITALIC_PURPLE + "DrAv0011", line)
        self.assertIn(manifest.ITALIC_BLUE + "FondUnicycle", line)
        self.assertIn(manifest.ITALIC_PURPLE + "RavinMaddHatter", line)


class ManifestFileTests(unittest.TestCase):
    def test_the_written_manifest_is_utf8_and_keeps_the_colour_codes(self):
        import tempfile
        import os
        work = tempfile.mkdtemp(prefix="scaffold-test-")
        try:
            manifest.export(work, "Sorter", nameTags=("a",), user_text="note")
            with open(os.path.join(work, "manifest.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["header"]["name"], "Scaffold: Sorter")
            self.assertIn("§a", data["header"]["description"])
            self.assertEqual(data["format_version"], 2)
            self.assertEqual(len(data["modules"]), 1)
            self.assertEqual(data["modules"][0]["type"], "resources")
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)




class FingerprintTests(unittest.TestCase):
    """What the pack's identity is actually built from."""

    def make(self, **kw):
        from scaffold import core
        pack = core.scaffold.__new__(core.scaffold)
        pack.display_name = kw.get("name", "Sorter")
        pack.description = kw.get("description", "")
        pack.opacity = kw.get("opacity", 0.35)
        pack.icon = kw.get("icon", paths.lookup("pack_icon.png"))
        pack.tech_pack = kw.get("tech_pack", False)
        pack.low_geometry = kw.get("low_geometry", False)
        pack.big_offset = kw.get("big_offset", None)
        pack.structure_files = kw.get("models", {
            "": {"file": "test_structures/stoneSlabs.mcstructure",
                 "offsets": [0, 0, 0]}})
        return pack.fingerprint()

    def test_the_same_inputs_give_the_same_fingerprint(self):
        self.assertEqual(self.make(), self.make())

    def test_every_setting_that_changes_the_pack_changes_it(self):
        base = self.make()
        for change in ({"name": "Other"}, {"description": "note"},
                       {"opacity": 0.5}, {"tech_pack": True},
                       # the same structures drawn with simpler shapes are a
                       # different pack, and must not replace the detailed one
                       # already in the player's list
                       {"low_geometry": True},
                       {"big_offset": [1, 2, 3]},
                       {"models": {"": {"file": "test_structures/rails.mcstructure",
                                        "offsets": [0, 0, 0]}}},
                       {"models": {"": {"file": "test_structures/stoneSlabs.mcstructure",
                                        "offsets": [1, 0, 0]}}}):
            with self.subTest(change=str(change)):
                self.assertNotEqual(base, self.make(**change))

    def test_a_missing_file_does_not_raise(self):
        self.assertIn("absent", self.make(icon="nowhere/at/all.png"))


class VersionTests(unittest.TestCase):
    """pyproject.toml is the only place a version is written down."""

    def project(self):
        import os
        import tomllib
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "pyproject.toml"), "rb") as handle:
            return tomllib.load(handle)

    def test_the_version_comes_from_pyproject(self):
        self.assertEqual(version.read(), self.project()["project"]["version"])

    def test_the_package_exposes_it_the_usual_way(self):
        import scaffold
        self.assertEqual(scaffold.__version__, version.read())

    def test_it_is_written_down_exactly_once(self):
        # a second copy is one that can disagree; version.read() is the only
        # way anything should learn it
        import os
        import re
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        wanted = re.compile(r"^%s$" % re.escape(version.read()))
        found = []
        for base, dirs, names in os.walk(os.path.join(here, "scaffold")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as handle:
                    for line in handle:
                        for literal in re.findall(r'"([^"]*)"|\'([^\']*)\'', line):
                            text = literal[0] or literal[1]
                            if wanted.match(text):
                                found.append("%s: %s" % (name, line.strip()))
        self.assertEqual(found, [], "the version is hardcoded somewhere")

    def test_a_prerelease_suffix_cannot_break_a_manifest(self):
        # a Bedrock manifest wants three integers and nothing else
        self.assertEqual(len(version.as_tuple()), 3)
        for part in version.as_tuple():
            self.assertIsInstance(part, int)


if __name__ == "__main__":
    unittest.main()
