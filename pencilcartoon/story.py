"""The picture: 30 seconds of pencil kids, keyed in real seconds.

One continuous shot, no cuts.  The sheet is the whole world, so every transition
is motivated by a character walking, running or flying somewhere.

    0-5   the cookie heist              15-20  the fake-cry swindle
    5-10  crumbs, and the chase starts  20-25  the slide, the crash, the spin
    10-15 leap over the pencil          25-30  peace offering -- and the betrayal
    15-20 eraser pile
"""

from __future__ import annotations

import math

from .film import depth_scale
from .rig import BASE, body_inv, body_pt, pose, remix
from .timing import clamp, clamp01, cycle, damped, ease, kf, lerp, pulse, tr, wave, jitter

# ---------------------------------------------------------------- stage
W, H = 1080, 1920
GROUND = 1500.0           # the drawn "ground line" of the page
SC = 2.28                 # actor scale on the page
FREEZE_T = 29.62          # the film locks onto this drawing and stops
PENCIL = (528.0, 1508.0)
PILE = (900.0, 1584.0)
ASY = GROUND - 372 * SC   # the doodle zone above A's head (he is the tall one)
BSY = GROUND - 252 * SC   # ...and above B's

SEATS = dict(A0=700.0, B0=430.0)


def _p(**kw) -> dict:
    p = dict(BASE)
    p.update(kw)
    return p


# ------------------------------------------------------------------- props
def _eraser_pile(t: float, scatter: float = 0.0):
    """The doodled erasers.  `scatter` 0..1 throws them into the air."""
    out = []
    for i, (dx, dy, ang, w) in enumerate([(-46, 8, -12, 40), (-6, 16, 9, 46),
                                          (34, 6, -5, 38), (-22, -14, 4, 34),
                                          (16, -18, -16, 30), (52, -12, 12, 36)]):
        s = clamp01(scatter - i * 0.05)
        if s > 0.001:                                  # fly out, then settle
            u = s
            arc = math.sin(u * math.pi)
            dx2 = dx + math.cos(i * 1.9 + 0.6) * 150 * ease(min(1.0, u * 1.35), "out")
            dy2 = dy - arc * (58 + 26 * abs(math.sin(i * 2.3)))
            ang = ang + u * (240 + 120 * i % 360) * (1 if i % 2 else -1)
        else:
            dx2 = dx + math.sin(t * 0.9 + i) * 0.7
            dy2 = dy + wave(t, 0.6, 0.5, i * .3)
        out.append(dict(draw="eraser", x=PILE[0] + dx2, y=PILE[1] + dy2, w=w, h=w * .42,
                        ang=ang, sc=SC * .92, seed=40 + i))
    return out


def _trail(t, x, y, rate=7.0, n=3, seed=0, scale=1.0, life_off=0.0):
    """Recurring dust puffs behind a runner."""
    fx = []
    for k in range(n):
        ph = (t * rate + k / n + life_off) % 1.0
        if ph < 0.02:
            continue
        fx.append(dict(draw="dust", x=x + (k - n / 2) * 11 - 10, y=y - 2 + ph * 14,
                       r=(36 + 15 * abs(math.sin(k * 2.1))) * scale, life=ph, sc=1.0,
                       seed=seed + k * 7, puffs=4))
    return fx


def _look_at(P, sx, sy, gain=1.0):
    """Pupils track a world point."""
    dx = sx - P["x"]
    dy = sy - (P["y"] - 250 * P["scale"])
    return clamp(dx / 240.0 * gain, -1, 1), clamp(-dy / 240.0 * gain, -1, 1)



# ---------------------------------------------------------------- running
# One clock drives every sprint in the film, so the beats hand the characters to
# each other at the exact same x instead of teleporting (no cuts, remember).
LOOP = dict(t0=6.35, per=2.10, cx=528.0, amp=326.0)


def loop_path(t, lead=0.0, lane=0, clock=None):
    """(x, dir, y, speed) along the big oval they tear around.

    `lane` 0 is A's outer track, 1 is B's inner one: slightly narrower, slightly
    lower on the page, so the two of them stay legible while one chases the other.
    """
    c = clock or LOOP
    a = 2 * math.pi * ((t - c["t0"]) / c["per"] + lead)
    amp, yoff = (c["amp"], 0.0) if lane == 0 else (c["amp"] * 0.86, 58.0)
    x = c["cx"] + amp * math.sin(a)
    v = math.cos(a)
    y = GROUND + yoff + 14 - 76 * abs(v)
    return x, (1 if v > 0 else -1), y, abs(v)


def blend_path(t, x_from, y_from, t0, dur, fn, lead=0.0):
    """Ease from a held position onto the running path over `dur` seconds."""
    xt, dt, yt, sp = fn(t, lead)
    u = ease(tr(t, t0, t0 + dur), "out") if t < t0 + dur else 1.0
    return (lerp(x_from, xt, u), dt, lerp(y_from, yt, u), sp)


# =================================================================== beats
def build(t: float) -> dict:
    """Return the full frame description at time t (seconds)."""
    t = min(t, FREEZE_T)
    fx: list = []
    props: list = []
    bgprops: list = []
    heavy = 1.0

    # ---- persistent world props (always on the page) ---------------------
    roll = 0.0
    if 10.5 < t < 12.6:                                 # it gets kicked
        roll = pulse(t, 10.95, 12.4) * 6.0
    bgprops.append(dict(draw="pencil", x=PENCIL[0], y=PENCIL[1] + roll * 0.6,
                       length=172.0, ang=7.5 + roll * 1.1, sc=SC, roll=roll, seed=11))
    scatter = 0.0
    if 11.4 < t < 15.0:
        scatter = clamp01((t - 11.42) / 0.42) * (1 - clamp01((t - 13.4) / 1.1))
    bgprops += _eraser_pile(t, scatter)

    # =================================================================== 1
    if t < 5.0:
        A, B, cookie_state, f1 = beat1(t)
        fx += f1
    # =================================================================== 2
    elif t < 10.0:
        A, B, cookie_state, f2 = beat2(t)
        fx += f2
    # =================================================================== 3
    elif t < 15.0:
        A, B, cookie_state, f3 = beat3(t)
        fx += f3
    # =================================================================== 4
    elif t < 20.0:
        A, B, cookie_state, f4 = beat4(t)
        fx += f4
    # =================================================================== 5
    elif t < 25.0:
        A, B, cookie_state, f5 = beat5(t)
        fx += f5
    # =================================================================== 6
    else:
        A, B, cookie_state, f6, heavy = beat6(t)
        fx += f6

    # ---- cookie: attached to a hand, or flying between two hands ---------
    if cookie_state:
        props.append(cookie_state)

    actors = []
    if A is not None:
        actors.append(dict(kind="A", pose=A))
    if B is not None:
        actors.append(dict(kind="B", pose=B))
    return dict(actors=actors, props=props, fx=fx, bgprops=bgprops, heavy=heavy)


