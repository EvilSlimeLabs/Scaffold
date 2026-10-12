# Lookup format 2, for Structura

This is for whoever maintains Structura. Scaffold grew out of Structura 1.7, and
its block tables started as Structura's `lookups/`. They have since been rebuilt
as **format 2**. This document describes format 2 well enough to write a reader
for it, and lists everything that changed from the 1.7 tables.

There are two ways to use it.

- **Keep Structura 1.7's code and take Scaffold's tables.** Run
  `python -m tools.export.structura <out>` in a Scaffold checkout. It writes a
  `lookups/` and a `Vanilla_Resource_Pack/` in 1.7's own format, to copy over a
  Structura checkout. Nothing in Structura changes. Some blocks come out
  approximate, because 1.7's code cannot express them; see
  [What the 1.7 export cannot carry](#what-the-17-export-cannot-carry).
- **Read format 2 directly.** This means porting a small rules engine and
  changing how `make_block` picks a form. The rest of this document is the
  specification. Scaffold's reference implementation is
  `scaffold/block_geometry.py` and `ArmorStandGeo.choose` and `make_block` in
  `scaffold/pack/armor_stand_geo_class.py`, all MIT licensed like Structura.

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
| | `dust_connections.json` | new: the rules redstone dust is joined by; see "Things the format relies on" |
| `material_list_names.json` | `block_list.json` + `block_categories.json` | not geometry, and not in this handoff: the names a block list gives each block, now beside the headings it is grouped under |
| `langs.csv` | `lang/<locale>.lang` | not geometry, and not in this handoff: the window's strings, now a file per language |
| `lookup_version.json` | removed | 1.7's table update endpoint; Scaffold's tables ship with the program, and its version names them |
| `armor_stand.larger_render.geo.json` | the same | unchanged |

Every format 2 table opens with the same header, in this order:

```json
{"$schema": "schema/block_geometry.schema.json", "format": 2, "minecraft": "26.50",
 "about": "Every shape family: ...", "families": {...}}
```

| Key | Says |
| --- | --- |
| `$schema` | the schema the file is checked against, on the three geometry files only |
| `format` | 2 |
| `minecraft` | the game version the table was checked against; Scaffold's tests fail when it differs from the game files it is built from, so it is the version every block in it is current for |
| `about` | one line on what the file holds |

What a file holds comes after, under one key or a few: `families` in
`block_geometry.json` and `block_rotation.json`, `states` in
`state_rotations.json`, `blocks` in `block_definition.json`, `rules` in
`block_upgrades.json`. A reader keyed on those names reads every one; a
`block_definition.json` with no header, a bare map at the top level, is the
same table in 1.7's shape. There is no field naming a coordinate frame: format
2 is defined to be in Minecraft's frame, described next.

---

## The frame

The numbers are in the same units 1.7 used: blocks, measured from the low
corner of the cell. A form's `center`, a cube's `size` and its `offset` mean what
1.7's `center`, `size` and `offsets` meant, and 1.7's origin formula still
places them:

```python
origin = [-(x + offsets[0]) + cube_offset[0], y + cube_offset[1] + offsets[1], z + cube_offset[2] + offsets[2]]
pivot  = [center[0] - (x + offsets[0]),        y + center[1] + offsets[1],      z + center[2] + offsets[2]]
```

What changed is the orientation and the meaning of a rotation.

- **A block rests facing north.** Its front is the north face when nothing turns
  it. This is Minecraft's rest pose, and `minecraft:cardinal_direction` "north"
  leaves it alone. Most 1.7 shapes rested facing south or east, so many shapes
  have been turned. Do not mix a format 2 shape with a 1.7 rotation table.
- **East is the low side of x**, as in every Bedrock `.geo.json`. A model read
  from a `.geo.json` converts with offset = (origin + 8) / 16 across and deep,
  and origin / 16 up.
- **A rotation table holds Minecraft's angle**, in degrees about x, y and z, the
  way Minecraft turns the block. 1.7's tables held the bone rotation itself. A
  bone turns the other way about y and z, because the model is the world
  mirrored in x, so convert at draw time:

  ```python
  def to_bone(angles):
      return [angles[0], -angles[1] % 360 if angles[1] else 0,
              -angles[2] % 360 if angles[2] else 0]
  ```

- **A cube's own `rotation` is still a bone turn**, about the cube's own centre,
  exactly as 1.7 applied it. Only the family's turn changed meaning.

These were settled in game with a pack of lettered cubes
(`python -m tools.checks.compass` in Scaffold), with the armor stand placed by
somebody standing north of it and facing south. The ghost turns with its stand,
so every in-game check of a facing needs the stand's placement stated.

---

## block_geometry.json

```json
"heavy_core": {
    "forms": {
        "default": {
            "center": [0.5, 0.25, 0.5],
            "cubes": [
                {"size": [0.5, 0.5, 0.5], "offset": [0.25, 0.0, 0.25], "faces": {
                    "up":    {"uv": [0.0, 0.0], "size": [0.5, 0.5], "texture": {"slot": "up"}},
                    "down":  {"uv": [0.5, 0.0], "size": [0.5, 0.5], "texture": {"slot": "up"}},
                    "north": {"uv": [0.0, 0.5], "size": [0.5, 0.5], "texture": {"slot": "up"}},
                    "south": {...}, "east": {...}, "west": {...}}}
            ]
        }
    },
    "low": {...}
}
```

A family has `forms`, always including `default`. A form has a `center` and a
list of `cubes`. A cube has:

| Key | | |
| --- | --- | --- |
| `size` | required | `[x, y, z]` in blocks |
| `offset` | required | the cube's low corner within the cell |
| `rotation` | optional | `[x, y, z]` degrees about the cube's own centre, as a bone applies it |
| `faces` | required | all six of `up`, `down`, `north`, `south`, `east`, `west` |

A face has:

| Key | | |
| --- | --- | --- |
| `uv` | required | the window's corner within the tile, in fractions of a tile, from the upper left |
| `size` | required | the window's size in fractions of a tile; negative runs it backwards |
| `texture` | optional | what the face reads; left out, the block's own texture for that face |

This is 1.7's `offset` and `uv_sizes` per cube per face, moved onto the cube.
1.7 kept the two in separate files and two separate lists, and a form present
in one file and not the other fell back to `default` without a warning. Format 2
cannot disagree with itself that way.

**A cube's windows are its own.** 1.7 picked a cube's windows by index, reusing
the last entry when a form had more cubes than windows, and, in `make_block`,
read a data form's windows from `top` or `default` rather than from the data
form. Format 2 gives every cube in every form its own six windows.

### texture

```json
{"slot": "north", "window": [0, 12]}
{"texture": "textures/blocks/obsidian"}
{"slot": "up", "turn": 90}
{"texture": "textures/blocks/cauldron_water", "tint": true}
```

| Key | Says |
| --- | --- |
| `slot` | whatever the block declares for that face in `blocks.json`: `up`, `down`, `north`, `south`, `east`, `west`; or `item`, the block's inventory picture, which only Scaffold's low geometry reads |
| `texture` | a path under the resource pack, without an extension |
| `window` | `[x, y]` in pixels: read the 16x16 region at that corner of a larger texture, as a tile of its own |
| `turn` | degrees clockwise, a multiple of 90: turn the tile before it is used |
| `tint` | `true`: multiply the tile by a colour the block entity carries |

A face has exactly one of `slot` and `texture`.

1.7's `overwrite` held a literal path or `"default"` per cube per face. That
maps directly: a path is `{"texture": path}` and `"default"` is no `texture` at
all. Scaffold's tables kept an intermediate string form for a while (`@up`,
`#x,y`, `^90`, `~tint` written after a name); format 2 replaces all of it with
the object above.

