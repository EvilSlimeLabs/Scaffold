"""Give the blocks that are furniture a shape worth the name.

    python -m tools.blocks.furniture

A lectern is a stand with a sloped desk on it, an enchanting table is a slab
with a book floating above, a bed is a mattress on legs and a conduit is a small
cage hanging in the middle of its block. Drawn as full cubes, which is what a
lookup with one entry gives them, they read as stone blocks in a row and say
nothing about what they are.

These also carry the states that change what they look like. A bed is two
blocks, head and foot, and the two are not the same shape or the same texture. A
conduit is open when it is powered and closed when it is not. A daylight
detector has a second block id for its inverted form, with a top of its own.

Nothing here is needed at run time. Re-run `tools/blocks/simplify.py`
afterwards: most of these have more than two cubes and want a simple form.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer
from tools.blocks.geometry import Cube, FACES, build, on_sheet
from tools.blocks import tables as _tables

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
DEFINITION = os.path.join(LOOKUPS, "block_definition.json")
ROTATION = os.path.join(LOOKUPS, "block_rotation.json")

BLOCKS = "textures/blocks/%s"


def write(family, forms, center=(8, 8, 8)):
    shapes, uvs = {}, {}
    for name, cubes in forms.items():
        shapes[name], uvs[name] = build(cubes, center)
    lookup_writer.put(SHAPES, family, shapes, tight=True)
    lookup_writer.put(UV, family, uvs, tight=True)
    print("   %-22s %s" % (family, ", ".join(forms)))


def define(blocks, family):
    """Point block ids at a shape family."""
    _tables.define(blocks, family)


def turns(family, table):
    """Give a family a rotation entry: Minecraft's angles, or the name of the
    state whose own angles it turns by."""
    lookup_writer.put(ROTATION, family, table, tight=True)


# --- daylight detector ------------------------------------------------------
#
# Three pixels tall, not a cube. The inverted detector is a block id of its own
# rather than a state, and the only thing that tells the two apart is the top:
# `daylight_detector_top` is a list of two, the plain one and the inverted.
DAYLIGHT = {"default": [Cube((16, 6, 16), (0, 0, 0))]}
DAYLIGHT_INVERTED = {"default": [Cube(
    (16, 6, 16), (0, 0, 0),
    texture={"up": BLOCKS % "daylight_detector_inverted_top",
             "down": "default", "north": "default", "south": "default",
             "east": "default", "west": "default"})]}


# --- lectern ----------------------------------------------------------------
#
# A post on a base with a desk sloped over the top of it.
#
# **Every face names the part of its texture it reads.** A face left to work its
# own window out takes the slice its cube happens to sit at, which is right for
# a block drawn from a terrain tile and wrong for every face here. Two of the
# three textures pack more than one piece of the block into one tile, so a face
# that reads the whole of either gets both pieces squeezed onto it:
#
#   lectern_front   the post, front on the left half, back on the right
#   lectern_sides   the desk down the top half, the post down the bottom half,
#                   and within the desk's half the front is the top quarter and
#                   the other three sides the quarter under it
#   lectern_base    planks, with the red inlay across the bottom of the tile
#
# **The front is north**, where a block at rest faces. The desk leans 22 about
# x, which drops its north edge, so the low side of the desk and the books on
# the post both face north.
LECTERN_WHOLE = (0, 0, 16, 16)

## the post: `lectern_front` is two 8 wide pictures side by side
LECTERN_BOOKS = (0, 0, 8, 16)       # the front, with the books on the shelf
LECTERN_BACK = (8, 0, 8, 16)        # the back, which is plain
## and its sides are the lower half of `lectern_sides`, which is drawn lying on
## its side: turned a quarter clockwise that half becomes the left of the tile,
## eight across by sixteen down, and the shading that ran down its left edge
## ends up across the top, where the desk overhangs the post.
##
## **The two sides are the same picture facing opposite ways.** A cube's east
## and west faces run their windows in opposite directions round the box, so one
## picture laid on both has its shading pointing to the front on one side and to
## the back on the other. The east face reads its eight pixels from the far end
## back, which is what a negative width does, and the post is then the same from
## either side.
LECTERN_POST_SIDE = (0, 0, 8, 16, 90)
LECTERN_POST_SIDE_BACK = (8, 0, -8, 16, 90)

## the desk: the upper half of `lectern_sides`, split again
LECTERN_DESK_FRONT = (0, 0, 16, 4)
LECTERN_DESK_SIDE = (0, 4, 16, 4)

## the base: the red inlay sits across the bottom of `lectern_base`, and only
## the front wears it. The other three take planks from the same phase of the
## pattern -- rows nine and ten rather than the first two -- so a seam does not
## land on three sides of the block and miss the fourth.
LECTERN_BAND = (0, 13, 16, 2)
LECTERN_PLANK = (0, 9, 16, 2)

## **The flat faces read their tiles backwards.** An up face runs its v from the
## block's south edge to its north one and a down face the other way, so a
## picture laid out the way it is seen from the front arrives back to front.
## A negative size in the window turns it round.
LECTERN_BASE_TOP = (16, 0, -16, 16)
LECTERN_PLANK_FLAT = (16, 11, -16, -2)
LECTERN_UNDER = (16, 12, -16, -12)
LECTERN_BACKWARDS = (16, 16, -16, -16)

LECTERN = {"default": [
    ## The base. Its underside is planks rather than `lectern_base`: the game
    ## reads a slot of its own for it and the tile it would otherwise take
    ## carries the red inlay, which does not belong under the block. A plank
    ## tile's seams run every four rows and the last of them is its bottom row,
    ## which a down face lays along the block's front.
    Cube((16, 2, 16), (0, 0, 0), texture={
        "up": BLOCKS % "lectern_base", "down": BLOCKS % "planks_oak",
        "north": BLOCKS % "lectern_base", "south": BLOCKS % "lectern_base",
        "east": BLOCKS % "lectern_base", "west": BLOCKS % "lectern_base"},
         window={"up": LECTERN_BASE_TOP, "down": LECTERN_BACKWARDS,
                 "north": LECTERN_BAND, "south": LECTERN_PLANK,
                 "east": LECTERN_PLANK, "west": LECTERN_PLANK}),
    ## The post. It runs up to the underside of the desk rather than stopping at
    ## the top of its own block: the desk is tilted, so its back edge lifts, and
    ## a post measured to the flat left a gap behind it.
    Cube((8, 12, 8), (4, 2, 4), texture={
        "up": BLOCKS % "lectern_base", "down": BLOCKS % "lectern_base",
        "north": BLOCKS % "lectern_front", "south": BLOCKS % "lectern_front",
        "east": BLOCKS % "lectern_sides", "west": BLOCKS % "lectern_sides"},
         window={"up": LECTERN_PLANK_FLAT, "down": LECTERN_PLANK_FLAT,
                 "north": LECTERN_BOOKS, "south": LECTERN_BACK,
                 "east": LECTERN_POST_SIDE_BACK,
                 "west": LECTERN_POST_SIDE}),
    ## The desk.
    Cube((16, 4, 14), (0, 12, 1), texture={
        "up": BLOCKS % "lectern_top", "down": BLOCKS % "lectern_base",
        "north": BLOCKS % "lectern_sides", "south": BLOCKS % "lectern_sides",
        "east": BLOCKS % "lectern_sides", "west": BLOCKS % "lectern_sides"},
         window={"up": LECTERN_WHOLE, "down": LECTERN_UNDER,
                 "north": LECTERN_DESK_FRONT, "south": LECTERN_DESK_SIDE,
                 "east": LECTERN_DESK_SIDE, "west": LECTERN_DESK_SIDE},
         rotation=(22, 0, 0))]}

## --- the book on it --------------------------------------------------------
##
## A lectern's book is not in its states. The block carries which way it faces
## and whether it is powered, and whether anybody put a book on it is in the
## block entity beside it, the way a sign keeps its text; the family's
## `instead` rule reads it and names this form.
##
## The book is drawn the way the game draws it: two covers open flat with a
## sheaf of pages on each, lying along the desk and leaning with it. Vanilla
## paints it from `textures/entity/enchanting_table_book.png`, a 64 by 32 sheet
## the enchanting table's book comes off as well, so the regions below are
## Mojang's own layout -- the covers across the top ten rows and the pages in
## the nine under them.
BOOK_SHEET = "textures/entity/enchanting_table_book"
BOOK_SIZE = 64

## the two halves of the cover, and the two sheaves of pages
BOOK_COVER = (6, 10)
BOOK_PAGES = (5, 8)
## where each is on the sheet
BOOK_COVER_LEFT = (0, 0) + BOOK_COVER
BOOK_COVER_RIGHT = (16, 0) + BOOK_COVER
BOOK_PAGES_LEFT = (0, 10) + BOOK_PAGES
BOOK_PAGES_RIGHT = (12, 10) + BOOK_PAGES

## how thick a leaf is drawn, and how far above the desk the book sits. The
## desk's own top is at 16 and leans 22 about its middle, so the book leans
## with it and is written just clear of the surface.
BOOK_LEAF = 0.2
BOOK_ON = 16.1
BOOK_LEAN = (22, 0, 0)


def leaf(size, at, region):
    """One flat piece of the book, painted from the sheet on both faces.

    Only the two large faces are ever seen -- the leaf is a fifth of a pixel
    thick -- so all six take the same region rather than four of them reading a
    strip of whatever they happen to sit over. The top and the bottom read it
    backwards, as every flat face here does.
    """
    name, window = on_sheet(BOOK_SHEET, region, BOOK_SIZE)
    x, y, wide, tall = window
    flat = (x + wide, y + tall, -wide, -tall)
    return Cube((size[0], BOOK_LEAF, size[1]), at, texture=name,
                window={face: flat if face in ("up", "down") else window
                        for face in FACES}, rotation=BOOK_LEAN)


## the covers first and the pages a hair above them, so the pages win where the
## two overlap
## the left half of the sheet is the book's west half, the high side of x
LECTERN_BOOK = LECTERN["default"] + [
    leaf(BOOK_COVER, (8, BOOK_ON, 3), BOOK_COVER_LEFT),
    leaf(BOOK_COVER, (2, BOOK_ON, 3), BOOK_COVER_RIGHT),
    leaf(BOOK_PAGES, (8, BOOK_ON + BOOK_LEAF, 4), BOOK_PAGES_LEFT),
    leaf(BOOK_PAGES, (3, BOOK_ON + BOOK_LEAF, 4), BOOK_PAGES_RIGHT)]

LECTERN["book"] = LECTERN_BOOK


# --- enchanting table -------------------------------------------------------
#
# Three quarters of a block, with the book above it. The book is two leaves
# leaning together, drawn from the table's own top texture: the book's own
# texture is an entity sheet the trimmed pack does not carry.
ENCHANTING = {"default": [
    Cube((16, 12, 16), (0, 0, 0)),
    Cube((8, 0.2, 6), (4, 14, 5), BLOCKS % "enchanting_table_top",
         rotation=(0, 0, 20)),
    Cube((8, 0.2, 6), (4, 14, 5), BLOCKS % "enchanting_table_top",
         rotation=(0, 0, -20))]}


# --- conduit ----------------------------------------------------------------
#
# A small cage in the middle of the block.
#
# **The cage is `conduit_base` and neither of the two shells.** That file is
# 24x12, which is the unwrap of a box six by six by six laid out the way Bedrock
# lays one out: the top and the bottom across the first six rows, then the four
# walls in a strip under them. Six by six by six is the cage. The two 8x8 shells
# beside it are the eye that opens once the conduit is running, and a conduit in
# a structure is not running, so both of them were the wrong picture.
CONDUIT_BASE = BLOCKS % "conduit_base"
CLOSED = BLOCKS % "conduit_closed"
OPEN = BLOCKS % "conduit_open"
CAGE = 6
CAGE_AT = {"up": (CAGE, 0), "down": (CAGE * 2, 0), "west": (0, CAGE),
           "south": (CAGE, CAGE), "east": (CAGE * 2, CAGE),
           "north": (CAGE * 3, CAGE)}
## The sheet is wider than a tile, so a face past x16 reads a tile cut from
## further along it: the left sixteen columns or the right sixteen.
CAGE_TILE = {face: 0 if at[0] + CAGE <= 16 else 8 for face, at in CAGE_AT.items()}
CAGE_ART = {face: (at[0] - CAGE_TILE[face], at[1], CAGE, CAGE)
            for face, at in CAGE_AT.items()}
CAGE_TEXTURE = {face: "%s#%d,0" % (CONDUIT_BASE, CAGE_TILE[face])
                for face in CAGE_AT}
SHELL = {face: (0, 0, 8, 8) for face in FACES}

CONDUIT = {
    "0": [Cube((CAGE, CAGE, CAGE), ((16 - CAGE) // 2,) * 3, CAGE_TEXTURE,
               window=CAGE_ART)],
    "1": [Cube((CAGE, CAGE, CAGE), ((16 - CAGE) // 2,) * 3, CAGE_TEXTURE,
               window=CAGE_ART),
          Cube((8, 8, 8), (4, 4, 4), OPEN, window=SHELL)],
}
CONDUIT["default"] = CONDUIT["0"]

## A conduit has no direction in its states, so it has no rotation table.


# --- beds -------------------------------------------------------------------
#
# Two blocks, head and foot, each a mattress on two legs. Bedrock tells the
# halves apart with `head_piece_bit`, which arrives as the shape variant.
#
# **A bed lies along z, with its head to the north**, the way a bed at rest
# faces. Its tiles run foot to head across their own width: on `bed_head_top`
# and `bed_head_side` the pillow is the right half of the picture, and on
# `bed_head_side` the leg is the last three pixels of it. So the top reads its
# tile a quarter turned, and the long sides, east and west, read theirs along
# the bed.
#
# **Two legs a block, not four.** `bed_feet_end` carries a leg at each corner,
# which is one end of the bed seen from outside, and `bed_feet_side` carries one,
# at the foot. Four to a block puts eight under a bed.
#
# The legs are drawn from the bed's own tile too, off the three by three patch
# under the mattress, rather than from planks.
BED_TALL = 6
BED_UP = 3
LEG = 3
# **The leg is drawn at the end of the tile the leg is at.** `bed_feet_side`
# carries it in the first three pixels and `bed_head_side` in the last three,
# because each picture runs foot to head. Both halves read the foot tile's
# corner, so the head's legs came out blank.
#
# **And one long side has to read its picture the other way round.** The two
# faces of a box opposite each other run their windows in opposite directions,
# so the pillow ends up at the head on one and at the foot on the other. The
# west side starts at the far edge and runs back, which is how Bedrock reads a
# picture mirrored.
BED_FACE = (0, 7, 16, BED_TALL)         # the mattress, on the side and the end
BED_BACK = (16, 7, -16, BED_TALL)       # the same, the other way round


## A bed's colour is in the block entity, not in its states, and there is one
## set of tiles per colour: `tools/textures/beds.py` recolours the red
## tiles the pack ships. The family's `entity_add` rule joins the colour to the
## half, so a form is named `<head_piece_bit>-<colour>`.
BED_COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime",
               "pink", "gray", "silver", "cyan", "purple", "blue", "brown",
               "green", "red", "black"]


def bed(part, head, colour):
    """One block of a bed: the mattress, and the two legs at its outer end.

    `head` says which end of the tile the legs' picture is at: 0 for the foot,
    whose legs stand at the south end of the block, and the far end for the
    head, whose legs stand at the north.
    """
    named = "bed_%s_%s_%%s" % (colour, part)
    top = BLOCKS % (named % "top")
    side = BLOCKS % (named % "side")
    end = BLOCKS % (named % "end")
    mattress = Cube((16, BED_TALL, 16), (0, BED_UP, 0), texture={
        "up": top, "down": BLOCKS % "planks_oak",
        ## the bed lies along z, so its ends are the z faces and its long sides
        ## the x ones
        "north": end, "south": end, "east": side, "west": side},
        window={"up": (0, 0, 16, 16, 90), "down": (0, 0, 16, 16, 270),
                "north": BED_FACE, "south": BED_FACE,
                "east": BED_FACE, "west": BED_BACK})
    leg_art = (head, 16 - LEG, LEG, LEG)
    flat = {"up": (0, head, LEG, LEG, 90),
            "down": (16 - LEG, 16 - LEG - head, LEG, LEG, 270)}
    legs = [Cube((LEG, BED_UP, LEG), (x, 0, 16 - LEG - head), side,
                 window=dict({face: leg_art for face in FACES}, **flat))
            for x in (0, 16 - LEG)]
    return [mattress] + legs


BEDS = {"%d-%d" % (half, number): bed(part, head, colour)
        for half, (part, head) in enumerate((("feet", 0), ("head", 16 - LEG)))
        for number, colour in enumerate(BED_COLOURS)}
## a bed with no entity beside it keeps its half and falls back to red, which is
## the colour the pack's own tiles are drawn in
BEDS["0"] = bed("feet", 0, "red")
BEDS["1"] = bed("head", 16 - LEG, "red")
BEDS["default"] = BEDS["0"]

## A dyed bed carries `direction` and a straw bed `minecraft:cardinal_direction`,
## and both turn by Minecraft's own angles for them.
BED_FACING = "direction"
STRAW_BED_FACING = "minecraft:cardinal_direction"


# --- straw beds -------------------------------------------------------------
#
# 26.50's second bed, and the first that is one thing rather than sixteen: the
# whole of it is `textures/blocks/straw_bed.png`, a 64x64 sheet laid out the way
# the dyed bed's is. `straw_bed_foot.geo.json` and `straw_bed_head.geo.json` in
# bedrock-samples give it a mattress filling the block at the foot, and at the
# head a lower half with the pillow raised on the end of it.
#
# **Its UV space is sixteen units across a sixty-four pixel sheet**, so one unit
# of Mojang's UV is four texture pixels and every rectangle below is already
# multiplied by four. A face written there with a negative height is the same
# rectangle measured upward from its own bottom edge; these are the rectangles.
#
# **The frills are left off.** The model hangs ten zero-thickness planes of
# straw off the edges, each leaning by a fraction of a degree. Every one would
# be another cube in a block that is meant to cost two, and a transparent texel
# still takes the depth it stands at, so a fringe of crossing planes would cut
# holes in the mattress it stands on rather than feathering its edge.
#
# **It lies along z with its head to the north**, as the dyed bed does. Each
# face reads the rectangle Mojang's model gives the face of that name, and the
# tops read theirs backwards.
STRAW_SHEET = "textures/blocks/straw_bed"
STRAW_WIDE = 64

## The joints never show: the foot's north face and the head's south face are the
## two halves pressed together, and the head base's north face is under the
## pillow.
## Mojang leaves them out of the model altogether; they are drawn here with the
## straw side, because a cube has six faces whether or not anything sees them.
STRAW_HIDDEN = (16, 41, 16, 4)

## (size, where it sits, the rectangle each face reads)
STRAW_FORMS = {
    ## head_piece_bit 0, the foot: one box filling the block
    "0": [((16, 4, 16), (0, 0, 0),
           {"north": (16, 41, 16, 4), "south": STRAW_HIDDEN,
            "east": (0, 41, 16, 4), "west": (32, 41, 16, 4),
            "up": (32, 41, -16, -16), "down": (32, 25, 16, 16)})],
    ## head_piece_bit 1, the head: a low half, and the pillow on the north end
    "1": [((16, 4, 8), (0, 0, 8),
           {"north": STRAW_HIDDEN, "south": STRAW_HIDDEN,
            "east": (0, 21, 8, 4), "west": (24, 21, 8, 4),
            "up": (24, 21, -16, -8), "down": (24, 13, 16, 8)}),
          ((16, 5, 8), (0, 0, 0),
           {"north": (8, 8, 16, 5), "south": (32, 8, 16, 5),
            "east": (0, 8, 8, 5), "west": (24, 8, 8, 5),
            "up": (24, 8, -16, -8), "down": (24, 0, 16, 8)})],
}


def straw_box(size, at, faces):
    """One box of the straw bed, each face reading its own rectangle."""
    texture, window = {}, {}
    for face in FACES:
        texture[face], window[face] = on_sheet(STRAW_SHEET, faces[face], STRAW_WIDE)
    return Cube(size, at, texture=texture, window=window)


STRAW_BEDS = {half: [straw_box(*box) for box in boxes]
              for half, boxes in STRAW_FORMS.items()}
## a straw bed carries no block entity at all, so unlike the dyed bed there is
## nothing to fall back from; the foot is what an unstated one comes up as
STRAW_BEDS["default"] = STRAW_BEDS["0"]


def main():
    print("writing the furniture")
    write("daylight", DAYLIGHT)
    write("daylight_inverted", DAYLIGHT_INVERTED)
    define(["daylight_detector_inverted"], "daylight_inverted")


    write("lectern", LECTERN)
    write("enchanting_table", ENCHANTING)
    write("conduit", CONDUIT)
    lookup_writer.unturn("conduit")
    write("bed", BEDS)
    ## a lectern and a bed both face somewhere; an enchanting table does not
    turns("lectern", "minecraft:cardinal_direction")
    turns("bed", BED_FACING)
    write("straw_bed", STRAW_BEDS)
    turns("straw_bed", STRAW_BED_FACING)
    define(["straw_bed"], "straw_bed")
    print("now re-run tools/blocks/simplify.py")


if __name__ == "__main__":
    main()
