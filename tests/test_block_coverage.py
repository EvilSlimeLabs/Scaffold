import json
import os
import re
import unittest

from scaffold import paths
from scaffold.pack import armor_stand_geo_class as asgc

## Education Edition and other blocks no vanilla pack ships textures for. They
## are declared so a structure containing one is named rather than mysterious,
## and they will never resolve. tools/audit_blocks.py holds the same list.
UNRESOLVABLE = re.compile(r"^(element_\d+|chemistry_table|chemical_heat"
                          r"|hard_(stained_)?glass(_pane)?"
                          r"|colored_torch_\w+|underwater_torch"
                          r"|coral_(fan_)?pink_dead)$")


def load(name):
    # through paths, so the suite does not depend on where it was run from
    with open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return json.load(f)


class LookupTableTests(unittest.TestCase):
    """The three tables that describe a block have to agree with each other.

    A block_definition entry naming a shape family that block_shapes does not
    describe raises inside make_block, which _add_blocks_to_geo catches, so a
    disagreement here does not fail a build. It quietly empties one out of it.
    """

    @classmethod
    def setUpClass(cls):
        cls.defs = load("block_definition")
        cls.shapes = load("block_shapes")
        cls.uv = load("block_uv")

    def test_every_shape_family_is_described_by_both_tables(self):
        families = {v for v in self.defs.values() if v != "ignore"}
        self.assertFalse(families - set(self.shapes),
                         "shape families with no block_shapes entry")
        self.assertFalse(families - set(self.uv),
                         "shape families with no block_uv entry")

    def test_every_shape_variant_has_a_usable_uv_window(self):
        # a variant missing from block_uv silently falls back to "default",
        # which is right only when its cubes are the same size as the default's
        families = {v for v in self.defs.values() if v != "ignore"}
        for family, variants in self.shapes.items():
            if family not in families:
                continue
            for variant, shape in variants.items():
                window = self.uv[family].get(variant, self.uv[family]["default"])
                for face in ("up", "down", "north", "south", "east", "west"):
                    self.assertGreaterEqual(
                        len(window["uv_sizes"][face]), 1,
                        "%s/%s has no %s uv size" % (family, variant, face))
                    self.assertEqual(
                        len(window["uv_sizes"][face]), len(window["offset"][face]),
                        "%s/%s: %s sizes and offsets disagree" % (family, variant, face))


class GeneratorTests(unittest.TestCase):
    """A generator says what a table is, never what to change it by.

    `build.py` regenerates every table before every compile, so a generator that
    reads a table, adjusts it and writes it back is correct exactly once. Run
    twice it is wrong again, and the tables are valid either way, so nothing
    complains. A carved pumpkin faced a different direction on alternate
    releases for exactly that reason: `faces.py` added a half turn to its own
    output every time it ran.

    Whether a generator is idempotent cannot be read off its source: reading a
    table to *derive* another family from it is ordinary and safe, and
    `faces.py` does it to build `azalea` and `vault` out of `cube`. Only running
    them twice settles it, which rewrites the tables and so belongs in a command
    rather than in here:

        python -m tools.checks.generators

    What this holds is the one that went wrong, so it cannot go wrong again
    quietly.
    """

    def test_the_carved_pumpkin_faces_a_half_turn_from_its_neighbours(self):
        # **A pumpkin is a half turn from `furnace` and `observer`, and it is
        # meant to be.** It carries the same six `facing_direction` words, so
        # matching them looks like the right answer, and it was what this test
        # held before. In game the pumpkin still faced backwards while those two
        # were right, so the two are not one fault in a shared place. What
        # matters is that the half turn is written into the table rather than
        # added to it: added, it corrects on one run and breaks on the next.
        rotation = load("block_rotation")
        turning = ("south", "east", "west", "north")
        for neighbour in ("furnace", "observer"):
            for word in turning:
                with self.subTest(neighbour=neighbour, facing=word):
                    self.assertEqual(
                        (rotation["carved_pumpkin"][word][1]
                         - rotation[neighbour][word][1]) % 360, 180,
                        "carved_pumpkin is no longer a half turn from %s"
                        % neighbour)
        # the two that are a turn about x are shared with them untouched, since
        # a pumpkin has no facing that uses them
        for word in ("up", "down"):
            self.assertEqual(rotation["carved_pumpkin"][word],
                             rotation["furnace"][word])


class BlockBuildTests(unittest.TestCase):
    """Blocks that are easy to drop, built in the states that drop them."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def build(self, name, **kwargs):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, name, **kwargs)

    def test_every_defined_block_builds(self):
        defs = load("block_definition")
        broken = []
        for name in defs:
            if UNRESOLVABLE.match(name):
                continue
            try:
                self.build(name)
            except Exception as exc:
                broken.append("%s (%s)" % (name, type(exc).__name__))
        self.assertEqual(broken, [], "blocks that raise in make_block")

    def test_an_unknown_rotation_state_does_not_drop_the_block(self):
        # soul_campfire reads direction 0 against a table that only listed 1,
        # and the block vanished every time it faced that way. A rotation the
        # table cannot describe should leave the block unrotated, not remove it.
        self.build("soul_campfire", rot=0)
        self.build("soul_campfire", rot="nonsense")
        self.assertTrue(self.geo.blocks)

    def test_legacy_slab_ids_build_in_both_halves(self):
        for name in ("stone_slab", "stone_slab2", "stone_slab3", "stone_slab4",
                     "petrified_oak_slab"):
            for top in (False, True):
                self.build(name, top=top)

    def test_the_new_shape_families_build(self):
        for name in ("oak_shelf", "sulfur_spike", "copper_golem_statue",
                     "heavy_core", "sculk_shrieker", "big_dripleaf",
                     "trip_wire"):
            self.build(name)


class TileTests(unittest.TestCase):
    """A texture with nothing in the part of it that becomes a tile.

    Only the top left 16x16 of a texture is read, and it is cropped rather than
    scaled, so a tile saved at ten times the size reads as the empty corner of
    the picture. The block is drawn, lands in no skipped list, and there is
    nothing to see: `fern` and `short_grass` were both 160x160 and both came out
    as holes in the model.
    """

    @classmethod
    def setUpClass(cls):
        from scaffold import jsonc

        cls.pack = paths.vanilla_pack()
        cls.blocks = jsonc.load(os.path.join(cls.pack, "blocks.json"))
        cls.terrain = jsonc.load(os.path.join(
            cls.pack, "textures", "terrain_texture.json"))["texture_data"]
        cls.ink = {}

    def covered(self, path):
        """How much of the tile Scaffold reads is not transparent."""
        from PIL import Image

        if path not in self.ink:
            full = os.path.join(self.pack, path + ".png")
            if not os.path.isfile(full):
                self.ink[path] = None
            else:
                tile = Image.open(full).convert("RGBA").crop((0, 0, 16, 16))
                self.ink[path] = sum(1 for pixel in tile.getdata()
                                     if pixel[3] > 8)
        return self.ink[path]

    def resolve(self, name):
        """A terrain texture name, as the file the first of its list points at."""
        entry = self.terrain.get(name)
        if entry is None:
            return None
        textures = entry["textures"]
        first = textures[0] if isinstance(textures, list) else textures
        return first["path"] if isinstance(first, dict) else first

    def test_no_supported_block_reads_an_empty_tile(self):
        # what the block declares for a face is only what it wears when the
        # family does not name something else for that face: a bubble column's
        # north slot is a flipbook whose first frame is empty down its left
        # half, and the family overwrites it for exactly that reason
        uvs = load("block_uv")
        empty = []
        for block, family in sorted(load("block_definition").items()):
            if family == "ignore" or UNRESOLVABLE.match(block):
                continue
            layout = self.blocks.get(block, {}).get("textures")
            if layout is None:
                continue
            names = layout if isinstance(layout, dict) else {"all": layout}
            written = uvs.get(family, {}).get("default", {}).get("overwrite", {})
            for face, name in sorted(names.items()):
                if not isinstance(name, str):
                    continue
                instead = (written.get(face) or [None])[0]
                if isinstance(instead, str) and instead not in ("default",):
                    if instead.startswith("@"):
                        continue   # a reference to another of this block's own
                    path = instead.split("#")[0]
                else:
                    path = self.resolve(name)
                if path is None:
                    continue
                if self.covered(path) == 0:
                    empty.append("%s %s -> %s" % (block, face, path))
        self.assertEqual(empty, [],
                         "textures with nothing in the 16x16 Scaffold reads")


class PlantTests(unittest.TestCase):
    """A plant is an X on the block's diagonals, and so is a sunflower."""

    def shapes(self):
        return load("block_shapes")

    def test_a_plant_is_turned_in_its_shape_not_by_a_rotation_table(self):
        # make_block looks a rotation up only when the block hands it one, and a
        # plant carries no facing state, so rot comes back None and the table is
        # never read. cross_texture had an entry turning every plant forty-five
        # degrees and it did nothing -- except in tools/checks/render.py, which
        # passes rot=0 and so drew the X the game never showed.
        turns = load("block_rotation")
        for family in ("cross_texture", "double_plant", "sunflower"):
            with self.subTest(family=family):
                self.assertNotIn(family, turns,
                                 "%s has a rotation table nothing reads" % family)
                for form, body in self.shapes()[family].items():
                    self.assertIn("rotation", body,
                                  "%s/%s has no turn, so it is a plus"
                                  % (family, form))
                    for turn in body["rotation"][:2]:
                        self.assertEqual(turn[1], 45,
                                         "%s/%s is square to the block"
                                         % (family, form))

    def test_a_turned_quad_reaches_the_corners_of_the_block(self):
        # sixteen across turned forty-five degrees spans eleven and a bit, which
        # leaves a gap at every corner; vanilla stretches its quads as it turns
        # them and this writes the stretched length out
        for size in self.shapes()["cross_texture"]["default"]["size"]:
            longest = max(size) * 16
            self.assertGreater(longest, 16,
                               "a quad turned into the diagonal has to be "
                               "longer than the block is wide")
            self.assertLess(longest, 16 * 2 ** 0.5 + 0.01,
                            "a quad longer than the diagonal leaves the block")

    def test_a_sunflower_carries_a_head_and_the_other_double_plants_do_not(self):
        shapes = self.shapes()
        self.assertEqual(len(shapes["sunflower"]["top"]["size"]),
                         len(shapes["double_plant"]["top"]["size"]) + 1,
                         "a sunflower's upper half is its cross and its head")
        self.assertEqual(len(shapes["sunflower"]["default"]["size"]),
                         len(shapes["double_plant"]["default"]["size"]),
                         "only the upper half carries the head")

    def test_the_sunflowers_head_is_yellow_east_and_green_west(self):
        # Bedrock keeps both pictures in sunflower_additional, a list of two,
        # and a block reads a list by its variant -- there is no variant that
        # reaches the second entry, so the head names both outright
        faces = load("block_uv")["sunflower"]["top"]["overwrite"]
        self.assertTrue(faces["east"][-1].endswith("sunflower_front"),
                        "the flower is not on the east face: %s" % faces["east"][-1])
        self.assertTrue(faces["west"][-1].endswith("sunflower_back"),
                        "the back is not on the west face: %s" % faces["west"][-1])
        # and the two sides read the picture opposite ways, because the faces of
        # a plane run their windows in opposite directions
        windows = load("block_uv")["sunflower"]["top"]["uv_sizes"]
        self.assertGreater(windows["east"][-1][0], 0)
        self.assertLess(windows["west"][-1][0], 0)

    def test_the_sunflowers_head_leans_back_east_of_the_stem(self):
        # The stem is a two pixel column up the middle and the flower's disc is
        # the middle eight pixels of its tile, so a head on the middle line puts
        # green through the bottom of the flower.
        #
        # **East is the low side of x.** `armor_stand_geo_class` negates a
        # block's place in the grid and leaves a cube's offset inside the block
        # alone, so a cube written east of the middle comes out west of it in
        # game. Six reads as two pixels east; ten read as two pixels west.
        body = self.shapes()["sunflower"]["top"]
        at, size, turn = (body["offsets"][-1], body["size"][-1],
                          body["rotation"][-1])
        across = (at[0] + size[0] / 2.0) * 16
        self.assertLess(across, 7, "the head stands on the stem")
        self.assertGreater(across, 4, "the head is a pixel or two east, not more")
        # and squarely on the north-south middle, which is the axis it leans about
        along = (at[2] + size[2] / 2.0) * 16
        self.assertAlmostEqual(along, 8, places=3,
                               msg="the head is off the north-south middle")
        # **The lean is positive, which is what makes the yellow face look up.**
        # The same mirror that puts east on the low side of x reverses every
        # turn about y and about z, so a negative angle here puts the flower's
        # face at the floor in game.
        self.assertGreater(turn[2], 0, "the flower looks at the floor")
        self.assertEqual(turn[2], 22.5, "the head leans by some odd amount")


