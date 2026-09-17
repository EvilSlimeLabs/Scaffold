# Changelog

What each release changed, and what an update offers. `build.py --publish`
reads the section for the version it is signing in and puts it in the update
metadata, so this file is what the update dialog shows.

A heading names the version, with or without a `v` and with or without a date
after it. Everything up to the next heading is that release's note.

Write it for somebody who builds in Minecraft and has never seen this code.
Only what a user would notice, in plain words -- no file names, no identifiers,
no jargon. A paragraph, not a document: it is read in a dialog that cannot
scroll. If an update needs anything doing, such as a pack being rebuilt or
re-applied, say that first.

## 1.1.2

Glow berry vines show their berries, and fence gates are drawn open when they
are open, swinging to the side they swing to rather than always the same way.
The books in a chiseled bookshelf sit properly in their slots. Doors and
trapdoors no longer carry a hinge along every edge: their tops and bottoms are
plain, one side has the hinge and the other the handle. The straw bed's blanket
is the right way round. Cushions now show up in big builds as well as ordinary
ones, and one sitting on a snow layer rests on top of it instead of sinking
into it. The poplar hanging sign has its own picture again. A finished pack can
be installed straight into Minecraft from the window that says it is built, and
it tells you when it has, including that Minecraft needs restarting before the
pack appears. An update now tells you what it changes before you take it, and
packs built from the command line are saved in the folder you ran it in.

## 1.1.1

Fixed a crash in Minecraft when building from a large structure. Every texture
a pack uses became one tile in a single column, so a structure with a thousand
distinct blocks shipped a texture 25,000 pixels tall -- past what a graphics
card will hold. The tiles are laid out in a grid instead.

## 1.1.0

Reads Minecraft 26.50's structure files and the 121 blocks it added: wool and
concrete slabs, stairs and double slabs, the poplar wood set, the shelf
mushroom, the straw bed and the red shrub. Cushions are drawn too, and block
lists now name every block instead of falling back to raw ids.
