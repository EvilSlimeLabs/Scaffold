"""Draw a block the way the pack draws it, without opening the game.

    python -m tools.checks.render lectern
    python -m tools.checks.render lectern --iso
    python -m tools.checks.render lectern --view up-nw --open
    python -m tools.checks.render standing_banner --data 5 --rot 0
    python -m tools.checks.render lectern --bg skyblue --scale 12 -o /tmp
    python -m tools.checks.render --manifest
    python -m tools.checks.render --manifest --update

`python -m tools.render` is the same command under a shorter name, which is what
to type when drawing one block to look at it. This lives under `checks/` because
its other half is a regression check.

Most of what goes wrong with a block is visible the moment you look at it and
invisible in the tables: a face reading the wrong half of a sheet, a window off
by two pixels, a picture on its side, a post that stops short of the thing above
it. Every one of those used to cost a pack build and a trip into a world. This
draws the block instead, six ways round, from what the pack itself would ship.

**It renders the real output, not a second opinion about it.** The cubes come
from `armor_stand_geo_class.make_block` and the pixels from the atlas that same
object builds, so what is drawn here is what a player's pack contains. Nothing
that builds a picture opens a lookup table, and it must stay that way: a
renderer that translated the tables itself would agree with the tables and tell
you nothing about the translation. `tests/test_render.py` holds the drawing to
it by name.

`every_form` is the exception that proves it. It reads the shape table to learn
which forms a block has, which decides what to draw and never how it looks --
and without it a sweep covers only the form a block draws with nothing asked
for, which is barely half of what the tables describe.

What it does not model
----------------------
- **Z-fighting.** Two faces on the same plane come out as one arbitrary but
  steady choice here and as a flicker in game, so a block can look settled here
  and shimmer in a world. Reading the shape table is what catches those: a
  standing sign's post ran the whole height of the block with its north and
  south faces exactly on the board's, and only the game ever said so.
- **Transparency over a world.** Blocks are drawn solid, because the point is
  to read the texture. `--alpha` gives a rough idea and no more.
- Lighting, Vibrant Visuals, and the armor stand's own scaling.

What it does model, and used not to
-----------------------------------
**The x mirror.** A block goes into the model with its x reversed, so a shape
that is asymmetric across x is drawn in game on the side opposite the one its
table names. `MIRROR` and `ACROSS` below carry it. Without them this drew a
sunflower's head on the wrong side of its own stem and called it right.

**The y turn.** Bedrock turns a cube about y the other way from `spun`, and
about x and z the same way. `TURN_SIGNS` and `_turn` carry it, and only for a
turn the shape table gave a cube.

**The two faces of a plane.** They read their u in opposite directions, which is
the south entry in `FACES` above.

Everything here was settled by building the block and looking, and every one of
them was wrong here while being right in a world. `tests/test_render.py` holds
all three.

Orientation
-----------
`FACES` is the whole of what this file assumes about how Bedrock lays a picture
on a face, and every entry says what it rests on. Two of them are settled by
things seen in game and held down by tests in `tests/test_render.py`; the rest
follow from `Cube.uv` in `tools/blocks/geometry.py`, which is the convention the
tables were written to. If a block ever comes out of the game disagreeing with
this file, this table is the one place to change.
"""
import argparse
import difflib
import hashlib
import io
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageColor, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scaffold import paths
from scaffold.pack import armor_stand_geo_class as asgc

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "render_hashes.json")

## Where a drawn block lands when nothing says otherwise. Gitignored, and made
## when it is first needed: these are pictures to look at while a block is being
## worked on, and drawing one again costs a second, so keeping any of them would
## only be keeping something out of date.
RENDERS = os.path.join(ROOT, "renders")

## Blocks no vanilla pack ships textures for, which will never resolve and are
## not a fault. `tests/test_block_coverage.py` holds the same list.
UNRESOLVABLE = re.compile(r"^(element_\d+|chemistry_table|chemical_heat"
                          r"|hard_(stained_)?glass(_pane)?"
                          r"|colored_torch_\w+|underwater_torch"
                          r"|coral_(fan_)?pink_dead)$")

## A block is a unit cube from 0 to 1 in each axis, with x and z running -0.5 to
## 0.5 because that is where `make_block` puts them.
TEXELS = 16.0

