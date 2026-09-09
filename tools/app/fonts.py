"""Build the font files Scaffold ships.

Two of them cannot simply be copied in.

**The CJK face.** Noto Sans SC is 17 MB because it carries every character in
Simplified Chinese. The window needs the few hundred that appear in its own
translations, so it is subset down to exactly those, a hundredth of the size for
a file that renders every string the program can display. Re-run this after
adding or changing a Chinese translation, or the new characters will be missing.

**The enchanting face.** Minecraft's enchanting table script is a font, not a
set of characters: there is no Unicode block for it, so no string can be the
real thing. The glyphs live in the resource pack as a bitmap sheet, and this
traces them into outlines and assembles a TTF, mapping each Latin letter to the
rune that stands for it. That makes the Enchanting language genuinely readable
by substitution, the way the alphabet is meant to be.

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
SGA_SHEET = os.path.join(ROOT, "CommunityVanillaResourcePack", "font", "ascii_sga.png")

CJK_OUT = "NotoSansSC-Scaffold.ttf"
SGA_OUT = "ScaffoldEnchanting.ttf"
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


## The rune face's proportions, in the units its sheet is drawn in.
## SGA_CAP_HEIGHT is where the top of a rune sits, as a fraction of an em, and
## is matched to the interface face so a line of runes is the same height as a
## line of Latin. SGA_LETTER_GAP is the blank the advance leaves after the ink,
## in sheet pixels, and SGA_SPACE is the width of a word space in the same.
SGA_CAP_HEIGHT = 0.68
SGA_LETTER_GAP = 1.0
SGA_SPACE = 3.0


def sga_cells(sheet_path):
    """The 16x16 grid of glyphs, as a map of ASCII code to a pixel mask."""
    from PIL import Image
    sheet = Image.open(sheet_path).convert("RGBA")
    cell_w = sheet.width // 16
    cell_h = sheet.height // 16
    cells = {}
    for index in range(256):
        col, row = index % 16, index // 16
        box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
        tile = sheet.crop(box)
        pixels = tile.load()
        mask = [[pixels[x, y][3] > 8 for x in range(cell_w)] for y in range(cell_h)]
        if any(any(line) for line in mask):
            cells[index] = mask
    return cells, cell_w, cell_h


## Midnight on the first of January 2000, in the seconds-since-1904 a font's
## head table counts in. Any fixed moment would do; what matters is that it does
## not move.
EPOCH = 3029529600


def build_sga(sheet_path):
    """Trace the glyph sheet into outlines and assemble a TTF.

    Every opaque pixel becomes one square contour. A font made of thousands of
    little squares sounds wasteful and is: it is also exactly what the source
    art is, and it renders correctly at any size, which a smarter tracing would
    have to work to match.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    cells, cell_w, cell_h = sga_cells(sheet_path)
    upem = 1024
    ## the sheet's rows sit on a baseline a quarter up from the cell bottom
    baseline = cell_h * 0.75
    ## Scaled so the runes stand as tall as the interface face's capitals
    ## rather than filling the cell. A cell is drawn to be tiled, so its height
    ## is the line, not the letter: taking it as the letter made every rune a
    ## sixth taller than the Latin text it sits beside.
    scale = upem * SGA_CAP_HEIGHT / baseline

    glyph_order = [".notdef", "space"]
    char_map = {32: "space"}
    pens = {}
    ink = {}

    for code, mask in cells.items():
        if code < 33 or code > 126:
            continue
        name = "uni%04X" % code
        pen = TTGlyphPen(None)
        for y, line in enumerate(mask):
            x = 0
            while x < cell_w:
                if not line[x]:
                    x += 1
                    continue
                run = x
                while run < cell_w and line[run]:
                    run += 1
                x0 = x * scale
                x1 = run * scale
                y0 = (baseline - (y + 1)) * scale
                y1 = (baseline - y) * scale
                pen.moveTo((x0, y0))
                pen.lineTo((x1, y0))
                pen.lineTo((x1, y1))
                pen.lineTo((x0, y1))
                pen.closePath()
                x = run
        pens[name] = pen.glyph()
        ## how far the ink actually reaches, which is what the advance is set
        ## from; every rune is drawn hard against the left of its cell
        columns = [x for x in range(cell_w)
                   if any(mask[y][x] for y in range(cell_h))]
        ink[name] = (columns[-1] + 1) if columns else SGA_SPACE
        glyph_order.append(name)
        char_map[code] = name
        ## the lower case letters share the upper case runes, as the game does
        if 65 <= code <= 90:
            char_map[code + 32] = name

    builder = FontBuilder(upem, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(char_map)

    empty = TTGlyphPen(None).glyph()
    glyphs = {".notdef": empty, "space": empty}
    glyphs.update(pens)
    builder.setupGlyf(glyphs)

    ## An advance per glyph, measured from the ink. Every cell is eight pixels
    ## across and no rune is wider than five, so a cell-wide advance spaced the
    ## runes almost twice as far apart as the letters of any other language,
    ## which pushes the interface's own labels past their controls.
    metrics = {name: (int((width + SGA_LETTER_GAP) * scale), 0)
               for name, width in ink.items()}
    metrics[".notdef"] = (int((SGA_SPACE + SGA_LETTER_GAP) * scale), 0)
    metrics["space"] = (int((SGA_SPACE + SGA_LETTER_GAP) * scale), 0)
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
        "copyright": "Glyph shapes traced from the Minecraft resource pack's "
                     "ascii_sga.png, which Scaffold already redistributes as "
                     "part of its trimmed vanilla pack.",
    })
    builder.setupOS2(sTypoAscender=int(upem * 0.8), usWinAscent=int(upem * 0.8),
                     usWinDescent=int(upem * 0.2))
    builder.setupPost()
    builder.setupDummyDSIG()
    ## fontTools stamps the hour it ran into the head table, so a font rebuilt
    ## from the same sheet is a different file every time and every build shows
    ## up as a change to it. The build regenerates everything it ships, so the
    ## stamp is pinned and the font is the same bytes until the sheet changes.
    builder.font["head"].created = EPOCH
    builder.font["head"].modified = EPOCH
    target = os.path.join(FONTS, SGA_OUT)
    builder.save(target)
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
    if os.path.isfile(SGA_SHEET):
        build_sga(SGA_SHEET)
    else:
        print("   %-28s skipped, %s is missing" % (SGA_OUT, SGA_SHEET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
