"""Each tweak's version of a block, side by side in one pack.

A pack is built with a set of tweaks, and every block in it is drawn with all of
them. A world for checking tweaks wants each tweak on its own blocks, the two of
a conflicting pair beside each other and a block both tabs change shown both
ways. So each (tweak, block) is given a family of its own, copied from a
geometry builder that has that tweak alone, under a pseudo block id the gallery
places in the ghost only, over the real block.

**Textures are read through the tweak they belong to.** Two tweaks may stage
files of the same name, the sand and gravel pair do, so every texture a variant
reads is named with its tweak in front, `tw:<tweak>|textures/...`, and looked up
in that tweak's folder alone. The name is also the atlas key, so each tweak's
picture is a tile of its own.

Used by `tools/checks/gallery.py --tweak-world`. Not shipped.
"""
import copy

from scaffold.pack import armor_stand_geo_class as asgc

PREFIX = "tw:%s|"


def block(tweak, name):
    """The pseudo block id one tweak's version of a block is drawn as."""
    return "scaffold:tw_%s__%s" % (tweak, name)


def _named(tweak, value):
    """A texture reference read through a tweak's own folder."""
    if isinstance(value, str) and value.startswith("textures/"):
        return PREFIX % tweak + value
    return value


def install(geo, pairs, builder=None):
    """Give `geo` a family per (tweak, block) in `pairs`, and the lookups that
    read each one's textures through its own tweak.

    `builder` is the geometry builder class each tweak's tables come from; the
    gallery passes the plain one, since the class it builds with installs these
    variants itself."""
    builder = builder or asgc.ArmorStandGeo
    builders, owners = {}, {}
    for tweak, name in pairs:
        if tweak not in builders:
            builders[tweak] = builder("tweak", offsets=[0, 0, 0], tweaks=[tweak])
        tweaked = builders[tweak]
        family = tweaked.defs.get(name)
        if family is None or family == "ignore":
            continue
        own = "tw_%s__%s" % (tweak, family)
        if own not in geo.block_shapes:
            geo.block_shapes[own] = copy.deepcopy(tweaked.block_shapes[family])
            uvs = copy.deepcopy(tweaked.block_uv[family])
            for form in uvs.values():
                for face, names in form.get("overwrite", {}).items():
                    form["overwrite"][face] = [_named(tweak, n) for n in names]
            geo.block_uv[own] = uvs
            geo.rules[own] = copy.deepcopy(tweaked.rules.get(family, {}))
            geo.block_rotations[own] = copy.deepcopy(tweaked.block_rotations.get(family, {}))
        geo.defs[block(tweak, name)] = own
        owners[block(tweak, name)] = (tweak, name)

    declared = geo.get_block_texture_paths
    found = geo.texture_file

    def get_block_texture_paths(name, *args, **kwargs):
        if name in owners:
            tweak, real = owners[name]
            paths = builders[tweak].get_block_texture_paths(real, *args, **kwargs)
            return {face: _named(tweak, value) for face, value in paths.items()}
        return declared(name, *args, **kwargs)

    def texture_file(source):
        if source.startswith("tw:"):
            tweak, _, rest = source[3:].partition("|")
            return builders[tweak].texture_file(rest)
        return found(source)

    geo.get_block_texture_paths = get_block_texture_paths
    geo.texture_file = texture_file
