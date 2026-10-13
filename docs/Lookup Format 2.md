# Lookup format 2

Format 2 is how Scaffold's block tables describe every block: its shape, the
textures on each face, the rules that choose a form from the block's states,
and the way it turns. This document is the specification, for anyone writing a
table, editing one, or writing something else that reads them.
`docs/Editing Blocks.md` is the practical guide to changing a block.

The reference reader is `scaffold/block_geometry.py`, which loads the tables
and chooses a block's form, with `ArmorStandGeo.choose` and `make_block` in
`scaffold/pack/armor_stand_geo_class.py`, which turn the result into geometry.
`scaffold/block_upgrade.py` reads `block_upgrades.json`.

---

## The files

| File | Holds |
| --- | --- |
| `block_definition.json` | block id to the family that draws it. **Current ids only** |
| `block_geometry.json` | every family: its forms, each form's cubes and faces, the textures each face reads, the simpler forms low geometry draws, and the rules that choose a form |
| `block_rotation.json` | family to the **state name** it turns by, or to a table of **Minecraft angles** of its own |
| `state_rotations.json` | Minecraft's own turn for each value of each facing state |
| `block_upgrades.json` | an older structure's ids and states to the ones the current game uses, applied as a structure is read |
| `dust_connections.json` | the rules redstone dust is joined to its neighbours by |
| `schema/*.schema.json` | a JSON schema for each of the three geometry files |

Every table opens with the same header, in this order:

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
`block_upgrades.json`. A `block_definition.json` with no header, a bare map at
the top level, is the same table and still reads. A reader that finds a
`format` other than 2 should refuse the file.

There is no field naming a coordinate frame: format 2 is defined to be in
Minecraft's frame, described next.

---

## The frame

Every number is in blocks, measured from the low corner of the block's cell. A
form's `center` is the point the block turns about, and a cube's `size` and
`offset` are its extent and its low corner. A block at grid position `x, y, z`,
in a model placed at `offsets`, puts a cube and its pivot at:

```python
origin = [-(x + offsets[0]) + cube_offset[0], y + cube_offset[1] + offsets[1], z + cube_offset[2] + offsets[2]]
pivot  = [center[0] - (x + offsets[0]),        y + center[1] + offsets[1],      z + center[2] + offsets[2]]
```

The block's place in the grid is negated in x, because a model is the world
mirrored in x. The cube's own offset within the block is not.

- **A block rests facing north.** Its front is the north face when nothing turns
  it. This is Minecraft's rest pose, and `minecraft:cardinal_direction` "north"
  leaves it alone.
- **East is the low side of x**, as in every Bedrock `.geo.json`. A model read
  from a `.geo.json` converts with offset = (origin + 8) / 16 across and deep,
  and origin / 16 up, and needs no flip.
- **A rotation table holds Minecraft's angle**, in degrees about x, y and z, the
  way Minecraft turns the block. A bone turns the other way about y and z,
  because the model is the world mirrored in x, so the angle is converted when
  it is handed to a bone:

  ```python
  def to_bone(angles):
      return [angles[0], -angles[1] % 360 if angles[1] else 0,
              -angles[2] % 360 if angles[2] else 0]
  ```

- **A cube's own `rotation` is a bone turn**, about the cube's own centre,
  written the way a `.geo.json` writes one. It is not converted.

These were settled in game with a pack of lettered cubes
(`python -m tools.checks.compass`), with the armor stand placed by somebody
standing north of it and facing south. The ghost turns with its stand, so every
in-game check of a facing needs the stand's placement stated.

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

**A cube's windows are its own.** Every cube in every form carries its six
faces, so a form's shape and its windows are one entry and cannot disagree.

### texture

```json
{"slot": "north", "window": [0, 12]}
{"texture": "textures/blocks/obsidian"}
{"slot": "up", "turn": 90}
{"texture": "textures/blocks/cauldron_water", "tint": true}
```

| Key | Says |
| --- | --- |
| `slot` | whatever the block declares for that face in `blocks.json`: `up`, `down`, `north`, `south`, `east`, `west`; or `item`, the block's inventory picture, which only low geometry reads |
| `texture` | a path under the resource pack, without an extension |
| `window` | `[x, y]` in pixels: read the 16x16 region at that corner of a larger texture, as a tile of its own |
| `turn` | degrees clockwise, a multiple of 90: turn the tile before it is used |
| `tint` | `true`: multiply the tile by a colour the block entity carries |

A face has exactly one of `slot` and `texture`.

What a reader has to do for each:

- **`slot`** reads the block's `blocks.json` declaration (`textures` as a
  string, or a dict with `side` and the six faces) for one face of one cube.
  One family therefore serves every wood a sign comes in, and a door's two
  halves read its two declared textures.
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

Only the top left 16x16 of a texture is ever a tile: a larger texture is
cropped, never scaled.

### low

`low` has the same form names as `forms` and the same layout. It is a simpler
drawing of each form, for clients that cannot afford the detailed geometry.
Everything except the cubes is the detailed family's: the rules, the rotation
table and the centre. A family with no `low` is drawn the same either way, and
a reader with no such setting can ignore it.

