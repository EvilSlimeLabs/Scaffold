"""The Scaffold window.

Built on CustomTkinter, which is tkinter underneath, so the frozen build stays
the size it was while drawing modern widgets and following the desktop's own
light or dark setting.

The window is one screen with no modes to hunt through. Structures stack on the
left, everything that describes the pack sits on the right, and the status line
along the bottom says what the program is doing at all times. There is no basic
and advanced split: a single structure simply does not need a name tag, and the
second one added asks for both.

Nothing here reaches into scaffold_core beyond its public calls, so the same
work can be driven from the command line or from another front end.
"""
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter
from tkinter import filedialog

import customtkinter as ctk
import nbtlib
import numpy
from PIL import Image

from scaffold import settings
from scaffold.ui import lang_icons
from scaffold import lang_parse
from scaffold.pack import manifest
from scaffold import paths
from scaffold import core
from scaffold import updates
from scaffold.pack import tech_pack
from scaffold.ui import ui_fonts
## Drawn at one scale, chosen once and never changed.
##
## Left to itself CustomTkinter makes the process per-monitor DPI aware and then
## compensates in software: a loop polls every window's monitor, and when one
## changes it fades the window to fifteen percent alpha, rebuilds every widget
## at the new scale and fades it back. Dragging between monitors of different
## scaling redraws the whole window several times.
ctk.deactivate_automatic_dpi_awareness()


def _fix_scale():
    """Render at the desktop's scale, and keep that scale for good.

    A process unaware of DPI is magnified by Windows from ninety-six dots per
    inch, which softens the text. Declaring it aware of the *system* scale draws
    the window at the desktop's own resolution, so the text stays sharp, and a
    monitor at a different scale is Windows' problem to magnify rather than a
    reason to rebuild the window.

    The scale is read once here. Left to CustomTkinter it is re-derived per
    monitor.
    """
    if not sys.platform.startswith("win"):
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware
    except Exception:
        pass                        # already set, or too old a Windows
    try:
        try:
            dots = ctypes.windll.user32.GetDpiForSystem()
        except AttributeError:      # before Windows 10 1607
            screen = ctypes.windll.user32.GetDC(0)
            dots = ctypes.windll.gdi32.GetDeviceCaps(screen, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, screen)
        scale = max(1.0, dots / 96.0)
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
    except Exception:
        pass


_fix_scale()
from scaffold.ui import ui_icons
from scaffold import version
try:
    import darkdetect
except ImportError:                     # optional; only used to resolve "system"
    darkdetect = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:                       # dropping is a convenience, never required
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False


# --- palette ---------------------------------------------------------------
# Taken from the app icon: the amber of the S against the cool slate of the
# hologram grid. Every colour is a (light mode, dark mode) pair.

AMBER = ("#C8891C", "#E8B23A")
AMBER_HOVER = ("#AB731A", "#F2C45C")
ON_AMBER = ("#FFFFFF", "#161A20")
SURFACE = ("#F2F3F5", "#1B1F26")
PANEL = ("#FFFFFF", "#222831")
FIELD = ("#FFFFFF", "#191D24")
BORDER = ("#D5D8DE", "#2E343E")
TEXT = ("#1B1E24", "#E9ECF2")
MUTED = ("#6B7280", "#8B94A3")
DANGER = ("#C0392B", "#F0705E")
OK = ("#2E7D46", "#6FCF8B")

## the amber the drawn glyphs use, one value rather than a light/dark pair
GLYPH_AMBER = (200, 137, 28)
GLYPH_MUTED = (139, 148, 163)

PAD = 12
## the two panel headings share these, so "Structures" and "Settings" sit on the
## same line; the settings panel has a frame of its own and drifted lower
HEADING_PAD = (14, 10)
HEADING_HEIGHT = 26

## The window's size. It does not resize; see the note where this is applied.
WINDOW_WIDE = 1080
WINDOW_TALL = 723

## How wide the global coordinates button is. Sized for the longest translation
## of its label rather than the English one. Ukrainian needs seventy per cent
## more room than English.
CORDS_WIDE = 178

## The icon control's size, and the only thing that decides it. Measuring it
## from the pack name label and field beside it resizes the rows those widgets
## are in, which moves them, which calls for measuring again. A number here
## cannot chase itself.
##
## The frame is drawn into the picture rather than being the widget's own
## border, so the cut corner is part of the same outline.
ICON_SIZE = 68
ICON_INSET = 0
ICON_RADIUS = 11
## The weight the drop zone's border is given. CustomTkinter turns an integer
## border width into pixels with int(width * scaling), truncating rather than
## rounding, so the frame here has to do the same arithmetic to come out the
## same thickness on a scaled display.
ICON_BORDER = 2

## The drop zone's +: how big it is drawn, and the room left around it. It is
## sized to stand as tall as the two lines of text it introduces.
DROP_PLUS = 40
DROP_GAP = 8
## where the drop zone's sentence is broken, in the window's own units: two
## lines of the English text, and two or three of a longer translation
DROP_WRAP = 300

## the language box's two fixed pieces, which the width of the box is measured
## around: the badge that names the language and the chevron that opens it
BADGE = 20
CHEVRON = 12
## the margin inside the box, at both ends
BOX_PAD = 10
## how far the pieces inside a selector stay clear of its outline
BOX_INSET = 2
## A field's rounded corner, and how far its contents stay clear of its edge.
## The inset covers the thickest border a field is ever given. That border grows
## from one to two while a field is showing an error, so the text keeps the same
## distance from the outline in both states instead of shifting.
FIELD_RADIUS = 8
FIELD_INSET = 2
## What each TechPack choice is called. Written out rather than composed, so
## that the check for untranslated strings can see every key the window uses.
TECH_PACK_LABELS = {"none": "techpack none",
                    "compatibility": "techpack compatibility",
                    "full": "techpack full"}

## the ? beside a switch that needs explaining, and how wide its explanation
## is allowed to run before it wraps
HELP_DOT = 18
TIP_WIDE = 300

## the edge of border colour showing around the list a selector opens, the
## margin inside that, and the gap between rows
LIST_RING = 2
LIST_PAD = 4
LIST_GAP = 1
## The height kept for the pack name's hint. It is held open all the time, so
## that the message appearing moves nothing below it, and the description
## section adds no gap of its own above itself to make up for it.
HINT_ROW = 14
## How wide each selector is, and how tall both are. Written down rather than
## measured from the longest choice: a measured width changes with the face the
## language is written in, so the control resizes when its own contents are
## relabelled. Even numbers, because CustomTkinter floors a frame's height and
## width to even before drawing its rounded border, and the odd row left over
## shows as a gap in the outline.
CHOOSER_WIDE = 178
CHOOSER_THEME_WIDE = 132
CHOOSER_TALL = 28
TAG_FIELD_WIDTH = 200          # every name tag field is this wide, on every row
STRUCTURE_TYPES = [("Minecraft structure", "*.mcstructure"), ("All files", "*.*")]


def structure_name(path):
    """A structure file's own name: no folder, no extension.

    What a pack is called when it is named after what is in it.
    """
    return os.path.splitext(os.path.basename(path or ""))[0]
IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")]

## Where the help and about buttons point. Both are here rather than inline so
## there is one place to correct if the project moves.
GITHUB_ISSUES = "https://github.com/EvilSlimeLabs/Scaffold/issues"
WEBSITE = "https://evilslimelabs.com"
LOGO = os.path.join("images", "evilslimelabs-logo3.png")

## The name tag field is labelled with Minecraft's own name tag item, so it is
## recognisable before the word is read.
NAME_TAG_TEXTURE = ("Vanilla_Resource_Pack", "textures", "items", "name_tag.png")

_image_cache = {}


## every font the window makes, so they can all be re-pointed at once when the
## language changes to one the interface face does not cover
_fonts = []
_font_language = [None]      # the language code the fonts are currently set for


def font(size=13, weight="normal"):
    """A window font in the typeface that ships with the program.

    Asking for a family Tk does not have gets silently substituted, which is how
    the window ended up looking different on every machine; ui_fonts hands back
    the platform default when the bundled file could not be registered, so the
    substitution is at least a deliberate one.
    """
    code = _font_language[0]
    made = ctk.CTkFont(family=ui_fonts.family(code),
                       size=_sized(size, code), weight=weight)
    ## the size asked for, kept so the face's own factor can be applied again
    ## from scratch when the language changes rather than compounding
    _fonts.append((made, size))
    return made


def _sized(size, code):
    return max(8, int(round(size * ui_fonts.scale(code))))


def restyle_fonts(code):
    """Point every font at the face this language code needs.

    Chinese and Enchanting are not written in the interface face: one has no CJK
    glyphs, the other is a different alphabet entirely. Tk will not fall back to
    a privately registered font on its own, so the whole window is switched over
    rather than left to render boxes.
    """
    _font_language[0] = code
    family = ui_fonts.family(code)
    for made, asked in _fonts:
        try:
            ## size as well as family: a face wider than the interface face is
            ## asked for smaller, and switching away from it has to put the
            ## size back
            made.configure(family=family, size=_sized(asked, code))
        except Exception:
            pass


def load_image(path, size):
    """A CTkImage, cached: the same picture is asked for on every row."""
    key = (path, size)
    if key not in _image_cache:
        try:
            picture = Image.open(path).convert("RGBA")
        except Exception:
            return None
        _image_cache[key] = ctk.CTkImage(light_image=picture, dark_image=picture,
                                         size=(size, size))
    return _image_cache[key]


def mode_colour(pair, fallback=(128, 128, 128)):
    """A (light, dark) colour pair resolved to the mode in use, as RGB.

    The drawn glyphs are pictures rather than widgets, so CustomTkinter cannot
    swap them for the theme; anything that has to match a widget's colour has to
    ask which mode is showing and be redrawn when it changes.
    """
    try:
        value = pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def glyph(name, size=16, colour=GLYPH_AMBER, **extra):
    """One of the drawn interface icons, as a CTkImage.

    A colour of None means the glyph keeps its own palette; corner_clear is
    drawn in the panel and border colours rather than in one accent.
    """
    key = ("glyph", name, size, colour, tuple(sorted(extra.items())))
    if key not in _image_cache:
        drawer = getattr(ui_icons, name)
        picture = (drawer(size * 2, **extra) if colour is None
                   else drawer(size * 2, colour, **extra))
        _image_cache[key] = ctk.CTkImage(light_image=picture, dark_image=picture,
                                         size=(size, size))
    return _image_cache[key]


def open_link(url):
    import webbrowser
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        pass


def _icon_path(name):
    """An icon file beside the program, wherever the program is.

    Through paths.py like every other data read, so a frozen build looks inside
    its bundle rather than beside a module that is no longer on disk.
    """
    return paths.data(os.path.join("images", name))


def draw_every_pixel(widget):
    """Stop a widget rounding its own size down to an even number.

    CustomTkinter floors a widget's width and height to an even number before
    it draws its rounded rectangle, so anything that comes out an odd number of
    pixels, which a scaled display produces constantly, goes unpainted along its
    last row or column, and whatever is behind it shows through as an extra
    pixel of edge.
    """
    try:
        widget._draw_engine.set_round_to_even_numbers(False, False)
    except Exception:
        pass


def centre_on(window, parent):
    """Put a window in the middle of the one it belongs to.

    Two things this has to avoid. A toplevel that has not been mapped yet
    answers winfo_width with Tk's default 200 rather than its real size, so the
    size it will take is asked for instead. And the result is not clamped to
    zero: a monitor left of or above the main one starts at a negative
    coordinate, and clamping put the window on the wrong screen.
    """
    try:
        window.update_idletasks()
        wide = max(window.winfo_reqwidth(), window.winfo_width())
        tall = max(window.winfo_reqheight(), window.winfo_height())
        x = parent.winfo_rootx() + (parent.winfo_width() - wide) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - tall) // 2
        ## through Tk's own method: CustomTkinter's geometry scales a size on
        ## the way through, and there is nothing here to scale
        tkinter.Toplevel.wm_geometry(window, "+%d+%d" % (x, y))
    except Exception:
        pass


