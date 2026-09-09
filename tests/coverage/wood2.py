import os

test_name = os.path.basename(__file__).split(".")[0]
structure = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "test_structures", "All Blocks World", "wood2.mcstructure"))
pack_name = "Test Wood2"
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
pack_file = os.path.join(root, "{}.mcpack".format(pack_name))
if os.path.isfile(pack_file):
    os.remove(pack_file)
os.chdir(root)

from scaffold.core import Scaffold

opacity = 20
offset = [0, 0, 0]

scaffold_base = Scaffold(pack_name)
scaffold_base.set_opacity(opacity)
scaffold_base.add_model("", structure)
scaffold_base.set_model_offset("", offset)
scaffold_base.generate_with_nametags()
scaffold_base.compile_pack()

unique_blocks = list(set(scaffold_base.unsupported_blocks))
total_count = scaffold_base.get_unique_blocks_count()
unsupported_count = len(unique_blocks)
coverage =  round((100 - (unsupported_count / total_count) * 100), 1)

print("Total Unique Blocks: %s" % total_count)
print("Total Unsupported Unique Blocks {}".format(unsupported_count))
print("Coverage of '{}' is {}% ".format(os.path.basename(structure),coverage))
for i in unique_blocks:
    print("\t",i.block["name"])
