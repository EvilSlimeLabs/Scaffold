"""What language the desktop is set to, for the first launch to start in.

Nobody should have to find the language picker to read the window in their own
language, and the machine already knows the answer. It is only ever a first
guess: once a language has been chosen it is remembered, and this is not asked
again.

There is no one way to ask. POSIX keeps the answer in the environment, Windows
keeps it in the user's profile and answers through the API, and the standard
library's own `locale` reads a mixture of both. All three are tried, nearest
first, and anything unreadable is no answer rather than an error: a desktop that
cannot be asked leaves the program in English, which is what it did before.
"""
import os
import sys

## POSIX, in the order gettext reads them. LANGUAGE may hold a whole list.
VARIABLES = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")

## the values that mean "no language in particular"
NOT_A_LANGUAGE = {"c", "posix", "", "none"}


def tidy(name):
    """A locale as this program writes them: `es_MX` out of `es-mx.UTF-8@euro`.

    An operating system may report a locale with an encoding after it, a
    modifier after that, a script in the middle of it and either separator
    throughout. It may also report something that is not a locale at all:
    Windows answers `locale.getlocale` with `english_UNITED STATES`, which is a
    description rather than a code, and comes back as no answer.
    """
    if not name:
        return None
    name = str(name).split(":")[0]
    name = name.split(".")[0].split("@")[0]
    name = name.strip().replace("-", "_")
    if not name or name.lower() in NOT_A_LANGUAGE:
        return None
    parts = [part for part in name.split("_") if part]
    language = parts[0].lower()
    if not language.isalpha() or not 2 <= len(language) <= 3:
        return None
    for part in parts[1:]:
        ## a four letter part is a script, `zh_Hans_CN`, and the region is what
        ## comes after it. A region may be digits, as `es_419` is
        if len(part) == 4 and part.isalpha():
            continue
        if 2 <= len(part) <= 3 and part.isalnum():
            return "%s_%s" % (language, part.upper())
        break
    return language


def _from_environment():
    for variable in VARIABLES:
        found = tidy(os.environ.get(variable))
        if found:
            return found
    return None


def _from_windows():
    """The user's interface language, which is not the same as their formats.

    Somebody in the Netherlands may well read English menus while writing dates
    the Dutch way, and it is the menus this is choosing.
    """
    if not sys.platform.startswith("win"):
        return None
    import ctypes

    buffer = ctypes.create_unicode_buffer(85)
    kernel = ctypes.windll.kernel32
    size = ctypes.c_ulong(85)
    count = ctypes.c_ulong(0)
    ## the languages the user listed, best first, as a double null terminated
    ## block. MUI_LANGUAGE_NAME asks for names rather than numeric ids.
    MUI_LANGUAGE_NAME = 0x8
    if kernel.GetUserPreferredUILanguages(MUI_LANGUAGE_NAME,
                                          ctypes.byref(count),
                                          buffer, ctypes.byref(size)):
        first = buffer[:].split("\x00")[0]
        found = tidy(first)
        if found:
            return found
    if kernel.GetUserDefaultLocaleName(buffer, 85):
        return tidy(buffer.value)
    return None


def _from_python():
    import locale
    try:
        found = tidy(locale.getlocale(locale.LC_CTYPE)[0])
    except (TypeError, ValueError):
        found = None
    if found:
        return found
    try:
        ## deprecated, and the only one that reads the environment on every
        ## platform, so it is asked last rather than not at all
        return tidy(locale.getdefaultlocale()[0])
    except (AttributeError, TypeError, ValueError):
        return None


def read():
    """The desktop's locale, or None when it cannot be read."""
    for source in (_from_environment, _from_windows, _from_python):
        try:
            found = source()
        except Exception:
            ## a locale nobody can read is not a reason to refuse to start
            continue
        if found:
            return found
    return None
