"""Stage Clearer Redstone: Redstone Tweaks' art, converted for Scaffold.

    python -m tools.vendor.redstone --source <Redstone Tweaks, a folder or zip>
    python -m tools.vendor.redstone --source <...> --apply

Redstone Tweaks (https://modrinth.com/resourcepack/redstone-tweaks), by
RexxStone with settings by KikuGie, is a Java resource pack. Its art is
converted here into one folder per Clearer Redstone option under
`scaffold/tweakpacks/`, the same place Bedrock Tweaks are staged, and committed,
because a pip install has to be able to offer the options. The source is the
`redstone_tweaks/` submodule, an archival mirror of the releases on Modrinth.
Without `--apply` this says what it would write and writes nothing.

**What is converted, and what is Scaffold's own.** Most of it is Redstone
Tweaks' pictures, cropped to their first frame where Java animates them, and
turned to match the Bedrock texture each one replaces. Java and Bedrock do not
always lay a texture the same way round, so each is tried in all eight turns
and flips against the Bedrock picture it stands in for and kept the way that
matches best. Several things are drawn here in the pack's style rather than
taken from it: the numbers on a cauldron's six levels and on snow layers, the
container counts, a crafter's locked slots, the redstone dust in Bedrock's own
shape, and a hopper's floor, which Scaffold paints into the top of its bowl. The
glyphs are the composter's, read out of the pack.

Only the textures are staged here. Which family reads which of them is
`tools/blocks/redstone.py`, which `tools/generate.py` runs, so the overlay
families follow the tables they copy. Re-run this after updating the pack.

Redstone Tweaks is CC BY-NC-SA 4.0, so everything staged here, the drawn parts
included, is too: `scaffold/tweakpacks/REDSTONE_TWEAKS_LICENSE` says so and is
staged beside it.
"""
import argparse
import io
import os
import shutil
import sys
import zipfile

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools import sources

from scaffold import marks

STAGED = os.path.join(ROOT, "scaffold", "tweakpacks")
VANILLA = os.path.join(ROOT, "scaffold", "Vanilla_Resource_Pack", "textures", "blocks")
GAME = sources.resource_pack("textures", "blocks")
LICENSE = "REDSTONE_TWEAKS_LICENSE"

## where an option's textures go inside its folder, which is also the path a
## family names them by: textures/clearer_redstone/<option>/<name>
PREFIX = "textures/clearer_redstone"

## the colours the drawn numbers are written in, as the composter's three roles:
## the light face of a digit, its shade, and its shadow
REDSTONE = {"L": (255, 74, 58), "M": (196, 30, 20), "D": (40, 8, 6)}
LIQUIDS = {"water": {"L": (52, 138, 247), "M": (42, 111, 208), "D": (52, 52, 56)},
           "lava": {"L": (228, 143, 48), "M": (196, 96, 28), "D": (52, 52, 56)},
           "powder_snow": {"L": (255, 255, 255), "M": (194, 218, 218), "D": (52, 52, 56)}}
EMPTY = {"L": (200, 200, 200), "M": (150, 150, 150), "D": (52, 52, 56)}
SNOW = {"L": (88, 104, 132), "M": (124, 140, 168), "D": (205, 218, 232)}

## the small digits a container count is written in, three by five, at twice a
## block's own resolution
SMALL = {
    "0": ["LLL", "L.L", "L.L", "L.L", "LLL"], "1": [".L.", "LL.", ".L.", ".L.", "LLL"],
    "2": ["LLL", "..L", "LLL", "L..", "LLL"], "3": ["LLL", "..L", ".LL", "..L", "LLL"],
    "4": ["L.L", "L.L", "LLL", "..L", "..L"], "5": ["LLL", "L..", "LLL", "..L", "LLL"],
    "6": ["LLL", "L..", "LLL", "L.L", "LLL"], "7": ["LLL", "..L", "..L", ".L.", ".L."],
    "8": ["LLL", "L.L", "LLL", "L.L", "LLL"], "9": ["LLL", "L.L", "LLL", "..L", "LLL"],
    "+": ["...", ".L.", "LLL", ".L.", "..."],
}
## how far in from the corner of the face a count starts, at twice a block's
## resolution, and how tall one line is with its shadow
COUNT_MARGIN = 2
COUNT_ROW = 16
## degrees anticlockwise a hopper's floor is turned to point at its spout, on
## top of the half turn the bowl's top reads its tile at
HOPPER_TURN = 0


