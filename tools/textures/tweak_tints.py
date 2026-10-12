"""Tint a tweak's picture the way the vanilla pack tints the one it replaces.

    python -m tools.textures.tweak_tints

A ghost block cannot run the game's colour maps, so the vanilla pack here keeps
leaves, redstone dust and the other tinted pictures already coloured. A tweak
replaces the game's grey original with a grey picture of its own, which a ghost
then draws grey. A tweak that paints its picture in colour already is left
alone. So each staged tweak picture whose vanilla namesake is
pre-tinted is multiplied by the same colour: the pre-tinted picture's average
over the game's own grey original.

The tweak's grey picture is kept beside it as `<name>_grey.png` the first time,
and every run tints from that, so running twice writes the same file. Re-run
after staging the tweaks again. Nothing here is needed at run time.
"""
import glob
import os

import numpy as np
from PIL import Image
from tools import sources

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TWEAKS = os.path.join(ROOT, "scaffold", "tweakpacks")
VANILLA = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
GAME = sources.resource_pack("textures", "blocks")
GREY = "_grey"


## how far from grey a picture's colours may sit on average and still count as
## grey; a tweak that paints in colour already is left alone
GREY_SPREAD = 5


def _greyscale(path):
    pixels = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    shown = pixels[..., 3] > 0
    rgb = pixels[shown][:, :3]
    return not len(rgb) or np.abs(rgb - rgb.mean(axis=1, keepdims=True)).mean() < GREY_SPREAD


def _mean(path):
    pixels = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    shown = pixels[..., 3] > 0
    return pixels[shown][:, :3].mean(axis=0) if shown.any() else None


def _found(folder, name):
    for kind in (".png", ".tga"):
        path = os.path.join(folder, name + kind)
        if os.path.isfile(path):
            return path
    return None


def tint(name):
    """The colour the vanilla pack multiplies this picture by, or None."""
    ours, original = _found(VANILLA, name), _found(GAME, name)
    if not ours or not original:
        return None
    coloured, grey = _mean(ours), _mean(original)
    if coloured is None or grey is None or np.allclose(coloured, grey, atol=2):
        return None
    return np.clip(coloured / np.maximum(grey, 1), 0, 4)


def main():
    print("tinting the tweaks' greyscale pictures")
    for path in sorted(glob.glob(os.path.join(TWEAKS, "*", "textures", "blocks", "*.png"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.endswith(GREY):
            continue
        colour = tint(name)
        if colour is None:
            continue
        grey = os.path.join(os.path.dirname(path), name + GREY + ".png")
        if not os.path.isfile(grey):
            if not _greyscale(path):
                continue
            os.replace(path, grey)
        pixels = np.asarray(Image.open(grey).convert("RGBA")).astype(float)
        pixels[..., :3] = np.clip(pixels[..., :3] * colour, 0, 255)
        Image.fromarray(pixels.astype(np.uint8), "RGBA").save(path)
        print("   %s/%s" % (os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))), name))


if __name__ == "__main__":
    main()
