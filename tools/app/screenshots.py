"""Regenerate the window screenshots used by the README.

Screenshots of a program's own interface go stale the moment the interface
changes, and a stale screenshot is worse than none: it teaches a layout that is
not there any more. These are taken from the running window instead of by
hand, so a UI change plus one command brings the documentation back in step.

    python -m tools.app.screenshots

Writes into docs/. Needs a desktop session: the window is really opened, raised
and photographed, so this cannot run headless. The in-game screenshots beside
these are the ones only a person in a world can take.

It photographs a rectangle of the screen, which means anything that comes to the
front during the run lands in the documentation instead of the program. Every
grab therefore checks that the foreground window still belongs to this process
and refuses to save if it does not. A missing screenshot is recoverable; a
committed picture of somebody's browser is not. Leave the machine alone while it
runs.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import customtkinter as ctk
from PIL import ImageGrab

from scaffold import settings
from scaffold.ui import scaffold_gui

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs")

## a populated window says far more than an empty one
SAMPLE = [("north wing", "test_structures/stoneSlabs.mcstructure"),
          ("rail deck", "test_structures/rails.mcstructure"),
          ("canopy", "test_structures/tree.mcstructure")]


def foreground_is_ours():
    """Whether the window in front belongs to this process.

    Without this the tool will happily photograph whatever the user brought to
    the front while it was working.
    """
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes
        from ctypes import wintypes
        pid = wintypes.DWORD()
        handle = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:
        return True


def settle(window, seconds=1.0):
    """Pump the event loop so Tk finishes drawing before the grab."""
    end = time.time() + seconds
    while time.time() < end:
        window.update_idletasks()
        window.update()
        time.sleep(0.02)


def shoot(window, name, chrome=36, attempts=4):
    """Grab a window, including the title bar above it.

    Refuses to write anything if the window is not the one in front, and tries
    again rather than giving up on the first stolen focus.
    """
    for attempt in range(attempts):
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)
        window.focus_force()
        settle(window)
        if not foreground_is_ours():
            print("   %-28s something else is in front, retrying" % name)
            continue
        x, y = window.winfo_rootx(), window.winfo_rooty()
        w, h = window.winfo_width(), window.winfo_height()
        image = ImageGrab.grab((x, y - chrome, x + w, y + h))
        if not foreground_is_ours():
            print("   %-28s focus lost mid-grab, retrying" % name)
            continue
        path = os.path.join(DOCS, name)
        image.save(path)
        print("   %-28s %dx%d" % (name, *image.size))
        return path
    raise SystemExit(
        "Refusing to save %s: this window was never in front. Nothing was "
        "written over. Leave the machine alone and run it again." % name)


def populate(app):
    ## the window opens empty now, so every row here is one this adds
    for tag, path in SAMPLE:
        app.add_structure_row(path).tag_var.set(tag)
    app.pack_name_var.set("Sorter Hall")
    app.desc_var.set("floor 3 sorter")
    ## a custom icon, so the notched clear control is visible in the shot
    custom = os.path.join("images", "evilslimelabs-logo3.png")
    if os.path.isfile(custom):
        app.icon_path = os.path.abspath(custom)
        app.refresh_icon_preview()
    app.revalidate()


def main():
    os.makedirs(DOCS, exist_ok=True)
    print("writing screenshots into docs/")
    app = scaffold_gui.App()
    ## the documentation is in English whatever the machine taking it is set to,
    ## and the setting is put back afterwards
    was = settings.settings["lang"]
    app.on_language("en_US")
    populate(app)
    settle(app, 0.8)

    for mode, name in (("dark", "window_dark.png"), ("light", "window_light.png")):
        ctk.set_appearance_mode(mode)
        settle(app, 0.8)
        shoot(app, name)

    ctk.set_appearance_mode("dark")
    app.big_build.set(1)
    app.on_big_build()
    settle(app, 0.5)
    shoot(app, "window_big_build.png")

    app.big_build.set(0)
    app.on_big_build()
    app.rows[-1].tag_var.set("")
    app.revalidate()
    settle(app, 0.5)
    shoot(app, "window_validation.png")

    dialog = scaffold_gui.ResultDialog(
        app, app.text("pack built"),
        [os.path.abspath("Sorter Hall.mcpack")], ".")
    dialog.attributes("-topmost", True)
    settle(app, 1.2)
    shoot(dialog, "pack_built.png")
    dialog.destroy()

    about = scaffold_gui.AboutDialog(app)
    about.attributes("-topmost", True)
    settle(app, 1.2)
    shoot(about, "about.png")
    about.destroy()

    app.on_language(was)
    app.destroy()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
