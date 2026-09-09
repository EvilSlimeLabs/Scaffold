import hashlib
import json
import os
import shutil
import tempfile
import time
from shutil import copyfile

import nbtlib.nbt

from scaffold.pack import animation_class
from scaffold.pack import armor_stand_class
from scaffold.pack import armor_stand_geo_class as asgc
from scaffold.pack import big_render_controller as brc
from scaffold.pack import manifest
from scaffold.pack import render_controller_class as rcc
from scaffold import paths
from scaffold.pack import structure_reader
from scaffold.pack import tech_pack
from scaffold import block_list
from scaffold import version
debug=False

## Which field of a block entity names the form its block takes. A block entity
## carries a great deal that has nothing to do with how a block looks, such as a
## chest's contents or a sign's text, so only the fields named here are read.
ENTITY_SHAPES = {"CopperGolemStatue": "Pose", "Banner": "Base"}

## Which field of a block entity names a form outright, in place of the one its
## `ENTITY_SHAPES` field chose. An ominous banner is not a colour: it is a
## banner the game draws from a sheet of its own, and `Type` is what says so. A
## banner carrying `Patterns` is the same case from the other end, because a
## ghost block cannot composite six patterns and their colours as a pack is
## built, so it is drawn with a mark of Scaffold's own instead.
##
## A field mapped to a dict is read for its value; one mapped to a string only
## has to be there and say something. The first that answers wins.
ENTITY_INSTEAD = {"Banner": (("Type", {"1": "illager"}),
                             ("Patterns", "designed"))}

## Which field of a block entity names something that goes *with* the block's
## own shape state rather than instead of it. A bed keeps its colour beside the
## block and which half it is in its states, and the shape wants both, so the
## two are joined the way two shape states are.
ENTITY_ADDS = {"Bed": "color"}

## Which field of a block entity holds a colour of its own rather than one of a
## list. A dyed cauldron keeps a whole RGB, which no lookup table could carry a
## texture for, so the colour is handed to the geometry builder and the tile is
## tinted as the pack is built.
ENTITY_TINTS = {"Cauldron": "CustomColor"}

## Which field of a block entity holds another whole block. A flower pot keeps
## whatever is planted in it beside the block rather than in its states, as a
## block with a name and states of its own, so the plant is drawn as a second
## block in the same place and by its own family. That is what makes every
## pottable plant work without a variant apiece.
ENTITY_HOLDS = {"FlowerPot": "PlantBlock"}

## Which field turns its block, for the blocks whose states do not say. A head
## standing on the floor can face any of sixteen ways and keeps that in the
## block entity, the way a sign keeps its text; the states carry only which of
## the six faces it is fixed to. The number beside the field is the facing that
## means "standing on the floor", because a head on a wall is turned by the wall
## it is on and the entity reads zero.
ENTITY_ROTATIONS = {"Skull": ("Rotation", 1)}

## a head turns in sixteen steps, the same as a sign
SPIN_STEP = 22.5

PACK_SUFFIX = ".mcpack"


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