## Which way each face looks, and where its picture's top left corner goes.
##
## `axis` is the outward normal. `origin` picks the corner of the box the
## texture's 0,0 sits at, as (x, y, z) with 0 meaning the low side and 1 the
## high. `along_u` and `along_v` are the directions the picture's two axes run
## from there.
##
## - **v runs downward on every upright face.** The upper half of a tile belongs
##   on the upper half of a block: a bottom slab shows the bottom of its
##   texture. That is what `docs/Block Notes.md` says and what every slab in the
##   pack is drawn from.
## - **u runs +x on north as well as south**, and +z on east as well as west,
##   which is `Cube.uv`'s own default.
## - **The south face's u runs the other way from the north's**, which is what
##   makes the two faces of a plane read in opposite directions when you look at
##   them from outside, and what `tools/blocks/banners.py` relies on to get a
##   design the right way round. Given the same direction as the north's, a
##   marked banner's front came out with each of its four columns mirrored where
##   it stood, and a brewing stand's arm carried its outer leg against the pole
##   on one side and away from it on the other. Both are right in game.
## - **The up face's v runs toward -z**, so the bottom of the tile lands at the
##   block's north edge. That one is not a convention, it is an observation: the
##   lectern's base carries a red inlay across the bottom of `lectern_base` and
##   it came out at the back of the block until the window was turned over.
##   `tests/test_render.py` holds it there.
FACES = {
    "south": {"axis": (0, 0, 1), "origin": (1, 1, 1),
              "along_u": (-1, 0, 0), "along_v": (0, -1, 0)},
    "north": {"axis": (0, 0, -1), "origin": (0, 1, 0),
              "along_u": (1, 0, 0), "along_v": (0, -1, 0)},
    "east":  {"axis": (1, 0, 0), "origin": (1, 1, 0),
              "along_u": (0, 0, 1), "along_v": (0, -1, 0)},
    "west":  {"axis": (-1, 0, 0), "origin": (0, 1, 0),
              "along_u": (0, 0, 1), "along_v": (0, -1, 0)},
    "up":    {"axis": (0, 1, 0), "origin": (0, 1, 1),
              "along_u": (1, 0, 0), "along_v": (0, 0, -1)},
    "down":  {"axis": (0, -1, 0), "origin": (0, 0, 0),
              "along_u": (1, 0, 0), "along_v": (0, 0, 1)},
}

## **The world is the mirror of the model in x, so this draws the mirror.**
## `armor_stand_geo_class` writes a cube's origin as `-1*(x + offsets[0]) +
## xoff`: the block's place in the grid is negated, which is what turns a
## structure's x into Bedrock's model x, and the cube's own offset inside the
## block is added to that untouched. What comes out is a model whose x runs
## opposite to the world's, and drawing it straight put every block that is
## asymmetric across x on the wrong side of itself -- a sunflower's head on the
## wrong side of its own stem, and every turn about y and about z the wrong way
## round.
##
## Two things follow, and both are in the loop below.
##
## **The picture on a face follows the side it is seen from.** Bedrock names a
## cube's uv faces by where they end up rather than by the model's own axes, so
## the face built here as the model's east is painted with the table's west. The
## other four keep their names, and their pictures come out reversed left to
## right, which is what `tools/blocks/banners.py` is compensating for when it
## writes a design mirrored and turns it back on the front.
##
## **The normal is mirrored with the points**, because `draw` culls a face by
## it. Left alone, every face across x would be drawn from the wrong side.
MIRROR = np.array([-1.0, 1.0, 1.0])
ACROSS = {"east": "west", "west": "east",
          "north": "north", "south": "south", "up": "up", "down": "down"}

## Where the camera stands for each named view, as the direction it looks *from*
## and the two screen axes. A flat view is named for the face of the block it
## puts in front of you, so "south" shows what `FACES["south"]` painted, and it
## shows it square on: one texel is a countable square of screen pixels.
VIEWS = {
    "south": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "north": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    "east":  ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "west":  ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "up":    ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
    "down":  ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}

## The six flat views, which are what a fingerprint is taken from. A three
## quarter view adds nothing a fingerprint could use -- what it shows is what
## the six already carry, arranged so a person can see the shape -- and it would
## only make the sweep slower.
FLAT = ("south", "north", "east", "west", "up", "down")

## The eight corners a block can be looked at from, named for where you are
## standing: up or down, then north or south, then east or west. `n` is -z and
## `s` is +z, matching the face names.
CORNERS = (("up-se", (1, 1, 1)), ("up-sw", (-1, 1, 1)),
           ("up-nw", (-1, 1, -1)), ("up-ne", (1, 1, -1)),
           ("down-se", (1, -1, 1)), ("down-sw", (-1, -1, 1)),
           ("down-nw", (-1, -1, -1)), ("down-ne", (1, -1, -1)))


def _corner(direction):
    """A three quarter view from one corner of the block.

    Screen right is level with the ground, so the block does not lean; screen up
    follows from it. What this is for is reading shape -- how pieces meet, and
    whether one leaves a gap under another -- rather than counting pixels, which
    is what the flat views are for.
    """
    look = np.asarray(direction, dtype=float)
    look /= np.linalg.norm(look)
    right = np.cross((0.0, 1.0, 0.0), look)
    right /= np.linalg.norm(right)
    return tuple(look), tuple(right), tuple(np.cross(look, right))


VIEWS.update({name: _corner(where) for name, where in CORNERS})

ISO_ORDER = tuple(name for name, _where in CORNERS)

