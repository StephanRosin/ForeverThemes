"""Tileable source fields for the HD backdrops (numpy, values 0..1).

Every field repeats seamlessly over its size: lattices have whole-number
periods and distances wrap around the torus. MaterialCraft gets them as
bitmaps and does the material work (tools/hd/build.py).
"""
import numpy as np


def normalise(a):
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / max(hi - lo, 1e-9)


def perlin(rng, size, period):
    """Gradient noise with `period` lattice cells across `size` pixels."""
    return perlin_xy(rng, size, period, period)


def fbm(rng, size, period, octaves=5, gain=0.5, stretch=(1, 1)):
    """Fractal sum of perlin octaves (each twice the frequency), 0..1.
    stretch: lattice cells per axis multiplied, e.g. (1, 4) for streaks
    along x (both whole numbers keep it tileable)."""
    total = np.zeros((size, size))
    amp = 1.0
    for o in range(octaves):
        p = period * 2 ** o
        n = perlin_xy(rng, size, p * stretch[0], p * stretch[1])
        total += n * amp
        amp *= gain
    return normalise(total)


def perlin_xy(rng, size, px, py):
    """Perlin noise with px cells across x and py cells down y."""
    angles = rng.random((py, px)) * 2 * np.pi
    gx, gy = np.cos(angles), np.sin(angles)
    xs = np.arange(size) * px / size
    ys = np.arange(size) * py / size
    x, y = np.meshgrid(xs, ys)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0

    def corner(ox, oy):
        ix, iy = (x0 + ox) % px, (y0 + oy) % py
        return gx[iy, ix] * (fx - ox) + gy[iy, ix] * (fy - oy)

    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    u, v = fade(fx), fade(fy)
    top = corner(0, 0) * (1 - u) + corner(1, 0) * u
    bottom = corner(0, 1) * (1 - u) + corner(1, 1) * u
    return top * (1 - v) + bottom * v


def points(rng, cells, jitter=1.0):
    """One jittered point per cell of a cells x cells grid, in 0..1."""
    gy, gx = np.mgrid[0:cells, 0:cells]
    off = 0.5 + (rng.random((cells, cells, 2)) - 0.5) * jitter
    return np.stack([(gx + off[..., 0]) / cells, (gy + off[..., 1]) / cells], -1).reshape(-1, 2)


def worley(size, pts, scale=(1.0, 1.0)):
    """Distances to the nearest and second nearest point (F1, F2, owner),
    wrapped on the unit torus; scale stretches the metric per axis."""
    c = (np.arange(size) + 0.5) / size
    x, y = np.meshgrid(c, c)
    f1 = np.full((size, size), 9.0)
    f2 = np.full((size, size), 9.0)
    owner = np.zeros((size, size), int)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(x - px)
        dy = np.abs(y - py)
        dx = np.minimum(dx, 1 - dx) * scale[0]
        dy = np.minimum(dy, 1 - dy) * scale[1]
        d = np.hypot(dx, dy)
        closer = d < f1
        f2 = np.where(closer, f1, np.minimum(f2, d))
        owner = np.where(closer, i, owner)
        f1 = np.where(closer, d, f1)
    return f1, f2, owner


def blur(a, radius):
    """Gaussian blur that wraps (stays tileable)."""
    if radius <= 0:
        return a
    size = a.shape[0]
    k = np.fft.fftfreq(size)
    kx, ky = np.meshgrid(k, k)
    g = np.exp(-2 * (np.pi * radius) ** 2 * (kx ** 2 + ky ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def blur_x(a, radius):
    """Blur along x only (streaks), wrapping."""
    size = a.shape[1]
    k = np.fft.fftfreq(size)
    g = np.exp(-2 * (np.pi * radius) ** 2 * k ** 2)
    return np.real(np.fft.ifft(np.fft.fft(a, axis=1) * g[None, :], axis=1))


def grid(size):
    """Pixel centres in 0..1 (x, y)."""
    c = (np.arange(size) + 0.5) / size
    return np.meshgrid(c, c)


def warp(a, dx, dy):
    """a sampled at (x + dx, y + dy) in pixels, bilinear and wrapping."""
    size = a.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(float)
    x, y = xx + dx, yy + dy
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0 %= size
    y0 %= size
    x1, y1 = (x0 + 1) % size, (y0 + 1) % size
    top = a[y0, x0] * (1 - fx) + a[y0, x1] * fx
    bottom = a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def smoothstep(e0, e1, a):
    t = np.clip((a - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ring_phase(rng, size, rings, spread=0.6):
    """Growth rings down y with uneven widths: 0..rings over the tile,
    denser in places (every ring its own width), still whole at the edge."""
    density = 1 + spread * (np.interp(np.arange(size), np.linspace(0, size, 9),
                                      np.append(r := rng.random(8) * 2 - 1, r[0])))
    density = blur_1d(np.clip(density, 0.25, None), 6)
    cum = np.cumsum(density)
    return (cum - density[0]) / cum[-1] * rings


def blur_1d(a, radius):
    k = np.fft.fftfreq(a.size)
    return np.real(np.fft.ifft(np.fft.fft(a) * np.exp(-2 * (np.pi * radius) ** 2 * k ** 2)))


def scatter(rng, count, min_gap=0.0):
    """count random points in 0..1 (uneven spacing: big and small cells),
    at least min_gap apart on the torus."""
    pts = []
    while len(pts) < count:
        p = rng.random(2)
        if all(np.hypot(*np.minimum(np.abs(p - q), 1 - np.abs(p - q))) >= min_gap for q in pts):
            pts.append(p)
    return np.array(pts)


def segments(rng, size, count, lmin, lmax, angles=None, width=0.5):
    """count short strokes (fibres, scratches) lmin..lmax px long, wrapping,
    each fading in and out; angles: None = any, else a list to pick from
    (radians). Sum of the strokes, blurred by width."""
    out = np.zeros((size, size))
    for _ in range(count):
        x0, y0 = rng.random(2) * size
        length = rng.uniform(lmin, lmax)
        a = rng.random() * np.pi if angles is None else rng.choice(angles)
        t = np.linspace(0, 1, max(int(length * 2), 2))
        xs = (x0 + np.cos(a) * length * t).astype(int) % size
        ys = (y0 + np.sin(a) * length * t).astype(int) % size
        np.add.at(out, (ys, xs), np.sin(t * np.pi) * 0.5)
    return blur(out, width)


def shear_streaks(rng, size, along, across, slope):
    """Noise drawn out along a direction of slope (dy/dx, whole-pixel shift
    per row, so it still tiles): streaks along+across px."""
    a = rng.random((size, size))
    shift = (np.arange(size) * slope).astype(int)
    a = np.stack([np.roll(r, -s) for r, s in zip(a, shift)])
    a = blur_x(a, along)
    a = np.stack([np.roll(r, s) for r, s in zip(a, shift)])
    return normalise(blur(a, across))
