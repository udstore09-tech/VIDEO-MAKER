"""Sketch pen: graphite-pencil line primitives.

Everything in the film is drawn as *wobbly polylines* on a white layer which is
later multiply-composited over scanned-looking notebook paper, so the "graphite"
catches the paper tooth exactly like a real pencil drawing.

The hand-drawn boil comes from ``frame`` (the current drawing number).  A
classical 2D cartoon is shot "on twos", so geometry is quantised to 20 pencil
drawables per second while the output runs at 60 fps -- the motion reads as
smooth, but every line shivers like xeroxed animation cels.
"""

from __future__ import annotations

import math
import random

from typing import Sequence

from PIL import ImageDraw

Point = tuple[float, float]


# --------------------------------------------------------------------------- #
# deterministic noise
# --------------------------------------------------------------------------- #
def _hash(i: int, seed: int) -> float:
    """Stable 0..1 hash - the same key always gives the same pencil wobble."""
    x = (i * 374761393 + seed * 1103515245 + 12345) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF) / 0xFFFFFF


def _h(i: int, seed: int) -> float:
    """Signed noise in -1..1."""
    return _hash(i, seed) * 2.0 - 1.0


def periodic_noise(u: float, seed: int, harmonics: int = 3) -> float:
    """Smooth noise for *closed* loops (u=0 and u=1 meet seamlessly)."""
    v = 0.0
    for k in range(1, harmonics + 1):
        a = _h(seed * 97 + k * 7, 1) / k ** 0.7
        b = _h(seed * 97 + k * 13, 2) / k ** 0.7
        v += a * math.sin(2 * math.pi * k * u) + b * math.cos(2 * math.pi * k * u)
    return v / (1.0 + harmonics ** 0.4)


def open_noise(u: float, seed: int, harmonics: int = 3) -> float:
    """Smooth noise for open strokes, calmed down near the ends."""
    v = 0.0
    for k in range(1, harmonics + 2):
        f = k * 0.77 + 0.6
        p = _h(seed * 131 + k * 17, 3) * math.pi
        v += math.sin(2 * math.pi * f * u - p) / k ** 0.8
    return v * 0.5 * (0.5 - math.cos(2 * math.pi * u) * 0.5) ** 0.25


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #
def resample(pts: Sequence[Point], spacing: float) -> list[Point]:
    """Re-space a polyline so wobble is applied per unit of arc length."""
    out: list[Point] = [pts[0]]
    if len(pts) < 2:
        return out
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg < 1e-9:
            continue
        while acc + seg >= spacing:
            t = (spacing - acc) / seg
            nx, ny = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            out.append((nx, ny))
            x0, y0, seg = nx, ny, seg * (1 - t)
            acc = 0.0
        acc += seg
    if math.hypot(out[-1][0] - pts[-1][0], out[-1][1] - pts[-1][1]) > spacing * 0.35:
        out.append(pts[-1])
    return out


def ellipse_pts(cx, cy, rx, ry, rot=0.0, n=26, a0=0.0, a1=360.0) -> list[Point]:
    rot = math.radians(rot)
    out = []
    steps = max(3, int(n * abs(a1 - a0) / 360.0))
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        x, y = rx * math.cos(a), ry * math.sin(a)
        out.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return out


