"""Build the font files Scaffold ships.

Two of them cannot simply be copied in.

**The CJK face.** Noto Sans SC is 17 MB because it carries every character in
Simplified Chinese. The window needs the few hundred that appear in its own
translations, so it is subset down to exactly those, a hundredth of the size for
a file that renders every string the program can display. Re-run this after
adding or changing a Chinese translation, or the new characters will be missing.

**The enchanting face.** Minecraft's enchanting table script is a font, not a
set of characters: there is no Unicode block for it, so no string can be the
real thing. The runes come from Monocraft, a pixel font under the SIL Open Font
License that carries the Standard Galactic Alphabet in its private use area,
kept in `art/Monocraft.ttf` with its licence beside it. This copies the 26 runes
into a small TTF of their own, mapping each Latin letter, upper and lower case,
to the rune that stands for it, so the Enchanting language is genuinely
readable by substitution, the way the alphabet is meant to be. The licence
travels with the result as `fonts/ScaffoldEnchanting-LICENSE.txt`.

    python -m tools.app.fonts

Needs fonttools, and for the CJK subset a copy of Noto Sans SC to subset from.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTS = os.path.join(ROOT, "scaffold", "fonts")
LANGS = os.path.join(ROOT, "scaffold", "lookups", "lang")
SGA_SOURCE = os.path.join(ROOT, "art", "Monocraft.ttf")
SGA_LICENCE = os.path.join(ROOT, "art", "Monocraft-LICENSE.txt")
## where Monocraft keeps the rune for A; B to Z follow it in order
SGA_FIRST = 0xEB40

CJK_OUT = "NotoSansSC-Scaffold.ttf"
SGA_OUT = "ScaffoldEnchanting.ttf"
SGA_LICENCE_OUT = "ScaffoldEnchanting-LICENSE.txt"
SGA_FAMILY = "Scaffold Enchanting"


def used_characters():
    """Every character the window can display, from every translation."""
    chars = set(" 0123456789.,:;!?()[]{}/\\-_+=%#@&*'\"|<>~")
    for name in sorted(os.listdir(LANGS)):
        if not name.endswith(".lang"):
            continue
        with open(os.path.join(LANGS, name), encoding="utf-8-sig") as f:
            for line in f:
                chars.update(line)
    ## the pack name, description and file names are the user's own text and
    ## cannot be known here; Latin and the digits above cover the common case
    for start, end in ((0x20, 0x7F),):
        chars.update(chr(c) for c in range(start, end))
    return {c for c in chars if c.strip() or c == " "}


def subset_cjk(source):
    """Cut Noto Sans SC down to the characters the interface actually uses."""
    from fontTools import subset

    chars = used_characters()
    target = os.path.join(FONTS, CJK_OUT)
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.recalc_bounds = True
    options.drop_tables = ["DSIG"]
    font = subset.load_font(source, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    subset.save_font(font, target, options)
    font.close()
    print("   %-28s %.0f KB from %.1f MB (%d characters)"
          % (CJK_OUT, os.path.getsize(target) / 1024,
             os.path.getsize(source) / 1024 / 1024, len(chars)))
    return target


## The rune face's proportions, in the units its glyphs are drawn in.
## SGA_CAP_HEIGHT is where the top of a rune sits, as a fraction of an em, and
## is matched to the interface face so a line of runes is the same height as a
## line of Latin. SGA_LETTER_GAP is the blank the advance leaves after the ink,
## in glyph pixels, and SGA_SPACE is the width of a word space in the same.
SGA_CAP_HEIGHT = 0.68
SGA_LETTER_GAP = 1.0
SGA_SPACE = 3.0


## Midnight on the first of January 2000, in the seconds-since-1904 a font's
## head table counts in. Any fixed moment would do; what matters is that it does
## not move.
EPOCH = 3029529600


def build_sga(source_path):
    """Copy Monocraft's runes into a font of their own and assemble a TTF.

    Monocraft is monospaced, and a rune centred in a cell as wide as any other
    spaces the runes almost twice as far apart as the letters of any other
    language, which pushes the interface's own labels past their controls. So
    each rune is moved to the left edge of its cell and spaced by the ink it
    carries, and scaled so it stands as tall as the interface face's capitals.
    """
    import shutil
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont

    source = TTFont(source_path)
    shapes = source.getGlyphSet()
    source_cmap = source.getBestCmap()
    upem = 1024
    tall = max(source["glyf"][source_cmap[SGA_FIRST + i]].yMax for i in range(26))
    scale = upem * SGA_CAP_HEIGHT / tall
    ## one of Monocraft's pixels, which the gaps below are counted in: a rune
    ## is seven of them tall
    pixel = scale * tall / 7

    glyph_order = [".notdef", "space"]
    char_map = {32: "space"}
    pens = {}
    ink = {}
    for i in range(26):
        upper = ord("A") + i
        name = "uni%04X" % upper
        drawn = source["glyf"][source_cmap[SGA_FIRST + i]]
        pen = TTGlyphPen(None)
        shapes[source_cmap[SGA_FIRST + i]].draw(
            TransformPen(pen, (scale, 0, 0, scale, -drawn.xMin * scale, 0)))
        pens[name] = pen.glyph()
        ink[name] = (drawn.xMax - drawn.xMin) * scale
        glyph_order.append(name)
        ## the lower case letters share the upper case runes, as the game does
        char_map[upper] = name
        char_map[upper + 32] = name

    builder = FontBuilder(upem, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(char_map)

    empty = TTGlyphPen(None).glyph()
    glyphs = {".notdef": empty, "space": empty}
    glyphs.update(pens)
    builder.setupGlyf(glyphs)

    ## an advance per glyph, its ink and a gap after it; see the docstring
    metrics = {name: (int(width + SGA_LETTER_GAP * pixel), 0)
               for name, width in ink.items()}
    metrics[".notdef"] = (int((SGA_SPACE + SGA_LETTER_GAP) * pixel), 0)
    metrics["space"] = (int((SGA_SPACE + SGA_LETTER_GAP) * pixel), 0)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=int(upem * 0.8), descent=-int(upem * 0.2))
    ## Windows refuses to register a font that is missing the full name or the
    ## unique identifier, and refuses it silently, because AddFontResourceEx
    ## returns zero and says no more. Every record GDI looks for is filled in
    ## here.
    builder.setupNameTable({
        "familyName": SGA_FAMILY,
        "styleName": "Regular",
        "uniqueFontIdentifier": "%s; Scaffold" % SGA_FAMILY,
        "fullName": SGA_FAMILY,
        "version": "Version 1.000",
        "psName": SGA_FAMILY.replace(" ", ""),
        "copyright": "Copyright (c) 2022, Idrees Hassan "
                     "(https://github.com/IdreesInc/Monocraft). The Standard "
                     "Galactic Alphabet of Monocraft, rescaled and spaced for "
                     "Scaffold.",
        "licenseDescription": "This Font Software is licensed under the SIL Open "
                              "Font License, Version 1.1.",
        "licenseInfoURL": "https://openfontlicense.org",
    })
    builder.setupOS2(sTypoAscender=int(upem * 0.8), usWinAscent=int(upem * 0.8),
                     usWinDescent=int(upem * 0.2))
    builder.setupPost()
    builder.setupDummyDSIG()
    ## fontTools stamps the hour it ran into the head table, so a font rebuilt
    ## from the same glyphs is a different file every time and every build shows
    ## up as a change to it. The build regenerates everything it ships, so the
    ## stamp is pinned and the font is the same bytes until the glyphs change.
    builder.font["head"].created = EPOCH
    builder.font["head"].modified = EPOCH
    target = os.path.join(FONTS, SGA_OUT)
    builder.save(target)
    shutil.copyfile(SGA_LICENCE, os.path.join(FONTS, SGA_LICENCE_OUT))
    print("   %-28s %.0f KB (%d glyphs)"
          % (SGA_OUT, os.path.getsize(target) / 1024, len(pens)))
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--noto", help="path to a full Noto Sans SC to subset from")
    args = ap.parse_args()

    os.makedirs(FONTS, exist_ok=True)
    print("building fonts into fonts/")
    if args.noto and os.path.isfile(args.noto):
        subset_cjk(args.noto)
    else:
        print("   %-28s skipped, no --noto source given" % CJK_OUT)
    build_sga(SGA_SOURCE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
