# Contributing
Thank you for being interested in contributing. Scaffold is a program that can be used in several ways and there are a few things you should understand before Contributing. 

## Use Cases

### Desktop Application
Scaffold was originally only a desktop application, this comes with some baggage and some down sides. But support for using it with the gui needs to remain in place. To make this easier, the application was pulled out of the gui: it lives in `scaffold/core.py`, the window is `scaffold/ui/`, and the entry points are thin wrappers around both.

### Hosted use
`scaffold/core.py` is the API any front end uses, including a hosted one. A service that runs Scaffold for other people belongs in its own project that imports this one; nothing here should know about a queue, a bucket, a bot or a user account. An earlier attempt at that lived in this repository as `lambda_function.py` and has been removed.

Two rules keep the core usable that way, and a pull request that breaks either cannot be merged:

- **Do not write outside the working directory or the caller's chosen output path.** Serverless hosts give you a read-only file system with only `/tmp` writable. The pack tree is assembled in a temporary directory, and the only things written where the caller asked are the `.mcpack` and its side reports.
- **Everything the core produces must be available as data, not only as a file.** `get_material_list()`, `get_block_lists()`, `get_nametags()` and `get_skipped(write_file=False)` exist because a service wants values, not text files it then has to read back.

#### Scaffold CLI
The CLI was added by contributors that wanted to make their own web services. This is allowed. Scaffold is MIT licensed and anyone can do anything with Scaffold.

It lives in `scaffold/cli/` now, and **nothing in there may import `scaffold/ui/`**. That rule is what lets `Scaffold-cli.exe` be built without the interface in it at all; `build.py` compiles it with Nuitka's `--nofollow-import-to=scaffold.ui`, so the interface stays out of that executable even if an import of it creeps back into the command line. Anything both the window and the command line need, such as the settings and the language tables, belongs at the top of the package instead, beside `core.py`.

## Blocks Definitions
Minecraft is a giant mess when it comes to naming, versioning, and block definitions, and structures saved years ago still carry the old names. Blocks are defined in two places: `scaffold/Vanilla_Resource_Pack/`, which holds the textures and the texture declarations the way the game's own resource pack does, and `scaffold/lookups/`, which holds every block's geometry and the rules that choose its form. `docs/Lookup Format 2.md` describes the tables and `docs/Editing Blocks.md` how to change one.

### Old block names
The tables describe the blocks the current game has, and nothing else. A structure saved under an old name is translated as it is read, by the rules in `scaffold/lookups/block_upgrades.json`. When Mojang renames a block or a state, add a rule there rather than keeping the old name in a table, and check it with `python -m tools.checks.upgrades --schema <a clone of pmmp/BedrockBlockUpgradeSchema>`.

### Editing Vanilla_Resource_Pack
Some of its textures are deliberately not vanilla, such as pre-tinted grass and leaves, so do not copy the game's files over it by hand. `python -m tools.vendor.vanilla_pack` reports how it differs from the game's own pack and knows which files to leave alone; read the report, then run it again with `--apply`.

### Adding Geometry
In 2025 when Vibrant Visuals was added, the CPU cost of rendering a bone became 50-100x more expensive. For that reason, when making new geometries, we need to be respectful of cube count. Excessive use of cubes will cause excessive lag.

A family that carries three or more cubes should also have a simplified form, so that a pack built with **Low Geometry** has something cheaper to draw. `tools/blocks/simplify.py` generates them from the detailed shapes; re-run it after changing one.

`be_tech_pack` is a git submodule and far too large to be package data, so the megabyte of it a generated pack needs is staged into `scaffold/techpack/` and committed. **After updating the submodule, run `python -m tools.vendor.tech_pack`**, or a release quietly ships the old assets. `tests/test_tech_pack.py` fails when the two have drifted.

### Adding Blocks to all_blocks world.
When adding blocks it is helpful to add them to the all_blocks world so they can at least get tested each update. This helps when we need to do a big refactor. Simply add the block to the world where it makes the most sense. Add every block state you can to help in the future. Then remove all packs. (may need to manually removed them if they were attached to the world) and export the world and add it back into the git repo.

Not everything a block looks like is in its states. A copper golem statue keeps its pose in the block entity beside it, so placing four statues in four poses is worth doing even though they share one palette entry, because the exported structure carries the difference in `block_position_data`. `test_structures/All Blocks World/problems.mcstructure` is the file for blocks that are known to still be drawn wrong.

# Recognition
In the beginning I added the first 2 people who contributed to the manifest.json of every pack. If you stick around and help for more than a few months, I may choose to do that in the future. If you fix things you will get credit in the release notes and likely in a video covering that release.
