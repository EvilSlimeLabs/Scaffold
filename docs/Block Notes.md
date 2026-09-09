# Block notes

What to know before adding a block, changing how one looks, or working out why
one looks wrong. The tables themselves are described in `docs/Editing Blocks.md`;
this is the accumulated knowledge that is not obvious from reading them.

Coverage is closed and stays closed. Check it at any time:

```bash
python -m tools.checks.blocks         every declared block resolved to a texture
python -m tools.checks.coverage      what the bundled structures drop
```

Both should report nothing missing. `coverage_report.py` drives the real
pipeline against all 108 bundled structures, so it is the fastest way to see
whether a lookup change broke something.

---

## How a block becomes geometry

1. `lookups/block_definition.json` maps the block id to a **shape family**. No
   entry means the block is skipped and reported, not drawn.
2. `lookups/nbt_defs.json` says what each of the block's **states** means.
3. `scaffold.core._process_block` turns those states into a rotation, a
   texture variant, a shape variant and a few flags.
4. `armor_stand_geo_class.make_block` reads `block_shapes.json` and
   `block_uv.json` with the resulting variant name and emits cubes.

**`block_shapes.json` and `block_uv.json` must agree.** A variant in one and not
the other silently falls back to `default`, which is how a half-height cube ends
up wearing a full-height texture. Add variants to both.

---

## What a state can mean

`nbt_defs.json` maps a state name to one of these:

| Meaning | Effect | Example |
| --- | --- | --- |
| `rot` | picks a rotation from `block_rotation.json` | `minecraft:cardinal_direction` |
| `variant` | picks an index into a texture **list** via `variants.json` | `rehydration_level` |
| `top` | selects the `top` shape variant | `upper_block_bit` |
| `open_bit`, `hinge` | door and trapdoor flags | `open_bit` |
| `data` | the state's number names the shape variant | `books_stored` |
| `shape` | the state's **value** names the shape variant | `attachment` |

`data` and `shape` both end up as the variant name. `data` is for numbers,
`shape` for words, because an `int()` on `"hanging"` raises. When a block carries
several `shape` states they are joined with `-` **in the order the state names
sort**, so `attached_bit` before `hanging` gives `"0-1"`. Write the variants in
that order or they will never be found.

A state that is not in `nbt_defs.json` is ignored entirely. That is the usual
reason a block looks the same however it is placed.

---

## Rotation tables need every form of the value

Bedrock gives some blocks a numeric `direction` and others a
`minecraft:cardinal_direction` **string**, and a few blocks carry both across
versions. `block_rotation.json` is a plain lookup: a value it has no key for is
drawn **unrotated, silently**.

That is what made every door face the same way. `door` had `0`–`3` and the
structures were giving it `"east"`. Twelve families had the same gap.

The numbering is not the same for every block:

- most blocks: `0` south, `1` west, `2` north, `3` east
- **doors**: `0` east, `1` south, `2` west, `3` north
- **trapdoors**: `0` east, `1` west, `2` south, `3` north
- **standing signs, and hanging signs fixed to the block above**: sixteen steps
  of 22.5°, not four

When adding a family, give it both the numbers and the words.

**A form may number its rotations differently from the rest of its family**, and
says so with a `"<variant>:<value>"` key, which is read before the plain value.
A hanging sign needs this because Bedrock gives it two rotation states and only
one applies: fixed to the underside of a block it turns with
`ground_sign_direction`, sixteen steps, and swinging from a chain or mounted on
a wall it turns with `facing_direction`, four values, the other reading zero.
`core.py` picks the state, `block_rotation.json` scopes the four values to the
forms that use them, and `2` means something different in each numbering.

**Which way "facing 0" actually points is not knowable from here.** The tables
follow the convention every existing entry uses; confirm a new one in a world.

**A mounting is the same piece run further, not a second piece bolted on.** A
hanging sign on a wall was written as the form fixed under a block plus an arm
running back into the wall, and the arm read as a post nobody asked for. The bar
it already has goes out to the edges of the block instead, the way a bell's beam
spans two walls.