class FootprintTests(unittest.TestCase):
    """Every face reads the part of the tile its own cube covers.

    `Cube.uv` in `tools/blocks/geometry.py` is the rule: an up or a down face
    reads the cube's x and z, a north or a south its x and y, an east or a west
    its z and y. Given the whole tile instead, a face two pixels deep carries
    all sixteen rows of the texture squashed onto it, and the grain stops
    lining up with whatever is beside it.

    **These families and no others.** Plenty of cubes read a whole tile on
    purpose -- a plant's quad is a picture rather than a box, a torch's top is
    the flame, a chain's tile is a strip down one edge rather than a block --
    so this names the families whose texture really is a block tile rather than
    sweeping the tables.
    """

    FOOTPRINT = ("stairs", "standing_sign", "wall_sign", "fence",
                 "fence_gate", "button")
    FACES = ("up", "down", "north", "south", "east", "west")

    @staticmethod
    def window(face, size, at):
        wide, tall, deep = size
        across, up, over = at
        # an up face's v runs toward -z and a down face's runs with it, so a
        # cube that does not fill the block front to back reads its top from
        # the far side
        if face == "up":
            return [across, 1 - over - deep], [wide, deep]
        if face == "down":
            return [across, over], [wide, deep]
        if face in ("north", "south"):
            return [across, 1 - up - tall], [wide, tall]
        return [over, 1 - up - tall], [deep, tall]

    def test_a_face_reads_the_cube_it_belongs_to(self):
        shapes = load("block_shapes")
        windows = load("block_uv")
        for family in self.FOOTPRINT:
            for form, body in shapes[family].items():
                entry = windows[family][form]
                for index, (size, at) in enumerate(zip(body["size"],
                                                       body["offsets"])):
                    for face in self.FACES:
                        offset, span = self.window(face, size, at)
                        with self.subTest(family=family, form=form,
                                          cube=index, face=face):
                            self.assertEqual(
                                [round(n, 6) for n in entry["offset"][face][index]],
                                [round(n, 6) for n in offset])
                            self.assertEqual(
                                [round(n, 6) for n in entry["uv_sizes"][face][index]],
                                [round(n, 6) for n in span])

    def test_every_face_has_a_window_for_every_cube(self):
        # make_block reads uv_idx off the up list and then uses it for all six
        # faces, so a family whose up list is longer than its north list walks
        # off the end of the shorter one
        windows = load("block_uv")
        for family in self.FOOTPRINT + ("chain",):
            for form, entry in windows[family].items():
                runs = {face: len(entry["uv_sizes"][face])
                        for face in self.FACES}
                self.assertEqual(len(set(runs.values())), 1,
                                 "%s/%s has %s" % (family, form, runs))

    def test_a_chain_reads_the_strip_its_tile_actually_holds(self):
        # chain1 and chain2 draw the chain three pixels wide down the left of an
        # otherwise empty tile, so a window taken from the cube's own footprint
        # lands in the empty three quarters and the face draws nothing at all
        entry = load("block_uv")["chain"]["default"]
        for face in self.FACES:
            with self.subTest(face=face):
                self.assertEqual(entry["offset"][face][0], [0, 0],
                                 "a chain's %s does not start at its strip" % face)

    def test_a_standing_signs_post_shares_no_plane_with_its_board(self):
        # the post ran the whole height of the block with its north and south
        # faces exactly on the board's own, which is a flicker rather than a
        # join. It stops a pixel inside the board instead, and is centred, so
        # no two faces sit on one plane.
        body = load("block_shapes")["standing_sign"]["default"]
        board, post = [(at, [a + b for a, b in zip(at, size)])
                       for at, size in zip(body["offsets"], body["size"])]
        for axis, name in enumerate("xyz"):
            self.assertEqual(
                {round(board[side][axis], 6) for side in (0, 1)}
                & {round(post[side][axis], 6) for side in (0, 1)}, set(),
                "the post and the board share a %s plane" % name)
        # and the post really is inside the board rather than stopping under it
        self.assertGreater(post[1][1], board[0][1],
                           "the post stops short of the board")
        # **and it is hidden under the board when you look down at it.** The
        # board sat a pixel south of the middle of the block while the post was
        # centred, so from above the post stuck out past the board's north edge.
        for axis, name in ((0, "x"), (2, "z")):
            self.assertGreaterEqual(round(post[0][axis], 6),
                                    round(board[0][axis], 6),
                                    "the post is outside the board in %s" % name)
            self.assertLessEqual(round(post[1][axis], 6),
                                 round(board[1][axis], 6),
                                 "the post is outside the board in %s" % name)

    def test_a_standing_sign_turns_about_the_middle_of_its_block(self):
        # sixteen rotation steps about a board that is off centre trace a circle
        # instead of spinning it where it stands
        body = load("block_shapes")["standing_sign"]["default"]
        for at, size in zip(body["offsets"], body["size"]):
            for axis in (0, 2):
                self.assertAlmostEqual(at[axis] + size[axis] / 2.0, 0.5,
                                       places=6,
                                       msg="a sign cube is off the middle")


