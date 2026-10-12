"""Props and gag effects, all drawn with the same pencil.

Props live in *page space* (screen px) so the story layer can just hand over an
x/y and a size.  FX (dust, speed lines, symbols, impact stars) each know how to
draw themselves at a given life value 0..1 so they can pop, wave and fade like
real animation doodles.
"""

from __future__ import annotations

import math

D = math.radians


def _n(i, k=0):
    """Deterministic -1..1 noise for prop details."""
    x = (i * 2246822519 + k * 3266489917) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 668265263) & 0xFFFFFFFF
    return ((x >> 8) & 0xFFFF) / 32768.0 - 1.0


# --------------------------------------------------------------------------- #
# PROPS
# --------------------------------------------------------------------------- #
def cookie(pen, x, y, r=13.0, bite=0.0, seed=3, alpha=195, crumbs=0.0, sc=1.0):
    """The cookie.  Small, round, covered in chips, worth fighting for."""
    r *= sc
    pts = []
    for i in range(21):
        a = math.pi * 2 * i / 20
        rr = r * (1.0 + 0.07 * _n(i, seed))
        if bite > 0.01 and -1.15 < math.sin(a) < 0.35 and math.cos(a) > 0.45:
            rr *= 1.0 - bite * 0.55 * (1 - abs(math.sin(a) * 1.3))
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr * .95))
    pen.loop(pts, weight=1.9 * sc, alpha=alpha, rough=1.15, seed=seed)
    pen.dots([(x + _n(i, seed + 9) * r * .55, y + _n(i, seed + 21) * r * .5)
              for i in range(5)], r=1.9 * sc, alpha=int(alpha * .85), seed=seed + 2)
    pen.hatch(x - r * .25, y + r * .3, r * .8, r * .55, angle=-40, spacing=3.6 * sc,
              weight=1.0 * sc, alpha=42, seed=seed + 5)
    if crumbs > 0.01:
        for i in range(6):
            pen.dot((x + _n(i, 77) * r * 1.6, y + abs(_n(i, 91)) * r * 1.1 + r * .6),
                    1.3 * sc, int(150 * crumbs))


def pencil_prop(pen, x, y, length=210.0, ang=6.0, sc=1.0, roll=0.0, seed=11):
    """A real pencil lying on the page - the obstacle."""
    L, hh = length * sc, 7.5 * sc
    a = D(ang)
    ca, sa = math.cos(a), math.sin(a)

    def P(u, v):
        # u along the pencil, v across it
        return (x + u * ca - v * sa, y + u * sa + v * ca)

    pts_top = [P(-L / 2 + i * L / 8, -hh * (1 + 0.06 * _n(i, seed)) + roll) for i in range(9)]
    pts_bot = [P(-L / 2 + i * L / 8, hh * (1 + 0.06 * _n(i, seed + 3)) + roll) for i in range(9)]
    pen.poly(pts_top, weight=1.9 * sc, alpha=190, rough=1.0, seed=seed)
    pen.poly(pts_bot, weight=1.9 * sc, alpha=190, rough=1.0, seed=seed + 1)
    # facets + wood grain
    for k in (1, 2):
        pen.poly([P(-L / 2, -hh + 2 * hh * k / 3 + i * 0.4) for i in range(9)],
                 weight=0.9 * sc, alpha=60, rough=.8, seed=seed + k)
    # sharpened end: cone + graphite tip
    tipx = L / 2
    pen.poly([P(tipx, -hh), (x + (tipx + 15 * sc) * ca, y + (tipx + 15 * sc) * sa - hh * .15),
              P(tipx, hh)], weight=1.7 * sc, alpha=185, rough=.9, seed=seed + 6)
    pen.dot(P(tipx + 15 * sc, 0), 2.1 * sc, 205)
    for i in range(4):
        u = tipx - 2 * sc
        pen.line(*P(u, -hh + i * 3.4 * sc), *P(u + 12 * sc, -hh * .25 + i * 2.2 * sc),
                 weight=.9 * sc, alpha=48, rough=.6, seed=seed + 7 + i)
    # eraser end + ferrule
    pen.poly([P(-tipx, -hh), P(-tipx - 5 * sc, -hh * .78), P(-tipx - 5 * sc, hh * .78),
              P(-tipx, hh)], weight=1.6 * sc, alpha=175, rough=.9, seed=seed + 12)
    for k in (-1, 1):
        pen.line(*P(-tipx - 1 * sc, hh * .8 * k), *P(-tipx - 4 * sc, hh * .8 * k),
                 weight=1.5 * sc, alpha=120, rough=.7, seed=seed + 13)
    pen.hatch(*P(-L * .28, 0), L * .18, hh * .75, angle=68, spacing=3.4 * sc,
              weight=.9 * sc, alpha=40, seed=seed + 20)


