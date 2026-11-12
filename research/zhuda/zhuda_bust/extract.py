"""Zhuda bust: parts cut from the user's design sheet pixels (src/sheet_pitch.png), nothing regenerated.

    python3 extract.py   ->  parts/*.png + parts/manifest.json  (canvas = the level panel at 3x)

Level / up / down heads come from the sheet's three front panels (registered on the body), the body from the
level panel.  Eyes, brows and mouth are lifted off each head (the skin under them filled from the surrounding skin,
a few px wide), so they can be swapped for expressions.  Snout, blush and the forehead highlights stay on the head.
Expression alternates (closed / happy eyes, open mouths ...) are drawn here in the sheet's line colour and weight.
"""
import json
import sys
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SRC, OUT, EV = HERE / "src", HERE / "parts", HERE / "evidence" / "extract"
K = 3                                    # working scale (sheet px x 3)
BOX = {"level": (130, 160, 470, 478), "up": (545, 160, 870, 478), "down": (980, 160, 1310, 478)}
LINE = (96, 52, 44)
WAVE_SPLIT = 720                         # rows below this belong to the body side in the wave pose, above to the arm                      # outline / feature line colour (sampled below and checked)


def panel(name):
    im = Image.open(SRC / "sheet_pitch.png").convert("RGB").crop(BOX[name])
    return np.asarray(im.resize((im.width * K, im.height * K), Image.LANCZOS)).astype(np.float32)


