"""Write the special languages out as ordinary language files.

    python -m tools.app.languages

Pirate Speak, LOLCAT, Shakespearean and upside-down English are English put
through a transform, and Enchanting is English left alone and rendered in the
rune face. The program reads all five as language files like any other, which is
what makes adding a language nothing more than adding a file. Writing them by
hand would mean sixty-odd strings times five to keep in step with every label
anyone adds, so they are generated from `en_US.lang` and committed.

**Re-run this after changing an English string**, or the special languages still
say the old one. `tests/test_languages.py` fails when they have drifted.

The transforms themselves are in `tools/app/transforms.py`.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.app import transforms as lang_fun
from scaffold import lang_parse

LANGS = os.path.join(ROOT, "scaffold", "lookups", "lang")
ENGLISH = "en_US"

HEADER = """# %s (%s)
# Generated from en_US.lang by tools/app/languages.py. Do not edit by
# hand: re-run that script instead, or the next English string added leaves this
# one behind.
"""


def source():
    """The English file, in the order it is written in."""
    ordered = []
    path = os.path.join(LANGS, "%s%s" % (ENGLISH, lang_parse.SUFFIX))
    with io.open(path, encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sign, value = line.partition("=")
            if sign:
                ordered.append((key.strip(), value))
    return ordered


def write(locale, transform, name, badge, english):
    """One special language, in the order the English file has."""
    lines = [HEADER % (name, locale)]
    for key, value in english:
        if key == lang_parse.NAME_KEY:
            ## the transform runs over English, whose own name for itself is
            ## "English", and a special language is not called that
            value = name
        elif key == lang_parse.BADGE_KEY:
            continue
        else:
            value = transform(value)
        lines.append("%s=%s" % (key, value))
    ## these are English underneath, so the badge cannot read the language part
    lines.append("%s=%s" % (lang_parse.BADGE_KEY, badge))
    body = "\n".join(lines) + "\n"
    path = os.path.join(LANGS, "%s%s" % (locale, lang_parse.SUFFIX))
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    return path


def main():
    english = source()
    print("writing %d strings into each special language" % len(english))
    for locale, (transform, name, badge) in lang_fun.TRANSFORMS.items():
        path = write(locale, transform, name, badge, english)
        ## the file name, not the language's own name for itself: a Windows
        ## console is cp1252 and upside-down English is not writable in it
        print("   %-7s %s" % (locale, os.path.basename(path)))


if __name__ == "__main__":
    main()