**A family turns about the middle of its block.** `center` in
`block_shapes.json` is that pivot, and a family whose cubes all sit at one edge
is tempting to pivot on that edge instead. Doing so takes the block out of its
own block: a door pivoted on the plane of its own panel, a quarter turn round,
ended up half in the block beside it. Only a family whose parts really do turn
about something other than the middle — a grindstone's wheel, a campfire's
fire — should say so, and then only in the axis it needs.

**A door's panel sits on the side it faces**, at `z` 13 when it faces south, the
way it does in the game: place a door standing to its south and the panel is on
the side nearest you. It was at `z` 0, so every door was drawn against the far
side of its own block.

---

## One texture per cube, not per block

Bedrock declares six textures for a block: up, down and the four sides. A block
built from one cube can use them directly. A block built from several **cannot**:
without help, every cube gets the same six, so a grindstone's legs are painted
with the wheel's texture on top and a beacon's glass shell, its core and its
obsidian base are all painted alike.

`block_uv.json` has an `overwrite` entry for this: a texture per cube, per face.

```json
"overwrite": {"up": ["@down", "@up", "@north"], ...}
```

- a literal path is used as given
- `"default"` leaves that cube's face alone
- `"@up"`, `"@down"`, `"@north"` … mean **whatever this block declares for that
  face**, which is how one entry serves every wood a sign comes in and every
  state a campfire has without naming a single texture file

Prefer the `@` form. It survives a block gaining new variants and works for
families shared by many block ids.

---

## Textures that are not what they seem

- **Some are lists.** `terrain_texture.json` may map one name to several files.
  `dried_ghast_front` is four, one per drying stage. The `variant` mechanism
  indexes them through `variants.json`. A numeric state arrives from nbtlib as
  `Int(0)`, whose `str()` is `"Int(0)"` and not `"0"`; the lookup converts.
- **Some are flipbooks.** `campfire.png` is 16×128, eight stacked frames, and
  `campfire_log_lit.png` is 16×64. Using one whole stretches every frame over the
  face; the UV window has to take one frame's worth of `v`.
- **Some are named and do not exist.** `blocks.json` names
  `chiseled_bookshelf_front`, which no vanilla pack ships and
  `terrain_texture.json` has no entry for. Name the real texture in `overwrite`.
- **Some are entity sheets.** `copper_golem.png` is 64×64 and `oak_hanging_sign.png`
  is 64×32, atlases laid out for an entity model rather than tiles.

Only the **top left 16×16** of a texture becomes a tile; a larger one is cropped,
never scaled, so its pixels keep their size. A block drawn from a sheet says
which part it needs by writing a window after the texture's name:

```json
"overwrite": {"north": ["@north#0,12", "@north#4,0"]}
```

`#x,y` is the corner of the 16×16 window, in pixels, and it travels with an `@`
reference so one entry serves every wood. Each window becomes a tile of its own,
because the atlas is keyed by the whole name. A hanging sign reads three: the bar
at `#4,0`, the chains at `#0,6` and the board at `#0,12`. A window that falls
outside the texture is ignored, so a legacy id resolving to a plain terrain tile
still reads the tile.

**UV `v` grows downward.** The upper half of a tile belongs on the upper half of
a block. A bottom slab shows the *bottom* half of its texture. Getting this
backwards is invisible on stone and obvious on planks.

---

## Not everything is in the block states

A copper golem statue keeps its **pose** in the block entity beside the block,
the way a sign keeps its text. A structure holding four statues in four poses has
one palette entry for all of them, and the pose is in
`structure.palette.default.block_position_data`, keyed by the block's flat index
(x outermost).

`structure_reader.get_block_entity(x, y, z)` reads it and
`scaffold.core.ENTITY_SHAPES` says which field of which block entity names the
shape. Add to that mapping to support another one. A block entity carries a
great deal that has nothing to do with how a block looks, so only the named
fields are read.

