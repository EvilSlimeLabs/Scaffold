# Working on Scaffold

Standing rules and the project information worth having before touching anything.

---

## The project

**Scaffold** — Previously called Structura, and inspired by Litematica. Scaffold is a Python desktop program that turns a `.mcstructure` file into a Bedrock resource pack (`.mcpack`). The pack replaces the vanilla armor stand client entity with one that renders when off screen and carries every block of your structure as a bone in its model, drawn as semi-transparent "ghost blocks" so you can see where the real blocks go.

There is no behaviour pack and no script API anywhere in this project. Whatever the generated pack does, it does with geometry, render controllers, animations and textures.

## Release and distribution

The repository is public on GitHub. Releases are built locally with `python build.py`, not by CI. `python build.py --publish` signs the build into the update server, pushes both branches, and makes the GitHub release with `gh`: the tag is the bare version, the text is the version's `CHANGELOG.md` section, and the files are the zip, `Scaffold.exe`, `Scaffold-cli.exe` and `SHA256SUMS.txt`, each executable on its own being the whole program. It checks before it compiles anything that nothing is uncommitted in the repository or in `pages/`, and that `gh` is installed, signed in, sees the repository, and has no release of that version yet. **It does not commit for you**: a release is made from what is committed, and a commit made by `git add -A` on the way takes whatever is lying in the tree.

**There is exactly one workflow, `.github/workflows/pypi.yml`, and it publishes the Python package.** Publishing the GitHub release is what fires it: it builds the wheel and the source archive and uploads them to PyPI as `mcpe-scaffold`, through PyPI's trusted publishing, so no token exists anywhere. PyPI's publisher for the project names that file and the repository's `pypi` environment. **Do not add any other build or release workflow.** The executables are compiled and signed here with keys that never leave this machine, and a copy built elsewhere would not be the build the updater vouches for. **Build the package with `pyproject-build`, never `python -m build`**: run from the repository, the second imports this project's own `build.py`. A version on PyPI can be neither replaced nor reused.

**The window is Windows only.** The release is built on a Windows machine, so `Scaffold.exe` and `Scaffold-cli.exe` are the only executables that exist. macOS and Linux get the command line through `pip install mcpe-scaffold`. Do not write documentation promising a Linux or macOS build; the README claimed one for a long time and it has never been produced.

**`dist/SHA256SUMS.txt` goes with the binaries**, and the release step attaches it. It is what somebody who downloaded the zip in a browser checks against. The program's own updates do not read it any more; they check signatures instead.

**Building a release needs a C compiler.** Nuitka compiles the program to C, so `build.py` asks for `--zig`, which Nuitka downloads and keeps up to date itself. Visual Studio 2022 works if it is installed; MinGW64 does not, because Nuitka stopped supporting it at Python 3.13. Nothing is needed to *run* Scaffold from a checkout.

**The program updates itself over TUF, and a release must be signed.** `scaffold/updates.py` is a `tufup` client. It fetches signed metadata from `https://evilslimelabs.github.io/Scaffold/metadata/`, and the archives from `targets/` beside it, and will not install anything the metadata does not vouch for. `python build.py --publish` is what signs a build in; `--init-trust` creates the keys, once.

**`--unpublish <version>` takes a release back off the server**, and builds nothing. It names the version rather than assuming it, because this is a release going away, and it refuses anything but the newest: tufup removes the latest bundle and only the latest, so pulling one out from under a newer one would leave a client holding a patch against an archive that is gone. **It is not a recall.** Anyone who already updated has the build on disk and nothing here reaches them; if the release is harmful rather than merely wrong, publish a newer one that supersedes it. It also leaves the GitHub release and the PyPI package alone: the release is somebody's download and the update repository knows nothing about it, so the browser download still serves the withdrawn build until that release is edited too, and PyPI cannot take a version back at all. Unlike `--publish` it commits only `gh-pages`, since it has built nothing that belongs on `master`.

**The private keys live in `~/.scaffold-keys` and must never be committed.** Anyone holding the targets key can sign a release every copy of Scaffold in the world will install. `scaffold/trust/root.json` is the public half and *does* ship, compiled into the executable, because it is the one piece of metadata an update cannot fetch.

That whole feature rests on the repository being **public**, because the metadata and the archives are fetched without credentials, and GitHub Pages on a private repository is a paid feature besides. While it is private every check comes back as "up to date", quietly, which is the same answer as no network.

**GitHub Pages serves it from an orphan `gh-pages` branch, and `pages/` is a worktree on it.** `python build.py --init-pages` makes that worktree once: the branch shares no history with `master`, because the site is built artifacts and has no business carrying the source's. In the repository's **Settings -> Pages**, set **Source** to *Deploy from a branch* and **Branch** to *gh-pages* with folder */ (root)*, which serves `pages/metadata/` and `pages/targets/` at the address `scaffold/updates.py` reads. A push is live in under a minute and there is nothing to approve.

**`.nojekyll` and `index.html` are written by the build**, by `pages_scaffolding()`, so they are there whichever command made the tree. Pages runs Jekyll over a branch unless that empty file says not to, and Jekyll drops anything whose name begins with an underscore; nothing tufup writes does today, so it is insurance rather than a fix, and it skips the build besides. The index exists because the address is a real one somebody may open, and without it the root of the site is a 404 that looks like the update server is down.

---

## Layout

Everything importable is one package. `from scaffold import Scaffold` is the whole API, and a service that wants to run Scaffold vendors one directory rather than fourteen paths.

Inside it, the pieces are grouped by what they are for: `pack/` turns a structure into a pack, `cli/` is the command line, `ui/` draws the window. **None of them import each other.** What more than one of them needs — the settings, the paths, the language tables — sits beside them at the top of the package, and so does `core.py`, which is what drives all three.

**`cli/` must not reach into `ui/`.** That is what lets the command line build leave the interface out, and `build.py` passes Nuitka `--nofollow-import-to=scaffold.ui` for that build, so it comes out small rather than quietly growing by six megabytes if it ever does. The language tables sit outside `ui/` for the same reason: `settings` needs them, and both sides need `settings`.

```
build.py                   local release build

scaffold/                  everything importable, and everything it reads
  __init__.py              exports Scaffold; never mentions the window
  __main__.py              entry point: dual use -- arguments build, none opens
  app.py                   the dual use decision, so __init__ stays clean
  core.py                  the pipeline: structure in, pack folder out
  settings.py              settings, and the strings both sides label things with
  lang_parse.py            reads lookups/lang/, one file per language
  system_locale.py         what language the desktop is set to, for a first launch
  updates.py               the tufup client: whether a signed release is out
  paths.py                 where data lives, in a checkout and inside the bundle
  version.py               reads the version out of pyproject.toml
  jsonc.py                 reads Bedrock's permissive JSON; shipped, not a tool
  block_upgrade.py         old block ids and states as the current game names them, as a structure is read
  block_geometry.py        reads and writes the format 2 geometry tables, and chooses a block's form from its states
  marks.py                 what a block entity says that is drawn beside the block: a container's count, a crafter's locked slots
  dust.py                  which way redstone dust runs, from the blocks round it
  lookup.py                the lookup tables' common header, and reading or writing one

  cli/                     the command line
    __main__.py            entry point: the command line alone, no window
    arguments.py           what the program accepts, for both entry points
    commands.py            building a pack
    console.py             output from a build frozen without a console

  pack/                    building a pack
    structure_reader.py    .mcstructure NBT parsing, and block entity data
    armor_stand_geo_class.py  block -> geometry and UV; the biggest and trickiest
    armor_stand_class.py   the armor_stand client entity
    animation_class.py     layer pose animations
    render_controller_class.py / big_render_controller.py
    manifest.py            the generated pack's manifest
    tech_pack.py           folds the TechPack submodule into a generated pack

  ui/                      the window
    scaffold_gui.py        the window, on CustomTkinter
    ui_icons.py            the drawn interface glyphs and the pack icon control
    ui_fonts.py            registers the bundled faces, one per language
    lang_icons.py          the language picker's code badges

  lookups/                 the lookup tables this project owns
    lang/                  one .lang file per language, named for its locale
    schema/                a JSON schema per geometry table
  trust/                   root.json, the TUF root an update is checked against
  Vanilla_Resource_Pack/   trimmed vanilla pack textures are read from
  fonts/                   the three bundled faces, with their licences
  images/                  the two pictures the running program opens
  techpack/                TechPack's assets, staged from the submodule
  tweakpacks/              the Bedrock Tweaks and Clearer Redstone options, staged, with their licences

art/                       source art the icons are generated from, and readme_header.png, which the README opens with; nothing here goes into a build
tools/                     the scripts that build the data, and the ones that check it; nothing here ships, and every one is run from the repository root as a module
  generate.py              runs every generator, in the order they need
  find.py                  find a block, or a texture, by any of its names; `KINDS` is where another search goes
  render.py                shorthand for checks/render.py, which is the long name for the thing done most
  sources.py               where the game's own packs are, from pyproject.toml
  blocks/                  the block lookup tables
    geometry.py            Cube, build, spun, unwrap, on_sheet
    tables.py              edit one family, leave the rest byte for byte
    java.py                reads a Java block model into a format 2 form: Java's elements, multipart turns and uvlock
    java_models.py         the Java models it reads, generated, not hand edited
    models.py              the families drawn from Java's models: plants, joins, stairs, buttons, torches, bells, pistons and more
    vanilla.py             blocks drawn the way Minecraft draws them: furnaces, portals, cakes, candles, copper bulbs, water
    mounted.py             signs, doors, campfires, pots, brewing
    growing.py             crops, compost, coral, petals
    crossed.py             fire, dripstone, sulfur spikes
    plants.py              the crossed plants and the sunflower
    furniture.py           beds, lecterns, conduits
    heads.py               the mob heads
    containers.py          the shulker boxes
    banners.py             standing and wall banners
    bookshelf.py           the sixty-four filled states
    chests.py              the chest, single and either half of a double
    dust.py                redstone dust's joined forms
    redstone.py            the families each Clearer Redstone option draws with, and its icon
    statues.py             the copper golem's four poses
    faces.py               a texture per cube, per face
    entities.py            the entities drawn as blocks, so far the cushion
    names.py               fills the block list's names from Mojang's own en_US.lang
    simplify.py            the low geometry forms
  textures/                banners, beds, string, cauldron, water, chests, shulkers, foliage, item_icons, wax, filled, dust_line, end_portal, low, tweak_tints
  app/                     icon.py, fonts.py, languages.py, transforms.py, screenshots.py
  vendor/                  tech_pack.py, vanilla_pack.py, tweaks.py -- staging submodules; redstone.py -- staging Redstone Tweaks
  checks/                  blocks, coverage, render, generators, api, speed, upgrades, compass, gallery, worldfile, game_pack;
                           trials, water_trials, fill_trials, tweak_blocks, tweak_variants -- what the test worlds draw
  export/                  structura.py -- Scaffold's tables in the shape Structura 1.7 reads;
                           handoff.py -- that, the format 2 tables and the guide, as one folder for Structura's developer;
                           From Structura 1.7.md -- what is particular to Structura, shipped only in the handoff
tests/                     unittest suite
test_structures/           .mcstructure files to generate against
docs/                      user-facing documentation: Block Notes.md, what to read before touching a block;
                           Editing Blocks.md; Lookup Format 2.md, the tables' specification; ROADMAP.md, what is planned
redstone_tweaks/           submodule: the archival mirror of Redstone Tweaks, which Clearer Redstone is converted from
.github/workflows/         pypi.yml, the one workflow
```

`bedrock-samples/`, `bedrock_tweaks/`, `be_tech_pack/` and `redstone_tweaks/` are git submodules and none is read at run time. `bedrock-samples/` is Mojang's own: the game's resource pack, its behaviour pack and its block metadata, current the day an update ships. **The tools find it through `pyproject.toml`'s `[tool.scaffold.sources]`**, a table of three folders read by `tools/sources.py`: `resource_pack`, `behavior_pack` and `metadata`. Pointing them at another copy is a change to that table alone; nothing names the submodule's path but it. TechPack is the source `tools/vendor/tech_pack.py` copies from — `scaffold/techpack/` is what the program actually reads.

---

## Two builds, one command line