# ---------------------------------------------------------------- beat one
def beat1(t: float):
    fx: list = []
    # ---- B: sits, happily eating
    chew = wave(t, 3.1, 0.5, 0.0) + 0.5
    bite = tr(t, 0.5, 3.5) * 0.62
    b_x = SEATS["B0"] + wave(t, 0.8, 1.2)
    B = _p(x=b_x, y=GROUND + 6, scale=SC, dir=-1, leg_mode="sit", crouch=1.0,
           m="chew", m_open=chew, m_w=1.05, e_style="happy" if t < 1.6 else "normal",
           e_look=0.35, b_raise=0.1, head_tilt=6 + wave(t, 1.6, 2.2),
           sqy=1.0 + 0.012 * wave(t, 3.1, 1), sqx=1.0 - 0.012 * wave(t, 3.1, 1),
           hand_r=(33, 133 + 5 * wave(t, 3.1, 1, .3)), elbow_r=-.62,
           breathe=wave(t, 1.1, 0.4))
    B["e_open"] = 0.25 if (t % 3.7) < 0.11 else 1.0
    if t > 3.55:                                        # hand closes on thin air
        B["m"] = "flat"
        B["hand_r"] = (30, 133)
    if t > 3.95:                                        # notice, then turn around
        turn = tr(t, 3.98, 4.36, )
        B["dir"] = -1
        if turn > 0.02:
            B["dir"] = -1 if turn < 0.5 else 1
            B["sqx"] = 1.0 - 0.45 * math.sin(turn * math.pi)
            B["sqy"] = 1.0 + 0.14 * math.sin(turn * math.pi)
            B["rot"] = 14 * math.sin(turn * math.pi)
        B["x"] = b_x + 6 * turn
        B["crouch"] = 1.0 - 0.55 * tr(t, 4.25, 4.8, )
        B["m"] = "flat" if turn < 0.7 else "o"
        B["m_open"] = 0.35 * tr(t, 4.3, 4.6)
        B["e_style"] = "normal"
        B["e_look"] = 0.5 * turn
        B["b_raise"] = 0.8 * tr(t, 4.3, 4.7)
        fx.append(dict(draw="symbol", kind="?", x=b_x + 6, y=BSY,
                       s=58, life=1 - pulse(t, 4.4, 5.3, shape="pop"), sc=SC, seed=7))
        if t > 4.5:
            for i in range(3):
                ph = (t * 1.6 + i / 3) % 1.0
                fx.append(dict(draw="arcs", x=b_x - 12, y=BSY - 60,
                               r=16 + ph * 12, a0=200, a1=340, n=2, life=ph, sc=SC,
                               seed=13 + i))

    # ---- A: watches, sneaks, steals, sits back down, whistles
    u_sit_stand = tr(t, 1.75, 2.05)
    u_sneak = tr(t, 2.0, 3.30)
    u_snatch = tr(t, 3.30, 3.62)
    u_back = tr(t, 3.62, 4.15)
    a_x = lerp(SEATS["A0"], 500.0, ease(u_sneak, "inout")) - 0 * u_back
    a_x = lerp(a_x, SEATS["A0"], ease(u_back, "out"))
    a_y = GROUND + 6 - 46 * math.sin(u_sneak * math.pi) + 26 * u_snatch
    a_y = lerp(a_y, GROUND + 6, u_back)
    ph = t * 1.9
    A = _p(x=a_x, y=a_y, scale=depth_scale(a_y, SC), dir=-1, crouch=1.0 - u_sit_stand,
           leg_mode="sit" if u_sit_stand < 0.5 else "stand",
           lean=lerp(-3, 21, math.sin(u_sneak * math.pi)),
           head_tilt=lerp(-4, -16, math.sin(u_sneak * math.pi)),
           e_look=0.7, e_looky=0.4 * math.sin(u_sneak * math.pi),
           b_ang=1.0, m="grin", m_w=1.05,
           sqx=1.0 + 0.05 * math.sin(u_sit_stand * math.pi),
           sqy=1.0 - 0.05 * math.sin(u_sit_stand * math.pi))
    if 0.5 < u_sneak < 0.95:                            # tiptoe: high knees, slow
        for i, sgn in enumerate((-1, 1)):
            p = (ph + (0.5 if i else 0.0)) % 1.0
            A["foot_r" if sgn > 0 else "foot_l"] = (22 + 20 * math.cos(2 * math.pi * p),
                                                   max(0.0, math.sin(2 * math.pi * p)) * 30)
        A["arm_swing"] = 0.8
        A["hand_r"] = (44, 150 + 8 * wave(t, 1.9, 1))
        A["hand_l"] = (-30, 168 + 6 * wave(t, 1.9, 1, .5))
        A["e_open"] = 0.55
    else:
        A["hand_r"] = (-6, 118)
        A["hand_l"] = (18, 116)
    if u_snatch > 0.001 and u_back < 0.99:              # the grab
        s = ease(min(1.0, u_snatch * 1.5), "out")
        A["hand_r"] = (lerp(40, 4, s), lerp(150, 132, s))
        A["elbow_r"] = -.62
        A["lean"] = 30
        A["hair"] = 0.4 * math.sin(u_snatch * math.pi)
        if u_snatch > 0.55:
            A["hand_r"] = (-34, 150)                     # tuck it behind the back
            A["elbow_r"] = .62
    if t > 4.3:                                          # innocent whistling
        A["m"] = "whistle"
        A["m_open"] = 0.4
        A["e_style"] = "closed"
        A["crouch"] = 0.62
        A["leg_mode"] = "sit"
        A["head_tilt"] = -12 - 3 * wave(t, 1.4, 1)
        A["dir"] = 1
        A["lean"] = -6
        A["hand_l"] = (-34, 120)
        A["hand_r"] = (-30, 138)
        A["elbow_r"] = .62
        A["e_look"] = 0.0
        for i in range(3):
            ph2 = (t * 0.85 + i / 3) % 1.0
            fx.append(dict(draw="symbol", kind="note", x=A["x"] + 58 + ph2 * 46,
                           y=ASY - ph2 * 70 + 8 * math.sin(ph2 * 7 + i),
                           s=26 + 5 * math.sin(ph2 * 6), life=ph2 * 0.98, sc=SC,
                           seed=21 + i))
    cookie = dict(draw="cookie", r=11.5, bite=bite, sc=SC, seed=3, crumbs=0.0)
    if t < 3.45:
        cookie["attach"] = ("B", "hand_r", 16, 4)
    elif t < 3.75:
        p0 = body_pt(B, 30, 146)
        p1 = body_pt(remix(A, hand_r=(40, 150)), 40, 150)
        s = ease(tr(t, 3.45, 3.72), "inout")
        cookie.update(x=lerp(p0[0] + 16, p1[0] - 30, s), y=lerp(p0[1] + 2, p1[1] - 4, s))
    else:
        cookie["attach"] = ("A", "hand_r", -6, 8)
    return A, B, cookie, fx