**A block entity may hold another whole block.** What is planted in a flower pot
is kept beside the block as `PlantBlock`, a compound with a name and states of
its own, and nothing about it is in the pot's states. `core.ENTITY_HOLDS` names
that field, and `core.Scaffold._drawn_at` turns one position into the pot plus
the plant, so the plant is drawn where the pot is and by whatever family it
belongs to. That is what makes every pottable plant work without a variant
apiece; the cost is that a plant Scaffold cannot draw lands in the skipped list
while the pot around it is still drawn.

Two things follow from it. The plant is drawn at its own full size rather than
shrunk into the pot, because a family cannot be scaled from outside, so its
lower half is inside the pot. And the plant is **not** in the block list: that
is counted off the structure's palette, which the pot's contents are not part
of.

---

## High and low geometry

Every ghost block is geometry the client lights and draws, and Vibrant Visuals
makes that markedly more expensive. A family may declare a simpler form of
itself, named with the `__low` suffix (`bell__low` beside `bell`), and a pack
built with low geometry uses it. A family without one is drawn as it always is,
which is most of them.

`tools/blocks/simplify.py` generates those forms for every family carrying
three or more cubes: the box the detailed shape fits inside, textured with the
window that box covers. **Re-run it after changing a detailed shape**, or the
simple form will still be the old one's outline.

---

## Approximations, and what still wants checking in a world

Geometry numbers and UV values can be checked here. How they look cannot.

- **A copper golem statue's four poses are four geometry files.** The community
  submodule ships `copper_golem`, `copper_golem_sitting`, `copper_golem_running`
  and `copper_golem_star`, and each is the golem's nine or eleven cubes with the
  arms and the legs turned where that pose puts them. Which `Pose` number goes
  with which file is the guess left in it: the order below is the order the game
  numbers them in, and only a world settles that. `tools/blocks/statues.py`.
- **The statue is taller than the block it stands on**, twenty four pixels to
  the top of its pompom, and is drawn at that size. Shrinking it would put the
  ghost somewhere the real statue will not be, which is the same reason a dragon
  head keeps its own size.
- **The eight oxidation stages all wear the unweathered sheet.** Every one of
  them declares the same texture name in `blocks.json`, and nothing in the block
  says which stage it is, so one family answers for all eight. The community
  pack ships `copper_golem_exposed`, `_weathered` and `_oxidized` beside it if
  that is ever worth eight families.
- **Which side a wall mounting attaches to** is taken from the convention
  `wall_sign` uses: at 0° a block faces south, so the wall is behind it at
  `z=0`, and a bell's beam, a grindstone's legs and a hanging sign's arm all run
  that way. If they come out of the wrong face in a world, that convention is
  what to flip.
- **A grindstone fixed to two walls** puts legs into both, by analogy with the
  bell's `multiple`, which spans two walls. The state appears in no test
  structure, so this form has never been built from a real one.
- **The campfire's fire** is two quads crossed through the middle of the block,
  the way vanilla draws a flame, textured from frame 0 of the flipbook. It does
  not animate: a ghost block has no flipbook.
- **A campfire's log tile is three pictures stacked.** `campfire_log` holds the
  bark across its top four rows, the cut end of a log beside it in the next
  four, and the ash the fire sits in across the bottom half; `campfire_log_lit`
  is the same layout, four frames deep, with the embers glowing. A face taking
  the whole tile wears all three. The ash is a plate one pixel deep across the
  floor with the logs standing in it, so it shows through the square between
  them. Two things are approximations: the ash reads a 16×8 window on a 16×16
  face, so it is stretched twice over, the way vanilla's own model stretches it;
  and a log lying along `z` has a top four across and sixteen deep while the
  bark is drawn the other way round, and a window cannot be turned, so those two
  faces take the bark as it is. Both are under the logs above them or on the
  floor.
- **Two block tall flowers** take the block's `down` texture on the lower half
  and `up` on the upper. Bedrock's `side` texture for these is a different
  plant's back and should never be used.