class Source:
    """Redstone Tweaks' block textures, from a folder or from its zip."""

    BLOCK = "assets/minecraft/textures/block/"

    def __init__(self, where):
        self.zip = zipfile.ZipFile(where) if zipfile.is_zipfile(where) else None
        self.root = where

    def image(self, name, whole=False):
        """One texture, as RGBA: its first 16x16 frame, or all of it."""
        path = self.BLOCK + name + ".png"
        if self.zip is not None:
            data = self.zip.read(path)
        else:
            with open(os.path.join(self.root, path.replace("/", os.sep)), "rb") as f:
                data = f.read()
        image = Image.open(io.BytesIO(data)).convert("RGBA")
        return image if whole else image.crop((0, 0, 16, 16))

    def text(self, name):
        if self.zip is not None:
            return self.zip.read(name).decode("utf-8", "replace")
        with open(os.path.join(self.root, name), encoding="utf-8", errors="replace") as f:
            return f.read()


def bedrock(name):
    return Image.open(os.path.join(VANILLA, name + ".png")).convert("RGBA").crop((0, 0, 16, 16))


# --- turning one picture to match another ---------------------------------------

def turns(image):
    """The eight ways a square picture can be laid: four turns, and each flipped."""
    found = []
    for flipped in (False, True):
        base = ImageOps.mirror(image) if flipped else image
        for quarter in range(4):
            found.append(((quarter, flipped), base.rotate(-90 * quarter)))
    return found


def difference(a, b):
    pa, pb = a.load(), b.load()
    total = 0
    for y in range(16):
        for x in range(16):
            p, q = pa[x, y], pb[x, y]
            if p[3] == 0 and q[3] == 0:
                continue
            total += sum(abs(p[i] - q[i]) for i in range(4))
    return total


def match(image, like):
    """How to lay `image` so it reads like `like`: (quarter turns, flipped)."""
    return min(turns(image), key=lambda pair: difference(pair[1], like))[0]


def laid(image, how):
    quarter, flipped = how
    image = ImageOps.mirror(image) if flipped else image
    return image.rotate(-90 * quarter)


def matched(image, like):
    return laid(image, match(image, like))


# --- digits ---------------------------------------------------------------------

def glyphs(source):
    """The composter's digits, as cells of the three roles, 0 to 9.

    Each numbered composter side is the plain side with one digit painted on, in
    a four by seven box at x 6, y 5. The 9 is the 6 turned half round, because
    the composter stops at 8.
    """
    side = source.image("composter/side")
    roles = {(219, 209, 166): "L", (180, 169, 115): "M", (37, 20, 5): "D"}
    found = {}
    for n, name in [(0, "0_alt")] + [(n, str(n)) for n in range(1, 9)]:
        image = source.image("composter/" + name)
        cells = {}
        for y in range(5, 12):
            for x in range(6, 10):
                pixel = image.getpixel((x, y))
                if pixel != side.getpixel((x, y)) and pixel[:3] in roles:
                    cells[(x - 6, y - 5)] = roles[pixel[:3]]
        found[n] = cells
    found[9] = {(3 - x, 6 - y): r for (x, y), r in found[6].items()}
    return found


def stamp(base, number, at_y, palette, digits):
    """`base` with `number` written across its middle in the composter's digits."""
    image = base.copy()
    written = [int(c) for c in str(number)]
    wide = 5 * len(written) - 1
    left = 8 - wide // 2
    for i, d in enumerate(written):
        for (x, y), role in digits[d].items():
            image.putpixel((left + 5 * i + x, at_y + y), palette[role] + (255,))
    return image


