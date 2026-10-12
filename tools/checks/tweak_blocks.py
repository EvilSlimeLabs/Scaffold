"""Which blocks each tweak changes, found by building with it and without it.

    python -m tools.checks.tweak_blocks

A tweak may restage a texture, repoint a block at a family of its own, or bring
whole families with it, and a list kept by hand of what each one touches would
be wrong the first time a tweak changed. So each is applied alone and every
block is compared against the plain build: its family, that family's shape and
windows, and the file each of its faces reads. A block that differs in any of
them is one the tweak changes.

Used by `tools/checks/gallery.py --tweak-world`. Not shipped.
"""
import json
import sys

from scaffold import tweaks as tweak_packs
from scaffold.pack import armor_stand_geo_class as asgc


def _look(geo, block):
    """Everything about a block that a tweak could change, as one string."""
    family = geo.defs.get(block)
    ## a few vanilla blocks declare a name the terrain table does not have;
    ## that is the same with a tweak and without, so it is part of the look
    try:
        textures = geo.get_block_texture_paths(block) or {}
    except KeyError as missing:
        textures = {"missing": str(missing)}
    files = {}
    for face, name in textures.items():
        source = asgc.split_window(str(name))[0]
        try:
            files[face] = geo.texture_file(source)
        except Exception:
            files[face] = source
    ## and the files a family names outright, which a tweak may restage too
    named = {}
    for form in (geo.block_uv.get(family) or {}).values():
        for names in form.get("overwrite", {}).values():
            for name in names:
                if isinstance(name, str) and name.startswith("textures/"):
                    source = asgc.split_window(name)[0]
                    try:
                        named[source] = geo.texture_file(source)
                    except Exception:
                        named[source] = source
    return json.dumps([family, geo.block_shapes.get(family), geo.block_uv.get(family),
                       geo.rules.get(family), files, named], sort_keys=True, default=str)


def changed_by(tweak, blocks=None):
    """The blocks a single tweak changes."""
    plain = asgc.ArmorStandGeo("plain", offsets=[0, 0, 0])
    tweaked = asgc.ArmorStandGeo("tweaked", offsets=[0, 0, 0], tweaks=[tweak])
    blocks = blocks or sorted(set(plain.defs) | set(tweaked.defs))
    return [block for block in blocks
            if tweaked.defs.get(block) != "ignore"
            and _look(plain, block) != _look(tweaked, block)]


def groups():
    """{tab: {tweak: [blocks]}} for every tweak that ships, by its tab."""
    found = {}
    for tweak in tweak_packs.offered():
        if tweak_packs.folder(tweak) is None:
            continue
        found.setdefault(tweak_packs.tab(tweak), {})[tweak] = changed_by(tweak)
    return found


def main():
    for tab, tweaks in groups().items():
        print(tab)
        for tweak, blocks in tweaks.items():
            print("   %-38s %3d  %s" % (tweak, len(blocks), " ".join(blocks[:6])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
