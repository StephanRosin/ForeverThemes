"""The HD backdrop recipes: name -> recipe(graph, rng) -> optional post(rgba).

A recipe adds source fields (fields.py) and MaterialCraft nodes to graph
and connects an output "base". Colours are final: WoW draws these
textures untinted, so their brightness is the backdrop's on screen; every
recipe ends on the mean of the old theme in the same colour (OLD), so
texts read as before, and on a contrast close to the old one (CONTRAST
scales the deviation from the mean colour). Rules from the reviews: no
hard procedural contours, crisp detail at 1-3 px, varied sizes, little
emboss, no single landmark, and no large-scale noise on a 128 px lattice
or with one cycle per tile (both show as stripes or a plaid when tiled):
large-scale fields use 3 or 5 cells per tile.
"""
import numpy as np

import fields as F
from build import SIZE, gradient

LIGHT = 0.375       # emboss light angle (turns): from the top left, as the UI's own bevels

# The old theme's on-screen mean in the matching colour (texture x tint, or
# the colour's back): what the HD variant lands on.
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
# Deviation from the mean colour kept (review: in-window contrast against the old theme's).
CONTRAST = {
    "WoodHDOak": 0.55, "WoodHDWalnut": 0.55, "WoodHDEbony": 0.75, "RunestoneHDGranite": 0.62,
    "WoodHDDriftwood": 0.8, "ParchmentHDClassic": 0.85, "ParchmentHDAged": 0.85,
    "ComicHDNewsprint": 0.3, "ComicHDPop": 0.34, "ComicHDPulp": 0.34, "ComicHDNoir": 0.55,
    "RunestoneHDSandstone": 0.85, "RunestoneHDSlate": 1.3, "TechHDSteel": 1.2,
    "FrostHDDeep": 0.8, "FrostHDAurora": 0.75, "FrostHDIce": 1.05, "ParchmentHDAsh": 1.15,
    "TechHDCircuit": 1.3, "GlassHDCathedral": 0.8,
}


def exposure(name):
    """Keeps CONTRAST of the deviation from the mean colour, then scales
    the colour so its mean lands on OLD."""
    target, k = OLD[name], CONTRAST.get(name, 1.0)

    def post(rgba):
        out = rgba.copy()
        rgb = rgba[..., :3]
        mean = rgb.reshape(-1, 3).mean(0)
        rgb = mean + (rgb - mean) * k
        out[..., :3] = np.clip(rgb * target / max(rgb.mean(), 1e-6), 0, 1)
        return out
    return post


def lit(g, colour, height, relief, highlight=(1, 1, 1), shadow=(0, 0, 0)):
    """Light from the top left baked into colour (emboss)."""
    return g.node("emboss", {"intensity": relief, "light_angle": LIGHT,
                             "highlight": {"t": "color", "v": [*highlight, 1]},
                             "shadow": {"t": "color", "v": [*shadow, 1]}}, input=colour, height=height)


def rgb_node(g, rgb):
    """An RGB field as one MaterialCraft colour node (three grey bitmaps
    shuffled together)."""
    layers = [g.bitmap(n, rgb[..., i]) for i, n in enumerate(("red", "green", "blue"))]
    colour = g.node("channels_shuffle", {"red": 0, "green": 4, "blue": 0}, input1=layers[0], input2=layers[1])
    return g.node("channels_shuffle", {"red": 0, "green": 1, "blue": 4}, input1=colour, input2=layers[2])


def finish(g, colour, height, relief, highlight, name, shadow=(0, 0, 0)):
    out = lit(g, colour, height, relief, highlight, shadow) if relief else colour
    g.output(out, "base", "base")
    return exposure(name)


def noise(rng):
    return rng.random((SIZE, SIZE))


def streaks(rng, widths):
    """Fibres along x: noise drawn out to lengths w, weighted a."""
    return F.normalise(sum(F.normalise(F.blur_x(noise(rng), w)) * a for w, a in widths))


def tinted(g, field, stops, tint, amount):
    """Gradient map of field, then a soft-light of an RGB tint field (hue
    shifts the gradient alone cannot make), amount 0..1."""
    colour = g.node("gradient_map", {"gradient": gradient(stops)}, input=g.bitmap("field", field))
    if tint is None:
        return colour
    return g.node("blend", {"mode": 11, "opacity": amount}, foreground=rgb_node(g, np.clip(tint, 0, 1)),
                  background=colour)


def soft_dots(rng, chance, radius, halo=0.0):
    """Soft round spots (foxing): a dark core of radius px, minus an
    optional lighter halo around it (negative values)."""
    seed = (noise(rng) > chance).astype(float)
    core = np.clip(F.blur(seed, radius) * radius * radius * 6, 0, 1)
    if halo:
        ring = np.clip(F.blur(seed, radius * 2.2) * radius * radius * 10, 0, 1) - core
        core = core - np.clip(ring, 0, 1) * halo
    return core


# Wood -----------------------------------------------------------------------

