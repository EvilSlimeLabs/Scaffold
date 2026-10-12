"""Blocks drawn from the Java edition's own block model.

    python -m tools.blocks.models

Every family here is Java's model for the block, converted by
`tools/blocks/java.py` from the elements kept in `tools/blocks/java_models.py`,
reading Bedrock's own textures. A Java texture is read as the Bedrock file of
the same name unless a family says otherwise, and the rules that pick a form
are Bedrock's states. A model that rests facing south in Java is turned half
round, so that every family rests facing north.

Nothing here is needed at run time.
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import java, tables


def own(_java_texture):
    """Every face reads what the block declares for it."""
    return None


def files(renamed=None):
    """Every face reads the Bedrock file its Java texture is, by name."""
    return lambda texture: java.bedrock(texture, renamed)


def slots(**by_name):
    """Faces read a slot of the block's own, by the Java texture's short name."""
    return lambda texture: java.slot(by_name[texture.split("/")[-1]]) \
        if texture and texture.split("/")[-1] in by_name else None


## a form of no cubes, for a state that shows nothing: one cube with no face
## drawn, which `make_block` leaves out
EMPTY = {"center": [0.5, 0.5, 0.5], "cubes": [{"size": [0, 0, 0], "offset": [0, 0, 0],
         "faces": {face: dict(java.NOTHING) for face in
                   ("north", "south", "east", "west", "up", "down")}}]}


def write(family, forms, blocks=None, keep_empty=(), **rules):
    ## a form with nothing in it is a state the game never leaves a block in --
    ## a wall with neither post nor sides, growth on no face -- and is left
    ## out, so the default form stands in for it
    forms = {name: form for name, form in forms.items()
             if form["cubes"] or name in keep_empty}
    forms.setdefault("default", copy.deepcopy(next(iter(forms.values()))))
    tables.forms(family, forms)
    if rules:
        tables.rules(family, **rules)
    if blocks:
        tables.define(blocks, family)


# --- small plants ---------------------------------------------------------------------

def turtle_eggs():
    """One to four eggs, the picture by how cracked they are."""
    counts = {"one_egg": "template_turtle_egg", "two_egg": "template_two_turtle_eggs",
              "three_egg": "template_three_turtle_eggs", "four_egg": "template_four_turtle_eggs"}
    write("turtle_egg", {count: java.model(name, own) for count, name in counts.items()},
          ["turtle_egg"], data={"join": ["turtle_egg_count"]},
          texture_by={"state": "cracked_state", "values": {
              "no_cracks": 0, "cracked": 1, "max_cracked": 2}})


def sea_pickles():
    """One to four pickles, `cluster_count` counting from 0."""
    counts = ["sea_pickle", "two_sea_pickles", "three_sea_pickles", "four_sea_pickles"]
    ## the top's hole is filled by `tools/textures/filled.py`, which the
    ## plane Java draws under it would do, and which a ghost cannot draw
    filled = files({"sea_pickle": "scaffold_sea_pickle"})
    write("sea_pickle", {str(n): java.model(name, filled, buried=False)
                         for n, name in enumerate(counts)},
          ["sea_pickle"], data={"number": ["cluster_count"]})


## Bedrock's grown pod picture is a seven pixel top and a side from x 7, where
## Java's current one is eight and from x 8; read with Java's windows the pod
## shows an empty strip
COCOA_WINDOWS = {2: {"side": [7, 4, 15, 13], "top": [0, 0, 7, 7]}}


## a world showed the pod and its stem half a turn from the numbered
## `direction` angles: `direction` names the side of the pod the log is not on
COCOA_TURNS = {"0": [0, 0, 0], "1": [0, 270, 0], "2": [0, 180, 0], "3": [0, 90, 0]}


def cocoa_elements(age):
    """Java's pod at one age, read the way Bedrock's pictures are laid out."""
    from tools.blocks.java_models import MODELS
    pod, stem = copy.deepcopy(MODELS["cocoa_stage%d" % age]["elements"])
    windows = COCOA_WINDOWS.get(age)
    if windows:
        for face, spec in pod["faces"].items():
            spec["uv"] = list(windows["top" if face in ("up", "down") else "side"])
    return [pod, stem]


def cocoa():
    """A pod on the side of a jungle log, the log to its south, larger with age."""
    forms = {str(age): java.form(cocoa_elements(age), lambda var, age=age: java.path(
        "textures/blocks/cocoa_stage_%d" % age)) for age in range(3)}
    write("cocoa", forms, ["cocoa"], data={"number": ["age"]},
          turn_by=[{"state": "direction"}])
    tables.turns("cocoa", COCOA_TURNS)


def spore_blossom():
    """A base under the ceiling, and the flower's four petals hanging from it."""
    write("spore_blossom", {"default": java.model("spore_blossom", files())}, ["spore_blossom"])


def azalea():
    """A bush: a top and four sides open underneath, the plant crossed inside.

    The top, the side and the plant are what each azalea declares on its up,
    north and east slots, so a flowering one wears its own."""
    ## the template names its textures by role, which the azalea model fills
    write("azalea", {"default": java.model("template_azalea", slots(
        top="up", side="north", azalea_plant="east"))},
        blocks=["azalea", "flowering_azalea"])


# --- tall plants ---------------------------------------------------------------------

DRIPLEAF = {"big_dripleaf_top": "big_dripleaf_top", "big_dripleaf_side": "big_dripleaf_side1",
            "big_dripleaf_tip": "big_dripleaf_side2", "big_dripleaf_stem": "big_dripleaf_stem"}


def big_dripleaf():
    """A head, tilted by how long something has stood on it, over a stem.

    `big_dripleaf_head` says which; `big_dripleaf_tilt` how far the head has
    gone over, and an unstable leaf has not moved yet."""
    leaf = files(DRIPLEAF)
    ## named by head and tilt joined; a stem carries a tilt too, and shows none
    heads = {"none": "big_dripleaf", "unstable": "big_dripleaf",
             "partial_tilt": "big_dripleaf_partial_tilt",
             "full_tilt": "big_dripleaf_full_tilt"}
    forms = {}
    for tilt, head in heads.items():
        forms["0-" + tilt] = java.model("big_dripleaf_stem", leaf)
        forms["1-" + tilt] = java.model(head, leaf)
    forms["default"] = copy.deepcopy(forms["1-none"])
    write("big_dripleaf", forms, ["big_dripleaf"],
          data={"join": ["big_dripleaf_head", "big_dripleaf_tilt"]},
          turn_by=[{"state": "minecraft:cardinal_direction"}])
    tables.turns("big_dripleaf", "minecraft:cardinal_direction")


