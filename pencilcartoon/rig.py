"""The two kids: a rig an animator would actually key with.

Both actors share one pose vocabulary (a flat dict of keyable parameters), are
resolved through a tiny 2-bone IK skeleton, and then drawn as pencil strokes.
Local space is "y up" with the origin at the contact point between the feet, so
squash & stretch always pivots on the floor like it should.

    A  tall, skinny, messy hair, long arms, permanently up to something
    B  short, round, tiny legs, big cheeks, cookie-shaped temper

Look notes, learned the hard way off the model sheet: dot eyes read best at
cartoon scale, mouths stay under 80% of the head width, brows sit close to the
eyes, and the far-side limbs are drawn lighter so a flat drawing still has depth.
"""

from __future__ import annotations

import math

from .sketchpen import ellipse_pts

D = math.radians
INKW = 2.35          # outline weight, world units
FAR = 0.72           # alpha multiplier for the far-side limb


# --------------------------------------------------------------------------- #
# transforms
# --------------------------------------------------------------------------- #
class T:
    """Composable local->screen transform (y-up local space, y-down screen)."""

    __slots__ = ("ox", "oy", "rot", "k", "parent")

    def __init__(self, ox=0.0, oy=0.0, rot=0.0, k=1.0, parent=None):
        self.ox, self.oy, self.rot, self.k, self.parent = ox, oy, rot, k, parent

    def v(self, x: float, y: float):
        if self.rot:
            c, s = math.cos(D(self.rot)), math.sin(D(self.rot))
            x, y = x * c - y * s, x * s + y * c
        x, y = x * self.k, y * self.k
        if self.parent is not None:
            return self.parent.v(x, y)
        return (self.ox + x, self.oy - y)

    def path(self, pts):
        return [self.v(x, y) for x, y in pts]


def root_frame(P) -> T:
    return T(P["x"], P["y"], rot=P["rot"], k=P["scale"])


def body_pt(P, x: float, y: float):
    """Character-local (y up, facing right) -> screen px, with squash + facing."""
    return root_frame(P).v(x * P["dir"] * P["sqx"], y * P["sqy"])


def body_path(P, pts):
    return [body_pt(P, x, y) for x, y in pts]


def body_inv(P, sx: float, sy: float):
    """screen px -> character-local units.  Lets the story point a hand at anything
    in the world and let the IK sort the arm out."""
    k = P["scale"]
    X, Y = (sx - P["x"]) / k, (P["y"] - sy) / k
    a = D(P["rot"]); c, s = math.cos(a), math.sin(a)
    x, y = X * c + Y * s, -X * s + Y * c
    a = D(P["lean"]); c, s = math.cos(a), math.sin(a)
    u, v = x * c - y * s, x * s + y * c
    return (u / (P["dir"] * P["sqx"]), v / P["sqy"])


# --------------------------------------------------------------------------- #
# skeleton maths
# --------------------------------------------------------------------------- #
def ik2(root, target, l1, l2, bend=1.0):
    """Two-bone IK: returns (joint, end), clamped when the target is out of reach."""
    rx, ry = root
    dx, dy = target[0] - rx, target[1] - ry
    d = math.hypot(dx, dy)
    d = min(max(d, abs(l1 - l2) + 0.001), l1 + l2 - 0.001)
    if d <= 0.002:
        return (rx, ry + l1), (rx, ry)
    a = math.atan2(dy, dx)
    cosA = max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))
    ang = math.acos(cosA) * bend
    return ((rx + math.cos(a + ang) * l1, ry + math.sin(a + ang) * l1),
            (rx + math.cos(a) * d, ry + math.sin(a) * d))


def ik2_front(root, target, l1, l2, front=1.0):
    """Two-bone IK, but the joint is forced to the 'front' side (knees forward,
    like a real cartoon leg) instead of whichever solution the maths picks."""
    a = ik2(root, target, l1, l2, bend=-1.0)
    b = ik2(root, target, l1, l2, bend=1.0)
    sa = (a[0][0] - root[0]) * front
    sb = (b[0][0] - root[0]) * front
    return (b if sb > sa else a)


def gait_foot(phase: float, stride=30.0, lift=14.0, x0=0.0, skew=0.55):
    """Foot on a running cycle: cartoon ellipse, big lift, snap forward."""
    p = phase % 1.0
    a = D(360.0 * p)
    return (x0 + math.cos(a) * stride, max(0.0, math.sin(a + D(20))) * lift * (1.0 + skew))


