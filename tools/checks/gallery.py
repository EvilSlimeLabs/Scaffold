"""Build a world that shows real blocks beside their ghosts, for checking in game.

    python -m tools.checks.gallery door stairs chest
    python -m tools.checks.gallery --all --one-block
    python -m tools.checks.gallery --all --every-block --output <folder>

Names are shape families or block ids. Every block named, in every state the
tables tell apart -- each facing, each form, each colour or pose a block entity
carries -- is placed as a real block, with its ghost drawn directly above it, so
geometry, turns and textures can be read against the game's own block from
every side. `--one-block` takes the first block of each family rather than all
of them; a family's blocks differ in their textures and nothing else.

What comes out, in the output folder:

  Scaffold Gallery.mcworld      the whole thing: open it and everything is there
  Scaffold Gallery.mcpack       the ghost pack on its own
  gallery_<n>.mcstructure       each plot as a structure, its name included
  Scaffold Gallery key.tsv      every case, with where its block and ghost are

**The world is written whole**, by `tools/checks/worldfile.py`: every block,
block entity and armor stand is in its database before the game opens it, and
nothing runs in game. It is a void superflat that starts in spectator, with
fire spread, random ticks, mobs, weather, drops and the day cycle off in its
`level.dat`.

**A plot per category.** The cases are grouped by the block list's own
headings -- Oak, Copper, Redstone and the rest -- and each heading gets a plot
of its own, laid out side by side across the world, with an armor stand in the
middle facing north and named for the plot, because a name is what picks a
plot's ghosts. A heading with more cases than a plot holds is spread across
numbered plots. **A plot's name is written in its own ghosts**, on panels above
it on all four sides, the words on both faces of each so they read from inside
the plot and from outside it; a ghost cannot be drawn far from its stand, so a
name shows as somebody comes near its plot.

**A door, a trapdoor and a glazed terracotta say which case they are** on a
sign hung on the front of the barrier each stands on, a state to a line, because
their cases cannot be told apart by eye. `--signs` puts one under every case.

**The ghosts are drawn fully opaque**, so a texture reads the same on both.
Every tier says which of its rows is which with paintings on both faces of
barrier walls just outside the plot: REAL level with the blocks and GHOST level
with their ghosts. They are two of the game's own four by two paintings with
their art replaced by a pack the world carries.

The sizes
---------
A plot is at most 64 by 64 across, the most a structure block holds, and
`PLOT_TIERS` high. Bedrock draws an entity, and so the stand's ghosts, only to
about 64 blocks from the player, so every case is kept that close to its
plot's stand: `REACH` is that distance and `tiers_in_reach` the tallest a plot
of a given width may be.

Cases sit at the widest pitch that fits. Each stands on a barrier, and one that
would fall off, pop off or flow away is caged in barriers on every side:
invisible, solid, and not a block anything connects to except a fence, a wall
or a pane, which are left uncaged. Blocks that live underwater stand in water
inside their cage.
"""
import argparse
import collections
import glob
import io
import itertools
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools import sources

import nbtlib
from nbtlib import Byte, Compound, Float, Int, List, Long, String

from scaffold import core, paths
from tools.checks.render import UNRESOLVABLE
from scaffold import lookup

NAME = "Scaffold Gallery"
MOJANG = sources.metadata("vanilladata_modules", "mojang-blocks.json")

## A set's footprint, the most a structure block holds across.
WIDE = 64
## How far Bedrock draws an entity, and so the stand's ghosts.
REACH = 64
## The most tiers a plot is stacked: a plot is meant to be walked round, so a
## category with more cases than that spreads into more plots, side by side.
PLOT_TIERS = 4
## a plot is never fewer cases across than this, so its name has room
MIN_ACROSS = 5
## the gap between neighbouring plots, and how far a row of plots runs along x
## before the next row starts
PLOT_GAP = 12
ROW_LENGTH = 640
## Cases are this far apart, or the widest of these that fits: at three the
## cages of neighbours touch, which costs nothing because a barrier is invisible
## and a spectator flies through it; at four there is a walkway between them.
PITCHES = (4, 3)
## A tier: barrier floor, up to two blocks of case, the cage's lid, and the
## ghost on top of that, two blocks tall at most.
TIER = 7
## How far above its block a ghost is drawn.
GHOST = 3
## where the first set's floor is, in the world
BASE_Y = 0
## a block with more state combinations than this is sampled rather than drawn
## in every combination; None draws every one
MOST_PER_BLOCK = None
## The world's simulation distance, in chunks. It keeps the world loaded around
## the player and does not widen what a set may be: the stand's reach does that.
SIMULATION = 12

## Blocks the game places for itself, or that only exist beside something
## else: a piston's head without its piston, a portal without its frame, fire,
## a bubble column, a command block or spawner without its block entity, and
## the world-edit blocks. `--skip-technical` leaves them out.
TECHNICAL = re.compile(
    r"^(moving_block|portal"
    r"|end_portal|end_gateway|bubble_column|frosted_ice|fire|soul_fire"
    r"|border_block|allow|deny|structure_block|structure_void|jigsaw"
    r"|(chain_|repeating_)?command_block|mob_spawner|trial_spawner|vault"
    r"|light_block(_\d+)?|camera|client_request_placeholder_block|unknown)$")

## families whose real block joins up to whatever is beside it, and so is
## never caged
CONNECTS = {"fence", "pane", "wall"}
## blocks that live in water, and stand in it
UNDERWATER = re.compile(r"kelp|seagrass|coral|sea_pickle")
## Blocks that hold water in the cell with them, as far as these worlds have
## tested: what `--tweak-world` waterlogs among the blocks it shows
WATERLOGGABLE = {
    "oak_stairs", "oak_slab", "oak_fence", "fence_gate", "cobblestone_wall", "glass_pane",
    "iron_bars", "chest", "trapped_chest", "ender_chest", "barrel", "lantern", "ladder",
    "standing_sign", "wall_sign", "oak_hanging_sign", "pale_oak_trapdoor", "iron_chain",
    "campfire", "bell", "conduit", "candle", "amethyst_cluster", "lightning_rod",
    "pointed_dripstone", "sculk_sensor", "sculk_shrieker", "glow_lichen",
    "small_dripleaf_block", "big_dripleaf", "mangrove_roots", "decorated_pot",
    "copper_grate", "scaffolding", "hopper", "sea_pickle", "kelp"}
## and every block of those kinds, whatever it is made of
WATERLOGGABLE_KINDS = re.compile(r"_stairs$|_slab$|_fence$|_wall$|_pane$|_bars$|chest$|"
                                 r"_sign$|lantern$|_trapdoor$|_chain$|lightning_rod$|"
                                 r"_grate$|_bulb$|_candle$")

## the blocks `--waterlogged` names, each of whose cases also gets a copy
## standing in water, kept in the second layer of the cell as the game keeps it
WATERLOGGED = " waterlogged"
WATERLOG = set()

## the four ways a numbered `direction` points, as an x and z step
DIRECTION_STEP = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}
## and the same for a bed that says it in words, which a straw bed does
CARDINAL_STEP = {"south": (0, 1), "west": (-1, 0), "north": (0, -1), "east": (1, 0)}
## a piston's head is one step along its facing_direction
FACING_STEP = {0: (0, -1, 0), 1: (0, 1, 0), 2: (0, 0, -1), 3: (0, 0, 1),
               4: (-1, 0, 0), 5: (1, 0, 0)}
## a piston and the head it pushes out, when it is drawn extended
PISTON_HEAD = {"piston": "piston_arm_collision",
               "sticky_piston": "sticky_piston_arm_collision"}

## What a block entity can say that the tables draw differently, per entity
## id: the fields and the values worth one case each.
ENTITY_CASES = {
    "Skull": [{"Rotation": Float(a)} for a in (0.0, 22.5, 90.0, 202.5)],
    "Banner": [{"Base": Int(15)}, {"Base": Int(1)}, {"Type": Int(1)},
               {"Base": Int(15), "Patterns": List[Compound]([Compound({
                   "Color": Int(0), "Pattern": String("bo")})])}],
    "Bed": [{"color": Byte(14)}, {"color": Byte(11)}],
    "CopperGolemStatue": [{"Pose": Int(n)} for n in range(4)],
    ## a shulker box keeps which way its lid opens in its block entity
    "ShulkerBox": [{"facing": Byte(n)} for n in range(6)],
    ## a jukebox empty and holding a disc, and a note block at five pitches,
    ## which only Clearer Redstone's families draw differently
    "Jukebox": [{}, {"RecordItem": Compound({
        "Name": String("minecraft:music_disc_cat"), "Count": Byte(1),
        "Damage": nbtlib.Short(0), "WasPickedUp": Byte(0)})}],
    "Music": [{"note": Byte(n)} for n in (0, 6, 12, 18, 24)],
    ## a lectern holding a book holds the book itself, as the game saves one;
    ## told it has one and given none, the game does not load the world
    "Lectern": [{"hasBook": Byte(0)},
                {"hasBook": Byte(1), "page": Int(0), "totalPages": Int(1),
                 "book": Compound({"Name": String("minecraft:writable_book"),
                                   "Count": Byte(1), "Damage": nbtlib.Short(0),
                                   "WasPickedUp": Byte(0),
                                   "tag": Compound({"pages": List[Compound]([Compound({
                                       "text": String(""),
                                       "photoname": String("")})])})})}],
}
## which block entity a family's blocks carry
ENTITY_OF = (("skull_", "Skull"), ("standing_banner", "Banner"),
             ("wall_banner", "Banner"), ("bed", "Bed"),
             ("copper_golem_statue", "CopperGolemStatue"),
             ("lectern", "Lectern"), ("shulker_box", "ShulkerBox"),
             ("clearer_jukebox", "Jukebox"), ("clearer_note_block", "Music"))


def _item(name, count=1):
    """An item as a block entity holds one; an empty slot is a count of nothing."""
    return Compound({"Name": String(name), "Count": Byte(count),
                     "Damage": nbtlib.Short(0), "WasPickedUp": Byte(0)})


def bookshelf(stored):
    """A chiseled bookshelf's block entity, holding a book in exactly the slots
    its `books_stored` bits name, the way the game keeps the two in step: six
    slots in order, an empty one written as an item of nothing."""
    return {"id": String("ChiseledBookshelf"),
            "Items": List[Compound]([_item("minecraft:book") if stored >> slot & 1
                                     else _item("", 0) for slot in range(6)]),
            "LastInteractedSlot": Int(0)}


## a brewing stand's three bottle states, and the slot of its block entity each
## names: slot 0 is the ingredient and 4 the fuel
BREWING_SLOTS = {"brewing_stand_slot_a_bit": 1, "brewing_stand_slot_b_bit": 2,
                 "brewing_stand_slot_c_bit": 3}


def brewing_stand(states):
    """A brewing stand's block entity, holding a water bottle in exactly the
    slots its states say are filled, the way the game keeps the two in step."""
    items = []
    for state, slot in BREWING_SLOTS.items():
        if states.get(state) in (True, 1, "1"):
            item = _item("minecraft:potion")
            item["Slot"] = Byte(slot)
            items.append(item)
    return {"id": String("BrewingStand"), "Items": List[Compound](items),
            "CookTime": nbtlib.Short(0), "FuelAmount": nbtlib.Short(0),
            "FuelTotal": nbtlib.Short(0)}


