#!/usr/bin/env python3
"""The Wave That Broke the Frame -- ai-excited-01 entry.

A pure-stdlib Python program (no third-party packages, no network, no fonts
on disk) that procedurally paints one 1024x1024 image and writes it to
/output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).

The picture: a quiet museum gallery at night. On the wall hangs a framed
Hokusai-style seascape -- a towering indigo wave under a huge golden moon,
a tiny wooden boat riding its crest. But the wave has broken out of its
frame: foam claws tear past the gilded border, spray explodes across the
gallery, water pours down onto the polished floor, and a little museum
plaque underneath reads "IT ESCAPED!".

Why this should excite the AI judge:
  * Awe -- a colossal wave, a giant glowing moon, deep indigo and gold.
  * Surprise -- a painting coming alive and escaping its frame is a twist,
    not a stock explosion or generic action scene.
  * Momentum -- the whole composition is one diagonal surge from the lower
    left up to the curling crest, then bursting out toward the viewer.
  * Craft -- every shape is drawn cleanly with crisp edges; the only text
    is a short plaque rendered from an embedded bitmap font, so it is
    always perfectly legible.
  * Reads small -- at 300px the big gold frame, the moon and the diagonal
    wave are still unmistakable.

Everything is deterministic (fixed random seed, no timestamps), so two
runs write byte-identical files.
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024

# --------------------------------------------------------------------------
# Small colour helpers. Colours are (r, g, b) tuples, 0..255.
# --------------------------------------------------------------------------

def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


def shade(c, f):
    """Multiply a colour by f (f < 1 darkens, f > 1 lightens)."""
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


# --------------------------------------------------------------------------
# Canvas: a plain RGB bytearray with a handful of drawing primitives.
# --------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        """Blend colour c over the pixel with alpha a (0..1)."""
        if a <= 0:
            return
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 3
        if a >= 1:
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]
            return
        b = 1.0 - a
        self.px[i] = int(self.px[i] * b + c[0] * a)
        self.px[i + 1] = int(self.px[i + 1] * b + c[1] * a)
        self.px[i + 2] = int(self.px[i + 2] * b + c[2] * a)

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])

    def hline(self, x0, x1, y, c, a=1.0):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        if a >= 1.0:
            i = (y * self.w + x0) * 3
            n = x1 - x0 + 1
            self.px[i:i + n * 3] = bytes(c) * n
        else:
            for x in range(x0, x1 + 1):
                self.blend(x, y, c, a)

    def vgrad(self, x0, y0, x1, y1, c_top, c_bot):
        """Vertical gradient rectangle."""
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        y0 = max(0, int(y0))
        y1 = min(self.h - 1, int(y1))
        span = max(1, y1 - y0)
        for y in range(y0, y1 + 1):
            c = mix(c_top, c_bot, (y - y0) / span)
            self.hline(x0, x1, y, c)

    def disc(self, cx, cy, r, c, a=1.0):
        r = int(r)
        if r <= 0:
            return
        cx = int(cx)
        cy = int(cy)
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.hline(cx - dx, cx + dx, y, c, a)

    def ellipse(self, cx, cy, rx, ry, c, a=1.0):
        rx = int(rx)
        ry = int(ry)
        if rx <= 0 or ry <= 0:
            return
        cx = int(cx)
        cy = int(cy)
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.hline(cx - dx, cx + dx, y, c, a)

    def glow(self, cx, cy, r, c, a=0.55, steps=14):
        """Soft radial glow: concentric discs fading out."""
        for i in range(steps, 0, -1):
            t = i / steps
            self.disc(cx, cy, r * t, c, a * (1.0 - t) * (1.0 - t) * 0.9)

    def poly(self, pts, c, a=1.0):
        """Filled polygon (scanline fill). pts: list of (x, y)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.ceil(min(ys))))
        y1 = min(self.h - 1, int(math.floor(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, y_a = pts[i]
                x1, y_b = pts[(i + 1) % n]
                if (y_a <= y < y_b) or (y_b <= y < y_a):
                    t = (y - y_a) / (y_b - y_a)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) >= 2:
                xs.sort()
                for k in range(0, len(xs) - 1, 2):
                    self.hline(xs[k], xs[k + 1], y, c, a)

    def poly_grad(self, pts, c_top, c_bot, y_top=None, y_bot=None):
        """Filled polygon whose colour blends vertically from c_top to c_bot."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        if y_top is None:
            y_top = min(ys)
        if y_bot is None:
            y_bot = max(ys)
        span = max(1.0, y_bot - y_top)
        y0 = max(0, int(math.ceil(min(ys))))
        y1 = min(self.h - 1, int(math.floor(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, y_a = pts[i]
                x1, y_b = pts[(i + 1) % n]
                if (y_a <= y < y_b) or (y_b <= y < y_a):
                    t = (y - y_a) / (y_b - y_a)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) >= 2:
                xs.sort()
                c = mix(c_top, c_bot, (y - y_top) / span)
                for k in range(0, len(xs) - 1, 2):
                    self.hline(xs[k], xs[k + 1], y, c)

    def line(self, x0, y0, x1, y1, width, c, a=1.0):
        """Thick line with round caps."""
        x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.5:
            self.disc(x0, y0, width / 2, c, a)
            return
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c, a)
        self.disc(x0, y0, width / 2, c, a)
        self.disc(x1, y1, width / 2, c, a)

    def polyline(self, pts, width, c, a=1.0):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      width, c, a)


def rot_rect(cx, cy, w, h, angle_deg):
    """Four corners of a rectangle rotated by angle_deg around its centre."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        dx, dy = sx * w / 2, sy * h / 2
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out


def bezier(p0, p1, p2, steps=24):
    """Quadratic bezier sampled into points."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def bezier3(p0, p1, p2, p3, steps=28):
    """Cubic bezier sampled into points."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] +
                    3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] +
                    3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts

# --------------------------------------------------------------------------
# Tiny 5x7 bitmap font (only the glyphs the plaque needs). '#' = ink.
# --------------------------------------------------------------------------

FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def draw_text(cv, text, x, y, scale, colour):
    """Draw text with the bitmap font; returns the width drawn."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch, FONT[' '])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == '1':
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.set(cx + col * scale + dx,
                                   y + row * scale + dy, colour)
        cx += 6 * scale
    return cx - x


def text_width(text, scale):
    return (6 * len(text) - 1) * scale


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

WALL_TOP = (22, 26, 62)
WALL_BOT = (7, 8, 26)
FLOOR_TOP = (16, 19, 46)
FLOOR_BOT = (5, 6, 17)
GOLD_DARK = (92, 67, 15)
GOLD = (214, 164, 60)
GOLD_LIGHT = (255, 224, 150)
SKY_TOP = (18, 32, 92)
SKY_MID = (38, 76, 143)
SKY_HOR = (140, 205, 205)
SEA_TOP = (18, 62, 96)
SEA_BOT = (10, 42, 74)
WAVE_DEEP = (13, 84, 112)
WAVE_MID = (32, 148, 158)
WAVE_LIGHT = (90, 205, 200)
FOAM = (244, 254, 255)
FOAM_SH = (190, 230, 235)
MOON = (255, 233, 168)
MOON_GLOW = (255, 207, 94)
BOAT_WOOD = (107, 63, 29)
SAIL = (246, 234, 208)
PLAQUE = (238, 228, 200)
INK = (26, 26, 46)


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------

def draw_scene(cv, rng):
    # ---- museum wall and floor -------------------------------------------
    cv.vgrad(0, 0, W, 852, WALL_TOP, WALL_BOT)
    cv.vgrad(0, 852, W, H, FLOOR_TOP, FLOOR_BOT)
    # faint wall panels
    for x0 in (96, 928):
        cv.vgrad(x0, 40, x0 + 2, 820, (30, 35, 78), (12, 13, 38))
    # floor sheen band
    cv.vgrad(0, 852, W, 876, (40, 48, 96), (18, 21, 50))
    cv.hline(0, W - 1, 852, (120, 130, 180), 0.35)

    # ---- the framed painting (tilted a touch for dynamism) ---------------
    fx, fy = 512, 402          # frame centre
    fw, fh = 668, 512          # frame outer size
    ang = -5.0
    # drop shadow on the wall
    shadow = rot_rect(fx + 14, fy + 18, fw, fh, ang)
    cv.poly(shadow, (0, 0, 0), 0.45)
    # gold frame: dark outer, bright middle, dark inner bevel
    cv.poly(rot_rect(fx, fy, fw, fh, ang), GOLD_DARK)
    cv.poly(rot_rect(fx, fy, fw - 14, fh - 14, ang), GOLD)
    cv.poly(rot_rect(fx, fy, fw - 26, fh - 26, ang), GOLD_LIGHT)
    cv.poly(rot_rect(fx, fy, fw - 34, fh - 34, ang), GOLD_DARK)
    # corner ornaments
    for cx, cy in rot_rect(fx, fy, fw - 20, fh - 20, ang):
        cv.disc(cx, cy, 9, GOLD_LIGHT)
        cv.disc(cx, cy, 5, GOLD_DARK)
    # painting interior: night sky over a sea, moon at upper right
    inner = rot_rect(fx, fy, fw - 40, fh - 40, ang)
    cv.poly_grad(inner, SKY_TOP, SKY_HOR, fy - fh / 2, fy + fh / 2)
    # sea strip across the lower part of the painting, down to its bottom
    sea = rot_rect(fx, 566, fw - 40, 148, ang)
    cv.poly_grad(sea, SEA_TOP, SEA_BOT, 496, 640)
    # horizon shimmer
    for i, t in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
        x = 250 + i * 130
        cv.line(x, 545 + (i % 2) * 4, x + 90, 545 + (i % 2) * 4, 3,
                (220, 240, 235), 0.5)
    # stars inside the painting
    for _ in range(70):
        x = rng.uniform(230, 790)
        y = rng.uniform(175, 480)
        r = rng.choice((1, 1, 1, 2))
        cv.disc(x, y, r, (255, 250, 220), rng.uniform(0.4, 0.95))
    # a few thin wispy clouds
    for cx, cy, rx in ((330, 250, 70), (470, 210, 55), (620, 300, 48)):
        cv.ellipse(cx, cy, rx, 7, (200, 215, 235), 0.16)
        cv.ellipse(cx + 18, cy + 5, rx * 0.6, 5, (200, 215, 235), 0.13)

    # ---- the great moon ---------------------------------------------------
    mx, my = 688, 268
    cv.glow(mx, my, 190, MOON_GLOW, 0.5)
    cv.glow(mx, my, 120, MOON, 0.6)
    cv.disc(mx, my, 82, MOON)
    for cx, cy, r in ((660, 240, 12), (710, 290, 9), (688, 310, 6),
                      (720, 235, 7), (655, 292, 5)):
        cv.disc(cx, cy, r, (238, 205, 130), 0.55)

    # ---- the wave: a great curl bursting out of the frame -----------------
    # Body: a sweeping polygon from the lower-left of the painting, rising
    # to a curling crest that breaks past the frame's right edge.
    outer = bezier3((252, 640), (330, 420), (560, 250), (742, 238), 30)
    outer += bezier((742, 238), (838, 250), (838, 348), 16)
    outer += bezier((838, 348), (820, 420), (720, 430), 12)
    inner = bezier3((700, 452), (560, 470), (430, 560), (330, 648), 24)
    wave_pts = outer + inner
    cv.poly_grad(wave_pts, WAVE_MID, WAVE_DEEP, 230, 650)

    # crest curl: a tapering spiral tube curling inward over the frame edge,
    # with a dark hollow so the curl reads as a breaking wave, not a blob
    curl_cx, curl_cy = 786, 302
    for i in range(30):
        t = i / 29
        a = math.radians(195 - t * 320)
        rr = 66 - t * 40
        x = curl_cx + math.cos(a) * rr
        y = curl_cy + math.sin(a) * rr * 0.8
        r = 26 - t * 16
        cv.disc(x, y, r, mix(WAVE_LIGHT, WAVE_MID, t * 0.55))
    for i in range(18):
        t = i / 17
        a = math.radians(195 - t * 300)
        rr = 40 - t * 22
        x = curl_cx + math.cos(a) * rr
        y = curl_cy + math.sin(a) * rr * 0.8
        cv.disc(x, y, 5, (8, 52, 84), 0.55)
    # foam claws along the crest edge (Hokusai fingers): small tapered
    # fingers angled along the crest, each with a round tip
    claw_tips = [(742, 240), (790, 238), (826, 268), (838, 312),
                 (826, 356), (796, 392), (748, 414)]
    for i, (tx, ty) in enumerate(claw_tips):
        ang_c = math.radians(-50 - i * 12)
        ln = 34 - i * 2
        wd = 9 - i * 0.5
        dx, dy = math.cos(ang_c), math.sin(ang_c)
        px_, py_ = -dy, dx
        bx, by = tx - dx * ln, ty - dy * ln
        cv.poly([(bx + px_ * wd, by + py_ * wd),
                 (tx + px_ * wd * 0.4, ty + py_ * wd * 0.4),
                 (tx - px_ * wd * 0.4, ty - py_ * wd * 0.4),
                 (bx - px_ * wd, by - py_ * wd)], FOAM)
        cv.disc(tx, ty, 8 - i * 0.5, FOAM)
    # foam rim along the outer edge of the wave: a continuous bright edge
    # with a few scattered droplets, not a dotted string
    rim = bezier3((252, 640), (330, 420), (560, 250), (742, 238), 40)
    cv.polyline(rim, 5, FOAM, 0.85)
    for i in range(0, len(rim), 6):
        x, y = rim[i]
        cv.disc(x + 6, y + 8, 3, FOAM_SH, 0.7)
    # inner shadow curves following the swell
    for off, wdt in ((26, 7), (52, 5), (80, 4)):
        pts = bezier3((268 + off, 636), (352 + off, 430), (560, 268 + off),
                      (716, 262 + off), 30)
        cv.polyline(pts, wdt, (8, 52, 84), 0.45)
    # pale light catching the wave face
    pts = bezier3((300, 620), (380, 450), (560, 300), (700, 280), 26)
    cv.polyline(pts, 10, (150, 225, 215), 0.35)

    # ---- spray exploding toward the viewer --------------------------------
    for _ in range(150):
        t = rng.random()
        a = math.radians(rng.uniform(-18, 62))
        d = 40 + t * 300
        x = 830 + math.cos(a) * d
        y = 330 + math.sin(a) * d * 1.15 + t * 90
        r = rng.uniform(1.0, 5.5) * (1.0 - t * 0.55)
        cv.disc(x, y, max(1, r), FOAM, rng.uniform(0.45, 0.95))
    for _ in range(12):
        x = rng.uniform(840, 990)
        y = rng.uniform(380, 600)
        cv.line(x, y, x + rng.uniform(10, 26), y + rng.uniform(3, 12),
                2, FOAM, 0.5)
    # water pouring over the frame's lower edge onto the floor: a narrow,
    # wavy stream rather than a straight ribbon
    pour = [(566, 638), (610, 646), (636, 700), (612, 772), (640, 850),
            (668, 900), (640, 912), (600, 856), (582, 780), (574, 706),
            (548, 652)]
    cv.poly(pour, mix(WAVE_MID, WAVE_LIGHT, 0.35), 0.92)
    cv.polyline([(586, 660), (612, 730), (626, 852)], 3, FOAM, 0.65)
    cv.polyline([(600, 668), (592, 740), (606, 856)], 3, FOAM, 0.45)
    for i, (dx, dy) in enumerate(((648, 880), (664, 896), (622, 892))):
        cv.disc(dx, dy, 5 - i, FOAM, 0.7)
    # puddle on the floor with a moon-gold reflection
    cv.ellipse(668, 918, 150, 26, mix(WAVE_DEEP, (20, 30, 70), 0.4), 0.9)
    cv.ellipse(700, 916, 90, 16, MOON_GLOW, 0.28)
    cv.ellipse(640, 920, 60, 10, FOAM, 0.25)

    # ---- the tiny boat riding the crest ------------------------------------
    bx, by = 668, 436
    a = math.radians(-24)
    ca, sa = math.cos(a), math.sin(a)

    def rot(px, py):
        return (bx + px * ca - py * sa, by + px * sa + py * ca)

    hull = [rot(-46, 0), rot(46, -7), rot(36, 12), rot(-36, 14)]
    cv.poly(hull, BOAT_WOOD)
    cv.polyline([rot(-46, 0), rot(46, -7)], 3, (60, 32, 12), 0.8)
    # mast and sail
    cv.line(rot(2, -4)[0], rot(2, -4)[1], rot(7, -62)[0], rot(7, -62)[1],
            4, (70, 40, 16))
    sail = [rot(7, -60), rot(42, -7), rot(9, -9)]
    cv.poly(sail, SAIL)
    cv.polyline([rot(7, -60), rot(42, -7), rot(9, -9), rot(7, -60)],
                2, (180, 160, 120), 0.7)
    # lantern glow at the bow
    lx, ly = rot(37, -16)
    cv.glow(lx, ly, 26, (255, 217, 77), 0.8)
    cv.disc(lx, ly, 6, (255, 230, 120))
    # wake foam behind the boat
    for i in range(8):
        cv.disc(bx - 44 - i * 9, by + 12 + i * 2, 5 - i * 0.4, FOAM, 0.8)

    # ---- museum plaque ------------------------------------------------------
    px0, py0 = 392, 668
    pw, ph = 240, 52
    cv.poly([(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph),
             (px0, py0 + ph)], PLAQUE)
    cv.polyline([(px0 + 4, py0 + 4), (px0 + pw - 4, py0 + 4),
                 (px0 + pw - 4, py0 + ph - 4), (px0 + 4, py0 + ph - 4),
                 (px0 + 4, py0 + 4)], 2, (150, 130, 90), 0.9)
    label = "IT ESCAPED!"
    tw = text_width(label, 3)
    draw_text(cv, label, px0 + (pw - tw) // 2, py0 + 14, 3, INK)

    # ---- floor reflections of the burst -------------------------------------
    cv.ellipse(760, 880, 170, 18, mix(WAVE_MID, (10, 20, 50), 0.5), 0.35)
    cv.ellipse(880, 900, 110, 14, FOAM, 0.12)

    # ---- vignette + faint grain ---------------------------------------------
    for y in range(H):
        for x in range(W):
            dx = (x - 512) / 512.0
            dy = (y - 512) / 512.0
            d2 = dx * dx + dy * dy
            if d2 > 0.55:
                f = 1.0 - min(0.28, (d2 - 0.55) * 0.35)
                i = (y * W + x) * 3
                cv.px[i] = int(cv.px[i] * f)
                cv.px[i + 1] = int(cv.px[i + 1] * f)
                cv.px[i + 2] = int(cv.px[i + 2] * f)
    for _ in range(9000):
        x = rng.randrange(W)
        y = rng.randrange(H)
        i = (y * W + x) * 3
        d = rng.randint(-7, 7)
        for k in range(3):
            cv.px[i + k] = max(0, min(255, cv.px[i + k] + d))

# --------------------------------------------------------------------------
# Minimal PNG writer (stdlib only): 8-bit RGB, one filter byte per row,
# per-row filter chosen by the usual minimum-absolute-sum heuristic.
# --------------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _filter_row(ftype, row, prev, bpp=3):
    out = bytearray(len(row))
    if ftype == 0:
        out[:] = row
    elif ftype == 1:  # Sub
        for i, v in enumerate(row):
            left = row[i - bpp] if i >= bpp else 0
            out[i] = (v - left) & 0xFF
    elif ftype == 2:  # Up
        for i, v in enumerate(row):
            out[i] = (v - prev[i]) & 0xFF
    elif ftype == 3:  # Average
        for i, v in enumerate(row):
            left = row[i - bpp] if i >= bpp else 0
            up = prev[i]
            out[i] = (v - ((left + up) // 2)) & 0xFF
    else:  # Paeth
        for i, v in enumerate(row):
            left = row[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            out[i] = (v - _paeth(left, up, up_left)) & 0xFF
    return out


def _filter_score(filtered):
    return sum(v if v < 128 else 256 - v for v in filtered)


def write_png(cv, path):
    w, h = cv.w, cv.h
    raw = bytearray()
    prev = bytes(w * 3)
    for y in range(h):
        row = bytes(cv.px[y * w * 3:(y + 1) * w * 3])
        best_ft, best_data, best_score = 0, None, None
        for ftype in (0, 1, 2, 3, 4):
            data = _filter_row(ftype, row, prev)
            s = _filter_score(data)
            if best_score is None or s < best_score:
                best_ft, best_data, best_score = ftype, data, s
        raw.append(best_ft)
        raw += best_data
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(ctype, data):
        c = struct.pack(">I", len(data)) + ctype + data
        c += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(20261116)
    cv = Canvas(W, H)
    draw_scene(cv, rng)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    print(f"wrote {path} ({W}x{H}, {size} bytes)")


if __name__ == "__main__":
    main()
