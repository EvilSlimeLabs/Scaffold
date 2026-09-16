"""Taking a release back off the update server.

`python build.py --unpublish VERSION` is the one command whose whole purpose is
to make a release stop existing for everybody who has not taken it yet, so what
matters is the refusals: it names the version rather than assuming it, it builds
nothing, and it stops before touching anything when the answer is no.

The signing half is tufup's and is not re-tested here. What is tested is the
reading and the guarding around it, which is where a mistake would be ours.
"""
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build


def targets_file(where, versions):
    """A targets.json naming these versions, and the patches beside them."""
    signed = {}
    for index, version in enumerate(versions):
        signed["Scaffold-%s.tar.gz" % version] = {"length": 1}
        if index:
            signed["Scaffold-%s.patch" % version] = {"length": 1}
    os.makedirs(os.path.join(where, "metadata"), exist_ok=True)
    with io.open(os.path.join(where, "metadata", "targets.json"), "w",
                 encoding="utf-8") as handle:
        json.dump({"signed": {"targets": signed}}, handle)


class ReadingTests(unittest.TestCase):
    """What the update repository is currently offering."""

    def setUp(self):
        self.was = build.PAGES_DIR
        self.work = tempfile.mkdtemp(prefix="scaffold-unpublish-")
        build.PAGES_DIR = self.work

    def tearDown(self):
        import shutil
        build.PAGES_DIR = self.was
        shutil.rmtree(self.work, ignore_errors=True)

    def test_nothing_published_reads_as_nothing(self):
        self.assertEqual(build.published_versions(), [])

    def test_the_archives_are_read_and_the_patches_are_not(self):
        # a patch is not a release in its own right: it is how one release
        # reaches the next, and listing it would offer a version twice
        targets_file(self.work, ["1.0.0", "1.1.0"])
        self.assertEqual(build.published_versions(), ["1.0.0", "1.1.0"])

    def test_versions_sort_as_numbers_not_as_text(self):
        # 1.10.0 is above 1.9.0; sorted as text it is below, and --unpublish
        # would then name the wrong release as the newest
        targets_file(self.work, ["1.9.0", "1.10.0", "1.2.0"])
        self.assertEqual(build.published_versions(),
                         ["1.2.0", "1.9.0", "1.10.0"])

    def test_a_pre_release_sorts_under_the_release_it_leads_to(self):
        targets_file(self.work, ["1.0.0", "1.1.0-rc1", "1.1.0"])
        self.assertEqual(build.published_versions()[-1], "1.1.0")

    def test_already_published_agrees_with_the_listing(self):
        targets_file(self.work, ["1.0.0", "1.1.0"])
        for version in build.published_versions():
            self.assertTrue(build.already_published(version))
        self.assertFalse(build.already_published("9.9.9"))


class RefusalTests(unittest.TestCase):
    """An unpublish that should not happen stops before anything moves."""

    def setUp(self):
        self.was_pages, self.was_keys = build.PAGES_DIR, build.KEYS_DIR
        self.work = tempfile.mkdtemp(prefix="scaffold-unpublish-")
        build.PAGES_DIR = os.path.join(self.work, "pages")
        build.KEYS_DIR = os.path.join(self.work, "keys")
        os.makedirs(build.PAGES_DIR)
        os.makedirs(build.KEYS_DIR)
        ## enough of a worktree and enough of a key store to get past the two
        ## checks that come before the interesting one
        io.open(os.path.join(build.PAGES_DIR, ".git"), "w").write("gitdir: x")
        io.open(os.path.join(build.KEYS_DIR, "root"), "w").write("x")

    def tearDown(self):
        import shutil
        build.PAGES_DIR, build.KEYS_DIR = self.was_pages, self.was_keys
        shutil.rmtree(self.work, ignore_errors=True)

    def refused(self, version):
        with self.assertRaises(SystemExit) as caught:
            build.ready_to_unpublish(version)
        return str(caught.exception)

    def test_nothing_published_is_refused(self):
        self.assertIn("nothing is published", self.refused("1.0.0"))

    def test_a_version_that_was_never_published_is_refused(self):
        targets_file(build.PAGES_DIR, ["1.0.0", "1.1.0"])
        said = self.refused("9.9.9")
        self.assertIn("9.9.9 is not published", said)
        ## and it says what is, so the next command is obvious
        self.assertIn("1.0.0, 1.1.0", said)

    def test_a_version_under_a_newer_one_is_refused(self):
        # tufup removes the latest bundle and only the latest, and a client
        # holding a patch against a removed archive cannot step forward
        targets_file(build.PAGES_DIR, ["1.0.0", "1.1.0"])
        said = self.refused("1.0.0")
        self.assertIn("1.1.0 is newer", said)
        self.assertIn("only the latest", said)

    def test_missing_keys_are_refused_before_anything_is_read(self):
        targets_file(build.PAGES_DIR, ["1.0.0"])
        os.remove(os.path.join(build.KEYS_DIR, "root"))
        self.assertIn("no signing keys", self.refused("1.0.0"))

    def test_a_pages_tree_that_is_not_a_worktree_is_refused(self):
        targets_file(build.PAGES_DIR, ["1.0.0"])
        os.remove(os.path.join(build.PAGES_DIR, ".git"))
        self.assertIn("not the gh-pages worktree", self.refused("1.0.0"))


class FlagTests(unittest.TestCase):
    """The flag itself: it takes a version, and it builds nothing."""

    def test_unpublish_takes_a_version_rather_than_assuming_one(self):
        # naming the release is the confirmation: this is the one command that
        # makes something stop existing for everybody who has not taken it
        source = io.open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
        self.assertIn('"--unpublish", metavar="VERSION"', source)

    def test_unpublish_returns_before_the_build(self):
        # it compiles nothing, so it has to leave main() before run_tools,
        # run_tests and freeze, the way --init-trust and --init-pages do
        source = io.open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
        body = source[source.index("def main("):]
        early = body.index("return unpublish(")
        for later in ("run_tools()", "run_tests()", "freeze(release_version)"):
            self.assertGreater(body.index(later), early,
                               "--unpublish reaches %s" % later)

    def test_it_does_not_initialise_the_repository(self):
        # Repository.initialize() calls Keys.create(), which asks "Overwrite
        # key pair?" once per role; a stray y destroys a key every installed
        # copy of Scaffold trusts
        source = io.open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
        body = source[source.index("def unpublish("):source.index("def publish(")]
        self.assertIn("load_repository()", body)
        self.assertNotIn("initialize()", body)


if __name__ == "__main__":
    unittest.main()
