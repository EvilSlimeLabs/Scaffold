"""A Java block model's elements, as format 2 cubes.

Java's block models are the most complete description of how a vanilla block is
shaped: Bedrock draws most of its blocks from geometry built into the engine,
and only data-driven blocks ship a `.geo.json`. A generator here may therefore
write a Java model's elements into its own source -- they are measurements,
`from`, `to` and `uv` -- and hand them to `cubes`, which turns them into the
cubes `block_geometry.json` holds. Nothing reads a Java model at build time.

The conventions, each settled by drawing the same model with a Java renderer
and with `tools/checks/render.py`:

- **x is mirrored.** Java's +x is east and a `.geo.json`'s +x is west, so a box
  from x0 to x1 sits at 16 - x1. The faces keep their names.
- **The sides read the same window either way.** A Java side's `uv` is the
  format's `uv` and `size`, divided by sixteen.
- **The top and the bottom read theirs half a turn round.** Java lays a top with
  the picture's top edge to the north; the format lays it to the south. Both are
  turned by running the window backwards both ways.
- **A face's `rotation` is the format's `turn`.** The tile is turned clockwise
  and the window is moved onto the turned tile. On a down face the turn runs
  the other way, which a coral fan and a spore blossom showed in a world: with
  it the same, their east and west blades read their pictures half round from
  underneath.
- **An element's rotation turns the other way about x and y**, and the same way
  about z. Java turns about `origin`; the format turns a cube about its own
  middle, so the cube is moved to where Java's turn would have put its middle.
  `rescale` stretches the two other axes by 1 / cos(angle) about the origin,
  which is what lets a crossed plane reach the corners of its block.
- **A face Java does not name is not drawn**: its window has no size, and
  `make_block` leaves such a face out of the geometry.

Not shipped.
"""
import math

FACES = ("north", "south", "east", "west", "up", "down")
NOTHING = {"uv": [0, 0], "size": [0, 0]}


def default_uv(face, a, b):
    """The window Java gives a face that names none: its own place."""
    x0, y0, z0 = a
    x1, y1, z1 = b
    return {"up": (x0, z0, x1, z1), "down": (x0, 16 - z1, x1, 16 - z0),
            "north": (16 - x1, 16 - y1, 16 - x0, 16 - y0),
            "south": (x0, 16 - y1, x1, 16 - y0),
            "west": (z0, 16 - y1, z1, 16 - y0),
            "east": (16 - z1, 16 - y1, 16 - z0, 16 - y0)}[face]


def turn(point, axis, angle):
    """A point turned the way a Java element is, about the origin."""
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    x, y, z = point
    if axis == "x":
        return (x, y * c - z * s, y * s + z * c)
    if axis == "y":
        return (x * c + z * s, y, -x * s + z * c)
    return (x * c - y * s, x * s + y * c, z)


def _turned_window(uv, quarter):
    """A window on a tile turned `quarter` degrees clockwise."""
    points = [(uv[0], uv[1]), (uv[2], uv[3])]
    for _ in range(quarter // 90 % 4):
        points = [(16 - v, u) for u, v in points]
    (a, b), (c, d) = points
    return min(a, c), min(b, d), max(a, c), max(b, d)


def _round(values):
    return [round(v, 6) for v in values]


def cubes(elements, texture_of, shift=(0, 0, 0)):
    """Format 2 cubes for Java elements.

    `texture_of(name)` answers a face's texture, a format 2 texture object or
    None for the block's own, given the Java texture variable without its `#`.
    `shift` moves every element, in pixels, before anything else.
    """
    out = []
    for element in elements:
        a = [element["from"][i] + shift[i] for i in range(3)]
        b = [element["to"][i] + shift[i] for i in range(3)]
        rotation = element.get("rotation")
        if rotation and rotation.get("angle") and rotation.get("rescale"):
            k = "xyz".index(rotation["axis"])
            stretch = 1 / math.cos(math.radians(rotation["angle"]))
            origin = [rotation.get("origin", [8, 8, 8])[i] + shift[i] for i in range(3)]
            for i in range(3):
                if i != k:
                    a[i] = origin[i] + (a[i] - origin[i]) * stretch
                    b[i] = origin[i] + (b[i] - origin[i]) * stretch
        size = [(b[i] - a[i]) / 16 for i in range(3)]
        offset = [(16 - b[0]) / 16, a[1] / 16, a[2] / 16]
        faces = {}
        for face in FACES:
            spec = element.get("faces", {}).get(face)
            if spec is None:
                faces[face] = dict(NOTHING)
                continue
            uv = spec.get("uv") or default_uv(face, element["from"], element["to"])
            quarter = int(spec.get("rotation", 0)) % 360
            ## seen from below a turn runs the other way
            if face == "down":
                quarter = -quarter % 360
            u1, v1, u2, v2 = _turned_window(uv, quarter)
            ## a window Java writes backwards reads its picture mirrored
            back_u, back_v = uv[0] > uv[2], uv[1] > uv[3]
            if face in ("up", "down"):
                back_u, back_v = not back_u, not back_v
            start = [u2 if back_u else u1, v2 if back_v else v1]
            span = [(u1 - u2) if back_u else (u2 - u1), (v1 - v2) if back_v else (v2 - v1)]
            read = {"uv": _round([n / 16 for n in start]),
                    "size": _round([n / 16 for n in span])}
            texture = texture_of(spec.get("texture", "#").lstrip("#"))
            if quarter:
                ## a turn has to say what it turns: the face's own slot, if
                ## nothing else is named
                texture = dict(texture or slot(face), turn=quarter)
            if texture is not None:
                read["texture"] = texture
            faces[face] = read
        cube = {"size": _round(size), "offset": _round(offset), "faces": faces}
        if rotation and rotation.get("angle"):
            corner, far = a, b
            middle = [(corner[i] + far[i]) / 2 for i in range(3)]
            origin = [rotation.get("origin", [8, 8, 8])[i] + shift[i] for i in range(3)]
            moved = turn([middle[i] - origin[i] for i in range(3)],
                         rotation["axis"], rotation["angle"])
            drift = [origin[i] + moved[i] - middle[i] for i in range(3)]
            cube["offset"] = _round([cube["offset"][0] - drift[0] / 16,
                                     cube["offset"][1] + drift[1] / 16,
                                     cube["offset"][2] + drift[2] / 16])
            k = "xyz".index(rotation["axis"])
            angles = [0, 0, 0]
            angles[k] = rotation["angle"] * (-1, -1, 1)[k]
            cube["rotation"] = angles
        out.append(cube)
    return out


OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east",
            "up": "up", "down": "down"}


