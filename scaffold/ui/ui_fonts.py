"""The interface's typeface, shipped with the program rather than borrowed.

Left to itself Tk picks the platform's UI font, which is Segoe UI on Windows and
something else everywhere else, so the window reads differently on every machine
and the language badges are drawn in a face the program has no right to
redistribute. Source Sans Pro travels with the program instead, under the SIL
Open Font License 1.1. See fonts/LICENSE.txt, which ships beside the fonts.

On Windows a font can be handed to the process privately, without installing it
for the whole machine, which is what AddFontResourceEx with FR_PRIVATE does.
Elsewhere there is no equivalent that Tk will see, so the window falls back to
the platform's own UI font; the badges still use the bundled file directly,
because PIL loads a .ttf by path and does not care whether it is installed.

Chinese and other scripts Source Sans Pro does not cover fall through to the
system font, which is what Tk does for a missing glyph anyway.
"""
import os
import sys

from scaffold import lang_parse
from scaffold import paths
FAMILY = "Source Sans Pro"

## Simplified Chinese, subset by tools/make_fonts.py to the characters the
## window can actually display, 189 KB rather than the 17 MB of the whole face
CJK_FAMILY = "Noto Sans SC"

## the enchanting table alphabet, traced from the resource pack's glyph sheet by
## tools/make_fonts.py. It is a font because the alphabet is a font: there is no
## Unicode block for it, so no string of characters could ever be the real thing
SGA_FAMILY = "Scaffold Enchanting"

## regular first: it is the one whose family name Tk will report
FILES = ("SourceSansPro-Regular.ttf",
         "SourceSansPro-Semibold.ttf",
         "SourceSansPro-Bold.ttf",
         "NotoSansSC-Scaffold.ttf",
         "ScaffoldEnchanting.ttf")

## A language whose script the interface face does not cover gets its own. Keyed
## by locale or by the language part of one: `zh` covers zh_CN and zh_TW alike,
## and en_SGA is English written in the enchanting alphabet.
LANGUAGE_FAMILY = {"zh": CJK_FAMILY, "en_SGA": SGA_FAMILY}

## What to multiply a requested point size by, per face. The rune alphabet is
## squarer than a Latin one and stays about a fifth wider even with the ink
## measured properly, so it is asked for a little smaller and the window's
## labels come out the length the layout was built around. Anything not listed
## is used at the size it was asked for.
LANGUAGE_SCALE = {"en_SGA": 0.85}

## what to use when the bundled font could not be registered
FALLBACKS = ("Segoe UI", "Helvetica Neue", "DejaVu Sans", "sans-serif")

_registered = None


def folder():
    return paths.data("fonts")


def path(name):
    return os.path.join(folder(), name)


def _register_windows():
    import ctypes
    FR_PRIVATE = 0x10
    added = 0
    for name in FILES:
        file_path = path(name)
        if not os.path.isfile(file_path):
            continue
        if ctypes.windll.gdi32.AddFontResourceExW(file_path, FR_PRIVATE, 0):
            added += 1
    return added > 0


def register():
    """Make the bundled font available to this process. Safe to call twice."""
    global _registered
    if _registered is not None:
        return _registered
    _registered = False
    try:
        if sys.platform.startswith("win"):
            _registered = _register_windows()
    except Exception:
        ## a font that will not load is not a reason to refuse to start
        _registered = False
    return _registered


def _for(table, locale, missing):
    """A locale's entry, or its language's, or `missing`.

    Falling back to the language is what lets a regional variant be added as a
    file and nothing else: zh_TW is drawn in the same face as zh_CN because both
    ask for `zh` when neither is listed by name.
    """
    if locale is None:
        return missing
    if locale in table:
        return table[locale]
    return table.get(lang_parse.language_of(locale), missing)


def family(locale=None):
    """The family name to ask Tk for, for this locale.

    Tk substitutes silently for a family it does not have, and its per-character
    fallback does not reach a privately registered font, so the face is chosen
    outright rather than left to chance: Chinese gets the CJK subset, Enchanting
    gets the rune face, everything else gets the interface face.
    """
    if not register():
        return FALLBACKS[0]
    return _for(LANGUAGE_FAMILY, locale, FAMILY)


def scale(locale=None):
    """How much to shrink this language's face, as a factor of the asked size."""
    return _for(LANGUAGE_SCALE, locale, 1.0)


def truetype(weight="Regular"):
    """A path PIL can open, for the drawn glyphs. None if it is not there."""
    candidate = path("SourceSansPro-%s.ttf" % weight)
    return candidate if os.path.isfile(candidate) else None
