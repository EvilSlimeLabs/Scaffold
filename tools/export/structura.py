"""Write Scaffold's block tables in the shape Structura 1.7 reads.

    python -m tools.export.structura <out>
    python -m tools.export.structura <out> --report

`<out>` gets a `lookups/` and a `Vanilla_Resource_Pack/` laid out the way a
Structura 1.7 checkout has them, to be copied over one. Nothing is written into
a checkout. `--report` lists every case and how near 1.7 can draw it.

**What Structura 1.7 can be told.** Its geometry builder is the one Scaffold's
grew out of and reads the same cube lists, but it chooses between them with far
less:

- one *data* value: the last state marked `data` in `nbt_defs.json` that the
  block carries, as a number. A state holding a word cannot be marked `data`,
  because the value goes through `int()` outside any `try` and one such block
  ends the whole build.
- one *top* flag, from the states marked `top`. `bool()` of a word is True,
  which is why `minecraft:vertical_half` is a rotation state there.
- one rotation state: the last marked `rot` the block carries, looked up as
  `str(value)` in its family's rotation table. A value the table lacks raises,
  and the block is skipped.
- one texture *variant*: the last state marked `variant`, looked up in
  `variants.json`, which picks an entry of a texture list in `blocks.json`. A
  number cannot be a variant: the table's keys are strings and the lookup
  raises.

The form drawn is `str(data)` when the family has one by that name, and
otherwise `top` or `default`; a family named `hopper` draws `side` whenever its
rotation value is not 0. **A form's UV windows always come from `top` or
`default`**, even when its cubes and textures come from a data form. So every
form of a block is laid out against one shared list of window slots, and a form
that does not use a slot fills it with a cube of no size.

It reads no block entity, so a banner's colour, a bed's dye, a statue's pose
and a lectern's book are lost; a block is drawn as Scaffold draws it without
one. It does not translate old blocks, so the old ids and states Scaffold
upgrades as it reads a structure are given tables of their own here, made by
running `block_upgrade` backwards from the blocks they become. It knows nothing
of a texture window (`#x,y`), a quarter turn (`^90`), a tint (`~tint`) or a face
slot reference (`@up`), so every texture is resolved here, per block, and a
picture Scaffold cuts or turns is written out as a tile of its own under
`textures/scaffold/`.

**So the families are written per block.** Every case the gallery enumerates is
drawn by Scaffold, and what each would show is filed under the key Structura
would pick for it. Blocks whose tables come out identical share a family. Where
cases Structura cannot tell apart draw differently, the commoner wins, and
`--report` lists the rest.

Not shipped.
"""
import argparse
import collections
import io
import json
import os
import re
import shutil
import sys

from tools.checks import gallery

ROOT = gallery.ROOT
FACES = ("up", "down", "east", "west", "north", "south")
## the states read as the top half
TOP = ("upside_down_bit", "upper_block_bit")
## a slab's half: a word, so Structura can only read it as a rotation
HALF = "minecraft:vertical_half"
## the turn that stands a bottom slab's cubes where a top slab's go
FLIP = [0, 0, 180]
MARKS = re.compile(r"[#^~]")
STAND_IN = "textures/blocks/stone"
STUB = "scaffold_export"
## what a face reads when its texture comes from the block's variant
VARIED = "default"


def _value(value):
    """A state value as nbtlib hands it over: a bool is a byte."""
    return int(value) if isinstance(value, bool) else value


def _typed(text):
    """A value from an upgrade table, which keys everything as text."""
    return int(text) if isinstance(text, str) and text.lstrip("-").isdigit() else text


def _key(thing):
    return json.dumps(thing, sort_keys=True)


# --- what Structura reads ------------------------------------------------------

