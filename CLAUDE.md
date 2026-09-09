# Working on Scaffold

Standing rules and the project information worth having before touching anything.

---

## The project

**Scaffold** — Previously called Structura, and inspired by Litematica. Scaffold is a Python desktop program that turns a `.mcstructure` file into a Bedrock resource pack (`.mcpack`). The pack replaces the vanilla armor stand client entity with one that renders when off screen and carries every block of your structure as a bone in its model, drawn as semi-transparent "ghost blocks" so you can see where the real blocks go.

There is no behaviour pack and no script API anywhere in this project. Whatever the generated pack does, it does with geometry, render controllers, animations and textures.

## Release and distribution

The repository is public on GitHub. Releases are built locally with `python build.py`, not by CI, and uploaded to the project's own GitHub releases by hand. **Do not add build or release workflows.** The package is published to PyPI as `mcpe-scaffold`.

**The window is Windows only.** The release is built on a Windows machine, so `Scaffold.exe` and `Scaffold-cli.exe` are the only executables that exist. macOS and Linux get the command line through `pip install mcpe-scaffold`. Do not write documentation promising a Linux or macOS build; the README claimed one for a long time and it has never been produced.

**Upload `dist/SHA256SUMS.txt` with the binaries.** It is what somebody who downloaded the zip in a browser checks against. The program's own updates do not read it any more; they check signatures instead.

**Building a release needs a C compiler.** Nuitka compiles the program to C, so `build.py` asks for `--zig`, which Nuitka downloads and keeps up to date itself. Visual Studio 2022 works if it is installed; MinGW64 does not, because Nuitka stopped supporting it at Python 3.13. Nothing is needed to *run* Scaffold from a checkout.

**The program updates itself over TUF, and a release must be signed.** `scaffold/updates.py` is a `tufup` client. It fetches signed metadata from `https://evilslimelabs.github.io/Scaffold/metadata/`, and the archives from `targets/` beside it, and will not install anything the metadata does not vouch for. `python build.py --publish` is what signs a build in; `--init-trust` creates the keys, once.

**The private keys live in `~/.scaffold-keys` and must never be committed.** Anyone holding the targets key can sign a release every copy of Scaffold in the world will install. `scaffold/trust/root.json` is the public half and *does* ship, compiled into the executable, because it is the one piece of metadata an update cannot fetch.

That whole feature rests on the repository being **public**, because the metadata and the archives are fetched without credentials, and GitHub Pages on a private repository is a paid feature besides. While it is private every check comes back as "up to date", quietly, which is the same answer as no network.

**GitHub Pages serves it from an orphan `gh-pages` branch, and `pages/` is a worktree on it.** `python build.py --init-pages` makes that worktree once: the branch shares no history with `master`, because the site is built artifacts and has no business carrying the source's. In the repository's **Settings -> Pages**, set **Source** to *Deploy from a branch* and **Branch** to *gh-pages* with folder */ (root)*, which serves `pages/metadata/` and `pages/targets/` at the address `scaffold/updates.py` reads. A push is live in under a minute and there is nothing to approve.

**`.nojekyll` and `index.html` are written by the build**, by `pages_scaffolding()`, so they are there whichever command made the tree. Pages runs Jekyll over a branch unless that empty file says not to, and Jekyll drops anything whose name begins with an underscore; nothing tufup writes does today, so it is insurance rather than a fix, and it skips the build besides. The index exists because the address is a real one somebody may open, and without it the root of the site is a 404 that looks like the update server is down.

---

## Layout

Everything importable is one package. `from scaffold import Scaffold` is the whole API, and a service that wants to run Scaffold vendors one directory rather than fourteen paths.

Inside it, the pieces are grouped by what they are for: `pack/` turns a structure into a pack, `cli/` is the command line, `ui/` draws the window. **None of them import each other.** What more than one of them needs — the settings, the paths, the language tables — sits beside them at the top of the package, and so does `core.py`, which is what drives all three.

**`cli/` must not reach into `ui/`.** That is what lets the command line build leave the interface out, and `build.py` passes Nuitka `--nofollow-import-to=scaffold.ui` for that build, so it comes out small rather than quietly growing by six megabytes if it ever does. The language tables sit outside `ui/` for the same reason: `settings` needs them, and both sides need `settings`.

