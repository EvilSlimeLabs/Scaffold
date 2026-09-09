"""Regenerate the Scaffold icons.

Draws a 5x5x5 isometric cube of hologram panes with the Scaffold S snaking
through it in yellow concrete, and writes both icons the project ships:

    scaffold/lookups/pack_icon.png
                            256x256, over the Slime Lab background art. This is
                            the icon copied into every generated pack, where it
                            sits in Minecraft's pack list as a filled tile.
    scaffold/lookups/app_icon.png
                            256x256 on transparency. The window's own title bar
                            icon, which is composed against the title bar rather
                            than sitting in a tile of its own.
    scaffold/images/pack_icon.ico
                            the desktop icon, 16 px through 256 px, on
                            transparency. A taskbar or Explorer icon is composed
                            against whatever is behind it, so it carries the
                            iconography alone. A baked-in background would show
                            as a square tile against every theme.

The block faces are real textures out of Vanilla_Resource_Pack; only the panes
are hand authored, and they are generated here rather than stored, so the grid
colour and weight are the two numbers at the top of this file.

Run from the repository root:  python -m tools.app.icon
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                    "textures", "blocks")
BACKGROUND = os.path.join(ROOT, "art", "background_slimelab.png")
PACK_ICON = os.path.join(ROOT, "scaffold", "lookups", "pack_icon.png")
APP_ICON = os.path.join(ROOT, "scaffold", "lookups", "app_icon.png")
DESKTOP_ICON = os.path.join(ROOT, "scaffold", "images", "pack_icon.ico")

# --- the look ---------------------------------------------------------------
GRID_RGB = (214, 236, 250)   # "ice": cyan pulled most of the way to white
GRID_A = 92                  # rim alpha, on a single width line
FILL_A = 5                   # interior tint, so a cell reads as filled air
S_BLOCK = "concrete_yellow"

SIZE = 256                   # what Microsoft documents for the pack icon
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
TEX = 16                     # source texture edge, in pixels

# the S, one row per layer from the top down. Its strokes run along the screen
# horizontal and vertical, which project without shear; only the depth snakes.
LAYERS = [
    ["###..", "#....", "#....", ".....", "....."],
    [".....", ".....", "#....", ".....", "....."],
    [".....", ".....", "#####", ".....", "....."],
    [".....", ".....", "....#", ".....", "....."],
    [".....", ".....", "....#", "....#", "..###"],
]
N = len(LAYERS)

# vanilla's own directional shading
SHADE = {"top": 1.00, "left": 0.80, "right": 0.62}
FACE_ORDER = ("top", "left", "right")

# for each visible face, which way is texture-right and which is texture-down,
# as a step in cell space
FACE_AXES = {
    "top":   ((1, 0, 0), (0, 1, 0)),
    "left":  ((1, 0, 0), (0, 0, -1)),
    "right": ((0, -1, 0), (0, 0, -1)),
}

_tex = {}


def s_cells():
    """The 17 cells the letter occupies. Slice 0 is the top layer."""
    return {(x, y, N - 1 - a)
            for a, rows in enumerate(LAYERS)
            for y, row in enumerate(rows)
            for x, ch in enumerate(row) if ch == "#"}


def pane(sides):
    """A hologram pane with its rim on `sides`, drawn from "t", "l", "r", "b".

    Neighbouring panes each draw their own rim, so a four sided pane makes every
    interior grid line two pixels wide. Drawing top and left only tiles into a
    single width grid; the cells on the outside of the volume have no neighbour
    to borrow from and add "r" or "b" back, or the cube loses its outline.
    """
    a = np.zeros((TEX, TEX, 4), np.uint8)
    a[:, :] = GRID_RGB + (FILL_A,)
    for n in range(TEX):
        px = []
        if "t" in sides: px.append((n, 0))
        if "b" in sides: px.append((n, TEX - 1))
        if "l" in sides: px.append((0, n))
        if "r" in sides: px.append((TEX - 1, n))
        for x, y in px:
            a[y, x] = GRID_RGB + (GRID_A,)
    return Image.fromarray(a, "RGBA")


def texture(name):
    if name not in _tex:
        for ext in (".png", ".tga"):
            path = os.path.join(PACK, name + ext)
            if os.path.isfile(path):
                im = Image.open(path).convert("RGBA")
                # animated textures are a vertical strip of frames
                if im.height > im.width:
                    im = im.crop((0, 0, im.width, im.width))
                _tex[name] = im
                break
        else:
            raise FileNotFoundError(name)
    return _tex[name]


def quads(w, h, v):
    N_, E, S, W = (w, 0), (2 * w, h), (w, 2 * h), (0, h)
    Ed, Sd, Wd = (2 * w, h + v), (w, 2 * h + v), (0, h + v)
    return {"top": [N_, E, S, W], "left": [W, S, Sd, Wd], "right": [S, E, Ed, Sd]}


def affine(tex, quad, size, pad=2):
    """Map `tex` onto quad (P0, P0+u, P0+u+v, P0+v).

    Image.transform returns transparent wherever the source coordinate lands
    outside the texture, and on the quad's own boundary it rounds out by a
    fraction of a pixel. That leaves a transparent hairline along every face,
    which reads as a black line between neighbouring blocks. Sampling a texture
    padded with replicated edge pixels removes it; the mask still decides where
    the face ends.
    """
    (x0, y0), (x1, y1), _, (x3, y3) = quad
    ux, uy = x1 - x0, y1 - y0
    vx, vy = x3 - x0, y3 - y0
    det = ux * vy - vx * uy
    i00, i01 = vy / det, -vx / det
    i10, i11 = -uy / det, ux / det
    w, h = tex.size
    src = Image.fromarray(
        np.pad(np.array(tex), ((pad, pad), (pad, pad), (0, 0)), mode="edge"), "RGBA")
    coeffs = (w * i00, w * i01, -w * (i00 * x0 + i01 * y0) + pad,
              h * i10, h * i11, -h * (i10 * x0 + i11 * y0) + pad)
    return src.transform(size, Image.AFFINE, coeffs, Image.NEAREST)


def face_image(tex, kind, w, h, v, scale=4):
    big = tex.resize((tex.width * scale, tex.height * scale), Image.NEAREST)
    shaded = np.array(big, np.float32)
    shaded[..., :3] *= SHADE[kind]
    shaded = Image.fromarray(np.clip(shaded, 0, 255).astype(np.uint8), "RGBA")
    return affine(shaded, quads(w, h, v)[kind], (2 * w, 2 * h + v))


def face_mask(kind, w, h, v):
    m = Image.new("L", (2 * w, 2 * h + v), 0)
    ImageDraw.Draw(m).polygon(quads(w, h, v)[kind], fill=255)
    return np.array(m) > 0


def cell_sprite(faces, w, h, v):
    """faces: {kind: texture}. One image, with the shared edges resolved once.

    The three quads share their edges and a polygon fill includes its boundary,
    so a translucent texture drawn face by face doubles along every seam. The
    masks are made exclusive to stop that, but only across the faces this cube
    actually draws, since a culled face cannot hand on its share of an edge.
    """
    out = Image.new("RGBA", (2 * w, 2 * h + v), (0, 0, 0, 0))
    taken = np.zeros((2 * h + v, 2 * w), bool)
    for kind in FACE_ORDER:
        if kind not in faces:
            continue
        keep = face_mask(kind, w, h, v) & ~taken
        taken |= keep
        img = face_image(faces[kind], kind, w, h, v)
        alpha = np.array(img.split()[3], np.uint16) * keep
        img.putalpha(Image.fromarray(alpha.astype(np.uint8)))
        out.alpha_composite(img)
    return out


def render(px, margin=0.06):
    """The cube, on transparent, at px by px."""
    letter = s_cells()
    cells = {(i, j, k) for i in range(N) for j in range(N) for k in range(N)}
    w = int(px * (1 - 2 * margin) / (2 * N))
    h, v = max(1, w // 2), max(1, w)

    def screen(i, j, k):
        return ((i - j) * w, (i + j) * h - k * v)

    xs, ys = [], []
    for c in cells:
        x, y = screen(*c)
        xs += [x - w, x + w]
        ys += [y - h, y + 2 * h + v]
    ox = int(px / 2 - (min(xs) + max(xs)) / 2)
    oy = int(px / 2 - (min(ys) + max(ys)) / 2)

    block = texture(S_BLOCK)
    nb = {"top": (0, 0, 1), "left": (0, 1, 0), "right": (1, 0, 0)}
    canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    for cell in sorted(cells, key=sum):
        solid = cell in letter
        faces = {}
        for kind, (di, dj, dk) in nb.items():
            other = (cell[0] + di, cell[1] + dj, cell[2] + dk)
            if other in cells:
                if other in letter:
                    continue                       # opaque neighbour hides it
                if not solid:
                    continue                       # pane against pane merges
            if solid:
                faces[kind] = block
                continue
            # a pane on the outside of the volume has no neighbour to borrow
            # its right or bottom line from, so it draws that edge itself
            u, d = FACE_AXES[kind]
            sides = "tl"
            if tuple(a + b for a, b in zip(cell, u)) not in cells:
                sides += "r"
            if tuple(a + b for a, b in zip(cell, d)) not in cells:
                sides += "b"
            faces[kind] = pane(sides)
        if not faces:
            continue
        sx, sy = screen(*cell)
        canvas.alpha_composite(cell_sprite(faces, w, h, v), (ox + sx - w, oy + sy - h))
    return canvas


def reduce_rgba(img, size):
    """Downsample without dark fringing.

    Fully transparent pixels still carry a colour, and here that colour is
    black. Resampling mixes it into every edge, so the cube would come back with
    a dark halo. Premultiplying by alpha first keeps the transparent pixels from
    contributing anything, and dividing back out afterwards restores the colour.
    """
    a = np.array(img, np.float32)
    alpha = a[..., 3:4] / 255.0
    a[..., :3] *= alpha
    small = np.array(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
                     .resize(size, Image.LANCZOS), np.float32)
    out_alpha = small[..., 3:4] / 255.0
    with np.errstate(divide="ignore", invalid="ignore"):
        small[..., :3] = np.where(out_alpha > 0, small[..., :3] / out_alpha, 0)
    return Image.fromarray(np.clip(small, 0, 255).astype(np.uint8), "RGBA")


def transparent(size):
    """The cube alone, on transparency, at `size`."""
    # rendered large and reduced, so the one pixel grid lines survive
    return reduce_rgba(render(size * 4), (size, size))


def compose(size):
    """The cube over the background art, square and fully opaque, at `size`."""
    art = Image.open(BACKGROUND).convert("RGBA").resize((size, size), Image.LANCZOS)
    art.alpha_composite(transparent(size))
    return art


def main():
    icon = compose(SIZE)
    icon.save(PACK_ICON)
    print("wrote %s (%d x %d, over the background)" % (PACK_ICON, *icon.size))

    bare = transparent(SIZE)
    bare.save(APP_ICON)
    print("wrote %s (%d x %d, transparent)" % (APP_ICON, *bare.size))

    ## every size rendered at its own scale rather than reduced from one big
    ## frame: at 16 and 24 px the grid is thinner than a pixel either way, but
    ## the S silhouette survives a fresh render better than a downsample
    frames = [transparent(n) for n in ICO_SIZES]
    frames[-1].save(DESKTOP_ICON, sizes=[(n, n) for n in ICO_SIZES],
                    append_images=frames[:-1])
    print("wrote %s (%s, transparent)"
          % (DESKTOP_ICON, ", ".join(str(n) for n in ICO_SIZES)))


if __name__ == "__main__":
    sys.exit(main())
