"""Somewhere to print, in a build that was made for a window.

The build that carries the interface is frozen without a console, so that
double-clicking it opens the window and not a black rectangle behind it. On
Windows that also means it starts with no standard output at all: run it from a
terminal with arguments and every print, every line of `--help`, and every
argument error goes nowhere.

Windows will lend a windowed process the console of whatever launched it, which
is exactly what is wanted here, so output appears in the terminal that ran the
command and nothing appears when the program was double-clicked, because then
there is no console to attach to.

Everywhere else this does nothing, because a process already has its streams.
"""
import sys

## AttachConsole's argument for "the console of the process that started me"
PARENT = -1


def attach():
    """Point standard output at the terminal that launched this program.

    Safe to call more than once, safe when there is nothing to attach to, and
    safe on a build that already has a console. In each case it leaves the
    streams alone.
    """
    if not sys.platform.startswith("win"):
        return False
    ## a build made with a console already has working streams; asking a
    ## stream for its file descriptor is the reliable test, and some raise
    ## rather than answering
    try:
        if sys.stdout is not None and sys.stdout.fileno() >= 0:
            return False
    except (OSError, ValueError, AttributeError):
        pass
    return _borrow_parent_console()


def _borrow_parent_console():
    try:
        import ctypes

        if not ctypes.windll.kernel32.AttachConsole(PARENT):
            return False                     # launched from a shortcut or Explorer
    except Exception:
        return False

    for name in ("stdout", "stderr"):
        try:
            stream = open("CONOUT$", "w", buffering=1, encoding="utf-8",
                          errors="replace")
        except OSError:
            continue
        setattr(sys, name, stream)
    try:
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
    except OSError:
        pass
    return True