## What a sheet holds, as rows. Six faces square on and one corner to see the
## shape from is the default; the flags below trade that for more or less.
LAYOUTS = {
    "default": (FLAT + ("up-se",),),
    "flat": (FLAT,),
    ## four and four rather than eight across, or the sheet is wider than a
    ## screen and the two halves cannot be read against each other
    "corners": (ISO_ORDER[:4], ISO_ORDER[4:]),
    "every": (FLAT, ISO_ORDER[:4], ISO_ORDER[4:]),
}
ORDER = LAYOUTS["default"][0]


def _spin(points, degrees, pivot):
    """Turn points about a pivot the way a cube's rotation turns it.

    Bedrock's angles run clockwise in the plane they name, which is the other
    way round from the usual mathematical sense; `geometry.spun` says the same
    thing and this has to agree with it.
    """
    if not degrees or not any(degrees):
        return points
    rx, ry, rz = (np.radians(-a) for a in degrees)
    p = np.asarray(points, dtype=float) - np.asarray(pivot, dtype=float)
    for angle, (a, b) in ((rx, (1, 2)), (ry, (2, 0)), (rz, (0, 1))):
        if angle:
            ca, sa = np.cos(angle), np.sin(angle)
            u, v = p[:, a].copy(), p[:, b].copy()
            p[:, a] = u * ca - v * sa
            p[:, b] = u * sa + v * ca
    return p + np.asarray(pivot, dtype=float)


## **Bedrock turns a cube about y the other way from `spun`, and about x and z
## the same way.** Measured against blocks whose look in game is settled: a
## brewing stand's arms and bottles, which carry a y turn and come out along
## their own radius only if it is negated here, and a sunflower's head, which
## carries a z turn and looks at the floor if it is. `spun` in
## `tools/blocks/geometry.py` and `_spin` below share one convention, so a
## generator that places a piece with `spun` and turns it by the same sign
## agrees with itself and disagrees with the game -- which is why `brew_turned`
## writes its move and its turn with opposite signs.
##
## Nothing here has an x turn whose direction is settled in game, so x is left
## as it is. If one ever reads backwards, this is the line.
TURN_SIGNS = (1, -1, 1)


## **Only a turn the cube brought with it is corrected.** `add_blocks_to_bones`
## copies a family's group rotation onto every cube that has none of its own,
## and those numbers were tuned by eye in game and are right as they stand --
## negating them puts every door, stair, trapdoor, anvil and bed a quarter turn
## out. The copying happens inside `make_block` and `geo.blocks` is keyed by
## bone by the time it returns, so the group's own turn is gone and the two
## cannot be told apart by it. Nor by the pivot: an anvil has a cube whose own
## middle *is* the block's middle. What does separate them is that a family's
## turn is the same on every cube of the block and a cube's own turn is not, so
## a block whose rotated cubes disagree is carrying its own.
##
## **Its one blind spot is a family that turns every cube the same way about one
## point**, which is `cross_texture` and `double_plant`: two quads at forty-five
## degrees about the middle of the block. Those are left as a family turn and
## not corrected. It does not show, because the pair is symmetric -- the X comes
## out the same either way and only the picture on each quad mirrors.
OWN_TURN = "_turned_by_its_shape"


def _turn(cube):
    """The turn a cube carries, the way Bedrock applies it."""
    turn = cube.get("rotation")
    if turn is None:
        return None
    if not cube.get(OWN_TURN):
        return list(turn)
    return [way * n for way, n in zip(TURN_SIGNS, turn)]


