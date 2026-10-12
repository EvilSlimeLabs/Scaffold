import hashlib
import json
import os
import shutil
import tempfile
import time
from shutil import copyfile

import nbtlib.nbt

from scaffold import dust
from scaffold import lookup
from scaffold.pack import animation_class
from scaffold.pack import armor_stand_class
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold import block_geometry
from scaffold import block_upgrade
from scaffold.pack import big_render_controller as brc
from scaffold.pack import manifest
from scaffold.pack import render_controller_class as rcc
from scaffold import paths
from scaffold.pack import structure_reader
from scaffold.pack import tech_pack
from scaffold import block_list
from scaffold import marks
from scaffold import tweaks
from scaffold import version
debug=False

## **A block entity is not an entity, and the two are read from different
## places.** Everything named BLOCK_ENTITY_* below describes a *block entity*:
## extra NBT hanging off a block that is already in the palette, kept in
## `structure.palette.default.block_position_data` and keyed by the cell. The
## block was always going to be drawn; the block entity only says which way. A
## banner's colour, a bed's dye, a copper golem's pose, a cauldron's RGB, a
## flower pot's plant and a skull's facing all work like that, and none of them
## ever needed a pipeline of its own because none of them was ever missing.
##
## ENTITY_MODELS, further down, is the other thing entirely: a whole entity in
## `structure.entities`, with a world position of its own and nothing in
## `block_indices` to mark it. A cushion is the only one of those so far.

## Which form a block entity chooses -- a banner's colour, a statue's pose, a
## bed's dye, whether a lectern holds a book -- is part of the family's rules in
## block_geometry.json (`data`), beside the forms it chooses between. What is
## named here is what a block entity hands the drawing besides a form.

## Which field of a block entity holds a colour of its own rather than one of a
## list. A dyed cauldron keeps a whole RGB, which no lookup table could carry a
## texture for, so the colour is handed to the geometry builder and the tile is
## tinted as the pack is built.
BLOCK_ENTITY_TINTS = {"Cauldron": "CustomColor"}

## Which field of a block entity holds another whole block. A flower pot keeps
## whatever is planted in it beside the block rather than in its states, as a
## block with a name and states of its own, so the plant is drawn as a second
## block in the same place and by its own family. That is what makes every
## pottable plant work without a variant apiece.
BLOCK_ENTITY_HOLDS = {"FlowerPot": "PlantBlock"}
## the state a held plant is drawn with, which its family's `pick` reads to
## draw it the size it is in a pot
POTTED = "scaffold:potted"

## Which field of a block entity is a yaw, for the blocks whose states do not
## say which way they face. A head standing on the floor can face any of sixteen
## ways and keeps that in the block entity, the way a sign keeps its text; the
## states carry only which of the six faces it is fixed to. The number beside the
## field is the facing that means "standing on the floor", because a head on a
## wall is turned by the wall it is on and the entity reads zero. The yaw is
## handed to `make_block` on top of whatever the states turn the block by, as a
## block angle: see `head_yaw`.
BLOCK_ENTITY_ROTATIONS = {"Skull": ("Rotation", 1)}

## Which fields of a block entity name the block it is joined to. A chest set
## beside another of its kind becomes one half of a double chest, and each
## half's entity keeps the other's world position. Nothing in the states says
## which half a block is, so `paired` works it out and hands it to the rules as
## the entity's `pair` field, `left` or `right` as seen from in front.
BLOCK_ENTITY_PAIRS = {"Chest": ("pairx", "pairz")}

## The world step, (x, z), toward the left hand of somebody standing in front of
## a block that faces each way: in front of a chest facing north they stand north
## of it looking south, and their left hand is east.
LEFT_HAND = {"north": (1, 0), "south": (-1, 0), "east": (0, 1), "west": (0, -1)}


def paired(struct, x, y, z, block, entity):
    """The block entity, with `pair` added when the block is half of a pair.

    A half is only drawn as one when its partner is in the structure, beside
    it, and the same block: a chest whose other half was left outside the
    captured box is drawn whole rather than as half of something missing.
    """
    fields = BLOCK_ENTITY_PAIRS.get(str(entity.get("id", ""))) if entity else None
    if not fields or not all(f in entity for f in fields):
        return entity
    facing = _plain(block.get("states", {}).get("minecraft:cardinal_direction", ""))
    if facing not in LEFT_HAND:
        return entity
    origin = getattr(struct, "origin", (0, 0, 0))
    step = (int(entity[fields[0]]) - int(origin[0]) - x,
            int(entity[fields[1]]) - int(origin[2]) - z)
    left = LEFT_HAND[facing]
    if step == left:
        side = "right"
    elif step == (-left[0], -left[1]):
        side = "left"
    else:
        return entity
    size = struct.get_size()
    there = (x + step[0], z + step[1])
    if not (0 <= there[0] < size[0] and 0 <= there[1] < size[2]):
        return entity
    if struct.get_block(there[0], y, there[1])["name"] != block["name"]:
        return entity
    return dict(entity, pair=side)