def apply_icon(window):
    """Put the app icon on a window's title bar.

    Both routes are used because neither is reliable on its own. Tk on Windows
    keeps the .ico and the icon photo in different places, and the title bar
    reads the .ico. CustomTkinter also resets the icon while it finishes setting
    a window up, which is why the caller repeats this on a delay.
    """
    ico = _icon_path("pack_icon.ico")
    if os.path.isfile(ico):
        try:
            window.wm_iconbitmap(ico)
        except Exception:
            ## non-Windows Tk refuses a .ico here; not worth failing to start over
            pass
    ## the transparent iconography, not the pack icon: a title bar composes the
    ## icon against itself, so a baked-in background reads as a square tile
    png = paths.lookup("app_icon.png")
    if not os.path.isfile(png):
        png = paths.lookup("pack_icon.png")
    if os.path.isfile(png):
        try:
            if not hasattr(window, "_scaffold_icon_photo"):
                window._scaffold_icon_photo = tkinter.PhotoImage(file=png)
            window.iconphoto(False, window._scaffold_icon_photo)
        except Exception:
            pass


def resolve_theme(choice):
    """Turn the stored preference into what CustomTkinter should be set to.

    "system" is handed straight to CustomTkinter, which follows the desktop --
    except where the desktop cannot be asked at all, and then a dark window is
    the safer thing to show against an unknown background.
    """
    if choice != "system":
        return choice
    if darkdetect is not None and darkdetect.theme() is not None:
        return "system"
    return settings.FALLBACK_THEME


class Tooltip(object):
    """A short explanation that appears beside a control while pointed at.

    A dialog would be too much for a sentence and would have to be dismissed;
    this shows while the pointer is on the mark and goes away when it leaves.
    The window is placed with Tk's own method rather than CustomTkinter's, which
    multiplies a size by the window scaling on the way through.
    """

    ## The one tip that is up, if any. Two cannot be open at once: showing one
    ## puts away whatever was there, so this is what everything else has to
    ## close and there is never a second one to lose track of.
    showing = None

    def __init__(self, widget, app, text):
        self.widget = widget
        self.app = app
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.leave)
        widget.bind("<Button-1>", self.toggle)
        ## a tip outliving the thing it explains would sit there forever
        widget.bind("<Destroy>", self.hide)
        self.watch(app)

    @classmethod
    def close_open(cls, _event=None):
        """Put away whichever tip is up, whatever asked."""
        if cls.showing is not None:
            cls.showing.hide()

    @classmethod
    def watch(cls, app):
        """Bind, once per window, everything that puts an open tip away.

        A tip is a borderless window of its own, so nothing closes it on its
        own: not a click, not a keystroke, not the program being left. Leaving
        the mark is the usual way and it is not enough on its own, because a
        mark can go out from under the pointer -- the window is relaid out, the
        language changes, a dialog opens over it -- and no Leave ever arrives.

        `bind_all` rather than a binding on the window, because the events that
        matter land on whichever widget was clicked or typed in, including the
        widgets of a dialog that has taken the grab. Bound once and left alone:
        tkinter's `unbind` takes a funcid and removes the whole binding for the
        sequence anyway, so binding and unbinding per tip would take the
        window's own handlers with it.
        """
        if getattr(app, "_tips_watched", False):
            return
        app._tips_watched = True
        for sequence in ("<Button>", "<Key>", "<MouseWheel>"):
            try:
                app.bind_all(sequence, cls._interacted, add="+")
            except Exception:
                pass
        for sequence in ("<FocusOut>", "<Unmap>"):
            try:
                app.bind(sequence, cls._left_the_program, add="+")
            except Exception:
                pass
        try:
            app.bind("<Configure>", cls._moved, add="+")
        except Exception:
            pass

    @classmethod
    def _interacted(cls, event=None):
        """Anything done to the program closes the tip that is up.

        Except the click on the mark itself, which is the one that opened it:
        the mark's own binding runs first and `bind_all` last, so a click there
        would open a tip and close it again in the same event.
        """
        tip = cls.showing
        if tip is not None and getattr(event, "widget", None) is not tip.widget:
            tip.hide()

    def over_mark(self):
        """Whether the pointer is really on the mark.

        Asked of the pointer rather than taken from the event, because a Leave
        also fires when the pointer crosses onto something drawn over the mark,
        and hiding then means the tip flickers instead of staying up.
        """
        try:
            x = self.widget.winfo_pointerx() - self.widget.winfo_rootx()
            y = self.widget.winfo_pointery() - self.widget.winfo_rooty()
        except Exception:
            return False
        return (0 <= x < self.widget.winfo_width()
                and 0 <= y < self.widget.winfo_height())

    def leave(self, _event=None):
        if not self.over_mark():
            self.hide()

    def toggle(self, _event=None):
        """A click on the mark shows the tip, or puts it away if it is up."""
        if self.window is not None:
            self.hide()
        else:
            self.show()

    def where(self):
        """The window's position and size, which the tip is placed against."""
        try:
            return (self.app.winfo_rootx(), self.app.winfo_rooty(),
                    self.app.winfo_width(), self.app.winfo_height())
        except Exception:
            return None

    @classmethod
    def _moved(cls, _event=None):
        """Hide if the window really moved, not merely settled.

        Configure fires throughout a window's layout as well as when it is
        dragged, so the event on its own is not the question. The window's
        geometry against the anchor recorded at open time is.
        """
        tip = cls.showing
        if tip is not None and tip.where() != tip._anchor:
            tip.hide()

    @classmethod
    def _left_the_program(cls, _event=None):
        """Hide if the focus left the program, not merely one widget.

        FocusOut also fires moving between widgets of the same window, which is
        most of what a window does, so what matters is whether anything in the
        program still holds focus. That is only settled once the move has
        finished, hence the hop through after().
        """
        tip = cls.showing
        if tip is None:
            return

        def settled():
            try:
                if tip.app.focus_displayof() is None:
                    tip.hide()
            except Exception:
                tip.hide()
        try:
            tip.app.after(1, settled)
        except Exception:
            tip.hide()

    def show(self, _event=None):
        if self.window is not None or not self.text:
            return
        ## one at a time, so there is only ever one to put away
        Tooltip.close_open()
        self.window = ctk.CTkToplevel(self.app)
        self.window.overrideredirect(True)
        self.window.configure(fg_color=BORDER)
        self.window.attributes("-topmost", True)
        inner = ctk.CTkFrame(self.window, fg_color=PANEL, corner_radius=8)
        inner.pack(padx=LIST_RING, pady=LIST_RING, fill="both", expand=True)
        draw_every_pixel(inner)
        label = ctk.CTkLabel(inner, text=self.text, justify="left",
                             anchor="w", text_color=TEXT,
                             wraplength=self.widget._apply_widget_scaling(TIP_WIDE),
                             font=font(size=11))
        label.pack(padx=10, pady=8)

        self.window.update_idletasks()
        wide = self.window.winfo_reqwidth()
        tall = self.window.winfo_reqheight()
        ## to the left of the mark, since the mark sits near the right edge of
        ## the panel and the text is wider than the room left beside it
        x = self.widget.winfo_rootx() + self.widget.winfo_width() - wide
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tkinter.Toplevel.wm_geometry(self.window,
                                     "%dx%d+%d+%d" % (wide, tall, x, y))

        ## what `_moved` compares the window against, so that the Configure
        ## events a layout fires do not read as the window being dragged
        self._anchor = self.where()
        Tooltip.showing = self

    def hide(self, _event=None):
        if Tooltip.showing is self:
            Tooltip.showing = None
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


class Field(ctk.CTkFrame):
    """An entry with a glyph or a letter sitting inside it, before the text.

    CustomTkinter has no way to inset an entry's text, and a picture placed over
    one covers the characters rather than moving them. So the border belongs to
    this frame and the entry inside is drawn without one; the mark and the text
    are laid out side by side, with margin between, and the whole thing reads as
    a single field.
    """

    def __init__(self, master, textvariable, icon=None, label=None,
                 width=None, height=32, on_clear=None, **kwargs):
        super().__init__(master, fg_color=FIELD, corner_radius=FIELD_RADIUS,
                         border_width=1, border_color=BORDER,
                         height=height, **kwargs)
        self.grid_propagate(False)
        draw_every_pixel(self)
        if width:
            self.configure(width=width)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.mark = None
        if icon is not None or label is not None:
            self.mark = ctk.CTkLabel(self, text=label or "", width=16,
                                     text_color=MUTED,
                                     font=font(size=11, weight="bold"))
            if icon is not None:
                self.mark.configure(image=icon, text="")
            ## the margin either side is what keeps the mark clear of the text
            self.mark.grid(row=0, column=0, padx=(9, 0), sticky="w")

        self.entry = ctk.CTkEntry(self, textvariable=textvariable,
                                  border_width=0, fg_color="transparent",
                                  text_color=TEXT, height=height - 4)
        ## Stretched to the row rather than centred in it. A CTkEntry paints the
        ## colour it finds behind it across its whole rectangle, and centring one
        ## that is shorter than the row splits the leftover unevenly, leaving a
        ## pixel of the field above the text and two below it.
        ##
        ## The left padding is remembered rather than read back, because
        ## grid_info returns one number when both sides match and a pair when
        ## they do not.
        self._text_left = 7 if self.mark else 8
        self.entry.grid(row=0, column=1, sticky="nsew", pady=FIELD_INSET,
                        padx=(self._text_left, 8))

        ## an emptying control belongs in the field it empties, not beside it
        self.clear_button = None
        self.variable = textvariable
        if on_clear is not None:
            self.clear_button = ctk.CTkButton(
                self, text="", width=20, height=20, corner_radius=10,
                image=glyph("cross", 10, GLYPH_MUTED), fg_color="transparent",
                hover_color=BORDER, command=on_clear)
            draw_every_pixel(self.clear_button)
            textvariable.trace_add("write", lambda *_: self._sync_clear())
            self._sync_clear()

    def _sync_clear(self):
        """Nothing to clear when the field is empty, so nothing is offered.

        The text gives up its right margin to the button when there is one, and
        takes it back when there is not, because otherwise the emptied field's
        text runs into the rounded corner the button was standing clear of.
        """
        if self.clear_button is None:
            return
        if self.variable.get():
            self.clear_button.grid(row=0, column=2, padx=(0, 6))
            self.entry.grid_configure(padx=(self._text_left, 4))
        else:
            self.clear_button.grid_forget()
            self.entry.grid_configure(padx=(self._text_left, 8))

    def set_label(self, text):
        if self.mark is not None:
            self.mark.configure(text=text)

    def flag(self, wrong):
        self.configure(border_color=DANGER if wrong else BORDER,
                       border_width=2 if wrong else 1)

    def set_enabled(self, enabled):
        """A field that cannot be typed in should not look like one that can."""
        self.entry.configure(state="normal" if enabled else "disabled")
        self.configure(fg_color=FIELD if enabled else BORDER)


class StructureRow(ctk.CTkFrame):
    """One .mcstructure in the pack: its file, its name tag and its offset.

    The offset lives on the row rather than in the settings panel because it
    belongs to this structure. The panel edits whichever row is selected.
    """

    def __init__(self, master, app, path):
        super().__init__(master, fg_color=PANEL, corner_radius=8,
                         border_width=1, border_color=BORDER)
        self.app = app
        self.path = path
        self.offset = [0, 0, 0]
        self.selected = False

        ## only the file button stretches; the name tag field is a fixed width
        ## so every row's field starts and ends in the same place
        self.grid_columnconfigure(0, weight=1)

        self.file_button = ctk.CTkButton(
            self, text="", anchor="w", height=32, corner_radius=6,
            fg_color="transparent", hover_color=FIELD, text_color=TEXT,
            image=glyph("folder", 15), compound="left",
            font=font(size=13), command=self.change_file)
        self.file_button.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=9)

        tag_icon = load_image(paths.data(*NAME_TAG_TEXTURE), 17)
        self.tag_var = tkinter.StringVar()
        self.tag_var.trace_add("write", lambda *_: self.app.revalidate())
        self.tag_field = Field(self, self.tag_var, icon=tag_icon,
                               width=TAG_FIELD_WIDTH, height=32)
        self.tag_field.grid(row=0, column=1, padx=(0, 4), pady=9)

        ## CustomTkinter never activates an entry's placeholder while the entry
        ## is bound to a textvariable, and the variable is what makes validation
        ## live, so the optional/required state is its own label instead.
        self.tag_hint = ctk.CTkLabel(self, text="", anchor="w", width=64,
                                     text_color=MUTED,
                                     font=font(size=11))
        self.tag_hint.grid(row=0, column=2, sticky="w", padx=(0, 2))

        self.remove_button = ctk.CTkButton(
            self, text="", width=30, height=30, corner_radius=6,
            image=glyph("cross", 13, GLYPH_MUTED),
            fg_color="transparent", hover_color=BORDER,
            command=lambda: self.app.remove_structure(self))
        self.remove_button.grid(row=0, column=3, padx=(2, 8), pady=9)

        self.bind("<Button-1>", lambda _e: self.app.select_row(self))
        self.refresh_file_label()

    def refresh_file_label(self):
        self.file_button.configure(text="  " + os.path.basename(self.path))

    def change_file(self):
        """Pick a different file for this row, rather than removing and re-adding."""
        self.app.select_row(self)
        chosen = filedialog.askopenfilename(
            title=self.app.text("change file"), filetypes=STRUCTURE_TYPES,
            initialdir=os.path.dirname(self.path) or None)
        if chosen:
            self.path = chosen
            self.refresh_file_label()
            self.app.set_status(self.app.text("status added",
                                              os.path.basename(chosen)))
            self.app.revalidate()

    def set_selected(self, selected):
        self.selected = selected
        self.configure(border_color=AMBER if selected else BORDER,
                       border_width=2 if selected else 1)

    def set_tag_state(self, required, wrong):
        """Show whether this row still needs a name tag, as the user types."""
        self.tag_hint.configure(
            text=self.app.text("required" if required else "optional"),
            text_color=DANGER if wrong else MUTED)
        self.tag_field.flag(wrong)

    def set_tag_enabled(self, enabled):
        self.tag_field.set_enabled(enabled)
        if not enabled:
            self.tag_hint.configure(text="")

    @property
    def tag(self):
        return self.tag_var.get().strip()


