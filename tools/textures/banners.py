"""Dye the banner sheet, once per colour, so a banner is drawn in its own.

    python -m tools.textures.banners

A banner's colour is not in its block states. It is in the block entity beside
the block, as `Base`, a number from 0 to 15 in the same order as wool, and the
game draws it by tinting one white sheet at run time. A ghost block cannot tint
anything, so the tinting is done here instead: sixteen copies of
`banner_base.tga`, each multiplied by its dye, written into the vanilla pack as
`textures/entity/banner/banner_<colour>.png`.

The dyes are read out of the pack's own wool textures rather than written down
here, so they are the colours this pack actually uses.

**Patterns are not drawn.** A banner may carry six of them, each with a colour
of its own, which is more combinations than could ever be written to disk: they
would have to be composited while a pack is built, and the texture atlas takes
files rather than pictures. What is here is the base colour.

Re-run `tools/blocks/containers.py` after this if the list of colours
changes. Nothing here is needed at run time.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PACK = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack")
BLOCKS = os.path.join(PACK, "textures", "blocks")
BANNERS = os.path.join(PACK, "textures", "entity", "banner")
BASE = os.path.join(BANNERS, "banner_base.tga")

## Bedrock's dye order, which `Base` counts in and which `variants.json` already
## keys wool and every other dyed block by
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "silver", "cyan", "purple", "blue", "brown", "green", "red",
           "black"]


def average(block):
    """The one colour a block's texture comes to, as the average of it."""
    tile = Image.open(
        os.path.join(BLOCKS, "%s.png" % block)).convert("RGB")
    return tuple(int(round(band.resize((1, 1), Image.BOX).getpixel((0, 0))))
                 for band in tile.split())


def dye(colour):
    """The colour this pack paints that wool, as the average of its texture."""
    return average("wool_colored_%s" % colour)


## Where the cloth is on the sheet, and nothing else. The post is up the right
## of it from x44 and the bar it hangs from is across the bottom from y42, and
## both of those are wood: the game tints only the cloth, so dyeing the whole
## sheet gives a banner a coloured post to stand on.
CLOTH = (0, 0, 42, 42)


