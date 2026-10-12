"""Which way redstone dust runs, worked out from the blocks round it.

Bedrock saves a dust block's signal and nothing else: which of its sides join
something is decided by the game as it draws, from the neighbours, and never
written down. So a structure's dust is joined here, with the rules in
`lookups/dust_connections.json`, and handed to the dust family as four states,
`scaffold:dust_<side>`, each `none`, `side` or `up`, which its `data` rule joins
into the name of a form.

A side joins:

  up     when the dust one block up and over is there, the block above this
         dust does not cut it off (is not a conductor) and the block beside
         can hold dust on top; drawn up the side only of a whole block, and
         joined flat, `side`, up a slab or a hopper
  side   when the block beside draws dust toward the face it turns to this
         dust, or when the block beside is not a conductor and dust is one
         block down and over

**What draws dust is the table's, not the code's.** A rule names blocks by
pattern, the faces that draw dust, and how to read the block's facing; a face
is `front`, `back` or `sides` relative to that facing, or `all`. Bedrock and
Java differ in places, a piston chief among them, and the table is Bedrock's.

**Add-on blocks join through `Connections.add`.** A custom block says in its
behaviour pack which faces join a circuit, `minecraft:redstone_producer`'s
`connected_faces`, and whether it carries power, `minecraft:redstone_
conductivity`. A reader for an add-on hands those over as rules of the same
shape as the table's, ahead of the table's own.
"""
import fnmatch
import io
import json

from scaffold import paths
from scaffold.block_geometry import plain

TABLE = "dust_connections.json"
STATE = "scaffold:dust_%s"
SIDES = {"north": (0, 0, -1), "east": (1, 0, 0), "south": (0, 0, 1), "west": (-1, 0, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east",
            "up": "down", "down": "up"}
EVERY = ("north", "south", "east", "west", "up", "down")
NONE, SIDE, UP = "none", "side", "up"


def _named(pattern, name):
    """A block id against a pattern, with `minecraft:` optional on either."""
    bare = name.replace("minecraft:", "")
    return fnmatch.fnmatchcase(name, pattern) or fnmatch.fnmatchcase(
        bare, pattern.replace("minecraft:", ""))


def _states_match(when, states):
    for state, values in when.items():
        if state not in states:
            return False
        value = states[state]
        if not any(value == v or plain(value) == plain(v) for v in values):
            return False
    return True


def matches(entries, block):
    """Whether a block is one of `entries`: patterns, or {"block", "when"}."""
    name, states = block["name"], block.get("states") or {}
    for entry in entries:
        if isinstance(entry, str):
            if _named(entry, name):
                return True
        elif _named(entry["block"], name) and _states_match(entry.get("when", {}), states):
            return True
    return False


class Connections:
    """The rules, and the questions the dust asks of its neighbours."""

    def __init__(self, table=None):
        if table is None:
            with io.open(paths.lookup(TABLE), encoding="utf-8") as f:
                table = json.load(f)
        self.dust = list(table["dust"])
        self.directions = dict(table["directions"])
        self.rules = list(table["attract"])
        self.not_conductors = list(table["not_conductors"])
        self.holds = list(table["holds_dust"])

    def add(self, rule, directions=None):
        """A rule from elsewhere, an add-on's block, read before the table's."""
        self.rules.insert(0, rule)
        self.directions.update(directions or {})

    def is_dust(self, block):
        return block is not None and matches(self.dust, block)

    def faces(self, block):
        """The sides of a block that draw dust toward them, as world sides."""
        for rule in self.rules:
            if not any(_named(p, block["name"]) for p in rule["blocks"]):
                continue
            if rule["faces"] == "all":
                return set(EVERY)
            facing = rule.get("facing")
            states = block.get("states") or {}
            front = None
            if facing and facing["state"] in states:
                front = self.directions[facing["by"]].get(plain(states[facing["state"]]))
            found = set()
            for face in rule["faces"]:
                if face in EVERY:
                    found.add(face)
                elif front is None:
                    continue
                elif face == "front":
                    found.add(front)
                elif face == "back":
                    found.add(OPPOSITE[front])
                elif face == "sides":
                    found.update(s for s in EVERY if s not in (front, OPPOSITE[front]))
            return found
        return set()

    def conductor(self, block, solid):
        """Whether a block carries power through it, and so cuts dust running
        past its corner: a whole block that is not on the table's list."""
        if block is None or block["name"] == "minecraft:air":
            return False
        return not matches(self.not_conductors, block) and solid(block)

    def holds_dust(self, block, solid):
        if block is None:
            return False
        return self.conductor(block, solid) or matches(self.holds, block)

    def sides(self, block_at, x, y, z, solid):
        """{side: none, side or up} for the dust at x, y, z.

        `block_at(x, y, z)` answers the block there or None, and `solid(block)`
        whether a block is a whole cube."""
        above = block_at(x, y + 1, z)
        clear_above = not self.conductor(above, solid)
        found = {}
        for side, (dx, dy, dz) in SIDES.items():
            beside = block_at(x + dx, y, z + dz)
            joined = NONE
            if (clear_above and self.is_dust(block_at(x + dx, y + 1, z + dz))
                    and self.holds_dust(beside, solid)):
                ## it climbs a whole block's side; up a slab or a hopper it
                ## joins with nothing drawn on the side
                joined = UP if solid(beside) else SIDE
            elif beside is not None and OPPOSITE[side] in self.faces(beside):
                joined = SIDE
            elif (not self.conductor(beside, solid)
                    and self.is_dust(block_at(x + dx, y - 1, z + dz))):
                joined = SIDE
            found[STATE % side] = joined
        return found