What a reader has to implement for these:

- **`slot`** reads the same `blocks.json` declaration 1.7 read for the whole
  block (`textures` as a string, or a dict with `side` and the six faces), but
  for one face of one cube. One family therefore serves every wood a sign comes
  in, and a door's two halves read its two declared textures.
- **`window`** crops the 16x16 region at that pixel corner instead of the top
  left. A window that falls outside the texture reads the top left instead. The
  atlas has to key the tile by the texture *and* its window, or two windows of
  one sheet share a tile.
- **`turn`** rotates the finished 16x16 tile clockwise. Bedrock's UV has a
  corner and a size and no angle, so this is the only way a face can read its
  picture a quarter round. Key the tile by the turn too.
- **`tint`** multiplies each channel by the block's colour, `channel * level //
  255`, on the way into the atlas. Scaffold reads the colour from a cauldron's
  `CustomColor`. Key the tile by the colour.

Only the top left 16x16 of a texture is ever a tile, exactly as in 1.7: a larger
texture is cropped, never scaled.

### low

`low` has the same form names as `forms` and the same layout. It is a simpler
drawing of each form, for clients that cannot afford the detailed geometry.
Everything except the cubes is the detailed family's: the rules, the rotation
table and the centre. A family with no `low` is drawn the same either way.
Ignore it if Structura has no such setting.

---

## Choosing a form

1.7 chose a form in `make_block` from flags `_process_block` set: `side` for a
family named `hopper` with a rotation other than 0, `open` for a family named
`trapdoor` that was open, `on` for `lever`, `top` for anything with a top flag,
and then `str(data)` if the family had a form by that name. Which states set
those flags was global, in `nbt_defs.json`.

Format 2 moves all of it into the family. A family may carry up to four rules,
written before its forms:

```json
"trapdoor": {
    "pick": [{"when": {"open_bit": true, "upside_down_bit": true}, "form": "open_top"},
             {"when": {"open_bit": true}, "form": "open"},
             {"when": {"upside_down_bit": true}, "form": "top"}],
    "data": {"number": ["direction"]},
    "turn_by": [{"state": "direction"}],
    "forms": {...}
}
```

A family need not turn at all. A door is drawn from one form per state, named
`lower-<facing>-<open>-<hinge>` by `pick` and a `join` of three states, with no
`turn_by`, because the game paints each side of a door by where it stands in
the world and no turned shape can do that.

### pick: the mounting

A list of `{"when": {state: value or [values]}, "form": name}`. The first rule
whose states are all present and all match names the block's **mounting**. With
no match the mounting is `default`.

### data: the value

An object whose keys say where the block's **value** comes from. With no `data`,
the value is `"0"`.

| Key | The value is |
| --- | --- |
| `number` | the last of these states present, as a number written in decimal |
| `join` | the values of these states that are present, joined with `-`, in the order listed |
| `entity` | a field of the block entity, replacing what came before |
| `entity_add` | a field of the block entity, appended after a `-` |
| `instead` | `[[field, form or {value: form}], ...]`: a block entity field that names a form outright. A dict is read for the field's value; a plain form needs the field present and non-empty. The first that answers wins |
| `tinted` | `[from, to]`: when the block entity has `CustomColor`, a value starting with `from` starts with `to` instead |

They apply in that order: `number`, then `join`, then the entity keys.

### The form drawn

The first of these that the family has:

1. `<mounting>-<value>`
2. `<value>`
3. `<mounting>`
4. `default`

A locked hopper on its side is mounting `side` and value `1`, so `side-1`. An
unlocked one falls through to `side`. A banner's dye is value `0` to `15` from
its block entity's `Base`, so form `5`. An ominous banner names `illager` with
`instead`.

### turn_by: the rotation state

A list of `{"state": name, "when": {...}}` or `{"entity": field, "when": {...}}`.
The first whose state, or block entity field, is present and whose optional
`when` matches is what the block turns by; its value is the key into the
rotation table. A shulker box keeps which way its lid opens in its block
entity's `facing`, so its families turn by `{"entity": "facing"}`. A hanging sign turns by `facing_direction` when it
hangs from chains (`attached_bit` false) and by `ground_sign_direction` when it
is fixed under a block.

### texture_by: the texture list

`{"state": name, "values": {value: index}}`. When the block's `blocks.json`
texture is a list, this state's value picks the entry, through `values` or, with
no `values`, as the number itself. It replaces 1.7's global `variants.json`.

`{"join": [states], "values": {joined: index}}` picks by several states at once,
their values joined with `-` in the order listed. A copper bulb's four pictures
are `lit` and `powered_bit` together: `{"0-0": 0, "1-0": 1, "0-1": 2, "1-1": 3}`.

A block with a list and no `texture_by` picks its entry by **name**: several
blocks Mojang split into an id each still share one list in `blocks.json`, and
every wooden door reads `door_lower`, whose entries run oak, spruce, birch,
jungle, acacia, dark oak. The longest leading part of the block's id that names
exactly one entry picks it, and otherwise the first entry is read. See
`ArmorStandGeo.named_entry`.

### Matching values

States arrive from NBT as bytes, ints and strings. Compare them as text: a byte
or a bool is `"1"` or `"0"`, a number its decimal, a string itself. A rule
written with `true` matches a byte 1.

The engine is about sixty lines: `plain`, `mounting`, `value`, `form`, `turn`
and `texture_index` in `scaffold/block_geometry.py`.

---

## block_rotation.json and state_rotations.json

```json
"anvil": "minecraft:cardinal_direction",
"button": {"0": [90, 0, 0], "1": [270, 0, 0], "2": [0, 0, 0], "3": [180, 0, 0], "4": [0, 270, 180], "5": [0, 270, 0]}
```

A family is either the name of a state in `state_rotations.json`, whose table it
uses, or a table of its own. Values are Minecraft angles; convert with
`to_bone` before handing one to a bone.

The standard tables:

| State | Values |
| --- | --- |
| `minecraft:cardinal_direction` | north 0, west 90, south 180, east 270 about y |
| `facing_direction` | 0 down `[90, 0, 0]`, 1 up `[270, 0, 0]`, 2 north, 3 south, 4 west, 5 east |
| `minecraft:facing_direction` | the same, with the words |
| `direction` | 0 south, 1 west, 2 north, 3 east |
| `weirdo_direction` | 0 east, 1 west, 2 south, 3 north |
| `ground_sign_direction` | sixteen steps of 22.5 degrees, 0 south |

Two behaviours differ from 1.7:

- **A missing key draws the block unrotated.** 1.7 raised `KeyError` and skipped
  the block.
- **A key `"<form>:<value>"` is read before `"<value>"`**, for a form that
  numbers its turns differently from the rest of its family.

A family whose blocks carry no facing state has no entry. A table holds only the
values its family's blocks can carry today: no numbers beside words.

An angle that is not a state, such as a floor skull's `Rotation` in its block
entity, is added to the table's y angle as a **yaw** in Minecraft degrees (0
north, 90 west). A skull's `Rotation` runs clockwise from north, so the yaw is
`-Rotation % 360`.

---

## Old blocks

1.7's tables carried old ids beside new ones: `wool` with `color` beside
`white_wool`, `stone_block_slab` with `stone_slab_type` beside `stone_brick_slab`
and the rest, `top_slot_bit` beside `minecraft:vertical_half`, which
`nbt_defs.json` reads as a rotation. Some rotation tables went the other way and
held only the old numbers: a door's is keyed `0` to `3`, so a door saved with
`minecraft:cardinal_direction` words finds no entry, raises, and is skipped.

**Format 2 tables describe current blocks only.** A structure's palette is
translated as it is read, one palette entry at a time, by the rules in
`block_upgrades.json`, applied top to bottom, each seeing the block as the
rules above it left it:

```json
{"id": "minecraft:seaLantern", "becomes": "minecraft:sea_lantern"}
{"id": "minecraft:wool", "by": ["color"], "into": {"silver": "minecraft:light_gray_wool", "...": "..."}}
{"id": ["minecraft:wooden_door", "..."], "state": "direction", "becomes": "minecraft:cardinal_direction", "values": {"0": "south", "...": "..."}}
{"id": "minecraft:bamboo_sapling", "state": "sapling_type", "drop": true}
{"id": ["minecraft:glow_lichen"], "state": "multi_face_direction_bits", "before": 17959425, "values": {"...": "..."}}
```

- `becomes` without `state` renames an id.
- `by` and `into` split an id by the value of one or more states, joined with
  `/`, and drop those states.
- `state` with `becomes` and `values` renames or remaps a state; `drop` removes
  it.
- `before` limits a rule to palette entries whose `version` is below it.
- `set` writes states onto a renamed block.
- `id` may be a list, and a rule without `id` applies to every block.

A new value is written with its JSON type, which is the NBT type the code then
receives. `scaffold/block_upgrade.py` is the reader, about a hundred lines.

**A state a block never had stays absent.** An old stair has no
`minecraft:corner`; the tables read an absent state as the default form, so
nothing invents one.

If Structura does not translate old palettes, old structures stop resolving with
format 2 tables. The 1.7 export does the translation backwards instead, writing
a table for every old id and every old state value.

---

## Block entities

Format 2 rules read the block entity beside a block, which 1.7 never read. The
entity is the compound in
`structure.palette.default.block_position_data[<index>].block_entity_data` for the
block's index in the grid. Scaffold reads these fields:

| Entity | Field | Used for |
| --- | --- | --- |
| `Banner` | `Base`, `Type`, `Patterns` | the dye, an ominous banner, a banner with a design |
| `Bed` | `color` | the bed's dye |
| `CopperGolemStatue` | `Pose` | which of four poses |
| `Lectern` | `hasBook`, `book` | whether a book lies on it |
| `Cauldron` | `CustomColor` | a dyed cauldron's colour, for `tint` |
| `Skull` | `Rotation` | a floor head's yaw |
| `FlowerPot` | `PlantBlock` | a whole block planted in the pot, drawn by its own family at the same position |

A block whose entity is missing is drawn as its rules give with no entity: the
default dye, no book, standing pose.

`Base` counts dyes, black 0 to white 15, the opposite way round from wool.

---

## Things the format relies on

- **The atlas.** 1.7 stacked every tile in one column, so a pack with a thousand
  distinct textures was 16,000 pixels tall and crashed the game on loading,
  because a graphics card holds 16,384 at most on a desktop and 4,096 on a
  phone. Scaffold lays tiles in a grid 64 wide: tile `i` sits at u `i % 64`,
  v `i // 64`, and `texture_width` and `texture_height` are tile counts. The
  tables do not depend on this, but windows, turns and tints all add tiles.
