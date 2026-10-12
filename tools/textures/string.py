"""Draw a string a ghost block can actually be seen with.

    python -m tools.textures.string

Vanilla's `trip_wire` tile is a scatter of faint single pixels across a quarter
of the tile, because the game draws string as a thin quad turned to face the way
the wire runs and lit at full brightness. A ghost block is neither: it is a
half-transparent plate lying flat in its block, drawn against whatever is behind
it, and vanilla's scatter on that plate is invisible from more than a couple of
blocks away.

So the tile is drawn here instead, in the colours vanilla's own string is drawn
in, written into the vanilla pack as `textures/blocks/scaffold_string.png`. The
string itself is Java's: strips along each way the wire runs, reading the top
two rows of the tile on the ground and the next two when hooks hold it up, which
`tools/blocks/models.py` draws a pixel wide rather than half of one. Those four
rows are a solid line, its lit core in the middle and its shade either side,
with a darker twist every few pixels so it reads as string rather than wire.

Nothing here is needed at run time.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                      "textures", "blocks")
SOURCE = os.path.join(BLOCKS, "trip_wire.png")
TARGET = os.path.join(BLOCKS, "scaffold_string.png")

TILE = 16
## the lit core of the line, and the shade either side of it, taken from the
## brightest and the middle greys vanilla's own tile is drawn in
CORE = (206, 206, 206, 255)
EDGE = (143, 143, 143, 255)
## every so many pixels along it, the string turns its darker side up
TWIST = 4
## each row a strip reads: shade and core on the ground, core and shade raised
ROWS = (EDGE, CORE, CORE, EDGE)


def main():
    if not os.path.isfile(SOURCE):
        raise SystemExit("no %s to take the colours from" % SOURCE)
    image = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    pixels = image.load()
    for row, colour in enumerate(ROWS):
        for along in range(TILE):
            pixels[along, row] = EDGE if along % TWIST == TWIST - 1 else colour
    image.save(TARGET)
    print("wrote %s" % os.path.relpath(TARGET, ROOT))


if __name__ == "__main__":
    main()
