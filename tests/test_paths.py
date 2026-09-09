import os
import shutil
import tempfile
import unittest

from scaffold import paths
class ResolverTests(unittest.TestCase):
    def test_data_finds_the_lookup_tables(self):
        self.assertTrue(os.path.isfile(paths.lookup("block_definition.json")))
        self.assertTrue(os.path.isdir(paths.vanilla_pack()))

    def test_a_missing_file_resolves_to_somewhere_writable(self):
        # so a caller creating the file puts it in the right place, and an error
        # message names a path a person can actually act on
        target = paths.data("lookups", "not_here_at_all.json")
        self.assertTrue(target.startswith(paths.beside_executable()))

    def test_writes_never_go_into_the_bundle(self):
        # a frozen build unpacks itself into a temporary folder that is thrown
        # away on exit, so anything written there would silently vanish
        self.assertTrue(paths.writable("lookups", "x.json")
                        .startswith(paths.beside_executable()))

    def test_the_default_output_folder_sits_under_documents(self):
        folder = paths.default_output_dir()
        self.assertTrue(folder.startswith(paths.documents()))
        self.assertTrue(folder.endswith("Scaffold Builds"))


class WorkingDirectoryTests(unittest.TestCase):
    """The program must not need the current directory to be the checkout.

    A frozen build runs from wherever the user put the executable, so every data
    read has to go through paths. Running the pipeline from an empty directory
    is the cheapest way to catch a module that still assumes otherwise: a
    missing `import paths` shows up here as the NameError it really is, rather
    than only in a release nobody has run yet.
    """

    def test_a_pack_builds_from_an_unrelated_working_directory(self):
        from scaffold import core
        structure = os.path.abspath(
            os.path.join("test_structures", "stoneSlabs.mcstructure"))
        was = os.getcwd()
        work = tempfile.mkdtemp(prefix="scaffold-cwd-")
        pack = None
        try:
            os.chdir(work)
            pack = core.scaffold(os.path.join(work, "CwdProbe"))
            pack.add_model("", structure)
            pack.set_model_offset("", [0, 0, 0])
            pack.generate_with_nametags()
            built = pack.compile_pack(overwrite=True)
            self.assertTrue(os.path.isfile(built))
        finally:
            if pack is not None:
                pack.cleanup()
            os.chdir(was)
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
