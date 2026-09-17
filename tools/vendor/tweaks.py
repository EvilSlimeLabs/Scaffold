"""Stage the Bedrock Tweaks this project offers into the package.

    python -m tools.vendor.tweaks                 report, change nothing
    python -m tools.vendor.tweaks --apply         copy them in

`bedrock_tweaks/` is a git submodule of https://github.com/BedrockTweaks/Files
and is seven hundred megabytes, so it cannot be package data. Scaffold offers
thirteen of its packs and each is a handful of textures, so those are copied
into `scaffold/tweakpacks/` and committed -- the same arrangement TechPack has, and
what lets a pip install offer the Tweaks menu at all. The submodule stays the
source of truth: **re-run this after updating it**, or a release ships the old
art.

`scaffold/lookups/tweaks.json` is what says which packs are offered and where
each one lives in the submodule. Nothing here decides that.

**What is copied.** A Bedrock Tweaks pack is an ordinary resource pack and
Scaffold reads only three kinds of thing out of one: the textures, the
`blocks.json` that says which texture a block wears, and the
`textures/terrain_texture.json` that turns a texture's name into a file. Item
definitions, pack icons, sounds, the UI and the RTX companion maps are all
dropped, which is most of the weight.

**The licence asks for two things.** Bedrock Tweaks' own licence allows this
project to include the files provided the result is not sold and provided the
credit travels with them. `LICENSE` is copied in beside the art for that reason
and `pack/manifest.py` puts the credit in any pack built with a tweak on.
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "bedrock_tweaks", "resource_packs", "files")
LICENCE = os.path.join(ROOT, "bedrock_tweaks", "LICENSE")
TARGET = os.path.join(ROOT, "scaffold", "tweakpacks")
TABLE = os.path.join(ROOT, "scaffold", "lookups", "tweaks.json")

## What a build can read out of a tweak pack: the textures, the `blocks.json`
## that says which texture a block wears, and the `terrain_texture.json` that
## turns a texture's name into a file.
##
## **And the pack's own icon**, which is not for a build at all: the Tweaks
## dialog shows it beside each name, so somebody picking one is looking at what
## it does rather than reading a title. Bedrock Tweaks draws one per pack at
## ninety pixels square.
WANTED = ("textures/", "blocks.json", "pack_icon.png")
SKIP_SUFFIXES = ("_mers.tga", "_normal.tga", "_heightmap.tga",
                 ".texture_set.json")


def offered():
    """The packs this project offers, as {id: entry}, in the table's order."""
    with open(TABLE, encoding="utf-8") as f:
        return json.load(f)


def wanted(relative):
    """Whether one file of a tweak pack is something Scaffold uses."""
    if relative.endswith(SKIP_SUFFIXES):
        return False
    return relative.startswith(WANTED[0]) or relative in WANTED[1:]


def files_of(where):
    """Every file of one pack worth staging, as paths relative to its root."""
    root = os.path.join(SOURCE, where)
    out = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            path = os.path.join(dirpath, name)
            relative = os.path.relpath(path, root).replace("\\", "/")
            if wanted(relative):
                out.append(relative)
    return sorted(out)


def stage(apply):
    if not os.path.isdir(SOURCE):
        print("bedrock_tweaks/ is not checked out. Run:")
        print("    git submodule update --init bedrock_tweaks")
        return 1

    total = 0
    for key, entry in offered().items():
        where = entry["from"]
        root = os.path.join(SOURCE, where)
        if not os.path.isdir(root):
            print("%-34s %s is not in the submodule" % (key, where))
            return 1
        names = files_of(where)
        total += len(names)
        print("%-34s %3d files  <- %s" % (key, len(names), where))
        if not apply:
            continue
        into = os.path.join(TARGET, key)
        ## the whole folder goes, so a texture dropped upstream stops shipping
        ## here too rather than lingering as art nothing names any more
        if os.path.isdir(into):
            shutil.rmtree(into)
        for name in names:
            destination = os.path.join(into, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(os.path.join(root, name), destination)

    print("\n%d files across %d tweaks" % (total, len(offered())))
    if apply:
        os.makedirs(TARGET, exist_ok=True)
        shutil.copyfile(LICENCE, os.path.join(TARGET, "LICENSE"))
        print("staged into scaffold/tweakpacks/, with the licence beside them")
    else:
        print("nothing written; pass --apply to copy them in")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="copy the files in rather than only reporting")
    sys.exit(stage(parser.parse_args().apply))


if __name__ == "__main__":
    main()
