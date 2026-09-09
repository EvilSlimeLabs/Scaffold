"""Whether a newer Scaffold has been released, and putting it in place.

Updates go through **TUF**, The Update Framework, by way of `tufup`. What that
buys is the thing the old updater could not do: a release is *signed*, and this
program will not install one that is not.

**The difference is what a fingerprint proves.** Scaffold used to publish a
`SHA256SUMS.txt` beside each release and check the download against it. That
proves the file arrived whole. It does not prove where it came from, because the
fingerprint travels with the build it describes, over the same connection, from
whoever is answering. Anyone able to serve the download is able to serve the
fingerprint for it. TUF signs the metadata with keys that never go near the
server, so a release has to be signed by the project to be installed at all.

**The trusted root ships inside the program.** `scaffold/trust/root.json` is
the one thing that cannot be fetched, because it is what everything else is
checked against; it is compiled into the executable and copied out on first run.
Every other piece of metadata is fetched and verified against it.

Three moving parts, and they are all just files on a web server:

    <PAGES>/metadata/     timestamp, snapshot, targets and root, all signed
    <PAGES>/targets/      the archives themselves, one per release

**The repository has to be public.** The metadata and the archives are fetched
without credentials, so while the GitHub repository is private every check comes
back as "up to date", quietly, which is the same answer as no network.

**How an update is applied.** The archive is downloaded, verified, and unpacked
into a temporary folder; then a script is started that copies the new files over
the installed ones and starts the new build. The script runs in its own process
and keeps retrying, so the window can take its time shutting down: a running
executable cannot be written over on Windows, but one that is on its way out
will be free by the time the copy gets to it.

`tufup` is imported where it is used rather than at the top, so a checkout
without it still runs -- there is nothing to update from a checkout anyway.

Nothing here runs unless asked: `settings` decides whether the launch asks, and
the window's About dialog asks on demand.
"""
import os
import subprocess
import sys
import time

from scaffold import paths
from scaffold import version

APP_NAME = "Scaffold"
REPOSITORY = "EvilSlimeLabs/Scaffold"
RELEASES = "https://github.com/%s/releases" % REPOSITORY

## Where the signed metadata and the archives are served from. GitHub Pages,
## because a release asset's URL carries the tag it belongs to and so changes
## every release, and TUF needs one address that does not move.
PAGES = "https://evilslimelabs.github.io/Scaffold"
METADATA_URL = PAGES + "/metadata/"
TARGET_URL = PAGES + "/targets/"

## The root of trust, compiled into the executable. Everything else is fetched.
TRUST_DIR = "trust"
ROOT_METADATA = "root.json"

## Where the client keeps what it has verified and what it has downloaded. Not
## beside the executable: a program installed in Program Files cannot write
## there, and the update would fail for the people most likely to need it.
WORKING = ".scaffold-updates"

TIMEOUT = 10

## A build displaced by a *pre-tufup* update, which renamed the running file out
## of the way rather than copying over it. Nothing writes one any more; this is
## here so that a program updating from an older release still tidies up after
## it, and can go once nobody is running 3.0 or older.
DISPLACED = ".old"
PATIENCE = 5.0
STEP = 0.25
FILE_HIDDEN = 0x02
BAD_ATTRIBUTES = 0xFFFFFFFF
NO_WINDOW = 0x08000000

## The batch script tufup writes does not start the program again, and opens a
## console window to run in. This is its template with a line added and, below,
## the flag that keeps the console out of sight.
RESTART_SCRIPT = """@echo off
{log_lines}
echo Moving app files...
robocopy "{src_dir}" "{dst_dir}" {robocopy_options}
echo Starting {app_name}...
start "" "{launch}"
{delete_self}
"""


def running_file():
    """The executable this is running as, or None from a checkout."""
    return paths.executable() if paths.frozen() else None


def install_dir():
    """The folder the program is installed in."""
    return os.path.dirname(running_file() or sys.executable)


def working_dir(*parts):
    """Where the client keeps its metadata and its downloads."""
    return os.path.join(os.path.expanduser("~"), WORKING, *parts)


def trusted_root():
    """The root metadata shipped with the program."""
    return paths.data(TRUST_DIR, ROOT_METADATA)


def channel(running=None):
    """Which releases this build is willing to be offered.

    A final release is only ever offered a final release. A pre-release is
    offered its own kind as well, so that somebody running a release candidate
    keeps getting them rather than being told there is nothing new until the
    final ships.
    """
    running = running or version.read()
    for mark in ("a", "b", "rc"):
        if mark in _tail(running):
            return mark
    return None


def _tail(running):
    """Whatever follows the numbers in a version string."""
    for index, letter in enumerate(running):
        if letter.isalpha():
            return running[index:]
    return ""


def ready():
    """Whether an update could even be attempted."""
    if not running_file():
        return False
    try:
        import tufup.client                                    # noqa: F401
    except ImportError:
        return False
    return os.path.isfile(trusted_root())


