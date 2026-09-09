"""What Scaffold accepts on the command line.

Both entry points parse the same arguments, so that a script written against the
command line build runs unchanged against the one with the window in it.
"""
import argparse

from scaffold import settings
from scaffold.pack import manifest


def parse(argv=None):
    parser = argparse.ArgumentParser(
        prog="scaffold",
        description="Scaffold turns .mcstructure files into Bedrock resource "
                    "packs. Give it a structure and a pack name to build one; "
                    "give it nothing and the window opens, if this build has "
                    "one.")
    parser.add_argument("--structure", type=str, help=".mcstructure file")
    parser.add_argument("--pack_name", type=str, help="Name of pack")
    parser.add_argument("--opacity", type=int,
                        help="Opacity of the ghost blocks, 1-100 (default %d)"
                             % settings.DEFAULT_OPACITY)
    parser.add_argument("--description", type=str,
                        help="Short note shown in the pack list, up to %d "
                             "characters" % manifest.DESCRIPTION_LIMIT)
    parser.add_argument("--icon", type=str, help="Icon for pack")
    parser.add_argument("--output", type=str,
                        help="Folder to write the pack into (default: the "
                             "Scaffold Builds folder in your documents)")
    parser.add_argument("--offset", type=str, help="X, Y, Z")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite the output file.")
    parser.add_argument("--debug", "-db", action="store_true",
                        help="Enable debug mode")
    parser.add_argument("--low_geometry", action="store_true",
                        help="Draw the most detailed blocks as simpler shapes. "
                             "Every ghost block is geometry the client lights "
                             "and draws, which Vibrant Visuals makes markedly "
                             "more expensive; this trades the detail on the few "
                             "blocks that carry a lot of it for a pack that is "
                             "cheaper to display.")
    parser.add_argument("--tech_pack", nargs="?", const="full", default="none",
                        choices=("none", "compatibility", "full"),
                        help="What to do about TechPack. Both projects replace "
                             "the armor stand entity, and a resource pack "
                             "replaces that file rather than merging with it, so "
                             "applying both loses whichever sits lower in the "
                             "player's list. 'compatibility' declares TechPack "
                             "on the armor stand so a separately installed copy "
                             "keeps working; 'full' carries TechPack's own files "
                             "too. Default: none.")
    args = parser.parse_args(argv)
    ## Half a command line is an error rather than a fall through to the
    ## window: on a headless machine opening the window fails somewhere much
    ## less obvious than here.
    if bool(args.structure) != bool(args.pack_name):
        parser.error("--structure and --pack_name go together; give both to "
                     "build from the command line, or neither to open the "
                     "window")
    return args
