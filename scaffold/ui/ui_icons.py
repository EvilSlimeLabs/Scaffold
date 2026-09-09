"""Small interface glyphs, drawn rather than shipped.

Two reasons they are drawn here. They follow the accent colour, so changing the
palette changes them; and they come out at whatever size the window is running
at rather than being a fixed-size PNG that goes soft on a scaled display.

Everything is drawn at several times the requested size and reduced, because a
diagonal or a rounded corner rasterised straight to 16 px has visibly stepped
edges.
"""
import math
from PIL import Image, ImageChops, ImageDraw

SCALE = 4


def _canvas(size):
    big = size * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image), big


def folder(size=16, colour=(200, 137, 28)):
    """A folder, for the controls that open a file or directory chooser."""
    image, draw, big = _canvas(size)
    fill = tuple(colour) + (255,)
    unit = big / 16.0

    ## the raised tab along the back edge
    draw.rounded_rectangle((unit * 1, unit * 3, unit * 7, unit * 6),
                           radius=unit * 0.9, fill=fill)
    ## the body
    draw.rounded_rectangle((unit * 1, unit * 4.6, unit * 15, unit * 13),
                           radius=unit * 1.4, fill=fill)
    ## a lighter front flap, so the shape reads as a folder and not a box
    lighter = tuple(min(255, int(c * 1.25)) for c in colour) + (255,)
    draw.rounded_rectangle((unit * 1, unit * 6.6, unit * 15, unit * 13),
                           radius=unit * 1.4, fill=lighter)
    return image.resize((size, size), Image.LANCZOS)


def cross(size=16, colour=(139, 148, 163), weight=1.6):
    """A plain ✕, for clearing a choice."""
    image, draw, big = _canvas(size)
    fill = tuple(colour) + (255,)
    unit = big / 16.0
    pad = unit * 4
    width = int(unit * weight)
    draw.line((pad, pad, big - pad, big - pad), fill=fill, width=width)
    draw.line((big - pad, pad, pad, big - pad), fill=fill, width=width)
    return image.resize((size, size), Image.LANCZOS)


def plus(size=16, colour=(139, 148, 163), weight=1.5):
    """The + on the control that adds a structure."""
    image, draw, big = _canvas(size)
    fill = tuple(colour) + (255,)
    unit = big / 16.0
    width = int(unit * weight)
    pad = unit * 2.5
    draw.line((pad, big / 2.0, big - pad, big / 2.0), fill=fill, width=width)
    draw.line((big / 2.0, pad, big / 2.0, big - pad), fill=fill, width=width)
    return image.resize((size, size), Image.LANCZOS)


def chevron(size=16, colour=(139, 148, 163), weight=1.7, up=False):
    """The v that says a control opens a list."""
    image, draw, big = _canvas(size)
    fill = tuple(colour) + (255,)
    unit = big / 16.0
    width = int(unit * weight)
    ## a third of the height, centred, so it reads as a mark rather than an
    ## arrowhead: wider than it is tall, the way a menu's chevron is drawn
    left, right = unit * 3.5, big - unit * 3.5
    top, bottom = unit * 6.4, unit * 9.6
    if up:
        top, bottom = bottom, top
    draw.line((left, top, big / 2.0, bottom), fill=fill, width=width)
    draw.line((big / 2.0, bottom, right, top), fill=fill, width=width)
    return image.resize((size, size), Image.LANCZOS)


def corner(size=16, colour=(200, 137, 28), weight=1.6):
    """Two edges meeting: the corner a big build is measured from."""
    image, draw, big = _canvas(size)
    fill = tuple(colour) + (255,)
    unit = big / 16.0
    width = int(unit * weight)
    draw.line((unit * 3, unit * 3, unit * 3, unit * 13), fill=fill, width=width)
    draw.line((unit * 3, unit * 13, unit * 13, unit * 13), fill=fill, width=width)
    draw.ellipse((unit * 1.6, unit * 1.6, unit * 4.4, unit * 4.4), fill=fill)
    return image.resize((size, size), Image.LANCZOS)


## where the cut crosses the frame, as a fraction of its width. The window
## needs the same numbers to work out whether a click landed in the wedge.
WEDGE_TOP = 0.70
WEDGE_SIDE = 0.30


## The X in the cut corner, as fractions of the largest circle that fits
## inside the wedge: how far the arms reach from its centre, and how thick they
## are drawn.
MARK_REACH = 0.30
MARK_WEIGHT = 0.135


