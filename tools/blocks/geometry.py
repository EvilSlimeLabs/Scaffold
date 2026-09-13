"""The pieces every block generator here is built out of.

A block is a list of cubes, and a cube is where it sits, how big it is, and what
each of its six faces is painted with. `Cube` holds one and `build` turns a list
of them into the pair of entries a shape family has in `block_shapes.json` and
`block_uv.json`.

The rest are the measurements that keep coming up. `spun` moves a point the way
a bone's rotation would have moved it, which is how a piece of a model that
turns about somewhere other than its own middle is drawn as a cube that turns
about its own. `unwrap` is the order Bedrock lays a box out on an entity sheet
in. `on_sheet` reads one region of a sheet that is bigger than a tile, and pulls
the tile corner back far enough that the region fits.

Nothing here writes a file. It is imported by the generators beside it and is
never run on its own.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

## the mark a turned tile carries in its name, taken from the runtime rather
## than spelled again here: the two have to agree exactly or a table asks for a
## tile nothing builds
from scaffold.pack.armor_stand_geo_class import TURN_MARK, TURNS

FACES = ("up", "down", "north", "south", "east", "west")

PX = 1.0 / 16


def px(value):
    """A measurement in pixels, as the fraction of a block the tables hold."""
    return round(value * PX, 6)


class Cube:
    """One box of a block: where it is, how big, and what it is textured with.

    `size` and `at` are in pixels. `texture` is an entry for the UV table's
    overwrite list, so "default" leaves the block's own faces alone, "@up" takes
    whatever the block declares for that face, and a window may travel with it.

    `window` names the part of the texture each face reads, again in pixels, as
    (across, down, wide, tall). Without one the cube is textured by its own
    place in the block, which is what a block drawn from a terrain texture
    wants: the front of a cube sitting in the lower left of the block reads the
    lower left of the tile.

    **A window may carry a fifth number, a quarter turn clockwise.** Bedrock's
    UV is a corner and a size with no angle in it, so a face cannot read its
    picture a quarter round; the tile is turned on the way into the atlas
    instead and the angle travels in the texture's name. Some textures pack a
    piece of the block lying on its side -- a lectern's post is down the bottom
    half of `lectern_sides`, across rather than up -- and there is no other way
    to stand it up.

    **The turn happens first and the window is measured on the turned tile.**
    A face wanting the bottom half of a tile stood on its end asks for the left
    half of the tile turned, not the bottom half of the tile it started as.
    """

    def __init__(self, size, at, texture="default", window=None, rotation=None):
        self.size = list(size)
        self.at = list(at)
        self.texture = texture
        self.window = window or {}
        self.rotation = rotation

    def paint(self, face):
        """The texture this face takes, which may differ from face to face.

        A face whose window asks for a turn has it written onto the name, so
        the turned tile is a separate entry in the atlas from the straight one.
        """
        if isinstance(self.texture, dict):
            texture = self.texture[face]
        else:
            texture = self.texture
        turn = self.turn(face)
        ## "default" is "leave the block's own face alone", which is read before
        ## a name is ever built, so a turn on it would go nowhere
        if turn and texture != "default":
            texture = "%s%s%d" % (texture, TURN_MARK, turn)
        return texture

    def turn(self, face):
        """The quarter turn this face's window asks for, in degrees."""
        window = self.window.get(face)
        if not window or len(window) < 5:
            return 0
        degrees = int(window[4]) % 360
        if degrees not in TURNS:
            raise ValueError(
                "a window turns by a right angle, not %s" % window[4])
        return degrees

    def shape(self):
        return [px(n) for n in self.size], [px(n) for n in self.at]

    def uv(self, face):
        """The window this face reads, as (offset, size) in tile fractions."""
        if face in self.window:
            ## a fifth number is the turn, which rides on the texture's name
            ## rather than in the numbers a face reads
            across, down, wide, tall = self.window[face][:4]
            return [px(across), px(down)], [px(wide), px(tall)]
        wide, tall, deep = self.size
        across, up, over = self.at
        ## **An up face's v runs toward -z, and a down face's runs with it.** So
        ## the top of a tile lands at the block's *south* edge on an up face and
        ## at its north edge on a down one. A cube that does not fill the block
        ## front to back therefore reads its top from the far side: measured the
        ## same way as the underside, a cauldron's north rim wore the picture of
        ## its south one and the two looked swapped.
        if face == "up":
            return [px(across), px(16 - over - deep)], [px(wide), px(deep)]
        if face == "down":
            return [px(across), px(over)], [px(wide), px(deep)]
        if face in ("north", "south"):
            return [px(across), px(16 - up - tall)], [px(wide), px(tall)]
        return [px(over), px(16 - up - tall)], [px(deep), px(tall)]


