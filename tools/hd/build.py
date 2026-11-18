#!/usr/bin/env python3
"""Builds the HD backdrops (Media/Themes/<Base>HD<Colour>.tga) with MaterialCraft.

Each recipe (tools/hd/recipes.py) makes tileable source fields in numpy
(fields.py) and a MaterialCraft graph over them: warps, gradient maps for
the colour, emboss for the light (WoW's UI draws no normal maps, so relief
and shading are baked into the colour). The graph is saved as
tools/hd/graphs/<name>.sbs with its source bitmaps, so it opens in the
MaterialCraft app (not committed: deterministic, the build makes them
again); the cooked base colour becomes the TGA.

    python3 tools/hd/build.py                 every texture
    python3 tools/hd/build.py WoodHDOak ...   some
    python3 tools/hd/build.py --preview DIR   also a 3x2 tiled PNG per texture

Needs materialcraft-cli (MaterialCraft 0.4.1+, Apache-2.0) on PATH,
Pillow and numpy. Deterministic: every recipe seeds its own generator.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "Media", "Themes")
GRAPHS = os.path.join(HERE, "graphs")
SIZE = 256          # LibForeverThemes TILE_HD
CLI = "materialcraft-cli"
USAGE = {"base": 0, "height": 4}


class Graph:
    """A MaterialCraft graph built as a list of engine commands (batch)."""

    def __init__(self, name):
        self.name = name
        self.steps = []
        self.next_id = 1
        self.res = os.path.join(GRAPHS, name + ".resources")

    def bitmap(self, label, field):
        """A 16-bit grey source bitmap from a 0..1 field; returns its node id."""
        os.makedirs(self.res, exist_ok=True)
        label = f"{label}{self.next_id}"     # unique: a second "red" would overwrite the first
        path = os.path.join(self.res, label + ".png")
        Image.fromarray((np.clip(field, 0, 1) * 65535).astype(np.uint16)).save(path)
        self.steps.append({"id": "file.importBitmap", "params": {"path": path, "name": label}})
        self.steps.append({"id": "graph.resource.add", "params": {"resource": label}})
        return self._take()

    def node(self, kind, params=None, **inputs):
        """An atomic node; inputs port=node id (or (node id, output port))."""
        self.steps.append({"id": "graph.node.add", "params": {"def": kind, "params": params or {}}})
        nid = self._take()
        for port, src in inputs.items():
            src_id, src_port = src if isinstance(src, tuple) else (src, "output")
            self.steps.append({"id": "graph.connect",
                               "params": {"from": src_id, "fromPort": src_port, "to": nid, "toPort": port}})
        return nid

    def output(self, src, identifier, usage):
        self.node("output", {"identifier": identifier, "usage": USAGE[usage]}, input=src)

    def _take(self):
        nid = self.next_id
        self.next_id += 1
        return nid


def linear(c):
    """sRGB 0..1 to linear: MaterialCraft holds colours linear and writes sRGB."""
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def gradient(stops):
    """A gradient_map value from [(pos, (r, g, b)), ...] in sRGB 0..1."""
    keys = [{"pos": p, "color": [*linear(c), 1.0], "midpoint": 0.5} for p, c in stops]
    return {"t": "gradient", "v": {"keys": keys}}


def run(*args):
    done = subprocess.run([CLI, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{CLI} {args[0]} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def cook(graph, work):
    """Saves the graph package and exports its base colour; returns RGBA floats."""
    sbs = os.path.join(GRAPHS, graph.name + ".sbs")
    empty = os.path.join(work, "empty.sbs")
    run("new", "empty", empty, "--size", str(SIZE), "--name", graph.name)
    script = os.path.join(work, "batch.json")
    with open(script, "w") as f:
        json.dump({"open": empty, "steps": graph.steps, "save": sbs}, f)
    result = json.loads(run("batch", script))
    if result.get("failed"):
        raise RuntimeError(f"{graph.name}: step failed: {json.dumps(result['failed'])[:600]}")
    out = os.path.join(work, "out")
    run("export", sbs, out, "--format", "png", "--depth", "16")
    path = os.path.join(out, f"{graph.name}_base.png")
    img = np.asarray(Image.open(path), dtype=np.float64)
    img = img / (65535.0 if img.max() > 255 else 255.0)
    if img.ndim == 2:
        img = np.stack([img] * 3, -1)
    if img.shape[-1] == 3:
        img = np.concatenate([img, np.ones(img.shape[:2] + (1,))], -1)
    return img


def save_tga(rgba, name):
    img = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    img.save(os.path.join(OUT, name + ".tga"))
    return img


def main(argv):
    import recipes
    preview = None
    if "--preview" in argv:
        i = argv.index("--preview")
        preview = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
        os.makedirs(preview, exist_ok=True)
    names = argv or list(recipes.RECIPES)
    work = os.path.join(HERE, ".work")
    for name in names:
        if name not in recipes.RECIPES:
            sys.exit(f"unknown texture {name} (known: {', '.join(recipes.RECIPES)})")
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        graph = Graph(name)
        shutil.rmtree(graph.res, ignore_errors=True)
        post = recipes.RECIPES[name](graph, np.random.default_rng(abs(hash_name(name))))
        rgba = cook(graph, work)
        if post:
            rgba = post(rgba)
        img = save_tga(rgba, name)
        mean = rgba[..., :3].mean()
        print(f"{name}: mean {mean:.3f}")
        if preview:
            sheet = Image.new("RGBA", (SIZE * 3, SIZE * 2))
            for x in range(3):
                for y in range(2):
                    sheet.paste(img, (x * SIZE, y * SIZE))
            sheet.save(os.path.join(preview, name + ".png"))
    shutil.rmtree(work, ignore_errors=True)


def hash_name(name):
    """A stable seed from the name (Python's hash() changes per run)."""
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) % 2 ** 31
    return h


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main(sys.argv[1:])