def roles(rules, values, legacy):
    """`nbt_defs.json`: which states Structura reads, and as what, in order.

    For each role the last state a block carries wins, so the order is part of
    the meaning. `legacy` is {old state: (the state it becomes, its values)}.
    """
    turn, data, texture = [], [], []
    for rule in rules.values():
        for entry in rule.get("turn_by", ()):
            if "state" in entry and entry["state"] not in turn:
                turn.append(entry["state"])
        named = [s for pick in rule.get("pick", ()) for s in pick["when"]]
        named += rule.get("data", {}).get("number", [])
        named += rule.get("data", {}).get("join", [])
        for state in named:
            if state not in data:
                data.append(state)
        chosen = rule.get("texture_by")
        for state in (chosen.get("join") or [chosen["state"]]) if chosen else ():
            if state not in texture:
                texture.append(state)

    def number(state):
        return all(isinstance(v, (bool, int)) for v in values.get(state, ["x"]))

    order = collections.OrderedDict()
    for state in texture:
        order[state] = "data" if number(state) else "variant"
    for state in data:
        if state not in turn and state not in TOP and number(state):
            order.setdefault(state, "data")
    for state in TOP:
        order[state] = "top"
    ## a hanging sign carries both, and one hung by its chains, which turns
    ## with facing_direction, is the commoner
    turn.sort(key=lambda s: s == "facing_direction")
    for state in turn:
        order[state] = "rot"
    order.setdefault(HALF, "rot")
    ## the states an older game wrote, read as whatever they became
    for state, (becomes, old) in legacy.items():
        if state in order:
            continue
        numbers = all(isinstance(v, int) for v in old)
        if becomes is None:
            order[state] = "data" if numbers else "variant"
        elif becomes == HALF and numbers:
            order[state] = "top"
        elif order.get(becomes) == "rot":
            order[state] = "rot"
        elif order.get(becomes) in ("data", "top") and numbers:
            order[state] = order[becomes]
        elif order.get(becomes) == "variant" and not numbers:
            order[state] = "variant"
    return order


def reads(states, order, name):
    """What Structura 1.7's `_process_block` makes of a block's states."""
    rot, top, variant, data = None, False, "default", 0
    for key, role in order.items():
        if key not in states:
            continue
        value = states[key]
        if role == "variant":
            variant = [key, value]
        elif role == "rot":
            rot = value if isinstance(value, int) else str(value)
        elif role == "top":
            top = bool(value)
        elif role == "data":
            data = int(value)
        if key == "rail_direction":
            data = str(int(value))
            if "rail_data_bit" in states:
                data += "-" + str(int(states["rail_data_bit"]))
    if "wood_type" in states:
        variant = ["wood_type", states["wood_type"]]
        if name == "wood":
            kind = states["wood_type"]
            if states.get("stripped_bit"):
                kind += "_stripped"
            variant = ["wood", kind]
    return rot, top, variant, str(data)


def fallback(family, rot, top):
    """The form Structura reads windows from, and draws without a data form."""
    if family == "hopper" and rot != 0:
        return "side"
    return "top" if top else "default"


def order_winner(order, states, role):
    """The state of this role that Structura reads from a block, if any."""
    winner = None
    for key, has in order.items():
        if has == role and key in states:
            winner = key
    return winner


# --- what Scaffold draws -------------------------------------------------------