def _hsh(i: int) -> float:
    x = (i * 2654435761) & 0xFFFFFFFF
    x ^= x >> 15
    return ((x * 40503) & 0xFFFF) / 32768.0 - 1.0


def _mw(W, i):
    """Far-side limbs: lighter and thinner, so a flat drawing still reads in depth."""
    if i == 0:
        return dict(W, weight=W["weight"] * .86, alpha=int(W["alpha"] * FAR))
    return dict(W, weight=W["weight"] * 1.05, alpha=min(235, W["alpha"] + 10))


# --------------------------------------------------------------------------- #
# pose defaults  (everything the story layer is allowed to key)
# --------------------------------------------------------------------------- #
BASE = dict(
    x=0.0, y=0.0, scale=1.0, dir=1, rot=0.0, sqx=1.0, sqy=1.0,
    lean=0.0, crouch=0.0, breathe=0.0,
    head_tilt=0.0, head_push=0.0, head_drop=0.0, head_turn=0.0,
    e_open=1.0, e_look=0.0, e_looky=0.0, e_style="normal",
    b_ang=0.0, b_raise=0.0,
    m="smile", m_open=0.0, m_w=1.0,
    hand_l=None, hand_r=None, elbow_l=-.55, elbow_r=.55,
    leg_mode="stand", foot_l=None, foot_r=None,
    gait_phase=0.0, gait_stride=30.0, gait_lift=14.0,
    hair=0.0, arm_swing=0.0, arm_len=1.0, leg_len=1.0, shadow=1.0,
)


def pose(**over) -> dict:
    p = dict(BASE)
    p.update(over)
    return p


def remix(src: dict, **over) -> dict:
    p = dict(src)
    p.update(over)
    return p


# --------------------------------------------------------------------------- #
# head frame + face library
# --------------------------------------------------------------------------- #
class Head:
    """Frame for the face.  ``cx, cy`` are the head centre in spine space; the head
    tilts about that point, then inherits facing, squash and world scale."""

    def __init__(self, parent: T, cx: float, cy: float, P: dict, rx: float, ry: float):
        self.parent, self.P = parent, P
        self.cx, self.cy = cx, cy
        self.rx, self.ry = rx, ry
        self.turn = P["head_turn"]

    def v(self, x, y):
        P = self.P
        a = D(P["head_tilt"])
        c, s = math.cos(a), math.sin(a)
        x, y = x * c - y * s + self.cx, x * s + y * c + self.cy
        return self.parent.v(x * P["dir"] * P["sqx"], y * P["sqy"])

    def path(self, pts):
        return [self.v(x, y) for x, y in pts]

    def ell(self, x, y, rx, ry):
        """Screen-space (cx, cy, rx, ry) for the pen - radii carry the world scale."""
        c = self.v(x, y)
        k = self.P["scale"]
        return (c[0], c[1], abs(rx * k * self.P["sqx"]), abs(ry * k * self.P["sqy"]))


