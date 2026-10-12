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

**Every family here rests facing north**, as Minecraft's blocks do: a wall
mounting sits against the south side of its block. The cubes are written
`behind`: their tops and bottoms read the tile backwards, and a side reading its
own place in the block measures it from the far side, which is how these blocks
have always been painted.

The families here own their entries in `lookups/block_geometry.json`
outright: re-running this replaces them. Nothing here is
needed at run time. Re-run `tools/blocks/simplify.py` afterwards, or the
simplified forms still outline the old shapes.
"""
import copy
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks.geometry import Cube, FACES, on_sheet, spun, unwrap
from tools.blocks import java
from tools.blocks.tables import define, forms, rules, turns, unturn, write


# --- hanging signs ----------------------------------------------------------
#
# A hanging sign's texture is an entity sheet, 64x32, laid out the way the
# entity model reads it: the plank a wall sign hangs from, 16 by 2 by 4, at the
# corner; the two crossed planes of one chain at (0,6) and (6,6); the single V
# shaped plane of chain an attached sign hangs from at (14,6); and the board, 14
# by 10 by 2, at (0,12). Each piece is a box of that model and reads its faces
# where the model would, through `unwrap`.
#
# Which pieces a sign shows depends on how it is mounted, and the form is named
# by `attached_bit` and `hanging`. Swinging under a block, two chains each made
# of two crossed planes. Attached to the block above, the V of chain. On a wall,
# the plank running out from the wall with the two chains under it.
HANGING_SHEET = "@north"
HANGING_WIDE = 64


def sign_piece(size, at, uv, rotation=None):
    """One box of the sign's entity model, reading its faces off the sheet.

    A face with no area, the edges of a plane, reads nothing. The entity draws
    a plane from both sides with only its front painted on the sheet, so the
    back of a plane reads the front's picture, which a back face shows mirrored.
    """
    wide, tall, deep = size
    texture, window = {}, {}
    regions = unwrap(uv, size)
    if deep == 0:
        regions["south"] = regions["north"]
    for face, region in regions.items():
        flat = {"up": wide * deep, "down": wide * deep,
                "north": wide * tall, "south": wide * tall,
                "east": deep * tall, "west": deep * tall}[face] == 0
        if flat:
            texture[face], window[face] = HANGING_SHEET, (0, 0, 0, 0)
        else:
            texture[face], window[face] = on_sheet(HANGING_SHEET, region,
                                                   HANGING_WIDE)
    return Cube(size, at, texture=texture, window=window, rotation=rotation)


board = sign_piece((14, 10, 2), (1, 0, 7), (0, 12))
plank = sign_piece((16, 2, 4), (0, 14, 6), (0, 0))
## each chain is two planes crossed at a right angle, standing over a point
## five pixels either side of the middle
chains = [sign_piece((3, 6, 0), (x - 1.5, 10, 8), uv, [0, turn, 0])
          for x in (3, 13) for uv, turn in (((0, 6), -45), ((6, 6), 45))]
v_chain = sign_piece((12, 6, 0), (2, 10, 8), (14, 6))

## Fixed to a chain it turns in sixteen steps with `ground_sign_direction`;
## every other mounting turns with `facing_direction`, read through a key of
## its own form. Facing up or down is not a way a sign hangs, and the game
## draws those as facing north.
HANGING_SIGN_TURNS = {str(step): [0, (180 - 22.5 * step) % 360, 0] for step in range(16)}
for form in ("0-1", "0-0", "1-0", "default"):
    HANGING_SIGN_TURNS.update({"%s:%d" % (form, facing): turn for facing, turn in (
        (0, [0, 0, 0]), (1, [0, 0, 0]), (2, [0, 0, 0]), (3, [0, 180, 0]),
        (4, [0, 90, 0]), (5, [0, 270, 0]))})

## Named by attached_bit and hanging, joined the way core.py joins shape states.
HANGING_SIGNS = {
    "0-1": [board] + chains,
    "1-1": [board, v_chain],
    "0-0": [board, plank] + chains,
    "1-0": [board, plank] + chains,
    "default": [board] + chains,
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
                         "down": (0, 0, WHEEL_WIDE, WHEEL_DEEP)}, behind=True)
    ## the stand runs across the block the way it always did; only the wheel
    ## between its two pivots turned
    pivots = [Cube((2, PIVOT_TALL, 4), (at, axle - PIVOT_TALL // 2, 6), PIVOT,
                   window={face: PIVOT_ART for face in FACES}, behind=True)
              for at in (WHEEL_AT + WHEEL_WIDE, WHEEL_AT - 2)]
    return legs(floor, axle) + pivots + [wheel]


## the two legs, west one first
LEG_AT = (12, 2)


def legs_down(floor, axle):
    ## up to the pivot, not up to the wheel: a post that stopped at the stone
    ## left a gap under the square it is meant to carry
    return [Cube((2, axle - PIVOT_TALL // 2, 2), (at, 0, 7), LEG, behind=True)
            for at in LEG_AT]


def legs_up(floor, axle):
    top = axle + PIVOT_TALL // 2
    return [Cube((2, 16 - top, 2), (at, top, 7), LEG, behind=True)
            for at in LEG_AT]


## back into the wall it is fixed to, the south side of the block
def legs_back(_floor, axle, sides=(10,)):
    return [Cube((2, 2, 6), (at, axle - 1, z), LEG, behind=True)
            for z in sides for at in LEG_AT]


GRINDSTONES = {
    ## on the floor, so the wheel is up against the block above it
    "standing": grindstone(LEG_ROOM, legs_down),
    ## under a block, so it hangs and the wheel is down against the floor
    "hanging": grindstone(0, legs_up),
    ## on a wall, so the wheel sits in the middle and the legs run into it
    "side": grindstone(LEG_ROOM // 2, legs_back),
    "multiple": grindstone(LEG_ROOM // 2,
                           lambda floor, axle: legs_back(floor, axle, (10, 0))),
    "default": grindstone(LEG_ROOM, legs_down),
}


# --- campfires --------------------------------------------------------------
#
# Java's `template_campfire`, turned to rest facing north: four logs, a strip of
# ash between the lower pair, and the fire crossed through the middle when it
# is lit. `campfire_log` is the bark across its top rows, a cut end under it and
# the ash below; a burning campfire's logs show `campfire_log_lit` on the faces
# that glow, which Bedrock declares on the side slot, and an extinguished one
# shows the plain log there. The fire reads the up slot, so a soul campfire
# burns blue without naming it here.
#
# **The underside is the two lower logs and the ash between them**, each
# reading the same picture underneath as on top: the bark for a log, the ash for
# the strip. Java draws none of them, since a campfire sits on a block.
CAMPFIRE = [
    {"from": [1, 0, 0], "to": [5, 4, 16], "faces": {
        "north": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "east": {"uv": [0, 1, 16, 5], "texture": "#lit_log"},
        "south": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "west": {"uv": [16, 0, 0, 4], "texture": "#log"},
        "up": {"uv": [0, 0, 16, 4], "rotation": 90, "texture": "#log"},
        "down": {"uv": [0, 0, 16, 4], "rotation": 90, "texture": "#log"}}},
    {"from": [0, 3, 11], "to": [16, 7, 15], "faces": {
        "north": {"uv": [16, 0, 0, 4], "texture": "#lit_log"},
        "east": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "south": {"uv": [0, 0, 16, 4], "texture": "#lit_log"},
        "west": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "up": {"uv": [0, 0, 16, 4], "rotation": 180, "texture": "#log"},
        "down": {"uv": [0, 4, 16, 8], "texture": "#lit_log"}}},
    {"from": [11, 0, 0], "to": [15, 4, 16], "faces": {
        "north": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "east": {"uv": [0, 0, 16, 4], "texture": "#log"},
        "south": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "west": {"uv": [16, 1, 0, 5], "texture": "#lit_log"},
        "up": {"uv": [0, 0, 16, 4], "rotation": 90, "texture": "#log"},
        "down": {"uv": [0, 0, 16, 4], "rotation": 90, "texture": "#log"}}},
    {"from": [0, 3, 1], "to": [16, 7, 5], "faces": {
        "north": {"uv": [0, 0, 16, 4], "texture": "#lit_log"},
        "east": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "south": {"uv": [16, 0, 0, 4], "texture": "#lit_log"},
        "west": {"uv": [0, 4, 4, 8], "texture": "#log"},
        "up": {"uv": [0, 0, 16, 4], "rotation": 180, "texture": "#log"},
        "down": {"uv": [0, 4, 16, 8], "texture": "#lit_log"}}},
    {"from": [5, 0, 0], "to": [11, 1, 16], "faces": {
        "north": {"uv": [0, 15, 6, 16], "texture": "#log"},
        "south": {"uv": [10, 15, 16, 16], "texture": "#log"},
        "up": {"uv": [0, 8, 16, 14], "rotation": 90, "texture": "#lit_log"},
        "down": {"uv": [0, 8, 16, 14], "rotation": 90, "texture": "#log"}}},
]
CAMPFIRE_FLAMES = [
    {"from": [0.8, 1, 8], "to": [15.2, 17, 8],
     "rotation": {"origin": [8, 8, 8], "axis": "y", "angle": 45, "rescale": True},
     "faces": {"north": {"uv": [0, 0, 16, 16], "texture": "#fire"},
               "south": {"uv": [0, 0, 16, 16], "texture": "#fire"}}},
    {"from": [8, 1, 0.8], "to": [8, 17, 15.2],
     "rotation": {"origin": [8, 8, 8], "axis": "y", "angle": 45, "rescale": True},
     "faces": {"west": {"uv": [0, 0, 16, 16], "texture": "#fire"},
               "east": {"uv": [0, 0, 16, 16], "texture": "#fire"}}},
]


def campfire(lit):
    read = {"log": java.slot("down"), "fire": java.slot("up"),
            "lit_log": java.slot("north") if lit else java.slot("down")}
    elements = java.half_turned(CAMPFIRE + (CAMPFIRE_FLAMES if lit else []))
    return java.form(elements, read.get)


CAMPFIRES = {"0": campfire(True), "1": campfire(False), "default": campfire(True)}


# --- doors ------------------------------------------------------------------
#
# A door is a panel three pixels thick standing at one edge of its block, and
# the game paints it the way its old block renderer painted any box: **every
# face reads the part of the picture under it**, the columns its own edge of the
# block spans, as seen from outside, and a few faces are flipped. So a door's
# edges read different strips depending on where in the world they face, which
# no turned shape can do: each facing, open or shut, hinged or not, is a form of
# its own, written unturned.
#
# The panel's place and the flipped face are the legacy door's, by its
# numbered direction: 0 south, 1 west, 2 north, 3 east, as Mojang's upgrade
# reads the old numbers. Shut, one side is flipped, and the hinge flips every
# side; open, the hinge moves the panel instead. The top and the bottom read
# the picture straight through, unflipped.
#
# **The two narrow edges are what a world showed**, state by state, in
# `DOOR_EDGES`: each shows the three columns at the end of the picture it
# borders, the two edges taking opposite ends, as columns seen left to right
# from outside.
DOOR_LOWER = "down"             # door_lower, the half nearest the floor
DOOR_UPPER = "north"            # door_upper, declared on `side`
DOOR_T = 3 / 16.0
DOOR_DIRECTION = {"south": 0, "west": 1, "north": 2, "east": 3}
DOOR_EDGES = {
    "east-0-0": {"east": (13, 16), "west": (3, 0)},
    "east-0-1": {"east": (3, 0), "west": (13, 16)},
    "east-1-0": {"north": (16, 13), "south": (0, 3)},
    "east-1-1": {"north": (13, 16), "south": (3, 0)},
    "north-0-0": {"north": (13, 16), "south": (3, 0)},
    "north-0-1": {"north": (3, 0), "south": (13, 16)},
    "north-1-0": {"east": (3, 0), "west": (13, 16)},
    "north-1-1": {"east": (0, 3), "west": (16, 13)},
    "south-0-0": {"north": (0, 3), "south": (16, 13)},
    "south-0-1": {"north": (16, 13), "south": (0, 3)},
    "south-1-0": {"east": (16, 13), "west": (0, 3)},
    "south-1-1": {"east": (13, 16), "west": (3, 0)},
    "west-0-0": {"east": (0, 3), "west": (16, 13)},
    "west-0-1": {"east": (16, 13), "west": (0, 3)},
    "west-1-0": {"north": (3, 0), "south": (13, 16)},
    "west-1-1": {"north": (0, 3), "south": (16, 13)},
}


def door_bounds(direction, open_, hinged):
    """(min x, min z, max x, max z) of the panel, in blocks, x east and z south."""
    t = DOOR_T
    if open_:
        return {(0, False): (0, 0, 1, t), (0, True): (0, 1 - t, 1, 1),
                (1, False): (1 - t, 0, 1, 1), (1, True): (0, 0, t, 1),
                (2, False): (0, 1 - t, 1, 1), (2, True): (0, 0, 1, t),
                (3, False): (0, 0, t, 1), (3, True): (1 - t, 0, 1, 1)}[(direction, hinged)]
    return {0: (0, 0, t, 1), 1: (0, 0, 1, t), 2: (1 - t, 0, 1, 1), 3: (0, 1 - t, 1, 1)}[direction]


def door_flipped(direction, open_, hinged):
    """The sides that read their picture the other way round."""
    if open_:
        flipped = {{0: "north", 1: "east", 2: "south", 3: "west"}[direction]}
    else:
        flipped = {{0: "east", 1: "south", 2: "west", 3: "north"}[direction]}
        if hinged:
            flipped = {"north", "south", "east", "west"} - flipped
    return flipped


def door_half(bounds, flipped, slot, y, edges):
    x0, z0, x1, z1 = bounds
    ## the columns a side spans, along x for north and south, z for east and
    ## west, read left to right as seen from outside
    spans = {"north": (x0, x1), "south": (x0, x1), "east": (z0, z1), "west": (z0, z1)}
    faces = {}
    for face, (low, high) in spans.items():
        if face in edges:
            left, right = edges[face]
            faces[face] = {"uv": [left / 16.0, 0], "size": [(right - left) / 16.0, 1]}
        elif face in flipped:
            faces[face] = {"uv": [high, 0], "size": [low - high, 1]}
        else:
            faces[face] = {"uv": [low, 0], "size": [high - low, 1]}
    for face in faces.values():
        face["texture"] = {"slot": slot}
    ## **The ends are the same plain strip on every door**: the bottom three
    ## rows of the lower picture under the door, the top three of the upper one
    ## over it, laid along the panel. A panel running north to south reads its
    ## strip turned a quarter, where the bottom rows become the left columns and
    ## the top rows the right. The two ends where the halves meet are inside
    ## the door and are not drawn.
    along_x = (x1 - x0) > (z1 - z0)
    rows = (13 / 16.0, 3 / 16.0) if y == 0 else (0, 3 / 16.0)
    end = "down" if y == 0 else "up"
    inner = "up" if y == 0 else "down"
    if along_x:
        faces[end] = {"uv": [0, rows[0]], "size": [1, rows[1]], "texture": {"slot": slot}}
    else:
        across = 0 if y == 0 else 13 / 16.0
        faces[end] = {"uv": [across, 0], "size": [3 / 16.0, 1],
                      "texture": {"slot": slot, "turn": 90}}
    faces[inner] = {"uv": [0, 0], "size": [0, 0]}
    return {"size": [x1 - x0, 1, z1 - z0], "offset": [1 - x1, y, z0], "faces": faces}


def door_form(facing, open_, hinged):
    direction = DOOR_DIRECTION[facing]
    bounds = door_bounds(direction, open_, hinged)
    flipped = door_flipped(direction, open_, hinged)
    edges = DOOR_EDGES["%s-%d-%d" % (facing, open_, hinged)]
    return {"center": [0.5, 0.5, 0.5], "cubes": [
        door_half(bounds, flipped, DOOR_LOWER, 0, edges),
        door_half(bounds, flipped, DOOR_UPPER, 1, edges)]}


## The lower block's forms are named `lower-<facing>-<open>-<hinge>`. A form is
## read by mounting and value before value alone, so a name of the value alone
## would be drawn by the upper block too, which has no form of its own value.
DOOR_FORMS = {"lower-%s-%d-%d" % (facing, open_, hinged): door_form(facing, open_, hinged)
              for facing in DOOR_DIRECTION for open_ in (0, 1) for hinged in (0, 1)}
DOOR_FORMS["default"] = copy.deepcopy(DOOR_FORMS["lower-north-0-0"])
## the upper block of a door draws nothing; the lower one draws both halves
DOOR_FORMS["top"] = {"center": [0.5, 0.5, 0.5], "cubes": [{
    "size": [0, 0, 0], "offset": [0, 0, 0],
    "faces": {face: {"uv": [0, 0], "size": [0, 0]} for face in FACES}}]}


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
# It hangs on the wall behind it, the south side of its block, so at no
# rotation it runs z 11 to 16, the same way a wall sign sits at z 14 to 16.
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
    ## measured from the far side, which is how the sheet is laid out
    across, over = 16 - across - wide, 16 - over - deep
    paint = {}
    window = {}
    for face in FACES:
        if face in inner:
            paint[face] = SHELF_INNER
        elif face == "north":
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
    return Cube(size, at, texture=paint, window=window, behind=True)


def shelf():
    """The floor, the ceiling, the back and the two uprights."""
    low, high = OPENING
    open_tall = high - low
    made = [
        ## the two boards, the full depth of the case. The compartment side of
        ## each is shaded: the floor lit along its front lip, the ceiling not
        shelf_piece((16, BOARD, SHELF_DEEP), (0, 0, 16 - SHELF_DEEP),
                    (0, high, 16, BOARD), inner=("up",)),
        shelf_piece((16, BOARD, SHELF_DEEP), (0, high, 16 - SHELF_DEEP),
                    (0, 0, 16, BOARD), inner=("down",)),
        ## the back, between them and three deep, so the opening it closes is
        ## two deep
        shelf_piece((16, open_tall, SHELF_BACK_DEEP),
                    (0, low, 16 - SHELF_BACK_DEEP), (0, low, 16, open_tall)),
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
## The lid is the throat: the bony corners of `sculk_shrieker_top` are the
## tops of the prongs, drawn where the prongs end.
SHRIEKER_THROAT = "textures/blocks/sculk_shrieker_inner_top"
SHRIEKER_CAPS = "textures/blocks/sculk_shrieker_top"

## The prongs stand on the lid, a pixel in from each side and seven tall, and
## are the top rows of the side picture: a prong at each end and a low bump
## between them. Each is a plane of its own, reading the picture where it
## stands, so each is cut down to what it shows and drawn after the lid.
PRONG_TALL = 7
## (from, to) across each side, in pixels: the two prongs, and the bump, which
## is only the bottom two rows
PRONGS = ((1, 6, PRONG_TALL), (10, 15, PRONG_TALL), (6, 10, 2))
## the corners the prongs' caps cover, five pixels square
CAP = 5


def plane(size, at, faces, texture="default", art=None):
    """A plane drawing only `faces`, each reading the picture where it stands,
    or `art`, a window per face, where it is given."""
    window = {face: (0, 0, 0, 0) for face in FACES if face not in faces}
    window.update(art or {})
    return Cube(size, at, texture, window=window)


def shrieker():
    made = [Cube((16, SHRIEKER_TALL, 16), (0, 0, 0),
                 texture={"north": "default", "south": "default", "east": "default",
                          "west": "default", "up": SHRIEKER_THROAT, "down": "default"})]
    ## A face looking north or west has the low end of the block on its left
    ## and reads the picture where it stands. One looking south or east has it
    ## on its right, so it reads the picture from the other end, or the prong
    ## shows with its tip toward the middle; that holds for the inside faces as
    ## much as the outside ones.
    for low, high, tall in PRONGS:
        row = 16 - SHRIEKER_TALL - tall
        turned = (16 - high, row, high - low, tall)
        for z in (1, 15):
            made.append(plane((high - low, tall, 0), (low, SHRIEKER_TALL, z),
                              ("north", "south"), art={"south": turned}))
        for x in (1, 15):
            made.append(plane((0, tall, high - low), (x, SHRIEKER_TALL, low),
                              ("east", "west"), art={"east": turned}))
    top = SHRIEKER_TALL + PRONG_TALL
    for x in (1, 16 - 1 - CAP):
        for z in (1, 16 - 1 - CAP):
            made.append(plane((CAP, 0, CAP), (x, top, z), ("up", "down"), SHRIEKER_CAPS))
    return made


SHRIEKERS = {"default": shrieker()}


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
# It hangs on the wall behind it, the south side of its block, so the plate sits
# at z 14 to 16, the same way a wall sign does, and the hook reaches out north.
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

## against the wall behind it, the south side of the block
plate = Cube((PLATE_WIDE, PLATE_TALL, PLATE_DEEP),
             ((16 - PLATE_WIDE) // 2, (16 - PLATE_TALL) // 2, 16 - PLATE_DEEP),
             texture="@down", behind=True)


def leaning(angle, along, up):
    """Where a point `along` the shaft and `up` from its middle line ends up.

    The shaft leaves the plate at `SHAFT_AT` and runs out of the wall to the
    north, and a positive angle lifts its far end; the cube carries the angle
    negated, which is the same lift seen from the north.
    """
    lean = math.radians(angle)
    out = (math.cos(lean), math.sin(lean))          # along the shaft
    over = (-math.sin(lean), math.cos(lean))        # square across it
    return (8,
            SHAFT_AT + along * out[1] + up * over[1],
            16 - (PLATE_DEEP - SHAFT_IN + along * out[0] + up * over[0]))


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
                 texture=HOOK, rotation=(-angle, 0, 0), window={
                     "north": HOOK_END, "south": HOOK_END,
                     "east": HOOK_SHAFT, "west": HOOK_SHAFT,
                     "up": HOOK_END, "down": HOOK_END}, behind=True)
    ## the ring hangs from the end of the shaft, off one half of its face, and
    ## reaches back across it: its own middle is that much further down again
    edge = 0.5 if high else -0.5
    at = leaning(angle, SHAFT_LONG + ring_out, edge - RING_WIDE / 2.0)
    at = (at[0], at[1] + ring_lift, at[2])
    ring = Cube((RING_WIDE, RING_WIDE, RING_THICK),
                (at[0] - RING_WIDE / 2.0, at[1] - RING_WIDE / 2.0,
                 at[2] - RING_THICK / 2.0),
                texture=HOOK, rotation=(-ring_angle, 0, 0), window={
                    "north": HOOK_RING, "south": HOOK_RING,
                    "east": (5, 3, 6, 6), "west": (5, 3, 6, 6),
                    "up": (5, 3, 6, 6), "down": (5, 3, 6, 6)}, behind=True)
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
# so `core.BLOCK_ENTITY_TINTS` reads that colour, the form becomes `dyed`, and its
# liquid asks for a tint. Scaffold builds the pack, so the tile is multiplied
# by the colour on its way into the atlas and every dye in a structure lands
# there as a tile of its own.
POT_WALL = 2
POT_FLOOR = 3
## `cauldron_water` is grey, because the game tints it with the water
## colour of wherever the cauldron is. Untinted it is white.
WATER_BLUE = "~3f76e4"
LIQUID = {"water": "textures/blocks/cauldron_water" + WATER_BLUE,
          "lava": "textures/blocks/lava_still",
          "powder_snow": "textures/blocks/powder_snow",
          ## the same water, asking for the block's own colour. `~tint` is put
          ## aside for the colour the block entity carries, and a cauldron with
          ## no colour reads the plain tile.
          "dyed": "textures/blocks/cauldron_water~tint"}
## where each liquid's picture starts on its tile. Lava is the still lava's
## first frame, the lava alone: `cauldron_lava` has the cauldron's rim drawn
## round it, which showed inside the pot.
LIQUID_AT = {}
## how high each fill level stands, in pixels off the floor of the block
CAULDRON_FILL = {level: POT_FLOOR + 2 * level for level in range(1, 7)}

INSIDE = 16 - 2 * POT_WALL

## **The floor of the pot needs its own picture on top.** `cauldron_top` is the
## rim seen from above and is clear through the middle, which is the hole a
## cauldron is looked into through. Given to the floor's upper face as well, an
## empty cauldron could be seen straight through to the sky. `cauldron_inner` is
## the one the game puts inside. The underside keeps `cauldron_bottom`, which is
## what the block declares for `down` and is already what it reads.
POT_INNER = "textures/blocks/cauldron_inner"

## **The underside is one flattened picture, not a cut one over a plate.**
## `cauldron_bottom` is opaque only at its four corners: the game expects the
## recessed floor of the pot to show through the gap between the feet. A ghost
## block cannot afford that, because a transparent texel still takes the depth
## it stands at, so the cut middle blanked whatever stood behind it and a
## cauldron could be seen up through from below and out of the top. Standing a
## plate behind the gap cured that and left a cube in the middle of the block
## for the liquid and the walls to trip over. `tools/textures/cauldron.py`
## draws the feet onto the inside instead, and the underside then needs no
## geometry behind it at all.
POT_UNDER = "textures/blocks/cauldron_bottom_flat"
POT_FLOOR_ART = dict({face: "default" for face in FACES},
                     up=POT_INNER, down=POT_UNDER)

cauldron_pot = [
    Cube((16, POT_FLOOR, 16), (0, 0, 0), texture=POT_FLOOR_ART),
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
             window={face: LIQUID_AT.get(liquid, (0, 0)) + (INSIDE, INSIDE)
                     for face in FACES})]


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
        "west": (across, down, deep, tall)}, behind=True)


def dried_ghast():
    far = GHAST_AT + GHAST_WIDE
    ## the two along a side, a pixel in from each corner of the body
    spread = (GHAST_AT + TENTACLE_IN,
              far - TENTACLE_IN - TENTACLE_WIDE)
    tentacles = []
    for near in reversed(spread):
        ## out of the west side and the east side
        tentacles.append(tentacle((far, 0, near), True))
        tentacles.append(tentacle((GHAST_AT - TENTACLE_LONG, 0, near), True))
        ## and out of the back, which is south; the face is north and has none
        tentacles.append(tentacle((near, 0, far), False))
    body = Cube((GHAST_WIDE, GHAST_WIDE, GHAST_WIDE),
                (GHAST_AT, 0, GHAST_AT),
                window={face: GHAST_ART for face in FACES}, behind=True)
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
## from the top of a plate up to two pixels above the rod
ARM_TALL = ROD_TALL + 2 - PLATE_TALL
## The arm reads four columns of the tile: the dark pixel against the rod, the
## grey pipe beside it, a clear column, then the brown outer leg.
ARM_COLUMNS = 4
## **It is drawn at the texture's own scale, one column to one pixel of block,
## and it starts where the rod stops.** Stretched to reach its own plate the
## columns came out a fraction of a pixel each, and running from the middle of
## the block rather than from the rod's face buried the first of them inside the
## rod, where nothing shows: the dark pipe the arm begins with had a sliver
## outside the pole instead of its two whole pixels.
ARM_REACH = ARM_COLUMNS
ROD_FACE = ROD_WIDE / 2.0
BOTTLE_WIDE, BOTTLE_TALL = 5, 7
## **The bottle is thick enough to hold the arm inside it, with room to spare.**
## Both planes are centred on the same line out from the rod and both run along
## it, so over the stretch where the arm passes the plate they are the same
## plane. The arm's tile carries a clear column between its pipe and its leg,
## and a transparent texel still takes the depth it stands at, so an arm at the
## same depth as the bottle cuts a stripe out of it. Nesting the arm inside the
## bottle answers that -- the bottle's faces are nearer from either side -- but
## only if the gap is big enough for the depth test to tell them apart. A
## twentieth of a pixel was not: it left the two turned bottles looking cut in
## half the moment they were squared up with their arms. A fifth of a pixel
## each side is.
ARM_DEEP = 0.1
BOTTLE_DEEP = 0.5

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
## How far each arm stands off the face of the rod, in the same order. The two
## turned ones are held half a pixel further out than the one drawn straight
## ahead.
ARM_GAPS = (
    0.0,                    # arm 1
    0.5,                    # arm 2
    0.5,                    # arm 3
)
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
## **The red leg goes at the far end, on every arm and from either side.** The
## four columns run outward in the tile -- 9 is the dark pipe that stands against
## the rod and 12 is the brown leg that stands over the plate -- and the cube
## runs inward, from its own far end at the low x to the rod's face at the high
## one. Read straight the tile lands on it backwards, and since all three arms
## are one cube at three angles they carry the leg against the pole together,
## which reads as three arms pointing one way rather than three pointing out.
##
## **So both faces take the same window, not opposite ones.** A banner's two
## faces want opposite windows because the design has to read the same way round
## to somebody walking round it, and walking round turns left and right over.
## The arm wants the opposite of that: the leg has to stay at the same end of
## the *block* whichever side it is seen from, and the two faces run their u the
## same way along x, so one window on all six is what keeps it there. Given the
## banner's treatment the arm came out with the leg outboard on its north face
## and against the pole on its south.
ARM_ROWS = 14
ARM_ART = (9 + ARM_COLUMNS, 0, -ARM_COLUMNS, ARM_ROWS)
ARM_BACK = (9, 0, ARM_COLUMNS, ARM_ROWS)
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

    **The move and the turn take opposite signs, and only the game says so.**
    `spun` is Scaffold's own arithmetic and `tools/checks/render.py` turns a cube
    the same way, so the two agree with each other whichever sign is used and the
    renderer draws a pinned arm either way. Bedrock turns a cube the other way
    about. Given the same sign the piece is carried round to its plate and then
    turned back, which leaves it beside the right plate lying across the block
    rather than out along its own radius -- visible on the two plates that are
    not straight ahead, and on those two only, which is what a brewing stand
    with one right arm and two wrong ones looks like.

    **So a picture from the renderer does not settle this one.** It draws what
    `spun` says, and `spun` is one of the two things being compared.
    """
    middle = [start + span / 2.0 for start, span in zip(at, size)]
    moved = spun(middle, (8, middle[1], 8), (0, angle, 0))
    return Cube(size, [put - span / 2.0 for put, span in zip(moved, size)],
                texture, window=window, rotation=(0, -angle, 0))


