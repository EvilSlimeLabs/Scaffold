"""The Scaffold version, from the one place it is written down.

`pyproject.toml` holds it, in `[project] version`, which is where PEP 621 says a
version lives and where every packaging tool looks for it. Nothing else declares
one.

Reading it back has to work three ways, because Scaffold runs three ways:

  * **from a checkout**: the file is right there, in the directory above the
    package
  * **compiled**: there is no distribution metadata, and `build.py` packs
    `pyproject.toml` into the executable in the same place relative to the
    package, so the same walk up finds it
  * **installed with pip**: the file is not installed, so the version comes
    from the installed distribution's metadata through `importlib.metadata`

**The file is asked first, and that order matters.** An editable install records
the version at install time and does not notice it changing, so a checkout that
asked its own metadata first would report the version of whenever `pip install
-e .` was last run. Bumping the version in `pyproject.toml` would then appear to
do nothing until the package was reinstalled, which is exactly the sort of thing
that ships a release labelled with the previous version's number. A real pip
install has no `pyproject.toml` beside the package, so it falls through to the
metadata and is unaffected.

`tomllib` is standard library from Python 3.11, which is what `requires-python`
asks for, so parsing costs no dependency.
"""
import os
import sys

FALLBACK = "0.0.0"
DISTRIBUTION = "scaffold"

_cached = None


def _from_metadata():
    """The version pip recorded at install time, if the package was installed."""
    try:
        from importlib import metadata

        return metadata.version(DISTRIBUTION)
    except Exception:
        return None


def _project_files():
    """Where pyproject.toml might be.

    One place answers both cases. In a checkout the file sits in the directory
    above the package, and a compiled build packs it in the same place relative
    to the package, so the same walk up finds it whether the package is a folder
    on disk or the copy a onefile build unpacked itself into.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.join(os.path.dirname(here), "pyproject.toml")


def _from_project_file():
    """The version out of pyproject.toml itself."""
    try:
        import tomllib
    except ImportError:                     # pragma: no cover - before 3.11
        return None
    for path in _project_files():
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as handle:
                found = tomllib.load(handle)["project"]["version"]
        except (OSError, KeyError, ValueError):
            continue
        if found:
            return found
    return None


def read():
    """The version string, or FALLBACK if it cannot be found at all.

    Answered once and remembered: it cannot change while the program runs, and
    it is asked for by the manifest, the credits line and the window title.
    """
    global _cached
    if _cached is None:
        _cached = _from_project_file() or _from_metadata() or FALLBACK
    return _cached


def as_tuple():
    """The version as the three-integer list a Bedrock manifest wants.

    Anything that is not a plain integer is dropped, and the result is padded
    or trimmed to three parts, so a pre-release suffix cannot break a build.
    """
    parts = []
    for part in read().split("."):
        digits = "".join(c for c in part if c.isdigit())
        parts.append(int(digits) if digits else 0)
    parts = (parts + [0, 0, 0])[:3]
    return parts


if __name__ == "__main__":
    print(read())
