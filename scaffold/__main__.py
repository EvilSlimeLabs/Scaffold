"""Scaffold: the window, and the command line, in one program.

Run it with a structure and a pack name and it builds a pack in the terminal.
Run it with nothing and the window opens.

    python -m scaffold --structure build.mcstructure --pack_name "My Pack"
    python -m scaffold

Installed with pip, the same thing is the `scaffold` command. The command line
itself lives in `scaffold/cli/`; the only thing decided here is what "nothing to
do" means, which for this build is "open the window".
"""
import sys

from scaffold.app import window_entry

if __name__ == "__main__":
    sys.exit(window_entry())