## The families whose cases say which they are on a sign, hung on the north
## face of the barrier each case stands on: one level down and in front, where
## it hides nothing of the block and reads from where the stand faces. A door
## or a trapdoor in eight turns, two hinges and two halves cannot be told
## apart by eye, and a glazed terracotta's turn is the whole question.
SIGNED = re.compile(r"door|glazed_terracotta|hanging_sign")
## the words a sign shortens a state to, so a case fits on its four lines
SIGN_WORDS = (("minecraft:", ""), ("cardinal_direction", "facing"),
              ("facing_direction", "facing"), ("door_hinge_bit", "hinge"),
              ("upside_down_bit", "upside down"), ("_bit", ""), ("_", " "))
SIGN_LINES = 4


def sign_text(label):
    """A case's label as a sign's lines: a state to a line, shortened."""
    lines = []
    for pair in label.split():
        name, _, value = pair.partition("=")
        for long, short in SIGN_WORDS:
            name = name.replace(long, short)
        value = {"True": "yes", "False": "no"}.get(value, value).replace("_", " ")
        lines.append("%s %s" % (name, value))
    return "\n".join(lines[:SIGN_LINES])


def _sign_side(text):
    return Compound({"HideGlowOutline": Byte(0), "IgnoreLighting": Byte(0),
                     "PersistFormatting": Byte(1),
                     "SignTextColor": Int(-16777216), "Text": String(text),
                     "TextOwner": String("")})


def sign(text):
    """A sign's block entity, written the way the game writes one: both sides,
    the words on the front."""
    return {"id": String("Sign"), "FrontText": _sign_side(text),
            "BackText": _sign_side(""), "IsWaxed": Byte(0)}


def load(name):
    with io.open(paths.lookup(name + ".json"), encoding="utf-8") as f:
        return lookup.unwrap(name + ".json", json.load(f))


def mojang():
    """Every block's state names, and every state's possible values."""
    with io.open(MOJANG, encoding="utf-8") as f:
        data = json.load(f)
    values = {p["name"]: [v["value"] for v in p["values"]]
              for p in data["block_properties"]}
    states = {b["name"]: [p["name"] for p in b["properties"]]
              for b in data["data_items"]}
    return states, values


def observed():
    """A real, complete set of states per block, from the test structures."""
    from scaffold import block_upgrade
    seen = collections.defaultdict(collections.Counter)
    newest = 0
    for path in glob.glob(os.path.join(ROOT, "test_structures", "*.mcstructure")):
        from scaffold.pack import structure_reader
        body = structure_reader.load(path)
        for entry in body["structure"]["palette"]["default"]["block_palette"]:
            newest = max(newest, int(entry["version"]))
            ## a test structure is an old save, so its blocks are read the way
            ## the current game names them before they are used as anything
            entry = block_upgrade.upgrade(entry)
            key = json.dumps({k: _plain(v) for k, v in entry["states"].items()},
                             sort_keys=True)
            seen[str(entry["name"])][key] += 1
    return ({name: json.loads(c.most_common(1)[0][0]) for name, c in seen.items()},
            newest)


def _shown(value):
    """A block entity field as a sign says it: a list or a compound by what it
    is, a number as itself."""
    if isinstance(value, List):
        return "pattern"
    if isinstance(value, Compound):
        return str(value.get("Name", "item")).replace("minecraft:", "")
    if isinstance(value, (Byte, Int, nbtlib.Short)):
        return int(value)
    return _plain(value)


def _plain(value):
    if isinstance(value, Byte):
        return bool(value)
    if isinstance(value, (Int, int)):
        return int(value)
    return str(value)


def _tag(value):
    if isinstance(value, bool):
        return Byte(int(value))
    if isinstance(value, int):
        return Int(value)
    return String(value)


## `extra` is any further block the case needs beside its own, as offsets
## with a block, its states and its block entity: an extended piston's head
Case = collections.namedtuple("Case", "block states entity label extra",
                              defaults=((),))


## a piston counts its sideways facings the other way from everything else: 2
## south, 3 north, 4 east, 5 west, so its head is a step that way
PISTON_STEP = {0: (0, -1, 0), 1: (0, 1, 0), 2: (0, 0, 1), 3: (0, 0, -1),
               4: (1, 0, 0), 5: (-1, 0, 0)}


def extended(case):
    """The same piston pushed out, the way the game saves one: the piston
    holding a `PistonArm` block entity that says it is fully out, and its head
    one block along its facing."""
    facing = int(case.states.get("facing_direction", 0))
    dx, dy, dz = PISTON_STEP[facing]
    head = PISTON_HEAD[case.block]
    arm = {"id": String("PistonArm"), "State": Byte(2), "NewState": Byte(2),
           "Progress": Float(1.0), "LastProgress": Float(1.0),
           "Sticky": Byte(int(case.block == "sticky_piston")),
           "AttachedBlocks": List([]), "BreakBlocks": List([]),
           "isMovable": Byte(0)}
    return Case(case.block, case.states, arm, (case.label + " extended").strip(),
                ((dx, dy, dz, head, {"facing_direction": facing}, None),))


## the chests that pair into a double chest; an ender chest never does
PAIRS = {"chest", "trapped_chest"} | {
    p + "copper_chest" for p in ("", "exposed_", "weathered_", "oxidized_",
                                 "waxed_", "waxed_exposed_", "waxed_weathered_",
                                 "waxed_oxidized_")}


def doubled(case):
    """The same chest as the left half of a double chest, with its right half
    beside it, the way the game saves a pair: each half's block entity names
    the other's position, which is only known once the plot is placed, so the
    step to it travels as `_pair` and `paired_fields` writes it out."""
    from scaffold.core import LEFT_HAND
    left = LEFT_HAND[str(case.states["minecraft:cardinal_direction"])]
    ## the right half stands on the left half's right
    dx, dz = -left[0], -left[1]
    own = {"id": String("Chest"), "Findable": Byte(0), "_pair": (dx, dz, 1)}
    other = {"id": String("Chest"), "Findable": Byte(0), "_pair": (-dx, -dz, 0)}
    return Case(case.block, case.states, own, (case.label + " double").strip(),
                ((dx, 0, dz, case.block, dict(case.states), other),))


## Blocks the game works some states out from: a fence's joins, a stair's corner,
## a hanging sign's attachment. A world loads them recomputed from what is beside
## them, so a case whose state names a neighbour is given that neighbour.
SIDE_STEP = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
JOINED = {"fence": "stone", "pane": "stone", "bars": "stone", "tripwire": "trip_wire"}
## a stair's `weirdo_direction` as the way its tall side faces, and a quarter
## anticlockwise of each
STAIR_FACING = {0: "east", 1: "west", 2: "south", 3: "north"}
STAIR_WEIRDO = {v: k for k, v in STAIR_FACING.items()}
ANTICLOCKWISE = {"north": "west", "west": "south", "south": "east", "east": "north"}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
HANGING_CHAIN = "iron_chain"


def supported(family, case):
    """The case with the neighbours its states need, as extra blocks."""
    states, extra = case.states, []
    if family in JOINED:
        for side, (dx, dz) in SIDE_STEP.items():
            if _plain(states.get("minecraft:connection_" + side)) in (True, 1):
                ## string beside string joins back to the case, which the
                ## game works out and its ghost has to be told
                joined = {} if JOINED[family] == "stone" else {
                    "minecraft:connection_" + other: other == OPPOSITE[side]
                    for other in SIDE_STEP}
                extra.append((dx, 0, dz, JOINED[family], joined, None))
    elif family == "stairs":
        corner = str(states.get("minecraft:corner", "none"))
        facing = STAIR_FACING.get(_plain(states.get("weirdo_direction", -1)))
        if facing and corner != "none":
            outer = corner.startswith("outer")
            left = corner.endswith("left")
            ## an outer corner has a stair behind its tall side, an inner one a
            ## stair in front, turned to the left or the right of it
            side = facing if outer else OPPOSITE[facing]
            turned = ANTICLOCKWISE[facing] if left else OPPOSITE[ANTICLOCKWISE[facing]]
            dx, dz = SIDE_STEP[side]
            extra.append((dx, 0, dz, case.block,
                          dict(states, weirdo_direction=STAIR_WEIRDO[turned],
                               **{"minecraft:corner": "none"}), None))
    elif family == "hanging_sign" and _plain(states.get("attached_bit")) in (True, 1)             and _plain(states.get("hanging")) in (True, 1):
        extra.append((0, 1, 0, HANGING_CHAIN, {"pillar_axis": "y"}, None))
    if not extra:
        return case
    return case._replace(extra=tuple(case.extra) + tuple(extra))


## the containers a Clearer Redstone count is drawn on, the block entity each
## keeps, and the signals shown, low, middle and full
FILLED = {"chest": "Chest", "barrel": "Barrel", "dispenser": "Dispenser",
          "dropper": "Dropper", "hopper": "Hopper"}
FILL_SIGNALS = (1, 8, 15)
## a crafter with every other slot locked, which shows both kinds
LOCKED_SLOTS = 0b101010101


def filled(case, entity_id, strength):
    """A container holding the fewest items that give a comparator `strength`."""
    from scaffold import marks
    slots = marks.CONTAINERS[case.block][0]
    full, loose = marks.recipe(strength, slots)
    items = []
    for slot in range(full):
        item = _item("minecraft:cobblestone", 64)
        item["Slot"] = Byte(slot)
        items.append(item)
    if loose:
        item = _item("minecraft:cobblestone", loose)
        item["Slot"] = Byte(full)
        items.append(item)
    return case._replace(entity={"id": String(entity_id), "Items": List[Compound](items)},
                         label=(case.label + " signal %d" % strength).strip(), extra=())


def locked(case):
    """A crafter with slots locked."""
    return case._replace(entity={"id": String("Crafter"),
                                 "disabled_slots": nbtlib.Short(LOCKED_SLOTS)},
                         label=(case.label + " slots locked").strip())


## Blocks the low world shows once. A grindstone's simpler form is its wheel
## and one box for the legs, and nothing about how it is attached changes what
## needs checking, so its other mountings add nothing.
LOW_ONE_CASE = ("grindstone",)


def low_blocks():
    """The first block of every family that has a simpler form."""
    shapes = load("block_geometry")["families"]
    defs = load("block_definition")
    found = []
    for family, entry in shapes.items():
        if "low" not in entry:
            continue
        blocks = sorted(b for b, f in defs.items() if f == family
                        and not UNRESOLVABLE.match(b) and b not in PARTS)
        if blocks:
            found.append(blocks[0])
    return found


## the options that only add marks and change no block; the pack is built with
## them on, and the containers and crafter that show them are real blocks
MARK_TWEAKS = ("container_fill", "crafter_slots")


