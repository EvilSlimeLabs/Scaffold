"""Bring Vanilla_Resource_Pack/ up to date from the community submodule.

    python -m tools.vendor.vanilla_pack                    report, change nothing
    python -m tools.vendor.vanilla_pack --apply            take the stale textures
    python -m tools.vendor.vanilla_pack --add-block oak_shelf stone_slab
    python -m tools.vendor.vanilla_pack --add-block ... --apply

Vanilla_Resource_Pack/ is a trimmed vanilla pack that has been hand-merged for
years, and some of its textures are deliberately not vanilla any more. Copying
the submodule over the top destroys that work, which is why this script
classifies every differing texture before it moves anything.

A texture is KEPT when any of these holds:

  * the community ships it greyscale and this pack's copy is not. Vanilla tints
    those at runtime from the biome colormap, and a ghost block cannot run the
    colormap, so Scaffold bakes the tint in
  * this pack's copy is more opaque. Some textures are solid on purpose so the
    ghost survives the alpha pass that the transparency slider applies
  * a commit outside the bulk vanilla imports touched it, meaning somebody
    edited it by hand and git remembers why

Everything else that differs in pixels is stale vanilla art and is safe to take.
Textures whose pixels match and differ only in PNG encoding are left alone; there
is nothing to gain from the churn.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

## jsonc lives in the package rather than here: the program reads Bedrock's
## permissive JSON at runtime too, so it is shipped code, not a tool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scaffold import jsonc
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OURS = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack")
COMM = os.path.join(ROOT, "CommunityVanillaResourcePack")
OUR_BLOCKS = os.path.join(OURS, "textures", "blocks")
COMM_BLOCKS = os.path.join(COMM, "textures", "blocks")

## Commits that imported or reverted a whole vanilla pack. A texture touched
## only by these is vanilla-as-shipped and may be replaced; anything else in its
## history is a deliberate edit.
BULK_IMPORT_COMMITS = {"37129f1", "a2c33d7", "47ffecd", "634b9cb"}

## Textures the greyscale and opacity tests do not catch but which are still
## deliberate edits to keep.
ALWAYS_KEEP = {
    "grass_side.png", "grass_side_snowed.png", "grass_top.png", "none.png",
}

## RTX and deferred-rendering companions. The generator never reads them and
## they would double the size of the pack.
SKIP_SUFFIXES = ("_mers.tga", "_normal.tga", "_heightmap.tga", ".texture_set.json")


def relpaths(root):
    out = {}
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            out[os.path.relpath(path, root).replace("\\", "/")] = path
    return out


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _numpy_image(path):
    from PIL import Image
    import numpy
    return numpy.array(Image.open(path).convert("RGBA")).astype(int)


def is_greyscale(pixels):
    rgb = pixels[..., :3]
    return bool((rgb[..., 0] == rgb[..., 1]).all() and (rgb[..., 1] == rgb[..., 2]).all())


def git_subjects():
    out = subprocess.run(["git", "log", "--format=%h|%s"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return dict(line.split("|", 1) for line in out.strip().split("\n") if "|" in line)


def hand_edit_commits(rel, subjects):
    out = subprocess.run(
        ["git", "log", "--format=%h", "--", "Vanilla_Resource_Pack/textures/blocks/" + rel],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    return [(c, subjects.get(c, "?")) for c in out if c not in BULK_IMPORT_COMMITS]


def classify_textures():
    """-> (keep, stale, encoding_only) lists of (relpath, reason)."""
    import numpy

    ours, theirs = relpaths(OUR_BLOCKS), relpaths(COMM_BLOCKS)
    subjects = git_subjects()
    keep, stale, encoding = [], [], []

    for rel in sorted(ours):
        if rel not in theirs or sha(ours[rel]) == sha(theirs[rel]):
            continue
        if rel in ALWAYS_KEEP:
            keep.append((rel, "on the always-keep list"))
            continue
        try:
            a, b = _numpy_image(ours[rel]), _numpy_image(theirs[rel])
        except Exception as exc:
            keep.append((rel, "could not be read (%s)" % exc))
            continue

        if a.shape == b.shape and numpy.array_equal(a, b):
            encoding.append((rel, "identical pixels"))
            continue

        reasons = []
        if a.shape == b.shape:
            if is_greyscale(b) and not is_greyscale(a):
                reasons.append("community is greyscale, ours is pre-tinted")
            if a[..., 3].mean() > b[..., 3].mean() + 1:
                reasons.append("ours is more opaque (%.0f vs %.0f)"
                               % (a[..., 3].mean(), b[..., 3].mean()))
        else:
            reasons.append("dimensions differ (%s vs %s)" % (a.shape[1::-1], b.shape[1::-1]))
            ## a frame-count change is a vanilla flipbook update, not a hand edit
            reasons = []
        for commit, subject in hand_edit_commits(rel, subjects):
            reasons.append("hand edited in %s (%s)" % (commit, subject[:44]))

        (keep if reasons else stale).append((rel, "; ".join(reasons) or "stale vanilla art"))

    return keep, stale, encoding


def missing_textures():
    """Textures the community pack has and this one does not, RTX aside."""
    ours, theirs = relpaths(OUR_BLOCKS), relpaths(COMM_BLOCKS)
    return sorted(r for r in theirs
                  if r not in ours and not r.endswith(SKIP_SUFFIXES))


# --- adding blocks -------------------------------------------------------

def texture_names(blocks, block):
    layout = blocks.get(block, {}).get("textures")
    if isinstance(layout, str):
        return [layout]
    if isinstance(layout, dict):
        return sorted({v for v in layout.values() if isinstance(v, str)})
    return []


def plan_blocks(names):
    """What it would take to support `names`: entries and files to copy in."""
    comm_blocks = jsonc.load(os.path.join(COMM, "blocks.json"))
    comm_terrain = jsonc.load(os.path.join(COMM, "textures/terrain_texture.json"))["texture_data"]
    our_blocks = jsonc.load(os.path.join(OURS, "blocks.json"))
    our_terrain = jsonc.load(os.path.join(OURS, "textures/terrain_texture.json"))["texture_data"]
    our_files = set()
    for dirpath, _, filenames in os.walk(os.path.join(OURS, "textures")):
        for filename in filenames:
            rel = os.path.relpath(os.path.join(dirpath, filename), OURS).replace("\\", "/")
            our_files.add(os.path.splitext(rel)[0])

    plan = {"blocks": {}, "terrain": {}, "files": [], "unknown": []}
    for name in names:
        if name not in comm_blocks:
            plan["unknown"].append(name)
            continue
        if name not in our_blocks:
            plan["blocks"][name] = comm_blocks[name]
        for short in texture_names(comm_blocks, name):
            if short not in comm_terrain:
                plan["unknown"].append("%s -> terrain_texture has no '%s'" % (name, short))
                continue
            if short not in our_terrain:
                plan["terrain"][short] = comm_terrain[short]
            entry = comm_terrain[short]["textures"]
            for item in (entry if isinstance(entry, list) else [entry]):
                path = item["path"] if isinstance(item, dict) else item
                if path not in our_files and path not in plan["files"]:
                    plan["files"].append(path)
    return plan


def apply_blocks(plan):
    import json
    added = []
    if plan["blocks"]:
        path = os.path.join(OURS, "blocks.json")
        data = jsonc.load(path)
        data.update(plan["blocks"])
        with open(path, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, indent=2)
        added.append("%d blocks.json entries" % len(plan["blocks"]))
    if plan["terrain"]:
        path = os.path.join(OURS, "textures/terrain_texture.json")
        data = jsonc.load(path)
        data["texture_data"].update(plan["terrain"])
        with open(path, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, indent=2)
        added.append("%d terrain_texture entries" % len(plan["terrain"]))
    copied = 0
    for rel in plan["files"]:
        for ext in (".png", ".tga", ".jpg"):
            source = os.path.join(COMM, rel + ext)
            if os.path.isfile(source):
                target = os.path.join(OURS, rel + ext)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(source, target)
                copied += 1
                break
        else:
            print("   no file found in the submodule for %s" % rel)
    if copied:
        added.append("%d texture files" % copied)
    return added


# --- reporting -----------------------------------------------------------

def show(title, rows, limit=None):
    print("\n=== %s (%d) ===" % (title, len(rows)))
    shown = rows if limit is None else rows[:limit]
    for rel, why in shown:
        print("   %-46s %s" % (rel, why))
    if limit is not None and len(rows) > limit:
        print("   ... and %d more" % (len(rows) - limit))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="write the changes instead of only reporting them")
    parser.add_argument("--add-block", nargs="+", metavar="BLOCK", default=[],
                        help="also pull in the blocks.json, terrain_texture and texture "
                             "files for these block ids")
    parser.add_argument("--quiet-keep", action="store_true",
                        help="summarise the kept textures instead of listing them")
    args = parser.parse_args()

    if not os.path.isdir(COMM_BLOCKS):
        sys.exit("CommunityVanillaResourcePack is not checked out.\n"
                 "  git submodule update --init CommunityVanillaResourcePack")

    keep, stale, encoding = classify_textures()
    if args.quiet_keep:
        print("\n=== KEEP (%d) === deliberate Scaffold edits, left alone" % len(keep))
    else:
        show("KEEP - deliberate Scaffold edits", keep)
    print("\n=== ENCODING ONLY (%d) === same pixels, left alone" % len(encoding))
    show("STALE - vanilla art has moved on", stale)

    missing = missing_textures()
    print("\n=== IN THE SUBMODULE, NOT HERE (%d) ===" % len(missing))
    print("   not pulled in automatically; use --add-block for the blocks you want")

    plan = None
    if args.add_block:
        plan = plan_blocks(args.add_block)
        print("\n=== ADD BLOCKS ===")
        print("   blocks.json entries:     %d" % len(plan["blocks"]))
        print("   terrain_texture entries: %d" % len(plan["terrain"]))
        print("   texture files:           %d" % len(plan["files"]))
        for problem in plan["unknown"]:
            print("   unresolved: %s" % problem)

    if not args.apply:
        print("\nNothing written. Re-run with --apply to take the %d stale textures%s."
              % (len(stale), " and the blocks above" if plan else ""))
        return

    ours, theirs = relpaths(OUR_BLOCKS), relpaths(COMM_BLOCKS)
    for rel, _ in stale:
        shutil.copyfile(theirs[rel], ours[rel])
    print("\ncopied %d stale textures" % len(stale))
    if plan:
        for line in apply_blocks(plan):
            print("added %s" % line)
    print("\nRun tools/checks/blocks.py next to confirm everything still resolves.")


if __name__ == "__main__":
    main()