class MountingTests(unittest.TestCase):
    """A block held up four different ways is four different shapes."""

    def setUp(self):
        self.geo = asgc.ArmorStandGeo("test", offsets=[0, 0, 0])

    def cubes(self, name, **kwargs):
        """Every cube one block produces, wherever it ended up."""
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, name, **kwargs)
        found = []
        for group in self.geo.blocks.values():
            for cube in group.get("cubes", []):
                found.append((tuple(cube["origin"]), tuple(cube["size"])))
        return found

    def forms(self, name, variants, **kwargs):
        return {variant: self.cubes(name, data=variant, **kwargs)
                for variant in variants}

    def test_a_bell_is_carried_differently_by_each_mounting(self):
        # standing has two posts and a beam, between two walls only the beam,
        # on one wall half of it, and under a block none of it
        forms = self.forms("bell", ("standing", "multiple", "side", "hanging"))
        self.assertEqual([len(form) for form in forms.values()], [5, 3, 3, 3])
        for one, other in (("standing", "multiple"), ("multiple", "side"),
                           ("side", "hanging")):
            self.assertNotEqual(forms[one], forms[other],
                                "a bell %s looks like one %s" % (one, other))

    def test_a_bell_is_two_pieces_and_wears_its_own_tile(self):
        # `bell_side` draws the whole bell down one column of its tile: the
        # narrow body over the flared lip. Faces left to work their own window
        # out read the middle of a sixteen by sixteen file holding an eight by
        # eight picture, which is mostly nothing, and the bell is a flat plate.
        entry = load("block_uv")["bell"]["standing"]
        for index in (0, 1):
            for face in ("north", "south", "east", "west"):
                self.assertEqual(entry["overwrite"][face][index], "@north",
                                 "the bell's %s is not the bell" % face)
        lip, body = entry["offset"]["north"][:2]
        self.assertNotEqual(lip, body,
                            "both pieces read the same rows of the tile")
        self.assertGreater(lip[1], body[1],
                           "the lip is drawn under the body, not over it")

    def test_what_holds_a_bell_up_is_never_the_bell(self):
        # the short bar under a ceiling wore the bell's own crown texture and
        # came out gold; it is the same dark oak as every other beam
        bell = {"@north", "@up", "@down"}
        uvs = load("block_uv")["bell"]
        shapes = load("block_shapes")["bell"]
        for variant, entry in uvs.items():
            carried = len(shapes[variant]["size"])
            for face, textures in entry["overwrite"].items():
                for index in range(2, carried):
                    self.assertNotIn(
                        textures[index], bell,
                        "%s: what carries the bell reads the bell on %s"
                        % (variant, face))

    def test_a_door_sits_on_the_side_it_faces_and_turns_in_its_block(self):
        # the panel was at z0, the far side of the block from the way the door
        # faces, and the family turned about the panel's own plane rather than
        # the middle of the block, so a door a quarter of the way round swung
        # out of its block entirely
        shapes = load("block_shapes")["door"]
        shut = shapes["default"]
        # a quarter turn clockwise from the side it used to sit on, which a
        # world showed was where it belongs
        self.assertEqual([off[0] for off in shut["offsets"]],
                         [0.8125, 0.8125], "the panel is not on the x side")
        for variant in ("open", "open_hinged"):
            self.assertEqual([size[2] for size in shapes[variant]["size"]],
                             [0.1875, 0.1875],
                             "%s is not a quarter turn round" % variant)
        for variant, form in shapes.items():
            self.assertEqual([form["center"][0], form["center"][2]], [0.5, 0.5],
                             "%s turns about something other than the middle"
                             % variant)

    def test_a_doors_edges_read_its_frame_and_not_its_panel(self):
        # a door is three pixels thick and every one of its six faces read the
        # whole picture, which squeezes the door into three pixels and puts a
        # row of panels down each edge and across the top
        entry = load("block_uv")["door"]["default"]
        for index in (0, 1):
            # shut, the panel is on the x faces and its picture is mirrored: a
            # window that starts at the far edge and runs back
            self.assertEqual(entry["uv_sizes"]["east"][index], [-1.0, 1.0],
                             "the outward face is not read the other way round")
            self.assertEqual(entry["offset"]["east"][index], [1.0, 0.0])
            self.assertEqual(entry["uv_sizes"]["west"][index], [1.0, 1.0],
                             "the inward face is mirrored as well")
            for face in ("north", "south", "up", "down"):
                self.assertEqual(entry["uv_sizes"][face][index], [0.1875, 1.0],
                                 "%s reads more than the frame" % face)
        # the two halves have a picture each, and neither is left to the block's
        # own faces, which would put the lower one on the top of the door
        self.assertEqual(entry["overwrite"]["up"], ["@down", "@north"])

    def test_a_copper_golem_statue_is_the_model_the_game_draws(self):
        # four poses, four geometry files, nine or eleven cubes each with the
        # arms and legs turned where that pose puts them. It was three boxes
        # leaned four ways, wearing terrain tiles, which is a copper blob.
        shapes = load("block_shapes")["copper_golem_statue"]
        self.assertEqual(sorted(shapes), ["0", "1", "2", "3", "default"])
        for pose in ("0", "1", "2", "3"):
            self.assertGreaterEqual(len(shapes[pose]["size"]), 9,
                                    "pose %s is not the whole golem" % pose)
        self.assertEqual(shapes["default"], shapes["0"])

        # the head carries the rod and the pompom above it, which take the
        # statue past the top of its own block
        tallest = max(off[1] + size[1] for off, size
                      in zip(shapes["0"]["offsets"], shapes["0"]["size"]))
        self.assertGreater(tallest, 1.0,
                           "the pompom does not reach past the block")

        # three of the four poses turn something; standing turns nothing
        turned = {pose: any(any(r) for r in shapes[pose].get("rotation", []))
                  for pose in ("0", "1", "2", "3")}
        self.assertFalse(turned["0"], "a standing golem leans")
        self.assertTrue(all(turned[pose] for pose in ("1", "2", "3")),
                        "a pose with no turn in it is the standing one again")

        # every face reads the corner of the entity sheet its own face was
        # drawn at, not a terrain tile
        written = load("block_uv")["copper_golem_statue"]["0"]["overwrite"]
        for face, textures in written.items():
            for texture in textures:
                self.assertIn("#", texture,
                              "%s reads the sheet as a plain tile" % face)

    def test_a_dried_ghast_is_the_cube_its_pictures_were_drawn_for(self):
        # all twenty four of its textures are ten by ten pictures in sixteen by
        # sixteen files. A fourteen by fourteen cube whose faces work their own
        # windows out reads x1 to x15 of a picture that stops at x10, so five
        # sixths of every face is the empty part of the file and the block comes
        # out as slivers.
        cubes = self.cubes("dried_ghast")
        body = max(cubes, key=lambda cube: cube[1][0])
        self.assertEqual(body[1], (0.625, 0.625, 0.625),
                         "the body is not the ten by ten cube")
        self.assertEqual(body[0][1], 0, "the body is off the floor")

        # six tentacles lying flat on the ground, three long, two across and
        # one deep: two out of each of the three blank sides and none out of
        # the face, which is south
        tentacles = [cube for cube in cubes if cube is not body]
        self.assertEqual(len(tentacles), 6, "a dried ghast has six tentacles")
        near, far = body[0][2], body[0][2] + body[1][2]
        sides = {"west": 0, "east": 0, "north": 0, "south": 0}
        for at, size in tentacles:
            self.assertEqual(at[1], 0, "a tentacle is off the ground")
            self.assertEqual(size[1], 0.0625, "a tentacle is not one deep")
            self.assertEqual(sorted([size[0], size[2]]), [0.125, 0.1875],
                             "a tentacle is not three long and two across")
            if size[0] > size[2]:
                sides["west" if at[0] < body[0][0] else "east"] += 1
            else:
                sides["north" if at[2] < near else "south"] += 1
        self.assertEqual(sides["south"], 0,
                         "a tentacle comes out of the ghast's face")
        self.assertEqual([sides["west"], sides["east"], sides["north"]],
                         [2, 2, 2], "the three blank sides take two each")
        self.assertLessEqual(far, 1.0)

        entry = load("block_uv")["dried_ghast"]["default"]
        for face in ("north", "south", "east", "west", "up", "down"):
            self.assertEqual(entry["uv_sizes"][face][0], [0.625, 0.625],
                             "the body reads past the picture on %s" % face)
            self.assertEqual(entry["offset"][face][0], [0.0, 0.0])
        # the tentacles keep the block's own faces, so they follow the
        # rehydration level with the rest of it
        for face in ("north", "south", "east", "west", "up", "down"):
            for index in range(1, len(cubes)):
                self.assertTrue(
                    entry["overwrite"][face][index].startswith("@"),
                    "a tentacle names a texture of its own")

    def test_a_campfire_sits_its_logs_in_ash(self):
        # the log tile is three pictures stacked: the bark, the cut end beside
        # it, and the ash across the bottom half. The ash is a plate on the
        # floor of the block with the logs standing in it, so it shows through
        # the square between them.
        out = self.cubes("campfire", data="1")
        self.assertEqual(len(out), 5, "the ash and four logs")
        ash = min(out, key=lambda cube: cube[1][1])
        self.assertEqual(ash[0][1], 0, "the ash is not on the floor")
        self.assertEqual([ash[1][0], ash[1][2]], [1.0, 1.0],
                         "the ash does not reach the edges of the block")

        logs = [cube for cube in out if cube is not ash]
        under = [cube for cube in logs if cube[0][1] == 0]
        over = [cube for cube in logs if cube[0][1] > 0]
        self.assertEqual(len(under), 2)
        self.assertEqual(len(over), 2)
        for at, size in logs:
            self.assertEqual(min(size[0], size[2]), 0.25,
                             "a log is not four pixels thick")
            self.assertEqual(max(size[0], size[2]), 1.0,
                             "a log does not run the whole block")
        # the two pairs cross, so one runs along x and the other along z
        self.assertNotEqual(under[0][1][0], over[0][1][0],
                            "both pairs of logs lie the same way")

        entry = load("block_uv")["campfire"]["1"]
        for face in ("north", "south", "east", "west", "up", "down"):
            for index in range(len(out)):
                self.assertNotEqual(
                    entry["uv_sizes"][face][index], [1.0, 1.0],
                    "cube %d reads the whole tile for %s" % (index, face))

    def test_a_heavy_core_reads_three_pictures_from_one_file(self):
        # `heavy_core.png` is a 16x16 file holding three eight by eight
        # pictures: the top with its rings, the bottom beside it and the side
        # under them. A face working its own window out from where the cube sits
        # reads the middle of the file, which straddles all three and the empty
        # quarter under the bottom, so the core comes out as mismatched plates.
        entry = load("block_uv")["heavy_core"]["default"]
        corners = {face: tuple(entry["offset"][face][0])
                   for face in ("up", "down", "north", "south", "east", "west")}
        for face, corner in corners.items():
            self.assertEqual(entry["uv_sizes"][face][0], [0.5, 0.5],
                             "%s does not read an eight by eight" % face)
            for value in corner:
                self.assertIn(value, (0.0, 0.5),
                              "%s reads across two of the pictures" % face)
        self.assertEqual(len({corners[face] for face in
                              ("north", "south", "east", "west")}), 1,
                         "the four walls wear one picture")
        self.assertEqual(len(set(corners.values())), 3,
                         "the top, the bottom and the side are three pictures")
        self.assertNotIn((0.5, 0.5), set(corners.values()),
                         "a face reads the empty quarter of the file")

    def test_a_brewing_stand_stands_in_a_channel_between_its_plates(self):
        # it was a rod on one 14 by 14 slab, which is a paving stone with a pole
        # through it, and the pole started on top of that slab so it stood two
        # pixels proud of the block
        shapes = load("block_shapes")["brewing_stand"]
        empty = shapes["0-0-0"]
        self.assertEqual(len(empty["size"]), 7,
                         "a rod, three plates and an arm to each")
        plates = [size for size in empty["size"] if size[1] == 0.125]
        self.assertEqual(len(plates), 3)
        for plate in plates:
            self.assertEqual([plate[0], plate[2]], [0.375, 0.375],
                             "a plate is not six by six")
        # a bottle is one upright plane, and each slot bit puts one on
        self.assertEqual(len(shapes["1-1-1"]["size"]),
                         len(empty["size"]) + 3,
                         "the slot bits do not each add a bottle")

        # the three arms are the same plane turned about the rod: one towards
        # the solitary plate and one to each of the pair, a hundred and thirty
        # five degrees either way
        turns = sorted(turn[1] for turn, size in
                       zip(empty["rotation"], empty["size"]) if size[2] < 0.05)
        self.assertEqual(turns, [-135.0, 0.0, 135.0])

        # the rod reads the column of its tile it is drawn in, not the whole of
        # it, which carries the arms that hold the bottles either side
        entry = load("block_uv")["brewing_stand"]["default"]
        for face in ("north", "south", "east", "west"):
            self.assertLess(entry["uv_sizes"][face][0][0], 0.5,
                            "the rod reads the arms as well as itself")

    def test_a_grindstones_wheel_is_the_size_its_textures_were_drawn_for(self):
        # `grindstone_side` is twelve across and twelve down and
        # `grindstone_round` is eight by twelve, which is a wheel twelve wide,
        # twelve tall and eight deep seen face on and then edge on. It was drawn
        # twelve by eight by four, a third of the stone that should be there.
        shapes = load("block_shapes")["grindstone"]
        for variant, form in shapes.items():
            wheel = max(form["size"], key=lambda size: size[0] * size[1] * size[2])
            # its round faces are the two you look at and they belong on the
            # x sides, so the wheel is eight across, twelve tall, twelve deep
            self.assertEqual(wheel, [0.5, 0.75, 0.75],
                             "%s has the wrong wheel" % variant)

        # and it names its faces: blocks.json puts the pivot's texture on north
        # and the leg's oak on down, which are slots the engine picks from and
        # not the six sides of a cube
        written = load("block_uv")["grindstone"]["standing"]["overwrite"]
        wheel = len(shapes["standing"]["size"]) - 1
        for face in ("north", "south", "east", "west", "up", "down"):
            self.assertNotIn(written[face][wheel], ("default", "@north", "@down"),
                             "the wheel wears a pivot or a leg on %s" % face)

    def test_a_grindstone_puts_its_legs_where_it_is_fixed(self):
        forms = self.forms("grindstone",
                           ("standing", "hanging", "side", "multiple"))
        for one, other in (("standing", "hanging"), ("hanging", "side"),
                           ("side", "multiple")):
            self.assertNotEqual(forms[one], forms[other],
                                "a grindstone %s looks like one %s" % (one, other))

    def test_a_hanging_sign_shows_how_it_is_hung(self):
        # named by attached_bit and hanging: chains under a block, a shortened
        # pair and a bar when attached to it, and the same again with the bar
        # run out to the edges when mounted on a wall
        forms = self.forms("oak_hanging_sign", ("0-1", "1-1", "0-0"))
        self.assertEqual([len(form) for form in forms.values()], [3, 4, 4])
        self.assertNotEqual(forms["0-1"], forms["1-1"])
        self.assertNotEqual(forms["1-1"], forms["0-0"])

    def test_a_hanging_sign_on_a_wall_reaches_it_with_the_bar_it_has(self):
        # it was the form fixed under a block with a second piece bolted on to
        # run back into the wall, which reads as a post nobody asked for. The
        # bar itself goes to the edges of the block instead, the way a bell's
        # beam spans two walls.
        under = self.cubes("oak_hanging_sign", data="1-1")
        wall = self.cubes("oak_hanging_sign", data="0-0")
        self.assertEqual(len(wall), len(under),
                         "the wall form carries a piece the other does not")
        widest = max(size[0] for _at, size in wall)
        self.assertEqual(widest, 1.0, "nothing on the wall form reaches a wall")
        self.assertLess(max(size[0] for _at, size in under), widest,
                        "the bar under a block reaches for a wall that is "
                        "not there")

    def test_a_hanging_sign_reads_the_state_its_mounting_turns_with(self):
        # Bedrock gives it both, and only one applies: a sign fixed to the
        # block above turns in sixteen steps with ground_sign_direction, and
        # every other mounting turns with facing_direction, which is why the
        # two numberings cannot share a rotation entry.
        from scaffold import core

        wall = {"states": {"attached_bit": 0, "hanging": 0,
                           "facing_direction": 4, "ground_sign_direction": 0}}
        fixed = {"states": {"attached_bit": 1, "hanging": 1,
                            "facing_direction": 0, "ground_sign_direction": 10}}
        self.assertEqual(core.Scaffold._process_block(None, wall)[0], 4)
        self.assertEqual(core.Scaffold._process_block(None, fixed)[0], 10)

    def test_each_mounting_turns_by_its_own_numbering(self):
        def angle(variant, rot):
            self.geo.blocks = {}
            self.geo.make_block(0, 0, 0, "oak_hanging_sign", rot=rot,
                                data=variant)
            group = list(self.geo.blocks.values())[0]
            return group["cubes"][0]["rotation"]

        # 4 is west to a wall sign and 90 degrees round to an attached one
        self.assertEqual(angle("0-0", 4), [0, 90, 0])
        self.assertEqual(angle("1-1", 4), [0, 90.0, 0])
        self.assertEqual(angle("1-1", 10), [0, 225.0, 0])

    def test_a_lit_campfire_is_the_one_with_a_fire_on_it(self):
        # the logs barely differ between lit and out, so the flame is what
        # tells them apart, and which flame tells a soul campfire from the rest
        lit = self.cubes("campfire", data="0")
        out = self.cubes("campfire", data="1")
        self.assertEqual(len(lit) - len(out), 2, "the flame is two quads")
        self.assertEqual(len(self.cubes("soul_campfire", data="0")), len(lit))

    def test_an_open_door_is_drawn_by_its_lower_block_alone(self):
        # the lower block of a door draws both halves and the upper draws
        # nothing, but the open forms used to be settled first, so an open door
        # was drawn twice, once by each of its blocks, in the same place
        for hinge in (False, True):
            self.assertEqual(len(self.cubes("iron_door", rot=1, top=True,
                                            trap_open=True, hinge=hinge)), 1)
        self.assertEqual(len(self.cubes("iron_door", rot=1, top=True)), 1)
        self.assertEqual(len(self.cubes("iron_door", rot=1, trap_open=True)), 2)

    def test_a_dyed_cauldron_is_drawn_in_its_own_colour(self):
        # a cauldron's dye is a whole RGB in the block entity, not one of a
        # list, so no lookup table could carry a texture for it and a ghost
        # block cannot tint as it draws. Scaffold builds the pack, so the tile
        # is multiplied by the colour on its way into the atlas and every dye in
        # a structure lands there as a tile of its own.
        from scaffold import core

        pack = core.Scaffold.__new__(core.Scaffold)
        states = {"cauldron_liquid": "water", "fill_level": 4}
        plain = core.Scaffold._process_block(
            pack, {"name": "minecraft:cauldron", "states": states},
            {"id": "Cauldron"})
        self.assertEqual(plain[4], "water-4")
        self.assertIsNone(plain[6], "an undyed cauldron carries a colour")

        seen = {}
        for colour in (0xFF3030, 0x3030FF):
            props = core.Scaffold._process_block(
                pack, {"name": "minecraft:cauldron", "states": states},
                {"id": "Cauldron", "CustomColor": colour})
            self.assertEqual(props[4], "dyed-4",
                             "a dyed cauldron does not change liquid")
            self.geo.blocks = {}
            self.geo.uv_map = {}
            self.geo.uv_array = None
            self.geo.make_block(0, 0, 0, "cauldron", data=props[4],
                                tint=props[6])
            named = [n for n in self.geo.uv_map if "~" in n]
            self.assertEqual(len(named), 1, "the water does not carry a colour")
            row = self.geo.uv_map[named[0]]
            seen[colour] = list(self.geo.uv_array[row * 16 + 4][4][:3])
        self.assertNotEqual(seen[0xFF3030], seen[0x3030FF],
                            "two dyes came out the same colour")
        self.assertGreater(seen[0xFF3030][0], seen[0xFF3030][2])
        self.assertGreater(seen[0x3030FF][2], seen[0x3030FF][0])

    def test_a_bed_is_drawn_in_the_colour_its_block_entity_names(self):
        # a bed's colour is in the block entity and which half it is in its
        # states, and the shape wants both, so the two are joined the way two
        # shape states are. There is one set of tiles per colour: the game holds
        # a model each rather than tinting anything, and a ghost block has
        # nothing to tint at run time either.
        from scaffold import core

        pack = core.Scaffold.__new__(core.Scaffold)
        for half, base, colour in ((0, 11, "blue"), (1, 5, "lime")):
            data = core.Scaffold._process_block(
                pack, {"name": "minecraft:bed",
                       "states": {"head_piece_bit": half, "direction": 0}},
                {"id": "Bed", "color": base})[4]
            self.assertEqual(data, "%d-%d" % (half, base))
            self.geo.blocks = {}
            self.geo.uv_map = {}
            self.geo.uv_array = None
            self.geo.make_block(0, 0, 0, "bed", data=data)
            worn = {n.split("/")[-1] for n in self.geo.uv_map if "bed_" in n}
            self.assertEqual(len(worn), 3, "a bed reads three of its tiles")
            for name in worn:
                self.assertTrue(name.startswith("bed_%s_" % colour), name)
        # and a bed with no entity beside it keeps its half
        plain = self.cubes("bed", data="1")
        self.assertEqual(len(plain), 3)

    def test_a_bed_has_two_legs_and_wears_its_own_tile(self):
        # four legs a block puts eight under a bed. `bed_feet_end` carries a leg
        # at each corner, which is one end seen from outside, so a block has two
        # and they stand at the end away from the other half.
        shapes = load("block_shapes")["bed"]
        for variant, at in (("0-14", 0.0), ("1-14", 0.8125)):
            form = shapes[variant]
            self.assertEqual(len(form["size"]), 3, "a mattress and two legs")
            legs = [off for off, size in zip(form["offsets"], form["size"])
                    if size[1] < 0.25]
            self.assertEqual(len(legs), 2)
            for leg in legs:
                self.assertEqual(leg[0], at,
                                 "the legs of %s are at the wrong end" % variant)

        written = load("block_uv")["bed"]["0-14"]["overwrite"]
        for face, textures in written.items():
            for index, texture in enumerate(textures):
                if face == "down":
                    continue    # nothing on the bed's tile is its underside
                self.assertIn("bed_", texture,
                              "%s of cube %d is not the bed's own tile"
                              % (face, index))

    def test_a_cocoa_pod_reads_the_pod_and_not_the_bark(self):
        # each stage's tile holds the pod's top in the corner, its side beside
        # that, and the stalk drawn diagonally between them. A face working its
        # own window out reads across all three and comes out as bark.
        uvs = load("block_uv")["cocoa"]
        shapes = load("block_shapes")["cocoa"]
        for stage in ("0", "1", "2"):
            entry, form = uvs[stage], shapes[stage]
            wide, tall, deep = form["size"][0]
            self.assertEqual(entry["uv_sizes"]["north"][0][1], tall,
                             "stage %s reads the pod at the wrong height"
                             % stage)
            self.assertEqual(entry["offset"]["up"][0], [0.0, 0.0],
                             "stage %s does not take its top from the corner"
                             % stage)
            self.assertNotEqual(entry["offset"]["north"][0], [0.0, 0.0],
                                "stage %s reads its side off the top corner"
                                % stage)

    def test_a_turtle_egg_reads_an_egg_on_every_face(self):
        # the tile holds an egg drawn several times over, and the two sizes are
        # drawn in different corners of it, so a face working its own window out
        # reads whichever eggs line up with where it stands and one window for
        # both sizes reads empty tile down the side of the bigger one
        from PIL import Image

        entry = load("block_uv")["turtle_egg"]["four_egg"]
        shapes = load("block_shapes")["turtle_egg"]["four_egg"]
        tile = Image.open(os.path.join(
            paths.vanilla_pack(), "textures", "blocks",
            "turtle_egg_not_cracked.png")).convert("RGBA")
        for index, size in enumerate(shapes["size"]):
            self.assertEqual(entry["uv_sizes"]["north"][index],
                             [size[0], size[1]],
                             "egg %d reads a window the wrong shape" % index)
            for face in ("north", "south", "east", "west", "up", "down"):
                across, down = entry["offset"][face][index]
                wide, tall = entry["uv_sizes"][face][index]
                clear = [(x, y)
                         for y in range(round(down * 16), round((down + tall) * 16))
                         for x in range(round(across * 16), round((across + wide) * 16))
                         if tile.getpixel((x, y))[3] == 0]
                self.assertEqual(clear, [],
                                 "egg %d reads empty tile on its %s"
                                 % (index, face))

    def test_a_crop_wears_the_texture_of_the_stage_it_is_at(self):
        # eight stages of wheat, and a lookup naming only the last of them
        # draws a field of seedlings as a field ready to harvest
        seen = []
        for stage in range(8):
            self.geo.blocks = {}
            self.geo.uv_map = {}
            self.geo.uv_array = None
            self.geo.make_block(0, 0, 0, "wheat", data=stage)
            seen.append(sorted(self.geo.uv_map)[0])
        self.assertEqual(len(set(seen)), 8, "every stage is its own texture")
        self.assertIn("wheat_stage_0", seen[0])
        self.assertIn("wheat_stage_7", seen[7])

    def test_a_head_is_drawn_rather_than_ignored(self):
        # a head was `ignore`, so every skull in a build was silently missing
        for name in ("skeleton_skull", "wither_skeleton_skull", "zombie_head",
                     "creeper_head", "player_head"):
            self.assertEqual(len(self.cubes(name, rot=1)), 1, name)
        # the piglin keeps its snout, its tusks and its ears, and the dragon
        # every one of its seven pieces, because both are read from the
        # geometry the game draws them with
        self.assertEqual(len(self.cubes("piglin_head", rot=1)), 6)
        self.assertEqual(len(self.cubes("dragon_head", rot=1)), 7)
        floor = self.cubes("skeleton_skull", rot=1)
        wall = self.cubes("skeleton_skull", rot=3)
        self.assertNotEqual(floor, wall, "a wall head hangs where it is fixed")

    def test_a_head_reads_every_face_of_its_sheet(self):
        # an entity sheet is 64 wide, and only a 16x16 window of a texture
        # becomes a tile, so each face has to name the window it reads
        self.geo.blocks = {}
        self.geo.uv_map = {}
        self.geo.uv_array = None
        self.geo.make_block(0, 0, 0, "skeleton_skull", rot=1)
        self.assertEqual(len(self.geo.uv_map), 6, "one tile a face")
        corners = sorted(name.split("#")[1] for name in self.geo.uv_map)
        self.assertEqual(corners, ["0,8", "16,0", "16,8", "24,8", "8,0", "8,8"])

    def test_a_cauldron_has_an_opaque_underside(self):
        # **`cauldron_bottom` is opaque only at its four corners.** The game
        # expects the recessed floor of the pot to show through the gap between
        # the feet; a ghost block cannot afford that, because a transparent
        # texel still takes the depth it stands at, so the cut middle blanked
        # whatever stood behind it and a cauldron could be seen up through from
        # below and out of the top. `tools/textures/cauldron.py` draws the feet
        # onto the inside instead, one picture with nothing cut out of it.
        from PIL import Image

        entry = load("block_uv")["cauldron"]["default"]["overwrite"]
        under = str(entry["down"][0])
        self.assertTrue(under.endswith("cauldron_bottom_flat"),
                        "the underside reads %s, which has its middle cut out"
                        % under)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        picture = Image.open(os.path.join(
            here, "scaffold", "Vanilla_Resource_Pack",
            under + ".png")).convert("RGBA")
        clear = [p for p in picture.getdata() if p[3] < 255]
        self.assertEqual(clear, [], "the flattened underside is not solid")

    def test_a_brewing_stands_arms_all_carry_their_leg_outward(self):
        # **The leg has to stay at the same end of the block from either side.**
        # The tile's four arm columns run outward -- 9 is the dark pipe against
        # the rod, 12 the brown leg over the plate -- and the cube runs inward,
        # so the window has to start at the far edge and run back. All three
        # arms are one cube at three angles, so getting it wrong points all
        # three the same way rather than each of them outward.
        #
        # **Whether the two large faces take the same window is still open.**
        # One window on all six keeps the leg at the same end of the block from
        # either side; `two_sided` gives the south face the opposite one, which
        # is what a banner wants and which put the leg outboard on north and
        # against the pole on south when it was measured. Both are being tried
        # in game, so this holds only what is true either way: the window runs
        # back from the far edge, which is what keeps the leg off the pole.
        entry = load("block_uv")["brewing_stand"]["default"]
        arms = [i for i, size in enumerate(entry["uv_sizes"]["north"])
                if abs(abs(size[0]) * 16 - 4) < 0.01]
        self.assertEqual(len(arms), 3, "a brewing stand is three arms")
        for index in arms:
            with self.subTest(cube=index):
                self.assertLess(
                    entry["uv_sizes"]["north"][index][0], 0,
                    "the arm reads its tile forwards, so its leg is at the pole")
                self.assertEqual(
                    abs(entry["uv_sizes"]["south"][index][0]),
                    abs(entry["uv_sizes"]["north"][index][0]),
                    "the two faces read different amounts of the tile")

    def test_a_brewing_stands_bottle_turns_with_the_arm_it_stands_on(self):
        # **A bottle takes its plate's middle outright and its arm swings round
        # to one**, so `brew_bottle` does not go through `brew_turned` and does
        # not get its sign correction for free. It kept the plain angle after
        # the arms were negated, which left the two turned bottles facing
        # across their plate while their arms ran along it.
        body = load("block_shapes")["brewing_stand"]["1-1-1"]
        pairs = []
        for size, turn in zip(body["size"], body.get("rotation", [])):
            wide, _tall, deep = [n * 16 for n in size]
            ## the arm is four across and a tenth thick, the bottle five and a
            ## fifth; the rod and the plates are square and carry no turn
            if deep < 1 and wide in (4, 5):
                pairs.append((round(wide), round(turn[1], 3)))
        self.assertEqual(len(pairs), 6, "a full brewing stand is three of each")
        for plate in range(3):
            arm, bottle = pairs[plate * 2], pairs[plate * 2 + 1]
            with self.subTest(plate=plate):
                self.assertEqual(arm[0], 4, "these are not arm then bottle")
                self.assertEqual(bottle[0], 5, "these are not arm then bottle")
                self.assertEqual(
                    arm[1], bottle[1],
                    "the bottle on plate %d does not turn with its arm" % plate)

    def test_a_head_on_the_floor_stands_on_the_floor(self):
        # **A floor head arrives as `spinN`, not as 1.** Which of sixteen ways
        # it faces is in the block entity rather than the states, so `core.py`
        # hands the turn over as `spin0` to `spin15`, and the plain 1 is only
        # what a head with no entity beside it keeps. `make_block` read anything
        # that was not 1 as a wall value, so every skull anybody had actually
        # placed on the ground was drawn four pixels up and four back.
        for rot in ["1"] + ["spin%d" % n for n in range(0, 16, 5)]:
            with self.subTest(rot=rot):
                floor = min(o[1] * 16 for o, _s in self.cubes("skeleton_skull",
                                                              rot=rot))
                self.assertEqual(round(floor, 3), 0.0,
                                 "a head turned %s hangs in the air" % rot)
        # and one on a wall is still lifted clear of it
        for rot in ("2", "3", "4", "5"):
            with self.subTest(rot=rot):
                floor = min(o[1] * 16 for o, _s in self.cubes("skeleton_skull",
                                                              rot=rot))
                self.assertGreater(floor, 0, "a head on a wall sits on the floor")

    def test_a_dragon_head_is_bigger_than_the_block_it_is_placed_on(self):
        # **Bigger than its block, and three quarters of its own model.**
        # `geometry.dragon_head` is the head off a full sized ender dragon --
        # sixteen across, twenty tall and thirty deep, which is two blocks of
        # snout -- and the ghost at that size swamped everything near it. Three
        # quarters is the factor the game draws the block at. It still leaves
        # the snout out the front and the jaw below the floor, which is where
        # the real one goes, so shrinking it to fit the block would be wrong.
        reach = [(min(o[i] * 16 for o, _ in self.cubes("dragon_head", rot=1)),
                  max((o[i] + s[i]) * 16
                      for o, s in self.cubes("dragon_head", rot=1)))
                 for i in range(3)]
        across, tall, deep = [(round(a, 1), round(b, 1)) for a, b in reach]
        self.assertEqual([across, tall, deep],
                         [(-6.0, 6.0), (0.0, 15.0), (-4.5, 18.0)])
        self.assertGreater(deep[1] - deep[0], 16, "the snout is inside the block")
        # **and it stands on the floor.** A ghost block reaching down into the
        # block underneath reads as belonging to that block rather than to this
        # one, so the floor form is lifted by however far its jaw falls short.
        # The wall form is left hanging, which is what the game does.
        self.assertEqual(tall[0], 0.0, "a dragon head on the floor hangs below it")
        self.assertLessEqual(tall[1], 16, "and it does not reach past the top")

    def test_a_head_and_a_banner_stay_inside_the_block_they_mark(self):
        # a ghost block is a mark on the place a block goes, so one that leans
        # into its neighbours makes a row of them hard to tell apart. x and z
        # run -8 to 8 about the middle; y runs 0 to 16 from the floor. The
        # dragon is the exception, and is checked above.
        limits = ((-8, 8), (0, 16), (-8, 8))
        cases = [(name, rot) for name in
                 ("skeleton_skull", "player_head", "piglin_head")
                 for rot in (1, 3)]
        for name, rot in cases:
            for axis, (low, high) in enumerate(limits):
                reach = [(origin[axis] * 16, (origin[axis] + size[axis]) * 16)
                         for origin, size in self.cubes(name, rot=rot)]
                self.assertGreaterEqual(min(a for a, _ in reach), low - 0.01,
                                        "%s at %s runs past %s" % (name, rot, axis))
                self.assertLessEqual(max(b for _, b in reach), high + 0.01,
                                     "%s at %s runs past %s" % (name, rot, axis))

    def test_a_banner_is_two_blocks_tall_and_stands_on_wood(self):
        # it stands out of its own block the way the game draws one, and the
        # post is wood: both the post and the cloth were reading a window in the
        # cloth's corner of the sheet, so a banner was a coloured post with a
        # coloured cloth on it.
        standing = self.cubes("standing_banner", rot=0)
        top = max((origin[1] + size[1]) * 16 for origin, size in standing)
        self.assertGreater(top, 16, "a banner stops at the top of its block")
        self.assertLessEqual(top, 32, "a banner is more than two blocks tall")
        # a wall banner hangs the other way, down past its own floor
        wall = self.cubes("wall_banner", rot=3)
        self.assertLess(min(origin[1] * 16 for origin, _size in wall), 0)

    def test_a_banner_reads_a_corner_that_leaves_a_whole_tile_on_the_sheet(self):
        # Only the sixteen square from the corner becomes a tile, and
        # extend_uv_image throws a corner away and reads from 0,0 instead when
        # sixteen more would run off the edge -- silently. 0,0 on a banner sheet
        # is the cloth, so a post asked for past the edge came out dyed.
        from PIL import Image

        pack = paths.vanilla_pack()
        uv = load("block_uv")
        sizes = {}
        for family in ("standing_banner", "wall_banner"):
            for variant, entry in uv[family].items():
                if variant.endswith("__low"):
                    continue
                for face, written in entry["overwrite"].items():
                    for texture in written:
                        if "#" not in texture:
                            continue
                        name, corner = texture.split("#")
                        across, down = (int(n) for n in corner.split(","))
                        if name not in sizes:
                            with Image.open(os.path.join(pack, name + ".png")) as s:
                                sizes[name] = s.size
                        wide, tall = sizes[name]
                        self.assertLessEqual(
                            across + 16, wide,
                            "%s/%s %s: %s runs off the sheet, so it reads 0,0"
                            % (family, variant, face, texture))
                        self.assertLessEqual(
                            down + 16, tall,
                            "%s/%s %s: %s runs off the sheet, so it reads 0,0"
                            % (family, variant, face, texture))

    def test_a_banners_post_and_bar_read_the_wood(self):
        # both the post and the cloth were reading a window in the cloth's
        # corner of the sheet, so a banner was a coloured post with a coloured
        # cloth on it. A dyed sheet leaves the wood alone, so nothing the post
        # or the bar reads may carry the dye.
        from PIL import Image

        pack = paths.vanilla_pack()
        entry = load("block_uv")["standing_banner"]["14"]     # red
        shape = load("block_shapes")["standing_banner"]["14"]
        with Image.open(os.path.join(
                pack, "textures/entity/banner/banner_red.png")) as cloth:
            dye = cloth.convert("RGBA").getpixel((10, 20))
        wooden = 0
        for index, texture in enumerate(entry["overwrite"]["south"]):
            if "#" not in texture:
                continue
            name, corner = texture.split("#")
            across, down = (int(n) for n in corner.split(","))
            x, y = entry["offset"]["south"][index]
            wide, tall = entry["uv_sizes"]["south"][index]
            at = (across + int(round(x * 16)) + max(int(round(wide * 16)), 1) // 2,
                  down + int(round(y * 16)) + max(int(round(tall * 16)), 1) // 2)
            with Image.open(os.path.join(pack, name + ".png")) as sheet:
                painted = sheet.convert("RGBA").getpixel(at)
            self.assertNotEqual(painted, dye,
                                "%s reads the cloth, not the wood" % texture)
            wooden += 1
        self.assertGreaterEqual(wooden, 2,
                                "a banner has a post and a bar to read wood for")
        self.assertEqual(len(shape["size"]), len(entry["overwrite"]["south"]))

    def test_the_dye_leaves_a_banners_post_alone(self):
        # the game tints only the cloth. Multiplying the whole sheet gives every
        # banner a post and a bar in its own colour.
        from PIL import Image

        pack = paths.vanilla_pack()
        opened = {}
        for colour in ("white", "red", "blue"):
            path = os.path.join(pack, "textures", "entity", "banner",
                                "banner_%s.png" % colour)
            opened[colour] = Image.open(path).convert("RGBA")
        posts = {image.getpixel((46, 10)) for image in opened.values()}
        bars = {image.getpixel((10, 43)) for image in opened.values()}
        self.assertEqual(len(posts), 1, "the dye reaches the post")
        self.assertEqual(len(bars), 1, "the dye reaches the bar")
        cloths = {image.getpixel((4, 4)) for image in opened.values()}
        self.assertEqual(len(cloths), 3, "the dye does not reach the cloth")

    def test_a_banner_is_drawn_in_the_colour_its_block_entity_names(self):
        from scaffold import core

        pack = core.Scaffold.__new__(core.Scaffold)
        # `Base` is the dye's own number, which runs the opposite way round
        # from wool's: 0 is black and 15 is white. An ominous banner and one
        # carrying patterns are not a dye at all and have sheets of their own.
        for base, colour in ((0, "black"), (6, "cyan"), (15, "white")):
            entity = {"id": "Banner", "Base": base}
            data = core.Scaffold._process_block(
                pack, {"name": "minecraft:standing_banner",
                       "states": {"ground_sign_direction": 0}}, entity)[4]
            self.geo.blocks = {}
            self.geo.uv_map = {}
            self.geo.uv_array = None
            self.geo.make_block(0, 0, 0, "standing_banner", rot=0, data=data)
            # the cloth and the post read the same sheet, the post through a
            # corner of its own
            self.assertEqual(
                {n.split("/")[-1].split("#")[0] for n in self.geo.uv_map},
                {"banner_%s" % colour})

        ## A marked banner reads its own sheet, and may borrow one more for its
        ## edges: a sheet's plain cloth is what vanilla dyes from rather than
        ## what the banner reads as, and the ominous sheet's is a light grey
        ## against a dark face, so it takes black's cloth instead. Nothing else
        ## may creep in, which is what the set comparison is for.
        from tools.blocks.banners import BANNER_EDGE

        for entity, colour in (({"id": "Banner", "Base": 0, "Type": 1},
                                "illager"),
                               ({"id": "Banner", "Base": 0,
                                 "Patterns": [{"Color": 1}]}, "designed")):
            data = core.Scaffold._process_block(
                pack, {"name": "minecraft:standing_banner",
                       "states": {"ground_sign_direction": 0}}, entity)[4]
            self.geo.blocks = {}
            self.geo.uv_map = {}
            self.geo.uv_array = None
            self.geo.make_block(0, 0, 0, "standing_banner", rot=0, data=data)
            allowed = {"banner_%s" % colour}
            borrowed = BANNER_EDGE.get(colour)
            if borrowed:
                allowed.add("banner_%s" % borrowed)
            self.assertEqual(
                {n.split("/")[-1].split("#")[0] for n in self.geo.uv_map},
                allowed)

    def test_a_banner_with_a_design_hangs_it_across_a_grid_of_tiles(self):
        # only sixteen by sixteen of a texture becomes a tile and a quad reads
        # one tile, so a design on a single quad is a design at sixteen by
        # sixteen: less than vanilla draws a cloth at, and squashed square
        shapes = load("block_shapes")["standing_banner"]
        entry = load("block_uv")["standing_banner"]
        plain = shapes["0"]["size"]

        def design_corner(name):
            """The tile a design quad reads, or None for the post and the bar.

            The design is written under vanilla's own 64 tall sheet, so a corner
            at or below that is one of its tiles and everything above it is the
            wood the banner hangs on.
            """
            if "#" not in name:
                return None
            across, down = (int(n) for n in name.split("#")[1].split(","))
            return (across, down) if down >= 64 else None
        for form in ("illager", "designed"):
            tiles = [name for name in entry[form]["overwrite"]["south"]
                     if "banner_%s#" % form in name]
            corners = [name.split("#")[1] for name in tiles]
            self.assertEqual(len(set(corners)), len(corners),
                             "%s reads one tile twice" % form)
            self.assertGreater(len(corners), len(plain) - 1,
                               "%s is still one quad" % form)

            # the design is laid out the way it is written: leftmost column at
            # the least x, top row at the greatest y
            placed = {}
            for index, name in enumerate(entry[form]["overwrite"]["south"]):
                corner = design_corner(name)
                if corner is None:
                    continue
                placed[corner] = shapes[form]["offsets"][index]
            for (across, down), at in placed.items():
                for (other_across, other_down), other in placed.items():
                    if other_across > across:
                        ## **Which way the columns run is still being settled in
                        ## game, so this only holds that they are consistent.**
                        ## The sheet holds the design mirrored and the block is
                        ## mirrored again across x on its way into the model, so
                        ## column order and tile mirroring are two halves of one
                        ## thing: turning one without the other gives the design
                        ## sliced rather than mirrored. What must not happen is
                        ## two quads landing on one column, which is what this
                        ## catches.
                        self.assertNotEqual(at[0], other[0],
                                            "%s puts two columns of its design "
                                            "in the same place" % form)
                    if other_down > down:
                        ## rows are untouched: a mirror is left to right
                        self.assertGreater(at[1], other[1],
                                           "%s runs its rows backwards" % form)

            # **The front turns its tile round and the back does not.** The
            # sheet holds the design mirrored, written that way on purpose, so
            # the face a banner is read from mirrors it back. The back needs
            # nothing: the two faces of a plane already run their windows in
            # opposite directions, so a plain window there shows the sheet
            # reversed once, which is the mirror of the front and is what a real
            # banner does. Turning the back as well cancels that reversal and
            # the two faces come out identical, which is what they were.
            for index, name in enumerate(entry[form]["overwrite"]["south"]):
                if design_corner(name) is None:
                    continue
                turned = [entry[form]["uv_sizes"][face][index][0] < 0
                          for face in ("south", "north")]
                self.assertEqual(
                    sorted(turned), [False, True],
                    "%s turns its tile the same way on both faces, so the back "
                    "is a copy of the front rather than its mirror" % form)

            # and only those two carry the picture. The other four are the
            # cloth's edges and the seams between the quads, a pixel wide, and
            # the design squashed down one is a stripe of noise. They take the
            # banner's own base colour, from the corner a dyed banner reads.
            plain_corner = None
            for face in ("east", "west", "up", "down"):
                for index, name in enumerate(entry[form]["overwrite"][face]):
                    if "#" not in name:
                        continue
                    self.assertIsNone(
                        design_corner(name),
                        "%s reads the design on its %s, which is an edge"
                        % (form, face))
                    plain_corner = plain_corner or name
            self.assertIsNotNone(plain_corner,
                                 "%s has no cloth on its edges at all" % form)

    def test_a_head_on_the_floor_turns_with_its_block_entity(self):
        # the states say only which of the six faces a head is fixed to; a head
        # standing on the floor keeps its sixteen steps in the block entity
        from scaffold import core

        entity = {"id": "Skull", "Rotation": 90.0}
        rot = core.Scaffold._process_block(
            core.Scaffold.__new__(core.Scaffold),
            {"name": "minecraft:skeleton_skull",
             "states": {"facing_direction": 1}}, entity)[0]
        self.assertEqual(rot, "spin4", "ninety degrees is the fourth step")
        # and it is named apart from the facings, which are numbers too
        self.assertNotEqual(rot, 4)

    def test_a_sheet_texture_is_read_a_window_at_a_time(self):
        # A hanging sign's texture is an entity sized sheet carrying the bar,
        # the chains and the board one under the other, and only the top left
        # 16x16 of a texture becomes a tile. Each part names the window it
        # needs, and each window is a tile of its own.
        self.assertEqual(asgc.split_window("blocks/oak"), ("blocks/oak", (0, 0)))
        self.assertEqual(asgc.split_window("blocks/oak#4,12"),
                         ("blocks/oak", (4, 12)))

        self.cubes("oak_hanging_sign", data="0-0")
        self.cubes("oak_hanging_sign", data="0-1")
        windows = [name for name in self.geo.uv_map if "#" in name]
        self.assertEqual(len(set(windows)), 3,
                         "the board, the bar and the chains are three windows")
        self.assertEqual(len(set(self.geo.uv_map[name] for name in windows)), 3,
                         "each window should be a tile of its own")

    def test_a_shelf_is_the_case_its_sheet_draws(self):
        # `shapes/shelf_facing_east.json` in bedrock-samples gives the block a
        # bottom board four thick and five deep, a back three deep, and a top
        # board four thick reaching out to the same five. The sheet's front
        # quarter agrees row for row: a rail over rows 0 to 3, the compartments
        # through rows 4 to 11, a rail over rows 12 to 15, parted by a lit pixel
        # at x5 and x10, which are painted on. So: two boards and a back, which
        # seen from the end is a C with nothing standing in it.
        shapes = load("block_shapes")["shelf"]["default"]
        self.assertEqual(len(shapes["size"]), 3,
                         "a floor, a ceiling and a back")
        deep = max(off[2] + size[2] for off, size
                   in zip(shapes["offsets"], shapes["size"]))
        self.assertAlmostEqual(deep, 5 / 16,
                               msg="the voxel shape is five deep")
        boards = [size for size in shapes["size"] if size[2] == 5 / 16]
        self.assertEqual([size[1] for size in boards], [0.25, 0.25],
                         "the two boards are four thick")
        back = [size for size in shapes["size"] if size[2] != 5 / 16]
        self.assertEqual(back, [[1, 0.5, 3 / 16]],
                         "the back is three deep and half the block tall")

    def test_a_shelf_shows_a_different_face_on_each_side(self):
        # its texture is a sheet: the front with the compartments painted in,
        # planks beside it for everything that looks out of the block, and the
        # shaded interior across the bottom half for the faces that look into a
        # compartment. Taking the whole tile puts the compartments on all six.
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "oak_shelf", rot="south")
        cubes = list(self.geo.blocks.values())[0]["cubes"]
        # a board shows all three regions: the front picture forward, planks
        # backward and to the sides, the shaded interior on the one face that
        # looks into a compartment
        cube = max(cubes, key=lambda one: one["origin"][1])
        # a face's v runs from the top of the tile it reads, so the whole part
        # of it names the tile and the fraction is the window within it
        tiles = {face: int(cube["uv"][face]["uv"][1])
                 for face in ("north", "south", "east", "west", "up", "down")}
        self.assertNotEqual(tiles["north"], tiles["south"],
                            "the back of a shelf is not its front")
        self.assertEqual(len(set(tiles.values())), 3,
                         "the front, the planks and the interior")
        self.assertEqual(tiles["north"], tiles["up"],
                         "the outward faces are all planks")
        self.assertEqual(tiles["up"], tiles["east"], "both planks, one tile")
        self.assertNotIn(tiles["down"], (tiles["north"], tiles["south"]),
                         "the ceiling's underside reads the shaded half")

    def test_a_window_larger_than_its_texture_is_ignored(self):
        # every wood has its own sheet, and a block whose texture is a plain
        # terrain tile must not end up reading blank space past the bottom of it
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "hanging_sign", data="0-1")
        self.assertTrue(self.geo.blocks)

    def test_a_turned_block_needs_one_bone_and_not_one_per_cube(self):
        # a cube that turns on its own goes into a bone carrying the block's own
        # turn, and every such cube of one block takes the same turn about the
        # same pivot, so they share the bone
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "campfire", rot="east", data="0")
        nested = [group for name, group in self.geo.blocks.items()
                  if "___" in name]
        self.assertEqual(len(nested), 1, "one bone for the block, not one a cube")
        self.assertEqual(len(nested[0]["cubes"]), 2, "both flame quads are in it")
        self.assertEqual(nested[0]["rotation"], [0, 270, 0])

    def test_a_cube_that_turns_on_its_own_is_drawn_once(self):
        # a cube carrying its own rotation goes into a nested bone, and leaving
        # it in the slice as well draws every campfire and statue twice
        for name, variant in (("campfire", "0"), ("copper_golem_statue", "1")):
            plain = self.cubes(name, data=variant)
            turned = self.cubes(name, data=variant, rot="east")
            self.assertEqual(len(plain), len(turned),
                             "%s gains cubes when it is turned" % name)

    def test_a_wall_mounting_sits_against_the_wall_behind_it(self):
        # A block fixed to a wall fills the near side of its own block, so the
        # wall is the block behind it and the face looks along +z, which is
        # where the rotation tables put south. Mounted at the far side instead,
        # the block is drawn against the wall opposite the one it is on and
        # every one of its four facings is half a turn out.
        shapes = load("block_shapes")
        for family, variant in (("wall_sign", "default"), ("shelf", "default"),
                                ("bell", "side"), ("grindstone", "side"),
                                ("tripwire_hook", "0-0")):
            form = shapes[family][variant]
            ## a tripwire hook's shaft leans, and the box it is cut from starts
            ## a hair outside the block before it turns; the plate on the wall
            ## is what has to sit at z 0
            offsets = (form["offsets"][:1] if family == "tripwire_hook"
                       else form["offsets"])
            nearest = min(off[2] for off in offsets)
            self.assertEqual(nearest, 0,
                             "%s %s is mounted on the far wall"
                             % (family, variant))

    def test_a_tripwire_hook_leans_by_what_is_tied_to_it(self):
        # attached_bit and powered_bit are both shape states, so a hook with
        # nothing on it, one with a wire pulling on it and one engaged are three
        # lists of cubes rather than one turned. The plate is the same in all
        # three, and the shaft is what leans.
        shapes = load("block_shapes")["tripwire_hook"]
        leans = {name: form["rotation"][1][0]
                 for name, form in shapes.items() if name != "default"}
        self.assertEqual(len(set(leans.values())), 3,
                         "two of the three forms lean the same way")
        self.assertGreater(leans["0-0"], 0, "a loose hook points down")
        self.assertLess(leans["1-1"], leans["1-0"],
                        "an engaged hook does not drop past a tied one")
        plates = {tuple(form["offsets"][0]) for form in shapes.values()}
        self.assertEqual(len(plates), 1, "the plate moved between states")

    def test_a_rod_wears_its_own_texture_on_each_of_its_pieces(self):
        # a lightning rod is a wide base with a thin rod out of it, and the two
        # are the wrong way round from the end rod its table was written beside.
        # Reading the UV list in the shape list's order gives the base the rod's
        # long stripe and stretches the base's square along the rod.
        shapes = load("block_shapes")["lightning_rod"]["default"]
        uv = load("block_uv")["lightning_rod"]["default"]
        for index, size in enumerate(shapes["size"]):
            for face, (across, down) in (("south", (0, 1)), ("up", (0, 2))):
                self.assertEqual(uv["uv_sizes"][face][index],
                                 [size[across], size[down]],
                                 "cube %d reads the wrong window for %s"
                                 % (index, face))

    def test_a_piglins_ears_stand_away_from_its_head(self):
        # the ears are bones the game turns thirty degrees about their own
        # pivots, and a head built from the cubes alone leaves them flat against
        # the skull. Each ear has to end up outside the head box and the two
        # have to be mirror images of each other.
        shapes = load("block_shapes")["skull_piglin"]["default"]
        turns = [tuple(r) for r in shapes["rotation"]]
        ears = [i for i, turn in enumerate(turns) if any(turn)]
        self.assertEqual(len(ears), 2, "a piglin has two turned ears")

        head = 0     # the skull itself is the first and largest cube
        left_edge = shapes["offsets"][head][0]
        right_edge = left_edge + shapes["size"][head][0]
        for ear in ears:
            near = shapes["offsets"][ear][0]
            far = near + shapes["size"][ear][0]
            self.assertTrue(near < left_edge or far > right_edge,
                            "an ear is tucked inside the head")

        one, other = ears
        self.assertEqual(turns[one], tuple(-a for a in turns[other]),
                         "the ears turn the same way as each other")
        self.assertAlmostEqual(
            shapes["offsets"][one][0] + shapes["size"][one][0] / 2.0
            + shapes["offsets"][other][0] + shapes["size"][other][0] / 2.0,
            1.0, places=4, msg="the ears are not a mirrored pair")

    def test_a_flower_pot_is_hollow_and_wears_the_pot(self):
        # it was one cube of the compost tile, which is a brown block with
        # nothing pot shaped about it. Four walls a pixel thick with the soil
        # sunk inside them is what the block is.
        cubes = self.cubes("flower_pot")
        self.assertEqual(len(cubes), 5, "four walls and the soil")
        for _at, size in cubes:
            self.assertLess(min(size), 0.375,
                            "a piece of the pot is as thick as the pot")
        # the soil is the short one, and it stops below the rim
        soil = min(cubes, key=lambda cube: cube[1][1])
        walls = [cube for cube in cubes if cube is not soil]
        self.assertLess(soil[1][1], min(size[1] for _at, size in walls),
                        "the soil comes up to the rim")

        written = load("block_uv")["flower_pot"]["default"]["overwrite"]
        for face, textures in written.items():
            self.assertNotIn("textures/blocks/compost", textures,
                             "the %s face still reads the compost tile" % face)

    def test_what_is_planted_in_a_pot_is_drawn_with_it(self):
        # a flower pot keeps its contents in the block entity beside it, as a
        # whole block with a name and states of its own, so the plant is drawn
        # where the pot is and by whatever family it belongs to
        from scaffold import core

        pot = {"name": "minecraft:flower_pot", "states": {}}
        alone = core.Scaffold._drawn_at(pot, {"id": "FlowerPot"})
        self.assertEqual(len(alone), 1, "an empty pot draws only the pot")

        planted = core.Scaffold._drawn_at(pot, {
            "id": "FlowerPot",
            "PlantBlock": {"name": "minecraft:red_flower",
                           "states": {"flower_type": "orchid"}}})
        self.assertEqual(len(planted), 2)
        self.assertEqual(planted[0][0], pot)
        self.assertEqual(planted[1][0]["name"], "minecraft:red_flower")
        self.assertEqual(planted[1][1], {},
                         "the plant is not handed the pot's own entity")

        # and every block without one is unaffected
        plain = {"name": "minecraft:stone", "states": {}}
        self.assertEqual(core.Scaffold._drawn_at(plain, {}),
                         [(plain, {})])

    def test_a_decorated_pot_names_the_part_of_its_sheet_each_face_reads(self):
        # `decorated_pot_base` is a 32x32 sheet holding the neck's unwrap over
        # the body's top and bottom, not a terrain tile. A face left to work its
        # window out from where its cube sits reads the neck's unwrap and the
        # empty row between the two, and the pot comes out with holes in it.
        cubes = self.cubes("decorated_pot")
        self.assertEqual(len(cubes), 2, "a body and a neck")
        body, neck = sorted(cubes, key=lambda cube: -cube[1][0])
        self.assertLess(neck[1][0], body[1][0], "the neck is the narrower one")
        self.assertEqual(neck[0][1], body[0][1] + body[1][1],
                         "the neck sits on the body")
        self.assertEqual(body[1][1] + neck[1][1], 1.0,
                         "the two together are a block tall")

        entry = load("block_uv")["decorated_pot"]["default"]
        written = entry["overwrite"]
        for face in ("up", "down", "north", "south", "east", "west"):
            for index, texture in enumerate(written[face]):
                self.assertNotEqual(texture, "default",
                                    "cube %d reads %s as a plain tile"
                                    % (index, face))
        # the body's four walls take the wall texture; the other eight faces
        # each read a different part of the sheet. A corner can be shared, since
        # a corner is only pulled back far enough for its region to fit inside
        # the tile, but no two of them may land on the same window.
        regions = set()
        for face in ("up", "down", "north", "south", "east", "west"):
            for index, texture in enumerate(written[face]):
                if "#" not in texture:
                    continue
                regions.add((texture, tuple(entry["offset"][face][index]),
                             tuple(entry["uv_sizes"][face][index])))
        self.assertEqual(len(regions), 8,
                         "two faces of the sheet read the same window")

    def test_a_pot_and_its_plant_are_both_drawn(self):
        self.geo.blocks = {}
        self.geo.make_block(0, 0, 0, "flower_pot")
        pot = sum(len(group["cubes"]) for group in self.geo.blocks.values())
        self.geo.make_block(0, 0, 0, "poppy")
        both = sum(len(group["cubes"]) for group in self.geo.blocks.values())
        self.assertGreater(both, pot, "the plant added nothing to the pot")

    def test_a_head_on_the_floor_starts_half_a_turn_round(self):
        # A block at rest faces south. A skull whose block entity Rotation is
        # zero faces north, which is why every floor turn carries the extra
        # half; without it every head in a build faces away from where it was
        # placed. That is an observation from the game rather than something
        # the tables can be read for, so it is written down here.
        turns = load("block_rotation")["skull_player"]
        self.assertEqual(turns["spin0"], [0, 180, 0])
        # and the plain facing, which a floor head with no block entity beside
        # it falls back to, has to be the same turn as the first step
        self.assertEqual(turns["1"], turns["spin0"])
        # the sixteen steps go the whole way round, once each
        steps = [tuple(turns["spin%d" % n]) for n in range(16)]
        self.assertEqual(len(set(steps)), 16)




