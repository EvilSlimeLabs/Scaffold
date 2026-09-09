"""Reads the interface's translations, one file per language.

`lookups/lang/` holds a `.lang` file per language, named for its **locale** the
way Minecraft names its own: a language and a region, `en_US.lang`, `es_MX.lang`,
`zh_CN.lang`. A file is one `key=value` per line, in UTF-8, with `#` for a
comment.

The file's name is the whole of a language's identity. It is the key every table
is read with, the value the picker carries, and what the settings file
remembers, and nothing inside the file repeats it: a locale written in two
places is a locale that can disagree with itself.

The language part is what a locale falls back to. `zh_TW` and `zh_CN` are drawn
in the same face and the same colours without either being listed, because
`ui_fonts` and `lang_icons` ask for the locale first and the language second.
That is what makes adding Mexican Spanish beside Spain's a matter of adding a
file: it inherits everything Spanish, and needs saying only where it differs.

Two keys describe the language rather than label anything. `language name` is
its own name for itself, which is what the picker shows and sorts by. `language
badge` is the two or three letters the badge carries, for the languages where
the language part is not the thing to show: the badge for `en_PT` is PT, because
Pirate Speak reading EN says nothing. Neither is a string the window draws,
which is why the tests that compare one language against another leave them out.
"""
import os

from scaffold import paths

FOLDER = "lang"
SUFFIX = ".lang"
SEPARATOR = "_"

## what a language says about itself rather than about the window
NAME_KEY = "language name"
BADGE_KEY = "language badge"
META = (NAME_KEY, BADGE_KEY)


def folder():
    return paths.lookup(FOLDER)


def language_of(locale):
    """The language part of a locale: the `es` of `es_MX`."""
    return locale.partition(SEPARATOR)[0]


def region_of(locale):
    """The region part of a locale, or an empty string when it has none."""
    return locale.partition(SEPARATOR)[2]


def read(path):
    """One file, as a dictionary. Comments and blank lines are skipped."""
    strings = {}
    with open(path, encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sign, value = line.partition("=")
            ## a line with no = at all is a typo, not a string; skipping it
            ## leaves the label English rather than putting a broken key on
            ## screen
            if sign:
                strings[key.strip()] = value
    return strings


def parse():
    """Every language file there is, keyed by the locale it is named for."""
    here = folder()
    if not os.path.isdir(here):
        return {}
    table = {}
    for name in sorted(os.listdir(here)):
        if not name.endswith(SUFFIX):
            continue
        table[name[:-len(SUFFIX)]] = read(os.path.join(here, name))
    return table


def name(locale, table=None):
    """A language's own name for itself, or its locale when it has none."""
    if table:
        written = table.get(locale, {}).get(NAME_KEY)
        if written:
            return written
    return locale


def badge(locale, table=None):
    """The letters the badge carries, which default to the language part."""
    if table:
        written = table.get(locale, {}).get(BADGE_KEY, "").strip()
        if written:
            return written
    return language_of(locale)
