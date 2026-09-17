"""Make water see-through, the way this pack's glass is.

    python -m tools.textures.water

Vanilla's water tile is fully opaque. The game gets water's transparency from
the material it draws it with rather than from the picture, and a ghost block
has no such material: it is drawn with one blended pass over whatever is behind
it, so an opaque tile is an opaque block. A pool of water in a build therefore
came out as a wall of solid grey with everything behind it hidden, which is the
one thing water should not do.

**The answer is the one this pack already gives glass.** `glass.png` here is a
fully opaque one pixel frame around an empty middle, so a glass block reads as
an outlined cube you can see straight through. Water gets the same frame, and a
middle that keeps a little of its own colour rather than none, because a pool
with no colour at all is not readable as water.

**The frame stays fully opaque on purpose.** Every tile's alpha is multiplied by
the transparency slider as the pack is built -- `armor_stand_geo_class.alpha`,
0.35 by default -- so a tile that starts faint arrives at nothing. The frame is
what survives that pass and what keeps one water block distinguishable from the
next in a column of them.

Both files are written in place, in the vanilla pack this project ships, and
nothing else reads them: `water` and `flowing_water` are the only two blocks in
`blocks.json` naming `still_water_grey` or `flowing_water_grey`. The alpha
written is an absolute value rather than a reduction of what is there, so
running this twice writes the same bytes as running it once.

Nothing here is needed at run time.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                      "textures", "blocks")

## the still tile is the up and down faces, the flow tile the four sides
FILES = ("water_still_grey.png", "water_flow_grey.png")

TILE = 16
## the outline, which is what is left after the transparency slider
EDGE = 255
## and the middle, faint enough to see a build through and not so faint that
## the water's own colour is gone
MIDDLE = 64


def framed(image):
    """One image with every tile of it outlined and its middle made faint.

    Both files are strips of animation frames -- the still water is sixteen by
    five hundred and twelve and the flow is twice as wide again -- and only the
    top left tile of either is ever read, since a tile is sixteen by sixteen.
    Every tile is treated all the same, so the file still reads as one animation
    to anything that opens it.
    """
    image = image.convert("RGBA")
    wide, tall = image.size
    pixels = image.load()
    for x in range(wide):
        for y in range(tall):
            across, down = x % TILE, y % TILE
            edge = across in (0, TILE - 1) or down in (0, TILE - 1)
            red, green, blue, _alpha = pixels[x, y]
            pixels[x, y] = (red, green, blue, EDGE if edge else MIDDLE)
    return image


def main():
    print("writing the see-through water")
    for name in FILES:
        path = os.path.join(BLOCKS, name)
        if not os.path.isfile(path):
            print("   %-24s is not there" % name)
            continue
        framed(Image.open(path)).save(path)
        print("   %-24s outlined, middle at %d" % (name, MIDDLE))


if __name__ == "__main__":
    main()
