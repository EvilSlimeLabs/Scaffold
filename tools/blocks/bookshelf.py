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

The front is the **south** face, at `z` 16, because a block at rest faces south
and that is where the rotation tables put `direction` 0. The books stand proud
of it. Put on the north face instead, the shelf reads its books out of the wall
it is against and every one of its four facings is half a turn out.

`blocks.json` names the front texture `chiseled_bookshelf_front` and the back
`chiseled_bookshelf_side`, but both are drawn from the empty shelf here rather
than taken from those names: `chiseled_bookshelf_front` resolves through
`terrain_texture.json` to the empty shelf, which would put a shelf front on the
back of the block as well, so the back names the side texture outright.

Writes into `lookups/block_shapes.json` and `lookups/block_uv.json`; nothing here
is needed at run time.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.blocks import tables as lookup_writer

SHAPES = os.path.join(ROOT, "scaffold", "lookups", "block_shapes.json")
UV = os.path.join(ROOT, "scaffold", "lookups", "block_uv.json")
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

    The front is the south face, and a face's texture column is read as its
    position along x, the way every other family in the tables reads one. The
    texture row counts down from the top of the tile while y counts up from the
    floor, so the two are turned over here.
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
    offsets = [[0, 0, 0]]
    windows = {face: [[1, 1]] for face in FACES}
    origins = {face: [[0, 0]] for face in FACES}
    ## the shelf's own front, which is where the empty slots are drawn
    front = [EMPTY]

    for index in filled:
        (u, v, wide, tall), (x, y) = slot_box(index)
        sizes.append([wide, tall, PROUD])
        ## standing on the front of the block, which is its south face
        offsets.append([x, y, BODY])
        for face in FACES:
            ## only the south face of a panel is really seen; the slivers round
            ## its edge take the same window rather than a meaningless one
            windows[face].append([wide, tall])
            origins[face].append([u, v])
        front.append(OCCUPIED)

    shape = {
        "size": sizes,
        "offsets": offsets,
        "center": [BODY / 2, BODY / 2, BODY / 2],
    }
    uv = {
        "uv_sizes": windows,
        "offset": origins,
        ## the shelf front and every panel name their texture outright, and so
        ## does the back: the name blocks.json puts on it resolves to the shelf
        ## front, which would draw a second set of slots on the wall side
        "overwrite": {"south": front,
                      "north": [BACK] + [OCCUPIED] * len(filled)},
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
    for name in (SHAPES, UV):
        json.loads(io.open(name, encoding="utf-8").read())
    print("both tables still parse")


if __name__ == "__main__":
    main()
