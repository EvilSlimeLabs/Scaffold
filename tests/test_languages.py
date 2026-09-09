import importlib.util
import os
import sys
import unittest

from scaffold import lang_parse


def tool(name):
    """One of the generators in tools/, by its dotted name.

    They are a package of their own rather than part of Scaffold, so they are
    imported the ordinary way and nothing here has to know where they sit.
    """
    return importlib.import_module(name)


class LanguageFileTests(unittest.TestCase):
    """One file per language, so adding a language is adding a file."""

    @classmethod
    def setUpClass(cls):
        cls.table = lang_parse.parse()
        cls.english = cls.table["en_US"]

    def strings(self, code):
        """A language's labels, without the key that describes it."""
        return {k: v for k, v in self.table[code].items()
                if k not in lang_parse.META}

    def test_the_folder_is_where_the_languages_are(self):
        self.assertTrue(os.path.isdir(lang_parse.folder()))
        files = [n for n in os.listdir(lang_parse.folder())
                 if n.endswith(lang_parse.SUFFIX)]
        self.assertEqual(sorted(files),
                         sorted("%s%s" % (code, lang_parse.SUFFIX)
                                for code in self.table))

    def test_every_file_is_named_for_a_locale(self):
        for code in self.table:
            self.assertRegex(code, r"^[a-z]{2,3}_[A-Za-z]{2,3}$",
                             "%s is not a locale" % code)

    def test_every_language_says_what_it_is_called(self):
        for code in self.table:
            name = lang_parse.name(code, self.table)
            self.assertTrue(name and name != code,
                            "%s does not name itself" % code)

    def test_no_language_is_missing_a_string(self):
        # a missing key falls back to English, which is a label in the wrong
        # language rather than an error, so nothing else would report it
        for code in self.table:
            self.assertEqual(set(self.strings(code)), set(self.strings("en_US")),
                             "%s has a different set of strings" % code)

    def test_a_comment_and_a_blank_line_are_not_strings(self):
        read = lang_parse.read(os.path.join(lang_parse.folder(), "en_US.lang"))
        self.assertNotIn("", read)
        for key in read:
            self.assertFalse(key.startswith("#"), key)


class SpecialLanguageTests(unittest.TestCase):
    """The generated languages, and the generator that has to stay in step."""

    @classmethod
    def setUpClass(cls):
        cls.table = lang_parse.parse()
        cls.english = cls.table["en_US"]
        cls.lang_fun = tool("tools.app.transforms")

    ## Two proper names and the three axis letters, which stay as they are, and
    ## the key that describes the language rather than labels anything.
    LEFT_ALONE = {"title", "techpack", "axis x", "axis y", "axis z"}
    LEFT_ALONE |= set(lang_parse.META)

    def test_each_one_says_something_different_from_english(self):
        # Enchanting is deliberately not one of these: the enchanting alphabet
        # is a font, so its strings stay in English and ui_fonts hands the
        # window the rune face instead
        for code in ("en_PT", "lol_US", "en_WS", "en_UD"):
            untouched = sorted(
                key for key, value in self.english.items()
                if value and self.table[code].get(key) == value
                and key not in self.LEFT_ALONE)
            self.assertEqual(untouched, [],
                             "%s leaves these in plain English: %s"
                             % (code, untouched))

    def test_enchanting_is_carried_by_the_font_not_by_substitution(self):
        from scaffold.ui import ui_fonts

        for key, value in self.english.items():
            if key in lang_parse.META:
                continue
            self.assertEqual(self.table["en_SGA"][key], value, key)
        self.assertEqual(ui_fonts.LANGUAGE_FAMILY.get("en_SGA"),
                         ui_fonts.SGA_FAMILY)

    def test_a_placeholder_survives_every_transform(self):
        # the transforms run only between the {} markers; a mangled placeholder
        # raises on the next .format()
        for code in ("en_SGA", "en_PT", "lol_US", "en_WS", "en_UD"):
            for key, english in self.english.items():
                if "{}" not in english:
                    continue
                spoken = self.table[code][key]
                self.assertIn("{}", spoken, "%s/%s" % (code, key))
                spoken.format("a thing")

    def test_the_generated_files_are_in_step_with_the_generator(self):
        # they are written by tools/app/languages.py from en_US.lang, so
        # an English string changed without re-running it leaves them behind
        maker = tool("tools.app.languages")
        english = maker.source()
        for code, (transform, name, badge) in self.lang_fun.TRANSFORMS.items():
            expected = {}
            for key, value in english:
                if key == lang_parse.NAME_KEY:
                    expected[key] = name
                else:
                    expected[key] = transform(value)
            expected[lang_parse.BADGE_KEY] = badge
            self.assertEqual(self.table[code], expected,
                             "%s has drifted: re-run "
                             "python -m tools.app.languages" % code)

    def test_upside_down_reverses_the_line(self):
        # the whole line turns over, so the pieces swap ends as well as the
        # letters. Turning only the letters reads as flipped English order.
        self.assertEqual(self.lang_fun.upside_down("ab"), "qɐ")


