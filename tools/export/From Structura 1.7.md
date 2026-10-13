# From Structura 1.7 to format 2

Written for whoever maintains Structura. Scaffold grew out of Structura 1.7, and
its block tables started as Structura's `lookups/`. They have since been rebuilt
as format 2, which `Lookup Format 2.md` beside this file specifies. This
document is what is particular to Structura: how the files map onto 1.7's,
every breaking change, what reading format 2 directly would take, and what the
converter cannot carry into 1.7's tables.

---

## The files

| 1.7 | Format 2 | |
| --- | --- | --- |
| `block_definition.json` | `block_definition.json` | block id to family, now under `blocks` beneath the header; a bare map, 1.7's shape, still reads. **Current ids only.** |
| `block_shapes.json` + `block_uv.json` | `block_geometry.json` | one file: forms, cubes, faces, textures, and the rules that pick a form |
| `block_rotation.json` | `block_rotation.json` | family to a **state name** or a table of **Minecraft angles** |
| | `state_rotations.json` | new: Minecraft's own turns for each facing state |
| `nbt_defs.json` | removed | each family's rules say which states it reads |
| `variants.json` | removed | replaced by each family's `texture_by` rule |
| | `block_upgrades.json` | new: old ids and states to current ones, applied as a structure is read |
| | `schema/*.schema.json` | new: a JSON schema for each geometry file |
| | `dust_connections.json` | new: the rules redstone dust is joined by |
| `material_list_names.json` | `block_list.json` + `block_categories.json` | not geometry, and not in this handoff: the names a block list gives each block, now beside the headings it is grouped under |
| `langs.csv` | `lang/<locale>.lang` | not geometry, and not in this handoff: the window's strings, now a file per language |
| `lookup_version.json` | removed | 1.7's table update endpoint; Scaffold's tables ship with the program, and its version names them |
| `armor_stand.larger_render.geo.json` | the same | unchanged |

---

## What carries over, and what does not

**The units and the placement.** A form's `center`, a cube's `size` and its
`offset` mean what 1.7's `center`, `size` and `offsets` meant, in blocks from
the low corner of the cell, and 1.7's origin formula still places them. What
changed is the orientation: blocks rest facing north, where most 1.7 shapes
rested facing south or east, and a rotation table holds Minecraft's angle where
1.7's held the bone rotation itself. Do not mix a format 2 shape with a 1.7
rotation table.

**Windows.** 1.7 kept a cube's windows in `block_uv.json`, apart from its shape,
picked them by index, reused the last entry when a form had more cubes than
windows, and in `make_block` read a data form's windows from `top` or `default`
rather than from the data form. A form present in one file and not the other
fell back to `default` without a warning. Format 2 puts six faces on every cube.

**Textures.** 1.7's `overwrite` held a literal path or `"default"` per cube per
face. A path is `{"texture": path}` and `"default"` is no `texture` at all.
Scaffold's tables kept an intermediate string form for a while (`@up`, `#x,y`,
`^90`, `~tint` written after a name); format 2 replaces all of it with the
texture object.

**Choosing a form.** 1.7 chose a form in `make_block` from flags
`_process_block` set: `side` for a family named `hopper` with a rotation other
than 0, `open` for a family named `trapdoor` that was open, `on` for `lever`,
`top` for anything with a top flag, and then `str(data)` if the family had a
form by that name. Which states set those flags was global, in `nbt_defs.json`.
Format 2 moves all of it into each family's `pick`, `data`, `turn_by` and
`texture_by`, and `texture_by` replaces the global `variants.json`.

**Rotation tables.** 1.7 raised `KeyError` on a missing key and skipped the
block; format 2 draws it unrotated. Some 1.7 tables held only old numbers: a
door's is keyed `0` to `3`, so a door saved with `minecraft:cardinal_direction`
words finds no entry and is skipped.

**Old blocks.** 1.7's tables carried old ids beside new ones: `wool` with
`color` beside `white_wool`, `stone_block_slab` with `stone_slab_type` beside
`stone_brick_slab` and the rest, `top_slot_bit` beside
`minecraft:vertical_half`, which `nbt_defs.json` reads as a rotation. Format 2
tables hold current ids only and translate a structure's palette as it is
read. A Structura that does not translate old palettes stops resolving old
structures with format 2 tables; the converter does the translation backwards
instead, writing a table for every old id and every old state value.

**Block entities.** 1.7 never read the block entity beside a block. Format 2
rules do.

**The ghost's size.** 1.7 writes a whole block 0.95 across from the low corner
of its cell, 0 to 0.95 with its centre at 0.475, so a ghost sat flush on three
sides and a pixel short on the other three, and its top slab is a full 1.0
across. Its `make_block` once set `inflate: -0.03` on every block, and that
line is commented out. Format 2 shapes are centred in the cell.