## Java's small dripleaf rests a quarter anticlockwise of north, which a world
## showed; it is turned back here so the family rests facing north
SMALL_DRIPLEAF_TURN = 90


def small_dripleaf():
    write("small_dripleaf", {"default": java.model("small_dripleaf_bottom", files(),
                                                   y=SMALL_DRIPLEAF_TURN),
                             "top": java.model("small_dripleaf_top", files(),
                                               y=SMALL_DRIPLEAF_TURN)},
          ["small_dripleaf_block"],
          pick=[{"when": {"upper_block_bit": True}, "form": "top"}],
          turn_by=[{"state": "minecraft:cardinal_direction"}])
    tables.turns("small_dripleaf", "minecraft:cardinal_direction")


def pitcher_crop():
    """The bulb and the plant growing from it, `growth` up to its fifth stage,
    the upper block from its fourth."""
    forms = {}
    for growth in range(8):
        stage = min(growth, 4)
        forms[str(growth)] = java.model("pitcher_crop_bottom_stage_%d" % stage, files())
        top = java.model("pitcher_crop_top_stage_%d" % stage, files())
        ## the upper block is there from the start and shows nothing until the
        ## plant reaches it
        forms["top-%d" % growth] = top if top["cubes"] else copy.deepcopy(EMPTY)
    forms["top"] = copy.deepcopy(forms["top-4"])
    forms["default"] = copy.deepcopy(forms["0"])
    write("pitcher_crop", forms, ["pitcher_crop"],
          pick=[{"when": {"upper_block_bit": True}, "form": "top"}],
          data={"number": ["growth"]})


BAMBOO = {"bamboo_stalk": "bamboo_stem", "bamboo_small_leaves": "bamboo_small_leaf",
          "bamboo_large_leaves": "bamboo_leaf"}


def bamboo():
    """A stalk two pixels across, or three when thick, and its leaves."""
    stalks = {"thin": "bamboo1_age0", "thick": "bamboo1_age1"}
    leaves = {"no_leaves": None, "small_leaves": "bamboo_small_leaves",
              "large_leaves": "bamboo_large_leaves"}
    forms = {}
    for thickness, stalk in stalks.items():
        for size, leaf in leaves.items():
            form = java.model(stalk, files(BAMBOO))
            if leaf:
                form["cubes"] += java.model(leaf, files(BAMBOO))["cubes"]
            forms["%s-%s" % (thickness, size)] = form
    forms["default"] = copy.deepcopy(forms["thin-no_leaves"])
    write("bamboo", forms, ["bamboo"],
          data={"join": ["bamboo_stalk_thickness", "bamboo_leaf_size"]})


def chorus_plant():
    """The middle of a chorus plant: Bedrock keeps no record of which way its
    branches go, so it is drawn as its core."""
    core = [element for element in java_models_of("chorus_plant")
            if element["from"] == [2, 2, 2]]
    write("chorus_plant", {"default": java.form(core, lambda name: None)}, ["chorus_plant"])


## Java's `cross`: two planes crossed through the middle, reaching the corners
CROSS = [
    {"from": [0.8, 0, 8], "to": [15.2, 16, 8],
     "rotation": {"origin": [8, 8, 8], "axis": "y", "angle": 45, "rescale": True},
     "faces": {"north": {"uv": [0, 0, 16, 16], "texture": "#cross"},
               "south": {"uv": [0, 0, 16, 16], "texture": "#cross"}}},
    {"from": [8, 0, 0.8], "to": [8, 16, 15.2],
     "rotation": {"origin": [8, 8, 8], "axis": "y", "angle": 45, "rescale": True},
     "faces": {"west": {"uv": [0, 0, 16, 16], "texture": "#cross"},
               "east": {"uv": [0, 0, 16, 16], "texture": "#cross"}}},
]
SUNFLOWER = {"sunflower_top": None, "sunflower_front": "double_plant_sunflower_front",
             "sunflower_back": "double_plant_sunflower_back"}


def sunflower():
    """A stem below, and above it the top of the stem with the flower's head
    leaning back off it, yellow to the east and green behind, as Java's
    `sunflower_top` is. The stem reads the block's own up and down slots."""
    top = lambda texture: java.slot("up") if texture and texture.endswith("sunflower_top")         else java.bedrock(texture, SUNFLOWER)
    write("sunflower", {"default": java.form(CROSS, lambda name: java.slot("down")),
                        "top": java.model("sunflower_top", top)}, ["sunflower"],
          pick=[{"when": {"upper_block_bit": True}, "form": "top"}])


STEMS = {"pumpkin_stem": "pumpkin_stem", "melon_stem": "melon_stem"}
## the short crossed stem an attached stem keeps, Java's, and the bent stem
## beside it: Bedrock's `_connected` picture is the whole bend, sixteen across,
## so it is one plane the width of the block, bent toward the west at rest
BENT = {"from": [0, 0, 8], "to": [16, 16, 8], "faces": {
    "north": {"uv": [16, 0, 0, 16], "texture": "#connected"},
    "south": {"uv": [0, 0, 16, 16], "texture": "#connected"}}}


