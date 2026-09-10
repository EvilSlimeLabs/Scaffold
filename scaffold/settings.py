"""User settings and translated strings, shared by the window and the CLI.

Kept out of both so the GUI module and the entry point can each read them
without importing the other. Importing this has no side effects; nothing is
read from disk until load() is called.
"""
import json
import os
import sys
import tempfile

from scaffold import lang_parse
from scaffold import paths
from scaffold import system_locale
SETTINGS_NAME = ".scaffold"

## The settings file Scaffold 1.7 and earlier wrote. Read once, to carry an
## existing choice across, and never written to.
LEGACY_SETTINGS_FILE = "settings.json"


def settings_file():
    """The settings file to use.

    A `.scaffold` sitting next to the **executable** wins, which makes the
    program portable: put it on a stick with its settings beside it and it
    carries them between machines, touching nothing on the host. Otherwise
    settings live in the home directory, where they survive replacing the
    executable and work when the program is run from a folder the user cannot
    write to. The home copy is the one created when neither exists.

    Only a frozen build has somewhere meaningful to be "beside": an installed
    package sits in site-packages, which is shared between everyone using that
    interpreter and is not the user's to write to. `paths.beside_executable()`
    answers the package directory when not frozen, which is right for reading
    data and wrong for this, so this asks the question directly.
    """
    if paths.frozen():
        portable = os.path.join(paths.beside_executable(), SETTINGS_NAME)
        if os.path.isfile(portable):
            return portable
    return os.path.join(os.path.expanduser("~"), SETTINGS_NAME)

## A language is named by its locale throughout, the way Minecraft names its
## own: a language and a region, `en_US`, `es_MX`, `zh_CN`. It is the file's
## name and what the settings file remembers, so a language's own name can be
## corrected without stranding anyone's stored choice, and a regional variant is
## a file rather than a special case.
DEFAULT_LANGUAGE = "en_US"
## a placeholder language file, useful for spotting a missing lookup but not
## something to offer in the menu
HIDDEN_LANGUAGES = {"xx_XX"}

## "system" follows the desktop. It is the default, and falls back to dark when
## the desktop cannot be asked, because a dark window is the safer thing to show
## against an unknown background.
THEMES = ("system", "light", "dark")
DEFAULT_THEME = "system"
FALLBACK_THEME = "dark"

## The slider is transparency: 0 is a solid ghost block and 100 would be
## invisible. It stops at 99 so a ghost block always has some alpha left.
## Transparency is the number the user sets, so it is the one defined here and
## everything else is derived from it. The CLI's --opacity and the core's
## DEFAULT_ALPHA both have to land on the same ghost block as the slider does.
DEFAULT_TRANSPARENCY = 65
DEFAULT_OPACITY = 100 - DEFAULT_TRANSPARENCY
MAX_TRANSPARENCY = 99

def default_output_dir():
    return paths.default_output_dir()


## What a generated pack does about TechPack, remembered between runs. The
## default is to leave it alone: bundling somebody else's pack into yours is a
## deliberate act, not a thing to happen because a switch was left on.
TECH_PACK_MODES = ("none", "compatibility", "full")
DEFAULT_TECH_PACK = "none"

## Whether the most detailed blocks are drawn as a simpler shape, remembered
## between runs. It describes the machine rather than the pack: whether this
## player's client can afford detailed ghost blocks depends on their hardware
## and on whether they run Vibrant Visuals, and that answer does not change
## between structures. Full detail is the default.
DEFAULT_LOW_GEOMETRY = False

## Whether the program asks GitHub for a newer release when it starts. On,
## because an updater nobody is told about is an updater nobody uses, and the
## About window says plainly that it is happening and turns it off. It is the
## only thing Scaffold sends anywhere.
DEFAULT_CHECK_UPDATES = True

DEFAULTS = {"lang": DEFAULT_LANGUAGE,
            "theme": DEFAULT_THEME,
            "tech_pack": DEFAULT_TECH_PACK,
            "low_geometry": DEFAULT_LOW_GEOMETRY,
            "check_updates": DEFAULT_CHECK_UPDATES,
            "transparency": DEFAULT_TRANSPARENCY,
            "output_dir": ""}          # empty means "use the default"

settings = dict(DEFAULTS)
langs = {}


def transparency_to_alpha(transparency):
    """The slider reads as transparency; set_opacity wants an alpha fraction."""
    return (100 - float(transparency)) / 100


