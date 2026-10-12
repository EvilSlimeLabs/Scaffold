"""Ways round a container's fill count cutting holes in the container.

The count is drawn on quads a hair off the container's faces, and their clear
texels take the depth they stand at, so a count drawn before the face behind it
blanks the face where the count's quad is. The count's quads are planes, in a
bone of their own drawn after the blocks', and in a busy world the cutout
comes and goes as the camera moves, which a lone hopper does not show. Each
trial draws every container's count another way:

  now         as a pack draws it today
  same_bone   the count's quads in the container's own bone, after its cubes,
              when the two turn alike
  opaque      the count's clear texels painted a container's dark grey, so a
              quad drawn first hides nothing it would not cover anyway

`tools/checks/gallery.py --fill-trials` lays them out, a plot per trial, each
holding every container in every facing at three signals. Not shipped.
"""
import copy
import os

from PIL import Image

from scaffold import marks

TRIALS = ("now", "same_bone", "opaque")
## a hopper's facings: down, and the four sides
FACINGS = (0, 2, 3, 4, 5)
## the colour the opaque trial paints a count's clear texels, a hopper's side
BACKING = (61, 61, 64, 255)


def family_of(trial, family):
    return "ft_%s__%s" % (trial, family)


def install(geo, folder):
    """Each trial's copy of the count's family, in memory, and the pictures
    the opaque one reads, written into `folder`."""
    family = geo.defs.get(marks.FILL)
    if family is None:
        return
    for trial in TRIALS[1:]:
        made = family_of(trial, family)
        geo.block_shapes[made] = copy.deepcopy(geo.block_shapes[family])
        uvs = copy.deepcopy(geo.block_uv[family])
        geo.rules[made] = copy.deepcopy(geo.rules.get(family, {}))
        geo.block_rotations[made] = copy.deepcopy(geo.block_rotations.get(family, {}))
        if trial == "same_bone":
            geo.shared_bone.add(made)
        if trial == "opaque":
            for form in uvs.values():
                for face, names in form.get("overwrite", {}).items():
                    form["overwrite"][face] = [_opaque(geo, n, folder) for n in names]
        geo.block_uv[made] = uvs


def _opaque(geo, name, folder):
    """A copy of a count's picture with its clear texels painted over."""
    if not isinstance(name, str) or not name.startswith("textures/"):
        return name
    source, sep, rest = name.partition("#")
    made = source + "_opaque"
    target = os.path.join(folder, made + ".png")
    if not os.path.isfile(target):
        picture = Image.open(geo.texture_file(source)).convert("RGBA")
        backed = Image.new("RGBA", picture.size, BACKING)
        backed.alpha_composite(picture)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        backed.save(target)
    return made + sep + rest
