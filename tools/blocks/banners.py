"""Give a banner its post, its cloth, and the sheet each of them reads.

    python -m tools.blocks.banners

A banner was `ignore`, so it was not drawn at all. It is a cloth hanging from a
post, and both are on one sheet. Standing banners turn in sixteen steps like a
sign; wall banners hang off the block behind them.

**The post is wood and it has to read the wood.** Both were reading a window in
the cloth's corner of the sheet, so a banner was a coloured post with a coloured
cloth on it. The post is up the right of the sheet at x44 and the bar across the
bottom of the cloth at y42, and `tools/textures/banners.py` leaves both of them
alone when it dyes a sheet.

**And a banner is two blocks tall.** It stands up out of the block it belongs
to, the way the game draws it and the way a dragon head and a copper golem
statue do here.

**A banner is drawn in its colour but without its patterns.** The colour is in
the block entity, as `Base`, and `tools/textures/banners.py` dyes the sheet once
per colour so that each has a texture to read: vanilla tints one white sheet at
run time and a ghost block cannot tint. Patterns are a different matter. A
banner may carry six, each with a colour of its own, which is more combinations
than could be written to disk, so the two that are not a dye get a sheet each
instead.

Nothing here is needed at run time. Re-run `python -m tools.blocks.simplify`
afterwards.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables
from tools.blocks.geometry import Cube, on_sheet, unwrap


def _middle(region, tile=16):
    """A face's rectangle on the sheet, cut down to what a tile can hold.

    **An over-sized face is served by the middle of itself, not by its left
    end.** The bar is drawn twenty across where the block's bar is sixteen, and
    the six pixels that pattern its middle -- two light, two dark, two light --
    have to land in the middle of the block's bar. Reading the left sixteen put
    them two pixels off it. The post is the same the other way round: forty-two
    down against thirty in the block.
    """
    x, y, wide, tall = region
    if wide > tile:
        x, wide = x + (wide - tile) // 2, tile
    if tall > tile:
        y, tall = y + (tall - tile) // 2, tile
    return x, y, wide, tall


def _windows(box):
    """One piece of the sheet as a tile corner and a window, per face.

    `box` is where the entity model lays the piece out, as (uv, size).
    `on_sheet` picks each corner: it pulls back far enough that the face fits
    inside the tile and never past the edge of the sheet, because a corner with
    less than a whole tile inside the sheet is thrown away and read from 0,0
    instead -- and 0,0 on a banner sheet is the cloth, which is how the post
    came out dyed.
    """
    art, window = {}, {}
    for face, region in unwrap(*box).items():
        mark, fitted = on_sheet("", _middle(region), SHEET)
        art[face] = mark
        window[face] = fitted
    return art, window


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
# across the bottom of the cloth at y42, and `tools/textures/banners.py` leaves
# both of them alone when it dyes a sheet.
#
# **And a banner is two blocks tall.** It stands up out of the block it belongs
# to, the way the game draws it and the way a dragon head and a copper golem
# statue do here.
BANNER = "textures/entity/banner/banner_%s"
SHEET = 64                  # vanilla's own sheet, which every corner fits in
TILE = 16

## Where the three pieces sit on the sheet, as the boxes the entity model draws
## them from: the cloth 20x40x1 at the corner, the post 2x42x2 up the right, and
## the bar 20x2x2 under the cloth.
CLOTH_BOX = ((0, 0), (20, 40, 1))
POLE_BOX = ((44, 0), (2, 42, 2))
BAR_BOX = ((0, 42), (20, 2, 2))

POLE_ART, POLE = _windows(POLE_BOX)
BAR_ART, BAR = _windows(BAR_BOX)

## **The cloth reads one corner well inside itself.** Its south face runs from
## 1,1 to 21,41 on the sheet, so a window starting at the sheet's own corner
## takes the transparent pixel above the cloth's top left and the strip the box
## unwrap puts along the top -- a hole in the corner of every banner. The middle
## sixteen of that face has none of it and no edge either.
##
## One corner does for all six faces because a dyed cloth is one colour: the
## twenty-four shades in it are all within a few units of each other, and no
## grid of quads would show a difference. The two marked forms are the
## exception and hang their design as a grid, below.
CLOTH_ART = "#%d,%d" % _middle(unwrap(*CLOTH_BOX)["south"])[:2]
CLOTH = {face: (0, 0, TILE, TILE) for face in
         ("up", "down", "north", "south", "east", "west")}

POLE_TALL = 30              # nearly two blocks, which is where vanilla stops
BAR_TALL = 2                # the bar the cloth hangs from, across the top
CLOTH_TALL = 27
## as wide as the bar it hangs from. Narrower left the bar sticking out a
## pixel at each end, which vanilla does not do
CLOTH_WIDE = 16
CLOTH_DEEP = 1              # a banner is a pixel thick, and vanilla draws it so

## The colour is in the block entity, as `Base`, and `core.ENTITY_SHAPES` hands
## it over as the form to draw. Each form names the sheet
## `tools/textures/banners.py` dyed for that colour, because the game tints
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

## **Which sheet a marked banner takes its edges from.** An edge is plain cloth
## beside the design, and a sheet's own plain cloth is what vanilla dyes from
## rather than what the banner reads as: the ominous sheet's is a light grey
## while the banner itself is dark, so its edges came out pale against its own
## face. It borrows black's. The designed sheet needs nothing, because
## `tools/textures/banners.py` tints the whole of it grey before writing on it.
BANNER_EDGE = {"illager": "black"}

## **A design is taller than a tile, so a cloth carrying one is a column of
## quads.** Only sixteen by sixteen of a texture becomes a tile and a quad reads
## one tile, so a design on a single quad is a design at sixteen by sixteen --
## squashed to a square, where the cloth it sits on is sixteen across by
## twenty-seven down. The two marked forms hang their cloth as four quads down
## instead, each reading a tile of its own out of the design
## `tools/textures/banners.py` writes under the sheet. Keep these in step
## with that script's `DESIGN`, `DESIGN_AT` and `TILE`.
##
## **One quad across, not two.** The cloth is exactly one tile wide, so cutting
## it in two bought a little horizontal detail and cost a seam down the middle
## of the banner -- and the two halves have to be swapped as well as each being
## turned round, since the sheet holds the design mirrored and the mirror of two
## columns side by side is the right one on the left. In game the front came out
## split with its halves out of step, with tears along the seam. The design is
## only ever seen at sixteen pixels across on the block, so the detail was
## paying for a join that had nothing to hold it together.
DESIGN_ACROSS, DESIGN_DOWN = 1, 4
DESIGN_AT = (0, 64)
TILE = 16
## **Both faces of a design turn their tile round, because the sheet holds it
## the wrong way round.** `tools/textures/banners.py` writes the picture
## mirrored on purpose, so every face reading it has to mirror it back -- not
## just the one a banner is looked at. The two faces of a plane already run
## their windows in opposite directions, which is what makes the back come out
## as the mirror of the front once both are turned; leaving the back alone
## instead cancelled one flip against the other and split the design down the
## middle, the same way the columns did.
##
## A cloth of flat colour has nothing to gain from any of this, so the sixteen
## dyed banners stay one quad apiece and read their tile as it comes.
CLOTH_DESIGN = dict(CLOTH, south=(TILE, 0, -TILE, TILE),
                    north=(TILE, 0, -TILE, TILE))


def art(sheet, corners):
    """This sheet's name, with the tile corner each face reads written on it."""
    return {face: sheet + mark for face, mark in corners.items()}


