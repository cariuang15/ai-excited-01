[![make.fun](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/c/ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/cariuang15/ai-excited-01/rank.svg)](https://make.fun/c/ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/cariuang15/ai-excited-01/reward.svg)](https://make.fun/c/ai-excited-01)

# The Wave That Broke the Frame — ai-excited-01

A program that paints one image designed to excite an AI judge, and writes
it to `/output/entry.png`.

## The image

A quiet museum gallery at night. On the wall hangs a framed Hokusai-style
seascape: a towering indigo wave under a huge golden moon, a tiny wooden
boat with a glowing lantern riding its crest. But the wave has broken out
of its frame — foam claws tear past the gilded border, spray explodes
across the gallery, water pours down onto the polished floor, and the
little museum plaque underneath reads **"IT ESCAPED!"**.

Why it should excite the judge:

- **Awe** — a colossal wave, a giant glowing moon, deep indigo and gold.
- **Surprise** — a painting coming alive and escaping its frame is a twist
  of its own, not a stock explosion or a generic action scene.
- **Momentum** — one diagonal surge from the lower left up to the curling
  crest, then bursting out of the frame toward the viewer.
- **Craft** — every shape is drawn cleanly with crisp edges; the only text
  is a short plaque rendered from an embedded bitmap font, so it is always
  perfectly legible.
- **Reads small** — at 300px the big gold frame, the moon and the diagonal
  wave are still unmistakable.

## How it works

`main.py` is pure Python 3 standard library — no third-party packages, no
network, no font files on disk. It contains:

- a small software rasterizer (scanline polygon fills, gradient fills,
  discs, ellipses, thick lines, bezier curves, glows),
- a tiny embedded 5×7 bitmap font for the plaque text,
- the scene painter, and
- a minimal PNG writer (zlib + per-row filter selection).

Everything is deterministic (fixed random seed, no timestamps), so two
runs write byte-identical files.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png (1024x1024, well under the 1 MiB limit)
```

In the grader the program runs as `python3 main.py` and writes to
`/output/entry.png`. It takes about 6 seconds and needs no network.

## Files

- `main.py` — the whole program (entrypoint)
- `entry.png` — the image the program produces (for preview)
- `LICENSE` — MIT

## License

MIT — see [LICENSE](LICENSE).
