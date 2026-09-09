"""Scaffold: a .mcstructure file, turned into a Bedrock resource pack.

    from scaffold import Scaffold

    pack = Scaffold("My Pack")
    pack.add_model("north wing", "wing.mcstructure")
    pack.set_model_offset("north wing", [0, 0, 0])
    pack.generate_with_nametags()
    print(pack.compile_pack())

`core` is the whole API and everything it produces is available as data as well
as as a file, because a service front end wants the former. The pieces beneath
it are grouped by what they are for: `pack` builds the resource pack, `cli` is
the command line, `ui` is the desktop window. None of those import each other,
and what more than one of them needs, meaning the settings, the paths and the
language tables, sits here beside them.

**Nothing here mentions the window.** The command line has to import this module
to reach `scaffold.cli`, so anything named here is something the command line
build would have to carry. The dual use entry point that chooses between building
a pack and opening a window lives in `scaffold/app.py` for that reason.
"""
from scaffold.core import Scaffold
from scaffold.version import read as _read_version

__version__ = _read_version()
__all__ = ["Scaffold", "__version__"]