class Scaffold:
    """Scaffold's own drawing of a block, cube by cube."""

    def __init__(self, tiles):
        from scaffold.pack import armor_stand_geo_class as asgc
        self.asgc = asgc
        self.geo = asgc.ArmorStandGeo("export", alpha=1.0, offsets=[0, 0, 0])
        self.tiles = tiles
        self.names = {}

    def _name(self, index):
        if len(self.names) != len(self.geo.uv_map):
            self.names = {i: n for n, i in self.geo.uv_map.items()}
        return self.names[index]

    def draw(self, block, states):
        """(content, rotation) for one block in one state.

        Content is the form's centre and a record per cube: its box, its own
        turn, and for each face the window and the texture it reads.
        """
        geo, asgc = self.geo, self.asgc
        family = geo.defs[block]
        form, turn, texture = geo.choose(block, states)
        shapes = geo.block_shapes[family][form]
        windows = geo.block_uv[family].get(form, geo.block_uv[family]["default"])
        cubes, chosen = [], 0
        for i in range(len(shapes["size"])):
            faces = geo.block_name_to_uv(block, shape_variant=form, index=i,
                                         block_type=family, texture=texture)
            if len(windows["uv_sizes"]["up"]) > i:
                chosen = i
            record = {"size": shapes["size"][i],
                      "offset": shapes["offsets"][i] if "offsets" in shapes else [0, 0, 0],
                      "rotation": (shapes["rotation"][i] if "rotation" in shapes
                                   and any(shapes["rotation"][i]) else None),
                      "faces": {}}
            for face in FACES:
                index = asgc.atlas_index(*faces[face]["uv"])
                record["faces"][face] = [
                    windows["offset"][face][chosen], windows["uv_sizes"][face][chosen],
                    self.tiles.path(self._name(index), geo, index)]
            cubes.append(record)
        rotation = None
        table = geo.block_rotations.get(family)
        if table is not None and turn is not None:
            rotation = table.get("{}:{}".format(form, turn))
            if rotation is None:
                rotation = table.get(str(turn))
        if rotation is not None:
            rotation = [round(a, 6) + 0.0 for a in asgc.to_bone(rotation)]
        return {"center": shapes["center"], "cubes": cubes}, rotation


class Tiles:
    """The textures an export uses, and the tiles it has to cut itself."""

    def __init__(self):
        self.plain = {STAND_IN}
        self.cut = {}

    def path(self, name, geo, index):
        if not MARKS.search(name):
            self.plain.add(name)
            return name
        if name not in self.cut:
            slug = re.sub(r"[^a-z0-9]+", "_",
                          name.lower().replace("textures/", "")).strip("_")
            self.cut[name] = ("textures/scaffold/" + slug, geo.tile(index).copy())
        return self.cut[name][0]

    def write(self, pack):
        from PIL import Image
        from scaffold import paths
        source = paths.vanilla_pack()
        missing = []
        for name in sorted(self.plain):
            for kind in (".png", ".tga"):
                found = os.path.join(source, name.replace("/", os.sep) + kind)
                if os.path.isfile(found):
                    target = os.path.join(pack, name.replace("/", os.sep) + kind)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copyfile(found, target)
                    break
            else:
                missing.append(name)
        for path, pixels in self.cut.values():
            target = os.path.join(pack, path.replace("/", os.sep) + ".png")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            Image.fromarray(pixels).save(target)
        return missing


class Store:
    """Every distinct content drawn, by number, so cases compare cheaply."""

    def __init__(self):
        self.contents, self.ids = [], {}

    def add(self, content):
        k = _key(content)
        if k not in self.ids:
            self.ids[k] = len(self.contents)
            self.contents.append(content)
        return self.ids[k]

    def __getitem__(self, cid):
        return self.contents[cid]


# --- one block's tables --------------------------------------------------------

