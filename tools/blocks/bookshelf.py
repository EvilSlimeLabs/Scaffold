"""Generate the chiseled bookshelf's sixty-four filled states.

    python -m tools.blocks.bookshelf

A chiseled bookshelf has six slots and remembers which of them hold a book, in a
`books_stored` state that is a six bit number, so there are sixty-four ways it
can look. Vanilla draws the shelf itself from `chiseled_bookshelf_empty` and lays
`chiseled_bookshelf_occupied` over the slots that are filled, and that is what
this builds: one variant per value, the shelf plus a small panel over each
occupied slot.

The slot grid is measured from the two textures rather than guessed, because the
pixels where they differ are exactly the six book faces. It comes out as three
columns four pixels wide at x 1, 6 and 11, and two rows six pixels tall at y 1
and 9.

The front is the **north** face, at `z` 0, because a block at rest faces north.
The books stand proud of it. Put on the south face instead, the shelf reads its
books out of the wall it is against and every one of its four facings is half a
turn out.

**The sides read each other's declared texture**, east the west one and west
the east one, and the top and bottom read their tiles backwards both ways. That
is how the shelf has always been drawn, and the game's own sides and top are
symmetric enough that nobody has seen otherwise.

`blocks.json` names the front texture `chiseled_bookshelf_front` and the back
`chiseled_bookshelf_side`, but both are drawn from the empty shelf here rather
than taken from those names: `chiseled_bookshelf_front` resolves through
`terrain_texture.json` to the empty shelf, which would put a shelf front on the
back of the block as well, so the back names the side texture outright.

Writes into `lookups/block_geometry.json`; nothing here
is needed at run time.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer

SHAPES = lookup_writer.SHAPES
UV = lookup_writer.UV
FACES = ("up", "down", "north", "south", "east", "west")
FAMILY = "chiseled_bookshelf"

EMPTY = "textures/blocks/chiseled_bookshelf_empty"
OCCUPIED = "textures/blocks/chiseled_bookshelf_occupied"
BACK = "textures/blocks/chiseled_bookshelf_side"

## the slot grid, in texture pixels, measured from where the two textures differ
COLUMNS = (1, 6, 11)
ROWS = (1, 9)
SLOT_WIDE = 4
SLOT_TALL = 6

## how far a book panel stands proud of the shelf front, so the two faces do not
## fight over the same plane
PROUD = 0.02

BODY = 0.95


def slot_box(index):
    """One slot, as a texture window and as a box on the front of the block.

    The front is the north face, which reads its tile left to right as x
    climbs: seen from the north, the low side of x, east, is on the left. The
    texture row counts down from the top of the tile while y counts up from the
    floor, so the rows are turned over here.
    """
    column = COLUMNS[index % 3]
    row = ROWS[index // 3]
    u, v = column / 16.0, row / 16.0
    wide, tall = SLOT_WIDE / 16.0, SLOT_TALL / 16.0
    ## v counts down from the top of the tile; y counts up from the floor
    x, y = u, 1.0 - (v + tall)
    return (u, v, wide, tall), (x, y)


def variant(mask):
    """The shape and the texture windows for one arrangement of books."""
    filled = [i for i in range(6) if mask & (1 << i)]

    sizes = [[BODY, BODY, BODY]]
    ## the case sits in the middle of its cell, and the books on it
    inset = round((1 - BODY) / 2, 6)
    offsets = [[inset, inset, inset]]
    windows = {face: [[1, 1]] for face in FACES}
    origins = {face: [[0, 0]] for face in FACES}
    ## the top and bottom read backwards, from their far corner
    for face in ("up", "down"):
        windows[face] = [[-1, -1]]
        origins[face] = [[1, 1]]
    ## the shelf's own front, which is where the empty slots are drawn
    front = [EMPTY]

    for index in filled:
        (u, v, wide, tall), (x, y) = slot_box(index)
        ## **Measured on the shelf, not on the block.** The slots are read off
        ## the texture as fractions of a whole block, but the shelf itself is
        ## drawn at BODY -- a shade under full size, the way every ghost block
        ## that fills its cell is -- so a panel placed at those fractions sits
        ## proud of the shelf's own edges and the six of them spread wider than
        ## the slots they are meant to fill. Scaling both the size and the
        ## corner by BODY keeps each book in its slot.
        sizes.append([round(wide * BODY, 6), round(tall * BODY, 6), PROUD])
        ## standing on the front of the block, which is its north face
        offsets.append([round(inset + x * BODY, 6), round(inset + y * BODY, 6),
                        round(inset - PROUD, 6)])
        for face in FACES:
            ## only the north face of a panel is really seen; the slivers round
            ## its edge take the same window rather than a meaningless one
            if face in ("up", "down"):
                windows[face].append([-wide, -tall])
                origins[face].append([u + wide, v + tall])
            else:
                windows[face].append([wide, tall])
                origins[face].append([u, v])
        front.append(OCCUPIED)

    shape = {
        "size": sizes,
        "offsets": offsets,
        "center": [0.5, 0.5, 0.5],
    }
    uv = {
        "uv_sizes": windows,
        "offset": origins,
        ## the shelf front and every panel name their texture outright, and so
        ## does the back: the name blocks.json puts on it resolves to the shelf
        ## front, which would draw a second set of slots on the wall side
        "overwrite": {"north": front,
                      "south": [BACK] + [OCCUPIED] * len(filled),
                      "east": ["@west"] * (1 + len(filled)),
                      "west": ["@east"] * (1 + len(filled))},
    }
    return shape, uv


def main():
    shapes = {}
    uvs = {}
    for mask in range(64):
        shape, uv = variant(mask)
        shapes[str(mask)] = shape
        uvs[str(mask)] = uv

    ## an empty shelf is what one looks like before anything is put in it
    shapes["default"] = shapes["0"]
    uvs["default"] = uvs["0"]

    print("shapes: %s" % lookup_writer.put(SHAPES, FAMILY, shapes))
    print("uv    : %s" % lookup_writer.put(UV, FAMILY, uvs, tight=True))

    total = sum(len(shapes[k]["size"]) for k in shapes)
    print("%d variants, %d cubes across the table" % (len(shapes), total))
    json.loads(io.open(lookup_writer.GEOMETRY, encoding="utf-8").read())
    print("both tables still parse")


if __name__ == "__main__":
    main()
