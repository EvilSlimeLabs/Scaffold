"""Installing a pack into Minecraft, and what a release says about itself.

Two things a bugfix release added: a finished pack can be copied straight into
Minecraft's own resource pack folder rather than imported by hand, and an
update says what it contains before anybody decides to take it.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build
from scaffold import core, paths, version


def a_pack(folder, name="P"):
    """The smallest thing install_pack will accept: a zip with a manifest."""
    made = os.path.join(folder, name + ".mcpack")
    with zipfile.ZipFile(made, "w") as archive:
        archive.writestr("manifest.json", json.dumps(
            {"header": {"uuid": "4afdfd22-e2b9-5cd2-a0e5-c14ccbdea9fc"}}))
        archive.writestr("pack_icon.png", b"not really a png")
    return made


class FolderTests(unittest.TestCase):
    """Where Minecraft's own folder is, and when it is not there at all."""

    def test_it_is_windows_only(self):
        # the path is an %APPDATA% one belonging to one of the several ways
        # Bedrock has been installed; nothing else has it
        if not sys.platform.startswith("win"):
            self.assertIsNone(paths.bedrock_packs())

    def test_a_folder_that_is_not_there_is_not_offered(self):
        was = os.environ.get("APPDATA")
        os.environ["APPDATA"] = tempfile.mkdtemp(prefix="no-minecraft-")
        try:
            self.assertIsNone(paths.bedrock_packs())
        finally:
            if was is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = was

    def test_it_is_found_when_it_is_there(self):
        if not sys.platform.startswith("win"):
            self.skipTest("the path is a Windows one")
        was = os.environ.get("APPDATA")
        base = tempfile.mkdtemp(prefix="fake-appdata-")
        os.makedirs(os.path.join(base, *paths.BEDROCK_PACKS))
        os.environ["APPDATA"] = base
        try:
            self.assertEqual(paths.bedrock_packs(),
                             os.path.join(base, *paths.BEDROCK_PACKS))
        finally:
            if was is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = was


class NameTests(unittest.TestCase):
    """The folder a pack installs as."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="install-name-")
        self.made = a_pack(self.work)

    def test_it_carries_the_version_and_the_pack_hash(self):
        name = core.install_name(self.made)
        self.assertTrue(name.startswith("Scaffoldv" + version.read()))
        self.assertIn("_", name)

    def test_it_is_a_name_any_filesystem_will_take(self):
        name = core.install_name(self.made)
        self.assertLess(len(name), 64)
        for ch in name:
            self.assertTrue(ch.isalnum() or ch in "._-",
                            "%r is not a safe folder character" % ch)

    def test_the_same_pack_installs_as_the_same_folder(self):
        again = a_pack(self.work, "Q")
        self.assertEqual(core.install_name(self.made), core.install_name(again))

    def test_a_different_pack_installs_as_a_different_folder(self):
        other = os.path.join(self.work, "R.mcpack")
        with zipfile.ZipFile(other, "w") as archive:
            archive.writestr("manifest.json", json.dumps(
                {"header": {"uuid": "11111111-2222-5333-a444-555555555555"}}))
        self.assertNotEqual(core.install_name(self.made),
                            core.install_name(other))


class InstallTests(unittest.TestCase):
    """Putting one there, and refusing to put one there twice."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="install-")
        self.made = a_pack(self.work)
        self.into = os.path.join(self.work, "resource_packs")
        os.makedirs(self.into)

    def test_a_pack_arrives_as_a_folder_with_its_manifest_in_it(self):
        where = core.install_pack(self.made, into=self.into)
        self.assertTrue(os.path.isdir(where))
        self.assertTrue(os.path.isfile(os.path.join(where, "manifest.json")))

    def test_installing_the_same_pack_again_is_refused(self):
        core.install_pack(self.made, into=self.into)
        with self.assertRaises(core.AlreadyInstalled) as caught:
            core.install_pack(self.made, into=self.into)
        ## and it says which folder, so the message can name it
        self.assertTrue(os.path.isdir(caught.exception.folder))

    def test_a_refusal_leaves_what_was_there_alone(self):
        where = core.install_pack(self.made, into=self.into)
        io.open(os.path.join(where, "mine.txt"), "w").write("do not lose me")
        try:
            core.install_pack(self.made, into=self.into)
        except core.AlreadyInstalled:
            pass
        self.assertTrue(os.path.isfile(os.path.join(where, "mine.txt")))

    def test_nothing_half_written_is_left_behind(self):
        core.install_pack(self.made, into=self.into)
        leftovers = [n for n in os.listdir(self.into) if n.endswith(".part")]
        self.assertEqual(leftovers, [])

    def test_it_says_so_when_minecraft_is_not_on_this_machine(self):
        with self.assertRaises(OSError):
            core.install_pack(self.made, into=None if not paths.bedrock_packs()
                              else "")


class ReleaseNotesTests(unittest.TestCase):
    """What the update dialog is given to show."""

    def notes(self, text, wanted):
        handle, path = tempfile.mkstemp(suffix=".md")
        os.close(handle)
        io.open(path, "w", encoding="utf-8").write(text)
        try:
            return build.release_notes(wanted, path=path)
        finally:
            os.remove(path)

    def test_the_section_for_this_version_is_read(self):
        found = self.notes("# Changelog\n\n## 1.2.0\nold news\n\n"
                           "## 1.1.0\nwhat this one did\n", "1.1.0")
        self.assertEqual(found, "what this one did")

    def test_it_stops_at_the_next_heading(self):
        found = self.notes("## 2.0.0\nmine\n\n## 1.0.0\nnot mine\n", "2.0.0")
        self.assertEqual(found, "mine")

    def test_a_date_after_the_version_is_allowed(self):
        self.assertEqual(self.notes("## 1.0.0 - 2026-01-01\nnote\n", "1.0.0"),
                         "note")

    def test_a_v_before_the_version_is_allowed(self):
        self.assertEqual(self.notes("## v1.0.0\nnote\n", "1.0.0"), "note")

    def test_a_version_with_no_section_says_nothing(self):
        self.assertEqual(self.notes("## 1.0.0\nnote\n", "9.9.9"), "")

    def test_a_missing_file_says_nothing(self):
        self.assertEqual(build.release_notes("1.0.0", path="nowhere.md"), "")

    def test_a_longer_note_than_a_dialog_holds_is_cut(self):
        found = self.notes("## 1.0.0\n" + ("word " * 400), "1.0.0")
        self.assertLessEqual(len(found), build.NOTES_LIMIT + 3)
        self.assertTrue(found.endswith("..."))

    def test_one_version_is_not_mistaken_for_another(self):
        # 1.1.1 must not match the 1.1.10 heading, or a release would show
        # somebody else's notes
        found = self.notes("## 1.1.10\nten\n\n## 1.1.1\none\n", "1.1.1")
        self.assertEqual(found, "one")

    def test_the_shipped_changelog_names_this_version(self):
        # a release whose notes nobody wrote offers a blank dialog
        self.assertTrue(build.release_notes(version.read()),
                        "CHANGELOG.md has no section for %s" % version.read())


if __name__ == "__main__":
    unittest.main()