def build(cubes, center=(8, 8, 8)):
    """A shapes entry and a UV entry for one list of cubes."""
    shape = {"size": [], "offsets": []}
    uv = {"uv_sizes": {face: [] for face in FACES},
          "offset": {face: [] for face in FACES},
          "overwrite": {face: [] for face in FACES}}
    for cube in cubes:
        size, at = cube.shape()
        shape["size"].append(size)
        shape["offsets"].append(at)
        for face in FACES:
            offset, window = cube.uv(face)
            uv["offset"][face].append(offset)
            uv["uv_sizes"][face].append(window)
            uv["overwrite"][face].append(cube.paint(face))
    if any(cube.rotation for cube in cubes):
        shape["rotation"] = [list(cube.rotation or (0, 0, 0)) for cube in cubes]
    shape["center"] = [px(n) for n in center]
    return shape, uv


def spun(point, pivot, rotation):
    """`point` turned about `pivot` the way a bone's rotation turns its cubes.

    Bedrock's angles run the other way round from the usual mathematical ones:
    a positive value turns clockwise in the plane it names. The piglin's ears
    are what settles that, because only one of the two signs takes them away
    from the head rather than into it.

    Every turn read here is about a single axis, so the order the three are
    applied in does not come up.
    """
    x, y, z = (a - b for a, b in zip(point, pivot))
    rx, ry, rz = (math.radians(-angle) for angle in rotation)
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    z, x = z * math.cos(ry) - x * math.sin(ry), z * math.sin(ry) + x * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x + pivot[0], y + pivot[1], z + pivot[2]]


def unwrap(uv, size):
    """The six rectangles of the sheet a box of an entity model reads.

    Bedrock lays a box out from its UV corner as two faces in a row above four
    in a strip: up and down across the top, then west, the front, east and the
    back. The front is named south here because the model is turned half a turn
    on the way into a block, which is what puts it on the block's south face.
    """
    wide, tall, deep = size
    u, v = uv
    return {
        "up": (u + deep, v, wide, deep),
        "down": (u + deep + wide, v, wide, deep),
        "west": (u, v + deep, deep, tall),
        "south": (u + deep, v + deep, wide, tall),
        "east": (u + deep + wide, v + deep, deep, tall),
        "north": (u + deep + wide + deep, v + deep, wide, tall),
    }


def on_sheet(name, region, sheet):
    """A texture reference and a window for one region of an entity sheet.

    Only a 16x16 window of a texture becomes a tile, so the reference carries
    the corner that tile starts at and the window is measured from there. The
    corner is pulled back far enough that the region fits inside the tile and
    never past the edge of the sheet, which is why the last face of a strip
    still reads from a corner sixteen in. `sheet` is the size of the sheet the
    region is on, and every caller says which, because a sheet that is not the
    size it is taken for puts every window on the wrong pixel.
    """
    x, y, wide, tall = region
    at = [max(0, min(n, sheet - 16)) for n in (x, y)]
    return ("%s#%d,%d" % (name, at[0], at[1]),
            (x - at[0], y - at[1], wide, tall))
