"""A square end portal tile.

    python -m tools.textures.end_portal

Bedrock's `end_portal.png` is a disc of starfield on a clear background, and a
plane reading it shows a circle where the game shows a square. Every clear
pixel here takes the colour of the nearest painted one, which carries the
starfield out to the corners. Written as `scaffold_end_portal.png` in the
vanilla pack. Nothing here is needed at run time.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
SOURCE = os.path.join(BLOCKS, "end_portal.png")
OUT = os.path.join(BLOCKS, "scaffold_end_portal.png")
TILE = 16


def squared(image):
    """The tile with every clear pixel filled from its nearest painted one."""
    image = image.convert("RGBA").crop((0, 0, TILE, TILE))
    pixels = image.load()
    painted = [(x, y) for x in range(TILE) for y in range(TILE)
               if pixels[x, y][3] == 255]
    out = image.copy()
    filled = out.load()
    for x in range(TILE):
        for y in range(TILE):
            if pixels[x, y][3] == 255:
                continue
            near = min(painted, key=lambda p: ((p[0] - x) ** 2 + (p[1] - y) ** 2, p))
            filled[x, y] = pixels[near]
    return out


def main():
    print("writing the square end portal")
    squared(Image.open(SOURCE)).save(OUT)


if __name__ == "__main__":
    main()