## **What Scaffold draws that is not a block.** An entity is kept apart from the
## blocks entirely: a structure records it in `structure.entities` as a whole
## entity with a world position of its own, so nothing in `block_indices` marks
## the cell it stands in and no lookup table could reach it. A cushion is the
## first of them, and is a block in every way a builder cares about -- it is
## placed in a cell, it is one of sixteen colours, and it is a thing to gather.
##
## So it is drawn as one. `block` is the pseudo block id its shape family is
## keyed by, `variant` is the entity field that picks the form, and `forms` is
## what each value of that field means. From there it goes through `make_block`
## like anything else, which is what gives it a shape, a texture, a rotation
## table, a simplified form and a line on the block list without any of those
## having to learn what an entity is.
##
## `forms` is here rather than in the generator because both sides need it and a
## list written twice is a list that can disagree with itself; `tools/blocks/
## entities.py` imports it.
ENTITY_MODELS = {
    "minecraft:cushion": {
        "block": "cushion",
        "variant": "Variant",
        ## `Array.skins` in `controller.render.cushion`, indexed by
        ## `query.variant`. That is the dye order rather than the wool order --
        ## black first, white last -- so reading it as wool would give every
        ## cushion the colour across the wheel from its own.
        "forms": ["black", "red", "green", "brown", "blue", "purple", "cyan",
                  "light_gray", "gray", "pink", "lime", "yellow",
                  "light_blue", "magenta", "orange", "white"],
        ## the behaviour pack's own default value for the field
        "fallback": "white",
    },
}

def entity_yaw(yaw):
    """An entity's yaw, as the block angle `make_block` turns a family by.

    An entity faces a way given as an angle rather than as one of a block's
    states, so it is not looked up anywhere: the angle is the turn. An entity's
    yaw is 0 facing south and 90 facing west. A block angle is Minecraft's for a
    block -- 0 is the rest pose, facing north, and 90 faces west -- so the two
    run the same way round from different starting points.
    """
    return (180 - float(yaw)) % 360


def head_yaw(rotation):
    """A head's `Rotation`, as the block angle `make_block` turns it by.

    A head on the floor whose `Rotation` is 0 faces north, which is a block's
    rest pose, and the number climbs clockwise seen from above, through east,
    which is the other way round from a block angle.
    """
    return (-float(rotation)) % 360


def entity_form(entity, model):
    """Which form of its family this entity is, as the name the tables use."""
    told = entity.get("fields", {}).get(model.get("variant"))
    forms = model.get("forms") or ()
    try:
        return forms[int(told)]
    except (TypeError, ValueError, IndexError):
        return model.get("fallback") or "default"

PACK_SUFFIX = ".mcpack"


class AlreadyInstalled(Exception):
    """A pack of this exact name and content is already in Minecraft's folder.

    Carries the folder, so the window can say which one rather than making the
    user go and look.
    """

    def __init__(self, folder):
        self.folder = folder
        Exception.__init__(self, folder)


def install_name(made):
    """The folder a finished pack installs as.

    `Scaffold<version>_<hash>`: the version says what built it and the hash
    says which pack it is. The hash is the first half of the pack's own header
    UUID, which `manifest.pack_uuids` already derives from the fingerprint --
    so two builds of the same structures with the same settings install as the
    same folder, and any change at all installs as a different one. Twenty-odd
    characters, plain ASCII, no spaces: a folder name Minecraft and every
    filesystem will take.
    """
    import zipfile

    with zipfile.ZipFile(made) as archive:
        header = json.loads(archive.read("manifest.json"))["header"]
    digest = str(header["uuid"]).replace("-", "")[:12]
    return "Scaffoldv%s_%s" % (version.read(), digest)


def install_pack(made, into=None):
    """Unpack a finished .mcpack into Minecraft's resource pack folder.

    A .mcpack is a zip and Minecraft reads a loose pack as a folder, so this is
    an extraction and nothing more.

    **An existing folder is never written into.** The name carries the pack's
    own hash, so a folder that is already there holds this very pack -- there
    is nothing to update and overwriting it would only risk half-replacing a
    pack the game may have open. It raises `AlreadyInstalled` instead, and the
    window turns that into a message with nowhere to go but OK.
    """
    import zipfile

    into = into or paths.bedrock_packs()
    if not into:
        raise OSError("Minecraft's resource pack folder is not on this machine")
    target = os.path.join(into, install_name(made))
    if os.path.exists(target):
        raise AlreadyInstalled(target)
    ## into a temporary name first, so an extraction that fails part way
    ## through does not leave a half a pack for the game to find
    staging = target + ".part"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(made) as archive:
            archive.extractall(staging)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def pack_file(target):
    """The pack a build under this name writes."""
    return "{}{}".format(target, PACK_SUFFIX)


def block_list_file(target, name_tag=None):
    """Where a block list lands. A big build writes one, and it has no tag."""
    if name_tag is None:
        return "{} block list.txt".format(target)
    return "{}-{} block list.txt".format(target, name_tag)


def skipped_file(target):
    """Where the list of blocks that could not be built lands."""
    return "{} skipped.txt".format(target)


def outputs(target, name_tags=(), block_lists=False, big=False):
    """Every file a build under this name would write.

    A front end asks for these before it starts, so it can offer to write over
    what is already there or to build under another name. The methods below
    write to these same paths, so the answer cannot disagree with the build.
    The skipped list is not among them: whether there is one is only known once
    the structures have been read.
    """
    files = [pack_file(target)]
    if block_lists:
        if big:
            files.append(block_list_file(target))
        else:
            files.extend(block_list_file(target, tag) for tag in name_tags)
    return files


def _plain(value):
    """An NBT value as the plain string a lookup table is keyed by.

    nbtlib hands back Byte(0) and String('hanging') rather than "0" and
    "hanging", and a table read with the former finds nothing.
    """
    text = str(value)
    if "(" in text and text.endswith(")"):
        text = text[text.index("(") + 1:-1]
    return text.strip("'\"")


def _variant(block):
    """The variant a skipped block is listed under: its texture state, if any."""
    state = block_geometry.variant_state(block["name"])
    if state is not None and state in block.get("states", {}):
        return [state, block["states"][state]]
    return "default"


_families = None