def mesh(block, rot=0, alpha=1.0, geo=None, stack=False, low=False, **states):
    """The quads of one block, and the atlas they read.

    `stack` draws the block's upper half in the block above as well, which is
    what a two block tall plant is: a sunflower is a lower block and an upper
    one, and drawing only the lower half shows a stem with nothing on it.
    Whether a block has an upper half is `taller_than_one`'s question rather
    than this one's; what gets drawn is still only what `make_block` hands back.

    `low` draws what a pack built with `set_low_geometry(True)` would draw:
    `make_block` swaps a family for its `__low` twin where one exists and leaves
    the rest alone, so most blocks come out unchanged. Those simplified forms
    are generated by `tools/blocks/simplify.py` and nothing else has ever drawn
    them, which is the point of the flag -- a simple form is meant to be the
    detailed one's outline and nothing said when it stopped being that.

    Everything here comes out of `make_block`, so a change to a lookup table
    shows up without this file knowing the table exists.

    `geo` lets a caller hand in its own, which the tests do. Sweeping every
    block reuses nothing on purpose: `extend_uv_image` builds the atlas again
    from scratch for each tile it adds, so one kept across a thousand blocks
    costs more in copying than a fresh one costs in reading textures.
    """
    if geo is None:
        geo = asgc.ArmorStandGeo("render", offsets=[0, 0, 0], low_geometry=low)
    geo.alpha = alpha
    ## a geo handed in has its own answer, and the flag overrides it, so that
    ## the tests can pass one either way round
    geo.low_geometry = bool(low)
    geo.blocks = {}
    ## **and the bones, which `add_blocks_to_bones` appends to.** A geo handed
    ## in twice otherwise carries the last block's bones into the next one, and
    ## the drawing gets slower every time: sixty-five forms of one block left
    ## sixty-six bones behind and took three times as long as building each from
    ## nothing would have.
    geo.geometry["bones"] = [{"name": "ghost_blocks", "pivot": [-8, 0, 8]}]
    geo.make_block(0, 0, 0, block, rot=rot, **states)
    if stack:
        geo.make_block(0, 1, 0, block, rot=rot, **dict(states, top=True))
    ## mark the turns that are the cube's own rather than the family's. See
    ## `OWN_TURN` above for why, and for why it has to happen here.
    for group in geo.blocks.values():
        turned = [cube for cube in group.get("cubes", [])
                  if cube.get("rotation") and any(cube["rotation"])]
        ## rounded, because two cubes built about the same middle come out of
        ## the arithmetic a few parts in a billion billion apart
        apart = {(tuple(cube["rotation"]),
                  tuple(round(n, 9) for n in cube.get("pivot") or ()))
                 for cube in turned}
        if len(apart) > 1:
            for cube in turned:
                cube[OWN_TURN] = True
    geo.add_blocks_to_bones()

    quads = []
    for bone in geo.geometry["bones"]:
        for cube in bone.get("cubes", []):
            low = np.asarray(cube["origin"], dtype=float)
            high = low + np.asarray(cube["size"], dtype=float)
            for face, how in FACES.items():
                ## The face built here from `how` lands on the other side of the
                ## block once x is mirrored, and Bedrock names a cube's uv faces
                ## by where they end up rather than by the model's own axes, so
                ## the paint follows the side it is seen from.
                shown = ACROSS[face]
                paint = cube["uv"][shown]
                u0, v0 = paint["uv"]
                du, dv = paint["uv_size"]
                corner = np.array([high[i] if how["origin"][i] else low[i]
                                   for i in range(3)])
                span = high - low
                across = np.asarray(how["along_u"], dtype=float) * span
                down = np.asarray(how["along_v"], dtype=float) * span
                points = np.array([corner, corner + across,
                                   corner + across + down, corner + down])
                points = _spin(points, _turn(cube),
                               cube.get("pivot") or (low + high) / 2.0)
                ## uv is in atlas units: u across the one-tile width, v down the
                ## stack of tiles, so a texel is a sixteenth of either
                uvs = np.array([[u0, v0], [u0 + du, v0],
                                [u0 + du, v0 + dv], [u0, v0 + dv]]) * TEXELS
                normal = np.asarray(how["axis"], dtype=float)
                if _turn(cube) and any(_turn(cube)):
                    turned = _spin(np.array([[0, 0, 0], normal]),
                                   _turn(cube), (0, 0, 0))
                    normal = turned[1] - turned[0]
                quads.append((points * MIRROR, uvs, normal * MIRROR, shown))
    return quads, geo.uv_array


def _frame(quads):
    """The box every view of this block is drawn in.

    At least the block's own cube, and wider when the block leaves it -- a
    banner is two blocks tall and half of it would be off the picture. All six
    views share it, so they can be read against each other.
    """
    points = np.concatenate([q[0] for q in quads])
    low = np.minimum(points.min(axis=0), [-0.5, 0.0, -0.5])
    high = np.maximum(points.max(axis=0), [0.5, 1.0, 0.5])
    return low, high


def draw(quads, atlas, view="south", scale=8, background=(24, 24, 28),
         frame=None):
    """One view of a block, as an image.

    Orthographic and nearest sampled, both on purpose: a texel is a square of
    `scale` pixels that can be counted against the source file, and nothing is
    softened on the way.
    """
    look, right, up = VIEWS[view]
    look = np.asarray(look, dtype=float)
    right = np.asarray(right, dtype=float)
    up = np.asarray(up, dtype=float)

    low, high = frame if frame is not None else _frame(quads)
    corners = np.array([[x, y, z] for x in (low[0], high[0])
                        for y in (low[1], high[1])
                        for z in (low[2], high[2])], dtype=float)
    xs, ys = corners @ right, corners @ up
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    px = TEXELS * scale
    wide = max(1, int(round((x1 - x0) * px)))
    tall = max(1, int(round((y1 - y0) * px)))

    canvas = np.zeros((tall, wide, 3), dtype=float)
    canvas[:, :] = background
    depth = np.full((tall, wide), -np.inf)
    atlas = np.asarray(atlas, dtype=float)
    rows, cols = atlas.shape[0], atlas.shape[1]

    for points, uvs, normal, _face in quads:
        ## a face pointing away is behind another face of the same box, and
        ## drawing it only makes the depth test do more work
        if float(np.dot(normal, look)) <= 1e-9:
            continue
        sx = (points @ right - x0) * px
        sy = (y1 - points @ up) * px
        sz = points @ look
        for a, b, c in ((0, 1, 2), (0, 2, 3)):
            _triangle(canvas, depth, atlas, rows, cols,
                      sx[[a, b, c]], sy[[a, b, c]], sz[[a, b, c]],
                      uvs[[a, b, c]])
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")