def eraser(pen, x, y, w=34.0, h=15.0, ang=0.0, sc=1.0, seed=31, label=True):
    w, h = w * sc, h * sc
    a = D(ang)
    ca, sa = math.cos(a), math.sin(a)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    pts = [(x + cx * ca - cy * sa, y + cx * sa + cy * ca) for cx, cy in corners]
    pen.loop(pts, weight=1.8 * sc, alpha=180, rough=1.25, seed=seed)
    o = [(x + (cx * ca - (cy - h * .42) * sa), y + (cx * sa + (cy - h * .42) * ca))
         for cx, cy in [(-w / 2, h / 2), (w / 2, h / 2)]]
    pen.line(o[0][0], o[0][1], o[1][0], o[1][1], weight=1.2 * sc, alpha=110, rough=1.0,
             seed=seed + 1)
    if label:
        for i in range(4):
            u = -w * .22 + i * w * .14
            pen.line(*(x + u * ca - (-h * .18) * sa, y + u * sa + (-h * .18) * ca),
                     *(x + (u + w * .07) * ca - (-h * .18) * sa,
                       y + (u + w * .07) * sa + (-h * .18) * ca),
                     weight=1.3 * sc, alpha=95, rough=.5, seed=seed + 5 + i)
    pen.hatch(x + w * .12, y + h * .28, w * .5, h * .3, angle=-18, spacing=3.4 * sc,
              weight=.9 * sc, alpha=38, seed=seed + 9)


def dust_cloud(pen, x, y, r, life=1.0, sc=1.0, seed=0, puffs=5):
    """A puff of pencil dust: loops that grow and evaporate."""
    r *= sc * (0.55 + 0.85 * life)
    a = 1 - life
    alpha = int(150 * (1 - life * 0.92))
    for i in range(puffs):
        ang = D(360 * i / puffs + _n(i, seed) * 30 + life * 40)
        d = r * (0.5 + 0.7 * life)
        cx, cy = x + math.cos(ang) * d, y + math.sin(ang) * d * .68
        rr = r * (0.42 + 0.2 * abs(_n(i, seed + 3)))
        n = 14
        pts = [(cx + math.cos(math.pi * 2 * k / n) * rr * (1 + .16 * _n(k, seed + i)),
                cy + math.sin(math.pi * 2 * k / n) * rr * .8 * (1 + .16 * _n(k, seed + i + 2)))
               for k in range(n + 1)]
        pen.stroke(pts, closed=True, weight=1.6 * sc, alpha=alpha, rough=1.5, seed=seed + i)
    if life < .5:
        for i in range(4):
            pen.dot((x + _n(i, seed + 11) * r * 1.3, y + _n(i, seed + 13) * r * .8),
                    1.2 * sc, int(120 * (1 - life * 2)))