def tint(sheet, colour):
    """The sheet's cloth multiplied by a dye, the way the game tints it."""
    out = sheet.copy()
    cloth = out.crop(CLOTH)
    red, green, blue, alpha = cloth.split()
    scale = dye(colour)
    red = red.point(lambda v: v * scale[0] // 255)
    green = green.point(lambda v: v * scale[1] // 255)
    blue = blue.point(lambda v: v * scale[2] // 255)
    out.paste(Image.merge("RGBA", (red, green, blue, alpha)), CLOTH)
    return out


# --- the two banners that are not a colour -----------------------------------
#
# An ominous banner is not a dye. It is a banner the game draws from a sheet of
# its own, and the pack the submodule carries has that sheet already: it is
# copied in rather than drawn. A banner carrying patterns is the other case,
# and there is nothing to copy, so it gets a mark of this project's own: the
# Evil Slime Labs logo the About window opens, over a black cloth.
#
# **A design is taller than a tile, so it is written where a column of tiles can
# read it.** Only sixteen by sixteen of a texture becomes a tile and a quad
# reads one tile, so a cloth showing a design is drawn as four quads stacked
# instead of as one, and the design is written at the size that column reads:
# sixteen across by sixty four down. Sixteen across is the cloth's own width on
# the block, so the picture is read pixel for pixel rather than through a seam.
#
# It goes below the sheet rather than in it. Both marked sheets keep vanilla's
# 64 by 64 layout in their top half, so the post and the bar are read by the
# same windows as every other banner's, and carry the design under it.
COMMUNITY = os.path.join(ROOT, "CommunityVanillaResourcePack", "textures",
                         "entity", "banner", "banner_illager.tga")
LOGO = os.path.join(ROOT, "scaffold", "images", "evilslimelabs-logo3.png")
FRONT = (1, 1, 21, 41)      # the face of the cloth, which is what a design is on
SHEET = 64                  # vanilla's own sheet, which stays where it is
## the design, and where it sits under the sheet. Keep these in step with
## `tools/blocks/banners.py`'s `DESIGN_ACROSS`, `DESIGN_DOWN` and `DESIGN_AT`.
DESIGN = (64, 64)

## **A pixel of the design is not square on the block.** The design covers the
## whole cloth, and the cloth is half as wide as it is tall, so `DESIGN` across
## lands on half the block pixels that `DESIGN` down does. A picture fitted by
## its own proportions in sheet pixels therefore comes out squashed by whatever
## that ratio is. Anything drawn here at its true shape has to be stretched by
## this first.
SQUARE_UP = (DESIGN[1] / 2.0) / DESIGN[0]
DESIGN_AT = (0, SHEET)
SHEET_COLOR = "gray"       # the cloth the logo is on


def written(sheet, design):
    """The sheet with a design written under it, at the size a grid reads."""
    out = Image.new("RGBA", (max(sheet.size[0], DESIGN_AT[0] + DESIGN[0]),
                             DESIGN_AT[1] + DESIGN[1]), (0, 0, 0, 0))
    out.paste(sheet, (0, 0))
    out.paste(design.resize(DESIGN, Image.NEAREST), DESIGN_AT)
    return out


def logo_on(cloth):
    """The Evil Slime Labs logo over a cloth, as wide as the cloth and centred.

    The logo is a wide picture and a banner is a tall one, so it is fitted
    across and left where a crest sits rather than stretched to the cloth: the
    rest is cloth, with the folds vanilla drew still on it.

    **Its height is stretched by `SQUARE_UP` on the way in.** A pixel of the
    design is twice as tall on the block as it is wide, so a logo fitted by its
    own proportions in sheet pixels lands on the cloth half the height it should
    be. Written this way it comes out the shape it was drawn.
    """
    ground = cloth.resize(DESIGN, Image.LANCZOS)
    logo = Image.open(LOGO).convert("RGBA")
    wide = DESIGN[0]
    tall = max(1, int(round(logo.size[1] * wide / float(logo.size[0])
                            * SQUARE_UP)))
    ground.alpha_composite(logo.resize((wide, tall), Image.LANCZOS),
                           (0, (DESIGN[1] - tall) // 2))
    return ground


def main():
    if not os.path.isfile(BASE):
        raise SystemExit(
            "No %s. Copy it out of the community submodule first." % BASE)
    sheet = Image.open(BASE).convert("RGBA")
    print("dyeing %s, %dx%d" % (os.path.basename(BASE), *sheet.size))
    for index, colour in enumerate(COLOURS):
        made = tint(sheet, colour)
        path = os.path.join(BANNERS, "banner_%s.png" % colour)
        made.save(path)
        print("   %2d %-12s %s" % (index, colour, os.path.basename(path)))

    designed = tint(sheet, SHEET_COLOR)
    path = os.path.join(BANNERS, "banner_designed.png")
    # The image needs to be mirrored for the face we are putting it on.
    made = written(designed, logo_on(designed.crop(FRONT)).transpose(Image.FLIP_LEFT_RIGHT))
    made.save(path)
    print("      %-12s %s, %dx%d" % ("designed", os.path.basename(path),
                                     *made.size))

    if not os.path.isfile(COMMUNITY):
        print("      no %s; the ominous banner keeps whatever is there"
              % os.path.basename(COMMUNITY))
        return
    ominous = Image.open(COMMUNITY).convert("RGBA")
    path = os.path.join(BANNERS, "banner_illager.png")
    made = written(ominous, ominous.crop(FRONT))
    made.save(path)
    print("      %-12s %s, %dx%d" % ("illager", os.path.basename(path),
                                     *made.size))


if __name__ == "__main__":
    main()