- **A window past its tile reads the next tile.** A face's window is in
  fractions of a tile and the atlas does not clamp, so `uv + size` beyond 1
  reads a neighbour. A few families still do this; `tools/checks/blocks.py
  --tables` in Scaffold lists them.
- **A ghost is a shade under full size, centred.** 1.7 writes a whole block
  0.95 across from the low corner of its cell, 0 to 0.95 with its centre at
  0.475, so a ghost sat flush on three sides and a pixel short on the other
  three; its top slab is a full 1.0 across. (Its `make_block` once set
  `inflate: -0.03` on every block, and that line is commented out.) Scaffold
  writes shapes that are more or less a full cube at about 0.95 of a block,
  **centred in the cell**, from 0.025 to 0.975 on every axis with the centre at
  0.5, so a ghost sits inside where the real block will go with an equal gap
  all round. A slab is 0.95 across; a bottom slab runs from 0.025 to 0.525 and
  a top slab from 0.475 to 0.975, so a top slab finishes level with a full
  block. Leave those numbers alone.
- **V grows downward**, and an up face's v runs toward -z, so the top of a tile
  lands at the block's south edge on an up face and at its north edge on a down
  face.
- **A face whose window has no size is not drawn**, and its texture is not put
  in the atlas. That is how a plane shows only its two faces: a cube with one
  dimension of zero and the other four windows `[0, 0]`. A cube with no face
  drawn at all is nothing, which is how a form says a state shows nothing: the
  upper block of a door, the top half of a pitcher crop too young to have one.
