"""Tint the plants the game colours by biome, ahead of time.

    python -m tools.textures.foliage

A ghost block cannot run the game's colour maps, so every biome-tinted tile this
pack draws is coloured before it is used. Tall grass, the large fern and leaf
litter ship grey, and were drawn grey. Each is written beside the original as a
PNG of the same name, which is read before the TGA the vanilla pack ships, in
the colour the game gives it in plains: the grass colour for the two plants and
the dry foliage colour for leaf litter.

Each is made from the grey original, so running this twice writes the same
bytes. Nothing here is needed at run time.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")

GRASS = (0x91, 0xBD, 0x59)
DRY_FOLIAGE = (0xA0, 0x6E, 0x3C)

## (grey original, tinted copy, colour)
TINTED = [
    ("double_plant_grass_top.tga", "double_plant_grass_top.png", GRASS),
    ("double_plant_grass_bottom.tga", "double_plant_grass_bottom.png", GRASS),
    ("double_plant_fern_top.tga", "double_plant_fern_top.png", GRASS),
    ("double_plant_fern_bottom.tga", "double_plant_fern_bottom.png", GRASS),
    ("leaf_litter_grey.png", "leaf_litter.png", DRY_FOLIAGE),
]


def tint(image, colour):
    image = image.convert("RGBA")
    red, green, blue, alpha = image.split()
    return Image.merge("RGBA", (red.point(lambda v: v * colour[0] // 255),
                                green.point(lambda v: v * colour[1] // 255),
                                blue.point(lambda v: v * colour[2] // 255), alpha))


def main():
    print("writing the biome-tinted plants")
    for grey, out, colour in TINTED:
        source = os.path.join(BLOCKS, grey)
        if not os.path.isfile(source):
            print("   %-28s is not there" % grey)
            continue
        tint(Image.open(source), colour).save(os.path.join(BLOCKS, out))
        print("   %s" % out)


if __name__ == "__main__":
    main()
