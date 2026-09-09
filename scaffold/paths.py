"""Where Scaffold's data lives, however Scaffold was installed.

`lookups/`, `Vanilla_Resource_Pack/`, `fonts/` and `images/` sit **inside** the
package, beside the code that opens them. That is what makes the project
installable: setuptools ships package data only from under the package
directory, so a `pip install` of a project that kept them at the repository root
would install a program with no tables and no textures.

Three ways the program can be running, and this handles all of them:

  * installed with pip, or run from a checkout, where the data is beside this
    file
  * compiled by Nuitka, where those same directories are packed into the
    executable under the package they came from and unpacked, at run time,
    into a private folder. Because the layout is kept, the data is beside this
    file there too, and nothing has to know it is inside a bundle.
  * compiled, with a copy dropped beside the executable, which **wins**,
    because a bundle is read only and this is how somebody hand-editing a
    lookup table makes it take effect without rebuilding. `docs/Editing
    Blocks.md` covers it.

The search order is therefore beside the executable, then the package itself.

**`sys.executable` is not the way to find the executable.** A onefile build
unpacks itself into a temporary folder and runs from there, so `sys.executable`
and `__file__` both point inside that folder rather than at the file the user
double-clicked. Nuitka gives the real one as `__compiled__.containing_dir`, and
`sys.argv[0]` is the fallback for anything that does not define it.
"""
import os
import sys

## the directories that make up Scaffold's data
DATA_DIRS = ("lookups", "Vanilla_Resource_Pack", "fonts", "images", "trust")

## the package, which is where the data is unless something nearer has it. In a
## compiled build this is the unpacked copy, because the package layout is kept.
_PACKAGE = os.path.dirname(os.path.abspath(__file__))

## Nuitka defines this in every module it compiles, and nothing else does, so
## its presence is what tells a release build from a checkout. `sys.frozen` is
## still honoured for anything that sets it.
_COMPILED = "__compiled__" in globals()


def frozen():
    """Whether this is a compiled release rather than a checkout or a pip install."""
    return _COMPILED or getattr(sys, "frozen", False)


def executable():
    """The file the user actually launched.

    Not `sys.executable`: a onefile build unpacks itself and runs the copy, so
    that names a file in a temporary folder that will be gone by morning.
    """
    containing = getattr(globals().get("__compiled__"), "containing_dir", None)
    if containing:
        return os.path.join(containing, os.path.basename(sys.argv[0]))
    if frozen():
        return os.path.abspath(sys.argv[0] or sys.executable)
    return sys.executable


def beside_executable():
    """The folder to write into, and the one an override is read from.

    Beside the executable when frozen; the package itself otherwise, since that
    is the only place a source or pip install has to put anything.
    """
    if frozen():
        return os.path.dirname(executable())
    return _PACKAGE


def roots():
    """Every place data might be, best first."""
    found = [beside_executable()]
    if _PACKAGE not in found:
        found.append(_PACKAGE)
    return found


def data(*parts):
    """The path to a data file, wherever it actually is.

    Falls back to the writable location when nothing exists yet, so a caller
    that is creating the file puts it somewhere sensible and an error message
    names a path a person can act on.
    """
    relative = os.path.join(*parts)
    for root in roots():
        candidate = os.path.join(root, relative)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(beside_executable(), relative)


def writable(*parts):
    """Where a file should be written: always beside the executable."""
    return os.path.join(beside_executable(), *parts)


def vanilla_pack():
    """The trimmed vanilla resource pack the generator reads textures from."""
    return data("Vanilla_Resource_Pack")


def lookup(name):
    return data("lookups", name)


def documents():
    """The user's Documents folder, or the closest thing this platform has.

    Windows keeps it under the user profile and can have it redirected, so the
    shell is asked before falling back to the obvious path. Elsewhere there is
    no strong convention, and the home directory is the honest answer.
    """
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ## CSIDL_PERSONAL = 5, SHGFP_TYPE_CURRENT = 0
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
                if buffer.value:
                    return buffer.value
        except Exception:
            pass
        return os.path.join(home, "Documents")
    if sys.platform == "darwin":
        return os.path.join(home, "Documents")
    ## Linux: honour the XDG documents directory when the user has one
    xdg = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg and os.path.isdir(os.path.expandvars(xdg)):
        return os.path.expandvars(xdg)
    candidate = os.path.join(home, "Documents")
    return candidate if os.path.isdir(candidate) else home


def default_output_dir():
    """Where finished packs go unless the user picks somewhere else."""
    return os.path.join(documents(), "Scaffold Builds")