## **Water is one body, not a stack of cubes.** Each cell of water is drawn as
## a box, and two boxes side by side put two faces between them that a ghost
## blends twice; so a face against more water is left out. Water with water
## above it fills its cell, and the surface stands lower, as the game draws it.
## The only thing asked of a neighbour is whether water is in it, as a block
## or as what a block stands in, so nothing here knows any block.
LIQUIDS = ("minecraft:water", "minecraft:flowing_water")
COVERED = "scaffold:covered"
SIDES = {"east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0),
         "south": (0, 0, 1), "north": (0, 0, -1)}


def _shape(struct):
    return getattr(getattr(struct, "cube", None), "shape", None) or getattr(
        getattr(struct, "blocks", None), "shape", None)


def block_at(struct, x, y, z):
    """The block at a cell of a structure, or None outside it."""
    shape = _shape(struct)
    if shape is None or not all(0 <= v < n for v, n in zip((x, y, z), shape)):
        return None
    try:
        return struct.get_block(x, y, z)
    except (IndexError, KeyError):
        return None


def _water_at(struct, x, y, z):
    found = block_at(struct, x, y, z)
    if found is None:
        return False
    if found["name"] in LIQUIDS:
        return True
    liquid = struct.get_liquid(x, y, z) if hasattr(struct, "get_liquid") else None
    return liquid is not None and liquid["name"] in LIQUIDS


def whole_cube(armorstand, block):
    """Whether a block is drawn as one cube filling its cell, near enough: what
    the dust rules take for a block that carries power."""
    name = block["name"].replace("minecraft:", "")
    if name not in armorstand.defs:
        return False
    try:
        form = armorstand.choose(name, block.get("states") or {})[0]
        shape = armorstand.block_shapes[armorstand.defs[name]][form]
    except (KeyError, IndexError, TypeError):
        return False
    sizes = shape.get("size") or []
    return len(sizes) == 1 and all(v >= 0.9 for v in sizes[0])


## **Water is drawn after the block standing in it, and its top before it when
## the top shows through the block.** A ghost is blended, so what is drawn first
## is depth tested against nothing and what comes after is tested against it:
## water's sides stand outside the block, and drawn after it let it show
## through. So the water is drawn in the block's own bone, straight after it,
## and, top and all, after every plane when the block is planes, a copper bar
## or kelp, which are drawn after the blocks. Its top stands inside
## a block that reaches above it, and drawn after it is hidden by every clear
## texel of the block's top, a grate's or a leaf's: under a block that covers
## the surface and whose top has clear texels, the top is drawn before
## everything. A block whose top is solid covers it either way, and a block
## that shows something below the surface has the top drawn after.
SIDES_PLAIN, SIDES_LATE = "water", "water_late"
SURFACE_PLAIN, SURFACE_LATE, SURFACE_EARLY = (
    "water_surface", "water_surface_late", "water_surface_early")


def water_families(armorstand, struct, x, y, z):
    """(sides, top): the families that draw the water at x, y, z."""
    found = block_at(struct, x, y, z)
    if found is None or found["name"] in LIQUIDS:
        return SIDES_PLAIN, SURFACE_PLAIN
    shape = _shape_of(armorstand, found)
    if shape is None:
        return SIDES_PLAIN, SURFACE_PLAIN
    ## a block that is all planes, a copper bar or kelp, has all of its water
    ## drawn after every plane
    if all(min(size) == 0 for size in shape[0]["size"]):
        return SIDES_LATE, SURFACE_LATE
    if _covers(shape, _surface_height(armorstand)) and _clear_top(armorstand, found):
        return SIDES_PLAIN, SURFACE_EARLY
    return SIDES_PLAIN, SURFACE_PLAIN


def _shape_of(armorstand, block):
    """(shape, up windows) of the form a block is drawn with, or None."""
    name = block["name"].replace("minecraft:", "")
    if name not in armorstand.defs:
        return None
    try:
        form = armorstand.choose(name, block.get("states") or {})[0]
        family = armorstand.defs[name]
        return (armorstand.block_shapes[family][form],
                armorstand.block_uv[family][form]["uv_sizes"]["up"])
    except (KeyError, IndexError, TypeError):
        return None


def _surface_height(armorstand):
    shape = armorstand.block_shapes[SURFACE_PLAIN]["default"]
    return shape["offsets"][0][1] if "offsets" in shape else 0.75


def _covers(found, surface):
    """Whether nothing of a block that faces up stands below `surface`, and
    something of it reaches above."""
    shape, ups = found
    offsets = shape.get("offsets") or [[0, 0, 0]] * len(shape["size"])
    tops = [offsets[i][1] + size[1] for i, size in enumerate(shape["size"])]
    shown = [tops[i] for i in range(len(tops)) if i < len(ups) and any(ups[i])]
    if shown:
        return min(shown) >= surface
    return max(tops) >= surface


_CLEAR = {}


def _clear_top(armorstand, block):
    """Whether the picture a block declares for its top has clear texels."""
    name = block["name"].replace("minecraft:", "")
    path = (armorstand.get_block_texture_paths(name) or {}).get("up")
    if not path:
        return False
    if path not in _CLEAR:
        from PIL import Image
        try:
            source = armorstand.texture_file(asgc.split_window(path)[0])
            tile = Image.open(source).convert("RGBA").crop((0, 0, 16, 16))
            _CLEAR[path] = tile.getextrema()[3][0] < 255
        except (OSError, TypeError, ValueError):
            _CLEAR[path] = False
    return _CLEAR[path]


def water_sides(struct, x, y, z):
    """The sides of a cell of water that more water is against."""
    return {side for side, (dx, dy, dz) in SIDES.items()
            if _water_at(struct, x + dx, y + dy, z + dz)}


def _rules(name, armorstand=None):
    """The rules of the family a block id is drawn by."""
    global _families
    if armorstand is not None:
        family = armorstand.defs.get(name.replace("minecraft:", ""))
        return armorstand.rules.get(family, {})
    if _families is None:
        _families = (lookup.entries("block_definition.json"), block_geometry.rules())
    definition, rules = _families
    return rules.get(definition.get(name.replace("minecraft:", "")), {})


