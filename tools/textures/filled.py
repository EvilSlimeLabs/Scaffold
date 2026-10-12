"""Pictures with their holes filled from what is drawn under them.

    python -m tools.textures.filled

Some blocks are a picture with a clear hole in it and something drawn just
behind the hole: a sea pickle's top over the plane inside it. A ghost cannot draw the thing behind, because a
clear texel still takes the depth it stands at and hides whatever is drawn after
it; and drawn a hair apart, the two fight. So the hole is filled from the
picture that shows through it and the block draws the one surface.

Each is written into the vanilla pack as `scaffold_<name>.png`.

**A hopper's top is a solid face here**, the vanilla pack's `hopper_top` filled
in, because Scaffold's bowl is a solid box. Directional Hoppers' tops are clear
in the middle, so each is laid over the vanilla pack's in place, in the staged
tweak; a picture already filled comes out the same. Nothing here is needed at
run time.
"""
import glob
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
HOPPER_TOPS = os.path.join(ROOT, "scaffold", "tweakpacks", "directional_hoppers",
                           "textures", "blocks", "hopper_top", "*.png")

## name: (the picture behind, where on the picture the hole's square starts,
## where the square behind it starts, and how big the square is)
FILLS = {
    ## the pickle's top, four by four at x4, over Java's plane reading x8
    "sea_pickle": ("sea_pickle", (4, 1), (8, 1), 4),
}


def filled(image, behind, at, source, square):
    image = image.convert("RGBA")
    behind = behind.convert("RGBA")
    pixels, under = image.load(), behind.load()
    for dx in range(square):
        for dy in range(square):
            here = (at[0] + dx, at[1] + dy)
            if pixels[here][3] < 255:
                below = under[source[0] + dx, source[1] + dy]
                if below[3]:
                    top = pixels[here]
                    ## what the hole lets through, under whatever of the picture
                    ## is drawn over it
                    out = Image.new("RGBA", (1, 1), below)
                    out.alpha_composite(Image.new("RGBA", (1, 1), top))
                    pixels[here] = out.getpixel((0, 0))
    return image


def main():
    print("writing the pictures with their holes filled")
    for name, (behind, at, source, square) in FILLS.items():
        image = Image.open(os.path.join(BLOCKS, name + ".png"))
        under = Image.open(os.path.join(BLOCKS, behind + ".png"))
        filled(image, under, at, source, square).save(
            os.path.join(BLOCKS, "scaffold_" + name + ".png"))
        print("   %s" % name)
    under = Image.open(os.path.join(BLOCKS, "hopper_top.png")).convert("RGBA")
    tops = sorted(glob.glob(HOPPER_TOPS))
    for path in tops:
        top = under.copy()
        top.alpha_composite(Image.open(path).convert("RGBA").crop((0, 0, 16, 16)))
        top.save(path)
    print("   %d hopper tops" % len(tops))


if __name__ == "__main__":
    main()
