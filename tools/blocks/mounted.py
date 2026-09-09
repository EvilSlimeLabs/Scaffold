"""Give a block a shape it cannot be read off a terrain tile with.

    python -m tools.blocks.mounted


Several families take more than one form, and the difference between the forms
is the
part that holds them up rather than the part everyone looks at. A bell is the
same bell whether it hangs from a beam between two stone posts, from a beam out
of one wall, from a beam spanning two walls, or straight from the block above;
what changes is what carries it. The same is true of a grindstone's legs and of
a hanging sign's chains, and none of it is in the block's own texture: the shape
has to say it.

This writes those forms out. Each variant is a different list of cubes rather
than the same list moved, so the mountings read as different objects.

A campfire also carries its fire here. `extinguished` is the only thing telling
a lit campfire from a dead one, and the logs alone barely differ, so the lit
form gets two crossed quads of the flame texture. That is also what tells a soul
campfire from an ordinary one, because `@up` resolves to whichever fire the
block declares.

The shelf is here for the other reason a block cannot be read off a terrain
tile: its texture is a sheet with a different picture for each face, and taking
the whole of it paints the front's compartments onto all six. A door is the
narrow version of the same thing: three pixels thick, and every one of its six
faces was reading the whole of the door's picture, so the panel was squeezed
into each edge.

The tripwire hook is here for a third reason: `attached_bit` says whether
anything is tied to it, and the hook hanging loose off its plate is a different
arrangement of the same three pieces from the hook held out level by a wire.

The shelf, the sculk shrieker and string are here for a fourth: a ghost block is
half transparent, and vanilla's own way of drawing them does not survive that. A
shelf's compartments are painted into its front texture, which reads as a shelf
on a solid block and as a plain box on a see-through one, so they are cut here
instead. A shrieker is half a block tall with a hole in the middle of its lid,
and drawn from the terrain tiles as a full cube it is a block of sculk with a
transparent top. String lies flat rather than filling its block, and wears a
tile `tools/textures/string.py` draws for it. A flower pot is hollow, and
one cube of the compost tile is a brown block with nothing pot shaped about it.

The brewing stand, the bell and the heavy core are here for the same reason from
the other end: their tiles hold more than the part any one face wants. A brewing
stand's rod is drawn down the middle of its tile with the arms that hold the
bottles either side of it, the bell is an eight by nine picture in a sixteen by
sixteen file, the heavy core's file holds three eight by eight pictures and an
empty quarter, and every one of a dried ghast's twenty four textures is a ten by
ten picture in a sixteen by sixteen file. A face taking the whole tile wears the
wrong thing or nothing at all.

Both pots are here for a fifth reason as well: what look like their terrain
tiles are sheets. A face left to work its own window out reads the whole of one
as if it were a single picture, which puts the decorated pot's shoulder on the
unwrap of its neck and takes the flower pot's wall from the rim. `on_sheet`
turns a region of a sheet into the reference and the window a face needs.

The families here own their entries in `lookups/block_shapes.json` and
`lookups/block_uv.json` outright: re-running this replaces them. Nothing here is
needed at run time. Re-run `tools/blocks/simplify.py` afterwards, or the
simplified forms still outline the old shapes.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks.geometry import Cube, FACES, on_sheet, spun
from tools.blocks.tables import define, write


# --- hanging signs ----------------------------------------------------------
#
# A hanging sign's texture is an entity sized sheet, 64x32, not a terrain tile,
# and it carries three things stacked up the left of it: the bar it hangs from
# at the top, the chains under that, and the board itself from y12 down. Only
# the top left 16x16 of a texture becomes a tile, so each part names the window
# it needs and gets a tile of its own.
BOARD = "@north#0,12"
CHAIN = "@north#0,6"
BAR = "@north#4,0"

## the board, hanging under whatever holds it. 14 wide and 10 deep on the sheet,
## with its edge strip to the left of it and its top edge above.
board = Cube((14, 10, 2), (1, 0, 7), BOARD, window={
    "north": (2, 2, 14, 10), "south": (2, 2, 14, 10),
    "east": (0, 2, 2, 10), "west": (0, 2, 2, 10),
    "up": (2, 0, 14, 2), "down": (2, 0, 14, 2)})

## two chains, reading the chain art rather than the plank art
CHAIN_ART = {face: (0, 0, 2, 6) for face in ("north", "south", "east", "west")}
CHAIN_ART.update({"up": (0, 0, 2, 2), "down": (0, 0, 2, 2)})
chains = [Cube((2, 6, 2), (3, 10, 7), CHAIN, window=CHAIN_ART),
          Cube((2, 6, 2), (11, 10, 7), CHAIN, window=CHAIN_ART)]

## the same two, shortened to make room for a bar above them
STUB_ART = {face: (0, 4, 2, 2) for face in FACES}
stubs = [Cube((2, 4, 2), (3, 10, 7), BAR, window=STUB_ART),
         Cube((2, 4, 2), (11, 10, 7), BAR, window=STUB_ART)]

## the bar a sign is attached to when it hangs straight off the block above
bar = Cube((14, 2, 2), (1, 14, 7), BAR, window={
    "north": (0, 4, 14, 2), "south": (0, 4, 14, 2),
    "east": (0, 4, 2, 2), "west": (0, 4, 2, 2),
    "up": (0, 0, 14, 2), "down": (0, 0, 14, 2)})

## the same bar, run out to the edges of the block so that it reaches the wall
## it is fixed to. The form under a block has nothing to reach and stays 14.
wall_bar = Cube((16, 2, 2), (0, 14, 7), BAR, window={
    "north": (0, 4, 14, 2), "south": (0, 4, 14, 2),
    "east": (0, 4, 2, 2), "west": (0, 4, 2, 2),
    "up": (0, 0, 14, 2), "down": (0, 0, 14, 2)})

## Named by attached_bit and hanging, joined the way core.py joins shape states.
## Hanging from a block: chains when it swings free, a bar when it is attached
## to the block. Not hanging: mounted on a wall, where the bar itself reaches
## the wall, the way a bell's beam spans two of them. A second piece running
## back into the wall reads as a post nobody asked for.
HANGING_SIGNS = {
    "0-1": [board] + chains,
    "1-1": [board] + stubs + [bar],
    "0-0": [board] + stubs + [wall_bar],
    "1-0": [board] + stubs + [wall_bar],
    "default": [board] + chains,
}


# --- bells ------------------------------------------------------------------
#
# The bell itself never changes. Everything above it does. A bell declares four
# different things on its six faces, which is how one entry serves every
# mounting without naming a texture: the bell on north and south, its crown on
# up, its rim on down, the beam's planks on east and the posts' stone on west.
BELL_SIDE = "@north"        # bell_side
BELL_TOP = "@up"            # bell_top
BELL_RIM = "@down"          # bell_bottom
BELL_WOOD = "@east"         # dark oak planks, whatever holds the bell up
BELL_STONE = "@west"        # the posts a standing bell hangs between

## `bell_side` draws the whole bell down one column of its tile: the narrow
## body, six across and seven down, over the flared lip, eight across and two
## down. `bell_top` and `bell_bottom` are the eight by eight faces at each end.
## Faces left to work their own window out read the middle of the tile, which
## for an eight by eight picture in a sixteen by sixteen file is mostly nothing,
## and the bell comes out as a flat plate.
BODY_WIDE, BODY_TALL = 6, 7
LIP_WIDE, LIP_TALL = 8, 2
BELL_FLOOR = 4              # so the bell's crown meets the beam at 13


def bell_piece(size, at, side_window, cap_window):
    """One of the bell's two parts, reading its own rows of the side tile."""
    wide, tall, _deep = size
    return Cube(size, at, texture={
        "north": BELL_SIDE, "south": BELL_SIDE,
        "east": BELL_SIDE, "west": BELL_SIDE,
        "up": BELL_TOP, "down": BELL_RIM}, window={
        "north": side_window, "south": side_window,
        "east": side_window, "west": side_window,
        "up": cap_window, "down": cap_window})