- **A bed is drawn in its colour, and the colour is a second set of tiles.**
  It is in the block entity, as `color`, and which half the block is is in its
  states, so `core.ENTITY_ADDS` joins the two and a variant is named
  `<head_piece_bit>-<colour>`. That is the one field of a block entity that goes
  *with* a shape state rather than instead of it. The game holds a model per
  colour rather than tinting anything, so `tools/textures/beds.py` recolours
  the red tiles the pack ships: only the blanket, which is the only strongly red
  part, and each pixel keeps how bright it is against an ordinary blanket pixel
  in its own tile. Multiplying a red tile by a dye gives mud. A bed with no
  entity beside it falls back to red.
- **A banner is drawn in its colour but without its patterns.** The colour is
  the block entity's `Base`, counted in the same order as wool, and
  `tools/textures/banners.py` dyes the sheet once per colour so each has a
  texture to read: vanilla tints one white sheet at run time and a ghost block
  cannot tint. Patterns are a different matter. A banner may carry six, each
  with a colour of its own, which is more combinations than could be written to
  disk, so they would have to be composited while a pack is built and handed to
  the atlas as a picture rather than a file.
- **Only a banner's cloth is dyed.** The post up the right of the sheet from
  `x44` and the bar across the bottom of the cloth from `y42` are wood, and
  `make_banner_textures.py` leaves both alone: dyeing the whole sheet gives every
  banner a post in its own colour, which is what it did. The post and the bar
  name those corners of the sheet, and the post reads a sixteen tall slice of a
  strip the sheet draws forty two tall, because only that much of a texture
  becomes a tile and the post is one colour all the way down.
- **A banner is two blocks tall and stands out of its own block**, the way the
  game draws one and the way a dragon head and a copper golem statue do here. A
  wall banner hangs the other way, down past its own floor. Kept inside one
  block a banner reads as half a banner, which is what it did.
- **A head standing on the floor turns with its block entity.** The states say
  only which of the six faces it is fixed to; the sixteen steps round are the
  `Rotation` field, which `core.ENTITY_ROTATIONS` reads and hands over as
  `spinN`, named apart from the facings because those are numbers too.
  **That numbering starts half a turn from the block convention.** A block at
  rest faces south and a skull whose `Rotation` is zero faces north, so
  `make_head_forms.FLOOR` adds 180 to the plain facing and to every one of the
  sixteen steps. Without it every head in a build faced away from where it was
  placed. The wall facings do not carry it: those come from `facing_direction`,
  which names the way the head looks, and the wall form is already built
  sitting against the wall behind it.
- **A conduit is drawn closed.** Bedrock gives the block no state for being
  active, because whether it is depends on the frame of prismarine around it at
  run time, so a structure file cannot say. The open form is written and
  reachable if a state ever appears.
- **A player head is always Steve.** A skin is the player's own and a resource
  pack cannot know it, so every player head wears the default one.
- **Every head is the model the game draws it with.** `entity/skull.entity.json`
  names four geometries, one per kind of head, and the community submodule ships
  them: `geometry.mob_head` and `geometry.player_head` in `models/mobs.json`
  alongside `geometry.dragon_head`, and `geometry.piglin` as a file of its own.
  So the piglin keeps its snout, its tusks and its ears, and the dragon all
  seven of its pieces, at the sizes and UV corners Mojang drew.
- **A bone that turns has to be turned on the way in.** The piglin's ears are
  bones the game leans thirty degrees about pivots of their own, and a head
  built from the cubes alone leaves them flat against the skull. Scaffold turns
  a cube about the cube's own middle, so `make_head_forms.on_its_own` moves the
  middle to where the bone's pivot would have put it and keeps the same turn on
  the cube, which comes to the same thing. Bedrock's angles run the other way
  round from the usual mathematical ones, and the ears are what settles that:
  only one of the two signs takes them away from the head rather than into it.
- **A dragon head is bigger than the block it is placed on**, and is drawn that
  way: sixteen across, twenty tall and thirty deep, with the snout a whole block
  out the front and the jaw hanging below the floor. Shrinking it to fit would
  put the ghost block somewhere the real one will not be. It is the one head
  that leaves its block.