class TurnedTileTests(unittest.TestCase):
    """A face that reads its picture a quarter round.

    Bedrock's per-face UV is a corner and a size: a negative size mirrors an
    axis and there is no angle in it at all. So a turn cannot be asked for in
    the geometry and is baked into the tile on the way into the atlas instead,
    with the angle travelling in the texture's name the way a window and a tint
    already do.
    """

    def test_the_mark_reads_alongside_a_window_and_a_tint(self):
        from scaffold.pack.armor_stand_geo_class import (
            split_tint, split_turn, split_window)

        self.assertEqual(split_turn("blocks/a")[1], 0)
        self.assertEqual(split_turn("blocks/a^90")[1], 90)
        # a name may carry all three, and each has to see past the others
        whole = "blocks/a#4,8^270~ff0000"
        self.assertEqual(split_turn(whole), ("blocks/a#4,8", 270))
        self.assertEqual(split_window(whole), ("blocks/a", (4, 8)))
        self.assertEqual(split_tint(whole)[1], (255, 0, 0))

    def test_an_angle_that_is_not_a_right_angle_is_no_turn(self):
        # the tables are written by hand, and a wrong number should draw the
        # block rather than stop the build
        from scaffold.pack.armor_stand_geo_class import split_turn

        self.assertEqual(split_turn("blocks/a^45")[1], 0)
        self.assertEqual(split_turn("blocks/a^nonsense")[1], 0)

    def test_a_window_that_turns_is_refused_a_half_angle_as_it_is_written(self):
        # and the generator says so outright, because a table it writes is read
        # by everything afterwards
        from tools.blocks.geometry import Cube

        self.assertRaises(ValueError,
                          Cube((1, 1, 1), (0, 0, 0), "x",
                               window={"up": (0, 0, 16, 16, 45)}).paint, "up")

    def test_the_tile_in_the_atlas_is_the_straight_one_turned(self):
        from numpy import array_equal, rot90
        from scaffold.pack import armor_stand_geo_class as asgc

        source = os.path.join(paths.vanilla_pack(),
                              "textures/blocks/lectern_sides.png")
        geo = asgc.ArmorStandGeo("turn", offsets=[0, 0, 0])
        geo.alpha = 1.0

        geo.uv_array = None
        geo.extend_uv_image(source, (0, 0), None, 0)
        straight = geo.uv_array[:16, :16, :3].copy()

        ## the mark is read clockwise and rot90 turns the other way
        for degrees, quarters in ((90, -1), (180, 2), (270, 1)):
            geo.uv_array = None
            geo.extend_uv_image(source, (0, 0), None, degrees)
            self.assertTrue(
                array_equal(geo.uv_array[:16, :16, :3],
                            rot90(straight, quarters)),
                "a %d turn is not the straight tile turned" % degrees)

    def test_a_turned_tile_does_not_displace_the_straight_one(self):
        # the atlas is keyed by the whole name, so a block reading a texture
        # both ways gets a tile of each rather than one that has to be both
        from scaffold.pack import armor_stand_geo_class as asgc

        geo = asgc.ArmorStandGeo("turn", offsets=[0, 0, 0])
        geo.make_block(0, 0, 0, "lectern", rot=0)
        sides = [name for name in geo.uv_map if "lectern_sides" in name]
        self.assertIn("textures/blocks/lectern_sides", sides)
        self.assertIn("textures/blocks/lectern_sides"
                      + asgc.TURN_MARK + "90", sides)