def _incircle(a, b, c):
    """The centre and radius of the circle inscribed in a triangle.

    Returned in the same units the corners were given in. The centre is the
    weighted mean of the corners, each weighted by the length of the side
    opposite it; the radius is the area over the half perimeter.
    """
    def span(p, q):
        return math.hypot(q[0] - p[0], q[1] - p[1])

    la, lb, lc = span(b, c), span(c, a), span(a, b)
    total = la + lb + lc
    if total <= 0:
        return a[0], a[1], 0.0
    x = (la * a[0] + lb * b[0] + lc * c[0]) / total
    y = (la * a[1] + lb * b[1] + lc * c[1]) / total
    area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
    return x, y, area / (total / 2.0)


def _frame_box(size, radius, width):
    """The frame's outline, at the size it is actually drawn at.

    Returns the supersampled canvas size, the box the outline follows, its
    corner radius and its stroke, so that the frame and anything masked to it
    are working from one description rather than two that have to be kept in
    step by hand.
    """
    big = size * SCALE
    stroke = max(1, int(width * SCALE))
    ## a stroke is centred on the line it follows, so an outline drawn hard
    ## against the edge of the picture loses half its width off the side
    pad = stroke / 2.0
    return big, (pad, pad, big - pad - 1, big - pad - 1), radius * SCALE, stroke


def frame_mask(size, radius, width):
    """The area the frame encloses, as a mask for the layers beneath it.

    Drawn from the same box and radius as the outline and reduced the same way,
    so the two curves are the same curve. Building the mask at the finished size
    instead leaves the background a fraction of a pixel wide outside the
    outline's corners, where the frame's smooth arc and the mask's rasterised
    one disagree.
    """
    big, box, r, _stroke = _frame_box(int(size), radius, width)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=r, fill=255)
    return mask.resize((int(size), int(size)), Image.LANCZOS)


## How much further out the corner can be clicked than it is drawn, as a
## fraction of the control. The cut is deliberately a small mark, and a small
## mark is a small target. Drawn at its own size it is a triangle about thirty
## points on a side, most of which is the thin part near the diagonal. The
## clickable corner is pushed out by this much so it can be hit comfortably;
## the hover lights the drawn wedge as soon as the pointer is inside the larger
## zone, so what answers the pointer is still what the user sees.
WEDGE_SLOP = 0.11


def in_wedge(x, y, size, slop=WEDGE_SLOP):
    """Whether a point inside the control falls in the cut corner."""
    if size <= 0:
        return False
    fx, fy = x / float(size), y / float(size)
    ## the same diagonal the wedge is drawn with, moved down and to the left,
    ## which grows the triangle without changing its shape
    top, side = WEDGE_TOP - slop, WEDGE_SIDE + slop
    return (fy - 0.0) * (1.0 - top) < (fx - top) * (side - 0.0)