class ResultDialog(ctk.CTkToplevel):
    """What happened, once the pack is written."""

    def __init__(self, app, title, lines, folder, reveal=None):
        super().__init__(app)
        self.app = app
        self.folder = folder
        ## the file to point at once the folder opens, if there is one
        self.reveal = reveal
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        self.grid_columnconfigure(0, weight=1)
        self.after(220, lambda: apply_icon(self))

        ctk.CTkLabel(self, text=title, font=font(size=17, weight="bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w",
                                           padx=20, pady=(18, 4))
        for i, line in enumerate(lines, start=1):
            ctk.CTkLabel(self, text=line, text_color=MUTED, justify="left",
                         anchor="w", wraplength=420).grid(
                row=i, column=0, sticky="ew", padx=20, pady=1)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=len(lines) + 1, column=0, sticky="e", padx=16, pady=(14, 16))
        if folder:
            ctk.CTkButton(buttons, text=app.text("open folder"), width=130,
                          height=32, corner_radius=8, fg_color="transparent",
                          border_width=1, border_color=BORDER, text_color=TEXT,
                          hover_color=BORDER, command=self.open_folder
                          ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=app.text("close"), width=110, height=32,
                      corner_radius=8, fg_color=AMBER, hover_color=AMBER_HOVER,
                      text_color=ON_AMBER, command=self.destroy).pack(side="left")

        ## transient ties the dialog to the window, so it can never end up
        ## behind it. A plain toplevel can.
        self.transient(app)
        self.after(60, self._centre)
        self.after(120, self.grab_set)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _centre(self):
        centre_on(self, self.app)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def open_folder(self):
        """Open the folder with the pack picked out in it, and stand down.

        Explorer and Finder both take a file and select it; there is no such
        thing on Linux, where the folder on its own is the whole answer. A
        selection that fails for any reason falls back to opening the folder,
        because the point of the button is to get somebody there.

        The dialog closes either way. It has said what it had to say, and
        leaving a modal in front of the window somebody has just been sent
        somewhere else means coming back to dismiss it.
        """
        folder = os.path.abspath(self.folder)
        wanted = os.path.abspath(self.reveal) if self.reveal else None
        try:
            if sys.platform.startswith("win"):
                if wanted and os.path.exists(wanted):
                    ## Passed as one command string, not an argument list:
                    ## list2cmdline quotes an argument that has a space in it,
                    ## and explorer will not parse a quoted "/select,<path>"
                    ## token -- it drops the selection and opens a default
                    ## view. Only the path is quoted here, the switch is not.
                    ## explorer exits 1 even on success, so its code is ignored.
                    subprocess.Popen('explorer /select,"%s"'
                                     % os.path.normpath(wanted))
                else:
                    os.startfile(folder)
            elif sys.platform == "darwin":
                if wanted and os.path.exists(wanted):
                    subprocess.Popen(["open", "-R", wanted])
                else:
                    subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            try:
                if sys.platform.startswith("win"):
                    os.startfile(folder)
            except Exception:
                pass
        self.destroy()


class QuestionDialog(ctk.CTkToplevel):
    """A dialog the build stops on, with the answer read once it closes.

    The two below are the same shape: a heading, some lines of explanation, and
    a row of buttons where the last one is the one to press. `answer` is what
    the caller reads after wait_window, and closing the window leaves it as it
    started, which is why every one of these treats None as cancel.
    """

    def __init__(self, app, title):
        super().__init__(app)
        self.app = app
        self.answer = None
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        self.grid_columnconfigure(0, weight=1)
        self.after(220, lambda: apply_icon(self))
        self.row = 0
        self.heading(title)

    def heading(self, text):
        ctk.CTkLabel(self, text=text, font=font(size=17, weight="bold"),
                     text_color=TEXT).grid(row=self.row, column=0, sticky="w",
                                           padx=20, pady=(18, 6))
        self.row += 1

    def line(self, text, colour=MUTED):
        ctk.CTkLabel(self, text=text, text_color=colour, justify="left",
                     anchor="w", wraplength=420).grid(
            row=self.row, column=0, sticky="ew", padx=20, pady=1)
        self.row += 1

    def buttons(self, choices):
        """Right to left as they are given, so the last is the rightmost and
        the only one drawn in the accent colour."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=self.row, column=0, sticky="e", padx=16, pady=(16, 16))
        self.row += 1
        for index, (label, command) in enumerate(choices):
            last = index == len(choices) - 1
            ctk.CTkButton(
                frame, text=label, width=120, height=32, corner_radius=8,
                fg_color=AMBER if last else "transparent",
                hover_color=AMBER_HOVER if last else BORDER,
                text_color=ON_AMBER if last else TEXT,
                border_width=0 if last else 1, border_color=BORDER,
                command=command).pack(side="left", padx=(8, 0))

    def show(self):
        ## transient ties the dialog to the window, so it can never end up
        ## behind it while the build waits on the answer
        self.transient(self.app)
        self.after(60, self._centre)
        self.after(120, self.grab_set)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _centre(self):
        centre_on(self, self.app)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def settle(self, answer):
        self.answer = answer
        self.destroy()


def free_name(folder, name, taken=None):
    """`name` with a number after it, the first that nothing answers to.

    A name that already carries a number is counted on rather than given a
    second, so the suggestion after "Pack (2)" is "Pack (3)" and not
    "Pack (2) (2)".

    `taken` decides what counts as in the way, and a build writes more than the
    pack: with block lists switched on, a name whose `.mcpack` is free can still
    collide on a list file. Checking only the pack there suggests a name that
    collides all over again, which is an argument the caller cannot win.
    """
    if taken is None:
        def taken(candidate):
            return os.path.exists(os.path.join(folder, candidate
                                               + core.PACK_SUFFIX))
    stem = re.sub(r"\s*\(\d+\)$", "", name).strip() or name
    number = 2
    while taken("%s (%d)" % (stem, number)):
        number += 1
    return "%s (%d)" % (stem, number)


class OverwriteDialog(QuestionDialog):
    """A build that would write over files that are already there.

    Answers "overwrite", or "rename" with the name in `chosen`, or None.
    """

    def __init__(self, app, folder, name, clashes, suggestion):
        super().__init__(app, app.text("overwrite title"))
        self.chosen = suggestion
        self.line(app.text("overwrite body", os.path.basename(folder) or folder))
        for path in clashes[:6]:
            self.line(os.path.basename(path), colour=TEXT)
        if len(clashes) > 6:
            self.line("...")
        self.line(app.text("overwrite ask"))

        ## The name to save under is offered rather than asked for. Typing one
        ## here duplicated the pack name field in the window behind, and a name
        ## typed into a dialog could collide too, which is what made this ask
        ## twice. Somebody who wants a different name entirely cancels and
        ## changes it where it lives.
        self.buttons([(app.text("cancel"), self.destroy),
                      (app.text("save as", suggestion),
                       lambda: self.settle("rename")),
                      (app.text("overwrite"), lambda: self.settle("overwrite"))])
        self.show()
        self.bind("<Return>", lambda _e: self.settle("rename"))


class RetryDialog(QuestionDialog):
    """A file the build could not write. Answers True to try it again."""

    def __init__(self, app, path, exc):
        super().__init__(app, app.text("write failed title"))
        self.line(app.text("write failed body", os.path.basename(path)),
                  colour=TEXT)
        self.line(str(exc), colour=DANGER)
        self.line(app.text("write failed hint"))
        self.buttons([(app.text("cancel"), self.destroy),
                      (app.text("retry"), lambda: self.settle(True))])
        self.show()
        self.bind("<Return>", lambda _e: self.settle(True))


class AboutDialog(ctk.CTkToplevel):
    """Who made this, and where to go next."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(app.text("about"))
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        self.grid_columnconfigure(0, weight=1)
        self.after(220, lambda: apply_icon(self))

        logo = load_image(paths.data(LOGO), 132)
        if logo is not None:
            ctk.CTkLabel(self, text="", image=logo).grid(row=0, column=0, pady=(18, 4))

        ctk.CTkLabel(self, text="Scaffold %s" % version.read(),
                     font=font(size=18, weight="bold"),
                     text_color=TEXT).grid(row=1, column=0, pady=(4, 0))
        ctk.CTkLabel(self, text=app.text("about body"), text_color=MUTED,
                     wraplength=340, justify="center").grid(
            row=2, column=0, padx=22, pady=(6, 2))
        ctk.CTkLabel(self, text="%s: DrAv0011, FondUnicycle, RavinMaddHatter"
                                % app.text("original authors"),
                     text_color=MUTED, wraplength=340, justify="center",
                     font=font(size=11)).grid(
            row=3, column=0, padx=22, pady=(2, 6))

        ## the update controls: what is there now, and whether to look at all
        panel = ctk.CTkFrame(self, fg_color=FIELD, corner_radius=10)
        panel.grid(row=4, column=0, padx=22, pady=(6, 4), sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        draw_every_pixel(panel)

        ## If the launch check already found a release, say so here rather than
        ## "up to date": the launch prompt may have been dismissed, and it is
        ## still available.
        opening = (app.text("update found", app.available_update)
                   if app.available_update else app.text("update current"))
        self.update_status = ctk.CTkLabel(
            panel, text=opening, text_color=MUTED,
            wraplength=300, justify="left", anchor="w", font=font(size=11))
        self.update_status.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="w")

        self.update_button = ctk.CTkButton(
            panel, text=app.text("check updates"), width=118, height=28,
            corner_radius=8, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT, hover_color=BORDER,
            font=font(size=12), command=self.check_now)
        self.update_button.grid(row=0, column=1, rowspan=2, padx=(8, 12), pady=10)

        self.check_on_launch = tkinter.IntVar(
            value=int(settings.check_updates()))
        switch = ctk.CTkSwitch(
            panel, text=app.text("check on launch"), variable=self.check_on_launch,
            width=40, progress_color=AMBER, font=font(size=11),
            text_color=MUTED, button_color=("#FFFFFF", "#E9ECF2"),
            command=lambda: settings.set_check_updates(
                bool(self.check_on_launch.get())))
        switch.grid(row=1, column=0, padx=12, pady=(2, 10), sticky="w")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, pady=(8, 18))
        ctk.CTkButton(buttons, text=app.text("website"), width=120, height=32,
                      corner_radius=8, fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=TEXT, hover_color=BORDER,
                      command=lambda: open_link(WEBSITE)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=app.text("close"), width=110, height=32,
                      corner_radius=8, fg_color=AMBER, hover_color=AMBER_HOVER,
                      text_color=ON_AMBER, command=self.destroy).pack(side="left")

        ## transient ties the dialog to the window, so it can never end up
        ## behind it. A plain toplevel can.
        self.transient(app)
        self.after(60, self._centre)
        self.after(120, self.grab_set)
        self.bind("<Escape>", lambda _e: self.destroy())

    def check_now(self):
        """Ask GitHub, off the main thread, and say what came back.

        The asking is a network call and Tk is not thread safe, so the answer
        comes back through the window's queue like a finished build does.
        """
        self.update_button.configure(state="disabled")
        self.update_status.configure(text=self.app.text("update checking"))

        def ask():
            found = None
            try:
                found = updates.available()
            except Exception:
                ## a check that fails is not a thing to interrupt anybody over
                found = None
            self.app.after(0, lambda: self.answered(found))

        threading.Thread(target=ask, daemon=True).start()

    def answered(self, tag):
        if not self.winfo_exists():
            return
        self.update_button.configure(state="normal")
        if tag:
            self.update_status.configure(text=self.app.text("update found", tag))
            self.app.offer_update(tag)
        else:
            ## a build from a checkout lands here too, and is told the same
            ## thing: whether a newer version is out is all anyone asked
            self.update_status.configure(text=self.app.text("update current"))

    def _centre(self):
        centre_on(self, self.app)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()