def half_turned(elements):
    """Java elements turned half round about the middle of the block.

    Many Java models rest facing south, where the tables rest facing north. A
    box from (x0, z0) to (x1, z1) moves to (16 - x1, 16 - z1); each side face
    becomes the opposite one with the same window, and the top and bottom read
    theirs half round. A turn about x or z runs the other way.
    """
    out = []
    for element in elements:
        a, b = element["from"], element["to"]
        turned = dict(element)
        turned["from"] = [16 - b[0], a[1], 16 - b[2]]
        turned["to"] = [16 - a[0], b[1], 16 - a[2]]
        faces = {}
        for face, spec in element.get("faces", {}).items():
            spec = dict(spec)
            if "uv" not in spec:
                spec["uv"] = list(default_uv(face, a, b))
            if face in ("up", "down"):
                spec["rotation"] = (spec.get("rotation", 0) + 180) % 360
            faces[OPPOSITE[face]] = spec
        turned["faces"] = faces
        rotation = element.get("rotation")
        if rotation:
            origin = rotation.get("origin", [8, 8, 8])
            turned["rotation"] = dict(rotation, origin=[16 - origin[0], origin[1], 16 - origin[2]],
                                      angle=rotation["angle"] if rotation["axis"] == "y"
                                      else -rotation["angle"])
        out.append(turned)
    return out


def form(elements, texture_of, center=(0.5, 0.5, 0.5), shift=(0, 0, 0)):
    """One form from Java elements."""
    return {"center": list(center), "cubes": cubes(elements, texture_of, shift)}


def slot(name):
    """A texture object reading what the block declares for a face."""
    return {"slot": name}


def path(name):
    """A texture object naming a file outright."""
    return {"texture": name}


def resolved(textures, name):
    """A Java texture variable followed to the texture it names, or None."""
    seen = 0
    while seen < 10 and name in textures:
        name = textures[name]
        if not name.startswith("#"):
            return name.replace("minecraft:", "")
        name = name[1:]
        seen += 1
    return None


def unburied(elements, within=0.1):
    """Java's elements less any flat one lying a hair inside another's face.

    Java draws a plane like that under a solid top so the inside shows when the
    top is cut away. A ghost block draws both, and two faces that close fight
    for depth in game, so the plane shows through the picture above it.
    """
    def flat(element):
        return [axis for axis in range(3)
                if element["from"][axis] == element["to"][axis]]

    kept = []
    for element in elements:
        axes = flat(element)
        hidden = False
        for other in elements:
            if other is element or not axes or flat(other):
                continue
            axis = axes[0]
            level = element["from"][axis]
            inside = all(other["from"][a] <= element["from"][a] and
                         element["to"][a] <= other["to"][a]
                         for a in range(3) if a != axis)
            if inside and min(abs(level - other["from"][axis]),
                              abs(level - other["to"][axis])) < within:
                hidden = True
        if not hidden:
            kept.append(element)
    return kept