# ---------------------------------------------------------------- beat two
def beat2(t: float):
    fx: list = []
    # 5.0-6.3 discovery; 6.3-10.0 chase around the page
    A_x0, B_x0 = SEATS["A0"], SEATS["B0"]
    u = tr(t, 5.0, 6.3)
    A = _p(x=A_x0, y=GROUND + 6, scale=SC, dir=1, crouch=0.55, leg_mode="sit",
           m="tongue", e_style="normal", e_look=-0.8, b_ang=1.2, lean=-6,
           head_tilt=-8, hand_l=(-34, 122), hand_r=(-30, 140), elbow_r=.62,
           sqx=1 + 0.02 * wave(t, 5.5, 1, .2))
    B = _p(x=B_x0 + 10, y=GROUND + 6, scale=SC, dir=1, crouch=1.0 - 0.4 * tr(t, 5.9, 6.3),
           leg_mode="sit", m="flat", e_style="normal", e_look=-0.5,
           b_ang=0.0, head_tilt=2, breathe=wave(t, 1.2, 0.3))

    # crumbs on A's face -> fury
    crumb_amt = clamp01((t - 5.35) / 0.3)
    if t > 5.5:
        A["hand_r"] = (-30, 140)
    B["e_style"] = "wide" if t > 5.62 else "normal"
    B["b_ang"] = 1.5 * clamp01((t - 5.6) / 0.4)
    B["m"] = "flat" if t < 5.9 else "bite"
    B["m_open"] = 0.5 * clamp01((t - 5.7) / 0.5)
    if 5.6 < t < 6.5:
        sh = (1 - (t - 5.6) / 0.9)
        B["x"] += jitter(t, 22, 2.4 * sh)
        B["sqx"] = 1 + 0.03 * sh * wave(t, 26, 1)
        B["sqy"] = 1 - 0.03 * sh * wave(t, 26, 1)
        fx.append(dict(draw="symbol", kind="anger", x=B["x"] + 44 * B["dir"],
                       y=GROUND - 250 * SC, s=26, life=1 - pulse(t, 5.62, 6.35, shape="pop"),
                       sc=SC, seed=44))
        fx.append(dict(draw="symbol", kind="steam", x=B["x"] - 44, y=BSY + 42,
                       s=22, life=1 - pulse(t, 5.8, 6.6, shape="pop"), sc=SC, seed=45))
    if t > 5.5:
        fx.append(dict(draw="crumbs", attach=("A", "head_c", 10, 22), amt=crumb_amt,
                       sc=SC, spread=6.5, mouth=True, seed=48))
    if 5.5 < t < 6.4:
        fx.append(dict(draw="symbol", kind="!", x=A["x"] - 96, y=ASY + 20, s=44,
                       life=1 - pulse(t, 5.55, 6.3, shape="pop"), sc=SC, seed=47))
    if t > 6.0:                                          # A: cheeky -> ready
        A["m"] = "tongue"
        A["crouch"] = 0.55 + 0.45 * tr(t, 6.05, 6.30)
        A["lean"] = lerp(-6, 26, tr(t, 6.05, 6.3))
        A["sqx"] = 1 + 0.16 * tr(t, 6.05, 6.3)
        A["sqy"] = 1 - 0.14 * tr(t, 6.05, 6.3)
    if t < 6.35:
        return A, B, dict(draw="cookie", attach=("A", "hand_r", -6, 8), r=11.5, bite=0.62,
                          sc=SC, seed=3, crumbs=crumb_amt), fx

    # ---------------- the chase: rounds and rounds of the page
    def fn(t, lead=0.0, lane=0):
        return loop_path(t, lead, lane)
    ax, adir, ay, asp = fn(t, 0.0, 0)
    bx, bdir, by, bsp = fn(t, -0.33, 1)
    ax = max(150.0, min(W - 150.0, ax))
    bx = max(120.0, min(W - 120.0, bx))
    T0 = 6.35
    runf = t * 7.4
    A = _p(x=ax, y=ay, scale=depth_scale(ay, SC), dir=adir,
           leg_mode="spin", gait_phase=runf, arm_swing=1.2, lean=26 * adir * adir,
           head_tilt=-6, m="laugh", m_open=.7 + .3 * wave(t, 9, 1), e_style="happy",
           hand_l=(-24, 176), hand_r=(52, 250), elbow_r=-.8, crouch=.18,
           sqy=1 + .05 * wave(t, 7.4, 1), sqx=1 - .04 * wave(t, 7.4, 1), hair=.5)
    B = _p(x=bx, y=by, scale=depth_scale(by, SC), dir=bdir, leg_mode="spin",
           gait_phase=runf + .4, arm_swing=1.4, lean=20, m="bite", m_open=1.0,
           e_style="squint", e_look=-.6, b_ang=1.6, crouch=.12,
           sqy=1 + .04 * wave(t, 7.4, 1, .4), hair=.35)
    for P in (A, B):
        rear = -P["dir"]
        fx += _trail(t, P["x"] + rear * 46 * SC, P["y"] + 2, rate=9.0, n=3,
                     seed=int(P["y"]) + 3, scale=1.0)
        fx.append(dict(draw="speed", x=P["x"] + rear * 52 * SC, y=P["y"] - 160 * SC,
                       ln=54, n=4, ang=180 if rear < 0 else 0, sc=1.0, life=(t * 3) % 1,
                       seed=int(P["y"]), curve=8))
    if t < 6.95:
        fx.append(dict(draw="dust", x=A["x"] - A["dir"] * 40, y=GROUND + 6, r=104,
                       life=tr(t, 6.3, 6.95), sc=1.0, seed=91))
        fx.append(dict(draw="dust", x=B["x"] - B["dir"] * 34, y=GROUND + 6, r=78,
                       life=tr(t, 6.5, 7.1), sc=1.0, seed=92))
    cookie = dict(draw="cookie", attach=("A", "hand_r", 10, -6), r=12.0, bite=.62, sc=SC,
                  seed=3, crumbs=crumb_amt)
    return A, B, cookie, fx


