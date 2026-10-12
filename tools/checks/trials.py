"""Three ways round a ghost plane's clear texels hiding what is behind it.

A ghost is drawn blended, not cut out, so a texel with nothing in it still
takes the depth it stands at and hides any ghost drawn after it. Each trial is
a copy of one family drawn a different way, given a pseudo block id the gallery
places in the ghost only, over a real block of the family it copies:

  haze   every clear texel of a plane's picture white at about one percent
  last   the family's turned cubes, which are its planes, drawn after every
         other bone
  trim   every plane cut down to the part of its picture with something in it

`tools/checks/gallery.py --trials` lays them out. Not shipped.
"""
import copy
import os

from PIL import Image

from scaffold.pack import armor_stand_geo_class as asgc

## the block the trials copy, and its state for each
BASE = "calibrated_sculk_sensor"
STATES = {"minecraft:cardinal_direction": "north", "sculk_sensor_phase": 0}
TRIALS = ("haze", "last", "trim")
## the alpha a clear texel takes in the haze trial, out of 255
HAZE_ALPHA = 3
FACES = ("north", "south", "east", "west", "up", "down")


def block(trial):
    return "scaffold:trial_" + trial


def _planes(shape):
    """The indices of a form's cubes that are flat."""
    return [i for i, size in enumerate(shape["size"]) if min(size) == 0]


def _picture(geo, name):
    """The 16x16 tile a texture reference reads, as RGBA."""
    source, window = asgc.split_window(name)
    image = Image.open(geo.texture_file(source)).convert("RGBA")
    return image.crop((window[0], window[1], window[0] + 16, window[1] + 16))


def _faces_of(uv, index):
    """(face, texture) for each face of a cube that names a texture."""
    found = []
    for face in FACES:
        names = uv.get("overwrite", {}).get(face, [])
        if index < len(names) and names[index] not in ("default", None) \
                and not str(names[index]).startswith("@"):
            if any(uv["uv_sizes"][face][index]):
                found.append((face, names[index]))
    return found


def haze(geo, shapes, uvs, folder):
    """Every plane reads a copy of its picture with clear texels faintly white."""
    out = os.path.join(folder, "textures", "trials")
    os.makedirs(out, exist_ok=True)
    made = {}
    for form, shape in shapes.items():
        uv = uvs[form]
        for index in _planes(shape):
            for face, name in _faces_of(uv, index):
                if name not in made:
                    picture = _picture(geo, name)
                    pixels = picture.load()
                    for x in range(16):
                        for y in range(16):
                            if pixels[x, y][3] == 0:
                                pixels[x, y] = (255, 255, 255, HAZE_ALPHA)
                    key = "haze_%d" % len(made)
                    picture.save(os.path.join(out, key + ".png"))
                    made[name] = "textures/trials/" + key
                uv["overwrite"][face][index] = made[name]


def trim(geo, shapes, uvs):
    """Every plane cut to the painted part of its window.

    Across, the same amount comes off both sides, the smaller of the two clear
    margins, so a plane turned about its own middle stays where it was; up and
    down, each end loses its own clear rows."""
    for form, shape in shapes.items():
        uv = uvs[form]
        for index in _planes(shape):
            faces = _faces_of(uv, index)
            if not faces:
                continue
            face, name = faces[0]
            alpha = _picture(geo, name).split()[3].load()
            (u0, v0), (du, dv) = uv["offset"][face][index], uv["uv_sizes"][face][index]
            cols = sorted({round((u0 + du * t) * 16) for t in (0, 1)})
            rows = sorted({round((v0 + dv * t) * 16) for t in (0, 1)})
            painted = [(x, y) for x in range(max(cols[0], 0), min(cols[1], 16))
                       for y in range(max(rows[0], 0), min(rows[1], 16)) if alpha[x, y]]
            if not painted:
                continue
            left = min(x for x, _ in painted) - cols[0]
            right = cols[1] - 1 - max(x for x, _ in painted)
            top = min(y for _, y in painted) - rows[0]
            bottom = rows[1] - 1 - max(y for _, y in painted)
            side = min(left, right)
            wide = cols[1] - cols[0]
            tall = rows[1] - rows[0]
            size = shape["size"][index]
            at = shape["offsets"][index]
            across = 0 if size[0] else 2
            ## the cube's own size along its picture, in blocks per texel
            per_u = size[across] / float(wide)
            per_v = size[1] / float(tall)
            ## v runs down the picture and up the block; a window read upside
            ## down swaps which end is the top
            lost_top, lost_bottom = (top, bottom) if dv > 0 else (bottom, top)
            size[across] -= 2 * side * per_u
            at[across] += side * per_u
            size[1] -= (lost_top + lost_bottom) * per_v
            at[1] += lost_bottom * per_v
            for face in FACES:
                if not any(uv["uv_sizes"][face][index]):
                    continue
                (fu, fv), (su, sv) = uv["offset"][face][index], uv["uv_sizes"][face][index]
                su_sign = 1 if su > 0 else -1
                sv_sign = 1 if sv > 0 else -1
                uv["offset"][face][index] = [fu + su_sign * side / 16.0,
                                             fv + sv_sign * (top if sv > 0 else bottom) / 16.0]
                uv["uv_sizes"][face][index] = [su - su_sign * 2 * side / 16.0,
                                               sv - sv_sign * (top + bottom) / 16.0]


def install(geo, folder):
    """Add each trial's family to a geometry builder, in memory."""
    family = geo.defs[BASE]
    for trial in TRIALS:
        name = "trial_" + trial
        shapes = copy.deepcopy(geo.block_shapes[family])
        uvs = copy.deepcopy(geo.block_uv[family])
        if trial == "haze":
            haze(geo, shapes, uvs, folder)
        elif trial == "trim":
            trim(geo, shapes, uvs)
        else:
            geo.drawn_last.add(name)
        geo.defs[block(trial)] = name
        geo.block_shapes[name] = shapes
        geo.block_uv[name] = uvs
        geo.rules[name] = copy.deepcopy(geo.rules.get(family, {}))
        geo.block_rotations[name] = copy.deepcopy(geo.block_rotations.get(family, {}))
