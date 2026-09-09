"""Draw a string a ghost block can actually be seen with.

    python -m tools.textures.string

Vanilla's `trip_wire` tile is a scatter of faint single pixels across a quarter
of the tile, because the game draws string as a thin quad turned to face the way
the wire runs and lit at full brightness. A ghost block is neither: it is a
half-transparent plate lying flat in its block, drawn against whatever is behind
it, and vanilla's scatter on that plate is invisible from more than a couple of
blocks away.

So the tile is drawn here instead: a cross of solid lines through the middle of
the tile, in the colours vanilla's own string is drawn in, written into the
vanilla pack as `textures/blocks/scaffold_string.png`.

**A cross, because the direction is not in the block.** Bedrock's `trip_wire`
carries `attached_bit`, `disarmed_bit`, `powered_bit` and `suspended_bit` and
nothing that says which way the wire runs; the game works that out from the
blocks beside it as it draws. A structure file cannot say, so a single line
would be pointing the wrong way about half the time and a cross is right about
where the string is either way. `redstone_dust_cross` is the same answer to the
same problem.

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
## two pixels reads as a taut line at a distance and still leaves the block
## behind it visible; one disappears into the alpha pass
THICK = 2
## the lit core of the line, and the shade down each side of it, taken from the
## brightest and the middle greys vanilla's own tile is drawn in
CORE = (206, 206, 206, 255)
EDGE = (143, 143, 143, 255)


def line(pixels, across):
    """One band through the middle of the tile, along x or along y."""
    first = (TILE - THICK) // 2
    for step in range(-1, THICK + 1):
        at = first + step
        if not 0 <= at < TILE:
            continue
        colour = CORE if 0 <= step < THICK else EDGE
        for along in range(TILE):
            spot = (along, at) if across else (at, along)
            ## the core wins where the two bands cross
            if pixels[spot][3] and colour is EDGE:
                continue
            pixels[spot] = colour


def main():
    if not os.path.isfile(SOURCE):
        raise SystemExit("no %s to take the colours from" % SOURCE)
    image = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    pixels = image.load()
    line(pixels, across=True)
    line(pixels, across=False)
    image.save(TARGET)
    solid = sum(1 for pixel in image.getdata() if pixel[3])
    print("wrote %s, %d of %d pixels covered"
          % (os.path.relpath(TARGET, ROOT), solid, TILE * TILE))


if __name__ == "__main__":
    main()