def language(code=None):
    """The strings for a language code, with English filling any gap.

    A language file missing a line, or with it blank, would otherwise put an
    empty label on screen. That is what makes a half-finished translation worth
    shipping: what is there is used and the rest reads English.
    """
    code = code or settings.get("lang", DEFAULT_LANGUAGE)
    strings = dict(langs.get(DEFAULT_LANGUAGE, {}))
    strings.update({k: v for k, v in langs.get(code, {}).items() if v})
    return strings


def language_name(locale):
    """What to call a language on screen: its own name for itself."""
    return lang_parse.name(locale, langs)


def language_badge(locale):
    """The letters its badge carries."""
    return lang_parse.badge(locale, langs)


def _speaking(language):
    """A file for a language, whatever region it was written for.

    The default comes first, so English asked for by a locale nobody has a file
    for lands on English rather than on whichever special language sorts before it.
    """
    if not language:
        return None
    if lang_parse.language_of(DEFAULT_LANGUAGE) == language:
        return DEFAULT_LANGUAGE
    for locale in sorted(langs):
        if locale in HIDDEN_LANGUAGES:
            continue
        if lang_parse.language_of(locale) == language:
            return locale
    return None


def language_code(stored):
    """The locale a remembered language means, if any file still provides it.

    Scaffold remembered a language by name until 3.0 and by bare code during
    it, so a settings file may hold `English`, `en`, or nothing recognisable.
    """
    if not stored:
        return None
    for locale in langs:
        if language_name(locale) == stored:
            return locale
    return _speaking(stored)


def match_locale(locale):
    """The language file that best serves a locale the desktop reported.

    A file for that exact locale if there is one, so a Mexican desktop gets
    Mexican Spanish; otherwise any file for the language, so it gets Spain's
    rather than English. None when nothing there speaks it.

    The special languages sit at locales an operating system does not report, so
    they are not reachable this way in practice. Somebody who sets their desktop
    to English (Portugal) by hand will be shown Pirate Speak, and can pick again.
    """
    if not locale:
        return None
    if locale in langs and locale not in HIDDEN_LANGUAGES:
        return locale
    return _speaking(lang_parse.language_of(locale))


def choices():
    """The codes worth offering, in an order somebody would expect.

    English first, because it is the source the rest are translated from and the
    fallback for anything missing; then every other language alphabetically by
    its own name, the special ones among them. A language added to the folder lands
    in that order without anything here being told about it.
    """
    offered = [code for code in langs if code not in HIDDEN_LANGUAGES]
    rest = sorted((c for c in offered if c != DEFAULT_LANGUAGE),
                  key=lambda c: language_name(c).casefold())
    return ([DEFAULT_LANGUAGE] if DEFAULT_LANGUAGE in offered else []) + rest


def save():
    """Write the settings file, all at once.

    Written to a temporary file beside the real one and moved into place with
    os.replace, which is atomic: a crash or a killed process partway through
    can never leave a truncated .scaffold behind. An empty or half-written file
    reads back as "no language chosen", and load() then adopts the desktop's
    locale, so a torn write here has shown up as the window silently coming
    back in the wrong language.
    """
    target = settings_file()
    directory = os.path.dirname(target) or "."
    try:
        handle, temp = tempfile.mkstemp(dir=directory, prefix=".scaffold-",
                                        suffix=".tmp")
    except OSError:
        ## a read-only location is not a reason to refuse to run
        return
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2)
        os.replace(temp, target)
    except BaseException as trouble:
        ## the half-written temp goes whatever went wrong, so a failed save
        ## leaves the settings file untouched and no litter beside it
        try:
            os.remove(temp)
        except OSError:
            pass
        ## a read-only location is not a reason to refuse to run; anything
        ## else is a fault worth seeing
        if not isinstance(trouble, OSError):
            raise


def read_languages():
    """Every language there is a file for, keyed by its code."""
    return lang_parse.parse()


def _read(path):
    try:
        with open(path, encoding="utf-8") as file:
            stored = json.load(file)
        return stored if isinstance(stored, dict) else None
    except (OSError, ValueError):
        ## a truncated or hand-edited file must not stop the program starting
        return None