class Block:
    """One block's drawn cases, and the tables Structura reads them through."""

    def __init__(self, block, family, cases, legacy=False):
        self.block, self.family = block, family
        ## (states, content id, rotation)
        self.cases = cases
        self.legacy = legacy
        self._varied = {}

    def varied(self, store, variant_of):
        """Content ids with the faces a variant paints marked, and the textures.

        A face is painted by the variant when each value of it gives the face
        one texture on every cube and the values do not all agree. Those faces
        read `blocks.json`, whose entry for them is a list the variant picks
        from. Any other face keeps its texture outright.
        """
        state = next((v[0] for v in variant_of if v != "default"), None)
        if state in self._varied:
            return self._varied[state]
        if state is None:
            result = ([c for _s, c, _r in self.cases], {}, None)
            self._varied[state] = result
            return result
        painted = {}
        for face in FACES:
            per_value, fits = {}, True
            for (states, cid, _r), variant in zip(self.cases, variant_of):
                if variant == "default":
                    continue
                seen = {c["faces"][face][2] for c in store[cid]["cubes"]}
                if len(seen) != 1 or per_value.setdefault(variant[1], seen) != seen:
                    fits = False
                    break
            if fits and len({next(iter(s)) for s in per_value.values()}) > 1:
                painted[face] = {v: next(iter(s)) for v, s in per_value.items()}
        ids = []
        for (states, cid, _r), variant in zip(self.cases, variant_of):
            if not painted or variant == "default":
                ids.append(cid)
                continue
            content = json.loads(_key(store[cid]))
            for c in content["cubes"]:
                for face in painted:
                    c["faces"][face][2] = VARIED
            ids.append(store.add(content))
        result = (ids, painted, state)
        self._varied[state] = result
        return result

    def build(self, order, store):
        read = [reads(states, order, self.block) for states, _c, _r in self.cases]
        ids, self.painted, self.variant = self.varied(store, [r[2] for r in read])
        read = [(rot, top, variant, data, cid, rotation)
                for (rot, top, variant, data), cid, (_s, _c, rotation)
                in zip(read, ids, self.cases)]
        family = self.family

        def tally(found):
            return collections.Counter(found).most_common(1)[0][0]

        def score(table):
            return sum(table.get(d if d in table else fallback(family, r, t)) == c
                       for r, t, _v, d, c, _ in read)

        table = {"default": tally([c for r, t, _v, _d, c, _ in read
                                   if fallback(family, r, t) == "default"]
                                  or [c for *_x, c, _ in read])}
        for name in ("top", "side"):
            served = [c for r, t, _v, _d, c, _ in read if fallback(family, r, t) == name]
            if served:
                table[name] = tally(served)
        best = score(table)
        for data in sorted({d for _r, _t, _v, d, *_ in read}):
            trial = dict(table)
            trial[data] = tally([c for _r, _t, _v, d, c, _ in read if d == data])
            got = score(trial)
            if got > best:
                table, best = trial, got
        for name in ("default", "top", "side"):
            served = [c for r, t, _v, d, c, _ in read
                      if d not in table and fallback(family, r, t) == name]
            if name in table and served:
                trial = dict(table, **{name: tally(served)})
                got = score(trial)
                if got > best:
                    table, best = trial, got

        turns = collections.defaultdict(collections.Counter)
        for rot, _t, _v, _d, _c, rotation in read:
            if rot is not None:
                turns[str(rot)][_key(rotation or [0, 0, 0])] += 1
        rotations = {k: json.loads(c.most_common(1)[0][0]) for k, c in turns.items()}

        ## a slab's half is only a rotation to Structura, so a top slab is the
        ## bottom one turned over about a centre placed to land it
        flip = None
        if order_winner(order, self.cases[0][0], "rot") == HALF and "top" in rotations:
            tops = [c for r, _t, _v, d, c, _ in read if r == "top"]
            bottoms = [c for r, _t, _v, d, c, _ in read if r == "bottom"]
            if tops and bottoms and tally(tops) != tally(bottoms):
                centre = flipped(store[tally(bottoms)], store[tally(tops)])
                if centre is not None:
                    flip = (tally(bottoms), centre)
                    rotations["top"] = FLIP
                    rotations.setdefault("bottom", [0, 0, 0])

        self.table, self.rotations, self.flip = table, rotations, flip
        self.matched = 0
        self.misses = []
        for (states, _c, _r), (rot, top, _v, data, cid, rotation) in zip(self.cases, read):
            got = table.get(data if data in table else fallback(family, rot, top))
            why = []
            if flip is not None and rot == "top" and got == flip[0]:
                why.append("turned over")
            elif got != cid:
                why.append("form")
            if rot is not None and not (flip is not None and rot in ("top", "bottom")) \
                    and (rotation or [0, 0, 0]) != rotations[str(rot)]:
                why.append("turn")
            if why:
                self.misses.append((states, why))
            else:
                self.matched += 1
        return self


