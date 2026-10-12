"""How much of the game's own block list Scaffold can draw.

    python -m tools.checks.game_pack

A block the game declares in its resource pack's `blocks.json` is covered when
`block_definition.json` names a family for it, or when it is an old id a rule in
`block_upgrades.json` turns into a current one as a structure is read.
`tests/test_block_coverage.GamePackTests` holds every block to that, and
`build.py --publish` writes the count as the README's coverage badge.

Not shipped.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scaffold import block_upgrade, jsonc, lookup
from tools import sources


def coverage():
    """(the blocks covered, every block the game declares, the ones left out),
    as sets of ids; None when the game's resource pack is not there."""
    path = sources.resource_pack("blocks.json")
    if not os.path.isfile(path):
        return None
    game = {name for name in jsonc.load(path) if name != "format_version"}
    defined = set(lookup.entries("block_definition.json"))
    translated = set()
    for rule in block_upgrade.rules():
        ids = rule.get("id")
        for name in [ids] if isinstance(ids, str) else (ids or []):
            translated.add(name.replace("minecraft:", ""))
    covered = game & (defined | translated)
    return covered, game, game - covered


def main():
    found = coverage()
    if found is None:
        sys.exit(sources.missing(sources.resource_pack("blocks.json")))
    covered, game, missing = found
    print("%d of %d blocks the game declares, Minecraft %s"
          % (len(covered), len(game), sources.game_version()))
    for name in sorted(missing):
        print("   not covered: %s" % name)


if __name__ == "__main__":
    main()
