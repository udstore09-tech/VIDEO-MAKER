"""Sound for the cartoon, synthesised from scratch.

No samples, no libraries beyond numpy: every footstep, gasp, boing and slide
whistle here is additive synthesis or filtered noise, cut straight onto the
story timeline so the sound effects sit on the drawings' exact frames.

Style: dry 1930s rubber-hose cartoon foley - shoe soles on paper, a muted
brass "oom-pah-pah" bed, slide whistles, a dazed triangle, and a kid laughing.
"""
from __future__ import annotations

import math
import os
import wave

import numpy as np

SR = 44100
TWO_PI = 2.0 * math.pi


# ----------------------------------------------------------------- utilities
def _t(n, sr=SR):
    return np.arange(n) / sr


def _adsr(n, a=0.005, d=0.08, s=0.4, r=0.18, sr=SR):
    """Attack / decay / sustain / release, in seconds."""
    i = _t(n, sr)
    env = np.where(i < a, i / max(a, 1e-6),
                   np.where(i < a + d, 1.0 - (1.0 - s) * (i - a) / d,
                            np.where(i < n / sr - r, s, s * np.maximum(0, 1 - (i - (n / sr - r)) / r))))
    return np.maximum(env, 0.0)


def _bandpass(x, f0, bw_oct=1.0, sr=SR):
    """Gaussian in log-frequency: cheap, smooth, no scipy."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    lc = np.log2(np.maximum(f, 20.0) / max(f0, 25.0))
    g = np.exp(-(lc / bw_oct) ** 2 * 1.44)
    g[f < 40] = 0.0
    return np.fft.irfft(np.fft.rfft(x) * g, n=n)


def _noise(n, seed=0, sr=SR):
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n)


def _fm(n, freq, harm=((1.0, 1.0), (2.0, .35), (3.0, .12), (5.0, .05)), sr=SR):
    """Additive voice with per-partial decay - a decent plucked/reedy colour."""
    i = _t(n, sr)
    out = np.zeros(n)
    for k, (mult, amp) in enumerate(harm):
        decay = np.exp(-i * (2.6 + 2.4 * mult))
        out += amp * np.sin(TWO_PI * freq * mult * i) * decay
    return out


# ------------------------------------------------------------------- voices
def voice(dur, fcurve, harm, env=None, vib=(0.0, 0.0), sr=SR, air=0.0, seed=0):
    """fcurve: (f0, f1, exponent) pitch glide; harm: list of (mult, amp, decay)."""
    n = int(dur * sr)
    i = _t(n, sr)
    u = i / max(dur, 1e-6)
    f0, f1, p = fcurve
    freq = (f0 + (f1 - f0) * np.power(u, p)) if f0 != f1 else np.full(n, float(f0))
    av, vhz = vib
    if av > 0:
        freq = freq * (1.0 + av * np.sin(TWO_PI * vhz * u * dur) * np.exp(-2.0 * u))
    ph = np.cumsum(freq) / sr
    out = np.zeros(n)
    for mult, amp, dec in harm:
        out += amp * np.sin(TWO_PI * mult * ph) * np.exp(-i * dec)
    if air > 0:
        out += air * _bandpass(_noise(n, seed, sr), 2200, 1.6) * _adsr(n, .01, .05, .6, .1, sr)
    e = _adsr(n, *env, sr=sr) if env else _adsr(n, .004, dur * .3, .55, dur * .45, sr)
    return out * e


def hit(dur, f0, f1, harm, **kw):
    return voice(dur, (f0, f1, 1.0), harm, **kw)


BRASS = ((1.0, .9, 2.2), (2.0, .55, 3.0), (3.0, .3, 4.2), (4.0, .18, 5.5), (6.0, .08, 7.))
REED = ((1.0, .8, 1.6), (2.0, .6, 2.4), (3.0, .45, 3.4), (4.0, .3, 5.))
STR = ((1.0, 1., 1.2), (2.0, .6, 2.4), (3.0, .4, 4.2), (5.0, .22, 7.))


# --------------------------------------------------------------------- mix
class Mix:
    def __init__(self, dur, sr=SR, chans=2):
        self.sr, self.n = sr, int(dur * sr)
        self.buf = np.zeros((self.n, chans), dtype=np.float64)

    def add(self, sig, t0, gain=1.0, pan=0.0, sr=None):
        sr = sr or self.sr
        a = int(t0 * sr)
        if a >= self.n:
            return
        seg = sig[:self.n - a]
        w = len(seg)
        g0 = math.sqrt(0.5) * (1.0 - min(1.0, max(-1.0, pan)))
        g1 = math.sqrt(0.5) * (1.0 + min(1.0, max(-1.0, pan)))
        self.buf[a:a + w, 0] += seg * (gain * g0)
        self.buf[a:a + w, 1] += seg * (gain * g1)

    def write(self, path):
        x = self.buf
        peak = np.abs(x).max() or 1.0
        x = x / peak * 0.92
        pcm = (x * 32767.0).astype("<i2")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with wave.open(path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes(pcm.tobytes())
        return path


# --------------------------------------------------------------- foley kit
def step(m, t, gain=.5, seed=0, hard=0.0):
    n = int(.05 * SR)
    sc = _bandpass(_noise(n, seed), 1500 + 900 * hard, 1.15) * _adsr(n, .001, .03, .02, .01)
    m.add(sc, t, .34 * gain)
    th = np.sin(TWO_PI * np.linspace(88, 52, int(.07 * SR)) / SR * np.arange(int(.07 * SR))) \
        * _adsr(int(.07 * SR), .002, .05, .0, .01)
    m.add(th, t, .30 * gain * (1 + hard))


def skitter(m, t, dur, rate=11.0, gain=.5, seed=0):
    i, tt, k = 0, t, 0
    while i < dur and tt < t + dur:
        step(m, tt, gain * (0.7 + 0.5 * np.random.default_rng(seed + k).uniform()), seed=seed + k,
             hard=k % 4 == 0)
        dt = 1.0 / rate * (0.86 + 0.28 * np.random.default_rng(seed + 91 + k).uniform())
        tt += dt
        i += dt
        k += 1


def whoosh(m, t, dur=.28, f0=420, f1=1700, gain=.22, seed=0):
    n = int(dur * SR)
    i = _t(n)
    u = i / dur
    c = f0 + (f1 - f0) * u ** .8
    x = _noise(n, seed) * np.exp(-((np.log2(np.maximum(c, 1) / np.array([f0])) ) ))
    env = np.sin(np.pi * u) ** 1.2
    m.add(_bandpass(_noise(n, seed) * env, (f0 + f1) / 2, 1.4) * 3.0, t, gain)


def crash(m, t, gain=.5, dur=1.1, seed=0, metal=1.0):
    n = int(dur * SR)
    i = _t(n)
    x = _noise(n, seed) * np.exp(-i * 4.2)
    if metal > 0:
        for k, f in enumerate((1173., 1643., 2211., 2899., 3607.)):
            x += metal * .12 * np.sin(TWO_PI * f * i) * np.exp(-i * (3.0 + k * .5))
        x += metal * .2 * _bandpass(_noise(n, seed + 5), 3400, 1.1) * np.exp(-i * 6.0)
    m.add(x, t, gain)


def bell(m, t, f=1400, dur=1.5, gain=.3, seed=0):
    n = int(dur * SR)
    i = _t(n)
    x = np.zeros(n)
    for k, (mult, amp, dec) in enumerate(((1, 1, 1.4), (2.76, .5, 2.2), (5.4, .22, 3.4), (8.9, .08, 5.))):
        x += amp * np.sin(TWO_PI * f * mult * i) * np.exp(-i * dec)
    x *= 1 + .25 * np.sin(TWO_PI * 5.5 * i)
    m.add(x, t, gain)


def bells_dazed(m, t, n_=3, gain=.24):
    for k in range(n_):
        bell(m, t + k * .34, 1180 - k * 60, 1.6, gain * (1 - k * .18), seed=k)
        bell(m, t + k * .34 + .05, 1180 - k * 60 + 18, 1.5, gain * .5, seed=k + 7)


def giggle(m, t, n_=4, f0=520, gain=.22, down=1.0):
    for k in range(n_):
        d = .085 + .012 * k
        f = f0 * (1 - .06 * k * down)
        v = voice(d, (f * 1.35, f, .5), ((1, 1, 3), (2, .7, 5), (3, .4, 8), (4, .2, 11)),
                  env=(.006, .03, .5, .04))
        m.add(v, t + k * (d + .045), gain * (1 - k * .06))


def laugh_big(m, t, n_=6, gain=.3):
    giggle(m, t, n_, f0=340, gain=gain, down=.35)
    for k in range(n_ // 2):
        m.add(_bandpass(_noise(int(.12 * SR), 40 + k), 900, 1.2) * np.hanning(int(.12 * SR)),
              t + .26 + k * .21, gain * .25)


def gasp(m, t, dur=.42, gain=.3, seed=0):
    n = int(dur * SR)
    i = _t(n)
    u = i / dur
    f = 380 + 620 * np.sqrt(u)
    ph = np.cumsum(f) / SR
    x = np.sin(TWO_PI * ph) * .5 + np.sin(TWO_PI * 2 * ph) * .25
    x = x * np.sin(np.pi * u) ** .7
    x += _bandpass(_noise(n, seed), 1500, 1.2) * np.sin(np.pi * u) ** 1.4 * .5
    m.add(x, t, gain)


def slide_whistle(m, t, dur, f0, f1, gain=.24, shape=1.0):
    n = int(dur * SR)
    u = _t(n) / dur
    f = f0 + (f1 - f0) * u ** shape
    f += 14 * np.sin(TWO_PI * 6.5 * u * dur) * np.sin(np.pi * u)
    ph = np.cumsum(f) / SR
    x = np.sin(TWO_PI * ph) * .8 + np.sin(TWO_PI * 2 * ph) * .12
    x *= np.minimum(1, u / .06) * np.minimum(1, (1 - u) / .18)
    x += _bandpass(_noise(n, 3), 2600, 1.4) * .06
    m.add(x, t, gain)


def boing(m, t, f0=300, f1=120, dur=.5, gain=.3):
    v = voice(dur, (f0, f1, .45), ((1, 1, 2.2), (2, .5, 4), (3, .25, 6)), vib=(.22, 17))
    m.add(v, t, gain)


def thud(m, t, gain=.5, f=110):
    n = int(.22 * SR)
    i = _t(n)
    x = np.sin(TWO_PI * np.linspace(f, 44, n) / SR * np.arange(n)) * np.exp(-i * 22)
    x += _bandpass(_noise(n, 11), 700, 1.0) * np.exp(-i * 60) * .5
    m.add(x, t, gain)


def chomp(m, t, gain=.4, seed=0):
    for k in range(2):
        n = int(.09 * SR)
        x = _bandpass(_noise(n, seed + k), 1100 + k * 900, .9) * np.hanning(n)
        m.add(x, t + k * .11, gain * (1 - k * .3))
    thud(m, t, gain * .4, 150)


def pop(m, t, gain=.3, f=1900):
    n = int(.07 * SR)
    m.add(_bandpass(_noise(n, 5), f, .8) * np.hanning(n) ** .6, t, gain)


def note(m, t, f, dur, gain, harm=STR, pan=0.0):
    m.add(voice(dur, (f, f, 1.), tuple((mh, a, d * .55) for mh, a, d in harm),
                env=(.004, dur * .35, .3, dur * .5)), t, gain, pan)


# ------------------------------------------------------------------- score
def mf(midi):
    """MIDI note number -> frequency (A4 = 69 = 440 Hz)."""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


BEAT = 60.0 / 132.0                     # a jaunty 132 bpm in 3/4
PROG = [(48, "C"), (46, "F"), (45, "G"), (48, "C"), (48, "C"), (46, "F"), (47, "G7"), (48, "C")]
CHORDS = {"C": (60, 64, 67), "F": (60, 65, 69), "G": (59, 62, 67), "G7": (59, 62, 65, 70)}


def _intensity(t):
    """How hard the little band plays, so the music follows the gag."""
    for t0, t1, v in ((0.0, 5.0, .30), (5.0, 6.5, .18), (6.5, 10.2, 1.0), (10.2, 12.6, .8),
                      (12.6, 15.0, .45), (15.0, 19.6, .22), (19.6, 25.0, 1.0),
                      (25.0, 27.6, .3), (27.6, 29.7, .75), (29.7, 99., .0)):
        if t0 <= t < t1:
            return v
    return .4


def bed(m, dur):
    for bar in range(int(dur / (3 * BEAT)) + 1):
        t = bar * 3 * BEAT
        v = _intensity(t) * _intensity(t + 3 * BEAT) ** 0
        if v <= 0.001:
            continue
        root, name = PROG[bar % len(PROG)]
        note(m, t, mf(root - 12), 3 * BEAT, .10 * v, BRASS, pan=-.15)
        note(m, t + BEAT, mf(root), 3 * BEAT, .075 * v, BRASS, pan=.15)
        note(m, t + 2 * BEAT, mf(root + 7), 3 * BEAT, .07 * v, BRASS, pan=.15)
        for k, pc in enumerate(CHORDS[name]):
            note(m, t + BEAT + .01, mf(pc), BEAT * .8, .05 * v / (1 + k * .5), STR, pan=.3 - .2 * k)
            note(m, t + 2 * BEAT + .01, mf(pc), BEAT * .8, .045 * v / (1 + k * .5), STR, pan=-.3 + .2 * k)
        if v > .7:                                       # chase: a tinny piccolo doubling
            for k in range(3):
                note(m, t + k * BEAT, mf(CHORDS[name][k % len(CHORDS[name])] + 12), BEAT * .5,
                     .028 * v, REED, pan=0.)


def whistle(m, t):
    """A's idea of innocent whistling: a little tripping tune."""
    fig = [(72, .00, .16), (76, .18, .14), (79, .34, .26), (76, .64, .14),
           (72, .80, .14), (74, .96, .38)]
    for midi, dt, d in fig:
        v = voice(d, (mf(midi), mf(midi), 1.), ((1, 1, .5), (2, .18, 1.), (3, .05, 2.)),
                  env=(.03, .06, .8, .12), vib=(.012, 5.5))
        m.add(v, t + dt, .16)