``` build.py                 local release build

scaffold/               everything importable, and everything it reads __init__.py              exports Scaffold; never mentions the window __main__.py              entry point: dual use -- arguments build, none opens app.py                   the dual use decision, so __init__ stays clean core.py                  the pipeline: structure in, pack folder out settings.py              settings, and the strings both sides label things with lang_parse.py            reads lookups/lang/, one file per language system_locale.py         what language the desktop is set to, for a first launch updates.py               the tufup client: whether a signed release is out paths.py                 where data lives, in a checkout and inside the bundle version.py               reads the version out of pyproject.toml jsonc.py                 reads Bedrock's permissive JSON; shipped, not a tool

  cli/                     the command line __main__.py              entry point: the command line alone, no window arguments.py             what the program accepts, for both entry points commands.py              building a pack console.py               output from a build frozen without a console

  pack/                    building a pack structure_reader.py      .mcstructure NBT parsing, and block entity data armor_stand_geo_class.py block -> geometry and UV; the biggest and trickiest armor_stand_class.py     the armor_stand client entity animation_class.py       layer pose animations render_controller_class.py / big_render_controller.py manifest.py              the generated pack's manifest tech_pack.py             folds the TechPack submodule into a generated pack

  ui/                      the window scaffold_gui.py         the window, on CustomTkinter ui_icons.py              the drawn interface glyphs and the pack icon control ui_fonts.py              registers the bundled faces, one per language lang_icons.py            the language picker's code badges

  lookups/                 the lookup tables this project owns lang/                    one .lang file per language, named for its locale trust/                   root.json, the TUF root an update is checked against Vanilla_Resource_Pack/   trimmed vanilla pack textures are read from fonts/                   the three bundled faces, with their licences images/                  the two pictures the running program opens techpack/                TechPack's assets, staged from the submodule

art/                     source art the icons are generated from, and readme_header.png, which the README opens with; nothing here goes into a build tools/                   the scripts that build the data, and the ones that check it; nothing here ships, and every one is run from the repository root as a module generate.py              runs every generator, in the order they need find.py                  find a block, or a texture, by any of its names; `KINDS` is where another search goes render.py                shorthand for checks/render.py, which is the long name for the thing done most blocks/                  the block lookup tables geometry.py              Cube, build, spun, unwrap, on_sheet tables.py                edit one family, leave the rest byte for byte mounted.py               bells, signs, doors, campfires, pots, brewing growing.py               crops, eggs, compost, coral crossed.py               fire, dripstone, sulfur spikes furniture.py             beds, lecterns, conduits heads.py                 the mob heads containers.py            the shulker boxes banners.py               standing and wall banners bookshelf.py             the sixty-four filled states statues.py               the copper golem's four poses faces.py                 a texture per cube, per face simplify.py              the low geometry forms textures/                banners.py, beds.py, string.py app/                     icon.py, fonts.py, languages.py, transforms.py, screenshots.py vendor/                  tech_pack.py, vanilla_pack.py -- staging submodules checks/                  blocks.py, coverage.py, render.py, generators.py, api.py, speed.py tests/                   unittest suite test_structures/         .mcstructure files to generate against docs/                    user-facing documentation, including Block Notes.md, which is what to read before touching a block ```

`CommunityVanillaResourcePack/` and `be_tech_pack/` are git submodules and neither is read at run time. The community pack is reference material for `tools/vendor/vanilla_pack.py` and `tools/checks/blocks.py`. TechPack is the source `tools/vendor/tech_pack.py` copies from — `scaffold/techpack/` is what the program actually reads.

---

## Two builds, one command line

