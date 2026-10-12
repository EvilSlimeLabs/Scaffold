"""The command line's --settings file: what it fills in, and what wins."""
import json
import os
import shutil
import tempfile
import unittest

from scaffold.cli import arguments


class SettingsFileTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def written(self, body):
        path = os.path.join(self.folder, "build.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return path

    def test_the_file_fills_in_what_the_command_line_leaves_out(self):
        path = self.written({"structure": "house.mcstructure", "pack_name": "House",
                             "opacity": 40, "offset": [1, 2, 3], "low_geometry": True,
                             "tweaks": ["ore_borders", "container_fill"],
                             "tech_pack": "compatibility"})
        args = arguments.parse(["--settings", path])
        self.assertEqual(args.structure, os.path.join(self.folder, "house.mcstructure"))
        self.assertEqual(args.pack_name, "House")
        self.assertEqual(args.opacity, 40)
        self.assertEqual(args.offset, "1,2,3")
        self.assertTrue(args.low_geometry)
        self.assertEqual(args.tweaks, ["ore_borders", "container_fill"])
        self.assertEqual(args.tech_pack, "compatibility")

    def test_the_command_line_wins(self):
        path = self.written({"structure": "a.mcstructure", "pack_name": "A",
                             "opacity": 40, "tech_pack": "full"})
        args = arguments.parse(["--settings", path, "--opacity", "70",
                                "--tech_pack=none"])
        self.assertEqual(args.opacity, 70)
        self.assertEqual(args.tech_pack, "none")

    def test_the_windows_own_file_is_read(self):
        path = self.written({"lang": "es_ES", "theme": "dark", "transparency": 65,
                             "output_dir": "out", "tweaks": True,
                             "tweaks_on": ["lever"], "low_geometry": False,
                             "check_updates": True, "tech_pack": "none"})
        args = arguments.parse(["--settings", path, "--structure", "s.mcstructure",
                                "--pack_name", "S"])
        self.assertEqual(args.opacity, 35)
        self.assertEqual(args.output, os.path.join(self.folder, "out"))
        self.assertEqual(args.tweaks, ["lever"])

    def test_a_window_file_with_tweaks_switched_off_applies_none(self):
        path = self.written({"tweaks": False, "tweaks_on": ["lever"]})
        args = arguments.parse(["--settings", path, "--structure", "s", "--pack_name", "S"])
        self.assertIsNone(args.tweaks)

    def test_a_key_nothing_reads_is_an_error(self):
        path = self.written({"opactiy": 40})
        with self.assertRaises(SystemExit):
            arguments.parse(["--settings", path])


class VersionTests(unittest.TestCase):
    """`--version` prints the version pyproject.toml declares and stops."""

    def test_prints_the_version(self):
        import contextlib
        import io as text
        from scaffold import version
        out = text.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
            arguments.parse(["--version"])
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "Scaffold %s" % version.read())


if __name__ == "__main__":
    unittest.main()