---

## Choosing a form

A family may carry up to four rules, written before its forms, and nothing
outside the family decides which form a block is drawn with:

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
entity's `facing`, so its families turn by `{"entity": "facing"}`. A hanging
sign turns by `facing_direction` when it hangs from chains (`attached_bit`
false) and by `ground_sign_direction` when it is fixed under a block.

### texture_by: the texture list

`{"state": name, "values": {value: index}}`. When the block's `blocks.json`
texture is a list, this state's value picks the entry, through `values` or, with
no `values`, as the number itself.

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

The whole engine is about sixty lines: `plain`, `mounting`, `value`, `form`,
`turn` and `texture_index` in `scaffold/block_geometry.py`.

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

- **A missing key draws the block unrotated.** It is not an error.
- **A key `"<form>:<value>"` is read before `"<value>"`**, for a form that
  numbers its turns differently from the rest of its family.
- **A table holds only the values its family's blocks can carry today**: no
  numbers beside words. A family whose blocks carry no facing state has no entry.

An angle that is not a state, such as a floor skull's `Rotation` in its block
entity, is added to the table's y angle as a **yaw** in Minecraft degrees (0
north, 90 west). A skull's `Rotation` runs clockwise from north, so the yaw is
`-Rotation % 360`.

---

## Old blocks

**The tables describe current blocks only.** A structure keeps every block the
way the game named it the day it was saved, so a reader translates a structure's
palette as it reads it, one palette entry at a time, by the rules in
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
- `before` limits a rule to palette entries whose `version` is below it. A
  block with no version, such as the plant a flower pot holds, is taken as
  current.
- `set` writes states onto a renamed block.
- `id` may be a list, and a rule without `id` applies to every block.

A new value is written with its JSON type, which is the NBT type the code then
receives: a string, a number, or `true`/`false` for a byte.

**A state a block never had stays absent.** An old stair has no
`minecraft:corner`; the tables read an absent state as the default form, so
nothing invents one.

---

## Block entities

Rules may read the block entity beside a block. The entity is the compound in
`structure.palette.default.block_position_data[<index>].block_entity_data` for
the block's index in the grid. Scaffold reads these fields:

| Entity | Field | Used for |
| --- | --- | --- |
| `Banner` | `Base`, `Type`, `Patterns` | the dye, an ominous banner, a banner with a design |
| `Bed` | `color` | the bed's dye |
| `Chest` | `pairx`, `pairz` | which half of a double chest, handed to the rules as `pair` |
| `CopperGolemStatue` | `Pose` | which of four poses |
| `Lectern` | `hasBook`, `book` | whether a book lies on it |
| `Cauldron` | `CustomColor` | a dyed cauldron's colour, for `tint` |
| `ShulkerBox` | `facing` | which way the lid opens |
| `Skull` | `Rotation` | a floor head's yaw |
| `FlowerPot` | `PlantBlock` | a whole block planted in the pot, drawn by its own family at the same position |

A block whose entity is missing is drawn as its rules give with no entity: the
default dye, no book, standing pose.

`Base` counts dyes, black 0 to white 15, the opposite way round from wool.

---

## Drawing what the tables describe

The tables say what each block looks like. Drawing it as a ghost depends on a
few things outside them, which any reader has to get right.

- **The atlas is a grid.** Every tile a pack uses goes into one texture, and a
  graphics card holds at most 16,384 pixels a side on a desktop and 4,096 on a
  phone, so a single column of a thousand tiles crashes the game on loading.
  Scaffold lays tiles 64 wide: tile `i` sits at u `i % 64`, v `i // 64`, and
  `texture_width` and `texture_height` are tile counts. Windows, turns and
  tints all add tiles.
- **A window past its tile reads the next tile.** A face's window is in
  fractions of a tile and the atlas does not clamp, so `uv + size` beyond 1
  reads a neighbour. `python -m tools.checks.blocks --tables` lists the faces
  that still do.
- **A ghost is a shade under full size, centred.** Shapes that are more or less
  a full cube are written at about 0.95 of a block, from 0.025 to 0.975 on
  every axis with the centre at 0.5, so a ghost sits inside where the real
  block will go with an equal gap all round and never shares a plane with it.
  A bottom slab runs from 0.025 to 0.525 and a top slab from 0.475 to 0.975, so
  a top slab finishes level with a full block. Leave those numbers alone.
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
  for blocks, then `tier1_` for planes and `tier2_` for water, and an `early_`
  tier sorted before all of them; and it puts anything that must come straight
  after a block, a container's count or the water a block stands in, in that
  block's own bone, after it. It also cuts every plane down to the painted part
  of its tile. This is `make_block`, `add_blocks_to_bones` and `trim_plane` in
  `scaffold/pack/armor_stand_geo_class.py`.
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
  `dust_connections.json`, and hands the `red_dust` family four states,
  `scaffold:dust_north` and the rest, each `none`, `side` or `up`, which its
  `data` rule joins into the form's name. A reader without that draws every
  dust as the lone cross, its `default` form. `docs/Block Notes.md` has the
  rules and where Bedrock differs from Java.
