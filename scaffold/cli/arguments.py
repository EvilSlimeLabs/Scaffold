"""What Scaffold accepts on the command line.

Both entry points parse the same arguments, so that a script written against the
command line build runs unchanged against the one with the window in it.
"""
import argparse
import os
import sys

from scaffold import jsonc
from scaffold import settings
from scaffold import version
from scaffold.pack import manifest

## the options a settings file may set, by the name of the flag, and the ones a
## path is resolved against the file's own folder for
FROM_FILE = ("structure", "pack_name", "opacity", "description", "icon",
             "output", "offset", "overwrite", "low_geometry", "tweaks",
             "tech_pack")
PATHS = ("structure", "icon", "output")
## what the window's own settings file holds that has no meaning here
WINDOW_ONLY = ("lang", "theme", "check_updates")


def parse(argv=None):
    parser = argparse.ArgumentParser(
        prog="scaffold",
        description="Scaffold turns .mcstructure files into Bedrock resource "
                    "packs. Give it a structure and a pack name to build one; "
                    "give it nothing and the window opens, if this build has "
                    "one.")
    parser.add_argument("--version", action="version",
                        version="Scaffold %s" % version.read(),
                        help="Print the version of Scaffold and stop")
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
                             "folder you ran the command in)")
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
    parser.add_argument("--tweaks", nargs="*", metavar="NAME", default=None,
                        help="Apply these Bedrock Tweaks and Clearer "
                             "Redstone options to the pack: texture changes "
                             "that make a build easier to read, such as a "
                             "border round ores, numbers on redstone dust or "
                             "how full a chest is. Given with no names it lists "
                             "the ones this build offers and stops. A pack "
                             "built with any of them credits whoever made the "
                             "art, which their licences ask for.")
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
    parser.add_argument("--settings", type=str, metavar="FILE",
                        help="Read any of these options from a JSON file, by "
                             "the name of the flag: {\"opacity\": 40, "
                             "\"tweaks\": [\"ore_borders\"]}. The window's own "
                             ".scaffold file works too. An option given on the "
                             "command line wins over the file, and a path in the "
                             "file is read from the file's own folder.")
    given = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(argv)
    if args.settings:
        try:
            from_file(args, parser, given)
        except (OSError, ValueError) as problem:
            parser.error("--settings %s: %s" % (args.settings, problem))
    ## Half a command line is an error rather than a fall through to the
    ## window: on a headless machine opening the window fails somewhere much
    ## less obvious than here.
    if bool(args.structure) != bool(args.pack_name):
        parser.error("--structure and --pack_name go together; give both to "
                     "build from the command line, or neither to open the "
                     "window")
    return args


def explicit(parser, given):
    """The options this command line actually spelled out."""
    found = set()
    for action in parser._actions:
        for flag in action.option_strings:
            if any(word == flag or word.startswith(flag + "=") for word in given):
                found.add(action.dest)
    return found


def from_file(args, parser, given):
    """Fill in what the command line left out from a settings file.

    The file uses the flags' own names. The window's `.scaffold` is read too:
    its `transparency` is an opacity the other way round, `output_dir` is
    `output`, and its tweaks are the names in `tweaks_on`, applied when its
    `tweaks` switch is on.
    """
    read = jsonc.load(args.settings)
    if not isinstance(read, dict):
        raise ValueError("expected a JSON object")
    read = dict(read)
    if "transparency" in read:
        read.setdefault("opacity", 100 - int(read.pop("transparency")))
    if "output_dir" in read:
        found = read.pop("output_dir")
        if found:
            read.setdefault("output", found)
    if isinstance(read.get("tweaks"), bool) or "tweaks_on" in read:
        switched = read.pop("tweaks", True)
        names = read.pop("tweaks_on", [])
        read["tweaks"] = list(names) if switched else []
    for key in WINDOW_ONLY:
        read.pop(key, None)
    unknown = sorted(set(read) - set(FROM_FILE))
    if unknown:
        raise ValueError("does not know %s" % ", ".join(unknown))

    here = os.path.dirname(os.path.abspath(args.settings))
    spelled = explicit(parser, given)
    for key in FROM_FILE:
        if key not in read or key in spelled:
            continue
        value = read[key]
        if key in PATHS and value and not os.path.isabs(str(value)):
            value = os.path.join(here, str(value))
        if key == "offset" and isinstance(value, (list, tuple)):
            value = ",".join(str(v) for v in value)
        if key == "opacity":
            value = int(value)
        if key in ("overwrite", "low_geometry"):
            value = bool(value)
        if key == "tweaks":
            ## none at all is no tweaks, not the empty --tweaks that lists them
            value = [str(v) for v in value] or None
        setattr(args, key, value)

