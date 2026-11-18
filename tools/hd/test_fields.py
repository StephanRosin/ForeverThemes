#!/usr/bin/env python3
"""Self-check of fields.py: every field tiles (the jump across the tile's
edge is no larger than between neighbours inside) and is deterministic.
    python3 tools/hd/test_fields.py"""
import numpy as np

import fields as F

SIZE = 128


def seam_ok(a, name):
    inner = max(np.abs(np.diff(a, axis=0)).max(), np.abs(np.diff(a, axis=1)).max())
    edge = max(np.abs(a[0] - a[-1]).max(), np.abs(a[:, 0] - a[:, -1]).max())
    assert edge <= inner * 1.05 + 1e-9, f"{name}: seam {edge:.4f} > inner {inner:.4f}"


rng = np.random.default_rng(7)
seam_ok(F.fbm(rng, SIZE, 2, octaves=4), "fbm")
seam_ok(F.fbm(rng, SIZE, 1, octaves=3, stretch=(1, 3)), "fbm stretched")
f1, f2, _ = F.worley(SIZE, F.points(rng, 5))
seam_ok(f1, "worley f1")
seam_ok(f2 - f1, "worley border")
seam_ok(F.blur(rng.random((SIZE, SIZE)), 2), "blur")
seam_ok(F.blur_x(rng.random((SIZE, SIZE)), 4), "blur_x")
smooth = F.fbm(rng, SIZE, 2)
seam_ok(F.warp(smooth, np.full((SIZE, SIZE), 3.5), np.full((SIZE, SIZE), -2.25)), "warp")
assert np.allclose(F.warp(smooth, np.zeros((SIZE, SIZE)), np.zeros((SIZE, SIZE))), smooth), "warp by 0"
assert np.allclose(F.warp(smooth, np.full((SIZE, SIZE), float(SIZE)), np.zeros((SIZE, SIZE))), smooth), "wraps"
a = F.fbm(np.random.default_rng(3), SIZE, 2)
b = F.fbm(np.random.default_rng(3), SIZE, 2)
assert np.array_equal(a, b), "fbm not deterministic"
print("fields: ok")