# ---------------------------------------------------------------- beat three
def beat3(t: float):
    """Same chase clock as beat 2, so nothing teleports: A clears the pencil at
    10.45 s, B eats it 0.39 s later and is thrown into the eraser pile."""
    fx: list = []
    px = PENCIL[0]
    T_LEAP, T_LAND = 10.45, 11.16
    T_TRIP = 11.12
    ax, adir, ay, _ = loop_path(t, 0.0, 0)
    bx, bdir, by, _ = loop_path(t, -0.33, 1)

    # ---------------- A: run, leap, roll with the laugh
    if t < T_LEAP:
        A = _p(x=ax, y=ay, scale=depth_scale(ay, SC), dir=adir, leg_mode="spin",
               gait_phase=t * 7.4, arm_swing=1.2, lean=26, m="laugh", m_open=.8,
               e_style="happy", hand_l=(-30, 150), hand_r=(48, 190), elbow_r=-.62,
               crouch=.18, hair=.5, sqy=1 + .05 * wave(t, 7.4, 1))
    elif t < T_LAND:
        u = tr(t, T_LEAP, T_LAND)
        A = _p(x=lerp(px - 96.0, px + 120.0, u),
               y=ay - 262 * math.sin(math.pi * u), scale=depth_scale(ay, SC), dir=1,
               leg_mode="tuck", foot_l=(-8, 46), foot_r=(30, 62), hand_l=(-46, 206),
               hand_r=(54, 214), elbow_l=.62, elbow_r=-.62, lean=lerp(24, -12, u),
               m="laugh", m_open=.85, e_style="happy", hair=.85,
               sqx=1 + .2 * pulse(t, T_LEAP - .14, T_LEAP + .1, shape="pop")
                   - .22 * pulse(t, T_LAND - .12, T_LAND + .1, shape="pop"),
               sqy=1 - .18 * pulse(t, T_LEAP - .14, T_LEAP + .1, shape="pop")
                   + .2 * pulse(t, T_LAND - .12, T_LAND + .12, shape="pop"))
        fx.append(dict(draw="arcs", x=A["x"], y=A["y"] + 40, r=46, a0=210, a1=330, n=2,
                       life=.2, sc=1.0, seed=55))
        if u > .9:
            fx.append(dict(draw="dust", x=A["x"] + 30, y=ay + 8, r=86, life=(u - .9) * 8,
                           sc=1.0, seed=56))
    else:
        u = tr(t, T_LAND, 15.0)
        sh = abs(wave(t, 5.0, 1))
        A = _p(x=px + 120, y=GROUND + 20 * sh * min(1.0, u * 6) * (1 - tr(t, 14.3, 15.0)),
               scale=SC, dir=-1,
               leg_mode="stand", gait_phase=t * 4.0,
               crouch=.40 - .36 * tr(t, 13.6, 14.3), lean=-22 + 7 * sh,
               head_tilt=18 + 6 * sh, m="laugh" if t < 14.1 else "grin",
               m_open=.45 + .55 * sh, e_style="happy" if t < 14.1 else "normal",
               e_look=.4, b_ang=.9, hand_r=(54, 200) if t < 14.1 else (-32, 138),
               elbow_r=-.62 if t < 14.1 else 1.0,
               foot_l=(-24, 2), foot_r=(28, 2), hair=.5)
        if t < 14.1:                                   # pointing at the pile, howling
            A["hand_l"] = body_inv(A, PILE[0] - 120, GROUND - 120 * SC)
            A["elbow_l"] = .62
            for i in range(2):
                fx.append(dict(draw="arcs", x=A["x"] - 40, y=ASY + 46, r=26, a0=200,
                               a1=340, n=2, life=(t * 1.6 + i * .5) % 1, sc=1.0,
                               seed=61 + i))
        else:
            A["hand_l"] = None
        if 13.6 < t < 14.5:                            # he slaps his own knee
            A["hand_l"] = body_inv(A, A["x"] - 70, GROUND - 96 * SC)
            A["elbow_l"] = .62

    # ---------------- B: the pencil, the cartwheel, the eraser bath
    if t < T_TRIP:
        B = _p(x=bx, y=by, scale=depth_scale(by, SC), dir=bdir, leg_mode="spin",
               gait_phase=t * 7.4 + .4, arm_swing=1.4, lean=22, m="bite", m_open=1.,
               e_style="squint", e_look=-.5, b_ang=1.7, crouch=.12, hair=.35)
        if t > 10.72:            # he sees it too late: eyes pop, arms fly up
            B["e_style"] = "wide"
            B["b_raise"] = tr(t, 10.72, T_TRIP)
            B["m"] = "o"
            B["m_open"] = tr(t, 10.72, T_TRIP)
    elif t < 11.72:
        u = tr(t, T_TRIP, 11.72)
        B = _p(x=lerp(px - 60.0, px + 130.0, ease(u, "lin")),
               y=by - 186 * math.sin(math.pi * clamp01(u * 1.05)), scale=SC, dir=1,
               leg_mode="tuck", rot=lerp(0, -420, ease(u, "in")),
               foot_l=(6, 44), foot_r=(36, 60), hand_l=(-56, 196), hand_r=(54, 220),
               elbow_l=.62, elbow_r=-.62, lean=lerp(16, -36, u), m="o", m_open=1.0,
               e_style="wide", b_raise=1.0, sqx=1 + .13 * math.sin(u * math.pi),
               sqy=1 - .11 * math.sin(u * math.pi), hair=.6 + u, crouch=.05)
        fx.append(dict(draw="symbol", kind="!", x=B["x"] + 90, y=B["y"] - 340, s=48,
                       life=1 - pulse(t, T_TRIP, 11.85, shape="pop"), sc=1.0, seed=51))
        for i in range(3):
            fx.append(dict(draw="arcs", x=B["x"], y=B["y"] - 110, r=54 + i * 28,
                           a0=140 + i * 28, a1=330 + i * 20, n=1, life=(u + i * .1) % 1,
                           sc=1.0, seed=52 + i))
    else:
        fly = tr(t, 11.72, 12.10)
        bx2 = lerp(px + 130.0, PILE[0] - 30.0, ease(fly, "out"))
        by2 = lerp(GROUND - 120, GROUND + 62, ease(fly, "in"))
        if fly >= 1:
            bx2, by2 = PILE[0] - 30.0, GROUND + 62
        sit = tr(t, 12.10, 12.5)
        stand = tr(t, 14.3, 14.9)
        B = _p(x=bx2 - 30 * stand, y=by2, scale=SC, dir=1,
               leg_mode="sit" if stand < .3 else "stand",
               rot=lerp(-420, -352, ease(sit, "out")) if sit < 1 else 0,
               foot_l=(18, 6) if stand < .3 else None,
               foot_r=(38, 2) if stand < .3 else None, crouch=.75 - .75 * stand,
               lean=lerp(-18, 4, sit) + 6 * stand, m="o", m_open=.55,
               e_style="spiral" if t < 13.1 else "normal",
               e_look=-.7 * tr(t, 12.9, 13.7), arm_swing=.5 * sit,
               sqx=1 + .24 * pulse(t, 12.06, 12.5, shape="pop"),
               sqy=1 - .22 * pulse(t, 12.06, 12.5, shape="pop"),
               head_tilt=damped(t, 12.12, 3.2, 2.1, 9), hair=.5 * (1 - sit))
        if t > 13.1:                            # he spits out rubber and starts to boil
            B["m"] = "flat"
            B["b_ang"] = 1.6 * tr(t, 13.4, 14.2)
            B["hand_r"] = body_inv(B, B["x"] - 44, B["y"] - 148 * SC)
            B["elbow_r"] = -.62
            if 13.6 < t < 15.0:
                for i in range(2):
                    fx.append(dict(draw="symbol", kind="anger", x=B["x"] + 66 + i * 30,
                                   y=BSY + 40 - i * 26, s=32,
                                   life=1 - pulse(t, 13.6 + i * .8, 14.6 + i * .8, shape="pop"),
                                   sc=1.0, seed=57 + i))
        fx.append(dict(draw="dust", x=PILE[0], y=GROUND + 30, r=132,
                       life=clamp01(tr(t, 12.06, 13.3)), sc=1.0, seed=58, puffs=7))
    if 11.0 < t < 11.9:                         # the pencil gets kicked about
        fx.append(dict(draw="arcs", x=px, y=PENCIL[1] - 10, r=42, a0=-40, a1=215, n=2,
                       life=.15, sc=1.0, seed=59))
    cookie = None
    if t > T_LEAP - .3:
        cookie = dict(draw="cookie", attach=("A", "hand_r", 8, 4), r=11.5, bite=.62,
                      sc=SC, seed=3)
    return A, B, cookie, fx