- **A ghost is blended, so draw order matters.** A clear texel still takes the
  depth it stands at and hides any ghost drawn after it, and water hides what
  stands in it the same way. Every cutout and every hidden waterlogged block
  seen in Scaffold's test worlds fits two rules, which no documentation states:
  **the game draws a model's bones sorted by name**, not in the order they are
  written, and **only the order of cubes within one bone holds** as the camera
  moves; two bones' order can swap. They are a model that fits what was seen,
  not something Mojang promises. So Scaffold names bones by tier, `slice_`
  for blocks, then `tier1_` for planes and `tier2_` for water, and an
  `early_` tier sorted before all of them; and it puts anything that must come
  straight after a block, a container's count or the water a block stands in,
  in that block's own bone, after it. It also cuts every plane down to the
  painted part of its tile. None of this is in the tables; it is `make_block`,
  `add_blocks_to_bones` and `trim_plane` in
  `scaffold/pack/armor_stand_geo_class.py`, and a reader without it draws the
  same blocks with more holes in them, and holes that come and go.
- **Water is drawn in pieces.** A structure keeps a waterlogged block's water in
  the second layer of `block_indices`, and Scaffold draws it as more cubes in
  the same cell: a box inset a hundredth of a block, its surface at 12/16, with
  no face against more water and no top under more water, where it fills its
  cell. Its sides and bottom go in the standing block's own bone, straight after
  the block; its top is a quad of its own, drawn there too unless the block
  covers the surface and its own top has clear texels, a grate or leaves, when
  it is drawn early, before the block, to show through them. A block that is
  all planes, copper bars or kelp, has all of its water drawn after the planes.
  `core.water_families` decides; the families are `water`, `water_late`,
  `water_surface`, `water_surface_late` and `water_surface_early`.
