#!/usr/bin/env python3
"""The Wave That Broke the Frame.

A single 1024x1024 picture, drawn entirely with the Python standard
library: a museum gallery where a great Japanese woodblock wave hangs
in a frame -- and the wave breaks OUT of the frame, spilling foam and
spray over the wall and onto the wooden floor.

Run:  python3 main.py
Writes entry.png next to this file. Deterministic (fixed seed).
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
SEED = 20261117

buf = bytearray(W * H * 3)
rng = random.Random(SEED)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def set_px(x, y, r, g, b):
    """Set one pixel, silently ignoring out-of-bounds coordinates."""
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def _dither_on(x, y, a):
    """Deterministic stipple test: True for a fraction `a` of pixels."""
    h = ((x * 73856093) ^ (y * 19349663) ^ (x * y * 83492791)) & 0xFF
    return h < int(a * 256)


def blend_px(x, y, r, g, b, a):
    """Paint one pixel with opacity a (0..1) using stippling."""
    if a >= 1.0:
        set_px(x, y, r, g, b)
    elif a > 0.0 and 0 <= x < W and 0 <= y < H:
        if _dither_on(x, y, a):
            set_px(x, y, r, g, b)


def fill_rect(x0, y0, x1, y1, r, g, b):
    """Solid filled rectangle (coordinates are clipped to the canvas)."""
    x0 = _clamp(x0, 0, W)
    x1 = _clamp(x1, 0, W)
    y0 = _clamp(y0, 0, H)
    y1 = _clamp(y1, 0, H)
    if x1 <= x0 or y1 <= y0:
        return
    span = bytes((r, g, b)) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        buf[i:i + len(span)] = span


def alpha_rect(x0, y0, x1, y1, r, g, b, a):
    """Translucent rectangle, painted with stippling at opacity a."""
    x0 = _clamp(x0, 0, W)
    x1 = _clamp(x1, 0, W)
    y0 = _clamp(y0, 0, H)
    y1 = _clamp(y1, 0, H)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _dither_on(x, y, a):
                set_px(x, y, r, g, b)


def vgrad(x0, y0, x1, y1, c0, c1):
    """Vertical gradient between two RGB colors."""
    if y1 <= y0:
        return
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        r = int(c0[0] + (c1[0] - c0[0]) * t)
        g = int(c0[1] + (c1[1] - c0[1]) * t)
        b = int(c0[2] + (c1[2] - c0[2]) * t)
        fill_rect(x0, y, x1, y + 1, r, g, b)


def hgrad(x0, y0, x1, y1, c0, c1):
    """Horizontal gradient between two RGB colors."""
    if x1 <= x0:
        return
    for x in range(x0, x1):
        t = (x - x0) / (x1 - x0)
        r = int(c0[0] + (c1[0] - c0[0]) * t)
        g = int(c0[1] + (c1[1] - c0[1]) * t)
        b = int(c0[2] + (c1[2] - c0[2]) * t)
        fill_rect(x, y0, x + 1, y1, r, g, b)


def circle(cx, cy, rad, r, g, b, a=1.0):
    """Filled circle. Translucent when a < 1 (stippled)."""
    if rad <= 0:
        return
    for dy in range(-rad, rad + 1):
        dx = math.isqrt(rad * rad - dy * dy)
        y = cy + dy
        if 0 <= y < H:
            x0 = max(0, cx - dx)
            x1 = min(W, cx + dx + 1)
            if a >= 1.0:
                span = bytes((r, g, b)) * (x1 - x0)
                i = (y * W + x0) * 3
                buf[i:i + len(span)] = span
            else:
                for x in range(x0, x1):
                    if _dither_on(x, y, a):
                        set_px(x, y, r, g, b)


def ellipse(cx, cy, rx, ry, r, g, b, a=1.0):
    """Filled ellipse."""
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        t = 1.0 - (dy * dy) / (ry * ry)
        if t < 0:
            continue
        dx = int(rx * math.sqrt(t))
        y = cy + dy
        if 0 <= y < H:
            x0 = max(0, cx - dx)
            x1 = min(W, cx + dx + 1)
            if a >= 1.0:
                span = bytes((r, g, b)) * (x1 - x0)
                i = (y * W + x0) * 3
                buf[i:i + len(span)] = span
            else:
                for x in range(x0, x1):
                    if _dither_on(x, y, a):
                        set_px(x, y, r, g, b)


def thick_line(x0, y0, x1, y1, rad, r, g, b, a=1.0):
    """A line drawn by stamping circles along the segment."""
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for s in range(steps + 1):
        t = s / steps
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        circle(x, y, rad, r, g, b, a)


def poly(points, r, g, b, a=1.0):
    """Filled polygon (scanline fill). Points are (x, y) tuples."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x_a, y_a = points[i]
            x_b, y_b = points[(i + 1) % n]
            if (y_a <= y < y_b) or (y_b <= y < y_a):
                t = (y + 0.5 - y_a) / (y_b - y_a)
                xs.append(x_a + (x_b - x_a) * t)
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[k]))
            xb = min(W, int(xs[k + 1]) + 1)
            if a >= 1.0:
                span = bytes((r, g, b)) * (xb - xa)
                i = (y * W + xa) * 3
                buf[i:i + len(span)] = span
            else:
                for x in range(xa, xb):
                    if _dither_on(x, y, a):
                        set_px(x, y, r, g, b)