def brew_middle(at):
    """The middle of one plate, which is where its bottle stands."""
    return at[0] + PLATE_WIDE / 2.0, at[1] + PLATE_WIDE / 2.0


def brew_arm(angle, gap=0.0):
    """An upright quad running out from the face of the rod, four pixels long.

    It starts where the rod stops rather than at the middle of the block, so the
    two dark columns the arm begins with are two whole pixels of block standing
    clear of the pole. Pinned at the middle instead, the innermost of them sat
    inside the rod and only a sliver of the second one showed.

    Four pixels for four columns of the tile is the texture's own scale. It
    stands from the top of the plate to two pixels above the rod.

    `gap` holds the arm that much further off the rod's face. The length is not
    the thing to change for that: four pixels is four columns of the tile at one
    apiece, and stretching it puts the columns back at a fraction of a pixel
    each, which is what left the dark pipe a sliver.
    """
    return brew_turned((ARM_REACH, ARM_TALL, ARM_DEEP),
                       (8 - ROD_FACE - gap - ARM_REACH, PLATE_TALL,
                        8 - ARM_DEEP / 2.0),
                       angle, BREW_ROD, two_sided(ARM_ART, ARM_BACK))


def brew_bottle(angle, at):
    """A bottle standing in the middle of one plate, turned with its arm.

    The three plates are not the same distance from the rod, so a bottle drawn
    at one of them and spun round misses the other two. It takes its plate's own
    middle and the turn its arm carries.
    """
    middle = brew_middle(at)
    ## **The same sign as the arm it stands on, which is the negative of the
    ## angle.** Bedrock turns a cube the other way about from `spun`, so a
    ## bottle written with the plain angle faces across its plate instead of
    ## along it. This does not go through `brew_turned` -- its plate's middle is
    ## given outright rather than swung round to it -- so it does not get that
    ## correction for free, and it kept the old sign after the arms had it.
    return Cube((BOTTLE_WIDE, BOTTLE_TALL, BOTTLE_DEEP),
                (middle[0] - BOTTLE_WIDE / 2.0, PLATE_TALL,
                 middle[1] - BOTTLE_DEEP / 2.0),
                BREW_ROD, window=two_sided(BOTTLE_ART, BOTTLE_BACK),
                rotation=(0, -angle, 0))


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
    for ((socket, at), angle, gap, full) in zip(BREW_PLATES, BREW_TURNS,
                                                ARM_GAPS, bottles):
        made.append(brew_plate(socket, at))
        made.append(brew_arm(angle, gap))
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
NECK_FACES = unwrap((0, 0), (NECK_WIDE, NECK_TALL, NECK_WIDE))
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
                texture=texture, window=window, behind=True)


