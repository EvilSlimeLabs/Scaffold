"""Ways round a waterlogged block disappearing in its water, side by side.

A ghost is blended, so whichever of a block and its water is drawn first, the
second is depth tested against it: water drawn first hides whatever stands
behind its faces, and a block drawn first hides water behind its clear texels,
such as the water under a grate's top. Each trial draws the same blocks with
their water another way, as a copy of water's family under a pseudo block id the
gallery places in the ghost's water only:

  now          as a pack draws them today: the sides after the block, and the
               top before it where the block covers it and shows through its
               own top (`core.water_families`)
  top_late     the top after every plane
  top_early    the top before everything
  no_top       no top at all
  dry          no water drawn at all

The top rows change the top alone, through `TOP_FAMILIES`, which the gallery
hands the builder by position.

The game draws a model's bones sorted by name, as far as every world so far
shows, so a tier is a prefix that sorts: `early_` before a block's `slice_`,
and the planes' and the water's tiers after it.

`tools/checks/gallery.py --water-trials` lays them out, a row per trial.
Not shipped.
"""
import copy

## the blocks tried, and their states
BLOCKS = (("copper_bars", {}), ("hopper", {"facing_direction": 0}),
          ("oak_stairs", {"weirdo_direction": 0, "upside_down_bit": False}),
          ("copper_grate", {}), ("copper_bulb", {}), ("mangrove_roots", {}),
          ("oak_leaves", {"persistent_bit": True}), ("lantern", {"hanging": False}),
          ("stone_button", {"facing_direction": 1}),
          ("smooth_stone_slab", {"minecraft:vertical_half": "bottom"}),
          ("acacia_trapdoor", {"open_bit": False, "upside_down_bit": False}),
          ("kelp", {"kelp_age": 25}), ("chest", {"minecraft:cardinal_direction": "north"}),
          ("glass_pane", {}), ("oak_fence", {}))
TRIALS = ("now", "top_late", "top_early", "no_top", "dry")
## the family each top trial draws water's top with; None draws no top
TOP_FAMILIES = {"top_late": "water_surface_late", "top_early": "water_surface_early",
                "no_top": None}
## the block or water each trial draws as a copy
COPIES_BLOCK = set()
COPIES_WATER = set()
## the trials whose water is drawn before the blocks
EARLY = set()
PREFIX = "scaffold:wt_"
## how far in water stands in the inside trial: past a ghost's own 0.025
INSIDE = 0.035


def block(trial, name):
    return "%s%s__%s" % (PREFIX, trial, name)


def real(name):
    """The block a pseudo id copies, for its textures."""
    return name.split("__", 1)[1] if name.startswith(PREFIX) else name


def _copy(geo, family, made):
    geo.block_shapes[made] = copy.deepcopy(geo.block_shapes[family])
    geo.block_uv[made] = copy.deepcopy(geo.block_uv[family])
    geo.rules[made] = copy.deepcopy(geo.rules.get(family, {}))
    geo.block_rotations[made] = copy.deepcopy(geo.block_rotations.get(family, {}))


def install(geo):
    """Add each trial's families to a geometry builder, in memory."""
    for trial in TRIALS:
        if trial in COPIES_BLOCK:
            for name, _states in BLOCKS:
                family = geo.defs[name]
                made = "wt_%s__%s" % (trial, family)
                _copy(geo, family, made)
                geo.defs[block(trial, name)] = made
                if trial == "with_water":
                    geo.drawn_liquid.add(made)
                else:
                    geo.drawn_last.add(made)
        if trial in COPIES_WATER:
            made = "wt_%s__water" % trial
            _copy(geo, geo.defs["water"], made)
            geo.defs[block(trial, "water")] = made
            if trial in EARLY:
                geo.drawn_early.add(made)
            for shape in geo.block_shapes[made].values():
                if trial == "inside":
                    shape["size"] = [[round(v - 2 * (INSIDE - 0.01), 6) for v in size]
                                     for size in shape["size"]]
                    shape["offsets"] = [[round(v + INSIDE - 0.01, 6) for v in at]
                                        for at in shape.get("offsets", [[0, 0, 0]])]
            if trial == "surface":
                for uv in geo.block_uv[made].values():
                    for face in ("north", "south", "east", "west", "down"):
                        uv["uv_sizes"][face] = [[0, 0] for _ in uv["uv_sizes"][face]]