`scaffold/__main__.py` is dual use: give it a structure and a pack name and it builds one in the terminal, give it nothing and the window opens. `cli/__main__.py` is the same command line with the window left out of the bundle. Neither holds any argument parsing of its own -- both call `cli.main`, which returns `cli.NOTHING_ASKED` when there was nothing to act on and lets the entry point decide what that means.

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
- **A `CTkToplevel` gets Tk's default icon** unless told otherwise, and it has to be told after the window exists. `apply_icon()` does it on a delay, and the main window repeats it because CustomTkinter resets the icon while it finishes setting up.
- **The build runs on a worker thread** and talks back through a queue that the main thread drains in `after()`. Tk is not thread safe; nothing off the main thread may touch a widget.
- **The status line is always saying something.** A finished build's message is `sticky` so re-validating does not wipe the one line that says it worked.
- **Nothing is written over without being asked about, and the asking happens before the build runs.** `settle_collisions` compares `core.outputs` against the output folder and offers overwrite, a suggested free name, or stopping; a rename is checked again, because the name typed in may collide too. Doing this at the end would mean running a build nobody wanted.
- **A write that fails is a question, not a lost build.** The worker hands `core.set_retry` a callback that puts the question on the same queue every other message uses and waits on a queue of its own; `_drain_events` opens the dialog on the main thread. Nothing else is drained while it is up, which is what the build wants. A cancel sets `App.cancelled`, so the error the write then raises is reported as a choice rather than as a fault.
- **Big build mode borrows the offset fields and the name tags.** Their values are stashed and handed back when it is switched off, so flipping it twice leaves the window exactly as it was. Anything else that mode takes over has to do the same.
- **The window does not resize.** CustomTkinter draws every widget on a canvas of its own and repaints it whenever its size changes, about a millisecond each; with the widgets this window has, one step of a drag cost a quarter of a second. An empty window of the same kind manages six. It is a fixed `WINDOW_WIDE` by `WINDOW_TALL`, and everything inside it is a constant too -- nothing measures a neighbour and applies the result, which used to settle in a visible flicker.
- **One scale, chosen once.** CustomTkinter otherwise makes the process per-monitor DPI aware and compensates in software: it fades a window to fifteen percent alpha and rebuilds every widget when it changes monitor. `_fix_scale()` declares the process aware of the *system* scale and hands CustomTkinter that number, so text stays sharp and nothing is ever rebuilt.
- **"Transparent" is not transparent.** A `CTkLabel` or `CTkEntry` with `fg_color="transparent"` fills its rectangle with the colour it finds behind it. A child as tall as its parent therefore paints over the parent's border. Keep children inset, and use `draw_every_pixel()` on anything with a rounded border -- the drawing code floors a widget's size to an even number first, and an odd one loses its last row.
- Screenshots in the README are generated by `tools/app/screenshots.py` from the running window. Change the interface, re-run it. It refuses to save unless the foreground window belongs to its own process, so leave the machine alone while it runs.
- **Settings live in `.scaffold`** -- next to the executable if one is there, which makes the program portable, and otherwise in the home directory, not beside the program, so they survive replacing the executable and work when it is run from a folder the user cannot write to. An older `settings.json` is read once to carry a choice over.
- **What is remembered describes the machine or the person, not the pack.** The theme, the language, the output folder, the TechPack mode, the low geometry switch and the transparency slider are stored; the pack name, the description, the icon and the offsets are not. Low geometry and transparency are both about the person in front of the screen rather than the pack: whether a client can afford detailed ghost blocks depends on the hardware and on Vibrant Visuals, and how far through a ghost block somebody wants to see depends on their eyes and their monitor. Neither answer changes between structures. Every setter in `settings.py` writes the file, and `tests/test_interface.py` fails when a key in `DEFAULTS` has no setter it checks.
- **The transparency slider fires on every pixel of a drag.** `set_transparency` writes only when the value actually changed, or a single drag is a hundred writes of the settings file.
- **A collision is answered with a name, not a field to type one in.** The overwrite dialog offers overwrite, the first free name, or stopping. It used to carry an entry box, which duplicated the pack name field in the window behind it and could itself be given a name that collided, which is what made the dialog ask twice. `free_name` is handed a test for what counts as taken, and the caller passes one that checks **every** file the build would write: checking only the `.mcpack` suggested names that collided on a block list file, and with nowhere left to type, that is a loop with no way out.
- **"Show in folder" points at the file and closes the dialog.** Explorer and Finder both take a file and select it, and a selection that fails for any reason falls back to opening the folder, because the point of the button is to get somebody there. Linux has no equivalent, so the folder is the whole answer. The dialog goes because it has said what it had to say, and a modal left in front of the window somebody has just been sent away from is one they have to come back and dismiss.
- **An update is signed, and that is the whole point of the mechanism.** The old updater downloaded an asset and checked it against a `SHA256SUMS.txt` published beside it, which proves the file arrived whole and nothing else: the fingerprint travels with the build it describes, over the same connection, from whoever is answering. TUF signs the metadata with keys that never go near the server, so a release has to be the project's to be installed at all. **Do not reintroduce a fingerprint check as though it were a signature.**
- **The trusted root ships inside the executable.** `scaffold/trust/root.json` is what everything else is checked against, so it is the one thing that cannot be fetched. `updates.client()` copies it into the client's metadata directory **only when there is nothing there**, because writing it every time would undo a root rotation that had already reached that machine.
- **The client's working files are in the home directory, not beside the executable.** `~/.scaffold-updates/` holds the verified metadata and the downloaded archives. A copy installed in Program Files cannot write beside itself, and that is exactly the copy whose update must not fail.
- **The install is a copy, and it outlives the process.** `tufup` unpacks the archive and starts a script that robocopies the new files over the old ones and launches the new build. Scaffold passes its own batch template, because tufup's does not restart the program, and `CREATE_NO_WINDOW`, because tufup opens a console to run it in. The script keeps retrying, so the window can take its time shutting down: a running executable cannot be written over on Windows, but one on its way out will be free by the time the copy reaches it.
- **tufup ends the install by calling `sys.exit`, and that has to be caught.** The window runs the install on a worker thread, where `sys.exit` ends the thread and leaves the program running on the file being copied over. `updates._put_in_place` catches it, the window is told it worked, and the window leaves in its own order.
- **A pre-release is offered pre-releases; a final release is not.** `updates.channel()` reads the running version, so somebody on a release candidate keeps being offered them instead of hearing there is nothing new until the final ships. tufup filters them out by default.
- **`clear_displaced` is for the updater this one replaced.** Scaffold used to rename the running file to `Scaffold.exe.old`. Nothing writes one any more, and this can go once nobody is running 3.0 or older.
- **A reason handed back is the name of a string, not a string.** `install_latest` returns `(reason, detail)` so the window can put it in the running language, and a name the table does not carry reaches the screen as itself. `tests/test_updates.py` reads the source for every `"update ..."` it names and fails when one is not in `en_US.lang`.
- **The first launch starts in the desktop's language.** With no language remembered, `system_locale.read()` asks the machine and `settings.match_locale` turns the answer into one of the files: that locale, then any file for the language, then English. It happens once, because the guess is written to the file like any other choice, so somebody who then picks English on a Spanish machine keeps English.

### The generated pack's name and description

`pack/manifest.py` owns both. The name shown in game is prefixed -- `Scaffold: <what the user typed>` -- but **the UUID is still derived from the bare name**, because folding the prefix in would have made every pack built by an older Scaffold look like a different pack to the game and left players holding two copies.

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

## Every bump ships with a summary and a commit message

Hand over both in the same reply as the bump, without being asked, at the end after describing the work. They are written for different readers and should not be the same sentence.

**Release summary** — one or two sentences on what is new and what changed, in prose. Add a short clause only if something breaks for existing users and they have to act on it. Not a formatted document, not a section per subsystem, not an artifact. Write it directly in the reply.

**Commit message** — one line, a few words, in the user's own log style. No body, no bullets, no test counts. Real examples from the log:

``` First release Bugfixes Fixed and updated items Revamped the compass to the ledger. More item fixes. Bracket customization. Changed Sigil watermark in the menu ```

Brevity here is about summaries and commit messages only. Detailed technical explanation while working through a problem is welcome.

---

## How a pack gets built

`Scaffold(pack_name)` makes a folder, then:

1. `add_model(name_tag, file)` and `set_model_offset(name_tag, offset)` register each structure. **`set_model_offset` is not optional** — the offset defaults to `None` and the geometry builder subscripts it. 2. `generate_with_nametags()` reads each structure, and for every non-air block calls `armorstandgeo.make_block`, which resolves the block through the lookup tables into cubes with UVs and appends them to a per-layer bone. 3. `compile_pack()` writes the manifest, copies the icon, zips the folder and renames it to `.mcpack`.

Blocks are batched into bones named `slice_<y>`, parented to `layer_<y % 12>`. The layer bones are what the pose animations scale up and down, which is how shift-right-clicking an armor stand steps through the build.

### Driving it from something other than the GUI

`scaffold.core` is the API any front end uses, and it is deliberately the only thing a future service would need. Everything it produces is available as data as well as as a file, because a service wants the former:

| Call | Gives you | | --- | --- | | `compile_pack()` | the path to the finished `.mcpack` | | `get_nametags()` | the name tags in the pack | | `get_block_lists()` | `{name tag: {block: count}}` | | `get_material_list()` | every block the pack needs, summed across models | | `get_skipped(write_file=False)` | `{block: {variant: count}}` that could not be built | | `get_unique_blocks_count()` | how many distinct blocks the pack covers | | `get_lookup_version()` | which build of the tables produced it | | `core.outputs(target, tags, block_lists, big)` | every file a build under that name would write |

Settings a caller can pass before generating: `set_opacity`, `set_description`, `set_icon`, `set_model_offset`, `set_list_labels`, `set_low_geometry` and `set_tech_pack`. Every one of them is in the fingerprint, so two packs that differ by any of them are different packs. `set_retry` is the exception: it describes what to do when a write fails rather than what the pack contains, so it is not part of the fingerprint.

**`core.outputs` has to agree with what the build writes.** It is what a front end asks before it starts, and it never looks again, so a file the build writes without being named there is one that gets written over with nobody asked. Both sides go through `pack_file` and `block_list_file`, and `tests/test_overwrite.py` builds a real pack and compares the folder against the list.

**A failed write is handed back, not thrown.** `set_retry` takes a callback given the `OSError` and the path, and returning True runs the same write again. Windows refuses to write a file another program holds open, and a pack the player still has loaded is exactly that. With no callback the write raises, which is what the command line wants: it refuses by name and points at `--overwrite`.

Keep it that way. A hosted version of Scaffold belongs in its own project that imports this one; anything that knows about a queue, a bucket, a bot or a user account does not belong in this repository. The previous attempt lived here as `lambda_function.py` and had to reach into `structure_files[...]["block_list"]` because the accessors above did not exist.

**A block that fails to resolve is not an error.** `make_block` raises, `_add_blocks_to_geo` catches it, and the block is recorded in `unsupported_blocks` and reported in the skipped list. That is why a missing `block_definition.json` entry produces a silently incomplete model rather than a crash — and why the audit in `tools/` matters.

### The pack icon

`pack_icon.png` must be a valid PNG, square, and **256×256** — the size Microsoft documents for the pack selection screens (`CPACKICON101`–`104` in the Creator Tools validation reference). There is one per pack root; a subpack carries its own, nothing else should.

`tools/app/icon.py` regenerates both icons the project ships — `lookups/pack_icon.png` at 256×256 and `images/pack_icon.ico` from 16 px to 256 px — by rendering the isometric S cube over `background_slimelab.png`. The grid colour, its alpha and the S material are the constants at the top of that file. Nothing is stored that the script cannot rebuild.

**No tool checks the icon rules.** This section used to claim the audit did; it never has. If it matters, the check belongs in `tools/checks/blocks.py`.

### High and low geometry

Every ghost block is geometry the client lights and draws, and Vibrant Visuals makes that markedly more expensive. A shape family may declare a simpler form of itself under its own name plus `armor_stand_geo_class.LOW_SUFFIX` — `bell__low` beside `bell` — and `simplify()` swaps to it when the pack is built with `set_low_geometry(True)`. A family without one is drawn as it always is, which is most of them.

`tools/blocks/simplify.py` generates those forms. **Re-run it after changing a detailed shape**, or the simple form is still the old one's outline.

### The lookup tables

| File | What it holds | | --- | --- | | `lookups/block_definition.json` | block id → shape family. Missing entry means the block is skipped | | `lookups/block_shapes.json` | shape family → cube sizes, offsets and the group pivot, per variant | | `lookups/block_uv.json` | shape family → per-face UV sizes and offsets, per variant, plus texture overrides | | `lookups/block_rotation.json` | shape family → rotation for each rotation state | | `lookups/nbt_defs.json` | block state name → what it means (`rot`, `top`, `variant`, `data`, `shape`, `open_bit`, `hinge`) | | `lookups/variants.json` | variant state value → index into a terrain_texture list | | `lookups/block_list.json` | block id → the name shown in the block list, and the headings the list is grouped under | | `lookups/lang/<locale>.lang` | UI strings, one file per language, named for its locale |

### The block list

**A block list is counted by block id and named only as it is written.** `structure_reader.get_block_list` counts ids, with the variant on the end where a block has one -- `minecraft:red_flower/poppy`, because a poppy and an allium are one id and two things to gather. `block_list.py` turns those into names and headings at the last moment, out of `lookups/block_list.json`. A count already turned into a name cannot be regrouped or renamed afterwards, which is the whole reason the naming happens last.