class GeometryDetailTests(unittest.TestCase):
    """The low geometry setting, and the simplified shapes it reaches for."""

    def tables(self):
        import json
        from scaffold import paths
        with open(paths.lookup("block_shapes.json")) as handle:
            shapes = json.load(handle)
        with open(paths.lookup("block_uv.json")) as handle:
            uv = json.load(handle)
        return shapes, uv

    def test_every_simplified_shape_is_in_both_tables(self):
        # a family described in one table and not the other silently falls back
        # to default, which is how a half-height cube ends up wearing a
        # full-height texture
        from scaffold.pack import armor_stand_geo_class as asgc

        shapes, uv = self.tables()
        for name in shapes:
            if name.endswith(asgc.LOW_SUFFIX):
                self.assertIn(name, uv, "%s has a shape but no UV" % name)
        for name in uv:
            if name.endswith(asgc.LOW_SUFFIX):
                self.assertIn(name, shapes, "%s has a UV but no shape" % name)

    def test_a_simplified_shape_is_simpler(self):
        from scaffold.pack import armor_stand_geo_class as asgc

        shapes, _uv = self.tables()
        found = 0
        for name, body in shapes.items():
            if not name.endswith(asgc.LOW_SUFFIX):
                continue
            found += 1
            detailed = shapes[name[:-len(asgc.LOW_SUFFIX)]]["default"]["size"]
            self.assertLess(len(body["default"]["size"]), len(detailed),
                            "%s is no simpler than what it replaces" % name)
        self.assertGreater(found, 0, "no simplified shapes at all")

    def test_the_setting_reaches_the_geometry(self):
        from scaffold.pack import armor_stand_geo_class as asgc

        plain = asgc.ArmorStandGeo("t", low_geometry=True)
        full = asgc.ArmorStandGeo("t", low_geometry=False)
        # a family with a simpler form is swapped, one without is left alone
        self.assertEqual(plain.simplify("bell"), "bell" + asgc.LOW_SUFFIX)
        self.assertEqual(full.simplify("bell"), "bell")
        self.assertEqual(plain.simplify("cube"), "cube")
        self.assertEqual(plain.simplify("ignore"), "ignore")