def flipped(bottom, top):
    """The centre a half turn lands a bottom form on a top one about, or None.

    A half turn about z through a centre at the middle of the two cubes' spans
    lands every box of one on the other's, but reads its faces upside down.
    """
    if len(bottom["cubes"]) != len(top["cubes"]):
        return None
    high = max(c["offset"][1] + c["size"][1] for c in bottom["cubes"])
    top_low = min(c["offset"][1] for c in top["cubes"])
    middle_y = (high + top_low) / 2.0
    xs = [c["offset"][0] for c in bottom["cubes"]] + \
         [c["offset"][0] + c["size"][0] for c in bottom["cubes"]]
    middle_x = (min(xs) + max(xs)) / 2.0
    for b, t in zip(bottom["cubes"], top["cubes"]):
        landed = [2 * middle_x - b["offset"][0] - b["size"][0],
                  2 * middle_y - b["offset"][1] - b["size"][1], b["offset"][2]]
        if any(abs(a - c) > 1e-6 for a, c in zip(landed, t["offset"])) \
                or b["size"] != t["size"]:
            return None
    return [middle_x, middle_y, bottom["center"][2]]


# --- laying a block's forms out for Structura ----------------------------------

def windows_of(record):
    return _key({f: record["faces"][f][:2] for f in FACES})


def lay_out(forms):
    """Structura's shape and UV entries for every form of one block.

    Every form reads its windows from one shared list of slots, because
    Structura reads a data form's windows from `default` or `top`. A form puts
    each cube in a slot holding its windows, and a slot it does not use, below
    the last it does, holds a cube of no size.
    """
    need = collections.OrderedDict()
    used_by = collections.Counter()
    sample = {}
    for content in forms.values():
        counts = collections.Counter(windows_of(c) for c in content["cubes"])
        for w, n in counts.items():
            need[w] = max(need.get(w, 0), n)
            used_by[w] += 1
        for c in content["cubes"]:
            sample.setdefault(windows_of(c), c)
    ## the windows used most widely go first, so fewer forms need fillers
    slots = [w for w in sorted(need, key=lambda w: -used_by[w]) for _ in range(need[w])]

    window_table = {"offset": {f: [] for f in FACES},
                    "uv_sizes": {f: [] for f in FACES}}
    for w in slots:
        for f in FACES:
            window_table["offset"][f].append(sample[w]["faces"][f][0])
            window_table["uv_sizes"][f].append(sample[w]["faces"][f][1])

    shapes, uvs = {}, {}
    for name, content in forms.items():
        placed = {}
        free = collections.defaultdict(list)
        for i, w in enumerate(slots):
            free[w].append(i)
        for c in content["cubes"]:
            placed[free[windows_of(c)].pop(0)] = c
        last = max(placed) + 1 if placed else 1
        filler = content["cubes"][0]
        cubes = [placed.get(i) for i in range(last)]
        shape = {"center": content["center"],
                 "size": [c["size"] if c else [0, 0, 0] for c in cubes],
                 "offsets": [c["offset"] if c else filler["offset"] for c in cubes]}
        if any(c and c["rotation"] for c in cubes):
            shape["rotation"] = [c["rotation"] if c and c["rotation"] else [0, 0, 0]
                                 for c in cubes]
        shapes[name] = shape
        uvs[name] = dict(window_table, overwrite={
            f: [(c or filler)["faces"][f][2] for c in cubes] for f in FACES})
    return shapes, uvs


# --- the cases -----------------------------------------------------------------

def _plain(value):
    from scaffold import block_upgrade
    return block_upgrade.plain(value)


def _ids(rule):
    wanted = rule.get("id")
    return wanted if isinstance(wanted, list) else [wanted]


