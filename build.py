"""Local release build.

Runs the data-generation tools (to rebuild lookup tables and assets), the tests,
freezes both entry points with PyInstaller (`structura/__main__.py` through
structura.spec and `structura/cli/__main__.py` through structura_cli.spec) and
writes the release: a **single self-contained executable**, a console twin of
it for scripts, a zip of both for places that will not carry a bare .exe, and a
`SHA256SUMS.txt` covering all three. Nothing has to be extracted alongside
either executable. The lookup tables, the vanilla pack and the TechPack assets
are all inside.

**Upload SHA256SUMS.txt with the release.** Structura checks a download against
the fingerprint published beside it and refuses to install a build it cannot
check, so a release uploaded without that file cannot be taken by the updater.

    python build.py                    full build with tools and tests
    python build.py --skip-tools       freeze and package without regenerating data
    python build.py --skip-tests       run tools and freeze without running tests
    python build.py --skip-freeze      repackage the executable already in dist/

The version comes from pyproject.toml, which is packed into the executable so
the frozen program can read it back.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

from structura import paths
from structura import version
ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
SPEC = os.path.join(ROOT, "structura.spec")
CLI_SPEC = os.path.join(ROOT, "structura_cli.spec")
EXE_NAME = "Structura.exe" if os.name == "nt" else "Structura"
CLI_NAME = "Structura-cli.exe" if os.name == "nt" else "Structura-cli"

## What travels beside the executable in the release zip. Everything the
## program reads is packed *inside* it, as structura.spec lays out, so this is
## only the paperwork.
LOOSE_FILES = ["LICENSE", "README.md"]

## The asset Structura reads before it replaces itself. updates.SUMS is the
## same name from the other end; the two have to agree.
SUMS_NAME = "SHA256SUMS.txt"


def run(cmd, what):
    print("\n>> %s" % what)
    print("   " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit("\nBuild stopped: %s failed (exit %d)" % (what, result.returncode))


def run_tools():
    """Regenerate all lookup tables and assets from source data."""
    tools = [
        ("tools/make_block_forms.py", "mounted forms, fire and shelf"),
        ("tools/make_growth_forms.py", "crops, eggs, compost, coral"),
        ("tools/make_cross_forms.py", "fire, dripstone and sulfur spikes"),
        ("tools/make_furniture_forms.py", "beds, lecterns, conduits"),
        ("tools/make_head_forms.py", "mob heads"),
        ("tools/make_container_forms.py", "shulker boxes and banners"),
        ("tools/make_bed_textures.py", "the sixteen recoloured beds"),
        ("tools/make_string_texture.py", "the string tile"),
        ("tools/make_bookshelf.py", "the bookshelf's 64 states"),
        ("tools/make_statue_poses.py", "the copper golem's four models"),
        ("tools/fix_problem_blocks.py", "blocks with custom geometry"),
        ("tools/make_banner_textures.py", "the dyed banners"),
        ("tools/make_low_geometry.py", "the simplified shapes"),
        ("tools/make_icon.py", "both icons"),
        ("tools/make_fonts.py", "the bundled typefaces"),
        ("tools/make_special_languages.py", "the five generated languages"),
    ]
    for tool_path, description in tools:
        tool = os.path.join(ROOT, tool_path)
        if os.path.isfile(tool):
            run([sys.executable, tool], description)


def run_tests():
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
        "unit tests")


def freeze():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("Build stopped: PyInstaller is not installed.\n"
                 '  python -m pip install -e ".[dev]"')
    for path in (BUILD, DIST):
        if os.path.isdir(path):
            shutil.rmtree(path)
    run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC],
        "PyInstaller: the window")
    exe = os.path.join(DIST, EXE_NAME)
    if not os.path.isfile(exe):
        sys.exit("Build stopped: PyInstaller produced no %s" % EXE_NAME)

    ## the same pipeline with no interface, for scripts and batch jobs
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", CLI_SPEC],
        "PyInstaller: the command line build")
    cli = os.path.join(DIST, CLI_NAME)
    if not os.path.isfile(cli):
        sys.exit("Build stopped: PyInstaller produced no %s" % CLI_NAME)
    return exe


def write_zip(zip_path, entries):
    """Sorted entries and a fixed timestamp, so the archive layout is stable
    between builds and a diff of two releases is about content, not ordering.
    The frozen executable itself is not byte-reproducible."""
    if os.path.isfile(zip_path):
        os.remove(zip_path)
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, arcname in sorted(entries, key=lambda e: e[1]):
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(source, "rb") as f:
                archive.writestr(info, f.read())
    return zip_path


def package(exe, release_version):
    """The release: the executable, and a zip of it.

    The executable is self-contained, so the zip exists only because some
    browsers and chat clients refuse a bare .exe download. Extracting it gives
    the program itself, not a folder that has to be kept together, which is the
    whole point of the self-contained packaging.

    The licence travels with the binary because it has to; nothing else does.
    """
    entries = [(exe, EXE_NAME)]
    cli = os.path.join(DIST, CLI_NAME)
    if os.path.isfile(cli):
        entries.append((cli, CLI_NAME))
    for name in LOOSE_FILES:
        path = os.path.join(ROOT, name)
        if os.path.isfile(path):
            entries.append((path, name))
        else:
            print("   warning: %s is missing and will not ship" % name)

    print("\n>> packaging the executable (%.1f MB) and %d loose files"
          % (os.path.getsize(exe) / 1024 / 1024, len(entries) - 1))
    return write_zip(os.path.join(DIST, "Structura-%s.zip" % release_version), entries)


def digest_of(path, block=1024 * 1024):
    """The SHA-256 of a file, read in pieces rather than held in memory."""
    running = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(block), b""):
            running.update(chunk)
    return running.hexdigest()


def write_sums(files):
    """Publish a fingerprint for everything the release carries.

    The format is what `sha256sum` itself writes, so the same file serves both
    readers: `sha256sum -c SHA256SUMS.txt` checks a hand download, and Structura
    reads it before replacing itself. A release uploaded without this file
    cannot be installed by the updater at all.
    """
    where = os.path.join(DIST, SUMS_NAME)
    with open(where, "w", encoding="utf-8", newline="\n") as file:
        for path in files:
            file.write("%s  %s\n" % (digest_of(path), os.path.basename(path)))
    return where


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-tools", action="store_true",
                        help="do not regenerate lookup tables and assets")
    parser.add_argument("--skip-tests", action="store_true",
                        help="do not run the unit tests first")
    parser.add_argument("--skip-freeze", action="store_true",
                        help="reuse the executable already in dist/")
    args = parser.parse_args()

    release_version = version.read()
    if release_version == version.FALLBACK:
        sys.exit("Build stopped: pyproject.toml declares no version")
    print("Structura %s" % release_version)

    if not args.skip_tools:
        run_tools()

    if not args.skip_tests:
        run_tests()

    if args.skip_freeze:
        exe = os.path.join(DIST, EXE_NAME)
        if not os.path.isfile(exe):
            sys.exit("Build stopped: --skip-freeze but dist/%s does not exist" % EXE_NAME)
    else:
        exe = freeze()

    zip_path = package(exe, release_version)

    shipped = [path for path in (exe, os.path.join(DIST, CLI_NAME), zip_path)
               if os.path.isfile(path)]
    sums = write_sums(shipped)

    print("\nBuilt %s" % os.path.relpath(exe, ROOT))
    print("      %s" % os.path.relpath(zip_path, ROOT))
    print("  %.1f MB zipped" % (os.path.getsize(zip_path) / 1024 / 1024))
    print("\n%s, to be uploaded with them:" % os.path.relpath(sums, ROOT))
    with open(sums, encoding="utf-8") as file:
        print("  " + "  ".join(file.read().splitlines(True)).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