with open(paths.lookup("nbt_defs.json")) as f:
    nbt_def = json.load(f)
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
        self.all_blocks={}
        self.icon=paths.lookup("pack_icon.png")
        self.dead_blocks={}
        self.description=""
        self.tech_pack=tech_pack.NONE
        self._tech_pack_merged=False
        ## full detail unless asked otherwise; see set_low_geometry
        self.low_geometry=False
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
        self.structure_files[""]={}
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
        held = ENTITY_HOLDS.get(str(entity.get("id","")) if entity else "")
        if held is not None and held in entity:
            inside = entity[held]
            name = inside.get("name") if hasattr(inside,"get") else None
            if name:
                drawn.append(({"name": str(name),
                               "states": inside.get("states", {})}, {}))
        return drawn

    def _add_blocks_to_geo(self,struct2make,model_name,export_big=False):
        [xlen, ylen, zlen] = struct2make.get_size()
        if export_big:
            self.structure_files[model_name]['offsets'][0]-=xlen.item()+7
            self.structure_files[model_name]['offsets'][2]-=zlen.item()+7
        armorstand = asgc.ArmorStandGeo(model_name,alpha = self.opacity, size=[xlen, ylen, zlen], offsets=self.structure_files[model_name]['offsets'], low_geometry=self.low_geometry)

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
                    entity=struct2make.get_block_entity(x, y, z)
                ## one position may draw more than one block: a filled flower
                ## pot is the pot and whatever is planted in it
                for drawn, beside in self._drawn_at(block, entity):
                    blk_name=drawn["name"].replace("minecraft:", "")
                    blockProp=self._process_block(drawn, beside)
                    rot = blockProp[0]
                    top = blockProp[1]
                    variant = blockProp[2]
                    open_bit = blockProp[3]
                    data = blockProp[4]
                    hinge = blockProp[5]
                    tint = blockProp[6]
                    if debug:
                        armorstand.make_block(x, y, z, blk_name, rot = rot, top = top,variant = variant, trap_open=open_bit, data=data, hinge=hinge, big = export_big, tint=tint)
                    else:
                        try:
                            armorstand.make_block(x, y, z, blk_name, rot = rot, top = top,variant = variant, trap_open=open_bit, data=data, hinge=hinge, big = export_big, tint=tint)
                        except Exception as e:
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
            ## consider temp file
        if export_big:
            armorstand.export_big(self.work_dir)
            self.animation.export_big(self.work_dir,self.big_offset)
        else:
            armorstand.export(self.work_dir)
            self.animation.export(self.work_dir)
        return struct2make.get_block_list()
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
                 "big=" + (",".join(str(v) for v in self.big_offset)
                           if getattr(self, "big_offset", None) else "off")]
        for name in sorted(self.structure_files):
            info = self.structure_files[name]
            offsets = info.get("offsets") or [0, 0, 0]
            parts.append("model=%s|%s|%s" % (
                name, self._digest(info["file"]),
                ",".join(str(v) for v in offsets)))
        return "\n".join(parts)

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
                        fingerprint=self.fingerprint())
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
    def _process_block(self,block,entity=None):
        shape_states = []
        tint = None
        rot = None
        top = False
        open_bit = False
        hinge = False
        data=0
        variant="default"
        for key in nbt_def.keys():
            if nbt_def[key]== "variant" and key in block["states"].keys():
                variant = [key,block["states"][key]]
            if nbt_def[key] == "rot" and key in block["states"].keys():
                try:
                    rot = int(block["states"][key])
                except (TypeError, ValueError):
                    rot = str(block["states"][key])
                
            if nbt_def[key]== "top" and key in block["states"].keys():
                top_state = block["states"][key]
                if key == "minecraft:vertical_half":
                    top = str(top_state).lower() == "top"
                else:
                    top = bool(top_state)
            if nbt_def[key]== "open_bit" and "open_bit" in block["states"].keys():
                open_bit = bool(block["states"][key])
            if nbt_def[key]== "hinge" and key in block["states"].keys():
                hinge = bool(block["states"][key])
            if nbt_def[key]== "data" and key in block["states"].keys():
                data = int(block["states"][key])
            if nbt_def[key]== "shape" and key in block["states"].keys():
                ## A state that names one of a block's forms rather than a
                ## number: which way a bell is mounted, whether a campfire is
                ## burning. Several of them on one block are joined in the order
                ## the states are named, so "0-1" always means the same pair.
                shape_states.append((key, _plain(block["states"][key])))
            if key == "rail_direction" and key in block["states"].keys():
                data = str(block["states"][key].as_unsigned)
                if "rail_data_bit" in block["states"].keys():
                    data += "-"+str(block["states"]["rail_data_bit"].as_unsigned)

        ## the shape a state asks for outranks a plain number, since a block
        ## carrying one is not described by its default form
        if shape_states:
            data = "-".join(value for _key, value in sorted(shape_states))

        ## A block carrying two rotation states is turned by only one of them.
        ## A hanging sign has both, and which one applies is attached_bit: a
        ## sign fixed to the underside of a block turns in sixteen steps with
        ## ground_sign_direction, and one swinging from a chain or hung on a
        ## wall turns with facing_direction, the other reading zero. The
        ## block_rotation entries for those forms scope the four values to them,
        ## since 2 means something different in each numbering.
        states = block["states"]
        if ("ground_sign_direction" in states.keys()
                and "facing_direction" in states.keys()
                and not bool(states.get("attached_bit", 0))):
            rot = int(states["facing_direction"])

        ## and what the block entity says outranks both: it is the only record
        ## of the pose a statue was placed in, of a banner's colour, and of the
        ## way a head standing on the floor is turned
        if entity:
            marker = ENTITY_SHAPES.get(str(entity.get("id","")))
            if marker is not None and marker in entity:
                data = _plain(entity[marker])
            joined = ENTITY_ADDS.get(str(entity.get("id","")))
            if joined is not None and joined in entity:
                data = "{}-{}".format(data, _plain(entity[joined]))
            ## and a field that names a form outright replaces whatever the
            ## one above chose. A banner that is ominous or carries patterns is
            ## not any of the sixteen dyes.
            for marker, named in ENTITY_INSTEAD.get(
                    str(entity.get("id", "")), ()):
                if marker not in entity:
                    continue
                held = entity[marker]
                if isinstance(named, dict):
                    form = named.get(_plain(held))
                elif len(held) if hasattr(held, "__len__") else held:
                    form = named
                else:
                    form = None
                if form is not None:
                    data = form
                    break
            ## A cauldron's water may be dyed, and the dye is a whole colour in
            ## the block entity rather than a state of its own, so the block
            ## says only "water". The form becomes `dyed`, whose liquid asks for
            ## a tint, and the colour itself is handed on: Scaffold builds the
            ## pack, so the tile is tinted on the way into the atlas and every
            ## colour in a structure lands there as a tile of its own.
            marker = ENTITY_TINTS.get(str(entity.get("id","")))
            if marker is not None and marker in entity:
                tint = int(entity[marker])
                if str(data).startswith("water-"):
                    data = "dyed" + str(data)[len("water"):]
            spin = ENTITY_ROTATIONS.get(str(entity.get("id","")))
            if spin is not None and spin[0] in entity and rot == spin[1]:
                try:
                    ## named apart from the facings, which are numbers too: a
                    ## head fixed to the north wall reads 2, and so would the
                    ## second of sixteen steps round
                    step = int(round(float(entity[spin[0]]) / SPIN_STEP)) % 16
                    rot = "spin%d" % step
                except (TypeError, ValueError):
                    pass

        if "wood_type" in block["states"].keys():
            variant = ["wood_type",block["states"]["wood_type"]]
            if block["name"] == "minecraft:wood":
                keys = block["states"]["wood_type"]
                if bool(block["states"]["stripped_bit"]):
                    keys+="_stripped"
                variant = ["wood",keys]
        return [rot, top, variant, open_bit, data, hinge, tint]
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
