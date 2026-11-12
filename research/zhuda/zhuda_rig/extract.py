"""Zhuda (豬大) skeletal rig parts.  Base = gen/base.png (full body built from the user's design).

Layers with hidden areas filled in were generated as edits of the base (head without ears / face, torso continued
under the head, legs continued into the body) and are registered back onto the base by features:
    head  <- the two blush blobs (spacing = scale, centre = position)
    torso <- the pale belly patch (bbox)
    legs  <- the two hooves
Arms, ears and face features are cut from the base itself (pixels the other layers do not explain); arms get a rounded
skin cap at the shoulder so the pivot sits inside the body.  The club comes from gen/club_01.png.
Expression alternates (eyes / brows / mouth) are drawn in the base's line colour.

    python3 extract.py   ->  parts/ + parts/manifest.json + extract-report.json + evidence/extract/*.png
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
REP = {}


def load(f, size=(W, H)):
    im = Image.open(GEN / f).convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im).astype(np.float32)


def alpha_of(rgb, thr=26, hole_keep=10):
    border = np.concatenate([rgb[:10].reshape(-1, 3), rgb[:, :10].reshape(-1, 3), rgb[:, -10:].reshape(-1, 3), rgb[-10:].reshape(-1, 3)])
    bg = np.median(border, 0)
    d = np.sqrt(((rgb - bg) ** 2).sum(-1))
    solid = d > thr
    lab, n = ndimage.label(solid)
    s = ndimage.sum(solid, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(s >= s.max() * 0.01)[0])
    filled = ndimage.binary_fill_holes(keep)
    holes, nh = ndimage.label(filled & ~keep)
    core = keep.copy()
    for i in range(1, nh + 1):
        hm = holes == i
        if float(np.median(d[hm])) > hole_keep:
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


def place(rgb, a, sc, dx, dy, size=(W, H)):
    im = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
    out = im.transform(size, Image.AFFINE, (1 / sc, 0, -dx / sc, 0, 1 / sc, -dy / sc), resample=Image.BICUBIC)
    o = np.asarray(out).astype(np.float32)
    return o[..., :3], o[..., 3] / 255


def blobs(mask, min_area=200):
    lab, n = ndimage.label(mask)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        m = lab[sl] == i + 1
        area = int(m.sum())
        if area >= min_area:
            ys, xs = np.nonzero(m)
            out.append(dict(x0=sl[1].start, y0=sl[0].start, x1=sl[1].stop, y1=sl[0].stop, cx=sl[1].start + xs.mean(), cy=sl[0].start + ys.mean(), area=area, id=i + 1))
    return out


def blush(rgb, a):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (a > 0.9) & (R > 225) & (G < 175) & (G > 110) & (R - G > 70) & (B > 120)
    m = ndimage.binary_opening(m, iterations=3)
    b = sorted(blobs(m, 1500), key=lambda q: -q["area"])[:6]
    # the two blushes: similar size, similar height, far apart
    best = None
    for i in range(len(b)):
        for j in range(i + 1, len(b)):
            p, q = b[i], b[j]
            if abs(p["cy"] - q["cy"]) < 40 and abs(p["cx"] - q["cx"]) > 200:
                sc = p["area"] + q["area"]
                if best is None or sc > best[0]:
                    best = (sc, p, q)
    p, q = sorted(best[1:], key=lambda z: z["cx"])
    return (p["cx"] + q["cx"]) / 2, (p["cy"] + q["cy"]) / 2, q["cx"] - p["cx"]


def belly(rgb, a):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (a > 0.9) & (R > 240) & (G > 215) & (B > 210) & (R - G < 32)
    m = ndimage.binary_opening(m, iterations=4)
    b = max(blobs(m, 3000), key=lambda q: q["area"])
    return b


def hooves(rgb, a):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (a > 0.9) & (R > 80) & (R < 175) & (G < 105) & (B < 95) & (R - B > 30)
    b = [q for q in blobs(m, 800) if (q["y1"] - q["y0"]) <= (q["x1"] - q["x0"]) * 0.9]
    b = sorted(b, key=lambda q: -q["y1"])[:2]
    return sorted(b, key=lambda q: q["cx"])


def save(name, rgb, a, parts, crop=True):
    ys, xs = np.where(a > 0.01)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    arr = np.dstack([rgb, a * 255])[y0:y1, x0:x1]
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})


def lum(rgb):
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


# ------------------------------------------------------------------------------------- drawn face alternates
def stroke_layer(draw_fn, blur=0.8):
    S = 3
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), S)
    im = im.resize((W, H), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32)
    return a[..., :3], a[..., 3] / 255


def arcpts(cx, cy, rx, ry, a0, a1, n=40):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def pline(d, S, pts, w, col):
    p = [(x * S, y * S) for x, y in pts]
    d.line(p, fill=col, width=int(w * S), joint="curve")
    r = w * S / 2
    for x, y in (p[0], p[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    parts = []
    base = load("base.png")
    ab, bgb = alpha_of(base)
    base, ab = decontam(base, ab, bgb)

    yy, xx = np.mgrid[0:H, 0:W]
    L_ = lum(base)
    MX = 1014                                    # the design's mirror axis is x = 507
    mir = lambda pts: [(MX - x, y) for x, y in pts]
    skin = np.median(base[(yy > 800) & (yy < 860) & (xx > 360) & (xx < 400) & (ab > 0.9)], 0)
    line_col = np.median(base[(ab > 0.9) & (L_ < 110) & (yy > 940) & (yy < 1000) & ((xx < 340) | (xx > 680))], 0)
    REP["skin"], REP["line"] = [int(v) for v in skin], [int(v) for v in line_col]

    def poly_mask(pts):
        im = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=255)
        return np.asarray(im) > 127

    def stroke(pts, w=7, alpha=255):
        im = Image.new("L", (W * 3, H * 3), 0)
        d = ImageDraw.Draw(im)
        d.line([(x * 3, y * 3) for x, y in pts], fill=alpha, width=w * 3, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse(((x - w / 2) * 3, (y - w / 2) * 3, (x + w / 2) * 3, (y + w / 2) * 3), fill=alpha)
        return np.asarray(im.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255

    def smooth(pts, n=8):                          # Catmull-Rom through the points
        out = []
        P = [pts[0]] + list(pts) + [pts[-1]]
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = map(np.array, P[i - 1:i + 3])
            for t in np.linspace(0, 1, n, endpoint=False):
                out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
        out.append(tuple(pts[-1]))
        return out

    # ---------------- chin line: darkest row below the mouth, per column, smoothed
    chin = np.zeros(W)
    for x in range(W):
        if ab[730:800, x].mean() > 0.5:
            chin[x] = 730 + np.argmin(L_[730:800, x])
    good = chin > 0
    pc = np.polyfit(np.where(good)[0], ndimage.median_filter(chin[good], 31), 4)
    xa, xb = np.where(good)[0].min(), np.where(good)[0].max()
    chin_y = np.polyval(pc, np.clip(xx, xa, xb))
    REP["chin_center"] = float(np.polyval(pc, 507))

    # ---------------- head: everything above the chin line (ears included), face marks lifted off
    head_m = (ab > 0.02) & (yy <= chin_y + 4) & (yy < 800)
    lab, n = ndimage.label(head_m & (ab > 0.4))
    big = lab == 1 + int(np.argmax(ndimage.sum(lab > 0, lab, range(1, n + 1))))
    head_m &= ndimage.binary_dilation(big, iterations=3)
    FB = {"eye_L": (418, 510, 478, 570), "eye_R": (546, 510, 606, 570), "brow_L": (405, 490, 478, 528), "brow_R": (546, 490, 619, 528), "mouth": (440, 688, 580, 718)}
    feats, fmask = {}, np.zeros((H, W), bool)
    marks = {}
    for k, (x0, y0, x1, y1) in FB.items():
        m = np.zeros((H, W), bool)
        m[y0:y1, x0:x1] = L_[y0:y1, x0:x1] < 120
        lab2, n2 = ndimage.label(m)
        if n2:
            s2 = ndimage.sum(m, lab2, range(1, n2 + 1))
            m = np.isin(lab2, 1 + np.where(s2 >= max(15, s2.max() * 0.2))[0])
        if k.startswith("eye"):
            m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=3))
        marks[k] = m
        fmask |= m
        ys, xs = np.where(m)
        feats[k] = dict(cx=float(xs.mean()), cy=float(ys.mean()), w=int(xs.max() - xs.min() + 1), h=int(ys.max() - ys.min() + 1))
    import cv2
    fm = ndimage.binary_dilation(fmask, iterations=6)
    blank = cv2.inpaint(np.clip(base, 0, 255).astype(np.uint8), fm.astype(np.uint8) * 255, 10, cv2.INPAINT_TELEA).astype(np.float32)
    sm = ndimage.gaussian_filter(blank, sigma=(5, 5, 0))
    w_ = ndimage.gaussian_filter(fm.astype(np.float32), 3)[..., None]
    blank = blank * (1 - w_) + sm * w_
    save("head", blank, np.where(head_m, ab, 0.0), parts)
    for k, m in marks.items():
        md = ndimage.binary_dilation(m, iterations=3)
        soft = np.clip(ndimage.gaussian_filter(md.astype(np.float32), 1.0) * 1.6, 0, 1)
        nm = {"eye_L": "eye_L_open", "eye_R": "eye_R_open", "brow_L": "brow_L_soft", "brow_R": "brow_R_soft", "mouth": "mouth_smile"}[k]
        save(nm, base, soft, parts)
    REP["features"] = feats
    head_bottom = int(np.polyval(pc, 507))

    # ---------------- clean-edge helpers: every cut part gets a smooth anti-aliased silhouette and a drawn outline
    def smooth_mask(m, sigma=2.0):
        b = ndimage.gaussian_filter(m.astype(np.float32), sigma)
        return np.clip((b - 0.5) * 3.0 + 0.5, 0, 1)

    def outline(alpha, width=6, weight=None):
        inside = alpha > 0.5
        ring = inside & ~ndimage.binary_erosion(inside, iterations=width)
        r = np.clip(ndimage.gaussian_filter(ring.astype(np.float32), 0.8) * 1.3, 0, 1) * (alpha > 0.05)
        if weight is not None:
            r = r * weight
        return r

    def finish(name, fill, m, line_w=6, weight=None):
        a = smooth_mask(m)
        o = outline(a, line_w, weight)
        rgb = fill * (1 - o[..., None]) + line_col * o[..., None]
        save(name, rgb, a, parts)
        return a

    body_pix = (ab > 0.9)

    # ---------------- arms: original arm pixels + a rounded shoulder end, one continuous outline all round
    ARM_L = [(318, 744), (296, 772), (276, 815), (262, 860), (248, 900), (252, 925), (270, 938), (298, 938), (316, 926), (322, 900), (326, 862), (336, 815), (344, 776), (340, 748)]
    EDGE_L = [(322, 750), (331, 782), (336, 815), (330, 840), (324, 868), (319, 895), (318, 905)]   # torso outline where the arm was
    PIV = {"L": (352, 805), "R": (MX - 352, 805)}
    HAND = {"L": (280, 905), "R": (MX - 280, 905)}
    arm_m = {"L": poly_mask(ARM_L) & (ab > 0.5), "R": poly_mask(mir(ARM_L)) & (ab > 0.5)}
    for s in "LR":
        m = arm_m[s]
        px, py = PIV[s]
        sg = 1 if s == "L" else -1
        # a rounded shoulder: an ellipse around the pivot, joined to the arm's top
        cap = poly_mask([(px - sg * 6 + 50 * math.cos(t), py - 4 + 62 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48)])
        full = ndimage.binary_closing(m | cap, iterations=6)
        full = ndimage.binary_fill_holes(full)
        fill = np.where((m & body_pix)[..., None], base, skin)
        finish(f"arm_{s}", fill, full)
        REP[f"arm_{s}"] = {"shoulder": list(PIV[s]), "hand": list(HAND[s])}

    # ---------------- legs: original leg below the body + a rounded top hidden under the torso, outlined all round
    LEG_L = [(292, 985), (480, 985), (480, 1110), (292, 1110)]
    for s, pts in (("L", LEG_L), ("R", mir(LEG_L))):
        m = poly_mask(pts) & (ab > 0.5)
        top = 1000
        xs_top = np.where(m[top])[0]
        cxl, half = (xs_top.min() + xs_top.max()) / 2, (xs_top.max() - xs_top.min()) / 2 - 4
        ext = poly_mask([(cxl + half * math.cos(t), top - 40 + 70 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48)]) | \
              poly_mask([(cxl - half, top - 40), (cxl + half, top - 40), (cxl + half, top + 4), (cxl - half, top + 4)])
        full = ndimage.binary_fill_holes(m | ext)
        fill = np.where((m & body_pix & (yy >= top))[..., None], base, skin)
        a = finish(f"leg_{s}", fill, full)
        ys, xs = np.where(a > 0.5)
        REP[f"leg_{s}"] = [int(xs.mean()), int(ys.min()), int(ys.max())]

    # ---------------- torso: one smooth closed contour (rounded top hidden under the head), original pixels inside
    side = [(322, 750), (331, 782), (336, 815), (330, 840), (324, 868), (319, 895), (318, 925), (322, 955), (330, 982), (344, 1004), (372, 1016), (430, 1020), (470, 1022), (507, 1028)]
    top = [(507, 612), (430, 628), (372, 668), (336, 712)]
    half_c = top + side
    contour = smooth(half_c + mir(half_c[::-1])[1:], n=10)
    tm = poly_mask(contour)
    below = yy > chin_y + 2
    fill = np.where((tm & below & body_pix & ~arm_m["L"] & ~arm_m["R"])[..., None], base, skin)
    # outline only where it can be seen: fades in below the chin (the part under the head stays plain)
    w = np.clip((yy - (chin_y - 6)) / 30.0, 0, 1)
    finish("torso", fill, tm, 6, w)
    # ears stay on the head; their pivot data is kept for reference only
    REP["head_box"] = [int(np.where(head_m.any(0))[0].min()), int(np.where(head_m.any(1))[0].min()), int(np.where(head_m.any(0))[0].max()), head_bottom]

    # ---------------- drawn alternates
    lc = tuple(int(v) for v in np.median(base[fmask & (L_ < 100)], 0)) + (255,)
    E = {s: feats[f"eye_{s}"] for s in "LR"}
    B = {s: feats[f"brow_{s}"] for s in "LR"}
    M = feats["mouth"]
    er = max(E["L"]["w"], E["L"]["h"]) / 2
    LW = 4.5

    def eyes(kind):
        for s in "LR":
            cx, cy = E[s]["cx"], E[s]["cy"]
            sg = 1 if s == "L" else -1

            def f(d, S):
                if kind == "closed":
                    pline(d, S, arcpts(cx, cy - 4, er * 1.3, er * 0.7, 20, 160), LW, lc)
                elif kind == "happy":
                    pline(d, S, arcpts(cx, cy + 8, er * 1.25, er * 1.0, 200, 340), LW, lc)
                elif kind == "squeeze":
                    pline(d, S, [(cx - er * 1.1 * sg, cy - er * 0.9), (cx + er * 0.9 * sg, cy), (cx - er * 1.1 * sg, cy + er * 0.9)], LW, lc)
                elif kind == "wide":
                    r = er * 1.35
                    d.ellipse(((cx - r) * S, (cy - r * 1.1) * S, (cx + r) * S, (cy + r * 1.1) * S), fill=lc)
                    d.ellipse(((cx - r * 0.05) * S, (cy - r * 0.8) * S, (cx + r * 0.5) * S, (cy - r * 0.25) * S), fill=(255, 255, 255, 255))
            rgb, a = stroke_layer(f)
            save(f"eye_{s}_{kind}", rgb, a, parts)

    def brows(kind):
        for s in "LR":
            cx, cy, bw = B[s]["cx"], B[s]["cy"], B[s]["w"]
            sg = 1 if s == "L" else -1

            def f(d, S):
                if kind == "angry":
                    pline(d, S, [(cx - bw * 0.5 * sg, cy - 12), (cx + bw * 0.45 * sg, cy + 10)], LW, lc)
                elif kind == "up":
                    pline(d, S, arcpts(cx, cy - 4, bw * 0.5, 12, 200, 340), LW, lc)
            rgb, a = stroke_layer(f)
            save(f"brow_{s}_{kind}", rgb, a, parts)

    def mouths():
        cx, cy, mw = M["cx"], M["cy"], M["w"]
        inner, tongue = (150, 62, 62, 255), (236, 132, 136, 255)
        for kind in ("shout", "grit", "o", "open_s"):
            def f(d, S, kind=kind):
                if kind == "shout":
                    rx, ry = mw * 0.42, mw * 0.36
                    d.ellipse(((cx - rx) * S, (cy - ry * 0.6) * S, (cx + rx) * S, (cy + ry * 1.3) * S), fill=inner, outline=lc, width=int(LW * S))
                    d.chord(((cx - rx * 0.6) * S, (cy + ry * 0.3) * S, (cx + rx * 0.6) * S, (cy + ry * 1.25) * S), 180, 360, fill=tongue)
                elif kind == "grit":
                    pline(d, S, [(cx - mw * 0.4, cy + 4), (cx + mw * 0.4, cy + 4)], LW, lc)
                    pline(d, S, arcpts(cx, cy + 14, mw * 0.4, 8, 200, 340), LW * 0.8, lc)
                elif kind == "o":
                    d.ellipse(((cx - mw * 0.2) * S, (cy - mw * 0.16) * S, (cx + mw * 0.2) * S, (cy + mw * 0.3) * S), fill=inner, outline=lc, width=int(LW * S))
                elif kind == "open_s":
                    d.ellipse(((cx - mw * 0.28) * S, (cy - mw * 0.1) * S, (cx + mw * 0.28) * S, (cy + mw * 0.22) * S), fill=inner, outline=lc, width=int(LW * S))
            rgb, a = stroke_layer(f)
            save(f"mouth_{kind}", rgb, a, parts)

    for k in ("closed", "happy", "squeeze", "wide"):
        eyes(k)
    for k in ("angry", "up"):
        brows(k)
    mouths()

    # ---------------- club (lying horizontal in its own image): handle at the left
    c = np.asarray(Image.open(GEN / "club_01.png").convert("RGB")).astype(np.float32)
    ca, cbg = alpha_of(c)
    c, ca = decontam(c, ca, cbg)
    ys, xs = np.where(ca > 0.5)
    c, ca = c[ys.min() - 4:ys.max() + 5, xs.min() - 4:xs.max() + 5], ca[ys.min() - 4:ys.max() + 5, xs.min() - 4:xs.max() + 5]
    # size: as long as the pig is tall from hoof to chin
    target = (max(REP["leg_L"][2], REP["leg_R"][2]) - head_bottom) * 1.25
    sc = target / c.shape[1]
    ci = Image.fromarray(np.dstack([c, ca * 255]).astype(np.uint8), "RGBA").resize((int(c.shape[1] * sc), int(c.shape[0] * sc)), Image.LANCZOS)
    # place the handle in the right hoof, pointing up and out (rest pose: resting on the shoulder)
    ci = ci.rotate(62, expand=True, resample=Image.BICUBIC)
    hx, hy = REP["arm_R"]["hand"]
    cpx = int(hx - ci.width * 0.18)
    cpy = int(hy - ci.height * 0.86)
    ca2 = np.asarray(ci).astype(np.float32)
    canvas = np.zeros((H, W, 4), np.float32)
    x0, y0 = max(cpx, 0), max(cpy, 0)
    sub = ca2[y0 - cpy:, x0 - cpx:]
    hh, ww = min(sub.shape[0], H - y0), min(sub.shape[1], W - x0)
    canvas[y0:y0 + hh, x0:x0 + ww] = sub[:hh, :ww]
    save("club", canvas[..., :3], canvas[..., 3] / 255, parts)
    REP["club_grip"] = [hx, hy]
    REP["club_len"] = float(target)
    REP["club_ang"] = 62.0

    # ---------------- effects from the battle project (same canvas), and the shadow
    bp = HERE.parent / "zhuda_battle" / "parts"
    bm = {q["name"]: q for q in json.loads((bp / "manifest.json").read_text())["parts"]}
    ca_ = math.radians(REP["club_ang"])
    tip = (hx + target * 0.82 * math.cos(ca_), hy - target * 0.82 * math.sin(ca_))
    centre = {"fx_impact": tip, "fx_slash": (662 + 40, 700), "fx_orb": (507, 300), "fx_burst": (507 + 760, 820)}   # = their bones in rig.py
    for n in ("shadow", "fx_circle", "fx_slash", "fx_dust_L", "fx_dust_R", "fx_impact", "fx_sparkles", "fx_orb", "fx_burst"):
        q = dict(bm[n])
        Image.open(bp / q["file"]).save(OUT / q["file"])
        if n in centre:
            q["x"], q["y"] = int(centre[n][0] - q["w"] / 2), int(centre[n][1] - q["h"] / 2)
        parts.append(q)

    order = ["shadow", "fx_circle", "fx_slash", "leg_L", "leg_R", "arm_L", "arm_R", "torso", "head",
             "eye_L_open", "eye_L_closed", "eye_L_happy", "eye_L_squeeze", "eye_L_wide", "eye_R_open", "eye_R_closed", "eye_R_happy", "eye_R_squeeze", "eye_R_wide",
             "brow_L_soft", "brow_L_angry", "brow_L_up", "brow_R_soft", "brow_R_angry", "brow_R_up",
             "mouth_smile", "mouth_shout", "mouth_grit", "mouth_o", "mouth_open_s", "club",
             "fx_dust_L", "fx_dust_R", "fx_impact", "fx_sparkles", "fx_orb", "fx_burst"]
    names = [q["name"] for q in parts]
    missing = [n for n in order if n not in names]
    extra = [n for n in names if n not in order]
    REP["missing"], REP["extra"] = missing, extra
    parts = [q for q in parts if q["name"] in order]
    parts.sort(key=lambda q: order.index(q["name"]))
    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "extract.py", "parts": parts}, indent=1))
    REP["ground"] = [W // 2, int(max(REP["leg_L"][2], REP["leg_R"][2]))]
    (HERE / "extract-report.json").write_text(json.dumps(REP, indent=1, ensure_ascii=False))

    # evidence: recomposed rest pose vs base, and every part on dark
    comp = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    skip = {"club", "fx_circle", "fx_slash", "fx_dust_L", "fx_dust_R", "fx_impact", "fx_sparkles", "fx_orb", "fx_burst"}
    for q in parts:
        if q["name"] in skip or (q["name"].count("_") >= 2 and not q["name"].endswith(("_open", "_soft"))) or q["name"] in ("mouth_shout", "mouth_grit", "mouth_o", "mouth_open_s"):
            continue
        comp.alpha_composite(Image.open(OUT / q["file"]), (q["x"], q["y"]))
    bimg = Image.fromarray(np.dstack([base, ab * 255]).astype(np.uint8), "RGBA")
    bb = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    bb.alpha_composite(bimg)
    ca_ = np.asarray(comp).astype(np.float32)[..., :3]
    bba = np.asarray(bb).astype(np.float32)[..., :3]
    d = np.abs(ca_ - bba).sum(-1)
    REP["recompose_mean"] = round(float(d[ab > 0.5].mean()), 2)
    REP["recompose_over_60"] = round(float((d[ab > 0.5] > 60).mean()), 4)
    sheet = Image.new("RGB", (W * 3, H))
    sheet.paste(bb.convert("RGB"), (0, 0))
    sheet.paste(comp.convert("RGB"), (W, 0))
    sheet.paste(Image.fromarray(np.clip(np.repeat(d[..., None], 3, -1) * 2, 0, 255).astype(np.uint8)), (2 * W, 0))
    sheet.resize((W * 3 // 2, H // 2)).save(EV / "recompose.png")
    (HERE / "extract-report.json").write_text(json.dumps(REP, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in REP.items() if k != "features"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