`scaffold/__main__.py` is dual use: give it a structure and a pack name and it builds one in the terminal, give it nothing and the window opens. `cli/__main__.py` is the same command line with the window left out of the bundle. Neither holds any argument parsing of its own -- both call `cli.main`, which returns `cli.NOTHING_ASKED` when there was nothing to act on and lets the entry point decide what that means.

**The command line writes where it was run.** `--output` wins when it is given; without it a pack lands in the current working directory, not in the window's remembered output folder. A command line is expected to put what it makes where it was invoked, and a script should not have to know where somebody's Documents are. The window is the other way round on purpose: somebody clicking a button wants the folder they chose last time.

**`--settings FILE` fills in what the command line leaves out.** A JSON object by the flags' own names, or the window's `.scaffold`, read by `arguments.from_file`: its `transparency` becomes an opacity, `output_dir` the output and its tweak switch and `tweaks_on` the tweak list. A flag spelled on the command line wins over the file, a path in the file is read from the file's folder, and a key nothing reads is an error rather than a typo that silently does nothing.

A build frozen without a console has nowhere to print on Windows, which would make the dual use build silent from a terminal. `cli/console.py` borrows the console of whatever launched it, and does so **before the arguments are read**, so that `--help` and argument errors land somewhere. Double-clicked there is no console to borrow, and nothing is printed.

## The window

`ui/scaffold_gui.py` is the whole interface; `scaffold/__main__.py` is the command line and one call into it. They share `settings.py` so neither has to import the other.

It is built on **CustomTkinter**, which is tkinter underneath -- so the frozen build stays roughly the size it was -- but draws modern widgets and can follow the desktop's light or dark setting. `darkdetect` is what answers that question; where it cannot (Linux), the theme falls back to dark rather than guessing.

There is **no basic and advanced split any more**. One screen: structures on the left, everything describing the pack on the right, status along the bottom. A single structure needs no name tag; the second one added makes tags required, and the window says so as it is typed.

Things worth knowing before changing it:

- **`Field` is the composite entry.** CustomTkinter cannot inset an entry's text, and a picture placed over one covers the characters rather than moving them. So `Field` owns the border and holds a borderless entry beside a mark -- the name tag's item texture, an axis letter. Anything that needs something *inside* a field goes through it.
- **The name tag fields are a fixed width**, not a weighted column. Rows have different file names, and a proportional field made every row a different length.
- **The window opens with no structures.** An empty row is something the user has to notice and delete.
- **A CustomTkinter entry bound to a `textvariable` never shows its placeholder.** The variable is what makes validation live, so every hint that used to be placeholder text -- optional/required on a name tag, the pack name label -- is a real label instead. Do not reintroduce `placeholder_text` on a field that has a variable; it will silently never appear.
- **A dialog is placed before it is shown, by `present`.** A toplevel is mapped wherever the window manager first puts it, so centring it afterwards draws it once in a corner and again in the middle. All four dialogs did that on a timer; the larger the dialog the more it showed, and the Tweaks grid showed it plainly. `present` withdraws the dialog, lays it out and measures it where nobody can see it, places it, and only then deiconifies. The order is fixed: a withdrawn window has no size to be centred by until it has been laid out, and `grab_set` on one the server has not mapped raises, so it is retried on the next idle rather than leaving the dialog un-modal. **Anything new that opens a dialog calls this rather than centring it itself.**
- **A `CTkToplevel` gets Tk's default icon** unless told otherwise, and it has to be told after the window exists. `apply_icon()` does it on a delay, and the main window repeats it because CustomTkinter resets the icon while it finishes setting up.
- **The build runs on a worker thread** and talks back through a queue that the main thread drains in `after()`. Tk is not thread safe; nothing off the main thread may touch a widget.
- **The status line is always saying something.** A finished build's message is `sticky` so re-validating does not wipe the one line that says it worked.
- **Nothing is written over without being asked about, and the asking happens before the build runs.** `settle_collisions` compares `core.outputs` against the output folder and offers overwrite, a suggested free name, or stopping; a rename is checked again, because the name typed in may collide too. Doing this at the end would mean running a build nobody wanted.
- **A write that fails is a question, not a lost build.** The worker hands `core.set_retry` a callback that puts the question on the same queue every other message uses and waits on a queue of its own; `_drain_events` opens the dialog on the main thread. Nothing else is drained while it is up, which is what the build wants. A cancel sets `App.cancelled`, so the error the write then raises is reported as a choice rather than as a fault.
- **Big build mode borrows the offset fields and the name tags.** Their values are stashed and handed back when it is switched off, so flipping it twice leaves the window exactly as it was. Anything else that mode takes over has to do the same.
- **The window does not resize, and nothing scrolls.** `WINDOW_TALL` is a constant, so a row added to the settings column pushes whatever is under it down rather than making room, and the Make button is last. Tk places a widget that no longer fits and the frame simply clips it, so nothing complains: adding the Tweaks row put the button that builds a pack twenty-three pixels off the bottom of its panel. `tests/test_interface.WindowFitsTests` lays the real window out and fails on it, because what a row costs depends on the fonts and the scale of the machine. **Raise `WINDOW_TALL` in the same change that adds the row.**

- **Why it does not resize.** CustomTkinter draws every widget on a canvas of its own and repaints it whenever its size changes, about a millisecond each; with the widgets this window has, one step of a drag cost a quarter of a second. An empty window of the same kind manages six. It is a fixed `WINDOW_WIDE` by `WINDOW_TALL`, and everything inside it is a constant too -- nothing measures a neighbour and applies the result, which used to settle in a visible flicker.
- **One scale, chosen once.** CustomTkinter otherwise makes the process per-monitor DPI aware and compensates in software: it fades a window to fifteen percent alpha and rebuilds every widget when it changes monitor. `_fix_scale()` declares the process aware of the *system* scale and hands CustomTkinter that number, so text stays sharp and nothing is ever rebuilt.
- **"Transparent" is not transparent.** A `CTkLabel` or `CTkEntry` with `fg_color="transparent"` fills its rectangle with the colour it finds behind it. A child as tall as its parent therefore paints over the parent's border. Keep children inset, and use `draw_every_pixel()` on anything with a rounded border -- the drawing code floors a widget's size to an even number first, and an odd one loses its last row.
- Screenshots in the README are generated by `tools/app/screenshots.py` from the running window. Change the interface, re-run it. It refuses to save unless the foreground window belongs to its own process, so leave the machine alone while it runs.
- **A pack can be installed straight into Minecraft.** `paths.bedrock_packs()` is `%APPDATA%\\Minecraft Bedrock\\Users\\Shared\\games\\com.mojang\\resource_packs`, and the button is built only when that folder is there -- Bedrock has been installed half a dozen ways over the years and guessing at another path would write a pack somewhere nothing reads. **It is offered on the dialog that says the pack was built**, beside "Show in folder", rather than decided by a switch beforehand: whether a pack belongs in the game is a thing to decide once it exists. A good install closes that dialog, because it has said what it had to say; a failed one leaves it up, because the notice explaining the failure is about the pack the dialog is reporting. `core.install_pack` extracts the finished `.mcpack`, because Minecraft reads a loose pack as a folder. The folder is `Scaffoldv<version>_<hash>`, where the hash is the pack's own header UUID, so the same build installs as the same folder and any change installs as a different one. **A folder that is already there is never written into**: it holds this very pack, so there is nothing to update, and overwriting one the game may have open is not worth offering. It raises `AlreadyInstalled` and the window shows a notice with nothing but OK.
- **Settings live in `.scaffold`** -- next to the executable if one is there, which makes the program portable, and otherwise in the home directory, not beside the program, so they survive replacing the executable and work when it is run from a folder the user cannot write to. An older `settings.json` is read once to carry a choice over.
- **The settings file is written all at once, and a broken one is left alone.** `settings.save` writes a temp file beside the real one and moves it into place, so nothing can leave a truncated `.scaffold` behind. That matters because an empty or half-written file reads back as "no language chosen", and `load` would then adopt the desktop's locale and write the guess down -- one torn write and the window comes back in the machine's language for good. `load` now only guesses the locale when the file is genuinely **absent**; a file that is there and will not parse keeps English and is not written over, since the user may be part way through fixing it. The window also keeps the file's exact bytes for the length of a build and puts them back afterwards, because a build has no business touching them.
- **What is remembered describes the machine or the person, not the pack.** The theme, the language, the output folder, the TechPack mode, the Tweaks switch and which tweaks are on, the low geometry switch and the transparency slider are stored; the pack name, the description, the icon and the offsets are not. Low geometry and transparency are both about the person in front of the screen rather than the pack: whether a client can afford detailed ghost blocks depends on the hardware and on Vibrant Visuals, and how far through a ghost block somebody wants to see depends on their eyes and their monitor. Neither answer changes between structures. Every setter in `settings.py` writes the file, and `tests/test_interface.py` fails when a key in `DEFAULTS` has no setter it checks.
- **The transparency slider fires on every pixel of a drag.** `set_transparency` writes only when the value actually changed, or a single drag is a hundred writes of the settings file.
- **A collision is answered with a name, not a field to type one in.** The overwrite dialog offers overwrite, the first free name, or stopping. It used to carry an entry box, which duplicated the pack name field in the window behind it and could itself be given a name that collided, which is what made the dialog ask twice. `free_name` is handed a test for what counts as taken, and the caller passes one that checks **every** file the build would write: checking only the `.mcpack` suggested names that collided on a block list file, and with nowhere left to type, that is a loop with no way out.
- **"Show in folder" points at the file and closes the dialog.** Explorer and Finder both take a file and select it, and a selection that fails for any reason falls back to opening the folder, because the point of the button is to get somebody there. Linux has no equivalent, so the folder is the whole answer. The dialog goes because it has said what it had to say, and a modal left in front of the window somebody has just been sent away from is one they have to come back and dismiss.
- **Explorer's `/select` goes as one command string, not an argument list.** Python quotes an argument as soon as it has a space in it, and Explorer will not parse a quoted `/select,<path>` token: it drops the selection and opens a default view. A pack in `Documents\Scaffold Builds` therefore opened `Documents`. The switch stays outside the quotes and only the path is quoted. Explorer also exits 1 on success, so its code says nothing.
- **An update says what it contains, and the notes are signed too.** `build.py --publish` reads the section for the version out of `CHANGELOG.md` and signs it into the target's custom metadata, and `updates.offered()` hands the window back `(version, notes)`. A dialog somebody decides from has to be as trustworthy as the download it describes, which is why the notes travel inside the signed metadata rather than in a file published beside it. A release with no section falls back to the general sentence the dialog always showed.
- **An update is signed, and that is the whole point of the mechanism.** The old updater downloaded an asset and checked it against a `SHA256SUMS.txt` published beside it, which proves the file arrived whole and nothing else: the fingerprint travels with the build it describes, over the same connection, from whoever is answering. TUF signs the metadata with keys that never go near the server, so a release has to be the project's to be installed at all. **Do not reintroduce a fingerprint check as though it were a signature.**
- **The trusted root ships inside the executable.** `scaffold/trust/root.json` is what everything else is checked against, so it is the one thing that cannot be fetched. `updates.client()` copies it into the client's metadata directory **only when there is nothing there**, because writing it every time would undo a root rotation that had already reached that machine.
- **The client's working files are in the home directory, not beside the executable.** `~/.scaffold-updates/` holds the verified metadata and the downloaded archives. A copy installed in Program Files cannot write beside itself, and that is exactly the copy whose update must not fail.
- **A build replaces itself and nothing else.** One signed archive carries both executables and the loose files beside them, because one archive is one thing to sign and one thing to verify. `updates._ours_only` empties the unpacked folder of everything but the running program's own executable before the copy runs, so the window replaces `Scaffold.exe`, the command line replaces `Scaffold-cli.exe`, and neither writes over the other or over the licence. A bundle that does not carry the running executable under the name it runs as is left whole, so a renamed copy still updates.
- **The install is a copy, and it outlives the process.** `tufup` unpacks the archive and starts a script that robocopies the new files over the old ones and launches the new build. Scaffold passes its own batch template, because tufup's does not restart the program, and `CREATE_NO_WINDOW`, because tufup opens a console to run it in. The script keeps retrying, so the window can take its time shutting down: a running executable cannot be written over on Windows, but one on its way out will be free by the time the copy reaches it.
- **tufup ends the install by calling `sys.exit`, and that has to be caught.** The window runs the install on a worker thread, where `sys.exit` ends the thread and leaves the program running on the file being copied over. `updates._put_in_place` catches it, the window is told it worked, and the window leaves in its own order.
- **A pre-release is offered pre-releases; a final release is not.** `updates.channel()` reads the running version, so somebody on a release candidate keeps being offered them instead of hearing there is nothing new until the final ships. tufup filters them out by default.
- **`clear_displaced` is for the updater this one replaced.** The builds from before the rename to Scaffold, numbered up to 3.0.1, updated by renaming the running file to `Scaffold.exe.old`. Every Scaffold release, from 0.9 on, updates through tufup and writes none, so this can go once nobody is updating from one of those builds.
- **A reason handed back is the name of a string, not a string.** `install_latest` returns `(reason, detail)` so the window can put it in the running language, and a name the table does not carry reaches the screen as itself. `tests/test_updates.py` reads the source for every `"update ..."` it names and fails when one is not in `en_US.lang`.
- **The first launch starts in the desktop's language.** With no language remembered, `system_locale.read()` asks the machine and `settings.match_locale` turns the answer into one of the files: that locale, then any file for the language, then English. It happens once, because the guess is written to the file like any other choice, so somebody who then picks English on a Spanish machine keeps English.

