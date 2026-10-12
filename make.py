#!/usr/bin/env python3
"""VIDEO-MAKER: render the cartoon.

    make.py sheet2   -> character model sheet (the animator's own check)
    make.py preview  -> individual frames as PNG
    make.py sheet    -> 24-frame contact sheet of the whole 30 s
    make.py video    -> output/pencil_cartoon.mp4 (60 fps, silent)
    make.py audio    -> output/score.wav
    make.py mux      -> picture + sound
    make.py all      -> everything

Nothing here is stock footage or a still image: 1800 frames of pencil drawing are
actually generated, one at a time, from the rig in pencilcartoon/.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                    # noqa: E402
from PIL import Image, ImageDraw                      # noqa: E402

from pencilcartoon.film import Film                   # noqa: E402

W, H, FPS, DUR = 1080, 1920, 60, 30.0
OUT = "output"


def _film():
    os.makedirs(OUT, exist_ok=True)
    return Film(W, H, FPS, seed=7, cache=os.path.join(OUT, "page_bg.png"))


def preview(times, scale=1.0):
    film = _film()
    for t in times:
        t0 = time.time()
        arr = film.paint(t)
        img = Image.fromarray(arr)
        if scale != 1.0:
            img = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
        p = os.path.join(OUT, f"frame_{t:05.2f}.png")
        img.save(p)
        print(f"  t={t:5.2f}  {time.time() - t0:4.2f}s -> {p}")


def sheet(n=24):
    """Contact sheet of the entire picture, 6 x 4."""
    film = _film()
    ts = [i * DUR / n for i in range(n)]
    tw, th = 270, 480
    tile = Image.new("RGB", (tw * 6, th * 4), (20, 20, 20))
    for i, t in enumerate(ts):
        im = Image.fromarray(film.paint(t)).resize((tw, th), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.text((6, 4), f"{t:4.1f}s", fill=(230, 230, 230))
        tile.paste(im, (i % 6 * tw, i // 6 * th))
    p = os.path.join(OUT, "contact_sheet.png")
    tile.save(p)
    print("wrote", p)
    return p


def strip(t0, t1, n=12, cols=4, scale=0.34, out="output/strip.png"):
    """An animator's x-sheet: N frames of a window, side by side."""
    film = _film()
    tw, th = int(W * scale), int(H * scale)
    rows = (n + cols - 1) // cols
    tile = Image.new("RGB", (tw * cols + 6 * (cols - 1), th * rows + 6 * (rows - 1)),
                     (26, 26, 26))
    for i in range(n):
        t = t0 + (t1 - t0) * i / max(1, n - 1)
        im = Image.fromarray(film.paint(t)).resize((tw, th), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, tw - 1, th - 1], outline=(60, 60, 60), width=2)
        d.text((8, 6), f"{t:5.2f}s", fill=(235, 235, 235))
        r, c = divmod(i, cols)
        tile.paste(im, (c * (tw + 6), r * (th + 6)))
    tile.save(out)
    print("wrote", out, tile.size)
    return out


def video(crf="19", preset="veryfast", upto=DUR, out=None):
    import imageio_ffmpeg
    out = out or os.path.join(OUT, "pencil_cartoon_silent.mp4")
    film = _film()
    n = int(round(upto * FPS))
    gen = imageio_ffmpeg.write_frames(
        out, (W, H), fps=FPS, codec="libx264", pix_fmt_in="gray", pix_fmt_out="yuv420p",
        quality=None, macro_block_size=2,
        output_params=["-crf", crf, "-preset", preset, "-profile:v", "high",
                       "-movflags", "+faststart"])
    gen.send(None)
    t0, done = time.time(), 0
    for i in range(n):
        arr = film.paint(i / FPS)
        gen.send(np.ascontiguousarray(arr[:, :, 0]).tobytes())   # graphite = luma
        done = i + 1
        if done % 60 == 0:
            el = time.time() - t0
            print(f"  {done}/{n} frames  {done / el:5.2f} fps  "
                  f"eta {int((n - done) / max(0.01, done / el))}s", flush=True)
    gen.close()
    print(f"  wrote {out} in {time.time() - t0:.1f}s")
    return out


def audio():
    from pencilcartoon.audio import build_score
    p = os.path.join(OUT, "score.wav")
    build_score(p, DUR, FPS)
    return p


def mux():
    import subprocess
    import imageio_ffmpeg
    v = os.path.join(OUT, "pencil_cartoon_silent.mp4")
    a = os.path.join(OUT, "score.wav")
    o = os.path.join(OUT, "pencil_cartoon.mp4")
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", v, "-i", a,
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-shortest", "-movflags", "+faststart", o]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("ffmpeg mux failed")
    print("wrote", o)
    return o


