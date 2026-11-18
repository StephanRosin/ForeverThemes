#!/usr/bin/env python3
"""Builds the HD backdrops (Media/Themes/<Base>HD<Colour>.tga) from CC0
photo scans (ambientCG, CC0 1.0) plus designed layers.

Each texture starts from a scanned material (colour and normal map, 1K,
seamless), scaled to the 256 px tile (LibForeverThemes TILE_HD; repeat 2 =
the scan twice per tile), lit from the top left through its normal map
(WoW's UI draws no normal maps, so the relief is baked in) and graded
around a target colour; then a designed layer gives it construction
(planks, ashlar slabs, vellum fibres and foxing, steel panels, a hairline
grid, fractures, aurora ribbons, a leaded lattice with jewels, print
processes, circuit traces), and the mean lands on the old theme's
on-screen brightness in that colour (OLD), so texts read as before.

    python3 tools/hd/build.py [names] [--preview DIR]

Sources are fetched once into ~/.cache/forever-photo/src (not committed;
the asset ids in TEXTURES pin them). Needs Pillow and numpy. Deterministic.
"""
import os
import sys
import urllib.request
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "Media", "Themes")
SRC = os.path.expanduser("~/.cache/forever-photo/src")
SIZE = 256
LIGHT = np.array((-0.55, 0.55, 0.63))          # from the top left (GL normals: +y up)


# The old theme's on-screen mean in the matching colour (texture x tint, or
# the colour's back): what the HD variant lands on, so texts read as before.
OLD = {
    "WoodHDOak": 0.158, "WoodHDWalnut": 0.10, "WoodHDEbony": 0.075, "WoodHDDriftwood": 0.23,
    "TechHDCarbon": 0.076, "TechHDSteel": 0.077, "TechHDCircuit": 0.065,
    "ParchmentHDClassic": 0.339, "ParchmentHDAged": 0.24, "ParchmentHDAsh": 0.323,
    "RunestoneHDGranite": 0.201, "RunestoneHDSlate": 0.193, "RunestoneHDSandstone": 0.26,
    "RunestoneHDObsidian": 0.072,
    "GlassHDCathedral": 0.203, "GlassHDSapphire": 0.16, "GlassHDEmerald": 0.14, "GlassHDRuby": 0.14,
    "ComicHDNewsprint": 0.672, "ComicHDPulp": 0.664, "ComicHDPop": 0.597, "ComicHDNoir": 0.152,
    "FrostHDIce": 0.35, "FrostHDDeep": 0.2, "FrostHDAurora": 0.203,
}


def soft_dots(rng, chance, radius, halo=0.0):
    """Soft round spots (foxing): a dark core of radius px, minus an
    optional lighter halo around it (negative values)."""
    from fields import blur
    seed = (rng.random((SIZE, SIZE)) > chance).astype(float)
    core = np.clip(blur(seed, radius) * radius * radius * 6, 0, 1)
    if halo:
        ring = np.clip(blur(seed, radius * 2.2) * radius * radius * 10, 0, 1) - core
        core = core - np.clip(ring, 0, 1) * halo
    return core


def dots45(spacing, coverage, ss=4):
    """A halftone screen at 45 degrees: round dots on the diagonal lattice
    (h, h) / (h, -h), h = spacing / 2 (spacing must divide SIZE or the tile
    shows a seam), supersampled ss x ss for round edges. Each dot's area is
    coverage (0..1, per pixel)."""
    assert SIZE % spacing == 0, f"halftone spacing {spacing} does not tile {SIZE}"
    h = spacing / 2
    n = SIZE * ss
    yy, xx = (np.mgrid[0:n, 0:n].astype(float) + 0.5) / ss
    u, v = np.round((xx + yy) / (2 * h)), np.round((xx - yy) / (2 * h))
    cx, cy = h * (u + v), h * (u - v)
    d = np.hypot(xx - cx, yy - cy)
    cov = np.repeat(np.repeat(np.broadcast_to(coverage, (SIZE, SIZE)), ss, 0), ss, 1)
    radius = np.sqrt(np.clip(cov, 0, 1) * 2 * h * h / np.pi)
    disc = np.clip(radius - d + 0.5, 0, 1)                         # anti-aliased edge before the box filter
    return disc.reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))


