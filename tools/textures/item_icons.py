"""The picture a block shows in the inventory, for low geometry's icon boxes.

    python -m tools.textures.item_icons

Low geometry draws some blocks as their inventory picture on the four sides of
a box: plants, crops, heads and the blocks whose detailed shape is most of a
dozen pieces. `make_block` reads that picture through the `item` slot, which
`lookups/item_icons.json` fills per block. This writes the table and puts every
picture it names into the vanilla pack.

A block's picture is the first of these it has:

  an item named for it    `ITEM_OF`, for a crop the seed or the produce it is
                          planted from; then an item of the block's own name
  its carried picture     when Bedrock declares one, as for a sea pickle
  its own picture         when it declares one picture for every face, as
                          every flower does
  a drawing of it         the block seen from above a corner, the way the
                          inventory shows a block with no flat picture: a
                          bell, an anvil, a head

**The box wears it as an inventory slot**, drawn at twice a block's
resolution: a thirty two pixel picture, read a quarter at a time by the four
quads of each face. It is a light grey border two pixels wide, a medium grey
fill, and the block's picture, trimmed to what is painted in it, inside the
middle twenty four pixels square, so fill always stands between it and the
border. The picture is enlarged by the largest whole number of times that
fits, so its pixels stay square, and shrunk only when it is too large. The
slots are written as `textures/items/scaffold_slot_<block>.png`, and the table
names them.

Nothing here is needed at run time.
"""
import io
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools import sources

from scaffold import jsonc
from scaffold import lookup

PACK = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack")
GAME = sources.resource_pack()
TABLE = os.path.join(ROOT, "scaffold", "lookups", "item_icons.json")
DRAWN = "textures/items/scaffold_%s"
SLOT = "textures/items/scaffold_slot_%s"
## the slot's colours, after the inventory screen's, the slot's size, twice a
## block's resolution, and the room the picture has inside it: two of the
## slot's pixels of border and two of fill on every side
BORDER = (198, 198, 198, 255)
FILL = (139, 139, 139, 255)
SIZE = 32
EDGE = 2
ROOM = 24
## the colour a drawing is made on, taken out again
BACKDROP = (255, 0, 255)

## the item a crop is planted from or grown into, by the item's name in
## `item_texture.json`, or a path where the name is a list
ITEM_OF = {
    "wheat": "seeds_wheat", "carrots": "carrot", "potatoes": "potato",
    "beetroot": "seeds_beetroot", "nether_wart": "nether_wart",
    "torchflower_crop": "torchflower_seeds", "pitcher_crop": "pitcher_pod",
    "sweet_berry_bush": "sweet_berries", "pumpkin_stem": "seeds_pumpkin",
    "melon_stem": "seeds_melon", "cocoa": "textures/items/dye_powder_brown",
}


def blocks_of(families):
    defs = lookup.entries("block_definition.json")
    return sorted(b for b, family in defs.items() if family in families)


def _copy(path):
    """Put a pack picture into the vanilla pack, from the game's resource pack."""
    for kind in (".png", ".tga"):
        source = os.path.join(GAME, path + kind)
        if os.path.isfile(source):
            target = os.path.join(PACK, path + ".png")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            Image.open(source).convert("RGBA").save(target)
            return path
    return None


def drawn(block):
    """The block drawn from above its north-west corner, as a sixteen pixel
    picture on a clear ground."""
    from tools.checks import render
    quads, atlas = render.mesh(block)
    picture = render.draw(quads, atlas, "up-nw", 2, BACKDROP, render._frame(quads))
    picture = picture.convert("RGBA")
    pixels = picture.load()
    for x in range(picture.width):
        for y in range(picture.height):
            if pixels[x, y][:3] == BACKDROP:
                pixels[x, y] = (0, 0, 0, 0)
    box = picture.getbbox()
    if box:
        picture = picture.crop(box)
    picture.thumbnail((16, 16), Image.NEAREST)
    tile = Image.new("RGBA", (16, 16))
    tile.paste(picture, ((16 - picture.width) // 2, 16 - picture.height))
    path = DRAWN % block
    tile.save(os.path.join(PACK, path + ".png"))
    return path


## a name a block declares that is a placeholder, not its picture: every head
## declares `skull`, which is soul sand
PLACEHOLDERS = ("skull",)


def _present(path):
    """A pack path the vanilla pack holds, copied in from the game's resource pack
    if it does not yet, or None."""
    if any(os.path.isfile(os.path.join(PACK, path + kind)) for kind in (".png", ".tga")):
        return path
    return _copy(path)


def icon(block, items, blocks, terrain, geo):
    """The picture one block shows in the inventory, as a pack path."""
    wanted = ITEM_OF.get(block, block)
    if wanted.startswith("textures/"):
        return _copy(wanted) or wanted
    entry = items.get(wanted)
    if entry and isinstance(entry.get("textures"), str):
        found = _copy(entry["textures"])
        if found:
            return found
    declared = blocks.get(block, {})
    carried = declared.get("carried_textures")
    if isinstance(carried, str) and isinstance(terrain.get(carried, {}).get("textures"), str):
        found = _present(terrain[carried]["textures"])
        if found:
            return found
    own = declared.get("textures")
    if isinstance(own, str) and own not in PLACEHOLDERS:
        ## read the way the engine reads it, an entry of a list included
        found = (geo.get_block_texture_paths(block) or {}).get("north")
        if found and _present(found):
            return found
    return drawn(block)


def slot(block, path):
    """The block's picture in an inventory slot, as a pack path."""
    source = None
    for kind in (".png", ".tga"):
        found = os.path.join(PACK, path + kind)
        if os.path.isfile(found):
            source = found
            break
    tile = Image.new("RGBA", (SIZE, SIZE), BORDER)
    tile.paste(Image.new("RGBA", (SIZE - 2 * EDGE, SIZE - 2 * EDGE), FILL), (EDGE, EDGE))
    if source:
        picture = Image.open(source).convert("RGBA")
        ## an animated strip's first frame
        picture = picture.crop((0, 0, picture.width, min(picture.height, picture.width)))
        box = picture.getbbox()
        if box:
            picture = picture.crop(box)
            ## as large as a whole number of times its own size allows, so
            ## every pixel of it stays square; shrunk only when it does not fit
            times = ROOM // max(picture.width, picture.height)
            if times >= 1:
                picture = picture.resize((picture.width * times, picture.height * times),
                                         Image.NEAREST)
            else:
                picture.thumbnail((ROOM, ROOM), Image.NEAREST)
            tile.alpha_composite(picture, ((SIZE - picture.width) // 2,
                                           (SIZE - picture.height) // 2))
    out = SLOT % block
    tile.save(os.path.join(PACK, out + ".png"))
    return out


def main():
    from tools.blocks.simplify import ICON_FAMILIES
    print("writing the inventory pictures")
    items = jsonc.load(os.path.join(GAME, "textures", "item_texture.json"))["texture_data"]
    blocks = jsonc.load(os.path.join(PACK, "blocks.json"))
    terrain = jsonc.load(os.path.join(PACK, "textures", "terrain_texture.json"))["texture_data"]
    from scaffold.pack import armor_stand_geo_class as asgc
    geo = asgc.ArmorStandGeo("icons", offsets=[0, 0, 0])
    table = {block: slot(block, icon(block, items, blocks, terrain, geo))
             for block in blocks_of(ICON_FAMILIES)}
    lookup.save_entries(TABLE, dict(sorted(table.items())))
    print("   %d blocks" % len(table))


if __name__ == "__main__":
    main()