def draw_eyes(pen, H: Head, P, seed, kind="A"):
    """Dot eyes with an expression library.  At cartoon scale this reads far better
    than outlined eyeballs, and it is what a doodler actually draws."""
    rx, ry = H.rx, H.ry
    sc = P["scale"]
    gap = rx * (0.40 if kind == "A" else 0.385)
    ey = ry * (0.19 if kind == "A" else 0.13)
    turn = H.turn * rx * 0.30
    style, openv = P["e_style"], P["e_open"]
    look, looky = P["e_look"] * rx * 0.22 + turn, P["e_looky"] * ry * 0.14
    pr = 3.05 if kind == "A" else 3.25          # pupil radius, head units

    for i, sx in enumerate((-1, 1)):
        cx, cy = sx * gap + turn * 0.5, ey
        if style in ("closed", "blink"):
            c = H.v(cx, cy + ry * 0.02)
            pen.arc(c[0], c[1], rx * .26 * sc, ry * .17 * sc, 210, 330, weight=2.5 * sc,
                    alpha=200, rough=.85, seed=seed + i)
            continue
        if style == "happy":
            c = H.v(cx, cy)
            pen.arc(c[0], c[1], rx * .27 * sc, ry * .21 * sc, 205, 335, weight=2.6 * sc,
                    alpha=205, rough=.85, seed=seed + i)
            continue
        if style == "spiral":
            pts = [(cx + math.cos(u + i * 1.3) * rx * .19 * (u / 7.0),
                    cy + math.sin(u + i * 1.3) * ry * .19 * (u / 7.0))
                   for u in [j * .48 for j in range(15)]]
            pen.poly(H.path(pts), weight=1.7 * sc, alpha=195, rough=.85, seed=seed + 10 + i)
            continue
        if style == "x":
            p = H.path([(cx - rx * .17, cy + ry * .15), (cx + rx * .17, cy - ry * .15)])
            q = H.path([(cx - rx * .17, cy - ry * .15), (cx + rx * .17, cy + ry * .15)])
            pen.line(p[0][0], p[0][1], p[1][0], p[1][1], weight=2.5 * sc, alpha=205,
                     rough=.7, seed=seed + 20 + i)
            pen.line(q[0][0], q[0][1], q[1][0], q[1][1], weight=2.5 * sc, alpha=205,
                     rough=.7, seed=seed + 21 + i)
            continue
        if style == "squint":
            p = H.path([(cx - rx * .20, cy - ry * .09 + (ry * .1 if sx > 0 else -ry * .06)),
                        (cx + rx * .20, cy + ry * .07 + (ry * .1 if sx > 0 else -ry * .06))])
            pen.line(p[0][0], p[0][1], p[1][0], p[1][1], weight=2.8 * sc, alpha=210,
                     rough=.7, seed=seed + 25 + i)
            continue
        if style == "wide":
            c = H.v(cx, cy)
            rr = rx * .235 * sc
            pen.ellipse(c[0], c[1], rr, rr * 1.12, weight=1.9 * sc, alpha=200, rough=.75,
                        seed=seed + 30 + i)
            px, py = H.v(cx + look * .55, cy + looky * .5)
            pen.dot((px, py), pr * .78 * sc, 235)
            continue
        if style == "bulge":
            c = H.v(cx, cy + ry * .05)
            rr = rx * .30 * sc
            pen.ellipse(c[0], c[1], rr, rr * 1.06, weight=2.3 * sc, alpha=212, rough=.9,
                        seed=seed + 32 + i)
            px, py = H.v(cx + look * .3, cy + looky * .3)
            pen.dot((px, py), pr * .52 * sc, 245)
            continue
        # normal: a pressed dot, half-lidded if e_open is low
        rr = pr * (1.0 + (0.18 if P["b_ang"] > 1.0 else 0.0))
        px, py = H.v(cx + look, cy + looky)
        rh = max(0.28, openv)
        pen.blob(px, py, rr * sc, rr * rh * sc, alpha=250, color=(44, 42, 40), rough=.5)
        if openv > .5:
            pen.dot((px - rr * .38 * sc, py - rr * .5 * sc), 1.15 * sc, 120,
                     color=(244, 243, 238))

    # brows, kept close to the eyes so the expression lands
    ba, br = P["b_ang"], P["b_raise"]
    bl = rx * (0.30 if kind == "A" else 0.27)
    for i, sx in enumerate((-1, 1)):
        cx, cy = sx * gap + turn * 0.5, ey + ry * (0.33 + br * 0.22)
        tilt = ba * (1 if sx > 0 else -1)
        p = H.path([(cx - bl, cy + tilt * 4.6), (cx + bl, cy - tilt * 4.6)])
        pen.line(p[0][0], p[0][1], p[1][0], p[1][1],
                 weight=(3.0 if kind == "B" else 2.5) * sc, alpha=206 if kind == "B" else 195,
                 rough=.95, seed=seed + 50 + i)


MOUTH_W = {"A": 0.72, "B": 0.66}


