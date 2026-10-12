try:
    import ujson as json
except ImportError:
    print("using built in json, but that is much slower, consider installing ujson")
    import json
from PIL import Image
from numpy import array, ascontiguousarray, ones, rot90, uint8, zeros
from operator import add
import copy
import os
import time

from scaffold import block_geometry, paths
from scaffold import lookup
from scaffold import tweaks as tweaks_packs
debug = False##used in API test to force errors and break error handler, should remain false.

## Blocks that never become geometry. scaffold_core needs the same list in the
## namespaced form the structure files store it, so it derives it from here
## rather than keeping a second copy.
EXCLUDED_BLOCKS = ("air", "structure_block")

## how a shape family names its simpler form, in block_shapes and block_uv
LOW_SUFFIX = "__low"


def detailed(block_type):
    """The family a simpler form was made from, or the family itself."""
    if block_type.endswith(LOW_SUFFIX):
        return block_type[:-len(LOW_SUFFIX)]
    return block_type


## **A lookup table holds Minecraft's angles, and a bone turns the other way
## about y and z.** The model is the world mirrored in x, so a turn that carries
## north to west in the world is a turn carrying it to east in the model. A
## rotation table is written the way Minecraft writes a block's: cardinal
## north 0, west 90, south 180, east 270, and facing down 90 about x. This is
## the one place that is turned into what a bone needs.
def to_bone(angles):
    """A Minecraft block rotation, as the bone rotation that draws it."""
    return [angles[0], -angles[1] % 360 if angles[1] else 0,
            -angles[2] % 360 if angles[2] else 0]

## Marks a window into a texture, written after the texture's name as
## "<texture>#<x>,<y>". Only the top left 16x16 of a texture becomes a tile, so
## a block drawn from an entity sized sheet -- a hanging sign's 64x32 sheet
## carries the bar, the chains and the board one under the other -- can reach
## the part it needs no other way. Each window becomes a tile of its own,
## because the atlas is keyed by the whole name.
WINDOW_MARK = "#"
## the prefixes of the bones drawn after every other, planes and then water,
## and the mark on a cube saying which of them it goes in. **The names put
## them in order, not the list:** every cutout and every hidden waterlogged
## block seen in game fits the game drawing a model's bones sorted by name, so
## a block's bones, `slice_`, sort before its planes', and those before its
## water's. That reading is untested; `tools/checks/gallery.py --water-trials`
## is the check.
LAST_BONE = "tier1_"
LIQUID_BONE = "tier2_"
## and the prefix of bones drawn before every other, which sorts first
EARLY_BONE = "early_"
LAST_CUBE = "_last"
## families drawn after everything else, planes included: a plane inside water
## is behind the water's face, so the water goes after it
DRAWN_LAST = {"water_late", "water_surface_late"}
## families drawn before everything: water's top under a block that covers it
## and shows through its own top
DRAWN_EARLY = {"water_surface_early"}
## families drawn in their slice's own bone, after the blocks drawn into it
## before them: a block's water, which core draws straight after the block.
## **Order within a bone holds; order between bones does not.** A world showed
## water in a bone of its own beside the block's flickering in and out as the
## camera moved, and the same water in the block's own bone steady.
AFTER_SLICE = "___water"
DRAWN_AFTER_SLICE = set()
## planes kept in the bone they are drawn into rather than the planes' tier
DRAWN_IN_TURN = {"water_surface"}


## the prefix of each other tier's layer bones, by tier
TIER_PREFIX = {-1: EARLY_BONE, 1: LAST_BONE, 2: LIQUID_BONE}


def bone_tier(name):
    """0 for a bone drawn in turn, 1 for planes drawn last, 2 for water after
    them, and -1 for a bone drawn before all of them."""
    if name.startswith(EARLY_BONE):
        return -1
    return 2 if name.startswith(LIQUID_BONE) else 1 if name.startswith(LAST_BONE) else 0

## "<texture>~<rrggbb>". A block whose colour is a whole colour rather than one
## of a list -- a cauldron's dyed water, which keeps an RGB in its block entity
## -- cannot name a texture per colour, and a ghost block cannot tint anything
## as it draws. Scaffold builds the pack, though, so the tile is tinted on the
## way into the atlas and the colour travels in the name. A table writes
## `~tint` and the colour is put in its place; with no colour to put there the
## mark is dropped and the plain texture is read.
TINT_MARK = "~"
TINT_WANTED = TINT_MARK + "tint"

## "<texture>^<degrees>". Bedrock's per-face UV is a corner and a size, and a
## negative size mirrors an axis, but there is no turn in it: a face cannot ask
## for its picture a quarter round. Some blocks need one anyway, because a
## texture packs a piece of the block lying on its side -- a lectern's post is
## down the bottom half of `lectern_sides`, across rather than up. So the tile
## is turned on the way into the atlas and the angle travels in the name, which
## keeps a turned tile and a straight one as two entries rather than one that
## would have to be both.
##
## **The turn happens first and the window is measured on the result.** Turning
## the whole tile and then reading a rectangle out of it composes; turning a
## rectangle inside a tile that has not moved does not, because everything
## around it would still be the way it was.
##
## Right angles only. Anything else would have to resample, and a ghost block's
## texture is sixteen pixels across.
TURN_MARK = "^"
TURNS = (0, 90, 180, 270)

## **How wide the texture atlas is, in tiles.** Every texture a pack uses
## becomes one 16x16 tile, and the atlas was a single column of them: sixteen
## pixels wide and sixteen times as tall as the pack has textures. A structure
## with a thousand distinct blocks in it therefore shipped a texture some
## twenty-five thousand pixels tall, which is past what a GPU will hold -- the
## common ceiling is 16384 on a desktop and 4096 on a phone, and a texture over
## it is not clamped or scaled, it fails.
##
## Sixty-four tiles to a row makes the sheet 1024 wide and a sixty-fourth as
## tall, so the same pack is 1024 by 400. The number is arbitrary beyond being
## a power of two and wide enough that nothing realistic grows tall again.
##
## The UV a cube carries is in *tile* units -- `texture_width` and
## `texture_height` are the tile counts, not pixels -- so a tile at index `i`
## sits at u `i % ATLAS_COLUMNS`, v `i // ATLAS_COLUMNS`, and a face's own
## offset and size are fractions added on top, exactly as before.
ATLAS_COLUMNS = 64


def atlas_place(index):
    """Where the tile at this index sits in the sheet, in tile units."""
    return index % ATLAS_COLUMNS, index // ATLAS_COLUMNS


