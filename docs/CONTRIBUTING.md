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

It lives in `scaffold/cli/` now, and **nothing in there may import `scaffold/ui/`**. That rule is what lets `Scaffold-cli.exe` be built without the interface in it at all; `scaffold_cli.spec` excludes `scaffold.ui` outright, so a build fails rather than quietly growing if the interface creeps back into the command line's imports. Anything both the window and the command line need, such as the settings and the language tables, belongs at the top of the package instead, beside `core.py`.

## Blocks Definitions
Minecraft is a giant mess when it comes to naming, versioning, and block definitions. But because Scaffold dates back to 2020 and posted files still reference old block names, we need to be careful when updating blocks. In 2020 an effort was made to remove all hard coded block definitions. At this point, blocks are defined in 2 locations. Vanilla_Resource_pack, where the textures and texture locations are saved in a similar way to the default texture pack from Minecraft, and in lookups, where all the block geometry and nbt is defined.

### Editing Vanilla_Resource_pack 
When adding new blocks, do not remove old block definitions. Due to the project Mojang ran between 2020 and 2024 renaming all the blocks, old structures will be broken if the terrain_texture.json and blocks.json is simply copied from the new version. Instead, the old and new terrain textures must be merged. This is a bit painful, but it is what it is.

### Adding Geometry
In 2025 when Vibrant Visuals was added, the CPU cost of rendering a bone became 50-100x more expensive. For that reason, when making new geometries, we need to be respectful of cube count. Excessive use of cubes will cause excessive lag.

A family that carries three or more cubes should also have a simplified form, so that a pack built with **Low Geometry** has something cheaper to draw. `tools/blocks/simplify.py` generates them from the detailed shapes; re-run it after changing one.

`be_tech_pack` is a git submodule and far too large to be package data, so the megabyte of it a generated pack needs is staged into `scaffold/techpack/` and committed. **After updating the submodule, run `python -m tools.vendor.tech_pack`**, or a release quietly ships the old assets. `tests/test_tech_pack.py` fails when the two have drifted.

### Adding Blocks to all_blocks world.
When adding blocks it is helpful to add them to the all_blocks world so they can at least get tested each update. This helps when we need to do a big refactor. Simply add the block to the world where it makes the most sense. Add every block state you can to help in the future. Then remove all packs. (may need to manually removed them if they were attached to the world) and export the world and add it back into the git repo.

Not everything a block looks like is in its states. A copper golem statue keeps its pose in the block entity beside it, so placing four statues in four poses is worth doing even though they share one palette entry, because the exported structure carries the difference in `block_position_data`. `test_structures/All Blocks World/problems.mcstructure` is the file for blocks that are known to still be drawn wrong.

# Recognition
In the beginning I added the first 2 people who contributed to the manifest.json of every pack. If you stick around and help for more than a few months, I may choose to do that in the future. If you fix things you will get credit in the release notes and likely in a video covering that release.
