"""Pictures for low geometry's boxes, drawn from the blocks they stand in for.

    python -m tools.textures.low

A few blocks are simplified to a box whose faces no texture in the pack can
dress: a copper golem statue, whose sheet is laid out for a model, and a banner
carrying a design, whose picture is spread over a grid of quads. Each is drawn
here from its detailed form, the way `tools/checks/render.py` draws a block, and
the drawing is the box's picture:

  copper golem statues   the statue from each side and from above, one picture
                         per side, per age of copper
  marked banners         the cloth alone, seen from in front, for the illager's
                         banner and for a banner carrying a design

Each picture is the block's own outline stretched to sixteen pixels square, and
the box it dresses has the block's proportions, which undoes the stretch.
Written into the vanilla pack under `textures/blocks/scaffold_low_*`. Nothing
here is needed at run time.
"""
import copy
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PACK = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack")
NAME = "textures/blocks/scaffold_low_%s"
BACKDROP = (255, 0, 255)

## each age of copper's statue family, and the block drawn for it
STATUES = {"copper_golem_statue": "copper_golem_statue",
           "exposed_copper_golem_statue": "exposed_copper_golem_statue",
           "weathered_copper_golem_statue": "weathered_copper_golem_statue",
           "oxidized_copper_golem_statue": "oxidized_copper_golem_statue"}
STATUE_VIEWS = ("north", "south", "east", "west", "up")
## the marked banners: the form, and the block entity that marks it
BANNERS = {"illager": {"Type": 1},
           "designed": {"Base": 15, "Patterns": [{"Color": 0, "Pattern": "bo"}]}}


SCALE = 2


def picture(quads, atlas, view):
    """One view drawn on a clear ground, cropped to the outline of the shape,
    clear texels and all, and stretched to sixteen pixels square."""
    import numpy as np
    from tools.checks import render
    frame = render._frame(quads)
    drawn = render.draw(quads, atlas, view, SCALE, BACKDROP, frame).convert("RGBA")
    pixels = drawn.load()
    for x in range(drawn.width):
        for y in range(drawn.height):
            if pixels[x, y][:3] == BACKDROP:
                pixels[x, y] = (0, 0, 0, 0)
    ## the shape's outline in the drawing, by the same projection `draw` uses
    _look, right, up = (np.asarray(v, dtype=float) for v in render.VIEWS[view])
    low, high = frame
    corners = np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1])
                        for z in (low[2], high[2])], dtype=float)
    x0, y1 = (corners @ right).min(), (corners @ up).max()
    points = np.concatenate([q[0] for q in quads])
    px = render.TEXELS * SCALE
    sx, sy = (points @ right - x0) * px, (y1 - points @ up) * px
    box = (int(round(sx.min())), int(round(sy.min())), int(round(sx.max())), int(round(sy.max())))
    return drawn.crop(box).resize((16, 16), Image.NEAREST)


def save(image, name):
    path = os.path.join(PACK, (NAME % name) + ".png")
    image.save(path)
    return NAME % name


def statues():
    from scaffold.pack import armor_stand_geo_class as asgc
    from tools.checks import render
    geo = asgc.ArmorStandGeo("low", offsets=[0, 0, 0])
    for family, block in STATUES.items():
        quads, atlas = render.mesh(block, geo=geo, states={
            "minecraft:cardinal_direction": "north"}, entity={"Pose": 0})
        for view in STATUE_VIEWS:
            save(picture(quads, atlas, view), "%s_%s" % (family, view))


def is_cloth(size):
    """A quad of a marked banner's cloth: a thin piece shorter than half a
    block."""
    return size[2] <= 1 / 16.0 + 1e-6 and size[1] < 7.5 / 16


def banners():
    from scaffold.pack import armor_stand_geo_class as asgc
    from tools.checks import render
    import nbtlib
    from nbtlib import Byte, Compound, Int, List, String
    geo = asgc.ArmorStandGeo("low", offsets=[0, 0, 0])
    shapes, uvs = geo.block_shapes["standing_banner"], geo.block_uv["standing_banner"]
    for form, entity in BANNERS.items():
        ## the cloth alone, so the drawing is the design and not the pole
        keep = [i for i, size in enumerate(shapes[form]["size"]) if is_cloth(size)]
        shape = copy.deepcopy(shapes[form])
        for key in ("size", "offsets", "rotation"):
            if key in shape:
                shape[key] = [shape[key][i] for i in keep]
        uv = copy.deepcopy(uvs[form])
        for part in uv.values():
            for face in part:
                part[face] = [part[face][i] for i in keep]
        geo.block_shapes["low_cloth"] = {"default": shape}
        geo.block_uv["low_cloth"] = {"default": uv}
        geo.defs["low_cloth"] = "low_cloth"
        geo.rules["low_cloth"] = {}
        real = geo.get_block_texture_paths
        geo.get_block_texture_paths = lambda name, *a, real=real: real(
            "standing_banner" if name == "low_cloth" else name, *a)
        quads, atlas = render.mesh("low_cloth", geo=geo)
        geo.get_block_texture_paths = real
        save(picture(quads, atlas, "north"), "banner_" + form)


def main():
    print("drawing the pictures low geometry's boxes wear")
    statues()
    banners()


if __name__ == "__main__":
    main()
