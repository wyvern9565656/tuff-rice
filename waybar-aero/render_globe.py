#!/usr/bin/env python3
"""Gera um video em loop (mp4) de um papel de parede Frutiger Aero com o globo
(so contornos, meia-esfera encostada na barra lateral) girando.

O globo vira parte do papel de parede: fica SEMPRE atras das janelas, nao bloqueia
cliques e usa pouquissimo CPU. Use com mpvpaper.

Uso:
  python3 render_globe.py                       # usa ~/.local/share/ultimadesk/globe/borders.txt
  python3 render_globe.py --bg minha_imagem.jpg # usa sua imagem de fundo
  python3 render_globe.py --secs 2 --out teste.mp4   # teste rapido
"""
import argparse
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("--borders", default=os.path.expanduser("~/.local/share/ultimadesk/globe/borders.txt"))
ap.add_argument("--bg", default=None, help="imagem de fundo (senao gera um ceu Frutiger Aero)")
ap.add_argument("--out", default=os.path.expanduser("~/.config/waybar-aero/globo.mp4"))
ap.add_argument("--w", type=int, default=1368)
ap.add_argument("--h", type=int, default=768)
ap.add_argument("--cx", type=int, default=58, help="x do centro do globo (borda direita da barra lateral)")
ap.add_argument("--cy", type=int, default=403, help="y do centro do globo")
ap.add_argument("--R", type=int, default=290, help="raio do globo em pixels")
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--secs", type=int, default=30, help="duracao = uma volta completa (loop perfeito)")
ap.add_argument("--tilt", type=float, default=23.4)
ap.add_argument("--tint", type=int, default=38, help="opacidade (0-255) do vidro azul dentro do globo")
ap.add_argument("--bg-only", default=None, help="so salva o fundo (PNG) neste caminho e sai")
ap.add_argument("--frame", default=None, help="so salva o primeiro quadro neste PNG e sai (preview)")
a = ap.parse_args()

W, H, R, SS = a.w, a.h, a.R, 3

# ---------- contornos ----------
lines = []
tok = []
if not a.bg_only:
    with open(a.borders) as f:
        tok = f.read().split()
i = 0
while i < len(tok):
    n = int(tok[i]); i += 1
    pts = []
    for _ in range(n):
        lon = math.radians(float(tok[i])); lat = math.radians(float(tok[i + 1])); i += 2
        pts.append((math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)))
    lines.append(pts)

# ---------- fundo ----------
def make_bg():
    if a.bg:
        im = Image.open(a.bg).convert("RGBA")
        s = max(W / im.width, H / im.height)
        im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2
        return im.crop((l, t, l + W, t + H))
    S = 2
    w, h = W * S, H * S
    im = Image.new("RGBA", (w, h))
    px = im.load()
    stops = [(0.0, (22, 112, 208)), (0.55, (92, 188, 246)), (1.0, (214, 243, 255))]
    for y in range(h):
        t = y / (h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                u = (t - t0) / (t1 - t0)
                col = tuple(int(c0[k] + (c1[k] - c0[k]) * u) for k in range(3))
                break
        for x in range(w):
            px[x, y] = col + (255,)
    # brilho do sol
    glow = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    ImageDraw.Draw(glow).ellipse((w * 0.62, -h * 0.25, w * 1.05, h * 0.35), fill=(255, 255, 255, 120))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70 * S)))
    # nuvens
    cl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    cd = ImageDraw.Draw(cl)
    rc = random.Random(11)
    for (bx, by) in [(0.30, 0.14), (0.58, 0.07), (0.82, 0.22), (0.46, 0.34)]:
        for _ in range(6):
            ex, ey = bx * w + rc.randint(-90, 90) * S, by * h + rc.randint(-18, 18) * S
            rw, rh = rc.randint(70, 140) * S, rc.randint(24, 46) * S
            cd.ellipse((ex - rw, ey - rh, ex + rw, ey + rh), fill=(255, 255, 255, 190))
    im.alpha_composite(cl.filter(ImageFilter.GaussianBlur(14 * S)))
    # colinas
    d = ImageDraw.Draw(im)
    d.ellipse((-w * 0.2, h * 0.80, w * 0.75, h * 1.5), fill=(70, 178, 70, 255))
    d.ellipse((w * 0.35, h * 0.86, w * 1.3, h * 1.6), fill=(46, 150, 62, 255))
    d.arc((-w * 0.2, h * 0.80, w * 0.75, h * 1.5), 200, 340, fill=(190, 255, 170, 255), width=3 * S)
    # bolhas
    rnd = random.Random(7)
    bub = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bub)
    for _ in range(26):
        r = rnd.randint(10, 70) * S
        x, y = rnd.randint(int(w * 0.25), w), rnd.randint(0, int(h * 0.85))
        bd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 28), outline=(255, 255, 255, 150), width=2 * S)
        bd.ellipse((x - r * 0.65, y - r * 0.75, x - r * 0.15, y - r * 0.4), fill=(255, 255, 255, 120))
    im.alpha_composite(bub)
    return im.resize((W, H), Image.LANCZOS)

