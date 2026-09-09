# Translation Guide

Scaffold's interface is translated one file per language, in
`scaffold/lookups/lang/`. A file is named for its locale and holds one string
per line:

```ini
# English (en_US)
# Scaffold's interface, one string per line as key=value.
# See docs/TRANSLATION.md before changing anything here.

language name=English
title=Scaffold
error=Error
browse file=You need to browse for a structure file!
```

The file's name is a **locale**, named the way Minecraft names its own: a
language and a region, `en_US`, `es_MX`, `zh_CN`. That is the whole of a
language's identity here. It is the key every table is read with, the value the
picker carries, and what your settings file remembers, and nothing inside the
file repeats it: a locale written in two places is a locale that can disagree
with itself.

## Adding a language

**Add a file. That is the whole of it.**

1. **Copy `en_US.lang` to `<language>_<REGION>.lang`.** The language part is its
   [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)
   two-letter code, lower case, or its three-letter ISO 639-2 code where it has
   no two-letter one, the way Cebuano uses `ceb`. The region is the
   [ISO 3166-1](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) country code,
   upper case. `pt_BR` and `pt_PT` are different files, and so are `es_MX` and
   `es_ES`.
2. **Set `language name` to the language's own name for itself**, written in
   that language: `Español`, not `Spanish`. That line is what the picker shows
   and sorts by, and it is the one line that is never translated as a phrase.
   Where two files are the same language, say which is which:
   `Español (México)`.
3. **Translate the rest.** Keep the keys on the left of the `=` exactly as they
   are; they are what the window asks for. A line you have not got to yet can be
   left blank or deleted, and English fills the gap, so a half-finished file is
   still worth committing.
4. **Keep the `{}` markers.** They are where a file name or a count is
   substituted, and a string that loses one raises when a build finishes. Their
   order can change to suit your grammar.
5. **Save as UTF-8.** Lines starting with `#` are comments. Everything after the
   first `=` is the string, so a value may contain `=` freely.
6. **Add a colour** for the *language* in
   `scaffold/lookups/language_colors.json` if it has none. It already carries
   nearly every ISO code, and a locale with no colours of its own takes its
   language's, so `es_MX` needs nothing: it is Spanish, and it is drawn in
   Spanish's colours. A language with no entry anywhere gets the default amber,
   which is legible but says nothing.
7. **Try it.** Run Scaffold, pick your language, and read every screen. The
   window does not resize, so a label far longer than the English one is worth
   shortening.
8. **Open a pull request** with the new file.

Nothing else needs editing. The picker finds the file, shows the name you gave
it, and sorts it in alphabetically among the others. English leads the list,
being the one the rest are translated from.

**A new file is also what a machine set to that language starts in.** On its
first run, before anything has been chosen, Scaffold asks the desktop what
language it is set to and opens in the file that best serves it: that exact
locale if there is one, otherwise any file for the language, otherwise English.
So adding `es_MX.lang` is what makes a Mexican desktop open in Spanish.

### The badge

Each language wears a coloured disc carrying two or three letters, because a
flag is a country and several countries share a language. The letters are the
language part of the locale, so `es_MX` and `es_ES` both read ES and their names
tell them apart.

A file can say otherwise with a `language badge` line, which exists for the
languages where the language part says nothing useful. Pirate Speak is `en_PT`
and would read EN, so its file asks for PT instead.

## Special language cases

Do not edit `en_PT`, `lol_US`, `en_WS`, `en_UD` or `en_SGA`. They are
**generated**: English put through the transforms in `tools/app/transforms.py`. Edit
that file instead, then re-run `python -m tools.app.languages` to write
the five files out again.

`tests/test_languages.py` fails when the generated files and English have
drifted apart, and `build.py` runs the tests, so a release cannot ship them out
of step. A pull request that edits one of the five directly will not pass.

## Scripts the bundled font does not cover

The interface ships Source Sans Pro. A language whose script it does not cover
needs a face of its own, listed in `scaffold/ui/ui_fonts.py`. That table is read
by locale and then by language, so listing `zh` covers `zh_CN` and `zh_TW`
alike. If your language needs a face, say so in the pull request rather than
adding a font: the file has to be licensed for redistribution and is subset by
`tools/app/fonts.py` to the characters the window actually uses. Re-run that
script after adding a translation in a script that is already covered, or its
new characters will be missing from the subset.