def bezier2(p0, p1, p2, steps):
    """Points along a quadratic Bezier curve."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def ribbon(pts, w0, w1, r, g, b, a=1.0):
    """A tapered ribbon through a list of points (width w0 -> w1)."""
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        rad = int(w0 + (w1 - w0) * t)
        if rad > 0:
            circle(int(x), int(y), rad, r, g, b, a)


def speckle(n, x0, y0, x1, y1, colors, a=0.5):
    """Scatter n tiny dots in a rectangle, for paper/wood texture."""
    for _ in range(n):
        x = rng.randint(x0, x1 - 1)
        y = rng.randint(y0, y1 - 1)
        c = colors[rng.randrange(len(colors))]
        blend_px(x, y, c[0], c[1], c[2], a)


def _png_chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def save_png(path):
    """Write the buffer as a 24-bit RGB PNG (filter: none per row)."""
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += buf[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ----------------------------------------------------------------------
# Bitmap font (3x5, one 15-character string per glyph, row by row)
# ----------------------------------------------------------------------

FONT = {
    "A": "010101111101101",
    "B": "110101110101110",
    "C": "011100100100011",
    "D": "110101101101110",
    "E": "111100110100111",
    "F": "111100110100100",
    "G": "011100101101011",
    "H": "101101111101101",
    "I": "111010010010111",
    "K": "101101110101101",
    "L": "100100100100111",
    "M": "101111111101101",
    "N": "101111101101101",
    "O": "010101101101010",
    "P": "110101110100100",
    "R": "110101110101101",
    "S": "011100010001110",
    "T": "111010010010010",
    "U": "101101101101111",
    "V": "101101101101010",
    "W": "101101111111101",
    "Y": "101101010010010",
    "0": "011101101101110",
    "2": "110001010100111",
    "6": "011100110101010",
    ".": "000000000000010",
    "-": "000000111000000",
    "'": "010010000000000",
    " ": "000000000000000",
}


def text_width(s, scale):
    """Pixel width of a string at the given scale."""
    return len(s) * 4 * scale - scale


def draw_text(x, y, s, scale, color):
    """Draw a string with the 3x5 bitmap font (scale = pixel size)."""
    r, g, b = color
    for i, ch in enumerate(s):
        glyph = FONT.get(ch, FONT[" "])
        ox = x + i * 4 * scale
        for row in range(5):
            for col in range(3):
                if glyph[row * 3 + col] == "1":
                    fill_rect(ox + col * scale, y + row * scale,
                              ox + (col + 1) * scale, y + (row + 1) * scale,
                              r, g, b)


def draw_text_centered(cx, y, s, scale, color):
    draw_text(cx - text_width(s, scale) // 2, y, s, scale, color)


# ----------------------------------------------------------------------
# Wave, foam and droplet helpers
# ----------------------------------------------------------------------

FOAM_WHITE = (246, 249, 252)
FOAM_BLUE = (198, 220, 242)
FOAM_SHADOW = (168, 196, 228)
WAVE_DEEP = (24, 62, 120)
WAVE_MID = (38, 96, 168)
WAVE_LIGHT = (86, 148, 208)


def foam_cluster(cx, cy, spread_x, spread_y, n, r0, r1):
    """A burst of foam: scattered white and pale-blue circles."""
    for _ in range(n):
        x = cx + rng.randint(-spread_x, spread_x)
        y = cy + rng.randint(-spread_y, spread_y)
        rad = rng.randint(r0, r1)
        pick = rng.random()
        if pick < 0.55:
            c = FOAM_WHITE
        elif pick < 0.85:
            c = FOAM_BLUE
        else:
            c = FOAM_SHADOW
        circle(x, y, rad, c[0], c[1], c[2])


def spiral(cx, cy, r0, r1, a0, a1, w0, w1, color, n=60):
    """Stamp circles along an Archimedean spiral (a curling wave)."""
    r, g, b = color
    for i in range(n + 1):
        t = i / n
        ang = a0 + (a1 - a0) * t
        rad = r0 + (r1 - r0) * t
        x = cx + rad * math.cos(ang)
        y = cy + rad * math.sin(ang)
        w = int(w0 + (w1 - w0) * t)
        if w > 0:
            circle(int(x), int(y), w, r, g, b)


def spiral_foam(cx, cy, r0, r1, a0, a1, w, n=40):
    """White foam edge following the same spiral, slightly outside."""
    for i in range(n + 1):
        t = i / n
        ang = a0 + (a1 - a0) * t
        rad = r0 + (r1 - r0) * t + w * 0.55
        x = cx + rad * math.cos(ang)
        y = cy + rad * math.sin(ang)
        rad2 = max(2, int(w * (0.35 + 0.35 * rng.random())))
        c = FOAM_WHITE if rng.random() < 0.7 else FOAM_BLUE
        circle(int(x), int(y), rad2, c[0], c[1], c[2])


def droplet(x, y, rad):
    """One water drop frozen in the air: pale disc, bright highlight."""
    circle(x + 1, y + 2, rad, 90, 110, 130, a=0.25)  # soft shadow
    circle(x, y, rad, 178, 208, 236)
    circle(x, y, max(1, rad - 2), 205, 228, 245)
    circle(x - rad // 3, y - rad // 3, max(1, rad // 3),
           250, 252, 254)


def foam_fingers(cx, cy, direction, n=4):
    """Claw-like foam fingers at a wave crest tip."""
    for k in range(n):
        ang = direction + (k - (n - 1) / 2.0) * 0.45
        length = 26 - abs(k - (n - 1) / 2.0) * 7
        x0 = cx + int(14 * math.cos(ang))
        y0 = cy + int(14 * math.sin(ang))
        x1 = cx + int((14 + length) * math.cos(ang))
        y1 = cy + int((14 + length) * math.sin(ang))
        thick_line(x0, y0, x1, y1, 7, *FOAM_WHITE)
        thick_line(x0, y0, x1, y1, 4, *FOAM_BLUE)


# ----------------------------------------------------------------------
# The gallery: wall, floor, frame, and the painting inside it
# ----------------------------------------------------------------------

WALL_BOTTOM = 700
FRAME = (180, 80, 844, 600)          # outer frame rectangle
PAINT = (226, 126, 798, 554)        # painting area inside the mat


def draw_wall():
    vgrad(0, 0, W, WALL_BOTTOM, (233, 221, 201), (213, 195, 166))
    speckle(1200, 0, 0, W, WALL_BOTTOM,
            [(225, 212, 190), (240, 230, 212), (206, 188, 158)], a=0.25)
    # picture rail shadow line
    fill_rect(0, 656, W, 660, 188, 168, 138)
    fill_rect(0, 660, W, 662, 240, 230, 210)
    # baseboard
    fill_rect(0, 686, W, 690, 150, 122, 92)
    fill_rect(0, 690, W, WALL_BOTTOM, 92, 62, 34)
    fill_rect(0, 690, W, 692, 130, 96, 58)


def draw_floor():
    browns = [(138, 90, 51), (122, 78, 43), (150, 100, 60), (110, 70, 38)]
    y = WALL_BOTTOM
    plank = 0
    while y < H:
        y1 = min(H, y + 46)
        fill_rect(0, y, W, y1, *browns[plank % len(browns)])
        # wood grain streaks (only when the plank is tall enough)
        if y1 - y > 6:
            for _ in range(16):
                gy = rng.randint(y + 4, y1 - 4)
                gx = rng.randint(0, W - 260)
                gl = rng.randint(80, 260)
                thick_line(gx, gy, gx + gl, gy + rng.randint(-2, 2), 1,
                           70, 44, 22, a=0.18)
        # plank seam
        fill_rect(0, y1 - 2, W, y1, 58, 34, 16)
        # butt joints, staggered per plank
        jx = (plank * 397) % W
        fill_rect(jx, y, jx + 3, y1, 58, 34, 16)
        fill_rect((jx + 560) % W, y, (jx + 560) % W + 3, y1, 58, 34, 16)
        y = y1
        plank += 1
    # warm pool of light on the floor beneath the frame
    ellipse(512, 830, 380, 95, 255, 228, 176, a=0.07)
    ellipse(512, 830, 300, 70, 255, 228, 176, a=0.07)


def draw_frame():
    # soft shadow thrown on the wall
    alpha_rect(196, 96, 860, 616, 60, 44, 26, a=0.20)
    x0, y0, x1, y1 = FRAME
    fill_rect(x0, y0, x1, y1, 58, 36, 21)                 # walnut outer
    fill_rect(x0 + 6, y0 + 6, x1 - 6, y1 - 6, 96, 64, 36)  # lighter inset
    fill_rect(x0 + 6, y0 + 6, x1 - 6, y0 + 10, 130, 92, 50)  # top bevel light
    fill_rect(x0 + 6, y0 + 6, x0 + 10, y1 - 6, 130, 92, 50)  # left bevel light
    fill_rect(x0 + 6, y1 - 10, x1 - 6, y1 - 6, 30, 18, 10)  # bottom shade
    fill_rect(x1 - 10, y0 + 6, x1 - 6, y1 - 6, 30, 18, 10)  # right shade
    # gold trim around the mat
    fill_rect(212, 112, 812, 118, 201, 162, 39)
    fill_rect(212, 562, 812, 568, 201, 162, 39)
    fill_rect(212, 112, 218, 568, 201, 162, 39)
    fill_rect(806, 112, 812, 568, 201, 162, 39)
    # cream mat
    fill_rect(218, 118, 806, 562, 242, 234, 216)
    # thin inner shadow where the painting meets the mat
    fill_rect(226, 126, 798, 129, 120, 100, 70)
    fill_rect(226, 126, 229, 554, 120, 100, 70)


def draw_painting():
    x0, y0, x1, y1 = PAINT
    # sky
    vgrad(x0, y0, x1, 252, (247, 234, 208), (238, 210, 166))
    # Mount Fuji in the distance
    poly([(252, 252), (372, 178), (492, 252)], 122, 139, 168)
    poly([(352, 198), (372, 178), (392, 198), (380, 208), (372, 200),
          (364, 208)], 238, 240, 244)
    poly([(252, 252), (372, 178), (492, 252)], 122, 139, 168)
    # a few pale clouds
    for (cx, cy, rx) in [(300, 160, 46), (560, 150, 60), (690, 170, 40)]:
        ellipse(cx, cy, rx, 10, 250, 242, 222)
        ellipse(cx - 18, cy + 4, rx // 2, 8, 250, 242, 222)
    # sea
    vgrad(x0, 252, x1, y1, (24, 56, 102), (12, 34, 66))
    # rolling swell bands
    for band_y, phase, col in [(300, 0.0, (38, 96, 168)),
                               (352, 1.3, (52, 112, 184)),
                               (408, 2.6, (38, 96, 168)),
                               (466, 0.7, (86, 148, 208))]:
        pts = []
        for x in range(x0, x1 + 1, 16):
            pts.append((x, band_y + int(7 * math.sin(x / 55.0 + phase))))
        for i in range(len(pts) - 1):
            thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                       3, col[0], col[1], col[2])
    # two small boats with rowers
    for (bx, by, s) in [(300, 330, 1), (520, 402, 2)]:
        poly([(bx - 22 * s, by), (bx + 22 * s, by), (bx + 15 * s, by + 9 * s),
              (bx - 15 * s, by + 9 * s)], 16, 24, 40)
        for dx in (-10, 0, 10):
            thick_line(bx + dx * s, by - 8 * s, bx + dx * s, by - 1,
                       1, 16, 24, 40)
            circle(bx + dx * s, by - 10 * s, 2, 16, 24, 40)
    draw_great_wave()


def draw_great_wave():
    """The big curling wave inside the painting, rising from bottom-right."""
    # main body: three chained Bezier sweeps, tapering width
    seg_a = bezier2((782, 548), (790, 380), (728, 282), 26)
    seg_b = bezier2((728, 282), (690, 190), (592, 212), 26)
    seg_c = bezier2((592, 212), (536, 240), (566, 300), 20)
    path = seg_a + seg_b[1:] + seg_c[1:]
    ribbon(path, 64, 10, *WAVE_DEEP)
    # lit face of the wave, offset up-left
    lit = [(x - 10, y - 12) for (x, y) in path]
    ribbon(lit, 36, 6, *WAVE_MID)
    ribbon([(x - 18, y - 20) for (x, y) in path], 14, 3, *WAVE_LIGHT)
    # white foam breaking along the crest's outer edge
    crest = [(x - 16, y - 30) for (x, y) in seg_b] + \
            [(x - 10, y - 26) for (x, y) in seg_c]
    for (x, y) in crest[::2]:
        circle(int(x), int(y), rng.randint(5, 11), *FOAM_WHITE)
    for (x, y) in crest[1::3]:
        circle(int(x) + 4, int(y) + 5, rng.randint(3, 6), *FOAM_BLUE)
    # foam claws at the tip
    foam_fingers(568, 294, math.radians(150), n=4)
    # whitecaps where the wave meets the sea
    foam_cluster(680, 520, 80, 16, 26, 3, 8)
    foam_cluster(610, 545, 60, 10, 18, 3, 7)
    # thin spray lines on the wave face
    for (sx, sy, ex, ey) in [(700, 420, 640, 340), (730, 460, 690, 380),
                             (660, 480, 620, 420)]:
        thick_line(sx, sy, ex, ey, 2, 210, 228, 244, a=0.7)


# ----------------------------------------------------------------------
# The wave breaks OUT: spill, droplets, puddle, plaque, velvet rope
# ----------------------------------------------------------------------

def draw_spill():
    # crest poking above the top of the frame (starts inside the wave
    # so the two read as one continuous crest breaking through)
    crest = bezier2((692, 178), (720, 40), (812, 58), 24)
    ribbon(crest, 34, 14, *WAVE_DEEP)
    ribbon([(x - 8, y - 10) for (x, y) in crest], 18, 8, *WAVE_MID)
    for (x, y) in crest[::2]:
        circle(int(x) - 6, int(y) - 16, rng.randint(4, 9), *FOAM_WHITE)
    foam_fingers(806, 62, math.radians(-30), n=3)
    # main spill down the wall on the right of the frame
    spill = bezier2((796, 170), (920, 290), (946, 612), 40)
    ribbon(spill, 26, 12, *WAVE_MID)
    ribbon([(x - 5, y - 4) for (x, y) in spill], 14, 7, *WAVE_LIGHT)
    for i, (x, y) in enumerate(spill):
        if i % 4 == 0:
            circle(int(x) + 12, int(y) + 4, rng.randint(3, 7), *FOAM_WHITE)
    foam_cluster(946, 640, 42, 12, 20, 3, 8)
    # thin stream dripping off the left edge of the frame
    drip = bezier2((196, 330), (186, 500), (190, 688), 24)
    ribbon(drip, 8, 5, *WAVE_MID)
    ribbon([(x + 2, y) for (x, y) in drip], 3, 2, *FOAM_BLUE)
    ellipse(192, 706, 42, 8, 42, 90, 158, a=0.4)
    foam_cluster(192, 702, 30, 5, 8, 2, 4)
    # droplets frozen in the air
    for (x, y, rad) in [(880, 140, 6), (930, 210, 8), (985, 300, 5),
                        (905, 380, 7), (970, 470, 6), (870, 520, 5),
                        (1000, 180, 4), (940, 90, 5), (760, 40, 6),
                        (660, 30, 4), (840, 110, 5), (1010, 420, 7),
                        (880, 590, 4), (990, 600, 5), (700, 55, 5),
                        (180, 420, 5), (196, 520, 4), (182, 610, 6)]:
        droplet(x, y, rad)


def draw_puddle():
    # wet sheen and the spill's pool on the wooden floor
    alpha_rect(760, 700, 1000, 762, 200, 210, 225, a=0.05)
    ellipse(880, 742, 135, 22, 42, 90, 158, a=0.5)
    ellipse(880, 738, 110, 16, 62, 116, 180, a=0.5)
    for k in range(16):
        ang = k * math.pi * 2 / 16
        x = 880 + int(128 * math.cos(ang))
        y = 742 + int(20 * math.sin(ang))
        circle(x, y, rng.randint(2, 5), *FOAM_WHITE)
    # faint reflection of the frame on the wet floor
    alpha_rect(330, 700, 700, 780, 96, 128, 168, a=0.06)


def draw_plaque():
    x0, y0, x1, y1 = 24, 300, 152, 400
    vgrad(x0, y0, x1, y1, (178, 142, 62), (146, 112, 44))
    fill_rect(x0, y0, x1, y0 + 3, 110, 82, 28)
    fill_rect(x0, y1 - 3, x1, y1, 110, 82, 28)
    fill_rect(x0, y0, x0 + 3, y1, 110, 82, 28)
    fill_rect(x1 - 3, y0, x1, y1, 110, 82, 28)
    fill_rect(x0 + 4, y0 + 4, x1 - 4, y0 + 6, 214, 180, 110)
    ink = (58, 44, 16)
    cx = (x0 + x1) // 2
    draw_text_centered(cx, 314, "THE WAVE", 2, ink)
    draw_text_centered(cx, 328, "THAT BROKE", 2, ink)
    draw_text_centered(cx, 342, "THE FRAME", 2, ink)
    draw_text_centered(cx, 362, "INK ON PAPER", 2, ink)
    draw_text_centered(cx, 378, "2026", 2, ink)


def draw_rope():
    # shadow of the rope on the floor
    ellipse(512, 946, 230, 12, 40, 26, 14, a=0.10)
    for cx in (290, 734):
        ellipse(cx, 988, 26, 9, 90, 68, 26)
        ellipse(cx, 984, 22, 7, 176, 141, 62)
        fill_rect(cx - 5, 812, cx + 5, 986, 176, 141, 62)
        fill_rect(cx - 3, 812, cx - 1, 986, 214, 180, 110)
        circle(cx, 802, 11, 176, 141, 62)
        circle(cx - 3, 799, 4, 232, 202, 122)
    # sagging velvet rope (catenary)
    pts = []
    for s in range(61):
        t = s / 60
        x = 290 + 444 * t
        y = 818 + 88 * 4 * t * (1 - t)
        pts.append((x, y))
    for i in range(len(pts) - 1):
        thick_line(int(pts[i][0]), int(pts[i][1]),
                   int(pts[i + 1][0]), int(pts[i + 1][1]),
                   9, 125, 26, 38)
    for i in range(len(pts) - 1):
        thick_line(int(pts[i][0]), int(pts[i][1]) - 3,
                   int(pts[i + 1][0]), int(pts[i + 1][1]) - 3,
                   5, 168, 44, 58)
    for s in range(0, 61, 6):
        x, y = pts[s]
        circle(int(x), int(y) - 6, 2, 200, 90, 104)


def vignette():
    for k in range(3):
        a = 0.02 + 0.01 * k
        d = k * 14
        alpha_rect(0, d, W, d + 14, 20, 14, 10, a)
        alpha_rect(0, H - d - 14, W, H - d, 20, 14, 10, a)
        alpha_rect(d, 0, d + 14, H, 20, 14, 10, a)
        alpha_rect(W - d - 14, 0, W - d, H, 20, 14, 10, a)


def main():
    draw_wall()
    draw_floor()
    draw_frame()
    draw_painting()
    draw_spill()
    draw_puddle()
    draw_plaque()
    draw_rope()
    vignette()
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "entry.png")
    size = save_png(out)
    print("wrote %s (%d bytes, %dx%d)" % (out, size, W, H))


if __name__ == "__main__":
    main()