# ---------------------------------------------------------------- beat four
def beat4(t: float):
    fx: list = []
    ax, bx = 648.0, PILE[0] - 56.0
    A = _p(x=ax, y=GROUND, scale=SC, dir=-1, leg_mode="stand", crouch=0.15,
           lean=-16, head_tilt=14, m="grin", m_open=0.3, e_style="normal", e_look=-0.5,
           b_ang=0.8, hand_l=None, hand_r=(-30, 140), elbow_r=.62, arm_swing=0.0,
           sqy=1 + 0.03 * wave(t, 6.5, 1), sqx=1 - 0.03 * wave(t, 6.5, 1))
    B = _p(x=bx, y=GROUND + 62, scale=SC, dir=1, leg_mode="sit", crouch=0.8,
           lean=6, m="flat", m_open=0.2, e_style="normal", e_look=-0.4, b_ang=1.2,
           head_tilt=-6, arm_swing=0.0, sqy=1, hair=0.2)
    cookie = dict(draw="cookie", attach=("A", "hand_r", -6, 8), r=11.5, bite=0.62,
                  sc=SC, seed=3)

    # ---- 15.0-16.7: the fake tears
    cry = clamp01(tr(t, 15.0, 15.5)) * (1 - clamp01(tr(t, 16.4, 16.8)))
    if cry > 0.01:
        B["m"] = "wail"
        B["m_open"] = 0.55 + 0.45 * abs(wave(t, 4.2, 1))
        B["e_style"] = "closed"
        B["b_ang"] = -1.0
        B["b_raise"] = 0.6
        B["head_tilt"] = lerp(-6, 14, cry) + 6 * wave(t, 4.2, 1)
        B["crouch"] = 0.8 - 0.15 * cry
        B["leg_mode"] = "sit"
        B["hand_l"] = body_inv(B, B["x"] - 34, B["y"] - 178 * SC)
        B["hand_r"] = body_inv(B, B["x"] + 30, B["y"] - 176 * SC)
        B["elbow_l"] = .62
        B["elbow_r"] = -.62
        B["sqy"] = 1 + 0.05 * wave(t, 4.2, 1)
        B["sqx"] = 1 - 0.04 * wave(t, 4.2, 1)
        for i in range(2):
            ph = (t * 2.2 + i * .5) % 1.0
            fx.append(dict(draw="symbol", kind="tear", x=B["x"] + (i * 2 - 1) * 26 * SC,
                           y=B["y"] - 150 * SC + ph * 50, s=20, life=ph * .9, sc=SC,
                           seed=71 + i))
    if 15.9 < t < 16.7:                                  # ...and the pointing
        B["hand_l"] = body_inv(B, ax - 190, GROUND - 90 * SC)
        B["elbow_l"] = -1.0
        B["m"] = "wail"
        B["hand_r"] = body_inv(B, B["x"] + 20, B["y"] - 150 * SC)
        B["head_tilt"] = -4
        B["e_style"] = "normal"
        B["e_look"] = -0.9
        fx.append(dict(draw="arcs", x=B["x"] - 90, y=B["y"] - 190 * SC, r=26, a0=150,
                       a1=320, n=2, life=0.2, sc=SC, seed=73))

    # ---- 16.6-17.6: A turns to look (nothing there)
    turn = tr(t, 16.7, 17.15)
    if turn > 0.01:
        A["dir"] = -1 if turn < 0.5 else 1
        A["sqx"] = 1 - 0.4 * math.sin(turn * math.pi)
        A["sqy"] = 1 + 0.13 * math.sin(turn * math.pi)
        A["rot"] = 10 * math.sin(turn * math.pi)
        A["m"] = "flat"
        A["e_style"] = "squint" if t < 17.4 else "normal"
        A["e_look"] = -0.7
        A["b_ang"] = 0.2
        A["hand_r"] = (-30, 140)
    if 17.2 < t < 18.4:                                  # look, look, shrug
        A["x"] = ax - 26 * tr(t, 17.2, 17.6)
        A["lean"] = -10
        A["head_tilt"] = lerp(0, -12, tr(t, 17.4, 17.8))
        A["m"] = "flat"
        A["e_style"] = "normal"
        A["hand_l"] = None
        A["arm_swing"] = 0.3 * tr(t, 17.8, 18.1)
        fx.append(dict(draw="symbol", kind="?", x=A["x"] + 84, y=ASY + 16, s=44,
                       life=1 - pulse(t, 17.15, 18.05, shape="pop"), sc=SC, seed=75))

    # ---- 17.6-18.6: B swipes the cookie back and bolts
    sneak = tr(t, 17.55, 18.35)
    if sneak > 0.01:
        B["dir"] = 1
        B["crouch"] = 0.8 - 0.8 * clamp01(tr(t, 17.55, 17.85))
        B["leg_mode"] = "spin" if t > 18.15 else "stand"
        if t < 18.15:
            for i, sgn in enumerate((-1, 1)):
                p = (t * 2.3 + .5 * i) % 1.0
                B["foot_r" if sgn > 0 else "foot_l"] = (-30 + 18 * math.cos(2 * math.pi * p),
                                                       max(0.0, math.sin(2 * math.pi * p)) * 26)
            B["lean"] = -18
            B["head_tilt"] = 10
            B["e_style"] = "normal"
            B["e_look"] = 0.7
            B["b_ang"] = -0.3
            B["m"] = "flat"
            B["hand_l"] = None
            B["hand_r"] = body_inv(B, ax - 40 - 4 * (1 - sneak), GROUND - 190 * SC)
            B["elbow_r"] = 1.0
        bx2 = lerp(bx - 66.0, 660.0, ease(tr(t, 18.15, 20.0), "in"))
        if t > 18.15:
            B["x"] = bx2
            B["y"] = GROUND + 6
            B["leg_mode"] = "spin"
            B["gait_phase"] = t * 8.4
            B["dir"] = -1
            B["lean"] = 24
            B["m"] = "laugh"
            B["m_open"] = 0.8
            B["e_style"] = "happy"
            B["hand_r"] = None
            B["hand_l"] = None
            B["arm_swing"] = 1.3
            B["crouch"] = 0.1
            B["hair"] = 0.3
            fx += _trail(t, B["x"] + 34, GROUND + 6, rate=9, n=3, seed=81, scale=1.0)
            fx.append(dict(draw="dust", x=B["x"] + 58, y=GROUND + 8, r=96,
                           life=clamp01(tr(t, 18.3, 19.2)), sc=1.0, seed=89))
            cookie = dict(draw="cookie", attach=("B", "hand_r", 10, 2), r=11.5, bite=0.62,
                          sc=SC, seed=3)
        else:
            B["x"] = bx - 66 * ease(tr(t, 17.55, 18.15), "in")
    if t < 17.6:
        cookie = None if cry < 0.01 else dict(draw="cookie", attach=("A", "hand_r", -6, 8),
                                              r=11.5, bite=0.62, sc=SC, seed=3)

    # ---- 18.6-20.0: the realisation.  Jaw on the floor.
    shock = tr(t, 18.55, 19.0)
    if shock > 0.01:
        A["dir"] = -1
        A["x"] = ax - 26
        A["sqx"] = lerp(1, 0.88, ease(shock, "out"))
        A["sqy"] = lerp(1, 1.16, ease(shock, "out"))
        A["m"] = "shock"
        A["m_open"] = 0.3 + 0.7 * shock
        A["e_style"] = "bulge"
        A["b_raise"] = 1.0
        A["b_ang"] = 0.0
        A["head_push"] = 0.0
        A["head_tilt"] = -6 - 6 * shock
        A["hair"] = shock
        A["hand_l"] = None
        A["hand_r"] = None
        A["arm_swing"] = 0.6 * shock
        A["crouch"] = 0.15 - 0.15 * shock
        A["lean"] = lerp(-10, 6, shock) + 3 * wave(t, 12, 1, .2)
        A["y"] = GROUND + 4 * shock
        if t > 19.5:                        # he coils back, then launches
            k = ease(tr(t, 19.5, 20.0), "out")
            A["x"] = lerp(ax - 26, 900.0, k)
            A["dir"] = -1
            A["leg_mode"] = "spin"
            A["gait_phase"] = t * 7.6
            A["arm_swing"] = 1.1
            A["lean"] = 6 + 16 * k
            A["y"] = GROUND - 6 * k
        for i in range(2):
            fx.append(dict(draw="symbol", kind="!", x=A["x"] - 66 - i * 42,
                           y=ASY - i * 22, s=52 + i * 10,
                           life=1 - pulse(t, 18.6 + i * .16, 19.5 + i * .16, shape="pop"),
                           sc=SC, seed=85 + i))
        fx.append(dict(draw="shock", x=A["x"], y=ASY + 60, r=74 * SC,
                       life=clamp01(tr(t, 18.7, 19.5)), sc=1.0, n=10, seed=87))
        if t > 19.3:                                     # fury, and the crouch
            f = tr(t, 19.3, 19.9)
            A["b_ang"] = 1.6 * f
            A["m"] = "bite"
            A["m_open"] = 1.0 * f
            A["hair"] = 1.0 - 0.4 * f
            A["sqx"] = 1 + 0.2 * f
            A["sqy"] = 1 - 0.22 * f
            A["crouch"] = 0.15 + 0.5 * f
            A["lean"] = 18 * f - 6
            A["e_style"] = "squint"
            A["e_look"] = 0.8
            fx.append(dict(draw="symbol", kind="anger", x=A["x"] - 58,
                           y=ASY - 6, s=34, life=1 - pulse(t, 19.35, 19.95, shape="pop"),
                           sc=SC, seed=88))
            cookie = dict(draw="cookie", attach=("B", "hand_r", 10, 2), r=11.5, bite=0.62,
                          sc=SC, seed=3)
    return A, B, cookie, fx


