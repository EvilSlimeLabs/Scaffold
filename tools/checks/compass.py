"""Build a pack that shows, in game, how Scaffold's tables map onto the world.

    python -m tools.checks.compass [--output <folder>]

What the tables mean is only knowable by looking: which world side a face the
tables call "east" ends up on, whether a picture on it reads the right way round,
where a cube placed in the table's low corner lands, and which way a turn about
each axis goes. This builds a pack of ghost blocks that answer those
questions, drawn through the real pipeline with nothing about them special
except their families, which exist only in this pack.

Every face carries its own letter and colour, named for the face the tables give
it -- N, E, S, W, U, D -- a **magenta** mark in its top left corner and a **cyan**
mark in its top right. A picture that arrives mirrored has the two marks swapped;
one upside down has them along the bottom; one turned a quarter has them down a
side.

The row, in structure order from the first block:

  1. a full cube, unturned, with a second one stacked on it to mark the start
  2. a half-size cube written in the table's low x, low y, low z corner
  3. a full cube turned 90 degrees about y
  4. a full cube turned 90 degrees about x
  5. a full cube turned 90 degrees about z

each turn a Minecraft angle, the way a rotation table holds one, so +90 about y
should carry the north face to the west and +90 about x carry it to the floor.

and one more plain cube a step along the structure's z from the start, off the
row. The row alone runs along x, where a half turn of the whole build and an
east-west mirror of it look the same; the second arm is what tells them apart.

**The ghost model turns with the armor stand**, so where the stand faces
decides everything the pack shows. The instructions this prints say where to
stand when placing it; a stand placed any other way invalidates the reading.

Nothing here is shipped, and the lookup tables are not touched: the families are
added to the geometry builder in memory for this one build.
"""
import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import nbtlib
from nbtlib import Compound, Int, List, String
from PIL import Image

from scaffold import core
from scaffold.pack import armor_stand_geo_class as asgc

PACK_NAME = "Scaffold Compass"
FACES = ("north", "south", "east", "west", "up", "down")

## a face's background, so a face is told apart before its letter is read
COLOURS = {"north": (60, 110, 230), "south": (240, 200, 40), "east": (220, 60, 50),
           "west": (60, 170, 70), "up": (235, 235, 235), "down": (90, 90, 90)}
LEFT_MARK = (230, 40, 220)          # magenta, top left
RIGHT_MARK = (40, 220, 230)         # cyan, top right

## five by seven letters, one string a row, "#" for a lit pixel
GLYPHS = {
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
}


def face_texture(face):
    """One 16x16 tile: colour, letter, and the two corner marks."""
    image = Image.new("RGBA", (16, 16), COLOURS[face] + (255,))
    pixels = image.load()
    for at_x, at_y, colour in ((0, 0, LEFT_MARK), (13, 0, RIGHT_MARK)):
        for dx in range(3):
            for dy in range(3):
                pixels[at_x + dx, at_y + dy] = colour + (255,)
    for row, line in enumerate(GLYPHS[face[0].upper()]):
        for column, lit in enumerate(line):
            if lit == "#":
                pixels[5 + column, 5 + row] = (0, 0, 0, 255)
    return image


def cube(size, offset):
    """One cube as the tables write it: fractions of a block, faces whole."""
    shape = {"size": [list(size)], "offsets": [list(offset)], "center": [0.5, 0.5, 0.5]}
    uv = {"uv_sizes": {f: [[1, 1]] for f in FACES},
          "offset": {f: [[0, 0]] for f in FACES},
          "overwrite": {f: ["textures/compass/%s" % f] for f in FACES}}
    return shape, uv


## block id -> (shape, uv, the state that turns it, the turn it names)
WHOLE = cube((1, 1, 1), (0, 0, 0))
FAMILIES = {
    "scaffold:compass_plain": (WHOLE, None),
    "scaffold:compass_corner": (cube((0.5, 0.5, 0.5), (0, 0, 0)), None),
    "scaffold:compass_turn_y": (WHOLE, ("east", [0, 90, 0])),
    "scaffold:compass_turn_x": (WHOLE, ("north", [90, 0, 0])),
    "scaffold:compass_turn_z": (WHOLE, ("west", [0, 0, 90])),
}