bg = make_bg()
if a.bg_only:
    os.makedirs(os.path.dirname(os.path.abspath(a.bg_only)), exist_ok=True)
    bg.convert("RGB").save(a.bg_only)
    print("fundo salvo em", a.bg_only)
    sys.exit(0)

# ---------- globo ----------
tilt = math.radians(a.tilt)
ct, st = math.cos(tilt), math.sin(tilt)
pad = 6
pw, ph = R + pad, 2 * R + 2 * pad     # so a metade direita
px0, py0 = a.cx, a.cy - R - pad

def render_globe(ang):
    ca, sa = math.cos(ang), math.sin(ang)
    patch = Image.new("RGBA", (pw * SS, ph * SS), (210, 240, 255, 0))
    d = ImageDraw.Draw(patch)
    c = (0, (R + pad) * SS)
    bbox = (c[0] - R * SS, c[1] - R * SS, c[0] + R * SS, c[1] + R * SS)
    d.pieslice(bbox, -90, 90, fill=(20, 90, 170, a.tint))          # vidro
    back_c = (230, 250, 255, 38)
    for pts in lines:
        proj = []
        for (bx, by, bz) in pts:
            x = bx * ca + bz * sa
            z = bz * ca - bx * sa
            X = x * ct - by * st
            Y = x * st + by * ct
            proj.append((c[0] + X * R * SS, c[1] - Y * R * SS, z, X))
        for p, q in zip(proj, proj[1:]):
            if p[3] < -0.01 and q[3] < -0.01:
                continue                                           # metade escondida
            fp, fq = p[2] > 0, q[2] > 0
            seg = (p[0], p[1], q[0], q[1])
            if fp and fq:
                d.line(seg, fill=(10, 70, 140, 110), width=int(2.8 * SS))
                d.line(seg, fill=(255, 255, 255, 235), width=int(1.4 * SS))
            elif not fp and not fq:
                d.line(seg, fill=back_c, width=int(1.0 * SS))
    d.arc((bbox[0] - 2 * SS, bbox[1] - 2 * SS, bbox[2] + 2 * SS, bbox[3] + 2 * SS), -90, 90, fill=(150, 220, 255, 90), width=int(4 * SS))
    d.arc(bbox, -90, 90, fill=(255, 255, 255, 240), width=int(2.2 * SS))
    return patch.resize((pw, ph), Image.LANCZOS)

def frame(i, n):
    f = bg.copy()
    f.alpha_composite(render_globe(2 * math.pi * i / n), (px0, py0))
    return f

n = a.fps * a.secs
if a.frame:
    frame(0, n).convert("RGB").save(a.frame)
    print("preview salvo em", a.frame)
    sys.exit(0)

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
ff = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
     "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
     "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out],
    stdin=subprocess.PIPE)
for i in range(n):
    ff.stdin.write(frame(i, n).convert("RGB").tobytes())
    if i % 48 == 0:
        print(f"quadro {i}/{n}", flush=True)
ff.stdin.close()
ff.wait()
print("pronto:", a.out)