DECORATED_POTS = {"default": [
    pot_body(),
    sheet_cube((NECK_WIDE, NECK_TALL, NECK_WIDE),
               ((16 - NECK_WIDE) // 2, BODY_TALL, (16 - NECK_WIDE) // 2),
               NECK_FACES, POT_BASE),
]}


# --- item frames -------------------------------------------------------------
#
# An item frame was one flat plate twelve across and two thick, which is a tile
# of `itemframe_background` on a slab and nothing frame shaped about it. The game
# draws a birch surround with the canvas recessed inside it, and neither half of
# that is in the block's own textures: `blocks.json` gives the whole block
# `itemframe_background`, so the wood has to be named outright.
#
# It rests against the south side of its block looking north, the way a block
# at rest faces, and the rotation table carries it to the other five faces.
FRAME_WOOD = "textures/blocks/planks_birch"
FRAME_ACROSS = 12           # the surround, outer edge to outer edge
FRAME_BAR = 1               # how wide each of the four bars is
FRAME_THICK = 1             # and how far the whole thing stands off the wall
FRAME_AT = (16 - FRAME_ACROSS) / 2.0

## **The canvas is thinner than the surround and sits down inside it.** Level
## with the bars it is a flat plate with a border painted on; recessed, the
## frame reads as a frame from any angle a ghost block is looked at. It is
## tucked under the bars rather than butted against them, and lifted off the
## wall a shade, so that none of its faces lands on one of theirs.
FRAME_CANVAS = FRAME_ACROSS - 2 * FRAME_BAR
FRAME_TUCK = 0.2            # how far it reaches under each bar
FRAME_SUNK = 0.1            # and how far off the wall, so nothing is coplanar
FRAME_DEEP = 0.5            # the canvas is half the thickness of the surround

## **The canvas reads the middle of its tile, at its own size.** It is ten
## across inside the surround, and reads the ten pixels in the middle of the
## tile, as Java's `template_item_frame` does; reading more stretches the
## picture onto the panel squashed.
FRAME_EDGE = 3
FRAME_PICTURE = 16 - 2 * FRAME_EDGE

## **And the plain frame's picture is turned half round; the glow frame's is
## not.** A window with both sizes negative is a half turn, the same way one
## negative size is a mirror. That is the only difference between the two
## families, and it is why they are two rather than one reading `@up`.
FRAME_ART = (FRAME_EDGE, FRAME_EDGE, FRAME_PICTURE, FRAME_PICTURE)
FRAME_TURNED = (FRAME_EDGE + FRAME_PICTURE, FRAME_EDGE + FRAME_PICTURE,
                -FRAME_PICTURE, -FRAME_PICTURE)

_bar_at = FRAME_AT
_bar_end = FRAME_AT + FRAME_ACROSS - FRAME_BAR
_inner = FRAME_AT + FRAME_BAR
## the wall the frame hangs on is the south side of its block
_wall = 16 - FRAME_THICK


def frame_bar(size, at):
    """One bar of the surround, the planks' grain running along it.

    Each face reads the planks the way they lie across the frame's own face:
    the front and the back square on, the ends and the edges stood on their
    sides a quarter turn.
    """
    wide, tall, _deep = size
    x, y, _z = at
    return Cube(size, at, FRAME_WOOD, window={
        "north": (x, 16 - y - tall, wide, tall),
        "south": (x + wide, y + tall, -wide, -tall),
        "east": (0, y, FRAME_THICK, tall, 90),
        "west": (16 - FRAME_THICK, 16 - y - tall, FRAME_THICK, tall, 270),
        "up": (x + wide, 16, -wide, -FRAME_THICK),
        "down": (x, 16 - FRAME_THICK, wide, FRAME_THICK)})


def item_frame(turned):
    """The birch surround, and the canvas recessed inside it."""
    picture, other = (FRAME_TURNED, FRAME_ART) if turned else (FRAME_ART, FRAME_TURNED)
    return [
        ## the four bars of the surround, birch, running round the edge
        frame_bar((FRAME_ACROSS, FRAME_BAR, FRAME_THICK), (_bar_at, _bar_at, _wall)),
        frame_bar((FRAME_ACROSS, FRAME_BAR, FRAME_THICK), (_bar_at, _bar_end, _wall)),
        frame_bar((FRAME_BAR, FRAME_CANVAS, FRAME_THICK), (_bar_at, _inner, _wall)),
        frame_bar((FRAME_BAR, FRAME_CANVAS, FRAME_THICK), (_bar_end, _inner, _wall)),
        ## and the canvas, which reads whatever the block declares, so that a
        ## glow frame wears its own picture without naming it here. The front
        ## is north and the back is against the wall; the four edges read the
        ## picture stood on its side.
        Cube((FRAME_CANVAS + 2 * FRAME_TUCK, FRAME_CANVAS + 2 * FRAME_TUCK,
              FRAME_DEEP),
             (_inner - FRAME_TUCK, _inner - FRAME_TUCK,
              16 - FRAME_SUNK - FRAME_DEEP),
             dict({face: "@up" for face in FACES}, up="default"),
             window={"north": picture, "down": picture,
                     "south": other, "up": other,
                     "east": FRAME_ART + (270 if turned else 90,),
                     "west": FRAME_ART + (90 if turned else 270,)}),
    ]


FRAMES = {"default": item_frame(turned=True)}
GLOW_FRAMES = {"default": item_frame(turned=False)}

## `facing_direction`, in Minecraft's angles. Both families carry it: a
## rotation table is keyed by shape family, so splitting the glow frame off
## left it with none and it faced whichever way it was placed. A frame on a
## wall is only turned about y, so its picture stays upright.
FRAME_TURNS = {"0": [90, 0, 0], "1": [270, 0, 0], "2": [0, 0, 0],
               "3": [0, 180, 0], "4": [0, 90, 0], "5": [0, 270, 0]}


# --- shelf mushrooms --------------------------------------------------------
#
# 26.50's wall foliage, and the first block here drawn from a block model rather
# than from a voxel shape or a terrain tile. `shelf_mushroom_small.geo.json` and
# `shelf_mushroom_large.geo.json` in bedrock-samples give it two boxes: a cap,
# and a thinner underside tucked beneath it and further out from the wall.
#
# **Its UV space is sixteen units across a thirty-two pixel sheet**, so a unit
# of Mojang's UV is two texture pixels and every rectangle below is already
# doubled. A down face is written there with a negative height, which is the
# same rectangle measured upward from its own bottom edge; these are the
# rectangles themselves, so the four of them stack down the sheet without
# overlapping, which is the check that the doubling is right.
#
# **Mojang's model faces north, as a block at rest does**, so each box and the
# rectangle each of its faces reads are taken as the model gives them. The
# block's own `minecraft:transformation` permutations turn the other three
# facings from north, the way `minecraft:cardinal_direction` does.
MUSHROOM_SHEET = 32

## (size, where it sits with the wall at z16, the rectangle each face reads)
MUSHROOM_FORMS = {
    ## growth 0, the small one, on shelf_mushroom_small
    "0": ("textures/blocks/shelf_mushroom_small", [
        ((10, 2, 7), (3, 9, 9),
         {"north": (10, 4, 10, 2), "south": (10, 6, 10, 2),
          "east": (10, 0, 7, 2), "west": (10, 2, 7, 2),
          "up": (0, 0, 10, 7), "down": (0, 7, 10, 7)}),
        ((6, 1, 4), (5, 8, 12),
         {"north": (10, 10, 6, 1), "south": (10, 11, 6, 1),
          "east": (10, 8, 4, 1), "west": (10, 9, 4, 1),
          "up": (0, 14, 6, 4), "down": (0, 18, 6, 4)}),
    ]),
    ## growth 1, the large one, on a sheet of its own
    "1": ("textures/blocks/shelf_mushroom_large", [
        ((14, 3, 10), (1, 8, 6),
         {"north": (14, 6, 14, 3), "south": (14, 9, 14, 3),
          "east": (14, 0, 10, 3), "west": (14, 3, 10, 3),
          "up": (0, 0, 14, 10), "down": (0, 10, 14, 10)}),
        ((8, 2, 6), (4, 6, 10),
         {"north": (8, 24, 8, 2), "south": (8, 26, 8, 2),
          "east": (8, 20, 6, 2), "west": (8, 22, 6, 2),
          "up": (0, 20, 8, 6), "down": (0, 26, 8, 6)}),
    ]),
}

def mushroom_box(size, at, faces, sheet):
    """One of Mojang's boxes, each face reading its own rectangle."""
    texture, window = {}, {}
    for face in FACES:
        texture[face], window[face] = on_sheet(sheet, faces[face], MUSHROOM_SHEET)
    return Cube(size, at, texture=texture, window=window)


def shelf_mushrooms():
    forms = {}
    for growth, (sheet, boxes) in MUSHROOM_FORMS.items():
        forms[growth] = [mushroom_box(size, at, faces, sheet)
                         for size, at, faces in boxes]
    ## a mushroom with no growth state is the small one, which is what a block
    ## placed by a command with no states comes up as
    forms["default"] = forms["0"]
    return forms


SHELF_MUSHROOMS = shelf_mushrooms()

## the four facings, the same way a shelf reads them
MOUNTED_TURNS = "minecraft:cardinal_direction"


def main():
    print("writing the mounted forms")
    write("frame", FRAMES)
    turns("frame", FRAME_TURNS)
    write("glow_frame", GLOW_FRAMES)
    turns("glow_frame", FRAME_TURNS)
    define(["glow_frame"], "glow_frame")
    write("hanging_sign", HANGING_SIGNS)
    turns("hanging_sign", HANGING_SIGN_TURNS)
    ## the grindstone turns about the wheel's own height rather than the middle
    ## of the block, which is where its entry has always put the pivot
    write("grindstone", GRINDSTONES, center=(8, 7.04, 8))
    forms("campfire", CAMPFIRES)
    write("shelf", SHELVES)
    forms("door", DOOR_FORMS)
    rules("door", pick=[{"when": {"upper_block_bit": True}, "form": "top"},
                        {"when": {"upper_block_bit": False}, "form": "lower"}],
          data={"join": ["minecraft:cardinal_direction", "open_bit", "door_hinge_bit"]},
          turn_by=None)
    unturn("door")
    write("tripwire_hook", TRIPWIRE_HOOKS)
    write("sculk_shrieker", SHRIEKERS)
    write("tripwire", STRINGS)
    write("flower_pot", FLOWER_POTS)
    write("decorated_pot", DECORATED_POTS)
    ## the rod turns about the middle of the block, not the middle of the base
    write("brewing_stand", BREWING_STANDS, center=(8, 6.4, 8))
    write("cauldron", CAULDRONS)
    define(["cauldron"], "cauldron")
    write("heavy_core", HEAVY_CORES, center=(8, 4, 8))
    write("dried_ghast", DRIED_GHASTS)
    ## a shrieker was drawn from the plain cube family, so it needs pointing at
    ## the one written here; `tripwire` already has both of its block ids
    define(["sculk_shrieker"], "sculk_shrieker")
    ## the closed form is byte for byte what the table already held; "open" is
    ## the one that was missing
    define(["piston_arm_collision"], "piston_arm")
    define(["sticky_piston_arm_collision"], "sticky_piston_arm")
    write("shelf_mushroom", SHELF_MUSHROOMS)
    turns("shelf_mushroom", MOUNTED_TURNS)
    define(["shelf_mushroom"], "shelf_mushroom")


if __name__ == "__main__":
    main()
