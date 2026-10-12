"""The notebook page: paper tooth, ruled lines, margin doodles.

The camera is a locked-off overhead shot, so the page never moves.  It is baked
once (paper fibres + faint ruling + the animator's own background doodles) and
every frame's pencil layer is multiplied on top of it, which is what makes the
graphite look genuinely drawn *into* the sheet instead of floating over it.
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .sketchpen import Pen, ellipse_pts

INK = (58, 56, 54)


def _box_blur(a: np.ndarray, r: int, passes: int = 2) -> np.ndarray:
    """Cheap separable box blur (repeated -> approximates a gaussian)."""
    for _ in range(passes):
        for axis in (0, 1):
            c = np.cumsum(a, axis=axis, dtype=np.float32)
            top = np.roll(c, r + 1, axis=axis)
            idx = [slice(None)] * a.ndim
            idx[axis] = slice(0, r + 1)
            top[tuple(idx)] = 0
            n = (np.arange(a.shape[axis]) + r + 1).clip(1, 2 * r + 1).astype(np.float32)
            shape = [1, 1]
            shape[axis] = -1
            a = (c - top) / n.reshape(shape)
    return a


def paper_textures(w: int, h: int, seed: int = 7):
    """Return (paper rgb uint8, tooth mask float32) for the sheet."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    tilt = 8.0 * (1.0 - xx / w) + 5.0 * (1.0 - yy / h)

    paper = np.empty((h, w, 3), np.float32)
    for c in range(3):
        paper[:, :, c] = 245.0 + tilt

    # large blotches (dents / uneven pulp)
    small = rng.standard_normal((h // 8, w // 8)).astype(np.float32)
    small = _box_blur(small, 2)
    blot = np.array(_norm(small).resize((w, h), Image.BICUBIC))
    paper += (blot[:, :, None] - 128.0) * 0.06

    # medium fibre + fine grain
    med = _box_blur(rng.standard_normal((h // 2, w // 2)).astype(np.float32), 1)
    fib = np.array(_norm(med).resize((w, h), Image.BILINEAR))
    paper += (fib[:, :, None] - 128.0) * 0.10
    fine = rng.standard_normal((h, w)).astype(np.float32)
    paper += fine[:, :, None] * 2.4

    # the "tooth" the graphite catches on
    tooth = 1.0 + (fib - 128.0) / 255.0 * 0.5 + fine * 0.18
    tooth = np.clip(tooth, 0.5, 1.4).astype(np.float32)

    # ---- notebook ruling: faint, slightly irregular ----
    rim = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(rim)
    gap = h / 22.0
    for i in range(1, 22):
        y = i * gap + float(rng.uniform(-3, 3))
        d.line([(w * 0.055, y), (w * 0.945, y)], fill=14, width=2)
    mx = w * 0.135
    d.line([(mx, h * 0.02), (mx + float(rng.uniform(-6, 6)), h * 0.985)], fill=16, width=2)
    rule = np.asarray(rim.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    paper -= rule[:, :, None] * 26.0

    # ---- erased ghosts: a scribble somebody rubbed out before our story ----
    for _ in range(3):
        g = Image.new("L", (w, h), 0)
        gd = ImageDraw.Draw(g)
        x0, y0 = rng.uniform(0.1, 0.9) * w, rng.uniform(0.05, 0.95) * h
        pts = [(x0 + i * rng.uniform(8, 20), y0 + rng.uniform(-16, 16)) for i in range(16)]
        gd.line(pts, fill=int(rng.uniform(40, 90)), width=int(rng.uniform(7, 18)))
        ghost = np.asarray(g.filter(ImageFilter.GaussianBlur(4)), np.float32) / 255.0
        paper -= ghost[:, :, None] * 16.0

    # ---- vignette / page shading ----
    dx = (xx - w / 2) / (w / 2)
    dy = (yy - h / 2) / (h / 2)
    paper -= ((0.13 * np.abs(dx) ** 3.2 + 0.10 * np.abs(dy) ** 3.2) * 255)[:, :, None]
    return np.clip(paper, 0, 255).astype(np.uint8), tooth


def _norm(a) -> Image.Image:
    """Rescale any array to 0..255 uint8."""
    arr = np.asarray(a, np.float32)
    lo, hi = float(arr.min()), float(arr.max())
    return Image.fromarray((((arr - lo) / (hi - lo + 1e-6)) * 255).astype(np.uint8), "L")


def background_cel(w: int, h: int, ground_y: float, seed: int = 7,
                   path: str | None = None) -> np.ndarray:
    """Paper + static background doodles + the ground line of the page."""
    if path and os.path.exists(path):
        return np.array(Image.open(path).convert("RGB"))

    paper, tooth = paper_textures(w, h, seed)
    ss = 2
    img = Image.new("L", (w * ss, h * ss), 0)
    pen = Pen(ImageDraw.Draw(img), frame=0, ss=ss, scale=1.0)
    rng = np.random.default_rng(seed + 1)

    # ---- margin doodles: sparkles, spirals, squiggles, clouds, hatch tufts ----
    placed = 0
    for i in range(150):
        if placed > 44:
            break
        x, y = rng.uniform(0.05, 0.95) * w, rng.uniform(0.03, 0.97) * h
        if abs(x - w / 2) < w * 0.30 and abs(y - ground_y) < h * 0.22:
            continue                                   # keep the acting area clear
        placed += 1
        s = rng.uniform(7, 20)
        a = int(rng.uniform(16, 44))
        k = int(rng.integers(0, 5))
        if k == 0:                                     # four-point sparkle
            pen.line((x - s, y), (x + s, y), weight=1.1, alpha=a, rough=0.5, seed=i)
            pen.line((x, y - s), (x, y + s), weight=1.1, alpha=a, rough=0.5, seed=i + 3)
        elif k == 1:                                   # spiral
            u = np.linspace(0, 7.7, 16)
            pts = [(x + math.cos(v) * s * v / 7.7, y + math.sin(v) * s * v / 7.7) for v in u]
            pen.poly(pts, weight=1.2, alpha=a, rough=0.8, seed=i + 11)
        elif k == 2:                                   # squiggle
            pts = [(x + j * s * 0.45, y + (s * 0.4 if j % 2 else -s * 0.4)) for j in range(7)]
            pen.poly(pts, weight=1.2, alpha=a, rough=0.9, seed=i + 23)
        elif k == 3:                                   # tiny cloud
            pen.arc(x, y, s, s * 0.62, 165, 375, weight=1.2, alpha=a, seed=i + 31)
            pen.arc(x - s * 0.15, y + s * 0.1, s * 0.75, s * 0.5, 20, 180, weight=1.0,
                    alpha=int(a * 0.8), seed=i + 41)
        else:                                          # grass / tuft hatch
            for j in range(4):
                pen.line((x + j * 4, y - s * 0.5), (x + j * 4 - s * 0.3, y + s * 0.5),
                         weight=1.0, alpha=a, rough=0.7, seed=i + j)

    # ---- the ground line the page hands them ----
    gy = ground_y
    pen.line((w * 0.09, gy), (w * 0.91, gy), weight=2.1, alpha=66, rough=2.3, seed=99)
    pen.line((w * 0.15, gy + 7), (w * 0.70, gy + 9), weight=1.1, alpha=28, rough=2.8, seed=101)
    for i in range(18):
        x = w * (0.11 + 0.78 * i / 17.0) + rng.uniform(-16, 16)
        pen.line((x, gy + rng.uniform(3, 13)),
                 (x + rng.uniform(-10, 10), gy + rng.uniform(16, 32)),
                 weight=1.0, alpha=int(rng.uniform(20, 46)), rough=1.0, seed=200 + i)
    # a couple of pencil nubs / crumbs already on the sheet
    for i in range(9):
        x, y = rng.uniform(0.12, 0.88) * w, gy + rng.uniform(10, 120)
        pen.circle(x, y, rng.uniform(1.2, 2.6), weight=1.0, alpha=int(rng.uniform(40, 90)),
                   rough=0.7, seed=300 + i, halo=False)

    cov = np.frombuffer(img.tobytes(), np.uint8).reshape(h * ss, w * ss)
    cov = (cov.reshape(h, ss, w, ss).sum((1, 3)).astype(np.float32) / (ss * ss * 255.0)) * tooth
    cov = np.clip(cov, 0, 1)[:, :, None]
    out = paper * (1.0 - cov) + np.array(INK, np.float32) * cov
    out = np.asarray(Image.fromarray(out.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.35)))
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(out).save(path)
    return out
