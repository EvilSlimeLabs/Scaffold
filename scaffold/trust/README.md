# The root of trust

`root.json` belongs here, and it is the one file an update cannot fetch.

Everything else about a release — the timestamp, the snapshot, the list of
targets, the archives themselves — is downloaded and checked against this file.
Which is why this file has to arrive some other way: it is compiled into the
executable, and copied out into the update client's metadata directory the first
time the program looks for an update.

It is written by `python build.py --init-trust`, which creates the four TUF
roles' keys and the metadata that goes with them. Run that once, ever, and
commit the `root.json` it leaves here.

## What is not here

**The private keys.** `--init-trust` puts them in `~/.scaffold-keys`, outside
the repository, and they must stay there. Anyone holding the targets key can
sign a release that every copy of Scaffold in the world will install without
complaint. Nothing in this directory is a secret; the four `.pub` files and
`root.json` are all public by design.

## Replacing it

A root rotation is the one update that cannot be automatic, because a new root
has to be signed by the old one. `tufup` handles the signing; what it means for
this directory is that the new `root.json` is committed here and ships in the
next release. The client only writes the shipped copy into its metadata
directory when there is nothing there already, so a rotation that has already
reached somebody is not undone by them installing an older build.