def _triangle(canvas, depth, atlas, rows, cols, sx, sy, sz, uvs):
    """One triangle into the canvas, depth tested, with the texture on it."""
    tall, wide = depth.shape
    lo_x = max(0, int(np.floor(sx.min())))
    hi_x = min(wide, int(np.ceil(sx.max())) + 1)
    lo_y = max(0, int(np.floor(sy.min())))
    hi_y = min(tall, int(np.ceil(sy.max())) + 1)
    if lo_x >= hi_x or lo_y >= hi_y:
        return

    area = ((sx[1] - sx[0]) * (sy[2] - sy[0])
            - (sx[2] - sx[0]) * (sy[1] - sy[0]))
    if abs(area) < 1e-12:
        return

    ys, xs = np.mgrid[lo_y:hi_y, lo_x:hi_x]
    px_ = xs + 0.5
    py = ys + 0.5
    w0 = ((sx[1] - px_) * (sy[2] - py) - (sx[2] - px_) * (sy[1] - py)) / area
    w1 = ((sx[2] - px_) * (sy[0] - py) - (sx[0] - px_) * (sy[2] - py)) / area
    w2 = 1.0 - w0 - w1
    inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
    if not inside.any():
        return

    ## orthographic, so a plain barycentric blend is exact and there is no
    ## perspective to correct for
    z = w0 * sz[0] + w1 * sz[1] + w2 * sz[2]
    here = depth[lo_y:hi_y, lo_x:hi_x]
    reaches = inside & (z > here)
    if not reaches.any():
        return

    tx = w0 * uvs[0, 0] + w1 * uvs[1, 0] + w2 * uvs[2, 0]
    ty = w0 * uvs[0, 1] + w1 * uvs[1, 1] + w2 * uvs[2, 1]
    col = np.clip(np.floor(tx).astype(int), 0, cols - 1)
    row = np.clip(np.floor(ty).astype(int), 0, rows - 1)
    texel = atlas[row, col]

    ## **A texel with nothing in it writes no depth.** Minecraft cuts a block's
    ## texture out rather than blending it, so a clear pixel is a hole and what
    ## is behind it shows through. Writing depth for one instead lets an empty
    ## face hide a painted one directly behind it, which is not a corner case:
    ## a shulker box's lid and base overlap and each paints exactly what the
    ## other leaves clear, so the whole join came out as a slot through the box.
    solid = texel[..., 3] > 0 if texel.shape[-1] == 4 else np.ones_like(reaches)
    take = reaches & solid
    if not take.any():
        return

    patch = canvas[lo_y:hi_y, lo_x:hi_x]
    if texel.shape[-1] == 4:
        a = (texel[..., 3:4] / 255.0) * take[..., None]
        patch[...] = patch * (1 - a) + texel[..., :3] * a
    else:
        patch[take] = texel[take][..., :3]
    here[take] = z[take]


def sheet(block, rot=0, scale=8, background=(24, 24, 28), rows=None,
          alpha=1.0, label=True, stack=False, low=False, **states):
    """Every view of one block, laid out in rows and named.

    `rows` is a run of view names per row, so a caller decides the shape of the
    sheet rather than this deciding for it. All of them share one frame, so a
    block is the same size in every picture and the rows line up.
    """
    rows = rows or LAYOUTS["default"]
    quads, atlas = mesh(block, rot=rot, alpha=alpha, stack=stack, low=low,
                        **states)
    frame = _frame(quads)
    drawn = [[(name, draw(quads, atlas, name, scale, background, frame))
              for name in row] for row in rows]

    pad = 4
    band = 12 if label else 0
    wide = max(sum(t.width for _n, t in row) + pad * (len(row) + 1)
               for row in drawn)
    tall = pad + sum(max(t.height for _n, t in row) + pad + band
                     for row in drawn)
    out = Image.new("RGB", (wide, tall), background)
    pen = ImageDraw.Draw(out)

    y = pad
    for row in drawn:
        x = pad
        for name, tile in row:
            out.paste(tile, (x, y + band))
            if label:
                pen.text((x, y), name, fill=(200, 200, 200))
            x += tile.width + pad
        y += max(t.height for _n, t in row) + pad + band
    return out


def digest(block, rot=0, scale=4, geo=None, **states):
    """A fingerprint of every view of a block, for noticing it changed."""
    quads, atlas = mesh(block, rot=rot, geo=geo, **states)
    frame = _frame(quads)
    shake = hashlib.sha256()
    for name in FLAT:
        image = draw(quads, atlas, name, scale, (0, 0, 0), frame)
        shake.update(name.encode())
        shake.update(b"%d,%d," % image.size)
        shake.update(image.tobytes())
    return shake.hexdigest()[:16]


def every_block():
    """The blocks worth drawing: everything the tables say how to build."""
    with io.open(paths.lookup("block_definition.json"), encoding="utf-8") as f:
        table = json.load(f)
    return sorted(name for name, family in table.items() if family != "ignore")