def tweak_world():
    """(tweaks the pack is built with, [(plot title, tweak, block)]) for
    `--tweak-world`.

    Every tweak that ships, a conflicting pair's both, and every block each one
    changes, each drawn with that tweak alone: see `tweak_variants`. The tabs
    are a plot each."""
    from scaffold import tweaks as tweak_packs
    from tools.checks import tweak_blocks
    titles = {"redstone": "Clearer Redstone"}
    entries = []
    for tweak in tweak_packs.offered():
        if tweak_packs.folder(tweak) is None or tweak in MARK_TWEAKS:
            continue
        title = titles.get(tweak_packs.tab(tweak), "Bedrock Tweaks")
        changed = [b for b in tweak_blocks.changed_by(tweak) if not b.startswith("scaffold:")]
        ## Age 25 Kelp paints only the oldest kelp, which a block's first
        ## picture does not show
        if tweak == "age_25_kelp" and not changed:
            changed = ["kelp"]
        entries += [(title, tweak, name) for name in changed]
    return list(MARK_TWEAKS), entries


def paired_fields(fields, x, z):
    """A block entity as written at (x, z), with a pair's step made a position."""
    step = fields.get("_pair")
    if step is None:
        return fields
    fields = {k: v for k, v in fields.items() if k != "_pair"}
    fields.update({"pairx": Int(x + step[0]), "pairz": Int(z + step[1]),
                   "pairlead": Byte(step[2])})
    return fields


def state_roles(rule):
    """What each state a family's rules read does to the block.

    `rot` turns it, `shape` picks its mounting or joins into its value,
    `data` is a number naming a form, and `variant` picks a texture.
    """
    roles = {}
    ## a turn read from the block entity is a case of ENTITY_CASES, not a state
    for entry in rule.get("turn_by", ()):
        if "state" in entry:
            roles[entry["state"]] = "rot"
    for pick in rule.get("pick", ()):
        for state in pick["when"]:
            roles.setdefault(state, "shape")
    data = rule.get("data", {})
    for state in data.get("join", ()):
        roles.setdefault(state, "shape")
    for state in data.get("number", ()):
        roles.setdefault(state, "data")
    chosen = rule.get("texture_by")
    if chosen and "join" in chosen:
        for state in chosen["join"]:
            roles.setdefault(state, "shape")
    elif chosen:
        roles.setdefault(chosen["state"], "variant")
    return roles


def _sampled(values):
    """A state's values, or for a number with more of them than a block may
    show, the ones that tell its bits apart: nothing, each bit alone, and
    everything. A glow lichen on each face shows what any mix of faces would."""
    numbers = [_plain(_tag(v)) for v in values]
    if (MOST_PER_BLOCK is None or len(values) <= MOST_PER_BLOCK
            or not all(isinstance(n, int) for n in numbers)):
        return values
    top = max(numbers)
    return [v for v, n in zip(values, numbers)
            if n == 0 or n == top or n & (n - 1) == 0]


## Families whose states mean something only in a few combinations, given just
## those. A hanging sign under a block turns in four steps with
## `facing_direction`, one hanging from a chain in sixteen with
## `ground_sign_direction`, and one on a wall in four again; any other
## combination is one the game does not keep, and a world loads it changed.
ONLY_CASES = {"hanging_sign": (
    [{"hanging": True, "attached_bit": False, "facing_direction": f,
      "ground_sign_direction": 0} for f in (2, 3, 4, 5)]
    + [{"hanging": True, "attached_bit": True, "facing_direction": 2,
        "ground_sign_direction": g} for g in range(16)]
    + [{"hanging": False, "attached_bit": False, "facing_direction": f,
        "ground_sign_direction": 0} for f in (2, 3, 4, 5)])}


def cases_for(block, family, mojang_states, values, base, shapes,
              rotations, rules):
    """Every state of one block the tables tell apart, as cases."""
    name = "minecraft:" + block
    own = mojang_states.get(name)
    if own is None:
        return []
    ## only the states the block has today, so nothing a save carried from an
    ## older game reaches the world: the game does not load a block whose
    ## states it does not know
    start = {k: v for k, v in (base.get(name) or {}).items() if k in own}
    for state in own:
        start.setdefault(state, values[state][0])
    ## leaves left alone keep their leaves
    if "persistent_bit" in start:
        start["persistent_bit"] = True

    forms = set(shapes.get(family, {}))
    roles = state_roles(rules.get(family, {}))
    table = rotations.get(family, {})
    turned = {key.split(":")[-1] for key in table}
    varied = {}
    for state in own:
        role = roles.get(state)
        every = values[state]
        if state in ("upper_block_bit", "head_piece_bit"):
            continue
        if role == "rot":
            picked = [v for v in every if str(_plain(_tag(v))) in turned
                      or str(v).lower() in turned]
        elif role == "shape" or state == "rail_data_bit":
            picked = list(every)
        elif role == "variant":
            ## the values the family's texture rule reads; one with no table
            ## reads the state's own number, so every value is a texture
            chosen = rules.get(family, {}).get("texture_by", {})
            if chosen.get("state") != state:
                continue
            listed = chosen.get("values")
            picked = [v for v in every if listed is None or str(v) in listed]
        elif role == "data":
            picked = [v for v in every if str(_plain(_tag(v))) in forms]
        else:
            continue
        if len(picked) > 1:
            varied[state] = picked

    names = sorted(varied)
    combos = [dict(zip(names, chosen))
              for chosen in itertools.product(*(varied[n] for n in names))]
    if family in ONLY_CASES:
        combos = ONLY_CASES[family]
    elif MOST_PER_BLOCK is not None and len(combos) > MOST_PER_BLOCK:
        ## every value of every state at least once, with the turning state
        ## gone all the way round at the start of each other one
        turning = [n for n in names if roles.get(n) == "rot"]
        others = [n for n in names if n not in turning]
        kept = []
        for n in others:
            for v in _sampled(varied[n]):
                kept.append({n: v})
        turns = list(itertools.product(*(varied[n] for n in turning)))
        if len(turns) <= MOST_PER_BLOCK:
            kept.extend(dict(zip(turning, chosen)) for chosen in turns)
        else:
            ## two turning states, a hanging sign's, each gone round on its own
            for n in turning:
                kept.extend({n: v} for v in varied[n])
        combos = kept
    entity_id = next((e for prefix, e in ENTITY_OF if family.startswith(prefix)),
                     None)
    extras = ENTITY_CASES.get(entity_id, [None])
    found = []
    for combo in combos or [{}]:
        states = dict(start)
        states.update(combo)
        for extra in extras:
            ## a head turns by its entity only standing on the floor
            if (entity_id == "Skull" and extra and states.get("facing_direction") != 1
                    and float(extra["Rotation"]) != 0):
                continue
            label = " ".join("%s=%s" % (k, combo[k]) for k in sorted(combo))
            if extra:
                label += " " + " ".join("%s=%s" % (k, _shown(v)) for k, v in extra.items())
            entity = dict(extra, id=String(entity_id)) if extra else None
            if block == "chiseled_bookshelf":
                entity = bookshelf(int(states.get("books_stored", 0)))
            if block == "brewing_stand":
                entity = brewing_stand(states)
            found.append(supported(family, Case(block, states, entity, label.strip())))
            if block in PISTON_HEAD:
                found.append(extended(found[-1]))
            if block in PAIRS and not extra:
                found.append(doubled(found[-1]))
    ## and one copy standing in water, of the last case, which is a facing a
    ## block can hold where the first is often down
    if block in WATERLOG and found:
        found.append(found[-1]._replace(label=found[-1].label + WATERLOGGED))
    return found


## blocks that are only ever drawn as part of another case
PARTS = {"piston_arm_collision", "sticky_piston_arm_collision"}


def choose(selection, every_block, everything, exact=False):
    """The blocks to show, grouped by family. With `exact`, a name that is a
    block id is that block alone, even where a family shares its name."""
    defs = load("block_definition")
    families = collections.OrderedDict()
    for block, family in sorted(defs.items()):
        if (family == "ignore" or UNRESOLVABLE.match(block) or block == "air"
                or block in PARTS):
            continue
        families.setdefault(family, []).append(block)
    ## a family asked for by name shows every block it has; --all shows the
    ## first of each unless every block is asked for too
    picked = collections.OrderedDict()
    for name in (families if everything else selection):
        if exact and name.replace("minecraft:", "") in defs:
            block = name.replace("minecraft:", "")
            picked.setdefault(defs[block], []).append(block)
        elif name in families:
            blocks = families[name]
            picked[name] = blocks if every_block or not everything else blocks[:1]
        elif name.replace("minecraft:", "") in defs:
            block = name.replace("minecraft:", "")
            picked.setdefault(defs[block], []).append(block)
        else:
            sys.exit("%s is neither a family nor a block" % name)
    return picked


def all_cases(picked):
    mojang_states, values = mojang()
    base, newest = observed()
    from scaffold import block_geometry
    shapes, rotations, rules = (block_geometry.load()[0], block_geometry.rotations(),
                                block_geometry.rules())
    out = []
    for family, blocks in picked.items():
        for block in blocks:
            out.extend((family, c) for c in cases_for(
                block, family, mojang_states, values, base, shapes,
                rotations, rules))
    return out, newest


