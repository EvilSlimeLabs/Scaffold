"""Give each chest front the two halves of a double chest beside it.

    python -m tools.textures.chests

A double chest is two chest blocks, each drawn by the `chest` family's `left`
or `right` form, and between them they show one front with one latch, on the
seam. A single chest's front has its latch in the middle, so neither half can
read it as it is.

Each front is written as a sheet three tiles wide: the single chest's front,
unchanged, then the left half of the double front, then the right half. The
single front is the top left tile, which is the only one anything else reads,
and the halves are read with a `window` on the same slot, so one family serves
every chest a front is declared for without naming a texture.

The double front is the game's own: the entity's double chest sheet holds the
front thirty pixels wide, a lid strip over a base strip, and that is scaled to
the thirty-two pixels two tiles hold. The latch is then painted over the seam
from the single front, where the block tile draws it, so the two halves carry
the same latch the single chest does and the plank grain is the sheet's own
rather than columns of the single front repeated.

The tops and the sides are the same three tiles: the single picture, then the
double lid's top, or the double chest's back, from the same entity sheet,
scaled to two tiles and cut at the seam. A side's halves are what a half's
back reads.

The single tile is read from the file's own top left, so running this twice
writes the same bytes as running it once. Nothing here is needed at run time.
"""
import os

from PIL import Image
from tools import sources

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                      "textures", "blocks")

ENTITY = sources.resource_pack("textures",
                      "entity", "chest")
## every front a chest that can pair declares, and the double sheet it is
## drawn from; an ender chest never pairs
FRONTS = {"chest_front": "double_normal",
          "trapped_chest_front": "trapped_double",
          "copper_chest_inventory_front": "copper_default_double",
          "exposed_copper_chest_inventory_front": "copper_exposed_double",
          "weathered_copper_chest_inventory_front": "copper_weathered_double",
          "oxidized_copper_chest_inventory_front": "copper_oxidized_double"}

## where the halves sit on the sheet, in pixels; the `chest` family's windows
LEFT = (16, 0)
RIGHT = (32, 0)

## the double chest's front on its entity sheet, as (left, top, right, bottom):
## the lid's five rows and the base's ten, thirty across
LID = (14, 14, 44, 19)
BASE = (14, 33, 44, 43)
## the latch on the single front, and where it lands across the seam
LATCH = (7, 1, 9, 8)
SEAM = 15


def halves(single, double):
    """(left, right): the double front's two tiles."""
    front = Image.new("RGBA", (30, 15))
    front.paste(double.crop(LID), (0, 0))
    front.paste(double.crop(BASE), (0, 5))
    strip = front.resize((32, 16), Image.NEAREST)
    strip.alpha_composite(single.crop(LATCH), (SEAM, LATCH[1]))
    return strip.crop((0, 0, 16, 16)), strip.crop((16, 0, 32, 16))


## every top a chest that can pair declares, and the double sheet it comes
## from; the trapped chest wears the plain chest's top
TOPS = {"chest_top": "double_normal",
        "copper_chest_inventory_top": "copper_default_double",
        "exposed_copper_chest_inventory_top": "copper_exposed_double",
        "weathered_copper_chest_inventory_top": "copper_weathered_double",
        "oxidized_copper_chest_inventory_top": "copper_oxidized_double"}
## the double lid's top on its entity sheet, thirty across and fourteen deep
LID_TOP = (14, 0, 44, 14)


## every side a chest that can pair declares, which its back reads too; waxed
## chests and the trapped chest declare these same files
BACKS = {"chest_side": "double_normal",
         "copper_chest_inventory_side": "copper_default_double",
         "exposed_copper_chest_inventory_side": "copper_exposed_double",
         "weathered_copper_chest_inventory_side": "copper_weathered_double",
         "oxidized_copper_chest_inventory_side": "copper_oxidized_double"}
## the double chest's back on its entity sheet: the lid's five rows and the
## base's ten, thirty across
LID_BACK = (58, 14, 88, 19)
BASE_BACK = (58, 33, 88, 43)


def back_halves(_single, double):
    """(left, right): the double chest's back, scaled to two tiles and cut."""
    back = Image.new("RGBA", (30, 15))
    back.paste(double.crop(LID_BACK), (0, 0))
    back.paste(double.crop(BASE_BACK), (0, 5))
    strip = back.resize((32, 16), Image.NEAREST)
    return strip.crop((0, 0, 16, 16)), strip.crop((16, 0, 32, 16))


def top_halves(_single, double):
    """(left, right): the double lid's top, scaled to two tiles and cut."""
    strip = double.crop(LID_TOP).resize((32, 16), Image.NEAREST)
    return strip.crop((0, 0, 16, 16)), strip.crop((16, 0, 32, 16))


def sheet(single, double, cut=None):
    left, right = (cut or halves)(single, double)
    out = Image.new("RGBA", (48, 16))
    out.paste(single, (0, 0))
    out.paste(left, LEFT)
    out.paste(right, RIGHT)
    return out


def main():
    print("writing the double chest fronts")
    for name, entity in FRONTS.items():
        path = os.path.join(BLOCKS, name + ".png")
        source = os.path.join(ENTITY, entity + ".png")
        if not os.path.isfile(path) or not os.path.isfile(source):
            print("   %-40s is not there" % name)
            continue
        single = Image.open(path).convert("RGBA").crop((0, 0, 16, 16))
        double = Image.open(source).convert("RGBA")
        sheet(single, double).save(path)
        print("   %s" % name)
    for table, cut in ((TOPS, top_halves), (BACKS, back_halves)):
        for name, entity in table.items():
            path = os.path.join(BLOCKS, name + ".png")
            source = os.path.join(ENTITY, entity + ".png")
            single = Image.open(path).convert("RGBA").crop((0, 0, 16, 16))
            double = Image.open(source).convert("RGBA")
            sheet(single, double, cut).save(path)
            print("   %s" % name)


if __name__ == "__main__":
    main()