## (block id, x, y, z): the row along x, and one cube along z from its start
ROW = [("scaffold:compass_plain", 0, 0, 0), ("scaffold:compass_plain", 0, 1, 0),
       ("scaffold:compass_corner", 2, 0, 0), ("scaffold:compass_turn_y", 4, 0, 0),
       ("scaffold:compass_turn_x", 6, 0, 0), ("scaffold:compass_turn_z", 8, 0, 0),
       ("scaffold:compass_plain", 0, 0, 1)]


def structure(path):
    """The row as a .mcstructure, air everywhere else."""
    size = (9, 2, 2)
    names = ["minecraft:air"] + sorted(FAMILIES)
    palette = []
    for name in names:
        turned = FAMILIES.get(name, (None, None))[1]
        states = {"minecraft:cardinal_direction": String(turned[0])} if turned else {}
        palette.append(Compound({"name": String(name), "states": Compound(states),
                                 "version": Int(18168865)}))
    indices = [0] * (size[0] * size[1] * size[2])
    for name, x, y, z in ROW:
        indices[(x * size[1] + y) * size[2] + z] = names.index(name)
    nbtlib.File({
        "format_version": Int(1),
        "size": List[Int]([Int(v) for v in size]),
        "structure_world_origin": List[Int]([Int(0), Int(0), Int(0)]),
        "structure": Compound({
            "block_indices": List([List[Int]([Int(v) for v in indices]),
                                   List[Int]([Int(-1)] * len(indices))]),
            "entities": List[Compound]([]),
            "palette": Compound({"default": Compound({
                "block_palette": List[Compound](palette),
                "block_position_data": Compound({})})}),
        }),
    }).save(path, byteorder="little")


def with_compass(textures):
    """The geometry builder, with the compass families added in memory."""
    base = asgc.ArmorStandGeo

    class CompassGeo(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            ## searched before the vanilla pack, the way a tweak's folder is
            self.tweak_folders = [textures] + list(self.tweak_folders)
            for name, ((shape, uv), turned) in FAMILIES.items():
                family = name.replace(":", "_")
                self.defs[name] = family
                self.block_shapes[family] = {"default": shape}
                self.block_uv[family] = {"default": uv}
                if turned:
                    self.block_rotations[family] = {turned[0]: turned[1]}

    return CompassGeo


INSTRUCTIONS = """
Placing the armor stand -- this decides everything the pack shows:
  1. Turn on Show Coordinates in the world's settings.
  2. Pick the spot for the stand. Stand two blocks NORTH of it (a smaller Z
     than the spot), facing SOUTH, and place the stand. It faces you, north.
  3. Don't turn it afterwards.

What to report:
  - which way the row runs: which world direction (east is a larger X, south a
    larger Z) you walk in to get from the two-high start to the others
  - which side of the two-high start the lone cube off the row sits on
  - for the plain cube: the letter you see on its north, south, east, west, top
    and bottom sides in the world
  - on every face you look at: where the MAGENTA and CYAN marks are (top left
    and top right is correct; anything else says the picture is mirrored,
    upside down or turned)
  - for the small cube: which corner of its block it sits in (e.g. north west
    and at the bottom)
  - for each turned cube: the letter now on its world north, east, south,
    west, top and bottom sides
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", default=os.getcwd(),
                        help="where to put the pack; the current folder by default")
    args = parser.parse_args()

    work = tempfile.mkdtemp(prefix="scaffold-compass-")
    try:
        textures = os.path.join(work, "pack")
        os.makedirs(os.path.join(textures, "textures", "compass"))
        for face in FACES:
            face_texture(face).save(os.path.join(textures, "textures", "compass", face + ".png"))
        made = os.path.join(work, "compass.mcstructure")
        structure(made)

        core.asgc.ArmorStandGeo = with_compass(textures)
        builder = core.Scaffold(os.path.join(args.output, PACK_NAME))
        builder.set_opacity(0.9)
        builder.add_model("", made)
        builder.set_model_offset("", [0, 0, 0])
        builder.generate_with_nametags()
        skipped = builder.get_skipped(write_file=False)
        if skipped:
            print("these did not build: %s" % skipped)
            return 1
        print("wrote %s" % builder.compile_pack(overwrite=True))
        print(INSTRUCTIONS)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
