"""Waxed copper art for the blocks Visual Waxed Copper paints as items.

    python -m tools.textures.wax

Visual Waxed Copper paints each waxed block's carried art: the block's own
picture with a yellow wax drawn round it. For a whole block that is the block
texture with its edge repainted, and a ghost can wear it. For bars, chains and
lanterns it is the inventory icon, laid out nothing like the textures the block
models read, so a chain read from it draws nothing and a lantern reads nonsense;
a lightning rod's is a sixty-four pixel icon given to its top alone; and a
waxed chest's is a single tile where a double chest reads halves beside it.

So for those this writes the block's own textures with the same wax added, into
the staged tweak, and points the tweak's declarations at them:

  a picture with clear pixels   the clear pixels touching the art turn to wax
  a whole tile                  its outer ring turns to wax
  a chest sheet                 the single tile ringed, and the double chest's
                                two halves ringed as one, not along the seam

The wax is the tweak's own five yellows, laid in a fixed pattern.

**A wax line round the art shows only where a face reads past the art.** A
single bar's post, a lightning rod and a lantern read windows that hold nothing
but the art, so the line drawn in the clear pixels round it is never on screen.
Each of those blocks gets a family of its own in the tweak's tables, a copy of
its own family:

  a single bar         the post is a pixel wider each side and reads the
                       waxed picture a pixel further out, so the line round the
                       middle bar is on it; every pixel it reads is opaque
  a lightning rod,     every face reads a tile of its own, its window cut out
  a lantern            and its edge waxed where the window is three pixels or
                       more each way; a thinner piece stays copper. A
                       lantern's and a rod's faces are waxed along the top and left
                       only, so most of the copper still shows how far it has
                       aged

Re-run after staging the tweak again: `tools/vendor/tweaks.py` copies its files
over these. Nothing here is needed at run time.
"""
import io
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VANILLA = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
TWEAK = os.path.join(ROOT, "scaffold", "tweakpacks", "visual_waxed_copper")
OUT = os.path.join(TWEAK, "textures", "blocks")

## the yellows Visual Waxed Copper paints its wax in
WAX = [(250, 171, 28, 255), (253, 193, 52, 255), (246, 219, 112, 255),
       (255, 206, 93, 255), (247, 153, 9, 255)]
AGES = ("", "exposed_", "weathered_", "oxidized_")


def wax_colour(x, y):
    return WAX[(x * 3 + y * 7) % len(WAX)]


def outlined(image):
    """Clear pixels touching the art, waxed."""
    image = image.convert("RGBA")
    pixels = image.load()
    wide, tall = image.size
    out = image.copy()
    done = out.load()
    for x in range(wide):
        for y in range(tall):
            if pixels[x, y][3]:
                continue
            near = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if any(0 <= a < wide and 0 <= b < tall and pixels[a, b][3] for a, b in near):
                done[x, y] = wax_colour(x, y)
    return out


def ringed(image, box, open_sides=()):
    """A whole region with its outer ring waxed, but for `open_sides`."""
    pixels = image.load()
    left, top, right, bottom = box
    for x in range(left, right):
        for y in range(top, bottom):
            edge = {"left": x == left, "right": x == right - 1,
                    "top": y == top, "bottom": y == bottom - 1}
            if any(on for side, on in edge.items() if side not in open_sides):
                pixels[x, y] = wax_colour(x, y)
    return image


def chest_sheet(sheet):
    """A chest sheet, 48 by 16: the single tile ringed, and the two halves of
    the double chest ringed as one, open along their seam."""
    sheet = sheet.convert("RGBA")
    ringed(sheet, (0, 0, 16, 16))
    ringed(sheet, (16, 0, 32, 16), ("right",))
    ringed(sheet, (32, 0, 48, 16), ("left",))
    return sheet


# --- families of the tweak's own -------------------------------------------------

LOOKUPS = os.path.join(ROOT, "scaffold", "lookups")
## the family each waxed block is drawn with, the vanilla picture it reads, and
## which edges of a face are waxed
OWN_FAMILIES = {"lantern": ("copper_lantern", ("top", "left")),
                "lightning_rod": ("lightning_rod", ("top", "left"))}
## the forms a bar stands alone in
LONE_BAR = ("0-0-0-0", "default")
## a window this many pixels or more each way has its edge waxed
RING_FROM = 3
## how much wider a lone bar's post is, each side, in blocks
WIDER = 1 / 16.0


def _box(face):
    """A face's window as a pixel box, and whether it runs backwards each way."""
    (u, v), (su, sv) = face["uv"], face["size"]
    x0, x1 = sorted((u * 16, (u + su) * 16))
    y0, y1 = sorted((v * 16, (v + sv) * 16))
    return (int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))), (su < 0, sv < 0)


def ring_art(image, edges=("left", "right", "top", "bottom")):
    """A window's picture with `edges` of its outer ring waxed where there is
    art."""
    image = image.convert("RGBA")
    pixels = image.load()
    wide, tall = image.size
    if wide < RING_FROM or tall < RING_FROM:
        return image
    for x in range(wide):
        for y in range(tall):
            on = {"left": x == 0, "right": x == wide - 1,
                  "top": y == 0, "bottom": y == tall - 1}
            if pixels[x, y][3] and any(on[edge] for edge in edges):
                pixels[x, y] = wax_colour(x, y)
    return image