def build_score(path, dur=30.0, fps=60):
    m = Mix(dur)
    rng = np.random.default_rng(7)

    # a whisper of room tone + pencil scratch, so it is never dead silent
    n = int(dur * SR)
    room = _bandpass(_noise(n, 3), 900, 2.2) * .012
    scratch = _bandpass(_noise(n, 4), 3600, 1.0) * (.010 + .008 * np.sin(2 * np.pi * 1.7 * _t(n)))
    m.add(room + scratch, 0, 1.0)
    bed(m, dur)

    # ---- beat one: two kids, one cookie -------------------------------- 0-5
    chomp(m, 1.28, .30)
    chomp(m, 2.05, .26)
    pop(m, 2.42, .12, 900)
    skitter(m, 2.72, 1.30, rate=6.5, gain=.16, seed=11)        # A's tiptoes
    pop(m, 4.06, .22, 1500)                                    # the grab
    whoosh(m, 4.12, .22, 300, 900, .10)
    m.add(voice(.5, (520, 430, .6), ((1, 1, 4), (2, .4, 7)), env=(.01, .1, .3, .3)), 4.30, .1)
    whistle(m, 5.55)                                           # "who? not me"

    # ---- beat two: crumbs, fury, chase -------------------------------- 5-10
    pop(m, 6.30, .18, 2400)
    gasp(m, 6.42, .40, .26)
    crash(m, 6.50, .13, .55, metal=.4)
    note(m, 6.52, mf(70), .16, .1, BRASS)
    note(m, 6.70, mf(68), .20, .1, BRASS)
    skitter(m, 6.62, 3.55, rate=12.5, gain=.30, seed=21)       # two sets of shoes
    skitter(m, 6.90, 3.30, rate=11.0, gain=.22, seed=27)
    for tt in (6.88, 8.98):
        whoosh(m, tt - .12, .34, 500, 1500, .16)               # the turnarounds
    slide_whistle(m, 7.4, .3, 900, 1500, .07)

    # ---- beat three: the pencil -------------------------------------- 10-15
    boing(m, 10.42, 420, 180, .30, .16)                        # A's leap
    slide_whistle(m, 10.46, .62, 1250, 620, .17, shape=.8)
    thud(m, 11.10, .28)
    whoosh(m, 11.06, .26, 700, 2200, .12)
    pop(m, 11.14, .3, 700)                                     # the trip
    skitter(m, 11.14, .5, rate=18., gain=.20, seed=31)
    slide_whistle(m, 11.30, .42, 700, 260, .12, shape=1.6)    # the cartwheel
    bell(m, 11.44, 640, .7, .16)
    crash(m, 12.06, .30, 1.0, metal=.75)                       # into the erasers
    for k in range(4):                                          # erasers scatter
        pop(m, 12.12 + k * .07, .16 - k * .03, 1200 + 500 * k)
        thud(m, 12.2 + k * .09, .08, 190)
    bells_dazed(m, 12.55, 3, .17)
    for k, tt in enumerate((12.62, 13.30, 13.94)):             # A howls
        laugh_big(m, tt, 5 - k, .22)
    thud(m, 13.98, .12, 220)                                    # knee slap
    note(m, 14.62, mf(56), .3, .07, BRASS)
    m.add(voice(.45, (200, 150, .7), ((1, 1, 2), (2, .5, 4)), env=(.02, .1, .5, .2)), 14.9, .12)

    # ---- beat four: the fake cry ------------------------------------- 15-20
    for k in range(4):                                          # theatrical sobs
        t = 15.25 + k * .52
        v = voice(.40, (660 - k * 30, 300 - k * 20, .55), ((1, 1, 1.2), (2, .6, 2.2), (3, .3, 4.)),
                  env=(.05, .12, .5, .18), vib=(.05, 7.5), air=.25)
        m.add(v, t, .16)
        if k == 3:
            pop(m, t + .34, .1, 1600)                           # a hiccup
    whoosh(m, 17.55, .22, 300, 1200, .12)                       # the point
    pop(m, 18.02, .16, 1300)
    whoosh(m, 18.10, .20, 900, 300, .10)                        # A turns
    pop(m, 18.55, .24, 1700)                                    # cookie snatched back
    skitter(m, 18.72, 1.35, rate=13., gain=.26, seed=41)        # B runs off laughing
    giggle(m, 19.10, 4, f0=300, gain=.20)
    gasp(m, 19.42, .46, .30)                                    # A's shock
    crash(m, 19.52, .18, .7, metal=.6)
    note(m, 19.52, mf(84), .22, .1, REED)
    note(m, 19.66, mf(79), .30, .1, REED)

    # ---- beat five: the big chase ---------------------------------- 20-25
    skitter(m, 20.05, 2.15, rate=14., gain=.30, seed=51)
    skitter(m, 20.30, 1.90, rate=12.5, gain=.22, seed=57)
    for tt, f0, f1 in ((20.9, 260, 2000), (21.5, 1800, 400)):  # the dodges
        whoosh(m, tt - .16, .38, f0, f1, .20)
        slide_whistle(m, tt - .10, .28, f0, f1, .09)
    slide_whistle(m, 21.62, .58, 1500, 320, .20, shape=.75)    # A slides in
    skitter(m, 21.60, .55, rate=26., gain=.16, seed=61)
    thud(m, 22.42, .55, 96)                                     # the collision
    crash(m, 22.44, .30, .9, metal=.5)
    boing(m, 22.56, 380, 150, .55, .20)
    boing(m, 22.74, 300, 130, .60, .18)
    for k in range(3):                                          # they spin like tops
        whoosh(m, 22.9 + k * .42, .40, 500 + k * 120, 900, .10)
    bells_dazed(m, 23.2, 3, .13)
    for k in range(2):                                          # wobbling heads
        m.add(voice(.5, (240, 205, .5), ((1, 1, 1.5), (2, .45, 3.)), vib=(.14, 6.5)),
              23.55 + k * .55, .12)

    # ---- beat six: peace, and no ------------------------------------- 25-30
    for k in range(5):                                          # heavy breathing
        br = _bandpass(_noise(int(.34 * SR), 70 + k), 700, 1.3) * np.hanning(int(.34 * SR))
        m.add(br, 24.95 + k * .44, .07)
    bell(m, 26.52, 1320, 1.2, .16)                              # the offering
    note(m, 26.60, mf(76), .5, .05, STR, pan=-.2)
    note(m, 26.78, mf(83), .5, .045, STR, pan=.2)
    pop(m, 27.52, .20, 1100)                                    # the handshake
    note(m, 27.54, mf(72), .3, .07, BRASS)
    note(m, 27.54, mf(79), .3, .05, BRASS)
    slide_whistle(m, 28.02, .30, 520, 1250, .16, shape=.6)     # the steal, again
    pop(m, 28.30, .2, 2200)
    for k, (a, b) in enumerate(((430, 360), (360, 300), (300, 232))):
        m.add(voice(.30, (a, b, .6), ((1, .9, 1.4), (2, .5, 2.6), (3, .25, 4.)),
                    env=(.02, .08, .6, .16)), 28.42 + k * .33, .13)
    laugh_big(m, 28.92, 7, .30)                                # everybody laughs
    giggle(m, 29.02, 5, f0=470, gain=.16)
    crash(m, 29.60, .34, 1.3, metal=.8)                         # freeze frame
    thud(m, 29.60, .40, 90)
    note(m, 29.62, mf(84), .8, .09, BRASS)
    note(m, 29.62, mf(88), .8, .07, BRASS)
    bell(m, 29.63, 1760, 1.4, .10)

    # a hair of saturation on the loudest moments keeps it feeling like a horn
    x = m.buf
    x[:] = np.tanh(1.25 * x) / 1.25
    return m.write(path)
