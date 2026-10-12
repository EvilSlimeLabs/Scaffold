# Roadmap

Features and bug fixes planned for after 1.3.0, roughly in the order they are
likely to be taken up. Nothing here is promised for a particular release. An
item leaves this file when it ships, and goes into `CHANGELOG.md` instead.

---

## Checks in game

Blocks changed in the 1.3.0 round that no world had confirmed when its notes
were closed. Each is a look, not a feature; drop a line once it has been seen.

- **Facing:** cocoa pods and their stem, repeater and comparator torches, bells,
  furnaces, the vault's east and west, wall coral fans, piston arms, observer
  arrows, every trapdoor and door direction.
- **Faces and textures:** big dripleaf's two side pictures, a chiseled
  bookshelf's book order, the plain bookshelf's top, the double chest front, bed
  sides, the calibrated sculk sensor's crystal size, hanging signs on a chain.
- **Test worlds:** no stone platform at 0,0, and the signs hung under each door
  and trapdoor.
- **Waiting on an answer:** glazed terracotta facings 0 and 1; why door edges
  read mirrored (a close-up of one edge, real beside ghost); a lit back on a
  Clearer Redstone piston, now that the pack's source is in `redstone_tweaks/`;
  which waterlogged copper blocks look inconsistent, and from which side; where
  the Clearer Redstone dust look should go as an alternate; how see-through a
  calibrated sculk sensor's clear texels should leave what is behind it.

---

## Blocks

**Decorated pot sides.** A pot is drawn plain. A pot made from sherds keeps
which sherd is on each side in its block entity, and the sherd art is in the
vanilla pack, so each side could wear its own.

---

## What is on and in blocks

**Writing on signs, both sides.** A sign keeps the text for its front and its
back in its block entity. Drawing it means rendering the letters into the
atlas as the pack is built, the way a dyed cauldron's colour is, from the
game's own font.

**Items in item frames.** An item frame's block entity names the item it
holds and how far round it is turned. The item's icon would be drawn on the
frame's canvas.

**Items on shelves.** A shelf keeps the items on it in its block entity, one
per compartment, and each would be drawn in its compartment.

---

## Entities

**Paintings.** A painting is an entity, not a block, so a build's paintings are
missing from its ghost. `core.ENTITY_MODELS` and `tools/blocks/entities.py` were
built for exactly this: a painting is a table entry and a family per motif,
drawn from the paintings' own art.

**Other entities, later.** The cushion was the first and paintings would be the
second. Anything else a builder places and expects to see belongs here once it
is asked for.

---

## Resource packs

**Read blocks from a resource pack or an add-on.** A structure holding a custom
block draws nothing for it, and a texture pack's art is not used. A data-driven
block carries its own `.geo.json` and `material_instances`, and format 2 is in
the same coordinates as a `.geo.json`, so reading one from a pack the user
points at is a conversion rather than a redesign. A plain texture pack is the
smaller half: its `blocks.json`, `terrain_texture.json` and textures layered
over the vanilla pack, the way a tweak already is.

---

## The code

**Errors that look like missing blocks.** Drawing a block, a mark and the water
it stands in are each wrapped in a broad `except Exception`, so a bug in
Scaffold's own code lands on the skipped list as though the block were simply
unknown, and a failed water draw leaves no record at all. A missing table entry
should be told apart from a fault, and a fault reported as one.

**The fingerprint does not name the tables.** A pack's identity is derived from
its name, its settings and its structures, not from the Scaffold version or the
lookup tables that drew it. A release is told apart by the manifest's version,
but two builds from one version whose tables changed in between share an
identity.

**The largest files.** `pack/armor_stand_geo_class.py` (about 1,200 lines)
still has the shape of Structura's builder, with its debug prints and a
`make_block` that does everything; `core.py` is about 1,100 and
`ui/scaffold_gui.py` about 3,400. Each would read better split by what it does.
`LOW_SUFFIX` is defined in both `armor_stand_geo_class.py` and
`block_geometry.py`, and should live in one.

**A faster test suite.** The suite takes about thirteen minutes and every build
runs it. Marking the slow tests, the render manifest and the world builders, so
a quick run can leave them out, would make it something to run between edits.
Several tests also open files without closing them and print a
`ResourceWarning` each time (`test_unpublish.py`, `test_updates.py`).

---

## Packaging

**Classifiers that promise too much.** `pyproject.toml` lists
"Environment :: X11 Applications" and "Operating System :: OS Independent",
while the window is supported on Windows only.

**The licence the package declares.** `pyproject.toml` says `license = "MIT"`,
and the package also carries Bedrock Tweaks' art under its own licence and
Redstone Tweaks' under CC BY-NC-SA 4.0. The declared licence, and
`license-files`, could name all three.

---

## Will not fix

**Education Edition blocks.** The elements, the compound creator, coloured
torches, hardened glass and the rest of Education Edition's 166 blocks will not
be supported. They have families but no textures in the trimmed vanilla pack,
so a structure holding them reports them as skipped.
