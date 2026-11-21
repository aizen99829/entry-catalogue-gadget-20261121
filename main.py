#!/usr/bin/env python3
"""UPPOUR — catalogue photo of an impossible gadget.

A studio catalogue shot of the UPPOUR umbrella: an umbrella that
rains UPWARD. Rain rises from its canopy into a clear sky while a
single dry yellow rain boot stands beside it, untouched.

Pure standard library: the image is rasterised by hand and encoded
as PNG with zlib. Deterministic: same bytes on every run.
"""

import math
import os
import struct
import zlib

W = H = 1024


def clamp(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


def lerp(a, b, t):
    return clamp(a + (b - a) * t)


class Img:
    def __init__(self):
        self.buf = bytearray(W * H * 3)

    def px(self, x, y, r, g, b):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def blend(self, x, y, r, g, b, a):
        """Blend colour (r,g,b) over pixel (x,y) with alpha a in 0..1."""
        if 0 <= x < W and 0 <= y < H and a > 0:
            i = (y * W + x) * 3
            self.buf[i] = clamp(self.buf[i] * (1 - a) + r * a)
            self.buf[i + 1] = clamp(self.buf[i + 1] * (1 - a) + g * a)
            self.buf[i + 2] = clamp(self.buf[i + 2] * (1 - a) + b * a)

    def vgrad(self, top, bot, y0=0, y1=H):
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            c = (lerp(top[0], bot[0], t), lerp(top[1], bot[1], t),
                 lerp(top[2], bot[2], t))
            row = bytes(c) * W
            s = y * W * 3
            self.buf[s:s + W * 3] = row

    def ellipse(self, cx, cy, rx, ry, rgb):
        for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
            dy = (y - cy) / ry
            dx = math.sqrt(max(0.0, 1.0 - dy * dy)) * rx
            x0 = max(0, int(cx - dx))
            x1 = min(W - 1, int(cx + dx))
            s = (y * W + x0) * 3
            self.buf[s:(y * W + x1 + 1) * 3] = bytes(rgb) * (x1 - x0 + 1)

    def soft_ellipse(self, cx, cy, rx, ry, rgb, alpha):
        """Dark soft-edged ellipse (studio floor shadow)."""
        for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
            dy = (y - cy) / ry
            span = math.sqrt(max(0.0, 1.0 - dy * dy))
            for x in range(max(0, int(cx - rx * span)),
                           min(W - 1, int(cx + rx * span) + 1)):
                d = math.sqrt(((x - cx) / rx) ** 2 + dy * dy)
                a = alpha * max(0.0, 1.0 - d * d)
                self.blend(x, y, rgb[0], rgb[1], rgb[2], a)

    def disc(self, cx, cy, r, rgb):
        self.ellipse(cx, cy, r, r, rgb)

    def thick_line(self, x0, y0, x1, y1, r, rgb):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(steps + 1):
            t = i / steps
            self.disc(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
                      r, rgb)


# 5x7 bitmap font (letters needed for the brand mark).
FONT = {
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
}


def draw_text(img, text, cx, top, scale, rgb):
    """Centre `text` on cx, first row at `top`, slight arc like a canopy."""
    widths = [5 * scale + 2 * scale for _ in text]
    total = sum(widths) - 2 * scale
    x = cx - total // 2
    for ch in text:
        glyph = FONT[ch]
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "1":
                    arc = int(6 * math.cos((x + col * scale - cx) / 160.0))
                    for dy in range(scale):
                        for dx in range(scale):
                            img.px(x + col * scale + dx,
                                   top + row * scale + dy + arc,
                                   rgb[0], rgb[1], rgb[2])
        x += 7 * scale


def lcg(seed):
    while True:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        yield seed / 0x7FFFFFFF


def render():
    img = Img()
    # Studio sweep: warm light grey backdrop, soft floor below.
    img.vgrad((240, 238, 232), (216, 212, 205), 0, 780)
    img.vgrad((210, 206, 199), (196, 192, 186), 780, H)
    # Gentle radial light centred on the product.
    for y in range(80, 780, 2):
        for x in range(120, 904, 2):
            d = math.sqrt(((x - 512) / 480.0) ** 2 + ((y - 430) / 420.0) ** 2)
            if d < 1.0:
                a = 0.10 * (1.0 - d)
                img.blend(x, y, 255, 255, 250, a)
                img.blend(x + 1, y, 255, 255, 250, a)
                img.blend(x, y + 1, 255, 255, 250, a)
                img.blend(x + 1, y + 1, 255, 255, 250, a)
    # Floor shadows.
    img.soft_ellipse(512, 838, 300, 42, (90, 86, 80), 0.34)
    img.soft_ellipse(730, 838, 95, 20, (90, 86, 80), 0.30)

    # ---- Umbrella canopy: 8 panels, dome over (512, 470). ----
    apex = (512, 255)
    cx, cy, rx, ry = 512, 470, 310, 215
    panels = [(178, 32, 32), (199, 52, 44), (178, 32, 32), (199, 52, 44),
              (178, 32, 32), (199, 52, 44), (178, 32, 32), (199, 52, 44)]
    for x in range(cx - rx, cx + rx + 1):
        dx = (x - cx) / rx
        if abs(dx) >= 1.0:
            continue
        y_top = int(cy - ry * math.sqrt(1.0 - dx * dx))
        # Panel from the angle around the apex.
        ang = math.degrees(math.atan2(y_top - apex[1], x - apex[0]))
        frac = (ang + 75.0) / 150.0
        panel = min(7, max(0, int(frac * 8)))
        # Scalloped lower edge.
        y_bot = int(cy + 16 * (0.5 + 0.5 * math.cos(8 * math.radians(ang))))
        # Shading: brighter near the top-left light, darker at the rim.
        dist = math.sqrt((x - 400) ** 2 + (y_top - 300) ** 2) / 700.0
        shade = 1.18 - 0.42 * dist - 0.18 * abs(dx)
        base = panels[panel]
        col = (clamp(base[0] * shade), clamp(base[1] * shade),
               clamp(base[2] * shade))
        for y in range(y_top, y_bot + 1):
            img.px(x, y, col[0], col[1], col[2])
    # Ribs: thin darker seams from apex to rim. The apex sits on the
    # dome's ellipse, so each rib ends where its ray exits the ellipse.
    for k in range(9):
        ang = math.radians(10 + k * (160.0 / 8))
        c, s = math.cos(ang), math.sin(ang)
        a = c * c / (310.0 ** 2) + s * s / (215.0 ** 2)
        t = (2.0 * s / 215.0) / a
        # Never past the canopy's scalloped lower edge (y ~ 472).
        if s > 0:
            t = min(t, (472.0 - apex[1]) / s)
        ex = int(apex[0] + t * c)
        ey = int(apex[1] + t * s)
        img.thick_line(apex[0], apex[1], ex, ey, 2, (120, 22, 22))
    # Canopy rim highlight along the top-left.
    for x in range(cx - rx + 20, cx - 40):
        dx = (x - cx) / rx
        y_top = int(cy - ry * math.sqrt(max(0.0, 1.0 - dx * dx)))
        img.blend(x, y_top + 2, 255, 170, 160, 0.35)
        img.blend(x, y_top + 3, 255, 170, 160, 0.22)
    # Gold ferrule tip.
    img.ellipse(512, 246, 10, 16, (201, 162, 74))
    img.ellipse(509, 242, 4, 7, (238, 205, 120))

    # ---- Pole: brushed metal, apex down to the handle. ----
    for x in range(505, 520):
        t = abs(x - 512) / 7.0
        shade = 1.0 - 0.45 * t
        col = (clamp(196 * shade), clamp(198 * shade), clamp(202 * shade))
        for y in range(258, 800):
            img.px(x, y, col[0], col[1], col[2])
    img.thick_line(512, 258, 512, 798, 1, (228, 230, 233))

    # ---- Wooden J-hook handle. ----
    hook = [(512, 800), (512, 838), (500, 862), (478, 868),
            (460, 856), (456, 838), (466, 826)]
    for i in range(len(hook) - 1):
        img.thick_line(hook[i][0], hook[i][1], hook[i + 1][0],
                        hook[i + 1][1], 10, (122, 82, 44))
        img.thick_line(hook[i][0], hook[i][1], hook[i + 1][0],
                        hook[i + 1][1], 6, (146, 102, 58))

    # ---- Rain going UP: droplets rising off the canopy. ----
    rnd = lcg(987654321)
    for _ in range(64):
        u = next(rnd)
        x = int(300 + u * 424)
        y = int(46 + next(rnd) * 190)
        s = 3 + int(next(rnd) * 6)
        a = 0.55 + 0.45 * (1.0 - (y - 46) / 190.0)
        for dy in range(-s, s + 1):
            for dx in range(-s // 2, s // 2 + 1):
                if (dx * 2) ** 2 + dy * dy <= s * s:
                    img.blend(x + dx, y + dy, 140, 195, 232, a * 0.9)
        img.blend(x - 1, y - s, 255, 255, 255, a)
    # A few droplets still rising from below the rim.
    for _ in range(10):
        x = int(260 + next(rnd) * 504)
        y = int(500 + next(rnd) * 90)
        s = 3 + int(next(rnd) * 4)
        img.ellipse(x, y, s // 2 + 1, s, (140, 195, 232))
        img.blend(x - 1, y - s, 255, 255, 255, 0.9)

    # ---- Brand mark on the centre canopy panel. ----
    draw_text(img, "UPPOUR", 512, 322, 4, (250, 244, 238))

    # ---- Accessory: one dry yellow rain boot, standing right. ----
    bx = 700
    # Shaft.
    for y in range(700, 828):
        for x in range(bx + 8, bx + 66):
            shade = 1.0 - 0.22 * ((x - (bx + 8)) / 58.0)
            img.px(x, y, clamp(234 * shade), clamp(192 * shade),
                   clamp(42 * shade))
    # Rounded shaft top.
    img.ellipse(bx + 37, 700, 29, 10, (234, 192, 42))
    img.ellipse(bx + 37, 700, 29, 10, (234, 192, 42))
    # Foot: toe pointing left.
    for y in range(786, 830):
        t = (y - 786) / 44.0
        x0 = int(bx + 8 - 52 * (1.0 - t * 0.4))
        x1 = bx + 66
        for x in range(x0, x1):
            shade = 1.0 - 0.18 * ((x - x0) / max(1, x1 - x0))
            img.px(x, y, clamp(234 * shade), clamp(192 * shade),
                   clamp(42 * shade))
    img.ellipse(bx - 40, 806, 14, 20, (234, 192, 42))
    # Sole.
    for y in range(828, 838):
        for x in range(bx - 46, bx + 68):
            img.px(x, y, 58, 48, 38)
    # Highlight stripe on the shaft.
    for y in range(706, 824):
        img.blend(bx + 20, y, 255, 236, 130, 0.55)
        img.blend(bx + 21, y, 255, 236, 130, 0.35)
    # Pull tab.
    img.thick_line(bx + 62, 700, bx + 74, 686, 4, (200, 160, 32))

    # ---- Photographic grain. ----
    rnd = lcg(12345)
    for _ in range(6000):
        x = int(next(rnd) * W)
        y = int(next(rnd) * H)
        n = int((next(rnd) - 0.5) * 14)
        i = (y * W + x) * 3
        img.buf[i] = clamp(img.buf[i] + n)
        img.buf[i + 1] = clamp(img.buf[i + 1] + n)
        img.buf[i + 2] = clamp(img.buf[i + 2] + n)

    return img


def write_png(path, img):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += img.buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    img = render()
    size = write_png("/output/entry.png", img)
    print("wrote /output/entry.png", size, "bytes")


if __name__ == "__main__":
    main()
