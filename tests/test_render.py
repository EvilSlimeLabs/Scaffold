"""The render check, and the things it is allowed to assume.

`tools/checks/render.py` draws a block from what the pack would ship, so that a
face reading the wrong half of a sheet is something you can see here rather than
something you find in a world. Two kinds of test hold it up.

**What it assumes about orientation.** `render.FACES` says where a picture's
corner goes on each face of a box. Most of it follows from `Cube.uv`, which is
the convention the tables were written to, but the up face's direction is an
observation from the game rather than a convention, and an observation with
nothing holding it in place is a guess waiting to drift. The first tests here
are that observation written down.

**What every block draws.** A lookup table is edited a family at a time and read
by everything afterwards, so the question after a change is not "does it still
build" -- `tools.checks.coverage` answers that -- but "what else moved".
`render_hashes.json` is a fingerprint per form of per block, and the last test
compares every one of them. It is the slow test in this suite, and it earns it: nothing else
here would notice a block quietly changing shape.
"""
import io
import os
import re
import unittest

import numpy as np

from tools.checks import render


def redness(pixels):
    """How many pixels are the red of the lectern's inlay."""
    r = pixels[..., 0].astype(int)
    g = pixels[..., 1].astype(int)
    b = pixels[..., 2].astype(int)
    return int(((r > 100) & (r > g + 50) & (r > b + 50)).sum())


def greenness(pixels):
    """How many pixels are a book spine rather than wood."""
    r = pixels[..., 0].astype(int)
    g = pixels[..., 1].astype(int)
    b = pixels[..., 2].astype(int)
    return int(((g > r + 20) & (g > b + 20)).sum())


class OrientationTests(unittest.TestCase):
    """What the renderer assumes about which way a picture goes on a face.

    The lectern is what settles both of these, because it is the block whose
    faces were compared against the game one at a time.
    """

    @classmethod
    def setUpClass(cls):
        cls.quads, cls.atlas = render.mesh("lectern", rot=0)
        cls.frame = render._frame(cls.quads)

    def view(self, name):
        return np.asarray(
            render.draw(self.quads, self.atlas, name, 8, (0, 0, 0), self.frame),
            dtype=int)

    def test_the_base_band_faces_the_front_seen_from_above(self):
        # `lectern_base` carries a red inlay across the bottom of the tile and
        # it belongs at the front of the block. It came out at the back until
        # the window was turned over, which is what says an up face runs its v
        # toward -z rather than +z. The view puts -z at the top of the picture.
        above = self.view("up")
        half = above.shape[0] // 2
        self.assertEqual(redness(above[:half]), 0,
                         "the base's inlay is at the back of the block")
        self.assertGreater(redness(above[half:]), 0,
                           "the base's inlay is not on the block at all")

    def test_the_post_carries_its_books_on_the_front_only(self):
        # `lectern_front` is two eight wide pictures side by side, the shelf on
        # the left and plain wood on the right. A face reading the whole tile
        # put books on every side of the post.
        self.assertGreater(greenness(self.view("south")), 0,
                           "the post has no books on its front")
        self.assertEqual(greenness(self.view("north")), 0,
                         "the post has books on its back as well")

    def test_every_view_of_a_block_shares_one_frame(self):
        # so the six can be read against each other, and a block that leaves
        # its own cube is not cropped in one view and not in another
        sizes = {render.draw(self.quads, self.atlas, name, 4, (0, 0, 0),
                             self.frame).size
                 for name in ("south", "north")}
        self.assertEqual(len(sizes), 1, "opposite views came out different sizes")


class RendererTests(unittest.TestCase):
    """That it draws what the pack ships rather than its own idea of it."""

    def test_the_drawing_never_reads_the_lookup_tables(self):
        # A renderer that translated the tables would agree with the tables and
        # say nothing about the translation, which is the whole point of it. So
        # what builds the picture may not open one.
        #
        # **Only what builds the picture.** `every_form` reads the shape table
        # to know which forms a block has, which is enumeration and not
        # translation: it decides what to draw, never how it looks. The check is
        # therefore scoped to those functions rather than to the whole file, and
        # reads the parsed code so that naming a table in a comment is not
        # mistaken for opening one.
        import ast

        where = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tools", "checks", "render.py")
        with io.open(where, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        drawing = {"mesh", "draw", "_triangle", "_frame", "_spin", "_corner"}
        found = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name in drawing]
        self.assertEqual({node.name for node in found}, drawing,
                         "a drawing function was renamed or removed; this check "
                         "names them by hand and has to keep up")

        for node in found:
            spoken = ast.get_docstring(node)
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Constant):
                    continue
                if not isinstance(inner.value, str) or inner.value == spoken:
                    continue
                for table in ("block_shapes", "block_uv", "block_rotation",
                              "block_definition"):
                    self.assertNotIn(
                        table, inner.value,
                        "%s reads %s instead of make_block's output"
                        % (node.name, table))

    def test_a_block_leaving_its_own_cube_is_still_in_the_picture(self):
        # a banner is two blocks tall, and a frame fixed to the unit cube would
        # cut half of it off
        quads, _atlas = render.mesh("standing_banner", rot=0)
        low, high = render._frame(quads)
        self.assertGreater(high[1], 1.0,
                           "a standing banner was framed inside one block")

    def test_a_turned_window_reaches_the_picture(self):
        # the lectern's post reads its sides from a tile turned a quarter, and
        # a renderer ignoring the mark would draw the straight one
        from scaffold.pack import armor_stand_geo_class as asgc

        geo = asgc.ArmorStandGeo("t", offsets=[0, 0, 0])
        geo.make_block(0, 0, 0, "lectern", rot=0)
        turned = [name for name in geo.uv_map
                  if name.endswith(asgc.TURN_MARK + "90")]
        self.assertTrue(turned, "the lectern stopped asking for a turned tile")


class ManifestTests(unittest.TestCase):
    """Every block still draws the way it was recorded drawing.

    This is the slow one. It renders every *form* of every block the tables can
    build, six ways round, and compares a fingerprint against
    `tools/checks/render_hashes.json`.

    **Every form, not every block.** A banner is sixteen dyes and two that are
    not, a chiseled bookshelf is sixty-four states, a bed is thirty-five: 1381
    blocks are 2239 forms, and a sweep of the default form alone covers barely
    half of what the tables describe. It was drawing only defaults when an
    ominous banner's face came out cut in half and swapped, and it reported
    nothing changed.

    **A failure here is not necessarily a fault.** It says a block changed, and
    the question is whether the ones listed are the ones that were meant to. If
    they are:

        python -m tools.checks.render --manifest --update

    and commit the file with the change that caused it, so the diff carries
    both.
    """

    def test_every_block_draws_as_it_was_recorded(self):
        self.assertTrue(os.path.isfile(render.MANIFEST),
                        "no render_hashes.json; write one with "
                        "python -m tools.checks.render --manifest --update")
        report = render.manifest()
        self.assertEqual(
            report["unbuildable"], [],
            "blocks that would not draw at all")
        trouble = []
        if report["changed"]:
            trouble.append("changed: " + ", ".join(report["changed"][:20]))
        if report["new"]:
            trouble.append("not recorded: " + ", ".join(report["new"][:20]))
        if report["removed"]:
            trouble.append("gone: " + ", ".join(report["removed"][:20]))
        self.assertEqual(
            trouble, [],
            "\n".join(trouble) + "\n\nIf those are the blocks you meant to "
            "change, re-record them:\n"
            "    python -m tools.checks.render --manifest --update")


if __name__ == "__main__":
    unittest.main()