**Counts are summed by the name, not by the id.** Several ids are one thing to gather -- a double slab and a slab are both slabs, and the table calls them the same -- and two lines for one item is arithmetic at a chest.

**A user can supply their own file, and it is looked for where the settings file is looked for**: beside the executable, then the home directory, as `.scaffold-blocks.json`. **Nothing is ever written to either place.** The file is Scaffold's to read and the user's to write, and a program that rewrites the file somebody is editing is a program that loses their work.

What is found is **merged over** what ships rather than swapped for it, and the two halves merge differently because they are different shapes. `names` is a dictionary, so one entry replaces one block's name and leaves the other thousand alone: renaming one thing is a four-line file. `categories` is an ordered list and the order is the whole meaning of it, so a file carrying any categories at all replaces the list outright. Half a list of categories merged by name into another is not something anyone could predict the result of.

Category patterns are shell-style globs on the block id, matched whole, with the `minecraft:` optional and **first match wins**, so the order in the file is the order they are tried. Anything unmatched lands under `Other` rather than being dropped: a block left off a shopping list is a wall somebody cannot finish.

**A pattern is matched against the variant as well as the id, and a star does not cross the slash.** Some blocks keep what they are made of in the variant: every stone slab Bedrock wrote before the block names were flattened is a `stone_block_slab`, and only the variant says whether it is quartz or cobblestone. `*/quartz` means "a quartz one of anything", which only works because the star stops at the separator -- otherwise `*/brick` would match `stone_block_slab/nether_brick` by swallowing the slash and half the variant.

**The headings group by material, not by shape.** Wood is a heading per wood type and stone a heading per stone, so everything oak is one pile rather than every stair in the build sitting together; concrete, wool, glass and terracotta each have their own; and the things gathered as items -- flowers, crops, saplings, fungus -- are matched first so they never land in a block heading. The order that follows from that is load-bearing three times over: the item-like categories come first, `Redstone` comes before anything matching `*stone*` or redstone and glowstone are "stone", and a type whose name contains another's goes above it, which is why Dark Oak and Pale Oak precede Oak and Red Sandstone precedes Sandstone.

`block_shapes.json` and `block_uv.json` must agree. A variant that exists in one and not the other silently falls back to `default`, which is how a snow layer ends up wearing a full-height texture. Add variants to both.

**Not every state is in the states.** A copper golem statue keeps its pose in the block entity beside the block, the way a sign keeps its text, so four statues in four poses share one palette entry. `structure_reader.get_block_entity` reads `block_position_data` and `scaffold.core.ENTITY_SHAPES` names the fields worth reading — a block entity carries a great deal that has nothing to do with how a block looks.

**A block drawn with an entity's model takes the model, not a box measured off a picture.** `make_block_forms.unwrap` is the way Bedrock lays a box out on a sheet and `make_block_forms.spun` is the turn a bone or a cube carries; the mob heads and the copper golem statue both go through them. The statue's four poses are four geometry files in the community submodule — `copper_golem`, `copper_golem_sitting`, `copper_golem_running`, `copper_golem_star` — not one shape leaned four ways.

**A block entity may hold another whole block, and then one position draws two.** A flower pot keeps what is planted in it as `PlantBlock`, a compound with a name and states of its own; `core.ENTITY_HOLDS` names that field and `core.Scaffold._drawn_at` returns the pot and the plant. The plant is then drawn by its own family with its own textures, which is why every pottable plant works without a variant apiece.

**A second field of a block entity may say the first one does not apply.** A banner's colour is `Base`, but an ominous banner is not a colour at all and a banner carrying `Patterns` cannot be drawn from a dye either, because a ghost block cannot composite six patterns as a pack is built. `core.ENTITY_INSTEAD` names the fields that replace the form outright, and both of those banners get a sheet of their own from `tools/textures/banners.py`: Mojang's own illager banner, and Scaffold's S as the stand-in for a design.

**`Base` counts the dyes, not the wool.** The two orders are opposite — `Base` 0 is black and 15 is white — so a banner read as wool comes out the colour across the wheel from its own, white as black and lime as purple.

**A picture bigger than a tile is drawn on a grid of quads.** Only sixteen by sixteen of a texture becomes a tile and a quad reads one tile, so anything needing more resolution than that is cut into quads that each read a tile of their own. A marked banner's cloth is two quads across by four down, and `tools/textures/banners.py` writes the design at the size that grid reads, under vanilla's own sheet so the post and the bar are still read by the windows every other banner uses. **The design is written mirrored and read back mirrored**, which is what `tools/textures/banners.py` means by "the image needs to be mirrored for the face we are putting it on": the sheet holds the picture the wrong way round and **both** faces that show it turn it back -- not only the one a banner is looked at. The two faces of a plane already run opposite each other, which is what makes the back come out as the mirror of the front once both are turned; leaving the back alone cancels one flip against the other and splits it. **Mirroring a picture cut into columns turns the columns round as well as flipping each one** -- the mirror of two columns side by side is the right one mirrored on the left, not each one mirrored where it stands. Flipping only the tiles cut an ominous banner's face down the middle and swapped its halves. Rows need none of it, because a mirror is left to right. **Only those two faces carry the picture**: the other four are the cloth's edges and the seams between the quads, a pixel wide, and they take the banner's own base colour from the same corner a dyed banner reads.

