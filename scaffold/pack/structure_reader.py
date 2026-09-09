import nbtlib

from scaffold import paths
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
class StructureFile:
    def __init__(self, file):
        global loaded
        with open(paths.lookup("nbt_defs.json")) as nbt_file:
            self.nbt_defs=json.load(nbt_file)
            
        if type(file) is dict:
            self.NBTfile = file
        else:
            self.NBTfile = nbtlib.load(file, byteorder='little')
        loaded=self.NBTfile
        
        if "" in self.NBTfile.keys():
            self.NBTfile=self.NBTfile[""]

        self.blocks = list(map(int, self.NBTfile["structure"]["block_indices"][0]))
        self.size = list(map(int, self.NBTfile["size"]))
        self.palette = self.NBTfile["structure"]["palette"]["default"]["block_palette"]
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

    def get_block_entity(self, x, y, z):
        """The block entity stored at a position, or an empty mapping.

        The indices run x outermost, the same order the block list is stored in.
        """
        flat=(x*self.size[1]+y)*self.size[2]+z
        return self.block_entities.get(flat,{})

    def get_block(self, x, y, z):
        index = self.cube[x, y, z]
        return self.palette[int(index)]

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
                for state in block["states"].keys():
                    if self.nbt_defs.get(state) == "variant":
                        variant=str(block["states"][state])
                if variant:
                    name="%s/%s" % (name, variant)
                if name not in block_counter.keys():
                    block_counter[name]=0
                
                block_counter[name]+=count_nonzero(block_array==i)
            
        return block_counter
class CombinedStructures:
    def __init__(self,file_list,exclude_list=[]):
        ## through paths, like every other data read: these were relative, so a
        ## big build only worked with the checkout as the working directory
        with open(paths.lookup("nbt_defs.json")) as nbt_file:
            self.nbt_defs=json.load(nbt_file)
        self.structs={}
        self.maxs = array([-2147483647,-2147483647,-2147483647],dtype=int32)
        self.mins = array([2147483647,2147483647,2147483647],dtype=int32)
        palette_size=0
        self.palette=[{"name":"minecraft:air","states":[],"version":"17959425"}]
        
        for file in file_list:
            self.structs[file] = {}
            self.structs[file]["nbt"] = nbtlib.load(file, byteorder='little')
            if "" in self.structs[file]["nbt"].keys():
                self.structs[file]["nbt"] = self.NBTfile[""]
            
            self.structs[file]["blocks"] = array(list(map(int, self.structs[file]["nbt"]["structure"]["block_indices"][0])))
            
            self.structs[file]["size"] = array(list(map(int, self.structs[file]["nbt"]["size"])))
            self.structs[file]["palette"] = self.structs[file]["nbt"]["structure"]["palette"]["default"]["block_palette"]
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
            
            self.palette += self.structs[file]["palette"]
        self.size = self.maxs-self.mins
        self.blocks = zeros(self.size, int)
        for file in file_list:
            embed(self.structs[file]["blocks"],self.blocks,self.structs[file]["mins"]-self.mins)
        self.blocks = flip(self.blocks,0)
        self.blocks = flip(self.blocks,2)
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
                for state in block["states"].keys():
                    if self.nbt_defs.get(state) == "variant":
                        variant=str(block["states"][state])
                if variant:
                    name="%s/%s" % (name, variant)
                if name not in block_counter.keys():
                    block_counter[name]=0
                
                block_counter[name]+=count_nonzero(block_array==i)
        return block_counter
        
    