### The generated pack's name and description

`pack/manifest.py` owns both. The name shown in game is prefixed -- `Scaffold: <what the user typed>` -- and the prefix is presentation only: the fingerprint the UUID is derived from holds the name as typed, so the prefix never makes a pack look like a different one.

The description is one field with newlines between its parts: the user's own note first, then the name tags, then the TechPack version if bundled, then the credits line. The credits colours are Minecraft formatting codes and each author keeps the colour they have always had.

---

## Where the data lives

**The data lives inside the package.** `scaffold/lookups/`, `scaffold/Vanilla_Resource_Pack/`, `scaffold/fonts/` and `scaffold/images/` sit beside the code that opens them, and that is what makes the project installable: setuptools ships package data only from under the package directory, so a `pip install` of a project keeping them at the repository root would install a program with no tables and no textures.

The release is also a **single self-contained executable**, and the same directories — plus the shipped part of `be_tech_pack/` and `pyproject.toml` — are packed inside it and unpacked at run time into a private folder.

**They keep the layout they have in the source tree.** `scaffold/lookups` is packed as `scaffold/lookups`, so inside the unpacked copy the tables sit beside the code that opens them exactly as they do in a checkout, and `paths.py` finds them without knowing it is inside a bundle at all. That is why there is no equivalent of PyInstaller's `sys._MEIPASS` here and nothing looks for one.

**`sys.executable` is not the way to find the executable.** A onefile build unpacks itself and runs the copy, so `sys.executable` and `__file__` both point into a temporary folder rather than at the file the user launched. Nuitka gives the real one as `__compiled__.containing_dir`; `paths.executable()` is the only place that knows, and `settings.py` and `updates.py` both go through it. `paths.frozen()` asks whether `__compiled__` exists, which is what Nuitka defines and a checkout does not.

`be_tech_pack/` is a git submodule and seventy megabytes, so it cannot be package data. A generated pack draws on about one megabyte of it, and **that megabyte is staged into `scaffold/techpack/` and committed** by `tools/vendor/tech_pack.py` — which is what lets a pip install offer the TechPack setting at all. The submodule stays the source of truth: **re-run the staging script after updating it**, or a release ships the old assets. `tests/test_tech_pack.py` fails when the two have drifted.

**Every data read goes through `paths.py`.** A hardcoded `open("lookups/...")` works in a checkout with the right working directory and fails everywhere else, which is the worst way for a bug to behave. `paths.data()` searches, in order: beside the executable, then the package itself -- which in a release is the unpacked copy.

Beside the executable wins on purpose: a bundle is read only, so anyone hand-editing a lookup table to add a block can drop the folder next to the exe and have it take effect without rebuilding.

`tests/test_paths.py` builds a pack with the working directory set to an empty temporary folder. That is the cheap way to catch a module that still assumes the checkout is the working directory -- a missing `import paths` shows up there as the NameError it is, rather than only in a release nobody has run yet.

## Languages

**One file per language, in `lookups/lang/`.** `<locale>.lang`, one `key=value` per line, UTF-8, `#` for a comment. Adding a language is adding a file and, if its *language* has no colour yet, a line in `lookups/language_colors.json`. Nothing lists the languages: `lang_parse.parse()` reads the folder.

**A language is named by its locale everywhere**, the way Minecraft names its own: a language and a region, `en_US`, `es_MX`, `zh_CN`. The language part is ISO 639-1 where there is one and ISO 639-2 where there is not, which is `ceb` for Cebuano. The locale is the file's name, the key every table is read with, the value the picker carries, and what `.scaffold` remembers, and **nothing inside the file repeats it** -- a locale written in two places is one that can disagree with itself.

**The language part is what a locale falls back to.** `ui_fonts` and `lang_icons` ask for the locale and then for its language, so `zh_TW` is drawn in the same face and the same colours as `zh_CN` without either being listed. That is what makes adding Mexican Spanish beside Spain's a matter of adding a file. `lang_parse.language_of` is the split.

**Two lines describe the language rather than label anything.** `language name` is its own name for itself, which the picker shows and sorts by. `language badge` is the letters on its badge, for the languages where the language part is not the thing to show: `en_PT` reads PT, because Pirate Speak reading EN says nothing. `lang_parse.META` names both, and the tests that compare one language against another leave them out. Neither is the `language` line, which is the word "language" translated, for the label beside the picker.

The picker leads with English, because it is the source the rest are translated from, and then goes alphabetically by name. The special languages sit among the real ones; nothing keeps them apart.

**The special languages are files too, and generated.** `tools/app/languages.py` writes them from `en_US.lang` using the transforms in `tools/app/transforms.py`, at the locales Minecraft itself uses: `en_PT` Pirate Speak, `lol_US` LOLCAT, `en_WS` Shakespearean, `en_UD` upside-down English, and `en_SGA` for Enchanting, which Minecraft has no language for because it is a font. Sixty-odd strings times five is three hundred lines nobody would keep in step. **Re-run it after changing an English string**; `tests/test_languages.py` fails when they have drifted.

Two things to keep in mind when touching `tools/app/transforms.py`:

- **Format placeholders are protected.** The transforms run only over the text between `{}` markers. Reversing "Built {}" without that protection produces "}{ ..." and the next finished build raises on `.format()`.
- **Enchanting is an evocation, not the real alphabet.** Minecraft's enchanting table script is a *font* -- the glyphs are in the resource pack as `font/ascii_sga.png` and there is no Unicode block for them -- so no string of characters can be the genuine article. It is generated as English unchanged and drawn in the rune face `tools/app/fonts.py` builds from that sheet.

Badges are drawn by `ui/lang_icons.py`, coloured by `lookups/language_colors.json`, which carries an entry for nearly every ISO code and one per special language, so every entry in the picker is told apart by its colours. **One badge is borrowed:** upside-down English wears the English badge flipped top to bottom, letters and all, which turns the slant of the bands over as well as the text. `lang_icons.UPSIDE_DOWN` is the only entry of its kind.

`docs/TRANSLATION.md` is what a translator reads; keep it in step with the files.

---

## Finish every round with a version bump

**Every time a set of tasks is completed, bump the version.** This is not something to ask about or offer; it is part of finishing the work. If a round of changes is done and the version has not moved, the round is not done.

- **Major** (`1.2.0` → `2.0.0`) — a change that breaks packs already in use, or a change so large it is not worth enumerating the minor and fix changes that went into it.
- **Minor** (`1.2.0` → `1.3.0`) — new behaviour a user can notice: a new setting, a new control, a change to what an existing feature does, newly supported blocks.
- **Fix** (`1.2.0` → `1.2.1`) — refinements to what is already there: bug fixes, texture and lookup-table iterations, wording, layout, internal restructuring with no visible change in behaviour.

When a round contains both a minor and a fix, the minor bump wins and the fix digit resets to zero. When the major digit is incremented, the minor and fix digits reset to zero.

The user will sometimes say a change "rolls into" the previous one and does not increment the counter, or will name the digit to move to. That overrides the rule for that round.

### Where the version lives

**`pyproject.toml`, `[project] version`.** That is where PEP 621 says a version lives and where every packaging tool looks for it. **Bump it there and nowhere else** — nothing in the tree hardcodes a version, and `scaffold.__version__`, the window title, the release zip's name and the generated pack's manifest version all come from it.

`version.py` reads it back, and has to do so three ways because Scaffold runs three ways:

- **from a checkout** — `tomllib` parses the file, which is right there
- **compiled** — there is no distribution metadata, which is why `build.py` packs `pyproject.toml` into the executable, beside the package where the same walk up finds it
- **installed with pip** — the file is not installed, so `importlib.metadata` answers instead

**The file is read first, and that order matters.** An editable install records the version when it is installed and does not notice it changing, so asking the metadata first meant a checkout reported whatever `pip install -e .` had last seen. Bumping `pyproject.toml` then appeared to do nothing, and the build's own version test was the only thing that noticed. A real pip install has no `pyproject.toml` beside the package, so it falls through and is unaffected.

`tomllib` is standard library from 3.11, which is what `requires-python` asks for, so none of that costs a dependency. The answer is cached: it cannot change while the program runs.

---

## Every bump updates CHANGELOG.md

**`CHANGELOG.md` is what the update dialog shows**, so it is read by somebody
deciding whether to take an update, in the middle of a game, on a small dialog.
`build.py --publish` reads the section whose heading names the version and signs
it into the update metadata. A release with no section offers a blank.

Add a section every time the version moves, above the previous one:

```
## 1.2.3
One short paragraph.
```

What belongs in it:

- **Only what a user would notice.** A new block, a new setting, something that
  was broken and now is not. Not refactoring, not test counts, not which
  function moved where. If nobody using the program could tell it happened, it
  does not go in.
- **Plain words.** Write it for somebody who builds in Minecraft and has never
  read a line of this code. "Packs can be installed straight into Minecraft"
  rather than "added `install_pack` to core". No identifiers, no file names, no
  jargon -- not `.mcstructure` if "structure file" will do, not "UUID" or
  "manifest" or "atlas" at all.
- **A paragraph, not a document.** `build.py` cuts anything past
  `NOTES_LIMIT` characters, and a dialog cannot scroll. Two or three sentences
  is the shape. Lead with the thing most people were waiting for.
- **Say when somebody has to do something.** If an update needs a pack rebuilt
  or re-applied, that sentence matters more than everything else in the entry
  and goes first.

The release summary written at the end of a round and the changelog entry are
close cousins; the summary is for the person reading the reply, and the entry is
for a stranger in a dialog, so the entry avoids anything the summary could
assume.

## Every bump ships with a summary and a commit message

Hand over both in the same reply as the bump, without being asked, at the end after describing the work. They are written for different readers and should not be the same sentence.

**Release summary** — one or two sentences on what is new and what changed, in prose. Add a short clause only if something breaks for existing users and they have to act on it. Not a formatted document, not a section per subsystem, not an artifact. Write it directly in the reply.

**Commit message** — one line, a few words, in the user's own log style. No body, no bullets, no test counts. Real examples from the log:

```
First release
Bugfixes
Fixed and updated items
Revamped the compass to the ledger.
More item fixes.
Bracket customization.
Changed Sigil watermark in the menu
```

Brevity here is about summaries and commit messages only. Detailed technical explanation while working through a problem is welcome.

---

## How a pack gets built

`Scaffold(pack_name)` makes a folder, then:

1. `add_model(name_tag, file)` and `set_model_offset(name_tag, offset)` register each structure. **`set_model_offset` is not optional** — the offset defaults to `None` and the geometry builder subscripts it.
2. `generate_with_nametags()` reads each structure, and for every non-air block calls `armorstandgeo.make_block`, which resolves the block through the lookup tables into cubes with UVs and appends them to a per-layer bone.
3. `compile_pack()` writes the manifest, copies the icon, zips the folder and renames it to `.mcpack`.

**Every structure file is opened through `structure_reader.load`.** From Minecraft 26.60 a version 2 file may say `compression` 1 at its root and keep its `structure` compound as zlib compressed little endian NBT in a byte array; `structure_reader.expanded` turns it back into the compound, and everything else in the root, the size and the origin among them, was never compressed. Nothing that reads a structure's blocks calls `nbtlib.load` on one itself. The window reads only the origin from the root, so it is the one place that does.