def speed_lines(pen, x, y, ln=42.0, n=4, ang=180.0, sc=1.0, life=1.0, seed=0,
                curve=6.0, weight=1.5):
    a = D(ang)
    for i in range(n):
        off = (i - (n - 1) / 2) * 9.0 * sc
        L = ln * sc * (0.5 + 0.5 * abs(_n(i, seed))) * (1.2 - life * 0.5)
        ca, sa = math.cos(a), math.sin(a)
        px, py = -sa, ca
        o = off + _n(i, seed + 5) * 3
        p0 = (x + px * o, y + py * o)
        p1 = (p0[0] + ca * L, p0[1] + sa * L)
        pm = (p0[0] * .5 + p1[0] * .5 + px * curve * sc * _n(i, seed + 9),
              p0[1] * .5 + p1[1] * .5 + py * curve * sc * _n(i, seed + 9))
        pen.poly([p0, pm, p1], weight=weight * sc, alpha=int(150 * (1 - life)),
                 rough=1.0, seed=seed + i, taper=0.7)


def impact_star(pen, x, y, r, life=0.0, sc=1.0, seed=0, spikes=11):
    r *= sc * (0.5 + life * 0.9)
    pts = []
    for i in range(spikes * 2):
        a = math.pi * i / spikes
        rr = r * (1.0 if i % 2 == 0 else 0.42 + 0.18 * _n(i, seed))
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr * (0.9 + 0.1 * _n(i, seed + 2))))
    alpha = int(215 * (1 - life))
    pen.loop(pts, weight=2.4 * sc * (1 - life * .4), alpha=alpha, rough=1.3, seed=seed)
    for i in range(spikes):
        a = math.pi * 2 * i / spikes + D(12)
        r0, r1 = r * 1.25, r * (1.7 + 0.5 * _n(i, seed + 7))
        pen.line(x + math.cos(a) * r0, y + math.sin(a) * r0,
                 x + math.cos(a) * r1, y + math.sin(a) * r1,
                 weight=1.5 * sc, alpha=int(alpha * .8), rough=1.0, seed=seed + 20 + i,
                 taper=0.6)