- **A head is placed about its pivot**, which sits at the middle of the block's
  floor: a mob head's cube runs from y24 to y32 and appears in the bottom half
  of its block. A head on a wall is the same model four pixels higher and four
  further back.
- **A brewing stand's three plates are placed from the sockets on its base
  tile.** Bedrock ships no model for this block and `brewing_stand_base` is
  opaque across the whole of its tile, so nothing in the pack says where one
  plate ends and the next begins except the three bottle sockets drawn on it, at
  (3.5, 3.5), (3.5, 11.5) and (12, 7.5). Each plate is the part of the tile its
  socket sits in the middle of: the whole of one side, and the other side
  halved, with the two pixel channel between them that the rod stands in. The
  arrangement is right; whether vanilla leaves more of a gap between them is not
  knowable from here.
- **A brewing stand's bottles are two crossed quads of an item texture.**
  `brewing_stand_slot_a_bit` and its two fellows say which of the three slots
  are full, and they are shape states, so the family has eight forms.
  `potion_bottle_empty` is an item texture rather than a terrain tile and had to
  be copied out of the community submodule; a bottle's own colour is not in the
  block, so every one of them is drawn empty.
- **The compost heights, the egg positions and the cocoa sizes** are plausible
  rather than measured from the game. The counts and the stages are right; where
  exactly each egg sits in its clutch is not knowable from here.
- **A shelf's compartments are cut, not painted.** Vanilla paints the three
  openings into the front texture and leaves the block a plain box, which reads
  as a shelf while the block is opaque and as a box once it is half
  transparent. The frame and the two uprights are geometry here, so the openings
  are openings. The back panel keeps the painted front, which is what gives the
  compartments their shading inside. A sculk shrieker gets the same treatment
  from the other end: it is half a block tall with a plate under the lid, since
  its top texture is four corner blobs with a hole between them.
- **String is drawn with a tile of its own.** Vanilla's `trip_wire` is a scatter
  of faint single pixels across a quarter of the tile, drawn on a quad turned to
  face the way the wire runs and lit at full brightness. On a half-transparent
  plate lying flat in its block it cannot be seen from more than a few blocks
  away, so `tools/textures/string.py` writes a cross of solid lines instead.
  **A cross because the direction is not in the block:** `trip_wire` carries
  `attached_bit`, `disarmed_bit`, `powered_bit` and `suspended_bit` and nothing
  saying which way the wire runs, so the game works that out from the blocks
  beside it while it draws and a structure file cannot say.
- **`blocks.json` names texture slots, not faces.** For nearly every block the
  two are the same. `big_dripleaf` is where they part: it reads `up:
  big_dripleaf_side2`, `down: big_dripleaf_side1` and the leaf on three of the
  sides, because the engine picks from those slots for a model of its own.
  Read as faces, the leaf's top wears four rows of edge profile over an empty
  tile and the block is very nearly invisible from above, which is what it was.
  Its faces name their textures outright now. A family whose block has this
  shape of entry has to do the same.
- **One dripleaf block id is two different things.** `big_dripleaf_head` says
  whether a block is the leaf you stand on or a length of the stalk holding one
  up. It is read as a shape state, so the two are separate forms. Both put the
  stalk in the same place, so a dripleaf several blocks tall lines up.
- **`small_dripleaf_block` is still `ignore`**, and is drawn as nothing. Its
  textures are the odd ones out in the pack: `small_dripleaf_top` has its art in
  an 8x8 corner of a 16x16 file and `small_dripleaf_side` has four pixels in its
  top row, so what those tiles are meant to be read as is not settled.

The forms a block takes from how it is mounted are written by
`tools/blocks/mounted.py`, which owns the shapes and the UV windows for
`hanging_sign`, `bell`, `grindstone` and `campfire`. Each mounting is a
different list of cubes rather than the same list moved:

| Family | The forms, and what carries the block |
| --- | --- |
| `bell` | the bell in two pieces, the narrow body over its flared lip, and then `standing` a beam across two stone posts, `multiple` the beam alone between two walls, `side` half a beam out of one wall, `hanging` a short bar up to the block above |
| `grindstone` | a wheel eight across, twelve tall and twelve deep, its round faces on the x sides where the axle runs, with a pivot each side, and `standing` legs to the floor, `hanging` legs to the block above, `side` legs into the wall behind, `multiple` legs into both. The wheel takes three quarters of the block, so where it sits is what the mounting decides |
| `hanging_sign` | `0-1` chains, `1-1` a bar under the block it is fixed to, `0-0` the same bar run out to the edges so it reaches the wall. Named by `attached_bit` and `hanging`, joined the way `core.py` joins shape states |
| `campfire` | a plate of ash across the floor with two logs standing in it and two more across those, and `0` the fire over them, `1` without |
| `door` | `default` shut, on the x side with its picture mirrored, `open` and `open_hinged` folded back against the wall on whichever side the hinge is, `top` nothing at all because the lower block draws both halves. Its four thin faces read the frame down the side of the tile, not the whole door squeezed into three pixels |
| `shelf` | a case: a floor, a ceiling, two ends, a back and two uprights, and the three compartments are the gaps between them. Built from what the sheet draws, which parts the openings at x5 and x10 and borders them at x0 and x15 |
| `tripwire_hook` | a plate four across and eight tall on the wall, a shaft out of it, and the ring square across the shaft's end. `0-0` the shaft up at 45 degrees with the ring on the low half of its end, `1-0` the wire pulling it down near the horizontal, `1-1` engaged, the shaft down at 45 degrees with the ring on the high half and square to the ground. Named by `attached_bit` and `powered_bit` |
| `sculk_shrieker` | half a block tall, with a second plate under the lid so there is something down the throat |
| `tripwire` | one flat plate a pixel and a half off the floor, wearing a tile drawn for it |
| `cauldron` | a pot with a floor and four walls, and a flat surface of whatever it holds inside it. `cauldron_liquid` and `fill_level` joined name the form; dyed water is `water` with a whole RGB in the block entity, which becomes the liquid `dyed`, and the tile is tinted with that colour as the pack is built |
| `flower_pot` | four terracotta walls a pixel thick with the soil sunk inside them, six across and six tall |
| `decorated_pot` | a body fourteen across and twelve tall with an eight by four neck on top of it, every face naming its own part of the 32x32 sheet |
| `brewing_stand` | a two by thirteen rod with three six by six plates round it, an arm out to each, and a bottle on a plate for each of `brewing_stand_slot_a_bit` and its two fellows. Each plate reads the socket drawn for it on the base tile, so the picture turns with the stone |
| `heavy_core` | one eight by eight by eight cube, its top, its bottom and its four walls reading the three pictures its file holds |
| `dried_ghast` | a ten by ten by ten body on the floor with six tentacles lying flat around it, all of it keeping the block's own faces so it follows `rehydration_level` |

Three more scripts write the families whose form follows a state:

| Script | What it owns |
| --- | --- |
| `tools/blocks/growing.py` | the crops, sweet berry bushes, cocoa, turtle eggs, composters, seagrass and coral fans |
| `tools/blocks/furniture.py` | beds, lecterns, enchanting tables, conduits, daylight detectors, spore blossoms |
| `tools/blocks/heads.py` | the mob heads |
| `tools/blocks/containers.py` | shulker boxes and banners |

**A stage is a family, not a variant of `cross_texture`.** Wheat has eight
textures, one per step of `growth`, and every crop, berry bush and cocoa pod has
its own. They cannot be variants of the shared plant family, because a variant
named "3" there would answer for every cross shaped block in the game that
happened to be in state 3. Each is a family of its own, and its stage textures
are named as literal paths: `terrain_texture.json` has no entry for
`wheat_stage_0`, which is a file in the pack that nothing points at.

**A state that indexes a texture list has to be in `variants.json`.** Without an
entry the index is zero, so every one of them draws the first texture in the
list, silently: that is what made every two-high plant a sunflower, every short
fern a tuft of grass, and every mushroom block wear the inside face.