**The atlas.** 1.7 stacks every tile in one column, so a pack with a thousand
distinct textures is 16,000 pixels tall and crashes the game on loading.

---

## Breaking changes from 1.7

**Files**

1. `block_shapes.json` and `block_uv.json` are one file, `block_geometry.json`,
   with a header and per-cube faces.
2. `variants.json` is gone; `texture_by` in each family replaces it.
3. `nbt_defs.json` is gone. Which states matter, and how, is each family's
   rules; a block list names a block's variant by its family's `texture_by`
   state.
4. `state_rotations.json`, `block_upgrades.json` and `schema/` are new.
5. Every table has a header, `format`, `minecraft` and `about`, with `$schema`
   on the geometry files, and its content under a key of its own: `families`,
   `states`, `blocks` or `rules`.

**Coordinates and rotation**

6. Blocks rest facing north; many shapes have been turned from 1.7's.
7. Rotation tables hold Minecraft angles. Convert with `to_bone` (negate y and z)
   before using one as a bone rotation.
8. A family's rotation entry may be a state name instead of a table.
9. A missing rotation key draws the block unrotated instead of raising.
10. `"<form>:<value>"` rotation keys are read first.
11. Table keys are the values current blocks carry: doors are keyed by words,
    not numbers.

**Forms**

12. Form choice moved from code and `nbt_defs.json` into each family's `pick`,
    `data`, `turn_by` and `texture_by`. The family names `hopper`, `trapdoor`
    and `lever` mean nothing special.
13. Form names combine: `<mounting>-<value>`, then `<value>`, then
    `<mounting>`, then `default`. `data` values may be words and joined states,
    not only `str(int)`.
14. Every cube carries its own windows; 1.7's reuse of the last window and its
    reading of a data form's windows from `top` or `default` are gone.

**Textures**

15. `overwrite` strings became texture objects: `slot`, `texture`, `window`,
    `turn`, `tint`.
16. A face can read any face's declared texture with `slot`, for one cube.
17. A texture list picks its entry by `texture_by`, or by the block's name,
    never by a global variant table.

**Blocks**

18. Tables carry current ids only. Old ids and old states are translated on
    read through `block_upgrades.json`.
19. Some blocks need their block entity to be drawn correctly.
20. Blocks added since Structura 1.7's tables, and many reshaped ones, have
    no 1.7 equivalent; `ignore` remains the family for blocks drawn as nothing.

---

## What it would take for Structura to read format 2

The converter is a bridge: it fits Scaffold's tables into 1.7's shape and loses
what that shape cannot hold. Reading format 2 directly loses nothing, and is
mostly a matter of moving decisions out of Structura's code and into the
tables. This is an outline of the work, not a design, and it names the Scaffold
file each piece can be compared against. The converter is the place to start
reading: it already reads every format 2 table and answers, per block, the
cubes and textures a reader should produce.

**Loading the tables.** Each file opens with the header and keeps its content
under one key, so the loader reads `families`, `states`, `blocks` or `rules`
rather than the top level. `block_shapes.json` and `block_uv.json` become one
read of `block_geometry.json`; `variants.json` and `nbt_defs.json` are no longer
read at all. `material_list_names.json`, `langs.csv` and `lookup_version.json`
are Structura's own and can stay as they are. A loader that checks `format` is
2 and refuses anything else is a cheap guard against a table from somewhere
else.

**Translating old blocks first.** Format 2 tables hold current ids only, so a
structure saved by an older game has to be run through `block_upgrades.json`
before anything looks a block up: once per palette entry, as the structure is
read, rules top to bottom, each seeing the block as the rules above it left it.
A rule with `before` needs the `version` every palette entry carries.
`scaffold/block_upgrade.py`, under two hundred lines, is the reference.
Without this step a structure from before the flattening loses most of its
blocks to the skipped list rather than drawing them wrongly.

**Replacing `_process_block` and the special cases in `make_block`.** 1.7
works out a rotation, a top flag, a variant, an open flag and a data number in
code, from `nbt_defs.json`, and `make_block` then names `hopper`, `trapdoor` and
`lever` to pick a shape. In format 2 a family's `pick`, `data`, `turn_by` and
`texture_by` rules do all of that. Structura needs one small rules reader in
place of both, which hands `make_block` a form name, a rotation and a texture
index. "Choosing a form" in the specification is the whole of what it has to
do; `ArmorStandGeo.choose` in `scaffold/pack/armor_stand_geo_class.py` is
Scaffold's.

