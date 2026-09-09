import io
import os
import shutil
import tempfile
import unittest

from scaffold import lang_parse
from scaffold import paths
from scaffold import updates


class ChannelTests(unittest.TestCase):
    """Which releases a build is willing to be offered.

    tufup filters pre-releases out unless it is asked for a channel, so this is
    what decides whether somebody running a release candidate keeps being
    offered them or waits for the final.
    """

    def test_a_final_release_is_offered_only_final_releases(self):
        for running in ("3.0.0", "3.0.1", "10.2.3"):
            self.assertIsNone(updates.channel(running), running)

    def test_a_pre_release_is_offered_its_own_kind(self):
        self.assertEqual(updates.channel("3.1.0rc2"), "rc")
        self.assertEqual(updates.channel("3.1.0b1"), "b")
        self.assertEqual(updates.channel("3.1.0a4"), "a")

    def test_a_release_candidate_is_not_read_as_an_alpha(self):
        # "rc" contains neither an "a" nor a "b", but a naive search over the
        # whole version string finds the "a" in a date or a build tag
        self.assertEqual(updates.channel("3.1.0rc1"), "rc")


class SourceTests(unittest.TestCase):
    """A checkout has nothing to replace, and says so rather than trying."""

    def test_a_checkout_is_not_something_to_update(self):
        self.assertFalse(paths.frozen())
        self.assertIsNone(updates.running_file())
        self.assertFalse(updates.ready())
        self.assertIsNone(updates.available())

    def test_asking_to_install_from_a_checkout_is_answered_not_attempted(self):
        reason, detail = updates.install_latest()
        self.assertEqual(reason, "update source")
        self.assertEqual(detail, "")


class TrustTests(unittest.TestCase):
    """The root of trust, which is the one thing an update cannot fetch."""

    def test_the_root_is_looked_for_inside_the_package(self):
        # it ships compiled into the executable, so it has to resolve through
        # paths like every other piece of data
        wanted = os.path.join("scaffold", "trust", "root.json")
        self.assertTrue(updates.trusted_root().replace("\\", "/")
                        .endswith(wanted.replace("\\", "/")))

    def test_the_trust_directory_is_shipped(self):
        self.assertIn("trust", paths.DATA_DIRS)

    def test_without_a_root_there_is_nothing_to_check_against(self):
        # a build that shipped without root.json must refuse to update rather
        # than fetch one, because fetching it is exactly what it cannot do
        real = updates.trusted_root
        updates.trusted_root = lambda: os.path.join(tempfile.gettempdir(),
                                                    "no-such-root.json")
        try:
            self.assertFalse(updates.ready())
        finally:
            updates.trusted_root = real


class LeftoverTests(unittest.TestCase):
    """Tidying up after the updater this one replaced.

    Scaffold used to update by renaming the running file to `.old` and writing
    the new build where it stood. Nothing does that any more, but anyone coming
    from 3.0 or older arrives with one on disk.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.exe = os.path.join(self.folder, "Scaffold.exe")
        io.open(self.exe, "wb").write(b"MZ")
        self.real = updates.running_file
        updates.running_file = lambda: self.exe
        self.addCleanup(setattr, updates, "running_file", self.real)

    def test_a_displaced_build_is_taken_away(self):
        left = self.exe + updates.DISPLACED
        io.open(left, "wb").write(b"MZ")
        self.assertTrue(updates.clear_displaced())
        self.assertFalse(os.path.exists(left))

    def test_clearing_is_quiet_when_there_is_nothing_to_clear(self):
        self.assertTrue(updates.clear_displaced())

    def test_a_checkout_has_nothing_to_clear(self):
        updates.running_file = lambda: None
        self.assertTrue(updates.clear_displaced())


class ReasonTests(unittest.TestCase):
    """Every way this reports a failure has to be a string the window can show.

    `install_latest` returns the *name* of a string rather than the string, so
    the window can put it in the running language. A name the table does not
    carry reaches the screen as itself, and nothing else would notice.
    """

    ## every key updates.py can hand back, which is short enough to keep by hand
    ## and long enough that the test is worth having
    REASONS = ("update source", "update no release", "update current",
               "update download failed", "update wrong fingerprint",
               "update cannot place", "update stage checking",
               "update stage downloading")

    def test_every_reason_is_a_string_the_window_can_show(self):
        english = lang_parse.parse()["en_US"]
        missing = sorted(key for key in self.REASONS if key not in english)
        self.assertEqual(missing, [], "updates.py names strings nothing carries")

    def test_the_reasons_the_source_names_are_the_reasons_listed(self):
        # the list above is what the test above checks, so it has to be the
        # list the module actually uses
        import re

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        body = io.open(os.path.join(here, "scaffold", "updates.py"),
                       encoding="utf-8").read()
        named = set(re.findall(r'"(update [a-z ]+)"', body))
        self.assertEqual(named - set(self.REASONS), set(),
                         "updates.py names a string this test does not check")


if __name__ == "__main__":
    unittest.main()