def model(name, texture_of, center=(0.5, 0.5, 0.5), half_turn=False, shift=(0, 0, 0),
          buried=True, y=0):
    """One form from a model in `java_models`.

    `texture_of(java_texture)` is handed the Java texture a face reads, such as
    "block/sea_pickle", and answers a format 2 texture object, or None for the
    block's own. `half_turn` turns a model that rests facing south to rest
    facing north.
    """
    from tools.blocks.java_models import MODELS
    found = MODELS[name]
    elements = found["elements"] if buried else unburied(found["elements"])
    elements = half_turned(elements) if half_turn else elements
    ## `y` turns the model clockwise seen from above, the way a blockstate does
    elements = turned(elements, y=y) if y else elements
    textures = found["textures"]
    ## a variable the model leaves open, as a template does, is handed on by
    ## its own name
    return form(elements, lambda var: texture_of(resolved(textures, var) or var),
                center, shift)


def bedrock(java_texture, renamed=None):
    """The Bedrock file a Java texture most likely is: its own name under
    `textures/blocks/`, unless `renamed` says otherwise."""
    if java_texture is None:
        return None
    short = java_texture.split("/")[-1]
    return path("textures/blocks/" + (renamed or {}).get(short, short))


TURN_Y = {"north": "east", "east": "south", "south": "west", "west": "north",
          "up": "up", "down": "down"}
FLIP_X = {"north": "south", "south": "north", "east": "east", "west": "west",
          "up": "down", "down": "up"}


def turned(elements, x=0, y=0, uvlock=False):
    """Java elements turned the way a blockstate turns a model.

    `x` is 0 or 180, turning the model upside down about the middle of the
    block, and is applied first; `y` is a multiple of 90, clockwise seen from
    above. With `uvlock` every face reads its own place in the block afterwards,
    so the picture stays where it is in the world rather than turning with the
    model, which is what Java does for fences, walls and stairs.
    """
    out = []
    for element in elements:
        a, b = list(element["from"]), list(element["to"])
        faces = {name: dict(spec) for name, spec in element.get("faces", {}).items()}
        rotation = dict(element["rotation"]) if element.get("rotation") else None
        for name, spec in faces.items():
            if "uv" not in spec:
                spec["uv"] = list(default_uv(name, element["from"], element["to"]))
        if x % 360 == 180:
            a, b = [a[0], 16 - b[1], 16 - b[2]], [b[0], 16 - a[1], 16 - a[2]]
            flipped = {}
            for name, spec in faces.items():
                if name not in ("up", "down"):
                    spec["rotation"] = (spec.get("rotation", 0) + 180) % 360
                flipped[FLIP_X[name]] = spec
            faces = flipped
            if rotation:
                o = rotation.get("origin", [8, 8, 8])
                rotation["origin"] = [o[0], 16 - o[1], 16 - o[2]]
                if rotation["axis"] != "x":
                    rotation["angle"] = -rotation["angle"]
        for _ in range(y // 90 % 4):
            a, b = [16 - b[2], a[1], a[0]], [16 - a[2], b[1], b[0]]
            turned_faces = {}
            for name, spec in faces.items():
                if name == "up":
                    spec["rotation"] = (spec.get("rotation", 0) + 90) % 360
                elif name == "down":
                    spec["rotation"] = (spec.get("rotation", 0) - 90) % 360
                turned_faces[TURN_Y[name]] = spec
            faces = turned_faces
            if rotation:
                o = rotation.get("origin", [8, 8, 8])
                rotation["origin"] = [16 - o[2], o[1], o[0]]
                if rotation["axis"] == "x":
                    rotation["axis"] = "z"
                elif rotation["axis"] == "z":
                    rotation["axis"] = "x"
                    rotation["angle"] = -rotation["angle"]
        if uvlock:
            for name, spec in faces.items():
                spec["uv"] = list(default_uv(name, a, b))
                spec.pop("rotation", None)
        moved = {"from": a, "to": b, "faces": faces}
        if rotation:
            moved["rotation"] = rotation
        out.append(moved)
    return out


def parts(pieces, textures_of):
    """Several Java models put together the way a multipart blockstate does:
    `pieces` is a list of (model name, x, y, uvlock). The elements of each are
    turned and their texture variables resolved to Java texture names."""
    from tools.blocks.java_models import MODELS
    elements = []
    for name, x, y, uvlock in pieces:
        found = MODELS[name]
        for element in turned(found["elements"], x, y, uvlock):
            for spec in element["faces"].values():
                variable = spec.get("texture", "#")[1:]
                spec["texture"] = "#" + (resolved(found["textures"], variable) or variable)
            elements.append(element)
    return elements