class UnsupportedBlock:
    """
    Holds all the properties of an unsupported block.
    Can be compared to filter.
    """
    def __init__(self, pos: tuple[int, int, int], block: nbtlib.nbt.Compound, variant: str):
        self.pos = pos
        self.block = block
        self.variant = variant

    def __str__(self):
        return "x:{} Y:{} Z:{}, Block:{}, Variant: {}".format(
        self.pos[0], self.pos[1],self.pos[2],
            self.block["name"],
            self.variant
        )
    def __eq__(self, other):
        if not isinstance(other, UnsupportedBlock):
            return NotImplemented
        return self.block["name"] == other.block["name"] and self.variant == other.variant

    def __hash__(self):
        return hash((frozenset(self.block["name"]), self.variant))

class Scaffold:
    def __init__(self,pack_name):
        ## pack_name names the outputs the user gets; the pack tree itself is
        ## assembled in a temporary folder. A run that fails part way then
        ## leaves nothing behind for the next run with the same name to collide
        ## with.
        self.timers={"start":time.time(),"previous":time.time()}
        self.pack_name=pack_name
        self.display_name=os.path.basename(pack_name.rstrip("/\\")) or pack_name
        ## a pack name may carry a directory ("tmp/my_pack"); the outputs go
        ## there, so it has to exist even though the tree is built elsewhere
        parent=os.path.dirname(pack_name)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.work_dir=tempfile.mkdtemp(prefix="scaffold-")
        self.structure_files={}
        self.rc=rcc.RenderController()
        self.armorstand_entity = armor_stand_class.ArmorStand()
        visual_name=pack_name
        self.animation = animation_class.Animations()
        self.exclude_list=["minecraft:{}".format(name) for name in asgc.EXCLUDED_BLOCKS]
        self.opacity=asgc.DEFAULT_ALPHA
        self.longestY=0
        self.unsupported_blocks=[]
        ## the rules dust is joined by; an add-on's blocks are added to these
        self.dust = dust.Connections()
        self.all_blocks={}
        self.icon=paths.lookup("pack_icon.png")
        self.dead_blocks={}
        self.description=""
        self.tech_pack=tech_pack.NONE
        self._tech_pack_merged=False
        ## full detail unless asked otherwise; see set_low_geometry
        self.low_geometry=False
        ## no Bedrock Tweaks unless asked for; see set_tweaks
        self.tweaks=[]
        ## only set when a big build is made; part of the fingerprint either way
        self.big_offset=None
        ## nothing to ask by default, so a failed write raises; see set_retry
        self._retry=None
    def set_retry(self,ask):
        """What to do when a file the build writes cannot be written.

        `ask` is handed the OSError and the path, and returns True to try the
        same write again. Windows refuses to write a file another program holds
        open, and a pack the player still has loaded is exactly that, so the
        answer worth offering is to close it and carry on rather than to throw
        the whole build away. With no callback the write raises, which is what
        the command line wants.
        """
        self._retry=ask
    def _writing(self,path,call):
        """Run a write, asking again for as long as the front end says to."""
        while True:
            try:
                return call()
            except OSError as exc:
                if self._retry is None or not self._retry(exc,path):
                    raise
    def cleanup(self):
        """Drop the working tree. Safe to call twice; callers may use it in
        a finally so a failed build leaves nothing behind."""
        if self.work_dir and os.path.isdir(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)
        self.work_dir=None
    def set_icon(self,icon):
        self.icon=icon
    def set_description(self,text):
        """A short note from the builder, shown above the credits in game.

        Trimmed to what the pack list can show without pushing the rest of the
        description out of view."""
        self.description=(text or "").strip()[:manifest.DESCRIPTION_LIMIT]
    def set_low_geometry(self,enabled=True):
        """Draw the most detailed blocks as simpler shapes.

        Every ghost block is a piece of geometry the client lights and draws,
        and Vibrant Visuals makes that markedly more expensive. The blocks that
        carry the most cubes, such as bells, beacons, hanging signs and copper
        golem statues, can be drawn as a plain form instead, keeping their
        textures and their place in the model. Blocks that are already a cube or
        two are unaffected, which is most of them.
        """
        self.low_geometry=bool(enabled)

    def set_tweaks(self,names=()):
        """Build this pack with these Bedrock Tweaks applied.

        `names` is the tweak ids `lookups/tweaks.json` uses, in the order they
        should be layered; the ones that did not ship and the ones nothing
        names are dropped, and of a conflicting pair the later wins. Passing
        nothing clears them, which is the default.

        The tweaks are an overlay on the vanilla pack the atlas is built from,
        so a build with one on differs from a build without it in nothing but
        its textures, and both are the same geometry.
        """
        self.tweaks=tweaks.chosen(names)

    def get_tweaks(self):
        """The tweaks this pack will be built with, after conflicts."""
        return self.tweaks_used()

    def tweaks_used(self):
        """The tweaks actually applied: none when low geometry is on, since a
        tweak repaints and reshapes the detailed forms that low geometry
        replaces. The ones chosen are kept for a build without it."""
        return [] if self.low_geometry else list(self.tweaks)

    def set_tech_pack(self,enabled=True):
        """Bundle the Bedrock Technical Resource Pack into this pack.

        Both projects replace the armor stand client entity, and a resource pack
        replaces that file rather than merging with it, so applying Scaffold
        and TechPack side by side loses whichever sits lower in the player's
        list. Folding TechPack's declarations and assets into the generated pack
        is the only arrangement that runs both. Raises when the submodule is not
        checked out, rather than quietly producing a pack without it."""
        mode = tech_pack.mode_of(enabled)
        if mode != tech_pack.NONE and not tech_pack.available():
            raise FileNotFoundError(
                "be_tech_pack is not available; run "
                "'git submodule update --init be_tech_pack'")
        self.tech_pack=mode
    def _apply_tech_pack(self):
        """Merge TechPack into the armor stand before it is exported.

        The entity file is rewritten once per model, so this guards itself
        rather than relying on the merge being harmless to repeat."""
        if self.tech_pack != tech_pack.NONE and not self._tech_pack_merged:
            self.armorstand_entity.merge_description(tech_pack.description())
            self._tech_pack_merged=True
    def set_opacity(self,opacity):
        ## an alpha fraction, not a slider position. Out of range values used
        ## to reach the uint8 alpha multiply and wrap around, which looked
        ## like a working control with a sawtooth response.
        self.opacity=min(max(float(opacity),0.0),1.0)
    def add_model(self,name,file_name):
        self.structure_files[name]={}
        self.structure_files[name]["file"]=file_name
        self.structure_files[name]["offsets"]=None
    def set_model_offset(self,name,offset):
        self.structure_files[name]["offsets"]=offset
    def generate_nametag_file(self):
        ## temp folder would be a good idea
        name_tags=self.structure_files.keys()
        fileName="{} Nametags.txt".format(self.pack_name)
        with open(fileName,"w+") as text_file:
            text_file.write("These are the nametags used in this file\n")
            for name in name_tags:
                text_file.write("{}\n".format(name))
    def make_big_model(self,offset):
        self.rc=brc.RenderController()
        file_names=[]
        for name in list(self.structure_files.keys()):
            file_names.append(self.structure_files[name]["file"])
        struct2make=structure_reader.CombinedStructures(file_names,exclude_list=self.exclude_list)
        ## The combined model takes the empty name, which is also the name a
        ## single unnamed structure already has, so this entry replaces one
        ## that had a file. It keeps every file it was built from: the
        ## fingerprint is what tells two packs apart, and one that forgot its
        ## sources would be the same string however the structures changed.
        self.structure_files[""]={}
        self.structure_files[""]["files"]=list(file_names)
        self.structure_files[""]["offsets"]=[0,0,0]
        self.structure_files[""]["offsets"][1]= 0
        layers=12
        if (struct2make.get_size()[1]<=12):
            layers=struct2make.get_size()[1]
        for i in range(layers):
            self.armorstand_entity.add_model(str(i))
            self.rc.add_geometry(str(i))
        self.armorstand_entity.add_scale()#scale animation was removed from normal build this needs to be added back for big builds
        self.big_offset=offset
        self.all_blocks=self._add_blocks_to_geo(struct2make,"",export_big=True)
        self._apply_tech_pack()
        self.armorstand_entity.export(self.work_dir)
    def generate_with_nametags(self):
        update_animation=True
        for model_name in self.structure_files.keys():
            if self.structure_files[model_name]["offsets"] is None:
                self.structure_files[model_name]["offsets"]=[0,0,0]
            self.rc.add_model(model_name)
            self.armorstand_entity.add_model(model_name)
            if debug:
                print(self.structure_files[model_name]['offsets'])
            struct2make = structure_reader.StructureFile(self.structure_files[model_name]["file"])
            blocks=self._add_blocks_to_geo(struct2make,model_name)
            self.structure_files[model_name]["block_list"]=blocks
            ##consider temp folder
            self._apply_tech_pack()
            self.armorstand_entity.export(self.work_dir)## this may be in the wrong spot, but transferred from 1.5
        
    ## What a block list says around the numbers. A front end that has
    ## translations passes its own, and the core keeps English so it is usable
    ## on its own.
    ##
    ## The list is counted by block id and turned into names and headings only
    ## as it is written, by `block_list.py`, out of `block_list.json`. That is
    ## what lets somebody drop their own copy of that file beside the executable
    ## and have the list come out in their words, grouped their way, without
    ## rebuilding anything. A count already turned into a name cannot be
    ## regrouped or renamed afterwards, which is why the naming happens last.
    LIST_HEADER = "Blocks needed for this build"
    LIST_FOOTER = "Built with"
    RULE = "_" * 30

    def set_list_labels(self, header=None, footer=None):
        """Translated wording for the block list files, from the front end."""
        if header:
            self.LIST_HEADER = header
        if footer:
            self.LIST_FOOTER = footer

    def _write_block_list(self, file_name, blocks, title=None):
        def write():
            with open(file_name, "w+", encoding="utf-8") as text_file:
                text_file.write("{}\n".format(title or self.LIST_HEADER))
                text_file.write(self.RULE + "\n")
                for heading, counted in block_list.grouped(blocks):
                    text_file.write("\n{}\n".format(heading))
                    for name, count in counted:
                        text_file.write("  {}: {}\n".format(name, count))
                text_file.write("\n" + self.RULE + "\n")
                text_file.write("{} {}\n".format(self.LIST_FOOTER,
                                                 self.get_lookup_version()))
        self._writing(file_name, write)

    def make_nametag_block_lists(self):
        ## consider temp file
        file_names=[]
        for model_name in self.structure_files.keys():
            file_name=block_list_file(self.pack_name,model_name)
            file_names.append(file_name)
            self._write_block_list(
                file_name, self.structure_files[model_name]["block_list"],
                title="{} - {}".format(self.LIST_HEADER, model_name)
                if model_name else None)
        return file_names
    def make_big_blocklist(self):
        ## consider temp file
        file_name=block_list_file(self.pack_name)
        self._write_block_list(file_name, self.all_blocks)
        return file_name

    @staticmethod
    def _drawn_at(block, entity):
        """Everything to draw at one position, as (block, its own entity).

        Usually just the block. A flower pot's contents are a whole block kept
        in the block entity beside it, with a name and states of its own, so it
        is drawn where the pot is and by whatever family it belongs to. Nothing
        is carried over from the pot's entity: the plant's own states are all
        it has.
        """
        drawn = [(block, entity)]
        held = BLOCK_ENTITY_HOLDS.get(str(entity.get("id","")) if entity else "")
        if held is not None and held in entity:
            inside = entity[held]
            name = inside.get("name") if hasattr(inside,"get") else None
            if name:
                ## a pot keeps its plant the way the game named it when the
                ## pot was saved, so it is translated like a palette entry
                plant = block_upgrade.upgrade(
                    {"name": str(name), "states": inside.get("states", {})})
                ## and the plant is marked as potted, which a family with a
                ## potted form draws smaller and standing on the soil
                plant["states"] = dict(plant.get("states", {}), **{POTTED: True})
                drawn.append((plant, {}))
        return drawn

    def _add_blocks_to_geo(self,struct2make,model_name,export_big=False):
        [xlen, ylen, zlen] = struct2make.get_size()
        if export_big:
            self.structure_files[model_name]['offsets'][0]-=xlen.item()+7
            self.structure_files[model_name]['offsets'][2]-=zlen.item()+7
        armorstand = asgc.ArmorStandGeo(model_name,alpha = self.opacity, size=[xlen, ylen, zlen], offsets=self.structure_files[model_name]['offsets'], low_geometry=self.low_geometry, tweaks=self.tweaks_used())

        ## the animation only needs the layers of the tallest model; a
        ## shorter one that follows needs a subset of what is already there
        if ylen > self.longestY:
            update_animation=True
            self.longestY = ylen
        else:
            update_animation=False
        for y in range(ylen):
            
            #creates the layer for controlling. Note there is implied formatting here
            #for layer names
            if y<12:
                armorstand.make_layer(y)
                #adds links the layer name to an animation
                if update_animation and not export_big:
                    self.animation.insert_layer(y)
            non_air=struct2make.get_layer_blocks(y)
            for loc in non_air:
                x=int(loc[0])
                z=int(loc[1])
                block = struct2make.get_block(x, y, z)
                blk_name=block["name"].replace("minecraft:", "")
                ## a big build reads through a combined reader, which has no
                ## entity data of its own
                entity={}
                if hasattr(struct2make,"get_block_entity"):
                    entity=paired(struct2make, x, y, z, block,
                                  struct2make.get_block_entity(x, y, z))
                ## one position may draw more than one block: a filled flower
                ## pot is the pot and whatever is planted in it
                for drawn, beside in self._drawn_at(block, entity):
                    blk_name=drawn["name"].replace("minecraft:", "")
                    if debug:
                        self.draw_block(armorstand, x, y, z, blk_name, drawn, beside, export_big,
                                        struct=struct2make)
                    else:
                        try:
                            self.draw_block(armorstand, x, y, z, blk_name, drawn, beside, export_big,
                                            struct=struct2make)
                        except Exception as e:
                            variant = _variant(drawn)
                            unsupported = UnsupportedBlock((x,y,z), drawn, variant)
                            self.unsupported_blocks.append(unsupported)
                            if drawn["name"] not in self.dead_blocks.keys():
                                self.dead_blocks[drawn["name"]]={}
                            if type(variant) is list:
                                ## a variant may name a number, such as a dried
                                ## ghast's drying stage, and nbtlib hands those
                                ## back as Int, which will not join with a string
                                variant="_".join(str(part) for part in variant)
                            if variant not in self.dead_blocks[drawn["name"]].keys():
                                self.dead_blocks[drawn["name"]][variant]=0
                            self.dead_blocks[drawn["name"]][variant]+=1
                ## and the water a waterlogged block stands in, which the
                ## structure keeps in a second layer rather than in its states
                liquid = (struct2make.get_liquid(x, y, z)
                          if hasattr(struct2make, "get_liquid") else None)
                if liquid is not None and liquid["name"] != block["name"]:
                    try:
                        self.draw_block(armorstand, x, y, z,
                                        liquid["name"].replace("minecraft:", ""),
                                        liquid, None, export_big,
                                        struct=struct2make)
                    except Exception:
                        pass
                ## and whatever a tweak draws beside the block from what its
                ## entity says; see scaffold/marks.py
                self._draw_marks(armorstand, struct2make, x, y, z, block,
                                 entity, export_big)
            ## consider temp file
        ## and whatever stands in the structure that is not a block. A big
        ## build reads through a combined reader, which merges several files
        ## into one grid and has no entities of its own, the same way it has no
        ## block entities.
        counted = struct2make.get_block_list()
        if hasattr(struct2make, "get_entities"):
            for key, count in self._add_entities_to_geo(
                    struct2make, armorstand, export_big).items():
                counted[key] = counted.get(key, 0) + count
        if export_big:
            armorstand.export_big(self.work_dir)
            self.animation.export_big(self.work_dir,self.big_offset)
        else:
            armorstand.export(self.work_dir)
            self.animation.export(self.work_dir)
        return counted

    @staticmethod
    def _draw_marks(armorstand, struct, x, y, z, block, entity, big=False):
        """Draw the marks a tweak defines for this block, if any does.

        A mark is not a block anybody placed, so one that fails is passed over
        rather than reported as skipped.
        """
        for mark in marks.made(struct, x, y, z, block, entity):
            if mark["name"] not in armorstand.defs:
                continue
            try:
                armorstand.make_block(x, y, z, mark["name"],
                                      states=mark["states"], big=big, beside=True)
            except Exception:
                if debug:
                    raise

    def _add_entities_to_geo(self, struct2make, armorstand, export_big=False):
        """Draw the entities Scaffold knows, and count them for the list.

        An entity that nothing in ENTITY_MODELS names is passed over in silence
        rather than reported as skipped. A structure is full of them -- the one
        this was written against carries a hundred and four dropped items -- and
        none of them is something a builder places, so listing them as blocks
        Scaffold could not draw would bury the ones that matter.
        """
        counted = {}
        for entity in struct2make.get_entities():
            model = ENTITY_MODELS.get(entity["id"])
            if not model:
                continue
            x, y, z = entity["at"]
            form = entity_form(entity, model)
            try:
                armorstand.make_block(x, y, z, model["block"],
                                      yaw=entity_yaw(entity["yaw"]),
                                      data=form, big=export_big,
                                      lift=entity.get("lift") or 0.0)
            except Exception:
                ## the same bargain a block gets: it lands on the skipped list
                ## rather than ending the build
                self.unsupported_blocks.append(
                    UnsupportedBlock((x, y, z), {"name": entity["id"]}, form))
                self.dead_blocks.setdefault(entity["id"], {})
                self.dead_blocks[entity["id"]][form] = (
                    self.dead_blocks[entity["id"]].get(form, 0) + 1)
                continue
            ## counted the way a block with a variant is, so one line per
            ## colour and a name a user can override per colour
            key = "%s/%s" % (entity["id"], form)
            counted[key] = counted.get(key, 0) + 1
        return counted
    @staticmethod
    def _digest(path):
        """A file's contents, as a short hex digest. Missing reads as missing."""
        try:
            with open(path, "rb") as handle:
                return hashlib.sha256(handle.read()).hexdigest()[:32]
        except OSError:
            return "absent"

    def fingerprint(self):
        """Everything that went into this pack, as one stable string.

        Two builds that would produce the same pack produce the same string, and
        any change to a structure file or a setting changes it. That is what the
        pack's UUID is derived from, so an unchanged rebuild is recognised as
        the same pack and a changed one is not.
        """
        parts = ["name=" + self.display_name,
                 "description=" + self.description,
                 "opacity=%.4f" % self.opacity,
                 "icon=" + self._digest(self.icon),
                 "techpack=%s:%s" % (
                     self.tech_pack,
                     tech_pack.version() if self.tech_pack != tech_pack.NONE
                     else "off"),
                 "geometry=" + ("low" if self.low_geometry else "high"),
                 ## the order matters, because two tweaks touching one texture
                 ## are applied in it, so it is not sorted
                 "tweaks=" + (",".join(self.tweaks_used() if hasattr(self, "tweaks") else ()) or "none"),
                 "big=" + (",".join(str(v) for v in self.big_offset)
                           if getattr(self, "big_offset", None) else "off")]
        for name in sorted(self.structure_files):
            info = self.structure_files[name]
            offsets = info.get("offsets") or [0, 0, 0]
            ## one file for an ordinary model, and every source for the
            ## combined one a big build makes, which has no file of its own
            sources = info.get("files")
            if sources is None:
                sources = [info["file"]] if info.get("file") else []
            parts.append("model=%s|%s|%s" % (
                name, ",".join(self._digest(one) for one in sources) or "none",
                ",".join(str(v) for v in offsets)))
        return "\n".join(parts)

    def _write_tweak_credits(self):
        """The `credits.txt` Bedrock Tweaks' licence asks a pack to carry.

        Written only when a tweak was actually applied, because a pack with none
        is carrying nobody else's work. It names what was used rather than the
        whole catalogue, so somebody reading it can tell which files came from
        where.
        """
        used = self.tweaks_used()
        if not used:
            return
        lines = []
        bedrock = [k for k in used if tweaks.tab(k) == "tweaks"]
        redstone = [k for k in used if tweaks.tab(k) == "redstone"]
        if bedrock:
            lines += ["This pack includes textures from Bedrock Tweaks.", ""]
            lines += ["  " + name for name in bedrock]
            lines += [""]
            lines += list(tweaks.CREDIT_LINES)
            lines.append("")
        if redstone:
            ## Redstone Tweaks is CC BY-NC-SA 4.0: the author, the licence and
            ## that the pack may not be sold all travel with it
            lines += ["This pack includes textures from Redstone Tweaks by "
                      "RexxStone, with settings by KikuGie, converted for "
                      "Scaffold, and drawings in the same style, all under "
                      "CC BY-NC-SA 4.0. It may not be sold.", ""]
            lines += ["  " + name for name in redstone]
            lines += [""]
            lines += ["  " + link for link in tweaks.REDSTONE_CREDIT_LINKS]
            lines.append("")
        path = os.path.join(self.work_dir, "credits.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))

    def compile_pack(self, overwrite=False):
        ## consider temp file
        nametags=list(self.structure_files.keys())
        ## a single unnamed model has nothing worth listing; an empty tag is how
        ## the one-structure case reaches here
        listed=[tag for tag in nametags if tag]
        manifest.export(self.work_dir,self.display_name,nameTags=listed,
                        user_text=self.description,
                        tech_pack_version=(tech_pack.version()
                                           if self.tech_pack == tech_pack.FULL
                                           else None),
                        fingerprint=self.fingerprint(),
                        tweaks=self.tweaks_used())
        self._write_tweak_credits()
        copyfile(self.icon, f"{self.work_dir}/pack_icon.png")
        larger_render = paths.lookup("armor_stand.larger_render.geo.json")
        larger_render_path = f"{self.work_dir}/models/entity/armor_stand.larger_render.geo.json"
        os.makedirs(os.path.dirname(larger_render_path), exist_ok=True)
        copyfile(larger_render, larger_render_path)
        self.rc.export(self.work_dir)
        ## After Scaffold's own files, so a name both projects use keeps
        ## Scaffold's copy and the collision is reported rather than silent.
        ## Only the full bundle ships them; compatibility declares TechPack on
        ## the armor stand and leaves the files to whoever installed TechPack.
        if self.tech_pack == tech_pack.FULL:
            written,skipped=tech_pack.copy_assets(self.work_dir)
            if debug:
                print("TechPack {}: {} files, {} skipped".format(
                    tech_pack.version(),written,len(skipped)))
        archive="{}.zip".format(self.pack_name)
        finished=pack_file(self.pack_name)
        self._writing(archive, lambda: shutil.make_archive(
            "{}".format(self.pack_name), 'zip', self.work_dir))
        ## os.replace writes over the pack in one step. Removing it first and
        ## renaming afterwards leaves a moment with neither file present, and
        ## the rename is the operation Windows refuses while the old pack is
        ## open. os.rename is kept for a build that was not told to overwrite,
        ## because it raises rather than taking the file.
        move=os.replace if overwrite else os.rename
        self._writing(finished, lambda: move(archive,finished))
        self.cleanup()
        self.timers["finished"]=time.time()-self.timers["previous"]
        self.timers["total"]=time.time()-self.timers["start"]


        return finished
    def draw_block(self, armorstand, x, y, z, blk_name, block, entity=None, big=False,
                   struct=None):
        """Draw one block from its states and its block entity.

        The family's rules choose the form, the turn and the textures, inside
        `make_block`; what is settled here is what a block entity hands the
        drawing besides a form: a colour to tint with and a yaw. Water is also
        told where more water is, from `struct`: see `water_sides`.
        """
        tint, yaw = self._process_block(block, entity, armorstand)
        states, hidden = block["states"], ()
        if struct is not None and block["name"] in LIQUIDS:
            hidden = water_sides(struct, x, y, z)
            if "up" in hidden:
                states = dict(states, **{COVERED: True})
        ## dust is told which of its sides join something; see scaffold/dust.py
        if struct is not None and self.dust.is_dust(block):
            states = dict(states, **self.dust.sides(
                lambda *at: block_at(struct, *at), x, y, z,
                lambda found: whole_cube(armorstand, found)))
        family = top_family = None
        if struct is not None and block["name"] in LIQUIDS:
            family, top_family = water_families(armorstand, struct, x, y, z)
        armorstand.make_block(x, y, z, blk_name, states=states,
                              entity=entity, big=big, tint=tint, yaw=yaw, hidden=hidden,
                              family=family)
        ## and water's top, unless more water is above it; see `water_families`
        if struct is not None and block["name"] in LIQUIDS and "up" not in hidden:
            armorstand.make_block(x, y, z, blk_name, states=states, big=big, tint=tint,
                                  family=top_family)

    def _process_block(self, block, entity=None, armorstand=None):
        """(tint, yaw): what a block's entity says beyond its form."""
        tint = None
        yaw = None
        if not entity:
            return tint, yaw
        ## A dyed cauldron keeps a whole colour, which no table could carry a
        ## texture for, so the tile is tinted as it goes into the atlas and
        ## every colour in a structure lands there as a tile of its own.
        marker = BLOCK_ENTITY_TINTS.get(str(entity.get("id","")))
        if marker is not None and marker in entity:
            tint = int(entity[marker])
        ## A head on the floor turns by the yaw its entity keeps, and one on a
        ## wall by its facing alone.
        turned = BLOCK_ENTITY_ROTATIONS.get(str(entity.get("id","")))
        if turned is not None and turned[0] in entity:
            rules = _rules(block["name"], armorstand)
            if block_geometry.turn(rules, block["states"]) == turned[1]:
                try:
                    yaw = head_yaw(entity[turned[0]])
                except (TypeError, ValueError):
                    pass
        return tint, yaw
    def get_nametags(self):
        """The name tags in this pack, in the order they were added."""
        return list(self.structure_files.keys())
    def get_block_lists(self):
        """{name tag: {block: count}} for every model, as data rather than as
        the text files make_nametag_block_lists writes. Populated by
        generate_with_nametags."""
        return {name: dict(info["block_list"])
                for name, info in self.structure_files.items()
                if "block_list" in info}
    def get_material_list(self):
        """Every block the finished pack needs and how many, summed over all
        models. A big build reports the combined total it already holds."""
        if self.all_blocks:
            return dict(self.all_blocks)
        totals={}
        for blocks in self.get_block_lists().values():
            for block, count in blocks.items():
                totals[block]=totals.get(block,0)+count
        return totals
    def get_skipped(self, write_file=True):
        """{block: {variant: count}} for everything that could not be built.
        write_file also drops a "<pack> skipped.txt" beside the pack; a caller
        that only wants the data should pass False."""
        if write_file and len(self.unsupported_blocks)>0:
            fileName=skipped_file(self.pack_name)
            def write():
                with open(fileName,"w+") as text_file:
                    text_file.write("These are the skipped blocks\n")
                    for skipped in self.unsupported_blocks:
                        text_file.write(f"{skipped}\n")
            self._writing(fileName, write)
        return self.dead_blocks

    def get_unique_blocks_count(self):
        count = 0
        if self.structure_files:
            for k, v in self.structure_files.items():
                count += len(list(v["block_list"].keys()))

        return count

    def get_lookup_version(self) -> str:
        """Which build of the lookup tables produced this pack.

        The tables ship with the program, so the program's own version names
        them. lookup_version.json only means anything once a drop has been
        pulled from the update server, which this fork does not use, so its
        shipped contents name a date from somebody else's release.
        """
        return "Scaffold {}".format(version.read())

## `core.scaffold(...)` is what every front end, including a hosted one, is
## written against, so the lowercase name stays pointing at the class.
scaffold = Scaffold