bell_lip = bell_piece(
    (LIP_WIDE, LIP_TALL, LIP_WIDE),
    ((16 - LIP_WIDE) // 2, BELL_FLOOR, (16 - LIP_WIDE) // 2),
    (0, BODY_TALL, LIP_WIDE, LIP_TALL), (0, 0, LIP_WIDE, LIP_WIDE))
bell_body = bell_piece(
    (BODY_WIDE, BODY_TALL, BODY_WIDE),
    ((16 - BODY_WIDE) // 2, BELL_FLOOR + LIP_TALL, (16 - BODY_WIDE) // 2),
    (1, 0, BODY_WIDE, BODY_TALL), (1, 1, BODY_WIDE, BODY_WIDE))

## and what carries it. The short bar under a ceiling is the same dark oak as
## every beam; it wore the bell's own crown texture and came out gold.
bell_stub = Cube((2, 3, 2), (7, 13, 7), BELL_WOOD)
bell_beam = Cube((2, 2, 16), (7, 13, 0), BELL_WOOD)
bell_arm = Cube((2, 2, 8), (7, 13, 0), BELL_WOOD)
bell_posts = [Cube((2, 13, 2), (7, 0, 1), BELL_STONE),
              Cube((2, 13, 2), (7, 0, 13), BELL_STONE)]

BELL = [bell_lip, bell_body]

BELLS = {
    ## on the floor: a beam across two stone posts
    "standing": BELL + [bell_beam] + bell_posts,
    ## between two walls: the same beam, carried by them instead
    "multiple": BELL + [bell_beam],
    ## on one wall: half a beam, out of the wall behind it
    "side": BELL + [bell_arm],
    ## straight off the block above: no beam at all, just the mount
    "hanging": BELL + [bell_stub],
    "default": BELL + [bell_beam] + bell_posts,
}


# --- grindstones ------------------------------------------------------------
#
# The wheel and its two pivots are the block. The legs are what changes: down to
# the floor, up to the block above, or back into the wall it is fixed to.
#
# **The wheel is the size its own textures were drawn for.** `grindstone_side`
# is twelve across and twelve down and `grindstone_round` is eight across and
# twelve down, which is a wheel twelve wide, twelve tall and eight deep seen
# face on and then edge on. It was drawn twelve by eight by four, a third of the
# stone that should be there.
#
# And it names its faces. `blocks.json` puts `grindstone_pivot` on north and
# the leg's oak on down, because those are slots the engine picks from for its
# own model rather than the six sides of a cube, so a wheel left to the block's
# own faces has a pivot painted on its back and a log on its underside.
# **The wheel turns with the block, not across it.** Its round faces are the two
# you look at, and they belong on the x sides with the axle running that way, so
# the wheel is eight across, twelve tall and twelve deep. Drawn the other way
# round it is the same stone seen edge on from the front.
LEG = "@down"               # log_big_oak
PIVOT = "@north"            # grindstone_pivot
STONE_FACE = "@east"        # grindstone_side, the wheel face on
STONE_EDGE = "@up"          # grindstone_round, the same wheel edge on
WHEEL_WIDE, WHEEL_TALL, WHEEL_DEEP = 8, 12, 12
WHEEL_AT = (16 - WHEEL_WIDE) // 2
WHEEL_Z = (16 - WHEEL_DEEP) // 2         # the pivots stand just outside it
PIVOT_TALL = 4
## the pivot's picture is ten across and six down in the corner of its tile, and
## a face left to its own window read past the bottom of that and came out half
## drawn
## six by six of the corner, at its own scale: a ten by six window on a two
## by four face squashes the picture
PIVOT_ART = (0, 0, 6, 6)
LEG_ROOM = 16 - WHEEL_TALL              # what the block has left for the legs


def grindstone(floor, legs):
    """The wheel at a height, its two pivots at the axle, and its legs.

    The wheel takes three quarters of the block, so where it sits is what the
    mounting decides: on the floor it stands on legs and everything is that much
    higher, under a block it hangs from them, and against a wall it is in the
    middle with the legs running back into the wall.
    """
    axle = floor + WHEEL_TALL // 2
    wheel = Cube((WHEEL_WIDE, WHEEL_TALL, WHEEL_DEEP),
                 (WHEEL_AT, floor, WHEEL_Z),
                 texture={"east": STONE_FACE, "west": STONE_FACE,
                          "north": STONE_EDGE, "south": STONE_EDGE,
                          "up": STONE_EDGE, "down": STONE_EDGE},
                 window={"east": (0, 0, WHEEL_DEEP, WHEEL_TALL),
                         "west": (0, 0, WHEEL_DEEP, WHEEL_TALL),
                         "north": (0, 0, WHEEL_WIDE, WHEEL_TALL),
                         "south": (0, 0, WHEEL_WIDE, WHEEL_TALL),
                         "up": (0, 0, WHEEL_WIDE, WHEEL_DEEP),
                         "down": (0, 0, WHEEL_WIDE, WHEEL_DEEP)})
    ## the stand runs across the block the way it always did; only the wheel
    ## between its two pivots turned
    pivots = [Cube((2, PIVOT_TALL, 4), (at, axle - PIVOT_TALL // 2, 6), PIVOT,
                   window={face: PIVOT_ART for face in FACES})
              for at in (WHEEL_AT - 2, WHEEL_AT + WHEEL_WIDE)]
    return legs(floor, axle) + pivots + [wheel]


LEG_AT = (2, 12)


def legs_down(floor, axle):
    ## up to the pivot, not up to the wheel: a post that stopped at the stone
    ## left a gap under the square it is meant to carry
    return [Cube((2, axle - PIVOT_TALL // 2, 2), (at, 0, 7), LEG)
            for at in LEG_AT]


def legs_up(floor, axle):
    top = axle + PIVOT_TALL // 2
    return [Cube((2, 16 - top, 2), (at, top, 7), LEG) for at in LEG_AT]


def legs_back(_floor, axle, sides=(0,)):
    return [Cube((2, 2, 6), (at, axle - 1, z), LEG)
            for z in sides for at in LEG_AT]


GRINDSTONES = {
    ## on the floor, so the wheel is up against the block above it
    "standing": grindstone(LEG_ROOM, legs_down),
    ## under a block, so it hangs and the wheel is down against the floor
    "hanging": grindstone(0, legs_up),
    ## on a wall, so the wheel sits in the middle and the legs run into it
    "side": grindstone(LEG_ROOM // 2, legs_back),
    "multiple": grindstone(LEG_ROOM // 2,
                           lambda floor, axle: legs_back(floor, axle, (0, 10))),
    "default": grindstone(LEG_ROOM, legs_down),
}


# --- campfires --------------------------------------------------------------
#
# Four logs, and the fire above them when it is lit. The fire is two quads
# crossed through the middle of the block, the way vanilla draws every flame,
# and it reads `@up`, which is campfire_fire on a campfire and soul_campfire_fire
# on a soul campfire.
#
# The log tile is three pictures stacked, not one: the bark across the top four
# rows, the cut end of a log beside it in the next four, and the ash the fire
# sits in across the bottom half. A face taking the whole tile wears all three.
#
# The ash is a plate one pixel deep across the floor of the block, and the logs
# stand on it rather than above it: the pair underneath is four across at x1 and
# x11 running the depth of the block, and the pair over them is four deep at z1
# and z11 running the width, so the ash shows through the square between them.
LOG_LIT = "@north"
LOG_OUT = "@down"
FLAME = "@up"

FLAME_ART = {"north": (0, 0, 16, 16), "south": (0, 0, 16, 16),
             "east": (0, 0, 1, 16), "west": (0, 0, 1, 16),
             "up": (0, 0, 16, 1), "down": (0, 0, 16, 1)}

LOG_BARK = (0, 0, 16, 4)        # the length of a log
LOG_END = (0, 4, 4, 4)          # its cut face
ASH = (0, 8, 16, 8)             # what the logs sit in
LOG_THICK = 4
ASH_DEEP = 1


def log(size, at, texture):
    """One log, its ends reading the cut face and its length the bark.

    A log lying along z has a top four across and sixteen deep, and the bark is
    drawn the other way round; there is no turning a window, so it takes the
    bark as it is. That face is under the pair above it or on the floor.
    """
    wide, _tall, deep = size
    along_x = wide > deep
    return Cube(size, at, texture, window={
        "north": LOG_BARK if along_x else LOG_END,
        "south": LOG_BARK if along_x else LOG_END,
        "east": LOG_END if along_x else LOG_BARK,
        "west": LOG_END if along_x else LOG_BARK,
        "up": LOG_BARK, "down": LOG_BARK})


def logs(texture):
    """The ash, the pair of logs in it, and the pair across those."""
    return [
        Cube((16, ASH_DEEP, 16), (0, 0, 0), texture, window={
            "up": ASH, "down": ASH,
            "north": (0, 15, 16, ASH_DEEP), "south": (0, 15, 16, ASH_DEEP),
            "east": (0, 15, 16, ASH_DEEP), "west": (0, 15, 16, ASH_DEEP)}),
        log((LOG_THICK, LOG_THICK, 16), (1, 0, 0), texture),
        log((LOG_THICK, LOG_THICK, 16), (16 - 1 - LOG_THICK, 0, 0), texture),
        log((16, LOG_THICK, LOG_THICK), (0, LOG_THICK, 1), texture),
        log((16, LOG_THICK, LOG_THICK), (0, LOG_THICK, 16 - 1 - LOG_THICK),
            texture),
    ]


flames = [Cube((12, 10, 1), (2, 6, 7.5), FLAME, window=FLAME_ART,
               rotation=(0, 45, 0)),
          Cube((12, 10, 1), (2, 6, 7.5), FLAME, window=FLAME_ART,
               rotation=(0, -45, 0))]

CAMPFIRES = {
    "0": logs(LOG_LIT) + flames,        # burning
    "1": logs(LOG_OUT),                 # out
    "default": logs(LOG_LIT) + flames,
}


# --- doors ------------------------------------------------------------------
#
# A door is a panel three pixels thick, and every one of its six faces was
# reading the whole of the door's picture. On the two big faces that is right.
# On the four thin ones it squeezes the whole door into three pixels, which is
# what put a row of panels down each edge and across the top. An edge is the
# frame down the side of the tile, three across and the height of the door.
#
# **The panel sits on the side the door faces**, the way it does in the game:
# placed from the south, a door faces south and its panel is at z13. It was at
# z0, so every door was drawn against the far side of its own block.
#
# **And it turns about the middle of the block**, like everything else. The
# pivot was on the panel's own plane, so a door turned a quarter of the way
# round swung out of its block entirely.
DOOR_THICK = 3
DOOR_LOWER = "@down"            # door_lower, the half nearest the floor
DOOR_UPPER = "@north"           # door_upper, declared on `side`
DOOR_WHOLE = (0, 0, 16, 16)
DOOR_EDGE = (0, 0, DOOR_THICK, 16)          # the frame down one side
DOOR_TOP = (0, 0, 16, DOOR_THICK)           # and across the top of it
DOOR_FOOT = (0, 16 - DOOR_THICK, 16, DOOR_THICK)


## The whole family stands a quarter turn from where it started, and the two
## states turn opposite ways: open wanted a quarter anticlockwise and shut a
## quarter clockwise. One rotation table cannot hold both, so the turn is in the
## cubes. Shut also wanted mirroring, which is not a turn at all: a door panel
## is the same box either way round and only its picture has a side to it, so
## the mirror is a negative window on the two faces that carry the picture.
def door_half(at, texture, along_x, mirror=False):
    """One block of a door, its edges reading the frame and not the panel."""
    ## a window that starts at the far edge and runs back is how Bedrock reads
    ## a picture the other way round
    ## only the face on the outside of the panel: the two faces of a box read
    ## their windows in opposite directions, so mirroring both puts the picture
    ## right on the inside and wrong on the outside again
    panel = (16, 0, -16, 16) if mirror else DOOR_WHOLE
    if along_x:
        size = (16, 16, DOOR_THICK)
        window = {"north": panel, "south": DOOR_WHOLE,
                  "east": DOOR_EDGE, "west": DOOR_EDGE,
                  ## a top face sixteen across and three deep cannot read a
                  ## frame three across and sixteen down without turning it, so
                  ## it takes the top of the door's own picture instead
                  "up": DOOR_TOP, "down": DOOR_FOOT}
    else:
        size = (DOOR_THICK, 16, 16)
        window = {"east": panel, "west": DOOR_WHOLE,
                  "north": DOOR_EDGE, "south": DOOR_EDGE,
                  "up": DOOR_EDGE, "down": DOOR_EDGE}
    return Cube(size, at, texture, window=window)


def door(x, z, along_x, mirror=False):
    """Both halves of a door. The lower block draws them; the upper draws
    nothing, which is what the `top` variant is for."""
    return [door_half((x, 0, z), DOOR_LOWER, along_x, mirror),
            door_half((x, 16, z), DOOR_UPPER, along_x, mirror)]


DOORS = {
    ## shut: a quarter turn clockwise from the side it used to sit on, and the
    ## picture mirrored
    "default": door(16 - DOOR_THICK, 0, False, mirror=True),
    ## open, folded back against the wall on whichever side the hinge is, a
    ## quarter turn anticlockwise from the sides those used to sit on
    "open": door(0, 0, True, mirror=True),
    "open_hinged": door(0, 16 - DOOR_THICK, True, mirror=True),
    ## the upper block of a door draws nothing at all: a cube of nothing rather
    ## than no cube, because the tables are read by the variant existing
    "top": [Cube((0.016, 0.016, 0.016), (0, 0, 0))],
}


# --- shelves ----------------------------------------------------------------
#
# A shelf's texture is a 32x32 sheet. The top left quarter is the front, with
# the three compartments and their shading painted into it; the top right is
# plain planks, which is every face that looks out of the block; the bottom half
# is the shaded interior, which is what the faces looking into the compartments
# read.
#
# **The measurements are Mojang's own.** `shapes/shelf_facing_east.json` in
# bedrock-samples gives the block three boxes, and with the wall at x0 they are a
# bottom board 0 to 4 tall and 5 deep, a back 4 to 16 tall and 3 deep, and a top
# board 12 to 16 tall reaching from the back out to 5. So the case is five deep,
# the two boards are four thick, and the opening between them is eight tall and
# two deep. That is a voxel shape rather than a model, so it says how big the
# pieces are and not how they are painted.
#
# It matches the front picture row for row: a rail across rows 0 to 3, the
# compartments through rows 4 to 11, a rail across rows 12 to 15, and a lit pixel
# parting the compartments at x5 and at x10. Those dividers are painted on: the
# voxel shape has nothing standing in the opening and neither does this.
#
# It hangs on the wall behind it, so at no rotation it runs z 0 to 5, the same
# way a wall sign sits at z 0 to 2.
SHELF_FRONT = "@north#0,0"      # the compartments, painted
SHELF_OUTER = "@north#16,0"     # planks, for every face that looks outward
SHELF_INNER = "@north#0,16"     # the shaded interior, rows 8 to 15 of the tile

SHELF_DEEP = 5
SHELF_BACK_DEEP = 3
BOARD = 4                       # how thick the two boards are
OPENING = (BOARD, 16 - BOARD)   # the rows the compartments run between
INSIDE = 8                      # the interior's first row within its own tile


def shelf_piece(size, at, front, inner=()):
    """One piece of the case, reading its own slice of each part of the sheet.

    `front` is where the piece sits on the front picture, in texture pixels.
    Faces named in `inner` look into a compartment and read the shaded half of
    the sheet instead of the planks; everything else looks out of the block.
    """
    wide, tall, deep = size
    across, _, over = at
    paint = {}
    window = {}
    for face in FACES:
        if face in inner:
            paint[face] = SHELF_INNER
        elif face == "south":
            paint[face] = SHELF_FRONT
        else:
            paint[face] = SHELF_OUTER
        if face in ("up", "down"):
            window[face] = (across, over, wide, deep)
        elif face in ("north", "south"):
            window[face] = front
        else:
            window[face] = (over, front[1], deep, tall)
    ## an inner face reads the same shape of window out of the shaded half,
    ## which is the bottom eight rows of that tile
    for face in inner:
        wide_, tall_ = window[face][2], window[face][3]
        window[face] = (0, INSIDE + (0 if face != "up" else 8 - tall_),
                        wide_, tall_)
    return Cube(size, at, texture=paint, window=window)


def shelf():
    """The floor, the ceiling, the back and the two uprights."""
    low, high = OPENING
    open_tall = high - low
    made = [
        ## the two boards, the full depth of the case. The compartment side of
        ## each is shaded: the floor lit along its front lip, the ceiling not
        shelf_piece((16, BOARD, SHELF_DEEP), (0, 0, 0),
                    (0, high, 16, BOARD), inner=("up",)),
        shelf_piece((16, BOARD, SHELF_DEEP), (0, high, 0),
                    (0, 0, 16, BOARD), inner=("down",)),
        ## the back, between them and three deep, so the opening it closes is
        ## two deep
        shelf_piece((16, open_tall, SHELF_BACK_DEEP), (0, low, 0),
                    (0, low, 16, open_tall)),
    ]
    ## Nothing stands in the opening. Seen from the end a shelf is a C -- a
    ## ceiling and a floor out of a back, open at the front -- and the lit pixels
    ## the front picture draws at x0, x5, x10 and x15 are painted on, not pieces.
    return made


SHELVES = {"default": shelf()}


# --- sculk shriekers --------------------------------------------------------
#
# A sculk shrieker is half a block tall, not a full one, and the hole in the
# middle of its top is a hole in the texture: `sculk_shrieker_top` is four
# corner blobs with nothing between them, and the game draws
# `sculk_shrieker_inner_top` under it so there is something to see down the
# throat. Drawn as a full cube from the terrain tiles, a shrieker is a block of
# sculk with a transparent lid.
SHRIEKER_TALL = 8
SHRIEKER_INNER = "textures/blocks/sculk_shrieker_inner_top"

SHRIEKERS = {"default": [
    Cube((16, SHRIEKER_TALL, 16), (0, 0, 0)),
    ## the throat, a hair under the lid so the two do not fight over the plane
    Cube((16, 1, 16), (0, SHRIEKER_TALL - 1.5, 0), texture=SHRIEKER_INNER,
         window={face: (0, 0, 16, 16) for face in FACES}),
]}


# --- string -----------------------------------------------------------------
#
# String lies flat on the floor of its block, a pixel or so up, and is one quad
# rather than the cube the tables drew it as. `tools/textures/string.py`
# writes the tile it wears, because vanilla's is a scatter of faint single
# pixels that cannot be seen on a half-transparent plate.
STRING = "textures/blocks/scaffold_string"
STRING_UP = 1.5

STRINGS = {"default": [
    Cube((16, 0.5, 16), (0, STRING_UP, 0), texture=STRING,
         window={face: (0, 0, 16, 16) for face in FACES}),
]}


# --- tripwire hooks ---------------------------------------------------------
#
# A tripwire hook is a plank plate against the wall with a metal hook on it, and
# `attached_bit` says which of two things the hook is doing: hanging straight
# down off the plate with nothing on it, or held out horizontally by the wire it
# is tied to. That is a different arrangement of the same three pieces rather
# than one shape turned, so each gets its own list.
#
# It hangs on the wall behind it, so the plate sits at z 0 to 2, the same way a
# wall sign does, and the hook reaches out towards +z.
#
# `blocks.json` gives the block three textures and the pieces take two of them:
# `@down` is trip_wire_base, which is oak planks, and `@north` is
# trip_wire_source, which holds the hook drawn face on. That tile is the hook at
# rest: the ring across x5 to x11 at the top, and the shaft hanging below it
# down the middle, which is where the windows below read from.
#
# The plate is four across, two deep and eight tall, flat on the wall. The shaft
# is the two by seven strip below the ring on the tile, at its own scale, and
# runs out of the plate at an angle. The hook is the ring, six by six on the
# tile, drawn four across so that it reads the width of the plate, and it hangs
# square across the end of the shaft.
#
# Three arrangements, from `attached_bit` and `powered_bit`:
#
#   nothing on it   the shaft points up out of the wall at 45 degrees and the
#                   hook hangs off the low half of its end
#   tied to a wire  the wire pulls the shaft down to near the horizontal and the
#                   hook comes with it
#   engaged         the shaft drops to 45 degrees the other way and the hook
#                   sits square on the high half of its end, level with the
#                   ground
HOOK = "@north"
HOOK_RING = (5, 3, 6, 6)        # the ring, face on
HOOK_SHAFT = (7, 9, 2, 7)       # the shaft below it, at its own scale
HOOK_END = (7, 9, 2, 2)         # a square of the shaft, for its small faces

PLATE_WIDE, PLATE_TALL, PLATE_DEEP = 4, 8, 2
SHAFT_THICK, SHAFT_LONG = 2, 7
RING_WIDE, RING_THICK = 4, 0.5
## how far up the plate the shaft leaves it, and the three angles a world showed
SHAFT_AT = 8
LOOSE, TIED, ENGAGED = 45.0, -10.0, -45.0
## the wire pulls the hook up off the shaft it hangs on
TIED_RING = TIED + 100.0
## and the shaft starts a pixel inside the plate rather than off its face
SHAFT_IN = 1
## the wire carries the ring higher than the shaft alone would, and further out
## along the shaft than the shaft's own end
RING_LIFT = 2
RING_OUT = SHAFT_IN + 1

plate = Cube((PLATE_WIDE, PLATE_TALL, PLATE_DEEP),
             ((16 - PLATE_WIDE) // 2, (16 - PLATE_TALL) // 2, 0),
             texture="@down")


def leaning(angle, along, up):
    """Where a point `along` the shaft and `up` from its middle line ends up.

    The shaft leaves the plate at `SHAFT_AT`, and Bedrock's angles run the other
    way round from the usual ones, so a positive angle lifts the far end.
    """
    lean = math.radians(angle)
    out = (math.cos(lean), math.sin(lean))          # along the shaft
    over = (-math.sin(lean), math.cos(lean))        # square across it
    return (8,
            SHAFT_AT + along * out[1] + up * over[1],
            PLATE_DEEP - SHAFT_IN + along * out[0] + up * over[0])


def hook(angle, high, ring_angle=None, ring_out=0, ring_lift=0):
    """The shaft at an angle, and the ring across the end of it.

    `high` puts the ring on the top two pixels of the shaft's end rather than
    the bottom two, which is what tells an engaged hook from a loose one.
    `ring_angle` is the ring's own lean: it goes with the shaft when the wire is
    pulling on it, and sits square to the ground once the hook is engaged.
    """
    ring_angle = angle if ring_angle is None else ring_angle
    middle = leaning(angle, SHAFT_LONG / 2.0, 0)
    shaft = Cube((SHAFT_THICK, SHAFT_THICK, SHAFT_LONG),
                 (middle[0] - SHAFT_THICK / 2.0,
                  middle[1] - SHAFT_THICK / 2.0,
                  middle[2] - SHAFT_LONG / 2.0),
                 texture=HOOK, rotation=(angle, 0, 0), window={
                     "north": HOOK_END, "south": HOOK_END,
                     "east": HOOK_SHAFT, "west": HOOK_SHAFT,
                     "up": HOOK_END, "down": HOOK_END})
    ## the ring hangs from the end of the shaft, off one half of its face, and
    ## reaches back across it: its own middle is that much further down again
    edge = 0.5 if high else -0.5
    at = leaning(angle, SHAFT_LONG + ring_out, edge - RING_WIDE / 2.0)
    at = (at[0], at[1] + ring_lift, at[2])
    ring = Cube((RING_WIDE, RING_WIDE, RING_THICK),
                (at[0] - RING_WIDE / 2.0, at[1] - RING_WIDE / 2.0,
                 at[2] - RING_THICK / 2.0),
                texture=HOOK, rotation=(ring_angle, 0, 0), window={
                    "north": HOOK_RING, "south": HOOK_RING,
                    "east": (5, 3, 6, 6), "west": (5, 3, 6, 6),
                    "up": (5, 3, 6, 6), "down": (5, 3, 6, 6)})
    return [plate, shaft, ring]


TRIPWIRE_HOOKS = {
    ## attached_bit and powered_bit, joined the way core.py joins shape states
    "0-0": hook(LOOSE, high=False),
    ## the wire holds the ring off the high half of the shaft, and further out
    ## along it than the shaft itself reaches
    "1-0": hook(TIED, high=True, ring_angle=TIED_RING, ring_out=RING_OUT,
                ring_lift=RING_LIFT),
    "0-1": hook(ENGAGED, high=True, ring_angle=0.0),
    "1-1": hook(ENGAGED, high=True, ring_angle=0.0),
}
TRIPWIRE_HOOKS["default"] = TRIPWIRE_HOOKS["0-0"]


# --- cauldrons --------------------------------------------------------------
#
# A pot with a floor and four walls, and whatever it is holding lying flat
# inside it. Drawn as a near cube, which is what one entry gives it, a cauldron
# is a block of iron with nothing to say what is in it.
#
# `cauldron_liquid` says water, lava or powder snow, and `fill_level` how much,
# so the two joined name the form: `water-3`, `powder_snow-6`. Dyed water is
# `water` with a whole RGB in the block entity rather than a liquid of its own,
# so `core.ENTITY_TINTS` reads that colour, the form becomes `dyed`, and its
# liquid asks for a tint. Scaffold builds the pack, so the tile is multiplied
# by the colour on its way into the atlas and every dye in a structure lands
# there as a tile of its own.
POT_WALL = 2
POT_FLOOR = 3
## `cauldron_water` is grey, because the game tints it with the water
## colour of wherever the cauldron is. Untinted it is white.
WATER_BLUE = "~3f76e4"
LIQUID = {"water": "textures/blocks/cauldron_water" + WATER_BLUE,
          "lava": "textures/blocks/cauldron_lava",
          "powder_snow": "textures/blocks/powder_snow",
          ## the same water, asking for the block's own colour. `~tint` is put
          ## aside for the colour the block entity carries, and a cauldron with
          ## no colour reads the plain tile.
          "dyed": "textures/blocks/cauldron_water~tint"}
## how high each fill level stands, in pixels off the floor of the block
CAULDRON_FILL = {level: POT_FLOOR + 2 * level for level in range(1, 7)}

INSIDE = 16 - 2 * POT_WALL
cauldron_pot = [
    Cube((16, POT_FLOOR, 16), (0, 0, 0)),
    Cube((POT_WALL, 16 - POT_FLOOR, 16), (0, POT_FLOOR, 0)),
    Cube((POT_WALL, 16 - POT_FLOOR, 16), (16 - POT_WALL, POT_FLOOR, 0)),
    Cube((INSIDE, 16 - POT_FLOOR, POT_WALL), (POT_WALL, POT_FLOOR, 0)),
    Cube((INSIDE, 16 - POT_FLOOR, POT_WALL),
         (POT_WALL, POT_FLOOR, 16 - POT_WALL)),
]


def cauldron(liquid, level):
    """The pot, and a surface of whatever it holds at that fill level."""
    if liquid is None or level not in CAULDRON_FILL:
        return list(cauldron_pot)
    return cauldron_pot + [
        Cube((INSIDE, 0.2, INSIDE),
             (POT_WALL, CAULDRON_FILL[level], POT_WALL), LIQUID[liquid],
             window={face: (0, 0, INSIDE, INSIDE) for face in FACES})]


CAULDRONS = {"%s-%d" % (liquid, level): cauldron(liquid, level)
             for liquid in LIQUID for level in range(7)}
CAULDRONS["default"] = cauldron(None, 0)


# --- dried ghasts -----------------------------------------------------------
#
# All twenty four of its textures are ten by ten pictures in sixteen by sixteen
# files, one set per `rehydration_level`. The block was a fourteen by fourteen
# cube whose faces worked their own windows out from where it sat, so every one
# of them read x1 to x15 of a picture that stops at x10 and the ghast came out
# as a handful of slivers rather than a body.
#
# It is that ten by ten picture's own cube, standing on the floor of the block
# with six tentacles lying flat on the ground around it: two out of each of its
# three blank sides, and none out of the face. Each is three long, two across
# and one deep, and they sit 2 pixels in from the corners of the body.
#
# The tentacles keep the block's own faces, so they follow the rehydration level
# with the rest of it.
GHAST_WIDE = 10
GHAST_ART = (0, 0, GHAST_WIDE, GHAST_WIDE)
GHAST_AT = (16 - GHAST_WIDE) // 2
TENTACLE_LONG = 3
TENTACLE_WIDE = 2
TENTACLE_TALL = 1
## how far along a side each of its two tentacles starts, from the near corner
## of the body
TENTACLE_IN = 2
## a patch of the underside, which is the pale the tentacles are
TENTACLE_ART = (4, 4)


def tentacle(at, along_x):
    """One tentacle, lying flat on the ground out of one side of the body.

    Every face reads a patch of the block's underside the size of that face, so
    the pale runs at the same pixel scale as the rest of the block.
    """
    size = ((TENTACLE_LONG, TENTACLE_TALL, TENTACLE_WIDE) if along_x
            else (TENTACLE_WIDE, TENTACLE_TALL, TENTACLE_LONG))
    wide, tall, deep = size
    across, down = TENTACLE_ART
    return Cube(size, at, "@down", window={
        "up": (across, down, wide, deep), "down": (across, down, wide, deep),
        "north": (across, down, wide, tall),
        "south": (across, down, wide, tall),
        "east": (across, down, deep, tall),
        "west": (across, down, deep, tall)})


def dried_ghast():
    far = GHAST_AT + GHAST_WIDE
    ## the two along a side, a pixel in from each corner of the body
    spread = (GHAST_AT + TENTACLE_IN,
              far - TENTACLE_IN - TENTACLE_WIDE)
    tentacles = []
    for near in spread:
        ## out of the west side and the east side
        tentacles.append(tentacle((GHAST_AT - TENTACLE_LONG, 0, near), True))
        tentacles.append(tentacle((far, 0, near), True))
        ## and out of the back, which is north; the face is south and has none
        tentacles.append(tentacle((near, 0, GHAST_AT - TENTACLE_LONG), False))
    body = Cube((GHAST_WIDE, GHAST_WIDE, GHAST_WIDE),
                (GHAST_AT, 0, GHAST_AT),
                window={face: GHAST_ART for face in FACES})
    return [body] + tentacles


DRIED_GHASTS = {"default": dried_ghast()}


# --- heavy cores ------------------------------------------------------------
#
# `heavy_core.png` is a 16x16 file holding three eight by eight pictures rather
# than one tile: the top with its rings at (0,0), the bottom beside it at (8,0),
# and the side under them at (0,8), which every one of the four walls wears. The
# block is the eight by eight by eight cube those pictures were drawn for.
#
# Faces left to work their own window out from where the cube sits read the
# middle of the file, which straddles all three pictures and the empty quarter
# under the bottom, so the core comes out as mismatched plates.
CORE_SIDE = 8
CORE_FACES = {"up": (0, 0), "down": (CORE_SIDE, 0)}

heavy_core = Cube(
    (CORE_SIDE, CORE_SIDE, CORE_SIDE),
    ((16 - CORE_SIDE) // 2, 0, (16 - CORE_SIDE) // 2),
    texture="@up",
    window={face: (CORE_FACES.get(face, (0, CORE_SIDE))
                   + (CORE_SIDE, CORE_SIDE))
            for face in FACES})

HEAVY_CORES = {"default": [heavy_core]}


# --- brewing stands ---------------------------------------------------------
#
# A brewing stand is a rod standing in a channel between three stone plates, not
# a rod standing on a slab. Drawn as one 14 by 14 plate it is a paving stone with
# a pole through it, and the pole sat on top of that plate rather than on the
# floor, so it stood two pixels proud of the block.
#
# `brewing_stand` draws the rod down the middle of its tile with the arms that
# hold the bottles either side of it, so a face taking the whole tile wears the
# arms as well. The rod names the two pixel column it wants.
#
# **The plates are placed from the sockets on the base tile.** Bedrock ships no
# model for this block and `brewing_stand_base` is opaque across the whole tile,
# so the only thing in the pack that says where one plate ends and the next
# begins is the three bottle sockets drawn on it, at (3.5, 3.5), (3.5, 11.5) and
# (12, 7.5). Each plate is the part of the tile its socket sits in the middle of.
BREW_ROD = "@up"            # brewing_stand
BREW_BASE = "@down"         # brewing_stand_base
ROD_WIDE, ROD_TALL = 2, 13
PLATE_WIDE, PLATE_TALL = 6, 2
## from the top of a plate up to two pixels above the rod, and out from the
## middle of the block as far as the bottle it holds
ARM_TALL = ROD_TALL + 2 - PLATE_TALL
## The arm reads four columns of the tile and the outermost of them is the brown
## leg, so a column is a quarter of however long the arm runs. An arm reaches
## half a column further than the bottle it holds, which puts the middle of that
## brown column on the middle of the bottle.
ARM_COLUMNS = 4
ARM_OVER = ARM_COLUMNS / (ARM_COLUMNS - 0.5)
BOTTLE_WIDE, BOTTLE_TALL = 5, 7
## Both planes are centred on the same line out from the rod, so the arm's face
## and the bottle's face used to sit at the exact same depth and z-fought over
## the stretch where the arm passes the plate. The bottle is thinner and nested
## inside the arm's own thickness instead of alongside it, which keeps both
## centred exactly where they were and leaves no shared plane to fight over.
ARM_DEEP = 0.1
BOTTLE_DEEP = 0.2

## Where the three sockets are drawn on the base tile, which is the only thing
## in the pack that says where a plate goes, and where each plate stands once
## the stand is turned half round. A plate keeps reading the socket it belongs
## to, so the picture turns with the stone.
## The order is the order the slot bits come in: a, then b, then c. The stone is
## the same three plates whichever way round the pair is read, so swapping the
## last two moves the bottles between them and nothing else.
BREW_PLATES = [((12, 8), (1, 5)), ((3, 12), (9, 1)), ((3, 4), (9, 9))]


def brew_plate(socket, at):
    """One of the three stone plates, reading its own socket on the base tile."""
    across, down = socket
    corner = (across - PLATE_WIDE // 2, down - PLATE_WIDE // 2)
    return Cube((PLATE_WIDE, PLATE_TALL, PLATE_WIDE), (at[0], 0, at[1]),
                texture=BREW_BASE, window={
                    "up": corner + (PLATE_WIDE, PLATE_WIDE),
                    "down": corner + (PLATE_WIDE, PLATE_WIDE),
                    "north": (corner[0], 16 - PLATE_TALL, PLATE_WIDE, PLATE_TALL),
                    "south": (corner[0], 16 - PLATE_TALL, PLATE_WIDE, PLATE_TALL),
                    "east": (corner[1], 16 - PLATE_TALL, PLATE_WIDE, PLATE_TALL),
                    "west": (corner[1], 16 - PLATE_TALL, PLATE_WIDE, PLATE_TALL)})


## The three plates stand at 180, 45 and minus 45 degrees round the rod, so an
## arm drawn once towards the solitary plate reaches the other two turned a
## hundred and thirty five degrees each way. The bottles are drawn the same way,
## as single upright planes rather than crossed pairs.
BREW_TURNS = (0.0, 135.0, -135.0)
## The whole arm is four columns of the tile: the dark pixel against the rod,
## the grey pipe beside it, a clear column, then the brown outer leg over the
## plate, with the bar that joins them across the top. It is drawn twice, once
## either side of the rod, and only the right hand copy is clean -- the bottle
## is painted over the left one from row 7 down -- so the arm reads columns 9 to
## 12 and the face that wants it the other way round reads them backwards.
##
## It runs from row 0, not from row 2: the outer column carries two more pixels
## above the bar, which is the point the arm finishes in, and a window starting
## at the bar crops them off.
##
## **Both faces read it the same way round, because the point has to stay over
## the plate.** The point is the top of the outer column, at the high x end of
## the window, and an arm is drawn running out from the rod at its high x to the
## plate at its low x -- so the window has to start at the far edge and run
## back, which is how Bedrock reads a picture mirrored. Giving the two faces
## opposite windows, which is what a plane usually wants, put the point over the
## rod on one side and over the plate on the other, and the arm looked like it
## turned round as you walked past it.
##
## A window that starts at the far edge and runs back is how Bedrock reads a
## picture mirrored.
ARM_ROWS = 14
ARM_ART = (13, 0, -ARM_COLUMNS, ARM_ROWS)
## the bottle vanilla draws into the same tile, five across by seven down
BOTTLE_ART = (0, 7, BOTTLE_WIDE, BOTTLE_TALL)
BOTTLE_BACK = (BOTTLE_WIDE, 7, -BOTTLE_WIDE, BOTTLE_TALL)


def two_sided(front, back):
    """A window for a plane, read the same way round from either side."""
    faces = {face: front for face in FACES}
    faces["south"] = back
    return faces


def brew_turned(size, at, angle, texture, window):
    """A piece turned about the rod, which stands at the middle of the block.

    The piece is drawn with an edge at the middle and then spun about that
    middle, so the edge stays pinned to the rod and the piece swings out to its
    own plate.

    **The move and the turn take the same sign.** `spun` moves a point the way a
    cube's own rotation moves the cube -- it negates the angle inside, which is
    the whole reason it exists -- so turning a piece about the rod is moving its
    middle by an angle and then turning the cube by that same angle. Opposite
    signs put the piece beside the right plate lying across the block instead of
    out along its own radius, which is a quarter turn wrong and only visible on
    the two plates that are not straight ahead.
    """
    middle = [start + span / 2.0 for start, span in zip(at, size)]
    moved = spun(middle, (8, middle[1], 8), (0, angle, 0))
    return Cube(size, [put - span / 2.0 for put, span in zip(moved, size)],
                texture, window=window, rotation=(0, angle, 0))


def brew_middle(at):
    """The middle of one plate, which is where its bottle stands."""
    return at[0] + PLATE_WIDE / 2.0, at[1] + PLATE_WIDE / 2.0


def brew_reach(at):
    """How far out from the rod the arm to one plate has to run.

    The three plates are not the same distance from the rod -- the solitary one
    is four out and the pair are nearer six -- so one arm drawn and turned three
    times reaches its own plate and stops short of the other two. Each arm is as
    long as its own plate is far, plus the half column that carries the brown
    leg past the middle of the bottle.
    """
    middle = brew_middle(at)
    return math.hypot(middle[0] - 8, middle[1] - 8) * ARM_OVER


def brew_arm(angle, reach):
    """An upright quad from the rod out to the middle of one plate.

    One edge is pinned at the rod and the other at the plate, and it stands from
    the top of the plate to two pixels above the rod.
    """
    return brew_turned((reach, ARM_TALL, ARM_DEEP),
                       (8 - reach, PLATE_TALL, 8 - ARM_DEEP / 2.0),
                       angle, BREW_ROD, {face: ARM_ART for face in FACES})


def brew_bottle(angle, at):
    """A bottle standing in the middle of one plate, turned with its arm.

    The three plates are not the same distance from the rod, so a bottle drawn
    at one of them and spun round misses the other two. It takes its plate's own
    middle and the turn its arm carries.
    """
    middle = brew_middle(at)
    ## the same sign as the arm it stands on, for the same reason: a bottle
    ## turned the other way faces across its plate instead of along it
    return Cube((BOTTLE_WIDE, BOTTLE_TALL, BOTTLE_DEEP),
                (middle[0] - BOTTLE_WIDE / 2.0, PLATE_TALL,
                 middle[1] - BOTTLE_DEEP / 2.0),
                BREW_ROD, window=two_sided(BOTTLE_ART, BOTTLE_BACK),
                rotation=(0, angle, 0))


brew_rod = Cube((ROD_WIDE, ROD_TALL, ROD_WIDE), (7, 0, 7), texture=BREW_ROD,
                window={
                    ## the rod's own column of the tile. It was read a row high,
                    ## which left a blank line across the top of the rod
                    "north": (7, 2, ROD_WIDE, ROD_TALL),
                    "south": (7, 2, ROD_WIDE, ROD_TALL),
                    "east": (7, 2, ROD_WIDE, ROD_TALL),
                    "west": (7, 2, ROD_WIDE, ROD_TALL),
                    "up": (7, 7, ROD_WIDE, ROD_WIDE),
                    "down": (7, 7, ROD_WIDE, ROD_WIDE)})


def brewing(bottles):
    """The rod, three plates with an arm each, and a bottle where there is one."""
    made = [brew_rod]
    for ((socket, at), angle, full) in zip(BREW_PLATES, BREW_TURNS, bottles):
        made.append(brew_plate(socket, at))
        made.append(brew_arm(angle, brew_reach(at)))
        if full:
            made.append(brew_bottle(angle, at))
    return made


## brewing_stand_slot_a_bit and its two fellows, joined the way core.py joins
## shape states, which sorts them a then b then c
BREWING_STANDS = {
    "-".join(str(n) for n in slots): brewing(slots)
    for slots in [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
}
BREWING_STANDS["default"] = BREWING_STANDS["0-0-0"]


# --- flower pots ------------------------------------------------------------
#
# A flower pot is a hollow box, not a solid one: four terracotta walls a pixel
# thick with a plug of dirt sunk inside them, six across and six tall, standing
# in the middle of its block. Drawn as one cube of the compost tile, which is
# what the table said, it is a brown block with nothing pot-shaped about it.
#
# `flower_pot.png` is a tile with two pictures on it rather than one texture:
# the rim seen from above at (5,5), six across and six down with the hole in
# the middle of it, and the outside of the wall under it at (5,10). Each face
# reads the part of whichever of those it belongs to, so a wall a pixel wide
# takes a one pixel slice and not the whole picture squeezed into it.
POT = "@up"                 # flower_pot; the block declares one texture for all
POT_SIDE = (5, 10)          # the outside of the wall, on the tile
POT_RIM = (5, 5)            # the rim from above, with its hole
POT_AT = 5                  # where the pot stands in its block
POT_WIDE = 6
POT_TALL = 6
DIRT = "textures/blocks/dirt"
DIRT_DEEP = 4               # the soil sits below the rim, as vanilla draws it


def pot_wall(size, at):
    """One wall, reading its own slice of the tile's two pictures.

    Both pictures are the pot six across and six down, so a face's slice of one
    is where the wall sits within the pot: along x for the faces you look at
    from the front, along z for the ends, and the footprint for the rim.
    """
    wide, tall, deep = size
    ## x and z are where the wall sits within the pot; y is its own height off
    ## the floor and is not measured from the pot's corner. Taking all three
    ## from the corner put every wall's window five rows past the bottom of the
    ## tile, which is nothing at all.
    x, z = at[0] - POT_AT, at[2] - POT_AT
    side_y = POT_SIDE[1] + POT_TALL - at[1] - tall
    return Cube(size, at, texture=POT, window={
        "north": (POT_SIDE[0] + x, side_y, wide, tall),
        "south": (POT_SIDE[0] + x, side_y, wide, tall),
        "east": (POT_SIDE[0] + z, side_y, deep, tall),
        "west": (POT_SIDE[0] + z, side_y, deep, tall),
        "up": (POT_RIM[0] + x, POT_RIM[1] + z, wide, deep),
        "down": (POT_RIM[0] + x, POT_RIM[1] + z, wide, deep)})


FLOWER_POTS = {"default": [
    ## the two long walls, then the two short ones between them
    pot_wall((1, POT_TALL, POT_WIDE), (POT_AT, 0, POT_AT)),
    pot_wall((1, POT_TALL, POT_WIDE), (POT_AT + POT_WIDE - 1, 0, POT_AT)),
    pot_wall((POT_WIDE - 2, POT_TALL, 1), (POT_AT + 1, 0, POT_AT)),
    pot_wall((POT_WIDE - 2, POT_TALL, 1),
             (POT_AT + 1, 0, POT_AT + POT_WIDE - 1)),
    ## and the soil, at its own pixel scale rather than a whole tile shrunk
    Cube((POT_WIDE - 2, DIRT_DEEP, POT_WIDE - 2), (POT_AT + 1, 0, POT_AT + 1),
         texture=DIRT,
         window={face: (0, 0, POT_WIDE - 2, POT_WIDE - 2) for face in FACES}),
]}


# --- decorated pots ---------------------------------------------------------
#
# The body and the neck read two different pictures, and neither is a terrain
# tile. `decorated_pot_side` is the pot's wall, fourteen across and the height
# of the block, and `decorated_pot_base` is a 32x32 sheet holding the unwrap of
# the neck across the top of it and the body's top and bottom under that.
#
# Faces left to work their window out from where their cube sits read that
# sheet as if it were a tile, which lands the body's top on the neck's unwrap
# and on the empty row between the two, so the pot comes out with holes through
# it. Every face names the part of the sheet it wants.
POT_SHEET = 32
POT_BASE = "@up"                # decorated_pot_base, on up and down
POT_WALL = "@north"             # decorated_pot_side, on the four sides
BODY_WIDE = 14
BODY_TALL = 12
NECK_WIDE = 8
NECK_TALL = 4

## the neck's unwrap on the sheet, in the order Bedrock lays a box out: the two
## square faces along the top, then the four walls in a strip under them
NECK_FACES = {
    "up": (NECK_WIDE, 0, NECK_WIDE, NECK_WIDE),
    "down": (NECK_WIDE * 2, 0, NECK_WIDE, NECK_WIDE),
    "west": (0, NECK_WIDE, NECK_WIDE, NECK_TALL),
    "south": (NECK_WIDE, NECK_WIDE, NECK_WIDE, NECK_TALL),
    "east": (NECK_WIDE * 2, NECK_WIDE, NECK_WIDE, NECK_TALL),
    "north": (NECK_WIDE * 3, NECK_WIDE, NECK_WIDE, NECK_TALL),
}
## and the body's two square faces, side by side under the neck's strip
BODY_FACES = {
    "up": (0, 13, BODY_WIDE, BODY_WIDE),
    "down": (BODY_WIDE, 13, BODY_WIDE, BODY_WIDE),
}


def sheet_cube(size, at, faces, name):
    """A cube whose every face names its own region of the pot sheet."""
    texture, window = {}, {}
    for face, region in faces.items():
        texture[face], window[face] = on_sheet(name, region, POT_SHEET)
    return Cube(size, at, texture=texture, window=window)

def pot_body():
    """The pot's wall, its shoulder and its floor.

    The wall texture is the height of the block and the body is the lower three
    quarters of it, so the wall reads the bottom twelve rows: the top four
    belong to the neck, which takes its own from the sheet.
    """
    texture, window = {}, {}
    for face in ("north", "south", "east", "west"):
        texture[face] = POT_WALL
        window[face] = (1, 16 - BODY_TALL, BODY_WIDE, BODY_TALL)
    for face, region in BODY_FACES.items():
        texture[face], window[face] = on_sheet(POT_BASE, region,
                                               POT_SHEET)
    return Cube((BODY_WIDE, BODY_TALL, BODY_WIDE), (1, 0, 1),
                texture=texture, window=window)


DECORATED_POTS = {"default": [
    pot_body(),
    sheet_cube((NECK_WIDE, NECK_TALL, NECK_WIDE),
               ((16 - NECK_WIDE) // 2, BODY_TALL, (16 - NECK_WIDE) // 2),
               NECK_FACES, POT_BASE),
]}


def main():
    print("writing the mounted forms")
    write("hanging_sign", HANGING_SIGNS)
    write("bell", BELLS)
    ## the grindstone turns about the wheel's own height rather than the middle
    ## of the block, which is where its entry has always put the pivot
    write("grindstone", GRINDSTONES, center=(8, 7.04, 8))
    write("campfire", CAMPFIRES, center=(8, 4, 8))
    write("shelf", SHELVES)
    write("door", DOORS)
    write("tripwire_hook", TRIPWIRE_HOOKS)
    write("sculk_shrieker", SHRIEKERS)
    write("tripwire", STRINGS)
    write("flower_pot", FLOWER_POTS)
    write("decorated_pot", DECORATED_POTS)
    ## the rod turns about the middle of the block, not the middle of the base
    write("brewing_stand", BREWING_STANDS, center=(8, 6.4, 8))
    write("cauldron", CAULDRONS)
    define(["cauldron", "lava_cauldron"], "cauldron")
    write("heavy_core", HEAVY_CORES, center=(8, 4, 8))
    write("dried_ghast", DRIED_GHASTS)
    ## a shrieker was drawn from the plain cube family, so it needs pointing at
    ## the one written here; `tripwire` already has both of its block ids
    define(["sculk_shrieker"], "sculk_shrieker")


if __name__ == "__main__":
    main()
