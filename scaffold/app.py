"""Scaffold the way most people run it: arguments build, none opens a window.

This is the dual use entry point, the one the `scaffold` command and
`Scaffold.exe` both call. It is the only place that knows about both halves of
the program, which is why it is a module of its own rather than part of
`scaffold/__init__.py`. The command line has to import the package to reach
`scaffold.cli`, and anything the package's `__init__` mentions the command line
build would have to carry.
"""
from scaffold import cli


def window_entry(argv=None):
    """Build what the arguments asked for, or open the window if they asked for
    nothing.

    The window is imported inside the function, not at the top of this module,
    so that a caller only interested in building a pack does not pull
    CustomTkinter in behind it.
    """
    outcome = cli.main(argv)
    if outcome != cli.NOTHING_ASKED:
        return outcome

    from scaffold.ui import scaffold_gui

    scaffold_gui.run()
    return 0
