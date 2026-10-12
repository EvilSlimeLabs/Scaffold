# Editing blocks

The reference for the lookup tables a block is described by. For the
knowledge that is not obvious from the formats, such as why a door faced the
wrong way, which textures are lists and where a copper golem keeps its pose, read
[Block Notes](Block%20Notes.md) instead.

Every table is keyed by a **shape family** rather than by a block id, so the
hundred kinds of stair share one description.

| File | Keyed by | Says |
| --- | --- | --- |
| `block_definition.json` | block id | which family draws it |
| `block_geometry.json` | family, then form | the cubes, the window and texture of each face, and how a block's states choose a form |
| `block_rotation.json` | family | which state turns it, or a table of its own |
| `state_rotations.json` | state name | Minecraft's own turn for each value of a facing state |
| `block_upgrades.json` | old block id or state | what the current game calls it |

**Every table describes current blocks only.** An older structure's blocks are
translated to the names the game uses today as the structure is read, by
`block_upgrades.json`, so nothing here needs an old id or an old state beside
the new one.

**The geometry tables are format 2**, and say so in a header:

```json
{"$schema": "schema/block_geometry.schema.json", "format": 2, "minecraft": "26.50", "families": {...}}
```

Format 2 means the tables are in Minecraft's frame: coordinates the way a
Bedrock `.geo.json` writes them, in blocks from the low corner of the cell, and
a block at rest facing north. `minecraft` is the game version they were last
checked against. Each file has a JSON schema beside it in `lookups/schema/`,
and `tests/test_lookup_format.py` validates all three against them.

---

## block_definition.json

`"minecraft:oak_door": "door"`. A block with no entry is skipped and reported,
not drawn. The family name is yours to choose; it only has to match the other
tables.

`"ignore"` draws nothing, for blocks that should not appear at all.

**An id here need not be a block.** An entity is drawn as one, under a pseudo id
that `scaffold.core.ENTITY_MODELS` names -- `cushion` is the first. It is an
ordinary entry in every table, and the only thing that marks it out is that no
vanilla `blocks.json` declares it, so its family names all six faces' textures
outright rather than leaning on the block's own declared ones. See
[Block Notes](Block%20Notes.md) for how one reaches the tables at all.

---

## block_rotation.json

A family names the state it turns by, or carries a table of its own:

```json
"anvil": "minecraft:cardinal_direction",
"button": {"0": [90, 0, 0], "1": [270, 0, 0], "2": [0, 0, 0], ...}
```

A name is looked up in `state_rotations.json`, which holds **Minecraft's own
turns**: the shape is drawn facing north at rest, and each value is given the
angle Minecraft gives it. `minecraft:cardinal_direction` is north 0, west 90,
south 180, east 270. `facing_direction` is the same four with down as
`[90, 0, 0]` and up as `[270, 0, 0]`, numbered 0 down, 1 up, 2 north, 3 south,
4 west, 5 east. A numbered `direction` is 0 south, 1 west, 2 north, 3 east, and
a trapdoor's is `weirdo_direction`'s numbering, 0 east, 1 west, 2 south,
3 north. `make_block` turns these into what a bone needs; a table never holds a
bone's turn.

A family carries a table of its own only when its turns are not exactly one
state's: a button lies on its back where `facing_direction` would stand it up.
`tools/blocks/tables.put` writes the state's name whenever a table it is handed
is exactly one of them.

**Every generator writes in these terms**, facing north and with Minecraft's
angles, so what a generator says and what the file holds are the same thing.
Many of the families in `tools/blocks/mounted.py` and its neighbours build their
cubes `behind=True`, which reads the top and bottom backwards and measures a
side's window from the far side of the block: that is how those blocks have
always been painted, and it is a property of the picture, not of the frame.

Keys are strings. **Give every value the family's blocks carry today.** A value
the table has no key for is drawn unrotated with no warning. A key written
`"<form>:<value>"` is read before the plain value, for a form that numbers its
turns differently from the rest of its family.

---

## block_geometry.json

A family holds its forms, always with a `default`, and optionally the simpler
forms low geometry draws, under the same names:

```json
"heavy_core": {
    "forms": {"default": {"center": [0.5, 0.25, 0.5], "cubes": [
        {"size": [0.5, 0.5, 0.5], "offset": [0.25, 0.0, 0.25], "faces": {
            "up":    {"uv": [0.0, 0.0], "size": [0.5, 0.5], "texture": {"slot": "up"}},
            "north": {"uv": [0.0, 0.5], "size": [0.5, 0.5], "texture": {"slot": "up"}},
            ...}}]}},
    "low": {...}}
```

