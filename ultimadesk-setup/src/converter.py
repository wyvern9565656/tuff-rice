#!/usr/bin/env python3
"""Converte um GeoJSON do Natural Earth em borders.txt (formato simples pro globo).

Uso: python3 converter.py ne_110m_admin_0_countries.geojson borders.txt
"""
import json
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "ne_110m_admin_0_countries.geojson"
dst = sys.argv[2] if len(sys.argv) > 2 else "borders.txt"

with open(src, encoding="utf-8") as f:
    data = json.load(f)

rings = []
for feat in data["features"]:
    geom = feat.get("geometry")
    if not geom:
        continue
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        continue
    for poly in polys:
        for ring in poly:
            rings.append(ring)

with open(dst, "w") as out:
    for ring in rings:
        out.write(f"{len(ring)}\n")
        for lon, lat, *_ in ring:
            out.write(f"{lon:.2f} {lat:.2f}\n")

print(f"{len(rings)} contornos escritos em {dst}")