**A head is an entity sheet.** So is a shulker box, a banner and a hanging sign.
Those sheets live in `textures/entity/` and are copied out of the community
submodule, because the trimmed pack carries only terrain tiles. Each face names
the 16×16 window it reads.

**And a block drawn with an entity's model reads that model's sheet the same
way.** A copper golem statue is drawn with the geometry the game gives the mob,
so `make_statue_poses.py` unwraps each of its cubes the way Bedrock lays a box
out — up and down across the top, then west, front, east and back in a strip —
and each face names its corner of the 64×64 sheet. `make_block_forms.unwrap` is
that layout and `make_block_forms.spun` is the turn a bone or a cube carries;
the mob heads use both. A model built from boxes measured off a picture instead
comes out as a blob wearing terrain tiles, which is what the statue was.

**A dried ghast is twenty four small pictures in full sized files.** Every one
of its six faces has four textures, one per `rehydration_level`, and all
twenty four are 10×10 pictures in 16×16 files. Drawn as a 14×14 cube with faces
working their own windows out, each read x1 to x15 of a picture that stops at
x10, so five sixths of every face was the empty part of the file and the block
came out as slivers. It is the cube those pictures were drawn for, standing on
the floor of the block with **six tentacles lying flat on the ground around
it**: two out of each of its three blank sides and none out of the face, which
is south. Each is three long, two across and one deep, and they sit a pixel in
from the corners of the body. Nothing in the pack says any of that — Bedrock
ships no model for this block and there is no tentacle texture in the trimmed
pack, so they take a patch of the underside for their colour. Everything keeps
the block's own faces, so the whole thing still follows the rehydration level.

**A tile can hold one picture drawn several times over.** A turtle egg's tile is
an egg's side down the left of it with more eggs across and beside it, and a
cocoa pod's is the pod's top in the corner, its side to the right and the stalk
drawn diagonally between them. A face working its own window out from where its
cube sits reads whatever happens to line up with it: a clutch of eggs came out
as pale boxes with the corners of other eggs on them, and a cocoa pod came out
as bark. Every face takes a picture the size of that face instead, and the pod's
top and side move as it ripens so each stage names its own.

**A bed lies along `x`, with its head at `x16`, because its tiles say so.** On
`bed_head_top` and `bed_head_side` the pillow is the right half of the picture,
and on `bed_head_side` the leg is the last three pixels, so the picture runs
foot to head across its own width. A face's window runs along `x` on the top and
along the block's own axis on the sides, so a bed lying along `z` has its pillow
painted down one side of the mattress rather than across the head of it. The
model lying a quarter turn from the convention is why `bed`'s rotation entry
carries that quarter turn in every facing; if beds come out across the way they
should lie, that is the number to move. **Two legs a block, not four**:
`bed_feet_end` carries a leg at each corner, which is one end seen from outside,
and four to a block puts eight under a bed.

**A tile that runs off the edge of its sheet is not cropped short.**
`extend_uv_image` drops the corner altogether and reads the sheet's own top
left, so the face comes out wearing something else entirely with nothing to say
it did. The piglin's right ear asked for a tile at `x60` of a 64 wide sheet and
came out wearing the side of its head. Pull the corner back far enough that the
tile fits, which is what `make_block_forms.on_sheet` does and what
`make_head_forms` reads every face through now.

**A colour that is a whole colour gets a tile of its own, built.** A cauldron's
dye is an RGB in its block entity, not one of a list, so no lookup table could
name a texture for it and a ghost block cannot tint as it draws. Scaffold is a
build step, though: a texture written `<name>~tint` in a table has the block's
own colour put in its place, `core.ENTITY_TINTS` says which field of which block
entity carries one, and `extend_uv_image` multiplies the tile by it on the way
into the atlas. The atlas is keyed by the whole name, so every distinct dye in a
structure lands there once. A block that asks for a tint and has none reads the
plain texture.