# ---------------------------------------------------------------- beat five
def beat5(t: float):
    fx: list = []
    T0 = 20.0
    runf = t * 7.6
    collide = 22.62
    spin_t = tr(t, 22.95, 24.5)
    if t < collide:
        # A chases from the left, B zig-zags ahead of him, A slides
        u = tr(t, T0, collide)
        b_x = lerp(660.0, 455.0, ease(u, "lin"))          # B, cookie in paw, in front
        a_x = lerp(900.0, 505.0, ease(u, "lin"))           # A, furious, behind
        dodge = math.sin(u * math.pi * 5.2) * 44 * (1 - u * 0.4)
        b_y = GROUND + 20 + dodge
        a_y = GROUND + 6 + dodge * 0.35
        slide = tr(t, 21.55, 22.35)
        A = _p(x=a_x, y=a_y, scale=depth_scale(a_y, SC), dir=-1,
               leg_mode="spin" if slide < 0.1 else "stand",
               gait_phase=runf, lean=lerp(22, 30, slide), crouch=lerp(0.1, 0.62, slide),
               m="grin" if t < 21.4 else "bite", m_open=1.0, e_style="squint",
               e_look=0.7, b_ang=1.6, hand_l=None, hand_r=None, arm_swing=1.2,
               sqx=1 + 0.14 * slide, sqy=1 - 0.12 * slide, hair=0.7,
               foot_l=(-30, 4) if slide > 0.1 else None,
               foot_r=(6, 10) if 0.1 < slide < 0.9 else None,
               leg_len=1.0 + 0.15 * slide)
        A["dir"] = -1
        B = _p(x=b_x, y=b_y, scale=depth_scale(b_y, SC), dir=-1, leg_mode="spin",
               gait_phase=runf + 0.4, lean=lerp(18, 26, u), crouch=0.1, m="laugh",
               m_open=0.85, e_style="happy", hand_l=None, hand_r=None, arm_swing=1.4,
               sqy=1 + 0.05 * wave(t, 7.6, 1), hair=0.4, sqx=1 - 0.04 * wave(t, 7.6, 1))
        cookie = dict(draw="cookie", attach=("B", "hand_r", 8, 2), r=11.5, bite=0.62,
                      sc=SC, seed=3)
        for P in (A, B):
            fx += _trail(t, P["x"] - 34 * P["dir"], P["y"] + 2, rate=9.5, n=3,
                         seed=int(P["y"] * .5) + 11, scale=1.0)
            fx.append(dict(draw="speed", x=P["x"] - 40 * P["dir"], y=P["y"] - 140 * SC,
                           ln=50, n=4, ang=0, sc=SC, life=(t * 4) % 1, seed=int(P["y"]),
                           curve=7))
        if slide > 0.05:
            for i in range(2):
                fx.append(dict(draw="symbol", kind="skid", x=a_x + 40 + i * 26,
                               y=a_y + 6, s=30, life=clamp01(slide * (1.2 - i * .1)),
                               sc=SC, seed=93 + i))
            fx.append(dict(draw="dust", x=a_x + 58, y=a_y + 6, r=126, life=clamp01(slide * .8),
                           sc=1.0, seed=95, puffs=6))
    elif t < 22.95:                                      # the collision
        u = tr(t, collide, 22.95)
        A = _p(x=505 + u * 42, y=GROUND + 4, scale=SC, dir=-1, leg_mode="stand",
               rot=16 + 12 * (1 - u), crouch=0.35, m="o", m_open=1.0, e_style="wide",
               b_raise=1.0, hand_l=(-70, 150), hand_r=(60, 168), elbow_l=.62,
               elbow_r=-.62, sqx=1.18 - 0.2 * u, sqy=0.86 + 0.14 * u, hair=1.0)
        B = _p(x=455 - u * 36, y=GROUND + 20, scale=SC, dir=1, leg_mode="stand",
               rot=-18 - 10 * (1 - u), crouch=0.3, m="o", m_open=0.9, e_style="wide",
               b_raise=0.8, hand_l=(66, 150), hand_r=(-52, 160), elbow_r=.62,
               sqx=1.16 - 0.18 * u, sqy=0.88 + 0.12 * u, hair=0.8)
        cookie = dict(draw="cookie", attach=("B", "hand_r", 6, 2), r=11.5, bite=0.62,
                      sc=SC, seed=3)
        fx.append(dict(draw="star", x=480, y=GROUND - 150 * SC, r=70,
                       life=clamp01(tr(t, collide, 22.9)), sc=SC, seed=97))
        for i in range(3):
            fx.append(dict(draw="arcs", x=480, y=GROUND - 150 * SC, r=64 + i * 34, a0=0,
                           a1=360, n=1, life=clamp01(tr(t, collide, 22.9 + i * .05)),
                           sc=SC, seed=98 + i))
        fx.append(dict(draw="dust", x=480, y=GROUND + 8, r=165, life=clamp01(tr(t, collide, 23.3)),
                       sc=1.0, seed=99, puffs=8))
    else:                                                 # spinning tops
        u = spin_t
        decay = (1 - ease(u, "in"))
        a_rot = -1500 * decay ** 1.4
        b_rot = 1320 * decay ** 1.4
        wob = damped(t, 24.4, 3.4, 1.6, 10)
        A = _p(x=547 - 95 * u, y=GROUND + 2, scale=SC, dir=-1, leg_mode="spin",
               rot=a_rot % 360, gait_phase=t * 5, crouch=0.1, m="o", m_open=0.5,
               e_style="spiral" if u > 0.55 else "wide", b_ang=0,
               hand_l=(-72, 150 + wob), hand_r=(66, 160 - wob), elbow_l=.62, elbow_r=-.62,
               sqx=1 + 0.05 * wave(t, 9, 1), sqy=1 - 0.04 * wave(t, 9, 1), hair=1.0,
               head_tilt=wob * 1.6)
        B = _p(x=419 + 221 * u, y=GROUND + 16, scale=SC, dir=1, leg_mode="spin",
               rot=b_rot % 360, gait_phase=t * 5 + .3, crouch=0.05, m="o", m_open=0.4,
               e_style="spiral" if u > 0.6 else "wide", hand_l=(64, 148 - wob),
               hand_r=(-66, 150 + wob), elbow_r=.62, hair=0.9, head_tilt=-wob * 1.5,
               sqx=1 + 0.06 * wave(t, 9, 1, .3))
        cookie = None
        if t > 21:
            cookie = None
        for i in range(3):
            ph = (t * 1.5 + i / 3) % 1.0
            a = 2 * math.pi * (ph + i / 3)
            fx.append(dict(draw="symbol", kind="bird", x=485 + math.cos(a) * 74,
                           y=ASY - 60 + math.sin(a) * 26,
                           s=17, life=1 - u, sc=SC, seed=110 + i))
            fx.append(dict(draw="symbol", kind="spiral_up", x=430 - 60 + i * 60,
                           y=ASY - 20, s=22, life=ph, sc=SC, seed=115 + i))
        if u > 0.72:                                     # they drop, exhausted
            A["y"] = GROUND + 2
            A["rot"] = 0
            B["rot"] = 0
            A["crouch"] = 0.1 + 0.9 * tr(t, 24.55, 24.95)
            B["crouch"] = 0.05 + 0.95 * tr(t, 24.6, 25.0)
            A["leg_mode"] = "sit"
            B["leg_mode"] = "sit"
            A["m"] = "flat"
            B["m"] = "flat"
            A["x"] = lerp(440.0, 452.0, tr(t, 24.5, 25.0))
            B["x"] = lerp(602.0, 640.0, tr(t, 24.5, 25.0))
            fx.append(dict(draw="dust", x=A["x"] - 6, y=GROUND + 6, r=78, life=clamp01(tr(t, 24.5, 25.1)), sc=1.0, seed=120))
            fx.append(dict(draw="dust", x=B["x"] + 6, y=GROUND + 22, r=74, life=clamp01(tr(t, 24.55, 25.15)), sc=1.0, seed=121))
    return A, B, cookie, fx


