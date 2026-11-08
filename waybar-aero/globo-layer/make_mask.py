#!/usr/bin/env python3
"""Gera mask.bin (terra + bordas, 2048x1024, projecao equirretangular) a partir do
GeoJSON do Natural Earth. Baixa o arquivo sozinho se nao existir.

Uso: python3 make_mask.py [ne_110m_admin_0_countries.geojson] [mask.bin]
"""
import json
import math
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
MW, MH, SS = 2048, 1024, 2

src = sys.argv[1] if len(sys.argv) > 1 else "ne_110m_admin_0_countries.geojson"
dst = sys.argv[2] if len(sys.argv) > 2 else "mask.bin"
dst_countries = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(dst) or ".", "countries.tsv")

if not os.path.exists(src):
    print("baixando", URL)
    urllib.request.urlretrieve(URL, src)

with open(src, encoding="utf-8") as f:
    data = json.load(f)

W, H = MW * SS, MH * SS
land = Image.new("L", (W, H), 0)
bord = Image.new("L", (W, H), 0)
dl, db = ImageDraw.Draw(land), ImageDraw.Draw(bord)

def xy(ring):
    return [((lon + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H) for lon, lat, *_ in ring]

def parse_zone_coordinate(value):
    split = next(i for i in range(1, len(value)) if value[i] in "+-")

    def parse_part(part, degree_digits):
        sign = -1 if part[0] == "-" else 1
        digits = part[1:]
        degrees = int(digits[:degree_digits])
        minutes = int(digits[degree_digits:degree_digits + 2])
        seconds = int(digits[degree_digits + 2:] or "0")
        return sign * (degrees + minutes / 60.0 + seconds / 3600.0)

    return parse_part(value[:split], 2), parse_part(value[split:], 3)

def load_timezones():
    for path in ("/usr/share/zoneinfo/zone.tab", "/usr/share/zoneinfo/zone1970.tab"):
        if not os.path.exists(path):
            continue
        zones = {}
        with open(path, encoding="utf-8") as table:
            for line in table:
                if line.startswith("#"):
                    continue
                fields = line.rstrip().split("\t")
                if len(fields) < 3:
                    continue
                try:
                    latitude, longitude = parse_zone_coordinate(fields[1])
                except (StopIteration, ValueError):
                    continue
                for code in fields[0].split(","):
                    zones.setdefault(code, []).append((latitude, longitude, fields[2]))
        if zones:
            return zones
    return {}

for feat in data["features"]:
    g = feat.get("geometry")
    if not g:
        continue
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
    for poly in polys:
        for k, ring in enumerate(poly):
            pts = xy(ring)
            if len(pts) < 3:
                continue
            dl.polygon(pts, fill=255 if k == 0 else 0)   # anel externo = terra, buracos = lagos
            db.line(pts + [pts[0]], fill=255, width=SS * 2)

land = land.resize((MW, MH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.9))
bord = bord.resize((MW, MH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.7))
with open(dst, "wb") as out:
    out.write(land.tobytes())
    out.write(bord.tobytes())
print("mascara salva em", dst)

with open(dst_countries, "w", encoding="utf-8") as out:
    timezones = load_timezones()
    timezone_fallbacks = {
        "República Turca do Chipre do Norte": "Asia/Nicosia",
        "Somalilândia": "Africa/Mogadishu",
        "Kosovo": "Europe/Belgrade",
    }
    for feature in data["features"]:
        properties = feature.get("properties") or {}
        name = str(properties.get("NAME_PT") or properties.get("ADMIN") or "").replace("\t", " ").replace("\n", " ").strip()
        continent = str(properties.get("CONTINENT") or "")
        population = int(properties.get("POP_EST") or 0)
        latitude = properties.get("LABEL_Y")
        longitude = properties.get("LABEL_X")
        if not name or not continent or latitude is None or longitude is None:
            continue
        iso_code = properties.get("ISO_A2_EH")
        if not iso_code or iso_code in ("-99", "--"):
            iso_code = properties.get("ISO_A2")
        candidates = timezones.get(iso_code, [])
        if candidates:
            latitude_cosine = math.cos(math.radians(latitude))

            def distance(candidate):
                delta_longitude = abs(candidate[1] - longitude)
                delta_longitude = min(delta_longitude, 360.0 - delta_longitude)
                return (candidate[0] - latitude) ** 2 + (delta_longitude * latitude_cosine) ** 2

            timezone = min(candidates, key=distance)[2]
        else:
            timezone = timezone_fallbacks.get(name, "Etc/UTC")
        out.write(f"{name}\t{continent}\t{population}\t{latitude:.6f}\t{longitude:.6f}\t{timezone}\n")
print("dados de paises salvos em", dst_countries)