def cloth(sheet, at, design=False, edge=None):
    """The cloth, as one quad or as the column of quads a design needs.

    **A design is written mirrored and read back mirrored**, which is what
    `tools/textures/banners.py` means by "the image needs to be mirrored for the
    face we are putting it on": the sheet holds the picture the wrong way round
    and `CLOTH_DESIGN` turns it the right way round again on the faces that
    carry it.

    The column arithmetic is kept general, but `DESIGN_ACROSS` is one: the cloth
    is a tile wide, and cutting it in two put a seam down the middle of the
    banner that the halves would not meet across. Rows need none of that:
    mirroring is left to right, and `down` counts from the top of the design to
    the quad at the greatest y.
    """
    if not design:
        return [Cube((CLOTH_WIDE, CLOTH_TALL, CLOTH_DEEP), at,
                     sheet + CLOTH_ART, window=CLOTH)]
    wide = CLOTH_WIDE / float(DESIGN_ACROSS)
    tall = CLOTH_TALL / float(DESIGN_DOWN)
    return [Cube((wide, tall, CLOTH_DEEP),
                 (at[0] + across * wide,
                  at[1] + (DESIGN_DOWN - 1 - down) * tall,
                  at[2]),
                 texture=design_faces(
                     sheet, edge=edge,
                     tile="%s#%d,%d" % (sheet,
                                   DESIGN_AT[0]
                                   + (DESIGN_ACROSS - 1 - across) * TILE,
                                   DESIGN_AT[1] + down * TILE)),
                 window=CLOTH_DESIGN)
            for down in range(DESIGN_DOWN)
            for across in range(DESIGN_ACROSS)]