def load():
    """Read the language files and the settings file. Returns the strings."""
    global settings, langs
    langs = read_languages()
    settings = dict(DEFAULTS)
    ## A file that is there but will not parse is a different case from no file
    ## at all: it means Scaffold has run before and the choices are simply
    ## unreadable this once. Guessing the desktop's locale then, and writing
    ## that guess down, is how a hand-edit slip or a torn write turned into the
    ## window permanently coming back in the machine's language. So a broken
    ## file keeps English and is left untouched until the user changes a
    ## setting, which rewrites it cleanly.
    present = os.path.isfile(settings_file())
    stored = _read(settings_file())
    broken = present and stored is None
    if stored is None and not present and os.path.exists(LEGACY_SETTINGS_FILE):
        ## carry an older choice over the first time, then leave the old file
        ## alone rather than deleting something the user may still want
        stored = _read(LEGACY_SETTINGS_FILE)
    if stored:
        settings.update({k: v for k, v in stored.items() if k in DEFAULTS})
    ## First launch: nobody has chosen a language, and the desktop's own is a
    ## better guess than English. Only ever a guess, and only ever now: the
    ## choice is written to the file below, so a person who then picks English
    ## on a Spanish machine keeps English.
    if not broken and (not stored or "lang" not in stored):
        settings["lang"] = (match_locale(system_locale.read())
                            or DEFAULT_LANGUAGE)
    ## an unknown language or theme must not stop the program starting either
    if settings.get("lang") not in langs:
        settings["lang"] = (language_code(settings.get("lang"))
                            or DEFAULT_LANGUAGE)
    if settings.get("theme") not in THEMES:
        settings["theme"] = DEFAULT_THEME
    if settings.get("tech_pack") not in TECH_PACK_MODES:
        settings["tech_pack"] = DEFAULT_TECH_PACK
    ## a switch is stored as a JSON boolean, but an older file or a hand edit
    ## may hold 0 or 1, which mean the same thing
    settings["low_geometry"] = bool(settings.get("low_geometry"))
    settings["check_updates"] = bool(settings.get("check_updates",
                                                  DEFAULT_CHECK_UPDATES))
    if not isinstance(settings.get("output_dir"), str):
        settings["output_dir"] = ""
    ## a file that would not parse is left exactly as it is; overwriting it
    ## would bury whatever the user was in the middle of fixing
    if not broken:
        save()
    return language()


def output_dir():
    """Where finished packs go. Empty means the platform default."""
    chosen = settings.get("output_dir") or ""
    return chosen or default_output_dir()


def set_output_dir(path):
    """Remember a folder. Storing the default as empty keeps the setting
    meaningful if the default ever moves."""
    path = (path or "").strip()
    settings["output_dir"] = "" if path == default_output_dir() else path
    save()
    return output_dir()


def set_language(code):
    """Remember a language by its code. Anything unknown leaves it alone."""
    if code in langs:
        settings["lang"] = code
        save()
    return language()


def set_tech_pack(mode):
    """Remember what to do about TechPack. Anything unrecognised means none."""
    settings["tech_pack"] = mode if mode in TECH_PACK_MODES else DEFAULT_TECH_PACK
    save()
    return settings["tech_pack"]


def low_geometry():
    """Whether to draw the detailed blocks as simpler shapes."""
    return bool(settings.get("low_geometry", DEFAULT_LOW_GEOMETRY))


def set_low_geometry(enabled):
    """Remember whether the simpler shapes are wanted."""
    settings["low_geometry"] = bool(enabled)
    save()
    return settings["low_geometry"]


def transparency():
    """How far through a ghost block the person wants to see.

    Remembered, unlike the rest of what describes a pack. It belongs with the
    theme and the low geometry switch rather than with the pack name and the
    description: it is about somebody's eyes and somebody's screen, and the
    answer does not change from one structure to the next.
    """
    try:
        wanted = float(settings.get("transparency", DEFAULT_TRANSPARENCY))
    except (TypeError, ValueError):
        return DEFAULT_TRANSPARENCY
    return min(max(wanted, 0), MAX_TRANSPARENCY)


def set_transparency(value):
    """Remember the slider, clamped to the range it can actually be dragged to."""
    try:
        wanted = min(max(float(value), 0), MAX_TRANSPARENCY)
    except (TypeError, ValueError):
        return transparency()
    ## the slider fires on every pixel of a drag, and each one would otherwise
    ## be a write; only a value that actually changed is worth the file
    if wanted == settings.get("transparency"):
        return wanted
    settings["transparency"] = wanted
    save()
    return wanted


def check_updates():
    """Whether to ask for a newer release at launch."""
    return bool(settings.get("check_updates", DEFAULT_CHECK_UPDATES))


def set_check_updates(enabled):
    """Remember whether to ask. Off means nothing is sent anywhere."""
    settings["check_updates"] = bool(enabled)
    save()
    return settings["check_updates"]


def set_theme(name):
    if name in THEMES:
        settings["theme"] = name
        save()
    return settings["theme"]