def every_form():
    """Every block, and every form of it, as (block, form) pairs.

    **A block is not one picture.** A banner is sixteen dyes and two that are
    not dyes, a chiseled bookshelf is sixty-four states, a bed is thirty-five.
    Fingerprinting only the form a block draws with nothing asked for covers
    little more than half of what the tables describe, and the half it leaves
    out is where the fiddly work is -- an ominous banner's face came out cut in
    half and swapped and the manifest reported nothing changed.

    The forms come from the shape table, which is the only place that knows
    them. That is enumeration and not translation: what a form *looks* like
    still comes from `make_block`, and `tests/test_render.py` holds the drawing
    to that.
    """
    with io.open(paths.lookup("block_definition.json"), encoding="utf-8") as f:
        families = json.load(f)
    with io.open(paths.lookup("block_shapes.json"), encoding="utf-8") as f:
        shapes = json.load(f)
    pairs = []
    for block, family in sorted(families.items()):
        if family == "ignore" or UNRESOLVABLE.match(block):
            continue
        forms = [form for form in shapes.get(family, {})
                 ## the simplified copies are the same block drawn plainer, and
                 ## `--low_geometry` is what reaches them, not a form name
                 if not form.endswith(asgc.LOW_SUFFIX)]
        pairs.extend((block, form) for form in sorted(forms) or ["default"])
    return pairs


def taller_than_one(block):
    """Whether this block is the lower half of a two block tall one.

    A sunflower, a lilac and a tall grass are each two blocks in the world, told
    apart by `upper_block_bit`, and a shape family says so by carrying a `top`
    form. Drawing only the lower half of one shows a stem and leaves the flower
    out, which reads as a bug in the block rather than as half a picture.

    Like `every_form`, this reads the shape table to decide *what* to draw and
    never how it looks, which is why it is here and not inside `mesh`.
    """
    with io.open(paths.lookup("block_definition.json"), encoding="utf-8") as f:
        family = json.load(f).get(block)
    if not family:
        return False
    with io.open(paths.lookup("block_shapes.json"), encoding="utf-8") as f:
        return "top" in json.load(f).get(family, {})


def named(block, form):
    """How one form of one block is written in the manifest."""
    return "%s/%s" % (block, form)


def manifest(update=False, only=None):
    """Compare every block's fingerprint against the one on record.

    A lookup table is edited a family at a time and read by everything
    afterwards, so the useful question after a change is not "does it still
    build" -- `tools.checks.coverage` answers that -- but "what else moved".
    This answers that, and the answer should be only what was meant.
    """
    known = {}
    if os.path.isfile(MANIFEST):
        with io.open(MANIFEST, encoding="utf-8") as f:
            known = json.load(f)

    pairs = only or every_form()
    made, broke = {}, []
    ## One atlas per block, kept across that block's own forms. Loading a
    ## texture is what a form costs, and a block's forms mostly read the same
    ## ones -- sixteen banner colours share a post and a bar. Keeping one across
    ## *every* block instead is slower, not faster: `extend_uv_image` builds the
    ## atlas again from scratch for each tile it adds, so a thousand blocks'
    ## worth of tiles costs more in copying than the textures cost to read.
    geo, standing = None, None
    for block, form in pairs:
        if block != standing:
            geo, standing = asgc.ArmorStandGeo("render", offsets=[0, 0, 0]), block
        try:
            made[named(block, form)] = digest(block, data=form, geo=geo)
        except Exception as trouble:
            broke.append("%s (%s)" % (named(block, form),
                                      type(trouble).__name__))

    moved = sorted(n for n in made if n in known and known[n] != made[n])
    fresh = sorted(n for n in made if n not in known)
    gone = sorted(n for n in known if n not in made)

    if update:
        with io.open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
            json.dump(made, f, indent=1, sort_keys=True)
            f.write("\n")
    return {"changed": moved, "new": fresh, "removed": gone,
            "unbuildable": broke, "counted": len(made)}


