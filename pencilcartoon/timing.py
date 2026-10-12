"""Timing: the easing toolbox an animator keys with.

Every beat in story.py is written in real seconds with these helpers, so the
gags can be re-timed by moving one number.
"""

from __future__ import annotations

import math


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def clamp01(x):
    return clamp(x, 0.0, 1.0)


def lerp(a, b, u):
    return a + (b - a) * u


def tr(t, t0, t1):
    """Normalised progress of t inside [t0, t1]."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return clamp01((t - t0) / (t1 - t0))


def in_range(t, t0, t1):
    return t0 <= t <= t1


def win(t, t0, t1, default=0.0):
    """Like tr but returns default outside the window (for pose blending)."""
    if t < t0 or t > t1:
        return default
    return tr(t, t0, t1)


def ease(u, mode="ease"):
    if mode == "lin":
        return u
    if mode == "out":
        return 1 - (1 - u) ** 2.6
    if mode == "in":
        return u ** 2.6
    if mode == "hard":                      # fast out, snap in (cartoon favourite)
        return 1 - (1 - u) ** 1.5
    if mode == "inout":
        return u * u * (3 - 2 * u)
    if mode == "smooth":
        return u * u * u * (u * (u * 6 - 15) + 10)
    if mode == "back":
        c = 1.70158
        return u ** 2 * ((c + 1) * u - c)
    if mode == "overshoot":
        return 1 - (1 - u) ** 2 * math.cos(u * math.pi * 1.15)
    if mode == "anticipate":                 # squash back, then go
        return -0.18 * math.sin(u * math.pi) * (1 - u) + u ** 1.6
    if mode == "bounce":
        p = 1 - u
        return 1 - abs(math.sin(p * math.pi * 2.2)) * p ** 1.3
    if mode == "elastic":
        return 1 - math.cos(u * math.pi * 3.2) * (1 - u) ** 1.6
    if mode == "hold":
        return 0.0 if u < 1 else 1.0
    return u * u * (3 - 2 * u)


def kf(t, keys, mode="ease"):
    """Keyframe track.  keys = [(time, value), (time, value, 'in'), ...]"""
    if not keys:
        return 0.0
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        t0, v0 = keys[i][0], keys[i][1]
        t1, v1 = keys[i + 1][0], keys[i + 1][1]
        if t <= t1:
            u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            m = keys[i][2] if len(keys[i]) > 2 else mode
            return v0 + (v1 - v0) * ease(u, m)
    return keys[-1][1]


def pulse(t, t0, t1, mode="inout", shape="arc"):
    """0 -> 1 -> 0 inside the window."""
    if t < t0 or t > t1:
        return 0.0
    u = (t - t0) / max(1e-6, (t1 - t0))
    if shape == "pop":
        return clamp01(u * 5.0) * clamp01((1 - u) * 3.0)
    return 1.0 - abs(1 - 2 * ease(u, mode))


def cycle(t, freq, phase=0.0):
    return (t * freq + phase) % 1.0


def wave(t, freq, amp=1.0, phase=0.0):
    return math.sin(2 * math.pi * (t * freq + phase)) * amp


def damped(t, t0, freq=3.0, decay=3.0, amp=1.0):
    """Wobble that dies away - heads, bellies, everything after a hit."""
    dt = max(0.0, t - t0)
    return math.exp(-dt * decay) * math.sin(2 * math.pi * freq * dt) * amp


def pingpong(t, period):
    u = (t / period) % 1.0
    return 1 - abs(1 - 2 * u)


def spin(t, rate, t0=0.0):
    return (t - t0) * rate


def jitter(t, rate=12.0, amp=1.0, salt=0):
    """Staccato random wobble at a fixed rate (jittery hands, shaking laughter)."""
    k = int(t * rate) + salt * 991
    x = math.sin(k * 12.9898 + salt * 78.233) * 43758.5453
    return (x - math.floor(x) - 0.5) * 2 * amp