**A rotation table needs every form of the value.** Bedrock gives some blocks a numeric `direction` and others a `minecraft:cardinal_direction` string, and a table with no entry for the value a block carries draws it unrotated, silently. That is what made every door face the same way. The numbering is not the same for every block either — see `docs/Block Notes.md`.

**A form may number its rotations differently from its family.** A `"<variant>:<value>"` key in `block_rotation.json` is read before the plain value. A hanging sign carries two rotation states and only one applies: fixed to the block above it turns with `ground_sign_direction` in sixteen steps, and swinging or wall mounted it turns with `facing_direction` in four, so 2 means something different in each. `core._process_block` picks the state.

**A family turns about the middle of its block.** `center` in `block_shapes.json` is that pivot. A family whose cubes all sit at one edge is tempting to pivot on that edge instead, and that takes the block out of its own block: a door pivoted on the plane of its own panel ended up half in the block beside it a quarter turn round.

**A colour that is a whole colour is tinted into the atlas as the pack is built.** A cauldron's dye is an RGB in its block entity rather than one of a list, so nothing in the tables could name a texture for it. A texture written `<name>~tint` takes the block's own colour, `core.ENTITY_TINTS` says which field carries one, and `armor_stand_geo_class.extend_uv_image` multiplies the tile as it loads it. The atlas is keyed by the whole name, so each dye lands there once.

**One texture per cube, not per block.** A block built from several cubes cannot use Bedrock's six face textures directly; every cube would get the same six. The `overwrite` entry in `block_uv.json` gives a texture per cube per face, and a value written `@up` or `@down` means "whatever this block declares for that face", which is how one entry serves every wood a sign comes in.

**A small picture in a full sized file is the same trap.** `bell_side` is a 16×16 file with the bell drawn in an 8×9 corner of it, so a face working its own window out from where its cube sits reads empty space and the bell is a flat plate. Both pieces of the bell name their rows. `heavy_core.png` is the version of that with three 8×8 pictures in one 16×16 file — top, bottom, side — and a quarter of it empty. Every one of a dried ghast's twenty four textures is a 10×10 picture in a 16×16 file, four to a face, one per `rehydration_level`.

**A sheet in `textures/blocks/` still looks like a tile.** `decorated_pot_base.png` is 32×32 and holds the neck's unwrap over the body's top and bottom; `flower_pot.png` holds the rim over the wall. Faces left to work their window out from where their cube sits read those as one picture, which is how a decorated pot ends up with holes through it. `make_block_forms.on_sheet` turns a region of a sheet into a texture reference and a window, pulling the tile corner back far enough that the region fits and never past the edge of the sheet.

**Only the top left 16×16 of a texture becomes a tile.** A larger one is cropped, never scaled, so its pixels keep their size. **So a tile saved at the wrong scale is a hole in the model, not a blurry block.** `fern` and `short_grass` were both saved as ten times upscales, 160×160, and the corner Scaffold reads was empty, so both drew nothing and neither reached the skipped list. `tests/test_block_coverage.TileTests` fails on a supported block whose tile has no pixels in it. A block drawn from an entity sized sheet says which part it needs by writing `#x,y` after the texture's name, and the window travels with an `@` reference: `"@north#0,12"` is the board half of whatever sheet that wood has. Each window is a tile of its own, and one that falls outside the texture is ignored.

**How a block is mounted is a different shape, not the same shape moved.** `tools/blocks/mounted.py` owns `hanging_sign`, `bell`, `grindstone`, `campfire`, `shelf`, `tripwire_hook`, `sculk_shrieker`, `tripwire`, `flower_pot`, `decorated_pot`, `brewing_stand`, `heavy_core`, `dried_ghast` and `door` in both tables, and gives each mounting its own list of cubes. It also gives a lit campfire its fire, which is the only thing telling it from a dead one and a soul campfire from an ordinary one, gives a shelf a different picture on each face, since its sheet holds the front, the planks and the shaded interior, and gives a tripwire hook the two arrangements `attached_bit` names.

**A ghost block is not a solid one, so vanilla's own trick is not always the answer.** Vanilla paints a shelf's three compartments into its front texture and leaves the block a plain box, which reads correctly when the block is opaque and reads as nothing at all when it is half transparent. The compartments are cut as geometry here instead. The same reasoning gives a sculk shrieker its throat, and `tools/textures/string.py` draws string a tile of its own because vanilla's is a scatter of single faint pixels that disappears on a see-through plate.

**`blocks.json` names texture slots, not faces.** For most blocks the two are the same, but `big_dripleaf` reads `up: big_dripleaf_side2`, `down: big_dripleaf_side1` and the leaf on three of the sides, because the engine picks from those slots for a model of its own. Taken literally, the leaf's top wears four rows of edge profile over an empty tile and the block is invisible from above. A family whose slots do not line up with its faces names its textures outright in `overwrite`.

**The UV lists run in the shape list's order, cube for cube.** A family whose entry was written beside another family's has to have its lists reordered to match its own cubes, not only its numbers changed. `lightning_rod` was copied from `end_rod`, whose two cubes are the same two the other way round, so the base wore the rod's long stripe and the base's square was stretched along the rod. Nothing reports this: both lists were the right length.

**A wall mounting sits at z 0.** `wall_sign` is the family to copy: its board is at `z` 0 to 2, so the wall is the block behind it and the face looks along +z, which is where the rotation tables put south. A bell's beam, a grindstone's legs, a hanging sign's arm and a shelf's whole body all run that way.

