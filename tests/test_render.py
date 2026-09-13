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


class AgreesWithTheGameTests(unittest.TestCase):
    """Blocks whose look in game is settled, held against what this draws.

    **The renderer is only worth having while it agrees with the game**, and
    every one of these was wrong here at some point while being right in a
    world. They are the cheapest thing standing between a picture from
    `tools/checks/render.py` and a wasted build.
    """

    @staticmethod
    def _flat_gap(one, other):
        apart = abs(one - other) % 180
        return min(apart, 180 - apart)

    def test_a_brewing_stands_arms_and_bottles_run_along_their_radius(self):
        # **Bedrock turns a cube about y the other way from `spun`.** The arms
        # are placed by `spun` and turned by a cube rotation of the opposite
        # sign, which is what the game wants; drawn with the sign as written,
        # the two turned arms and their bottles came out square across their
        # own plate. `render.TURN_SIGNS` is what corrects it.
        import math

        quads, _atlas = render.mesh("brewing_stand", data="1-1-1")
        found = {}
        for points, _uvs, _normal, face in quads:
            if face != "north":
                continue
            flat = points[:, [0, 2]] * 16
            edges = [np.hypot(*(flat[(n + 1) % 4] - flat[n])) for n in range(4)]
            longest = round(max(edges), 1)
            ## the arm is four across and the bottle five; the rod and the
            ## plates are square and carry no turn
            if longest not in (4.0, 5.0):
                continue
            run = flat[(int(np.argmax(edges)) + 1) % 4] - flat[int(np.argmax(edges))]
            middle = points.mean(axis=0) * 16
            found[(longest, round(middle[0], 2), round(middle[2], 2))] = (
                self._flat_gap(math.degrees(math.atan2(run[1], run[0])) % 180,
                               math.degrees(math.atan2(middle[2], middle[0])) % 180))
        self.assertEqual(len(found), 6, "a full brewing stand is six pieces")
        for (longest, across, over), apart in found.items():
            with self.subTest(wide=longest, at=(across, over)):
                self.assertLess(apart, 5,
                                "this piece lies across its own radius, %.0f "
                                "degrees off it" % apart)

    def test_a_brewing_stands_arm_carries_its_leg_outward_from_both_sides(self):
        # the tile's four arm columns run 9 dark against the rod to 12 the
        # outer leg. Both large faces have to put the leg at the far end, and
        # with the south face's u running the same way as the north's they came
        # out one each way.
        quads, _atlas = render.mesh("brewing_stand", data="0-0-0")
        faces = 0
        for points, uvs, _normal, face in quads:
            if face not in ("north", "south"):
                continue
            if abs(abs(uvs[:, 0].max() - uvs[:, 0].min()) - 4) > 0.01:
                continue
            faces += 1
            out = lambda p: float(np.hypot(p[0], p[2]))
            near = out(points[uvs[:, 0].argmin()])
            far = out(points[uvs[:, 0].argmax()])
            with self.subTest(face=face, at=round(near * 16, 1)):
                self.assertGreater(far, near,
                                   "this arm face has its leg at the pole")
        self.assertEqual(faces, 6, "three arms, two large faces each")

    def test_a_designed_banners_front_is_the_design_and_its_back_the_mirror(self):
        # **The one thing four quads across buys, and the one that keeps going
        # wrong.** The sheet holds the design mirrored, so column order and
        # per-tile mirroring are two halves of one thing: turn one without the
        # other and the front comes out sliced into four with each slice
        # mirrored where it stands, which reads as almost right.
        from PIL import Image

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sheet = Image.open(os.path.join(
            here, "scaffold", "Vanilla_Resource_Pack", "textures", "entity",
            "banner", "banner_designed.png")).convert("RGB")
        art = sheet.crop((0, 64, 64, 128)).transpose(Image.FLIP_LEFT_RIGHT)

        def in_slices(picture):
            out = picture.copy()
            wide = picture.size[0] // 4
            for n in range(4):
                box = (n * wide, 0, (n + 1) * wide, picture.size[1])
                out.paste(picture.crop(box).transpose(Image.FLIP_LEFT_RIGHT),
                          box)
            return out

        def apart(one, other):
            a = np.asarray(one.resize((64, 64)), dtype=float)
            b = np.asarray(other.convert("RGB").resize((64, 64)), dtype=float)
            return float(np.abs(a - b).mean())

        quads, atlas = render.mesh("standing_banner", data="designed")
        frame = render._frame(quads)
        mirrored = art.transpose(Image.FLIP_LEFT_RIGHT)
        for view, wanted, named in (("south", art, "the design"),
                                    ("north", mirrored, "its mirror")):
            shot = render.draw(quads, atlas, view, 8, (255, 0, 255), frame)
            grid = np.asarray(shot.convert("RGB"))
            solid = np.any(grid != (255, 0, 255), axis=2)
            rows, cols = np.where(solid)
            tall = rows.max() - rows.min() + 1
            keep = [r for r in range(rows.min(), rows.max() + 1)
                    if solid[r].sum() > solid.sum() / tall]
            cloth = Image.fromarray(grid).crop(
                (cols.min(), min(keep), cols.max() + 1, max(keep) + 1))
            close = apart(cloth, wanted)
            for other, other_named in ((in_slices(art), "the design sliced"),
                                       (in_slices(mirrored),
                                        "its mirror sliced")):
                with self.subTest(view=view, against=other_named):
                    self.assertLess(
                        close, apart(cloth, other),
                        "the %s face looks more like %s than like %s"
                        % (view, other_named, named))

    def test_a_sunflowers_head_faces_east_and_tips_upward(self):
        # the one block whose z turn is settled in game, and the reason
        # `TURN_SIGNS` negates y alone: negating all three squares the arms up
        # and leaves this looking at the floor
        quads, _atlas = render.mesh("sunflower", top=True)
        best = None
        for points, _uvs, normal, face in quads:
            if face not in ("east", "west") or normal[0] <= 0:
                continue
            edges = [np.linalg.norm(points[(n + 1) % 4] - points[n])
                     for n in range(4)]
            if best is None or edges[0] * edges[1] > best[0]:
                best = (edges[0] * edges[1], points, normal)
        self.assertIsNotNone(best, "the flower head has no east facing side")
        _area, points, normal = best
        self.assertGreater(points.mean(axis=0)[0] * 16, 0.5,
                           "the head is not east of its own stem")
        self.assertGreater(abs(normal[0]), abs(normal[2]),
                           "the head does not face east and west")
        self.assertGreater(normal[1], 0.05, "the flower looks at the floor")


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
