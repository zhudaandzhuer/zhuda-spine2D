"""Zhuda battle: pose drawings (gen/*.png, edits of the full-body base built from the user's design) -> parts/.

Each pose is one whole-figure drawing.  They are registered on the snout (size + centre x) and the hooves' ground line,
so swapping drawings keeps the character the same size and standing on the same floor.  Paper colour is removed from
every edge (no white fringe on dark backgrounds).  Effects (slash arc, impact, magic circle, orb, sparkles, burst) are
drawn here.

    python3 extract.py  ->  parts/*.png + parts/manifest.json + extract-report.json + evidence/extract/poses.png
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

HERE = Path(__file__).resolve().parent
GEN, OUT, EV = HERE / "gen", HERE / "parts", HERE / "evidence" / "extract"
W, H = 1024, 1536
POSES = {"base": "base.png", "stance": "stance_01.png", "windup": "windup_02.png", "smash": "smash_01.png",
         "cast_raise": "cast_raise_01.png", "cast_push": "cast_push_01.png"}


def load(f):
    return np.asarray(Image.open(GEN / f).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32)


def alpha_of(rgb):
    border = np.concatenate([rgb[:10].reshape(-1, 3), rgb[:, :10].reshape(-1, 3), rgb[:, -10:].reshape(-1, 3), rgb[-10:].reshape(-1, 3)])
    bg = np.median(border, 0)
    d = np.sqrt(((rgb - bg) ** 2).sum(-1))
    solid = d > 26
    lab, n = ndimage.label(solid)
    s = ndimage.sum(solid, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(s >= s.max() * 0.02)[0])
    filled = ndimage.binary_fill_holes(keep)
    holes, nh = ndimage.label(filled & ~keep)
    core = keep.copy()
    for i in range(1, nh + 1):                       # a hole of paper colour (between raised arms and head) stays open;
        hm = holes == i                              # a pale hole (the belly patch) is part of the pig
        if float(np.median(d[hm])) > 10:
            core |= hm
    a = np.clip((d - 8) / 20.0, 0, 1)
    near = ndimage.binary_dilation(core, iterations=3)
    a = np.where(core, 1.0, np.where(near, a, 0.0))
    return a, bg


def decontam(rgb, a, bg):
    a = np.minimum(a, ndimage.grey_erosion(a, size=3))
    a3 = a[..., None]
    out = np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), rgb)
    return np.clip(out, 0, 255), a


def _brown_blobs(rgb, a):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (a > 0.9) & (R > 80) & (R < 175) & (G < 105) & (B < 95) & (R - B > 30)
    lab, n = ndimage.label(m)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        area = int((lab[sl] == i + 1).sum())
        if area > 300:
            out.append(dict(x0=sl[1].start, y0=sl[0].start, x1=sl[1].stop, y1=sl[0].stop, area=area))
    return out


def snout(rgb, a):
    """snout centre and scale from the two nostrils: a pair of similar dark blobs side by side, closest to centre"""
    bl = [b for b in _brown_blobs(rgb, a) if 800 < b["area"] < 3000 and (b["y1"] - b["y0"]) > (b["x1"] - b["x0"]) * 1.2]
    best = None
    for i in range(len(bl)):
        for j in range(i + 1, len(bl)):
            p, q = bl[i], bl[j]
            cy1, cy2 = (p["y0"] + p["y1"]) / 2, (q["y0"] + q["y1"]) / 2
            cx1, cx2 = (p["x0"] + p["x1"]) / 2, (q["x0"] + q["x1"]) / 2
            if abs(cy1 - cy2) > 12 or not 35 < abs(cx1 - cx2) < 110:
                continue
            score = abs((cx1 + cx2) / 2 - W / 2)
            if best is None or score < best[0]:
                best = (score, (cx1 + cx2) / 2, (cy1 + cy2) / 2, abs(cx1 - cx2))
    return best[1], best[2], best[3]


def ground(rgb, a):
    """lowest row of the hooves: flat brown blobs (the club's knobbly end is long and is skipped)"""
    sx, sy, _ = snout(rgb, a)
    feet = [b for b in _brown_blobs(rgb, a) if 800 < b["area"] < 7000 and (b["y1"] - b["y0"]) <= (b["x1"] - b["x0"]) * 0.9 and b["y0"] > sy + 240]
    return float(max(b["y1"] for b in feet))


def place(rgb, a, sc, dx, dy):
    """scale about (0,0) by sc then shift by (dx, dy), on the W x H canvas"""
    rgba = np.dstack([rgb, a * 255]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")
    inv = (1 / sc, 0, -dx / sc, 0, 1 / sc, -dy / sc)
    out = im.transform((W, H), Image.AFFINE, inv, resample=Image.BICUBIC)
    o = np.asarray(out).astype(np.float32)
    return o[..., :3], o[..., 3] / 255


def save_part(name, rgb, a, parts):
    ys, xs = np.where(a > 0.01)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    arr = np.dstack([rgb, a * 255])[y0:y1, x0:x1]
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})