def wood(name, stops, rings=10, spread=0.6, wave=0.6, band=0.28, fibre=0.45, pores=0.5, relief=0.08,
         highlight=(0.5, 0.4, 0.3), checks=0, bundles=0.0, planks=0.0, late_tint=(1.0, 0.82, 0.78),
         arc_cells=3, early_tint=(1.0, 1.0, 0.94), lenses=0.0):
    """Plain-sawn board along x: growth rings of uneven width (some merge)
    bending in long low arcs that drift, each ring a soft swell from early
    to late wood, the late wood a little redder (late_tint); fibres at 1-3
    px broken into 30-80 px segments (no full-width line), crisp pore slits
    3-10 px. checks: hairline splits along the grain; bundles: fibres
    gathered into groups with quiet zones (ebony); planks: broad tonal
    bands."""
    def recipe(g, rng):
        ry = F.ring_phase(rng, SIZE, rings, spread)
        arcs = F.fbm(rng, SIZE, 1, octaves=4, gain=0.45, stretch=(arc_cells, 5)) - 0.5
        phase = ry[:, None] + arcs * wave + (F.fbm(rng, SIZE, 3, octaves=2) - 0.5) * 0.4
        r = phase % 1.0
        index = np.floor(phase).astype(int) % rings
        strength = (0.35 + rng.random(rings) * 0.35)[index]         # no band core much darker than the rest
        late = F.smoothstep(0.3, 0.86, r) * (1 - F.smoothstep(0.86, 0.94, r)) * strength   # one crisp edge
        if lenses:   # bands pinch out inside the tile (80-160 px lenses), so none runs as a stripe
            late = late * (1 - lenses + lenses * F.smoothstep(0.3, 0.6, F.fbm(rng, SIZE, 3, octaves=2, stretch=(1, 2))))
        breaks = F.smoothstep(0.3, 0.6, F.fbm(rng, SIZE, 5, octaves=2, stretch=(3, 1)))
        fib = streaks(rng, ((24, 0.35), (8, 0.35), (2.5, 0.3)))
        fib = 0.5 + (fib - 0.5) * (0.5 + breaks * 0.5)
        if bundles:
            group = F.smoothstep(0.4, 0.65, F.fbm(rng, SIZE, 5, octaves=3, stretch=(1, 6)))
            fib = 0.5 + (fib - 0.5) * (1 - bundles + group * bundles * 1.8) + (group - 0.5) * bundles * 0.08
        slits = np.clip(F.segments(rng, SIZE, 450, 3, 14, angles=[0.0], width=0.3) * 3, 0, 1) \
            * (0.4 + F.fbm(rng, SIZE, 5, octaves=2) * 0.6)
        slits = slits * (1 - F.smoothstep(0.15, 0.5, r) * 0.6)
        body = 0.75 - late * band * 2 - (fib - 0.5) * fibre - slits * pores * 0.25 \
            - slits * (1 - late) * pores * 0.12
        if planks:
            rows = F.blur_1d(np.repeat(rng.random(SIZE // 16), 16), 6)
            body = body + (F.normalise(rows)[:, None] - 0.5) * planks
        height = 0.6 + (fib - 0.5) * 0.5 - slits * 0.5
        if checks:
            split = np.clip(F.segments(rng, SIZE, checks, 20, 45, angles=[0.0, 0.03, -0.03], width=0.3) * 4, 0, 1)
            split = split * (0.4 + F.fbm(rng, SIZE, 5, octaves=2) * 0.6)
            silver = np.roll(split, -1, axis=0)                      # the raised edge above each furrow
            body = body - split * 0.3 + silver * 0.12
            height = height - split * 0.5
        tint = 0.5 + (np.array(late_tint) - 1)[None, None, :] * late[..., None] * 2 \
            + (np.array(early_tint) - 1)[None, None, :] * (1 - late[..., None]) * 2
        colour = tinted(g, np.clip(body, 0, 1), stops, tint, 1.0)
        h_n = g.bitmap("height", F.blur(np.clip(height, 0, 1), 0.35))
        return finish(g, colour, h_n, relief, highlight, name)
    return recipe


# Stone ----------------------------------------------------------------------

def granite(name, stops, relief=0.12):
    """Granite: 1-2 px mineral speckle in three grain sizes, sparse soft
    feldspar flecks 3-5 px (lighter, faintly warm), dark mica dots, cool and
    warm mineral tint at low saturation, an irregular drift (5 cells)."""
    def recipe(g, rng):
        grain = np.zeros((SIZE, SIZE))
        for cells, weight in ((128, 0.45), (72, 0.35), (40, 0.2)):
            f1, f2, owner = F.worley(SIZE, F.points(rng, cells, 1.0))
            grain += rng.random(owner.max() + 1)[owner] * weight
        grain = F.blur(grain, 0.45)
        felds = np.clip(F.blur((noise(rng) > 0.9975).astype(float), 1.6) * 22, 0, 1)
        mica = np.clip(F.blur((noise(rng) > 0.996).astype(float), 0.7) * 6, 0, 1)
        drift = F.normalise(F.fbm(rng, SIZE, 3, octaves=2) * 0.6 + F.fbm(rng, SIZE, 5, octaves=2) * 0.4)
        angular = (F.worley(SIZE, F.scatter(rng, 40, 0.05))[0] * SIZE < 2.2).astype(float) * (noise(rng) > 0.0)
        felds = np.maximum(felds, angular * 0.9)
        field = np.clip(0.5 + (grain - 0.5) * 0.65 + (drift - 0.5) * 0.22 + felds * 0.18 - mica * 0.25
                        + np.roll(mica, 1, axis=1) * 0.08 + (noise(rng) - 0.5) * 0.08, 0, 1)
        hue = F.fbm(rng, SIZE, 3, octaves=3)
        tint = 0.5 + np.stack([(hue - 0.5) * 0.08 + felds * 0.3, felds * 0.12 - 0.01, 0.04 - felds * 0.2], -1)
        colour = tinted(g, field, stops, tint, 0.8)
        h_n = g.bitmap("height", np.clip(field * 0.7 + drift * 0.3, 0, 1))
        return finish(g, colour, h_n, relief, (0.8, 0.82, 0.86), name)
    return recipe


def slate(name, stops, relief=0.12):
    """Cleft slate: six cleavage steps of varied length (20-160 px) and
    height, each slightly skewed and feathered at both ends, lit as a ledge
    (shadow below, light lip above); a soft tone change across the longer
    ones; flaky grain along the cleavage, a few tiny mica sparkles."""
    def recipe(g, rng):
        xs = np.arange(SIZE)
        yy = np.arange(SIZE)[:, None]
        step = np.zeros((SIZE, SIZE))
        tone = np.zeros((SIZE, SIZE))
        for _ in range(8):
            y0, skew = rng.uniform(0, SIZE), rng.choice([-1, 1]) * rng.uniform(0.02, 0.05)
            wander = (F.fbm(rng, SIZE, 3, octaves=3)[0] - 0.5) * 6
            start, length = rng.integers(0, SIZE), rng.uniform(20, 160)
            run = (xs - start) % SIZE
            fade = np.clip(np.minimum(run, length - run) / 25, 0, 1) * (run < length)
            yline = y0 + wander + (run - length / 2) * skew
            d = ((yy - yline[None, :]) + SIZE / 2) % SIZE - SIZE / 2
            weight = rng.uniform(0.3, 1.0) * fade[None, :]
            step += F.smoothstep(-1.2, 1.2, d) * weight * np.exp(-np.abs(d) / 25)
            if length > 90:
                tone += F.smoothstep(-1.5, 1.5, d) * weight * 0.05 * np.exp(-np.abs(d) / 30)
        flake = F.normalise(F.blur_x(noise(rng), 10) * 0.7 + F.blur(noise(rng), 0.5) * 0.3)
        mica = (noise(rng) > 0.9995).astype(float) * (0.5 + noise(rng) * 0.5)
        mica = np.maximum(mica, np.roll(mica, 1, axis=1) * 0.6)
        cloud = F.fbm(rng, SIZE, 3, octaves=3)
        field = np.clip(0.5 + tone + (flake - 0.5) * 0.3 + (cloud - 0.5) * 0.14 + mica * 0.2, 0, 1)
        height = np.clip(0.5 + step * 0.5 + (flake - 0.5) * 0.12, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        h_n = g.bitmap("height", F.blur(height, 0.4))
        return finish(g, colour, h_n, relief, (0.55, 0.6, 0.68), name, (0.02, 0.02, 0.03))
    return recipe


def sandstone(name, stops, relief=0.07):
    """Bedded sandstone: thin strata (4-12 px) of slightly different tone,
    cross-bedded in places, layers pinching out; flat 1-2 px sand speckle;
    small pits 1-4 px, half of them with a light lower rim."""
    def recipe(g, rng):
        layers = 26
        ry = F.ring_phase(rng, SIZE, layers, 0.8)
        x, y = F.grid(SIZE)
        bend = (F.fbm(rng, SIZE, 1, octaves=3, stretch=(3, 3)) - 0.5) * 1.2
        cross = F.smoothstep(0.45, 0.6, F.fbm(rng, SIZE, 3, octaves=2)) * np.sin(x * 2 * np.pi) * 0.5
        phase = ry[:, None] + bend + cross
        index = np.floor(phase).astype(int) % layers
        tone = F.blur(rng.random(layers)[index], 1.2)
        pinch = F.fbm(rng, SIZE, 3, octaves=2)
        sand = F.blur(noise(rng), 0.45)
        quartz = (noise(rng) > 0.996).astype(float)
        tone = np.clip(tone, 0.3, 0.85)
        pits = np.zeros((SIZE, SIZE))
        rims = np.zeros((SIZE, SIZE))
        yy, xx = np.mgrid[0:SIZE, 0:SIZE]
        for i in range(16):
            px, py, rad = rng.random() * SIZE, rng.random() * SIZE, rng.uniform(0.3, 2.2)
            dx = (xx - px + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - py + SIZE / 2) % SIZE - SIZE / 2
            pit = np.clip(rad + 0.5 - np.hypot(dx, dy), 0, 1)
            pits = np.maximum(pits, pit)
            if i % 2:
                rims = np.maximum(rims, np.clip(rad + 0.5 - np.hypot(dx, dy - 1.2), 0, 1) * (1 - pit))
        field = np.clip(0.52 + (tone - 0.5) * 0.22 * (0.5 + pinch) + (sand - 0.5) * 0.22
                        + (F.fbm(rng, SIZE, 5) - 0.5) * 0.1 - pits * 0.22 + rims * 0.15 + quartz * 0.12, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        h_n = g.bitmap("height", np.clip(0.5 + (tone - 0.5) * 0.3 - pits * 0.5, 0, 1))
        return finish(g, colour, h_n, relief, (0.9, 0.84, 0.75), name)
    return recipe


def obsidian(name, stops, sheen=(0.62, 0.34, 1.0)):
    """Volcanic glass: near-black and neutral; conchoidal fracture marks as
    partial arcs (60-140 degrees) fanning from six scattered impact points,
    radii 40-200 px, each arc a crisp anti-aliased 1-px rim with a 6-10 px
    glow behind it; violet sheen; a few single-pixel glints on the rims."""
    def recipe(g, rng):
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        band = np.zeros((SIZE, SIZE))
        rims = np.zeros((SIZE, SIZE))
        for _ in range(4):
            ox, oy = rng.random(2) * SIZE
            dx = (xx - ox + SIZE / 2) % SIZE - SIZE / 2
            dy = (yy - oy + SIZE / 2) % SIZE - SIZE / 2
            dist = np.hypot(dx, dy)
            ang = np.arctan2(dy, dx)
            facing, open_ = rng.uniform(-np.pi, np.pi), np.deg2rad(rng.uniform(60, 140)) / 2
            off = np.abs((ang - facing + np.pi) % (2 * np.pi) - np.pi)
            within = 1 - F.smoothstep(open_ * 0.6, open_, off)
            for radius in rng.uniform(40, 200, rng.integers(1, 3)):
                ox2, oy2 = rng.uniform(-25, 25, 2)
                dist = np.hypot(dx - ox2, dy - oy2)
                d = dist - radius
                rim = np.clip(1 - np.abs(d) / 0.8, 0, 1)                 # anti-aliased 1 px
                glow = np.exp(-np.clip(-d, 0, None) / 3) * (d < 0)      # inside, 6-10 px
                rims = np.maximum(rims, rim * within)
                band = np.maximum(band, (rim * 0.9 + glow * 0.2) * within)
        glints = (noise(rng) > 0.97).astype(float) * rims
        body = F.fbm(rng, SIZE, 3, octaves=3)
        field = np.clip(0.42 + (body - 0.5) * 0.1 + F.blur(noise(rng), 0.5) * 0.03, 0, 1)
        glow = np.clip(band * 0.05 + glints * 0.12, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        glow_n = rgb_node(g, np.clip(glow[..., None] * np.array(sheen), 0, 1))
        colour = g.node("blend", {"mode": 1}, foreground=glow_n, background=colour)
        return finish(g, colour, None, 0, None, name)
    return recipe


# Glass ----------------------------------------------------------------------

def luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def glass(name, palette, accents=None, cols=6, rows=4, rim=(0.7, 0.8, 0.95), level=0.3, spread=0.08, rosettes=2):
    """Leaded quarry glazing: a designed diamond lattice (cols x rows quarries
    across the tile, taller than wide, tiles exactly), the field quarries in
    the palette's colours at one luminance (level, +-spread) so only hue
    varies, and rosettes: the four quarries round a crossing in the accent
    colours, as a motif; each quarry lit from within (centre bright, 8 px
    darker toward the lead) with soft streaks at its own angle; cames 2.5 px
    near black with solder joints at the crossings, raised by an emboss lit
    from 12 o'clock so both diagonals catch the same highlight."""
    def recipe(g, rng):
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        a, b = SIZE / cols, SIZE / rows
        u, v = xx / a + yy / b, xx / a - yy / b
        norm = np.hypot(1 / a, 1 / b)
        du = np.abs(u - np.round(u)) / norm                          # px to the nearest came of each family
        dv = np.abs(v - np.round(v)) / norm
        d = np.minimum(du, dv)
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        # quarry identity, unchanged by the tile's own shifts (cols, cols) and (rows, -rows)
        ka, kb = (i + j) % (2 * cols), (i - j) % (2 * rows)
        n = (2 * cols, 2 * rows)
        table = rng.integers(0, len(palette), n)
        lum = 1 + rng.uniform(-spread, spread, n)
        pal = np.stack([np.array(c, float) * level / luminance(c) for c in palette])
        base = pal[table[ka, kb]] * lum[ka, kb][..., None]
        if accents:
            apal = np.stack([np.array(c, float) * level * 1.25 / luminance(c) for c in accents])
            mark = -np.ones(n, int)
            ci, cj = rng.integers(0, 64, 2)
            # rosettes: the four quarries round a crossing, top/bottom in one accent, left/right in
            # the next; the second rosette half a tile away diagonally, its colours swapped
            for r, (oi, oj) in enumerate(((0, 0), (cols // 2 + rows // 2, cols // 2 - rows // 2))[:rosettes]):
                for di, dj, side in ((0, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 1)):
                    pi, pj = ci + oi + di, cj + oj + dj
                    mark[(pi + pj) % n[0], (pi - pj) % n[1]] = (side + r) % len(accents)
            pick = mark[ka, kb]
            base = np.where((pick >= 0)[..., None], apal[np.maximum(pick, 0)], base)
        core = F.smoothstep(1.5, 14, d)
        streak_sets = [F.shear_streaks(rng, SIZE, 22, 1.4, s) for s in (0, 1, -1, 0.5)]
        streak = np.choose(rng.integers(0, 4, n)[ka, kb], streak_sets)
        shade = 0.7 + core * 0.42 + (streak - 0.5) * 0.45
        seeds = np.clip(F.blur((noise(rng) > 0.9985).astype(float), 0.45) * 4, 0, 1) * core
        rgb = np.clip(base * shade[..., None] + seeds[..., None] * 0.12, 0, 1)
        lead = 1 - F.smoothstep(0.9, 1.7, d)
        joint = 1 - F.smoothstep(1.6, 2.6, np.hypot(du, dv))
        lead = np.maximum(lead, joint)
        rgb = rgb * (1 - lead[..., None]) + np.array((0.008, 0.008, 0.01)) * lead[..., None]
        rgb = rgb + joint[..., None] * 0.025
        colour = rgb_node(g, np.clip(rgb, 0, 1))
        height = g.bitmap("height", F.blur(lead, 0.6))
        out = g.node("emboss", {"intensity": 0.22, "light_angle": 0.25,
                                "highlight": {"t": "color", "v": [*rim, 1]},
                                "shadow": {"t": "color", "v": [0, 0, 0, 1]}}, input=colour, height=height)
        g.output(out, "base", "base")
        return exposure(name)
    return recipe


# Frost ----------------------------------------------------------------------

def frost(name, stops, crack=(0.82, 0.92, 1.0), ribbons=None, crack_amount=0.28, cloud_amount=0.35, keep=0.56):
    """Thick ice: soft cloudy depth (3 and 5 cells, no lattice), a fainter
    blurred crack layer below the surface, an open surface network (cells
    of varied size, ~40 % of the borders missing, tips fading), cracks 1-2
    px with feathered rime on one side of a few, small bubble clusters;
    ribbons: soft diagonal aurora bands (an rgb pair)."""
    def recipe(g, rng):
        cloud = F.normalise(F.fbm(rng, SIZE, 3, octaves=5) * 0.6 + F.fbm(rng, SIZE, 5, octaves=3) * 0.4)
        bend = (F.fbm(rng, SIZE, 3, octaves=3) - 0.5) * 10

        def crack_layer(count, width, keep):
            """(soft, core): a crack network with a Gaussian profile in px (width: the soft line's
            sigma; the core's is 0.75 px), sampled smoothly so thin lines do not break into beads."""
            f1, f2, _ = F.worley(SIZE, F.scatter(rng, count, 0.5 / np.sqrt(count)))
            on = F.smoothstep(keep - 0.08, keep + 0.08, F.fbm(rng, SIZE, 3, octaves=3))
            px = (f2 - f1) * SIZE / 2                                # ~px to the cell border
            w = width * (0.7 + F.fbm(rng, SIZE, 5, octaves=2) * 0.8)
            soft = F.warp(np.exp(-(px / w) ** 2) * on, bend, -bend)
            core = F.warp(np.exp(-(px / 0.75) ** 2) * on, bend, -bend)
            return soft, core

        deep = F.blur(crack_layer(7, 2.2, 0.45)[0], 1.8)
        surface, core = crack_layer(11, 1.0, keep)
        feather = F.normalise(F.perlin_xy(rng, SIZE, 64, 64) + F.perlin_xy(rng, SIZE, 128, 32) * 0.5)
        side = np.roll(F.blur(surface, 2.5), 2, axis=0)
        rime = np.clip((feather - 0.6) / 0.2, 0, 1) * side * 1.2
        bubbles = np.clip(F.blur((noise(rng) > 0.993).astype(float), 0.8) * 5, 0, 1) \
            * F.smoothstep(0.72, 0.8, F.fbm(rng, SIZE, 7))
        field = np.clip(0.45 + (cloud - 0.5) * cloud_amount + deep * 0.1 + bubbles * 0.15, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        if ribbons:
            x, y = F.grid(SIZE)
            diag = (x + y + (F.fbm(rng, SIZE, 2, octaves=2, stretch=(1, 1)) - 0.5) * 0.4) % 1.0
            mix = (np.sin(diag * 4 * np.pi) * 0.5 + 0.5)[..., None]
            rib = np.array(ribbons[0]) * mix + np.array(ribbons[1]) * (1 - mix)
            fringe = F.smoothstep(0.55, 0.9, np.sin(diag * 4 * np.pi + 1.1) * 0.5 + 0.5)[..., None] * (1 - mix)
            rib = rib * (1 - fringe) + np.array((0.55, 0.3, 1.0)) * fringe
            rib = 0.5 + (rib - rib.reshape(-1, 3).mean(0)) * 0.42      # soft light: grey keeps, hue shifts
            colour = g.node("blend", {"mode": 11, "opacity": 1.0}, foreground=rgb_node(g, np.clip(rib, 0, 1)),
                            background=colour)
        lines = np.clip(surface * crack_amount * 0.6 + core * crack_amount * 0.9 + F.blur(rime, 1.2) * 0.05, 0, 1)
        lines_n = rgb_node(g, np.ones((SIZE, SIZE, 3)) * np.array(crack) * lines[..., None])
        colour = g.node("blend", {"mode": 10}, foreground=lines_n, background=colour)
        h_n = g.bitmap("height", F.blur(np.clip(0.5 + cloud * 0.2, 0, 1), 0.5))   # cracks not embossed: the emboss beads thin lines
        return finish(g, colour, h_n, 0.1, (0.85, 0.95, 1.0), name, (0.02, 0.06, 0.12))
    return recipe


# Parchment ------------------------------------------------------------------

def parchment(name, stops, stains=0.5, foxing=0.5, creases=0, warm=(1.0, 0.97, 0.9), fibre_len=(4, 25),
              specks=0, veins=1):
    """Vellum: skin-side mottling at 40-80 px (3 and 5 cells, no lattice);
    paper tooth from random fibres 6-15 px at any angle and faint laid
    lines in one direction; broken tide marks; foxing 1-6 px with a light
    halo, in clusters; creases: soft fold shadows that wrap."""
    def recipe(g, rng):
        x, y = F.grid(SIZE)
        mottle = F.normalise(F.fbm(rng, SIZE, 3, octaves=5, gain=0.55) * 0.6
                             + F.fbm(rng, SIZE, 7, octaves=3) * 0.4)
        lo, hi = fibre_len
        fibres = np.clip(F.segments(rng, SIZE, 500, lo, (lo + hi) / 2, width=0.4) * 2.5
                         + F.segments(rng, SIZE, 120, (lo + hi) / 2, hi, width=0.45) * 2.5, 0, 1)
        dark_fibres = np.clip(F.segments(rng, SIZE, 160, lo, hi, width=0.4) * 3, 0, 1)
        vein = np.clip(F.segments(rng, SIZE, veins, 80, 150, width=0.7) * 6, 0, 1)
        ash = np.clip(F.blur((noise(rng) > 1 - specks / SIZE ** 2).astype(float), 0.5) * 5, 0, 1) \
            * (0.4 + F.smoothstep(0.5, 0.6, F.fbm(rng, SIZE, 5)) * 0.6)
        laid = (np.cos(y * 2 * np.pi * 32) * 0.5 + 0.5) * 0.02
        st = F.fbm(rng, SIZE, 3, octaves=4)
        stain = F.smoothstep(0.6, 0.74, st) * stains
        fade = F.smoothstep(0.4, 0.6, F.fbm(rng, SIZE, 5, octaves=3))
        tide = np.clip(1 - np.abs(st - 0.62) / 0.012, 0, 1) * fade * stains
        clusters = F.smoothstep(0.55, 0.7, F.fbm(rng, SIZE, 5))
        fox = np.zeros((SIZE, SIZE))
        for radius, chance in ((0.6, 0.997), (1.4, 0.9988), (2.6, 0.9996), (4.0, 0.99992)):
            fox = np.maximum(fox, soft_dots(rng, chance, radius, halo=0.3))
        fox = fox * clusters * foxing
        fold = np.zeros((SIZE, SIZE))
        for _ in range(creases):
            slope, off = rng.uniform(-0.3, 0.3), rng.random() * SIZE
            d = ((y * SIZE - off - x * SIZE * slope) + SIZE / 2) % SIZE - SIZE / 2
            fold += np.exp(-((d - 1.5) / 1.8) ** 2) - np.exp(-((d + 1.5) / 1.8) ** 2)   # dark side, light side
        field = np.clip(0.58 + (mottle - 0.5) * 0.2 + fibres * 0.035 - dark_fibres * 0.05 - laid
                        - stain * 0.08 - tide * 0.18 - fox * 0.3 - fold * 0.06 - vein * 0.025 - ash * 0.12, 0, 1)
        height = np.clip(0.5 + fibres * 0.3 - fold * 0.2, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        h_n = g.bitmap("height", F.blur(height, 0.4))
        return finish(g, colour, h_n, 0.07, warm, name)
    return recipe


# Comic ----------------------------------------------------------------------

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


def comic(name, paper, ink, spacing=8, coverage=(0.1, 0.35), fibres=0.05, stains=0.0, speck=0.02,
          misregister=None, show=0.0):
    """Printed comic paper: paper tone with fine fibre, ONE halftone screen
    at 45 degrees whose dots swell and shrink in irregular, diagonally
    leaning ink-wash shapes (3 cells plus diagonal streaks, so no stripe
    per tile), faint ink speckle; misregister: a faint offset copy in a
    second ink; stains: soft foxing (pulp); show: faint show-through."""
    def recipe(g, rng):
        rgb = np.ones((SIZE, SIZE, 3)) * np.array(paper)
        fib = np.clip(F.segments(rng, SIZE, 1200, 3, 9, width=0.35) * 2, 0, 1)
        rgb = rgb * (1 - fib[..., None] * fibres)
        wash = F.normalise(F.fbm(rng, SIZE, 2, octaves=2, gain=0.35) * 0.4 + F.fbm(rng, SIZE, 3, octaves=2) * 0.2
                           + F.shear_streaks(rng, SIZE, 40, 10, 1) * 0.4)
        cov = coverage[0] + F.smoothstep(0.2, 0.85, wash) * (coverage[1] - coverage[0])
        if show:
            through = F.smoothstep(0.55, 0.7, F.fbm(rng, SIZE, 5, octaves=3))
            rgb = rgb * (1 - through[..., None] * show)
        if misregister:
            ghost = np.roll(dots45(spacing, cov), (1, 1), axis=(0, 1))
            rgb = rgb * (1 - ghost[..., None] * (1 - np.array(misregister)) * 0.3)
        mask = dots45(spacing, cov)
        rgb = rgb * (1 - mask[..., None]) + np.array(ink) * mask[..., None]
        if stains:
            spot = F.smoothstep(0.62, 0.75, F.fbm(rng, SIZE, 5, octaves=4)) * stains * 0.35
            rgb = rgb * (1 - spot[..., None] * np.array((0.1, 0.18, 0.32)))
        if speck:
            sp = np.clip(F.blur((noise(rng) > 0.9992).astype(float), 0.6) * 6, 0, 1) * speck * 20
            rgb = rgb * (1 - np.clip(sp, 0, 1)[..., None] * 0.3)
        return finish(g, rgb_node(g, np.clip(rgb, 0, 1)), None, 0, None, name)
    return recipe


# Tech -----------------------------------------------------------------------

def carbon(name, dark=(0.006, 0.03, 0.055), light=(0.08, 0.23, 0.33), sheen=(0.2, 0.6, 0.85)):
    """2x2 twill carbon: tows 8 px wide, over two under two; each tow a
    soft cylinder brightest at its middle and falling off at its ends, fine
    fibres; a faint diagonal clear-coat sheen that wraps; cyan-black."""
    def recipe(g, rng):
        ss = 4
        n = SIZE * ss
        yy, xx = np.mgrid[0:n, 0:n].astype(float) / ss
        cell = 8
        cx, cy = np.floor(xx / cell), np.floor(yy / cell)
        horiz = ((cx - cy) % 4) < 2
        across = np.where(horiz, yy % cell, xx % cell) / cell
        along = np.where(horiz, (xx - cy * cell) % (cell * 2), (yy - cx * cell) % (cell * 2)) / (cell * 2)
        roll = np.sin(across * np.pi) ** 0.8
        spec = roll * (0.45 + 0.55 * np.sin(along * np.pi) ** 1.5)
        tone = (np.where(horiz, 1.0, 0.7) * spec).reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))
        fib = F.normalise(F.blur_x(noise(rng), 3))
        fib_v = F.normalise(F.blur_x(noise(rng).T, 3).T)
        h_small = (((np.arange(SIZE)[None, :] // cell) - (np.arange(SIZE)[:, None] // cell)) % 4) < 2
        tone = np.clip(tone + (np.where(h_small, fib, fib_v) - 0.5) * 0.1, 0, 1)
        shimmer = F.fbm(rng, SIZE, 3, octaves=2)
        tow = shimmer[(np.arange(SIZE)[:, None] // cell * cell) % SIZE, (np.arange(SIZE)[None, :] // cell * cell) % SIZE]
        tone = tone * (0.94 + tow * 0.12)
        x, y = F.grid(SIZE)
        coat = (np.sin((x + y) * 2 * np.pi) * 0.5 + 0.5) * 0.09
        gap = ((np.arange(SIZE)[:, None] % cell) == cell - 1) & h_small            # shadow under each horizontal tow
        tone = tone * np.where(gap, 0.75, 1.0)
        rgb = np.array(dark) + (np.array(light) - np.array(dark)) * tone[..., None] + coat[..., None] * np.array(sheen)
        return finish(g, rgb_node(g, np.clip(rgb, 0, 1)), None, 0, None, name)
    return recipe


def brushed(name, stops, scratches=2):
    """Brushed steel, cool: brush lines of varied length (20-80 px segments
    over longer ones), rows softened so no single row jumps; a soft
    anisotropic highlight band that wraps; two short faint scratches at
    10-40 degrees; a panel seam at low contrast."""
    def recipe(g, rng):
        long_lines = streaks(rng, ((80, 0.5), (30, 0.5)))
        short = np.clip(F.segments(rng, SIZE, 500, 20, 80, angles=[0.0], width=0.3) * 2, 0, 1)
        lines = F.blur(F.normalise(long_lines * 0.6 + short * 0.4), 0.45)
        hair = np.clip(F.segments(rng, SIZE, 160, 20, 120, angles=[0.0], width=0.25) * 3, 0, 1)
        lines = np.clip(lines + hair * rng.choice([-1, 1], (SIZE, 1)) * 0.12, 0, 1)
        knots = rng.random(3)
        band = F.blur_1d(np.interp(np.arange(SIZE), np.linspace(0, SIZE, 4), np.append(knots, knots[0])), 20)
        sheen = np.repeat(band[:, None], SIZE, 1)
        scratch = np.clip(F.segments(rng, SIZE, 6, 8, 40, angles=[0.18, -0.4, 0.65, 0.3], width=0.3) * 3, 0, 1) \
            * rng.choice([0.5, 1.0], (SIZE, 1))
        seam_y = int(rng.integers(0, SIZE))
        seam = np.zeros((SIZE, SIZE))
        seam[seam_y] = 1
        seam[(seam_y + 1) % SIZE] = -0.6
        field = np.clip(0.5 + (lines - 0.5) * 0.4 + (sheen - 0.5) * 0.7 + scratch * 0.05 - seam * 0.18, 0, 1)
        colour = tinted(g, field, stops, None, 0)
        h_n = g.bitmap("height", np.clip(0.5 + (lines - 0.5) * 0.2 - scratch * 0.3, 0, 1))
        return finish(g, colour, h_n, 0.06, (0.7, 0.8, 0.9), name)
    return recipe


def circuit(name, board=(0.014, 0.11, 0.045), trace=(0.07, 0.32, 0.14), trace2=(0.045, 0.2, 0.09),
            copper=(0.95, 0.7, 0.28)):
    """A routed circuit board: parallel bundles (brighter) and single traces
    (dimmer), 1-2 px, 45/90 degree bends; ring vias in copper with a dark
    hole; one IC footprint (outline and pads) at low contrast; open areas
    left empty; green solder mask beneath."""
    def recipe(g, rng):
        ss = 3
        n = SIZE * ss
        yy, xx = np.mgrid[0:n, 0:n].astype(float) / ss
        traces = np.zeros((n, n))
        traces2 = np.zeros((n, n))
        vias = []

        def seg(field, x0, y0, x1, y1, w):
            dx, dy = x1 - x0, y1 - y0
            length = max(np.hypot(dx, dy), 1e-6)
            px = (xx - x0 + SIZE / 2) % SIZE - SIZE / 2
            py = (yy - y0 + SIZE / 2) % SIZE - SIZE / 2
            t = np.clip((px * dx + py * dy) / length ** 2, 0, 1)
            d = np.hypot(px - t * dx, py - t * dy)
            np.maximum(field, (d <= w / 2).astype(float), out=field)

        for b in range(7):
            bundle = b % 2 == 0
            field = traces if bundle else traces2
            x, y = rng.integers(0, SIZE), rng.integers(0, SIZE)
            count = rng.integers(3, 5) if bundle else 1
            heading = rng.integers(0, 4) * 90
            path = [(x, y)]
            for _ in range(rng.integers(2, 4)):
                length = rng.integers(20, 70)
                ang = np.deg2rad(heading)
                x, y = x + np.cos(ang) * length, y + np.sin(ang) * length
                path.append((x, y))
                heading += rng.choice([-45, 45])
            for k in range(count):
                off = k * 4
                for (ax, ay), (bx, by) in zip(path, path[1:]):
                    seg(field, ax + off, ay + off, bx + off, by + off, 1.4 if bundle else 1.8)
                vias.append((path[-1][0] + off, path[-1][1] + off))
                if not bundle or k == 0:
                    vias.append((path[0][0] + off, path[0][1] + off))
        tr = traces.reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))
        tr2 = traces2.reshape(SIZE, ss, SIZE, ss).mean(axis=(1, 3))
        ring = np.zeros((SIZE, SIZE))
        hole = np.zeros((SIZE, SIZE))
        gy, gx = np.mgrid[0:SIZE, 0:SIZE].astype(float) + 0.5
        for vx, vy in vias:
            d = np.hypot((gx - vx + SIZE / 2) % SIZE - SIZE / 2, (gy - vy + SIZE / 2) % SIZE - SIZE / 2)
            ring = np.maximum(ring, np.clip(2.4 - d, 0, 1))
            hole = np.maximum(hole, np.clip(1.1 - d, 0, 1))
        # one IC footprint: outline 34 x 22 px with a row of pads above and below
        cx0, cy0 = rng.integers(0, SIZE, 2)
        w, h = 34, 22
        rx, ry = (gx - 0.5 - cx0) % SIZE, (gy - 0.5 - cy0) % SIZE
        outline = (rx < w) & (ry < h) & ((rx < 1) | (rx >= w - 1) | (ry < 1) | (ry >= h - 1))
        pad_col = ((rx % 5) < 2) & (rx > 2) & (rx < w - 2)
        pads = pad_col & ((ry >= SIZE - 4) | ((ry >= h + 1) & (ry < h + 4)))
        chip = (outline | pads).astype(float)
        mask = F.fbm(rng, SIZE, 3, octaves=3)
        rgb = np.ones((SIZE, SIZE, 3)) * np.array(board) * (0.92 + (mask - 0.5) * 0.15)[..., None]
        rgb = rgb * (1 - chip[..., None]) + np.array(trace) * chip[..., None]
        rgb = rgb * (1 - tr2[..., None]) + np.array(trace2) * tr2[..., None]
        rgb = rgb * (1 - tr[..., None]) + np.array(trace) * tr[..., None]
        rgb = rgb * (1 - ring[..., None]) + np.array(copper) * ring[..., None]
        rgb = rgb * (1 - hole[..., None] * 0.92)
        h_n = g.bitmap("height", F.blur(np.clip(0.4 + tr * 0.3 + tr2 * 0.2 + ring * 0.3 - hole * 0.5, 0, 1), 0.4))
        return finish(g, rgb_node(g, np.clip(rgb, 0, 1)), h_n, 0.08, (0.6, 0.85, 0.7), name)
    return recipe


def _recipes():
    r = {}

    def add(name, make, *args, **kw):
        r[name] = make(name, *args, **kw)

    add("WoodHDOak", wood, [(0.0, (0.13, 0.06, 0.04)), (0.45, (0.25, 0.145, 0.09)), (0.8, (0.36, 0.24, 0.14)),
                            (1.0, (0.43, 0.31, 0.18))], wave=0.25, arc_cells=2, band=0.2, lenses=0.7, pores=1.0,
        late_tint=(1.0, 0.78, 0.74), early_tint=(1.0, 1.0, 0.9))
    add("WoodHDWalnut", wood, [(0.0, (0.1, 0.05, 0.068)), (0.45, (0.17, 0.095, 0.095)), (0.8, (0.25, 0.155, 0.11)),
                               (1.0, (0.31, 0.2, 0.13))], rings=9, band=0.22, lenses=0.6, spread=1.6, wave=0.6, arc_cells=1,
        late_tint=(0.84, 0.74, 1.0), pores=1.6)
    add("WoodHDEbony", wood, [(0.0, (0.04, 0.025, 0.03)), (0.5, (0.09, 0.06, 0.065)), (0.85, (0.16, 0.11, 0.11)),
                              (1.0, (0.21, 0.15, 0.14))], rings=22, spread=0.4, wave=0.25, band=0.12, fibre=0.75,
        pores=0.15, bundles=1.0, late_tint=(1.0, 0.9, 1.0))
    add("WoodHDDriftwood", wood, [(0.0, (0.22, 0.215, 0.2)), (0.5, (0.36, 0.352, 0.33)), (1.0, (0.5, 0.49, 0.47))],
        rings=9, spread=0.5, wave=0.4, band=0.06, fibre=0.7, pores=0.3, highlight=(0.6, 0.58, 0.55),
        checks=9, planks=0.1, late_tint=(1.0, 0.97, 0.94), early_tint=(1.0, 0.99, 0.97))
    add("RunestoneHDGranite", granite, [(0.0, (0.1, 0.1, 0.11)), (0.5, (0.38, 0.38, 0.4)), (1.0, (0.66, 0.65, 0.65))])
    add("RunestoneHDSlate", slate, [(0.0, (0.09, 0.115, 0.17)), (0.5, (0.19, 0.225, 0.31)), (1.0, (0.32, 0.37, 0.47))])
    add("RunestoneHDSandstone", sandstone, [(0.0, (0.36, 0.28, 0.16)), (0.5, (0.58, 0.47, 0.3)),
                                            (1.0, (0.76, 0.65, 0.46))])
    add("RunestoneHDObsidian", obsidian, [(0.0, (0.04, 0.04, 0.045)), (0.5, (0.08, 0.078, 0.085)),
                                          (1.0, (0.13, 0.125, 0.14))])
    add("GlassHDCathedral", glass, [(0.08, 0.22, 0.95), (0.1, 0.26, 0.9)],
        accents=[(0.9, 0.05, 0.07), (1.0, 0.22, 0.0)])
    add("GlassHDSapphire", glass, [(0.08, 0.22, 0.85), (0.12, 0.3, 0.92), (0.06, 0.18, 0.75)],
        accents=[(0.38, 0.2, 0.92), (0.05, 0.5, 0.75)])
    add("GlassHDEmerald", glass, [(0.05, 0.55, 0.22), (0.08, 0.6, 0.3), (0.04, 0.5, 0.25)],
        accents=[(0.03, 0.55, 0.5), (0.45, 0.75, 0.03)])
    add("GlassHDRuby", glass, [(0.8, 0.03, 0.1), (0.85, 0.05, 0.14), (0.75, 0.04, 0.06)],
        accents=[(0.7, 0.03, 0.4), (1.0, 0.18, 0.0)], rim=(0.95, 0.75, 0.55))
    add("FrostHDIce", frost, [(0.0, (0.2, 0.36, 0.52)), (0.5, (0.42, 0.62, 0.78)), (1.0, (0.7, 0.85, 0.95))],
        cloud_amount=0.38, crack_amount=0.42)
    add("FrostHDDeep", frost, [(0.0, (0.06, 0.12, 0.26)), (0.5, (0.12, 0.22, 0.42)), (1.0, (0.3, 0.45, 0.68))],
        crack=(0.55, 0.72, 0.95), crack_amount=0.15, cloud_amount=0.3, keep=0.64)
    add("FrostHDAurora", frost, [(0.0, (0.05, 0.16, 0.18)), (0.5, (0.1, 0.27, 0.28)), (1.0, (0.25, 0.48, 0.45))],
        crack=(0.6, 0.9, 0.85), crack_amount=0.16, cloud_amount=0.25, ribbons=((0.15, 0.85, 0.5), (0.45, 0.25, 0.9)))
    add("ParchmentHDClassic", parchment, [(0.0, (0.49, 0.39, 0.25)), (0.6, (0.85, 0.75, 0.56)),
                                          (1.0, (0.96, 0.89, 0.72))], fibre_len=(4, 18))
    add("ParchmentHDAged", parchment, [(0.0, (0.4, 0.26, 0.12)), (0.6, (0.74, 0.57, 0.34)),
                                       (1.0, (0.88, 0.74, 0.5))], stains=1.0, foxing=0.9, fibre_len=(5, 20))
    add("ParchmentHDAsh", parchment, [(0.0, (0.39, 0.36, 0.31)), (0.6, (0.69, 0.65, 0.57)), (1.0, (0.85, 0.81, 0.72))],
        stains=0.3, foxing=0.2, creases=2, warm=(1.0, 0.98, 0.94), fibre_len=(3, 12), specks=15, veins=0)
    add("ComicHDNewsprint", comic, (0.97, 0.93, 0.8), (0.32, 0.31, 0.33), coverage=(0.1, 0.26),
        fibres=0.12, show=0.03, speck=0.03)
    add("ComicHDPulp", comic, (1.0, 0.86, 0.18), (0.75, 0.33, 0.2), fibres=0.08, stains=0.35, speck=0.04,
        coverage=(0.1, 0.28),
        misregister=(0.3, 0.5, 0.7))
    add("ComicHDPop", comic, (0.34, 0.6, 1.0), (0.12, 0.3, 0.9), coverage=(0.18, 0.34), fibres=0.06,
        misregister=(0.95, 0.4, 0.6))
    add("ComicHDNoir", comic, (0.12, 0.115, 0.105), (0.3, 0.29, 0.27), coverage=(0.06, 0.2), fibres=0.1, speck=0.05)
    add("TechHDCarbon", carbon)
    add("TechHDSteel", brushed, [(0.0, (0.05, 0.06, 0.075)), (0.5, (0.12, 0.135, 0.16)), (1.0, (0.24, 0.27, 0.32))])
    add("TechHDCircuit", circuit)
    return r


RECIPES = _recipes()
