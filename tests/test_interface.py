import os
import re
import sys
import unittest

from scaffold import settings
from scaffold import lang_parse
def open_window():
    """A fresh App, or a skip when there is no display to put one on.

    The drawn glyphs and the fonts are cached at module level and belong to the
    Tk root that was alive when they were made, so a second window in the same
    process finds the first one's images and cannot use them. Tests get a clean
    slate rather than the leftovers of whichever test ran first.
    """
    from scaffold.ui import scaffold_gui

    scaffold_gui._image_cache.clear()
    del scaffold_gui._fonts[:]
    try:
        return scaffold_gui.App()
    except Exception as complaint:
        raise unittest.SkipTest("no window: %s" % complaint)

def settle(app, passes=6):
    """Let the window actually lay itself out.

    update_idletasks alone leaves some widgets at their unplaced size, which
    reads as a zero height rather than as an error.
    """
    for _ in range(passes):
        app.update()

class TransparencyTests(unittest.TestCase):
    """The slider is transparency; everything downstream wants alpha."""

    def test_the_ends_of_the_slider(self):
        self.assertEqual(settings.transparency_to_alpha(0), 1.0)
        self.assertAlmostEqual(settings.transparency_to_alpha(100), 0.0)

    def test_the_default_is_the_same_number_everywhere(self):
        # the window, the CLI's --opacity and the core's own default all have to
        # land on the same ghost block, or a pack built one way looks different
        # from the same pack built another
        from scaffold.pack import armor_stand_geo_class as asgc

        alpha = settings.transparency_to_alpha(settings.DEFAULT_TRANSPARENCY)
        self.assertAlmostEqual(alpha, asgc.DEFAULT_ALPHA)
        self.assertAlmostEqual(settings.DEFAULT_OPACITY / 100, alpha)

    def test_the_slider_never_reaches_fully_invisible(self):
        self.assertLess(settings.MAX_TRANSPARENCY, 100)


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.langs = settings.read_languages()

    def test_a_language_is_named_by_its_locale(self):
        # named the way Minecraft names its own, a language and a region. The
        # language part is ISO 639-1 where it has one and 639-2 where it does
        # not, which is ceb for Cebuano; the special languages take Minecraft's own
        # codes, which is why four of them are English underneath.
        for locale in settings.langs:
            self.assertRegex(locale, r"^[a-z]{2,3}_[A-Za-z]{2,3}$",
                             "%s is not a locale" % locale)

    def test_every_language_says_what_it_is_called(self):
        # the name is in the file, in the language itself, so a new column is a
        # whole language and nothing about it lives anywhere else
        for code in settings.choices():
            name = settings.language_name(code)
            self.assertTrue(name and name != code,
                            "%s does not name itself" % code)

    def test_a_language_remembered_by_name_still_resolves(self):
        # Scaffold stored the name rather than the code until 3.0
        self.assertEqual(settings.language_code("Español"), "es_ES")
        self.assertEqual(settings.language_code("LOLCAT"), "lol_US")
        self.assertIsNone(settings.language_code("Klingon"))

    def test_every_language_has_colours_and_they_differ_by_language(self):
        from scaffold.ui import lang_icons

        seen = {}
        for code in settings.choices():
            palette = lang_icons.colour(code)
            self.assertTrue(1 <= len(palette) <= 3,
                            "%s has %d colours" % (code, len(palette)))
            for rgb in palette:
                self.assertEqual(len(rgb), 3)
            seen[code] = palette
        # a badge that looks like every other badge is not identifying anything
        self.assertGreater(len(set(map(str, seen.values()))), len(seen) // 2)

    def test_english_comes_first_and_the_rest_are_in_name_order(self):
        # English is the source the rest are translated from and the fallback
        # for anything missing, so it leads; everything else is alphabetical by
        # its own name, wherever a language file turns up
        offered = settings.choices()
        self.assertEqual(offered[0], "en_US")
        names = [settings.language_name(code).casefold() for code in offered[1:]]
        self.assertEqual(names, sorted(names))

    def test_an_unlisted_language_falls_back_to_the_default_colour(self):
        from scaffold.ui import lang_icons

        table = lang_icons.colours()
        self.assertIn(lang_icons.DEFAULT_KEY, table)
        expected = [tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                    for c in table[lang_icons.DEFAULT_KEY][:3]]
        self.assertEqual(lang_icons.colour("zzz"), expected)

    def test_english_fills_gaps_in_another_language(self):
        strings = settings.language("es_ES")
        english = settings.langs["en_US"]
        self.assertEqual(set(strings), set(english))
        self.assertTrue(all(strings.values()))

    def test_the_placeholder_column_is_not_offered(self):
        self.assertNotIn("xx_XX", settings.choices())
        self.assertIn("en_US", settings.choices())

    def test_an_unknown_language_falls_back_rather_than_raising(self):
        strings = settings.language("tlh")
        self.assertEqual(strings, settings.langs["en_US"])


class StringCoverageTests(unittest.TestCase):
    """Every label the window asks for has to exist in the table.

    A missing key would put the raw lookup name on screen rather than a word,
    and nothing else would complain about it.
    """

    def test_every_key_the_window_uses_is_translated(self):
        with open(os.path.join("scaffold", "ui", "scaffold_gui.py"),
                  encoding="utf-8") as f:
            source = f.read()
        keys = set(re.findall(r'(?:self\.)?text\(\s*"([^"]+)"', source))
        keys |= set(re.findall(r'app\.text\(\s*"([^"]+)"', source))
        english = lang_parse.parse()["en_US"]
        # themes are looked up by their stored name
        keys |= set(settings.THEMES)
        # a key built by interpolation cannot be read out of the source; the
        # concrete forms are asserted separately below
        keys = {k for k in keys if "%" not in k}
        missing = sorted(k for k in keys if k not in english)
        self.assertEqual(missing, [], "strings used by the window but not translated")

    def test_the_interpolated_keys_exist_in_every_form(self):
        english = lang_parse.parse()["en_US"]
        for axis in "xyz":
            self.assertIn("axis %s" % axis, english)


class ThemeTests(unittest.TestCase):
    def test_system_is_the_default_and_dark_is_the_fallback(self):
        self.assertEqual(settings.DEFAULT_THEME, "system")
        self.assertEqual(settings.FALLBACK_THEME, "dark")
        self.assertIn(settings.FALLBACK_THEME, settings.THEMES)

    def test_an_undetectable_desktop_resolves_to_dark(self):
        from scaffold.ui import scaffold_gui

        real = scaffold_gui.darkdetect
        try:
            scaffold_gui.darkdetect = None
            self.assertEqual(scaffold_gui.resolve_theme("system"), "dark")
            self.assertEqual(scaffold_gui.resolve_theme("light"), "light")
        finally:
            scaffold_gui.darkdetect = real




class FontTests(unittest.TestCase):
    """The typeface ships with the program, and follows the language."""

    def test_the_bundled_files_are_present_with_their_licences(self):
        import os
        from scaffold.ui import ui_fonts

        for name in ui_fonts.FILES:
            self.assertTrue(os.path.isfile(ui_fonts.path(name)), name)
        for licence in ("LICENSE.txt", "NotoSansSC-LICENSE.txt"):
            self.assertTrue(os.path.isfile(ui_fonts.path(licence)),
                            "%s must travel with the fonts" % licence)

    def test_a_language_whose_script_is_not_covered_gets_its_own_face(self):
        from scaffold.ui import ui_fonts
        # Source Sans Pro has no CJK glyphs and is not the enchanting alphabet,
        # and Tk will not fall back to a privately registered font by itself
        self.assertNotEqual(ui_fonts.family("zh_CN"), ui_fonts.family("en_US"))
        self.assertNotEqual(ui_fonts.family("en_SGA"), ui_fonts.family("en_US"))
        self.assertEqual(ui_fonts.family("en_PT"), ui_fonts.family("en_US"))


class IconControlTests(unittest.TestCase):
    """The pack icon control: what it draws, and what answers the pointer."""

    def test_nothing_is_drawn_outside_the_frame(self):
        # the background and the preview are masked to the frame's own outline,
        # and the outline is cut out of that same mask, so no part of the
        # control may have any opacity where the mask has none
        from scaffold.ui import ui_icons
        from PIL import Image
        size, radius, width = 128, 14, 2
        art = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
        mask = ui_icons.frame_mask(size, radius, width)
        for cut in (False, True):
            control = ui_icons.icon_control(size, radius=radius, art=art,
                                            width=width, cut=cut)
            alpha = control.split()[3]
            for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
                self.assertEqual(
                    mask.getpixel((x, y)), 0,
                    "the mask should not reach the very corner")
                self.assertEqual(
                    alpha.getpixel((x, y)), 0,
                    "cut=%s leaves the control painted outside its frame at "
                    "%d,%d" % (cut, x, y))

    def test_the_clickable_corner_covers_the_drawn_one(self):
        # the cut is drawn small on purpose, which makes it a small target, so
        # the clickable corner is pushed out past it. Whatever else it does, it
        # has to accept every point the wedge is actually drawn over.
        from scaffold.ui import ui_icons

        size = 128
        top, side = ui_icons.WEDGE_TOP, ui_icons.WEDGE_SIDE
        for i in range(1, 10):
            for j in range(1, 10):
                fx, fy = top + (1 - top) * i / 10.0, side * j / 10.0
                if fy * (1 - top) < (fx - top) * side:      # inside the drawing
                    self.assertTrue(
                        ui_icons.in_wedge(fx * size, fy * size, size),
                        "the drawn wedge is not clickable at %.2f,%.2f" % (fx, fy))

    def test_the_clickable_corner_stays_in_its_corner(self):
        from scaffold.ui import ui_icons

        size = 128
        for x, y in ((size // 2, size // 2), (4, 4), (4, size - 4),
                     (size - 4, size - 4), (size // 2, size - 4)):
            self.assertFalse(ui_icons.in_wedge(x, y, size),
                             "%d,%d is not the corner" % (x, y))

    def test_the_pointer_reaches_every_part_of_the_control(self):
        # a CTkButton is a canvas with a label over it, and the label is not
        # made until an image is configured. Binding while the button is being
        # built therefore reaches only the canvas, and the label then covers all
        # but a one pixel rim, leaving the whole control unclickable.
        app = open_window()
        try:
            app.update_idletasks()
            app.refresh_icon_preview()
            app.update_idletasks()
            parts = [part for part in
                     (app.icon_button._canvas,
                      getattr(app.icon_button, "_image_label", None),
                      getattr(app.icon_button, "_text_label", None))
                     if part is not None]
            self.assertGreaterEqual(len(parts), 2,
                                    "the button should have a label over its canvas")
            for part in parts:
                for sequence in ("<Button-1>", "<Motion>", "<Leave>"):
                    self.assertTrue(
                        part.bind(sequence),
                        "%s on %s is not bound" % (sequence, part.winfo_class()))
        finally:
            app.destroy()


class RuneFaceTests(unittest.TestCase):
    """The Enchanting face has to fit the same controls the others do."""

    def face(self):
        from fontTools.ttLib import TTFont
        from scaffold import paths
        path = paths.data("fonts", "ScaffoldEnchanting.ttf")
        if not os.path.isfile(path):
            raise unittest.SkipTest("the rune face is not built")
        return TTFont(path)

    def test_the_runes_are_not_a_full_em_apart(self):
        # every glyph is drawn in a cell eight pixels across and no rune fills
        # more than five of them. An advance of one cell, which is what a
        # cell-sized em works out to, spaces them almost twice as far apart as
        # the letters of any other language, and the window's labels overflow.
        font = self.face()
        upem = font["head"].unitsPerEm
        widths = [font["hmtx"][name][0] for name in font.getGlyphOrder()
                  if font["hmtx"][name][0] > 0]
        self.assertTrue(widths, "the face has no advancing glyphs")
        average = sum(widths) / float(len(widths))
        self.assertLess(average, upem * 0.7,
                        "the runes average %.2f em apart" % (average / upem))

    def test_the_advances_vary_with_the_ink(self):
        # a single advance for every glyph is the mark of the cell width being
        # used instead of the glyph width
        font = self.face()
        widths = {font["hmtx"][name][0] for name in font.getGlyphOrder()}
        self.assertGreater(len(widths), 1, "every glyph has the same advance")

    def test_the_face_is_asked_for_smaller_than_the_interface_face(self):
        from scaffold.ui import ui_fonts

        self.assertLess(ui_fonts.scale("en_SGA"), 1.0)
        self.assertEqual(ui_fonts.scale("en_US"), 1.0)


class LanguageMenuTests(unittest.TestCase):
    def test_the_box_and_its_list_are_the_same_width(self):
        # a list narrower than the box it drops from, or wider, reads as two
        # controls rather than one
        app = open_window()
        try:
            app.update_idletasks()
            menu = app.language_menu
            menu.open()
            app.update_idletasks()
            # the size the list was placed at, not the size it reports: an
            # unmapped toplevel answers with Tk's default 200x200, which is what
            # hid half this list before it was given a size of its own. Reading
            # the mapped window instead would need the program to be the one in
            # use, which a test cannot ask for.
            wide, tall, _x, _y = menu.placed
            self.assertAlmostEqual(menu.winfo_width(), wide, delta=2)
            self.assertGreaterEqual(tall, menu.popup.winfo_reqheight() - 2)
            menu.close()
        finally:
            app.destroy()

    def test_both_selectors_are_the_same_kind_of_control(self):
        # the theme selector was a CTkOptionMenu: it lit only the strip its
        # arrow was in, drew its list with a border of its own, used a larger
        # font and dropped downward off the bottom of the window
        app = open_window()
        try:
            self.assertIs(type(app.theme_menu), type(app.language_menu))
            self.assertEqual(app.theme_menu.label.cget("font").cget("size"),
                             app.language_menu.label.cget("font").cget("size"))
            for menu in (app.theme_menu, app.language_menu):
                for part in menu.parts():
                    self.assertEqual(part.cget("cursor"), "hand2")
        finally:
            app.destroy()

    def test_the_list_is_placed_where_the_box_is(self):
        # not clamped to zero: a monitor left of or above the main one starts at
        # a negative coordinate, and clamping put the list on the other screen
        app = open_window()
        try:
            app.update_idletasks()
            menu = app.language_menu
            menu.open()
            app.update_idletasks()
            _wide, tall, x, y = menu.placed
            self.assertEqual(x, menu.winfo_rootx())
            self.assertEqual(y, menu.winfo_rooty() - tall - 4)
            menu.close()
        finally:
            app.destroy()

    def test_the_window_is_drawn_at_one_scale(self):
        # CustomTkinter otherwise makes the process per-monitor DPI aware and
        # rebuilds every widget at a new scale when a window changes monitor,
        # fading it out and back while it does, which does not survive a drag
        # between monitors intact
        import customtkinter
        from scaffold.ui import scaffold_gui                            # noqa: F401
        self.assertTrue(
            customtkinter.ScalingTracker.deactivate_automatic_dpi_awareness,
            "importing the window should have turned off automatic rescaling")

    def test_the_selectors_draw_their_whole_border(self):
        # CustomTkinter floors a frame's width and height to an even number
        # before drawing its rounded border, so a box that comes out an odd
        # number of pixels, which a scaled display will produce, loses its
        # bottom row and the outline looks broken along that edge
        app = open_window()
        try:
            for menu in (app.theme_menu, app.language_menu):
                engine = menu._draw_engine
                self.assertFalse(engine._round_width_to_even_numbers)
                self.assertFalse(engine._round_height_to_even_numbers)
        finally:
            app.destroy()

    def test_nothing_in_a_selector_covers_its_border(self):
        # a CTkLabel's "transparent" fills its rectangle with the colour behind
        # it rather than leaving those pixels alone, so a label as tall as the
        # box paints over the outline along the top and the bottom
        app = open_window()
        try:
            app.update_idletasks()
            for menu in (app.theme_menu, app.language_menu):
                edge = menu.winfo_height()
                border = menu.cget("border_width")
                for part in menu.parts():
                    if part is menu:
                        continue
                    self.assertGreaterEqual(part.winfo_y(), border)
                    self.assertLessEqual(part.winfo_y() + part.winfo_height(),
                                         edge - border)
        finally:
            app.destroy()

    def test_the_selectors_are_wide_enough_for_every_language(self):
        # the boxes are a fixed width now, so nothing measures whether the
        # longest label still fits inside one
        from scaffold.ui import scaffold_gui

        app = open_window()
        try:
            app.update_idletasks()
            for language in settings.choices():
                app.on_language(language)
                app.update_idletasks()
                for menu in (app.theme_menu, app.language_menu):
                    measure = menu.label.cget("font")
                    widest = max(measure.measure(menu.labels(value))
                                 for value in menu.values)
                    # measure() answers in real pixels and a width is in the
                    # window's own units, which are not the same on a scaled
                    # display
                    widest /= menu._get_widget_scaling() or 1.0
                    room = menu.cget("width") - (
                        scaffold_gui.BOX_PAD
                        + (scaffold_gui.BADGE + 7 if menu.badges else 0)
                        + 4 + scaffold_gui.CHEVRON + scaffold_gui.BOX_PAD)
                    self.assertLessEqual(
                        widest, room,
                        "%s clips in %s: %d into %d" % (
                            menu.labels(menu.values[0]), language, widest, room))
        finally:
            app.destroy()

    def test_the_pack_name_hint_moves_nothing_when_it_appears(self):
        # the hint holds its row whether or not it has anything to say: taken
        # out of the layout when silent, everything below it jumped up and down
        # as the pack name was typed and cleared
        app = open_window()
        try:
            app.update_idletasks()
            app.pack_name_var.set("a pack")
            app.update_idletasks()
            quiet = [w.winfo_rooty() for w in
                     (app.desc_label, app.trans_label, app.make_button)]
            app.pack_name_var.set("")
            app.update_idletasks()
            complaining = [w.winfo_rooty() for w in
                           (app.desc_label, app.trans_label, app.make_button)]
            self.assertEqual(quiet, complaining)
            self.assertTrue(app.name_hint.cget("text"))
        finally:
            app.destroy()

    def test_the_hint_row_is_tall_enough_for_its_own_text(self):
        app = open_window()
        try:
            app.update_idletasks()
            hint = app.name_hint
            self.assertGreaterEqual(hint.winfo_height(),
                                    hint.cget("font").metrics("linespace"))
        finally:
            app.destroy()

    def test_a_list_is_inset_the_same_at_both_ends(self):
        app = open_window()
        try:
            app.update_idletasks()
            menu = app.theme_menu
            menu.open()
            app.update_idletasks()
            # read from how the rows were packed rather than from where they
            # landed: an unmapped toplevel has not laid its children out, and
            # mapping one needs the program to be the one in use
            from scaffold.ui import scaffold_gui

            rows = menu.popup.winfo_children()[0].winfo_children()
            first = rows[0].pack_info()["pady"]
            last = rows[-1].pack_info()["pady"]
            self.assertEqual(int(first[0]), int(last[1]),
                             "the list is inset %s at the top and %s at the "
                             "bottom" % (first, last))
            # pack padding is scaled on the way in, so compare with the
            # constant put through the same scaling
            self.assertEqual(
                int(first[0]),
                menu._apply_widget_scaling(scaffold_gui.LIST_PAD))
            menu.close()
        finally:
            app.destroy()

    def test_the_window_does_not_resize(self):
        # CustomTkinter repaints every widget's own canvas when its size
        # changes, about a millisecond each, so a single step of a resize cost
        # a quarter of a second with the widgets this window has, against six
        # milliseconds for an empty window of the same kind
        app = open_window()
        try:
            self.assertEqual(app.resizable(), (0, 0))
        finally:
            app.destroy()

    def test_everything_fits_the_window_it_cannot_grow(self):
        # nothing may be laid out past the bottom of a window that can no
        # longer be dragged bigger
        import glob
        app = open_window()
        try:
            app.update_idletasks()
            for path in sorted(glob.glob("test_structures/*.mcstructure"))[:8]:
                app.add_structure_row(path)
            app.update_idletasks()
            floor = app.winfo_rooty() + app.winfo_height()
            for name in ("make_button", "list_frame", "language_menu"):
                widget = getattr(app, name)
                bottom = widget.winfo_rooty() + widget.winfo_height()
                self.assertLessEqual(bottom, floor,
                                     "%s runs past the bottom" % name)
        finally:
            app.destroy()

    def test_the_border_around_a_list_is_even_on_all_four_sides(self):
        # the window behind the list is the border colour, and the list is
        # inset from it by the same amount all round. A frame whose height
        # comes out odd goes unpainted along its last row, and the
        # colour behind shows through as an extra pixel at the bottom
        from scaffold.ui import scaffold_gui

        app = open_window()
        try:
            app.update_idletasks()
            for menu in (app.theme_menu, app.language_menu):
                menu.open()
                app.update_idletasks()
                inner = menu.popup.winfo_children()[0]
                self.assertFalse(inner._draw_engine._round_height_to_even_numbers)
                self.assertFalse(inner._draw_engine._round_width_to_even_numbers)
                ring = inner.pack_info()
                self.assertEqual(int(ring["padx"]), int(ring["pady"]))
                self.assertEqual(
                    int(ring["padx"]),
                    menu._apply_widget_scaling(scaffold_gui.LIST_RING))
                menu.close()
        finally:
            app.destroy()


class CoordinatesButtonTests(unittest.TestCase):
    def test_it_is_wide_enough_in_every_language(self):
        # Ukrainian needs seventy per cent more room than English, and the
        # button sat in a column a third of the panel wide
        app = open_window()
        try:
            app.big_build.set(1)
            app.on_big_build()
            app.update_idletasks()
            button = app.cords_button
            for language in settings.choices():
                app.on_language(language)
                app.update_idletasks()
                self.assertGreaterEqual(
                    button.winfo_width(), button.winfo_reqwidth(),
                    "the coordinates button clips in %s: %d into %d"
                    % (language, button.winfo_reqwidth(), button.winfo_width()))
        finally:
            app.destroy()


class PackNameTests(unittest.TestCase):
    """The pack is named after the first structure until somebody says otherwise."""

    def files(self):
        import glob
        found = sorted(glob.glob("test_structures/*.mcstructure"))[:2]
        if len(found) < 2:
            raise unittest.SkipTest("needs two test structures")
        return found

    def test_the_first_structure_names_an_unnamed_pack(self):
        first, second = self.files()
        app = open_window()
        try:
            app.add_structure_row(first)
            self.assertEqual(app.pack_name_var.get(),
                             os.path.splitext(os.path.basename(first))[0])
            # the second leaves the name alone
            app.add_structure_row(second)
            self.assertEqual(app.pack_name_var.get(),
                             os.path.splitext(os.path.basename(first))[0])
        finally:
            app.destroy()

    def test_a_name_somebody_typed_is_never_written_over(self):
        first, _ = self.files()
        app = open_window()
        try:
            app.pack_name_var.set("My Build")
            app.add_structure_row(first)
            self.assertEqual(app.pack_name_var.get(), "My Build")
            # and it outlives the structure it was typed beside
            app.remove_structure(app.rows[0])
            self.assertEqual(app.pack_name_var.get(), "My Build")
        finally:
            app.destroy()

    def test_the_name_goes_when_the_structure_it_came_from_does(self):
        first, second = self.files()
        app = open_window()
        try:
            row = app.add_structure_row(first)
            other = app.add_structure_row(second)
            app.remove_structure(other)
            # still one structure left, so the name stays
            self.assertEqual(app.pack_name_var.get(),
                             os.path.splitext(os.path.basename(first))[0])
            app.remove_structure(row)
            self.assertEqual(app.pack_name_var.get(), "")
        finally:
            app.destroy()

    def test_clearing_the_list_clears_a_name_that_came_from_it(self):
        first, _ = self.files()
        app = open_window()
        try:
            app.add_structure_row(first)
            app.clear_all_structures()
            self.assertEqual(app.pack_name_var.get(), "")
        finally:
            app.destroy()


class FieldTests(unittest.TestCase):
    def test_a_field_shows_the_same_margin_above_and_below_its_text(self):
        # a CTkEntry paints the colour behind it across its whole rectangle, so
        # one centred in a taller row splits the leftover unevenly, leaving a
        # pixel of field above the text and two below it
        app = open_window()
        try:
            app.update_idletasks()
            settle(app)
            fields = [("pack name", app.pack_name_field),
                      ("description", app.desc_field)]
            fields += [("offset %d" % i, f)
                       for i, f in enumerate(app.offset_fields)]
            for state in ("", "a pack"):
                app.pack_name_var.set(state)
                settle(app)
                for name, field in fields:
                    above = field.entry.winfo_y()
                    below = field.winfo_height() - (
                        field.entry.winfo_y() + field.entry.winfo_height())
                    self.assertEqual(
                        above, below,
                        "%s shows %d above and %d below" % (name, above, below))
        finally:
            app.destroy()

    def test_the_text_clears_the_thickest_border_a_field_can_have(self):
        # the border grows from one to two while a field is showing an error,
        # and the text must not shift or be painted over when it does
        from scaffold.ui import scaffold_gui

        app = open_window()
        try:
            app.update_idletasks()
            app.pack_name_var.set("")
            settle(app)
            field = app.pack_name_field
            self.assertEqual(field.cget("border_width"), 2)
            self.assertGreaterEqual(
                field.entry.winfo_y(),
                field._apply_widget_scaling(scaffold_gui.FIELD_INSET))
        finally:
            app.destroy()


class SettingsFileTests(unittest.TestCase):
    """Everything the settings file holds is written back when it changes.

    A setting that is remembered in memory and not on disk looks like it worked
    until the program is next opened, which is the kind of bug nobody reports
    because it is easy to believe you imagined it.
    """

    ## every key in the file, with a value different from the default and the
    ## call that is supposed to persist it. A key with no entry here fails the
    ## first test rather than being quietly untested.
    def changes(self):
        return {
            "lang": ("es_ES", settings.set_language),
            "theme": ("dark", settings.set_theme),
            "tech_pack": ("compatibility", settings.set_tech_pack),
            "low_geometry": (True, settings.set_low_geometry),
            "check_updates": (False, settings.set_check_updates),
            "transparency": (42, settings.set_transparency),
            "output_dir": (os.path.join(os.path.expanduser("~"), "Somewhere"),
                           settings.set_output_dir),
        }

    def setUp(self):
        import json
        import shutil
        import tempfile

        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, ".scaffold")
        self._real = settings.settings_file
        settings.settings_file = lambda: self.path
        self.addCleanup(setattr, settings, "settings_file", self._real)
        self.addCleanup(shutil.rmtree, self.folder, True)
        self._stored = dict(settings.settings)
        self.addCleanup(settings.settings.update, self._stored)
        settings.load()
        self.json = json

    def on_disk(self):
        if not os.path.isfile(self.path):
            return {}
        with open(self.path, encoding="utf-8-sig") as handle:
            return self.json.load(handle)

    def test_every_key_in_the_file_has_a_setter_that_is_checked(self):
        self.assertEqual(sorted(self.changes()), sorted(settings.DEFAULTS))

    def test_changing_a_setting_writes_it_back(self):
        for key, (value, setter) in sorted(self.changes().items()):
            with self.subTest(setting=key):
                setter(value)
                self.assertEqual(self.on_disk().get(key), settings.settings[key],
                                 "%s was not written to the file" % key)

    def first_launch(self, desktop):
        """Load with nothing remembered, pretending the desktop says this."""
        from scaffold import system_locale

        if os.path.isfile(self.path):
            os.remove(self.path)
        ## a machine that once ran 1.7 has a settings.json of its own, which is
        ## the migration path rather than a first launch
        real_legacy = settings.LEGACY_SETTINGS_FILE
        real_read = system_locale.read
        settings.LEGACY_SETTINGS_FILE = os.path.join(self.folder, "nothing.json")
        system_locale.read = lambda: desktop
        try:
            settings.load()
            return settings.settings["lang"]
        finally:
            settings.LEGACY_SETTINGS_FILE = real_legacy
            system_locale.read = real_read

    def test_the_first_launch_starts_in_the_desktops_language(self):
        # nobody should have to find the picker to read the window in their own
        # language, and the machine already knows the answer
        self.assertEqual(self.first_launch("uk_UA"), "uk_UA")
        self.assertEqual(self.first_launch("ceb_PH"), "ceb_PH")
        # a region with no file of its own falls back to the language
        self.assertEqual(self.first_launch("es_MX"), "es_ES")
        self.assertEqual(self.first_launch("zh_TW"), "zh_CN")
        # and a language with no file at all reads English
        self.assertEqual(self.first_launch("fr_FR"), "en_US")
        self.assertEqual(self.first_launch("en_GB"), "en_US")
        self.assertEqual(self.first_launch(None), "en_US")
        # the placeholder is never chosen for anybody
        self.assertEqual(self.first_launch("xx_XX"), "en_US")

    def test_a_remembered_language_outlives_the_desktops(self):
        from scaffold import system_locale

        settings.set_language("en_US")
        real = system_locale.read
        system_locale.read = lambda: "uk_UA"
        try:
            settings.load()
        finally:
            system_locale.read = real
        self.assertEqual(settings.settings["lang"], "en_US")

    def test_the_guess_is_written_down_so_it_is_made_once(self):
        # a person who then picks English on a Spanish machine keeps English
        self.first_launch("uk_UA")
        self.assertEqual(self.on_disk().get("lang"), "uk_UA")

    def test_the_window_opens_with_the_remembered_low_geometry(self):
        # the switch describes the machine, so it has to survive a restart
        settings.set_low_geometry(True)
        app = open_window()
        try:
            self.assertEqual(app.low_geometry.get(), 1)
        finally:
            app.destroy()
            settings.set_low_geometry(False)

    def test_a_file_that_will_not_parse_keeps_english(self):
        # A file that is there but unreadable means Scaffold has run before, so
        # the desktop's locale is not the answer: guessing it, and writing the
        # guess down, is how one torn write turned into the window permanently
        # coming back in the machine's language.
        from scaffold import system_locale

        real = system_locale.read
        system_locale.read = lambda: "zh_CN"
        try:
            for broken in ("", "   ", "{not json", "[]"):
                with self.subTest(contents=broken):
                    with open(self.path, "w", encoding="utf-8") as handle:
                        handle.write(broken)
                    settings.load()
                    self.assertEqual(settings.settings["lang"],
                                     settings.DEFAULT_LANGUAGE)
        finally:
            system_locale.read = real

    def test_a_file_that_will_not_parse_is_left_alone(self):
        # the user may be part way through fixing it by hand, and a program that
        # rewrites the file somebody is editing is a program that loses their work
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        settings.load()
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "{not json")

    def test_no_file_at_all_still_follows_the_desktop(self):
        # the guess is for a first launch, and that still has to work
        self.assertEqual(self.first_launch("uk_UA"), "uk_UA")

    def test_a_write_is_all_or_nothing(self):
        # save() moves a finished temp file into place, so a crash partway
        # through can never leave a half-written .scaffold behind
        settings.set_language("en_US")
        before = self.on_disk()
        real = self.json.dump

        def explode(*_args, **_kwargs):
            raise OSError("disk full")

        self.json.dump = explode
        try:
            settings.save()
        finally:
            self.json.dump = real
        self.assertEqual(self.on_disk(), before)
        self.assertEqual([n for n in os.listdir(self.folder)
                          if n.endswith(".tmp")], [])

    def test_the_file_is_never_inside_the_package(self):
        # paths.beside_executable() means the package when not frozen, which is
        # right for reading data and wrong for the user's own settings:
        # site-packages is shared and not theirs to write to
        from scaffold import paths

        settings.settings_file = self._real
        self.assertNotIn(os.path.dirname(os.path.abspath(paths.__file__)),
                         settings.settings_file())



@unittest.skipUnless(sys.platform.startswith("win"),
                     "explorer is the only shell that takes a file to select")
class ShowInFolderTests(unittest.TestCase):
    """The button points at the pack, not at the folder above it.

    Explorer will not parse a quoted `/select,<path>` token: given one it drops
    the selection and opens a default view, which is how a build in
    `Documents\\Scaffold Builds` opened `Documents` instead. Passing an argument
    list quotes the whole token as soon as the path has a space in it, so the
    command goes as one string with only the path quoted.
    """

    def commanded(self, folder, reveal):
        from scaffold.ui import scaffold_gui

        app = open_window()
        seen = []
        real = scaffold_gui.subprocess.Popen
        scaffold_gui.subprocess.Popen = lambda command, *a, **k: seen.append(command)
        try:
            dialog = scaffold_gui.ResultDialog(app, "built", ["line"], folder,
                                              reveal=reveal)
            dialog.open_folder()
        finally:
            scaffold_gui.subprocess.Popen = real
            app.destroy()
        return seen

    def test_the_pack_is_picked_out_in_the_folder_it_was_written_to(self):
        import tempfile

        folder = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        pack = os.path.join(folder, "My Pack.mcpack")
        with open(pack, "wb") as handle:
            handle.write(b"PK")
        seen = self.commanded(folder, pack)
        self.assertEqual(len(seen), 1)
        command = seen[0]
        self.assertIsInstance(command, str,
                              "an argument list gets the whole token quoted")
        self.assertTrue(command.startswith("explorer /select,\""),
                        "the switch must sit outside the quotes: %r" % command)
        self.assertIn(os.path.normpath(pack), command)


class HelpMarkTests(unittest.TestCase):
    """The ? beside a setting, and the tip it shows."""

    def marks(self, app):
        found = [(sw.key, sw.label, sw.mark) for sw in app.switches if sw.mark]
        found.append(("techpack", app.tech_label, app.tech_mark))
        return found

    def test_the_mark_sits_against_its_label_not_the_control(self):
        # the ? belongs to the words, so its column must not be the stretchy
        # one: a stretchy column carries it across the row to the switch
        app = open_window()
        try:
            settle(app)
            for key, label, mark in self.marks(app):
                gap = mark.winfo_x() - (label.winfo_x() + label.winfo_width())
                self.assertGreaterEqual(gap, 0, "%s: the ? overlaps its label" % key)
                self.assertLess(gap, 20,
                                "%s: the ? is %d px from its label" % (key, gap))
        finally:
            app.destroy()

    def test_the_tip_survives_the_window_merely_laying_itself_out(self):
        # Configure fires throughout a layout, so binding it directly made the
        # tip vanish the instant it appeared
        app = open_window()
        try:
            settle(app)
            tip = app.tech_mark.tip
            tip.show()
            settle(app)
            self.assertIsNotNone(tip.window, "the tip dismissed itself")
            tip.hide()
        finally:
            app.destroy()

    def test_every_way_out_puts_the_tip_away(self):
        # a tip is a borderless window of its own, so nothing closes it unless
        # something is watching for it: a click, a keystroke, the mark going out
        # from under the pointer, the window being dragged
        from scaffold.ui import scaffold_gui

        tooltip = scaffold_gui.Tooltip
        app = open_window()
        try:
            settle(app)
            tip = app.tech_mark.tip

            class Elsewhere(object):
                widget = app.make_button

            for name, dismiss in (
                    ("a click elsewhere",
                     lambda: tooltip._interacted(Elsewhere())),
                    ("a keystroke", lambda: tooltip._interacted(Elsewhere())),
                    ("leaving the mark", tip.leave),
                    ("the window moving", tooltip._moved)):
                tip.show()
                settle(app, 2)
                self.assertIsNotNone(tip.window)
                if name == "the window moving":
                    tip._anchor = (-1, -1, -1, -1)
                dismiss()
                self.assertIsNone(tip.window, "%s left it up" % name)
                self.assertIsNone(tooltip.showing,
                                  "%s left a tip on record" % name)
        finally:
            app.destroy()

    def test_a_click_on_the_mark_itself_keeps_it(self):
        # the mark's own binding opens the tip and the window-wide one runs
        # after it, so a click there must not close what it just opened
        from scaffold.ui import scaffold_gui

        tooltip = scaffold_gui.Tooltip
        app = open_window()
        try:
            settle(app)
            tip = app.tech_mark.tip
            tip.show()
            settle(app, 2)

            class OnTheMark(object):
                widget = app.tech_mark

            tooltip._interacted(OnTheMark())
            self.assertIsNotNone(tip.window)
            tip.hide()
        finally:
            app.destroy()

    def test_only_one_tip_is_up_at_a_time(self):
        # whatever is open is what everything else has to close, so a second
        # one opening has to put the first away rather than leaving it behind
        from scaffold.ui import scaffold_gui

        tooltip = scaffold_gui.Tooltip
        app = open_window()
        try:
            settle(app)
            marks = [mark for _key, _label, mark in self.marks(app)]
            self.assertGreater(len(marks), 1, "only one mark to test with")
            first, second = marks[0].tip, marks[1].tip
            first.show()
            settle(app, 2)
            self.assertIs(tooltip.showing, first)
            second.show()
            settle(app, 2)
            self.assertIsNone(first.window, "the first tip was left up")
            self.assertIs(tooltip.showing, second)
            second.hide()
            self.assertIsNone(tooltip.showing)
        finally:
            app.destroy()

    def test_showing_twice_leaves_one_window(self):
        app = open_window()
        try:
            settle(app)
            tip = app.tech_mark.tip
            tip.show()
            window = tip.window
            tip.show()
            settle(app, 2)
            self.assertIs(tip.window, window, "the second show built another")
            tip.hide()
            self.assertIsNone(tip.window)
        finally:
            app.destroy()

if __name__ == "__main__":
    unittest.main()
