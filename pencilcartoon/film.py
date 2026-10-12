"""Renderer: pencil layer -> paper composite -> ffmpeg, one frame at a time.

Frames are drawn on a 2x supersampled *grayscale coverage* layer (the graphite),
box-filtered down to 1080x1920, multiplied into the baked page through a paper
"tooth" mask, and piped straight into x264.  Nothing is written to disk in
between, which is how a 30 s @ 60 fps cartoon fits inside a 3 GB sandbox.

Frame flow:   story.build(t) -> spec -> draw_spec(pen, spec) -> compose -> encode
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .paper import INK, background_cel
from .props import cookie, crumbs, dust_cloud, eraser, hand_flag, hand_shadow, \
    impact_star, motion_arcs, page_mark, pencil_prop, shock_lines, speed_lines, \
    sweat, symbol
from .rig import PROP_A, PROP_B, draw_actor
from .sketchpen import Pen

SS = 2                    # supersample factor
DRAW_FPS = 20.0           # pencil drawables per second -> shot "on threes" at 60

DISPATCH = {
    "cookie": cookie, "pencil": pencil_prop, "eraser": eraser, "dust": dust_cloud,
    "speed": speed_lines, "star": impact_star, "symbol": symbol, "arcs": motion_arcs,
    "sweat": sweat, "shadow": hand_shadow, "crumbs": crumbs, "shock": shock_lines,
    "hands": hand_flag, "tick": page_mark,
}


class Film:
    def __init__(self, w: int, h: int, fps: float, seed: int = 7,
                 cache: str | None = None):
        self.w, self.h, self.fps, self.seed = w, h, fps, seed
        self.hold = max(1, int(round(fps / DRAW_FPS)))
        self.bg = background_cel(w, h, ground_y=1500, seed=seed, path=cache)
        self.tooth = _tooth(w, h, seed)
        self.paper = self.bg.astype(np.float32)
        self.layer = Image.new("L", (w * SS, h * SS), 0)
        self.draw = ImageDraw.Draw(self.layer)
        self.freeze_at: float | None = None      # set -> boil locks off

    # ------------------------------------------------------------------ paint
    def paint(self, t: float) -> np.ndarray:
        from .story import build                 # late import: story owns the beats
        idx = int(t * self.fps) // self.hold
        if self.freeze_at is not None:           # freeze-frame: lines stop boiling
            idx = int(self.freeze_at * self.fps) // self.hold
            t = self.freeze_at
        spec = build(t)
        w, h = self.w, self.h
        self.draw.rectangle([0, 0, w * SS, h * SS], fill=0)
        pen = Pen(self.draw, frame=idx, ss=SS, scale=1.0)
        draw_spec(pen, spec, self)
        return self.compose(spec.get("heavy", 1.0))

    def compose(self, heavy: float = 1.0) -> np.ndarray:
        w, h = self.w, self.h
        cov = np.frombuffer(self.layer.tobytes(), np.uint8)
        cov = cov.reshape(h, SS, w, SS).sum((1, 3)).astype(np.float32) / (SS * SS * 255.0)
        cov = np.clip(cov * self.tooth * heavy, 0, 1) ** 0.86
        cov = cov[:, :, None]
        out = self.paper * (1.0 - cov) + np.array(INK, np.float32) * cov
        return out.astype(np.uint8)


def draw_spec(pen: Pen, spec: dict, film: Film):
    """Paint one frame description produced by story.build()."""
    bg = spec.get("bgprops", [])
    marks: dict = {}
    _items(pen, bg, marks, actors_drawn=False)
    actors = sorted(spec.get("actors", []), key=lambda a: a["pose"]["y"])  # far first
    marks: dict = {}
    for a in actors:
        P = a["pose"]
        pr = PROP_A if a["kind"] == "A" else PROP_B
        sh = P.get("shadow", 1.0)
        if sh > 0.01:
            hand_shadow(pen, P["x"] + P.get("shadow_dx", 0.0), P["y"] + 3.0,
                        36 * P["scale"] * P["sqx"], 8.5 * P["scale"], alpha=int(32 * sh))
        m: dict = {}
        if not a.get("ghost"):
            draw_actor(pen, P, pr, m)
        marks[a["kind"]] = m

    _items(pen, spec.get("props", []) + spec.get("fx", []), marks)


def _items(pen: Pen, items, marks: dict, actors_drawn=True):
    for item in items:
        kw = {k: v for k, v in item.items() if k not in ("draw", "attach")}
        if "attach" in item and item["attach"]:
            kind, which, dx, dy = item["attach"]
            m = marks.get(kind) or {}
            pos = m.get(which)
            if pos is None:
                continue
            kw["x"], kw["y"] = pos[0] + dx, pos[1] + dy
        fn = DISPATCH.get(item["draw"])
        if fn is None:
            raise KeyError(f"unknown draw call {item['draw']!r}")
        fn(pen, **kw)


def _tooth(w: int, h: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 5)
    n = rng.standard_normal((h // 2, w // 2)).astype(np.float32)
    lo, hi = float(n.min()), float(n.max())
    n8 = (((n - lo) / (hi - lo)) * 255).astype(np.uint8)
    n = np.asarray(Image.fromarray(n8).resize((w, h), Image.BILINEAR), np.float32)
    return np.clip(1.0 + (n - 128.0) / 255.0 * 0.55 + rng.standard_normal((h, w)) * 0.10,
                   0.62, 1.34).astype(np.float32)


def depth_scale(y: float, base: float) -> float:
    """Fake depth: the far side of the page is a touch smaller, like a real sketch."""
    k = (y - 1378.0) / (1568.0 - 1378.0)
    return base * (0.84 + 0.16 * max(0.0, min(1.0, k)))
