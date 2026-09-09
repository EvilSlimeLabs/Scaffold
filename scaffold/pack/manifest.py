import json
import os
import uuid

from scaffold import version
## Fixed namespace, kept for derived_pack_uuids() below.
SCAFFOLD_NAMESPACE = uuid.UUID("a833ff26-366d-4a32-91b4-3b307ff291e4")

## A pack's UUID is derived from everything that went into it: the structure
## files, the name, the icon, the description, the transparency, the offsets
## and the toggles.
##
## Hashing the content is what makes an import behave. Build the same pack
## twice and both carry the same UUID, so the game treats the second as the
## pack it already has. Change any of it and the UUID moves, so the import is
## an addition rather than a clash with an installed pack that differs. The
## pack version cannot carry that difference: it is the Scaffold version, and
## every pack one build produces has it.
##
## Setting this True gives every export a random UUID instead, which makes each
## rebuild a separate entry in the player's list.
RANDOM_UUIDS = False

## Shown in front of the pack's own name in the player's pack list, so every
## pack this program builds groups together there.
NAME_PREFIX = "Scaffold: "

## What Scaffold is, in the one line the pack list shows.
TAGLINE = "block overlay pack"

## Minecraft formatting codes. The pack list renders these, so the credits keep
## the colours each author has carried since they were added.
GREEN = "§a"          # slime green, for EvilSlimeLabs
ITALIC_PURPLE = "§o§5"
ITALIC_BLUE = "§o§9"
RESET = "§r"

MAINTAINER = "EvilSlimeLabs"
PAST_AUTHORS = ((ITALIC_PURPLE, "DrAv0011"),
                (ITALIC_BLUE, "FondUnicycle"),
                (ITALIC_PURPLE, "RavinMaddHatter"))

## A pack description is one field, and Minecraft wraps it; newlines are what
## separate the parts a reader wants to pick out at a glance.
DESCRIPTION_LIMIT = 25


def derived_pack_uuids(pack_name):
    """UUIDs derived from the pack name, the same for every build of it.

    Derived from the name the user typed, never from the displayed name: the
    "Scaffold: " prefix is presentation, and folding it in would have made
    every pack built by an older Scaffold look like a different pack.
    """
    return (str(uuid.uuid5(SCAFFOLD_NAMESPACE, pack_name)),
            str(uuid.uuid5(SCAFFOLD_NAMESPACE, pack_name + "/resources")))


def content_uuids(fingerprint):
    """UUIDs derived from everything that went into the pack."""
    return (str(uuid.uuid5(SCAFFOLD_NAMESPACE, "content:" + fingerprint)),
            str(uuid.uuid5(SCAFFOLD_NAMESPACE, "content:" + fingerprint + "/resources")))


def pack_uuids(pack_name, fingerprint=None):
    """The header and module UUIDs for this build of a pack."""
    if fingerprint:
        return content_uuids(fingerprint)
    if RANDOM_UUIDS:
        return (str(uuid.uuid4()), str(uuid.uuid4()))
    return derived_pack_uuids(pack_name)


def display_name(pack_name):
    """What the player sees in the pack list."""
    if pack_name.startswith(NAME_PREFIX):
        return pack_name
    return NAME_PREFIX + pack_name


def credits_line():
    """Who built the program, in the colours each author is known by."""
    names = [GREEN + MAINTAINER + RESET]
    names += [colour + name + RESET for colour, name in PAST_AUTHORS]
    return "Scaffold {}, {}, by {}".format(version.read(), TAGLINE, ", ".join(names))


def build_description(nameTags=(), user_text="", tech_pack_version=None):
    """The pack description, one part per line.

    Ordered by how much it belongs to the person who built the pack: their own
    note first, then what is in the pack, then what made it.
    """
    lines = []
    if user_text:
        lines.append(user_text.strip()[:DESCRIPTION_LIMIT])
    if nameTags:
        lines.append("Nametags: {}".format(", ".join(nameTags)))
    if tech_pack_version:
        lines.append("TechPack {} included".format(tech_pack_version))
    lines.append(credits_line())
    return "\n".join(lines)


def export(work_dir, pack_name, nameTags=(), user_text="", tech_pack_version=None,
           fingerprint=None):
    ## work_dir is wherever the tree happens to be assembled; the name is only
    ## what the player reads, and the fingerprint is what identifies the pack
    tempname = pack_name.split("/")[-1]
    header_uuid, module_uuid = pack_uuids(tempname, fingerprint)
    ## the generated pack carries the version of the Scaffold that built it, so
    ## a rebuild after an upgrade reads as an update rather than a sidegrade
    pack_version = version.as_tuple()
    manifest = {
        "format_version": 2,
        "header": {
            "name": display_name(tempname),
            "description": build_description(nameTags, user_text, tech_pack_version),
            "uuid": header_uuid,
            "version": pack_version,
            "min_engine_version": [
                1,
                16,
                0
            ]
        },
        "modules": [
            {
                "type": "resources",
                "uuid": module_uuid,
                "version": pack_version
            }
        ]
    }

    path_to_ani = "{}/manifest.json".format(work_dir)
    os.makedirs(os.path.dirname(path_to_ani), exist_ok=True)

    with open(path_to_ani, "w+", encoding="utf-8") as json_file:
        json.dump(manifest, json_file, indent=2, ensure_ascii=False)