def stems():
    """A stem grows taller with `growth`, showing the top of its picture, and
    bends to its fruit once there is one, which `facing_direction` names; down
    is no fruit."""
    from tools.blocks.java_models import MODELS
    for family, block in STEMS.items():
        straight = lambda texture: java.slot("up") if texture else None
        forms = {str(growth): java.model("stem_growth%d" % growth, straight)
                 for growth in range(8)}
        pictures = {"stem": java.path("textures/blocks/%s_disconnected" % block),
                    "connected": java.path("textures/blocks/%s_connected" % block)}
        crossed = MODELS["attached_" + block]["elements"][:2]
        attached = java.form(crossed + [BENT], pictures.get)
        ## a form is read by mounting and growth before growth alone, so the
        ## bent stem is there under every growth
        for growth in range(8):
            forms["attached-%d" % growth] = copy.deepcopy(attached)
        forms["default"] = copy.deepcopy(forms["0"])
        write(family, forms, [block],
              pick=[{"when": {"facing_direction": [2, 3, 4, 5]}, "form": "attached"}],
              data={"number": ["growth"]},
              turn_by=[{"state": "facing_direction"}], texture_by=None)
        ## the attached stem rests bent toward the west
        tables.turns(family, {"4": [0, 0, 0], "2": [0, 270, 0], "3": [0, 90, 0],
                              "5": [0, 180, 0]})


# --- plants in a flower pot ------------------------------------------------------------
#
# A pot draws what it holds as the plant's own block, marked `scaffold:potted`,
# and a family with a `potted` form draws it the size it is in a pot, standing
# on the soil: Java's `flower_pot_cross` for every crossed plant, and the potted
# bamboo and cactus their own. The pot's own pieces are left out of each, since
# the pot is drawn already.
POTTED = {"cross_texture": "flower_pot_cross", "bamboo": "potted_bamboo",
          "cactus": "potted_cactus"}
POT_TEXTURES = ("block/flower_pot", "block/dirt")
POTTED_PLANT = {"bamboo_stalk": "bamboo_stem", "bamboo_singleleaf": "bamboo_singleleaf",
                "cactus_side": None, "cactus_top": None}


def potted():
    from tools.blocks.java_models import MODELS
    document = tables._read(tables.GEOMETRY)["families"]
    for family, name in POTTED.items():
        found = MODELS[name]
        plant = [element for element in found["elements"]
                 if not any(java.resolved(found["textures"], face.get("texture", "#")[1:])
                            in POT_TEXTURES for face in element["faces"].values())]
        if family == "cactus":
            read = lambda texture: java.slot("up") if texture and texture.endswith("top")                 else None
        elif family == "cross_texture":
            read = lambda texture: None
        else:
            read = lambda texture: java.bedrock(texture, POTTED_PLANT)
        forms = copy.deepcopy(document[family]["forms"])
        forms["potted"] = java.form(plant, lambda var, f=found, r=read: r(
            java.resolved(f["textures"], var)))
        tables.forms(family, forms)
        rules = document[family]
        pick = [rule for rule in rules.get("pick", ()) if rule["form"] != "potted"]
        tables.rules(family, pick=[{"when": {"scaffold:potted": True}, "form": "potted"}] + pick)


# --- things that grow flat on the faces of a block -------------------------------------
#
# Vines, glow lichen, sculk veins and resin: a plane with no thickness on each
# face the block covers, as far off the wall as Java sets it, unmirrored seen
# from inside the cell and mirrored from behind. Which faces are covered is a
# bitmask, Bedrock's own order: a vine's `vine_direction_bits` south 1, west 2,
# north 4, east 8, and `multi_face_direction_bits` down 1, up 2, south 4, west
# 8, north 16, east 32. A vine on no side hangs from the block above.

def face_plane(face, away):
    """A plane `away` blocks in from one face of the cell, seen from inside."""
    near, far = away, 1 - away
    across = {"uv": [0, 0], "size": [1, 1]}
    behind = {"uv": [1, 0], "size": [-1, 1]}
    flat_up = {"uv": [1, 1], "size": [-1, -1]}
    flat_down = {"uv": [0, 1], "size": [1, -1]}
    laid = {
        "north": ((1, 1, 0), (0, 0, near), "south", "north", across, behind),
        "south": ((1, 1, 0), (0, 0, far), "north", "south", across, behind),
        ## east is the low side of x
        "east": ((0, 1, 1), (near, 0, 0), "west", "east", across, behind),
        "west": ((0, 1, 1), (far, 0, 0), "east", "west", across, behind),
        "down": ((1, 0, 1), (0, near, 0), "up", "down", flat_up, flat_down),
        "up": ((1, 0, 1), (0, far, 0), "down", "up", flat_up, flat_down),
    }
    size, offset, seen, back, front_read, back_read = laid[face]
    faces = {other: dict(java.NOTHING) for other in java.FACES}
    faces[seen] = dict(front_read)
    faces[back] = dict(back_read)
    return {"size": list(size), "offset": [round(v, 6) for v in offset], "faces": faces}


VINE_BITS = ["south", "west", "north", "east"]
MULTI_BITS = ["down", "up", "south", "west", "north", "east"]


def multiface(bits, away, hanging=None):
    forms = {}
    for mask in range(1 << len(bits)):
        covered = [face for n, face in enumerate(bits) if mask >> n & 1] or (
            [hanging] if hanging else [])
        forms[str(mask)] = {"center": [0.5] * 3,
                            "cubes": [face_plane(face, away) for face in covered]}
    forms["default"] = copy.deepcopy(forms["1"])
    return forms


def flat_growth():
    write("vine", multiface(VINE_BITS, 0.8 / 16, hanging="up"), ["vine"],
          data={"number": ["vine_direction_bits"]}, turn_by=None)
    tables.unturn("vine")
    write("vine-multi", multiface(MULTI_BITS, 0.1 / 16),
          ["glow_lichen", "sculk_vein", "resin_clump"],
          data={"number": ["multi_face_direction_bits"]})
    ## a ladder is a vine's plane on one wall, the south wall at rest, turned by
    ## its facing
    write("ladder", {"default": {"center": [0.5] * 3,
                                 "cubes": [face_plane("south", 0.8 / 16)]}},
          ["ladder"], turn_by=[{"state": "facing_direction"}])


# --- torches ---------------------------------------------------------------------------
#
# Java's torch, two pixels across and ten tall, standing or leaning out from a
# wall. `torch_facing_direction` is the way a torch on a wall leans, away from
# the wall; Java's wall torch rests leaning east. Every torch is this shape:
# its picture is what tells a redstone torch from a soul torch.

TORCHES = ["torch", "soul_torch", "redstone_torch", "unlit_redstone_torch", "copper_torch",
           "underwater_torch", "colored_torch_blue", "colored_torch_purple",
           "colored_torch_red", "colored_torch_green"]


