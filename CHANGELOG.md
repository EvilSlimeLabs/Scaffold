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

## 1.4.0

Structure files saved by Minecraft 26.60 and later, which the game now compresses, can be opened. Older structure files open as before.

## 1.3.1

Scaffold installed from PyPI now knows its own version. It said 0.0.0, and packs it built were labelled 0.0.0 too. The downloadable program was not affected.

## 1.3.0

Rebuild your packs to pick these up. Redstone dust now joins up the way it does in game. A new Clearer Redstone tab in the Tweaks menu, with art from Redstone Tweaks, shows dust power and how full containers and pots are, among much else. Fences, walls, panes and stair corners join up in structures saved in Minecraft 26.50 or later. Waterlogged blocks show their water without hiding the block. Over a hundred blocks were reshaped to match the game, ghosts sit centred in their block, and low geometry draws plants and small blocks as their inventory picture. Double chests show as one chest. The command line can read its options from a file.

## 1.2.0

New Tweaks menu: apply certain textures from Bedrock Tweaks. Pistons now show extended if they are. Water is now translucent. Fixed lectern and hopper visuals.

## 1.1.2

Fixed visuals for glow berries, open fence gates, bookshelf books, doors, trapdoors, straw beds, and poplar hanging signs. Cushions show up in big builds. Added a button to install packs directly into Minecraft.

## 1.1.1

Fixed a crash when exporting massive builds. Texture layouts were converted into a compact grid so giant builds no longer overwhelm your graphics card.

## 1.1.0

Adds full support for Minecraft 26.50 structures and its 121 new blocks. Block lists now name every block in categories.