# ------------------------------------------------------------------------------------------- effects
def canvas(w, h, S=3):
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im), S


def fx_save(name, im, S, parts, cx, cy, blur=0):
    im = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    arr = np.asarray(im).astype(np.float32)
    x0, y0 = int(cx - im.width / 2), int(cy - im.height / 2)
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": x0, "y": y0, "w": im.width, "h": im.height})


def glow(d, S, cx, cy, r, col, steps=10, a0=180):
    for i in range(steps, 0, -1):
        rr = r * i / steps
        al = int(a0 * (1 - i / steps) ** 1.2 + 10)
        d.ellipse(((cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S), fill=col + (al,))


def star4(d, S, cx, cy, r, col, w=0.22):
    pts = []
    for k in range(8):
        ang = math.pi / 4 * k - math.pi / 2
        rr = r if k % 2 == 0 else r * w
        pts.append(((cx + rr * math.cos(ang)) * S, (cy + rr * math.sin(ang)) * S))
    d.polygon(pts, fill=col)


def draw_effects(parts, rep):
    # slash arc: a crescent sweeping from the upper left over the head down to the club's impact point
    w, h = 900, 900
    im, d, S = canvas(w, h)
    cx, cy, R = 450, 470, 400
    n = 60
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        a0, a1 = -150 + 230 * t0, -150 + 230 * t1
        thick = 95 * math.sin(math.pi * t0) ** 0.8 + 6
        alpha = int(235 * (t0 ** 0.6))
        for (rr, col) in ((R, (255, 250, 225)), (R - thick * 0.35, (255, 225, 140))):
            p0 = (cx + rr * math.cos(math.radians(a0)), cy + rr * math.sin(math.radians(a0)))
            p1 = (cx + rr * math.cos(math.radians(a1)), cy + rr * math.sin(math.radians(a1)))
            q1 = (cx + (rr - thick) * math.cos(math.radians(a1)), cy + (rr - thick) * math.sin(math.radians(a1)))
            q0 = (cx + (rr - thick) * math.cos(math.radians(a0)), cy + (rr - thick) * math.sin(math.radians(a0)))
            d.polygon([(x * S, y * S) for x, y in (p0, p1, q1, q0)], fill=col + (alpha,))
    fx_save("fx_slash", im, S, parts, rep["slash_c"][0], rep["slash_c"][1], blur=1.2)

    # impact burst at the club's head
    im, d, S = canvas(420, 420)
    glow(d, S, 210, 210, 150, (255, 230, 150), a0=200)
    for k in range(10):
        ang = 2 * math.pi * k / 10 + 0.2
        r0, r1 = 70, 190 if k % 2 == 0 else 140
        p = [(210 + r0 * math.cos(ang - 0.12), 210 + r0 * math.sin(ang - 0.12)), (210 + r1 * math.cos(ang), 210 + r1 * math.sin(ang)),
             (210 + r0 * math.cos(ang + 0.12), 210 + r0 * math.sin(ang + 0.12))]
        d.polygon([(x * S, y * S) for x, y in p], fill=(255, 245, 200, 240))
    star4(d, S, 210, 210, 80, (255, 255, 245, 255), 0.3)
    fx_save("fx_impact", im, S, parts, *rep["impact_c"], blur=0.8)

    # dust puffs at the feet
    for side, sx in (("L", -1), ("R", 1)):
        im, d, S = canvas(260, 160)
        for (x, y, r) in ((130, 110, 46), (90 + 60 * (sx < 0), 90, 34), (170 - 60 * (sx < 0), 100, 30), (130 + 50 * sx, 70, 24)):
            d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(236, 220, 200, 230), outline=(170, 140, 120, 255), width=3 * S)
        fx_save(f"fx_dust_{side}", im, S, parts, rep["ground_x"] + sx * 230, rep["ground_y"] - 50)

    # ground shadow (always on): tells the eye where the floor is, so the club tip below the feet reads as nearer the camera
    im, d, S = canvas(520, 120)
    for i in range(12, 0, -1):
        rx, ry = 250 * i / 12, 46 * i / 12
        d.ellipse(((260 - rx) * S, (60 - ry) * S, (260 + rx) * S, (60 + ry) * S), fill=(20, 14, 30, int(14 + 8 * (12 - i))))
    fx_save("shadow", im, S, parts, rep["ground_x"], rep["ground_y"] + 4, blur=2)

    # magic circle (seen from the camera, slightly from above: an ellipse on the floor)
    im, d, S = canvas(760, 760)
    c = 380
    col, col2 = (255, 140, 200), (255, 220, 120)
    glow(d, S, c, c, 375, (255, 120, 190), a0=90)
    for r_, wdt, cc in ((360, 14, col), (330, 7, col2), (250, 9, col), (150, 7, col2)):
        d.ellipse(((c - r_) * S, (c - r_) * S, (c + r_) * S, (c + r_) * S), outline=cc + (255,), width=wdt * S)
    for k in range(6):                                            # hexagram
        a1, a2 = math.radians(60 * k - 90), math.radians(60 * (k + 2) - 90)
        d.line(((c + 250 * math.cos(a1)) * S, (c + 250 * math.sin(a1)) * S, (c + 250 * math.cos(a2)) * S, (c + 250 * math.sin(a2)) * S), fill=col2 + (255,), width=7 * S)
    for k in range(24):                                           # rune ticks
        a1 = math.radians(15 * k)
        r0, r1 = 333, 357 if k % 2 else 345
        d.line(((c + r0 * math.cos(a1)) * S, (c + r0 * math.sin(a1)) * S, (c + r1 * math.cos(a1)) * S, (c + r1 * math.sin(a1)) * S), fill=col + (255,), width=5 * S)
    for k in range(6):
        a1 = math.radians(60 * k + 30)
        star4(d, S, c + 290 * math.cos(a1), c + 290 * math.sin(a1), 22, col2 + (255,))
    fx_save("fx_circle", im, S, parts, rep["ground_x"], rep["ground_y"] - 10, blur=1.0)

    # energy orb (core + halo) and its burst
    im, d, S = canvas(440, 440)
    glow(d, S, 220, 220, 215, (255, 90, 170), a0=230, steps=14)
    glow(d, S, 220, 220, 120, (255, 190, 225), a0=255)
    d.ellipse((168 * S, 168 * S, 272 * S, 272 * S), fill=(255, 255, 255, 255))
    star4(d, S, 220, 220, 170, (255, 240, 250, 230), 0.1)
    fx_save("fx_orb", im, S, parts, *rep["orb_c"], blur=1.5)
    im, d, S = canvas(560, 560)
    glow(d, S, 280, 280, 270, (255, 110, 190), a0=230, steps=14)
    for k in range(12):
        ang = 2 * math.pi * k / 12
        star4(d, S, 280 + 190 * math.cos(ang), 280 + 190 * math.sin(ang), 40 if k % 2 else 26, (255, 240, 250, 255))
    star4(d, S, 280, 280, 140, (255, 255, 255, 240), 0.18)
    fx_save("fx_burst", im, S, parts, rep["orb_c"][0] + 520, rep["orb_c"][1], blur=1.0)

    # sparkles rising around the caster (a ring of 8 small stars, animated by their bone)
    im, d, S = canvas(700, 300)
    rng = np.random.default_rng(3)
    for k in range(14):
        x, y = rng.uniform(40, 660), rng.uniform(30, 270)
        r_ = rng.uniform(10, 24)
        star4(d, S, x, y, r_, (255, 235, 150, 255) if k % 2 else (255, 170, 220, 255))
    fx_save("fx_sparkles", im, S, parts, rep["ground_x"], rep["ground_y"] - 260, blur=0.6)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    parts, rep = [], {"poses": {}}
    ref = None
    placed = {}
    for name, f in POSES.items():
        rgb = load(f)
        a, bg = alpha_of(rgb)
        rgb, a = decontam(rgb, a, bg)
        sx, sy, sw = snout(rgb, a)
        gy = ground(rgb, a)
        if ref is None:
            ref = dict(sx=sx, sw=sw, gy=gy)
        sc = ref["sw"] / sw
        dx, dy = ref["sx"] - sx * sc, ref["gy"] - gy * sc
        prgb, pa = place(rgb, a, sc, dx, dy)
        placed[name] = (prgb, pa)
        save_part(f"pose_{name}", prgb, pa, parts)
        rep["poses"][name] = {"snout_w": round(sw, 1), "scale": round(sc, 3), "dx": round(dx, 1), "dy": round(dy, 1), "ground": round(gy, 1)}
    rep["ground_x"], rep["ground_y"] = round(ref["sx"]), round(ref["gy"])

    # where effects sit: club head in the smash pose (light-brown blob lowest-right), hooves in cast poses
    rgb, a = placed["smash"]
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    wood = (a > 0.9) & (R > 170) & (G > 120) & (G < 200) & (B < 150) & (R - B > 60)
    ys, xs = np.where(wood)
    k = np.argsort(-(xs + ys))[:400]
    rep["impact_c"] = [float(xs[k].mean()), float(ys[k].mean())]
    rep["slash_c"] = [rep["ground_x"] + 60, rep["impact_c"][1] - 340]
    rgb, a = placed["cast_raise"]
    ys, xs = np.where(a > 0.5)
    rep["orb_raise_c"] = [float(rep["ground_x"]), float(ys.min() - 90)]
    rgb, a = placed["cast_push"]
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hoof = (a > 0.9) & (R > 80) & (R < 175) & (G < 105) & (B < 95) & (R - B > 30) & (np.arange(H)[:, None] < rep["ground_y"] - 150)
    ys, xs = np.where(hoof)
    rep["orb_c"] = [float(xs.mean() + 70), float(ys.mean())]
    draw_effects(parts, rep)

    order = ["shadow", "fx_circle", "fx_slash"] + [f"pose_{n}" for n in POSES] + ["fx_dust_L", "fx_dust_R", "fx_impact", "fx_sparkles", "fx_orb", "fx_burst"]
    parts.sort(key=lambda q: order.index(q["name"]))
    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "extract.py", "parts": parts}, indent=1))
    (HERE / "extract-report.json").write_text(json.dumps(rep, indent=1))
    sheet = Image.new("RGBA", (W * 6 // 3, H * 1 // 3), (30, 35, 50, 255))
    for i, name in enumerate(POSES):
        rgb, a = placed[name]
        im = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA").resize((W // 3, H // 3), Image.LANCZOS)
        sheet.alpha_composite(im, (i * W // 3, 0))
    d = ImageDraw.Draw(sheet)
    d.line((0, rep["ground_y"] / 3, sheet.width, rep["ground_y"] / 3), fill=(120, 200, 255, 255), width=1)
    sheet.save(EV / "poses.png")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