class ChiseledBookshelfTests(unittest.TestCase):
    def test_every_arrangement_of_books_is_described(self):
        # books_stored is a six bit number, so there are sixty-four of them
        import json
        from scaffold import paths
        with open(paths.lookup("block_shapes.json")) as handle:
            shapes = json.load(handle)["chiseled_bookshelf"]
        with open(paths.lookup("block_uv.json")) as handle:
            uv = json.load(handle)["chiseled_bookshelf"]
        for mask in range(64):
            self.assertIn(str(mask), shapes)
            self.assertIn(str(mask), uv)
            # the shelf itself, plus one panel for each book it holds
            self.assertEqual(len(shapes[str(mask)]["size"]),
                             1 + bin(mask).count("1"))

    def test_the_front_texture_is_one_that_exists(self):
        # blocks.json names chiseled_bookshelf_front, which no vanilla pack
        # ships and terrain_texture.json has no entry for
        import json
        import os
        from scaffold import paths
        with open(paths.lookup("block_uv.json")) as handle:
            uv = json.load(handle)["chiseled_bookshelf"]
        for mask in ("0", "63"):
            for texture in uv[mask]["overwrite"]["north"]:
                self.assertTrue(
                    os.path.isfile(os.path.join(paths.vanilla_pack(),
                                                texture + ".png")),
                    "%s is not in the vanilla pack" % texture)