def icon_control(size, radius, art=None, background=(25, 29, 36),
                 line=(46, 52, 62), width=1.6, cut=False,
                 hot_control=False, hot_corner=False,
                 wedge=(34, 40, 49), mark=(139, 148, 163),
                 hot_wedge=None, hot_mark=None):
    """The pack icon control, drawn as one picture, bottom layer first.

    Tk cannot clip a widget to a rounded rectangle, so a control built out of
    stacked widgets always ends up with one of them poking a square corner past
    another's curve, or painting over the layer below it. Drawing the whole
    thing once removes the question: everything here is masked to the same
    rounded shape, so nothing can render outside the frame.

    The layers, in order:

      1. the background, which is what lights up under the pointer
      2. the preview image, scaled to fit whole and centred
      3. the frame, on the shape's own edge
      4. the cut corner and its X, when there is an icon to clear

    Everything outside the rounded shape is left transparent, so the panel
    behind the control shows through it.
    """
    size = int(size)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    ## everything below the frame is masked to the frame's own outline, so the
    ## background cannot show past the edge that is supposed to contain it
    shape = frame_mask(size, radius, width)

    ## 1. the background layer
    fill = tuple(min(255, int(c * 1.45)) for c in background) if hot_control \
        else tuple(background)
    image.paste(Image.new("RGBA", (size, size), fill + (255,)), (0, 0), shape)

    ## 2. the preview, whole and centred
    if art is not None:
        ratio = min(size / art.width, size / art.height)
        fitted = art.resize((max(1, round(art.width * ratio)),
                             max(1, round(art.height * ratio))), Image.LANCZOS)
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        layer.alpha_composite(fitted, ((size - fitted.width) // 2,
                                       (size - fitted.height) // 2))
        image.paste(layer, (0, 0), Image.composite(
            layer.split()[3], Image.new("L", (size, size), 0), shape))

    ## 3 and 4. the frame, and the corner taken out of it
    image.alpha_composite(icon_frame(size, radius=radius, inset=0, line=line,
                                     width=width, cut=cut, wedge=wedge,
                                     mark=mark, hot=hot_corner,
                                     hot_wedge=hot_wedge, hot_mark=hot_mark))
    return image


def icon_frame(size=72, radius=12, inset=0, line=(96, 106, 122), width=1.6,
               cut=False, wedge=(34, 40, 49), wedge_alpha=255,
               mark=(139, 148, 163), hot=False,
               hot_wedge=None, hot_mark=None):
    """The pack icon's frame, drawn as one piece.

    A rounded box outline the whole way round. When there is a custom icon to
    clear, its top right corner is taken out by a diagonal, with an X in the
    piece that is missing. Frame and cut are one drawing rather than a
    border on one widget and a badge stuck over another, so the outline stays
    continuous and the cut reads as part of the same shape.

    Everything except the outline and the wedge is transparent, so the control
    underneath still shows through and still lights up on hover.
    """
    image, draw, big = _canvas(size)
    big, box, r, stroke = _frame_box(size, radius, width)
    pad = box[0]

    if cut:
        ## The pointer swaps in a second pair of colours rather than brightening
        ## the first. Multiplying works in a dark theme and does nothing in a
        ## light one, where the corner is already white.
        if hot:
            wedge = tuple(hot_wedge if hot_wedge is not None else wedge)
            mark = tuple(hot_mark if hot_mark is not None else mark)
            wedge_alpha = 255
        ## the wedge: the frame's own rounded corner on the outside, the
        ## diagonal on the inside
        corner = Image.new("L", (big, big), 0)
        ImageDraw.Draw(corner).rounded_rectangle(box, radius=r, fill=255)
        triangle = Image.new("L", (big, big), 0)
        span = big - 2 * pad
        ImageDraw.Draw(triangle).polygon(
            [(pad + span * WEDGE_TOP, pad), (big - pad, pad),
             (big - pad, pad + span * WEDGE_SIDE)], fill=255)
        fill = Image.new("RGBA", (big, big), tuple(wedge) + (wedge_alpha,))
        image.paste(fill, (0, 0),
                    Image.composite(triangle, Image.new("L", (big, big), 0), corner))

        draw = ImageDraw.Draw(image)
        ## the diagonal that closes the cut
        draw.line((pad + span * WEDGE_TOP, pad, big - pad, pad + span * WEDGE_SIDE),
                  fill=tuple(line) + (255,), width=stroke)
        ## and the X, placed and sized by the wedge's inscribed circle.
        ## The centre of the largest circle that fits inside a triangle is
        ## where a symmetric mark looks centred; the mean of the corners pulls
        ## it towards the long side and leaves the X crowding the diagonal.
        ## Sizing it from that circle rather than from the frame's stroke also
        ## keeps the mark the same whatever weight the outline is drawn at.
        cx, cy, inner = _incircle((WEDGE_TOP, 0.0), (1.0, 0.0), (1.0, WEDGE_SIDE))
        cx = pad + span * cx
        cy = pad + span * cy
        inner *= span
        arm = inner * MARK_REACH
        pen = max(1, int(round(inner * MARK_WEIGHT)))
        draw.line((cx - arm, cy - arm, cx + arm, cy + arm),
                  fill=tuple(mark) + (255,), width=pen)
        draw.line((cx + arm, cy - arm, cx - arm, cy + arm),
                  fill=tuple(mark) + (255,), width=pen)

    ## The outline last, so it sits on top of the wedge and stays unbroken. It
    ## is the area between the frame's box and the same box shrunk by the
    ## stroke, rather than a drawn outline: an outline and a fill of the same
    ## rounded rectangle are rasterised by different code in PIL and their
    ## corner arcs do not land on identical pixels, which left the masked
    ## background showing a sliver outside the outline at each corner. Taking
    ## the ring out of the very mask those layers are clipped to makes the two
    ## edges the same edge.
    outer = Image.new("L", (big, big), 0)
    ImageDraw.Draw(outer).rounded_rectangle(box, radius=r, fill=255)
    inner = Image.new("L", (big, big), 0)
    ImageDraw.Draw(inner).rounded_rectangle(
        (box[0] + stroke, box[1] + stroke, box[2] - stroke, box[3] - stroke),
        radius=max(1, r - stroke), fill=255)
    image.paste(Image.new("RGBA", (big, big), tuple(line) + (255,)), (0, 0),
                ImageChops.subtract(outer, inner))
    return image.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    sheet = Image.new("RGBA", (3 * 56, 56), (48, 50, 56, 255))
    for i, glyph in enumerate((folder(40), cross(40), corner(40))):
        sheet.alpha_composite(glyph, (i * 56 + 8, 8))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save("ui_icons_preview.png")
    print("wrote ui_icons_preview.png")