def symbol(pen, kind, x, y, s=34.0, life=0.0, sc=1.0, seed=0, tilt=0.0):
    """Doodle punctuation: ?, !, anger-pop, notes, zzz, sweat, stars."""
    s *= sc
    a = 1.0 - life
    al = int(200 * min(1.0, a * 1.6))
    y += -18 * life
    if kind == "?":
        # hook over the top, then the stem: drawn the way a pencil does it
        pen.arc(x, y - s * .26, s * .30, s * .34, 168, 372, weight=2.8 * sc, alpha=al,
                rough=1.0, seed=seed + 1)
        pen.poly([(x + s * .30, y - s * .22), (x + s * .10, y + s * .02),
                  (x + s * .04, y + s * .16)], weight=2.7 * sc, alpha=al, rough=.9,
                 seed=seed + 2)
        pen.dot((x + s * .04, y + s * .38), s * .075, al)
    elif kind == "!":
        pen.line(x, y - s * .55, x + s * .03, y - s * .05, weight=3.0 * sc, alpha=al,
                 rough=.9, seed=seed + 3)
        pen.dot((x + s * .03, y + s * .30), s * .085, al)
        for i in range(5):
            aa = D(-90 + i * 45)
            pen.line(x + math.cos(aa) * s * .75, y + math.sin(aa) * s * .75,
                     x + math.cos(aa) * s * 1.05, y + math.sin(aa) * s * 1.05,
                     weight=1.4 * sc, alpha=int(al * .8), rough=.8, seed=seed + 30 + i,
                     taper=.5)
    elif kind == "anger":
        # the classic crossed-vein pop
        for k in range(4):
            aa = D(45 + k * 90)
            r0, r1 = s * .10, s * .42
            pts = [(x + math.cos(aa) * r0, y + math.sin(aa) * r0),
                   (x + math.cos(aa) * r1 * .7, y + math.sin(aa) * r1 * .7),
                   (x + math.cos(aa + D(22)) * r1, y + math.sin(aa + D(22)) * r1)]
            pen.poly(pts, weight=2.2 * sc, alpha=al, rough=.8, seed=seed + k)
            pts = [(x + math.cos(aa) * r0, y + math.sin(aa) * r0),
                   (x + math.cos(aa) * r1 * .7, y + math.sin(aa) * r1 * .7),
                   (x + math.cos(aa - D(22)) * r1, y + math.sin(aa - D(22)) * r1)]
            pen.poly(pts, weight=2.2 * sc, alpha=al, rough=.8, seed=seed + 8 + k)
    elif kind == "note":
        pen.ellipse(x, y, s * .17, s * .13, rot=-20, weight=1.9 * sc, alpha=al, rough=.9,
                    seed=seed + 1)
        pen.line(x + s * .15, y + s * .04, x + s * .16, y - s * .48, weight=1.8 * sc,
                 alpha=al, rough=.9, seed=seed + 2)
        pen.poly([(x + s * .16, y - s * .48), (x + s * .34, y - s * .40),
                  (x + s * .30, y - s * .22)], weight=1.6 * sc, alpha=al, rough=.9,
                 seed=seed + 3)
    elif kind == "steam":
        for i in range(2):
            off = (i - .5) * s * .5
            pts = []
            for k in range(9):
                u = k / 8
                pts.append((x + off + math.sin(u * 6 + i) * s * .22, y - u * s * 1.35))
            pen.poly(pts, weight=1.7 * sc, alpha=int(al * .8), rough=1.2, seed=seed + i)
    elif kind == "tear":
        for i, sgn in enumerate((-1, 1)):
            x0 = x + sgn * s * .34
            pts = [(x0, y + s * .05), (x0 + sgn * s * .3, y + s * .5),
                   (x0 + sgn * s * .1, y + s * .95)]
            pen.poly(pts, weight=1.8 * sc, alpha=al, rough=1.0, seed=seed + i)
            pen.arc(x0, y + s * .05, s * .12, s * .1, 200, 340, weight=1.4 * sc,
                    alpha=int(al * .7), rough=.7, seed=seed + 5 + i)
    elif kind == "swallow":
        pen.arc(x, y, s * .5, s * .5, 20, 340, weight=1.6 * sc, alpha=int(al * .6),
                rough=1.4, seed=seed)
    elif kind == "bird":
        for i in range(3):
            aa = D(-140 + i * 40 + life * 900)
            bx, by = x + math.cos(aa) * s * 1.15, y + math.sin(aa) * s * .55
            f = math.sin(life * 40 + i) * s * .22
            pen.poly([(bx - s * .22, by), (bx - s * .08, by - f), (bx + s * .06, by),
                      (bx + s * .20, by - f * .9), (bx + s * .34, by + s * .02)],
                     weight=1.6 * sc, alpha=al, rough=.9, seed=seed + i)
    elif kind == "spiral_up":
        pts = []
        for u in [j * .5 for j in range(22)]:
            rr = s * .1 + s * .07 * u
            pts.append((x + math.cos(u) * rr, y - u * s * .13 + math.sin(u) * rr * .5))
        pen.poly(pts, weight=1.7 * sc, alpha=al, rough=1.0, seed=seed)
    elif kind == "skid":
        for i in range(2):
            o = (i - .5) * s * .5
            pen.poly([(x - s * .9, y + o), (x - s * .2, y + o * 1.4 + s * .05),
                      (x + s * .6, y + o * .8)], weight=2.2 * sc,
                     alpha=int(150 * (1 - life)), rough=1.3, seed=seed + i)


def motion_arcs(pen, x, y, r, a0, a1, n=3, life=0.0, sc=1.0, seed=0):
    for i in range(n):
        rr = r * (1 + i * 0.16) * sc
        pen.arc(x, y, rr, rr * .96, a0, a1, weight=(1.8 - i * .3) * sc,
                alpha=int((150 - i * 35) * (1 - life)), rough=1.1, seed=seed + i, taper=.4)


