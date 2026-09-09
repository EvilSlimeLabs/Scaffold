"""Writing over what is already there, and writing what will not be written.

A build lands on files a previous build left behind, and on files another
program is holding open. Neither is a fault worth throwing a finished pack away
over, so the front end is asked before anything is written over and asked again
when a write fails. What is tested here is the part that can be: which files a
build claims it will write, that the claim matches what it does write, and that
the retry hook is offered every failed write and obeyed either way.
"""
import os
import shutil
import tempfile
import unittest

from scaffold import core


STRUCTURE = os.path.join("test_structures", "01-6xSingleItemSortes.mcstructure")


class OutputNameTests(unittest.TestCase):
    """What a build says it will write, before it has written anything."""

    def test_the_pack_is_named_on_its_own(self):
        self.assertEqual(core.outputs("folder/Sorter"),
                         ["folder/Sorter.mcpack"])

    def test_a_block_list_is_named_for_every_tag(self):
        self.assertEqual(
            core.outputs("Sorter", ["a", "b"], block_lists=True),
            ["Sorter.mcpack", "Sorter-a block list.txt",
             "Sorter-b block list.txt"])

    def test_a_big_build_writes_one_list_and_it_carries_no_tag(self):
        self.assertEqual(
            core.outputs("Sorter", ["a", "b"], block_lists=True, big=True),
            ["Sorter.mcpack", "Sorter block list.txt"])

    def test_the_lists_are_only_named_when_they_are_asked_for(self):
        self.assertEqual(core.outputs("Sorter", ["a"]), ["Sorter.mcpack"])


class WhatABuildActuallyWritesTests(unittest.TestCase):
    """The claim above is only worth anything if the build agrees with it.

    A front end asks before it starts and then never looks again, so a file the
    build writes without naming it here is one that gets written over with
    nobody asked.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="scaffold-outputs-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def build(self, tags, block_lists):
        target = os.path.join(self.folder, "Sorter")
        pack = core.Scaffold(target)
        for tag in tags:
            pack.add_model(tag, STRUCTURE)
            pack.set_model_offset(tag, [0, 0, 0])
        pack.generate_with_nametags()
        if block_lists:
            pack.make_nametag_block_lists()
        pack.compile_pack(overwrite=True)
        return target

    def test_one_model_writes_exactly_what_was_named(self):
        target = self.build([""], block_lists=True)
        self.assertEqual(sorted(os.listdir(self.folder)),
                         sorted(os.path.basename(path) for path in
                                core.outputs(target, [""], block_lists=True)))

    def test_two_models_write_a_list_each(self):
        target = self.build(["north", "south"], block_lists=True)
        self.assertEqual(
            sorted(os.listdir(self.folder)),
            sorted(os.path.basename(path) for path in
                   core.outputs(target, ["north", "south"], block_lists=True)))

    def test_without_the_lists_only_the_pack_is_written(self):
        target = self.build([""], block_lists=False)
        self.assertEqual(os.listdir(self.folder),
                         [os.path.basename(core.pack_file(target))])


class RetryTests(unittest.TestCase):
    """A write that fails is offered back before it is given up on."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="scaffold-retry-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.target = os.path.join(self.folder, "Sorter")
        self.asked = []

    def pack(self):
        pack = core.Scaffold(self.target)
        pack.add_model("", STRUCTURE)
        pack.set_model_offset("", [0, 0, 0])
        pack.generate_with_nametags()
        return pack

    def blocked(self):
        """Something in the pack's place that cannot be written over.

        A directory stands in for the file another program is holding open: the
        sharing violation Windows raises and this both arrive at os.replace as
        an OSError, and only one of them can be arranged on every platform.
        """
        os.makedirs(core.pack_file(self.target))

    def test_the_write_is_asked_about_and_tried_again(self):
        pack = self.pack()
        self.blocked()

        def clear(exc, path):
            self.asked.append(path)
            os.rmdir(path)
            return True

        pack.set_retry(clear)
        written = pack.compile_pack(overwrite=True)
        self.assertEqual(self.asked, [core.pack_file(self.target)])
        self.assertTrue(os.path.isfile(written))

    def test_saying_no_lets_the_error_out(self):
        pack = self.pack()
        self.blocked()
        pack.set_retry(lambda exc, path: False)
        with self.assertRaises(OSError):
            pack.compile_pack(overwrite=True)

    def test_with_nobody_to_ask_the_write_raises(self):
        pack = self.pack()
        self.blocked()
        with self.assertRaises(OSError):
            pack.compile_pack(overwrite=True)

    def test_a_block_list_is_asked_about_too(self):
        pack = self.pack()
        os.makedirs(core.block_list_file(self.target, ""))

        def clear(exc, path):
            self.asked.append(path)
            os.rmdir(path)
            return True

        pack.set_retry(clear)
        pack.make_nametag_block_lists()
        self.assertEqual(self.asked,
                         [core.block_list_file(self.target, "")])

    def test_a_build_told_not_to_overwrite_still_refuses(self):
        # the retry hook is about writes that cannot be made, not about
        # consent; a pack already there is still a FileExistsError
        pack = self.pack()
        open(core.pack_file(self.target), "w").close()
        pack.set_retry(lambda exc, path: False)
        with self.assertRaises(OSError):
            pack.compile_pack(overwrite=False)


class FreeNameTests(unittest.TestCase):
    """The name the window offers instead of writing over a pack."""

    def setUp(self):
        from scaffold.ui import scaffold_gui

        self.free_name = scaffold_gui.free_name
        self.folder = tempfile.mkdtemp(prefix="scaffold-names-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def took(self, name):
        open(os.path.join(self.folder, name + core.PACK_SUFFIX), "w").close()

    def test_the_first_spare_number_is_offered(self):
        self.took("Sorter")
        self.assertEqual(self.free_name(self.folder, "Sorter"), "Sorter (2)")

    def test_a_number_already_taken_is_counted_past(self):
        self.took("Sorter")
        self.took("Sorter (2)")
        self.took("Sorter (3)")
        self.assertEqual(self.free_name(self.folder, "Sorter"), "Sorter (4)")

    def test_a_name_that_already_carries_one_is_not_given_a_second(self):
        self.took("Sorter (2)")
        self.assertEqual(self.free_name(self.folder, "Sorter (2)"),
                         "Sorter (3)")


if __name__ == "__main__":
    unittest.main()