def small(image, text, x, y, palette):
    """`text` in the small digits, each with its shadow down and to the right."""
    for c in text:
        rows = SMALL[c]
        for r, row in enumerate(rows):
            for k, ch in enumerate(row):
                if ch == "L" and 0 <= x + k + 1 < image.width and y + r + 1 < image.height:
                    image.putpixel((x + k + 1, y + r + 1), palette["D"] + (255,))
        for r, row in enumerate(rows):
            for k, ch in enumerate(row):
                if ch == "L":
                    image.putpixel((x + k, y + r), palette["L"] + (255,))
        x += len(rows[0]) + 1
    return image


def fill_sheet(slots):
    """Every count for one slot count, a row of 32 by 16 per signal.

    The count is written at twice a block's resolution, in the top rows of its
    row, two pixels in from the left: the family reads the left 16 and the next
    8 pixels of those top rows as two quads, at the corner of the face.
    """
    sheet = Image.new("RGBA", (32, 16 * 16), (0, 0, 0, 0))
    for strength in range(16):
        small(sheet, marks.text(strength, slots), COUNT_MARGIN,
              16 * strength + COUNT_MARGIN, REDSTONE)
    return sheet


# --- redstone dust --------------------------------------------------------------

def dust_tint(power):
    """Java's redstone wire colour for a power level, as an RGB multiplier."""
    f = power / 15.0
    red = f * 0.6 + (0.4 if f > 0 else 0.3)
    green = max(0.0, min(1.0, f * f * 0.7 - 0.5))
    blue = max(0.0, min(1.0, f * f * 0.6 - 0.7))
    return red, green, blue


def tinted(image, tint):
    out = image.copy()
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (int(r * tint[0]), int(g * tint[1]), int(b * tint[2]), a)
    return out


## Redstone Tweaks draws dust two ways, `vanilla` dust and `clean` wire, the
## second in `alt/`; Clearer Redstone stages the wire
DUST_STYLE = "redstone_dust/alt/"


def dust(source, power):
    """Bedrock's dust cross, tinted for a power level.

    Scaffold's dust reads each of its pieces from the cross, so the cross is the
    picture: Redstone Tweaks' dot and its line, both ways, in the wire style,
    coloured the way Java colours dust for this power.
    """
    line = source.image(DUST_STYLE + "line0")
    cross = source.image(DUST_STYLE + "dot")
    cross.alpha_composite(line)
    cross.alpha_composite(line.rotate(90))
    return tinted(cross, dust_tint(power))


def dust_line(source, power):
    """Redstone Tweaks' wire line, laid the way Bedrock's line lies and tinted
    for a power level, for a straight run of dust."""
    line = matched(source.image(DUST_STYLE + "line0"), bedrock("redstone_dust_line"))
    return tinted(line, dust_tint(power))


def dust_number(source, power):
    """The number Redstone Tweaks floats over the middle of a wire, untinted:
    white with a dark edge, at four times a block's resolution. 0 is the
    pack's other 0, which shows rather than being left blank."""
    return source.image("redstone_dust/%s" % ("0_alt" if power == 0 else power))


# --- what each option stages ----------------------------------------------------

def hopper_top(source, lock, mount):
    """The top of Scaffold's hopper bowl: the rim, with the floor in its hollow.

    Scaffold's bowl is a solid box whose top pictures the hollow, so Redstone
    Tweaks' floor -- its lock frame, and for a hopper on its side the chevron
    pointing at the spout -- is painted into the middle of the rim.
    """
    floor = source.image("hopper/%s/%s" % (lock, "inside" if mount == "down" else "inside_side"))
    floor.alpha_composite(source.image("hopper/top"))
    return floor


