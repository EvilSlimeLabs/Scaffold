"""The Structura 1.7 export: what it tells Structura, and how it lays forms out."""
import unittest

from scaffold import block_geometry
from tools.checks import gallery
from tools.export import structura


class RoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _states, cls.values = gallery.mojang()
        cls.order = structura.roles(block_geometry.rules(), cls.values,
                                    {"top_slot_bit": ("minecraft:vertical_half", [0, 1]),
                                     "color": (None, ["red", "white"])})

    def test_no_word_is_read_as_a_number(self):
        # Structura runs a data state through int() outside any try, so one
        # block carrying a word there ends the whole build
        for state, role in self.order.items():
            if role in ("data", "top") and state in self.values:
                with self.subTest(state=state):
                    self.assertTrue(all(isinstance(v, (bool, int))
                                        for v in self.values[state]))

    def test_a_slabs_half_is_a_rotation(self):
        # bool() of "bottom" is True, so the half cannot be a top flag
        self.assertEqual(self.order[structura.HALF], "rot")
        self.assertEqual(self.order["top_slot_bit"], "top")

    def test_an_old_split_by_a_word_is_a_variant(self):
        self.assertEqual(self.order["color"], "variant")


class ReadTests(unittest.TestCase):
    def test_the_last_state_of_a_role_wins(self):
        order = {"a": "data", "b": "data", "facing_direction": "rot"}
        rot, top, variant, data = structura.reads(
            {"a": 1, "b": 2, "facing_direction": 3}, order, "x")
        self.assertEqual((rot, top, variant, data), (3, False, "default", "2"))

    def test_a_rail_joins_its_direction_and_its_bit(self):
        order = {"rail_direction": "rot", "rail_data_bit": "data"}
        self.assertEqual(structura.reads({"rail_direction": 3}, order, "rail")[3], "3")

    def test_wood_reads_its_kind_and_whether_it_is_stripped(self):
        got = structura.reads({"wood_type": "oak", "stripped_bit": 1}, {}, "wood")
        self.assertEqual(got[2], ["wood", "oak_stripped"])

    def test_a_hopper_on_its_side_draws_its_side_form(self):
        self.assertEqual(structura.fallback("hopper", 2, False), "side")
        self.assertEqual(structura.fallback("hopper", 0, True), "top")
        self.assertEqual(structura.fallback("cube", 2, False), "default")


def cube(windows, texture="t", offset=(0, 0, 0), size=(1, 1, 1)):
    faces = {f: [list(windows), [1, 1], texture] for f in structura.FACES}
    return {"size": list(size), "offset": list(offset), "rotation": None, "faces": faces}


class LayOutTests(unittest.TestCase):
    def test_every_cube_reads_its_own_windows_from_the_shared_slots(self):
        # Structura reads a data form's windows from default, so a data form
        # whose cubes sit at other windows has to find them in default's list
        forms = {"default": {"center": [0.5, 0.5, 0.5], "cubes": [cube((0, 0))]},
                 "1": {"center": [0.5, 0.5, 0.5],
                       "cubes": [cube((0.5, 0), "a"), cube((0, 0), "b")]}}
        shapes, uvs = structura.lay_out(forms)
        windows = uvs["default"]["offset"]["up"]
        for name, content in forms.items():
            sizes = shapes[name]["size"]
            textures = uvs[name]["overwrite"]["up"]
            drawn = sorted((tuple(windows[i]), textures[i])
                           for i in range(len(sizes)) if any(sizes[i]))
            wanted = sorted((tuple(c["faces"]["up"][0]), c["faces"]["up"][2])
                            for c in content["cubes"])
            with self.subTest(form=name):
                self.assertEqual(drawn, wanted)

    def test_a_slot_a_form_skips_holds_a_cube_of_no_size(self):
        forms = {"default": {"center": [0, 0, 0], "cubes": [cube((0, 0)), cube((0.5, 0))]},
                 "1": {"center": [0, 0, 0], "cubes": [cube((0.5, 0))]}}
        shapes, _uvs = structura.lay_out(forms)
        self.assertEqual(sum(1 for s in shapes["1"]["size"] if any(s)), 1)


class FlipTests(unittest.TestCase):
    def test_a_half_turn_lands_a_bottom_slab_on_a_top_one(self):
        bottom = {"center": [0.475, 0.2375, 0.475],
                  "cubes": [cube((0, 0), offset=(0, 0, 0), size=(0.95, 0.5, 0.95))]}
        top = {"center": [0.475, 0.7, 0.475],
               "cubes": [cube((0, 0), offset=(0, 0.45, 0), size=(0.95, 0.5, 0.95))]}
        self.assertEqual(structura.flipped(bottom, top), [0.475, 0.475, 0.475])

    def test_two_shapes_no_half_turn_relates_are_left_alone(self):
        bottom = {"center": [0, 0, 0], "cubes": [cube((0, 0), size=(1, 0.5, 1))]}
        top = {"center": [0, 0, 0], "cubes": [cube((0, 0), offset=(0, 0.45, 0),
                                                   size=(1, 0.25, 1))]}
        self.assertIsNone(structura.flipped(bottom, top))


class OlderTests(unittest.TestCase):
    def test_an_old_split_id_comes_back_with_the_state_it_was_split_by(self):
        found = structura.older("red_wool", {})
        self.assertIn(("wool", {"color": "red"}), found)

    def test_an_old_state_comes_back_with_its_old_value(self):
        found = structura.older("oak_slab", {"minecraft:vertical_half": "top"})
        self.assertIn(("oak_slab", {"top_slot_bit": 1}), found)


if __name__ == "__main__":
    unittest.main()