- **Redstone dust's joins are worked out, not read.** Bedrock saves a dust
  block's `redstone_signal` and nothing about which way it runs, so Scaffold
  works the joins out from the neighbours, by the rules in
  `lookups/dust_connections.json`, and hands the `red_dust` family four states,
  `scaffold:dust_north` and the rest, each `none`, `side` or `up`, which its
  `data` rule joins into the form's name. A reader without that draws every
  dust as the lone cross, its `default` form.

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

The export above is a bridge: it fits Scaffold's tables into 1.7's shape and
loses what that shape cannot hold. Reading format 2 directly loses nothing, and
is mostly a matter of moving decisions out of Structura's code and into the
tables. This is an outline of the work, not a design, and it names the
Scaffold file each piece can be compared against. The converter in this handoff
is the place to start reading: it already reads every format 2 table and
answers, per block, the cubes and textures a reader should produce.

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
`texture_by` rules do all of that, and the form drawn is the first of
`<mounting>-<value>`, `<value>`, `<mounting>` and `default` the family has.
Structura needs one small rules reader in place of both, which hands
`make_block` a form name, a rotation and a texture index. "Choosing a form"
above is the whole of what it has to do; `ArmorStandGeo.choose` in
`scaffold/pack/armor_stand_geo_class.py` is Scaffold's.