def fetch(asset):
    """The asset's 1K JPG set from ambientCG, cached; returns its folder."""
    folder = os.path.join(SRC, asset)
    if not os.path.exists(os.path.join(folder, f"{asset}_1K-JPG_Color.jpg")):
        os.makedirs(folder, exist_ok=True)
        archive = os.path.join(folder, asset + ".zip")
        req = urllib.request.Request(f"https://ambientcg.com/get?file={asset}_1K-JPG.zip",
                                     headers={"User-Agent": "texture-fetch/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(archive, "wb") as f:
            f.write(r.read())
        with zipfile.ZipFile(archive) as z:
            z.extractall(folder)
        os.remove(archive)
    return folder


def load(asset, repeat=1):
    """(colour sRGB 0..1, normal -1..1) of the asset at SIZE, the source repeat x repeat times."""
    folder = fetch(asset)

    def img(kind, mode):
        im = Image.open(os.path.join(folder, f"{asset}_1K-JPG_{kind}.jpg")).convert(mode)
        if repeat > 1:
            big = Image.new(mode, (im.width * repeat, im.height * repeat))
            for x in range(repeat):
                for y in range(repeat):
                    big.paste(im, (x * im.width, y * im.height))
            im = big
        return np.asarray(im.resize((SIZE, SIZE), Image.LANCZOS), float) / 255

    return img("Color", "RGB"), img("NormalGL", "RGB") * 2 - 1


def luminance(rgb):
    rgb = np.asarray(rgb, float)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def relief(normal, strength):
    """Light from the top left as a multiplier around 1."""
    n = normal / np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-6)
    shade = n @ (LIGHT / np.linalg.norm(LIGHT))
    return 1 + (shade - shade.mean()) * strength


def grade(rgb, target, sat=0.6, contrast=1.0, hue=None):
    """The photo's variation around target (sRGB 0..255): sat of its own
    colour variation (the rest follows its luminance), contrast an exponent
    on it; hue: an optional (rgb, weight-field) pair mixed into the shadows."""
    mean = rgb.reshape(-1, 3).mean(0)
    lum = luminance(rgb)
    rel = rgb / np.maximum(mean, 1e-4)
    rel_l = (lum / max(lum.mean(), 1e-4))[..., None]
    mix = rel_l * (1 - sat) + rel * sat
    out = np.array(target, float) / 255 * np.maximum(mix, 0) ** contrast
    if hue is not None:
        tint, weight = hue
        out = out * (1 - weight[..., None]) + out * np.array(tint) * weight[..., None]
    return out


def land(rgb, name):
    """Mean brought to the old theme's brightness in this colour."""
    target = OLD[name]
    return np.clip(rgb * target / max(rgb.mean(), 1e-6), 0, 1)


def flatten(rgb, amount, sigma=48):
    """Divides out amount of the tile-scale light and dark (what shows the
    repeat), keeping the fine detail."""
    from fields import blur
    lum = luminance(rgb)
    low = blur(lum, sigma)
    return rgb / ((low / low.mean()) ** amount)[..., None]


def sharpen(rgb, amount=0.6):
    """Unsharp mask (radius 1): the downscale smears pores and fibres."""
    from fields import blur
    soft = np.stack([blur(rgb[..., c], 1) for c in range(3)], -1)
    return rgb + (rgb - soft) * amount


def groove_lines(horizontal, vertical, width):
    """0..1 mask of grooves: rows in horizontal, (x, y0, y1) cuts in vertical."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
    d = np.full((SIZE, SIZE), 99.0)
    for y in horizontal:
        dy = np.abs(yy - y)
        d = np.minimum(d, np.minimum(dy, SIZE - dy))
    for x, y0, y1 in vertical:
        dx = np.abs(xx - x)
        dx = np.minimum(dx, SIZE - dx)
        inside = (yy >= y0) & (yy < y1)
        d = np.where(inside, np.minimum(d, dx), d)
    return np.clip(1 - (d - width / 2 + 0.5), 0, 1)


def carve(rgb, mask, depth, lip, offset=1):
    """Incised mask lit from the top left: dark in the cut, a lit lip just
    below and right of it, a shadowed one above and left."""
    below = np.clip(np.roll(mask, (offset, offset), axis=(0, 1)) - mask, 0, 1)
    above = np.clip(np.roll(mask, (-offset, -offset), axis=(0, 1)) - mask, 0, 1)
    shade = 1 - mask * depth + below * lip - above * lip * 0.5
    return rgb * shade[..., None]


def planks(lip=1.0, nail=1.0, seam=0.4, heights=(58, 70, 62, 66)):
    """Four 64 px boards per tile: rows 0 and 2 run unbroken, rows 1 and 3
    have a butt joint each (at least 60 px apart); every board and segment
    is cut from its own spot of the scan (some mirrored), ±8 % tone per
    board, ±3 % per segment. Long seams eased (lit below, shaded above),
    butt joints finer; lip: the lit edge's additive floor (dark woods need
    it, light ones not); two nail heads at each joint."""
    assert sum(heights) == SIZE
    tops = np.cumsum((0,) + tuple(heights[:-1]))

    def layer(rgb, rng):
        out = np.empty_like(rgb)
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        bevel = np.ones((SIZE, SIZE))
        joints, nails = [], []
        prev = None
        for board, (top, board_h) in enumerate(zip(tops, heights)):
            tone = rng.uniform(0.92, 1.08)
            if board % 2:
                jx = int(rng.integers(0, SIZE))
                while prev is not None and min(abs(jx - prev), SIZE - abs(jx - prev)) < 60:
                    jx = int(rng.integers(0, SIZE))
                prev = jx
                segs = ((jx, int(rng.integers(100, 157))),)
                segs = ((jx, segs[0][1]), ((jx + segs[0][1]) % SIZE, SIZE - segs[0][1]))
                joints += [(jx, top, top + board_h), ((jx + segs[0][1]) % SIZE, top, top + board_h)]
                nails += [(x + 4, top + board_h * f) for x in (jx, (jx + segs[0][1]) % SIZE) for f in (0.25, 0.75)]
            else:
                segs = ((0, SIZE),)
            for start, length in segs:
                cols = ((np.arange(SIZE) - start) % SIZE) < length
                src = np.roll(rgb, (int(rng.integers(0, SIZE)), int(rng.integers(0, SIZE))), axis=(0, 1))
                if rng.random() < 0.5:
                    src = src[:, ::-1]
                out[top:top + board_h, cols] = src[top:top + board_h, cols] * tone * rng.uniform(0.97, 1.03)
            below = (yy - top) % SIZE
            above = (top + board_h - yy) % SIZE
            bevel *= np.where(below < 5, 1 + 0.1 * (1 - below / 5), 1)
            bevel *= np.where((above > 0) & (above < 5), 1 - 0.14 * (1 - above / 5), 1)
        for x, top, bottom in joints:
            inside = (yy >= top) & (yy < bottom)
            right = (xx - x) % SIZE
            left = (x - xx) % SIZE
            bevel *= np.where(inside & (right < 4), 1 + 0.05 * (1 - right / 4), 1)
            bevel *= np.where(inside & (left > 0) & (left < 4), 1 - 0.07 * (1 - left / 4), 1)
        out = out * bevel[..., None]
        floor = out.mean() * 0.25 * lip
        seams = groove_lines(list(tops), [], 2.0)
        butts = groove_lines([], joints, 1.0)
        for mask, depth in ((seams, seam), (butts, 0.3)):
            lit = np.clip(np.roll(mask, (1, 1), axis=(0, 1)) - mask, 0, 1)
            out = out * (1 - mask[..., None] * depth) + lit[..., None] * floor * 2.5
        for nx, ny in (nails if nail else []):
            dx = (xx - nx + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - ny + SIZE / 2) % SIZE - SIZE / 2
            d = np.hypot(dx, dy)
            head = np.clip(2.2 - d + 0.5, 0, 1)
            lit = np.clip(1 - np.abs(np.hypot(dx - 1, dy - 1) - 2.2), 0, 1) * (1 - head)
            shade = np.clip(1 - np.abs(np.hypot(dx + 1, dy + 1) - 2.2), 0, 1) * (1 - head)
            out = out * (1 - (head[..., None] * 0.6 + shade[..., None] * 0.3) * nail) + lit[..., None] * out.mean() * 0.9 * nail
        return out
    return layer


def ashlar(tone=0.08, depth=0.4, lip=0.2, lip_tint=(1, 1, 1)):
    """Dressed stone slabs: two courses of unequal height (104 and 152 px),
    one vertical joint each at an irregular x; every slab shows the scan at
    its own offset (some flipped) and tone, with a soft worn edge (lighter
    top left, darker bottom right) and a few chipped corners; chiselled
    joints that wander a little. lip_tint: the lit lip's colour (on black
    stone the lip, not the groove, draws the slabs)."""
    def layer(rgb, rng):
        from fields import fbm, warp
        out = np.empty_like(rgb)
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        edge = np.ones((SIZE, SIZE))
        courses = ((0, 104), (104, SIZE))
        joints, verticals, corners = [], [0, 104], []
        for top, bottom in courses:
            jx = int(rng.integers(40, 216))
            other = (jx + int(rng.integers(90, 166))) % SIZE
            for x0, x1 in ((jx, other), (other, jx + SIZE)):
                width = (x1 - x0) % SIZE or SIZE
                cols = ((np.arange(SIZE) - x0) % SIZE) < width
                src = np.roll(rgb, tuple(rng.integers(0, SIZE, 2)), axis=(0, 1))
                if rng.random() < 0.5:
                    src = src[:, ::-1]
                out[top:bottom, cols] = src[top:bottom, cols] * rng.uniform(1 - tone, 1 + tone)
                inside = (yy >= top) & (yy < bottom) & cols[None, :]
                fx, fy = (xx - x0) % SIZE, yy - top
                near = np.minimum(fx, fy)
                far = np.minimum(width - fx, bottom - top - fy)
                edge = np.where(inside, edge * (1 + 0.05 * np.clip(1 - near / 6, 0, 1))
                                * (1 - 0.05 * np.clip(1 - far / 6, 0, 1)), edge)
                if rng.random() < 0.5:
                    corners.append((x0, top))
            joints += [(jx, top, bottom), (other, top, bottom)]
        out = out * edge[..., None]
        mask = groove_lines(verticals, joints, 3)
        for cx, cy in corners:            # a chip: the groove widens into a small broken triangle
            dx = (xx - cx + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - cy + SIZE / 2) % SIZE - SIZE / 2
            chip = np.clip(rng.uniform(4, 7) - (np.abs(dx) + np.abs(dy)) + 0.5, 0, 1) * (dx > -1) * (dy > -1)
            mask = np.maximum(mask, chip)
        dx = (fbm(rng, SIZE, 4, octaves=2) - 0.5) * 3
        dy = (fbm(rng, SIZE, 4, octaves=2) - 0.5) * 3
        mask = warp(mask, dx, dy)
        below = np.clip(np.roll(mask, (2, 2), axis=(0, 1)) - mask, 0, 1)
        above = np.clip(np.roll(mask, (-2, -2), axis=(0, 1)) - mask, 0, 1)
        out = out * (1 - mask * depth - above * lip * 0.5)[..., None] * 1 \
            + out * below[..., None] * lip * np.array(lip_tint)
        return out
    return layer


def material(asset, target, repeat=1, sat=0.6, contrast=1.0, light=1.2, shadow_hue=None, stain=None,
             flat=0.0, sharp=0.0, layout=None, median=False):
    """stain: (asset, strength) - a second scan's light and dark laid over
    as mottling (age, wear) where the first is too clean. flat: share of
    the tile-scale banding removed; sharp: unsharp amount; layout: a
    designed layer on top (planks, ashlar)."""
    def make(name):
        rng = np.random.default_rng(sum(map(ord, name)) * 31)
        rgb, normal = load(asset, repeat)
        if median:      # speckle baked into the scan's colour
            from PIL import ImageFilter
            im = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).filter(ImageFilter.MedianFilter(3))
            rgb = np.asarray(im, float) / 255
        if stain:
            other, strength = stain
            lum = luminance(load(other, 1)[0])
            rgb = rgb * ((lum / lum.mean()) ** strength)[..., None]
        if flat:
            rgb = flatten(rgb, flat)
        if sharp:
            rgb = np.clip(sharpen(rgb, sharp), 0, None)
        hue = None
        if shadow_hue:
            lum = luminance(rgb)
            hue = (shadow_hue, np.clip(1 - lum / max(lum.mean(), 1e-4), 0, 1))
        out = grade(rgb, target, sat, contrast, hue) * relief(normal, light)[..., None]
        if layout:
            out = layout(out, rng)
        return land(out, name)
    return make


# Designed layers over the photo (layout functions: (rgb, rng) -> rgb) ----

def wrap_draw(strokes, width, k=4):
    """Anti-aliased 0..1 mask of polylines in px, drawn wrapping (each
    stroke also one tile over in every direction)."""
    from PIL import ImageDraw
    big = Image.new("L", (SIZE * k, SIZE * k))
    d = ImageDraw.Draw(big)
    for pts in strokes:
        for ox in (-SIZE, 0, SIZE):
            for oy in (-SIZE, 0, SIZE):
                q = [((x + ox) * k, (y + oy) * k) for x, y in pts]
                d.line(q, fill=255, width=max(1, int(width * k)), joint="curve")
    return np.asarray(big.resize((SIZE, SIZE), Image.LANCZOS), float) / 255


def fibre_mask(rng, count, lmin, lmax):
    """Bent fibres: three-point polylines (midpoint off by up to ±15 % of
    the length), each its own strength and width, anti-aliased, wrapping."""
    out = np.zeros((SIZE, SIZE))
    for width in (0.75, 1.0, 1.25):
        for _ in range(count // 3):
            x, y = rng.random(2) * SIZE
            length, ang = rng.uniform(lmin, lmax), rng.uniform(0, np.pi)
            ex, ey = x + np.cos(ang) * length, y + np.sin(ang) * length
            bend = rng.uniform(-0.15, 0.15) * length
            mx, my = (x + ex) / 2 - np.sin(ang) * bend, (y + ey) / 2 + np.cos(ang) * bend
            strength = 0.4 + 1.2 * rng.random() ** 3        # a few fibres carry, the rest stay subliminal
            out = np.maximum(out, wrap_draw([[(x, y), (mx, my), (ex, ey)]], width) * strength)
    return out


def vellum(foxing=0.5, tide=0.0, soot=0.0, wash=0.08, fibres=0.04, tint=(1.04, 0.97, 0.88), scuffs=0.0, dark=True):
    """Paper life: a slow wash (its darks tinted), bent light and dark
    fibres, rust foxing in clusters, broken tide lines, soot smudges,
    pale scuffs (wear that shows on dark grounds)."""
    def layer(rgb, rng):
        from fields import fbm, smoothstep, blur
        w = fbm(rng, SIZE, 3, octaves=4, gain=0.6) - 0.5
        fine = fbm(rng, SIZE, 8, octaves=2) - 0.5
        light_f = fibre_mask(rng, 110, 6, 28)
        dark_f = fibre_mask(rng, 60, 6, 20) if dark else 0
        shade = 1 + w * wash * 2 + fine * 0.08 + light_f * fibres - dark_f * fibres * 0.7
        out = rgb * shade[..., None]
        darkish = np.clip(-w * 2, 0, 1)[..., None]
        out = out * (1 - darkish) + out * np.array(tint) * darkish
        if scuffs:
            patch = smoothstep(0.55, 0.75, fbm(rng, SIZE, 3, octaves=3))[..., None]
            out = out * (1 + patch * scuffs * np.array((1.06, 1.0, 0.86)))
        if foxing:
            clusters = smoothstep(0.58, 0.72, fbm(rng, SIZE, 4))
            fox = np.zeros((SIZE, SIZE))
            for radius, chance in ((0.7, 0.9975), (1.5, 0.999), (2.8, 0.9997), (5.0, 0.99993)):
                fox = np.maximum(fox, soft_dots(rng, chance, radius, halo=0.6))
            fox = np.clip(fox * clusters * foxing, -0.2, 1)
            rust = np.array((0.85, 0.55, 0.32))
            out = out * (1 - fox[..., None] * 0.25) + out * rust * fox[..., None] * 0.25
        if tide:
            st = fbm(rng, SIZE, 3, octaves=4)
            ring = np.clip(1 - np.abs(st - 0.62) / 0.012, 0, 1) * smoothstep(0.35, 0.6, fbm(rng, SIZE, 5, octaves=3))
            out = out * (1 - ring[..., None] * tide * 0.25)
        if soot:
            flecks = np.clip(blur((rng.random((SIZE, SIZE)) > 0.9997).astype(float), 1.6) * 20, 0, 1)
            out = out * (1 - flecks[..., None] * soot)
        return out
    return layer


def hairgrid(colour, step=64, amount=0.07):
    """A fine lit grid (tech HUD), brighter at the crossings."""
    def layer(rgb, rng):
        yy, xx = np.mgrid[0:SIZE, 0:SIZE] % step
        line = ((yy == 0) | (xx == 0)).astype(float)
        cross = ((yy == 0) & (xx == 0)).astype(float)
        from fields import blur
        glow = np.clip(blur(cross, 1.5) * 12, 0, 1)
        add = (line * amount + glow * amount * 1.5)[..., None] * np.array(colour)
        return rgb + add
    return layer


def panels(rgb, rng):
    """Steel plates in running bond (128 px, the lower row shifted 64 px),
    each its own tone, seams with a lit lip and four rivets per plate."""
    half, quarter = SIZE // 2, SIZE // 4
    out = rgb.copy()
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
    rivets, joints = [], []
    for r, shift in ((0, 0), (1, quarter)):
        for c in range(2):
            x0 = c * half + shift
            cols = ((np.arange(SIZE) - x0) % SIZE) < half
            out[r * half:(r + 1) * half, cols] *= rng.uniform(0.8, 1.2)
            joints.append((x0 % SIZE, r * half, (r + 1) * half))
            for dy in (9, half - 9):
                for dx in (9, half - 9):
                    rivets.append(((x0 + dx) % SIZE, r * half + dy))
    out = carve(out, groove_lines([0, half], joints, 1.6), 0.6, 0.8)
    for cx, cy in rivets:
        d = np.hypot(xx - cx, yy - cy)
        head = np.clip(2.6 - d + 0.5, 0, 1)
        lit = np.clip(((cx - xx) + (cy - yy)) / 3.6, -1, 1) * head
        ring = np.clip(1 - np.abs(d - 3.2), 0, 1)
        out = out * (1 + lit[..., None] * 1.3 - ring[..., None] * 0.5)
    return out


def fractures(count=3, amount=0.1):
    """A few long faint fracture planes: a bright line with a dark twin."""
    def layer(rgb, rng):
        strokes = []
        for _ in range(count):
            x, y = rng.random(2) * SIZE
            pts = [(x, y)]
            ang = rng.uniform(-0.8, 0.8)
            for _ in range(5):
                ang += rng.uniform(-0.9, 0.9)
                x, y = x + np.cos(ang) * 30, y + np.sin(ang) * 30
                pts.append((x, y))
            strokes.append(pts)
        m = wrap_draw(strokes, 1.0)
        dark = np.roll(m, (1, 1), axis=(0, 1))
        return rgb * (1 + m[..., None] * amount * 3 - dark[..., None] * amount * 1.5)
    return layer


def ribbons(c1, c2, amount=0.12):
    """Aurora: two soft diagonal ribbons, colour drifting c1 to c2, warped."""
    def layer(rgb, rng):
        from fields import fbm
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) / SIZE
        warp = (fbm(rng, SIZE, 2, octaves=3) - 0.5) * 0.25
        phase = (xx + yy + warp) * 2 * np.pi                   # one ribbon across the tile
        band = np.clip(np.sin(phase), 0, 1) ** 3
        mix = (np.sin((xx - yy + warp) * 2 * np.pi) * 0.5 + 0.5)[..., None]
        tint = np.array(c1) * (1 - mix) + np.array(c2) * mix
        return rgb * (1 - band[..., None] * amount) + tint * band[..., None] * amount * rgb.mean() * 4
    return layer


def chain(*layers):
    def layer(rgb, rng):
        for f in layers:
            rgb = f(rgb, rng)
        return rgb
    return layer


# Glass ----------------------------------------------------------------------

def glass(palette, accents, glass_asset="Ice004", cols=4, rows=3, rim=(0.75, 0.82, 0.95), level=0.3,
          pane_tex=0.2, jewel_gain=1.0):
    """Leaded quarries over real rolled glass: every pane samples the scan
    at its own offset (no vein runs through the lead), value drift per
    pane, a soft glow from the centre; cames with body, a lit upper-left
    flank and solder blobs; jewel quarries on a regular sub-lattice of
    crossings; each pane lit by its own slight gradient."""
    def make(name):
        tex, _ = load(glass_asset, 1)
        t = luminance(tex)
        t = (t - t.mean()) / max(t.std(), 1e-4)
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        a, b = SIZE / cols, SIZE / rows
        u, v = xx / a + yy / b, xx / a - yy / b
        norm = np.hypot(1 / a, 1 / b)
        du, dv = np.abs(u - np.round(u)) / norm, np.abs(v - np.round(v)) / norm
        d = np.minimum(du, dv)
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        n = (2 * cols, 2 * rows)
        ka, kb = (i + j) % n[0], (i - j) % n[1]
        rng = np.random.default_rng(len(name) * 7919 + sum(map(ord, name)))
        pal = np.stack([np.array(c, float) * level / luminance(c) for c in palette])
        tone = (1 + rng.uniform(-0.18, 0.18, n))[ka, kb][..., None]
        base = pal[rng.integers(0, len(palette), n)[ka, kb]] * tone
        ox, oy = rng.integers(0, SIZE, n), rng.integers(0, SIZE, n)
        flip = rng.integers(0, 2, n).astype(bool)
        sx = (xx.astype(int) + ox[ka, kb]) % SIZE
        sy = (yy.astype(int) + oy[ka, kb]) % SIZE
        pane_t = np.where(flip[ka, kb], t[sx, sy], t[sy, sx])
        # jewels: whole mini-quarries, one accent per row of crossings,
        # 128 px apart and staggered row to row, lighter than their field
        jewel = np.zeros((SIZE, SIZE))
        jcol = np.zeros((SIZE, SIZE, 3))
        shine = np.zeros((SIZE, SIZE))
        def jewel_colour(c):            # lighter than the field; red glows harder, so less of it; max channel capped
            c = np.array(c, float) * level * jewel_gain * (1.6 if c[0] > 2 * max(c[1], c[2]) else 2.4) / luminance(c)
            return c * min(1.0, 0.9 * jewel_gain / c.max())
        apal = [jewel_colour(c) for c in accents]
        facet = np.zeros((SIZE, SIZE))
        for r in range(rows):
            for k in range(2):
                S, D = (2 * r + 4 * k) % (2 * cols), 2 * r
                px, py = S / 2 * a, D / 2 * b
                dx = (xx - px + SIZE / 2) % SIZE - SIZE / 2
                dy = (yy - py + SIZE / 2) % SIZE - SIZE / 2
                rr = np.abs(dx) / (a * 0.22) + np.abs(dy) / (b * 0.22)
                m = np.clip((1 - rr) * 12, 0, 1)
                jewel = np.maximum(jewel, m)
                jcol = np.where((m > 0)[..., None], m[..., None] * apal[r % len(apal)], jcol)
                facet = np.where(m > 0, np.clip(-(dx / (a * 0.22) + dy / (b * 0.22)), -1, 1), facet)
                shine = np.maximum(shine, np.clip(1 - np.hypot(dx + 3, dy + 4) / 3, 0, 1) * m)
        fu, fv = u - np.floor(u), v - np.floor(v)
        theta = rng.uniform(0, 2 * np.pi, n)[ka, kb]
        slope = (np.cos(theta) * (fu - 0.5) + np.sin(theta) * (fv - 0.5)) * 0.3
        core = np.clip((d - 2.5) / 6, 0, 1)
        shade = (0.88 + core * 0.16) * (1 + pane_t * pane_tex) * (1 + slope)
        rgb = base * shade[..., None]
        rgb = rgb * (1 - jewel[..., None]) + jcol * (1 + pane_t[..., None] * 0.3 + facet[..., None] * 0.12) \
            + shine[..., None] * 0.35
        lead = 1 - np.clip((d - 1.6) / 0.9, 0, 1)
        joint = 1 - np.clip((np.hypot(du, dv) - 3.0), 0, 1)
        lead = np.maximum(lead, joint) * (1 - np.clip(jewel * 1.5, 0, 1))
        jedge = np.clip(1 - np.abs(jewel - 0.5) * 2.2, 0, 1)
        lead = np.maximum(lead, jedge)
        flank = np.clip(lead - np.roll(lead, (1, 1), axis=(0, 1)), 0, 1)    # upper-left side of the came
        rgb = rgb * (1 - lead[..., None]) + lead[..., None] * 0.06 + flank[..., None] * np.array(rim) * 0.35
        return land(rgb, name)
    return make


# Comic ----------------------------------------------------------------------

def screen(spacing, coverage, angle45=True, offset=(0, 0), ss=4):
    """Round halftone dots on a square (0 degrees) or diagonal (45) lattice."""
    if angle45:
        return np.roll(dots45(spacing, coverage, ss), offset, axis=(0, 1))
    assert SIZE % spacing == 0
    n = SIZE * ss
    yy, xx = (np.mgrid[0:n, 0:n].astype(float) + 0.5) / ss
    cx, cy = (np.floor(xx / spacing) + 0.5) * spacing, (np.floor(yy / spacing) + 0.5) * spacing
    d = np.hypot(xx - cx, yy - cy)
    cov = np.repeat(np.repeat(np.broadcast_to(coverage, (SIZE, SIZE)), ss, 0), ss, 1)
    radius = np.sqrt(np.clip(cov, 0, 1) * spacing * spacing / np.pi)
    disc = np.clip(radius - d + 0.5, 0, 1).reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))
    return np.roll(disc, offset, axis=(0, 1))


def ramp(lo, hi, period=128, warp=0.0, rng=None):
    """Tile-periodic diagonal triangle ramp lo..hi (clean paper into dense dots)."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float)
    w = 0
    if warp and rng is not None:
        from fields import fbm
        w = (fbm(rng, SIZE, 2, octaves=2) - 0.5) * warp * period
    t = ((xx + yy + w) % period) / period
    tri = 1 - np.abs(t * 2 - 1)
    from fields import smoothstep
    return lo + smoothstep(0, 1, tri) * (hi - lo)


