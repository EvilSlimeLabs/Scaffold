import io
import zlib

import nbtlib

from scaffold import block_geometry
from scaffold import paths
from scaffold import block_upgrade
from math import floor

from numpy import array, argwhere , int32, maximum, minimum, zeros, count_nonzero, flip
import json
loaded={}
def embed( small_array, big_array, loc):
    """Overwrites values in big_array starting at big_index with those in small_array"""
    xstart=loc[0]
    ystart=loc[1]
    zstart=loc[2]
    xstop=xstart+small_array.shape[0]
    ystop=ystart+small_array.shape[1]
    zstop=zstart+small_array.shape[2]
    big_array[xstart:xstop,ystart:ystop,zstart:zstop]=small_array
## what a version 2 file's `compression` tag says its structure compound is
UNCOMPRESSED = 0
ZLIB = 1


def load(path):
    """A structure file's root compound, its structure compound readable.

    Every reader of a .mcstructure goes through this, so none of them has to
    know whether the file was compressed.
    """
    return expanded(nbtlib.load(path, byteorder="little"))


def expanded(root):
    """The root compound with its `structure` compound decompressed.

    A version 2 file may carry a `compression` tag at its root: 0, or no tag at
    all, for none, and 1 for zlib. Compressed, the whole structure compound is
    serialized as little endian NBT, zlib compressed and stored as a byte array
    in its place, while the rest of the root -- the size, the origin, the
    format version -- stays as it is. The game writes compressed files from
    Minecraft 26.60.
    """
    if "" in root.keys():
        root = root[""]
    method = int(root.get("compression", UNCOMPRESSED))
    if method == UNCOMPRESSED or isinstance(root.get("structure"), nbtlib.Compound):
        return root
    if method != ZLIB:
        raise ValueError("unknown structure compression %d" % method)
    packed = bytes(root["structure"].astype("uint8"))
    inner = nbtlib.File.parse(io.BytesIO(zlib.decompress(packed)), byteorder="little")
    if "" in inner.keys():
        inner = inner[""]
    ## the serialized compound is the structure itself; one that arrives
    ## wrapped under its own name is unwrapped
    if "block_indices" not in inner and "structure" in inner:
        inner = inner["structure"]
    root["structure"] = nbtlib.Compound(inner)
    return root