def draw_mouth(pen, H: Head, P, seed, kind="A"):
    rx, ry = H.rx, H.ry
    sc = P["scale"]
    w = rx * MOUTH_W[kind] * P["m_w"]
    cx, cy = H.turn * rx * .26, -ry * (0.42 if kind == "A" else 0.36)
    st, op = P["m"], P["m_open"]

    def line(a, b, **kw):
        p = H.path([a, b])
        pen.line(p[0][0], p[0][1], p[1][0], p[1][1], **kw)

    def poly(pts, **kw):
        pen.poly(H.path(pts), **kw)

    def ell(x, y, rxx, ryy, **kw):
        e = H.ell(x, y, rxx, ryy)
        pen.ellipse(e[0], e[1], e[2], e[3], **kw)

    def shade(x, y, rxx, ryy, ang=-25, spacing=3.4, alpha=100, sd=0):
        e = H.ell(x, y, rxx, ryy)
        pen.hatch(e[0], e[1], e[2], e[3], angle=ang, spacing=spacing * sc,
                  weight=1.25 * sc, alpha=alpha, seed=seed + sd)

    if st == "smile":
        poly([(cx - w * .5, cy + 1), (cx - w * .1, cy - w * .26 - op * 4),
              (cx + w * .5, cy + 1)], weight=2.3 * sc, alpha=200, rough=.95, seed=seed)
    elif st == "grin":
        poly([(cx - w * .58, cy + w * .04), (cx - w * .3, cy - w * .3),
              (cx + w * .34, cy - w * .3), (cx + w * .6, cy + w * .04),
              (cx + w * .2, cy - w * .02), (cx - w * .24, cy - w * .02),
              (cx - w * .58, cy + w * .04)], weight=2.1 * sc, alpha=205, rough=1.05,
             seed=seed + 1)
        poly([(cx - w * .05, cy - w * .02), (cx - w * .05, cy - w * .17),
              (cx + w * .13, cy - w * .17), (cx + w * .13, cy - w * .02)],
             weight=1.25 * sc, alpha=165, rough=.5, seed=seed + 2)
        shade(cx - w * .3, cy - w * .1, w * .2, w * .07, alpha=70, sd=3)
    elif st == "laugh":
        h = w * (.42 + .8 * op)
        poly([(cx - w * .5, cy + w * .06), (cx - w * .46, cy - h * .5),
              (cx + w * .48, cy - h * .55), (cx + w * .5, cy + w * .04),
              (cx + w * .1, cy - h * .12), (cx - w * .14, cy - h * .1),
              (cx - w * .5, cy + w * .06)], weight=2.1 * sc, alpha=205, rough=1.15,
             seed=seed + 4)
        shade(cx, cy - h * .42, w * .34, h * .26, alpha=110, sd=5)
    elif st in ("o", "gasp", "shock"):
        ell(cx, cy - w * .04, w * .28, w * (.26 + .5 * op), weight=2.1 * sc, alpha=205,
            rough=.85, seed=seed + 6)
        shade(cx, cy - w * .04, w * .2, w * (.2 + .4 * op), ang=25, spacing=3.0, alpha=120,
              sd=7)
        if st == "shock":
            ell(cx, cy - w * .04, w * .36, w * (.34 + .56 * op), weight=1.1 * sc,
                alpha=95, rough=1.6, seed=seed + 8)
    elif st == "flat":
        line((cx - w * .3, cy), (cx + w * .3, cy - 1.5), weight=2.3 * sc, alpha=200,
             rough=1.2, seed=seed + 9)
    elif st == "frown":
        poly([(cx - w * .34, cy - w * .08), (cx, cy + w * .16), (cx + w * .34, cy - w * .08)],
             weight=2.3 * sc, alpha=200, rough=1.0, seed=seed + 10)
    elif st == "wail":
        h = w * (.5 + .85 * op)
        poly([(cx - w * .42, cy + w * .14), (cx - w * .3, cy - h * .6),
              (cx + w * .32, cy - h * .62), (cx + w * .44, cy + w * .1),
              (cx + w * .1, cy - h * .16), (cx - w * .12, cy - h * .14),
              (cx - w * .42, cy + w * .14)], weight=2.05 * sc, alpha=205, rough=1.15,
             seed=seed + 11)
        shade(cx, cy - h * .42, w * .28, h * .22, alpha=115, sd=12)
        poly([(cx - w * .12, cy + w * .12), (cx + w * .12, cy + w * .14),
              (cx + w * .06, cy + w * .02)], weight=1.4 * sc, alpha=170, rough=.8,
             seed=seed + 13)
    elif st == "whistle":
        ell(cx - w * .16, cy, w * .19, w * .17, weight=2.1 * sc, alpha=200, rough=.8,
            seed=seed + 14)
        for i in range(3):
            e = H.ell(cx - w * .16, cy, w * (.19 - i * .05), w * (.17 - i * .045))
            pen.arc(e[0], e[1], e[2], e[3], 140, 250, weight=1.0 * sc,
                    alpha=90 - i * 25, rough=.6, seed=seed + 15 + i)
        line((cx + w * .06, cy + 1), (cx + w * .34, cy - w * .05), weight=1.8 * sc,
             alpha=165, rough=.8, seed=seed + 18)
    elif st == "tongue":
        poly([(cx - w * .44, cy), (cx, cy - w * .24), (cx + w * .44, cy)],
             weight=2.2 * sc, alpha=200, rough=.95, seed=seed + 19)
        poly([(cx + w * .06, cy - w * .02), (cx + w * .34, cy - w * .1),
              (cx + w * .42, cy + w * .3), (cx + w * .16, cy + w * .38),
              (cx + w * .04, cy + w * .1)], weight=1.9 * sc, alpha=200, rough=1.0,
             seed=seed + 20)
        line((cx + w * .22, cy), (cx + w * .24, cy + w * .3), weight=1.1 * sc,
             alpha=140, rough=.6, seed=seed + 21)
    elif st == "chew":
        ell(cx + w * .04, cy, w * .26, w * (.12 + .24 * op), weight=2.0 * sc, alpha=200,
            rough=.9, seed=seed + 22)
        shade(cx + w * .04, cy, w * .18, w * (.08 + .18 * op), ang=0, spacing=2.6,
              alpha=95, sd=23)
    elif st == "bite":
        poly([(cx - w * .36, cy - w * .04), (cx - w * .1, cy - w * .2),
              (cx + w * .2, cy - w * .18), (cx + w * .38, cy - w * .02),
              (cx - w * .36, cy - w * .04)], weight=2.0 * sc, alpha=205, rough=.9,
             seed=seed + 24)
        for k in range(4):
            x0 = cx - w * .26 + k * w * .17
            line((x0, cy - w * .05), (x0 + w * .05, cy - w * .17), weight=1.2 * sc,
                 alpha=150, rough=.5, seed=seed + 25 + k)
    else:
        poly([(cx - w * .5, cy + 1), (cx, cy - w * .26), (cx + w * .5, cy + 1)],
             weight=2.2 * sc, alpha=200, rough=.95, seed=seed + 30)


