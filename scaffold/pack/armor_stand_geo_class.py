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

from scaffold import paths
debug = False##used in API test to force errors and break error handler, should remain false.

## Blocks that never become geometry. scaffold_core needs the same list in the
## namespaced form the structure files store it, so it derives it from here
## rather than keeping a second copy.
EXCLUDED_BLOCKS = ("air", "structure_block")

## how a shape family names its simpler form, in block_shapes and block_uv
LOW_SUFFIX = "__low"

## Marks a window into a texture, written after the texture's name as
## "<texture>#<x>,<y>". Only the top left 16x16 of a texture becomes a tile, so
## a block drawn from an entity sized sheet -- a hanging sign's 64x32 sheet
## carries the bar, the chains and the board one under the other -- can reach
## the part it needs no other way. Each window becomes a tile of its own,
## because the atlas is keyed by the whole name.
WINDOW_MARK = "#"

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
    def __init__(self, name, alpha = DEFAULT_ALPHA,offsets=None, size=[64, 64, 64], ref_pack=None, low_geometry=False):
        self.ref_resource_pack = ref_pack or paths.vanilla_pack()
        ## Each of these tables maps a block to a property that the structure
        ## file leaves hidden, implied, or otherwise unclear.
        with open("{}/blocks.json".format(self.ref_resource_pack)) as f:
            ## defines a block from its NBT name, and gives sides against textures
            self.blocks_def = json.load(f)
        with open("{}/textures/terrain_texture.json".format(self.ref_resource_pack)) as f:
            ##maps textures names to texture files.
            self.terrain_texture = json.load(f)
        with open(paths.lookup("block_rotation.json")) as f:
            ## rotation per state, per shape family. A block whose state has no
            ## entry is left unrotated, and reports it when debug is on.
            self.block_rotations = json.load(f)
        with open(paths.lookup("variants.json")) as f:
            ## maps a variant state's value to an index into a terrain_texture
            ## list. log2 index 2, for instance, means a wood type the block's
            ## own states never name.
            self.block_variants = json.load(f)
        with open(paths.lookup("block_definition.json")) as f:
            self.defs = json.load(f)
        with open(paths.lookup("block_shapes.json")) as f:
            self.block_shapes = json.load(f)
        with open(paths.lookup("block_uv.json")) as f:
            self.block_uv = json.load(f)
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
        self.uv_array = None
        self.pre_gen_blocks={}
        self.excluded = EXCLUDED_BLOCKS

    def export(self, pack_folder):
        start = time.time()
        ## This exporter just packs up the armorstand json files and dumps them where it should go. as well as exports the UV file
        self.add_blocks_to_bones()
        self.geometry["description"]["texture_height"] = len(
            self.uv_map.keys())
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
            geometries[layer_name]["description"]["texture_width"] = 1
            geometries[layer_name]["description"]["texture_height"] = len(self.uv_map.keys())
            geometries[layer_name]["description"]["visible_bounds_width"] = 5120
            geometries[layer_name]["description"]["visible_bounds_height"] = 5120
            geometries[layer_name]["description"]["visible_bounds_offset"] = [0, 1.5, 0]
            ## A big build turns its whole model with the stand, and a bone
            ## rotates about its pivot, so this one and the offsets in
            ## animation_class.export_big are a pair: change either and the
            ## model swings around a different point.
            geometries[layer_name]["bones"]=[{"name": "ghost_blocks","pivot": [0, 0, 0]},
                                             {"name": layer_name,"parent": "ghost_blocks","pivot": [0, 0, 0]}]
        
        for key in self.blocks.keys():
            layer_name = self.blocks[key]["parent"]
            if layer_name in geometries.keys():
                geometries[layer_name]["bones"].append(self.blocks[key])
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

    def make_block(self, x, y, z, block_name, rot=None, top=False,data=0, trap_open=False, parent=None,variant="default", big = False, hinge=False, tint=None):
        # Resolves one block through the lookup tables and appends its cubes to
        # the slice bone: shape family, then variant, then rotation, then the
        # UV window each face reads from the texture sheet.
        block_type = self.simplify(self.defs[block_name])
        if block_type!="ignore":
            slice_name = "slice_{}".format(y)
            ghost_block_coordinates = "block_{}_{}_{}".format(x, y, z)
            temp_block_group = {}
            temp_block_group["name"] = slice_name
            
            layer_name = "layer_{}".format(y % (12))
            if layer_name not in self.layers:
                self.layers.append(layer_name)
            
            temp_block_group["parent"] = layer_name
            
            ## Settle on one variant name, then read both tables with it. The
            ## shape and the UV window describe the same cubes, so reading them
            ## with different names is how a half-height cube ends up wearing a
            ## full-height texture.
            shape_variant="default"
            if block_type == "hopper" and rot is not None and rot != 0:
                shape_variant="side"
            elif (block_type.startswith("skull") and rot is not None
                  and str(rot) != "1" and not str(rot).startswith("spin")):
                ## A head reads facing_direction, where 1 is the floor and 2 to
                ## 5 name the wall it hangs on. The mounting is the shape as
                ## well as the turn, and the state carries both.
                ##
                ## **A head on the floor arrives as `spinN`, not as 1.** Which
                ## of sixteen ways it faces is in the block entity rather than
                ## the states, so `core.py` hands the turn over as `spin0` to
                ## `spin15` and the plain 1 is only what a floor head with no
                ## entity beside it keeps. Read as a wall value, every skull
                ## anybody had actually placed on the ground was drawn four
                ## pixels up and four back, hanging in the air.
                shape_variant = "wall"
            elif block_type == "door" and top:
                ## The lower block of a door draws both of its halves, so the
                ## upper one draws nothing at all. That has to be settled before
                ## the open forms below, or an open door is drawn twice: once by
                ## each of its blocks, in the same place.
                shape_variant = "top"
            elif block_type == "door" and trap_open:
                ## A door standing open is a different shape, not the closed one
                ## turned. Which way it swings is the hinge, which decides the
                ## side of the frame it folds back against, so two doors of one
                ## facing and opposite hinges open into different blocks.
                shape_variant = "open_hinged" if hinge else "open"
            elif block_type == "trapdoor" and trap_open:
                shape_variant = "open"
            elif block_type == "lever" and trap_open:
                shape_variant = "on"
            elif top:
                shape_variant = "top"

            ## a numeric state - snow depth, repeater delay, sea pickle count -
            ## names its own variant and outranks the flags above
            if str(data) in self.block_shapes[block_type] or str(data) in self.block_uv[block_type]:
                shape_variant = str(data)

            ## A shape family that does not describe this variant falls back to
            ## its default rather than raising, which would drop the block into
            ## the skipped list. A double slab carries a vertical_half state it
            ## does not use.
            if shape_variant not in self.block_shapes[block_type]:
                shape_variant = "default"

            if data!=0 and debug:
                print(data)

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
            if block_type in self.block_rotations.keys() and rot is not None:
                rotation = self.block_rotations[block_type].get(
                    "{}:{}".format(shape_variant, rot))
                if rotation is None:
                    rotation = self.block_rotations[block_type].get(str(rot))
                if rotation is None and debug:
                    print("no rotation {} for block type {}".format(rot, block_type))
            if rotation is not None:
                temp_block_group["rotation"] = copy.deepcopy(rotation)
                if big:
                    temp_block_group["rotation"][1] += 180
            elif debug:
                print("no rotation for block type {} found".format(block_type))
            temp_block_group["cubes"] = []
            uv_idx = 0
            
            
            for i in range(len(block_shapes["size"])):
                uv = self.block_name_to_uv(block_name,variant=variant,shape_variant=shape_variant,index=i,tint=tint)
                block={}
                if len(block_uv["uv_sizes"]["up"])>i:
                    uv_idx=i
                xoff = 0
                yoff = 0
                zoff = 0
                if "offsets" in block_shapes.keys():
                    xoff = block_shapes["offsets"][i][0]
                    yoff = block_shapes["offsets"][i][1]
                    zoff = block_shapes["offsets"][i][2]
                block["origin"] = [-1*(x + self.offsets[0]) + xoff, y + yoff + self.offsets[1], z + zoff + self.offsets[2]]
                block["size"] = block_shapes["size"][i]

                if "rotation" in block_shapes.keys():
                    block["rotation"] = block_shapes["rotation"][i]
                    

                block_uv_faces=dict(uv)
                for dir in ["up", "down", "east", "west", "north", "south"]:
                    block_uv_faces[dir]["uv"][0] += block_uv["offset"][dir][uv_idx][0]
                    block_uv_faces[dir]["uv"][1] += block_uv["offset"][dir][uv_idx][1]
                    block_uv_faces[dir]["uv_size"] = block_uv["uv_sizes"][dir][uv_idx]
                
                block["uv"] = block_uv_faces
                temp_block_group["cubes"].append(block)

            for each_group in [ temp_block_group ]:
                ## the one nested bone this block needs, if any, and the cubes
                ## that went into it and so must not be drawn in the slice too
                nested_group = None
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
                    
                    if( isOnlyRotatedCube ):
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
                        if nested_group is None:
                            nested_group =  { "parent": each_group["name"], "name": each_group["name"] + "___" + ghost_block_coordinates }

                            for primitiveKey in [ "mirror", "inflate", "debug", "render_group_id", "binding" ]:
                                if primitiveKey in each_group.keys():
                                    nested_group[primitiveKey] = each_group[primitiveKey]

                            for objectKey in [ "pivot", "rotation", "locators", "poly_mesh", "texture_meshes" ]:
                                if objectKey in each_group.keys():
                                    nested_group[objectKey] = copy.deepcopy( each_group[objectKey] )

                            nested_group["cubes"] = []
                            copied_groups.append( nested_group )
                        nested_group["cubes"].append( each_cube )
                        nested_cubes.add( id( each_cube ) )
                
                ## next each_cube
                
                
                ## A cube that went into a nested bone is drawn there. Leaving it
                ## in the slice as well draws it twice, once turned and once not,
                ## which is two ghost blocks in one place.
                kept = [each_cube for each_cube in temp_block_group["cubes"]
                        if id(each_cube) not in nested_cubes]

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

                for newChildGroup in copied_groups:
                    self.blocks[newChildGroup["name"]] = newChildGroup
            

    def save_uv(self, name):
        # writes the assembled UV sheet to the given path
        if self.uv_array is None:
            print("No Blocks Were found")
        else:
            im = Image.fromarray(self.uv_array)
            im.save(name)

    def stand_init(self):
        # helper function to initialize the dictionary that will be exported as the json object
        self.stand["format_version"] = "1.16.0"
        self.geometry["description"] = {
            "identifier": "geometry.armor_stand.ghost_blocks_{}".format(self.name)}
        self.geometry["description"]["texture_width"] = 1
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
        ## is better off reading the tile than reading nothing.
        across, down = window
        if impt.shape[0] < down + 16 or impt.shape[1] < across + 16:
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
        if type(self.uv_array) is type(None):
            self.uv_array = image_array
        else:
            startshape = list(self.uv_array.shape)
            endshape = startshape.copy()
            endshape[0] += image_array.shape[0]
            temp_new = zeros(endshape, uint8)
            temp_new[0:startshape[0], :, :] = self.uv_array
            temp_new[startshape[0]:, :, :] = image_array
            self.uv_array = temp_new

    def block_name_to_uv(self, block_name, variant = "",shape_variant="default",index=0,data=0,tint=None):
        
        # helper function maps the section of the uv file to the side of the block
        temp_uv = {}
        if block_name not in self.excluded:  # if you dont want a block to be rendered, exclude the UV

            block_type = self.defs[block_name]
            
            texture_files = self.get_block_texture_paths(block_name, variant = variant)

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
                ## a texture that asks for a tint takes this block's own colour,
                ## so every colour lands in the atlas as a tile of its own
                texture_files[key] = tinted(texture_files[key], tint)
                if texture_files[key] not in self.uv_map.keys():
                    try:
                        source, window = split_window(texture_files[key])
                        _named, colour = split_tint(texture_files[key])
                        _named, turn = split_turn(texture_files[key])
                        self.extend_uv_image(
                            "{}/{}.png".format(self.ref_resource_pack, source),
                            window, colour, turn)
                        self.uv_map[texture_files[key]] = len(self.uv_map.keys())
                    except Exception as e:
                        raise RuntimeError("Failed to load texture {}".format(texture_files[key]))
                temp_uv[key] = {
                    "uv": [0, self.uv_map[texture_files[key]]], "uv_size": [1, 1]}

        return temp_uv

    def add_blocks_to_bones(self):
        # Moves every collected block group into the geometry's bone list. Called
        # during the writing step, once every block has been made. A slice is
        # already one bone; the rest are the nested bones a turned block needs,
        # one per block.
        for key in self.blocks.keys():
            self.geometry["bones"].append(self.blocks[key])

    def get_block_texture_paths(self, blockName, variant = ""):
        # helper function for getting the texture locations from the vanilla files.
        texture_layout = self.blocks_def[blockName]["textures"]
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
                index=0
                if variant[0] in self.block_variants.keys():
                    ## A table is keyed by strings. A state that names a number
                    ## arrives as an nbtlib Int, whose str() is "Int(0)" rather
                    ## than "0", so it is converted rather than printed.
                    choices = self.block_variants[variant[0]]
                    index = choices.get(variant[1])
                    if index is None:
                        try:
                            index = choices.get(str(int(variant[1])))
                        except (TypeError, ValueError):
                            index = choices.get(str(variant[1]))
                    if index is None:
                        raise KeyError(variant[1])
                ## One variant index reads every face, and the faces do not
                ## have to name lists of the same length: a double plant's
                ## sides name two textures, the sunflower's front and back,
                ## while its halves name six, one per plant. A face with no
                ## entry that far along takes its last one rather than dropping
                ## the block.
                choices_for_face = texturedata[textures[key]]["textures"]
                textures[key] = choices_for_face[min(index, len(choices_for_face) - 1)]

            
        return textures