class StructureFile:
    def __init__(self, file):
        global loaded
        ## tags already loaded, an nbtlib File or a plain dict, or a path
        if isinstance(file, dict):
            self.NBTfile = expanded(file)
        else:
            self.NBTfile = load(file)
        loaded=self.NBTfile

        ## block_indices is a list of layers, and the first is the one a
        ## ghost block is drawn from; the second carries waterlogging and
        ## is not read here. A version 1 file stores each layer as a list
        ## of Int tags and a version 2 file as a single IntArray, which is
        ## already a numpy array -- so this converts one and borrows the
        ## other, rather than walking either a value at a time.
        self.blocks = array(
            self.NBTfile["structure"]["block_indices"][0], dtype=int32)
        self.size = list(map(int, self.NBTfile["size"]))
        ## The second layer is what shares a cell with the block: the water a
        ## waterlogged block stands in. -1 is nothing.
        layers = self.NBTfile["structure"]["block_indices"]
        self.liquid = None
        if len(layers) > 1 and len(layers[1]) == len(self.blocks):
            self.liquid = array(layers[1], dtype=int32).reshape(self.size)
        ## every entry as the current game names it, so nothing after this
        ## point sees an old id or an old state; see block_upgrade
        self.palette = [block_upgrade.upgrade(entry) for entry in
                        self.NBTfile["structure"]["palette"]["default"]["block_palette"]]
        self.mins = array(list(map(int,self.NBTfile["structure_world_origin"])))
        self.maxs = self.mins + array(self.size)-1
        self.origin = array(list(map(int,self.NBTfile["structure_world_origin"])))
        ## Some of what a block looks like is not in its states at all. A copper
        ## golem statue keeps its pose in the block entity beside it, the way a
        ## sign keeps its text, so a structure holding four statues in four
        ## poses has one palette entry for all of them.
        self.block_entities={}
        entity_data=self.NBTfile["structure"]["palette"]["default"].get(
            "block_position_data")
        if entity_data:
            for index,body in dict(entity_data).items():
                fields=body.get("block_entity_data")
                if fields is not None:
                    self.block_entities[int(index)]=dict(fields)
        self.get_blockmap()
    def get_layer_blocks(self,y):
        lb=self.cube[:,y,:]
        return argwhere(lb > 0)
    def get_blockmap(self):
        index_of_air = 0
        for i in range(len(self.palette)):
            if self.palette[i]["name"] == "minecraft:air":
                index_of_air = i
                break
        self.cube = array(self.blocks)
        self.cube += 1
        self.palette = [{"name":"minecraft:air","states":[]}] + self.palette
        self.cube[self.cube==index_of_air+1]=0
        self.cube=self.cube.reshape(self.size)

    def get_entities(self):
        """Every entity in the structure, in the cell it stands in.

        An entity is kept apart from the blocks. `structure.entities` is a list
        of whole entity records rather than palette indices, so nothing in
        `block_indices` marks the cell one occupies and no amount of reading the
        palette would ever find it. That is why a cushion, which is an entity
        and not a block, needs this to be drawn at all.

        `Pos` is where the entity stands in the world, as floats, and
        `structure_world_origin` is where in the world the structure was taken
        from, so the cell is the difference with the fraction dropped. An entity
        standing outside the recorded box is left out rather than clamped to the
        edge: it is not part of what was captured, and a mark on the wrong cell
        is worse than no mark.

        **The fraction is kept, not dropped.** A snow layer is two pixels
        tall, so a cushion resting on one stands an eighth of a block above the
        floor of the cell it is in -- the same cell the snow is in, because a
        cell is a whole block. Rounding that away stacks the two ghosts inside
        each other. `lift` is how far above the cell floor the entity stands,
        in blocks, and whatever draws it puts it there.

        Returns a list of `{"id", "at", "lift", "yaw", "fields"}`, where `at`
        is the cell as (x, y, z) and `yaw` is the first of `Rotation`, in
        degrees.
        """
        found = []
        for entity in self.NBTfile["structure"].get("entities") or ():
            name = str(entity.get("identifier", ""))
            place = entity.get("Pos")
            if not name or place is None or len(place) < 3:
                continue
            exact = [float(place[i]) - int(self.origin[i]) for i in range(3)]
            at = [int(floor(n)) for n in exact]
            if any(n < 0 or n >= self.size[i] for i, n in enumerate(at)):
                continue
            spin = entity.get("Rotation") or ()
            found.append({"id": name, "at": tuple(at),
                          "lift": exact[1] - at[1],
                          "yaw": float(spin[0]) if len(spin) else 0.0,
                          "fields": dict(entity)})
        return found

    def get_block_entity(self, x, y, z):
        """The block entity stored at a position, or an empty mapping.

        The indices run x outermost, the same order the block list is stored in.
        """
        flat=(x*self.size[1]+y)*self.size[2]+z
        return self.block_entities.get(flat,{})

    def get_block(self, x, y, z):
        index = self.cube[x, y, z]
        return self.palette[int(index)]

    def get_liquid(self, x, y, z):
        """What shares a cell with the block there, the water a waterlogged
        block stands in, or None. The second layer indexes the palette as it
        was saved, before `get_blockmap` put air at its front."""
        if self.liquid is None:
            return None
        index = int(self.liquid[x, y, z])
        if index < 0:
            return None
        found = self.palette[index + 1]
        return None if found["name"] == "minecraft:air" else found

    def get_size(self):
        return self.size

    def get_block_list(self, ignored_blocks=["minecraft:air","minecraft:structure_block"]):
        block_counter = {}
        i=-2
        block_array=array(self.blocks)
        for block in self.palette:
            i+=1
            name=block["name"]
            if not(name in ignored_blocks):
                
                ## The id, with the variant on the end when the block has one.
                ## What a block is *called* is not settled here: the name and
                ## the heading it goes under both come out of block_list.json,
                ## which a user may replace, and a count already turned into a
                ## name cannot be regrouped or renamed afterwards.
                variant=None
                state=block_geometry.variant_state(name)
                if state is not None and state in block["states"].keys():
                    variant=str(block["states"][state])
                if variant:
                    name="%s/%s" % (name, variant)
                if name not in block_counter.keys():
                    block_counter[name]=0
                
                block_counter[name]+=count_nonzero(block_array==i)
            
        return block_counter