def torches():
    write("torch", {"default": java.model("template_torch", own),
                    "wall": java.model("template_torch_wall", own)}, TORCHES,
          pick=[{"when": {"torch_facing_direction": ["north", "south", "east", "west"]},
                 "form": "wall"}],
          turn_by=[{"state": "torch_facing_direction"}])
    tables.turns("torch", {"top": [0, 0, 0], "east": [0, 0, 0], "north": [0, 90, 0],
                           "west": [0, 180, 0], "south": [0, 270, 0]})


# --- repeaters and comparators ------------------------------------------------------
#
# Java's, turned to rest facing north. Bedrock tells a powered one from an
# unpowered one by its id, so each is two families of one shape: the powered
# one wears the lit board and lit torches.

def board(lit, top):
    pictures = {"repeater": "repeater_on" if lit else "repeater_off",
                "comparator": "comparator_on" if lit else "comparator_off",
                "smooth_stone": "stone_slab_top", "redstone_torch": "redstone_torch_on",
                "redstone_torch_off": "redstone_torch_off"}
    return files(pictures)


def redstone_components():
    for lit, (repeater, comparator) in ((False, ("repeater", "comparator")),
                                        (True, ("repeater_on", "comparator_on"))):
        suffix = "_on" if lit else ""
        write(repeater, {str(delay): java.model("repeater_%dtick%s" % (delay + 1, suffix),
                                                board(lit, "repeater"), half_turn=True)
                         for delay in range(4)},
              ["powered_repeater" if lit else "unpowered_repeater"],
              data={"number": ["repeater_delay"]},
              turn_by=[{"state": "minecraft:cardinal_direction"}])
        tables.turns(repeater, "minecraft:cardinal_direction")
        name = "comparator_on" if lit else "comparator"
        write(comparator, {"0": java.model(name, board(lit, "comparator"), half_turn=True),
                           "1": java.model(name + "_subtract", board(lit, "comparator"),
                                           half_turn=True)},
              ["powered_comparator" if lit else "unpowered_comparator"],
              data={"number": ["output_subtract_bit"]},
              turn_by=[{"state": "minecraft:cardinal_direction"}])
        tables.turns(comparator, "minecraft:cardinal_direction")


# --- buttons ---------------------------------------------------------------------------
#
# Java's button, six by four and two tall, one tall pressed, resting on the
# floor with its long side across x. `facing_direction` is the way it points
# out from what it is fixed to: up on a floor, down under a ceiling, and the
# four sides on a wall, its long side kept level.

BUTTON_TURNS = {"1": [0, 0, 0], "0": [180, 0, 0], "2": [90, 0, 0], "3": [270, 0, 0],
                "4": [270, 270, 0], "5": [270, 90, 0]}


def buttons():
    write("button", {"0": java.model("button", own), "1": java.model("button_pressed", own)},
          data={"number": ["button_pressed_bit"]},
          turn_by=[{"state": "facing_direction"}])
    tables.turns("button", BUTTON_TURNS)


# --- blocks that join their neighbours ---------------------------------------------------
#
# Fences, panes, bars, walls and string are a post with a piece reaching out to
# each side they join, as Java's multipart blockstates put them together, each
# piece turned to its side with its picture kept where it is in the world. The
# current game records which sides join in `minecraft:connection_<side>`, a wall
# in `wall_connection_type_<side>` and `wall_post_bit`; the forms are every
# combination, named by the values joined in the order north, east, south, west.

SIDES = ["north", "east", "south", "west"]
TURN = {"north": 0, "east": 90, "south": 180, "west": 270}


def combinations(choices, count):
    found = [[]]
    for _ in range(count):
        found = [done + [choice] for done in found for choice in choices]
    return found


def joined(family, blocks, form_of, choices, states, read):
    forms = {}
    for picked in combinations(choices, len(states)):
        pieces = form_of(dict(zip(states, picked)))
        forms["-".join(picked)] = java.form(java.parts(pieces, None), read)
    forms["default"] = copy.deepcopy(forms["-".join(choice_default(choices)
                                                    for _ in states)])
    write(family, forms, blocks, data={"join": states})


def choice_default(choices):
    return choices[0]


def connected(prefix="minecraft:connection_"):
    return [prefix + side for side in SIDES]


def fence(on):
    pieces = [("fence_post", 0, 0, False)]
    for side in SIDES:
        if on[connected()[SIDES.index(side)]] == "1":
            pieces.append(("fence_side", 0, TURN[side], True))
    return pieces


def pane(on, post, side, side_alt, noside, noside_alt):
    """Java's `glass_pane` multipart: the post, a side toward each join, and a
    cap toward each side that does not join."""
    north, east, south, west = (on[state] == "1" for state in connected())
    pieces = [(post, 0, 0, False)]
    pieces += [(side, 0, 0, False)] if north else [(noside, 0, 0, False)]
    pieces += [(side, 0, 90, False)] if east else [(noside_alt, 0, 0, False)]
    pieces += [(side_alt, 0, 0, False)] if south else [(noside_alt, 0, 90, False)]
    pieces += [(side_alt, 0, 90, False)] if west else [(noside, 0, 270, False)]
    return pieces


def bars(on):
    """Java's `iron_bars` multipart: the ends of the post always, the post when
    nothing joins, a cap where one side alone does, and a side toward each join."""
    north, east, south, west = (on[state] == "1" for state in connected())
    pieces = [("iron_bars_post_ends", 0, 0, False)]
    if not (north or east or south or west):
        pieces.append(("iron_bars_post", 0, 0, False))
    alone = {(True, False, False, False): ("iron_bars_cap", 0),
             (False, True, False, False): ("iron_bars_cap", 90),
             (False, False, True, False): ("iron_bars_cap_alt", 0),
             (False, False, False, True): ("iron_bars_cap_alt", 90)}
    if (north, east, south, west) in alone:
        name, turn = alone[(north, east, south, west)]
        pieces.append((name, 0, turn, False))
    if north:
        pieces.append(("iron_bars_side", 0, 0, False))
    if east:
        pieces.append(("iron_bars_side", 0, 90, False))
    if south:
        pieces.append(("iron_bars_side_alt", 0, 0, False))
    if west:
        pieces.append(("iron_bars_side_alt", 0, 90, False))
    return pieces