def stage(source):
    """{option: {texture name: image}}: everything every option ships."""
    digits = glyphs(source)
    out = {}

    out["redstone_dust_shades"] = dict(
        {"dust_%d" % p: dust(source, p) for p in range(16)},
        **{"line_%d" % p: dust_line(source, p) for p in range(16)})
    out["redstone_dust_numbers"] = dict(out["redstone_dust_shades"], **{
        "number_%d" % p: dust_number(source, p) for p in range(16)})

    out["composter_numbers"] = {
        "composter_%d" % n: source.image("composter/%s" % ("0_alt" if n == 0 else n))
        for n in range(9)}

    side = bedrock("cauldron_side")
    cauldron = {"cauldron_0": stamp(side, 0, 4, EMPTY, digits)}
    for liquid, palette in LIQUIDS.items():
        for level in range(1, 7):
            cauldron["cauldron_%s_%d" % (liquid, level)] = stamp(side, level, 4, palette, digits)
    out["cauldron_levels"] = cauldron

    snow = bedrock("snow")
    out["snow_layers"] = {"snow_%d" % n: stamp(snow, n, 4, SNOW, digits) for n in range(1, 9)}

    out["respawn_anchor_charges"] = dict(
        {"top_%d" % n: matched(source.image("respawn_anchor/top/%d" % n),
                               bedrock("respawn_anchor_top")) for n in range(5)},
        **{"side_%d" % n: matched(source.image("respawn_anchor/side/%d" % n),
                                  bedrock("respawn_anchor_side0")) for n in range(5)},
        bottom=matched(source.image("respawn_anchor/bottom"), bedrock("respawn_anchor_bottom")))

    honey = {}
    for hive, top in (("beehive", "beehive_top"), ("bee_nest", "bee_nest_top")):
        for n in range(6):
            honey["%s_front_%d" % (hive, n)] = matched(
                source.image("%s/front/%d" % (hive, n)), bedrock(hive + "_front"))
            honey["%s_top_%d" % (hive, n)] = matched(
                source.image("%s/top/%d" % (hive, n)), bedrock(top))
        honey[hive + "_side"] = matched(source.image(hive + "/side"), bedrock(hive + "_side"))
    honey["beehive_end"] = matched(source.image("beehive/end"), bedrock("beehive_top"))
    honey["bee_nest_bottom"] = matched(source.image("bee_nest/bottom"), bedrock("bee_nest_bottom"))
    out["bee_honey"] = honey

    ## each pitch is a whole face at twice a block's resolution, its label in
    ## the top left corner, which the family reads a quarter at a time
    out["note_block_pitch"] = {"note_%d" % n: source.image("note_block/unpowered/%d" % n,
                                                           whole=True)
                               for n in range(25)}
    out["note_block_pitch"]["note"] = source.image("note_block/unpowered")

    out["jukebox_record"] = {
        "top": matched(source.image("jukebox/top"), bedrock("jukebox_top")),
        "side": matched(source.image("jukebox/side"), bedrock("jukebox_side")),
        "top_record": matched(source.image("jukebox/top_has_record"), bedrock("jukebox_top")),
        "side_record": matched(source.image("jukebox/side_has_record"), bedrock("jukebox_side"))}

    observer = {}
    for name, like in (("front", "observer_front"), ("back", "observer_back"),
                       ("side", "observer_side"), ("top", "observer_top")):
        observer[name] = matched(source.image("observer/" + name), bedrock(like))
    observer["top_mirror"] = matched(source.image("observer/top"), bedrock("observer_top_mirror"))
    out["observer_unpowered"] = observer

    piston = {}
    for name, rt, like in (("side", "piston/side", "piston_side"),
                           ("side_sticky", "piston/side_sticky", "piston_side"),
                           ("bottom", "piston/alt2/bottom", "piston_bottom"),
                           ("bottom_sticky", "piston/alt2/bottom_sticky", "piston_bottom"),
                           ## the back of an extended piston, its indicator lit
                           ("bottom_extended", "piston/alt2/bottom_extended", "piston_bottom"),
                           ("bottom_extended_sticky", "piston/alt2/bottom_extended_sticky",
                            "piston_bottom"),
                           ("top", "piston/top", "piston_top_normal"),
                           ("top_sticky", "piston/top_sticky", "piston_top_sticky")):
        piston[name] = matched(source.image(rt), bedrock(like))
    out["piston_corners"] = piston

    launchers = {}
    for block in ("dispenser", "dropper"):
        rt = block + "/untriggered/"
        launchers[block + "_front"] = matched(source.image(rt + "front"),
                                              bedrock(block + "_front_horizontal"))
        launchers[block + "_front_vertical"] = matched(source.image(rt + "front_vertical"),
                                                       bedrock(block + "_front_vertical"))
        launchers[block + "_side"] = matched(source.image(rt + "side"), bedrock("furnace_side"))
        launchers[block + "_back"] = laid(source.image(rt + "back_indicator"),
                                          match(source.image(rt + "side"), bedrock("furnace_side")))
        launchers[block + "_top"] = matched(source.image(rt + "top_arrow"), bedrock("furnace_top"))
        ## the far end of one facing up or down: the top, its indicator lit
        launchers[block + "_back_vertical"] = laid(
            source.image(rt + "top_indicator"),
            match(source.image(rt + "top_arrow"), bedrock("furnace_top")))
    out["dispenser_directions"] = launchers

    hopper = {}
    outside = bedrock("hopper_outside")
    for lock in ("unlocked", "locked"):
        hopper["side_" + lock] = matched(source.image("hopper/%s/side" % lock), outside)
        for mount in ("down", "side"):
            ## the rim is the same all round, so nothing to match it by: it is
            ## turned so the chevron points at the spout, which rests north
            hopper["top_%s_%s" % (mount, lock)] = hopper_top(
                source, lock, mount).rotate(HOPPER_TURN)
    out["hopper_directions"] = hopper

    lever = {"base": source.image("lever/base"), "base_on": source.image("lever/base_on"),
             "lever": matched(source.image("lever/lever"), bedrock("lever"))}
    out["lever"] = lever

    locked = Image.new("RGBA", (16, 16), (178, 34, 34, 255))
    out["crafter_slots"] = {"locked": locked}

    out["container_fill"] = {"fill_%d" % n: fill_sheet(n) for n in marks.SLOT_COUNTS}
    return out