| Key | | |
| --- | --- | --- |
| `center` | required | the point the family's own rotation is applied about |
| `cubes` | required | the cubes, each with a `size`, an `offset` (its low corner) and six `faces` |
| `rotation` | optional, per cube | `[x, y, z]` in degrees, turning that cube alone, as a bone applies it |

Every face has a window and a texture:

- `uv`: where on the tile the window starts, from the **upper left**, as a fraction
- `size`: how much of the tile it takes; negative runs it backwards
- `texture`: what it reads. Left out, the block's own texture for that face.

**V grows downward.** A block sitting on the floor of its cell takes the lower
part of the tile, so its `v` offset is one minus the top of the box.

### texture

A texture is either a slot or a file, and may carry three things more:

| Key | Says |
| --- | --- |
| `slot` | whatever this block declares for that face in `blocks.json`: `up`, `down`, `north` ... |
| `texture` | a path under the pack, such as `textures/blocks/obsidian` |
| `window` | `[x, y]` in pixels: the corner of the 16x16 region of a larger sheet to read |
| `turn` | quarter turns clockwise, in degrees, applied to the tile |
| `tint` | `true`: multiply by the colour the block's entity carries |

Prefer a slot. It survives a family gaining forms and works for a family shared
by many block ids, so one entry serves every wood a sign comes in.

### Choosing a form

A family may say, beside its forms, how a block's states and block entity choose
between them. The rules come first in the entry, a line each:

```json
"door": {
    "pick": [{"when": {"upper_block_bit": true}, "form": "top"},
             {"when": {"open_bit": true, "door_hinge_bit": true}, "form": "open_hinged"},
             {"when": {"open_bit": true}, "form": "open"}],
    "turn_by": [{"state": "minecraft:cardinal_direction"}],
    "forms": {...}}
```

| Rule | Says |
| --- | --- |
| `pick` | the block's **mounting**: the first rule all of whose states match names it, and with none it is `default`. A state may match any of a list of values |
| `data` | the block's **value**, from its states or its block entity; see below. With none it is `"0"` |
| `turn_by` | which state turns it: the first present whose `when` holds |
| `texture_by` | which entry of a texture list its faces read: the state's own number, or its value through `values` |

The form drawn is the first of `"<mounting>-<value>"`, `"<value>"`,
`"<mounting>"` and `default` the family has. So a hopper's `side` mounting and
its lock's `1` make `side-1`, and an unlocked side hopper falls back to `side`.

`data` takes any of:

| Key | The value is |
| --- | --- |
| `number` | the last of these states present, as a number |
| `join` | the values of these states present, joined with `-` in this order |
| `entity` | a field of the block entity, instead: a banner's `Base` |
| `entity_add` | a field of the block entity, after a `-`: a bed's `color` |
| `instead` | `[[field, form or {value: form}], ...]`, a block entity field that names a form outright; the first that answers wins |
| `tinted` | `[from, to]`: with a `CustomColor` in the block entity, a value starting `from` starts `to` instead |

`scaffold/block_geometry.py` is the engine, and its functions are what
`make_block` calls; `ArmorStandGeo.choose` gives the form, the turn and the
texture index a block would be drawn with, which is what a test should ask.

---

### What else reads the rules

Nothing else says what a block state means. A block list names a block's
variant by the state its family's `texture_by` reads, a turtle egg's
`cracked_state`, and so does the skipped report; the gallery shows every value
of every state a family's rules name.

---

## block_upgrades.json

How an older structure's blocks are named today, read by
`scaffold/block_upgrade.py` for every palette entry as the structure is read.
The rules run top to bottom, and each sees the block as the rules above it left
it.

```json
{"id": "minecraft:seaLantern", "becomes": "minecraft:sea_lantern"}
{"id": "minecraft:wool", "by": ["color"], "into": {"silver": "minecraft:light_gray_wool", ...}}
{"id": ["minecraft:wooden_door", ...], "state": "direction",
 "becomes": "minecraft:cardinal_direction", "values": {"0": "south", ...}}
{"id": "minecraft:bamboo_sapling", "state": "sapling_type", "drop": true}
```

