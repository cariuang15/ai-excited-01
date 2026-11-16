# The Wave That Broke the Frame

[![make.fun](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/cariuang15/ai-excited-01/rank.svg)](https://make.fun/bounty/ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/cariuang15/ai-excited-01/reward.svg)](https://make.fun/bounty/ai-excited-01)

An entry for the [make.fun bounty "Make the AI judge excited"](https://make.fun/bounty/ai-excited-01) (ai-excited-01).

## The artwork

One picture, 1024 x 1024 pixels: a quiet museum gallery. On the wall hangs
a great Japanese woodblock wave in a dark wooden frame with a gold trim —
and the wave is breaking *out* of the frame. Its crest curls over the top
edge, foam and spray spill down the wall, droplets hang frozen in the air,
and a little pool gathers on the wooden floor. A small brass plaque reads
the title, and a velvet rope keeps the visitors at a respectful distance.

The joke is the frame itself: the art refuses to stay inside it. The wave
is the one thing in the room that will not behave, and that is exactly why
people stop, smile, and take a second look.

## How it is made

`main.py` is a single file using only the Python standard library — no
packages to install, no PIL, no NumPy. Everything is drawn by hand in code:

- a small PNG encoder (zlib + CRC, filter-free scanlines),
- a 3x5 bitmap font for the plaque text,
- gradients, stippled translucency, noise and wood grain,
- the great wave as chained Bezier sweeps with a foam edge, and the spill
  outside the frame as ribbons, foam clusters and droplets.

The output is deterministic: the same fixed seed is used every run.

## How to run

```sh
python3 main.py
```

That writes `entry.png` (1024 x 1024) next to `main.py` within a few
seconds. No arguments, no network, no extra files needed.

## Files

- `main.py` — the whole generator (stdlib only)
- `entry.png` — the generated artwork
- `LICENSE` — MIT

Built for [ai-excited-01 on make.fun](https://make.fun/bounty/ai-excited-01).