class Grid:
    """One plot: a square of cases, tier above tier, with its stand in the
    middle and its name written round it in its own ghosts."""

    def __init__(self, across, tiers, pitch, title="", signed=None):
        self.across = across
        ## which families say which case is which on a sign
        self.signed = signed or (lambda family: False)
        self.most = tiers
        self.pitch = pitch
        self.title = title
        self.blocks = {}       # (x, y, z) -> (name, states)
        self.water = set()
        self.entities = {}     # (x, y, z) -> compound
        row = [1 + i * pitch for i in range(across)]
        self.cells = [(t, x, z) for t in range(self.most)
                      for z in row for x in row]
        self.used = 0
        self.key = []
        ## blocks the ghost draws in place of the real one at a position: a
        ## trial in tools/checks/trials.py over the block it copies
        self.ghost_as = {}
        ## and the water it draws in place of a position's water, or None for
        ## none: tools/checks/water_trials.py
        self.water_as = {}

    @property
    def wide(self):
        """How far the plot reaches across, cages included."""
        return (self.across - 1) * self.pitch + 3

    @property
    def full(self):
        return self.used >= len(self.cells)

    @property
    def tiers(self):
        """How many tiers the cases placed so far fill."""
        per = len(self.cells) // self.most
        return max(1, -(-self.used // per))

    @property
    def size(self):
        return (self.wide, self.tiers * TIER, self.wide)

    ## how far above its block a ghost is drawn; a plot holding a whole
    ## structure raises it to clear the structure's own height
    lift = GHOST

    @property
    def top(self):
        """The first height above everything the plot draws, ghosts included."""
        return self.tiers * TIER

    def stand(self):
        """Where the armor stand stands, in the plot's own coordinates: the
        middle, among the ghosts of the middle tier, on a column no case uses
        and over a cell no cage takes."""
        middle = self.wide // 2
        if (middle - 1) % self.pitch == 0:
            middle += 1
        return (middle, (self.tiers // 2) * TIER + 1 + self.lift, middle)

    def labels(self):
        """The rows each tier labels: the blocks' and the ghosts', as heights
        within the plot and the painting that says which."""
        found = []
        for tier in range(self.tiers):
            base = tier * TIER + 1
            found.append((base, REAL))
            found.append((base + self.lift, GHOST_LABEL))
        return found

    def add(self, family, case):
        tier, x, z = self.cells[self.used]
        self.used += 1
        y = tier * TIER + 1
        placed = [(x, y, z, case.states)]
        states = case.states
        if "upper_block_bit" in states:
            states = dict(states, upper_block_bit=False)
            placed = [(x, y, z, states), (x, y + 1, z, dict(states, upper_block_bit=True))]
        if "head_piece_bit" in states:
            ## the head lies one block the way the bed faces, whichever of the
            ## two facing states the bed carries
            if "minecraft:cardinal_direction" in states:
                dx, dz = CARDINAL_STEP[str(states["minecraft:cardinal_direction"])]
            else:
                dx, dz = DIRECTION_STEP[int(states.get("direction", 0))]
            states = dict(states, head_piece_bit=False)
            placed = [(x, y, z, states), (x + dx, y, z + dz, dict(states, head_piece_bit=True))]
        name = "minecraft:" + case.block
        for px, py, pz, s in placed:
            self.blocks[(px, py, pz)] = (name, s)
            if case.entity:
                self.entities[(px, py, pz)] = case.entity
            if UNDERWATER.search(case.block) or case.label.endswith(WATERLOGGED):
                self.water.add((px, py, pz))
        for dx, dy, dz, block, extra_states, extra_entity in case.extra:
            at = (x + dx, y + dy, z + dz)
            self.blocks[at] = ("minecraft:" + block, extra_states)
            if extra_entity:
                self.entities[at] = extra_entity
            placed.append(at + (extra_states,))
        ## a barrier under everything, and round the sides and over the top
        ## of anything that does not join up with its neighbours
        cage = family not in CONNECTS
        for px, py, pz, _s in placed:
            around = [(0, -1, 0)]
            if cage:
                around += [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)]
            for dx, dy, dz in around:
                spot = (px + dx, py + dy, pz + dz)
                ## the edge of the set is the edge of the structure, and
                ## nothing out there can fall onto a case
                if not (0 <= spot[0] < self.wide and 0 <= spot[2] < self.wide
                        and 0 <= spot[1] < self.most * TIER):
                    continue
                if spot not in self.blocks:
                    self.blocks.setdefault(spot, ("minecraft:barrier", {}))
        ## hung on the north face of the barrier the case stands on
        if self.signed(family) and case.label:
            at = (x, y - 1, z - 1)
            if at not in self.blocks and at[1] >= 0:
                self.blocks[at] = ("minecraft:wall_sign", {"facing_direction": 2})
                self.entities[at] = sign(sign_text(case.label))
        self.key.append((family, case, (x, y, z)))


    def save(self, path, version, extra=()):
        """The plot as a structure: its blocks, and `extra` -- blocks only its
        ghosts carry -- shifted so nothing sits below or beside the origin.
        Answers how far everything was shifted."""
        found = dict(self.blocks)
        for at, name in self.ghost_as.items():
            found[at] = (name, found[at][1])
        for at, name in extra:
            found[at] = (name, {})
        low = [min(0, min(p[i] for p in found)) for i in range(3)]
        high = [max(self.size[i], max(p[i] for p in found) + 1) for i in range(3)]
        shift = [-v for v in low]
        sx, sy, sz = (high[i] - low[i] for i in range(3))
        index = {}
        layer = [0] * (sx * sy * sz)
        second = [-1] * (sx * sy * sz)
        palette = []

        def entry(name, states):
            key = (name, json.dumps(states, sort_keys=True, default=str))
            if key not in index:
                index[key] = len(palette)
                palette.append(Compound({
                    "name": String(name),
                    "states": Compound({k: _tag(v) for k, v in states.items()}),
                    "version": Int(version)}))
            return index[key]

        def flat(x, y, z):
            return ((x + shift[0]) * sy + y + shift[1]) * sz + z + shift[2]

        entry("minecraft:air", {})
        water = entry("minecraft:water", {"liquid_depth": 0})
        positions = {}
        for (x, y, z), (name, states) in found.items():
            layer[flat(x, y, z)] = entry(name, states)
            if (x, y, z) in self.water:
                instead = self.water_as.get((x, y, z), "minecraft:water")
                if instead:
                    second[flat(x, y, z)] = entry(instead, {"liquid_depth": 0})
        for (x, y, z), fields in self.entities.items():
            data = Compound(paired_fields(fields, x + shift[0], z + shift[2]))
            data.update({"isMovable": Byte(1), "x": Int(x + shift[0]),
                         "y": Int(y + shift[1]), "z": Int(z + shift[2])})
            positions[str(flat(x, y, z))] = Compound({"block_entity_data": data})
        nbtlib.File({
            "format_version": Int(1),
            "size": List[Int]([Int(sx), Int(sy), Int(sz)]),
            "structure_world_origin": List[Int]([Int(0), Int(0), Int(0)]),
            "structure": Compound({
                "block_indices": List([List[Int]([Int(v) for v in layer]),
                                       List[Int]([Int(v) for v in second])]),
                "entities": List[Compound]([]),
                "palette": Compound({"default": Compound({
                    "block_palette": List[Compound](palette),
                    "block_position_data": Compound(positions)})}),
            }),
        }).save(path, byteorder="little")
        return shift


class StructureGrid(Grid):
    """A plot holding a structure as it was saved, one block in from its edge,
    each block on a barrier: for blocks whose states only hold beside the
    neighbours they were saved with, such as string and stair corners."""

    def __init__(self, path, title=None, tweak=None):
        from scaffold.pack.structure_reader import StructureFile
        found = StructureFile(path)
        sx, sy, sz = found.size
        super().__init__(1, 1, 1, title or os.path.splitext(os.path.basename(path))[0])
        self._wide = max(sx, sz) + 2
        ## the ghost one block clear of the structure's top
        self.lift = max(GHOST, sy + 1)
        self._tall = sy
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = found.get_block(x, y, z)
                    if block["name"] == "minecraft:air":
                        continue
                    at = (x + 1, y + 1, z + 1)
                    self.blocks[at] = (block["name"], {k: _plain(v) for k, v in
                                                       dict(block.get("states", {})).items()})
                    entity = found.get_block_entity(x, y, z)
                    if entity:
                        self.entities[at] = entity
                    if found.get_liquid(x, y, z) is not None:
                        self.water.add(at)
                    self.blocks.setdefault((x + 1, 0, z + 1), ("minecraft:barrier", {}))
        self.used = 1
        dusted(self, tweak)

    @property
    def wide(self):
        return self._wide

    @property
    def top(self):
        return max(self.tiers * TIER, 1 + self.lift + self._tall)

    @property
    def size(self):
        return (self.wide, self.top, self.wide)

    def stand(self):
        middle = self.wide // 2
        return (middle, 1 + self.lift, middle)


## redstone dust as it was saved, every signal, laid out in lines that join,
## cross and end
DUST_LAYOUT = os.path.join("test_structures", "redstone_dust.mcstructure")
## the tweaks that change redstone dust, each given a dust plot of its own
DUST_TWEAKS = (("Bedrock Tweaks", "clean_redstone_dust", "Clean dust"),
               ("Clearer Redstone", "redstone_dust_shades", "Dust shades"),
               ("Clearer Redstone", "redstone_dust_numbers", "Dust numbers"))
## the pseudo ids a tweak's dust is drawn as, which join like dust
VARIANT_DUST = "scaffold:tw_*__redstone_wire"
## blocks no Bedrock Tweak changes, shown on that plot as they are drawn
## without one, beside the tweaks that do
PLAIN_ON_TWEAK_PLOT = ("dispenser", "dropper")


class DustGrid(StructureGrid):
    """The redstone dust structure as it was saved, its ghosts drawn with one
    tweak."""

    def __init__(self, tweak, title):
        super().__init__(DUST_LAYOUT, title)
        if tweak:
            from tools.checks import tweak_variants
            for at, (name, _states) in self.blocks.items():
                if name.endswith("redstone_wire"):
                    self.ghost_as[at] = tweak_variants.block(tweak, "redstone_wire")


## A block with dust on all four sides, to show which of its faces draw dust
## toward them, in rows west to east from the north-west corner
JOIN_SCENES = (
    ("minecraft:unpowered_comparator", {"minecraft:cardinal_direction": "north"}),
    ("minecraft:unpowered_repeater", {"minecraft:cardinal_direction": "north"}),
    ("minecraft:piston", {"facing_direction": 3}),
    ("minecraft:sticky_piston", {"facing_direction": 1}),
    ("minecraft:observer", {"minecraft:facing_direction": "north"}),
    ("minecraft:lever", {"lever_direction": "up_north_south", "open_bit": True}),
    ("minecraft:redstone_torch", {"torch_facing_direction": "top"}),
    ("minecraft:redstone_block", {}),
    ("minecraft:target", {}),
    ("minecraft:daylight_detector", {}),
    ("minecraft:sculk_sensor", {}),
    ("minecraft:stone", {}),
    ("minecraft:glass", {}),
    ("minecraft:dispenser", {"facing_direction": 2}),
)
## dust on the floor beside a block and on top of it, west to east; the last
## has stone over the lower dust, which cuts the climb
CLIMBS = (("minecraft:stone", {}), ("minecraft:glass", {}), ("minecraft:glowstone", {}),
          ("minecraft:smooth_stone_slab", {"minecraft:vertical_half": "top"}),
          ("minecraft:hopper", {"facing_direction": 0}), ("minecraft:stone", {"cut": True}),
          ("minecraft:glass", {"cut": True}),
          ("minecraft:smooth_stone_slab", {"minecraft:vertical_half": "top", "cut": True}))
SCENE = 5
SCENES_ACROSS = 7


_STATE_SOURCES = []


def whole_states(name, states):
    """A block's every state, the ones given and the rest as a save has them,
    so the game loads what is written."""
    if not _STATE_SOURCES:
        _STATE_SOURCES.extend(mojang() + (observed()[0],))
    mojang_states, values, base = _STATE_SOURCES
    own = mojang_states.get(name, [])
    found = {k: v for k, v in (base.get(name) or {}).items() if k in own}
    for state in own:
        found.setdefault(state, values[state][0])
    found.update(states)
    return {k: v for k, v in found.items() if k in own}


## what powers dust beside it in these plots
POWERS = {"minecraft:redstone_block": None, "minecraft:redstone_torch": None,
          "minecraft:lever": ("open_bit", True)}


def powered(blocks):
    """Dust's signal, as the game would settle it with nothing but these
    sources: 15 beside one, one less for every joined step."""
    from scaffold import dust
    rules = dust.Connections()

    def at(x, y, z):
        found = blocks.get((x, y, z))
        return {"name": found[0], "states": found[1]} if found else None

    def solid(block):
        name = block["name"]
        return name not in ("minecraft:air", "minecraft:barrier") and not name.endswith(
            ("_slab", "hopper", "wire", "torch", "lever", "repeater", "comparator"))

    def source(block):
        if block is None or block["name"] not in POWERS:
            return False
        need = POWERS[block["name"]]
        return need is None or block["states"].get(need[0]) == need[1]

    level, queue = {}, []
    for (x, y, z), (name, _states) in blocks.items():
        if name.endswith("redstone_wire") and any(
                source(at(x + dx, y, z + dz)) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            level[(x, y, z)] = 15
            queue.append((x, y, z))
    spread(blocks, level, queue, rules, at, solid)
    ## a repeater passes a full signal to its front from the side its
    ## `minecraft:cardinal_direction` names, which is its input, and a
    ## comparator the signal it has; then it spreads again
    steps = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
    passed = True
    while passed:
        passed = False
        for (x, y, z), (name, states) in blocks.items():
            if not name.endswith(("repeater", "comparator")):
                continue
            facing = str(states.get("minecraft:cardinal_direction", "north"))
            (ax, az) = steps[facing]
            for (bx, bz) in ((-ax, -az),):
                a, b = (x + ax, y, z + az), (x + bx, y, z + bz)
                if level.get(a, 0) <= 0 or b not in blocks or \
                        not blocks[b][0].endswith("redstone_wire"):
                    continue
                signal = 15 if name.endswith("repeater") else level[a]
                if level.get(b, -1) < signal:
                    level[b] = signal
                    spread(blocks, level, [b], rules, at, solid)
                    passed = True
    for spot, signal in level.items():
        name, states = blocks[spot]
        blocks[spot] = (name, dict(states, redstone_signal=signal))


def spread(blocks, level, queue, rules, at, solid):
    """Carry a signal along joined dust, one less each step."""
    from scaffold import dust
    while queue:
        x, y, z = queue.pop(0)
        joins = rules.sides(at, x, y, z, solid)
        for side, (dx, _dy, dz) in dust.SIDES.items():
            if joins[dust.STATE % side] == dust.NONE:
                continue
            for dy in (0, 1, -1):
                spot = (x + dx, y + dy, z + dz)
                if spot in blocks and blocks[spot][0].endswith("redstone_wire") and \
                        level.get(spot, -1) < level[(x, y, z)] - 1:
                    level[spot] = level[(x, y, z)] - 1
                    queue.append(spot)


def dusted(grid, tweak):
    """Draw a plot's dust with one tweak's version of it."""
    if tweak:
        from tools.checks import tweak_variants
        for at, (name, _states) in grid.blocks.items():
            if name.endswith("redstone_wire"):
                grid.ghost_as[at] = tweak_variants.block(tweak, "redstone_wire")


class DustJoinGrid(Grid):
    """Dust beside the blocks it may join, to check the rules in
    `lookups/dust_connections.json` against the game."""

    def __init__(self, title="Dust joins", tweak=None):
        super().__init__(1, 1, 1, title)
        whole = whole_states

        wire = ("minecraft:redstone_wire", whole("minecraft:redstone_wire", {"redstone_signal": 0}))

        def put(at, block):
            self.blocks[at] = block
            self.blocks.setdefault((at[0], 0, at[2]), ("minecraft:barrier", {}))

        for i, (name, states) in enumerate(JOIN_SCENES):
            cx = 2 + SCENE * (i % SCENES_ACROSS)
            cz = 2 + SCENE * (i // SCENES_ACROSS)
            put((cx, 1, cz), (name, whole(name, states)))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                put((cx + dx, 1, cz + dz), wire)
        rows = -(-len(JOIN_SCENES) // SCENES_ACROSS)
        for i, (name, states) in enumerate(CLIMBS):
            cx = 2 + SCENE * (i % SCENES_ACROSS)
            cz = 2 + SCENE * (rows + i // SCENES_ACROSS)
            states = dict(states)
            cut = states.pop("cut", False)
            ## powered from a redstone block behind the lower dust
            put((cx - 2, 1, cz), ("minecraft:redstone_block", {}))
            put((cx - 1, 1, cz), wire)
            put((cx, 1, cz), (name, whole(name, states)))
            self.blocks[(cx, 2, cz)] = wire
            if cut:
                self.blocks[(cx - 1, 2, cz)] = (name, whole(name, states))
        powered(self.blocks)
        dusted(self, tweak)
        self._wide = max(x for x, _y, _z in self.blocks) + 2
        self.used = 1

    @property
    def wide(self):
        return self._wide

    def stand(self):
        middle = self.wide // 2
        return (middle, 1 + GHOST, middle)


## A small circuit of every kind of join at once: a powered line through a
## branch, a crossing, a climb and a drop, past a repeater into a piston, a
## comparator, an observer and a target, and up a slab and a glass block.
## (x, y, z), the block by its id's tail, and its states
CIRCUIT = [((1, 1, 1), "redstone_block", {})]
CIRCUIT += [((x, 1, 1), "redstone_wire", {}) for x in range(2, 7)]
CIRCUIT += [((7, 1, 1), "unpowered_repeater", {"minecraft:cardinal_direction": "west"}),
            ((8, 1, 1), "redstone_wire", {}), ((9, 1, 1), "redstone_wire", {}),
            ((10, 1, 1), "piston", {"facing_direction": 5})]
CIRCUIT += [((4, 1, z), "redstone_wire", {}) for z in range(2, 5)]
CIRCUIT += [((4, 1, 5), "stone", {}), ((4, 2, 5), "redstone_wire", {}),
            ((4, 1, 6), "stone", {}), ((4, 2, 6), "redstone_wire", {}),
            ((4, 1, 7), "redstone_wire", {}), ((4, 1, 8), "redstone_wire", {})]
CIRCUIT += [((x, 1, 8), "redstone_wire", {}) for x in range(5, 8)]
CIRCUIT += [((8, 1, 8), "unpowered_comparator", {"minecraft:cardinal_direction": "west"}),
            ((9, 1, 8), "redstone_wire", {})]
CIRCUIT += [((6, 1, z), "redstone_wire", {}) for z in (5, 6, 7, 9, 10)]
CIRCUIT += [((x, 1, 6), "redstone_wire", {}) for x in (5, 7, 8)]
CIRCUIT += [((9, 1, 6), "target", {}),
            ((6, 1, 11), "observer", {"minecraft:facing_direction": "north"}),
            ((3, 1, 8), "redstone_wire", {}),
            ((2, 1, 8), "smooth_stone_slab", {"minecraft:vertical_half": "top"}),
            ((2, 2, 8), "redstone_wire", {}),
            ((2, 1, 9), "glass", {}), ((2, 2, 9), "redstone_wire", {}),
            ((1, 1, 9), "redstone_wire", {})]


class CircuitGrid(Grid):
    """`CIRCUIT`, its dust powered from the redstone block and drawn with one
    tweak, or plain."""

    def __init__(self, title, tweak=None):
        super().__init__(1, 1, 1, title)
        for at, name, states in CIRCUIT:
            full = "minecraft:" + name
            self.blocks[at] = (full, whole_states(full, states))
            self.blocks.setdefault((at[0], 0, at[2]), ("minecraft:barrier", {}))
        powered(self.blocks)
        dusted(self, tweak)
        self._wide = max(x for x, _y, _z in self.blocks) + 2
        self.used = 1

    @property
    def wide(self):
        return self._wide

    def stand(self):
        middle = self.wide // 2
        return (middle, 1 + GHOST, middle)


class WaterTrialGrid(Grid):
    """A row per way of drawing a waterlogged block, a column per block, each
    signed with its trial; see tools/checks/water_trials.py."""

    def __init__(self, title="Waterlogging"):
        from tools.checks import water_trials as trials
        super().__init__(1, 1, 1, title)
        self.trial_at = {}
        for row, trial in enumerate(trials.TRIALS):
            z = 2 + 3 * row
            for col, (name, states) in enumerate(trials.BLOCKS):
                x = 2 + 3 * col
                at = (x, 1, z)
                self.blocks[at] = ("minecraft:" + name,
                                   whole_states("minecraft:" + name, states))
                self.water.add(at)
                self.blocks[(x, 0, z)] = ("minecraft:barrier", {})
                self.blocks[(x, 0, z - 1)] = ("minecraft:wall_sign", {"facing_direction": 2})
                self.entities[(x, 0, z - 1)] = sign("%s\n%s" % (trial, name.replace("_", " ")))
                self.trial_at[at] = trial
                if trial in trials.COPIES_BLOCK:
                    self.ghost_as[at] = trials.block(trial, name)
                if trial == "dry":
                    self.water_as[at] = None
                elif trial in trials.COPIES_WATER:
                    self.water_as[at] = trials.block(trial, "water")
        self._wide = max(x for x, _y, _z in self.blocks) + 2
        self.used = 1

    @property
    def wide(self):
        return self._wide

    def stand(self):
        middle = self.wide // 2
        return (middle, 1 + GHOST, middle)


## every container a count is drawn on, and each way it can face
FILL_FACINGS = {
    "chest": [{"minecraft:cardinal_direction": d} for d in ("north", "south", "east", "west")],
    "barrel": [{"facing_direction": f} for f in range(6)],
    "dispenser": [{"facing_direction": f} for f in range(6)],
    "dropper": [{"facing_direction": f} for f in range(6)],
    "hopper": [{"facing_direction": f} for f in (0, 2, 3, 4, 5)],
}
FILL_ACROSS = 9


class FillTrialGrid(Grid):
    """Every container a count is drawn on, filled, its count drawn one
    trial's way; see tools/checks/fill_trials.py. Each kind in every facing at
    three signals, every copper chest, double chests of each kind both ways
    round, and decorated pots. `trial_at` maps a container's place on the plot
    to the trial."""

    def __init__(self, trial):
        from scaffold import marks
        from scaffold.core import LEFT_HAND
        super().__init__(1, 1, 1, "Fill " + trial.replace("_", " "))
        self.trial_at = {}
        cells = [(block, states, signal, False) for block, facings in FILL_FACINGS.items()
                 for states in facings for signal in FILL_SIGNALS]
        north = {"minecraft:cardinal_direction": "north"}
        cells += [(block, north, 8, False) for block in marks.CHESTS if block != "chest"]
        for block in ("chest", "trapped_chest", "copper_chest", "oxidized_copper_chest"):
            for facing in ("north", "south", "east", "west"):
                cells.append((block, {"minecraft:cardinal_direction": facing}, 8, True))
        cells += [("decorated_pot", {"direction": 0}, signal, False) for signal in FILL_SIGNALS]
        for i, (block, states, signal, double) in enumerate(cells):
            x = 2 + 3 * (i % FILL_ACROSS)
            z = 2 + 3 * (i // FILL_ACROSS)
            at = (x, 1, z)
            name = "minecraft:" + block
            full = whole_states(name, states)
            self.blocks[at] = (name, full)
            self.blocks[(x, 0, z)] = ("minecraft:barrier", {})
            self.entities[at] = self.filled_entity(block, signal)
            self.trial_at[at] = trial
            if double:
                ## the right half on the left half's right, each naming the other
                left = LEFT_HAND[states["minecraft:cardinal_direction"]]
                dx, dz = -left[0], -left[1]
                other = (x + dx, 1, z + dz)
                self.blocks[other] = (name, full)
                self.blocks[(x + dx, 0, z + dz)] = ("minecraft:barrier", {})
                self.entities[at] = dict(self.entities[at], _pair=(dx, dz, 1))
                self.entities[other] = dict(self.filled_entity(block, 0), _pair=(-dx, -dz, 0))
                self.trial_at[other] = trial
        self._wide = max(max(x, z) for x, _y, z in self.blocks) + 2
        self.used = 1

    @staticmethod
    def filled_entity(block, signal):
        """A container's block entity holding the fewest items that give
        `signal`; a decorated pot's, its one stack."""
        from scaffold import marks
        if block == "decorated_pot":
            full, loose = marks.recipe(signal, 1)
            count = 64 if full else loose
            entity = {"id": String("DecoratedPot"),
                      "sherds": List[String]([String("minecraft:brick")] * 4)}
            if count:
                entity["item"] = _item("minecraft:cobblestone", count)
            return entity
        entity_id = FILLED.get(block, "Chest")
        return filled(Case(block, {}, None, ""), entity_id, signal).entity if signal else {
            "id": String(entity_id), "Items": List[Compound]([])}

    @property
    def wide(self):
        return self._wide

    def stand(self):
        middle = self.wide // 2
        return (middle, 1 + GHOST, middle)


def tiers_in_reach(wide, pitch):
    """The most tiers whose farthest case is still within reach of the stand."""
    across = ((wide / 2.0) ** 2 * 2) ** 0.5 + pitch
    up = max(0.0, REACH ** 2 - across ** 2) ** 0.5
    return max(1, int(2 * up // TIER))


def plan(title, count):
    """How a category's cases are laid out: as plots of (across, tiers, pitch,
    title, how many cases), widest pitch first, a plot no more than
    `PLOT_TIERS` high and `WIDE` across, a category too big for one cut into
    numbered plots."""
    for pitch in PITCHES:
        most_across = (WIDE - 3) // pitch + 1
        tiers = min(PLOT_TIERS, tiers_in_reach(WIDE, pitch))
        if count <= most_across ** 2 * tiers:
            need = -(-count // most_across ** 2)
            across = MIN_ACROSS
            while across ** 2 * need < count:
                across += 1
            return [(min(across, most_across), need, pitch, title, count)]
    per = most_across ** 2 * tiers
    parts = -(-count // per)
    return [(most_across, tiers, pitch, "%s %d/%d" % (title, n + 1, parts),
             min(per, count - n * per)) for n in range(parts)]


## ---- labels drawn in the ghosts ------------------------------------------

## how many blocks tall a plot's name is, and how far outside the plot it hangs
NAME_ROWS = 3
NAME_GAP = 2
## the colour of a name's panel and of its letters
NAME_COLOURS = ((30, 30, 34, 255), (250, 250, 250, 255))
## the shape every slice of a name is drawn on: a sheet a sixteenth thick,
## standing across z or across x
NAME_SHAPES = {
    "z": {"size": [[1, 1, 0.0625]], "offsets": [[0, 0, 0.46875]], "center": [0.5, 0.5, 0.5]},
    "x": {"size": [[0.0625, 1, 1]], "offsets": [[0.46875, 0, 0]], "center": [0.5, 0.5, 0.5]},
}
FACES = ("north", "south", "east", "west", "up", "down")


def name_tiles(title, folder, key, longest):
    """A plot's name, cut into one 16 by 16 tile per block of the panel.

    Answers the tiles' texture paths by (column, row), column 0 at the left of
    the words and row 0 at the top. The words are as large as fit in
    `longest` blocks across and `NAME_ROWS` down.
    """
    from PIL import Image, ImageDraw, ImageFont
    bold = os.path.join(ROOT, "scaffold", "fonts", "SourceSansPro-Bold.ttf")
    tall = NAME_ROWS * 16
    size = tall - 10
    while True:
        face = ImageFont.truetype(bold, size)
        box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), title, font=face)
        wide = box[2] - box[0] + 16
        if wide <= longest * 16 or size <= 10:
            break
        size -= 2
    cols = -(-wide // 16)
    image = Image.new("RGBA", (cols * 16, tall), NAME_COLOURS[0])
    draw = ImageDraw.Draw(image)
    draw.text(((cols * 16 - (box[2] - box[0])) / 2 - box[0],
               (tall - (box[3] - box[1])) / 2 - box[1]),
              title, font=face, fill=NAME_COLOURS[1])
    here = os.path.join(folder, "textures", "gallery")
    os.makedirs(here, exist_ok=True)
    tiles = {"blank": "textures/gallery/%s_blank" % key}
    Image.new("RGBA", (16, 16), NAME_COLOURS[0]).save(
        os.path.join(here, key + "_blank.png"))
    for c in range(cols):
        for r in range(NAME_ROWS):
            name = "%s_%d_%d" % (key, c, r)
            image.crop((c * 16, r * 16, c * 16 + 16, r * 16 + 16)).save(
                os.path.join(here, name + ".png"))
            tiles[(c, r)] = "textures/gallery/" + name
    return tiles, cols


## A panel on each side of a plot: where it stands across the plot, which axis
## its sheet lies across, the face looking out and the face looking in, and for
## each of those whether the words read with the coordinate along the side
## rising or falling. Every face reads the right way round from outside, so the
## face looking out reads correctly from outside the plot and the one looking
## in from inside it.
def name_sides(wide):
    near, far = -NAME_GAP, wide - 1 + NAME_GAP
    return (
        ("z", near, "north", -1, "south", +1),   # north side
        ("z", far, "south", +1, "north", -1),    # south side
        ("x", far, "east", -1, "west", +1),      # east side
        ("x", near, "west", +1, "east", -1),     # west side
    )


def name_blocks(grid, n, tiles, cols):
    """The blocks a plot's name is drawn with, and the families they need.

    Answers [(position, block id)] in the plot's own coordinates, at the height
    the ghosts are drawn from, and {block id: (shape, uv)}.
    """
    blocks, families = [], {}
    centre = grid.wide // 2
    first = centre - cols // 2
    for side, (axis, across, outer, outer_way, inner, inner_way) in enumerate(name_sides(grid.wide)):
        for c in range(cols):
            along = first + c
            for r in range(NAME_ROWS):
                ## drawn GHOST above where it is put, and above every ghost
                y = grid.top + (NAME_ROWS - 1 - r) - grid.lift + 1
                at = (along, y, across) if axis == "z" else (across, y, along)
                ## which column of the words this block shows, read from each side
                out_c = c if outer_way > 0 else cols - 1 - c
                in_c = c if inner_way > 0 else cols - 1 - c
                block = "scaffold:name_%d_%d_%d_%d" % (n, side, c, r)
                textures = {face: tiles["blank"] for face in FACES}
                textures[outer] = tiles[(out_c, r)]
                textures[inner] = tiles[(in_c, r)]
                uv = {"uv_sizes": {f: [[1, 1]] for f in FACES},
                      "offset": {f: [[0, 0]] for f in FACES},
                      "overwrite": {f: [textures[f]] for f in FACES}}
                blocks.append((at, block))
                families[block] = (NAME_SHAPES[axis], uv)
    return blocks, families


def with_names(families, folder, trials=False, variants=(), water_trials=False,
               fill_trials=None):
    """The geometry builder, with the name blocks' families added in memory,
    and the transparency trials when they are asked for."""
    base = core.asgc.ArmorStandGeo
    from tools.checks import trials as trial_families

    class NamedGeo(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            ## searched before the vanilla pack, the way a tweak's folder is
            self.tweak_folders = [folder] + list(self.tweak_folders)
            for block, (shape, uv) in families.items():
                family = block.replace(":", "_")
                self.defs[block] = family
                self.block_shapes[family] = {"default": shape}
                self.block_uv[family] = {"default": uv}
            if trials:
                trial_families.install(self, folder)
            if variants:
                from tools.checks import tweak_variants
                tweak_variants.install(self, variants, base)
            if water_trials:
                from tools.checks import water_trials as wet
                wet.install(self)
            if fill_trials is not None:
                from tools.checks import fill_trials as counts
                counts.install(self, folder)

        def make_block(self, x, y, z, block_name, *args, **kwargs):
            ## a trial's count or water top is drawn its trial's way; every plot
            ## has its own coordinates, so the plot's name is part of the key
            trial = (fill_trials or {}).get((self.name, (x, y, z)))
            from tools.checks import fill_trials as counts
            from tools.checks import water_trials as wet
            if trial in counts.TRIALS[1:] and block_name == "scaffold:fill":
                kwargs["family"] = counts.family_of(trial, self.defs[block_name])
            if trial in wet.TOP_FAMILIES and str(kwargs.get("family") or "").startswith(
                    "water_surface"):
                if wet.TOP_FAMILIES[trial] is None:
                    return None
                kwargs["family"] = wet.TOP_FAMILIES[trial]
            return super().make_block(x, y, z, block_name, *args, **kwargs)

        def get_block_texture_paths(self, block_name, *args, **kwargs):
            ## a trial reads the textures of the block it copies
            if str(block_name).startswith("scaffold:trial_"):
                block_name = trial_families.BASE
            if str(block_name).startswith("scaffold:wt_"):
                block_name = str(block_name).split("__", 1)[1]
            return super().get_block_texture_paths(block_name, *args, **kwargs)

    return NamedGeo


def into(world, grid, origin, labels=True):
    """One set's blocks, water and block entities, placed in the world, and
    its labels when they are asked for."""
    ox, oy, oz = origin
    for (x, y, z), (name, states) in grid.blocks.items():
        world.blocks[(ox + x, oy + y, oz + z)] = world.block(
            name, {k: _tag(v) for k, v in states.items()})
    for (x, y, z) in grid.water:
        world.water.add((ox + x, oy + y, oz + z))
    for (x, y, z), fields in grid.entities.items():
        world.block_entities[(ox + x, oy + y, oz + z)] = paired_fields(
            fields, ox + x, oz + z)
    sx, sy, sz = grid.stand()
    world.blocks[(ox + sx, oy + sy - 1, oz + sz)] = world.block("minecraft:barrier", {})
    barrier = world.block("minecraft:barrier", {})
    for row, motive in (grid.labels() if labels else ()):
        for along in (grid.wide // 2,):
            for wall, inward, outward in label_walls(grid.wide):
                for facing in (inward, outward):
                    block, cells, centre = painting(facing, wall, row, along)
                    for at in cells:
                        world.blocks[(ox + block[0] + at[0], oy + block[1] + at[1],
                                      oz + block[2] + at[2])] = barrier
                    world.entities.append((
                        "minecraft:painting",
                        (ox + centre[0], oy + centre[1], oz + centre[2]),
                        PAINTING_YAW[facing],
                        ## the game saves the motive as Motif and the
                        ## direction twice, as Dir and as Direction
                        {"Motif": String(motive), "Dir": Byte(facing),
                         "Direction": Byte(facing),
                         "TileX": Int(ox + block[0]), "TileY": Int(oy + row),
                         "TileZ": Int(oz + block[2])}))


## Which painting says which row is which. Both are four wide and two tall,
## the most a seven high tier has room for twice over, and their art is replaced
## by `label_pack`.
REAL = "passage"
GHOST_LABEL = "finding"
LABEL_ART = {REAL: ("REAL", (40, 120, 60)), GHOST_LABEL: ("GHOST", (60, 80, 150))}
## a painting's Direction, as Bedrock numbers it, and the yaw facing that way
PAINTING_YAW = {0: 0.0, 1: 90.0, 2: 180.0, 3: 270.0}


## how far outside the set a label wall stands, in blocks of air between them
LABEL_GAP = 2


def painting(facing, wall, row, along):
    """One label painting, hung on one face of a wall.

    `wall` is where the wall stands across the axis it blocks, `along` where on
    it the painting is centred, and `facing` the painting's Direction: 0 south,
    1 west, 2 north, 3 east. Answers the wall block, the wall's blocks behind
    the painting as offsets along the wall, and the middle of the painting,
    which is where Bedrock keeps a painting's position.

    A painting four wide covers the two blocks either side of its middle
    whichever way it faces, which is how the game lays out two on opposite
    faces of one wall, and stands one sixteenth off the wall.
    """
    thin = 1 / 32.0
    spread = (-2, -1, 0, 1)
    if facing in (1, 3):     # on a wall running north to south
        block = (wall, row, along)
        x = wall + 1 + thin if facing == 3 else wall - thin
        centre = (x, row + 1, along)
        cells = [(0, dy, d) for dy in (0, 1) for d in spread]
    else:                    # on a wall running west to east
        block = (along, row, wall)
        z = wall + 1 + thin if facing == 0 else wall - thin
        centre = (along, row + 1, z)
        cells = [(d, dy, 0) for dy in (0, 1) for d in spread]
    return block, cells, centre


def label_walls(wide):
    """Each side's wall, and the two ways the paintings on it face: in towards
    the plot and out away from it, so a label reads from either side."""
    near, far = -1 - LABEL_GAP, wide + LABEL_GAP
    return ((far, 1, 3), (near, 3, 1),      # east and west walls
            (far, 2, 0), (near, 0, 2))      # south and north walls


def label_pack(folder):
    """A resource pack giving the two label paintings their words."""
    from PIL import Image, ImageDraw, ImageFont
    art = os.path.join(folder, "textures", "painting")
    os.makedirs(art)
    bold = os.path.join(ROOT, "scaffold", "fonts", "SourceSansPro-Bold.ttf")
    for motive, (words, colour) in LABEL_ART.items():
        image = Image.new("RGBA", (256, 128), colour + (255,))
        draw = ImageDraw.Draw(image)
        ## as large as fits inside the frame, the same size for every word
        ## that fits at it
        size = 92
        while True:
            face = ImageFont.truetype(bold, size)
            box = draw.textbbox((0, 0), words, font=face)
            if box[2] - box[0] <= 216:
                break
            size -= 2
        draw.rectangle((4, 4, 251, 123), outline=(240, 240, 240, 255), width=6)
        box = draw.textbbox((0, 0), words, font=face)
        draw.text(((256 - (box[2] - box[0])) / 2 - box[0],
                   (128 - (box[3] - box[1])) / 2 - box[1]),
                  words, font=face, fill=(250, 250, 250, 255))
        image.save(os.path.join(art, motive + ".png"))
        ## the painting's own texture set names a second map that would be
        ## laid over the words, so the label carries one naming its colour only
        json.dump({"format_version": "1.21.30", "minecraft:texture_set": {
            "color": motive}},
            open(os.path.join(art, motive + ".texture_set.json"), "w"), indent=2)
    header = str(uuid.uuid5(uuid.NAMESPACE_URL, "scaffold gallery labels"))
    json.dump({"format_version": 2, "header": {
        "name": NAME + " labels", "description": "REAL and GHOST paintings.",
        "uuid": header, "version": [1, 0, 0], "min_engine_version": [1, 21, 0]},
        "modules": [{"type": "resources", "version": [1, 0, 0],
                     "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, "scaffold gallery labels rp"))}]},
        open(os.path.join(folder, "manifest.json"), "w"), indent=2)
    return header


def write_world(path, pack, sets, version, name=NAME, labels=True, per_batch=None):
    """One .mcworld, built whole: the blocks, the stands, the packs, the rules.

    `pack` is the ghost pack, or None for a world of the real blocks alone.
    """
    import zipfile
    from tools.checks import worldfile
    work = tempfile.mkdtemp(prefix="scaffold-gallery-world-")
    try:
        world = worldfile.World(version)
        for origin, grid, tag in sets:
            into(world, grid, origin, labels)
            sx, sy, sz = grid.stand()
            ## facing north, which is how the ghosts line up with the set, and
            ## named, which is what picks this set's ghosts
            world.entities.append(("minecraft:armor_stand",
                                   (origin[0] + sx + 0.5, origin[1] + sy,
                                    origin[2] + sz + 0.5), 180.0,
                                   {"CustomName": String(tag),
                                    "CustomNameVisible": Byte(0)}))
        worldfile.write_db(os.path.join(work, "db"), world.items(), per_batch)
        origin, grid, _tag = sets[0]
        sx, sy, sz = grid.stand()
        ## a spectator flies, so anywhere near the first stand will do
        spawn = (origin[0] + sx, origin[1] + sy + 2, origin[2] + sz + grid.pitch)
        worldfile.level_dat(os.path.join(work, "level.dat"), name, spawn,
                            simulation=SIMULATION)
        open(os.path.join(work, "levelname.txt"), "w").write(name)
        packs = []
        if labels:
            packs.append({"pack_id": label_pack(os.path.join(work, "resource_packs", "labels")),
                          "version": [1, 0, 0]})
        if pack:
            ghosts = os.path.join(work, "resource_packs", "ghosts")
            with zipfile.ZipFile(pack) as z:
                z.extractall(ghosts)
            header = json.load(open(os.path.join(ghosts, "manifest.json")))["header"]
            packs.append({"pack_id": header["uuid"], "version": header["version"]})
        if packs:
            json.dump(packs, open(os.path.join(work, "world_resource_packs.json"), "w"))
        if os.path.exists(path):
            os.remove(path)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
            for here, _dirs, files in os.walk(work):
                for one in files:
                    full = os.path.join(here, one)
                    out.write(full, os.path.relpath(full, work).replace(os.sep, "/"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="shape families or block ids")
    parser.add_argument("--all", action="store_true", help="every family")
    parser.add_argument("--every-block", action="store_true",
                        help="every block of a family, not only the first")
    parser.add_argument("--one-block", action="store_true",
                        help="only the first block of each named family")
    parser.add_argument("--output", default=os.getcwd())
    parser.add_argument("--name", default=NAME, help="the world's name")
    parser.add_argument("--no-ghosts", action="store_true",
                        help="the real blocks alone, with no ghost pack")
    parser.add_argument("--tweak-world", action="store_true",
                        help="every block a Bedrock Tweak or a Clearer Redstone "
                             "option changes, in a plot per tab, built with them on")
    parser.add_argument("--low", action="store_true",
                        help="a block of every family with a simpler form, built "
                             "with low geometry")
    parser.add_argument("--dust-world", action="store_true",
                        help="redstone dust: the dust structure, the joins, and a "
                             "circuit drawn plain and with each dust tweak")
    parser.add_argument("--fill-trials", action="store_true",
                        help="a filled hopper in every facing, its count drawn "
                             "three ways, to find why it cuts holes in the hopper")
    parser.add_argument("--water-trials", action="store_true",
                        help="waterlogged blocks drawn five ways, to find "
                             "why water hides what stands in it")
    parser.add_argument("--trials", action="store_true",
                        help="three calibrated sculk sensors whose ghosts try "
                             "three ways round a plane's clear texels")
    parser.add_argument("--dust-tweaks", action="store_true",
                        help="with --structure, the structure again once per "
                             "dust tweak, its dust drawn with that tweak")
    parser.add_argument("--structure", action="append", default=[], metavar="FILE",
                        help="a structure placed as it was saved, on a plot of "
                             "its own; may be given more than once")
    parser.add_argument("--waterlogged", nargs="*", default=[], metavar="BLOCK",
                        help="blocks whose every case also gets a copy standing "
                             "in water")
    parser.add_argument("--exact", action="store_true",
                        help="a name that is a block id is that block alone, "
                             "not the family sharing its name")
    parser.add_argument("--most", type=int, default=None, metavar="N",
                        help="a block with more cases than this shows every "
                             "value of every state once rather than every "
                             "combination")
    parser.add_argument("--signs", action="store_true",
                        help="a sign under every case naming its states, not "
                             "only under doors, trapdoors and glazed terracotta")
    parser.add_argument("--no-labels", action="store_true",
                        help="no REAL and GHOST paintings")
    parser.add_argument("--skip-technical", action="store_true",
                        help="leave out blocks the game keeps for itself")
    ## for finding what a world the game will not load is choking on
    parser.add_argument("--part", default=None, metavar="N/OF",
                        help="only the Nth of OF equal parts of the cases, in order")
    parser.add_argument("--stand-in", default=None, metavar="BLOCK",
                        help="every case drawn as this block, with no block entity")
    parser.add_argument("--per-batch", type=int, default=None,
                        help="write the database this many keys to a batch")
    args = parser.parse_args(argv)
    if not (args.names or args.all or args.structure or args.waterlogged or args.trials
            or args.tweak_world or args.low or args.dust_world or args.water_trials
            or args.fill_trials):
        parser.error("name a family or a block, or pass --all")

    global MOST_PER_BLOCK, WATERLOG
    MOST_PER_BLOCK = args.most
    tweaks_on, groups, variants = [], {}, []
    if args.tweak_world:
        tweaks_on, variants = tweak_world()
        ## the dust plots draw each dust tweak's version of the wire
        for title, tweak, _plot in DUST_TWEAKS:
            if (title, tweak, "redstone_wire") not in variants:
                variants.append((title, tweak, "redstone_wire"))
        args.exact = True
        names = []
        for _title, _tweak, name in variants:
            if name not in names:
                names.append(name)
        args.names = names + [b for b in list(FILLED) + ["crafter"] if b not in names]
        args.waterlogged = [b for b in args.names
                            if b in WATERLOGGABLE or WATERLOGGABLE_KINDS.search(b)]
        groups = collections.OrderedDict([("Bedrock Tweaks", []), ("Clearer Redstone", [])])
        for title, tweak, name in variants:
            print("%-17s %-36s %s" % (title, tweak, name))
    if args.low:
        args.names = list(args.names) + low_blocks()
        args.exact = True
    WATERLOG = {name.replace("minecraft:", "") for name in args.waterlogged}
    named = list(args.names)
    args.names = list(args.names) + [n for n in args.waterlogged if n not in args.names]
    picked = choose(args.names, args.every_block, args.all, args.exact)
    if args.one_block:
        picked = collections.OrderedDict((f, b[:1]) for f, b in picked.items())
    cases, version = all_cases(picked)
    if args.low:
        ## a block whose simpler form is one shape however it is attached
        ## shows it once
        seen = set()
        kept = []
        for family, case in cases:
            if case.block in LOW_ONE_CASE:
                if case.block in seen:
                    continue
                seen.add(case.block)
            kept.append((family, case))
        cases = kept
    ## a case's plot, and the block its ghost is drawn as instead, for the
    ## tweak world; keyed by the case's place in `cases`
    placed_as = {}
    if args.tweak_world:
        from tools.checks import tweak_variants
        by_block = collections.defaultdict(list)
        for family, case in cases:
            by_block[case.block].append((family, case))
        ## A tweak's own family may read states and block entity fields the
        ## plain one does not, a hive's honey or a jukebox's disc, so each
        ## (tweak, block) lists its cases from that tweak's tables.
        from scaffold.pack import armor_stand_geo_class as asgc
        mojang_states, values = mojang()
        base, _newest = observed()
        builders, own_cases = {}, {}
        for _title, tweak, name in variants:
            if tweak not in builders:
                builders[tweak] = asgc.ArmorStandGeo("tweak", offsets=[0, 0, 0], tweaks=[tweak])
            geo = builders[tweak]
            family = geo.defs.get(name)
            if not family or family == "ignore":
                continue
            listed = [(family, c) for c in cases_for(
                name, family, mojang_states, values, base, geo.block_shapes,
                geo.block_rotations, geo.rules)]
            own_cases[(tweak, name)] = listed or by_block.get(name, [])
        tweaked = []
        varied = {(tweak, name) for _title, tweak, name in variants}
        for title, tweak, name in variants:
            for family, case in own_cases.get((tweak, name), by_block.get(name, ())):
                tweaked.append((family, case._replace(
                    label=("tweak=%s %s" % (tweak, case.label)).strip())))
                ## a piston's head is a block of its own beside it, drawn as
                ## the tweak's version too when the tweak changes it
                beside = [((dx, dy, dz), tweak_variants.block(tweak, other))
                          for dx, dy, dz, other, _s, _e in case.extra
                          if (tweak, other) in varied]
                placed_as[len(tweaked) - 1] = (title, tweak_variants.block(tweak, name), beside)
        ## each container filled to three signals and a crafter with slots
        ## locked, drawn as themselves with the marks the pack is built with
        for family, case in cases:
            if case.entity:
                continue
            if case.block in FILLED and not any(
                    c.block == case.block and "signal" in c.label for _f, c in tweaked):
                for strength in FILL_SIGNALS:
                    tweaked.append((family, filled(case, FILLED[case.block], strength)))
                    placed_as[len(tweaked) - 1] = ("Clearer Redstone", None, [])
            elif case.block == "crafter" and not any(
                    c.block == "crafter" and "locked" in c.label for _f, c in tweaked):
                tweaked.append((family, locked(case)))
                placed_as[len(tweaked) - 1] = ("Clearer Redstone", None, [])
        for family, case in cases:
            if case.block in PLAIN_ON_TWEAK_PLOT and not case.entity:
                tweaked.append((family, case._replace(label=("plain " + case.label).strip())))
                placed_as[len(tweaked) - 1] = ("Bedrock Tweaks", None, [])
        cases = tweaked
    ## a block named only to be waterlogged shows one case dry and one wet
    only_wet = WATERLOG - set(n.replace("minecraft:", "") for n in named)
    kept, seen = [], set()
    for family, case in cases:
        if case.block in only_wet:
            wet = case.label.endswith(WATERLOGGED)
            if (case.block, wet) in seen:
                continue
            seen.add((case.block, wet))
        kept.append((family, case))
    cases = kept
    if args.skip_technical:
        cases = [(f, c) for f, c in cases if not TECHNICAL.match(c.block)]
    if args.part:
        which, of = (int(v) for v in args.part.split("/"))
        size = -(-len(cases) // of)
        cases = cases[(which - 1) * size:which * size]
    if args.stand_in:
        cases = [(f, Case(args.stand_in, {}, None, c.block + " " + c.label))
                 for f, c in cases]
    if not cases and not (args.structure or args.trials or args.dust_world
                          or args.water_trials or args.fill_trials):
        sys.exit("nothing to show")
    ## a plot per category of the block list, in the list's own order, and
    ## more than one for a category too big to walk round
    from scaffold import block_list
    by_category = collections.OrderedDict((name, []) for name in block_list.order())
    if groups:
        by_category = collections.OrderedDict((title, []) for title in groups)
    for index, (family, case) in enumerate(cases):
        if groups:
            title, ghost, beside = placed_as[index]
            by_category[title].append((family, case, (ghost, beside)))
            continue
        by_category[block_list.category_of("minecraft:" + case.block)].append(
            (family, case, (None, [])))
    grids = []
    for title, members in by_category.items():
        if not members:
            continue
        start = 0
        for across, tiers, pitch, named, count in plan(title, len(members)):
            grid = Grid(across, tiers, pitch, named,
                        lambda family: args.signs or bool(SIGNED.search(family)))
            for family, case, (ghost, beside) in members[start:start + count]:
                grid.add(family, case)
                at = grid.key[-1][2]
                if ghost:
                    grid.ghost_as[at] = ghost
                for step, other in beside:
                    grid.ghost_as[tuple(a + b for a, b in zip(at, step))] = other
            start += count
            grids.append(grid)
    for path in args.structure:
        grids.append(StructureGrid(path))
        if args.dust_tweaks:
            base = os.path.splitext(os.path.basename(path))[0]
            for _group, tweak, title in DUST_TWEAKS:
                grids.append(StructureGrid(path, "%s %s" % (base, title), tweak))
    if args.dust_world:
        grids.append(DustGrid(None, "Plain dust"))
        grids.append(DustJoinGrid())
        grids.append(DustJoinGrid("Dust joins wire", DUST_TWEAKS[1][1]))
        grids.append(CircuitGrid("Dust circuit"))
        for _group, tweak, title in DUST_TWEAKS:
            grids.append(CircuitGrid(title + " circuit", tweak))
    if args.water_trials:
        grids.append(WaterTrialGrid())
    if args.fill_trials:
        from tools.checks import fill_trials as counts
        for trial in counts.TRIALS:
            grids.append(FillTrialGrid(trial))
        tweaks_on = list(MARK_TWEAKS)
    if args.trials:
        from tools.checks import trials as trial_families
        grid = Grid(MIN_ACROSS, 1, PITCHES[0], "Transparency trials",
                    lambda family: True)
        for trial in trial_families.TRIALS:
            grid.add(trial_families.BASE, Case(trial_families.BASE,
                                               dict(trial_families.STATES), None,
                                               "trial " + trial))
            grid.ghost_as[grid.key[-1][2]] = trial_families.block(trial)
        grids.append(grid)

    ## plots side by side along x, a new row along z when a row is long enough
    origins, x, z, row_deep = [], 0, 0, 0
    for grid in grids:
        reach = max(grid.wide, 2 * NAME_GAP + 24) + 2 * (LABEL_GAP + 2)
        if x and x + reach > ROW_LENGTH:
            x, z, row_deep = 0, z + row_deep + PLOT_GAP, 0
        origins.append((x + LABEL_GAP + 2, BASE_Y, z + LABEL_GAP + 2))
        x += reach + PLOT_GAP
        row_deep = max(row_deep, reach)

    os.makedirs(args.output, exist_ok=True)
    work = tempfile.mkdtemp(prefix="scaffold-gallery-")
    real = core.asgc.ArmorStandGeo
    try:
        sets, families = [], {}
        textures = os.path.join(work, "names")
        shifts = []
        for n, grid in enumerate(grids, 1):
            tiles, cols = name_tiles(grid.title, textures, "plot%d" % n,
                                     max(grid.wide, 24))
            blocks, made = name_blocks(grid, n, tiles, cols)
            families.update(made)
            path = os.path.join(args.output, "gallery_%d.mcstructure" % n)
            shifts.append((path, grid.save(path, version, blocks)))
        if args.dust_world or args.dust_tweaks:
            variants = variants + [(title, tweak, "redstone_wire")
                                   for title, tweak, _plot in DUST_TWEAKS]
        ## each fill trial's hopper, where the builder will find it
        fill_at = None
        if args.fill_trials or args.water_trials:
            fill_at = {}
            for n, (grid, (_path, shift)) in enumerate(zip(grids, shifts), 1):
                for (gx, gy, gz), trial in getattr(grid, "trial_at", {}).items():
                    fill_at[("plot_%d" % n, (gx + shift[0], gy + shift[1], gz + shift[2]))] = trial
        core.asgc.ArmorStandGeo = with_names(families, textures, args.trials,
                                             [(t, n) for _title, t, n in variants],
                                             args.water_trials, fill_at)
        builder = core.Scaffold(os.path.join(work, NAME))
        ## a tweak's dust, drawn as a block of its own, is still dust
        builder.dust.dust.append(VARIANT_DUST)
        builder.dust.add({"blocks": [VARIANT_DUST], "faces": "all"})
        ## a ghost to be read against a real block is as solid as one
        builder.set_opacity(1.0)
        if tweaks_on:
            builder.set_tweaks(tweaks_on)
        if args.low:
            builder.set_low_geometry(True)
        for n, (grid, origin, (path, shift)) in enumerate(zip(grids, origins, shifts), 1):
            tag = "plot %d" % n
            sets.append((origin, grid, tag))
            stand = grid.stand()
            builder.add_model(tag, path)
            ## a ghost at its block's place plus the plot's lift, with the
            ## stand in the middle: an offset moves the model east, up and
            ## south, and the structure was shifted to take in the plot's name
            builder.set_model_offset(tag, [-stand[0] - shift[0],
                                           grid.lift - stand[1] - shift[1],
                                           -stand[2] - shift[2]])
        builder.generate_with_nametags()
        pack = builder.compile_pack(overwrite=True)
        kept = os.path.join(args.output, NAME + ".mcpack")
        shutil.copy(pack, kept)
        write_world(os.path.join(args.output, args.name + ".mcworld"),
                    None if args.no_ghosts else kept, sets, version,
                    name=args.name, labels=not args.no_labels,
                    per_batch=args.per_batch)
    finally:
        core.asgc.ArmorStandGeo = real
        shutil.rmtree(work, ignore_errors=True)

    with io.open(os.path.join(args.output, NAME + " key.tsv"), "w", encoding="utf-8") as f:
        f.write("plot\tcategory\tblock x\tblock y\tblock z\tghost y\tfamily\tblock\tcase\n")
        for (origin, grid, tag) in sets:
            for family, case, (x, y, z) in grid.key:
                f.write("%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\t%s\n" % (
                    tag, grid.title, origin[0] + x, origin[1] + y, origin[2] + z,
                    origin[1] + y + grid.lift, family, case.block, case.label))
    skipped = builder.get_skipped(write_file=False)
    print("%d cases in %d plots, the largest %d across and %d tiers, in %s" % (
        len(cases), len(grids), max(g.wide for g in grids),
        max(g.tiers for g in grids), args.output))
    if skipped:
        print("drew no ghost for: %s" % ", ".join(sorted(skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
