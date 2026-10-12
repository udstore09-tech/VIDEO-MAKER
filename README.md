# VIDEO-MAKER — *Pencil Cartoon*

A 30-second, vertical (1080×1920, 60 fps), black-and-white slapstick cartoon that
looks like a graphite pencil sketch drawing itself alive on a sheet of notebook
paper.

There is **no video model and no image sequence** in this pipeline. Every one of the
1800 output frames is *drawn from scratch as live vector line art* by a tiny
procedural animation system — a rig, a timing library and a storyboard — so the
whole film is reproducible from source in about eight minutes.

```
python make.py all            # sheet -> video -> audio -> mux  (~8 min)
open output/pencil_cartoon.mp4
```

## The film

Two kids on a page. **A** is tall, skinny, messy-haired, long-armed and a smart-aleck.
**B** is short, round, short-legged and short-tempered.

| time | gag |
|---|---|
| 0–5 s | they sit in peace; B eats a cookie; A creeps up behind, takes it, whistles |
| 5–10 s | B spots the crumbs on A's face, erupts; A sticks his tongue out, chase, dust |
| 10–15 s | A leaps the pencil on the page; B face-plants into doodled erasers; A howls |
| 15–20 s | B fake-cries, points behind A, snatches the cookie back and flees; A's shock |
| 20–25 s | the big chase: slide, two dodges, head-on collision, both spin like tops |
| 25–30 s | dizzy truce, a shared handshake, A steals it again, the angry look, freeze-frame |

One continuous overhead camera on the page. No cuts, no dissolves, no titles, no
dialogue — the sound is footsteps, gasps, boings, a slide whistle and a small band.

## How it is put together

```
make.py                  CLI: sheet / sheet2 / strip / preview / video / audio / mux / all
pencilcartoon/
  sketchpen.py           the "pencil": resampled, jittered, multi-pass graphite strokes
  paper.py               paper grain, tooth, page shading, margin doodles (baked once)
  rig.py                 the characters: poses, two-bone IK, heads, eyes, mouths, hair
  props.py               cookie, pencil, erasers, dust, speed lines, symbols, sweat
  timing.py               easing, loops, waves, damped oscillators, onions of a beat
  story.py               build(t) -> the whole frame at time t  (the storyboard)
  film.py                dispatch of that spec onto the pen; depth scaling; freeze-frame
  audio.py               the soundtrack, synthesised from scratch with numpy
```

`story.py` is the animation itself: each beat is a function of time that returns the
actors' poses, the props they hold and a list of effects. Nothing is keyframed — a
laugh is `wave(t, 5, 1)` driving the squash, the head bob and the pointing arm, so a
beat can be retimed by editing numbers, not by re-drawing.

Two conventions worth knowing before you touch it:

* **The running clock is shared.** `LOOP` / `loop_path()` in `story.py` drives every
  sprint in the film, so one beat hands the characters to the next at the exact same
  `x` — that is what keeps the "chase" continuous instead of jumping.
* **One scale.** `SC` and `GROUND` in `story.py` set how big the cast is on the page.
  Everything else (symbol anchors `ASY`/`BSY`, the pencil, the eraser pile) is derived
  from them. If you change them, delete `output/page_bg.png`, which is a cache of the
  baked page.

## Look

* `DRAW_FPS = 20` while the film renders at 60: each drawing is held for three frames,
  which is the "shot on twos/threes" frame-by-frame wobble.
* Strokes are drawn twice with independent jitter and a 2× supersample, then pushed
  through the paper's tooth, so no two lines are alike and none of them are straight.
* Depth: characters scale down and lighten as they run to the far side of the page
  (`film.depth_scale`), which is what stops the chase from looking like a cut-out.
* `FREEZE_T = 29.62` freezes the last drawing (with a hard re-ink) so the film ends on
  the posed gag, exactly as a hand-drawn short would.

## Sound

`audio.py` writes `output/score.wav` with the standard library and numpy only: no
samples and no synthesis toolkit. Every cue is placed on the same timeline as the
gags — shoe-soles for the chase, a chomp for the cookie, a slide whistle for the leap,
a dazed triangle for the eraser pile, a small muted-brass band on a 132 bpm waltz that
gets louder when they run and drops out when B fake-cries.

## Tuning

| want | change |
|---|---|
| bigger/smaller cast | `SC` in `story.py` (then delete `output/page_bg.png`) |
| more/less pencil jitter | `INKW`, `rough` in `rig.py`, `rough` defaults in `sketchpen.py` |
| snappier animation | raise `DRAW_FPS` toward 60 in `film.py` |
| retime a gag | the constants at the top of each `beatN()` in `story.py` |
| colour | nothing — it is deliberately monochrome (see below) |

Render flags: `--crf 16` for a finer file, `--preset slower` for a smaller one,
`--upto 15` to render half while checking.

`make.py strip --t0 10.0 --t1 13.0 --n 12` prints an animator's x-sheet for any window
and is the fastest way to review acting; `make.py sheet2` is the model sheet.

## Deliberately absent

no colour, no photorealism, no 3D shading, no static frames or slideshow, no
mid-film redesign of the characters, no missing limbs, no scene changes, no cuts, no
subtitles, no dialogue.
