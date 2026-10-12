"""Make water see-through, as water is in the game.

    python -m tools.textures.water

Vanilla's water tile is close to opaque. The game gets water's transparency from
the material it draws it with rather than from the picture, and a ghost block
has no such material: it is drawn with one blended pass over whatever is behind
it, so an opaque tile is an opaque block, and a pool of water in a build hides
everything behind it.

So the grey picture is tinted blue, the way every biome-tinted tile in this pack
is tinted ahead of time, with Java's default water colour, and every pixel takes
one alpha, `ALPHA`. That alpha is then
multiplied by the transparency slider as the pack is built --
`armor_stand_geo_class.alpha`, 0.35 by default -- so water comes out fainter
than the solid blocks around it, the way it does in the game.

Both files are written in place, in the vanilla pack this project ships, and
nothing else reads them: `water` and `flowing_water` are the only two blocks in
`blocks.json` naming `still_water_grey` or `flowing_water_grey`. They are made
from the game's own grey water rather than from what is there, so running
this twice writes the same bytes as running it once.

Nothing here is needed at run time.
"""
import os

from PIL import Image
from tools import sources

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack",
                      "textures", "blocks")

## the still tile is the up and down faces, the flow tile the four sides
FILES = ("water_still_grey.png", "water_flow_grey.png")

## how solid water is before the transparency slider: about two thirds, near
## what the game's own water material shows
ALPHA = 160


## The colour the grey water is tinted with: Java's default water, a deeper
## blue than Bedrock's ocean water, so a pool reads as water beside ice rather
## than as more ice. The grey picture is the game's own, which this pack
## was merged from; with that submodule absent the files are left as they are.
COLOUR = (0x3F, 0x76, 0xE4)
GREY = sources.resource_pack("textures", "blocks")


def see_through(image):
    """One grey image tinted with `COLOUR`, every pixel at `ALPHA`.

    Both files are strips of animation frames -- the still water is sixteen by
    five hundred and twelve and the flow is twice as wide again -- and only the
    top left tile of either is ever read. Every frame is treated alike, so the
    file still reads as one animation to anything that opens it.
    """
    image = image.convert("RGBA")
    red, green, blue, _alpha = image.split()
    image = Image.merge("RGBA", (
        red.point(lambda v: v * COLOUR[0] // 255),
        green.point(lambda v: v * COLOUR[1] // 255),
        blue.point(lambda v: v * COLOUR[2] // 255),
        Image.new("L", image.size, ALPHA)))
    return image


def main():
    print("writing the see-through water")
    for name in FILES:
        path = os.path.join(BLOCKS, name)
        if not os.path.isfile(path):
            print("   %-24s is not there" % name)
            continue
        source = os.path.join(GREY, name)
        if not os.path.isfile(source):
            print("   %-24s left alone, no grey water to tint" % name)
            continue
        see_through(Image.open(source)).save(path)
        print("   %-24s alpha %d" % (name, ALPHA))


if __name__ == "__main__":
    main()