class UpdateDialog(ctk.CTkToplevel):
    """A newer build is out. Take it now, or not."""

    def __init__(self, app, tag):
        super().__init__(app)
        self.app = app
        self.tag = tag
        self.title(app.text("update title"))
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        self.grid_columnconfigure(0, weight=1)
        self.after(220, lambda: apply_icon(self))

        ctk.CTkLabel(self, text=app.text("update found", tag),
                     font=font(size=15, weight="bold"), text_color=TEXT).grid(
            row=0, column=0, padx=34, pady=(22, 4))
        self.detail = ctk.CTkLabel(self, text=app.text("update body"),
                                   text_color=MUTED, wraplength=320,
                                   justify="center")
        self.detail.grid(row=1, column=0, padx=34, pady=(2, 12))

        self.buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons.grid(row=2, column=0, pady=(4, 20))
        self.later = ctk.CTkButton(
            self.buttons, text=app.text("not now"), width=120, height=32,
            corner_radius=8, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT, hover_color=BORDER,
            command=self.destroy)
        self.later.pack(side="left", padx=(0, 8))
        self.take = ctk.CTkButton(
            self.buttons, text=app.text("update now"), width=120, height=32,
            corner_radius=8, fg_color=AMBER, hover_color=AMBER_HOVER,
            text_color=ON_AMBER, command=self.install)
        self.take.pack(side="left")

        ## Hold the size the "available" state lays out at. The dialog is reused
        ## for the download, whose text is shorter, and a window that fits its
        ## content would shrink to a small box mid-update. A longer error string
        ## can still grow it.
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())

        self.transient(app)
        self.after(60, self._centre)
        self.after(120, self.grab_set)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _centre(self):
        centre_on(self, self.app)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def install(self):
        """Fetch the build and put it in place, then start it and leave."""
        ## leaving is the last step, and a build in progress would go with it
        if self.app.building:
            self.detail.configure(text=self.app.text("update while building"))
            return
        self.take.configure(state="disabled")
        self.later.configure(state="disabled")
        self.detail.configure(text=self.app.text("update working"))

        def work():
            trouble = updates.install_latest(report=self.stage)
            self.app.after(0, lambda: self.finished(trouble))

        threading.Thread(target=work, daemon=True).start()

    def stage(self, key):
        """Say which part of the update is happening, from the worker thread."""
        self.app.after(0, lambda: self.winfo_exists()
                       and self.detail.configure(text=self.app.text(key)))

    def finished(self, trouble):
        if not self.winfo_exists():
            return
        if trouble:
            reason, detail = trouble
            self.detail.configure(text=self.app.text(reason, detail))
            self.take.configure(state="normal")
            self.later.configure(state="normal")
            return
        ## The new build is already starting and this one has to be gone before
        ## it can clear away what it replaced, so leave now rather than unwind.
        self.app.destroy()
        os._exit(0)