WALL_SIDES = ["wall_connection_type_" + side for side in SIDES]


def wall(on):
    pieces = [("template_wall_post", 0, 0, False)] if on["wall_post_bit"] == "1" else []
    for side, state in zip(SIDES, WALL_SIDES):
        if on[state] == "short":
            pieces.append(("template_wall_side", 0, TURN[side], True))
        elif on[state] == "tall":
            pieces.append(("template_wall_side_tall", 0, TURN[side], True))
    return pieces


def by_name(**names):
    """Faces read a slot of the block, by the Java texture variable's name."""
    return lambda texture: java.slot(names[texture]) if texture in names else None


def blocks_of(family):
    import json
    return [block for block, named in tables.definitions().items() if named == family]


def joining():
    yes_no = ["0", "1"]
    joined("fence", blocks_of("fence"), fence, yes_no, connected(), own)
    joined("pane", blocks_of("pane"), lambda on: pane(
        on, "template_glass_pane_post", "template_glass_pane_side",
        "template_glass_pane_side_alt", "template_glass_pane_noside",
        "template_glass_pane_noside_alt"), yes_no, connected(),
        by_name(pane="north", edge="east"))
    joined("bars", ["iron_bars", "copper_bars"] + [
        age + "copper_bars" for age in ("exposed_", "weathered_", "oxidized_", "waxed_",
                                        "waxed_exposed_", "waxed_weathered_", "waxed_oxidized_")],
        bars, yes_no, connected(), lambda texture: java.slot(
            "east" if texture and texture.endswith("edge") else "north"))
    walls = [["0", "1"]] + [["none", "short", "tall"]] * 4
    forms = {}
    for picked in [[a, b, c, d, e] for a in walls[0] for b in walls[1] for c in walls[2]
                   for d in walls[3] for e in walls[4]]:
        on = dict(zip(["wall_post_bit"] + WALL_SIDES, picked))
        forms["-".join(picked)] = java.form(java.parts(wall(on), None), own)
    forms["default"] = copy.deepcopy(forms["1-none-none-none-none"])
    write("wall", forms, blocks_of("wall"), data={"join": ["wall_post_bit"] + WALL_SIDES})


# --- stairs --------------------------------------------------------------------------
#
# Java's straight, inner and outer stair, turned and turned over the way its
# blockstate does for each facing, half and corner, with the picture kept where
# it is in the world, so the grain of a wooden stair runs the same way as the
# planks beside it whichever way the stair faces. Every case is a form of its
# own and nothing is turned at draw time. Bedrock's `weirdo_direction` counts
# east, west, south, north; a stair saved before `minecraft:corner` existed has
# none and is straight.

STAIR_MODELS = {"straight": "stairs", "inner": "inner_stairs", "outer": "outer_stairs"}
STAIR_FACING = {"0": "east", "1": "west", "2": "south", "3": "north"}
STAIR_HALF = {"0": "bottom", "1": "top"}
STAIR_CORNER = {"none": "straight", "inner_left": "inner_left",
                "inner_right": "inner_right", "outer_left": "outer_left",
                "outer_right": "outer_right"}
## Java's own blockstate for a stair: (model, x, y, uvlock) per facing, half
## and shape
STAIR_VARIANTS = {
    "east,bottom,inner_left": ("inner", 0, 270, True), "east,bottom,inner_right": ("inner", 0, 0, False),
    "east,bottom,outer_left": ("outer", 0, 270, True), "east,bottom,outer_right": ("outer", 0, 0, False),
    "east,bottom,straight": ("straight", 0, 0, False), "east,top,inner_left": ("inner", 180, 0, True),
    "east,top,inner_right": ("inner", 180, 90, True), "east,top,outer_left": ("outer", 180, 0, True),
    "east,top,outer_right": ("outer", 180, 90, True), "east,top,straight": ("straight", 180, 0, True),
    "north,bottom,inner_left": ("inner", 0, 180, True), "north,bottom,inner_right": ("inner", 0, 270, True),
    "north,bottom,outer_left": ("outer", 0, 180, True), "north,bottom,outer_right": ("outer", 0, 270, True),
    "north,bottom,straight": ("straight", 0, 270, True), "north,top,inner_left": ("inner", 180, 270, True),
    "north,top,inner_right": ("inner", 180, 0, True), "north,top,outer_left": ("outer", 180, 270, True),
    "north,top,outer_right": ("outer", 180, 0, True), "north,top,straight": ("straight", 180, 270, True),
    "south,bottom,inner_left": ("inner", 0, 0, False), "south,bottom,inner_right": ("inner", 0, 90, True),
    "south,bottom,outer_left": ("outer", 0, 0, False), "south,bottom,outer_right": ("outer", 0, 90, True),
    "south,bottom,straight": ("straight", 0, 90, True), "south,top,inner_left": ("inner", 180, 90, True),
    "south,top,inner_right": ("inner", 180, 180, True), "south,top,outer_left": ("outer", 180, 90, True),
    "south,top,outer_right": ("outer", 180, 180, True), "south,top,straight": ("straight", 180, 90, True),
    "west,bottom,inner_left": ("inner", 0, 90, True), "west,bottom,inner_right": ("inner", 0, 180, True),
    "west,bottom,outer_left": ("outer", 0, 90, True), "west,bottom,outer_right": ("outer", 0, 180, True),
    "west,bottom,straight": ("straight", 0, 180, True), "west,top,inner_left": ("inner", 180, 180, True),
    "west,top,inner_right": ("inner", 180, 270, True), "west,top,outer_left": ("outer", 180, 180, True),
    "west,top,outer_right": ("outer", 180, 270, True), "west,top,straight": ("straight", 180, 180, True),
}