Blocks are batched into bones named `slice_<y>`, parented to `layer_<y % 12>`. The layer bones are what the pose animations scale up and down, which is how shift-right-clicking an armor stand steps through the build.

### Driving it from something other than the GUI

`scaffold.core` is the API any front end uses, and it is deliberately the only thing a future service would need. Everything it produces is available as data as well as as a file, because a service wants the former:

| Call | Gives you |
| --- | --- |
| `compile_pack()` | the path to the finished `.mcpack` |
| `get_nametags()` | the name tags in the pack |
| `get_block_lists()` | `{name tag: {block: count}}` |
| `get_material_list()` | every block the pack needs, summed across models |
| `get_skipped(write_file=False)` | `{block: {variant: count}}` that could not be built |
| `get_unique_blocks_count()` | how many distinct blocks the pack covers |
| `get_lookup_version()` | which build of the tables produced it |
| `core.outputs(target, tags, block_lists, big)` | every file a build under that name would write |

Settings a caller can pass before generating: `set_opacity`, `set_description`, `set_icon`, `set_model_offset`, `set_list_labels`, `set_low_geometry`, `set_tweaks` and `set_tech_pack`. Every one of them is in the fingerprint, so two packs that differ by any of them are different packs. `set_retry` is the exception: it describes what to do when a write fails rather than what the pack contains, so it is not part of the fingerprint.

**`core.outputs` has to agree with what the build writes.** It is what a front end asks before it starts, and it never looks again, so a file the build writes without being named there is one that gets written over with nobody asked. Both sides go through `pack_file` and `block_list_file`, and `tests/test_overwrite.py` builds a real pack and compares the folder against the list.

**A failed write is handed back, not thrown.** `set_retry` takes a callback given the `OSError` and the path, and returning True runs the same write again. Windows refuses to write a file another program holds open, and a pack the player still has loaded is exactly that. With no callback the write raises, which is what the command line wants: it refuses by name and points at `--overwrite`.

Keep it that way. A hosted version of Scaffold belongs in its own project that imports this one; anything that knows about a queue, a bucket, a bot or a user account does not belong in this repository. The previous attempt lived here as `lambda_function.py` and had to reach into `structure_files[...]["block_list"]` because the accessors above did not exist.

**A block that fails to resolve is not an error.** `make_block` raises, `_add_blocks_to_geo` catches it, and the block is recorded in `unsupported_blocks` and reported in the skipped list. That is why a missing `block_definition.json` entry produces a silently incomplete model rather than a crash — and why the audit in `tools/` matters.

### The pack icon

`pack_icon.png` must be a valid PNG, square, and **256×256** — the size Microsoft documents for the pack selection screens (`CPACKICON101`–`104` in the Creator Tools validation reference). There is one per pack root; a subpack carries its own, nothing else should.

`tools/app/icon.py` regenerates both icons the project ships — `lookups/pack_icon.png` at 256×256 and `images/pack_icon.ico` from 16 px to 256 px — by rendering the isometric S cube over `background_slimelab.png`. The grid colour, its alpha and the S material are the constants at the top of that file. Nothing is stored that the script cannot rebuild.

**No tool checks the icon rules.** This section used to claim the audit did; it never has. If it matters, the check belongs in `tools/checks/blocks.py`.

### High and low geometry

Every ghost block is geometry the client lights and draws, and Vibrant Visuals makes that markedly more expensive. A shape family may carry simpler forms of itself in a `low` section beside its `forms`, which the geometry builder reads as a family named with `armor_stand_geo_class.LOW_SUFFIX` -- `bell__low` beside `bell` -- and `simplify()` swaps to it when the pack is built with `set_low_geometry(True)`. A family without one is drawn as it always is, which is most of them.

`tools/blocks/simplify.py` generates those forms. **Re-run it after changing a detailed shape**, or the simple form is still the old one's outline.

**A simpler form is the same block with fewer cubes**, so everything but the cubes is the detailed family's: the rules that pick a form and the rotation table both go by `family`, and only the shapes and the windows come from the family's `low` section in `block_geometry.json`, under the same form names. A family that is simplified gets a simpler form for *every* form it has -- a bell on a wall is its own box, not the standing bell's -- and each one pivots on the detailed form's `center`, because it is turned by the same table about the same point. A family whose default form has stopped being worth simplifying has its simpler form dropped.

### The lookup tables

| File | What it holds |
| --- | --- |
| `lookups/block_definition.json` | block id → shape family, for current ids only. Missing entry means the block is skipped |
| `lookups/block_upgrades.json` | an older structure's block ids and states → the ones the current game uses, applied as a structure is read |
| `lookups/block_geometry.json` | shape family → its forms, each a centre and cubes with a window and a texture per face, the simpler forms low geometry draws, and the rules that choose a form from a block's states |
| `lookups/block_rotation.json` | shape family → the state it turns by, or a rotation table of its own |
| `lookups/state_rotations.json` | facing state → Minecraft's turn for each of its values |
| `lookups/schema/` | a JSON schema per geometry table, which `tests/test_lookup_format.py` validates against |
| `lookups/block_list.json` | block id → the name shown in the block list |
| `lookups/block_categories.json` | the headings the block list is grouped under, as patterns tried in order |
| `lookups/dust_connections.json` | the rules redstone dust is joined to its neighbours by |
| `lookups/item_icons.json` | block id → its inventory picture, which low geometry draws small blocks as |
| `lookups/stack_sizes.json` | what stacks to 1 and to 16, for a container's fill count |
| `lookups/tweaks.json` | every Bedrock Tweak and Clearer Redstone option offered |
| `lookups/language_colors.json` | the colours of each language's badge |
| `lookups/lang/<locale>.lang` | UI strings, one file per language, named for its locale |

**Every table opens with the same header**: `$schema` where a schema checks it, `format` (2), `minecraft` where what it holds describes the game, which is the version of the game's files the tables were checked against and is kept in every table so a table used on its own still says it (`tests/test_lookup_format.py` fails when it differs from `latest` in the submodule's `version.json`, which is the signal that an update needs doing), and `about`, one line on what it holds; then what it holds, under one key or a few named for it. A table with a single map under its header, `block_definition.json`'s `blocks` and the like, is read through `lookup.entries` or `lookup.unwrap`, which also read a table written before the header, a map at the top level, so one a user has edited and dropped beside the executable keeps working. A generator writes one through `lookup.save_entries`, which keeps the header, and every table but the three geometry tables is written in one style, tab indented with a space after each colon, by `lookup.save`.

### The tables are in Minecraft's terms

**A table describes a block the way Minecraft does**, so that one day Scaffold can read a block's definition straight out of a resource pack or an add-on. Three things follow, and `tests/test_frame.py` holds all of them:

- **The geometry is in the coordinates a Bedrock `.geo.json` uses**, in blocks from the corner of the cell rather than pixels from the middle of its floor: offset = (origin + 8) / 16 across and deep, origin / 16 up. Mojang's own shelf mushroom model converts that way into the table exactly. **East is the low side of x**, as it is in every `.geo.json`.
- **A block rests facing north.** Its front is the north face when nothing turns it, which is Minecraft's own rest pose and what `minecraft:cardinal_direction` "north" leaves alone.
- **A rotation table holds Minecraft's angle for each state**: `minecraft:cardinal_direction` north 0, west 90, south 180, east 270; `facing_direction` the same, with down 90 about x and up 270. A numbered `direction` is 0 south, 1 west, 2 north, 3 east, and a trapdoor's is 0 east, 1 west, 2 south, 3 north. `make_block` turns that into what a bone needs in one place, `armor_stand_geo_class.to_bone`: **a bone turns the other way about y and z**, because the model is the world mirrored in x.

A cube's own `rotation` in `block_geometry.json` is not a Minecraft angle: it is the turn a bone applies, which is how a `.geo.json` writes one too. A `yaw` handed to `make_block` *is* a Minecraft angle. `core.entity_yaw` turns an entity's (0 south, 90 west) into one and `core.head_yaw` a skull's `Rotation` (0 north, clockwise).

**Every generator writes in Minecraft's frame**: its cubes facing north, in a `.geo.json`'s coordinates, and its rotation tables in Minecraft's angles or as the name of a state in `state_rotations.json`. `tables.put` writes what it is handed and turns nothing. **Many families are painted `behind`**: `geometry.Cube(..., behind=True)` reads the top and bottom backwards, measures a side's window from the far side of the block, and lets a side left to the block's own textures read the opposite side's slot. That is how the families that once rested facing south were painted, and it keeps them drawing exactly what they drew, which was settled in game. `tests/test_frame.BehindTests` holds what it does.


**Some tables disagree with Minecraft's numbering, and are kept drawing what they drew.** Pistons, sticky pistons, their arms and end rods have all four sides half a turn from Mojang's facing; a lightning rod has east and west swapped; a vault north and south; a dispenser and a command block put up and down somewhere Minecraft's angles would not. Each could be a table tuned with the armor stand facing the wrong way, or a real quirk of the block. Nothing has been changed until a world says which. `docs/Block Notes.md` keeps the list.

**The ghost turns with its armor stand**, and a structure is drawn the way it was saved only when the stand faces north: placed by somebody standing north of the spot and facing south. Every in-game check of which way a block faces needs that placement stated, or a stand a quarter turn out looks exactly like a table a quarter turn out. `tools/checks/compass.py` builds a pack of lettered cubes for checking the frame itself, and `tools/checks/gallery.py` builds a whole `.mcworld` for checking blocks: every state the tables tell apart, as a real block with its ghost three blocks above it, fully opaque, in a void world written whole by `tools/checks/worldfile.py` -- blocks, block entities, stands and paintings already in its database, spectator, simulation distance 12, and fire, random ticks, mobs and weather off in its `level.dat`. The blocks are grouped into a plot per block list category, each with its own named stand facing north and its name written in its own ghosts on all four sides; REAL and GHOST paintings mark each tier's rows. Bedrock draws an entity, and so the ghosts, only to about 64 blocks from the player, which is why a plot is never more than 64 across or `PLOT_TIERS` high. **Write a block entity the way the game writes one.** A world holding lecterns that said they held a book with none in it, and chiseled bookshelves whose states named books with no block entity to hold them, crashed the game on loading with nothing in any log; both were fixed at once, so which of the two did it is untested. Its own docstring has the rest.

### Old structures are translated as they are read

**A structure keeps every block the way the game described it the day it was saved**, and Mojang has renamed a great deal since: `wool` with a `color` is sixteen ids now, a door's numeric `direction` became `minecraft:cardinal_direction`, every slab's `top_slot_bit` became `minecraft:vertical_half`. `scaffold/block_upgrade.py` translates each palette entry to the current names as `structure_reader` reads it -- and the plant a flower pot holds, which is a whole block in the pot's entity -- so **every lookup table describes current blocks only** and none carries an old name beside a new one. The file on disk is never touched. It runs once per palette entry, not per block, so a build of any size costs a few hundred lookups.

The rules are data, in `lookups/block_upgrades.json`, and run top to bottom, each seeing the block as the rules above it left it: an id renamed (`becomes`), an id split by the value of one or more states (`by`, `into`), or a state renamed, remapped or dropped (`state` with `becomes`, `values`, `drop`). Ids are renamed and split first, so a state rule names the id a block has *become* -- an old anvil is split into `chipped_anvil` and only then has its `direction` turned into words. A new value is written with its JSON type, which is the NBT type the rest of the code receives: a string, a number, or `true`/`false` for a byte.

**`before` is for a rule that remaps values.** A renamed id never comes back, so a rename can apply to anything, but a remapped value means one thing before the change and another after it. Glow lichen's face bits were reordered in 1.18.10 and a number alone cannot say which order it is in; the `version` every palette entry carries can, and a rule with `before` applies only below it. A block with no version -- the flower pot's plant -- is taken as current.