def hand_shadow(pen, x, y, rx, ry, sc=1.0, seed=0, alpha=40):
    pen.smudge(x, y, rx * sc, ry * sc, alpha=alpha, seed=seed)


def sweat(pen, x, y, s=13.0, sc=1.0, life=0.0, seed=0):
    s *= sc
    a = int(190 * (1 - life))
    pts = [(x, y - s * .7), (x + s * .34, y + s * .1), (x, y + s * .42),
           (x - s * .34, y + s * .1)]
    pen.loop(pts, weight=1.6 * sc, alpha=a, rough=.9, seed=seed)
    pen.arc(x - s * .1, y - s * .05, s * .18, s * .22, 120, 240, weight=1.1 * sc,
            alpha=int(a * .6), rough=.6, seed=seed + 1)


def crumbs(pen, x, y, sc=1.0, amt=1.0, seed=55, spread=16.0, mouth=False):
    """Cookie crumbs: where the evidence lands."""
    if amt <= 0.01:
        return
    for i in range(9):
        rr = 1.0 + abs(_n(i, seed)) * 1.5
        pen.dot((x + _n(i, seed + 1) * spread * sc, y + abs(_n(i, seed + 2)) * spread * .8 * sc),
                rr * sc, int(175 * amt))
    if mouth:  # a smear around the mouth: the giveaway
        pen.arc(x, y, spread * .9 * sc, spread * .62 * sc, 30, 320, weight=1.4 * sc,
                alpha=int(110 * amt), rough=1.6, seed=seed + 7)


def shock_lines(pen, x, y, r, life=0.0, sc=1.0, n=9, seed=0, a0=-160, a1=-20):
    """The little radiating dashes that appear when a drawing realises something."""
    r *= sc
    al = int(190 * (1 - life))
    for i in range(n):
        a = D(a0 + (a1 - a0) * i / max(1, n - 1))
        r0 = r * (1.05 + 0.12 * _n(i, seed))
        r1 = r * (1.55 + 0.45 * abs(_n(i, seed + 3))) * (1.0 - life * 0.3)
        pen.line(x + math.cos(a) * r0, y + math.sin(a) * r0,
                 x + math.cos(a) * r1, y + math.sin(a) * r1,
                 weight=1.8 * sc, alpha=al, rough=0.9, seed=seed + i, taper=0.55)


def hand_flag(pen, x, y, sc=1.0, life=0.0, seed=0, r=26.0):
    """Two clasped hands + a little shake mark, for the peace handshake."""
    r *= sc
    al = int(190 * (1 - life))
    pen.circle(x - r * .42, y, r * .5, weight=1.9 * sc, alpha=al, rough=1.1, seed=seed)
    pen.circle(x + r * .42, y, r * .5, weight=1.9 * sc, alpha=al, rough=1.1, seed=seed + 1)
    pen.line(x - r * .18, y - r * .1, x + r * .18, y - r * .12, weight=1.6 * sc,
             alpha=al, rough=1.0, seed=seed + 2)
    for i in range(2):
        yy = y - r * (.8 + i * .3)
        pen.arc(x, yy, r * .5, r * .22, 200, 340, weight=1.2 * sc,
                alpha=int(al * (.5 - i * .18)), rough=1.2, seed=seed + 5 + i)


def page_mark(pen, x, y, sc=1.0, seed=0, r=9.0, alpha=60):
    """Registration tick used by the freeze-frame."""
    for i in range(4):
        a = D(90 * i + 45)
        pen.line(x + math.cos(a) * r * sc, y + math.sin(a) * r * sc,
                 x + math.cos(a) * r * 2.1 * sc, y + math.sin(a) * r * 2.1 * sc,
                 weight=1.4 * sc, alpha=alpha, rough=0.7, seed=seed + i)