def line_screen(spacing, coverage, direction=1):
    """45 degree ink lines whose width follows coverage."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
    pos = ((xx + direction * yy) % spacing)
    d = np.minimum(pos, spacing - pos) / np.sqrt(2)
    half = coverage * spacing / np.sqrt(2) / 2
    return np.clip(half - d + 0.5, 0, 1)


def speed_lines(rng, bundles=3, direction=(0.8, -0.6), widths=(0.8, 3.0), long=0):
    """Bundles of 4-6 parallel tapered wedges (comic motion lines), wrapping."""
    from PIL import ImageDraw
    k = 4
    big = Image.new("L", (SIZE * k, SIZE * k))
    d = ImageDraw.Draw(big)
    ux, uy = direction                     # direction of motion
    nx, ny = -uy, ux                       # across it
    for _ in range(bundles):
        x0, y0 = rng.random(2) * SIZE
        for i in range(int(rng.integers(4, 7))):
            off = i * rng.uniform(5, 9)
            length = rng.uniform(50, 120) if i >= long else rng.uniform(180, 250)
            w = rng.uniform(*widths)
            bx, by = x0 + nx * off + ux * rng.uniform(-15, 15), y0 + ny * off + uy * rng.uniform(-15, 15)
            tip = (bx + ux * length, by + uy * length)
            poly = [(bx - nx * w / 2, by - ny * w / 2), (bx + nx * w / 2, by + ny * w / 2), tip]
            for ox in (-SIZE, 0, SIZE):
                for oy in (-SIZE, 0, SIZE):
                    d.polygon([((x + ox) * k, (y + oy) * k) for x, y in poly], fill=255)
    return np.asarray(big.resize((SIZE, SIZE), Image.LANCZOS), float) / 255


def show_through(rng):
    """Type from the other side of the page: rows of blurred bars (words),
    mirrored and faint."""
    from fields import blur
    m = np.zeros((SIZE, SIZE))
    for y in range(6, SIZE, 14):
        x = int(rng.integers(0, 20))
        while x < SIZE:
            w = int(rng.integers(8, 40))
            m[y:y + 6, x:min(SIZE, x + w)] = 1
            x += w + int(rng.integers(4, 9))
    return np.clip(blur(m, 1.4), 0, 1)


def comic(paper_asset, paper, inks, light=0.6, stain=None, process="dots"):
    """A print process on real paper graded to the paper colour; inks: list
    of (rgb 0..255, alpha). process: newsprint (one warm-grey screen with
    cyan and magenta misregistration ghosts), pulp (dots, a second ink,
    motion-line bundles), pop (big dots in clean-ended ramp bands with a
    pale counter-screen), noir (hand-inked line screen, cross-hatch,
    krackle)."""
    def make(name):
        from fields import fbm, smoothstep, blur
        rng = np.random.default_rng(sum(map(ord, name)))
        rgb, normal = load(paper_asset, 1)
        if stain:
            lum = luminance(load(stain[0], 1)[0])
            rgb = rgb * ((lum / lum.mean()) ** stain[1])[..., None]
        sheet = grade(rgb, paper, 0.4, 1.0) * relief(normal, light)[..., None]

        def ink(out, mask, k, alpha=None):
            colour, a0 = inks[k]
            a = np.clip(mask, 0, 1)[..., None] * (a0 if alpha is None else alpha)
            return out * (1 - a) + np.array(colour, float) / 255 * a

        if process == "newsprint":
            dots = screen(8, ramp(0.03, 0.45, period=256, warp=0.6, rng=rng), True)
            out = ink(sheet, show_through(rng), 0, 0.1)
            out = ink(out, np.roll(dots, (3, 3), axis=(0, 1)), 1, 0.2)
            out = ink(out, np.roll(dots, (-3, 0), axis=(0, 1)), 2, 0.15)
            out = ink(out, dots, 0)
        elif process == "pulp":
            cov = ramp(0.04, 0.45, warp=0.25, rng=rng)
            out = ink(sheet, screen(8, cov, True), 0)
            out = ink(out, screen(8, np.roll(cov, 32, axis=1) * 0.9, False, (4, 4)), 1)
            out = ink(out, speed_lines(rng, 3), 0, 0.6)
        elif process == "pop":
            cov = ramp(0.0, 0.5, warp=0.15, rng=rng)
            cov = np.where(cov < 0.06, 0, cov)
            out = ink(sheet, screen(8, np.clip(0.18 - cov, 0, 0.18) * 1.2, False), 1)
            out = ink(out, screen(16, cov, True), 0)
        else:  # noir: scratchboard rain, light ink scratched out of black
            cov = ramp(0.04, 0.4, period=256, warp=0.8, rng=rng)
            cov = cov * (0.75 + fbm(rng, SIZE, 16, octaves=2) * 0.5)
            out = ink(sheet, line_screen(6, cov, 1), 1)
            out = ink(out, speed_lines(rng, 5, (0.3, 0.954), widths=(0.8, 2.5), long=1), 1, 0.5)
        return land(out, name)
    return make


# Circuit --------------------------------------------------------------------

def circuit(board=(8, 28, 14), trace=(18, 58, 30), via=(220, 200, 130), buses=9):
    """A board: the fibreglass weave scan (Fabric004) as substrate under the
    solder mask, bus bundles of 2 px traces on an 8 px grid with 45 degree
    jogs, lit on their upper-left edge, pale-gold via rings at the ends."""
    def make(name):
        rng = np.random.default_rng(sum(map(ord, name)) * 17)
        rgb, normal = load("Fabric004", 2)
        sub = grade(rgb, board, 0.2, 0.6) * relief(normal, 0.6)[..., None]
        strokes, ends, pads = [], [], []
        cell = SIZE // 3      # one bus per cell of a 3x3 grid: spread evenly, no landmark
        for slot in range(buses):
            for attempt in range(30):           # a single-layer board never crosses: reroute, shorter each time
                vertical = (slot + slot // 3 + attempt) % 2 == 1
                x = (slot % 3) * cell + rng.integers(0, cell // 8) * 8 + 4
                y = (slot // 3 % 3) * cell + rng.integers(0, cell // 8) * 8 + 4
                reach = max(4, 9 - attempt // 5)
                run1, jog, run2 = rng.integers(2, reach) * 8, rng.integers(2, 5) * 8 * rng.choice((-1, 1)), rng.integers(2, reach) * 8
                bundle = []
                for k in range(rng.integers(2, 5)):
                    o = k * 8
                    pts = [(x, y + o), (x + run1, y + o), (x + run1 + abs(jog), y + o + jog),
                           (x + run1 + abs(jog) + run2, y + o + jog)]
                    if vertical:
                        pts = [(py, px) for px, py in pts]
                    bundle.append(pts)
                if not strokes or (wrap_draw(bundle, 4.0) * wrap_draw(strokes, 4.0)).sum() == 0:
                    strokes += bundle
                    ends += [pts[0] for pts in bundle]
                    pads += [pts[-1] for pts in bundle]
                    break
        singles = []
        while len(singles) < 5:                 # a second, finer density layer between the bundles
            x, y = rng.integers(0, SIZE // 8, 2) * 8 + 4
            run, jog = rng.integers(3, 8) * 8, rng.integers(1, 3) * 8 * rng.choice((-1, 1))
            pts = [(x, y), (x + run, y), (x + run + abs(jog), y + jog), (x + run + abs(jog) + 24, y + jog)]
            if rng.random() < 0.5:
                pts = [(py, px) for px, py in pts]
            if (wrap_draw([pts], 4.0) * wrap_draw(strokes + singles, 4.0)).sum() == 0:
                singles.append(pts)
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        pad = np.zeros((SIZE, SIZE))
        for px, py in pads:                     # trace ends without a via stop on a small pad
            dx = (xx - px + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - py + SIZE / 2) % SIZE - SIZE / 2
            pad = np.maximum(pad, np.clip(1.5 - np.hypot(dx, dy) + 0.5, 0, 1))
        m = np.maximum(np.maximum(wrap_draw(strokes, 2.0), wrap_draw(singles, 1.0) * 0.6), pad)
        lit = np.clip(m - np.roll(m, (1, 1), axis=(0, 1)), 0, 1)
        out = sub * (1 - m[..., None]) + np.array(trace, float) / 255 * m[..., None] * (0.8 + 0.2 * relief(normal, 0.3))[..., None]
        out = out + lit[..., None] * np.array(trace, float) / 255 * 0.4
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        ring = np.zeros((SIZE, SIZE))
        hole = np.zeros((SIZE, SIZE))
        for ex, ey in ends:
            dx = (xx - ex + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - ey + SIZE / 2) % SIZE - SIZE / 2
            d = np.hypot(dx, dy)
            ring = np.maximum(ring, np.clip(1 - np.abs(d - 2.6) / 1.1, 0, 1))
            hole = np.maximum(hole, np.clip(1.4 - d, 0, 1))
        ring, hole = ring * 0.55, hole * 0.55
        out = out * (1 - ring[..., None]) + np.array(via, float) / 255 * ring[..., None]
        out = out * (1 - hole[..., None] * 0.85)
        return land(out, name)
    return make


TEXTURES = {
    "WoodHDOak": material("Wood066", (66, 40, 20), sat=0.8, contrast=1.2, light=1.5, flat=0.8, sharp=0.5, layout=planks(0.4)),
    "WoodHDWalnut": material("Wood060", (46, 24, 16), sat=0.7, contrast=0.9, light=1.8, shadow_hue=(1.0, 0.88, 0.80), flat=0.6, sharp=0.4, layout=planks(1.0)),
    "WoodHDEbony": material("Wood051", (25, 21, 20), sat=0.4, contrast=1.8, light=1.5, flat=0.8, sharp=0.6, layout=planks(1.0, nail=0)),
    "WoodHDDriftwood": material("Wood062", (74, 64, 52), sat=0.45, contrast=0.8, light=1.3, shadow_hue=(0.9, 0.95, 1.06), flat=0.6, sharp=0.3, layout=planks(0.0, nail=0.6, seam=0.3)),
    "RunestoneHDGranite": material("Granite007A", (50, 50, 54), sat=0.25, contrast=0.85, light=0.4, repeat=2, flat=0.5, sharp=0.4, layout=ashlar(tone=0.12)),
    "RunestoneHDSlate": material("Rock041", (38, 45, 62), sat=0.4, light=0.9, shadow_hue=(0.9, 0.95, 1.12), stain=("Rock022", 0.3), flat=0.5, layout=ashlar()),
    "RunestoneHDSandstone": material("Granite001B", (92, 66, 40), sat=0.5, contrast=0.8, light=0.5, repeat=2, sharp=0.3, stain=("Travertine003", 0.4), shadow_hue=(1.1, 0.9, 0.75), flat=0.5, layout=ashlar(depth=0.3, lip=0.15)),
    "RunestoneHDObsidian": material("Marble006", (19, 16, 24), sat=0.35, contrast=0.75, light=0.6, flat=0.5, sharp=0.4,
                                    layout=ashlar(tone=0.04, lip=0.35, lip_tint=(1.0, 0.9, 1.25))),
    "ParchmentHDClassic": material("Paper006", (108, 84, 52), sat=0.9, contrast=2.0, light=1.1, shadow_hue=(1.08, 0.92, 0.72),
                                   flat=0.3, layout=vellum(foxing=0.6, fibres=0.09)),
    "ParchmentHDAged": material("Paper006", (82, 58, 34), sat=0.9, contrast=2.6, light=1.1, stain=("Leather037", 0.8), shadow_hue=(1.1, 0.88, 0.68),
                                flat=0.3, layout=vellum(foxing=1.0, wash=0.16, fibres=0.14, scuffs=0.1)),
    "ParchmentHDAsh": material("Paper002", (88, 84, 76), sat=0.8, contrast=2.0, light=1.2,
                               shadow_hue=(0.86, 0.95, 1.12), flat=0.3, layout=vellum(foxing=0, soot=0.1, fibres=0.11, wash=0.05, dark=False, tint=(0.95, 0.98, 1.06))),
    "FrostHDIce": material("Ice004", (70, 98, 122), sat=0.5, contrast=0.45, light=0.6, stain=("Marble012", 0.5), flat=0.3, layout=fractures(2, 0.08)),
    "FrostHDDeep": material("Ice001", (30, 50, 92), sat=0.35, contrast=0.65, light=0.8, shadow_hue=(0.85, 0.95, 1.15),
                            flat=0.4, layout=fractures(2, 0.18)),
    "FrostHDAurora": material("Ice003", (24, 64, 62), sat=0.45, contrast=0.6, light=0.5, shadow_hue=(1.15, 0.85, 1.2),
                              median=True, layout=ribbons((0.35, 1.0, 0.65), (0.65, 0.3, 1.0), 0.15)),
    "TechHDCarbon": material("Fabric004", (10, 22, 30), sat=0.2, contrast=1.0, light=2.0, sharp=0.8, repeat=2,
                             layout=hairgrid((0.25, 0.75, 0.95), 64, 0.06)),
    "TechHDSteel": material("Metal009", (20, 24, 32), sat=0.2, contrast=1.8, light=1.6, stain=("Metal046B", 0.3), sharp=0.8, layout=panels),
    "TechHDCircuit": circuit(),
    "GlassHDCathedral": glass([(0.08, 0.22, 0.95), (0.1, 0.26, 0.9)], [(1.0, 0.8, 0.3), (0.85, 0.03, 0.08)]),
    "GlassHDSapphire": glass([(0.08, 0.22, 0.85), (0.2, 0.18, 0.9), (0.05, 0.35, 0.85)],
                             [(0.25, 0.75, 1.0), (0.7, 0.4, 1.0)], jewel_gain=1.15),
    "GlassHDEmerald": glass([(0.05, 0.55, 0.22), (0.08, 0.6, 0.3), (0.04, 0.5, 0.25)],
                            [(0.03, 0.55, 0.5), (0.45, 0.75, 0.03)]),
    "GlassHDRuby": glass([(0.8, 0.03, 0.1), (0.85, 0.05, 0.14), (0.45, 0.02, 0.06)],
                         [(1.0, 0.6, 0.7), (1.0, 0.7, 0.2)], rim=(0.95, 0.75, 0.55), pane_tex=0.12,
                         jewel_gain=1.7),
    "ComicHDNewsprint": comic("Paper002", (182, 176, 160), [((70, 66, 62), 0.4), ((40, 150, 200), 0.12), ((200, 50, 120), 0.12)],
                              stain=("Concrete034", 0.4), process="newsprint"),
    "ComicHDPulp": comic("Paper006", (222, 190, 96), [((180, 45, 35), 0.45), ((235, 150, 30), 0.4)],
                         stain=("Concrete034", 0.4), process="pulp"),
    "ComicHDPop": comic("Paper001", (118, 152, 205), [((30, 60, 175), 0.45), ((200, 215, 240), 0.5)], light=0.2, process="pop"),
    "ComicHDNoir": comic("Paper001", (44, 42, 39), [((10, 10, 12), 0.7), ((120, 116, 108), 0.35)], process="noir"),
}


def main(argv):
    preview = None
    if "--preview" in argv:
        i = argv.index("--preview")
        preview = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
        os.makedirs(preview, exist_ok=True)
    for name in argv or list(TEXTURES):
        rgb = TEXTURES[name](name)
        img = Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").convert("RGBA")
        img.save(os.path.join(OUT, name + ".tga"))
        print(f"{name}: mean {rgb.mean():.3f}")
        if preview:
            sheet = Image.new("RGBA", (SIZE * 3, SIZE * 2))
            for x in range(3):
                for y in range(2):
                    sheet.paste(img, (x * SIZE, y * SIZE))
            sheet.save(os.path.join(preview, name + ".png"))


if __name__ == "__main__":
    main(sys.argv[1:])