**A state a block never had is left absent**, not given the value the game would now give it. A stair saved before `minecraft:corner` existed has none, and every table reads an absent state as the default form. **Nothing works such a state out from the neighbours either.** Stair corners and the `minecraft:connection_*` joins of fences, panes, bars and string were first saved by 26.50, and a structure from before that draws them unjoined and straight; the README says so where it explains exporting. **Redstone dust is the exception**, because Bedrock saved no joins for it before 26.60: a structure from 26.60 on carries `redstone_north` and the rest, which `dust.saved` reads as they are, and for an older one `scaffold/dust.py` works them out from the neighbours by the rules in `lookups/dust_connections.json`, and `docs/Block Notes.md` has the rules, where Bedrock differs from Java, and how an add-on's own redstone components will feed them. **Water is told where more water is** in the same way, so a face between two cells of water is not drawn and water with water above it fills its cell. Its top is drawn apart from its sides: the sides after the block standing in it, and the top before it when the block covers the surface, so it shows through a grate's or a leaf's clear texels (`core.water_families`).

**Mojang's own numbering is the answer, not the rotation tables'.** Door `direction` 0 is `south` after Mojang's upgrade, and the door table had paired `0` with the turn it gives `east` -- the two sets of keys were tuned apart, and an upgraded door has to look the same as it did. A translated block is turned by the word keys, which are the ones current placements use.

**A block list reads the same way.** `block_upgrade.list_key` turns an id and variant from somebody's own `.scaffold-blocks.json` into the current id, so a name given to `stone_block_slab`'s `quartz` variant still names a quartz slab.

**Structura 1.7 can be handed these tables, translated.** `python -m tools.export.structura <out>` writes a `lookups/` and a `Vanilla_Resource_Pack/` to copy over a Structura 1.7 checkout. Structura picks a form from one data state, one top flag and one rotation state, reads a data form's windows from `default`, reads no block entity and translates no old block, so the export is per block: every gallery case is drawn by Scaffold and filed under the key Structura would read it with, every window, turn and slot is resolved into a texture, cut out as a tile of its own where Scaffold cuts one, and every old id and state `block_upgrade` knows is run backwards into cases of its own. What it cannot carry -- an attached hanging sign's sixteen turns, a door's hinge, a cauldron's liquid, a top slab other than turned over -- is listed by `--report`.

**PocketMine's upgrade schema is the reference and is never shipped.** `pmmp/BedrockBlockUpgradeSchema` is generated from Mojang's dedicated server, one release at a time, and is LGPL-3; this project is MIT. `python -m tools.checks.upgrades --schema <clone>` reads a local clone and compares every test structure's palette, and old blocks made from every rule, against what the schema makes of them. Its docstring lists the differences a clean run still shows and why. **When Mojang renames something, add a rule by hand and run the check**; do not generate the table from the schema.

**A rotation table holds only the values its family's blocks can carry today.** A family whose blocks carry `minecraft:cardinal_direction` has the four words and no numbers; one whose blocks still carry a numbered `direction` has the numbers and no words. A key nothing can reach is dead weight that reads as though it did something, and a family with no rotation state has no table at all -- `tables.unturn`. **An angle is not a key:** an entity's yaw, and the `Rotation` a floor head keeps in its block entity, are handed to `make_block` as `yaw`, a Minecraft angle in degrees, and added to whatever the table gives, so neither the cushion nor the heads carry a key per angle.

### The block list

**Not everything drawn is a block.** An entity is kept out of the grid entirely: a structure records it in `structure.entities` as a whole entity with a world position of its own, so nothing in `block_indices` marks the cell it stands in and no lookup table could ever reach it. `core.ENTITY_MODELS` is the bridge, naming per entity identifier a pseudo block id to draw it as and which of its own fields picks the form; `structure_reader.get_entities` turns a world position into a cell and `core.entity_yaw` turns the entity's yaw into a block angle for `make_block`, which applies it directly, so an entity's family has no rotation table. From there an entity is an ordinary block, with a family in `tools/blocks/entities.py`, a shape, a rotation table, a simplified form and a line on the block list, none of which had to learn what an entity is. **A cushion is the only one so far**, and it is why the pipeline exists: 26.50 made it an entity rather than a block, so a build full of them showed nothing at all. An entity nothing names is passed over in silence rather than reported as skipped -- a structure is full of dropped items and none of them is something a builder places.

**An entity's list key is its identifier and its form**, `minecraft:cushion/white`, so it is named and grouped out of the same two files every block is, and a user's own `.scaffold-blocks.json` overrides it the same way. They sit under **Entities**, a heading of their own, because a cushion is not going to be in the same chest as the wool it was made from. Entities are counted into the list whether or not one is written; the window's **lists** switch is what decides if a file appears.

**A block list is counted by block id and named only as it is written.** `structure_reader.get_block_list` counts ids, with the variant on the end where a block has one -- `minecraft:red_flower/poppy`, because a poppy and an allium are one id and two things to gather. `block_list.py` turns those into names and headings at the last moment, out of `lookups/block_list.json` and `lookups/block_categories.json`. A count already turned into a name cannot be regrouped or renamed afterwards, which is the whole reason the naming happens last.

**Counts are summed by the name, not by the id.** Several ids are one thing to gather -- a double slab and a slab are both slabs, and the table calls them the same -- and two lines for one item is arithmetic at a chest.

**A user can supply their own file, and it is looked for where the settings file is looked for**: beside the executable, then the home directory, as `.scaffold-blocks.json`. **Nothing is ever written to either place.** The file is Scaffold's to read and the user's to write, and a program that rewrites the file somebody is editing is a program that loses their work.

What is found is **merged over** what ships rather than swapped for it, and the two halves merge differently because they are different shapes. `names` is a dictionary, so one entry replaces one block's name and leaves the other thousand alone: renaming one thing is a four-line file. `categories` is an ordered list and the order is the whole meaning of it, so a file carrying any categories at all replaces the list outright. Half a list of categories merged by name into another is not something anyone could predict the result of.

Category patterns are shell-style globs on the block id, matched whole, with the `minecraft:` optional and **first match wins**, so the order in the file is the order they are tried. Anything unmatched lands under `Other` rather than being dropped: a block left off a shopping list is a wall somebody cannot finish.

**A pattern is matched against the variant as well as the id, and a star does not cross the slash.** A few current blocks keep something in the variant, such as how cracked a turtle egg is: `*/cracked` means "a cracked one of anything", which only works because the star stops at the separator -- otherwise it would match `turtle_egg/max_cracked` by swallowing the slash and half the variant. An old structure's multi-material ids never reach the list as one id and a variant: `stone_block_slab` with `quartz` arrives as `quartz_slab`, already translated.

**The headings group by material, not by shape.** Wood is a heading per wood type and stone a heading per stone, so everything oak is one pile rather than every stair in the build sitting together; concrete, wool, glass and terracotta each have their own; and the things gathered as items -- flowers, crops, saplings, fungus -- are matched first so they never land in a block heading. The order that follows from that is load-bearing three times over: the item-like categories come first, `Redstone` comes before anything matching `*stone*` or redstone and glowstone are "stone", and a type whose name contains another's goes above it, which is why Dark Oak and Pale Oak precede Oak and Red Sandstone precedes Sandstone.

**The geometry tables are format 2.** `block_geometry.json`, `block_rotation.json` and `state_rotations.json` each open with `"format": 2` and the Minecraft version they were checked against, and format 2 *is* Minecraft's frame: there is no frame field because there is no other frame. A form's cubes and windows are one entry, so the two cannot disagree. `scaffold/block_geometry.py` reads the file into the two column tables `make_block` has always consumed and writes them back, and `tools/blocks/tables.py` is how a generator puts one column of a family.

**A family's rules choose its form.** `pick` names a mounting from matching states, `data` makes a value from states or the block entity, `turn_by` names the state that turns it and `texture_by` the one that picks from a texture list; the form drawn is the first of `<mounting>-<value>`, `<value>`, `<mounting>` and `default` the family has. Nothing in `core` or `make_block` names a family any more: a door's open, hinged and upper forms, a hopper's side, a hanging sign's two numberings, a banner's dye and a lectern's book are all rules in the file. `ArmorStandGeo.choose` gives the form, turn and texture index a block would be drawn with, and is what a test should ask. `docs/Editing Blocks.md` has every key.

**Not every state is in the states.** A copper golem statue keeps its pose in the block entity beside the block, the way a sign keeps its text, so four statues in four poses share one palette entry. `structure_reader.get_block_entity` reads `block_position_data`, and a family's `data` rule names the fields worth reading — a block entity carries a great deal that has nothing to do with how a block looks.

**A block drawn with an entity's model takes the model, not a box measured off a picture.** `tools/blocks/geometry.unwrap` is the way Bedrock lays a box out on a sheet and `geometry.spun` is the turn a bone or a cube carries; the mob heads and the copper golem statue both go through them. The statue's four poses are four geometry files in the game's resource pack — `copper_golem`, `copper_golem_sitting`, `copper_golem_running`, `copper_golem_star` — not one shape leaned four ways.

**A block entity may hold another whole block, and then one position draws two.** A flower pot keeps what is planted in it as `PlantBlock`, a compound with a name and states of its own; `core.BLOCK_ENTITY_HOLDS` names that field and `core.Scaffold._drawn_at` returns the pot and the plant. The plant is then drawn by its own family with its own textures, which is why every pottable plant works without a variant apiece.

**A double chest is two chest blocks, and nothing in their states says so.** Each half's block entity names the other's world position in `pairx` and `pairz`. `core.paired` turns that into which half a block is seen from in front, `left` or `right`, and hands it to the rules as the entity's `pair` field, which the `chest` family's `data` reads; a half whose partner is not in the structure, not beside it or not the same block is drawn as a single chest. Each half reaches from its outer edge to the seam. The front is one picture across both with the latch on the seam: `tools/textures/chests.py` widens each pairing chest's front into a sheet three tiles wide, the single front and then the two halves, and the halves read theirs through a `window` on the same slot, so the one family serves wooden, trapped and copper chests alike. A front staged by a tweak at sixteen wide falls back to the single front, which is the window rule. The gallery writes a pair beside every single chest.

**A second field of a block entity may say the first one does not apply.** A banner's colour is `Base`, but an ominous banner is not a colour at all and a banner carrying `Patterns` cannot be drawn from a dye either, because a ghost block cannot composite six patterns as a pack is built. the banner families' `instead` rule names the fields that replace the form outright, and both of those banners get a sheet of their own from `tools/textures/banners.py`: Mojang's own illager banner, and Scaffold's S as the stand-in for a design.

**`Base` counts the dyes, not the wool.** The two orders are opposite — `Base` 0 is black and 15 is white — so a banner read as wool comes out the colour across the wheel from its own, white as black and lime as purple.

**A picture bigger than a tile is drawn on a stack of quads.** Only sixteen by sixteen of a texture becomes a tile and a quad reads one tile, so anything needing more resolution than that is cut into quads that each read a tile of their own. A marked banner's cloth is one quad across by four down, and `tools/textures/banners.py` writes the design at the size that column reads, under vanilla's own sheet so the post and the bar are still read by the windows every other banner uses. **The design is written mirrored, and the front turns it back.** The sheet holds the picture the wrong way round on purpose, so the face a banner is read from mirrors it back. The back needs nothing: the two faces of a plane already run their windows in opposite directions, so a plain window there shows the sheet reversed once, which is the mirror of the front and is what a real banner does. Turning the back as well cancels that reversal and both faces come out identical. **The cloth is half as wide as it is tall**, and has to be: it carries the whole of a design across its whole width and height, so the cloth's own proportions are the design's. Vanilla's is twenty by forty entity units at two thirds scale, one to two; drawn a full sixteen across it is one to one point seven and an ominous banner's mark came out sixteen percent short. The bar it hangs from matches the cloth, or it sticks out at each end. **Four quads across.** One quad reads one tile, so one across is sixteen texels for the whole width of the cloth and no logo with writing on it survives that. **Column order and tile mirroring are two halves of one thing and have to move together**: reversing the column order *is* a mirror at column granularity, so turning one dial without the other gives the design sliced into four with each slice mirrored in place, rather than a mirror. That is what cutting it up looked like the first two times, and it hid entirely at one column across, where every arrangement is the same tile. Settled in game: **both faces read the column where the quad stands**, because the sheet's own mirror and the block's x mirror cancel on the order, and all that separates the front from the back is which of them turns its own tile round — `CLOTH_DESIGN` in `tools/blocks/banners.py`. Each quad also reaches a twentieth of a pixel past its slot and alternate rows sit a thousandth forward, or the nine joins between them tear. **The renderer disagrees with the game about which face is which here**, and the game is what settled it. The cloth is exactly a tile wide, so cutting it in two bought a little horizontal detail and cost a seam down the middle -- and the halves have to be swapped as well as each being turned round, since the mirror of two columns side by side is the right one on the left. In game the front came out split with its halves out of step, and torn along the seam, while the back read correctly. Rows need none of that, because a mirror is left to right. **Only the two large faces carry the picture**: the other four are the cloth's edges and the seams between the quads, a pixel wide, and they take the banner's own base colour from the same corner a dyed banner reads.