**A mirrored picture is a window that runs backwards.** Bedrock reads a negative
`uv_size` from the far edge back, so a face that needs its picture the other way
round takes `(16, v, -16, h)` rather than `(0, v, 16, h)`. A door shut wanted
that, and so does one long side of a bed: the two faces of a box opposite each
other run their windows in opposite directions, so a picture with a side to it
comes out right on one and reversed on the other.

**A texture's own size says how big the part it covers is.** `grindstone_side`
is 12×12 and `grindstone_round` is 8×12, which is one wheel twelve wide, twelve
tall and eight deep, seen face on and then edge on. The wheel was drawn 12×8×4,
a third of the stone that should be there, and no measurement of the block would
have said so — the pictures do.

**Several small pictures in one full sized file is the same trap again.**
`heavy_core.png` is 16×16 and holds three 8×8 pictures: the top with its rings
at (0,0), the bottom beside it at (8,0), and the side under them at (0,8), which
all four walls wear. The last quarter of the file is empty. A face working its
own window out from where the cube sits reads the middle of the file, which
straddles all three pictures and that empty quarter, so the core comes out as
mismatched plates.

**A small picture in a full sized file is the same trap.** `bell_side` is a
16×16 file with the bell drawn in an 8×9 corner of it: the narrow body six
across and seven down, over the flared lip eight across and two down. A face
left to work its own window out from where its cube sits reads the middle of the
file, which is empty, and the bell comes out as a flat plate with a sliver of
metal on it. Both pieces of the bell name their rows. `bell_top` and
`bell_bottom` are the 8×8 faces at each end and are read the same way.

**What holds a block up is not the block.** A bell declares four different
things across its six faces — the bell on north and south, its crown on up, its
rim on down, the beam's dark oak on east and the posts' stone on west — so one
entry serves every mounting without naming a texture. The pieces that carry it
have to say which of those they want: the short bar under a ceiling was left on
the bell's own crown and came out gold.

**A sheet can also sit in `textures/blocks/` and look like a tile.**
`decorated_pot_base.png` is 32×32 and holds the unwrap of the pot's neck across
the top with the body's top and bottom under it, and `flower_pot.png` holds the
rim over the wall in one 16×16 file. A face left to work its window out from
where its cube sits reads those as if they were one picture: the decorated pot
came out with holes through it, because the body's top landed on the neck's
unwrap and on the empty row between the two. `make_block_forms.on_sheet` is what
turns a region of a sheet into a texture reference and a window, pulling the
tile corner back far enough that the region fits inside it and never past the
edge of the sheet. Two regions may share a corner, which is why the last face of
a strip reads from a corner sixteen pixels in.

**A shelf is a box against the wall behind it.** Its texture is a 32×32 sheet
holding four different things: the front with three compartments painted into
it, the solid back beside it, and plain planks across the bottom half for the
top, the bottom and the two ends. Those regions are exactly the unwrap of a
16×16×8 box, which is what a shelf is, and vanilla paints the compartments
rather than cutting them, which is why the front carries their shading. Taking
the whole tile puts the compartments on all six faces.

It fills the back half of its block, `z` 0 to 8, the way a wall sign sits at `z`
0 to 2. Its `powered_shelf_type` state, which says where a shelf sits in a row
of them, is not read: the ends are painted on, and only the value 0 appears in
any test structure.

---

## Adding a block

1. Put the id in `block_definition.json` against a shape family.
2. If the family is new, describe it in `block_shapes.json` **and**
   `block_uv.json`.
3. If it turns, give it a `block_rotation.json` entry with both numbers and
   words.
4. If any of its states change how it looks, map them in `nbt_defs.json`.
5. If it is built from more than one cube, give it an `overwrite`.
6. If it now carries three or more cubes, re-run `tools/blocks/simplify.py`.
7. Run `tools/checks/coverage.py` and `tools/checks/blocks.py`. Both should
   report nothing.

Keep the tables compact. `json.dumps` explodes short numeric arrays across a
line each, which turns a one-value change into an unreviewable diff;
`tools/blocks/tables.py` edits one family's span and leaves the rest of the file
byte for byte alone.