def older(block, states):
    """Every way an older game could have written this block in these states.

    `block_upgrade` run backwards: an id one of its rules renames or splits into
    this one, and a state one of them renamed, with the value it had. Each is
    kept only if upgrading it gives this block back, so a rule that cannot be
    run backwards is never guessed at.
    """
    from scaffold import block_upgrade
    name = "minecraft:" + block
    found = []
    rules = [r for r in block_upgrade.rules() if "before" not in r and "set" not in r]

    def unrenamed(id_, given):
        out = [dict(given)]
        for rule in rules:
            if "state" not in rule or rule.get("drop") or id_ not in _ids(rule) \
                    and rule.get("id") is not None:
                continue
            new = rule.get("becomes", rule["state"])
            more = []
            for s in out:
                if new not in s:
                    continue
                for old, now in rule.get("values", {}).items():
                    if _plain(now) == _plain(s[new]):
                        t = {k: v for k, v in s.items() if k != new}
                        t[rule["state"]] = _typed(old)
                        more.append(t)
                        break
                else:
                    if "values" not in rule:
                        t = {k: v for k, v in s.items() if k != new}
                        t[rule["state"]] = s[new]
                        more.append(t)
            out += more
        return out

    candidates = [(name, s) for s in unrenamed(name, states)[1:]]
    for rule in rules:
        if "state" in rule:
            continue
        for old in _ids(rule):
            if rule.get("becomes") == name:
                candidates += [(old, s) for s in unrenamed(name, states)]
            for value, target in rule.get("into", {}).items():
                if target != name:
                    continue
                parts = value.split("/")
                for s in unrenamed(name, states):
                    s = dict(s)
                    for key, part in zip(rule["by"], parts):
                        s[key] = _typed(part)
                    candidates.append((old, s))
    for old, s in candidates:
        got = block_upgrade.upgrade({"name": old, "states": dict(s)})
        if str(got["name"]) == name and \
                {k: _plain(v) for k, v in got["states"].items()} == \
                {k: _plain(v) for k, v in states.items()}:
            found.append((old.replace("minecraft:", ""), s))
    return found


def gather(scaffold, store):
    """Every case worth drawing, drawn by Scaffold, grouped by block.

    The gallery's cases for every block it shows, a block it leaves out drawn
    at rest, and every older way of writing each of them.
    """
    mojang_states, values = gallery.mojang()
    picked = gallery.choose([], True, True)
    cases, _newest = gallery.all_cases(picked)
    by_block = collections.OrderedDict()
    for family, case in cases:
        by_block.setdefault((case.block, family), []).append(
            {k: _value(v) for k, v in case.states.items()})
    covered = {block for block, _f in by_block}
    for block, family in scaffold.geo.defs.items():
        if block in covered or family == "ignore" or block == "air":
            continue
        own = mojang_states.get("minecraft:" + block, [])
        by_block[(block, family)] = [{s: _value(values[s][0]) for s in own if s in values}]

    blocks, failed = [], []
    legacy = collections.defaultdict(list)
    for (block, family), states_list in by_block.items():
        drawn, seen = [], set()
        for states in states_list:
            k = _key(states)
            if k in seen:
                continue
            seen.add(k)
            try:
                content, rotation = scaffold.draw(block, states)
            except Exception as trouble:
                failed.append((block, k, repr(trouble)))
                continue
            cid = store.add(content)
            drawn.append((states, cid, rotation))
            for old, old_states in older(block, states):
                legacy[old].append((family, (old_states, cid, rotation)))
        if drawn:
            blocks.append(Block(block, family, drawn))
    names = {b.block: b for b in blocks}
    for old, found in legacy.items():
        ## one old id may split into blocks of several families, and is one
        ## block to Structura; it is named for the commonest
        family = collections.Counter(f for f, _c in found).most_common(1)[0][0]
        drawn = [c for _f, c in found]
        if old in names:
            ## an id still current, written with states it no longer has
            names[old].cases += [c for c in drawn
                                 if _key(c[0]) not in {_key(s) for s, _c, _r in names[old].cases}]
        else:
            unique = {}
            for c in drawn:
                unique.setdefault(_key(c[0]), c)
            blocks.append(Block(old, family, list(unique.values()), legacy=True))
    return blocks, failed