class CombinedStructures:
    def __init__(self,file_list,exclude_list=[]):
        self.structs={}
        self.maxs = array([-2147483647,-2147483647,-2147483647],dtype=int32)
        self.mins = array([2147483647,2147483647,2147483647],dtype=int32)
        palette_size=0
        self.palette=[{"name":"minecraft:air","states":[],"version":"17959425"}]
        
        for file in file_list:
            self.structs[file] = {}
            self.structs[file]["nbt"] = load(file)
            
            ## the first layer, as an array either way -- see StructureFile
            self.structs[file]["blocks"] = array(
                self.structs[file]["nbt"]["structure"]["block_indices"][0],
                dtype=int32)
            
            self.structs[file]["size"] = array(list(map(int, self.structs[file]["nbt"]["size"])))
            self.structs[file]["palette"] = [
                block_upgrade.upgrade(entry) for entry in
                self.structs[file]["nbt"]["structure"]["palette"]["default"]["block_palette"]]
            index_of_air = 0
            for i in range(len(self.structs[file]["palette"])):
                if self.structs[file]["palette"][i]["name"] == "minecraft:air":
                    index_of_air = i
            self.structs[file]["mins"] = array(list(map(int,self.structs[file]["nbt"]["structure_world_origin"])))
            self.structs[file]["maxs"] = self.structs[file]["mins"] + self.structs[file]["size"]
            self.maxs=maximum(self.maxs, self.structs[file]["maxs"])
            self.mins=minimum(self.mins, self.structs[file]["mins"])
            self.structs[file]["blocks"] = self.structs[file]["blocks"].reshape(self.structs[file]["size"])
            self.structs[file]["blocks"] = self.structs[file]["blocks"]+len(self.palette)
            self.structs[file]["blocks"][self.structs[file]["blocks"]==index_of_air+len(self.palette)]=0
            
            self.structs[file]["entities"] = (
                self.structs[file]["nbt"]["structure"].get("entities") or [])
            self.palette += self.structs[file]["palette"]
        self.size = self.maxs-self.mins
        self.blocks = zeros(self.size, int)
        for file in file_list:
            embed(self.structs[file]["blocks"],self.blocks,self.structs[file]["mins"]-self.mins)
        self.blocks = flip(self.blocks,0)
        self.blocks = flip(self.blocks,2)
    def get_entities(self):
        """Every entity in every structure, in the combined grid's own cells.

        **The same move the blocks make.** Each structure is embedded at its
        own corner and then the whole grid is flipped along x and along z, so
        an entity has to travel exactly that path or it lands somewhere its
        own building is not. The flip is applied here rather than reasoned
        about: `_combined_cell` is the one place that knows, and the blocks and
        the entities both go through it.

        **The yaw is not touched.** Flipping both x and z is a half turn about
        y, so it is tempting to turn every entity with it -- but a block's
        rotation state is handed to `make_block` unchanged in a big build too,
        and whatever the flip is compensating for it compensates for both. An
        entity turned here and a block not turned would face different ways in
        the same model, which is the one thing that must not happen.

        A big build had no entities at all before this, the way it still has no
        block entities.
        """
        found = []
        for file in self.structs:
            info = self.structs[file]
            corner = info["mins"] - self.mins
            for entity in info["entities"]:
                name = str(entity.get("identifier", ""))
                place = entity.get("Pos")
                if not name or place is None or len(place) < 3:
                    continue
                exact = [float(place[i]) - int(info["mins"][i]) + int(corner[i])
                         for i in range(3)]
                at, lift = self._combined_cell(exact)
                if at is None:
                    continue
                spin = entity.get("Rotation") or ()
                yaw = float(spin[0]) if len(spin) else 0.0
                found.append({"id": name, "at": at, "lift": lift,
                              "yaw": yaw, "fields": dict(entity)})
        return found

    def _combined_cell(self, exact):
        """A position in the assembled grid, as the cell and the lift.

        `exact` is already offset to the assembled grid but not yet flipped.
        Returns (None, 0.0) for anything outside it.
        """
        at = [int(floor(n)) for n in exact]
        if any(n < 0 or n >= int(self.size[i]) for i, n in enumerate(at)):
            return None, 0.0
        lift = exact[1] - at[1]
        ## the two flips the blocks get, so a cushion lands on its own building
        at[0] = int(self.size[0]) - 1 - at[0]
        at[2] = int(self.size[2]) - 1 - at[2]
        return tuple(at), lift

    def get_layer_blocks(self,y):
        lb=self.blocks[:,y,:]
        return argwhere(lb > 0)
    def get_block(self, x, y, z):
        index = self.blocks[x, y, z]
        return self.palette[int(index)]
    def get_size(self):
        return self.size
    def get_block_list(self, ignored_blocks=["minecraft:air"]):
        block_counter = {}
        i=0-2
        block_array=array(self.blocks)
        for i in range(len(self.palette)):
            block = self.palette[i]
            name=block["name"]
            if not(name in ignored_blocks):
                ## The id, with the variant on the end when the block has one.
                ## What a block is *called* is not settled here: the name and
                ## the heading it goes under both come out of block_list.json,
                ## which a user may replace, and a count already turned into a
                ## name cannot be regrouped or renamed afterwards.
                variant=None
                state=block_geometry.variant_state(name)
                if state is not None and state in block["states"].keys():
                    variant=str(block["states"][state])
                if variant:
                    name="%s/%s" % (name, variant)
                if name not in block_counter.keys():
                    block_counter[name]=0
                
                block_counter[name]+=count_nonzero(block_array==i)
        return block_counter
        
    
