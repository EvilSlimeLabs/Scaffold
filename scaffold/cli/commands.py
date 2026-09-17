"""What the command line can do: build a pack."""
import os

from scaffold import settings
from scaffold import core
def enable_debug():
    """Let a block that cannot be drawn raise instead of being collected.

    Also turns on the lookup tracing. Imported here rather than at the top so
    that a run without --debug does not pull the geometry module in early.
    """
    from scaffold.pack import armor_stand_geo_class

    core.debug = True
    armor_stand_geo_class.debug = True


def list_tweaks():
    """Print the tweaks this build offers, for `--tweaks` with no names."""
    from scaffold import lang_parse
    from scaffold import tweaks

    english = lang_parse.parse()["en_US"]
    print("Bedrock Tweaks this build offers, for --tweaks:")
    for key in tweaks.offered():
        print("  %-36s %s" % (key, english.get("tweak " + key, key)))
    print("\nTextures by Bedrock Tweaks and Vanilla Tweaks. A pack built with "
          "any of\nthem credits them, which their licence asks for.")


def build(args):
    """Build one pack from what the command line asked for."""
    opacity = settings.DEFAULT_OPACITY if args.opacity is None else args.opacity
    offset = [0, 0, 0]
    if args.offset:
        offset = [int(value) for value in args.offset.split(",")]

    ## **An explicit --output wins; otherwise the folder the command was run
    ## in.** Not the window's output folder: a command line is expected to put
    ## what it makes where it was invoked, the way every other build tool does,
    ## and a script that builds a pack should not have to know where somebody's
    ## Documents are. The window keeps its own remembered folder, which is what
    ## somebody clicking a button expects instead.
    folder = args.output or os.getcwd()
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, args.pack_name)

    ## the window asks; a command line has nobody to ask, so it refuses by name
    ## and points at the flag that says otherwise
    if not args.overwrite:
        already = [path for path in core.outputs(target) if os.path.exists(path)]
        if already:
            raise SystemExit("{} already exists. Pass --overwrite to write over "
                             "it, or build under another name.".format(already[0]))

    pack = core.Scaffold(target)
    pack.set_opacity(min(max(opacity, 1), 100) / 100)

    if args.description:
        pack.set_description(args.description)
    if args.low_geometry:
        pack.set_low_geometry(True)
    if args.tech_pack and args.tech_pack != "none":
        pack.set_tech_pack(args.tech_pack)
    if args.tweaks:
        ## A name nothing offers is dropped rather than refused, but saying so
        ## matters: a typo would otherwise be a pack quietly built without the
        ## tweak somebody asked for.
        pack.set_tweaks(args.tweaks)
        applied = pack.get_tweaks()
        unknown = [name for name in args.tweaks if name not in applied]
        if unknown:
            print("no tweak called: {}".format(", ".join(unknown)))
            print("run --tweaks with no names to list them")
    if args.icon:
        pack.set_icon(args.icon)

    pack.add_model("", args.structure)
    pack.set_model_offset("", offset)
    pack.generate_with_nametags()
    print(pack.compile_pack(overwrite=args.overwrite))