def client(running=None):
    """A tufup client, with the trusted root in place for it to start from.

    The metadata directory is seeded from the copy compiled into the program the
    first time, and updated from the server after that. Handing it the shipped
    root every time would undo a root rotation, so it is only written when there
    is nothing there.

    `running` is the version to compare against, and defaults to this build's
    own. It is what a client is built with rather than something set afterwards,
    because tufup works out which archive it is holding at that moment; a
    diagnostic asking what an older release would be offered has to say so here.
    """
    from tufup.client import Client

    metadata = working_dir("metadata")
    targets = working_dir("targets")
    os.makedirs(metadata, exist_ok=True)
    os.makedirs(targets, exist_ok=True)
    here = os.path.join(metadata, ROOT_METADATA)
    if not os.path.isfile(here):
        import shutil

        shutil.copy(trusted_root(), here)

    import pathlib

    return Client(
        app_name=APP_NAME,
        app_install_dir=pathlib.Path(install_dir()),
        current_version=running or version.read(),
        metadata_dir=pathlib.Path(metadata),
        metadata_base_url=METADATA_URL,
        target_dir=pathlib.Path(targets),
        target_base_url=TARGET_URL,
    )


def available():
    """The version of a newer release, or None.

    Quiet about every way of failing. Somebody opening Scaffold to build a pack
    does not want to hear that an update check timed out, and the check runs on
    every launch.
    """
    if not ready():
        return None
    try:
        found = client().check_for_updates(pre=channel())
    except Exception:
        return None
    return str(found.version) if found else None


def install_latest(restart=True, report=None):
    """Take the newest release and put it in place.

    Returns None when it worked, and otherwise a (reason, detail) pair: the
    reason names one of the ways this goes wrong, for the caller to put in its
    own words, and the detail is whatever went wrong, or an empty string.

    `report` is called with the name of each stage as it begins, because
    verifying and downloading both take long enough to need saying.

    On success this returns rather than exiting, with the copy already started
    and waiting for this process to let go of its own executable. The caller
    leaves in its own order; robocopy keeps trying until it can.
    """
    def say(stage):
        if report:
            report(stage)

    if not running_file():
        return "update source", ""
    if not ready():
        return "update no release", ""

    say("update stage checking")
    try:
        talking_to = client()
        found = talking_to.check_for_updates(pre=channel())
    except Exception as complaint:
        return "update no release", str(complaint)
    if not found:
        return "update current", ""

    say("update stage downloading")
    try:
        talking_to.download_and_apply_update(
            skip_confirmation=True,
            install=_put_in_place,
            progress_hook=None)
    except Exception as complaint:
        ## tuf raises for a bad signature, a stale timestamp and a hash that
        ## does not match, and every one of them means the same thing here:
        ## what arrived is not a release this program will install
        return _blame(complaint), str(complaint)
    return None


## the ways tuf says no, and what each of them means to somebody looking at a
## window rather than a stack trace
def _blame(complaint):
    named = type(complaint).__name__
    if "Download" in named or "Connection" in named or "Timeout" in named:
        return "update download failed"
    if isinstance(complaint, OSError):
        return "update cannot place"
    return "update wrong fingerprint"


def _put_in_place(src_dir, dst_dir, **kwargs):
    """Copy the new build over the installed one, and start it.

    tufup ends this by exiting the process, which on the worker thread the
    window runs it on would end only the thread and leave the program running on
    the file being copied over. The exit is caught, so the window is told it
    worked and leaves in its own order; the script is already running by then
    and retries until the executable is free.
    """
    from tufup.utils import platform_specific

    extra = {}
    if os.name == "nt":
        extra = {
            "batch_template": RESTART_SCRIPT,
            "batch_template_extra_kwargs": {
                "app_name": APP_NAME,
                "launch": running_file() or "",
            },
            ## the copy is Scaffold's business, not something to open a console
            ## window in front of somebody for
            "process_creation_flags": NO_WINDOW,
        }
    try:
        platform_specific.install_update(
            src_dir=src_dir, dst_dir=dst_dir, purge_dst_dir=False,
            **dict(extra, **kwargs))
    except SystemExit:
        pass


# --- tidying up after the updater this replaced ------------------------------
#
# Scaffold used to update itself by renaming: the running file was moved to
# `Scaffold.exe.old`, the download was written where it stood, and the old file
# was hidden and cleared away by the next launch. Nothing writes one any more,
# but somebody updating from 3.0 or older arrives here with one on disk.


def keep_trying(call, patience=PATIENCE):
    """Ask again for a while. Windows refuses a file another process has open."""
    ends = time.time() + patience
    while True:
        try:
            return call()
        except OSError:
            if time.time() >= ends:
                raise
            time.sleep(STEP)


def hidden(path):
    """Whether a file carries the hidden attribute."""
    if os.name != "nt":
        return os.path.basename(path).startswith(".")
    import ctypes

    got = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    return got != BAD_ATTRIBUTES and bool(got & FILE_HIDDEN)


def clear_displaced(patience=0.0):
    """Take away the build a pre-tufup update left behind, if there is one.

    Returns True when there is nothing left to clear, which includes there never
    having been anything.
    """
    running = running_file()
    if not running:
        return True
    left = running + DISPLACED
    if not os.path.exists(left):
        return True
    try:
        keep_trying(lambda: os.remove(left), patience)
    except OSError:
        return False
    return True
