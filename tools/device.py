"""rev. 0.12: the owner's device (Mírë Nolmeo, v12) as flat colour regions for the inlaid plaque on the case.
The SVG is rendered (rsvg-convert), every pixel is given the nearest colour of the drawing's own palette, the edges are
cleaned by a majority filter and every colour is traced into polygons (OpenCV). The polygons, in the SVG's units with
the centre of the lozenge at the origin and y up, are written to data/device/device_regions.json; the model builds the
plaque from that file and needs neither rsvg nor OpenCV.
Usage: python3 -I tools/device.py data/device/nyankonyan_elvish_device_v12_rope.svg data/device/device_regions.json"""
import sys, os, re, json, subprocess, tempfile
import numpy as np
import cv2

SRC, OUT = sys.argv[1:3]
PX = 6                       # pixels per SVG unit
VB = (60.0, 20.0, 560.0, 560.0)
CENTRE = (340.0, 300.0)      # centre of the lozenge (points 340,30 610,300 340,570 70,300)
svg = open(SRC, encoding='utf-8').read()
pal = []
for c in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{6})"', svg):
    c = c.lower()
    if c not in pal:
        pal.append(c)
P = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in pal], float)
with tempfile.TemporaryDirectory() as td:
    png = os.path.join(td, 'd.png')
    subprocess.run(['rsvg-convert', '-w', str(int(VB[2] * PX)), '-h', str(int(VB[3] * PX)), '-o', png, SRC], check=True)
    img = cv2.imread(png, cv2.IMREAD_UNCHANGED)          # BGRA
rgb = img[:, :, 2::-1].astype(float); a = img[:, :, 3]
H, W = a.shape
lab = np.full((H, W), -1, np.int32)
m = a > 127
d = ((rgb[m][:, None, :] - P[None]) ** 2).sum(-1)
lab[m] = d.argmin(1)
# majority filter: anti-aliased edges pick odd colours; every pixel takes the commonest label of its 5x5 neighbourhood
K = len(pal)
for _ in range(2):
    cnt = np.zeros((K + 1, H, W), np.float32)
    for k in range(-1, K):
        cnt[k + 1] = cv2.boxFilter((lab == k).astype(np.float32), -1, (5, 5), normalize=False)
    lab = cnt.argmax(0).astype(np.int32) - 1
lum = lambda c: (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0
regions = []
for k, c in enumerate(pal):
    mk = (lab == k).astype(np.uint8)
    if mk.sum() < 4 * PX * PX:
        continue
    cs, hier = cv2.findContours(mk, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        continue
    hier = hier[0]
    polys = []
    for i, cnt_ in enumerate(cs):
        if hier[i][3] != -1:           # a hole: attached to its parent below
            continue
        if cv2.contourArea(cnt_) < 2.0 * PX * PX:
            continue
        rings = [cnt_]
        j = hier[i][2]
        while j != -1:
            if cv2.contourArea(cs[j]) >= 1.0 * PX * PX:
                rings.append(cs[j])
            j = hier[j][0]
        out = []
        for r in rings:
            r = cv2.approxPolyDP(r, 1.2, True)[:, 0, :].astype(float)
            if len(r) < 3:
                continue
            x = (r[:, 0] + 0.5) / PX + VB[0] - CENTRE[0]
            y = -((r[:, 1] + 0.5) / PX + VB[1] - CENTRE[1])
            out.append([[round(float(u), 1), round(float(v), 1)] for u, v in zip(x, y)])
        if out:
            polys.append(out)
    if polys:
        regions.append(dict(color=c, lum=round(lum(P[k]), 3), polys=polys))
json.dump(dict(source=os.path.basename(SRC), units='svg', half_diagonal=270.0, regions=regions), open(OUT, 'w'), separators=(',', ':'))
print(len(regions), 'colours,', sum(len(r['polys']) for r in regions), 'polygons,', os.path.getsize(OUT) // 1024, 'kB')