# --------------------------------------------------------------------------- #
# the pen
# --------------------------------------------------------------------------- #
class Pen:
    """A pencil of a given hardness drawing onto a supersampled RGBA layer.

    Callers work in *final* pixel space; the pen multiplies by ``ss`` so nothing
    downstream has to know about the supersampling factor.
    """

    def __init__(self, draw: ImageDraw.ImageDraw, frame: int, ss: float = 2.0,
                 scale: float = 1.0, ink=(58, 56, 54)):
        self.draw = draw
        self.mode = getattr(draw, "im", None)
        self.lmode = bool(self.mode is not None and self.mode.mode == "L")
        self.frame = frame      # quantised drawing index -> the line boil
        self.ss = ss
        self.scale = scale      # world zoom of the current shot
        self.ink = ink

    # ---------------------------------------------------------------- plumbing
    def _fill(self, alpha: float, color=None):
        """'L' layers store ink coverage as a single int; RGBA layers take a tuple."""
        a = int(max(0, min(255, alpha)))
        if self.lmode:
            return a
        col = color or self.ink
        return (col[0], col[1], col[2], a)

    def _xy(self, p: Point) -> tuple[float, float]:
        return (p[0] * self.ss, p[1] * self.ss)

    def _px(self, v: float) -> int:
        return max(1, int(round(v * self.ss * self.scale)))

    def dot(self, p: Point, r: float, alpha: int, color=None):
        x, y = self._xy(p)
        rr = r * self.ss * self.scale
        self.draw.ellipse([x - rr, y - rr, x + rr, y + rr],
                          fill=self._fill(alpha if self.lmode else alpha, color))

    # ------------------------------------------------------------------ stroke
    def stroke(self, pts, weight=2.0, alpha=170, rough=1.7, seed=0, closed=False,
               halo=True, taper=0.0, passes=2, color=None, joint="curve"):
        """Draw one sketchy pencil stroke -- the work-horse of the whole film."""
        if len(pts) < 2:
            return
        spacing = max(3.0, 7.0 / max(0.35, self.scale))
        rp = resample(pts, spacing)
        while len(rp) < 3:            # a near-dot still needs a real u range
            rp = rp + [rp[-1]]
        n = len(rp)
        # length feeds the noise phase, so a stroke keeps its own personality
        # while the character moves instead of boiling at random
        length = sum(math.hypot(rp[i + 1][0] - rp[i][0], rp[i + 1][1] - rp[i][1])
                     for i in range(n - 1))
        seed = int(seed * 1000003 + self.frame * 7919 + length) & 0x7FFFFFFF
        amp = rough / max(0.6, self.scale) ** 0.35

        # pressure taper: split the path into chunks with a width curve
        chunks = 3 if taper > 0.01 else 1
        bounds = [int(round(i * (n - 1) / chunks)) for i in range(chunks + 1)]
        widths = [weight * max(0.25, 1.0 - taper *
                (1.0 - 2.0 * abs((b + 0.5) / chunks - 0.5)) ** 2) for b in bounds[:-1]]

        col = color or self.ink
        for p in range(passes):
            s2 = seed + p * 7717
            jit = 1.0 - 0.4 * p
            geo = []
            for i, (x, y) in enumerate(rp):
                u = i / (n - 1)
                e = periodic_noise(u, s2, 3) if closed else open_noise(u, s2)
                if i == 0:
                    dx, dy = rp[1][0] - x, rp[1][1] - y
                elif i == n - 1:
                    dx, dy = x - rp[-2][0], y - rp[-1][1]
                else:
                    dx, dy = rp[i + 1][0] - rp[i - 1][0], rp[i + 1][1] - rp[i - 1][1]
                L = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / L, dx / L
                off = e * amp * jit * self.scale
                geo.append((x + nx * off + _h(s2 + i, 9) * 0.3 * amp,
                            y + ny * off + _h(s2 + i, 11) * 0.3 * amp))
            bnds, wds = [(0, len(geo) - 1)], [weight * (1.0 if p == 0 else 0.62)]
            if closed:
                geo.append(geo[0])
            else:
                bnds, wds = list(zip(bounds[:-1], bounds[1:])), widths
            for (lo, hi), w in zip(bnds, wds):
                seg = geo[lo:max(lo + 1, hi + 1)]
                if len(seg) < 2:
                    continue
                w = max(0.4, w) * (1.0 if p == 0 else 0.62)
                a = alpha * (0.55 if p == 0 else 1.0)
                ss_pts = [self._xy(q) for q in seg]
                if halo:
                    self.draw.line(ss_pts, fill=self._fill(a * 0.42, col),
                                   width=self._px(w * 2.3), joint=joint)
                self.draw.line(ss_pts, fill=self._fill(a, col),
                               width=self._px(w), joint=joint)

    # ------------------------------------------------------------ shape sugars
    def line(self, *args, **kw):
        """Accepts line((x0, y0), (x1, y1), ...) or line(x0, y0, x1, y1, ...)"""
        if len(args) == 2:
            a, b = args
        else:
            x0, y0, x1, y1 = args[:4]
            a, b = (x0, y0), (x1, y1)
        return self.stroke([a, b], **kw)

    def poly(self, pts, **kw):
        return self.stroke(list(pts), **kw)

    def loop(self, pts, **kw):
        kw.setdefault("closed", True)
        return self.stroke(list(pts) + [pts[0]], **kw)

    def circle(self, cx, cy, r, **kw):
        kw.setdefault("seed", int(cx * 31 + cy * 17 + r * 7))
        rot = kw.pop("rot", 0.0)
        a0, a1 = kw.pop("a0", 0.0), kw.pop("a1", 360.0)
        ry = r * kw.pop("ry_ratio", 1.0)
        pts = ellipse_pts(cx, cy, r, ry, rot, n=kw.pop("n", 26), a0=a0, a1=a1)
        return self._finish(pts, a1 - a0 >= 359.9, kw)

    def _finish(self, pts, full_loop, kw):
        if full_loop:
            kw["closed"] = True
        return self.stroke(pts, **kw)

    def ellipse(self, cx, cy, rx, ry, rot=0.0, **kw):
        kw.setdefault("seed", int(cx * 31 + cy * 17 + rx * 11))
        a0, a1 = kw.pop("a0", 0.0), kw.pop("a1", 360.0)
        pts = ellipse_pts(cx, cy, rx, ry, rot, n=kw.pop("n", 26), a0=a0, a1=a1)
        return self._finish(pts, a1 - a0 >= 359.9, kw)

    def arc(self, cx, cy, rx, ry, a0, a1, rot=0.0, **kw):
        kw.setdefault("seed", int(cx * 13 + cy * 29 + a0))
        kw.setdefault("rough", 1.3)
        return self.stroke(ellipse_pts(cx, cy, rx, ry, rot, n=18, a0=a0, a1=a1), **kw)

    # -------------------------------------------------------------- fills/tints
    def hatch(self, cx, cy, rx, ry, angle=-38.0, spacing=6.0, weight=1.3,
              alpha=95, rough=1.1, seed=0, inset=0.0):
        """Pencil shading: parallel strokes clipped to an ellipse."""
        rad = math.radians(angle)
        ca, sa = math.cos(rad), math.sin(rad)
        rng = random.Random(int(seed * 867 + self.frame))
        span = max(rx, ry) * 2.0
        k = -span / 2
        while k < span / 2:
            rr = max(0.0, 1.0 - (k / (span / 2)) ** 2)
            half = math.sqrt(rr) * (span / 2) - inset
            if half > spacing * 0.6:
                o = k + rng.uniform(-spacing * 0.35, spacing * 0.35)
                a = (-half + inset * 0.4, o)
                b = (half - inset * 0.4, o)
                pa = (cx + a[0] * ca - a[1] * sa, cy + a[0] * sa + a[1] * ca)
                pb = (cx + b[0] * ca - b[1] * sa, cy + b[0] * sa + b[1] * ca)
                self.stroke([pa, pb], weight=weight, alpha=alpha, rough=rough,
                            seed=seed + int(k * 13), halo=False, passes=1)
            k += spacing

    def scribble(self, cx, cy, rx, ry, loops=7, weight=1.9, alpha=150,
                 rough=2.4, seed=0, tail=0.0):
        """Rapid back-and-forth shading, messy hair, puffy smoke."""
        pts = []
        n = loops * 2
        for i in range(n + 1):
            u = i / n
            a = u * loops * math.pi * 2
            wob = 1.0 - 0.55 * abs(math.sin(a * 0.5))
            pts.append((cx + math.cos(a) * rx * wob, cy + math.sin(a) * ry * wob * 0.8))
        if tail:
            pts.append((cx + rx * tail, cy - ry * tail * 0.4))
        self.stroke(pts, weight=weight, alpha=alpha, rough=rough, seed=seed, halo=False)

    def dots(self, pts, r=2.0, alpha=180, seed=0, color=None):
        """Small pressed marks: cookie chips, pupils, dust specks."""
        for i, p in enumerate(pts):
            jx = _h(seed + i * 3, self.frame) * 0.6
            jy = _h(seed + i * 5, self.frame + 1) * 0.6
            self.dot((p[0] + jx, p[1] + jy), r, alpha, color)

    def blob(self, cx, cy, rx, ry, rot=0.0, alpha=225, color=None, n=16, rough=0.0):
        """A pressed, filled mark: pupils, nostrils, the dark of an open mouth."""
        pts = [(x, y) for x, y in ellipse_pts(cx, cy, rx, ry, rot, n=n)]
        if rough > 0.01:
            sd = int(cx * 7 + cy * 13 + rx * 3) & 0x7FFFFFF
            pts = [(x + _h(sd + i, self.frame) * rough, y + _h(sd * 3 + i, self.frame) * rough)
                   for i, (x, y) in enumerate(pts)]
        ss_pts = [self._xy(q) for q in pts]
        self.draw.polygon(ss_pts, fill=self._fill(alpha, color or self.ink))

    def smudge(self, cx, cy, rx, ry, alpha=34, seed=0):
        """Soft graphite smear used as a contact shadow."""
        for i in range(4):
            r = 1.0 - i * 0.16
            self.ellipse(cx, cy, rx * r, ry * r, rot=i * 11, weight=2.6 - i * 0.4,
                         alpha=alpha, rough=2.6 + i, seed=seed + i * 31,
                         halo=False, passes=1)
