"""Scaffold's command line.

Everything the program does without a window: reading the arguments and building
a pack from them. Nothing here imports the
interface, and nothing here decides what to do when no build is asked for --
`main` reports that back and lets the caller answer it, because the two entry
points answer it differently. The build that carries the window opens one; the
command line build says it has none.

That split is what lets one executable be both. `scaffold.py` is the dual use
entry point: run it with arguments and it builds a pack in the terminal, run it
with none and the window opens. `cli/__main__.py` is the same command line with
the interface left out of the bundle entirely.
"""
import sys

from scaffold.cli import arguments
from scaffold.cli import commands
from scaffold.cli import console

## `main` returns this when the command line asked for no build. It is not an
## error and not a success: it means the caller has to decide.
NOTHING_ASKED = "nothing asked"


def main(argv=None):
    """Do what the arguments say, and report what happened.

    Returns a process exit code, or NOTHING_ASKED when there was nothing on the
    command line to act on.
    """
    ## before the arguments are read: argparse writes its help and its errors
    ## out, and a windowed build has nowhere to write until this is done
    console.attach()

    args = arguments.parse(argv)

    from scaffold import settings
    settings.load()

    if args.debug:
        commands.enable_debug()
    if args.structure and args.pack_name:
        commands.build(args)
        return 0
    return NOTHING_ASKED


NO_WINDOW = """This is the command line build of Scaffold; it has no window.
Give it something to build:

  scaffold-cli --structure build.mcstructure --pack_name "My Pack"

Run with --help for everything it accepts.
"""


def console_entry(argv=None):
    """The command line on its own, with no window to fall back to.

    What `scaffold-cli` and `Scaffold-cli.exe` both call. `scaffold`, which
    does have a window, is `scaffold.window_entry`.
    """
    outcome = main(argv)
    if outcome != NOTHING_ASKED:
        return outcome
    sys.stderr.write(NO_WINDOW)
    return 2