**Edit the tables a family at a time.** `tools/blocks/tables.py` replaces one family's span and leaves the rest of the file byte for byte alone. `block_uv.json` is not formatted consistently, so rewriting it from a parsed copy reformats entries nobody touched and buries the real change.

**UV V grows downward.** The upper half of a texture tile belongs on the upper half of a block. A bottom slab shows the *bottom* half of its texture; a top slab shows the top half. Getting this backwards is invisible on stone and obvious on planks.

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
- **UUIDs are derived, not random.** `uuid5` over a fixed Scaffold namespace plus the pack name, so regenerating a pack replaces the one already in the player's list instead of appearing as an unrelated pack. Never go back to `uuid4` here; the accepted cost is that two people who pick the same pack name get the same UUID.
- The pack version is the Scaffold version, from `pyproject.toml`.

### Bundling TechPack

`pack/tech_pack.py` has three answers rather than two — `tech_pack.NONE`, `COMPATIBILITY` and `FULL`, chosen with `set_tech_pack(mode)`, the **TechPack** menu, or `--tech_pack none|compatibility|full`. The default is none: bundling somebody else's pack into yours is a deliberate act, not something that happens because a switch was left on, and the choice is remembered in `.scaffold`.

**Compatibility** merges TechPack's declarations onto the armor stand and ships none of its files, so a separately installed TechPack keeps working alongside the generated pack. **Full** copies its assets in as well, so the one pack is both. `mode_of()` still reads a bare `True` as full, because the setting used to be a switch and a stored one has to keep meaning what it did.

This exists because the two projects collide head on. Both replace `entity/armor_stand.entity.json`, a client entity file replaces the vanilla one rather than merging with it, and **between two packs only the higher in the player's list is read at all**. Applying Scaffold and TechPack side by side does not half-work: whichever sits lower is ignored completely. There is no ordering that runs both, which is why bundling is the only answer and why the README says to disable the standalone TechPack while a bundled pack is active.

The merge lives on `armorstand.merge_description`, not in `pack/tech_pack.py`, because it is about the shape of a client entity file rather than about TechPack. Scaffold wins every conflict, and one of them matters: `geometry.default` has to stay on `geometry.armor_stand.larger_render`, or the model stops drawing the moment the stand leaves the screen. Script order matters too — the pose controllers have to run before anything that reads the pose index, and TechPack's `spawner_radius` entry does exactly that.

Two things worth knowing:

- TechPack's own `scripts.animate` asks for `controller.pose` and `controller.wiggling` without declaring them in its `animations` map — the drift this file warns about, in somebody else's copy. Bundled with Scaffold, which does declare both, nothing is left dangling.
- Both projects ship `models/entity/armor_stand.larger_render.geo.json` and both declare the same geometry id. The files are currently byte-identical, which is the only reason `copy_assets` can skip the collision instead of resolving it. A test asserts they stay identical.

### Bedrock is case-sensitive; Windows is not

`textures/Density` resolves to `textures/density.png` on a Windows dev machine and resolves to nothing on Android, iOS and consoles, where it draws an untextured surface with no error anywhere. Match the case the files actually have on disk.

### Pack JSON is not JSON

Bedrock's parser is more permissive than `json.loads`, and the vanilla packs use it: `//` comments, trailing commas, and a UTF-8 BOM. The community submodule's `blocks.json` and `terrain_texture.json` both carry comments. Read them through `tools/jsonc.py`, never `json.load`, or valid content will be reported as broken. The trimmed `Vanilla_Resource_Pack/` in this repository is plain JSON and is safe either way.

### Replacing the vanilla armor stand

`pack/armor_stand_class.py` carries a hardcoded copy of vanilla's `armor_stand.entity.json` description with this project's geometry and textures added. A client entity file in a resource pack **replaces** the vanilla one; they do not merge. Vanilla's own animation and render controllers keep asking for the short names vanilla's copy declared, so every name the copy fails to carry over is a `can't find animation <name>` in the content log and a vanilla animation that stops playing.

This drifts on its own: Mojang adds a short name in an update and the hardcoded copy, which never changed, is suddenly missing it. When a Minecraft update lands, diff the `animations`, `scripts.animate` and `render_controllers` lists in `pack/armor_stand_class.py` against `CommunityVanillaResourcePack/entity/armor_stand.entity.json`.

---

## Keeping the vanilla pack current

`Vanilla_Resource_Pack/` is a trimmed vanilla pack, hand-merged over years. Some of its textures are **deliberately** not vanilla:

- biome-tinted textures are pre-tinted, because ghost blocks cannot run the colormap (`grass_top`, `tallgrass`, `vine`, the stems, `water_*_grey`, `redstone_dust_cross`)
- some are made more opaque so the ghost stays visible after the alpha pass (`glass_*`, `slime`, `hopper_top`)

`tools/vendor/vanilla_pack.py` encodes those rules. Run it against the community submodule rather than copying files by hand, and read what it reports before applying anything. `tools/checks/blocks.py` resolves every declared block down to a texture file and reports what does not.

---

## Comments describe how things work, not how they were decided

Write comments that explain mechanism, logic flow, and anything a reader needs in order to change the code safely. **Do not** record decision history: what was tried and rejected, what a previous version did, which bug prompted a change, what was weighed against what. That belongs in the commit log and `docs/PROJECT_REVIEW.md`.

Empirical facts about engine behaviour are worth keeping, stated as facts — "the X axis runs opposite to the Z axis here" rather than "this took three builds to work out".