class LayeringTests(unittest.TestCase):
    """The command line build has no interface in it, and must not grow one."""

    def reachable(self, start):
        """Every module in this tree that `start` can reach, directly or not."""
        import ast
        import io
        import os

        def imports_of(path):
            tree = ast.parse(io.open(path, encoding="utf-8").read())
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.add(node.module)
                    names |= {node.module + "." + a.name for a in node.names}
            return names

        def resolve(name):
            base = name.replace(".", os.sep)
            for candidate in (base + ".py", os.path.join(base, "__init__.py")):
                if os.path.isfile(candidate):
                    return candidate
            return None

        seen, queue = set(), [start]
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            for name in imports_of(path):
                found = resolve(name)
                if found and found not in seen:
                    queue.append(found)
        return seen

    def test_the_command_line_never_reaches_the_window(self):
        import os
        reached = self.reachable(os.path.join("scaffold", "cli", "__main__.py"))
        inside = os.path.join("scaffold", "ui") + os.sep
        window = sorted(p for p in reached if p.startswith(inside))
        self.assertEqual(window, [],
                         "the command line build pulls in %s" % window)

    def test_the_command_line_package_imports_no_interface(self):
        import io
        import os
        folder = os.path.join("scaffold", "cli")
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".py"):
                continue
            body = io.open(os.path.join(folder, name), encoding="utf-8").read()
            where = "scaffold/cli/%s" % name
            self.assertNotIn("from scaffold.ui import", body, where)
            for line in body.split("\n"):
                self.assertNotEqual(line.strip(), "from scaffold import ui", where)

    def test_both_entry_points_share_one_argument_parser(self):
        # a script written against one build has to run against the other
        from scaffold import cli
        first = cli.arguments.parse(["--structure", "a", "--pack_name", "b"])
        self.assertEqual(first.tech_pack, "none")
        self.assertFalse(first.low_geometry)
        self.assertEqual(first.structure, "a")

    def test_nothing_to_do_is_reported_rather_than_guessed(self):
        # the entry points answer it differently, so cli.main must not decide
        from scaffold import cli
        self.assertEqual(cli.main([]), cli.NOTHING_ASKED)


if __name__ == "__main__":
    unittest.main()