def pig_alpha(rgb):
    """Alpha from the cream background: soft ramp on colour distance, largest blob only."""
    H, W = rgb.shape[:2]
    border = np.concatenate([rgb[:8].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
    bg = np.median(border, 0)
    d = np.sqrt(((rgb - bg) ** 2).sum(-1))
    solid = d > 28
    lab, n = ndimage.label(solid)
    big = 1 + int(np.argmax(ndimage.sum(solid, lab, range(1, n + 1))))
    core = lab == big
    # the panel crops the body at the bottom edge: close it there so the pale belly (close to the background) is inside
    last = int(np.where(core.any(1))[0].max())
    for r in range(last - 6, last + 1):
        xs = np.where(core[r])[0]
        if len(xs):
            core[r, xs.min():xs.max() + 1] = True
    core = ndimage.binary_fill_holes(core)
    a = np.clip((d - 8) / 22.0, 0, 1)
    near = ndimage.binary_dilation(core, iterations=3)
    a = np.where(core, 1.0, np.where(near, a, 0.0))
    return a, bg


def lum(rgb):
    return rgb @ np.array([0.299, 0.587, 0.114])


def inpaint(rgb, mask, r=6):
    m = (mask > 0).astype(np.uint8) * 255
    out = cv2.inpaint(np.clip(rgb, 0, 255).astype(np.uint8), m, r, cv2.INPAINT_TELEA)
    return out.astype(np.float32)


def remove_guides(rgb, alpha):
    """the level panel has four dashed guide lines entering the head from the left"""
    L = lum(rgb)
    m = np.zeros(L.shape, bool)
    for y in (231, 361, 493, 623):
        band = np.zeros_like(m)
        band[y - 7:y + 8, :275] = True
        m |= band & (L > 120) & (L < 222) & (alpha > 0.5)
    m = ndimage.binary_dilation(m, iterations=2) & (lum(rgb) > 110)
    return inpaint(rgb, m, 5), m


def register(ref, mov, rows=(760, 925), cols=(140, 880)):
    """shift (dx, dy) that puts `mov` on `ref`, matched on the body (which does not move between panels)"""
    a = lum(ref)[rows[0]:rows[1], cols[0]:cols[1]].astype(np.float32)
    best = None
    g = lum(mov).astype(np.float32)
    for dy in range(-30, 31, 1):
        for dx in range(-30, 31, 2):
            y0, x0 = rows[0] - dy, cols[0] - dx
            if y0 < 0 or x0 < 0 or y0 + a.shape[0] > g.shape[0] or x0 + a.shape[1] > g.shape[1]:
                continue
            b = g[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
            e = float(np.abs(a - b).mean())
            if best is None or e < best[0]:
                best = (e, dx, dy)
    e, dx, dy = best
    for ddx in (-1, 1):                                    # refine x
        y0, x0 = rows[0] - dy, cols[0] - (dx + ddx)
        b = g[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
        e2 = float(np.abs(a - b).mean())
        if e2 < e:
            e, dx = e2, dx + ddx
    return dx, dy, e


def shift(img, dx, dy, H, W):
    out = np.zeros((H, W) + img.shape[2:], img.dtype)
    sh, sw = img.shape[:2]
    ys0, xs0 = max(0, -dy), max(0, -dx)
    yd0, xd0 = max(0, dy), max(0, dx)
    h = min(sh - ys0, H - yd0)
    w = min(sw - xs0, W - xd0)
    out[yd0:yd0 + h, xd0:xd0 + w] = img[ys0:ys0 + h, xs0:xs0 + w]
    return out


def chin_curve(rgb, alpha, x0=150, x1=870, band=(630, 745)):
    """y of the head's bottom outline per column (darkest pixel in the band, smoothed)"""
    L = lum(rgb)
    ys = np.full(rgb.shape[1], -1.0)
    for x in range(x0, x1):
        col = L[band[0]:band[1], x]
        if alpha[band[0]:band[1], x].mean() < 0.5:
            continue
        ys[x] = band[0] + int(np.argmin(col))
    good = ys >= 0
    xs = np.arange(len(ys))
    # robust smoothing: median filter then polynomial
    yy = ndimage.median_filter(ys[good], size=31)
    p = np.polyfit(xs[good], yy, 4)
    return p, xs[good].min(), xs[good].max()


def head_mask(alpha, p, xa, xb, H, W, pad=4):
    yy, xx = np.mgrid[0:H, 0:W]
    cy = np.polyval(p, np.clip(xx, xa, xb))
    m = (alpha > 0.02) & (yy <= cy + pad)
    solid = (alpha > 0.35) & m
    lab, n = ndimage.label(solid)
    if n > 1:
        solid = lab == 1 + int(np.argmax(ndimage.sum(solid, lab, range(1, n + 1))))
    return m & ndimage.binary_dilation(solid, iterations=3)     # soft edge kept, faint specks outside it dropped


def save_part(name, rgba, parts, crop=True):
    a = rgba[..., 3]
    ys, xs = np.where(a > 2)
    if not len(ys):
        raise SystemExit(f"{name}: empty")
    x0, y0, x1, y1 = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if crop else (0, 0, rgba.shape[1], rgba.shape[0])
    Image.fromarray(np.clip(rgba[y0:y1, x0:x1], 0, 255).astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})


def decontam(rgb, a, bg):
    """Edge pixels are a mix of pig and the cream paper: remove the paper's share from the colour (so the edge does not
    glow white on a dark background) and pull the soft edge in by ~1 px."""
    a = np.minimum(a, ndimage.grey_erosion(a, size=3))
    a3 = a[..., None]
    out = np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), rgb)
    return np.clip(out, 0, 255), a


def rgba(rgb, a):
    return np.dstack([rgb, np.clip(a, 0, 1) * 255])


# ------------------------------------------------------------------------------- drawn expression parts
def stroke_layer(H, W, draw_fn, blur=0.9):
    S = 4
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), S)
    im = im.resize((W, H), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))      # the sheet's lines are soft, painted
    return np.asarray(im).astype(np.float32)


