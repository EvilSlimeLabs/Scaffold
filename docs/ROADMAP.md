# Roadmap

Features and bug fixes planned for after 1.3.0, roughly in the order they are
likely to be taken up. Nothing here is promised for a particular release. An
item leaves this file when it ships, and goes into `CHANGELOG.md` instead.

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

---

## Packaging

**Classifiers that promise too much.** `pyproject.toml` lists
"Environment :: X11 Applications" and "Operating System :: OS Independent",
while the window is supported on Windows only.

---

## Will not fix

**Education Edition blocks.** The elements, the compound creator, coloured
torches, hardened glass and the rest of Education Edition's 166 blocks will not
be supported. They have families but no textures in the trimmed vanilla pack,
so a structure holding them reports them as skipped.