def stairs():
    read = by_name(top="up", bottom="down", side="north")
    forms = {}
    for direction, facing in STAIR_FACING.items():
        for half_bit, half in STAIR_HALF.items():
            for corner, shape in STAIR_CORNER.items():
                kind, x, y, uvlock = STAIR_VARIANTS["%s,%s,%s" % (facing, half, shape)]
                drawn = java.form(java.parts([(STAIR_MODELS[kind], x, y, uvlock)], None), read)
                forms["%s-%s-%s" % (direction, half_bit, corner)] = drawn
            forms["%s-%s" % (direction, half_bit)] = copy.deepcopy(
                forms["%s-%s-none" % (direction, half_bit)])
    forms["default"] = copy.deepcopy(forms["3-0-none"])
    write("stairs", forms, data={"join": ["weirdo_direction", "upside_down_bit",
                                          "minecraft:corner"]},
          pick=None, turn_by=None)
    tables.unturn("stairs")


# --- string and its hooks ------------------------------------------------------------
#
# Java's string, a strip along each way the wire runs, low on the ground and
# raised where hooks hold it, chosen from `attached_bit` and the joins the
# current game records; and Java's hook, its ring turned down when string is
# attached and level when that string is pulled. The strips are a pixel wide
# rather than Java's half, and read `scaffold_string`, which
# `tools/textures/string.py` draws to be seen through a ghost.

STRING = "textures/blocks/scaffold_string"
STRING_WIDE = 0.5
## Java's blockstate for string: (model, y) by attached and the joins north,
## east, south, west
TRIPWIRE_VARIANTS = {
    "f,ffff": ("tripwire_ns", 0), "f,ffft": ("tripwire_n", 270), "f,fftf": ("tripwire_n", 180),
    "f,fftt": ("tripwire_ne", 180), "f,tfff": ("tripwire_n", 0), "f,tfft": ("tripwire_ne", 270),
    "f,tftf": ("tripwire_ns", 0), "f,tftt": ("tripwire_nse", 180), "f,ftff": ("tripwire_n", 90),
    "f,ftft": ("tripwire_ns", 90), "f,fttf": ("tripwire_ne", 90), "f,fttt": ("tripwire_nse", 90),
    "f,ttff": ("tripwire_ne", 0), "f,ttft": ("tripwire_nse", 270), "f,tttf": ("tripwire_nse", 0),
    "f,tttt": ("tripwire_nsew", 0),
}


def widened(elements):
    """String strips a pixel wide, about the line Java draws them on."""
    out = []
    for element in elements:
        element = copy.deepcopy(element)
        a, b = element["from"], element["to"]
        for axis in (0, 2):
            if abs(b[axis] - a[axis]) == 0.5:
                middle = (a[axis] + b[axis]) / 2
                a[axis], b[axis] = middle - STRING_WIDE, middle + STRING_WIDE
        out.append(element)
    return out


def string():
    forms = {}
    for attached in ("0", "1"):
        for joins in combinations(["0", "1"], 4):
            key = "%s,%s" % ("f", "".join("t" if j == "1" else "f" for j in joins))
            name, turn = TRIPWIRE_VARIANTS[key]
            if attached == "1":
                name = name.replace("tripwire_", "tripwire_attached_")
            from tools.blocks.java_models import MODELS
            elements = java.turned(widened(MODELS[name]["elements"]), 0, turn)
            forms["%s-%s" % (attached, "-".join(joins))] = java.form(
                elements, lambda var: java.path(STRING))
    forms["default"] = copy.deepcopy(forms["0-0-0-0-0"])
    write("tripwire", forms, ["trip_wire"],
          data={"join": ["attached_bit"] + connected()})


def hooks():
    read = {"tripwire_hook": java.slot("north"), "oak_planks": java.slot("down"),
            "tripwire": java.path(STRING)}
    named = lambda texture: read.get((texture or "").split("/")[-1])
    forms = {"0-0": java.model("tripwire_hook", named),
             "1-0": java.model("tripwire_hook_attached", named),
             "0-1": java.model("tripwire_hook_on", named),
             "1-1": java.model("tripwire_hook_attached_on", named)}
    write("tripwire_hook", forms, ["tripwire_hook"],
          data={"join": ["attached_bit", "powered_bit"]},
          turn_by=[{"state": "direction"}])
    tables.turns("tripwire_hook", "direction")


# --- sculk sensors ---------------------------------------------------------------------
#
# Java's: half a block with four tendrils crossed at its corners, and a
# calibrated one's amethyst crossed in the middle and its input side to the
# south. `sculk_sensor_phase` is 0 at rest and 1 or 2 just after it has heard
# something, when its tendrils are lit. A calibrated sensor turns by its facing;
# a plain one is the same from every side.

def sensor_textures(active):
    tendril = "sculk_sensor_tendril_%s" % ("active" if active else "inactive")
    return files({"sculk_sensor_tendril_inactive": tendril})


def unstretched(elements, texture):
    """Java's elements with the crossed planes reading `texture` left at their
    own size: Java stretches them to the corners of the block, and Bedrock
    draws the calibrated sensor's crystal at the size of its picture."""
    out = copy.deepcopy(elements)
    for element in out:
        reads = {spec.get("texture") for spec in element.get("faces", {}).values()}
        if "#" + texture in reads and element.get("rotation"):
            element["rotation"].pop("rescale", None)
    return out


def sculk_sensors():
    from tools.blocks.java_models import MODELS
    for family, model, blocks in (("sculk_sensor", "sculk_sensor", ["sculk_sensor"]),
                                  ("calibrated_sculk_sensor", "calibrated_sculk_sensor",
                                   ["calibrated_sculk_sensor"])):
        found = MODELS[model]
        elements = unstretched(found["elements"], "amethyst")
        forms = {str(phase): java.form(elements, lambda var, read=sensor_textures(phase > 0):
                                       read(java.resolved(found["textures"], var) or var))
                 for phase in range(3)}
        forms["default"] = copy.deepcopy(forms["0"])
        if family == "sculk_sensor":
            write(family, forms, blocks, data={"number": ["sculk_sensor_phase"]}, turn_by=None)
            tables.unturn(family)
        else:
            write(family, forms, blocks, data={"number": ["sculk_sensor_phase"]},
                  turn_by=[{"state": "minecraft:cardinal_direction"}])
            tables.turns(family, "minecraft:cardinal_direction")


