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
re-applied, say that first. Be succinct; too long and people won't bother to read it.

## 1.2.0

New Tweaks menu: apply certain textures from Bedrock Tweaks. Pistons now show extended if they are. Water is now translucent. Fixed lectern and hopper visuals.

## 1.1.2

Fixed visuals for glow berries, open fence gates, bookshelf books, doors, trapdoors, straw beds, and poplar hanging signs. Cushions show up in big builds. Added a button to install packs directly into Minecraft.

## 1.1.1

Fixed a crash when exporting massive builds. Texture layouts were converted into a compact grid so giant builds no longer overwhelm your graphics card.

## 1.1.0

Adds full support for Minecraft 26.50 structures and its 121 new blocks. Block lists now name every block in categories.