def legacy_states(blocks):
    """{old state: (the state it becomes or None, its values)} from the cases."""
    from scaffold import block_upgrade
    found = collections.defaultdict(set)
    becomes = {}
    for rule in block_upgrade.rules():
        if "state" in rule and not rule.get("drop") and "before" not in rule:
            becomes[rule["state"]] = rule.get("becomes", rule["state"])
        for key in rule.get("by", ()):
            becomes.setdefault(key, None)
    for b in blocks:
        for states, _c, _r in b.cases:
            for key, value in states.items():
                if key in becomes:
                    found[key].add(value)
    return {k: (becomes[k], sorted(v, key=str)) for k, v in found.items()}


def legal_rotations(states, order, rotations, values, seen):
    """Every value the block's rotation state can take, so none raises."""
    winner = order_winner(order, states, "rot")
    full = dict(rotations)
    for value in values.get(winner, []) + sorted(seen.get(winner, ()), key=str):
        full.setdefault(str(_value(value)), [0, 0, 0])
    return full


def tune(blocks, order, store):
    """Move each state between data, top and nothing while it helps."""
    def total(candidate):
        return sum(b.build(candidate, store).matched for b in blocks)

    best = total(order)
    for state in [s for s, r in order.items() if r in ("data", "top")]:
        for role in ("data", "top", None):
            trial = collections.OrderedDict((k, v) for k, v in order.items() if k != state)
            if role:
                trial[state] = role
            got = total(trial)
            if got > best:
                order, best = trial, got
    ## and the order of what is left: a state that should win goes last
    for state in [s for s, r in order.items() if r == "data"]:
        trial = collections.OrderedDict((k, v) for k, v in order.items() if k != state)
        trial[state] = "data"
        got = total(trial)
        if got > best:
            order, best = trial, got
    return order


# --- the whole export ----------------------------------------------------------