def design_faces(sheet, tile, edge=None):
    """The design on the two faces that show it, cloth on the four that do not.

    **Only the front and the back of a banner carry the picture.** The other
    four faces of a quad are its edges -- the cloth is a pixel thick, and a
    design grid cuts it into eight, so those edges are the seams between the
    quads as well as the rim of the whole cloth. Reading the design on them put
    a squashed column of it down every seam. They take the plain cloth instead,
    from the same corner the sixteen dyed banners read.

    **Off `edge`'s sheet when the design's own cloth is the wrong colour.** A
    sheet's plain cloth is what vanilla dyes from, and on the ominous banner
    that is a light grey while the banner itself reads dark, so its edges came
    out pale against its own face. `BANNER_EDGE` says which sheet to borrow.
    """
    plain = (edge or sheet) + CLOTH_ART
    faces = {face: plain for face in CLOTH}
    faces["north"] = faces["south"] = tile
    return faces


def standing(sheet, design=False, edge=None):
    """On the floor: a post up the middle with the cloth hanging in front.

    It stands out of its own block, the way the game draws one. A ghost block is
    read as a mark on the place a block goes, and a banner that stopped at the
    top of its own block read as half a banner.
    """
    ## Hung against the post rather than a pixel clear of it. Its front face
    ## would then land exactly on the post's, over the two pixels they share, so
    ## the cloth is drawn a shade thinner and finishes just inside the post
    ## instead of on its plane.
    ##
    ## The bar is the same one a wall banner hangs from, at the top of the post,
    ## which is where the entity model puts it: the cloth hangs from a bar in
    ## both mountings and a post with the cloth tied straight to it was the odd
    ## one out.
    ## **The post stops where the bar starts.** The game draws the bar over the
    ## top of the post and never sees the two pixels underneath it; drawn as
    ## ghost blocks they are two faces on the same plane, which is a flicker
    ## rather than a join. So the post is short by the height of the bar.
    hangs = POLE_TALL - BAR_TALL
    ## the cloth hangs the whole depth of the bar, its top edge level with the
    ## bar's own, rather than starting under it and leaving a seam
    top = hangs + BAR_TALL
    return ([Cube((2, hangs, 2), (7, 0, 7), art(sheet, POLE_ART), window=POLE),
             Cube((16, BAR_TALL, 2), (0, hangs, 7), art(sheet, BAR_ART),
                  window=BAR)]
            + cloth(sheet, (0, top - CLOTH_TALL, 9), design, edge))


def wall(sheet, design=False, edge=None):
    """On a wall: the bar lies across the top and the cloth hangs below it.

    Against the block behind it, at z 0, the way a wall sign sits, and the cloth
    hangs down past the block's own floor.
    """
    hangs = 16 - BAR_TALL
    top = hangs + BAR_TALL
    return ([Cube((16, BAR_TALL, 2), (0, hangs, 0), art(sheet, BAR_ART),
                  window=BAR)]
            ## and out of the wall far enough to clear the bar
            + cloth(sheet, (0, top - CLOTH_TALL, 2), design, edge))


def dyed(shape):
    """One form per colour, and white for a banner with no entity beside it."""
    last = len(BANNER_COLOURS) - 1
    forms = {str(n): shape(BANNER % BANNER_COLOURS[last - n])
             for n in range(len(BANNER_COLOURS))}
    for marked in BANNER_MARKED:
        borrowed = BANNER_EDGE.get(marked)
        forms[marked] = shape(BANNER % marked, design=True,
                              edge=BANNER % borrowed if borrowed else None)
    forms["default"] = shape(BANNER % "white")
    return forms


STANDING = dyed(standing)
WALL = dyed(wall)

## a standing banner turns in sixteen steps, a wall banner in four
SIXTEEN = {str(n): [0, round(n * 22.5, 1), 0] for n in range(16)}
FOUR = {"2": [0, 180, 0], "3": [0, 0, 0], "4": [0, 90, 0], "5": [0, 270, 0],
        "south": [0, 0, 0], "west": [0, 90, 0], "north": [0, 180, 0],
        "east": [0, 270, 0]}


def main():
    print("writing the banners")
    tables.write("standing_banner", STANDING)
    tables.turns("standing_banner", SIXTEEN)
    tables.write("wall_banner", WALL)
    tables.turns("wall_banner", FOUR)
    tables.define(["standing_banner"], "standing_banner")
    tables.define(["wall_banner"], "wall_banner")
    print("   standing and wall, %d colours" % len(BANNER_COLOURS))
    print("now re-run python -m tools.blocks.simplify")


if __name__ == "__main__":
    main()
