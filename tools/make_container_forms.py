"""Give shulker boxes and banners the shape and the sheet they really have.

    python tools/make_container_forms.py

A shulker box was a cube wearing its lid texture on all six faces, because the
only thing `blocks.json` names for it is `shulker_top_<colour>`. It is really a
base with a lid on top, and the whole box is one entity sheet, 64x64 per colour.
Each colour is a family of its own: the sheet is the only thing that tells them
apart, and one family cannot carry seventeen of them.

A banner was `ignore`, so it was not drawn at all. It is a cloth hanging from a
pole, and both are on one sheet. Standing banners turn in sixteen steps like a
sign; wall banners hang off the block behind them.

The sheets are copied out of the community submodule into `textures/entity/`.
Only the top left 16x16 of a texture becomes a tile, so every face names the
window it reads.

**A banner is drawn in its colour but without its patterns.** The colour is in
the block entity, as `Base`, and `tools/make_banner_textures.py` dyes the sheet
once per colour so that each has a texture to read: vanilla tints one white
sheet at run time and a ghost block cannot tint. Patterns are a different
matter. A banner may carry six, each with a colour of its own, which is more
combinations than could be written to disk, so they would have to be composited
while a pack is built and handed to the atlas as a picture rather than a file.

Nothing here is needed at run time. Re-run `tools/make_low_geometry.py`
afterwards.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import lookup_writer
from make_block_forms import Cube, build

LOOKUPS = os.path.join(ROOT, "structura", "lookups")
SHAPES = os.path.join(LOOKUPS, "block_shapes.json")
UV = os.path.join(LOOKUPS, "block_uv.json")
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")


# --- shulker boxes ----------------------------------------------------------
#
# The sheet is the entity one: the lid's top sits at x16 y0, the lid's sides run
# across y16, and the base's sides across y36. The box is drawn as the two parts
# it has, so the lid's art is on the lid and the base's on the base.
SHULKER = "textures/entity/shulker/shulker_%s"

## The dyes that name a block, then below them the ids that name no colour and
## the one whose sheet is spelled differently: Bedrock calls the block light
## gray and the sheet silver, and there is no silver_shulker_box to define.
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]
EXTRA = {"undyed_shulker_box": "undyed", "shulker_box": "undyed",
         "light_gray_shulker_box": "silver"}


def shulker(colour):
    """A base with a lid on it, each reading its own part of the sheet."""
    sheet = SHULKER % colour
    lid = Cube((16, 8, 16), (0, 8, 0), texture={
        "up": sheet + "#16,0", "down": sheet + "#0,16",
        "north": sheet + "#0,16", "south": sheet + "#0,16",
        "east": sheet + "#0,16", "west": sheet + "#0,16"}, window={
        "up": (0, 0, 16, 16), "down": (0, 0, 16, 12),
        "north": (0, 0, 16, 12), "south": (0, 0, 16, 12),
        "east": (0, 0, 16, 12), "west": (0, 0, 16, 12)})
    base = Cube((16, 8, 16), (0, 0, 0), texture={
        "up": sheet + "#0,32", "down": sheet + "#0,48",
        "north": sheet + "#0,32", "south": sheet + "#0,32",
        "east": sheet + "#0,32", "west": sheet + "#0,32"}, window={
        "up": (0, 0, 16, 12), "down": (0, 0, 16, 12),
        "north": (0, 4, 16, 12), "south": (0, 4, 16, 12),
        "east": (0, 4, 16, 12), "west": (0, 4, 16, 12)})
    return {"default": [base, lid]}


# --- banners ----------------------------------------------------------------
#
# A pole with a cloth hanging from it. The sheet holds the cloth across its left
# and the pole up its right, and the cloth is a plane rather than a box: a
# banner is one pixel thick and reading a box unwrap onto it would put the back
# of the cloth on its front.
#
# **The pole is wood and it has to read the wood.** Both were reading a window
# in the cloth's corner of the sheet, so a banner was a coloured post with a
# coloured cloth on it. The post is up the right of the sheet at x44 and the bar
# across the bottom of the cloth at y42, and `make_banner_textures.py` leaves
# both of them alone when it dyes a sheet.
#
# **And a banner is two blocks tall.** It stands up out of the block it belongs
# to, the way the game draws it and the way a dragon head and a copper golem
# statue do here.
BANNER = "textures/entity/banner/banner_%s"
POLE_ART = "#44,2"          # the post, up the right of the sheet
BAR_ART = "#0,42"           # the bar it hangs from, under the cloth
CLOTH = {face: (0, 0, 16, 16) for face in
         ("up", "down", "north", "south", "east", "west")}
## the post is two across and the sheet draws it forty two down, which is more
## than a tile holds; it is one colour, so a sixteen tall slice of it serves
POLE = {"north": (0, 0, 2, 16), "south": (0, 0, 2, 16),
        "east": (0, 0, 2, 16), "west": (0, 0, 2, 16),
        "up": (0, 0, 2, 2), "down": (0, 0, 2, 2)}
BAR = {face: (0, 0, 16, 4) for face in
       ("up", "down", "north", "south", "east", "west")}

POLE_TALL = 30              # nearly two blocks, which is where vanilla stops
CLOTH_TALL = 27
CLOTH_WIDE = 14
## thin enough that a cloth hung against the post finishes inside it rather
## than on the same plane as its face
CLOTH_DEEP = 0.3

## The colour is in the block entity, as `Base`, and `core.ENTITY_SHAPES` hands
## it over as the form to draw. Each form names the sheet
## `tools/make_banner_textures.py` dyed for that colour, because the game tints
## one white sheet at run time and a ghost block cannot tint.
##
## **`Base` counts backwards.** It is the dye's own number rather than the
## wool's, and the two run in opposite directions: 0 is black and 15 is white,
## not the other way about. Read as wool, every banner came out as the colour
## opposite its own -- white black, lime purple, light blue brown.
BANNER_COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime",
                  "pink", "gray", "silver", "cyan", "purple", "blue", "brown",
                  "green", "red", "black"]

## The two banners that are not a dye at all. An ominous banner has a sheet of
## its own in the vanilla pack and a banner carrying patterns gets a stand-in,
## since a ghost block cannot composite six patterns and their colours as a pack
## is built. `core.ENTITY_INSTEAD` is what names these forms.
BANNER_MARKED = ("illager", "designed")

## **A design is bigger than a tile, so a cloth carrying one is a grid.** Only
## sixteen by sixteen of a texture becomes a tile and a quad reads one tile, so
## a design on a single quad is a design at sixteen by sixteen -- less than the
## twenty by forty vanilla draws a cloth at, and squashed to a square besides.
## The two marked forms hang their cloth as two quads across by four down
## instead, each reading a tile of its own out of the design
## `tools/make_banner_textures.py` writes under the sheet. Keep these in step
## with that script's `DESIGN`, `DESIGN_AT` and `TILE`.
DESIGN_ACROSS, DESIGN_DOWN = 2, 4
DESIGN_AT = (0, 64)
TILE = 16
## The face a banner is looked at is south, and a plane's two faces run their
## windows in opposite directions: the same tile that reads the right way round
## on the north face reads backwards on the south one. So the side that has to
## be right takes its tile the other way round, the way a bed's long sides do.
## A cloth of flat colour has nothing to gain from any of this, so the sixteen
## dyed banners stay one quad apiece and read their tile as it comes.
CLOTH_FRONT = dict(CLOTH, south=(TILE, 0, -TILE, TILE))


def cloth(sheet, at, design=False):
    """The cloth, as one quad or as the grid a design needs.

    The design is laid out the way it is written: its leftmost column on the
    quad at the least x, its top row on the quad at the greatest y. What has to
    be turned round instead is the picture within each tile, because the two
    faces of a plane run their windows in opposite directions and the face a
    banner is looked at is the one that reads its tile backwards. Turning the
    columns round rather than the tiles draws each tile flipped where it stands,
    which is not a mirrored design but a jumbled one.
    """
    if not design:
        return [Cube((CLOTH_WIDE, CLOTH_TALL, CLOTH_DEEP), at, sheet,
                     window=CLOTH)]
    wide = CLOTH_WIDE / float(DESIGN_ACROSS)
    tall = CLOTH_TALL / float(DESIGN_DOWN)
    return [Cube((wide, tall, CLOTH_DEEP),
                 (at[0] + across * wide,
                  at[1] + (DESIGN_DOWN - 1 - down) * tall,
                  at[2]),
                 "%s#%d,%d" % (sheet, DESIGN_AT[0] + across * TILE,
                               DESIGN_AT[1] + down * TILE),
                 window=CLOTH_FRONT)
            for down in range(DESIGN_DOWN)
            for across in range(DESIGN_ACROSS)]


def standing(sheet, design=False):
    """On the floor: a post up the middle with the cloth hanging in front.

    It stands out of its own block, the way the game draws one. A ghost block is
    read as a mark on the place a block goes, and a banner that stopped at the
    top of its own block read as half a banner.
    """
    ## Hung against the post rather than a pixel clear of it. Its front face
    ## would then land exactly on the post's, over the two pixels they share, so
    ## the cloth is drawn a shade thinner and finishes just inside the post
    ## instead of on its plane.
    return ([Cube((2, POLE_TALL, 2), (7, 0, 7), sheet + POLE_ART, window=POLE)]
            + cloth(sheet, (1, 3, 9), design))


def wall(sheet, design=False):
    """On a wall: the bar lies across the top and the cloth hangs below it.

    Against the block behind it, at z 0, the way a wall sign sits, and the cloth
    hangs down past the block's own floor.
    """
    return ([Cube((16, 2, 2), (0, 14, 0), sheet + BAR_ART, window=BAR)]
            ## and out of the wall far enough to clear the bar
            # + cloth(sheet, (1, 15 - CLOTH_TALL, 4), design))
            + cloth(sheet, (1, 14, 2), design))


def dyed(shape):
    """One form per colour, and white for a banner with no entity beside it."""
    last = len(BANNER_COLOURS) - 1
    forms = {str(n): shape(BANNER % BANNER_COLOURS[last - n])
             for n in range(len(BANNER_COLOURS))}
    for marked in BANNER_MARKED:
        forms[marked] = shape(BANNER % marked, design=True)
    forms["default"] = shape(BANNER % "white")
    return forms


STANDING = dyed(standing)
WALL = dyed(wall)

## a standing banner turns in sixteen steps, a wall banner in four
SIXTEEN = {str(n): [0, round(n * 22.5, 1), 0] for n in range(16)}
FOUR = {"2": [0, 180, 0], "3": [0, 0, 0], "4": [0, 90, 0], "5": [0, 270, 0],
        "south": [0, 0, 0], "west": [0, 90, 0], "north": [0, 180, 0],
        "east": [0, 270, 0]}


def define(blocks, family):
    table = json.load(io.open(DEFINITION, encoding="utf-8"))
    for block in blocks:
        table[block] = family
    io.open(DEFINITION, "w", encoding="utf-8", newline="").write(
        json.dumps(table, indent="\t", ensure_ascii=False,
                   separators=(",", ":")) + "\n")


def write(family, forms, rotation=None):
    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes)
    lookup_writer.put(SHAPES, family, shapes, tight=True)
    lookup_writer.put(UV, family, uvs, tight=True)
    if rotation:
        lookup_writer.put(ROTATION, family, rotation, tight=True)


def main():
    print("writing the shulker boxes")
    for colour in COLOURS:
        family = "shulker_box_%s" % colour
        write(family, shulker(colour))
        define(["%s_shulker_box" % colour], family)
    for block, colour in EXTRA.items():
        family = "shulker_box_%s" % colour
        write(family, shulker(colour))
        define([block], family)
    print("   %d colours" % (len(COLOURS) + 1))

    print("writing the banners")
    write("standing_banner", STANDING, SIXTEEN)
    write("wall_banner", WALL, FOUR)
    define(["standing_banner"], "standing_banner")
    define(["wall_banner"], "wall_banner")
    print("   standing and wall, %d colours" % len(BANNER_COLOURS))
    print("now re-run tools/make_low_geometry.py")


if __name__ == "__main__":
    main()
