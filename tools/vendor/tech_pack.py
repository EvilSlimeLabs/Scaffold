"""Copy the part of TechPack a generated pack needs into the package.

    python -m tools.vendor.tech_pack

`be_tech_pack/` is a git submodule and a whole add-on repository, seventy
megabytes of it, most of that source art and history. A generated pack draws on
about a megabyte, and that megabyte has to live *inside* `scaffold/` for the
same reason the lookup tables do. Setuptools ships package data only from under
the package directory, so a `pip install` of a project keeping it outside
installs a program that cannot offer the TechPack setting at all.

The subset is therefore staged into `scaffold/techpack/` and committed. The
submodule stays the source of truth, so re-run this after updating it.
`tests/test_tech_pack.py` fails if the two have drifted.
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUBMODULE = os.path.join(ROOT, "be_tech_pack")
STAGED = os.path.join(ROOT, "scaffold", "techpack")

## the folders a generated pack actually draws from
KEEP = ("animation_controllers", "animations", "entity", "materials",
        "models", "particles", "render_controllers", "textures")

## and the paperwork that has to travel with them
FILES = ("manifest.json", "LICENSE", "README.md")

## source art and editor leftovers that are in the submodule but have no
## business in a generated pack
SKIP_SUFFIXES = (".afphoto", ".xcf", ".psd", ".py", ".pyc")
SKIP_NAMES = {"Thumbs.db", ".DS_Store"}


def worth_shipping(name):
    return name not in SKIP_NAMES and not name.lower().endswith(SKIP_SUFFIXES)


def stage():
    if not os.path.isdir(SUBMODULE):
        sys.exit("be_tech_pack is not checked out.\n"
                 "  git submodule update --init be_tech_pack")

    if os.path.isdir(STAGED):
        shutil.rmtree(STAGED)
    os.makedirs(STAGED)

    written = 0
    for folder in KEEP:
        source = os.path.join(SUBMODULE, folder)
        if not os.path.isdir(source):
            continue
        for base, dirs, names in os.walk(source):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in names:
                if not worth_shipping(name):
                    continue
                relative = os.path.relpath(os.path.join(base, name), SUBMODULE)
                target = os.path.join(STAGED, relative)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(base, name), target)
                written += 1

    for name in FILES:
        source = os.path.join(SUBMODULE, name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(STAGED, name))
            written += 1
    return written


def differences():
    """Files that are staged and stale, or shippable and not staged.

    What `tests/test_tech_pack.py` checks, so that a submodule update without a
    re-stage is caught rather than silently shipping the old assets.
    """
    if not os.path.isdir(SUBMODULE) or not os.path.isdir(STAGED):
        return None
    wrong = []
    for folder in KEEP:
        source = os.path.join(SUBMODULE, folder)
        if not os.path.isdir(source):
            continue
        for base, dirs, names in os.walk(source):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in names:
                if not worth_shipping(name):
                    continue
                relative = os.path.relpath(os.path.join(base, name), SUBMODULE)
                mine = os.path.join(STAGED, relative)
                if not os.path.isfile(mine):
                    wrong.append("missing: " + relative)
                elif not filecmp.cmp(os.path.join(base, name), mine, shallow=False):
                    wrong.append("stale: " + relative)
    return wrong


if __name__ == "__main__":
    count = stage()
    size = sum(os.path.getsize(os.path.join(b, n))
               for b, _, names in os.walk(STAGED) for n in names)
    print("staged %d files (%.1f MB) into scaffold/techpack/"
          % (count, size / 1024.0 / 1024.0))