**Rotation in Minecraft's angles.** A rotation table holds the game's angle
for a state, or names a table in `state_rotations.json`. A missing key means
"no turn" rather than an error, a `"<form>:<value>"` key is read before the
plain value, and the angle is turned into a bone rotation in one place by
negating y and z, which is `to_bone`. Blocks also rest facing north now, so
any rotation Structura applies outside the tables has to be checked against
that.

**Per-cube faces.** Every cube carries its own six faces, each a texture
object. `block_name_to_uv` and the `overwrite` lists it reads are replaced by
reading those objects. The atlas then has to be keyed by the whole of what is
drawn, texture, window and turn together, since two faces reading different
windows of one file are two tiles. A face with a window of no size is left out
of the model.

**The atlas as a grid.** A fixed number of columns, with UVs in tile units,
keeps a pack of many textures within what a graphics card holds; Scaffold uses
sixty-four. This is worth doing whatever else is done.

**Block entities.** Some forms depend on the entity beside the block: a
banner's dye, a bed's colour, a statue's pose, a lectern's book, a shulker
box's facing, a chest's pairing, a pot's plant. The structure keeps them in
`block_position_data`, keyed by the block's index. Structura's reader would
need to hand each block its entity alongside its states, and the rules reader
to look fields up there when a rule names `entity`. A reader that skips this
draws those blocks as with no entity, which is what the converter does today.

**Water and the second layer.** `block_indices` has two layers, and the second
holds the water a waterlogged block stands in. 1.7 reads the first only.
Drawing water is optional, but if it is drawn it needs the ordering in the
specification or it hides what stands in it.

**Draw order.** A ghost is blended, and the game appears to draw a model's
bones sorted by name. 1.7 writes one bone per slice, so the order within a
slice is the order blocks were added, and planes and water land wherever they
fall. Naming bones so planes and water sort after the blocks, and keeping
anything that has to follow one block in that block's own bone, removes most
of the holes a blended ghost shows. "Drawing what the tables describe" in the
specification has the order Scaffold uses. This is engine work rather than
table work and can come later.

**What can be left out.** Redstone dust joins (`dust_connections.json`) and the
`low` section of each family are Scaffold features layered on the tables. A
reader that ignores both draws every dust as the lone cross and every block in
its detailed form, which is what it would draw without them anyway.

**Checking the result.** The converter walks every state of every block,
19,003 of them, through Scaffold's own code. A structure holding those states,
built once by a Structura that reads format 2 and once by Scaffold and compared
cube by cube, turns "does it match" into a list of cases to look at rather than
a guess.

---

## What the converter cannot carry

`python convert.py <out> --report` lists every case. Running 1.7's own code
over the converter's tables and comparing it with Scaffold cube by cube,
against Structura 1.7 as released (`V1.7-rel`), over 19,003 states of 1,370
blocks, it draws 6,137 the same and skips none, within a few cases of the 6,122
the report predicts. Most of the rest are doors, walls, panes and fences in
every arrangement of their states. What remains:

- **The joins of walls, panes, bars, fences and string**, the
  `minecraft:connection_*` and `wall_connection_type_*` states a structure from
  Minecraft 26.50 on carries. 1.7 reads one data state, so every arrangement is
  drawn as the same one.
- **A hanging sign fixed under a block** turns by `ground_sign_direction`, a
  second rotation state 1.7 cannot read beside `facing_direction`.
- **An open door's hinge side**, which needs a third state beside the upper half
  and open flags.
- **A top slab** is drawn as the bottom slab turned over about a recentred
  pivot, as 1.7 did: the shape is right and the side textures are upside down,
  because `minecraft:vertical_half` is a word and 1.7 can only read it as a
  rotation.
- **A cauldron's liquid**, an egg clutch's count and a dripstone's thickness,
  which are words.
- **Block entities**: banner dyes and designs, bed dyes, statue poses, lectern
  books, dyed cauldrons and floor heads' sixteen turns are drawn as with no
  entity.
- **Old shulker boxes** come out in one colour, because each face of their
  model reads a different window of one sheet.
- **An amethyst bud or cluster on a north or south wall.** 1.7 adds a block's
  turn to a cube's own turn when the two share a pivot, and a turn about x
  followed by one about y is not the sum of the two. Those four of each come out
  leaning the wrong way. This is the one difference the report does not
  predict, and it was measured by the comparison, not seen in game.

The converter also works around 1.7 in ways worth knowing before editing its
output by hand: forms are padded with cubes of no size so a data form finds its
windows in `default`'s list, every texture is resolved per block and cut into
`textures/scaffold/` where Scaffold cuts or turns one, and every face of every
block is named outright, so `blocks.json` holds only placeholders and the few
lists a `variant` state picks from.
