"""Where the tools read Minecraft's own data from.

`pyproject.toml`'s `[tool.scaffold.sources]` names three folders and a file,
from the repository root: `resource_pack`, the game's resource pack, for
textures, models, fonts and names; `behavior_pack`, its behaviour pack, for
block shapes and definitions; `metadata`, Mojang's data on every block and its
states; and `version`, Mojang's record of the game version they are from.
They are Mojang's own `bedrock-samples` submodule today, which is current the
day an update ships; pointing them elsewhere is a change to that table alone.

Not shipped: nothing the program runs reads these.
"""
import os
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_found = None


def _sources():
    global _found
    if _found is None:
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            _found = tomllib.load(f)["tool"]["scaffold"]["sources"]
    return _found


def resource_pack(*parts):
    """A path inside the game's resource pack."""
    return os.path.normpath(os.path.join(ROOT, _sources()["resource_pack"], *parts))


def behavior_pack(*parts):
    """A path inside the game's behaviour pack."""
    return os.path.normpath(os.path.join(ROOT, _sources()["behavior_pack"], *parts))


def metadata(*parts):
    """A path inside Mojang's block metadata."""
    return os.path.normpath(os.path.join(ROOT, _sources()["metadata"], *parts))


def game_version():
    """The Minecraft version the sources are from, as the lookup tables write
    it: 1.26.50.4 is "26.50". None when the version file is not there."""
    import json
    path = os.path.normpath(os.path.join(ROOT, _sources()["version"]))
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        full = json.load(f)["latest"]["version"]
    parts = full.split(".")
    ## Bedrock's release number is 1.<year>.<drop>, and the tables name the
    ## year and the drop
    return "%s.%s" % (parts[1], parts[2])


def missing(path):
    """What to say when a source is not there."""
    return ("%s is not there.\n  git submodule update --init bedrock-samples, or point "
            "[tool.scaffold.sources] in pyproject.toml at a copy" % os.path.relpath(path, ROOT))