**Rotation in Minecraft's angles.** A rotation table holds the game's angle
for a state, or names a table in `state_rotations.json`. A missing key means
"no turn" rather than an error, a `"<form>:<value>"` key is read before the
plain value, and the angle is turned into a bone rotation in one place by
negating y and z, which is `to_bone`. Blocks also rest facing north now, so
any rotation Structura applies outside the tables has to be checked against
that.

**Per-cube faces.** Every cube carries its own six faces, each a texture
object: a `slot` to read from the block's own `blocks.json` entry, a
`texture` named outright, a `window` into the picture, a `turn` and a `tint`.
`block_name_to_uv` and the `overwrite` lists it reads are replaced by reading
those objects. The atlas then has to be keyed by the whole of what is drawn,
texture, window and turn together, since two faces reading different windows
of one file are two tiles. A face with a window of no size is left out of the
model.

**The atlas as a grid.** 1.7 stacks every tile in one column. A structure with
many distinct textures makes a picture taller than a graphics card will hold,
and the game crashes loading the world. A fixed number of columns, with UVs in
tile units, fixes it; Scaffold uses sixty-four. This is worth doing whatever
else is done.

**Block entities.** Some forms depend on the entity beside the block: a
banner's dye, a bed's colour, a statue's pose, a lectern's book, a shulker
box's facing, a chest's pairing, a pot's plant. The structure keeps them in
`block_position_data`, keyed by the block's index. Structura's reader would
need to hand each block its entity alongside its states, and the rules reader
to look fields up there when a rule names `entity`. A reader that skips this
draws those blocks as with no entity, which is what the export does today.

**Water and the second layer.** `block_indices` has two layers, and the second
holds the water a waterlogged block stands in. 1.7 reads the first only.
Drawing water is optional, but if it is drawn it needs the ordering below or it
hides what stands in it.

**Draw order.** A ghost is blended, and the game draws a model's bones sorted
by name. 1.7 writes one bone per slice, so the order within a slice is the
order blocks were added, and planes and water land wherever they fall. Naming
bones so planes and water sort after the blocks, and keeping anything that has
to follow one block in that block's own bone, removes most of the holes a
blended ghost shows. "Things the format relies on" has the order Scaffold uses.
This is engine work rather than table work and can come later.

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

## What the 1.7 export cannot carry

`python -m tools.export.structura <out> --report` lists every case. Running
1.7's own code over the export and comparing it with Scaffold cube by cube,
against Structura 1.7 as released (`V1.7-rel`), over 19,003 states of 1,370
blocks, it draws 6,137 the same and skips none, within a few cases of the 6,122
the report predicts. Most of the rest are doors, walls, panes and fences in every
arrangement of their states. What remains:

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
  leaning the wrong way. This is the one difference the export does not
  predict, and it is measured by the comparison, not seen in game.

The export also works around 1.7 in ways worth knowing before editing it by
hand: forms are padded with cubes of no size so a data form finds its windows in
`default`'s list, every texture is resolved per block and cut into
`textures/scaffold/` where Scaffold cuts or turns one, and every face of every
block is named outright, so `blocks.json` holds only placeholders and the few
lists a `variant` state picks from.