def atlas_rows(count):
    """How many rows of tiles a sheet holding `count` textures needs."""
    return -(-count // ATLAS_COLUMNS)


def atlas_index(across, down):
    """The tile index a uv corner names. The inverse of `atlas_place`."""
    return int(down) * ATLAS_COLUMNS + int(across)


def split_turn(texture):
    """A texture's name, and how far clockwise its tile is turned."""
    texture = split_tint(texture)[0]
    if TURN_MARK not in texture:
        return texture, 0
    name, _, turn = texture.partition(TURN_MARK)
    try:
        degrees = int(turn) % 360
    except ValueError:
        return name, 0
    ## a turn that is not a right angle is no turn, rather than a crash: the
    ## tables are hand written and a wrong number should draw the block
    return name, degrees if degrees in TURNS else 0


def split_window(texture):
    """A texture's name, and the corner of the 16x16 window to take from it."""
    texture = split_turn(split_tint(texture)[0])[0]
    if WINDOW_MARK not in texture:
        return texture, (0, 0)
    name, _, corner = texture.partition(WINDOW_MARK)
    across, _, down = corner.partition(",")
    return name, (int(across), int(down))


def split_tint(texture):
    """A texture's name, and the colour to multiply it by, if it names one."""
    if TINT_MARK not in texture:
        return texture, None
    name, _, colour = texture.partition(TINT_MARK)
    try:
        packed = int(colour, 16)
    except ValueError:
        return name, None
    return name, ((packed >> 16) & 255, (packed >> 8) & 255, packed & 255)


def tinted(texture, colour):
    """A texture that asks for a tint, with this block's colour put in.

    A block that wants one and has none reads the plain texture, so a cauldron
    of undyed water is not left naming a file nobody wrote.
    """
    if TINT_WANTED not in texture:
        return texture
    if colour is None:
        return texture.replace(TINT_WANTED, "")
    return texture.replace(TINT_WANTED, "%s%06x" % (TINT_MARK, colour & 0xFFFFFF))

## Alpha the ghost blocks are drawn at when nothing sets one. The texture's
## alpha channel is multiplied by this, so it is a fraction, not a percentage.
## It is the counterpart of settings.DEFAULT_TRANSPARENCY: a caller that sets
## nothing has to get the same ghost block the slider's default gives, and a
## test asserts the two stay in step.
DEFAULT_ALPHA = 0.35

class ArmorStandGeo:
    def __init__(self, name, alpha = DEFAULT_ALPHA,offsets=None, size=[64, 64, 64], ref_pack=None, low_geometry=False, tweaks=None):
        self.ref_resource_pack = ref_pack or paths.vanilla_pack()
        ## families whose turned cubes go in bones written after every other
        ## bone, so they are drawn last; empty unless a trial asks for it
        self.drawn_last = set()
        ## and the families drawn in the water's tier, after them, and before
        ## everything
        self.drawn_liquid = set(DRAWN_LAST)
        self.drawn_early = set(DRAWN_EARLY)
        self.drawn_after_slice = set(DRAWN_AFTER_SLICE)
        ## and the families whose planes are drawn in turn, in the bone of the
        ## block at the same place when it is turned the same way, rather than
        ## in the planes' tier: water's top, which is a plane, drawn straight
        ## after the block standing in it
        self.shared_bone = set(DRAWN_IN_TURN)
        ## each block's inventory picture, read through the `item` slot
        try:
            self.item_icons = lookup.entries("item_icons.json")
        except OSError:
            self.item_icons = {}
        ## **The chosen tweaks are an overlay on the pack below.** A Bedrock
        ## Tweaks pack is an ordinary resource pack, and applying one in game is
        ## a matter of putting it higher in the list; nothing here has a list,
        ## so the same thing is done by looking in each tweak's folder before
        ## the vanilla pack and by merging what they declare over what it does.
        ## `scaffold/tweaks.py` settles which ones are on and in what order.
        self.tweaks = tweaks_packs.chosen(tweaks)
        (self.tweak_folders, tweak_blocks, tweak_terrain,
         self.tweak_carried) = tweaks_packs.overlay(self.tweaks)
        ## Each of these tables maps a block to a property that the structure
        ## file leaves hidden, implied, or otherwise unclear.
        with open("{}/blocks.json".format(self.ref_resource_pack)) as f:
            ## defines a block from its NBT name, and gives sides against textures
            self.blocks_def = json.load(f)
        with open("{}/textures/terrain_texture.json".format(self.ref_resource_pack)) as f:
            ##maps textures names to texture files.
            self.terrain_texture = json.load(f)
        ## a tweak's own declarations go over the vanilla ones, block by block
        ## and texture name by texture name, so one that renames a single
        ## texture leaves the other thousand alone
        self.blocks_def.update(tweak_blocks)
        self.terrain_texture.setdefault("texture_data", {}).update(tweak_terrain)
        ## rotation per state, per shape family, a family that follows one of
        ## Minecraft's own states already given that state's turns. A block
        ## whose state has no entry is left unrotated, and reports it when debug
        ## is on.
        self.block_rotations = block_geometry.rotations()
        self.defs = dict(lookup.entries("block_definition.json"))
        ## every family's cubes, and the window each face of each reads, from
        ## lookups/block_geometry.json; see `scaffold/block_geometry.py`
        self.block_shapes, self.block_uv = block_geometry.load()
        ## and each family's rules for choosing between its forms
        self.rules = block_geometry.rules()
        ## **A tweak may change the tables as well as the art.** A family it
        ## carries replaces the one of that name whole -- forms, rules and
        ## simpler forms -- so a simpler form the overlay does not draw is not
        ## left behind wearing the old textures. See `scaffold/tweaks.py`.
        families, definitions, turning = tweaks_packs.tables(self.tweaks)
        if families:
            shapes, uvs = block_geometry.columns(families)
            for family in families:
                self.block_shapes.pop(family + LOW_SUFFIX, None)
                self.block_uv.pop(family + LOW_SUFFIX, None)
                self.rules[family] = {key: families[family][key]
                                      for key in block_geometry.RULES
                                      if key in families[family]}
            self.block_shapes.update(shapes)
            self.block_uv.update(uvs)
        self.defs.update(definitions)
        standard = block_geometry.read(block_geometry.STATES)["states"]
        for family, table in turning.items():
            self.block_rotations[family] = (dict(standard[table])
                                            if isinstance(table, str) else table)
        ## A shape family may declare a simpler form of itself, named with this
        ## suffix. When the simpler drawing is asked for, that form is used
        ## instead; a family that does not declare one is drawn as it always is,
        ## which is why most blocks look identical either way.
        self.low_geometry = bool(low_geometry)
        self.name = name.replace(" ","_").lower()
        self.stand = {}
        ## a copy, because the half-block shift below is applied in place and
        ## the caller keeps using the list it passed in
        self.offsets = [0, 0, 0] if offsets is None else list(offsets)
        self.offsets[0] += 0.5
        self.offsets[2] -= 0.5
        self.alpha=alpha
        self.texture_list = []
        self.geometry = {}
        self.stand_init()
        self.uv_map = {}
        self.blocks = {}
        self.size = size
        self.bones = []
        self.errors={}
        self.layers=[]
        self.uv_tiles = []
        self.pre_gen_blocks={}
        self.excluded = EXCLUDED_BLOCKS

    def export(self, pack_folder):
        start = time.time()
        ## This exporter just packs up the armorstand json files and dumps them where it should go. as well as exports the UV file
        self.add_blocks_to_bones()
        self.geometry["description"]["texture_width"] = ATLAS_COLUMNS
        self.geometry["description"]["texture_height"] = atlas_rows(
            len(self.uv_map))
        self.stand["minecraft:geometry"] = [self.geometry] ## this is insuring the geometries are imported, there is an implied reference other places.
        path_to_geo = "{}/models/entity/armor_stand.ghost_blocks_{}.geo.json".format(
            pack_folder,self.name)
        os.makedirs(os.path.dirname(path_to_geo), exist_ok=True)
        i=0
        
        for index in range(len(self.stand["minecraft:geometry"][0]["bones"])):
            if "name" not in self.stand["minecraft:geometry"][0]["bones"][index].keys():
                self.stand["minecraft:geometry"][0]["bones"][index]["name"]="empty_row+{}".format(i)
                self.stand["minecraft:geometry"][0]["bones"][index]["parent"]="ghost_blocks"
                self.stand["minecraft:geometry"][0]["bones"][index]["pivot"]=[0.5,0.5,0.5]
                i+=1
        start=time.time()
        with open(path_to_geo, "w+") as json_file:
            json.dump(self.stand, json_file)
        texture_name = "{}/textures/entity/ghost_blocks_{}.png".format(
            pack_folder,self.name)
        os.makedirs(os.path.dirname(texture_name), exist_ok=True)
        self.save_uv(texture_name)
        
    def export_big(self, pack_folder):
        ## This exporter just packs up the armorstand json files and dumps them where it should go. as well as exports the UV file
        self.stand["minecraft:geometry"] = []
        size=list(map(int,self.size))
        #offset=[-size[0]//2,0,-size[2]//2]
        geometries={}
        geometries["default"]={}
        geometries["default"]["description"]={}
        geometries["default"]["description"]["identifier"] = "geometry.armor_stand.default"
        geometries["default"]["description"]["texture_width"] = 1
        geometries["default"]["description"]["texture_height"] = 1
        geometries["default"]["description"]["visible_bounds_width"] = 5120
        geometries["default"]["description"]["visible_bounds_height"] = 5120
        geometries["default"]["description"]["visible_bounds_offset"] = [0, 1.5, 0]     
        geometries["default"]["bones"]=[{"name":"ghost_blocks","pivot": [-8, 0, 8],"origin":[0,0,0]}]
        default_geo=[{"size": size,
                        "uv": {
                                "north": {"uv": [0, 0], "uv_size": [1, 1]},
                                "east": {"uv": [0, 0], "uv_size": [1, 1]},
                                "south": {"uv": [0, 0], "uv_size": [1, 1]},
                                "west": {"uv": [0, 0], "uv_size": [1, 1]},
                                "up": {"uv": [1, 1], "uv_size": [-1, -1]},
                                "down": {"uv": [1, 1], "uv_size": [-1, -1]}
                        }},
                     {
                        "size": size,
                        "uv": {
                                "north": {"uv": [0, 3], "uv_size": [1, -1]},
                                "east": {"uv": [0, 3], "uv_size": [1, -1]},
                                "south": {"uv": [0, 3], "uv_size": [1, -1]},
                                "west": {"uv": [0, 3], "uv_size": [1, -1]},
                                "up": {"uv": [0, 1], "uv_size": [1, -1]},
                                "down": {"uv": [0, 3], "uv_size": [1, -1]}
                        }}]
        geometries["default"]["bones"][0]["cubes"]=default_geo
        for i in range(len(self.layers)):
            layer_name=self.layers[i]
            geometries[layer_name] = {}
            geometries[layer_name]["description"] = {}
            geometries[layer_name]["description"]["identifier"] = "geometry.armor_stand.ghost_blocks_{}".format(i)
            geometries[layer_name]["description"]["texture_width"] = ATLAS_COLUMNS
            geometries[layer_name]["description"]["texture_height"] = atlas_rows(
                len(self.uv_map))
            geometries[layer_name]["description"]["visible_bounds_width"] = 5120
            geometries[layer_name]["description"]["visible_bounds_height"] = 5120
            geometries[layer_name]["description"]["visible_bounds_offset"] = [0, 1.5, 0]
            ## A big build turns its whole model with the stand, and a bone
            ## rotates about its pivot, so this one and the offsets in
            ## animation_class.export_big are a pair: change either and the
            ## model swings around a different point.
            geometries[layer_name]["bones"]=[{"name": "ghost_blocks","pivot": [0, 0, 0]},
                                             {"name": layer_name,"parent": "ghost_blocks","pivot": [0, 0, 0]}]
        
        for key in sorted(self.blocks.keys(), key=bone_tier):
            bone = self.blocks[key]
            if bone_tier(key):
                bone["parent"] = self.layer_of(bone)
            layer_name = bone["parent"]
            if layer_name in geometries.keys():
                geometries[layer_name]["bones"].append(bone)
        self.stand["minecraft:geometry"].append(geometries["default"])
        for layer_name in self.layers:
            self.stand["minecraft:geometry"].append(geometries[layer_name])
            
        path_to_geo = "{}/models/entity/armor_stand.ghost_blocks_{}.geo.json".format(pack_folder,self.name)
        os.makedirs(os.path.dirname(path_to_geo), exist_ok=True)            
        with open(path_to_geo, "w+") as json_file:
            json.dump(self.stand, json_file, indent=2)
        
        
        ## Every layer gets its own texture file even though they are identical:
        ## make_big_model declares one texture short name per layer on the armor
        ## stand entity, and a declared texture that resolves to nothing is a
        ## content-log error.
        for i in range(len(self.layers)):
            texture_name = "{}/textures/entity/ghost_blocks_{}.png".format(pack_folder,i)
            os.makedirs(os.path.dirname(texture_name), exist_ok=True)
            self.save_uv(texture_name)

    
    def simplify(self, block_type):
        """The family to draw this block with, given the detail asked for."""
        if not self.low_geometry or block_type == "ignore":
            return block_type
        plain = block_type + LOW_SUFFIX
        ## both tables have to describe it, or the shape and the UV window
        ## would be read from different families
        if plain in self.block_shapes and plain in self.block_uv:
            return plain
        return block_type

    def make_layer(self, y):
        # Adds a layer bone for the animation controller to name later. The pose
        # animations move these bones, which is how the build steps through.
        layer_name = "layer_{}".format(y)
        self.geometry["bones"].append(
            {"name": layer_name, "parent": "ghost_blocks"})#, "pivot": [-8, 0, 8]})

    def choose(self, block_name, states=None, entity=None, data=0):
        """(form, turn, texture index) for one block, as `make_block` reads them.

        With states, the family's rules choose all three. Without, `data` names
        the form and there is no turn or texture choice to make.
        """
        family = self.defs[block_name]
        forms = self.block_shapes[self.simplify(family)]
        if states is not None:
            rules = self.rules.get(family, {})
            return (block_geometry.form(rules, forms, states, entity),
                    block_geometry.turn(rules, states, entity),
                    block_geometry.texture_index(rules, states))
        for name in ("default-{}".format(data), str(data)):
            if name in forms:
                return name, None, None
        return "default", None, None

    def make_block(self, x, y, z, block_name, rot=None, data=0, states=None,
                   entity=None, big=False, tint=None, lift=0.0, yaw=None, hidden=(),
                   family=None, beside=False):
        # Resolves one block through the lookup tables and appends its cubes to
        # the slice bone: shape family, then form, then rotation, then the UV
        # window each face reads from the texture sheet.
        ##
        ## `states` and `entity` are the block's own states and block entity,
        ## and the family's rules in block_geometry.json choose its form, the
        ## state it turns by and the textures it reads from them (see
        ## `block_geometry.form`). Without them, `data` names a form outright
        ## and `rot` the value the rotation table is read with, which is how a
        ## caller asks for one particular form of a block.
        ##
        ## `lift` raises the whole block inside its own cell, in blocks. A block
        ## never needs it -- a block fills the cell it is in -- but an entity is
        ## not on the grid and can stand part way up one: a cushion on a snow
        ## layer is an eighth of a block above the floor of the cell they share.
        ##
        ## `yaw` is a turn about y in degrees, for whatever faces a way given as
        ## an angle rather than a state: an entity, or a head on the floor, whose
        ## block entity holds one. It is a Minecraft block angle -- 0 is the rest
        ## pose, facing north, and 90 faces west -- and is not looked up
        ## anywhere: it is added to whatever the rotation table turns the block
        ## by, and a family with no table is turned by the angle itself.
        ##
        ## `hidden` names faces left undrawn, by the side of the cell they are
        ## on: water against water shows no face between the two.
        ##
        ## `family` draws the block with another family than its own, reading
        ## the block's own textures: water's top, drawn apart from its sides.
        ##
        ## `beside` draws a mark on the block already at this place: its planes
        ## go in that block's own bone, after it, rather than in the planes'
        ## tier, since order within a bone holds and order between bones does
        ## not. A container's count is drawn so.
        ##
        ## `family` is the block's own family and `block_type` the one drawn,
        ## which is its simpler form when low geometry asks for one. Which form
        ## a state picks, and how the block turns, are the family's: a simpler
        ## form is the same block with fewer cubes.
        family = family or self.defs[block_name]
        block_type = self.simplify(family)
        if block_type!="ignore":
            slice_name = "slice_{}".format(y)
            ghost_block_coordinates = "block_{}_{}_{}".format(x, y, z)
            temp_block_group = {}
            temp_block_group["name"] = slice_name
            
            layer_name = "layer_{}".format(y % (12))
            if layer_name not in self.layers:
                self.layers.append(layer_name)
            
            temp_block_group["parent"] = layer_name
            
            ## Settle on one form, then read both tables with it. The shape and
            ## the UV window describe the same cubes, so reading them with
            ## different names is how a half-height cube ends up wearing a
            ## full-height texture.
            shape_variant, turned, texture = self.choose(block_name, states, entity, data)
            if rot is None:
                rot = turned


            block_shapes = self.block_shapes[block_type][shape_variant]
            block_uv = self.block_uv[block_type].get(shape_variant,
                                                     self.block_uv[block_type]["default"])

            temp_block_group["pivot"] = [ block_shapes["center"][0] - (x + self.offsets[0]) \
                                        , block_shapes["center"][1] +  y + self.offsets[1]  \
                                        , block_shapes["center"][2] +  z + self.offsets[2] ]
            #temp_block_group["inflate"] = -0.03

            ## A rotation table that does not describe this state leaves the
            ## block unrotated rather than raising. The tables are keyed by the
            ## state's value, and a family can carry a rotation state its table
            ## has no entry for.
            ## A form may also number its rotations differently from the rest of
            ## the family, and says so with a "<variant>:<value>" key, which is
            ## read first. A hanging sign on a wall turns with facing_direction,
            ## four values, while one hanging from a block turns with
            ## ground_sign_direction, sixteen values, and 2 means something
            ## different in each.
            rotation = None
            if family in self.block_rotations.keys() and rot is not None:
                rotation = self.block_rotations[family].get(
                    "{}:{}".format(shape_variant, rot))
                if rotation is None:
                    rotation = self.block_rotations[family].get(str(rot))
                if rotation is None and debug:
                    print("no rotation {} for block type {}".format(rot, family))
            if yaw is not None:
                rotation = list(rotation) if rotation is not None else [0, 0, 0]
                rotation[1] = (rotation[1] + yaw) % 360
            if rotation is not None:
                temp_block_group["rotation"] = to_bone(rotation)
                if big:
                    temp_block_group["rotation"][1] += 180
            elif debug:
                print("no rotation for block type {} found".format(block_type))
            temp_block_group["cubes"] = []
            uv_idx = 0
            
            
            for i in range(len(block_shapes["size"])):
                if len(block_uv["uv_sizes"]["up"])>i:
                    uv_idx=i
                ## the faces this cube draws; see below
                faces = {dir for dir, sizes in block_uv["uv_sizes"].items()
                         if any(sizes[uv_idx]) and dir not in hidden}
                uv = self.block_name_to_uv(block_name,shape_variant=shape_variant,index=i,tint=tint,block_type=block_type,texture=texture,faces=faces)
                block={}
                xoff = 0
                yoff = 0
                zoff = 0
                if "offsets" in block_shapes.keys():
                    xoff = block_shapes["offsets"][i][0]
                    yoff = block_shapes["offsets"][i][1]
                    zoff = block_shapes["offsets"][i][2]
                block["origin"] = [-1*(x + self.offsets[0]) + xoff, y + yoff + lift + self.offsets[1], z + zoff + self.offsets[2]]
                block["size"] = block_shapes["size"][i]

                if "rotation" in block_shapes.keys():
                    block["rotation"] = block_shapes["rotation"][i]
                    

                block_uv_faces=dict(uv)
                ## the tile each face reads, before its window moves it
                tiles = {dir: list(face["uv"]) for dir, face in uv.items()}
                for dir in ["up", "down", "east", "west", "north", "south"]:
                    ## **A face whose window has no size is not drawn.** A
                    ## cube's uv in a .geo.json may leave a face out, and the
                    ## face is then not drawn at all, which is how a plane or a
                    ## crossed plant shows only the sides it has.
                    if dir in hidden or not any(block_uv["uv_sizes"][dir][uv_idx]):
                        block_uv_faces.pop(dir, None)
                        continue
                    block_uv_faces[dir]["uv"][0] += block_uv["offset"][dir][uv_idx][0]
                    block_uv_faces[dir]["uv"][1] += block_uv["offset"][dir][uv_idx][1]
                    block_uv_faces[dir]["uv_size"] = block_uv["uv_sizes"][dir][uv_idx]
                
                block["uv"] = block_uv_faces
                flat = sum(1 for n in block["size"] if n == 0) == 1
                if flat:
                    self.trim_plane(block, tiles)
                ## **A plane and water are drawn after everything else.** A
                ## ghost is blended, so a clear texel still takes the depth it
                ## stands at and hides any ghost drawn after it, and water
                ## hides whatever stands in it the same way. Drawn last, what
                ## is behind them is already there.
                if family in self.drawn_early:
                    block[LAST_CUBE] = EARLY_BONE
                elif family in self.drawn_after_slice:
                    block[LAST_CUBE] = AFTER_SLICE
                elif family in self.drawn_liquid:
                    block[LAST_CUBE] = LIQUID_BONE
                elif (flat or family in self.drawn_last) and not (
                        beside or family in self.shared_bone):
                    block[LAST_CUBE] = LAST_BONE
                ## a cube with no face drawn is nothing, which is how a form
                ## says a state shows nothing at all, such as the top half of
                ## a pitcher crop too young to have grown one
                if block_uv_faces:
                    temp_block_group["cubes"].append(block)

            for each_group in [ temp_block_group ]:
                ## the one nested bone this block needs, if any, and the cubes
                ## that went into it and so must not be drawn in the slice too
                ## one nested bone for the cubes drawn in turn and one for those
                ## drawn last
                nested_groups = {}
                nested_cubes = set()
                copied_groups = []

                is_rotated_group = ( "rotation" in each_group.keys() ) and ( "pivot" in each_group.keys() )
                if( is_rotated_group and ( each_group["rotation"] is None or len( each_group["rotation"] ) != 3 ) ):
                    is_rotated_group = False
                if( is_rotated_group and ( each_group["pivot"]    is None or len( each_group["pivot"] ) != 3 ) ):
                    is_rotated_group = False
                
                for each_cube in temp_block_group["cubes"]:
                    cube_is_ready = False

                    ## A cube that does not turn on its own is not a rotated
                    ## cube. The shape table gives every cube a rotation as soon
                    ## as one of them needs one, and treating a zero as a turn
                    ## puts each of them in a bone of its own for nothing.
                    if ( "rotation" in each_cube.keys() ) and ( each_cube["rotation"] is not None ) and not any( each_cube["rotation"] ):
                        del each_cube["rotation"]

                    isRotatedCube = ( "rotation" in each_cube.keys() ) and ( "pivot" in each_cube.keys() )
                    if( isRotatedCube and ( each_cube["rotation"] is None or len( each_cube["rotation"] ) != 3 ) ):
                        isRotatedCube = False
                    if( isRotatedCube and ( each_cube["pivot"]    is None or len( each_cube["pivot"] ) != 3 ) ):
                        isRotatedCube = False
                    
                    isOnlyRotatedCube = ( "rotation" in each_cube.keys() )
                    if( isOnlyRotatedCube and ( each_cube["rotation"] is None or len( each_cube["rotation"] ) != 3 ) ):
                        isOnlyRotatedCube = False
                    
                    if( isOnlyRotatedCube and "pivot" not in each_cube ):
                        ## A cube with a "rotation" and no "pivot" rotates around
                        ## its own centre, so state that centre outright. See the
                        ## geometry 1.16.0 schema reference:
                        ## https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_geometry_1.16.0
                        each_cube["pivot"] = [ each_cube["origin"][0] + each_cube["size"][0] / 2.0 \
                                            , each_cube["origin"][1] + each_cube["size"][1] / 2.0 \
                                            , each_cube["origin"][2] + each_cube["size"][2] / 2.0 ]
                        isRotatedCube = True
                    
                    
                    if( not(isRotatedCube) and is_rotated_group ):
                        ## Apply group's "rotation" and "pivot" to cube
                        each_cube["rotation"] = [ each_group["rotation"][0], each_group["rotation"][1], each_group["rotation"][2] ]
                        each_cube["pivot"]    = [ each_group["pivot"   ][0], each_group["pivot"   ][1], each_group["pivot"   ][2] ]
                    #elif( not(is_rotated_group) and isRotatedCube ):
                        ## Keep existing cube "rotation" and "pivot"
                    elif( is_rotated_group and isRotatedCube and  each_cube["pivot"] == each_group["pivot"] ):
                        ## Same "pivot" point...  Matrix-Sum cube and group "rotation" value arrays
                        each_cube["rotation"] = [ each_group["rotation"][0] + each_cube["rotation"][0], each_group["rotation"][1] + each_cube["rotation"][1], each_group["rotation"][2] + each_cube["rotation"][2] ]
                    elif( is_rotated_group and isRotatedCube ):
                        ## Cube and group turn about different points, and no
                        ## single rotation says both, so the cube goes into a
                        ## bone carrying the group's turn and keeps its own. One
                        ## bone holds all of a block's cubes that need this: they
                        ## take the same rotation about the same pivot, and only
                        ## the cubes inside differ.
                        late = each_cube.get(LAST_CUBE) or ""
                        nested_group = nested_groups.get(late)
                        if nested_group is None:
                            nested_group =  { "parent": each_group["name"], "name": each_group["name"] + "___" + ghost_block_coordinates }
                            if late:
                                nested_group["name"] = late + nested_group["name"]

                            for primitiveKey in [ "mirror", "inflate", "debug", "render_group_id", "binding" ]:
                                if primitiveKey in each_group.keys():
                                    nested_group[primitiveKey] = each_group[primitiveKey]

                            for objectKey in [ "pivot", "rotation", "locators", "poly_mesh", "texture_meshes" ]:
                                if objectKey in each_group.keys():
                                    nested_group[objectKey] = copy.deepcopy( each_group[objectKey] )

                            nested_group["cubes"] = []
                            nested_groups[late] = nested_group
                            copied_groups.append( nested_group )
                        nested_group["cubes"].append( each_cube )
                        nested_cubes.add( id( each_cube ) )
                
                ## next each_cube
                
                
                ## A cube that went into a nested bone is drawn there. Leaving it
                ## in the slice as well draws it twice, once turned and once not,
                ## which is two ghost blocks in one place.
                kept = [each_cube for each_cube in temp_block_group["cubes"]
                        if id(each_cube) not in nested_cubes]
                ## a cube drawn last goes in a bone of its own under the slice,
                ## written after every other bone
                late = [each_cube for each_cube in kept if each_cube.get(LAST_CUBE)]
                kept = [each_cube for each_cube in kept if not each_cube.get(LAST_CUBE)]
                for each_cube in late:
                    mark = each_cube[LAST_CUBE]
                    last_name = (each_group["name"] + mark if mark == AFTER_SLICE
                                 else mark + each_group["name"])
                    if last_name not in self.blocks:
                        self.blocks[last_name] = {"name": last_name, "parent": each_group["name"],
                                                  "pivot": [0, 0, 0], "cubes": []}
                    self.blocks[last_name]["cubes"].append(each_cube)
                for each_cube in temp_block_group["cubes"]:
                    each_cube.pop(LAST_CUBE, None)

                ## Nothing here is copied on the way in. temp_block_group is
                ## built again for the next block and never read after this, so
                ## the cubes have one owner from here on.
                if each_group["name"] in self.blocks.keys():
                    self.blocks[each_group["name"]]["cubes"].extend( kept )
                else:
                    if "rotation" in each_group.keys():
                        del each_group["rotation"]
                    if "pivot" in each_group.keys():
                        del each_group["pivot"]
                    each_group["cubes"] = kept
                    self.blocks[each_group["name"]] = each_group

                ## **Two things drawn at one place share its turned bone when they
                ## turn alike**, a container and the marks on it, a pot and its
                ## plant: the second's cubes are drawn after the first's in it.
                ## Turned differently, the second has a bone of its own.
                for newChildGroup in copied_groups:
                    name = newChildGroup["name"]
                    found = self.blocks.get(name)
                    if found is not None and (found.get("pivot"), found.get("rotation")) == (
                            newChildGroup.get("pivot"), newChildGroup.get("rotation")):
                        found["cubes"].extend(newChildGroup["cubes"])
                        continue
                    count = 2
                    while name in self.blocks:
                        name = "%s_%d" % (newChildGroup["name"], count)
                        count += 1
                    newChildGroup["name"] = name
                    self.blocks[name] = newChildGroup
            

    @property
    def uv_array(self):
        """The whole sheet, assembled from the tiles collected so far.

        Built on demand rather than grown a tile at a time: the old version
        reallocated the entire array on every append, which is quadratic in the
        number of textures and was a measurable part of a large pack's build.
        """
        if not self.uv_tiles:
            return None
        rows = atlas_rows(len(self.uv_tiles))
        sheet = zeros([rows * 16, ATLAS_COLUMNS * 16, 4], uint8)
        for index, tile in enumerate(self.uv_tiles):
            across, down = atlas_place(index)
            sheet[down * 16:down * 16 + 16,
                  across * 16:across * 16 + 16, :] = tile
        return sheet

    @uv_array.setter
    def uv_array(self, value):
        ## only ever set to None, to empty the sheet between blocks
        if value is not None:
            raise ValueError("the sheet is built from uv_tiles")
        self.uv_tiles = []

    def tile(self, index):
        """One 16x16 tile, by the index uv_map gave it.

        The way to read a tile without knowing how the sheet is laid out, which
        is what everything checking a texture wants.
        """
        return self.uv_tiles[index]

    def save_uv(self, name):
        # writes the assembled UV sheet to the given path
        sheet = self.uv_array
        if sheet is None:
            print("No Blocks Were found")
        else:
            im = Image.fromarray(sheet)
            im.save(name)

    def stand_init(self):
        # helper function to initialize the dictionary that will be exported as the json object
        self.stand["format_version"] = "1.16.0"
        self.geometry["description"] = {
            "identifier": "geometry.armor_stand.ghost_blocks_{}".format(self.name)}
        self.geometry["description"]["texture_width"] = ATLAS_COLUMNS
        self.geometry["description"]["visible_bounds_offset"] = [
            0.0, 1.5, 0.0]
        # Changed render distance of the block geometry
        self.geometry["description"]["visible_bounds_width"] = 5120
        # Changed render distance of the block geometry
        self.geometry["description"]["visible_bounds_height"] = 5120
        self.geometry["bones"] = []
        self.stand["minecraft:geometry"] = [self.geometry]
        self.geometry["bones"] = [
                                    {"name": "ghost_blocks",
                                     "pivot": [-8, 0, 8]}]

    def extend_uv_image(self, new_image_filename, window=(0, 0), tint=None,
                        turn=0):
        # Appends one 16x16 tile to the atlas. `window` is the corner of the
        # region to take, in pixels; a texture larger than a tile is cropped
        # rather than scaled, so its pixels keep their size. `tint` multiplies
        # it on the way in, which is how a block whose colour is a whole colour
        # rather than one of a list gets a tile of its own. `turn` is a quarter
        # turn clockwise, applied to the finished tile, which is the only way a
        # face can read its picture a quarter round: Bedrock's UV has a corner
        # and a size and no angle.

        # Fallback to a tga
        if not os.path.isfile(new_image_filename):
            new_image_filename = new_image_filename.split(".")[0] + ".tga"

        image = Image.open(new_image_filename).convert("RGBA")
        impt = array(image)
        if tint is not None:
            ## the same multiply the game does with a colormap, done once here
            ## because a ghost block has no colormap to run
            impt = impt.astype(int)
            for band, level in enumerate(tint):
                impt[:, :, band] = impt[:, :, band] * level // 255
        ## A window past the edge of the texture is ignored rather than filled
        ## with the blank the tile is built on. The blocks that name one are
        ## drawn from a sheet, and a legacy id resolving to a plain terrain tile
        ## is better off reading the tile than reading nothing. A texture
        ## smaller than a tile one way is read from its edge that way, so a
        ## strip like conduit_base, 24 by 12, can still be read past x16.
        across, down = window
        if (max(impt.shape[0], 16) < down + 16
                or max(impt.shape[1], 16) < across + 16):
            across, down = 0, 0
        if down:
            impt = impt[down:, :, :]
        if across:
            impt = impt[:, across:, :]
        shape=list(impt.shape)
        if shape[0]>16:
            shape[0]=16
            impt=impt[0:16,:,:]
        if shape[1]>16:
            shape[1]=16
            impt=impt[:,0:16,:]
        image_array = ones([16, 16, 4],uint8)*255
        image_array[0:shape[0], 0:shape[1], 0:impt.shape[2]] = impt
        if turn:
            ## rot90 turns anticlockwise, and the mark is read clockwise, so
            ## the count is negated. The tile is square, so it stays 16x16.
            image_array = ascontiguousarray(rot90(image_array, -turn // 90))
        image_array[:, :, 3] = image_array[:, :, 3] * self.alpha
        self.uv_tiles.append(image_array)

    def block_name_to_uv(self, block_name, shape_variant="default", index=0, tint=None,
                         block_type=None, texture=None, faces=None):
        
        # helper function maps the section of the uv file to the side of the block
        temp_uv = {}
        if block_name not in self.excluded:  # if you dont want a block to be rendered, exclude the UV

            ## the family being drawn, which is the simpler form when one was
            ## asked for: its cubes are not the detailed family's, so neither
            ## are the textures each one wears
            block_type = block_type or self.defs[block_name]
            
            texture_files = self.get_block_texture_paths(block_name, texture)

            ## a face `make_block` leaves out of the model, because its window
            ## has no size, has no texture to put in the atlas either
            drawn = set(texture_files) if faces is None else set(faces)

            corrected_textures={}
            if shape_variant in self.block_uv[block_type].keys():
                if "overwrite" in self.block_uv[block_type][shape_variant].keys():
                    corrected_textures = self.block_uv[block_type][shape_variant]["overwrite"]
            else:
                if "overwrite" in self.block_uv[block_type]["default"].keys():
                    corrected_textures = self.block_uv[block_type]["default"]["overwrite"]
            
            ## An overwrite entry names the texture a particular cube of a
            ## particular face should use. A literal path is used as given. A
            ## value written "@up", "@down" or "@north" means "the texture this
            ## block already declares for that face", which is how one family can
            ## put a different texture on each part of a multi-part model without
            ## naming any block's textures. A door is the clearest case: every
            ## door declares its lower half on "down" and its upper half on
            ## "side", and the model is two stacked cubes.
            declared = dict(texture_files)
            for side in corrected_textures.keys():
                if len(corrected_textures[side])>index:
                    chosen = corrected_textures[side][index]
                    if chosen == "default":
                        continue
                    if isinstance(chosen, str) and chosen.startswith("@"):
                        ## a window travels with the reference, so one entry can
                        ## say "the board half of whatever sheet this wood has"
                        reference, mark, window = chosen.partition(WINDOW_MARK)
                        ## and a turn may travel with it whether or not a
                        ## window does, so it is taken off the name first
                        reference, spin, angle = reference.partition(TURN_MARK)
                        resolved = declared.get(reference[1:])
                        if resolved is None:
                            continue
                        chosen = resolved + mark + window + spin + angle
                    texture_files[side]=chosen
                    if debug:
                        print("{}: {}".format(side,texture_files[side]))
            for key in texture_files.keys():
                if key not in drawn:
                    continue
                ## a texture that asks for a tint takes this block's own colour,
                ## so every colour lands in the atlas as a tile of its own
                texture_files[key] = tinted(texture_files[key], tint)
                if texture_files[key] not in self.uv_map.keys():
                    try:
                        source, window = split_window(texture_files[key])
                        _named, colour = split_tint(texture_files[key])
                        _named, turn = split_turn(texture_files[key])
                        self.extend_uv_image(
                            self.texture_file(source), window, colour, turn)
                        self.uv_map[texture_files[key]] = len(self.uv_map.keys())
                    except Exception as e:
                        raise RuntimeError("Failed to load texture {}".format(texture_files[key]))
                across, down = atlas_place(self.uv_map[texture_files[key]])
                temp_uv[key] = {"uv": [across, down], "uv_size": [1, 1]}

        return temp_uv

    def trim_plane(self, cube, tiles):
        """Cut an upright plane down to the part of its picture with something
        in it.

        A plane's clear texels hide the ghosts drawn behind them, so the less
        clear picture a plane carries the less it hides. Across, the same
        amount comes off both sides, the smaller of the two clear margins, so
        a plane turned about its own middle stays where it was; up and down,
        each end loses its own clear rows, and a turned plane keeps the pivot
        it had. A plane lying flat loses the same amount off both sides each
        way: see `trim_flat`.
        """
        size, origin, faces = cube["size"], cube["origin"], cube["uv"]
        if not faces:
            return
        if size[1] == 0:
            return self.trim_flat(cube, tiles)
        across = 0 if size[0] else 2
        main = next(iter(faces))
        corner = tiles.get(main)
        if corner is None:
            return
        tile = self.tile(atlas_index(*corner))
        (u0, v0) = [faces[main]["uv"][i] - corner[i] for i in (0, 1)]
        su, sv = faces[main]["uv_size"]
        cols = sorted(int(round((u0 + su * t) * 16)) for t in (0, 1))
        rows = sorted(int(round((v0 + sv * t) * 16)) for t in (0, 1))
        cols = [max(cols[0], 0), min(cols[1], 16)]
        rows = [max(rows[0], 0), min(rows[1], 16)]
        if cols[1] <= cols[0] or rows[1] <= rows[0]:
            return
        painted = tile[rows[0]:rows[1], cols[0]:cols[1], 3] > 0
        if not painted.any():
            return
        used_cols = painted.any(axis=0).nonzero()[0]
        used_rows = painted.any(axis=1).nonzero()[0]
        side = int(min(used_cols[0], len(painted[0]) - 1 - used_cols[-1]))
        top = int(used_rows[0])
        bottom = int(len(painted) - 1 - used_rows[-1])
        if not (side or top or bottom):
            return
        if cube.get("rotation") and any(cube["rotation"]) and "pivot" not in cube:
            cube["pivot"] = [origin[i] + size[i] / 2.0 for i in range(3)]
        per_u = size[across] / float(cols[1] - cols[0])
        per_v = size[1] / float(rows[1] - rows[0])
        lost_top, lost_bottom = (top, bottom) if sv > 0 else (bottom, top)
        size = list(size)
        origin = list(origin)
        size[across] -= 2 * side * per_u
        origin[across] += side * per_u
        size[1] -= (lost_top + lost_bottom) * per_v
        origin[1] += lost_bottom * per_v
        cube["size"], cube["origin"] = size, origin
        for face in faces.values():
            fu, fv = face["uv"]
            u_size, v_size = face["uv_size"]
            u_sign = 1 if u_size > 0 else -1
            v_sign = 1 if v_size > 0 else -1
            face["uv"] = [fu + u_sign * side / 16.0,
                          fv + v_sign * (top if v_size > 0 else bottom) / 16.0]
            face["uv_size"] = [u_size - u_sign * 2 * side / 16.0,
                               v_size - v_sign * (top + bottom) / 16.0]

    def trim_flat(self, cube, tiles):
        """Cut a plane lying flat down to the part of its picture with
        something in it, the smaller clear margin off both sides each way, so
        it keeps its middle. A face's window runs along x and z, whichever way
        round, and the same amount comes off each end."""
        size, origin, faces = cube["size"], cube["origin"], cube["uv"]
        if cube.get("rotation") and any(cube["rotation"]):
            return
        main = "up" if "up" in faces else next(iter(faces))
        corner = tiles.get(main)
        if corner is None:
            return
        tile = self.tile(atlas_index(*corner))
        (u0, v0) = [faces[main]["uv"][i] - corner[i] for i in (0, 1)]
        su, sv = faces[main]["uv_size"]
        cols = sorted(int(round((u0 + su * t) * 16)) for t in (0, 1))
        rows = sorted(int(round((v0 + sv * t) * 16)) for t in (0, 1))
        cols = [max(cols[0], 0), min(cols[1], 16)]
        rows = [max(rows[0], 0), min(rows[1], 16)]
        if cols[1] <= cols[0] or rows[1] <= rows[0]:
            return
        painted = tile[rows[0]:rows[1], cols[0]:cols[1], 3] > 0
        if not painted.any():
            return
        used_cols = painted.any(axis=0).nonzero()[0]
        used_rows = painted.any(axis=1).nonzero()[0]
        side_u = int(min(used_cols[0], len(painted[0]) - 1 - used_cols[-1]))
        side_v = int(min(used_rows[0], len(painted) - 1 - used_rows[-1]))
        if not (side_u or side_v):
            return
        per_u = size[0] / float(cols[1] - cols[0])
        per_v = size[2] / float(rows[1] - rows[0])
        size = list(size)
        origin = list(origin)
        size[0] -= 2 * side_u * per_u
        origin[0] += side_u * per_u
        size[2] -= 2 * side_v * per_v
        origin[2] += side_v * per_v
        cube["size"], cube["origin"] = size, origin
        for face in faces.values():
            fu, fv = face["uv"]
            u_size, v_size = face["uv_size"]
            u_sign = 1 if u_size > 0 else -1
            v_sign = 1 if v_size > 0 else -1
            face["uv"] = [fu + u_sign * side_u / 16.0, fv + v_sign * side_v / 16.0]
            face["uv_size"] = [u_size - u_sign * 2 * side_u / 16.0,
                               v_size - v_sign * 2 * side_v / 16.0]

    def add_blocks_to_bones(self):
        # Moves every collected block group into the geometry's bone list. Called
        # during the writing step, once every block has been made. A slice is
        # already one bone; the rest are the nested bones a turned block needs,
        # one per block.
        ## **The bones drawn last go at the end, planes and then water, each
        ## under a layer bone of its own tier.** Hung from its slice, a slice's
        ## water would be reached with the slice, before every layer after it,
        ## wherever the game walks the bones by their parents. A tier's layer
        ## bones sit after every plain one, so the tiers are drawn in order
        ## whether the bones are walked as listed or by parent, and the pose
        ## animations scale each with the plain layer of its number.
        made = set()
        for key in sorted(self.blocks.keys(), key=bone_tier):
            bone = self.blocks[key]
            tier = TIER_PREFIX.get(bone_tier(key))
            if tier:
                layer = tier + self.layer_of(bone)
                if layer not in made:
                    made.add(layer)
                    self.geometry["bones"].append({"name": layer, "parent": "ghost_blocks"})
                bone["parent"] = layer
            self.geometry["bones"].append(bone)

    def layer_of(self, bone):
        """The plain layer a bone is drawn in: its slice's layer."""
        parent = bone.get("parent")
        while parent in self.blocks and not parent.startswith("layer_"):
            parent = self.blocks[parent].get("parent")
        return parent

    ## the extensions a texture may be saved with, in the order they are
    ## tried. Bedrock reads either and a tweak may ship one where the vanilla
    ## pack ships the other, which is how Age 25 Kelp arrives as a TGA.
    TEXTURE_KINDS = (".png", ".tga")

    def texture_file(self, source):
        """Where one texture actually is, tweaks first and vanilla after.

        `source` is a pack relative path with no extension, the way
        `terrain_texture.json` writes it. The path handed back is the first that
        exists; when none does, the vanilla pack's PNG is named anyway, so the
        error a caller raises points at the file somebody would expect.
        """
        for root in self.tweak_folders + [self.ref_resource_pack]:
            for kind in self.TEXTURE_KINDS:
                candidate = os.path.join(root, source.replace("/", os.sep)
                                         + kind)
                if os.path.isfile(candidate):
                    return candidate
        return "{}/{}.png".format(self.ref_resource_pack, source)

    @staticmethod
    def named_entry(block_name, entries):
        """Which entry of a shared texture list a block reads, by its name.

        Several blocks Mojang has split into an id each still point at one list
        in `blocks.json`, and the game picks each one's entry itself: every
        wooden door reads `door_lower`, whose entries run oak, spruce, birch,
        jungle, acacia, dark oak. Nothing in the files says which is which,
        but the names do, so the longest leading part of the block's id that
        names exactly one entry picks it. Anything else reads the first.
        """
        parts = block_name.split(":")[-1].split("_")
        files = [entry.split("/")[-1] if isinstance(entry, str) else ""
                 for entry in entries]
        for end in range(len(parts), 0, -1):
            stem = "_".join(parts[:end])
            found = [i for i, name in enumerate(files)
                     if stem in name.split("_") or "_" + stem + "_" in "_" + name + "_"]
            if len(found) == 1:
                return found[0]
            if found:
                return 0
        return 0

    def get_block_texture_paths(self, blockName, texture=None):
        # helper function for getting the texture locations from the vanilla files.
        ## **A drawn thing that is not a block has no declaration to read.** An
        ## entity is not in blocks.json and never will be, so a family drawn for
        ## one names every face outright in its `overwrite` and wants nothing
        ## from here. Answering with nothing rather than raising is what lets it
        ## through; a real block missing its declaration has no overwrite
        ## either, so it still fails and is still reported as unsupported.
        declared = self.blocks_def.get(blockName)
        if not declared:
            return {}
        ## **A tweak may paint the carried block rather than the placed one.**
        ## Minecraft can only tell waxed copper from unwaxed in the inventory,
        ## so Bedrock Tweaks puts that art in `carried_textures`. A ghost block
        ## is the placed block and there is no inventory near it, so for those
        ## packs the carried textures are the ones to read.
        if (blockName in self.tweak_carried
                and "carried_textures" in declared):
            texture_layout = declared["carried_textures"]
        elif "textures" in declared:
            texture_layout = declared["textures"]
        else:
            return {}
        texturedata = self.terrain_texture["texture_data"]
        textures = {}

        if type(texture_layout) is dict:
            if "side" in texture_layout.keys():
                textures["east"] = texture_layout["side"]
                textures["west"] = texture_layout["side"]
                textures["north"] = texture_layout["side"]
                textures["south"] = texture_layout["side"]
            if "east" in texture_layout.keys():
                textures["east"] = texture_layout["east"]
            if "west" in texture_layout.keys():
                textures["west"] = texture_layout["west"]
            if "north" in texture_layout.keys():
                textures["north"] = texture_layout["north"]
            if "south" in texture_layout.keys():
                textures["south"] = texture_layout["south"]
            if "down" in texture_layout.keys():
                textures["down"] = texture_layout["down"]
            if "up" in texture_layout.keys():
                textures["up"] = texture_layout["up"]
        elif type(texture_layout) is str:
            textures["east"] = texture_layout
            textures["west"] = texture_layout
            textures["north"] = texture_layout
            textures["south"] = texture_layout
            textures["up"] = texture_layout
            textures["down"] = texture_layout
        for key in textures.keys():
            
            if type(texturedata[textures[key]]["textures"]) is str:
                textures[key] = texturedata[textures[key]]["textures"]
            elif type(texturedata[textures[key]]["textures"]) is list:
                ## the entry a state of the block picks, through its family's
                ## `texture_by`, and otherwise the one the block's name points at
                if texture is not None:
                    index = texture
                else:
                    index = self.named_entry(
                        blockName, texturedata[textures[key]]["textures"])
                ## One variant index reads every face, and the faces do not
                ## have to name lists of the same length: a double plant's
                ## sides name two textures, the sunflower's front and back,
                ## while its halves name six, one per plant. A face with no
                ## entry that far along takes its last one rather than dropping
                ## the block.
                choices_for_face = texturedata[textures[key]]["textures"]
                textures[key] = choices_for_face[min(index, len(choices_for_face) - 1)]

        ## the block's inventory picture, for a face that reads the `item`
        ## slot: low geometry draws some blocks as it, on the sides of a box.
        ## `tools/textures/item_icons.py` writes the table; a block it does not
        ## name shows its own north picture
        if textures:
            textures["item"] = self.item_icons.get(blockName) or textures.get("north")
        return textures