# --- trapdoors ------------------------------------------------------------------------
#
# A panel three pixels thick: lying on the floor, under the ceiling, or standing
# open against the south side, where an upside-down trapdoor that is open reads
# its faces differently from one that is not. Every face reads the block's one
# picture, the edges its top three rows. Each window is written out as the
# world with the trapdoor at rest showed it, and the family turns by
# `direction`, which rests at 3.

T = 3 / 16


def trap_face(uv, size):
    return {"uv": list(uv), "size": list(size)}


def trap_form(at, size, faces):
    return {"center": [0.5, 0.5, 0.5], "cubes": [
        {"size": list(size), "offset": list(at), "faces": faces}]}


## a lying panel's four edges, and the same read half round
LYING_EDGE = trap_face((0, 0), (1, T))
LYING_EDGE_ROUND = trap_face((1, T), (-1, -T))
WHOLE = trap_face((0, 0), (1, 1))
WHOLE_ROUND = trap_face((1, 1), (-1, -1))


def trapdoors():
    def lying(y, edge, down=WHOLE):
        return trap_form((0, y, 0), (1, T, 1), dict(
            {side: dict(edge) for side in SIDES}, up=dict(WHOLE), down=dict(down)))

    def standing(big, up):
        return trap_form((0, 0, 1 - T), (1, 1, T), {
            "north": dict(big), "south": dict(big),
            "west": trap_face((T, 0), (-T, 1)), "east": trap_face((0, 1), (T, -1)),
            "up": dict(up), "down": trap_face((1, T), (-1, -T))})

    shapes = {"default": lying(0, LYING_EDGE_ROUND), "top": lying(1 - T, LYING_EDGE),
              "open": standing(WHOLE_ROUND, trap_face((0, 0), (1, T))),
              "open_top": standing(WHOLE, trap_face((0, 0), (1, T)))}
    ## **Turned a quarter, the game turns a shut trapdoor's bottom the other
    ## way from its top**, which a turned box cannot do, so at `direction` 0
    ## and 1 a shut one reads its bottom half round. Every mounting is named
    ## with its direction, so no form stands in for another.
    turned_bottom = {"default": lying(0, LYING_EDGE_ROUND, WHOLE_ROUND),
                     "top": lying(1 - T, LYING_EDGE, WHOLE_ROUND)}
    forms = {}
    for mounting, form in shapes.items():
        for direction in range(4):
            chosen = turned_bottom.get(mounting, form) if direction in (0, 1) else form
            name = str(direction) if mounting == "default" else "%s-%d" % (mounting, direction)
            forms[name] = copy.deepcopy(chosen)
        forms[mounting] = copy.deepcopy(form)
    write("trapdoor", forms,
          pick=[{"when": {"open_bit": True, "upside_down_bit": True}, "form": "open_top"},
                {"when": {"open_bit": True}, "form": "open"},
                {"when": {"upside_down_bit": True}, "form": "top"}],
          data={"number": ["direction"]}, turn_by=[{"state": "direction"}])


# --- fence gates ----------------------------------------------------------------------
#
# Java's four gates: shut or open, standing free or lowered into a wall, its
# picture kept where it is in the world. `open_bit` and `in_wall_bit` choose,
# and it turns by its facing; an open gate swings to the side its facing names.

def fence_gates():
    models = {"0-0": "template_fence_gate", "1-0": "template_fence_gate_open",
              "0-1": "template_fence_gate_wall", "1-1": "template_fence_gate_wall_open"}
    from tools.blocks.java_models import MODELS
    forms = {key: java.form(java.half_turned(MODELS[name]["elements"]), lambda var: None)
             for key, name in models.items()}
    write("fence_gate", forms, blocks_of("fence_gate"),
          pick=None, data={"join": ["open_bit", "in_wall_bit"]},
          turn_by=[{"state": "minecraft:cardinal_direction"}])
    tables.turns("fence_gate", "minecraft:cardinal_direction")


# --- anvils ---------------------------------------------------------------------------
#
# Java's anvil, its top running the length of the block from the side it faces.
# Each of the three is a family of its own, because which top it wears is the
# block's id: Bedrock lists all three tops on every anvil and nothing picks one.

ANVILS = {"anvil": 0, "chipped_anvil": 1, "damaged_anvil": 2}


def anvils():
    from tools.blocks.java_models import MODELS
    elements = java.half_turned(MODELS["anvil"]["elements"])
    for block, damage in ANVILS.items():
        top = java.path("textures/blocks/anvil_top_damaged_%d" % damage)
        read = lambda var, top=top: top if java.resolved(
            MODELS["anvil"]["textures"], var) == "block/anvil_top" else java.slot("down")
        write(block, {"default": java.form(elements, read)}, [block],
              turn_by=[{"state": "minecraft:cardinal_direction"}])
        tables.turns(block, "minecraft:cardinal_direction")


# --- bells -----------------------------------------------------------------------------
#
# The bell and whatever holds it up. Java draws the bell itself as an entity, so
# it is written here the same way: a lip eight across under a body six across,
# reading the rows of `bell_side` each was drawn in, its crown and rim the
# bell's own top and bottom. What holds it is Java's frame for each
# `attachment`: a bar between two stone posts on the floor, the same bar between
# two walls, half of it out of one wall, and a short nib from the block above.
# A bell declares its planks on the east slot and the posts' stone on the west.

BELL_BODY = [
    {"from": [4, 4, 4], "to": [12, 6, 12], "faces": dict(
        {side: {"uv": [0, 7, 8, 9], "texture": "#side"} for side in SIDES},
        ## the lip's top is the ring left round the body, and reads the rim
        up={"uv": [0, 0, 8, 8], "texture": "#rim"},
        down={"uv": [0, 0, 8, 8], "texture": "#rim"})},
    {"from": [5, 6, 5], "to": [11, 13, 11], "faces": dict(
        {side: {"uv": [1, 0, 7, 7], "texture": "#side"} for side in SIDES},
        up={"uv": [1, 1, 7, 7], "texture": "#crown"})},
]
## Java's frames rest with what holds the bell along x; a quarter turn puts a
## wall beam against the south wall, where a wall mounting rests. The floor
## frame keeps Java's own, which a world showed.
BELL_TURNS = {"standing": 0, "side": 90, "multiple": 90, "hanging": 90}
BELL_FRAMES = {"standing": "bell_floor", "multiple": "bell_between_walls",
               "side": "bell_wall", "hanging": "bell_ceiling"}