def tiled(family, picture, name, edges):
    """A copy of `family` whose every face reading the block's own picture
    reads a waxed tile of its own window instead."""
    import copy
    made = copy.deepcopy(family)
    tiles = {}
    for section in ("forms", "low"):
        for form in made.get(section, {}).values():
            for cube in form["cubes"]:
                for face in cube["faces"].values():
                    if not any(face.get("size", [0, 0])):
                        continue
                    texture = face.get("texture")
                    if isinstance(texture, dict) and "slot" not in texture:
                        continue
                    box, (back_u, back_v) = _box(face)
                    ## a window reads the tile after it is turned clockwise, so
                    ## the cut is taken from the turned tile and the new tile is
                    ## not turned again
                    turn = (texture or {}).get("turn", 0) if isinstance(texture, dict) else 0
                    if (box, turn) not in tiles:
                        key = "scaffold_%s_%d_%d_%d_%d" % ((name,) + box)
                        key += "_%d" % turn if turn else ""
                        tile = picture.crop((0, 0, 16, 16)).rotate(-turn)
                        ring_art(tile.crop(box), edges).save(os.path.join(OUT, key + ".png"))
                        tiles[box, turn] = key
                    wide, tall = (box[2] - box[0]) / 16.0, (box[3] - box[1]) / 16.0
                    face["uv"] = [wide if back_u else 0, tall if back_v else 0]
                    face["texture"] = {"texture": "textures/blocks/" + tiles[box, turn]}
    return made


def _wider_post(cube):
    """A lone bar's post plane or cap, a pixel wider each side, reading a pixel
    further out each side."""
    size, offset = cube["size"], cube["offset"]
    for axis in (0, 2):
        if abs(size[axis] - 0.125) > 1e-6 or abs(offset[axis] - 0.4375) > 1e-6:
            continue
        size[axis] = round(size[axis] + 2 * WIDER, 6)
        offset[axis] = round(offset[axis] - WIDER, 6)
        ## each face running along this axis, and which of its window's two
        ## directions does
        along = {0: {"north": 0, "south": 0, "up": 0, "down": 0},
                 2: {"east": 0, "west": 0, "up": 1, "down": 1}}[axis]
        for name, i in along.items():
            face = cube["faces"][name]
            if not any(face["size"]):
                continue
            if face["size"][i] > 0:
                face["uv"][i] = round(face["uv"][i] - WIDER, 6)
                face["size"][i] = round(face["size"][i] + 2 * WIDER, 6)
            else:
                face["uv"][i] = round(face["uv"][i] + WIDER, 6)
                face["size"][i] = round(face["size"][i] - 2 * WIDER, 6)


def lone_bar(family):
    import copy
    made = copy.deepcopy(family)
    for section in ("forms", "low"):
        for name in LONE_BAR:
            form = made.get(section, {}).get(name)
            if form:
                for cube in form["cubes"]:
                    _wider_post(cube)
    return made


def own_tables():
    """The tweak's geometry, definition and rotation overlays."""
    geometry = _json(os.path.join(LOOKUPS, "block_geometry.json"))["families"]
    turning = _json(os.path.join(LOOKUPS, "block_rotation.json"))["families"]
    families, definition, rotation = {}, {}, {}
    for age in AGES:
        bars = "waxed_%scopper_bars" % age
        families[bars] = lone_bar(geometry["bars"])
        definition[bars] = bars
        for family, (picture, edges) in OWN_FAMILIES.items():
            block = "waxed_%s%s" % (age, picture)
            image = Image.open(os.path.join(VANILLA, age + picture + ".png")).convert("RGBA")
            families[block] = tiled(geometry[family], image, block, edges)
            definition[block] = block
            if family in turning:
                rotation[block] = turning[family]
    _save_json(os.path.join(TWEAK, "geometry.json"), {"format": 2, "families": families})
    _save_json(os.path.join(TWEAK, "definition.json"), definition)
    _save_json(os.path.join(TWEAK, "rotation.json"), {"families": rotation})


def _json(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    print("writing the waxed copper art")
    blocks_path = os.path.join(TWEAK, "blocks.json")
    terrain_path = os.path.join(TWEAK, "textures", "terrain_texture.json")
    blocks, terrain = _json(blocks_path), _json(terrain_path)
    named = terrain["texture_data"]
    for age in AGES:
        plain = lambda name: Image.open(os.path.join(VANILLA, name + ".png"))
        ## bars and lanterns keep the name the tweak declares
        outlined(plain(age + "copper_bars")).save(
            os.path.join(OUT, "waxed_%scopper_bars.png" % age))
        outlined(plain(age + "copper_lantern")).save(
            os.path.join(OUT, "waxed_%scopper_lantern.png" % age))
        ## a chain is two strips, so it gets two names of its own
        chain = {}
        for part in ("1", "2"):
            key = "scaffold_waxed_%scopper_chain%s" % (age, part)
            outlined(plain("%scopper_chain%s" % (age, part))).save(os.path.join(OUT, key + ".png"))
            named[key] = {"textures": "textures/blocks/" + key}
            chain[part] = key
        blocks["waxed_%scopper_chain" % age]["carried_textures"] = {
            "down": chain["1"], "side": chain["2"], "up": chain["1"]}
        ## a lightning rod's every face is the waxed rod
        rod = "waxed_%slightning_rod" % age
        outlined(plain(age + "lightning_rod")).save(os.path.join(OUT, rod + ".png"))
        blocks[rod]["textures"] = {"up": rod, "side": rod, "down": rod}
        ## a chest's sheets, the double chest's halves included
        for part in ("front", "side", "top"):
            sheet = plain("%scopper_chest_inventory_%s" % (age, part))
            chest_sheet(sheet).save(os.path.join(
                OUT, "waxed_%scopper_chest_inventory_%s.png" % (age, part)))
        print("   %s" % (age or "plain"))
    _save_json(blocks_path, blocks)
    _save_json(terrain_path, terrain)
    own_tables()


if __name__ == "__main__":
    main()
