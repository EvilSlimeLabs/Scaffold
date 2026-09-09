"""Fold the Bedrock Technical Resource Pack into a generated Scaffold pack.

Both packs replace `entity/armor_stand.entity.json`, and a client entity file in
a resource pack **replaces** the vanilla one rather than merging with it. Between
two packs only the higher one in the player's list is read at all, so running
Scaffold and TechPack side by side silently loses whichever sits lower: either
the ghost blocks stop appearing, or every TechPack visualisation does. There is
no ordering that gives both.

Bundling is the way out. The two entity descriptions are merged into one file
and TechPack's supporting assets are copied in beside Scaffold's, so a single
pack drives both sets of features and the ordering question disappears. The
player then loads only the generated pack; keeping the standalone TechPack
applied as well re-creates the conflict.

The submodule is reference material at rest, so nothing here runs unless the
caller asks for it. When TechPack's assets are absent, as in a checkout without
submodules, `available()` is False and the setting has nothing to offer.
"""
import os
import shutil

from scaffold import jsonc
from scaffold import paths
## the submodule, and the staged copy of the part of it a generated pack needs
SUBMODULE = "be_tech_pack"
STAGED = "techpack"


## What a generated pack does about TechPack.
##
## NONE leaves it alone. COMPATIBILITY declares TechPack's animations, render
## controllers and scripts on the armor stand without shipping any of its files,
## so a player who installs TechPack separately gets both instead of Scaffold
## replacing it. FULL folds TechPack's own assets in as well, so the one pack is
## both and nothing else need be installed.
NONE = "none"
COMPATIBILITY = "compatibility"
FULL = "full"
MODES = (NONE, COMPATIBILITY, FULL)


def mode_of(value):
    """Read a mode from whatever a caller passed.

    A boolean is accepted as well as a mode name, because a stored setting or a
    caller written against the older switch carries one: True means the full
    pack, False means none. Anything unrecognised means none.
    """
    if value is True:
        return FULL
    if value is False or value is None:
        return NONE
    text = str(value).strip().lower()
    return text if text in MODES else NONE


def _has_pack(directory):
    return os.path.isfile(
        os.path.join(directory, "entity", "armor_stand.entity.json"))


def _root():
    """Where TechPack's assets are, nearest first.

    The part a generated pack needs, about a megabyte of a seventy megabyte
    submodule, is staged into `scaffold/techpack/` by
    `tools/stage_tech_pack.py` and committed, so that it travels with a pip
    install and a frozen build alike. `paths.data` finds that copy, and a copy
    dropped beside the executable still beats it.

    The submodule itself is the fallback and the source of truth: a checkout
    that has it can be re-staged from it. A checkout with neither is not an
    error. `available()` answers False and the TechPack setting stays on "none".
    """
    staged = paths.data(STAGED)
    if _has_pack(staged):
        return staged
    checkout = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    for directory in list(paths.roots()) + [checkout]:
        candidate = os.path.join(directory, SUBMODULE)
        if _has_pack(candidate):
            return candidate
    return staged


ROOT = _root()
ENTITY = os.path.join(ROOT, "entity", "armor_stand.entity.json")
MANIFEST = os.path.join(ROOT, "manifest.json")

## Copied wholesale into the pack. Scaffold only ever writes entity/,
## models/entity/armor_stand.larger_render.geo.json, textures/entity/ and its
## own render_controllers file, so nothing here lands on top of its output. The
## one file both projects ship, armor_stand.larger_render.geo.json, is byte for
## byte the same asset in both.
ASSET_DIRS = ("animation_controllers", "animations", "materials", "models",
              "particles", "render_controllers", "textures")

## the armor stand is merged rather than copied; the player entity has no
## Scaffold counterpart, so it goes in as it stands
ASSET_FILES = (os.path.join("entity", "player.entity.json"),)


def available():
    """Whether TechPack's assets are present and carry the entity file."""
    return os.path.isfile(ENTITY) and os.path.isdir(ROOT)


def version():
    """TechPack's own version, for the manifest description and the log."""
    if not os.path.isfile(MANIFEST):
        return "unknown"
    try:
        header = jsonc.load(MANIFEST).get("header", {})
        return ".".join(str(n) for n in header.get("version", [])) or "unknown"
    except Exception:
        return "unknown"


def description():
    """TechPack's client entity description, as data."""
    entity = jsonc.load(ENTITY)
    return entity["minecraft:client_entity"]["description"]


def copy_assets(work_dir):
    """Copy TechPack's assets into the pack tree. Returns what was written.

    Scaffold's own files are never overwritten. Any collision is reported
    rather than resolved silently, because a file that differs and gets skipped
    is the sort of thing that shows up much later as a missing texture.
    """
    written, skipped = 0, []
    for folder in ASSET_DIRS:
        source = os.path.join(ROOT, folder)
        if not os.path.isdir(source):
            continue
        for base, _dirs, files in os.walk(source):
            rel = os.path.relpath(base, ROOT)
            target = os.path.join(work_dir, rel)
            os.makedirs(target, exist_ok=True)
            for name in files:
                dest = os.path.join(target, name)
                if os.path.exists(dest):
                    skipped.append(os.path.join(rel, name).replace("\\", "/"))
                    continue
                shutil.copyfile(os.path.join(base, name), dest)
                written += 1

    for rel in ASSET_FILES:
        source = os.path.join(ROOT, rel)
        dest = os.path.join(work_dir, rel)
        if not os.path.isfile(source):
            continue
        if os.path.exists(dest):
            skipped.append(rel.replace("\\", "/"))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(source, dest)
        written += 1

    return written, skipped
