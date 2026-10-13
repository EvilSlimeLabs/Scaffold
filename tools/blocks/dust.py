"""Redstone dust, a form for every way its four sides can join.

    python -m tools.blocks.dust

`scaffold/dust.py` works out which sides of a dust join something and hands
them over as `scaffold:dust_<side>`, each `none`, `side` or `up`; the family's
`data` rule joins the four, north, east, south and west, into the form's name,
`side-none-up-none`. A dust joined to nothing is the whole cross, as Bedrock
draws it.

Dust reads the game's grey cross and line, `redstone_dust_cross_grey` and
`redstone_dust_line_grey`, tinted by the colour its power gives it, so every
power level draws in its own shade. A tweak that repaints the dust keeps grey
copies under the same names, which are read first, so it is tinted the same:

  a straight run   dust joined along one axis only, one end or both: the line
                   across the whole block, turned a quarter for north and
                   south, as Bedrock draws it with no dot in the middle
  anything else    the cross in pieces, the middle eight pixels square and an
                   arm, the strip from the middle to its edge, for each joined
                   side; joined to nothing, all four
  a climb          the line stood upright on the wall of the block the dust
                   runs up, a hair off it
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.blocks import tables

FAMILY = "red_dust"
SIDES = ("north", "east", "south", "west")
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
JOINS = ("none", "side", "up")
## how far above the floor the dust lies, and how far off a wall it climbs
LIFT = 0.01
OFF_WALL = 0.01
NOTHING = {"uv": [0, 0], "size": [0, 0]}
READ = {"texture": "textures/blocks/redstone_dust_cross_grey", "tint": True}
## the line, which the game draws a straight run with
LINE = {"texture": "textures/blocks/redstone_dust_line_grey", "tint": True}
## pixel boxes on the floor, (x0, z0, x1, z1), in a .geo.json's frame, where
## east is the low side of x and north the low side of z
MIDDLE = (4, 4, 12, 12)
ARMS = {"north": (4, 0, 12, 4), "south": (4, 12, 12, 16),
        "east": (0, 4, 4, 12), "west": (12, 4, 16, 12)}


def flat(box):
    """A quad on the floor over `box`, reading the same part of the cross."""
    x0, z0, x1, z1 = box
    ## read backwards both ways, as a whole top is, so the picture's top lands
    ## at the north edge and its right at the east
    window = {"uv": [(16 - x0) / 16.0, z1 / 16.0], "size": [-(x1 - x0) / 16.0, -(z1 - z0) / 16.0],
              "texture": dict(READ)}
    faces = {face: dict(NOTHING) for face in ("north", "south", "east", "west")}
    faces["up"] = dict(window)
    faces["down"] = dict(window)
    return {"size": [(x1 - x0) / 16.0, 0, (z1 - z0) / 16.0],
            "offset": [x0 / 16.0, LIFT, z0 / 16.0], "faces": faces}


def climb(side):
    """The line stood upright on the wall at `side`, facing into the block."""
    window = {"uv": [0, 0], "size": [1, 1], "texture": dict(LINE, turn=90)}
    faces = {face: dict(NOTHING) for face in ("north", "south", "east", "west", "up", "down")}
    faces[OPPOSITE[side]] = dict(window)
    if side in ("north", "south"):
        z = OFF_WALL if side == "north" else 1 - OFF_WALL
        return {"size": [1, 1, 0], "offset": [0, 0, z], "faces": faces}
    x = OFF_WALL if side == "east" else 1 - OFF_WALL
    return {"size": [0, 1, 1], "offset": [x, 0, 0], "faces": faces}


def straight(along):
    """The line across the whole block, east to west, or north to south when
    `along` is the z axis."""
    window = {"uv": [1, 1], "size": [-1, -1], "texture": dict(LINE)}
    if along == "z":
        window["texture"]["turn"] = 90
    faces = {face: dict(NOTHING) for face in ("north", "south", "east", "west")}
    faces["up"] = dict(window, texture=dict(window["texture"]))
    faces["down"] = dict(window, texture=dict(window["texture"]))
    return {"size": [1, 0, 1], "offset": [0, LIFT, 0], "faces": faces}


def form(joins):
    joined = [side for side in SIDES if joins[side] != "none"]
    if joined and set(joined) <= {"east", "west"}:
        cubes = [straight("x")]
    elif joined and set(joined) <= {"north", "south"}:
        cubes = [straight("z")]
    else:
        arms = joined or list(SIDES)
        cubes = [flat(MIDDLE)] + [flat(ARMS[side]) for side in SIDES if side in arms]
    cubes += [climb(side) for side in SIDES if joins[side] == "up"]
    return {"center": [0.5, 0.5, 0.5], "cubes": cubes}


def main():
    print("writing redstone dust")
    forms = {}
    for values in itertools.product(JOINS, repeat=4):
        forms["-".join(values)] = form(dict(zip(SIDES, values)))
    forms["default"] = form({side: "none" for side in SIDES})
    tables.forms(FAMILY, forms)
    tables.rules(FAMILY, data={"join": ["scaffold:dust_%s" % side for side in SIDES]})
    print("   %d forms" % len(forms))


if __name__ == "__main__":
    main()
