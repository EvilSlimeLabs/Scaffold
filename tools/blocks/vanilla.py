"""Blocks drawn the way Minecraft draws them, from its own model where there is one.

    python -m tools.blocks.vanilla

Several families were written by hand long before the tables were in
Minecraft's frame, and drew their blocks a turn out, or as a box where the game
draws planes. This rebuilds them: every family here rests facing north, reads
its top with the picture's top edge to the north, and where the shape is more
than a box, takes it from the Java edition's block model, whose elements are
written out below as numbers and converted by `tools/blocks/java.py`.

Nothing here is needed at run time.
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import java, tables

FACES = ("north", "south", "east", "west", "up", "down")
## a whole block, drawn a shade under full size; see "A ghost block is drawn a
## shade under full size" in CLAUDE.md
GHOST = 0.95
## a ghost sits in the middle of its cell, an equal gap on every side
INSET = round((1 - GHOST) / 2, 6)
MIDDLE = [0.5] * 3


def box(read, size=(GHOST, GHOST, GHOST), offset=(INSET, INSET, INSET)):
    """One cube whose faces read `read[face]`, a texture object or None."""
    faces = {}
    for face in FACES:
        entry = {"uv": [1, 1], "size": [-1, -1]} if face in ("up", "down") \
            else {"uv": [0, 0], "size": [1, 1]}
        if read.get(face) is not None:
            entry["texture"] = read[face]
        faces[face] = entry
    return {"size": list(size), "offset": list(offset), "faces": faces}


def fronted(front):
    """A whole block with its front, read from slot `front`, on the north face.

    The sides read the block's own slots except the south, which shows the
    north slot, since the front's slot is now on the north face.
    """
    read = {face: None for face in FACES}
    read["north"] = java.slot(front)
    if front != "north":
        read[front] = java.slot("north")
    return {"center": MIDDLE, "cubes": [box(read)]}


# --- furnaces ---------------------------------------------------------------------
#
# Furnaces, blast furnaces and smokers declare their front on the south slot
# when unlit and on the east slot when lit, a quarter apart, so each is a family
# of its own: the front read onto the north face, where a block at rest looks,
# and turned by Minecraft's own angles.

FURNACE_FRONTS = {"furnace": ("south", ["furnace", "blast_furnace", "smoker", "pumpkin"]),
                  "lit_furnace": ("east", ["lit_furnace", "lit_blast_furnace", "lit_smoker"])}


def furnaces():
    for family, (front, blocks) in FURNACE_FRONTS.items():
        tables.forms(family, {"default": fronted(front)})
        tables.rules(family, turn_by=[{"state": "minecraft:cardinal_direction"}])
        tables.turns(family, "minecraft:cardinal_direction")
        tables.define(blocks, family)


# --- dispensers and droppers -------------------------------------------------------
#
# Facing sideways the front is the south slot, `_front_horizontal`, on the north
# face and the other sides are the north slot. Facing up or down the front is
# the east slot, `_front_vertical`, and every other face is the top, the way
# Java's vertical model has it. The rotation table puts the north face where the
# block faces, so both forms keep their front there.

def dispensers():
    sideways = {face: java.slot("north") for face in ("south", "east", "west")}
    sideways.update(north=java.slot("south"), up=None, down=None)
    upright = {face: java.slot("up") for face in FACES}
    upright["north"] = java.slot("east")
    tables.forms("dispenser", {"default": {"center": MIDDLE, "cubes": [box(sideways)]},
                               "vertical": {"center": MIDDLE, "cubes": [box(upright)]}})
    tables.rules("dispenser", pick=[{"when": {"facing_direction": [0, 1]},
                                     "form": "vertical"}])


# --- glazed terracotta ------------------------------------------------------------
#
# Every face reads the pattern, each turned or flipped the way the game lays the
# pattern round the block. Facing east or west the game turns the bottom the
# other way from the top, which a turned box cannot do, so those two facings
# have a form of their own with the bottom read half round.

def glazed_face(uv, size):
    return {"uv": list(uv), "size": list(size)}


GLAZED = {"north": glazed_face((0, 1), (1, -1)), "south": glazed_face((1, 0), (-1, 1)),
          "east": glazed_face((0, 0), (1, 1)), "west": glazed_face((1, 1), (-1, -1)),
          "up": glazed_face((0, 0), (1, 1)), "down": glazed_face((0, 0), (1, 1))}


## Facing up or down, which only a command or a structure can place, each face
## reads its picture turned, by the face of the form before the block is
## turned: as a world showed facing 1, and the game draws facing 0 the same.
UPRIGHT_TURNS = {"north": 270, "south": 270, "up": 180, "east": 90, "west": 90}


def glazed_turned(face, window, turn):
    """A face reading the block's own picture turned `turn` clockwise as seen.

    A window read backwards one way shows a turned picture turned the other
    way, so its turn is reversed."""
    flipped = (window["size"][0] < 0) != (window["size"][1] < 0)
    return dict(window, texture={"slot": face, "turn": (-turn if flipped else turn) % 360})


def glazed_terracotta():
    def form(down, turns=None):
        faces = dict(GLAZED, down=down)
        for face, turn in (turns or {}).items():
            faces[face] = glazed_turned(face, faces[face], turn)
        return {"center": MIDDLE, "cubes": [{"size": [GHOST] * 3, "offset": [INSET] * 3,
                                             "faces": copy.deepcopy(faces)}]}
    turned = glazed_face((1, 1), (-1, -1))
    upright = form(GLAZED["down"], UPRIGHT_TURNS)
    tables.forms("glazed_terracotta", {"default": form(GLAZED["down"]),
                                       "0": copy.deepcopy(upright), "1": upright,
                                       "4": form(turned), "5": form(turned)})
    tables.rules("glazed_terracotta", data={"number": ["facing_direction"]})
    ## facing 0 is drawn as facing 1
    table = dict(tables.load(tables.ROTATION)["glazed_terracotta"])
    table["0"] = list(table["1"])
    tables.turns("glazed_terracotta", table)


# --- water ---------------------------------------------------------------------------
#
# Water fills its cell a hair short of every side. A waterlogged stair or
# fence shares the cell and is drawn to its edges, and a face of each on the
# same plane flickers; inset, the water sits just inside them.

WATER_INSET = 0.01


## where water's surface stands in a cell with no water above it, as the game
## draws a still source
WATER_SURFACE = 12 / 16.0


def water():
    """Water at its surface, and water with more water above it, which fills
    its cell. Which one is the `scaffold:covered` state core gives water.

    **The sides and the top are families of their own, each in three tiers.**
    Core picks them for the block standing in the water (`core.water_families`):
    `water` and `water_surface` are drawn in the block's own bone, straight
    after it, `water_late` and `water_surface_late` after every plane, and
    `water_surface_early` before everything, for a top that shows through the
    clear texels of the block over it."""
    faces = {face: {"uv": [0, 0], "size": [1, 1]} for face in FACES}
    faces["up"] = {"uv": [0, 0], "size": [0, 0]}

    def box(top):
        return {"center": [0.5, 0.5, 0.5], "cubes": [{
            "size": [1 - 2 * WATER_INSET, round(top - 2 * WATER_INSET, 6), 1 - 2 * WATER_INSET],
            "offset": [WATER_INSET] * 3, "faces": copy.deepcopy(faces)}]}
    for family in ("water", "water_late"):
        tables.forms(family, {"default": box(WATER_SURFACE), "covered": box(1)})
        tables.rules(family, pick=[{"when": {"scaffold:covered": [True]}, "form": "covered"}])
    top = {face: {"uv": [0, 0], "size": [0, 0]} for face in FACES}
    top["up"] = {"uv": [0, 0], "size": [1, 1]}
    surface = {"center": [0.5, 0.5, 0.5], "cubes": [{
        "size": [1 - 2 * WATER_INSET, 0, 1 - 2 * WATER_INSET],
        "offset": [WATER_INSET, round(WATER_SURFACE - WATER_INSET, 6), WATER_INSET],
        "faces": top}]}
    for family in ("water_surface", "water_surface_late", "water_surface_early"):
        tables.forms(family, {"default": copy.deepcopy(surface)})


# --- the observer --------------------------------------------------------------------
#
# The face on the north side, the back on the south, the top on top and the top
# again, mirrored, underneath. Every arrow on it points to the back, where its
# signal leaves: the top's does as it is, the mirrored one underneath does, and a
# side's arrow, which Directional Observers draws pointing right, points to the
# back on the west side as it is and on the east side turned half round. The
# plain side has no arrow and reads the same either way.

def observer():
    read = {face: java.slot(face) for face in FACES}
    read["east"] = {"slot": "east", "turn": 180}
    read["down"] = java.path("textures/blocks/observer_top_mirror")
    cube = box(read)
    ## the top and the bottom read their pictures forwards, as a world showed
    for face in ("up", "down"):
        cube["faces"][face].update(uv=[0, 0], size=[1, 1])
    tables.forms("observer", {"default": {"center": MIDDLE, "cubes": [cube]}})
    tables.rules("observer", data={"join": ["powered_bit"]},
                 turn_by=[{"state": "minecraft:facing_direction"}])


# --- the barrel ---------------------------------------------------------------------
#
# The lid is the north slot. The four faces round it show the staves, which run
# toward the lid, so on the east and west faces the tile is turned a quarter.

def barrel():
    read = {face: None for face in FACES}
    read["east"] = {"slot": "east", "turn": 90}
    read["west"] = {"slot": "west", "turn": 90}
    tables.forms("barrel", {"default": {"center": MIDDLE, "cubes": [box(read)]}})


# --- pillars in the plain cube's family ---------------------------------------------
#
# Basalt, deepslate, froglights, stems and woods share `cube` and carry
# `pillar_axis`, which turns them the way a log turns.

AXIS_TURNS = {"x": [0, 0, 270], "y": [0, 0, 0], "z": [90, 0, 0]}


def pillars():
    turning = dict(tables.load(tables.ROTATION)["cube"])
    turning.update(AXIS_TURNS)
    tables.turns("cube", turning)


# --- planes ------------------------------------------------------------------------
#
# A portal is a picture, not a box: a nether portal one flat plane along its
# axis, seen from both sides, and an end portal a square lying at the height it
# sits in its frame, twelve pixels up.

## Bedrock's end portal picture is a disc; `tools/textures/end_portal.py`
## squares it
END_PORTAL = java.path("textures/blocks/scaffold_end_portal")


def plane(size, offset, shows, texture=None):
    faces = {face: dict(java.NOTHING) for face in FACES}
    for face in shows:
        faces[face] = {"uv": [1, 1], "size": [-1, -1]} if face in ("up", "down")             else {"uv": [0, 0], "size": [1, 1]}
        if texture:
            faces[face]["texture"] = texture
    return {"size": list(size), "offset": list(offset), "faces": faces}


def portals():
    tables.forms("nether_portal", {
        "default": {"center": [0.5] * 3, "cubes": [plane((1, 1, 0), (0, 0, 0.5), ("north", "south"))]},
        "z": {"center": [0.5] * 3, "cubes": [plane((0, 1, 1), (0.5, 0, 0), ("east", "west"))]}})
    tables.rules("nether_portal", pick=[{"when": {"portal_axis": "z"}, "form": "z"}])
    tables.define(["portal"], "nether_portal")
    tables.forms("end_portal", {"default": {"center": [0.5] * 3, "cubes": [
        plane((1, 0, 1), (0, 0.75, 0), ("up", "down"), END_PORTAL)]}})
    tables.define(["end_portal"], "end_portal")


# --- farmland and the dirt path -------------------------------------------------------
#
# Fifteen pixels tall, their sides reading the tile from its second row, since
# the top row of a path's side is empty: Java's `template_farmland` and
# `dirt_path`, which are the same box.

LOW_BLOCK = [{"from": [0, 0, 0], "to": [16, 15, 16], "faces": {
    "down": {"uv": [0, 0, 16, 16]}, "up": {"uv": [0, 0, 16, 16]},
    "north": {"uv": [0, 1, 16, 16]}, "south": {"uv": [0, 1, 16, 16]},
    "west": {"uv": [0, 1, 16, 16]}, "east": {"uv": [0, 1, 16, 16]}}}]


def own(_name):
    return None


def low_blocks():
    tables.forms("farmland", {"default": java.form(LOW_BLOCK, own)})


# --- leaf litter ----------------------------------------------------------------------
#
# Flat planes a quarter of a pixel up, Java's `template_leaf_litter_<n>`: one
# quarter, the west half, the west half and the south east quarter, then all of
# it. `growth` counts them from 0, and everything from 3 up is the whole block.

def litter(x0, z0, x1, z1):
    return {"from": [x0, 0.25, z0], "to": [x1, 0.25, z1], "faces": {
        "up": {"uv": [x0, z0, x1, z1]}, "down": {"uv": [x0, z1, x1, z0]}}}


LITTER = {"0": [litter(0, 0, 8, 8)], "1": [litter(0, 0, 8, 16)],
          "2": [litter(0, 0, 8, 16), litter(8, 8, 16, 16)], "3": [litter(0, 0, 16, 16)]}


def leaf_litter():
    forms = {growth: java.form(elements, own) for growth, elements in LITTER.items()}
    for growth in range(4, 8):
        forms[str(growth)] = copy.deepcopy(forms["3"])
    forms["default"] = copy.deepcopy(forms["0"])
    tables.forms("leaf_litter", forms)
    tables.rules("leaf_litter", data={"number": ["growth"]},
                 turn_by=[{"state": "minecraft:cardinal_direction"}])
    tables.turns("leaf_litter", "minecraft:cardinal_direction")
    tables.define(["leaf_litter"], "leaf_litter")


# --- cakes and candles ---------------------------------------------------------------
#
# Java's `cake`, `cake_slice<n>`, `template_candle` and the rest, every face
# reading its own place on its tile. A bite comes off the west, two pixels at a
# time, and the cut face is what Bedrock declares on a cake's west slot, so a
# whole cake's west face reads the east slot instead. A candle's tile holds the
# candle and its wick; `lit` picks between the unlit and lit picture, which
# Bedrock keeps as a two-entry list, and a candle cake names its candle's file
# outright, since the cake's own declaration has no candle in it.

CAKE_SIDES = ("north", "south", "east")
COLOURS = ["", "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black"]


def cake_box(bites=0):
    x0 = 1 + 2 * bites
    faces = {face: {"texture": "#side"} for face in CAKE_SIDES}
    faces.update({"up": {"texture": "#top"}, "down": {"texture": "#bottom"},
                  "west": {"texture": "#inside" if bites else "#side_east"}})
    return {"from": [x0, 0, 1], "to": [15, 8, 15], "faces": faces}


## Bedrock's `cake_west` is a list, the plain side and then the cut inside, and
## a block reads the first; the cut face names the inside outright
CAKE_INSIDE = java.path("textures/blocks/cake_inner")


def cake_textures(name):
    return {"inside": CAKE_INSIDE, "side_east": java.slot("east")}.get(name)


WICK = {"north": {"uv": [0, 5, 1, 6], "texture": "#all"},
        "south": {"uv": [0, 5, 1, 6], "texture": "#all"}}


def candle(x, z, tall, base=0):
    """One candle two pixels across standing at (x, z), its wick crossed above."""
    side = {"uv": [0, 8, 2, 8 + tall], "texture": "#all"}
    body = {"from": [x, base, z], "to": [x + 2, base + tall, z + 2], "faces": dict(
        north=side, east=side, south=side, west=side,
        up={"uv": [0, 6, 2, 8], "texture": "#all"},
        down={"uv": [0, 14, 2, 16], "texture": "#all"})}
    top = base + tall
    middle = (x + 1, top, z + 1)
    wicks = [{"from": [x + 0.5, top, z + 1], "to": [x + 1.5, top + 1, z + 1],
              "rotation": {"angle": angle, "axis": "y", "origin": list(middle)},
              "faces": WICK} for angle in (45, -45)]
    return [body] + wicks


## where each candle of one to four stands, (x, z, tall), Java's own templates
CANDLES = {1: [(7, 7, 6)], 2: [(5, 7, 5), (9, 6, 6)],
           3: [(7, 9, 3), (5, 7, 5), (8, 6, 6)],
           4: [(6, 8, 3), (9, 8, 5), (5, 5, 5), (8, 5, 6)]}


def cakes():
    forms = {str(bites): java.form([cake_box(bites)], cake_textures) for bites in range(7)}
    forms["default"] = copy.deepcopy(forms["0"])
    tables.forms("cake", forms)
    tables.rules("cake", data={"number": ["bite_counter"]})

    forms = {}
    for count, standing in CANDLES.items():
        elements = []
        for x, z, tall in standing:
            elements += candle(x, z, tall)
        forms[str(count - 1)] = java.form(elements, own)
    forms["default"] = copy.deepcopy(forms["0"])
    tables.forms("candle", forms)
    tables.rules("candle", data={"number": ["candles"]},
                 texture_by={"state": "lit", "values": {"0": 0, "1": 1}})

    for colour in COLOURS:
        name = (colour + "_candle") if colour else "candle"
        family = "candle_cake_" + (colour or "plain")
        forms = {}
        for lit, suffix in (("default", ""), ("1", "_lit")):
            picture = java.path("textures/blocks/candles/%s%s" % (name, suffix))
            forms[lit] = java.form([cake_box()] + candle(7, 7, 6, base=8),
                                   lambda n, picture=picture: picture if n == "all"
                                   else cake_textures(n))
        tables.forms(family, forms)
        tables.rules(family, data={"join": ["lit"]})
        tables.define([name + "_cake"], family)


# --- whole blocks whose picture follows a state ---------------------------------------
#
# The plain box, its picture picked from the list the block declares by a state
# of its own: a copper bulb's four by whether it is lit and powered, in Bedrock's
# order, and a respawn anchor's five by its charge.

BULBS = [age + "copper_bulb" for age in ("", "exposed_", "weathered_", "oxidized_")]
BULBS += ["waxed_" + bulb for bulb in BULBS]


def pictured():
    plain = {"default": {"center": MIDDLE, "cubes": [box({})]}}
    tables.forms("copper_bulb", copy.deepcopy(plain))
    tables.rules("copper_bulb", texture_by={"join": ["lit", "powered_bit"], "values": {
        "0-0": 0, "1-0": 1, "0-1": 2, "1-1": 3}})
    tables.define(BULBS, "copper_bulb")
    tables.forms("respawn_anchor", copy.deepcopy(plain))
    tables.rules("respawn_anchor", texture_by={"state": "respawn_anchor_charge"})
    tables.define(["respawn_anchor"], "respawn_anchor")


# --- amethyst ------------------------------------------------------------------------
#
# Buds and clusters are the crossed plant, pointing out of the face of the block
# they grew on, which `minecraft:block_face` names: up when they stand on the
# floor, down hanging from a ceiling, and the four sides on a wall.

AMETHYST = ["small_amethyst_bud", "medium_amethyst_bud", "large_amethyst_bud",
            "amethyst_cluster"]
POINTING = {"up": [0, 0, 0], "down": [180, 0, 0], "north": [90, 0, 0],
            "south": [270, 0, 0], "west": [0, 0, 270], "east": [0, 0, 90]}


def amethyst():
    crossed = copy.deepcopy(tables.load(tables.SHAPES)["cross_texture"])
    windows = copy.deepcopy(tables.load(tables.UV)["cross_texture"])
    tables.put(tables.SHAPES, "amethyst", {"default": crossed["default"]})
    tables.put(tables.UV, "amethyst", {"default": windows["default"]})
    tables.rules("amethyst", turn_by=[{"state": "minecraft:block_face"}])
    tables.turns("amethyst", POINTING)
    tables.define(AMETHYST, "amethyst")


def main():
    print("writing the blocks drawn the way Minecraft draws them")
    amethyst()
    pictured()
    cakes()
    portals()
    low_blocks()
    leaf_litter()
    furnaces()
    dispensers()
    water()
    observer()
    glazed_terracotta()
    barrel()
    pillars()


if __name__ == "__main__":
    main()