class RealLanguageTests(unittest.TestCase):
    def test_tagalog_and_cebuano_are_complete(self):
        table = lang_parse.parse()
        english = set(table["en_US"])
        for code in ("tl_PH", "ceb_PH"):
            self.assertIn(code, table)
            self.assertEqual(set(table[code]), english)
            blank = [k for k, v in table[code].items() if not v]
            self.assertEqual(blank, [], "%s has untranslated rows" % code)


class DesktopLocaleTests(unittest.TestCase):
    """What the machine says its language is, and what that is taken to mean."""

    def test_a_locale_is_tidied_into_the_shape_the_files_use(self):
        from scaffold import system_locale

        for reported, wanted in (
                ("es-MX", "es_MX"),            # Windows writes it with a dash
                ("es_MX.UTF-8", "es_MX"),      # POSIX adds the encoding
                ("en_GB@euro", "en_GB"),       # and sometimes a modifier
                ("en_GB:en", "en_GB"),         # LANGUAGE holds a whole list
                ("zh_Hans_CN", "zh_CN"),       # a script sits in the middle
                ("es_419", "es_419"),          # a region may be digits
                ("pt", "pt"),                  # a language on its own
                ("en-us", "en_US")):
            self.assertEqual(system_locale.tidy(reported), wanted, reported)

    def test_what_is_not_a_locale_is_no_answer(self):
        from scaffold import system_locale

        for reported in ("C", "POSIX", "", None, "english_UNITED STATES"):
            self.assertIsNone(system_locale.tidy(reported), reported)

    def test_reading_the_desktop_never_raises(self):
        # every way of asking is platform specific and none of them is a reason
        # to refuse to start
        from scaffold import system_locale

        found = system_locale.read()
        if found is not None:
            self.assertEqual(system_locale.tidy(found), found)

    def test_a_locale_is_matched_to_the_file_that_serves_it_best(self):
        from scaffold import settings

        settings.langs = lang_parse.parse()
        self.assertEqual(settings.match_locale("uk_UA"), "uk_UA")
        self.assertEqual(settings.match_locale("es_MX"), "es_ES")
        self.assertEqual(settings.match_locale("en_GB"), "en_US")
        self.assertIsNone(settings.match_locale("fr_FR"))
        self.assertIsNone(settings.match_locale("xx_XX"))
        self.assertIsNone(settings.match_locale(None))


class BadgeTests(unittest.TestCase):
    """Upside-down English wears the English badge, upside down."""

    def test_the_flipped_badge_is_the_english_one_turned_over(self):
        from PIL import ImageOps
        from scaffold.ui import lang_icons

        english = lang_icons.badge("en_US", 44, text=(255, 255, 255))
        upside_down = lang_icons.badge("en_UD", 44, text=(255, 255, 255))
        self.assertEqual(list(upside_down.getdata()),
                         list(ImageOps.flip(english).getdata()))
        # and it is not simply the English badge
        self.assertNotEqual(list(upside_down.getdata()), list(english.getdata()))

    def test_the_slant_of_the_bands_turns_over_with_it(self):
        # English is two colours split along the diagonal, so a flip has to
        # swap which corner each of them is in
        from scaffold.ui import lang_icons

        english = lang_icons.badge("en_US", 44)
        upside_down = lang_icons.badge("en_UD", 44)
        for x, y in ((33, 10), (10, 33)):
            self.assertNotEqual(english.getpixel((x, y))[:3],
                                upside_down.getpixel((x, y))[:3])

    def test_no_other_language_borrows_a_badge(self):
        from scaffold.ui import lang_icons

        self.assertEqual(set(lang_icons.UPSIDE_DOWN), {"en_UD"})


if __name__ == "__main__":
    unittest.main()