def check_block(block, ap):
    """Stop on a block the tables do not carry, and say what is nearby.

    A name that is not in `block_definition.json` reaches `make_block` and comes
    back as a KeyError from four frames down, which says the name and nothing
    about what to do. Half a name is the common way to get there -- `standing`
    for `standing_banner` -- so the answer is usually one of its neighbours.
    """
    known = every_block()
    if block in known:
        return
    close = difflib.get_close_matches(block, known, n=6, cutoff=0.5)
    if not close:
        ## a fragment is a poor match for anything by edit distance and a good
        ## one by eye, so fall back to what merely contains it
        close = [name for name in known if block.lower() in name.lower()][:6]
    ap.error("no block called %r%s. Look one up with: "
             "python -m tools.find %s"
             % (block,
                ("; did you mean: " + ", ".join(close)) if close else "",
                block))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Draw a block six ways round, from what the pack ships.")
    ap.add_argument("block", nargs="?",
                    help="a block id, as the tables name it")
    ap.add_argument("--rot", type=int, default=0,
                    help="rotation state")
    ap.add_argument("-v", "--variant",
                    help="shape variant, for a block that has them; "
                         "python -m tools.find <block> lists what there is")
    ## not type=int. `make_block` matches `str(data)` against the shape family's
    ## own keys, and a family names some of them in words: a banner is 0 to 15
    ## for its dyes and `illager` or `designed` for the two that are not a dye
    ## at all. Reading this as a number put those two out of reach.
    ap.add_argument("-d", "--data", metavar="STATE",
                    help="which form to draw, which is what picks a banner's "
                         "colour and a head's kind. Numbers and words alike; "
                         "python -m tools.find <block> lists them")
    ap.add_argument("--top", action="store_true", help="the upper half state")
    ap.add_argument("--scale", type=int, default=8,
                    help="screen pixels per texel (default 8)")
    ap.add_argument("--bg", "--background", dest="background",
                    default="18181c", metavar="COLOUR",
                    help="what to draw the block against: a name like 'skyblue' or a hex code like 18181c or #18181c (default 18181c)")
    ap.add_argument("--alpha", type=float, default=1.0,
                    help="how solid to draw it; 1 is opaque and is the default")
    ap.add_argument("--low", "--low-geometry", dest="low", action="store_true",
                    help="draw the simplified form, the way a pack built with "
                         "low geometry does. Most blocks have none and come "
                         "out the same either way")
    ap.add_argument("-o", "--output", default=RENDERS,
                    help="directory to write into, or a file to write; renders/ by default")
    picked = ap.add_mutually_exclusive_group()
    picked.add_argument("--iso", action="store_true",
                        help="all eight corners instead of the six flat faces")
    picked.add_argument("--no-iso", dest="no_iso", action="store_true",
                        help="the six flat faces alone, with no corner view")
    picked.add_argument("--all", dest="every", action="store_true",
                        help="the six flat faces and all eight corners")
    picked.add_argument("-w", "--view", action="append", metavar="NAME",
                        help="just this view, given again or comma separated for several. One of: " + ", ".join(VIEWS))
    ap.add_argument("--open", dest="show", action="store_true",
                    help="open the picture in whatever views images here")
    ap.add_argument("--manifest", action="store_true",
                    help="fingerprint every block and say which ones moved")
    ap.add_argument("--update", action="store_true",
                    help="with --manifest, write the fingerprints down")
    args = ap.parse_args(argv)

    if args.manifest:
        try:
            report = manifest(update=args.update)
        except OSError as trouble:
            ## the sweep takes half a minute, so a manifest that cannot be
            ## written is worth saying plainly rather than as a traceback
            ap.error(_why_not(MANIFEST, trouble))
        except ValueError as trouble:
            ap.error("%s is not readable as JSON: %s. Rewrite it with "
                     "--manifest --update" % (_shown(MANIFEST), trouble))
        print("forms drawn  : %d" % report["counted"])
        for label, key in (("changed", "changed"), ("new", "new"),
                           ("removed", "removed"),
                           ("would not build", "unbuildable")):
            names = report[key]
            print("%-15s: %d" % (label, len(names)))
            for name in names[:40]:
                print("    %s" % name)
            if len(names) > 40:
                print("    ... and %d more" % (len(names) - 40))
        if args.update:
            print("\nwritten to %s" % os.path.relpath(MANIFEST, ROOT))
            return 0
        moved = report["changed"] or report["new"] or report["removed"]
        if moved:
            print("\nRe-run with --update once the change is the one you meant.")
        return 1 if moved else 0

    if not args.block:
        ap.error("name a block, or pass --manifest")

    states = {}
    if args.variant:
        states["variant"] = args.variant
    if args.data is not None:
        states["data"] = args.data
    if args.top:
        states["top"] = True
    if args.view:
        ## "--view up --view down-nw" and "--view up,down-nw" both work, since
        ## there is no telling which one somebody will reach for
        wanted = [name.strip() for group in args.view
                  for name in group.split(",") if name.strip()]
        unknown = [name for name in wanted if name not in VIEWS]
        if unknown:
            ap.error("no such view: %s. There is: %s"
                     % (", ".join(unknown), ", ".join(VIEWS)))
        rows = (tuple(wanted),)
    else:
        rows = LAYOUTS["corners" if args.iso else
                       "flat" if args.no_iso else
                       "every" if args.every else "default"]
    try:
        ground = ground_colour(args.background)
    except ValueError as wrong:
        ap.error(str(wrong))
    check_block(args.block, ap)
    ## A two block tall plant is drawn whole unless a half was asked for, since
    ## half a sunflower is a stem and reads as a broken block rather than as one
    ## of the two blocks it really is. `--top` and `--data top` both mean a half
    ## was asked for.
    stack = (not args.top and states.get("data") != "top"
             and taller_than_one(args.block))
    try:
        image = sheet(args.block, rot=args.rot, scale=args.scale,
                      background=ground, rows=rows, alpha=args.alpha,
                      stack=stack, low=args.low, **states)
    except Exception as trouble:
        ## a block whose family, variant or texture is missing raises from deep
        ## inside make_block; the traceback names the key and not the choice
        ## that asked for it, which is what somebody running this needs
        ap.error("could not draw %s: %s: %s. That usually means a variant or "
                 "a texture the tables name is not there"
                 % (args.block, type(trouble).__name__, trouble))
    where = destination(args, ap)
    try:
        image.save(where)
    except OSError as trouble:
        ap.error(_why_not(where, trouble))
    print("%s  %dx%d" % (_shown(where), *image.size))
    if args.show:
        _open(where)
    return 0


