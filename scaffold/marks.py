"""What a block entity says that is drawn as a mark beside the block.

Some of what Clearer Redstone shows is not in a block's states and is not a
picture of the block either: how full a container is, which of a crafter's slots
are locked. Each is drawn as a mark, a small pseudo-block at the same position,
named `scaffold:<something>` and drawn by a family of its own like any other
block. A mark is only drawn when a tweak defines its family; with none on,
`made` still answers and nothing draws what it says.

**How full a container is, as what to put in it.** A comparator reads a
container as the sum, over its slots, of how many items are in each out of how
many make a full stack, and turns that into a signal from 0 to 15. A mark shows
the fewest items that give the same signal, as full slots and loose items out
of 64: `5+37` is five full slots, each a whole stack or one item that does not
stack, and thirty-seven more of something that stacks to 64. The text depends
only on the slot count and the signal, so `recipe` is all the art needs and the
sheets of it are drawn ahead of time by `tools/vendor/redstone.py`.

A double chest is read the way a comparator reads either half: both halves'
items over fifty-four slots, written once, on the left half.
"""
import fnmatch
import json
import math
from fractions import Fraction

from scaffold import paths
from scaffold import lookup

FILL = "scaffold:fill"
CRAFTER_SLOT = "scaffold:crafter_slot"

## The containers a count is drawn on: how many slots each has and where on
## the block the count goes. `chest` is the top of a chest, which is lower and
## narrower than a whole block; `block` the top of a whole one; `hopper` the
## four sides of a hopper's bowl; `pot` the four sides of a decorated pot's
## body, which holds one stack.
CHESTS = ["chest", "trapped_chest"] + [
    wax + age + "copper_chest" for wax in ("", "waxed_")
    for age in ("", "exposed_", "weathered_", "oxidized_")]
CONTAINERS = dict({name: (27, "chest") for name in CHESTS},
                  barrel=(27, "block"), dispenser=(9, "block"),
                  dropper=(9, "block"), hopper=(5, "hopper"),
                  decorated_pot=(1, "pot"))

## every slot count a count may be drawn for, a double chest's included
SLOT_COUNTS = (1, 5, 9, 27, 54)

## a numbered facing, as the words a mark is turned by; up and down have no
## front to read from, so they read as north
FACING_WORDS = {2: "north", 3: "south", 4: "west", 5: "east"}

_stacks = None


def stack_size(item):
    """How many of an item make a full stack."""
    global _stacks
    if _stacks is None:
        table = lookup.entries("stack_sizes.json")
        _stacks = [(int(size), patterns) for size, patterns in table.items()
                   if size.isdigit()]
    name = str(item).replace("minecraft:", "")
    for size, patterns in _stacks:
        if any(fnmatch.fnmatchcase(name, p) for p in patterns):
            return size
    return 64


def stacks(items):
    """How many full slots these items amount to, as a comparator counts."""
    total = Fraction(0)
    for item in items or ():
        name = str(item.get("Name", ""))
        count = int(item.get("Count", 0))
        if name and count > 0:
            total += Fraction(count, stack_size(name))
    return total


def signal(items, slots):
    """The signal a comparator reads from these items in this many slots."""
    total = stacks(items)
    if total <= 0:
        return 0
    return min(15, math.floor(1 + total / slots * 14))


def recipe(strength, slots):
    """(full slots, loose items out of 64): the fewest items that give a signal.

    One loose item is the least that gives 1. Every other signal needs the sum
    to reach (signal - 1) / 14 of the slots, and what is short of a whole slot
    is rounded up to the next item.
    """
    if strength <= 0:
        return 0, 0
    if strength == 1:
        return 0, 1
    need = Fraction(strength - 1) * slots / 14
    whole = math.floor(need)
    return whole, math.ceil((need - whole) * 64)


def text(strength, slots):
    """A count as it is written: full slots, a plus, and loose items."""
    return "%d+%d" % recipe(strength, slots)


def _facing(states):
    if "minecraft:cardinal_direction" in states:
        return str(states["minecraft:cardinal_direction"]).strip("'\"")
    try:
        return FACING_WORDS.get(int(states.get("facing_direction", 2)), "north")
    except (TypeError, ValueError):
        return "north"


def _partner_items(struct, x, y, z, entity):
    """The items in the other half of a double chest, or none."""
    origin = getattr(struct, "origin", (0, 0, 0))
    try:
        there = (int(entity["pairx"]) - int(origin[0]),
                 int(entity["pairz"]) - int(origin[2]))
    except (KeyError, TypeError, ValueError):
        return []
    if not hasattr(struct, "get_block_entity"):
        return []
    return list(struct.get_block_entity(there[0], y, there[1]).get("Items") or ())


def made(struct, x, y, z, block, entity):
    """The marks to draw at one position, as blocks: `{"name", "states"}`."""
    name = str(block.get("name", "")).replace("minecraft:", "")
    states = block.get("states", {})
    found = []
    if entity and name in CONTAINERS:
        slots, mount = CONTAINERS[name]
        items = list(entity.get("Items") or ())
        ## a decorated pot keeps its one stack as `item`
        if not items and entity.get("item"):
            items = [entity["item"]]
        side = entity.get("pair")
        if side == "right":
            items = None
        elif side == "left":
            items += _partner_items(struct, x, y, z, entity)
            slots, mount = slots * 2, "chest_left"
        if items is not None:
            found.append({"name": FILL, "states": {
                "mount": mount, "slots": slots, "signal": signal(items, slots),
                "minecraft:cardinal_direction": _facing(states)}})
    if entity and str(entity.get("id", "")) == "Crafter":
        try:
            locked = int(entity.get("disabled_slots", 0))
        except (TypeError, ValueError):
            locked = 0
        for slot in range(9):
            if locked >> slot & 1:
                found.append({"name": CRAFTER_SLOT, "states": dict(
                    {"slot": slot}, **({"orientation": states["orientation"]}
                                       if "orientation" in states else {}))})
    return found