| Key | |
| --- | --- |
| `id` | a block id or a list of them. A state rule without one applies to every block |
| `becomes` | on an id rule, the new id; on a state rule, the state's new name |
| `by`, `into` | split one id into several by the value of the states in `by`, joined with `/` when there are two. The states are removed unless `keep` is set |
| `state`, `values`, `drop` | rename a state, map its values, or remove it |
| `set` | states an id rule adds, for a new id that carries one the old did not |
| `before` | a block data version; the rule applies only to entries saved below it. For rules that remap values, where one number meant different things either side of a change |

Ids are renamed and split before states are, so a state rule names the id a
block has become. A new value is written with its JSON type, which becomes the
NBT type: a string, a number, or `true`/`false` for a byte. A value a rule does
not name leaves the block as it was.

**Add a rule when Mojang renames something**, by hand, and check it with
`python -m tools.checks.upgrades --schema <clone>` against a local clone of
PocketMine's `BedrockBlockUpgradeSchema`, which is generated from Mojang's own
server. That schema is LGPL and is read only to check; it is never copied here.

---

## Working on the tables

- Keep them compact. `json.dumps` explodes short numeric arrays across a line
  each, which turns a one-value change into an unreviewable diff.
  `tools/blocks/tables.py` replaces one family's span and leaves the rest of the
  file byte for byte alone.
- Be sparing with cubes. Since Vibrant Visuals arrived, the cost of drawing a
  bone rose sharply, and every ghost block is one. A family carrying three or
  more cubes should have a simplified form; `tools/blocks/simplify.py`
  generates them, and wants re-running after a detailed shape changes.
- Check your work:

```bash
python -m tools.checks.coverage      what the bundled structures drop
python -m tools.checks.blocks        every declared block resolved to a texture
python -m tools.checks.render --manifest    which blocks changed how they look
python -m tools.checks.generators           the generators are idempotent
```

All of them should report nothing.

The last one is the odd one: it runs every generator twice and compares what they wrote. A generator that reads a table, adjusts it and writes it back is right once and wrong the next time the build regenerates -- a carved pumpkin faced a different way on alternate releases for exactly that. It rewrites the tables to find out, so it is a command you run rather than part of the suite.

## Finding a block

The tables name blocks the way Bedrock does, which is not always the way you
would look for one. A banner is `standing_banner`, a block list calls it
"Banner", and the shape family behind it is `standing_banner` again.

```bash
python -m tools.find banner
python -m tools.find block "Raw Iron"
python -m tools.find block '*_slab'
```

**The list a block shows is `--data`.** Given no states, `make_block` draws the
form `--data` names, so those are what it takes. `--state` is the other way in:
the block's own states, which the family's rules turn into a form, a turn and a
texture the way a build does. `find` labels the list `--data` for that reason.

It looks in all three at once -- the block id, the name a block list shows, and
the shape family -- and prints the id, the variants the family has, and the
command that would draw it. A search carrying `*` or `?` is a shell pattern on
the id, matched whole, the way `block_list.json` writes its categories.
`minecraft:lectern` and `lectern` find the same block.

A block that cannot be drawn says so instead of handing you a command that
fails: either it is declared `ignore` and has no shape, or no vanilla pack ships
a texture for it.

### Other things to find

`tools.find` takes what kind of thing to look for, and assumes blocks when
nothing says otherwise, so `find banner` and `find block banner` are the same.

```bash
python -m tools.find texture planks
```

Textures are worth looking up because the pack names them the way Bedrock does
rather than the way anybody would guess: oak planks are `planks_oak`, not
`oak_planks`. It prints the path an `overwrite` entry would name -- pack
relative, no extension, ready to paste -- and the size, because the size decides
how the entry has to be written:

```
textures/entity/banner/banner_red
    size      64x64  bigger than a tile: needs a #x,y window
```

Adding another kind of search is writing a function that takes a search and
returns rows, and naming it in `KINDS`. The dispatching, ranking and printing
are already there.

### When nothing matches

You get the nearest few names, so a typo is one line rather than a hunt:

```
$ python -m tools.find lectrn
nothing in blocks matches 'lectrn'
did you mean: lectern, lantern, fern
```

`--names` prints bare names one per line, for feeding into something else, and
the exit status is 0 when anything matched and 1 when nothing did.

## Looking at a block

Most of what goes wrong with a block is obvious the moment you see it and
invisible in the tables: a face reading the wrong half of a sheet, a window two
pixels off, a picture on its side, a post that stops short of the thing above
it. Finding those by building a pack and walking to an armor stand is slow
enough that it is tempting not to.

```bash
python -m tools.render lectern
```

`tools.render` is shorthand for `tools.checks.render`; the renderer lives under
`checks/` because its other half is the regression check below. A block name the
tables do not carry stops with the nearest few rather than a traceback.