def destination(args, ap):
    """Where the picture goes, with the directory made if it has to be.

    A directory takes a file named for the block, so a run does not have to
    think of a name; anything ending in .png is taken as the file itself.
    """
    ## a trailing separator says "a directory" and would otherwise hide both the
    ## .png test and the is-it-a-file test behind a name that matches neither
    where = args.output.rstrip("/\\") or args.output
    if where.lower().endswith(".png"):
        holding = os.path.dirname(os.path.abspath(where))
        if os.path.isdir(where):
            ap.error("%s is a directory, so a file cannot be written over it"
                     % where)
    else:
        if os.path.isfile(where):
            ap.error("%s is a file, not a directory. Give it a name ending "
                     ".png to write that file, or a directory to write into"
                     % where)
        holding = where

    try:
        if not os.path.isdir(holding):
            os.makedirs(holding)
    except OSError as trouble:
        ap.error(_why_not(holding, trouble, making=True))

    if where is not holding:
        return where
    return os.path.join(where, "%s.png" % _named(args))


def _why_not(where, trouble, making=False):
    """Why a write failed, in terms of what to do about it.

    The errno says what the operating system refused and not what somebody
    should try instead, and the likeliest cause here has a specific answer:
    Windows will not write a file another program is holding open, and `--open`
    means the last picture is very likely open in a viewer right now.
    """
    what = "make" if making else "write"
    if isinstance(trouble, PermissionError):
        return ("cannot %s %s: permission refused. On Windows that usually "
                "means the file is open in a viewer -- close it, or pass -o "
                "to write somewhere else" % (what, where))
    if isinstance(trouble, FileNotFoundError):
        return ("cannot %s %s: part of that path does not exist" % (what, where))
    if isinstance(trouble, IsADirectoryError):
        return "cannot %s %s: it is a directory" % (what, where)
    if isinstance(trouble, FileExistsError):
        return ("cannot %s %s: something of that name is already there and is "
                "not a directory" % (what, where))
    return "cannot %s %s: %s" % (what, where, trouble)


def _shown(where):
    """A path to print: short when it is inside the repository, whole when not."""
    try:
        inside = os.path.relpath(where, ROOT)
    except ValueError:
        ## a different drive on Windows has no relative path to here at all
        return where
    return where if inside.startswith("..") else inside


def ground_colour(text):
    """What to draw a block against, from a name or a hex code.

    PIL carries the whole CSS colour table, so a name costs nothing to support
    and is easier to type than a number. A bare hex code with no `#` in front is
    taken as one anyway, because that is what somebody types and there is no
    colour named for six hex digits to be confused with. The name is tried
    first, so a name always wins.
    """
    for attempt in (text, "#" + text.lstrip("#")):
        try:
            found = ImageColor.getrgb(attempt)
        except ValueError:
            continue
        ## a colour given with an alpha still paints an opaque background
        return tuple(found[:3])
    raise ValueError(
        "no colour called %r; give a name like 'skyblue' or a hex code "
        "like 18181c" % text)


def _open(where):
    """Hand the picture to whatever the desktop opens images with.

    Every platform has its own way and none of them raises usefully when there
    is nothing to open it with, so a failure is reported and nothing more: the
    file is written either way and saying where it is has already been done.
    """
    import subprocess

    try:
        if sys.platform.startswith("win"):
            os.startfile(where)                  # noqa: S606 - the point of it
        elif sys.platform == "darwin":
            subprocess.run(["open", where], check=False)
        else:
            subprocess.run(["xdg-open", where], check=False)
    except Exception as trouble:
        print("could not open it: %s" % trouble)


def _named(args):
    """A file name that says which block, and which of it.

    Drawing the same block in two states should leave two pictures rather than
    one that got written over.
    """
    parts = [args.block]
    if args.rot:
        parts.append("rot%d" % args.rot)
    if args.variant:
        parts.append(str(args.variant))
    if args.data is not None:
        parts.append("data%s" % args.data)
    if args.top:
        parts.append("top")
    for flag, mark in ((args.iso, "iso"), (args.no_iso, "flat"),
                       (args.every, "all")):
        if flag:
            parts.append(mark)
    if args.view:
        parts.extend(name.strip() for group in args.view
                     for name in group.split(",") if name.strip())
    return "-".join(parts)


if __name__ == "__main__":
    sys.exit(main())
