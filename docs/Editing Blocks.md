# Editing blocks

The reference for the five lookup tables a block is described by. For the
knowledge that is not obvious from the formats, such as why a door faced the
wrong way, which textures are lists and where a copper golem keeps its pose, read
[Block Notes](Block%20Notes.md) instead.

Every table is keyed by a **shape family** rather than by a block id, so the
hundred kinds of stair share one description.

| File | Keyed by | Says |
| --- | --- | --- |
| `block_definition.json` | block id | which family draws it |
| `block_rotation.json` | family | how each rotation state turns it |
| `block_shapes.json` | family, then variant | the cubes |
| `block_uv.json` | family, then variant | the texture window per cube per face |
| `nbt_defs.json` | block state name | what that state means |
| `variants.json` | state name | which entry of a texture list a value picks |

`block_shapes.json` and `block_uv.json` **must agree**. A variant in one and not
the other silently falls back to `default`, which is how a half-height cube ends
up wearing a full-height texture.

---

## block_definition.json

`"minecraft:oak_door": "door"`. A block with no entry is skipped and reported,
not drawn. The family name is yours to choose; it only has to match the other
tables.

`"ignore"` draws nothing, for blocks that should not appear at all.

---

## block_rotation.json

A family maps each rotation state to a turn about X, Y and Z in degrees.

```json
"repeater": {"0": [0, 180, 0], "1": [0, -90, 0],
             "2": [0, 0, 0], "3": [0, 90, 0]}
```

Keys are strings. **Give both the numbers and the compass words**, because
Bedrock uses
a numeric `direction` on some blocks and a `minecraft:cardinal_direction` string
on others, and a value the table has no key for is drawn unrotated with no
warning. The numbering differs between blocks; see
[Block Notes](Block%20Notes.md).

---

## block_shapes.json

A family holds one entry per variant, and always a `default`.

```json
"heavy_core": {"default": {"size": [[0.5, 0.5, 0.5]],
                           "offsets": [[0.25, 0, 0.25]],
                           "center": [0.5, 0.25, 0.5]}}
```

| Key | | |
| --- | --- | --- |
| `size` | required | one `[x, y, z]` per cube, as a fraction of a block |
| `offsets` | optional | one `[x, y, z]` per cube; where each starts. Omitted means the origin |
| `rotation` | optional | one `[x, y, z]` per cube, in degrees, turning that cube alone |
| `center` | required | the point the family's own rotation is applied about |

A variant name comes from the block's states, described under `nbt_defs.json`
below. The
names `top`, `open`, `open_hinged` and `side` are used by the code itself for
upper halves, open doors and trapdoors, and side-fed hoppers.

---

## block_uv.json

The same variants, describing where on the texture each cube's faces are cut
from. All six directions must be present, and each must have one entry per cube.

```json
"heavy_core": {"default": {
    "uv_sizes": {"up": [[0.5, 0.5]], "down": [[0.5, 0.5]], "north": [[0.5, 0.5]],
                 "south": [[0.5, 0.5]], "east": [[0.5, 0.5]], "west": [[0.5, 0.5]]},
    "offset":   {"up": [[0.25, 0.25]], "down": [[0.25, 0.25]], "north": [[0.25, 0.5]],
                 "south": [[0.25, 0.5]], "east": [[0.25, 0.5]], "west": [[0.25, 0.5]]}}}
```

- `uv_sizes`: how much of the tile that face takes, as a fraction
- `offset`: where on the tile it starts, from the **upper left**

**V grows downward.** A block sitting on the floor of its cell takes the lower
part of the tile, so its `v` offset is one minus the top of the box.

### overwrite

Optional, and the only way to give the parts of a multi-cube block different
textures. Without it every cube gets the block's same six faces.

```json
"overwrite": {"up": ["@down", "@up", "@north"], "north": ["@down", "@up", "@north"]}
```

One entry per cube, per face:

- a literal path such as `textures/blocks/obsidian` is used as given
- `"default"` leaves that cube's face alone
- `"@up"`, `"@down"`, `"@north"` … mean **whatever this block declares for that
  face**

Prefer the `@` form. It survives a family gaining variants and works for a family
shared by many block ids, so one entry serves every wood a sign comes in.

---

## nbt_defs.json

What a block state means. A state that is not listed is ignored entirely, which
is the usual reason a block looks the same however it is placed.

| Value | Effect |
| --- | --- |
| `rot` | picks a rotation from `block_rotation.json` |
| `variant` | picks an entry from a texture **list**, through `variants.json` |
| `top` | selects the `top` shape variant |
| `data` | the state's **number** names the shape variant |
| `shape` | the state's **value** names the shape variant |
| `open_bit`, `hinge` | door and trapdoor flags |

`data` is for numbers and `shape` for words. Several `shape` states on one block
are joined with `-` in the order the state names sort, so `attached_bit` before
`hanging` gives `"0-1"`.

---

## variants.json

For textures that are declared as a list. Maps a state's value to the index that
picks one.

```json
"rehydration_level": {"0": 0, "1": 1, "2": 2, "3": 3}
```

Keys are strings even when the state is a number.

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
```

All three should report nothing.

## Finding a block

The tables name blocks the way Bedrock does, which is not always the way you
would look for one. A banner is `standing_banner`, a block list calls it
"Banner", and the shape family behind it is `standing_banner` again.

```bash
python -m tools.find banner
python -m tools.find block "Raw Iron"
python -m tools.find block '*_slab'
```

**The list a block shows is `--data`, not `--variant`.** `make_block` picks a
form by matching `str(data)` against the shape family's own keys, so those are
what `--data` takes. `--variant` is a different axis -- which texture to take out
of a `terrain_texture` list -- and handing it one of these draws the default
without complaining. `find` labels the list `--data` for that reason.

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
puts in front of you, so the picture under **south** is what `block_uv.json`
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
| `-v`, `--variant` | which texture out of a `terrain_texture` list, for a block whose state indexes one. **Not** the form -- that is `--data` |
| `--data STATE` | which form to draw. Numbers and words alike: a banner is `0`-`15` for its dyes and `illager` or `designed` for the two that are not |
| `--top` | the upper half state, for slabs and doors |
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
never reads `block_shapes.json` or `block_uv.json` itself, and a test enforces
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