**A rotation table needs every form of the value a current block can carry.** Bedrock gives some blocks a numeric `direction` and others a `minecraft:cardinal_direction` string, and a table with no entry for the value a block carries draws it unrotated, silently. That is what made every door face the same way. An older structure's numbers on a block Mojang has since moved to words are translated before any table is read, so those families need only the words; the numbering is not the same for every block — see `docs/Block Notes.md`.

**A block with no rotation state is never turned by the rotation table.** `make_block` looks a rotation up only when it is handed one — `rot is not None` — so a family whose blocks carry no facing state gets no turn however full its table is. `cross_texture` had an entry turning every plant forty-five degrees, and it was dead: a flower reached `_process_block` with `rot` None and came out square to the block. **And `tools/checks/render.py` hid it**, because it used to pass `rot=0` by default and so found the `"0"` entry — the renderer drew the X and the game drew a plus. It now draws a block at rest unless it is given a state value with `--rot`. A turn that does not depend on a state belongs in the shape, as a cube rotation, where both agree. `tools/blocks/plants.py` is where that one now lives.

**A form may number its rotations differently from its family.** A `"<variant>:<value>"` key in `block_rotation.json` is read before the plain value. A hanging sign carries two rotation states and only one applies: fixed to the block above it turns with `ground_sign_direction` in sixteen steps, and swinging or wall mounted it turns with `facing_direction` in four, so 2 means something different in each. The hanging sign family's `turn_by` rule picks the state.

**A block that Minecraft draws from a Java model is read from that model.** `tools/blocks/java.py` turns Java's elements into a form: x mirrored, up and down read backwards both ways, a face's `rotation` carried as a texture turn, and a face Java leaves out given a window of no size, which `make_block` leaves out of the model and out of the atlas. Multipart blocks -- fences, panes, bars, walls, string -- are assembled from their parts per arrangement with `java.turned` and `java.parts`, and stairs from Java's straight, inner and outer models per facing, half and corner. `tools/blocks/java_models.py` holds the models it reads. A rule may read the block entity as well as the states: `turn_by` takes `{"entity": field}`, which is how a shulker box turns, and `texture_by` takes a `join` of states with a table of values, which is how a copper bulb picks lit and powered.

**A cube's offset inside its block is not mirrored, and the block itself is.** `armor_stand_geo_class` writes a cube's origin as `-1*(x + offsets[0]) + xoff`: the block's place in the grid is negated, which is what turns a structure's x into Bedrock's model x, and the cube's own offset within the block is added to that untouched. So **east is the low side of x within a block**: a cube written east of the middle of its block comes out west of it in game, while the picture on its faces stays where the table put it. It is how a `.geo.json` lays a block out as well, so a model read from one needs no flip. Almost nothing shows this, because a shape's asymmetry is nearly always along z — a wall mounting sits against one wall and a rotation table turns it. The sunflower's flower head is the first shape to hard-code an east-west facing, and it came out on the wrong side of its own stem.

**The same mirror reverses every turn about y and about z.** A bone turns about y the right handed way in the model, which the world sees as the left handed way, and the other way round about z; `spun` works in the table's own space, so a family that places a piece with `spun` and then hands the engine a rotation for the same piece has the two disagreeing. `tools/checks/render.py` **does** model the mirror — `MIRROR` and `ACROSS` at the top of it, and `_spin` for the turns — so what it draws is what the game draws. The audit of which families carry a cube rotation is in `docs/Block Notes.md`.

**The texture atlas is a grid, and it has to stay one.** Every texture a pack uses becomes one 16x16 tile, and the tiles were a single column: sixteen pixels wide and sixteen times as tall as the pack had textures. A structure with a thousand distinct blocks therefore shipped a texture twenty-five thousand pixels tall, which is past what a graphics card will hold -- the common ceiling is 16384 on a desktop and 4096 on a phone -- and Minecraft crashed on loading the world. `ATLAS_COLUMNS` in `armor_stand_geo_class` is sixty-four, so the same pack is 1024 by 400. The UV a cube carries is in *tile* units, so `texture_width` and `texture_height` are tile counts rather than pixels and a tile at index `i` sits at u `i % ATLAS_COLUMNS`, v `i // ATLAS_COLUMNS`. **Do not put it back in one column**, and do not assume a tile index is a v coordinate: `atlas_place` and `atlas_index` are the two directions and everything goes through them.

**A window that runs past its own tile reads the next one.** A face's offset and size are fractions of a tile, and one that reaches beyond 1.0 lands in whatever texture happens to sit next to it -- which depends on the order the blocks were built in, so it was never right. `python -m tools.checks.blocks --tables` lists them; `lever` is the one family that still does it.

**A transparent texel still takes the depth it stands at.** A ghost block is drawn with blending rather than an alpha test, so the empty part of a quad is not free: it wins the depth test against whatever is behind it and blanks it. Two pieces of one block that cross each other therefore cut holes in each other wherever one of them is transparent, which nothing here can show — `tools/checks/render.py` draws a block solid and in one pass. **What is drawn first is decided by the bone's name.** Every cutout and every hidden waterlogged block seen in game fits the game drawing a model's bones sorted by name, not in the order they are written, so the tiers are prefixes that sort: `early_` before a block's `slice_`, then `tier1_` for planes and `tier2_` for water (`armor_stand_geo_class.LAST_BONE` and its neighbours). That reading is untested beyond those worlds; `tools/checks/gallery.py --water-trials` is the check. **So a quad must not reach past its own picture.** A sunflower's stem was drawn a full sixteen tall over a texture with nothing in its top half, and the empty half cut pieces out of the flower it stood behind.

**A ghost block is drawn a shade under full size, and that is on purpose.** A block that is more or less a full cube is written at about 0.95 of it, **centred in its cell**, an equal gap on every side, — a slab is 15.2 wide rather than 16, a stair's step stops a pixel short of the top of its own block. The ghost is a mark on the place a block goes, and the player eventually puts the real block there to cover it: two faces on the same plane flicker, so the ghost sits inside where the real one will be. **Do not "fix" a shape back to a round sixteen** because it looks off by a pixel in the tables. It is not a strict rule and it is not applied to everything — a plant is a picture rather than a box, and things that are already thin have nowhere to shrink to — but for anything cube-shaped, assume the gap is meant.

**A family turns about the middle of its block.** A form's `center` in `block_geometry.json` is that pivot. A family whose cubes all sit at one edge is tempting to pivot on that edge instead, and that takes the block out of its own block: a door pivoted on the plane of its own panel ended up half in the block beside it a quarter turn round.

**A colour that is a whole colour is tinted into the atlas as the pack is built.** A cauldron's dye is an RGB in its block entity rather than one of a list, so nothing in the tables could name a texture for it. A texture written `<name>~tint` takes the block's own colour, `core.BLOCK_ENTITY_TINTS` says which field carries one, and redstone dust takes the colour its `redstone_signal` gives it, `dust.colour`, so every power level is a shade of its own drawn from the game's grey `redstone_dust_cross_grey` and `redstone_dust_line_grey`, and `armor_stand_geo_class.extend_uv_image` multiplies the tile as it loads it. The atlas is keyed by the whole name, so each dye lands there once.

**One texture per cube, not per block.** A block built from several cubes cannot use Bedrock's six face textures directly; every cube would get the same six. `block_geometry.json` gives every face of every cube a texture of its own, and a `slot` means "whatever this block declares for that face", which is how one entry serves every wood a sign comes in.

**A small picture in a full sized file is the same trap.** `bell_side` is a 16×16 file with the bell drawn in an 8×9 corner of it, so a face working its own window out from where its cube sits reads empty space and the bell is a flat plate. Both pieces of the bell name their rows. `heavy_core.png` is the version of that with three 8×8 pictures in one 16×16 file — top, bottom, side — and a quarter of it empty. Every one of a dried ghast's twenty four textures is a 10×10 picture in a 16×16 file, four to a face, one per `rehydration_level`.

**A sheet in `textures/blocks/` still looks like a tile.** `decorated_pot_base.png` is 32×32 and holds the neck's unwrap over the body's top and bottom; `flower_pot.png` holds the rim over the wall. Faces left to work their window out from where their cube sits read those as one picture, which is how a decorated pot ends up with holes through it. `tools/blocks/geometry.on_sheet` turns a region of a sheet into a texture reference and a window, pulling the tile corner back far enough that the region fits and never past the edge of the sheet.

**Only the top left 16×16 of a texture becomes a tile.** A larger one is cropped, never scaled, so its pixels keep their size. **So a tile saved at the wrong scale is a hole in the model, not a blurry block.** `fern` and `short_grass` were both saved as ten times upscales, 160×160, and the corner Scaffold reads was empty, so both drew nothing and neither reached the skipped list. `tests/test_block_coverage.TileTests` fails on a supported block whose tile has no pixels in it. A block drawn from an entity sized sheet says which part it needs by writing `#x,y` after the texture's name, and the window travels with an `@` reference: `"@north#0,12"` is the board half of whatever sheet that wood has. Each window is a tile of its own, and one that falls outside the texture is ignored.

**How a block is mounted is a different shape, not the same shape moved.** `tools/blocks/mounted.py` owns `hanging_sign`, `bell`, `grindstone`, `campfire`, `shelf`, `tripwire_hook`, `sculk_shrieker`, `tripwire`, `flower_pot`, `decorated_pot`, `brewing_stand`, `heavy_core`, `dried_ghast` and `door` in both tables, and gives each mounting its own list of cubes. It also gives a lit campfire its fire, which is the only thing telling it from a dead one and a soul campfire from an ordinary one, gives a shelf a different picture on each face, since its sheet holds the front, the planks and the shaded interior, and gives a tripwire hook the two arrangements `attached_bit` names.

**A ghost block is not a solid one, so vanilla's own trick is not always the answer.** Vanilla paints a shelf's three compartments into its front texture and leaves the block a plain box, which reads correctly when the block is opaque and reads as nothing at all when it is half transparent. The compartments are cut as geometry here instead. The same reasoning gives a sculk shrieker its throat, and `tools/textures/string.py` draws string a tile of its own because vanilla's is a scatter of single faint pixels that disappears on a see-through plate.

**`blocks.json` names texture slots, not faces.** For most blocks the two are the same, but `big_dripleaf` reads `up: big_dripleaf_side2`, `down: big_dripleaf_side1` and the leaf on three of the sides, because the engine picks from those slots for a model of its own. Taken literally, the leaf's top wears four rows of edge profile over an empty tile and the block is invisible from above. A family whose slots do not line up with its faces names its textures outright on its faces.

**The UV lists run in the shape list's order, cube for cube.** A family whose entry was written beside another family's has to have its lists reordered to match its own cubes, not only its numbers changed. `lightning_rod` was copied from `end_rod`, whose two cubes are the same two the other way round, so the base wore the rod's long stripe and the base's square was stretched along the rod. Nothing reports this: both lists were the right length.

**A wall mounting sits against the south side of its block, facing north.** That is the rest pose, so a wall is the block south of it and the rotation table turns it to the wall it is on; `wall_sign` is the family to copy. A bell's beam, a grindstone's legs, a hanging sign's arm and a shelf's whole body all run that way.

**Edit the tables a family at a time.** `tools/blocks/tables.py` replaces one family and writes the file in one fixed layout, a cube to a line and the rules a line each, so a change to one family changes only that family's lines. Its rules are kept when a generator puts the family's forms.

**UV V grows downward.** The upper half of a texture tile belongs on the upper half of a block. A bottom slab shows the *bottom* half of its texture; a top slab shows the top half. Getting this backwards is invisible on stone and obvious on planks. **An up face is the exception**: its v runs toward -z, so the top of a tile lands at the block's *south* edge there and at its north edge on a down face. A cube that does not fill the block front to back reads its top from the far side, and `Cube.uv` is where that is written.