Match the surrounding density: module headers carry a short orientation, non-obvious logic carries an inline comment. This codebase is lightly commented and inconsistently formatted; match the file you are in rather than reformatting around your change.

---

## Working habits

- **Isolate one variable at a time.** Changing two things and then attributing the result to one of them has produced wrong diagnoses here more than once.
- **Do not claim a causal link that has not been tested.** A hypothesis stated once becomes a fact if it is repeated; say "untested" and name the check that would settle it. The user tests in-game and reports back — give them the specific thing to look at, and say which observations would *not* prove it.
- **In-game behaviour is not knowable from here.** Rendering, placement, z-fighting and transparency need a live world. Geometry numbers and UV values can be checked here; how they look cannot.
- **Prefer Python patch scripts over shell heredocs** for multi-line source edits. `\n` inside a heredoc has repeatedly become a literal newline and corrupted string literals. Write the script with the Write tool, or anchor on text containing neither.
- **Re-compact JSON after writing it with `json.dumps`**, which explodes short numeric arrays across lines. The lookup tables are kept compact, and a reformatted table makes a one-value change unreviewable.
- **The test structures are the regression suite.** `tools/checks/coverage.py` builds against all 108 of them and prints what `get_skipped()` reports, which is the fastest way to see whether a lookup change broke something. It drives the real pipeline rather than reimplementing the state translation, so the answer is what a user's build would actually produce. It should print zero.

**Look at a block before believing it.** `tools/checks/render.py` draws one from `make_block`'s own output -- six flat views, one per face, orthographic and nearest sampled so a texture pixel is a countable square, and a three quarter view on the end for the shape. `--no-iso` drops the corner, `--iso` trades the flat six for all eight corners four to a row, `--all` draws both in three rows, and `-w <name>` draws one view on its own. `--open` opens the result. Pictures land in `renders/`, which is gitignored because every one of them redraws in a second. It catches what the tables cannot show: a face on the wrong half of a sheet, a window two pixels out, a picture on its side, a gap under a tilted slab. It never reads the lookup tables itself, and `tests/test_render.py` enforces that, because a renderer that translated them would only ever agree with them.

`--manifest` fingerprints every *form* of every block -- a banner's eighteen, a chiseled bookshelf's sixty-four, 2239 in all against 1381 blocks -- and compares them against `tools/checks/render_hashes.json`, which answers "what else moved" after a table edit. **Forms, not blocks:** a default-only sweep covers barely half the tables and slept through an ominous banner's face coming out cut in half. The test suite runs the same comparison. **Re-record it with `--manifest --update` and commit the manifest in the same change that moved the blocks**, so the diff carries both. It does not model z-fighting, transparency over a world, or lighting; those still need a world. `docs/Editing Blocks.md` has the details.

---

## Running, testing and building

```bash python -m scaffold                                    the window python -m scaffold --structure in.mcstructure --pack_name Name    CLI python -m unittest discover -s tests -t .              tests python build.py                                        release zip in dist/ python build.py --publish                              sign it into the update repo python build.py --init-trust                           create the signing keys, once

python -m tools.generate                               every generator, in order python -m tools.generate --list                        what that runs, and when python -m tools.generate blocks                        only the block tables

python -m tools.checks.coverage                        what the test structures drop python -m tools.checks.blocks                          what does not resolve python -m tools.checks.generators                      run the generators twice and diff python -m tools.find <search>                          find a block by id, name or family python -m tools.find texture <search>                  find a texture, as an overwrite entry names it python -m tools.render <block>                         draw one block, six ways round python -m tools.checks.render --manifest               which blocks changed how they look python -m tools.app.screenshots                        refresh the README's shots python -m tools.vendor.tech_pack                       stage TechPack's assets python -m tools.vendor.vanilla_pack                    sync the trimmed vanilla pack ```

`lookups/` and `Vanilla_Resource_Pack/` are opened by relative path, so all of these must run from the repository root, which is also what makes `python -m tools.…` resolve.

**A generator says what a table is, never what to change it by.** One that reads a table, adjusts it and writes it back is right exactly once: run again it is wrong, and the build regenerates everything before every compile, so the answer depends on how many times the build has run. A carved pumpkin faced a different way on alternate releases because `tools/blocks/faces.py` added a half turn to its own output each time. Nothing catches that by reading the source -- deriving one family from another is ordinary, and `faces.py` builds `azalea` and `vault` out of `cube` -- so `tools/checks/generators.py` runs them twice and diffs what they wrote. It rewrites the tables, which is why it is a command and not a test.

**`tools/generate.py` owns the order, and `build.py` runs it.** A table generated by an older version of the script that writes it is the kind of thing nobody notices until a block is wrong in game, so the build regenerates everything before it compiles anything; `--skip-tools` is the exception. Three are deliberately left out of it: `app/screenshots.py` needs a window on screen, and the two under `vendor/` copy out of the submodules, whose diffs are meant to be read before they are applied.

---

## Reference

- Bedrock samples: https://github.com/Mojang/bedrock-samples  - `behavior_pack/shapes/<block>.json` carries Mojang's own voxel shape for a block, one file per facing, as boxes in pixels. **Read that before measuring a shape off a texture** — it is where the shelf's five deep case and four thick boards came from, after four shapes guessed from the sheet. It is a collision shape, so it gives sizes and positions and says nothing about how a piece is painted.
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
