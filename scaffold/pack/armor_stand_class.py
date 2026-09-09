import json
import os


class ArmorStand:
    def __init__(self):
        self.stand = {"format_version": "1.10.0"}
        self.stand["minecraft:client_entity"] = {}
        ##sorry about this dump... it is just copied over...
        desc={"identifier": "minecraft:armor_stand",
              "min_engine_version": "1.8.0",
              "materials": {
                  "default": "armor_stand",
                  "ghost_blocks": "entity_alphablend"
                  },
              "animations": {
                    "default_pose": "animation.armor_stand.default_pose",
                    "no_pose": "animation.armor_stand.no_pose",
                    "solemn_pose": "animation.armor_stand.solemn_pose",
                    "athena_pose": "animation.armor_stand.athena_pose",
                    "brandish_pose": "animation.armor_stand.brandish_pose",
                    "honor_pose": "animation.armor_stand.honor_pose",
                    "entertain_pose": "animation.armor_stand.entertain_pose",
                    "salute_pose": "animation.armor_stand.salute_pose",
                    "riposte_pose": "animation.armor_stand.riposte_pose",
                    "zombie_pose": "animation.armor_stand.zombie_pose",
                    "cancan_a_pose": "animation.armor_stand.cancan_a_pose",
                    "cancan_b_pose": "animation.armor_stand.cancan_b_pose",
                    "hero_pose": "animation.armor_stand.hero_pose",
                    "wiggle": "animation.armor_stand.wiggle",
                    "controller.pose": "controller.animation.armor_stand.pose",
                    "controller.wiggling": "controller.animation.armor_stand.wiggle"
                    #"scale": "animation.armor_stand.ghost_blocks.scale" 		
                  },
                        "scripts": {
                        "initialize": [
                            "variable.armor_stand.pose_index = 0;",
                            "variable.armor_stand.hurt_time = 0;"
                            ],
                        "animate": [
                              "controller.pose",
                              "controller.wiggling"#,
                              #"scale" 
                            ]
                  },
            "render_controllers": [
                    "controller.render.armor_stand",
                    "controller.render.armor_stand.ghost_blocks" 
                  ],
            "enable_attachables": True
            }
        self.stand["minecraft:client_entity"]["description"]=desc
        self.geos = {"default": "geometry.armor_stand.larger_render"}
        self.textures =  {"default": "textures/entity/armor_stand"}
    def add_model(self, name):
        prog_name = "ghost_blocks_{}".format(name.replace(" ","_").lower())
        self.geos[prog_name] = "geometry.armor_stand.{}".format(prog_name)
        self.textures[prog_name] = "textures/entity/{}".format(prog_name)
    def merge_description(self, extra):
        """Fold another pack's client entity description into this one.

        A client entity file in a resource pack replaces the vanilla one rather
        than merging with it, and between two packs only the higher in the
        player's list is read at all. A pack that wants both its own armor stand
        and somebody else's therefore has to carry both sets of declarations in
        one file; there is no ordering that combines them.

        Scaffold's own entries win every conflict. The ghost blocks are the
        point of the pack, and `geometry.default` in particular has to stay on
        the larger render bounds or the model stops drawing once the stand
        leaves the screen.
        """
        desc = self.stand["minecraft:client_entity"]["description"]

        for key in ("materials", "animations", "particle_effects"):
            merged = dict(extra.get(key, {}))
            merged.update(desc.get(key, {}))
            if merged:
                desc[key] = merged

        ## geometry and textures are not written into the description until
        ## export, which assigns both wholesale, so they are merged into the
        ## dictionaries export reads rather than into the description here
        for name, value in extra.get("geometry", {}).items():
            self.geos.setdefault(name, value)
        for name, value in extra.get("textures", {}).items():
            self.textures.setdefault(name, value)

        ## script order is what decides what runs over what. Scaffold's pose
        ## controller has to stay ahead of anything that reads the pose index.
        scripts = desc.setdefault("scripts", {})
        for key, value in extra.get("scripts", {}).items():
            if key not in scripts:
                scripts[key] = list(value) if isinstance(value, list) else value
            elif isinstance(value, list) and isinstance(scripts[key], list):
                for item in value:
                    if item not in scripts[key]:
                        scripts[key].append(item)

        controllers = list(desc.get("render_controllers", []))
        for item in extra.get("render_controllers", []):
            if item not in controllers:
                controllers.append(item)
        desc["render_controllers"] = controllers

    def add_scale(self):
        self.stand["minecraft:client_entity"]["description"]["animations"]["scale"] = "animation.armor_stand.ghost_blocks.scale"
        self.stand["minecraft:client_entity"]["description"]["scripts"]["animate"].append("scale")
    def export(self, pack_name):
        self.stand["minecraft:client_entity"]["description"]["textures"] = self.textures
        self.stand["minecraft:client_entity"]["description"]["geometry"] = self.geos

        path = "{}/entity/armor_stand.entity.json".format(pack_name)
        os.makedirs(os.path.dirname(path), exist_ok = True)
        
        with open(path, "w+") as json_file:
            json.dump(self.stand, json_file, indent=2)
    def export_big(self, pack_name):
        self.stand["minecraft:client_entity"]["description"]["textures"] = self.textures
        self.stand["minecraft:client_entity"]["description"]["geometry"] = self.geos

        path = "{}/entity/armor_stand.entity.json".format(pack_name)
        os.makedirs(os.path.dirname(path), exist_ok = True)
        
        with open(path, "w+") as json_file:
            json.dump(self.stand, json_file, indent=2)
    