**Bedrock turns a cube about y the other way from `spun`, and about x and z the same way.** `tools/blocks/geometry.spun` computes a position at generation time and the engine turns the cube at run time, so the two have to agree wherever a family does both — a brewing stand's arms are the one that does, and given the same sign they are carried round to their plate and then turned back, landing across the block instead of along their own radius. That is why `brew_turned` writes its move and its turn with opposite signs. **The renderer models this**, in `_spin`, for a cube's own turn and a family's alike, so a picture from it can be trusted; a turn the family's rotation table gives is converted by `to_bone` before either sees it.

---

## What an `.mcpack` actually is

A ZIP archive with the extension changed. Everything that makes one work or not work is about the archive's shape:

- **The pack root is the archive root.** `manifest.json` must be a top-level entry. If the archive contains a wrapper folder, Minecraft imports it without an error and the pack never appears in the list.
- **Entry paths use forward slashes**, always, whatever the host OS.
- No `__MACOSX`, no `.DS_Store`, no `Thumbs.db`.
- Classic 32-bit ZIP only. No ZIP64, no encryption.

### Manifest rules

`pack/manifest.py` is the only thing that writes a generated pack's manifest.

- `format_version` is `2`, exactly one `resources` module, no scripts.
- **UUIDs are derived, not random.** `uuid5` over a fixed Scaffold namespace and the pack's fingerprint, `core.Scaffold.fingerprint`: the name, every setting, and a digest and offset of every structure. An unchanged rebuild is therefore the same pack and replaces itself in the player's list, and any change makes a different pack. Never go back to `uuid4` here. `manifest.derived_pack_uuids`, from the name alone, is what a caller that hands over no fingerprint gets.
- The pack version is the Scaffold version, from `pyproject.toml`.

### Bundling TechPack

`pack/tech_pack.py` has three answers rather than two — `tech_pack.NONE`, `COMPATIBILITY` and `FULL`, chosen with `set_tech_pack(mode)`, the **TechPack** menu, or `--tech_pack none|compatibility|full`. The default is none: bundling somebody else's pack into yours is a deliberate act, not something that happens because a switch was left on, and the choice is remembered in `.scaffold`.

**Compatibility** merges TechPack's declarations onto the armor stand and ships none of its files, so a separately installed TechPack keeps working alongside the generated pack. **Full** copies its assets in as well, so the one pack is both. `mode_of()` still reads a bare `True` as full, because the setting used to be a switch and a stored one has to keep meaning what it did.

This exists because the two projects collide head on. Both replace `entity/armor_stand.entity.json`, a client entity file replaces the vanilla one rather than merging with it, and **between two packs only the higher in the player's list is read at all**. Applying Scaffold and TechPack side by side does not half-work: whichever sits lower is ignored completely. There is no ordering that runs both, which is why bundling is the only answer and why the README says to disable the standalone TechPack while a bundled pack is active.

The merge lives on `armorstand.merge_description`, not in `pack/tech_pack.py`, because it is about the shape of a client entity file rather than about TechPack. Scaffold wins every conflict, and one of them matters: `geometry.default` has to stay on `geometry.armor_stand.larger_render`, or the model stops drawing the moment the stand leaves the screen. Script order matters too — the pose controllers have to run before anything that reads the pose index, and TechPack's `spawner_radius` entry does exactly that.

Two things worth knowing:

- TechPack's own `scripts.animate` asks for `controller.pose` and `controller.wiggling` without declaring them in its `animations` map — the drift this file warns about, in somebody else's copy. Bundled with Scaffold, which does declare both, nothing is left dangling.
- Both projects ship `models/entity/armor_stand.larger_render.geo.json` and both declare the same geometry id. The files are currently byte-identical, which is the only reason `copy_assets` can skip the collision instead of resolving it. A test asserts they stay identical.

### The Tweaks menu

Bedrock Tweaks publishes small resource packs that each change one thing about how Minecraft looks. Applying one to a world is a matter of putting it above the others in the player's list, and **a Scaffold pack has no "above"**: every texture it uses is baked into one atlas as the pack is built. So a tweak is applied at that moment instead, as an overlay on the vanilla pack the atlas is read from.

`scaffold/lookups/tweaks.json` is the whole list of what is offered: an id, where it lives in the `bedrock_tweaks/` submodule, and any tweak it cannot be on with. `tools/vendor/tweaks.py --apply` stages each one's textures, `blocks.json` and `terrain_texture.json` into `scaffold/tweakpacks/<id>/` and commits them, the way TechPack's assets are staged -- the submodule is seven hundred megabytes and cannot be package data, and a pip install has to be able to offer the menu. **Re-run it after updating the submodule.**

`scaffold/tweaks.py` settles which are on and hands `ArmorStandGeo` the folders to search. **There is exactly one place a texture file is opened**, `texture_file`, and it tries each chosen tweak's folder and then the vanilla pack, `.png` before `.tga`. `blocks.json` and `terrain_texture.json` are merged the same way, entry by entry, which is what lets a tweak name a texture the vanilla pack has never heard of -- Age 25 Kelp ships a TGA and a twenty-sixth entry on a list that was a single string.

**Two of them paint the carried block rather than the placed one.** Minecraft can only tell waxed copper from unwaxed, or infested stone from stone, in the inventory, so Bedrock Tweaks puts that art in `carried_textures` and leaves `textures` alone. A ghost block *is* the placed block and there is no inventory near it, so `carried` on a table entry means the block's `carried_textures` are read as its textures. That is the only reason those two can be offered at all.

**A conflicting pair is settled in two places.** Sus Sand and Gravel and Suspicious Sand & Gravel Borders write the same eight files. The dialog switches one off as the other goes on, so somebody sees it happen, and `tweaks.chosen` does it again underneath because the settings file can be edited by hand. A conflict is declared from both ends and a test fails when it is not.

**The menu is a switch and a door.** The panel carries the master switch and a button, and `TweaksDialog` carries the grid. The two answers are remembered apart -- `tweaks` and `tweaks_on` -- because switching the lot off for one pack must not forget which ones somebody likes.

**The dialog is pictures, not prose.** Bedrock Tweaks draws a ninety-pixel icon per pack showing what it does, `tools/vendor/tweaks.py` stages those beside the art, and each cell is a short name with its switch beside it and the picture under both, so the names line up across a column and the pictures are as large as the room allows. The names are `font(size=13)`, the size the settings panel's own labels are, because a smaller one made the dialog read as a footnote. `App.warm_tweak_icons` decodes all thirteen on the first idle, so opening the dialog does no image reading. Nothing explains a tweak in words, because the picture does it in a quarter of the room. The short names are `tweak control <name>`; the pack's published title stays under `tweak <id>`, which is what the command line lists.

**Three columns of four, straight out of the table.** `tweaks.controls()` groups the table into controls and the dialog fills columns from that order, down and then across, so moving an entry in `lookups/tweaks.json` moves the cell. There is no layout anywhere else, and a test fails when the table stops making exactly twelve.

**A conflicting pair is one switch, not two.** `MultiSwitch` is CustomTkinter's own `CTkSwitch` with a third place for its knob: the drawing engine takes the knob's position along the track as a fraction, so the track, the border, the amber fill, the hover and the grey it goes when off are all inherited rather than imitated. **Do not draw a copy of a switch here.** The first attempt did, on a canvas, and it did not match the settings panel's switches in any state. A `control` on a table entry puts a tweak in a group and the group is one switch with a position per member; Sand & Gravel is the only group so far, and an off switch keeps the first member's picture so the cell still says what it is about.

**The credit sits on the last line, beside the buttons.** The licence asks for it to travel with the files; it is not something to read before deciding, so it goes where a footnote goes rather than above the grid.

**Their licence asks for two things and both are done.** A pack built with any tweak carries the credit in its description and a `credits.txt` naming what was used, and `scaffold/tweakpacks/LICENSE` ships beside the art with a `credits.txt` of its own, written by `tools/vendor/tweaks.py`, because the licence asks any project carrying the files for one. The credit lines are `tweaks.CREDIT_LINES`, word for word as the licence gives them. The licence also forbids selling a pack that includes the files.

### Clearer Redstone

The Tweaks dialog's second tab. Its options are entries in the same `lookups/tweaks.json` with `"tab": "redstone"`, staged into `scaffold/tweakpacks/<id>/` like any tweak, remembered in the same `tweaks_on` list and named to `--tweaks` the same way. The art is **Redstone Tweaks** by RexxStone, a Java pack published only on Modrinth. `redstone_tweaks/` is a submodule on `EvilSlimeLabs/redstone-tweaks-mirror`, an archive of every release: a weekly workflow there fetches a new one from Modrinth, checks it against Modrinth's SHA-512, and commits it unpacked under a tag of its version number, so the conversion can be run again whatever happens to the download. `tools/vendor/redstone.py --source redstone_tweaks` converts it and stages the textures, and is run by hand after moving the submodule to a newer tag, the way every other submodule is followed. Each converted texture is laid the way of the Bedrock one it stands in for by trying all eight turns and flips against it. Several things are drawn here in the pack's style rather than taken from it: cauldron and snow numbers, container counts, the crafter's locked slots, the dust in Bedrock's cross shape, and the hopper's floor painted into the top of Scaffold's solid bowl.