BELL_SLOTS = {"side": "north", "rim": "down", "crown": "up",
              "block/dark_oak_planks": "east", "block/stone": "west"}


def bells():
    from tools.blocks.java_models import MODELS
    forms = {}
    for attachment, frame in BELL_FRAMES.items():
        found = MODELS[frame]
        elements = BELL_BODY + [dict(element, faces={
            face: dict(spec, texture="#" + java.resolved(found["textures"], spec["texture"][1:]))
            for face, spec in element["faces"].items()})
            for element in java.turned(found["elements"], y=BELL_TURNS[attachment])]
        forms[attachment] = java.form(elements, lambda var: java.slot(BELL_SLOTS[var]))
    forms["default"] = copy.deepcopy(forms["standing"])
    write("bell", forms, ["bell"], data={"join": ["attachment"]},
          turn_by=[{"state": "direction"}])
    tables.turns("bell", "direction")


# --- command blocks ----------------------------------------------------------------------
#
# Java's directional cube: the front on the north face, the back on the south,
# and the sides turned so their arrows point toward the front, the conditional
# side when `conditional_bit` is set. Each kind is a family of its own because
# its pictures are named for it; it turns by Minecraft's own facing angles.

DIRECTIONAL = [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": {
    "down": {"texture": "#side", "rotation": 180}, "up": {"texture": "#side"},
    "north": {"texture": "#front"}, "south": {"texture": "#back"},
    "west": {"texture": "#side", "rotation": 270}, "east": {"texture": "#side", "rotation": 90}}}]


def command_blocks():
    for kind in ("command_block", "chain_command_block", "repeating_command_block"):
        forms = {}
        for conditional in ("0", "1"):
            named = {"front": "front", "back": "back",
                     "side": "conditional" if conditional == "1" else "side"}
            forms[conditional] = java.form(DIRECTIONAL, lambda var, n=named, k=kind: java.path(
                "textures/blocks/%s_%s_mipmap" % (k, n[var])), center=(0.5, 0.5, 0.5))
        write(kind, forms, [kind], pick=None, data={"number": ["conditional_bit"]},
              turn_by=[{"state": "facing_direction"}])
        tables.turns(kind, "facing_direction")


# --- pistons -----------------------------------------------------------------------------
#
# Java's piston, its arm and the shorter base it leaves when the arm is out. A
# piston keeps whether it is out in its `PistonArm` block entity, `State` 0 in,
# 1 going out, 2 out and 3 coming back; anything but in draws the short base
# with the inner face where the head was. Bedrock numbers a piston's
# `facing_direction` its own way, down, up, south, north, east, west, and the
# arm left in the block in front turns by the same table, so the two always
# meet.

ARM_SHEETS = {"piston": "pistonArm", "sticky_piston": "pistonArmSticky"}
PISTON_TURNS = {"0": [90, 0, 0], "1": [270, 0, 0], "2": [0, 180, 0], "3": [0, 0, 0],
                "4": [0, 270, 0], "5": [0, 90, 0]}


def pistons():
    from tools.blocks.java_models import MODELS
    for family, arm, face in (("piston", "piston_arm", "piston_top_normal"),
                              ("sticky_piston", "sticky_piston_arm", "piston_top_sticky")):
        platform = java.path("textures/blocks/" + face)
        base_read = {"platform": platform, "bottom": java.slot("down"),
                     "side": java.slot("north"), "inside": java.slot("up")}

        def read_base(model):
            found = MODELS[model]
            return lambda var: base_read.get(var) or base_read.get(
                (java.resolved(found["textures"], var) or "").split("/")[-1].replace(
                    "piston_", "").replace("inner", "inside"))
        retracted = java.form(MODELS["template_piston"]["elements"], read_base("template_piston"))
        extended = java.form(MODELS["piston_base"]["elements"], read_base("piston_base"))
        write(family, {"0": retracted, "1": extended, "2": copy.deepcopy(extended),
                       "3": copy.deepcopy(extended), "default": copy.deepcopy(retracted)},
              [family], data={"entity": "State"}, turn_by=[{"state": "facing_direction"}])
        tables.turns(family, PISTON_TURNS)

        ## **The head is read from the sheet Bedrock draws the arm with**, one
        ## per kind of piston: its front at (16, 0), its back at (32, 0) and
        ## its rim along the row at 16, so a tweak that paints the arm, as
        ## Sticky Piston Sides does, paints this one. The shaft behind it
        ## reads the plain side, as Java's does.
        sheet = "textures/entity/pistonarm/" + ARM_SHEETS[family]
        arm_read = {"platform": {"texture": sheet, "window": [16, 0]},
                    "unsticky": {"texture": sheet, "window": [32, 0]},
                    "side": {"texture": sheet, "window": [16, 16]},
                    "shaft": java.path("textures/blocks/piston_side")}
        head = copy.deepcopy(MODELS["piston_head"])
        for spec in head["elements"][1]["faces"].values():
            spec["texture"] = "#shaft"
        write(arm, {"default": java.form(head["elements"], lambda var: arm_read.get(var))},
              [family + "_arm_collision"], turn_by=[{"state": "facing_direction"}])
        tables.turns(arm, PISTON_TURNS)


def java_models_of(name):
    from tools.blocks.java_models import MODELS
    return MODELS[name]["elements"]


def main():
    print("writing the blocks drawn from Java's models")
    turtle_eggs()
    sea_pickles()
    cocoa()
    spore_blossom()
    azalea()
    big_dripleaf()
    small_dripleaf()
    pitcher_crop()
    bamboo()
    chorus_plant()
    stems()
    sunflower()
    potted()
    flat_growth()
    torches()
    redstone_components()
    buttons()
    joining()
    stairs()
    string()
    hooks()
    sculk_sensors()
    fence_gates()
    trapdoors()
    anvils()
    bells()
    command_blocks()
    pistons()


if __name__ == "__main__":
    main()