def credits_text(source):
    """The pack's own credits, as it ships them."""
    try:
        return source.text("credits.txt")
    except (KeyError, OSError):
        return ""


def write(staged, source):
    for option, images in staged.items():
        folder = os.path.join(STAGED, option)
        textures = os.path.join(folder, *PREFIX.split("/"), option)
        if os.path.isdir(textures):
            shutil.rmtree(textures)
        os.makedirs(textures, exist_ok=True)
        for name, image in sorted(images.items()):
            image.save(os.path.join(textures, name + ".png"))
        print("   %-24s %d textures" % (option, len(images)))
    credit = credits_text(source).strip()
    licence = os.path.join(STAGED, LICENSE)
    with open(licence, "w", encoding="utf-8", newline="\n") as f:
        f.write(LICENSE_TEXT.format(credits=credit))


LICENSE_TEXT = """Clearer Redstone
================

The textures in the folders of the Clearer Redstone options are Redstone Tweaks
by RexxStone, with settings by KikuGie, converted for Scaffold, and drawings made
for Scaffold in the same style. Redstone Tweaks is licensed under the Creative
Commons Attribution-NonCommercial-ShareAlike 4.0 International licence, and so
are these textures, the drawn ones included:

    https://creativecommons.org/licenses/by-nc-sa/4.0/

Redstone Tweaks: https://modrinth.com/resourcepack/redstone-tweaks

A pack built with any Clearer Redstone option carries this credit in its
description and in its credits.txt, and may not be sold.

Redstone Tweaks' own credits follow.

{credits}
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True,
                    help="Redstone Tweaks, unzipped or as its zip")
    ap.add_argument("--apply", action="store_true", help="write the folders")
    args = ap.parse_args(argv)
    source = Source(args.source)
    staged = stage(source)
    if not args.apply:
        for option, images in staged.items():
            print("   %-24s %d textures" % (option, len(images)))
        print("Nothing written. Run again with --apply.")
        return
    print("staging Clearer Redstone")
    write(staged, source)
    from tools.blocks import redstone
    redstone.main()
    redstone.icons()


if __name__ == "__main__":
    main()
