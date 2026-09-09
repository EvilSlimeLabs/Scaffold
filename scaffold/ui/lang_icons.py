"""Round language badges carrying a language code.

A flag is a country, and a country is not a language: Spanish is not Spain,
English is not England, and picking one flag per language tells a good part of
the world their language belongs to somebody else. The picker therefore labels
each language with its code on a disc, with the language's own name alongside.

The disc is coloured from `lookups/language_colors.json`, which is
AnandChowdhary/language-icons' colours.json with three additions: an entry for
each constructed language, one for Cebuano, which the upstream file does not
carry, and a `default` for anything unlisted. A language may name one, two or
three colours and the disc is divided into that many equal diagonal bands, so
one fills it, two split it along the diagonal, and three take a third each.

Drawn here rather than shipped as art so a badge comes out at whatever size and
scaling the window is running at, and in the bundled typeface rather than
whichever one the machine happens to have.

One badge is borrowed: upside-down English wears the English badge turned over.
"""
import json

from PIL import Image, ImageDraw, ImageFont, ImageOps

from scaffold import lang_parse
from scaffold import paths
from scaffold.ui import ui_fonts

COLOURS_FILE = "language_colors.json"
DEFAULT_KEY = "default"

_colours = None
_font_cache = {}


def colours():
    """The whole colour table, read once."""
    global _colours
    if _colours is None:
        try:
            with open(paths.lookup(COLOURS_FILE), encoding="utf-8") as f:
                _colours = json.load(f)
        except (OSError, ValueError):
            _colours = {}
    return _colours


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def colour(locale):
    """The one, two or three colours a locale is drawn in.

    A locale with no colours of its own takes its language's, which is what lets
    es_MX be added beside es_ES as a file and nothing else. Only a language that
    is its own thing, rather than a region of another, needs an entry.
    """
    table = colours()
    entry = (table.get(locale)
             or table.get(lang_parse.language_of(locale))
             or table.get(DEFAULT_KEY) or ["#E2A834"])
    return [_rgb(c) for c in entry[:3]]


def _font(size):
    if size not in _font_cache:
        font = None
        for weight in ("Semibold", "Bold", "Regular"):
            candidate = ui_fonts.truetype(weight)
            if not candidate:
                continue
            try:
                font = ImageFont.truetype(candidate, size)
                break
            except (OSError, IOError):
                continue
        _font_cache[size] = font or ImageFont.load_default()
    return _font_cache[size]


def _band(size, low, high):
    """The polygon of the square where `low` <= x + y <= `high`.

    The bands run corner to corner, so a two colour badge is split along its
    diagonal rather than down the middle.
    """
    def clip(points, keep_above, threshold):
        out = []
        for i, current in enumerate(points):
            previous = points[i - 1]
            cv = current[0] + current[1] - threshold
            pv = previous[0] + previous[1] - threshold
            c_in = cv >= 0 if keep_above else cv <= 0
            p_in = pv >= 0 if keep_above else pv <= 0
            if p_in != c_in and pv != cv:
                t = pv / (pv - cv)
                out.append((previous[0] + (current[0] - previous[0]) * t,
                            previous[1] + (current[1] - previous[1]) * t))
            if c_in:
                out.append(current)
        return out

    shape = clip([(0, 0), (size, 0), (size, size), (0, size)], True, low)
    return clip(shape, False, high)


## A badge drawn as another language's, turned over. Upside-down English is the
## only one: it is English, upside down, so its badge is the English badge the
## same way round as the language. A vertical flip mirrors the slant of the
## bands as well as the letters, which a half turn would not.
UPSIDE_DOWN = {"en_UD": "en_US"}


def badge(locale, size=22, fill=None, text=None, scale=4, label=None):
    """A disc in a language's colours, optionally carrying its letters.

    The letters are off by default. At the size the picker uses, two or three
    of them over a two or three colour field are hard to read whatever is done
    to them, and the language's own name is always written beside the badge, so
    they repeat something already legible. Pass `text` to draw them anyway.

    `label` is what they say, and defaults to the language part of the locale.
    A language file can name its own where that is not the thing to show, which
    is how Pirate Speak reads PT rather than EN.

    Drawn at `scale` times the requested size and reduced, because a circle and
    a diagonal both come out visibly stepped when rasterised straight to 22 px.
    """
    borrowed = UPSIDE_DOWN.get(locale)
    if borrowed and fill is None:
        ## the borrowed badge is drawn as its own language, letters and all
        return ImageOps.flip(badge(borrowed, size, fill, text, scale))

    palette = [tuple(c) for c in fill] if fill else colour(locale)
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    bands = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bands)

    count = max(1, len(palette))
    span = (2.0 * big) / count
    for i, band_colour in enumerate(palette):
        shape = ([(0, 0), (big, 0), (big, big), (0, big)] if count == 1
                 else _band(big, i * span, (i + 1) * span))
        if len(shape) >= 3:
            draw.polygon(shape, fill=tuple(band_colour) + (255,))

    ## the bands are square; the disc is what is kept of them
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    img.paste(bands, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    ## a rim, so a pale band still has an edge against a pale panel
    draw.ellipse((0, 0, big - 1, big - 1), outline=(0, 0, 0, 90),
                 width=max(1, int(big * 0.045)))

    if text is not None:
        label = (label or lang_parse.language_of(locale) or "?").upper()[:3]
        font = _font(int(big * (0.52 if len(label) < 3 else 0.38)))
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        position = ((big - (right + left)) / 2, (big - (bottom + top)) / 2)
        ## an outline under the letters: the bands behind them can be any
        ## colour at all, and white alone disappears on a white band
        draw.text(position, label, font=font, fill=tuple(text) + (255,),
                  stroke_width=max(1, int(big * 0.035)), stroke_fill=(0, 0, 0, 190))
    return img.resize((size, size), Image.LANCZOS)


def pair(locale, size=22, light=None, dark=None,
         light_text=None, dark_text=None, label=None):
    """(light mode image, dark mode image) for one locale.

    The colours belong to the language, not to the window, so both modes get the
    same picture unless a caller overrides them.
    """
    return (badge(locale, size, light, light_text, label=label),
            badge(locale, size, dark, dark_text, label=label))


if __name__ == "__main__":
    table = lang_parse.parse()
    codes = list(table)
    sheet = Image.new("RGBA", (len(codes) * 52 + 8, 60), (60, 60, 60, 255))
    for i, code in enumerate(codes):
        sheet.alpha_composite(
            badge(code, 44, label=lang_parse.badge(code, table)), (i * 52 + 8, 8))
    sheet.save("lang_badges_preview.png")
    print("wrote lang_badges_preview.png")