class Chooser(ctk.CTkFrame):
    """A box showing the current choice, and the list it opens.

    Both selectors on the bottom bar are this, so that they behave the same:
    CTkOptionMenu highlights only the strip its arrow is in, draws its list with
    a border of its own, and drops downward off the bottom of the window. It also
    cannot show a picture, which the language list needs, because a badge
    belongs in the control it names rather than beside it.

    The box is this frame, so border, fill and corner radius are its own and the
    badge, the text and the chevron are laid out inside it. A frame within a
    frame puts a square of the parent's colour behind the rounded box, which
    shows as a ragged outline at the corners.
    """

    def __init__(self, master, app, values, command, labels=None, badges=True,
                 width=CHOOSER_WIDE, height=CHOOSER_TALL):
        super().__init__(master, fg_color=FIELD, corner_radius=8,
                         border_width=1, border_color=BORDER,
                         width=width, height=height)
        self.app = app
        self.values = list(values)
        self.command = command
        self.labels = labels or (lambda value: value)
        self.badges = badges
        self.popup = None
        self.current = None
        ## the list is drawn to this too, so the two are the same width by
        ## construction rather than by one being measured against the other
        self._needed = width

        ## The pieces inside are laid out with grid, so it is grid propagation
        ## that has to be stopped. Left on, the box shrinks to its contents and
        ## stops being the width the list is drawn to.
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        draw_every_pixel(self)

        ## Everything inside is kept clear of the outline. A CTkLabel's
        ## "transparent" fills its rectangle with the colour it finds behind it
        ## rather than leaving those pixels alone, so a label as tall as the box
        ## paints over the border along the top and the bottom.
        inner = height - 2 * BOX_INSET

        self.badge = None
        if badges:
            self.badge = ctk.CTkLabel(self, text="", width=BADGE, height=inner)
            self.badge.grid(row=0, column=0, padx=(BOX_PAD, 0), pady=BOX_INSET)
        self.label = ctk.CTkLabel(self, text="", anchor="w", text_color=TEXT,
                                  height=inner, font=font(size=12))
        self.label.grid(row=0, column=1, sticky="ew", pady=BOX_INSET,
                        padx=(7 if badges else BOX_PAD, 0))
        self.chevron = ctk.CTkLabel(self, text="", width=CHEVRON, height=inner,
                                    image=glyph("chevron", CHEVRON, GLYPH_MUTED))
        self.chevron.grid(row=0, column=2, padx=(4, BOX_PAD), pady=BOX_INSET)

        ## the whole box is the control: every piece of it answers the pointer,
        ## lights the same way and shows the same cursor, so there is no strip
        ## of it that behaves differently from the rest
        for part in self.parts():
            part.configure(cursor="hand2")
            part.bind("<Button-1>", lambda _e: self.toggle())
            part.bind("<Enter>", lambda _e: self._hover(True))
            part.bind("<Leave>", lambda _e: self._hover(False))

    def parts(self):
        return [part for part in (self, self.badge, self.label, self.chevron)
                if part is not None]

    def _hover(self, on):
        self.configure(fg_color=BORDER if on else FIELD)

    def badge_for(self, value, size=BADGE):
        ## a language chooser carries locales, and each language file says what
        ## letters its badge should read
        if not self.badges:
            return None
        light, dark = lang_icons.pair(value, size=size,
                                      label=settings.language_badge(value))
        return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))

    def set(self, value):
        self.current = value
        if self.badge is not None:
            self.badge.configure(image=self.badge_for(value))
        self.label.configure(text=self.labels(value))

    def get(self):
        return self.current

    def configure_values(self, values):
        self.values = list(values)

    def refit(self):
        """Relabel: the text, or the face it is drawn in, changed."""
        if self.current is not None:
            self.label.configure(text=self.labels(self.current))

    def toggle(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.close()
            return
        self.open()

    def open(self):
        self.popup = ctk.CTkToplevel(self.app)
        self.popup.overrideredirect(True)
        self.popup.configure(fg_color=BORDER)
        self.popup.attributes("-topmost", True)
        inner = ctk.CTkFrame(self.popup, fg_color=PANEL, corner_radius=8)
        ## The window behind it is the border colour, and this is what leaves an
        ## even edge of it showing on all four sides.
        inner.pack(padx=LIST_RING, pady=LIST_RING, fill="both", expand=True)
        draw_every_pixel(inner)

        last = len(self.values) - 1
        for index, value in enumerate(self.values):
            chosen = value == self.current
            row = ctk.CTkButton(
                inner, text="  " + self.labels(value),
                image=self.badge_for(value),
                anchor="w", compound="left", height=30, corner_radius=6,
                width=self._needed - 10, cursor="hand2",
                fg_color=AMBER if chosen else "transparent",
                text_color=ON_AMBER if chosen else TEXT,
                ## the row already chosen brightens rather than darkening, so
                ## that it still reads as the one in use and not as the one
                ## about to be picked
                hover_color=AMBER_HOVER if chosen else BORDER,
                font=font(size=12),
                command=lambda v=value: self.choose(v))
            draw_every_pixel(row)
            ## The ends of the list get the wider margin. The selected row is
            ## filled and the rest are transparent, so a margin equal to the gap
            ## between rows reads as no margin at all above a filled first row.
            row.pack(fill="x", padx=LIST_PAD,
                     pady=(LIST_PAD if index == 0 else LIST_GAP,
                           LIST_PAD if index == last else LIST_GAP))

        self.popup.update_idletasks()
        ## How tall the rows need it to be, not how tall it currently is: a
        ## toplevel that has not been mapped yet reports Tk's default 200,
        ## which is shorter than this list and would cut the end off it.
        tall = self.popup.winfo_reqheight()
        wide = self.winfo_width()
        x = self.winfo_rootx()
        ## above the control, because it sits on the bottom bar
        y = self.winfo_rooty() - tall - 4
        ## Placed through Tk's own method rather than CustomTkinter's, which
        ## multiplies a size by the window scaling on the way through and leaves
        ## the position alone. Both figures here are already real pixels.
        ##
        ## The position may be negative. A monitor left of or above the main one
        ## starts at a negative coordinate, and clamping to zero puts the list
        ## on the wrong screen.
        self.placed = (wide, tall, x, y)
        tkinter.Toplevel.wm_geometry(self.popup, "%dx%d+%d+%d" % self.placed)
        self.chevron.configure(image=glyph("chevron", CHEVRON, GLYPH_MUTED, up=True))
        ## A click anywhere else in the window closes the list. Clicks inside it
        ## are a different toplevel and never reach this binding.
        ##
        ## The popup must not take focus. Clicking a row would then move focus,
        ## and closing on FocusOut destroys the popup before the click that was
        ## about to choose reaches it.
        self._outside = self.app.bind("<Button-1>", lambda _e: self.close(), add="+")
        ## A menu belongs to the window it was opened from. It goes away when
        ## that window stops being the one in use, and when the window is moved
        ## or resized, since it is placed at a position on the screen rather
        ## than inside anything.
        self._unfocus = self.app.bind("<FocusOut>", self._maybe_close, add="+")
        self._anchor = self._where()
        self._moved = self.app.bind("<Configure>", self._maybe_moved, add="+")
        self.popup.bind("<Escape>", lambda _e: self.close())

    def _where(self):
        """The window's position and size, which the list is placed against."""
        try:
            return (self.app.winfo_rootx(), self.app.winfo_rooty(),
                    self.app.winfo_width(), self.app.winfo_height())
        except Exception:
            return None

    def _maybe_moved(self, _event=None):
        """Close if the window really moved, not merely settled.

        Configure fires throughout a window's layout as well as when it is
        dragged or resized, so the event on its own is not the question; what
        matters is whether the window is somewhere other than where it was when
        the list was placed against it.
        """
        if self._where() != self._anchor:
            self.close()

    def _maybe_close(self, _event=None):
        """Close if the focus has left the program, not merely this widget.

        FocusOut also fires when focus moves between widgets of the same window,
        which is most of what a window does, so the answer has to come from
        whether anything in the program still holds it. That is only settled
        once the move has finished, hence the hop through after().
        """
        def settled():
            try:
                if self.app.focus_displayof() is None:
                    self.close()
            except Exception:
                self.close()
        try:
            self.app.after(1, settled)
        except Exception:
            pass

    def choose(self, value):
        self.close()
        self.set(value)
        if self.command:
            self.command(value)

    def close(self):
        for sequence, attribute in (("<Button-1>", "_outside"),
                                    ("<FocusOut>", "_unfocus"),
                                    ("<Configure>", "_moved")):
            handle = getattr(self, attribute, None)
            if handle:
                try:
                    self.app.unbind(sequence, handle)
                except Exception:
                    pass
                setattr(self, attribute, None)
        try:
            self.chevron.configure(image=glyph("chevron", CHEVRON, GLYPH_MUTED))
            self._hover(False)
        except Exception:
            pass
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        self.popup = None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.strings = settings.load()
        self.rows = []
        self.selected = None
        self.building = False
        ## set when the user answers a write question with cancel, so the
        ## failure that follows is reported as a choice rather than a fault
        self.cancelled = False
        self.sticky_status = False
        ## the newest release the launch or About check has seen, so About does
        ## not say "up to date" after the launch prompt was dismissed
        self.available_update = None
        self.events = queue.Queue()
        self.default_icon = paths.lookup("pack_icon.png")
        self.icon_path = self.default_icon
        ## per-row offsets are put aside while big build mode borrows the three
        ## offset fields for its own single corner, and handed back afterwards
        self.big_offset = [0, 0, 0]
        self.stashed_tags = {}
        ## guards the offset fields against re-entering their own write trace
        self._sanitising = False

        restyle_fonts(settings.settings["lang"])
        ctk.set_appearance_mode(resolve_theme(settings.settings["theme"]))
        ctk.set_default_color_theme("blue")

        self.title("Scaffold %s" % version.read())
        self.geometry("%dx%d" % (WINDOW_WIDE, WINDOW_TALL))
        ## Fixed, like everything inside it.
        ##
        ## CustomTkinter draws every widget on a canvas of its own and repaints
        ## it whenever its size changes, which costs about a millisecond each.
        ## With the widgets this window has, one step of a resize costs a quarter
        ## of a second. An empty window of the same kind resizes in six
        ## milliseconds, and the difference is entirely the repainting.
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        for delay in (0, 200, 600, 1200):
            self.after(delay, lambda: apply_icon(self))
        self._enable_drop()

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self._build_structures_panel()
        self._build_settings_panel()
        self._build_footer()

        ## The window opens with no structures. An empty row is something the
        ## user has to notice and delete, and it makes a new pack look half
        ## filled in before anything has been chosen.
        self.revalidate()
        self.after(120, self._drain_events)

    # --- chrome ----------------------------------------------------------

    def text(self, key, *args):
        value = self.strings.get(key, key)
        return value.format(*args) if args else value

    def _enable_drop(self):
        """Graft tkinterdnd2 onto the CustomTkinter root, if it is installed."""
        self.dnd_ready = False
        if not DND_AVAILABLE:
            return
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self.dnd_ready = True
        except Exception:
            self.dnd_ready = False

    # --- structures panel -------------------------------------------------

    def _build_structures_panel(self):
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(PAD, 6), pady=(PAD, 6))
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkFrame(panel, fg_color="transparent", height=HEADING_HEIGHT)
        heading.grid(row=0, column=0, sticky="ew", pady=HEADING_PAD)
        heading.grid_propagate(False)
        heading.grid_columnconfigure(0, weight=1)
        self.structures_label = ctk.CTkLabel(
            heading, text=self.text("structures"), anchor="w", text_color=MUTED,
            font=font(size=12, weight="bold"))
        self.structures_label.grid(row=0, column=0, sticky="ew", padx=6)
        self.clear_all_button = ctk.CTkButton(
            heading, text=self.text("clear all"), width=84, height=22,
            corner_radius=11, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=MUTED, hover_color=BORDER,
            font=font(size=11), command=self.clear_all_structures)
        self.clear_all_button.grid(row=0, column=1, padx=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(
            panel, fg_color=("#E9EBEF", "#151920"), corner_radius=10)
        self.list_frame.grid(row=1, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        ## The + is a drawn glyph rather than a character in the text, so it can
        ## stand at the height of both lines beside it instead of sitting on the
        ## baseline of the first. The text is wrapped to the width the control
        ## actually gets, which is not known until it has been laid out.
        self.drop_zone = ctk.CTkButton(
            self.list_frame, text=self.text("dropfiles"),
            image=glyph("plus", DROP_PLUS, GLYPH_MUTED), compound="left",
            height=88, corner_radius=10, fg_color="transparent",
            border_width=2, border_color=BORDER, text_color=MUTED,
            hover_color=PANEL, font=font(size=15), anchor="center",
            command=self.browse_structures)
        self.drop_zone.configure(border_spacing=DROP_GAP)
        self.drop_zone.grid(row=999, column=0, sticky="ew", padx=8, pady=8)
        self._wrap_drop_text()

        if self.dnd_ready:
            for widget in (self.list_frame, self.drop_zone):
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", self._on_drop)
                    ## a drop target that does not react looks broken while a
                    ## file is hovering over it
                    widget.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                    widget.dnd_bind("<<DropLeave>>", self._on_drag_leave)
                except Exception:
                    pass

    def _highlight_drop(self, on):
        self.drop_zone.configure(border_color=AMBER if on else BORDER,
                                 text_color=TEXT if on else MUTED,
                                 fg_color=PANEL if on else "transparent")

    def _on_drag_enter(self, event):
        self._highlight_drop(True)
        return event.action

    def _on_drag_leave(self, event):
        self._highlight_drop(False)
        return event.action

    def _on_drop(self, event):
        self._highlight_drop(False)
        for path in self.tk.splitlist(event.data):
            if path.lower().endswith(".mcstructure"):
                self.add_structure_row(path)
        return event.action

    def browse_structures(self):
        chosen = filedialog.askopenfilenames(title=self.text("structurefile"),
                                             filetypes=STRUCTURE_TYPES)
        for path in chosen:
            self.add_structure_row(path)

    def add_structure_row(self, path):
        row = StructureRow(self.list_frame, self, path)
        row.grid(row=len(self.rows), column=0, sticky="ew", padx=8, pady=(8, 0))
        self.rows.append(row)
        self.name_after_structure(path)
        self.set_status(self.text("status added", os.path.basename(path)))
        self.select_row(row)
        self.revalidate()
        return row

    def name_after_structure(self, path):
        """Name the pack after the first structure, if it has no name yet.

        A pack is usually called what is in it, and typing that twice is work.
        Only the first structure, and only into an empty field: a name somebody
        typed is never written over.
        """
        if self.pack_name_var.get().strip():
            return
        if len([row for row in self.rows if row.path]) != 1:
            return
        self.pack_name_var.set(structure_name(path))

    def forget_structure_name(self, gone):
        """Drop a pack name that came from a structure once it is gone.

        Only when the list is empty and the name is still that file's, so a
        name typed over the suggestion, or one that outlived other structures,
        stays where it is.
        """
        if [row for row in self.rows if row.path]:
            return
        if self.pack_name_var.get().strip() in gone:
            self.pack_name_var.set("")

    def remove_structure(self, row):
        if row not in self.rows:
            return
        name = os.path.basename(row.path) or self.text("structures")
        gone = structure_name(row.path)
        self.rows.remove(row)
        row.destroy()
        self.forget_structure_name({gone})
        for index, remaining in enumerate(self.rows):
            remaining.grid_configure(row=index)
        if self.selected is row:
            self.selected = None
            if self.rows:
                self.select_row(self.rows[0])
            else:
                self.load_offset_fields([0, 0, 0])
        self.set_status(self.text("status removed", name))
        self.revalidate()

    def select_row(self, row):
        if self.big_build.get():
            return                      # the fields belong to big build mode
        if self.selected is not None and self.selected in self.rows:
            self.selected.set_selected(False)
        self.selected = row
        row.set_selected(True)
        self.load_offset_fields(row.offset)

    # --- settings panel ---------------------------------------------------

    def _build_settings_panel(self):
        panel = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, width=350)
        panel.grid(row=0, column=1, sticky="nsew", padx=(6, PAD), pady=(PAD, 6))
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        r = 0

        heading = ctk.CTkFrame(panel, fg_color="transparent", height=HEADING_HEIGHT)
        heading.grid(row=r, column=0, sticky="ew", padx=16, pady=HEADING_PAD); r += 1
        heading.grid_propagate(False)
        heading.grid_columnconfigure(0, weight=1)
        self.settings_label = ctk.CTkLabel(
            heading, text=self.text("settings"), anchor="w", text_color=MUTED,
            font=font(size=12, weight="bold"))
        self.settings_label.grid(row=0, column=0, sticky="ew")
        ## the panel is already titled Settings; the button only has to say what
        ## it does to them
        self.reset_button = ctk.CTkButton(
            heading, text=self.text("reset"), width=64, height=22,
            corner_radius=11, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=MUTED, hover_color=BORDER,
            font=font(size=11), command=self.reset_settings)
        self.reset_button.grid(row=0, column=1)

        # icon preview and pack name
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=r, column=0, sticky="ew", padx=16); r += 1
        head.grid_columnconfigure(1, weight=1)

        ## The preview, its frame and the clear corner are one control rather
        ## than a button inside a frame, so that the hover lights all of it and
        ## the outline belongs to the thing the pointer is over.
        ##
        ## A CTkButton grows to fit its content whatever width and height it is
        ## given, so the holder is a fixed box with propagation off and the
        ## button fills it. A click is measured against the control's real size,
        ## so a control that is not square puts the hit test out.
        icon_holder = self.icon_holder = ctk.CTkFrame(
            head, fg_color="transparent", width=ICON_SIZE, height=ICON_SIZE)
        ## no top padding: the control's top edge lines up with the pack name
        ## label beside it
        icon_holder.grid(row=0, column=0, rowspan=3, padx=(0, 10), pady=(0, 2),
                         sticky="n")
        icon_holder.grid_propagate(False)
        icon_holder.pack_propagate(False)

        ## The button draws nothing of its own: no fill, no border, no hover
        ## tint. The picture is the whole control and the widget only answers the
        ## click. A button that painted its own rounded background would put two
        ## curves of slightly different radii on top of each other, and one would
        ## show past the other.
        self.icon_button = ctk.CTkButton(
            icon_holder, text="", width=ICON_SIZE, height=ICON_SIZE,
            corner_radius=0, fg_color="transparent", hover=False,
            border_width=0, border_spacing=0, command=self.on_icon_clicked)
        self.icon_button.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        ## The clear corner is only drawn once a custom icon is chosen. There is
        ## nothing to clear before that, and an always-present button implies
        ## otherwise.
        ##
        ## There is no second widget over the corner. A CTkButton paints a
        ## "transparent" fill with the parent's colour rather than leaving it
        ## alone, so an overlay button covers the wedge with a solid box. The one
        ## control answers both jobs, and where the click lands decides which.
        self._icon_bound = set()
        self._bind_icon_pointer()

        self.name_label = ctk.CTkLabel(head, text=self.text("packname"), anchor="w",
                                       text_color=MUTED, font=font(size=12))
        self.name_label.grid(row=0, column=1, sticky="ew")

        self.pack_name_var = tkinter.StringVar()
        self.pack_name_var.trace_add("write", lambda *_: self.revalidate())
        self.pack_name_field = Field(head, self.pack_name_var, height=34)
        self.pack_name_field.grid(row=1, column=1, sticky="ew", pady=(4, 0))

        ## The hint holds its row whether or not it has anything to say, at a
        ## height of its own so the row does not change when it does. Removing
        ## it from the layout instead made everything below jump up and down as
        ## the pack name was typed and cleared.
        self.name_hint = ctk.CTkLabel(head, text="", anchor="w", text_color=MUTED,
                                      height=HINT_ROW, font=font(size=11))
        self.name_hint.grid(row=2, column=1, sticky="ew")
        self.refresh_icon_preview()

        # description
        desc = ctk.CTkFrame(panel, fg_color="transparent")
        ## no gap of its own above it: the pack name's hint row is already
        ## holding that space open, and holds it whether or not it is in use
        desc.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 0)); r += 1
        ## the label takes only the room its own text needs, so that "optional"
        ## lands against it rather than adrift in the middle of the row
        desc.grid_columnconfigure(0, weight=0)
        self.desc_label = ctk.CTkLabel(desc, text=self.text("description"),
                                       anchor="w", text_color=MUTED,
                                       font=font(size=12))
        self.desc_label.grid(row=0, column=0, sticky="w")
        ## said outright rather than left to be inferred from an empty field
        self.desc_optional = ctk.CTkLabel(desc, text=self.text("optional"),
                                          anchor="w", text_color=MUTED,
                                          font=font(size=11))
        self.desc_optional.grid(row=0, column=1, sticky="w", padx=(6, 0))
        desc.grid_columnconfigure(1, weight=1)
        self.desc_count = ctk.CTkLabel(desc, text="", anchor="e", text_color=MUTED,
                                       font=font(size=11))
        self.desc_count.grid(row=0, column=2, sticky="e")

        self.desc_var = tkinter.StringVar()
        self.desc_var.trace_add("write", lambda *_: self.on_description_typed())
        self.desc_field = Field(desc, self.desc_var, height=34,
                                on_clear=self.clear_description)
        self.desc_field.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.on_description_typed()

        # transparency
        trans = ctk.CTkFrame(panel, fg_color="transparent")
        trans.grid(row=r, column=0, sticky="ew", padx=16, pady=(14, 0)); r += 1
        trans.grid_columnconfigure(0, weight=1)
        self.trans_label = ctk.CTkLabel(trans, text=self.text("blocktransparency"),
                                        anchor="w", text_color=MUTED,
                                        font=font(size=12))
        self.trans_label.grid(row=0, column=0, sticky="ew")
        self.trans_value = ctk.CTkLabel(trans, text="", anchor="e", text_color=TEXT,
                                        font=font(size=12, weight="bold"))
        self.trans_value.grid(row=0, column=1, sticky="e")

        self.transparency = ctk.CTkSlider(
            trans, from_=0, to=settings.MAX_TRANSPARENCY, height=18,
            button_color=AMBER, button_hover_color=AMBER_HOVER,
            progress_color=AMBER, fg_color=BORDER, command=self.on_transparency)
        self.transparency.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.transparency.set(settings.transparency())
        self.on_transparency(settings.transparency())

        # offset, or the corner of a big build
        off = ctk.CTkFrame(panel, fg_color="transparent")
        off.grid(row=r, column=0, sticky="ew", padx=16, pady=(14, 0)); r += 1
        off.grid_columnconfigure((0, 1, 2), weight=1)
        self.offset_label = ctk.CTkLabel(off, text=self.text("offset"), anchor="w",
                                         text_color=MUTED, font=font(size=12))
        self.offset_label.grid(row=0, column=0, sticky="w", pady=(0, 4))
        ## the axis letter sits inside its own field rather than floating above
        ## it, so three numbers read as three labelled boxes and not six things
        self.offset_vars, self.offset_fields = [], []
        for i, axis in enumerate("xyz"):
            var = tkinter.StringVar(value="0")
            var.trace_add("write",
                          lambda *_, v=var: (self._clean_offset(v),
                                             self.on_offset_typed()))
            field = Field(off, var, label=self.text("axis %s" % axis), height=32)
            field.grid(row=1, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            self.offset_vars.append(var)
            self.offset_fields.append(field)

        ## Big build assembles several structures into one model, so its corner
        ## is the lowest world origin of all of them. The game records that
        ## origin inside each structure file.
        ##
        ## The button sits on the heading's own line, so turning big build mode
        ## on and off does not push the three fields up and down the panel.
        self.cords_button = ctk.CTkButton(
            off, text=self.text("getcords"), height=22, width=CORDS_WIDE,
            corner_radius=11, image=glyph("corner", 12), compound="left",
            fg_color="transparent", border_width=1, border_color=BORDER,
            text_color=MUTED, hover_color=BORDER, font=font(size=11),
            command=self.get_global_cords)

        # switches
        self.big_build = tkinter.IntVar()
        self.block_lists = tkinter.IntVar()
        ## Remembered between runs, because it describes the machine the packs
        ## are viewed on rather than any one pack. Full detail is the default.
        self.low_geometry = tkinter.IntVar(value=int(settings.low_geometry()))

        switches = ctk.CTkFrame(panel, fg_color="transparent")
        switches.grid(row=r, column=0, sticky="ew", padx=16, pady=(16, 0)); r += 1
        switches.grid_columnconfigure(0, weight=1)

        self.switches = [
            self._switch(switches, 0, "bigbuild", self.big_build, self.on_big_build),
            self._switch(switches, 1, "lists", self.block_lists, None),
            self._switch(switches, 2, "lowgeo", self.low_geometry,
                         self.on_low_geometry, help_key="lowgeo help"),
        ]

        ## Three answers rather than two: leave TechPack alone, declare it so a
        ## separately installed copy still works, or carry the whole thing.
        tech = ctk.CTkFrame(switches, fg_color="transparent")
        tech.grid(row=3, column=0, sticky="ew", pady=5)
        ## as with the switches: the label hugs its text so the ? lands against
        ## the words, and the gap before the menu is its own column
        tech.grid_columnconfigure(0, weight=0)
        tech.grid_columnconfigure(2, weight=1)
        self.tech_label = ctk.CTkLabel(tech, text=self.text("techpack"),
                                       anchor="w", text_color=TEXT,
                                       font=font(size=13))
        self.tech_label.grid(row=0, column=0, sticky="w")
        self.tech_mark = ctk.CTkLabel(
            tech, text="?", width=HELP_DOT, height=HELP_DOT,
            corner_radius=HELP_DOT // 2, fg_color=FIELD, text_color=MUTED,
            cursor="hand2", font=font(size=11, weight="bold"))
        self.tech_mark.grid(row=0, column=1, padx=(6, 0), sticky="w")
        draw_every_pixel(self.tech_mark)
        self.tech_mark.tip = Tooltip(self.tech_mark, self,
                                     self.text("techpack help"))
        self.tech_pack = Chooser(
            tech, self, settings.TECH_PACK_MODES, self.on_tech_pack,
            labels=lambda mode: self.text(TECH_PACK_LABELS[mode]), badges=False,
            width=CHOOSER_THEME_WIDE, height=CHOOSER_TALL)
        self.tech_pack.grid(row=0, column=3, sticky="e")
        self.tech_pack.set(settings.settings["tech_pack"]
                           if tech_pack.available() else "none")

        panel.grid_rowconfigure(r, weight=1); r += 1

        ## where the finished pack lands, next to the button that makes it
        out = ctk.CTkFrame(panel, fg_color="transparent")
        out.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 2)); r += 1
        out.grid_columnconfigure(0, weight=1)
        self.output_label = ctk.CTkLabel(out, text=self.text("output folder"),
                                         anchor="w", text_color=MUTED,
                                         font=font(size=12))
        self.output_label.grid(row=0, column=0, sticky="ew")
        self.output_button = ctk.CTkButton(
            out, text="", height=32, corner_radius=8, anchor="w",
            image=glyph("folder", 15), compound="left",
            fg_color=FIELD, hover_color=BORDER, border_width=1,
            border_color=BORDER, text_color=TEXT,
            font=font(size=11), command=self.browse_output)
        self.output_button.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.refresh_output_button()

        self.make_button = ctk.CTkButton(
            panel, text=self.text("makepack"), height=46, corner_radius=10,
            fg_color=AMBER, hover_color=AMBER_HOVER, text_color=ON_AMBER,
            font=font(size=15, weight="bold"), command=self.make_pack)
        self.make_button.grid(row=r, column=0, sticky="ew", padx=16, pady=(12, 16))

    def _switch(self, parent, row, key, variable, command, help_key=None):
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=0, sticky="ew", pady=5)
        ## The label takes only the room its own text needs and the gap between
        ## the two is its own column, so that the ? sits against the end of the
        ## words rather than being carried across to the switch.
        holder.grid_columnconfigure(0, weight=0)
        holder.grid_columnconfigure(2, weight=1)
        label = ctk.CTkLabel(holder, text=self.text(key), anchor="w",
                             text_color=TEXT, font=font(size=13))
        label.grid(row=0, column=0, sticky="w")

        mark = None
        if help_key:
            ## a ? beside the label rather than the sentence itself: the panel
            ## has no room for a paragraph against every switch
            mark = ctk.CTkLabel(holder, text="?", width=HELP_DOT,
                                height=HELP_DOT, corner_radius=HELP_DOT // 2,
                                fg_color=FIELD, text_color=MUTED,
                                cursor="hand2", font=font(size=11, weight="bold"))
            mark.grid(row=0, column=1, padx=(6, 0), sticky="w")
            draw_every_pixel(mark)
            mark.tip = Tooltip(mark, self, self.text(help_key))

        switch = ctk.CTkSwitch(holder, text="", variable=variable, width=46,
                               progress_color=AMBER,
                               button_color=("#FFFFFF", "#E9ECF2"),
                               command=command)
        switch.grid(row=0, column=3, sticky="e")
        switch.label = label
        switch.mark = mark
        switch.help_key = help_key
        switch.key = key
        return switch

    # --- footer -----------------------------------------------------------

    def _build_footer(self):
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10, height=44)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(0, PAD))
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bar, text="", anchor="w", text_color=MUTED,
                                         font=font(size=12))
        self.status_label.grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        self.help_button = ctk.CTkButton(
            bar, text="?", width=30, height=28, corner_radius=8,
            fg_color="transparent", hover_color=BORDER, text_color=MUTED,
            font=font(size=14, weight="bold"), command=self.open_help)
        self.help_button.grid(row=0, column=1, padx=(4, 2), pady=8)

        self.about_button = ctk.CTkButton(
            bar, text="i", width=30, height=28, corner_radius=8,
            fg_color="transparent", hover_color=BORDER, text_color=MUTED,
            font=font(size=14, weight="bold"),
            command=lambda: AboutDialog(self))
        self.about_button.grid(row=0, column=2, padx=(0, 6), pady=8)

        self.theme_menu = Chooser(
            bar, self, settings.THEMES, self.on_theme,
            labels=self.text, badges=False, width=CHOOSER_THEME_WIDE)
        self.theme_menu.set(settings.settings["theme"])
        self.theme_menu.grid(row=0, column=3, padx=(0, 6), pady=8)

        ## the picker carries codes and shows each language's own name for
        ## itself, which is the one thing a reader looking for it will know
        self.language_menu = Chooser(bar, self, settings.choices(),
                                     self.on_language,
                                     labels=settings.language_name)
        self.language_menu.set(settings.settings["lang"])
        self.language_menu.grid(row=0, column=4, padx=(4, 12), pady=8)

        self.set_status(self.text("status ready"))

        ## An update left the build it replaced behind, because a running file
        ## cannot delete itself. When this launch is the one the update started,
        ## that build is still shutting down, so the wait happens off the main
        ## thread and the window does not stop for it.
        threading.Thread(target=updates.clear_displaced,
                         args=(updates.PATIENCE,), daemon=True).start()
        if settings.check_updates():
            self.check_for_updates()

    def refresh_icon_preview(self):
        """Redraw the control: background, preview, frame, cut corner.

        Built at the display's own pixel count rather than at the logical size,
        because CustomTkinter scales a picture up to fill the widget. A 102 px
        drawing stretched to 127 px softens the frame and the cut corner until
        they look broken.
        """
        custom = self._icon_is_custom()
        try:
            art = Image.open(self.icon_path).convert("RGBA")
        except Exception:
            self.icon_button.configure(text="!", text_color=DANGER, image=None)
            return

        edge = ICON_SIZE
        scaling = 1.0
        try:
            scaling = self.icon_button._get_widget_scaling() or 1.0
        except Exception:
            pass
        ## the widget's own width is the number of pixels the picture will be
        ## painted into; rounding the logical size instead can land a pixel out
        ## and make CustomTkinter resample a drawing that was already the right
        ## size
        measured = self.icon_button.winfo_width()
        pixels = measured if measured > 16 else max(16, int(round(edge * scaling)))
        self._icon_pixels = pixels

        picture = ui_icons.icon_control(
            pixels, radius=ICON_RADIUS * scaling, art=art,
            background=mode_colour(FIELD), line=mode_colour(BORDER),
            width=int(ICON_BORDER * scaling), cut=custom,
            ## The cut corner is the panel the control sits on, showing through
            ## where the icon's corner has been folded away, outlined in the same
            ## border colour as the frame. The X is the muted grey every other
            ## secondary label in the window uses. Under the pointer both step up
            ## one place in the same palette, to border and full text, so the
            ## corner answers the way the rest of the window does.
            wedge=mode_colour(PANEL), mark=mode_colour(MUTED),
            hot_wedge=mode_colour(BORDER), hot_mark=mode_colour(TEXT),
            hot_control=getattr(self, "_icon_over", False),
            hot_corner=custom and getattr(self, "_icon_hot", False))

        self.icon_button.configure(
            text="", image=ctk.CTkImage(light_image=picture, dark_image=picture,
                                        size=(edge, edge)))
        if getattr(self, "_icon_bound", None) is not None:
            self._bind_icon_pointer()

    # --- handlers ---------------------------------------------------------

    def refresh_output_button(self):
        """Show the tail of the path: the start is the same for everybody."""
        shown = settings.output_dir()
        if len(shown) > 36:
            shown = "..." + shown[-33:]
        self.output_button.configure(text="  " + shown)

    def browse_output(self):
        folder = filedialog.askdirectory(title=self.text("choose folder"),
                                         initialdir=settings.output_dir())
        if folder:
            settings.set_output_dir(folder)
            self.refresh_output_button()
            self.set_status(self.text("status output", folder))

    def open_help(self):
        open_link(GITHUB_ISSUES)
        self.set_status(GITHUB_ISSUES)

    def _bind_icon_pointer(self):
        """Put the pointer handlers on every part of the button.

        A CTkButton is a canvas with a label placed over it, and its bind()
        passes the binding on to whichever of those exist at the time. The
        image label is not made until an image is first configured, so a
        binding made while the button is being built reaches only the canvas --
        and once the picture is set, the label covers all of the control but a
        one pixel rim, which is the only place the pointer was being seen.

        Called again after every redraw, since configuring an image can make
        the label; the set remembers what is already bound so nothing is bound
        twice.
        """
        parts = (self.icon_button._canvas,
                 getattr(self.icon_button, "_image_label", None),
                 getattr(self.icon_button, "_text_label", None))
        for part in parts:
            if part is None or part in self._icon_bound:
                continue
            self._icon_bound.add(part)
            part.bind("<Button-1>", self._track_icon_pointer, add="+")
            part.bind("<Motion>", self._track_icon_pointer, add="+")
            part.bind("<Enter>", self._track_icon_pointer, add="+")
            part.bind("<Leave>", self._leave_icon, add="+")

    def _wrap_drop_text(self):
        """Wrap the drop zone's sentence to a fixed width.

        A width in pixels, not a share of the room the control was given. The
        control's width is not settled while the window is being laid out, so
        wrapping to it rewraps the sentence, and resizes the + beside it, on
        every step of a resize, which shows as flicker.
        """
        label = getattr(self.drop_zone, "_text_label", None)
        if label is None:
            return
        try:
            label.configure(
                wraplength=int(DROP_WRAP * self._scaling()), justify="left")
        except Exception:
            pass

    def _icon_extent(self):
        """The control's size in real pixels, which a click is measured against."""
        return int(round(ICON_SIZE * self._scaling()))

    def _scaling(self):
        """The display's scaling, asked of the window rather than a widget.

        A widget answers only once it exists, and this is wanted while the
        window is still being built. Asking the icon control quietly returns
        1.0 to everything laid out before it.
        """
        try:
            return ctk.ScalingTracker.get_widget_scaling(self) or 1.0
        except Exception:
            return 1.0

    def _pointer_over_icon(self):
        """Where the pointer is within the control, and whether it is inside.

        Worked out from the pointer's position on the screen rather than from
        an event's own coordinates, because the event may have come from the
        canvas or from the label placed over it, and those two do not share an
        origin. The label sits a pixel in from the button's corner.
        """
        button = self.icon_button
        try:
            x = button.winfo_pointerx() - button.winfo_rootx()
            y = button.winfo_pointery() - button.winfo_rooty()
        except Exception:
            return 0, 0, False
        size = self._icon_extent()
        return x, y, 0 <= x < size and 0 <= y < size

    def _over_wedge(self, x, y):
        return ui_icons.in_wedge(x, y, self._icon_extent())

    def _track_icon_pointer(self, _event=None):
        """Light the background, and the corner when the pointer is in it."""
        x, y, inside = self._pointer_over_icon()
        if not inside:
            return self._leave_icon()
        corner = self._icon_is_custom() and self._over_wedge(x, y)
        if (corner, True) != (getattr(self, "_icon_hot", False),
                              getattr(self, "_icon_over", False)):
            self._icon_hot = corner
            self._icon_over = True
            self.refresh_icon_preview()

    def _leave_icon(self, _event=None):
        ## leaving the canvas for the label over it is not leaving the control
        if self._pointer_over_icon()[2]:
            return
        if getattr(self, "_icon_hot", False) or getattr(self, "_icon_over", False):
            self._icon_hot = False
            self._icon_over = False
            self.refresh_icon_preview()

    def _icon_is_custom(self):
        return os.path.abspath(self.icon_path) != os.path.abspath(self.default_icon)

    def on_icon_clicked(self):
        """The corner clears the icon; anywhere else chooses one."""
        x, y, _inside = self._pointer_over_icon()
        if self._icon_is_custom() and self._over_wedge(x, y):
            self.clear_icon()
        else:
            self.browse_icon()

    def browse_icon(self):
        path = filedialog.askopenfilename(title=self.text("icon"),
                                          filetypes=IMAGE_TYPES)
        if path:
            self.icon_path = path
            self.refresh_icon_preview()
            self.set_status(self.text("status icon", os.path.basename(path)))

    def check_for_updates(self):
        """Ask GitHub whether there is a newer build, without holding anything up.

        Off the main thread, because it is a network call, and quiet about
        every way of failing: somebody opening the program to build a pack does
        not want to hear that an update check timed out.
        """
        def ask():
            try:
                found = updates.available()
            except Exception:
                found = None
            if found:
                self.after(0, lambda: self.offer_update(found))

        threading.Thread(target=ask, daemon=True).start()

    def offer_update(self, tag):
        """Put the choice in front of the person: take it now, or not."""
        ## remembered so the About dialog can say a release is out even after
        ## this prompt has been dismissed
        self.available_update = tag
        if getattr(self, "update_dialog", None) is not None:
            try:
                if self.update_dialog.winfo_exists():
                    self.update_dialog.lift()
                    return
            except Exception:
                pass
        self.update_dialog = UpdateDialog(self, tag)

    def clear_all_structures(self):
        """Empty the list in one go rather than a row at a time."""
        if not self.rows:
            return
        count = len(self.rows)
        gone = {structure_name(row.path) for row in self.rows if row.path}
        for row in list(self.rows):
            row.destroy()
        self.rows = []
        self.selected = None
        self.forget_structure_name(gone)
        self.stashed_tags.clear()
        self.load_offset_fields([0, 0, 0])
        self.set_status(self.text("status cleared",
                                  "%d %s" % (count, self.text("structures"))))
        self.revalidate()

    def clear_description(self):
        self.desc_var.set("")
        self.set_status(self.text("clear description"))

    def reset_settings(self):
        """Put the settings panel back to how it opens.

        The output folder is left alone deliberately, because it is a place on
        the user's disk they chose once rather than a setting for this pack. So
        are the pack name, the structure list, the theme and the language.
        """
        self.desc_var.set("")
        self.transparency.set(settings.DEFAULT_TRANSPARENCY)
        self.on_transparency(settings.DEFAULT_TRANSPARENCY)
        self.icon_path = self.default_icon
        self.refresh_icon_preview()
        if self.big_build.get():
            self.big_build.set(0)
            self.on_big_build()
        self.tech_pack.set(settings.set_tech_pack("none"))
        self.block_lists.set(0)
        self.low_geometry.set(int(settings.set_low_geometry(False)))
        self.big_offset = [0, 0, 0]
        for row in self.rows:
            row.offset = [0, 0, 0]
        self.load_offset_fields([0, 0, 0])
        self.set_status(self.text("status reset"))
        self.revalidate()

    def clear_icon(self):
        self._icon_hot = False
        self.icon_path = self.default_icon
        self.refresh_icon_preview()
        self.set_status(self.text("clear icon"))

    def on_description_typed(self):
        text = self.desc_var.get()
        if len(text) > manifest.DESCRIPTION_LIMIT:
            self.desc_var.set(text[:manifest.DESCRIPTION_LIMIT])
            return
        self.desc_count.configure(
            text="%d/%d" % (len(text), manifest.DESCRIPTION_LIMIT),
            text_color=DANGER if len(text) == manifest.DESCRIPTION_LIMIT else MUTED)

    def on_transparency(self, value):
        self.trans_value.configure(text="%d%%" % round(float(value)))
        ## Remembered like the theme and the low geometry switch: how far
        ## through a ghost block somebody wants to see is about their eyes and
        ## their screen, not about the pack, and it does not change from one
        ## structure to the next.
        settings.set_transparency(value)

    def _clean_offset(self, var):
        """Keep an offset field to digits with at most one leading minus.

        Typing a letter into a coordinate silently became a zero, so a typo
        moved the model without saying anything. Rejecting the character as it
        is typed is the only version of this the user can see.
        """
        if self._sanitising:
            return
        raw = var.get()
        cleaned = re.sub(r"[^0-9-]", "", raw)
        cleaned = ("-" if cleaned.startswith("-") else "") + cleaned.replace("-", "")
        if cleaned != raw:
            self._sanitising = True
            var.set(cleaned)
            self._sanitising = False

    def on_offset_typed(self):
        target = self.big_offset if self.big_build.get() else (
            self.selected.offset if self.selected in self.rows else None)
        if target is None:
            return
        for i, var in enumerate(self.offset_vars):
            try:
                target[i] = int(var.get() or 0)
            except ValueError:
                target[i] = 0

    def load_offset_fields(self, offset):
        for var, value in zip(self.offset_vars, offset):
            var.set(str(value))

    def get_global_cords(self):
        """Fill the corner with the lowest world origin of every structure.

        Each .mcstructure records where in the world it was taken from. A big
        build is several of them assembled, so the corner of the whole thing is
        the smallest origin across the set. That puts the ghost model back where
        the pieces came from, instead of making the user read coordinates off
        the structure blocks and type them in.
        """
        files = [row.path for row in self.rows if row.path]
        if not files:
            self.set_status(self.text("need structure"), warn=True)
            return
        lowest = None
        for path in files:
            try:
                data = nbtlib.load(path, byteorder="little")
                if "" in data.keys():
                    data = data[""]
                origin = numpy.array(list(map(int, data["structure_world_origin"])))
            except Exception as exc:
                self.set_status(self.text("status failed", exc), warn=True)
                return
            lowest = origin if lowest is None else numpy.minimum(lowest, origin)
        self.big_offset = [int(v) for v in lowest]
        self.load_offset_fields(self.big_offset)
        self.set_status("%s: %d, %d, %d" % ((self.text("corner"),) +
                                            tuple(self.big_offset)))

    def on_tech_pack(self, mode):
        """Remember the choice, unless there is no TechPack to choose."""
        if mode != "none" and not tech_pack.available():
            self.tech_pack.set("none")
            settings.set_tech_pack("none")
            self.set_status(self.text("techpack missing"))
            return
        settings.set_tech_pack(mode)
        self.revalidate()

    def on_low_geometry(self):
        """Remember the choice, which outlives this pack and this session."""
        settings.set_low_geometry(bool(self.low_geometry.get()))

    def on_big_build(self):
        """Swap the offset fields and the name tags without losing either.

        Big build mode has one corner for the whole pack and names its models
        itself, so the per-structure fields have nowhere to go while it is on.
        Their values are put aside here and handed back when it is turned off,
        so flipping the switch twice leaves the window exactly as it was.
        """
        on = bool(self.big_build.get())
        if on:
            if self.selected is not None and self.selected in self.rows:
                self.selected.set_selected(False)
            for row in self.rows:
                self.stashed_tags[row] = row.tag_var.get()
                row.tag_var.set("")
                row.set_tag_enabled(False)
            self.offset_label.configure(text=self.text("corner"))
            self.load_offset_fields(self.big_offset)
            ## across two of the three columns: one of them is a third of the
            ## panel, which is narrower than this button's longest translation
            self.cords_button.grid(row=0, column=1, columnspan=2, sticky="e",
                                   pady=(0, 4))
        else:
            for row in self.rows:
                row.set_tag_enabled(True)
                if row in self.stashed_tags:
                    row.tag_var.set(self.stashed_tags.pop(row))
            self.offset_label.configure(text=self.text("offset"))
            self.cords_button.grid_forget()
            if self.rows:
                self.select_row(self.selected if self.selected in self.rows
                                else self.rows[0])
            else:
                self.load_offset_fields([0, 0, 0])
        self.revalidate()

    def on_theme(self, name):
        ctk.set_appearance_mode(resolve_theme(settings.set_theme(name)))
        ## the icon's frame is drawn, not styled, so it has to be redrawn to
        ## follow the theme
        self.refresh_icon_preview()
        self.set_status(self.text("status theme", self.text(name)))

    def on_language(self, code):
        self.strings = settings.set_language(code)
        ## keep the control in step: it is already right when the user picked
        ## from it, but not when the language is set from anywhere else
        self.language_menu.set(code)
        restyle_fonts(code)
        ## the box is sized from measured text, and the measurement changed
        ## with the face
        self.language_menu.refit()
        self.retranslate()
        self.set_status(self.text("status language",
                                  settings.language_name(code)))

    def retranslate(self):
        """Relabel everything in place, without rebuilding the window."""
        self.structures_label.configure(text=self.text("structures"))
        self.settings_label.configure(text=self.text("settings"))
        ## the + is a glyph beside the text now, not a character in it
        self.drop_zone.configure(text=self.text("dropfiles"))
        self._wrap_drop_text()
        self.name_label.configure(text=self.text("packname"))
        self.desc_label.configure(text=self.text("description"))
        self.trans_label.configure(text=self.text("blocktransparency"))
        self.offset_label.configure(text=self.text(
            "corner" if self.big_build.get() else "offset"))
        for axis, field in zip("xyz", self.offset_fields):
            field.set_label(self.text("axis %s" % axis))
        self.cords_button.configure(text=self.text("getcords"))
        self.output_label.configure(text=self.text("output folder"))
        self.clear_all_button.configure(text=self.text("clear all"))
        self.reset_button.configure(text=self.text("reset"))
        self.desc_optional.configure(text=self.text("optional"))
        self.make_button.configure(text=self.text("makepack"))
        for switch in self.switches:
            switch.label.configure(text=self.text(switch.key))
            ## the explanation is held by the tooltip, not by a widget, so it
            ## has to be handed the new wording rather than relabelled
            if switch.mark is not None:
                switch.mark.tip.text = self.text(switch.help_key)
        self.tech_label.configure(text=self.text("techpack"))
        self.tech_mark.tip.text = self.text("techpack help")
        self.tech_pack.refit()
        self.theme_menu.refit()
        self.refresh_output_button()
        self.revalidate()

    # --- validation -------------------------------------------------------

    def revalidate(self):
        """Re-check every required field and show the result as the user types.

        A name tag is optional while there is one structure and required from
        the second onwards, so adding or removing a file changes what the other
        rows are asking for, which is why this runs over all of them rather than
        over the field that changed.
        """
        filled = [row for row in self.rows if row.path]
        tags_required = len(filled) > 1 and not self.big_build.get()

        ## a tag used twice is wrong on both rows, so both are marked
        counts = {}
        for row in filled:
            if row.tag:
                counts[row.tag] = counts.get(row.tag, 0) + 1
        duplicated = {tag for tag, n in counts.items() if n > 1}

        for row in self.rows:
            if self.big_build.get():
                ## the tags are put away in big build mode, so there is nothing
                ## for the hint to be asking for
                row.tag_hint.configure(text="")
                row.tag_field.flag(False)
                continue
            wrong = tags_required and (not row.tag or row.tag in duplicated)
            row.set_tag_state(tags_required, wrong)

        problem = None
        if not filled:
            problem = self.text("need structure")
        elif not self.pack_name_var.get().strip():
            problem = self.text("need pack name")
        elif tags_required and any(not row.tag for row in filled):
            problem = self.text("need nametag")
        elif tags_required and duplicated:
            problem = self.text("duplicate nametag")

        missing_name = not self.pack_name_var.get().strip()
        self.pack_name_field.flag(missing_name)
        self.name_hint.configure(
            text=self.text("need pack name") if missing_name else "",
            text_color=DANGER)

        self.make_button.configure(
            state="disabled" if problem else "normal",
            fg_color=BORDER if problem else AMBER,
            text_color=MUTED if problem else ON_AMBER)
        self.problem = problem
        ## a finished build's message stays until the user does something else;
        ## re-validating on the way out of a build would otherwise wipe the one
        ## line that says it worked
        if not self.building and not (self.sticky_status and problem is None):
            self.set_status(problem or self.text("status ready"),
                            warn=problem is not None)
        return problem is None

    def set_status(self, message, warn=False, good=False, sticky=False):
        """The status line always says what just happened or what is wrong.

        `sticky` holds a message in place until the next thing the user does,
        so the line reporting a finished pack is still there to read.
        """
        self.sticky_status = sticky
        colour = DANGER if warn else (OK if good else MUTED)
        self.status_label.configure(text=message, text_color=colour)

    # --- building ---------------------------------------------------------

    def list_tags(self):
        """The name tags the block list files would be written under.

        The worker names an untagged model after its position, so the files it
        writes are only predictable if the same rule is applied here.
        """
        models = [row for row in self.rows if row.path]
        if self.big_build.get():
            ## a big build is one model and one list, and it carries no tag
            return None
        return [row.tag or ("" if len(models) == 1 else str(index))
                for index, row in enumerate(models)]

    def settle_collisions(self, folder, name):
        """Ask before writing over anything, and hand back the name to build
        under. None means the build was called off.

        A renamed pack is checked again, since the name typed in may collide
        with something too.
        """
        big = bool(self.big_build.get())
        lists = bool(self.block_lists.get())
        tags = self.list_tags() or []
        def collides(candidate):
            written = core.outputs(os.path.join(folder, candidate),
                                   tags, lists, big)
            return any(os.path.exists(path) for path in written)

        while True:
            target = os.path.join(folder, name)
            clashes = [path for path in core.outputs(target, tags, lists, big)
                       if os.path.exists(path)]
            if not clashes:
                return name
            dialog = OverwriteDialog(self, folder, name, clashes,
                                     free_name(folder, name, collides))
            self.wait_window(dialog)
            if dialog.answer == "overwrite":
                return name
            if dialog.answer == "rename":
                name = dialog.chosen
                self.pack_name_var.set(name)
                self.revalidate()
                continue
            return None

    def make_pack(self):
        if self.building or not self.revalidate():
            return
        ## scaffold() takes a path, and the last part of it is the pack name,
        ## so the chosen folder simply prefixes it. The folder is created here
        ## rather than in the worker so a permissions problem is reported before
        ## anything else has been done.
        folder = settings.output_dir()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            self.set_status(self.text("status failed", exc), warn=True)
            self.revalidate()
            return
        ## asked before the build starts rather than at the end of it, so a
        ## build nobody wanted is never run
        name = self.settle_collisions(folder, self.pack_name_var.get().strip())
        if not name:
            self.set_status(self.text("status cancelled"), warn=True,
                            sticky=True)
            return
        self.building = True
        self.cancelled = False
        self.make_button.configure(state="disabled")
        ## The settings file has been observed to come back changed after a
        ## build -- the window reopening in the machine's language rather than
        ## the chosen one. A build has no business touching it, so its exact
        ## bytes are kept here and put back when the build ends.
        self._snapshot_settings()
        job = {
            "folder": folder,
            "pack_name": name,
            "description": self.desc_var.get().strip(),
            "list header": self.text("list header"),
            "list footer": self.text("list footer"),
            "icon": self.icon_path,
            "alpha": settings.transparency_to_alpha(self.transparency.get()),
            "low_geometry": bool(self.low_geometry.get()),
            "tech_pack": self.tech_pack.get(),
            "big_build": bool(self.big_build.get()),
            "block_lists": bool(self.block_lists.get()),
            "big_offset": list(self.big_offset),
            "models": [(row.tag, row.path, list(row.offset))
                       for row in self.rows if row.path],
        }
        threading.Thread(target=self._build_worker, args=(job,), daemon=True).start()

    def _build_worker(self, job):
        """Runs off the main thread; every message goes back through the queue."""
        pack = None
        try:
            pack = core.Scaffold(
                os.path.join(job["folder"], job["pack_name"]))
            ## a file another program holds open stops the build rather than
            ## losing it; the question is answered on the main thread
            pack.set_retry(self._ask_to_retry)
            pack.set_opacity(job["alpha"])
            pack.set_description(job["description"])
            pack.set_list_labels(job["list header"], job["list footer"])
            if job["icon"]:
                pack.set_icon(job["icon"])
            if job["low_geometry"]:
                pack.set_low_geometry(True)
            if job["tech_pack"] and job["tech_pack"] != "none":
                pack.set_tech_pack(job["tech_pack"])

            for index, (tag, path, offset) in enumerate(job["models"]):
                name = tag or ("" if len(job["models"]) == 1 else str(index))
                self.events.put(("status", self.text(
                    "status reading", os.path.basename(path))))
                pack.add_model(name, path)
                pack.set_model_offset(name, offset)

            self.events.put(("status", self.text("status building", job["pack_name"])))
            if job["big_build"]:
                pack.make_big_model(job["big_offset"])
                if job["block_lists"]:
                    pack.make_big_blocklist()
            else:
                pack.generate_with_nametags()
                if job["block_lists"]:
                    pack.make_nametag_block_lists()

            self.events.put(("status", self.text("status packing", job["pack_name"])))
            skipped = pack.get_skipped(write_file=True)
            path = pack.compile_pack(overwrite=True)
            self.events.put(("done", (path, skipped, job["pack_name"])))
        except Exception as exc:
            if pack is not None:
                pack.cleanup()
            if self.cancelled:
                self.events.put(("cancelled", None))
            else:
                self.events.put(("failed", "%s: %s" % (type(exc).__name__, exc)))

    def _ask_to_retry(self, exc, path):
        """Called on the worker thread, answered on the main one.

        Tk is not thread safe, so the question goes through the same queue
        everything else does and the worker waits on a queue of its own for the
        answer. Nothing is drained while the dialog is up, which is what the
        build wants: it is stopped on this one file until the user says.
        """
        answer = queue.Queue(maxsize=1)
        self.events.put(("ask", (exc, path, answer)))
        return answer.get()

    def _drain_events(self):
        """The worker's messages, applied on the main thread where Tk wants them."""
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.set_status(payload)
                elif kind == "done":
                    self._build_finished(*payload)
                elif kind == "ask":
                    exc, path, answer = payload
                    again = False
                    try:
                        dialog = RetryDialog(self, path, exc)
                        self.wait_window(dialog)
                        again = bool(dialog.answer)
                    finally:
                        ## the worker is waiting on this and nothing else will
                        ## release it, so it is answered even if the dialog
                        ## could not be put on screen
                        ##
                        ## the worker will raise the write's own error; the flag
                        ## is what tells the failure handler it was asked for
                        self.cancelled = not again
                        answer.put(again)
                elif kind == "cancelled":
                    self.building = False
                    self._restore_settings()
                    self.set_status(self.text("status cancelled"), warn=True,
                                    sticky=True)
                    self.revalidate()
                elif kind == "failed":
                    self.building = False
                    self._restore_settings()
                    self.set_status(self.text("status failed", payload), warn=True)
                    ResultDialog(self, self.text("error"), [payload], None)
                    self.revalidate()
        except queue.Empty:
            pass
        self.after(120, self._drain_events)

    def _snapshot_settings(self):
        """Keep the settings file's exact bytes for the length of a build."""
        self._settings_snapshot = None
        try:
            path = settings.settings_file()
            with open(path, "rb") as handle:
                self._settings_snapshot = (path, handle.read())
        except OSError:
            ## no file yet, or unreadable; nothing to protect
            pass

    def _restore_settings(self):
        """Put the settings file back if the build changed it, and reload.

        A build does not touch settings, so any difference here is a fault
        elsewhere writing over them. The bytes are restored verbatim and
        settings.load() is re-run so the in-memory copy matches the disk.
        """
        snapshot = getattr(self, "_settings_snapshot", None)
        self._settings_snapshot = None
        if not snapshot:
            return
        path, data = snapshot
        try:
            current = None
            if os.path.isfile(path):
                with open(path, "rb") as handle:
                    current = handle.read()
            if current == data:
                return
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError:
            return
        settings.load()

    def _build_finished(self, path, skipped, pack_name):
        self.building = False
        self._restore_settings()
        self.set_status(self.text("status built", os.path.basename(path)),
                        good=True, sticky=True)
        lines = [os.path.abspath(path)]
        count = sum(sum(v.values()) for v in skipped.values())
        if count:
            lines.append(self.text("status skipped", count))
        ResultDialog(self, self.text("pack built"), lines,
                     os.path.dirname(os.path.abspath(path)) or ".",
                     reveal=os.path.abspath(path))
        self.revalidate()


def run():
    App().mainloop()
