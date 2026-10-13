"""Redstone dust's straight line, coloured the way the vanilla pack colours its
cross.

    python -m tools.textures.dust_line

The game tints dust as it draws it, and a ghost cannot, so the vanilla pack's
`redstone_dust_cross` is kept already red. A straight run of dust reads
`redstone_dust_line` instead, which is grey in the game's pack. It is written
here from the game's own grey line, multiplied by the colour the cross
carries over its own grey original, so the two match. A tweak's grey line is
then tinted the same way by `tools/textures/tweak_tints.py`, which runs after.
Nothing here is needed at run time.
"""
import os

import numpy as np
from PIL import Image
from tools import sources

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VANILLA = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
GAME = sources.resource_pack("textures", "blocks")


def _mean(path):
    pixels = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    shown = pixels[..., 3] > 0
    return pixels[shown][:, :3].mean(axis=0)


def main():
    ## the game's own grey pictures, which dust is drawn from, tinted by its
    ## power as a pack is built
    for name in ("redstone_dust_cross", "redstone_dust_line"):
        Image.open(os.path.join(GAME, name + ".png")).convert("RGBA").save(
            os.path.join(VANILLA, name + "_grey.png"))
    print("writing redstone dust's line")
    tint = _mean(os.path.join(VANILLA, "redstone_dust_cross.png")) / _mean(
        os.path.join(GAME, "redstone_dust_cross.png"))
    line = np.asarray(Image.open(os.path.join(GAME, "redstone_dust_line.png"))
                      .convert("RGBA")).astype(float)
    line[..., :3] = np.clip(line[..., :3] * tint, 0, 255)
    Image.fromarray(line.astype(np.uint8), "RGBA").save(
        os.path.join(VANILLA, "redstone_dust_line.png"))


if __name__ == "__main__":
    main()
