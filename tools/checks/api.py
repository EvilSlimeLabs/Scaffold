"""Generate every kind of pack from the bundled test structures.

Exercises the nametag, big-build and multi-file paths in one go, with
core.debug on so an unsupported block raises instead of being
swallowed into the skipped list.

Run from anywhere; it works against the repository root.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import shutil
from scaffold import core
core.debug=True
big_hatter_files = ["test_structures/BigHatter/1.mcstructure","test_structures/BigHatter/1-1.mcstructure","test_structures/BigHatter/2.mcstructure","test_structures/BigHatter/3.mcstructure","test_structures/BigHatter/4.mcstructure"]
files_to_conver = {
        
        "gems":{"file":"test_structures/All Blocks World/gems and redstone.mcstructure",
                "offset":[-32,0,-32]},
        "stone":{"file":"test_structures/All Blocks World/Stones.mcstructure",
                 "offset":[-30,0,-32]},
        "wood":{"file":"test_structures/All Blocks World/wood.mcstructure",
                "offset":[-31,0,-31]},
        "decor":{"file":"test_structures/All Blocks World/decorative.mcstructure",
                 "offset":[-32,0,-31]},
        "wood2":{"file":"test_structures/All Blocks World/wood2.mcstructure",
                 "offset":[-32,0,-31]}}
shutil.rmtree("tmp/", ignore_errors=True)
if os.path.exists("tmp/big_hatter.mcpack"):
    os.remove("tmp/big_hatter.mcpack")
if os.path.exists("tmp/big_hatter Nametags.txt"):
    os.remove("tmp/big_hatter Nametags.txt")
if os.path.exists("tmp/all_blocks.mcpack"):
    os.remove("tmp/all_blocks.mcpack")
if os.path.exists("tmp/all_blocks Nametags.txt"):
    os.remove("tmp/all_blocks Nametags.txt")
if os.path.exists("tmp/bigBuild.mcpack"):
    os.remove("tmp/bigBuild.mcpack")
if os.path.exists("tmp/bigBuild Nametags.txt"):
    os.remove("tmp/bigBuild Nametags.txt")
scaffold_base=core.scaffold("tmp/all_blocks")

for name_tag, info in files_to_conver.items():
    print(f'{name_tag}, {info}')
    
    scaffold_base.add_model(name_tag,info["file"])
    scaffold_base.set_model_offset(name_tag,info["offset"])
scaffold_base.generate_nametag_file()
scaffold_base.generate_with_nametags()
print(scaffold_base.compile_pack())
print(scaffold_base.make_nametag_block_lists())

scaffold_base=core.scaffold("tmp/bigBuild")
for name_tag, info in files_to_conver.items():
    print(f'{name_tag}, {info}')
    scaffold_base.add_model(name_tag,info["file"])


scaffold_base.make_big_model([-132,-56,-65])
#print(scaffold_base.make_nametag_block_lists())
print(scaffold_base.compile_pack())

scaffold_base=core.scaffold("tmp/bigHatter")
for file in big_hatter_files:
    name_tag = file.split("/")[-1].replace(".mcstructure","")
    scaffold_base.add_model(name_tag,file)
print(scaffold_base.make_big_model([0,0,0]))
print(scaffold_base.compile_pack())