def export(out, report=False):
    from scaffold import block_geometry
    from scaffold import version

    _mojang_states, values = gallery.mojang()
    tiles = Tiles()
    store = Store()
    scaffold = Scaffold(tiles)
    blocks, failed = gather(scaffold, store)
    legacy = legacy_states(blocks)
    order = roles(block_geometry.rules(), values, legacy)
    order = tune(blocks, order, store)
    for b in blocks:
        b.build(order, store)
    seen_values = collections.defaultdict(set)
    for b in blocks:
        for states, _c, _r in b.cases:
            for k, v in states.items():
                seen_values[k].add(v)

    definition, shapes, uvs, rotation_tables = {}, {}, {}, {}
    families = {}
    variants = collections.defaultdict(set)
    for b in blocks:
        if b.painted:
            for face, by_value in b.painted.items():
                variants[b.variant].update(by_value)
    variants = {state: {v: i for i, v in enumerate(sorted(vs, key=str))}
                for state, vs in variants.items()}

    blocks_json = {"format_version": [1, 1, 0]}
    terrain_data = {STUB: {"textures": STAND_IN}}
    for b in blocks:
        forms = {name: store[cid] for name, cid in b.table.items()}
        if b.flip is not None:
            bottom, centre = b.flip
            forms = {name: (dict(store[cid], center=centre) if cid == bottom
                            else store[cid]) for name, cid in b.table.items()}
        rotations = b.rotations
        if any(r != [0, 0, 0] for r in rotations.values()):
            rotations = legal_rotations(b.cases[0][0], order, rotations, values, seen_values)
        else:
            rotations = None
        shape, uv = lay_out(forms)
        signature = _key([shape, uv, rotations])
        if signature not in families:
            count = sum(1 for f in families.values() if f.split(".")[0] == b.family)
            label = b.family if count == 0 else "%s.%d" % (b.family, count)
            families[signature] = label
            shapes[label], uvs[label] = shape, uv
            if rotations:
                rotation_tables[label] = rotations
        definition[b.block] = families[signature]
        ## every face is named outright unless the variant paints it, so most
        ## blocks need only an entry here for Structura to read before the
        ## overwrites; a painted face gets a list the variant picks from
        if b.painted:
            layout = {}
            for face in FACES:
                if face not in b.painted:
                    layout[face] = STUB
                    continue
                name = "scaffold_%s_%s" % (b.block, face)
                listed = variants[b.variant]
                textures = [STAND_IN] * len(listed)
                for value, texture in b.painted[face].items():
                    textures[listed[value]] = texture
                terrain_data[name] = {"textures": textures}
                layout[face] = name
            blocks_json[b.block] = {"textures": layout}
        else:
            blocks_json[b.block] = {"textures": STUB}

    ## what Scaffold deliberately draws nothing for, Structura passes over
    ## in silence too rather than listing it as skipped
    for block, family in scaffold.geo.defs.items():
        if family == "ignore":
            definition.setdefault(block, "ignore")

    lookups = os.path.join(out, "lookups")
    pack = os.path.join(out, "Vanilla_Resource_Pack")
    os.makedirs(lookups, exist_ok=True)
    os.makedirs(os.path.join(pack, "textures"), exist_ok=True)
    terrain = {"resource_pack_name": "vanilla", "texture_name": "atlas.terrain",
               "padding": 8, "num_mip_levels": 4, "texture_data": terrain_data}

    def dump(name, data):
        with io.open(name, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent="\t")
            f.write("\n")

    dump(os.path.join(lookups, "block_definition.json"), definition)
    dump(os.path.join(lookups, "block_shapes.json"), shapes)
    dump(os.path.join(lookups, "block_uv.json"), uvs)
    dump(os.path.join(lookups, "block_rotation.json"), rotation_tables)
    dump(os.path.join(lookups, "nbt_defs.json"), order)
    dump(os.path.join(lookups, "variants.json"), variants)
    dump(os.path.join(lookups, "lookup_version.json"),
         {"version": "scaffold-%s" % version.read(),
          "author": "Scaffold",
          "update_url": "https://update.structuralab.com/structuraUpdate",
          "notes": "Exported from Scaffold %s." % version.read()})
    dump(os.path.join(pack, "blocks.json"), blocks_json)
    dump(os.path.join(pack, "textures", "terrain_texture.json"), terrain)
    missing = tiles.write(pack)

    total = sum(len(b.cases) for b in blocks)
    matched = sum(b.matched for b in blocks)
    print("blocks          : %d, %d of them old ids" % (
        len(definition), sum(1 for b in blocks if b.legacy)))
    print("families        : %d" % len(shapes))
    print("cases           : %d" % total)
    print("drawn the same  : %d" % matched)
    print("drawn otherwise : %d, in %d blocks" % (total - matched,
                                                  sum(1 for b in blocks if b.misses)))
    print("tiles           : %d copied, %d cut" % (len(tiles.plain), len(tiles.cut)))
    if failed:
        print("not drawn by Scaffold: %d" % len(failed))
    if missing:
        print("textures not found: %s" % ", ".join(missing[:10]))
    reasons = collections.Counter(w for b in blocks for _s, why in b.misses for w in why)
    for why, count in reasons.most_common():
        print("    %-12s %d" % (why, count))
    if report:
        for b in sorted(blocks, key=lambda b: b.block):
            if not b.misses:
                continue
            print("\n%s (%s)" % (b.block, definition.get(b.block)))
            for states, why in b.misses[:6]:
                print("    %-14s %s" % (",".join(why), _key(states)))
            if len(b.misses) > 6:
                print("    ... and %d more" % (len(b.misses) - 6))
    return blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", help="the folder to write lookups/ and "
                                "Vanilla_Resource_Pack/ into")
    ap.add_argument("--report", action="store_true",
                    help="list every case Structura would draw differently")
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out)
    os.chdir(ROOT)
    export(out, args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