That writes `renders/lectern.png`: the block drawn six ways round, one view per
face, and a three quarter view on the end. A flat view is named for the face it
puts in front of you, so the picture under **south** is what `block_geometry.json`
painted on `south`, square on and at full scale.

The flat views are for reading pixels and the corner views are for reading
shape: a gap under a tilted slab or a post that stops short is hard to see
square on. Corners are named for where you are standing -- `up-se`, `down-nw`
and so on, with `n` meaning -z and `s` meaning +z, the same as the face names.

| Flag | Sheet |
| --- | --- |
| *(none)* | the six faces and one corner, in a row |
| `--no-iso` | the six faces alone |
| `--iso` | all eight corners, four to a row |
| `--all` | the six faces, then all eight corners: three rows |
| `-w NAME` | just that view, on its own and as big as `--scale` allows |

`-w` takes any of the fourteen names, given again or comma separated, and says
which ones it knows if you get one wrong:

```bash
python -m tools.render lectern -w down
python -m tools.render lectern -w up-nw,south --scale 12 --open
```

Every picture in a sheet shares one frame, so a block is the same size in all of
them and the rows line up against each other.

`renders/` is gitignored and made when it is first needed. Nothing in it is
worth keeping -- every picture can be drawn again in a second, so one committed
is only one that will go out of date. The file is named for the block and the
state it was drawn in, so `--rot 3 --data 5` leaves
`standing_banner-rot3-data5.png` rather than writing over the last one.

| Option | What it does |
| --- | --- |
| `--rot N` | the rotation state, as `block_rotation.json` numbers them |
| `-s`, `--state NAME=VALUE` | a block state, given again for several; the family's rules then choose the form, the turn and the texture |
| `--data STATE` | which form to draw. Numbers and words alike: a banner is `0`-`15` for its dyes and `illager` or `designed` for the two that are not |
| `--top` | the `top` form: the upper half of a slab, a door or a tall plant |
| `--scale N` | screen pixels per texture pixel; 8 by default |
| `--bg`, `--background` | what to draw it against: a name like `skyblue` or a hex code like `18181c`, with or without the `#` |
| `--iso`, `--no-iso`, `--all` | which views the sheet holds; see above |
| `--alpha F` | how solid to draw it; 1 is opaque and is the default |
| `-o`, `--output` | a directory to write into, or a `.png` to write; `renders/` by default |
| `--open` | open the picture when it is written |

It is drawn **orthographic and nearest sampled**, both deliberately: a texture
pixel is a square of `--scale` screen pixels, so you can count them against the
source file and say which pixel is wrong rather than that something looks off.

**It draws what the pack ships.** The cubes come from
`armor_stand_geo_class.make_block` and the pixels from the atlas that same
object builds, so what you are looking at is what a player would install. It
never reads `block_geometry.json` itself, and a test enforces
that: a renderer that translated the tables would agree with the tables and tell
you nothing about the translation.

**What it will not tell you.** Z-fighting comes out here as one steady arbitrary
choice and in game as a flicker, so two faces on the same plane look fine.
Transparency over a world, lighting, Vibrant Visuals and the armor stand's own
scaling are all outside it. Those still need a world.

## Noticing what else moved

A table is edited one family at a time and read by everything afterwards, so the
question after a change is not whether it still builds -- `tools.checks.coverage`
answers that -- but which *other* blocks moved.

```bash
python -m tools.checks.render --manifest
```

That draws every **form** of every block the tables can build, fingerprints the
six flat views of each, and compares them against
`tools/checks/render_hashes.json`.

Forms matter: a banner is sixteen dyes and two that are not, a chiseled
bookshelf is sixty-four states, a bed is thirty-five. 1381 blocks are 2239
forms, and a sweep of the default alone would leave out most of the fiddly work
-- an ominous banner's face was coming out cut in half and swapped while a
default-only sweep reported nothing changed.

The corner views are left out of the fingerprint: what they show is what the six
already carry, arranged so a person can see it, so including them would only
make the sweep slower. It names the blocks
that changed. `tests/test_render.py` runs the same comparison, so a block that
quietly changed shape fails the suite rather than reaching a release.

It takes about fifty seconds for twenty-two hundred forms.

When the blocks it lists are the ones you meant to change:

```bash
python -m tools.checks.render --manifest --update
```

**Commit the manifest with the change that caused it.** The point of the file is
that a diff carries both what moved and why, so re-recording it on its own
throws away the only evidence.