def arcpts(cx, cy, rx, ry, a0, a1, n=40):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def poly_stroke(d, S, pts, w, col):
    p = [(x * S, y * S) for x, y in pts]
    d.line(p, fill=col, width=int(w * S), joint="curve")
    r = w * S / 2
    for x, y in (p[0], p[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    lv = panel("level")
    H, W = lv.shape[:2]
    a_lv, bg = pig_alpha(lv)
    lv, a_lv = decontam(lv, a_lv, bg)
    # guide lines are horizontal: in each band, every column is re-filled by interpolating straight down from the clean
    # pixels just above to the clean pixels just below (colour and alpha) -- outlines crossing the band stay continuous
    guide = np.zeros(a_lv.shape, bool)
    for gy in (231, 361, 493, 623):
        y0, y1 = gy - 6, gy + 6
        for y in range(y0 + 1, y1):
            t_ = (y - y0) / (y1 - y0)
            lv[y, :300] = lv[y0, :300] * (1 - t_) + lv[y1, :300] * t_
            a_lv[y, :300] = a_lv[y0, :300] * (1 - t_) + a_lv[y1, :300] * t_
            guide[y, :300] = True

    report = {"canvas": [W, H], "guides_inpainted_px": int(guide.sum())}

    heads, feats = {}, {}
    for name in ("level", "up", "down"):
        rgb = lv if name == "level" else panel(name)
        if name == "level":
            a = a_lv
        else:
            a, bgp = pig_alpha(rgb)
            rgb, a = decontam(rgb, a, bgp)
        if name != "level":
            dx, dy, e = register(lv, rgb)
            report[f"register_{name}"] = {"dx": dx, "dy": dy, "err": round(e, 2)}
            rgb, a = shift(rgb, dx, dy, H, W), shift(a, dx, dy, H, W)
        p, xa, xb = chin_curve(rgb, a)
        hm = head_mask(a, p, xa, xb, H, W)
        heads[name] = (rgb, a, hm, p, xa, xb)

    # ---------------- face features on each head: dark marks inside boxes found from the level head layout
    def dark_marks(rgb, a, hm, box, thr=110):
        x0, y0, x1, y1 = box
        L = lum(rgb)
        m = np.zeros(L.shape, bool)
        m[y0:y1, x0:x1] = (L[y0:y1, x0:x1] < thr) & hm[y0:y1, x0:x1]
        lab, n = ndimage.label(m)
        if not n:
            return m
        s = ndimage.sum(m, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(s >= max(20, s.max() * 0.15))[0])
        return keep

    # feature boxes per head (3x canvas coords; read off the grid of each panel)
    FB = {"level": {"eye_L": (395, 352, 450, 402), "eye_R": (573, 352, 628, 402), "brow_L": (380, 312, 452, 352), "brow_R": (568, 312, 642, 352), "mouth": (445, 585, 575, 625)}}
    parts = []
    lvl = heads["level"]
    rgb, a, hm = lvl[0], lvl[1], lvl[2]
    masks = {k: dark_marks(rgb, a, hm, b) for k, b in FB["level"].items()}
    for k in ("eye_L", "eye_R"):                               # include the eye's white highlight dot
        x0, y0, x1, y1 = FB["level"][k]
        m = masks[k]
        filled = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=3))
        masks[k] = filled
    feat_rgba = {}
    allm = np.zeros((H, W), bool)
    for k, m in masks.items():
        md = ndimage.binary_dilation(m, iterations=3)
        allm |= md
        soft = ndimage.gaussian_filter(md.astype(np.float32), 1.2)
        feat_rgba[k] = rgba(rgb, np.clip(soft * 1.6, 0, 1) * (hm > 0))
        ys, xs = np.where(m)
        feats[k] = dict(cx=float(xs.mean()), cy=float(ys.mean()), w=int(xs.max() - xs.min() + 1), h=int(ys.max() - ys.min() + 1))
    # fill the skin where eyes / brows / mouth were: wide mask, then smooth only inside it (no halo of the old lines)
    fm = ndimage.binary_dilation(allm, iterations=7)
    blank = inpaint(rgb, fm, 12)
    sm = ndimage.gaussian_filter(blank, sigma=(6, 6, 0))
    w_ = ndimage.gaussian_filter(fm.astype(np.float32), 3)[..., None]
    blank = blank * (1 - w_) + sm * w_
    report["features"] = feats

    # sample the real line colour from the brows / mouth
    sel = masks["brow_L"] | masks["mouth"]
    line_col = tuple(int(v) for v in np.median(rgb[sel], 0))
    eye_col = tuple(int(v) for v in np.median(rgb[masks["eye_L"] & (lum(rgb) < 90)], 0))
    report["line_colour"], report["eye_colour"] = line_col, eye_col
    LW = 2.0 * K                                                 # line width of brows / mouth on the sheet (~2 px)

    # ---------------- body: level pixels below the chin, extended upward under the head; arms cut off for waving
    p, xa, xb = lvl[3], lvl[4], lvl[5]
    yy, xx = np.mgrid[0:H, 0:W]
    chin = np.polyval(p, np.clip(xx, xa, xb))
    body_m = (a > 0.02) & (yy > chin - 2)
    body_rgb = rgb.copy()
    # extend the body upward under the head: copy the row 14 px below the chin up to 150 px above it
    ext_a = a.copy()
    for x in range(W):
        if x < xa or x > xb:
            continue
        c = int(np.polyval(p, x))
        src_y = min(H - 1, c + 14)
        if a[src_y, x] < 0.5:
            continue
        for y in range(max(0, c - 150), c + 14):
            body_rgb[y, x] = rgb[src_y, x]
            ext_a[y, x] = 1.0
            body_m[y, x] = True

    ARM = {"R": [(742, 712), (796, 688), (832, 752), (856, 826), (868, 884), (864, 930), (772, 930), (786, 896), (776, 840), (764, 790), (748, 748)],
           "L": [(280, 712), (226, 688), (190, 752), (166, 826), (154, 884), (158, 930), (250, 930), (236, 896), (246, 840), (258, 790), (274, 748)]}
    arm_masks = {}
    for s, poly in ARM.items():
        im = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).polygon(poly, fill=255)
        am = (np.asarray(im) > 127) & (a > 0.02) & (yy > chin - 2)
        arm_masks[s] = am
    body_only = body_m & ~arm_masks["L"] & ~arm_masks["R"]
    body_a = np.where(body_only, ext_a, 0.0)
    # where an arm was cut away, the torso needs its own outline: draw it along the cut (inner edge of the arm polygon)
    def torso_edge(d, S):
        for s, poly in ARM.items():
            inner = poly[6:] + [poly[0]]                       # from the hoof up along the inner line to the shoulder
            poly_stroke(d, S, inner[::-1][:4], LW * 0.8, line_col + (150,))
    edge = stroke_layer(H, W, torso_edge, blur=0.8)
    ea = edge[..., 3:4] / 255 * (body_a[..., None] > 0)
    body_rgb2 = body_rgb * (1 - ea) + edge[..., :3] * ea
    save_part("body", rgba(body_rgb2, body_a), parts)

    # arms: own pixels + a rounded skin cap at the shoulder end + an outline along the cut
    skin = np.median(rgb[(yy > 700) & (yy < 760) & (xx > 300) & (xx < 340)], 0)
    for s in "LR":
        am = arm_masks[s]
        cap = Image.new("L", (W, H), 0)
        x0, y0 = ARM[s][0]
        x1, y1 = ARM[s][1]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 8
        inward = 16 if s == "R" else -16                       # keep the cap inside the body outline
        ImageDraw.Draw(cap).ellipse((cx - inward - 22, cy - 6, cx - inward + 22, cy + 30), fill=255)
        capm = (np.asarray(cap) > 127) & ~am & body_only
        arm_rgb = np.where(capm[..., None], skin, rgb)
        arm_a = np.where(am, a, 0.0) + np.where(capm, 1.0, 0.0)
        def arm_edge(d, S, s=s):
            poly = ARM[s]
            inner = poly[6:] + [poly[0]]
            poly_stroke(d, S, inner, LW, line_col + (255,))
        e2 = stroke_layer(H, W, arm_edge, blur=0.8)
        ea2 = e2[..., 3:4] / 255 * (arm_a[..., None] > 0)
        arm_rgb = arm_rgb * (1 - ea2) + e2[..., :3] * ea2
        save_part(f"arm_{s}", rgba(arm_rgb, np.clip(arm_a, 0, 1)), parts)
        report[f"arm_{s}_pivot"] = [cx, cy]

    # ---------------- heads (level = blank, features separate; up / down keep their drawn faces)
    save_part("head_level", rgba(blank, np.where(lvl[2], a, 0.0)), parts)
    for name in ("up", "down"):
        rgbh, ah, hmh = heads[name][:3]
        save_part(f"head_{name}", rgba(rgbh, np.where(hmh, ah, 0.0)), parts)

    # ---------------- face parts of the level head: originals + drawn alternates in the same line style
    E = {s: feats[f"eye_{s}"] for s in "LR"}
    B = {s: feats[f"brow_{s}"] for s in "LR"}
    M = feats["mouth"]
    er = max(E["L"]["w"], E["L"]["h"]) / 2
    face = {}
    for s in "LR":
        face[f"eye_{s}_open"] = feat_rgba[f"eye_{s}"]
        face[f"brow_{s}_soft"] = feat_rgba[f"brow_{s}"]
    face["mouth_smile"] = feat_rgba["mouth"]

    def draw_eye(kind, s):
        cx, cy = E[s]["cx"], E[s]["cy"]
        sg = 1 if s == "L" else -1
        def f(d, S):
            col = eye_col + (255,)
            if kind == "closed":
                poly_stroke(d, S, arcpts(cx, cy - 2, er * 1.25, er * 0.55, 200, 340)[::-1], LW, line_col + (255,))
                poly_stroke(d, S, arcpts(cx, cy - 10, er * 1.15, er * 0.75, 20, 160), LW, line_col + (255,))
            elif kind == "happy":
                poly_stroke(d, S, arcpts(cx, cy + 8, er * 1.2, er * 1.0, 200, 340), LW * 1.1, line_col + (255,))
            elif kind == "wide":
                r = er * 1.35
                d.ellipse(((cx - r) * S, (cy - r * 1.08) * S, (cx + r) * S, (cy + r * 1.08) * S), fill=col)
                d.ellipse(((cx - r * 0.1) * S, (cy - r * 0.75) * S, (cx + r * 0.45) * S, (cy - r * 0.2) * S), fill=(255, 255, 255, 255))
            elif kind == "sad":
                d.chord(((cx - er) * S, (cy - er) * S, (cx + er) * S, (cy + er * 1.05) * S), 0, 180, fill=col)
                poly_stroke(d, S, [(cx - er * 1.2, cy - 1), (cx + er * 1.2, cy - 1)], LW, line_col + (255,))
            elif kind == "cry":
                poly_stroke(d, S, [(cx - er * 1.0 * sg, cy - er * 0.8), (cx + er * 0.8 * sg, cy), (cx - er * 1.0 * sg, cy + er * 0.8)], LW * 1.1, line_col + (255,))
        return stroke_layer(H, W, f)

    def draw_brow(kind, s):
        cx, cy, bw = B[s]["cx"], B[s]["cy"], B[s]["w"]
        sg = 1 if s == "L" else -1                              # +x is toward the face centre for the left brow
        def f(d, S):
            c = line_col + (255,)
            if kind == "angry":
                poly_stroke(d, S, [(cx - bw * 0.45 * sg, cy - 9), (cx + bw * 0.4 * sg, cy + 7)], LW, c)
            elif kind == "sad":
                poly_stroke(d, S, [(cx - bw * 0.45 * sg, cy + 7), (cx + bw * 0.4 * sg, cy - 9)], LW, c)
            elif kind == "up":
                poly_stroke(d, S, arcpts(cx, cy - 4, bw * 0.48, 12, 200, 340), LW, c)
        return stroke_layer(H, W, f)

    def draw_mouth(kind):
        cx, cy, mw = M["cx"], M["cy"], M["w"]
        def f(d, S):
            c = line_col + (255,)
            inner, tongue = (150, 62, 62, 255), (236, 132, 136, 255)
            if kind == "flat":
                poly_stroke(d, S, [(cx - mw * 0.28, cy + 2), (cx + mw * 0.28, cy + 2)], LW, c)
            elif kind == "frown":
                poly_stroke(d, S, arcpts(cx, cy + 22, mw * 0.36, 18, 205, 335), LW, c)
            elif kind in ("open_s", "open_m", "o", "laugh", "wail"):
                rx, ry = {"open_s": (mw * 0.2, 12), "open_m": (mw * 0.28, 20), "o": (mw * 0.16, 16), "laugh": (mw * 0.4, 30), "wail": (mw * 0.34, 26)}[kind]
                if kind == "laugh":
                    box = ((cx - rx) * S, (cy - ry * 0.9) * S, (cx + rx) * S, (cy + ry * 1.1) * S)
                    d.chord(box, 0, 180, fill=inner, outline=c, width=int(LW * S))
                    d.chord(((cx - rx * 0.55) * S, (cy + ry * 0.2) * S, (cx + rx * 0.55) * S, (cy + ry * 1.1) * S), 180, 360, fill=tongue)
                elif kind == "wail":
                    box = ((cx - rx) * S, (cy - ry * 0.4) * S, (cx + rx) * S, (cy + ry * 1.6) * S)
                    d.chord(box, 180, 360, fill=inner, outline=c, width=int(LW * S))
                else:
                    d.ellipse(((cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S), fill=inner, outline=c, width=int(LW * S))
                    if kind == "open_m":
                        d.chord(((cx - rx * 0.6) * S, cy * S, (cx + rx * 0.6) * S, (cy + ry * 0.95) * S), 0, 180, fill=tongue)
        return stroke_layer(H, W, f)

    for s in "LR":
        for k in ("closed", "happy", "wide", "sad", "cry"):
            face[f"eye_{s}_{k}"] = draw_eye(k, s)
        for k in ("angry", "sad", "up"):
            face[f"brow_{s}_{k}"] = draw_brow(k, s)
    for k in ("flat", "frown", "open_s", "open_m", "o", "laugh", "wail"):
        face[f"mouth_{k}"] = draw_mouth(k)

    def extras(d, S):
        pass
    # shy: three little strokes over each existing blush (the sheet's blush is already strong)
    for s, bx in (("L", 262), ("R", 762)):
        def f(d, S, bx=bx):
            for i in range(3):
                x = bx - 28 + i * 28
                poly_stroke(d, S, [(x + 7, 470), (x - 7, 506)], LW * 0.8, (206, 96, 104, 255))
        face[f"shy_{s}"] = stroke_layer(H, W, f)
    for s in "LR":
        cx, cy = E[s]["cx"], E[s]["cy"]
        def f(d, S, cx=cx, cy=cy):
            d.rounded_rectangle(((cx - 9) * S, (cy + er + 2) * S, (cx + 9) * S, (cy + er + 120) * S), radius=9 * S, fill=(150, 205, 240, 235), outline=(90, 150, 210, 255), width=int(2 * S))
        face[f"tear_{s}"] = stroke_layer(H, W, f, blur=0.6)

    order = ["eye_L_open", "eye_L_closed", "eye_L_happy", "eye_L_wide", "eye_L_sad", "eye_L_cry",
             "eye_R_open", "eye_R_closed", "eye_R_happy", "eye_R_wide", "eye_R_sad", "eye_R_cry",
             "brow_L_soft", "brow_L_angry", "brow_L_sad", "brow_L_up", "brow_R_soft", "brow_R_angry", "brow_R_sad", "brow_R_up",
             "mouth_smile", "mouth_flat", "mouth_frown", "mouth_open_s", "mouth_open_m", "mouth_o", "mouth_laugh", "mouth_wail",
             "shy_L", "shy_R", "tear_L", "tear_R"]
    for n in order:
        save_part(n, face[n], parts)

    # draw order: body, arms (lowered arms sit beside the body; a raised arm goes in front by draw-order key), heads, face
    # ---------------- wave pose, from gen/wave_01_reg.png (the sheet panel edited ONLY to raise the right arm; checked
    # against the original: outside the arm the edit differs by thin re-drawn edge lines only).  Two parts:
    #   wave_body_R  the body side where the arm used to hang (rigid on the body, opaque, feathered into the body)
    #   wave_arm_R   the raised arm, outside the head, its base hidden under wave_body_R; it swings about the shoulder
    head_full = ndimage.binary_dilation(lvl[2] & (a > 0.5), iterations=2)
    inner_head = ndimage.binary_erosion(lvl[2] & (a > 0.5), iterations=4)
    yy, xx = np.mgrid[0:H, 0:W]
    chin = np.polyval(lvl[3], np.clip(xx, lvl[4], lvl[5]))
    feather = np.clip((xx - 660) / 40.0, 0, 1)
    report["wave_frames"] = {}
    for src, suf in (("wave_01_reg.png", ""), ("wave_02_reg.png", "2")):
        wv = HERE / "gen" / src
        if not wv.is_file():
            continue
        wrgb = np.asarray(Image.open(wv).convert("RGB")).astype(np.float32)
        wa, wbg = pig_alpha(wrgb)
        wrgb, wa = decontam(wrgb, wa, wbg)
        side = (xx >= 660) & (yy > chin + 8) & ((yy >= WAVE_SPLIT) | (xx < 772))   # body side, below the head's own chin line
        save_part(f"wave_body_R{suf}", rgba(wrgb, np.where(side, wa * feather, 0.0)), parts)
        arm = (xx >= 700) & (yy >= 300) & (yy < WAVE_SPLIT + 50) & ~inner_head
        lab, n = ndimage.label(arm & (wa > 0.5))
        big = lab == 1 + int(np.argmax(ndimage.sum(lab > 0, lab, range(1, n + 1))))
        armm = ndimage.binary_dilation(big, iterations=3) & arm
        skin_c = np.median(wrgb[(yy > 780) & (yy < 840) & (xx > 700) & (xx < 760) & (wa > 0.9)], 0)
        save_part(f"wave_arm_R{suf}", rgba(wrgb, np.where(armm, wa, 0.0)), parts)
        base = ndimage.binary_dilation(armm & (yy > chin - 30) & (yy < WAVE_SPLIT + 40), iterations=10) & (yy > chin - 40) & (wa > 0.5)
        save_part(f"wave_back_R{suf}", rgba(np.ones_like(wrgb) * skin_c, ndimage.gaussian_filter(base.astype(np.float32), 1.0)), parts)
        ys, xs = np.where(big)
        d = np.abs(wrgb - lv).sum(-1)
        keep = (a > 0.5) & ~((xx >= 660) & (yy >= 300))
        report["wave_frames"][src] = {"arm_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "diff_outside_arm": round(float(d[keep].mean()), 2)}

    import turn as _turn
    _turn.add_turn(sys.modules[__name__], parts, H, W, report)

    rank = {"arm_L": 0, "arm_R": 1, "body": 2, "wave_back_R": 3, "wave_back_R2": 3.1, "wave_arm_R": 4, "wave_arm_R2": 4.1, "wave_body_R": 5, "wave_body_R2": 5.1, "head_level": 5, "head_up": 50, "head_down": 51, "turn_q": 60, "turn_q_R": 60, "turn_side": 60, "turn_side_R": 60}
    parts.sort(key=lambda q: rank.get(q["name"], 10))
    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "extract.py (pixels from src/sheet_pitch.png)", "parts": parts}, indent=1))
    report["parts"] = len(parts)
    report["chin_level"] = [float(np.polyval(lvl[3], x)) for x in (300, 512, 700)]
    (HERE / "extract-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))

    # evidence: the level panel recomposed from the parts vs the original
    comp = np.zeros((H, W, 4), np.float32)
    for q in parts:
        if q["name"] in ("body", "arm_L", "arm_R", "head_level", "eye_L_open", "eye_R_open", "brow_L_soft", "brow_R_soft", "mouth_smile"):
            im = np.asarray(Image.open(OUT / q["file"])).astype(np.float32)
            y0, x0 = q["y"], q["x"]
            sl = comp[y0:y0 + q["h"], x0:x0 + q["w"]]
            al = im[..., 3:4] / 255
            sl[..., :3] = sl[..., :3] * (1 - al) + im[..., :3] * al
            sl[..., 3:4] = sl[..., 3:4] + (1 - sl[..., 3:4] / 255) * al * 255
    orig = panel("level")
    comp_on = comp[..., :3] * (comp[..., 3:4] / 255) + bg * (1 - comp[..., 3:4] / 255)
    diff = np.abs(comp_on - orig).sum(-1)
    pig = a_lv > 0.5
    report["recompose_mean_abs_on_pig"] = round(float(diff[pig].mean()), 2)
    report["recompose_px_over_30"] = round(float((diff[pig] > 30).mean()), 4)
    sheet = np.concatenate([orig, comp_on, np.clip(np.repeat(diff[..., None], 3, -1) * 4, 0, 255)], 1)
    Image.fromarray(sheet.astype(np.uint8)).save(EV / "recompose_level.png")
    (HERE / "extract-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "features"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