**An option is more than art.** A staged folder may carry `geometry.json` (whole format 2 families that replace the ones of that name, rules and simpler forms included), `definition.json` (block ids pointed at a family of the option's own) and `rotation.json` (a turn for a family it adds), which `tweaks.tables` merges and `ArmorStandGeo` applies. `tools/blocks/redstone.py` writes those by **copying Scaffold's own families and re-pointing faces by the file they read today**, so it runs in `tools/generate.py` after everything it copies; the overlays are never older than the tables they copy. A note block, a respawn anchor, a jukebox, a dispenser and a dropper get families of their own because their base family is shared by blocks the option does not touch.

**Clearer Redstone wins.** `tweaks.chosen` puts every redstone option after every Bedrock Tweak, whatever order they were asked for in. Nothing on one tab switches anything on the other off.

**A mark is a pseudo-block drawn at the block's position.** `scaffold/marks.py` reads a container's `Items` or a crafter's `disabled_slots` and answers `scaffold:fill` or `scaffold:crafter_slot` blocks with states of their own; `core` draws them only when an option's `definition.json` defines the id, and a mark that fails is passed over, not listed as skipped. The fill count is the **fewest items that give the comparator's signal**, as full slots and loose items out of 64 (`5+37`), so it depends only on the slot count and the signal and is drawn ahead of time, one sheet per slot count. `lookups/stack_sizes.json` says what stacks to 1 and to 16; Mojang's item data carries no stack size. A double chest is counted once, both halves over 54 slots, on its left half.

**Detail finer than a tile is a quad reading a window.** A count, a dust number and a note block's pitch are drawn at twice or four times a block's resolution on small quads a hair off the face, each reading 16 pixels of a larger picture through `window`. Their see-through texels still take depth, the trap described under the atlas, so they are kept as small as what they carry. **Redstone Tweaks' note block faces are 32 by 32**, and a note block is four quads a face.

**Its licence is CC BY-NC-SA 4.0**, and covers what is drawn here in its style too. `scaffold/tweakpacks/REDSTONE_TWEAKS_LICENSE` ships beside the art, a pack built with any option carries `manifest.REDSTONE_CREDIT` and a section of `credits.txt`, and the tab's footer carries the credit.

**A tweak's name is not translated.** The `tweak <id>` strings are the titles Bedrock Tweaks publishes those packs under, and the Clearer Redstone options' are kept the same way, so somebody looking one up on their site reads the name they will find there. `tests/test_languages.py` leaves them alone for the same reason it leaves `techpack` alone.

### Bedrock is case-sensitive; Windows is not

`textures/Density` resolves to `textures/density.png` on a Windows dev machine and resolves to nothing on Android, iOS and consoles, where it draws an untextured surface with no error anywhere. Match the case the files actually have on disk.

### Pack JSON is not JSON

Bedrock's parser is more permissive than `json.loads`, and the vanilla packs use it: `//` comments, trailing commas, and a UTF-8 BOM. The game's own `blocks.json` and `terrain_texture.json` can carry comments. Read them through `tools/jsonc.py`, never `json.load`, or valid content will be reported as broken. The trimmed `Vanilla_Resource_Pack/` in this repository is plain JSON and is safe either way.

### Replacing the vanilla armor stand

`pack/armor_stand_class.py` carries a hardcoded copy of vanilla's `armor_stand.entity.json` description with this project's geometry and textures added. A client entity file in a resource pack **replaces** the vanilla one; they do not merge. Vanilla's own animation and render controllers keep asking for the short names vanilla's copy declared, so every name the copy fails to carry over is a `can't find animation <name>` in the content log and a vanilla animation that stops playing.

This drifts on its own: Mojang adds a short name in an update and the hardcoded copy, which never changed, is suddenly missing it. When a Minecraft update lands, diff the `animations`, `scripts.animate` and `render_controllers` lists in `pack/armor_stand_class.py` against `entity/armor_stand.entity.json` in the game's resource pack, `bedrock-samples/resource_pack` by default.

---

## Keeping the vanilla pack current

`Vanilla_Resource_Pack/` is a trimmed vanilla pack, hand-merged over years. Some of its textures are **deliberately** not vanilla:

- biome-tinted textures are pre-tinted, because ghost blocks cannot run the colormap (`grass_top`, `tallgrass`, `vine`, the stems, `water_*_grey`, `redstone_dust_cross`); dust itself is drawn from the grey `redstone_dust_*_grey` pair, tinted by its power
- some are made more opaque so the ghost stays visible after the alpha pass (`glass_*`, `slime`, `hopper_top`)
- the water tiles go the other way and are made see-through, keeping their pre-tinted picture at one alpha, because vanilla gets water's transparency from the material it draws it with and a ghost block has none (`water_still_grey`, `water_flow_grey`, written by `tools/textures/water.py`)

`tools/vendor/vanilla_pack.py` encodes those rules. Run it against a submodule rather than copying files by hand, and read what it reports before applying anything. `--add-block` pulls a block's declarations and textures in from the game's resource pack, which is how a block from the update that just shipped gets in. **A data-driven block is missed by it**: it names its art in `minecraft:material_instances` in the behaviour pack rather than in `blocks.json`, so nothing walking from `blocks.json` reaches it and its textures have to be fetched by hand. 26.50's shelf mushroom, straw bed and red shrub are all like that. `tools/checks/blocks.py` resolves every declared block down to a texture file and reports what does not.

---

## Comments describe how things work, not how they were decided

Write comments that explain mechanism, logic flow, and anything a reader needs in order to change the code safely. **Do not** record decision history: what was tried and rejected, what a previous version did, which bug prompted a change, what was weighed against what. That belongs in the commit log.

Empirical facts about engine behaviour are worth keeping, stated as facts — "the X axis runs opposite to the Z axis here" rather than "this took three builds to work out".

Match the surrounding density: module headers carry a short orientation, non-obvious logic carries an inline comment. This codebase is lightly commented and inconsistently formatted; match the file you are in rather than reformatting around your change.

---

## Working habits

- **Isolate one variable at a time.** Changing two things and then attributing the result to one of them has produced wrong diagnoses here more than once.
- **Do not claim a causal link that has not been tested.** A hypothesis stated once becomes a fact if it is repeated; say "untested" and name the check that would settle it. The user tests in-game and reports back — give them the specific thing to look at, and say which observations would *not* prove it.
- **In-game behaviour is not knowable from here.** Rendering, placement, z-fighting and transparency need a live world. Geometry numbers and UV values can be checked here; how they look cannot.
- **Prefer Python patch scripts over shell heredocs** for multi-line source edits. `\n` inside a heredoc has repeatedly become a literal newline and corrupted string literals. Write the script with the Write tool, or anchor on text containing neither.
- **Re-compact JSON after writing it with `json.dumps`**, which explodes short numeric arrays across lines. The lookup tables are kept compact, and a reformatted table makes a one-value change unreviewable.
- **The test structures are the regression suite.** `tools/checks/coverage.py` builds against every one of them and prints what `get_skipped()` reports, which is the fastest way to see whether a lookup change broke something. It drives the real pipeline rather than reimplementing the state translation, so the answer is what a user's build would actually produce. It should print zero.

**Look at a block before believing it.** `tools/checks/render.py` draws one from `make_block`'s own output -- six flat views, one per face, orthographic and nearest sampled so a texture pixel is a countable square, and a three quarter view on the end for the shape. `--no-iso` drops the corner, `--iso` trades the flat six for all eight corners four to a row, `--all` draws both in three rows, and `-w <name>` draws one view on its own. `--low` draws the simplified form instead, which is the only way anything has ever drawn one — `tools/blocks/simplify.py` writes them and the manifest skips them on purpose, so a simple form that has stopped outlining the detailed one is invisible until somebody looks. `--open` opens the result. Pictures land in `renders/`, which is gitignored because every one of them redraws in a second. It catches what the tables cannot show: a face on the wrong half of a sheet, a window two pixels out, a picture on its side, a gap under a tilted slab. It never reads the lookup tables itself, and `tests/test_render.py` enforces that, because a renderer that translated them would only ever agree with them.

`--manifest` fingerprints every *form* of every block -- a banner's eighteen, a chiseled bookshelf's sixty-four, many thousands in all -- and compares them against `tools/checks/render_hashes.json`, which answers "what else moved" after a table edit. **Forms, not blocks:** a default-only sweep covers barely half the tables and slept through an ominous banner's face coming out cut in half. The test suite runs the same comparison. **Re-record it with `--manifest --update` and commit the manifest in the same change that moved the blocks**, so the diff carries both. It **does** model the three things that separated it from the game, all of them settled by building blocks and looking: the x mirror, so a block asymmetric across x is drawn on the side the game puts it; the turns, a bone's y the other way from `spun`; and every face reading the right way round from outside, which makes the two faces of a plane mirror each other. The last two were pinned with `tools/checks/compass.py`. `tests/test_render.AgreesWithTheGameTests` holds them against blocks whose look is settled — a brewing stand's arms, a sunflower's head, a marked banner's front. It does not model z-fighting, transparency over a world, or lighting; those still need a world. `docs/Editing Blocks.md` has the details.

---

## Running, testing and building

```bash
python -m scaffold                                    the window
python -m scaffold --structure in.mcstructure --pack_name Name    CLI
python -m unittest discover -s tests -t .              tests
python build.py                                        release zip in dist/
python build.py --publish                              sign it into the update repo
python build.py --unpublish 1.2.3                      take the newest release back off
python build.py --init-trust                           create the signing keys, once

python -m tools.generate                               every generator, in order
python -m tools.generate --list                        what that runs, and when
python -m tools.generate blocks                        only the block tables
python -m tools.blocks.names --report                  what a block list still cannot name

python -m tools.checks.coverage                        what the test structures drop
python -m tools.checks.blocks                          what does not resolve
python -m tools.checks.generators                      run the generators twice and diff
python -m tools.checks.upgrades --schema <clone>     the old-block translation against PocketMine's schema
python -m tools.checks.compass                        a pack that shows in game how the tables map onto the world
python -m tools.export.structura <out>                 the tables for a Structura 1.7 checkout
python -m tools.export.handoff                         handoff/structura/: the guide, the format 2 tables and a converter that runs alone, for Structura's developer; git ignores it
python -m tools.checks.gallery --tweak-world          every block a Bedrock Tweak or Clearer Redstone option changes, a plot per tab, waterlogged where it can be
python -m tools.checks.gallery --low                  a block of every family with a simpler form, built with low geometry
python -m tools.checks.gallery --dust-world           redstone dust: the dust structure, every kind of join, and a circuit drawn plain and with each dust tweak
python -m tools.checks.gallery --water-trials         waterlogged blocks drawn five ways, to find why water hides what stands in it
python -m tools.checks.gallery --fill-trials          a filled container per facing, its count drawn three ways
python -m tools.checks.gallery --all --every-block     a world of every block, real beside its ghost
python -m tools.find <search>                          find a block by id, name or family
python -m tools.find texture <search>                  find a texture, as an overwrite entry names it
python -m tools.render <block>                         draw one block, six ways round
python -m tools.render <block> --low                   draw its simplified form instead
python -m tools.checks.render --manifest               which blocks changed how they look
python -m tools.app.screenshots                        refresh the README's shots
python -m tools.vendor.tech_pack                       stage TechPack's assets
python -m tools.vendor.tweaks --apply                  stage the Bedrock Tweaks
python -m tools.vendor.redstone --source redstone_tweaks --apply   stage Clearer Redstone from Redstone Tweaks
python -m tools.vendor.vanilla_pack                    sync the trimmed vanilla pack
```

`lookups/` and `Vanilla_Resource_Pack/` are opened by relative path, so all of these must run from the repository root, which is also what makes `python -m tools.…` resolve.

**A generator says what a table is, never what to change it by.** One that reads a table, adjusts it and writes it back is right exactly once: run again it is wrong, and the build regenerates everything before every compile, so the answer depends on how many times the build has run. A carved pumpkin faced a different way on alternate releases because `tools/blocks/faces.py` added a half turn to its own output each time. Nothing catches that by reading the source -- deriving one family from another is ordinary, and `faces.py` builds `azalea` and `vault` out of `cube` -- so `tools/checks/generators.py` runs them twice and diffs what they wrote. It rewrites the tables, which is why it is a command and not a test.

**`tools/generate.py` owns the order, and `build.py` runs it.** A table generated by an older version of the script that writes it is the kind of thing nobody notices until a block is wrong in game, so the build regenerates everything before it compiles anything; `--skip-tools` is the exception. Three are deliberately left out of it: `app/screenshots.py` needs a window on screen, and the scripts under `vendor/` copy out of the submodules and Redstone Tweaks, whose diffs are meant to be read before they are applied.

---

## Reference

- Bedrock samples: the `bedrock-samples/` submodule, from https://github.com/Mojang/bedrock-samples
  - `behavior_pack/shapes/<block>.json` carries Mojang's own voxel shape for a block, one file per facing, as boxes in pixels. **Read that before measuring a shape off a texture** — it is where the shelf's five deep case and four thick boards came from, after four shapes guessed from the sheet. It is a collision shape, so it gives sizes and positions and says nothing about how a piece is painted.
  - `resource_pack/models/blocks/<block>.geo.json` carries the model itself for a data-driven block, which does say how it is painted. `docs/Block Notes.md` has what converting one costs: the UV space is not the texture size, a negative `uv_size` is a rectangle measured backwards, and the model faces a different way from this project's default.
  - `behavior_pack/blocks/<block>.json` is the block itself — its geometry, its textures and the permutation each state picks.
- Community documentation: https://wiki.bedrock.dev/
- Vanilla listings: https://learn.microsoft.com/en-us/minecraft/creator/reference/content/vanillalistingsreference/?view=minecraft-bedrock-stable

# Writing Prose

Explore widely, output narrowly, keep conclusions simple.

You write brief, declarative prose, without personal pronouns, unsolicited additions, or em dashes.

You should prioritize perspicuity. The answer goes in the final sentence.

# Messages to Me

I am scanning your messages while doing something else. Long messages get skimmed, and the line that needed an answer gets missed. You are writing a status note, not marketing copy.

Put the result in the first line.

Keep only what I will act on. Cut the request I already made, the steps I watched you take, and any summary that repeats the first line.

Be precise. Use the real file name, the real value, the real error text.

Put questions last, each on its own line.

Always keep risks, mistakes, and guesses you made. Those stay in even when everything else goes.

Use plain sentences. One idea each. State the fact and stop.

Do not write for effect. If a sentence sounds quotable, rewrite it as a plain statement. Avoid:
- "load-bearing", "worth stating plainly", "worth naming", "worth flagging", "full stop", "carries the argument", "the trap is", "the real question is", "the honest answer is", "to be clear", "let me be direct"
- "real" or "actual" used for emphasis, like "a real tension" or "the actual problem"
- Any sentence that announces a point instead of making it. If a line can be deleted without losing information, delete it.
- "This is not X, it is Y" and "it isn't just X, it's Y"
- Sentence fragments used for emphasis, like "Not a bug. A design choice."
- Em dashes. Colons and semicolons used as a dramatic pause. Write "and", "but", or "because", or start a new sentence.
- Opening with agreement or praise, like "You're absolutely right" or "Great catch".
- Grading your own work: "successfully", "perfect", "now works flawlessly", "production ready".

Say what changed and what it means, in the words a coworker would use out loud. A good update reads like this:

> auth.ts: token refresh now runs only within 5 minutes of expiry. It used to run on every request. I also added logging for the 401s that were being dropped silently.

> Do you want the refresh window at 60 seconds instead of 5 minutes?