# --------------------------------------------------------------------------- #
# proportions
# --------------------------------------------------------------------------- #
PROP_A = dict(kind="A", hip=110.0, chest=204.0, sh=27.0, hipw=14.0, head=(0.0, 258.0),
              hrx=33.0, hry=36.0, arm=(24.0, 200.0, 52.0, 54.0),
              leg=(9.0, 110.0, 56.0, 54.0), hand=9.2, foot=14.0)
PROP_B = dict(kind="B", hip=46.0, chest=126.0, sh=42.0, hipw=30.0, head=(0.0, 150.0),
              hrx=38.0, hry=36.0, arm=(40.0, 120.0, 22.0, 21.0),
              leg=(17.0, 48.0, 24.0, 20.0), hand=8.8, foot=11.5)


def head_outline_A(rx, ry):
    """A's skull: tall egg, narrower chin, a flat-ish crown for the hair to sit on."""
    pts = []
    for i in range(25):
        a = math.pi * 2 * i / 24
        x, y = math.cos(a) * rx, math.sin(a) * ry
        y += 2.0 * math.sin(a) ** 3
        if math.sin(a) < 0:
            x *= 0.93
        pts.append((x, y + 1.0))
    return pts


# --------------------------------------------------------------------------- #
# the actors
# --------------------------------------------------------------------------- #
def draw_actor(pen, P, pr, marks=None):
    root = root_frame(P)
    spine = T(0, 0, rot=-P["lean"], k=1.0, parent=root)
    mx = P["dir"] * P["sqx"]
    my = P["sqy"]

    def SV(x, y):
        return spine.v(x * mx, y * my)

    def SP(pts):
        return [SV(x, y) for x, y in pts]

    sc = P["scale"]
    kind = pr["kind"]
    crouch = P["crouch"]
    hip_y = pr["hip"] - crouch * (24 if kind == "A" else 8)
    sh_y = pr["chest"] - crouch * (14 if kind == "A" else 5)
    W = dict(weight=INKW * sc, alpha=186, rough=1.75)
    out: dict = {}

    # ---------------- legs ----------------
    mode = P["leg_mode"]
    if mode == "spin":
        for i, side in enumerate((-1, 1)):
            x, y = SV(side * pr["leg"][0] + 5, 17)
            r = (24 if kind == "A" else 14) * sc
            pen.line(*SV(side * pr["leg"][0], hip_y), *SV(side * pr["leg"][0] + 5, 27),
                     **_mw(W, i), seed=440 + i)
            for k in range(3):
                pen.arc(x, y, r * (1 - k * .1), r * .86 * (1 - k * .1),
                        rot=P["gait_phase"] * 1300 + k * 55, a0=k * 115,
                        a1=k * 115 + 250, weight=(1.9 - k * .25) * sc,
                        alpha=int(180 - k * 42), rough=1.0, seed=430 + i * 10 + k)
    else:
        for i, side in enumerate((-1, 1)):
            hip = (side * pr["leg"][0], hip_y)
            ln = P.get("leg_len", 1.0)
            l1, l2 = pr["leg"][2] * ln, pr["leg"][3] * ln
            if mode == "sit":
                ft = (side * (14 if kind == "A" else 20) + 27, 2)
                knee = (ft[0] * .72 + 8, hip_y * .62)
                pen.poly(SP([hip, knee, ft]), **_mw(W, i), seed=400 + i)
            else:
                f = P["foot_l"] if i == 0 else P["foot_r"]
                front = 1.0
                if f is None and mode == "stand" and P["foot_l"] is None and P["foot_r"] is None:
                    f = (side * (pr["leg"][0] + (14 if kind == "A" else 15)), 1.5)
                    front = float(side) * .35          # planted: knees a touch out
                elif f is None:
                    ph = P["gait_phase"] + (0.5 if i else 0.0)
                    f = gait_foot(ph, P["gait_stride"] * (.8 if kind == "B" else 1.0),
                                  P["gait_lift"])
                jt, ft = ik2_front(hip, f, l1, l2, front=front)
                pen.poly(SP([hip, jt, ft]), **_mw(W, i), seed=410 + i)
            fx, fy = SV(*ft)
            far = FAR if i == 0 else 1.0
            fw, fh = pr["foot"] * sc * .92, pr["foot"] * sc * .44
            pen.ellipse(fx + fw * .3 * P["dir"], fy - fh * .1, fw, fh,
                        weight=1.9 * sc, alpha=int(200 * far), rough=1.0, seed=420 + i)
            pen.line(fx - fw * .45, fy + fh * .52, fx + fw * 1.12, fy + fh * .44,
                     weight=1.5 * sc, alpha=int(150 * far), rough=.85, seed=424 + i)

    # ---------------- body ----------------
    if kind == "A":
        hw, sh = pr["hipw"], pr["sh"]
        mid = (hip_y + sh_y) * .5
        body = [(-sh + 1, sh_y + 3), (-sh - 3, mid + 12), (-hw - 8, hip_y + 7),
                (-hw - 5, hip_y - 2), (0, hip_y - 6), (hw + 5, hip_y - 2),
                (hw + 8, hip_y + 7), (sh + 3, mid + 12), (sh - 1, sh_y + 3)]
        pen.poly(SP(body), closed=True, **dict(W, rough=1.45), seed=500)
        pen.poly(SP([(-10, sh_y - 1), (0, sh_y - 8), (10, sh_y - 2)]),        # neckline
                 weight=1.5 * sc, alpha=130, rough=1.0, seed=502)
        cx, cy = SV(-hw - 5, mid + 4)
        pen.hatch(cx, cy, 6 * sc, 15 * sc, angle=-74, spacing=6.4 * sc, weight=1.05 * sc,
                  alpha=26, seed=504)
        n0, n1 = SV(-6, sh_y - 2), SV(-5, sh_y + 15)
        n2, n3 = SV(6, sh_y - 2), SV(6, sh_y + 14)
        pen.line(n0[0], n0[1], n1[0], n1[1], weight=1.8 * sc, alpha=170, rough=1.0, seed=505)
        pen.line(n2[0], n2[1], n3[0], n3[1], weight=1.8 * sc, alpha=170, rough=1.0, seed=506)
    else:
        bx, by = SV(0, hip_y + 31)
        k = sc
        # the top of the belly is behind his head, so it simply isn't drawn
        pen.ellipse(bx, by, pr["sh"] * 1.19 * k * abs(mx), pr["sh"] * 1.05 * k * abs(my),
                    a0=312, a1=588, weight=W["weight"], alpha=W["alpha"], rough=1.55,
                    seed=510)
        cx, cy = SV(14, hip_y + 6)
        pen.hatch(cx, cy, pr["sh"] * .5 * k, pr["sh"] * .34 * k, angle=-42,
                  spacing=6.2 * k, weight=1.1 * k, alpha=26, seed=511)
        pen.poly(SP([(-pr["sh"] * .74, hip_y + 14), (0, hip_y + 5),
                     (pr["sh"] * .74, hip_y + 11)]),
                 weight=1.5 * k, alpha=95, rough=1.4, seed=512)
        for s2 in (-1, 1):                      # suspender straps
            pen.line(*SP([(s2 * 13, hip_y + 58), (s2 * 22, sh_y - 6)]), weight=1.5 * k,
                     alpha=110, rough=1.3, seed=513 + s2)
        for s2 in (-1, 1):                      # little buttons
            bp = SP([(s2 * 15, hip_y + 54)])[0]
            pen.blob(bp[0], bp[1], 2.3 * k, 2.3 * k, alpha=180, rough=.4)

    # ---------------- arms ----------------
    for i, side in enumerate((-1, 1)):
        sho = (side * pr["arm"][0], pr["arm"][1])
        aln = P.get("arm_len", 1.0)
        l1, l2 = pr["arm"][2] * aln, pr["arm"][3] * aln
        hand = P["hand_l" if i == 0 else "hand_r"]
        bend = P["elbow_l"] if i == 0 else P["elbow_r"]
        if hand is None:
            sw = P["arm_swing"] * (1 if i == 0 else -1)
            hand = (side * (pr["arm"][0] + 15 + sw * 5.0),
                    pr["arm"][1] - (l1 + l2) * .82 + sw * 9.0 + P["breathe"] * 3)
        jt, et = ik2(sho, hand, l1, l2, bend=bend)
        s0, j, e = SP([sho, jt, et])
        far = FAR if i == 0 else 1.0
        wl = W["weight"] * (.9 if i == 0 else 1.06)
        elb = (j[0] - s0[0], j[1] - s0[1])
        pen.line(s0[0], s0[1], j[0], j[1], weight=wl, alpha=int(192 * far), rough=1.5,
                 seed=520 + i)
        pen.line(j[0], j[1], e[0], e[1], weight=wl * .95, alpha=int(192 * far), rough=1.5,
                 seed=530 + i)
        # mitten hand with a thumb: reads as a hand, not as a clock
        rr = pr["hand"] * sc
        rot = math.degrees(math.atan2(elb[1], elb[0])) + 90
        pen.ellipse(e[0], e[1], rr, rr * .92, rot=rot, weight=wl * .95,
                    alpha=int(198 * far), rough=1.15, seed=540 + i)
        pen.arc(e[0], e[1], rr * .58, rr * .58, -30, 90, rot=rot - 90, weight=wl * .8,
                alpha=int(150 * far), rough=.9, seed=545 + i)
        for kk in range(2):
            aa = D(rot + 96 + kk * 26)
            pen.line(e[0] + math.cos(aa) * rr * .72, e[1] + math.sin(aa) * rr * .72,
                     e[0] + math.cos(aa) * (rr + 3.4 * sc), e[1] + math.sin(aa) * (rr + 3.4 * sc),
                     weight=1.3 * sc, alpha=int(140 * far), rough=.6, seed=550 + i * 3 + kk)
        out["hand_l" if i == 0 else "hand_r"] = e

    # ---------------- head ----------------
    hx = pr["head"][0] + P["head_push"] * 5
    hy = pr["head"][1] - P["head_drop"] * 7
    rx, ry = pr["hrx"], pr["hry"]
    H = Head(spine, hx, hy, P, rx, ry)
    H.raw = H.v

    if kind == "A":
        pen.poly(H.path(head_outline_A(rx, ry)), closed=True, weight=W["weight"] * 1.04,
                 alpha=196, rough=1.5, seed=600)
        c = H.raw(-rx * .95, 2)
        pen.arc(c[0], c[1], 7.5 * sc, 9.5 * sc, 100, 262, weight=1.8 * sc, alpha=160,
                rough=.85, seed=601)
        pen.poly(H.path([(rx * .24, 0), (rx * .5, -10), (rx * .28, -17)]),
                 weight=1.9 * sc, alpha=190, rough=.85, seed=602)
    else:
        pen.poly(H.path(ellipse_pts(0, 0, rx, ry, 0, n=24)), closed=True,
                 weight=W["weight"] * 1.04, alpha=196, rough=1.55, seed=610)
        for i, side in enumerate((-1, 1)):      # puffy cheeks, bulging the silhouette
            c = H.raw(side * rx * .74, -ry * .26)
            rr = rx * .315 * sc
            pen.circle(c[0], c[1], rr, ry_ratio=.92, weight=1.95 * sc, alpha=178,
                       rough=1.15, seed=611 + i)
            if P["m"] == "chew":
                pen.hatch(c[0], c[1], rr * .74, rr * .68, angle=18, spacing=4.6 * sc,
                          weight=1.0 * sc, alpha=30, seed=613 + i)
        c = H.raw(-rx * .98, 8)
        pen.arc(c[0], c[1], 7 * sc, 9 * sc, 105, 255, weight=1.8 * sc, alpha=155,
                rough=.85, seed=615)

    draw_eyes(pen, H, P, 620, kind=kind)
    draw_mouth(pen, H, P, 660, kind=kind)

    # ---------------- hair ----------------
    if kind == "A":
        # doodle hair: one open zigzag over the crown - tip, dip, tip, dip - with a
        # few stray strokes inside it.  Reads instantly, and it boils nicely.
        N = 13
        pts = []
        for i in range(N + 1):
            a = math.pi * (0.78 - i / N * 0.56)
            n = _hsh(i * 7 + 3)
            if i % 2 == 1:                                   # a spike
                ln = (7 + 9 * abs(n)) * (1.0 + P["hair"] * .95)
                pts.append((math.cos(a) * (rx + ln * .30) + n * 2.2,
                            math.sin(a) * (ry * 1.02 + ln)))
            else:                                            # back down to the skull
                pts.append((math.cos(a) * rx * .99, math.sin(a) * ry * 1.0))
        pen.poly(H.path(pts), weight=2.05 * sc, alpha=198, rough=1.15, seed=695)
        for i in range(4):                                   # hair mass, inside
            a0 = math.pi * (.74 - i * .13)
            a1 = math.pi * (.52 - i * .16)
            rr = ry * (.78 + i * .06)
            pen.poly(H.path([(math.cos(a0) * rx * .86, math.sin(a0) * rr + 2),
                             (math.cos(a1) * rx * .3, math.sin(a1) * (rr + 6)),
                             (math.cos(a0 - .5) * rx * .8, math.sin(a0 - .3) * rr)]),
                     weight=1.5 * sc, alpha=88, rough=1.5, seed=706 + i)
        for i in range(3):                                   # flyaways
            n = _hsh(i * 11 + 40)
            a = math.pi * (.84 - i * .3)
            bx, by = math.cos(a) * rx * 1.02, math.sin(a) * ry * 1.06
            pen.poly(H.path([(bx, by), (bx + n * 12, by + 13 + 6 * abs(n)),
                             (bx + n * 20, by + 20 + 8 * abs(n))]),
                     weight=1.3 * sc, alpha=112, rough=1.4, seed=730 + i)
    else:
        tuft = 1 + P["hair"] * 1.9
        N = 7
        pts = []
        for i in range(N + 1):
            a = math.pi * (0.76 - i / N * 0.52)
            n = _hsh(i * 5 + 2)
            if i % 2 == 1:
                ln = (5 + 4 * abs(n)) * tuft
                pts.append((math.cos(a) * (rx + ln * .3), math.sin(a) * (ry * 1.02 + ln)))
            else:
                pts.append((math.cos(a) * rx * .99, math.sin(a) * ry * 1.01))
        pen.poly(H.path(pts), weight=1.95 * sc, alpha=192, rough=1.0, seed=1019)
        n = _hsh(99)                            # one stubborn cowlick
        pen.poly(H.path([(rx * .2, ry * .9), (rx * .34 + n * 4, ry * .9 + 9 * tuft),
                         (rx * .14 + n * 8, ry * .9 + 15 * tuft)]),
                 weight=1.7 * sc, alpha=175, rough=1.2, seed=1030)

    hc = H.raw(0, 0)
    out["head_c"] = hc
    out["head_top"] = (hc[0], hc[1] - (ry + 16) * sc)
    out["head_r"] = rx * sc
    if marks is not None:
        marks.update(out)
    return out


def draw_A(pen, P, marks=None):
    return draw_actor(pen, P, PROP_A, marks)


def draw_B(pen, P, marks=None):
    return draw_actor(pen, P, PROP_B, marks)