# --------------------------------------------------------------------------- #
# model sheet: the character check, rendered without the story
# --------------------------------------------------------------------------- #
SHEET_POSES = [
    ("A stand / cheeky", "A", dict(m="grin", b_ang=1.0, e_look=0.4,
                                   hand_l=(30, 120), hand_r=(-28, 118))),
    ("A sit", "A", dict(leg_mode="sit", crouch=1.0, m="smile", lean=6)),
    ("A sneak", "A", dict(leg_mode="stand", crouch=.45, lean=26, head_tilt=-14,
                          e_open=.5, e_looky=.6, m="grin", b_ang=1.2, hand_l=(46, 150),
                          hand_r=(-34, 150), arm_swing=.8, foot_l=(-16, 24),
                          foot_r=(26, 4))),
    ("A run (legs are wheels)", "A", dict(leg_mode="spin", gait_phase=.3, lean=24,
                                          arm_swing=1.2, m="laugh", m_open=.9,
                                          e_style="happy", hand_l=(-30, 150),
                                          hand_r=(46, 186), crouch=.15, hair=.6)),
    ("A laugh + point", "A", dict(leg_mode="stand", lean=-22, head_tilt=16, m="laugh",
                                  m_open=.9, e_style="happy", hand_l=(70, 150),
                                  hand_r=(-26, 96), crouch=.2, sqy=1.05)),
    ("A shock", "A", dict(leg_mode="stand", m="shock", m_open=1.0, e_style="bulge",
                          b_raise=1.0, hair=1.0, sqy=1.14, sqx=.9, crouch=-.15,
                          head_push=2, arm_swing=.6)),
    ("B sit / eat", "B", dict(leg_mode="sit", crouch=1.0, m="chew", m_open=.7,
                              e_style="happy", hand_r=(30, 146), elbow_r=-1.0,
                              head_tilt=6)),
    ("B furious", "B", dict(leg_mode="stand", m="bite", m_open=1.0, e_style="squint",
                            b_ang=1.8, hair=.9, hand_l=(40, 120), hand_r=(-40, 120),
                            lean=6)),
    ("B fake cry", "B", dict(leg_mode="sit", crouch=.8, m="wail", m_open=.9,
                             e_style="closed", b_ang=-1.0, b_raise=.6, head_tilt=12,
                             hand_l=(20, 150), hand_r=(-24, 152), sqx=1.05)),
    ("B chase", "B", dict(leg_mode="spin", gait_phase=.2, arm_swing=1.4, lean=22,
                          m="laugh", m_open=.8, e_style="happy", crouch=.1, hair=.4)),
    ("B swiped it", "B", dict(leg_mode="stand", m="grin", e_look=-.6, b_ang=-.4,
                              hand_l=(-30, 150), hand_r=(70, 176), elbow_r=-1.0,
                              head_tilt=-6)),
    ("B dizzy", "B", dict(leg_mode="sit", crouch=.9, m="o", m_open=.5, e_style="spiral",
                          head_tilt=-10, arm_swing=.4, hair=.2)),
]


def modelsheet(out="output/model_sheet.png", scale=1.95):
    from pencilcartoon.sketchpen import Pen
    from pencilcartoon.rig import PROP_A, PROP_B, draw_actor, pose
    from pencilcartoon.props import cookie

    cw, ch, cols = 520, 700, 4
    rows = (len(SHEET_POSES) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), (232, 230, 224))
    ss = 2
    for i, (label, kind, kw) in enumerate(SHEET_POSES):
        layer = Image.new("L", (cw * ss, ch * ss), 0)
        pen = Pen(ImageDraw.Draw(layer), frame=(i * 5) % 20, ss=ss)
        P = pose(x=cw / 2, y=ch - 60, dir=1 if i % 2 == 0 else -1, scale=scale, **kw)
        m = {}
        draw_actor(pen, P, PROP_A if kind == "A" else PROP_B, m)
        if "eat" in label and "hand_r" in m:
            cookie(pen, m["hand_r"][0] + 12, m["hand_r"][1] - 6, r=26, bite=.5, sc=1.0,
                   seed=3, crumbs=.5)
        if "swiped" in label and "hand_r" in m:
            cookie(pen, m["hand_r"][0] + 8, m["hand_r"][1] - 10, r=24, bite=.6, sc=1.0,
                   seed=3)
        cov = np.frombuffer(layer.tobytes(), np.uint8)
        cov = (cov.reshape(ch, ss, cw, ss).sum((1, 3)).astype(np.float32)
               / (ss * ss * 255.0))
        cov = np.clip(cov, 0, 1)[:, :, None]
        base = np.full((ch, cw, 3), 245.0, np.float32)
        art = (base * (1 - cov) + np.array((58, 56, 54), np.float32) * cov).astype(np.uint8)
        cell = Image.fromarray(art)
        d = ImageDraw.Draw(cell)
        d.line([(30, ch - 60), (cw - 30, ch - 60)], fill=(150, 148, 143), width=2)
        d.rectangle([0, 0, cw - 1, ch - 1], outline=(180, 178, 172), width=2)
        d.text((12, 10), label, fill=(90, 88, 84))
        sheet.paste(cell, ((i % cols) * cw, (i // cols) * ch))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("wrote", out, sheet.size)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["preview", "sheet", "sheet2", "strip", "video",
                                     "audio", "mux", "all"])
    ap.add_argument("--times", default="1.0")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--crf", default="19")
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--upto", type=float, default=DUR)
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=1.0)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--out", default="output/strip.png")
    a = ap.parse_args()
    if a.mode == "preview":
        preview([float(x) for x in a.times.split(",")], a.scale)
    elif a.mode == "sheet":
        sheet()
    elif a.mode == "sheet2":
        modelsheet()
    elif a.mode == "strip":
        strip(a.t0, a.t1, a.n, a.cols, a.scale, a.out)
    elif a.mode == "video":
        video(a.crf, a.preset, a.upto)
    elif a.mode == "audio":
        audio()
    elif a.mode == "mux":
        mux()
    else:
        video(a.crf, a.preset, a.upto)
        audio()
        mux()