# ---------------------------------------------------------------- beat six
def beat6(t: float):
    fx: list = []
    ax, bx = 452.0, 640.0
    ay, by = GROUND + 2, GROUND + 18
    br = wave(t, 1.15, 1.0)
    A = _p(x=ax, y=ay, scale=SC, dir=1, leg_mode="sit", crouch=1.0, lean=-8,
           head_tilt=8 + 3 * br, m="flat", m_open=0.35, e_style="normal", e_open=0.42,
           e_look=-0.5, b_ang=0.2, breathe=br, arm_swing=0.0, hand_l=None,
           hand_r=(-26, 120), elbow_r=.62, sqy=1 + 0.02 * br, sqx=1 - 0.02 * br,
           hair=0.2)
    B = _p(x=bx, y=by, scale=SC, dir=-1, leg_mode="sit", crouch=0.95, lean=6,
           head_tilt=-6 - 2 * br, m="flat", m_open=0.4, e_style="normal", e_open=0.4,
           e_look=0.4, b_ang=0.4, breathe=wave(t, 1.05, 1.0, .4), arm_swing=0.0,
           hand_l=None, hand_r=None, sqy=1 + 0.022 * wave(t, 1.05, 1, .4),
           hair=0.1)
    for i, P in enumerate((A, B)):
        fx.append(dict(draw="sweat", x=P["x"] + (46 if i == 1 else -50),
                       y=(ASY if i == 0 else BSY) + 26 + 10 * i,
                       s=15, sc=SC, life=(t * 0.8 + i * .4) % 1, seed=130 + i))
    cookie = None
    heavy = 1.0

    # ---- 26.3 the peace offering (a last crust)
    offer = tr(t, 26.3, 27.0)
    take = tr(t, 27.05, 27.5)
    hand = tr(t, 27.4, 27.75)
    steal = tr(t, 28.05, 28.5)
    if offer > 0.01:
        A["crouch"] = 1.0 - 0.42 * offer
        A["leg_mode"] = "sit" if offer < 0.7 else "stand"
        A["lean"] = lerp(-8, 12, offer)
        A["m"] = "grin" if offer > 0.4 else "smile"
        A["m_w"] = 0.9
        A["e_open"] = 0.75
        A["b_raise"] = 0.7
        A["x"] = ax + 10 * offer
        reach = body_inv(A, lerp(ax + 40, (ax + bx) / 2 - 26, offer), GROUND - 150 * SC)
        A["hand_r"] = reach
        A["elbow_r"] = .62
        cookie = dict(draw="cookie", attach=("A", "hand_r", 10, -4), r=9.5, bite=0.82,
                      sc=SC, seed=5, crumbs=0.6)
        B["e_open"] = lerp(0.4, 1.0, offer)
        B["e_look"] = -0.3 - 0.3 * offer
        B["b_ang"] = lerp(0.4, -0.2, tr(t, 26.7, 27.3))
        B["m"] = "flat"
        if t > 26.9:
            B["m"] = "smile"
            B["crouch"] = 0.95 - 0.55 * offer
            B["leg_mode"] = "sit" if offer < 0.8 else "stand"
            B["x"] = bx - 6 * offer
    if take > 0.01:                                       # B takes it
        B["hand_r"] = body_inv(B, lerp((ax + bx) / 2 + 18, bx - 46, take),
                               GROUND - 152 * SC)
        B["elbow_r"] = -.62
        B["m"] = "grin"
        B["m_w"] = 1.0
        A["hand_r"] = body_inv(A, lerp((ax + bx) / 2 - 26, ax + 60, take), GROUND - 150 * SC)
        cookie = dict(draw="cookie", attach=("B", "hand_r", -8, -2), r=9.5, bite=0.82,
                      sc=SC, seed=5, crumbs=0.4)
        if t > 27.25:
            B["hand_r"] = (-40, 120)                     # parked low, out of the way
    if hand > 0.01:                                       # the handshake
        mx = (ax + bx) / 2 - 6
        pump = math.sin(clamp01(tr(t, 27.5, 28.05)) * math.pi * 2.0) * 12
        for P, sgn in ((A, 1), (B, -1)):
            P["hand_r"] = None
            P["hand_l"] = None
        A["hand_l"] = body_inv(A, mx - 16, GROUND - 150 * SC + pump)
        B["hand_r"] = body_inv(B, mx + 16, GROUND - 128 * SC + pump)
        A["elbow_l"] = -1.0
        A["hand_r"] = body_inv(A, mx - 4, GROUND - 152 * SC + pump)
        B["hand_l"] = body_inv(B, mx + 4, GROUND - 130 * SC + pump)
        B["elbow_l"] = .62
        A["m"] = "grin"
        B["m"] = "grin"
        A["crouch"] = 0.45
        B["crouch"] = 0.35
        A["lean"] = 8
        B["lean"] = 6
        fx.append(dict(draw="hands", x=mx, y=GROUND - 150 * SC + pump, sc=SC,
                       life=0.0, seed=140))
        cookie = dict(draw="cookie", attach=("B", "hand_r", -34, -10), r=9.5, bite=0.82,
                      sc=SC, seed=5, crumbs=0.4)
    if steal > 0.01:                                      # ...and the long-arm swindle
        mx = (ax + bx) / 2 - 6
        A["arm_len"] = lerp(1.0, 1.72, ease(steal, "inout")) * (1.0 - 0.5 * tr(t, 28.5, 28.85))
        back = B["x"] - 34
        A["hand_r"] = body_inv(A, lerp(mx, back, ease(clamp01(steal * 1.35), "inout")),
                              lerp(GROUND - 152 * SC, GROUND - 118 * SC, ease(steal, "inout")))
        A["elbow_r"] = .62 if steal < 0.6 else -1.0
        A["lean"] = 12
        A["head_tilt"] = 4
        A["m"] = "grin"
        A["e_look"] = -0.2
        A["b_ang"] = 1.1
        A["hand_l"] = body_inv(A, mx - 14, GROUND - 150 * SC)
        B["hand_l"] = None
        B["hand_r"] = (-40, 118)
        B["elbow_r"] = 1.0
        B["arm_len"] = 1.0
        if steal < 0.55:
            cookie = dict(draw="cookie", attach=("A", "hand_r", 0, 4), r=9.5, bite=0.82,
                          sc=SC, seed=5)
        elif steal < 0.95:
            cookie = dict(draw="cookie", x=lerp(back, A["x"] + 26, tr(t, 28.35, 28.62)),
                          y=GROUND - 118 * SC, r=9.5, bite=0.82, sc=SC, seed=5)
        else:
            cookie = dict(draw="cookie", attach=("A", "hand_r", -6, 10), r=9.5, bite=0.82,
                          sc=SC, seed=5)
            A["arm_len"] = 1.0
            A["hand_r"] = (-34, 128)
            A["elbow_r"] = .62
    if t > 28.55:                                         # B looks at his empty hand
        B["hand_r"] = (-40, 112)
        B["elbow_r"] = 1.0
        B["m"] = "flat"
        B["e_look"] = -0.2
        B["e_open"] = 1.0
        B["b_ang"] = 0.0
        B["head_tilt"] = lerp(-6, 10, tr(t, 28.6, 28.9))
        B["arm_len"] = 1.0
    if t > 28.75:                                         # ...and turns on the camera
        turn = clamp01(tr(t, 28.78, 29.05))
        B["dir"] = -1 if turn < 0.5 else 1
        B["sqx"] = 1 - 0.42 * math.sin(turn * math.pi)
        B["sqy"] = 1 + 0.1 * math.sin(turn * math.pi)
        B["rot"] = -12 * math.sin(turn * math.pi)
        B["x"] = bx - 10 * turn
        B["y"] = by + 2
        B["leg_mode"] = "sit" if turn < 0.4 else "stand"
        B["crouch"] = lerp(0.35, 0.05, turn)
        B["head_tilt"] = 0
        B["e_style"] = "wide"
        B["e_look"] = 0.0
        B["e_looky"] = 0.0
        B["b_ang"] = 1.8
        B["b_raise"] = -0.4
        B["m"] = "bite"
        B["m_open"] = 1.0
        A["e_look"] = -0.6
        A["b_ang"] = 1.3
    if t > 29.08:                                         # both crack up
        la = tr(t, 29.08, 29.3)
        for P in (A, B):
            P["m"] = "laugh"
            P["m_open"] = 0.5 + 0.5 * abs(wave(t, 7.5, 1))
            P["e_style"] = "happy"
            P["b_ang"] = 0.0
            P["head_tilt"] = lerp(P["head_tilt"], -14, la)
            P["sqy"] = 1 + 0.07 * wave(t, 7.5, 1)
            P["sqx"] = 1 - 0.06 * wave(t, 7.5, 1)
            P["crouch"] = P["crouch"] + 0.25 * la
            P["y"] = P["y"] + abs(wave(t, 7.5, 5.0))
        for i, P in enumerate((A, B)):
            for k in range(2):
                fx.append(dict(draw="symbol", kind="tear", x=P["x"] + (k * 2 - 1) * 20,
                               y=P["y"] - 210 * SC, s=16, sc=SC,
                               life=(t * 2.6 + k * .5 + i * .25) % 1, seed=150 + k))
        cookie = dict(draw="cookie", attach=("A", "hand_r", -6, 10), r=9.5, bite=0.82,
                      sc=SC, seed=5)
    if t >= FREEZE_T - 0.02:                              # the freeze frame
        heavy = 1.35
        for i in range(4):
            cx, cy = (120 if i % 2 == 0 else W - 120, 220 if i < 2 else H - 210)
            fx.append(dict(draw="tick", x=cx, y=cy, sc=1.0, r=9.0, alpha=70, seed=200 + i))
        for k in range(10):
            a = 2 * math.pi * k / 10
            r0, r1 = 300, 340
            fx.append(dict(draw="speed", x=540 + math.cos(a) * r1, y=1000 + math.sin(a) * r1,
                           ln=40, n=1, ang=math.degrees(a), sc=1.0, life=0.0, seed=300 + k,
                           curve=0, weight=2.2))
    return A, B, cookie, fx, heavy
