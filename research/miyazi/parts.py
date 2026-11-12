"""米丫子: canvas layers (gen/L_*, gen/P_*) -> parts/*.png + parts/manifest.json (draw order, back to front).

    python3 parts.py
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
GEN, OUT, EV = HERE / "gen", HERE / "parts", HERE / "evidence" / "parts"
W, H = 1024, 1536
REP = {}


def rgba(name):
    a = np.asarray(Image.open(GEN / f"{name}.png").convert("RGBA")).astype(np.float32)
    return a[..., :3], a[..., 3] / 255


def despill(rgb):
    """green-screen residue: in this palette G never exceeds R - (R - B) / 4 (blonde, skin, cream, lavender all satisfy it)"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lim = r - np.maximum(r - b, 0) * 0.25
    out = rgb.copy()
    out[..., 1] = np.minimum(g, lim)
    return out


def save(name, rgb, a, parts):
    rgb = despill(rgb)
    a = np.where(a < 0.01, 0, a)
    ys, xs = np.where(a > 0)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    arr = np.dstack([np.clip(rgb, 0, 255), a * 255])[y0:y1, x0:x1]
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})


def inpaint_rgba(rgb, a, mask, r=7):
    m = (mask > 0).astype(np.uint8) * 255
    out = cv2.inpaint(np.clip(rgb, 0, 255).astype(np.uint8), m, r, cv2.INPAINT_TELEA).astype(np.float32)
    al = cv2.inpaint(np.clip(a * 255, 0, 255).astype(np.uint8), m, r, cv2.INPAINT_TELEA).astype(np.float32) / 255
    return out, al


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    parts = []
    yy, xx = np.mgrid[0:H, 0:W]

    # ---- ownership: every pixel the key art shows belongs to exactly one part, so the rest pose IS the key art.
    #      Generated layers only supply what is hidden (under hair, under arms, behind the face).
    kr, ka = rgba("L_keyart")
    L = {"hair_back": rgba("L_hairb"), "face": rgba("P_face"), "body": rgba("L_body"), "arms": rgba("L_arms"), "hair_front": rgba("L_hairf")}
    order = ["hair_back", "face", "body", "arms", "hair_front"]               # back to front

    def bleed(rgb, a, r=5):
        """colour of semi-transparent edge pixels from their opaque neighbours (kills green-screen tint)"""
        w = (a > 0.9).astype(np.float32)
        num = ndimage.uniform_filter(rgb * w[..., None], size=(2 * r + 1, 2 * r + 1, 1))
        den = ndimage.uniform_filter(w, size=2 * r + 1)[..., None]
        est = np.where(den > 1e-3, num / np.maximum(den, 1e-3), rgb)
        return np.where((a < 0.9)[..., None], est, rgb)

    for k in order:
        L[k] = (bleed(*L[k]), L[k][1])
    kr = bleed(kr, ka)
    vis = ka > 0.02
    # owner: front-most layer that covers the pixel with a matching colour; else front-most that covers it; else nearest layer
    owner = np.full((H, W), -1, np.int32)
    for i in range(len(order) - 1, -1, -1):                                  # occlusion: the front-most layer is what you see
        g, ga = L[order[i]]
        owner[(ga > 0.5) & vis & (owner < 0)] = i
    if (vis & (owner < 0)).any():                                             # key-art pixels no layer covers (silhouette drift)
        dists = []
        for i, k in enumerate(order):
            dists.append(ndimage.distance_transform_edt(~(L[k][1] > 0.5)))
        near = np.argmin(np.stack(dists), 0)
        owner = np.where(vis & (owner < 0), near, owner)
    REP["owner_px"] = {k: int((owner == i).sum()) for i, k in enumerate(order)}

    def compose(i):
        k = order[i]
        g, ga = L[k]
        own = owner == i
        behind = (owner > i) & vis                       # hidden under a front part at rest: generated fill
        front_of_owner = (owner < i) & (owner >= 0) & vis
        if k == "face":                                   # the face keeps its own clean pixels (features are separate parts)
            rgb = np.where(own[..., None], g, g)
        else:
            rgb = np.where(own[..., None], kr, g)
        a = np.where(own, ka, 0.0) + np.where(behind, ga, 0.0)
        a = np.where(front_of_owner, 0.0, a)              # never cover the true owner
        if k == "face":                                   # the face is never cut: whatever is in front of it covers it
            a = np.where(vis | (ga > 0.5), ga, 0.0) * np.where(vis | (L["hair_front"][1] > 0.5), 1.0, 0.0)
        if k == "hair_front":                            # strands over the face keep their soft generated alpha
            soft = own & (ga > 0.02) & (ga < 0.98) & (owner_under_face(i))
            a = np.where(soft, ga, a)
        return rgb, np.clip(a, 0, 1)

    face_i = order.index("face")

    def owner_under_face(i):
        return L["face"][1] > 0.5

    comps = {k: compose(i) for i, k in enumerate(order)}
    save("hair_back", *comps["hair_back"], parts)
    save("face", *comps["face"], parts)

    # ---- body: drop the neck stump (skin above the collar) -- the face layer's neck shows there
    rgb, a = comps["body"]
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    fneck = L["face"][1] > 0.5
    a = np.where(fneck & (yy < 520) & (owner != order.index("body")), 0.0, a)
    save("body", rgb, a, parts)

    # ---- arms: split by side
    rgb, a = comps["arms"]
    for s, sel in (("L", xx < W / 2), ("R", xx >= W / 2)):
        save(f"arm_{s}", rgb, np.where(sel, a, 0.0), parts)
        ys, xs = np.where(np.where(sel, a, 0) > 0.5)
        REP[f"arm_{s}"] = {"top": [float(xs[ys < ys.min() + 20].mean()), int(ys.min())], "bottom": [float(xs[ys > ys.max() - 20].mean()), int(ys.max())]}

    # ---- face parts (z-order inside the head)
    for n_ in ("eye_white_L", "eye_white_R", "iris_L", "iris_R", "lash_L", "lash_R"):
        r_, a_ = rgba(f"P_{n_}")
        save(n_, r_, a_, parts)
    for k in ("half", "closed", "smile"):
        for s in "LR":
            r_, a_ = rgba(f"P_eye_{k}_{s}")
            save(f"eye_{k}_{s}", r_, a_, parts)
    for s in "LR":
        r_, a_ = rgba(f"P_brow_{s}")
        save(f"brow_{s}", r_, a_, parts)
    for k in ("closed", "a", "aa", "o", "smile"):
        r_, a_ = rgba(f"P_mouth_{k}")
        save(f"mouth_{k}", r_, a_, parts)
    r_, a_ = rgba("P_blush")
    save("blush", r_, a_, parts)

    # ---- front hair; the red ribbon tails become their own part (they swing), hair is painted in under them
    rgb, a = comps["hair_front"]
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = (a > 0.3) & (R > 120) & (R - G > 60) & (R - B > 50)
    red = ndimage.binary_closing(red, iterations=2)
    lab, n = ndimage.label(red)
    sz = ndimage.sum(red, lab, range(1, n + 1))
    red = np.isin(lab, 1 + np.where(sz > 150)[0])
    ys, xs = np.where(red)
    knot_y = int(np.percentile(ys, 12))                 # knot = upper part of the red; tails hang below it
    tails = red & (yy > knot_y + 40)
    tails = ndimage.binary_dilation(tails, iterations=2) & (a > 0.05)
    REP["ribbon"] = {"knot_y": knot_y, "tail_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
    tail_rgb = rgb.copy()
    tail_a = np.where(tails, a, 0.0)
    save("ribbon_tail", tail_rgb, tail_a, parts)
    # under the tails: the hair from a generated edit of this layer with the tails removed (registered on the hair around)
    import layers as LY
    nr_rgb, nr_a = LY.key(LY.load("hairf_noribbon_01.png"))
    zone = ndimage.binary_dilation(tails, iterations=6)
    ring = ndimage.binary_dilation(zone, iterations=30) & ~zone & (a > 0.95)
    e, sc, dx, dy = LY.register(nr_rgb, nr_a, rgb, a, ring, scales=(0.99, 1.0, 1.01), shift=10)
    nr_rgb, nr_a = LY.warp(nr_rgb, nr_a, sc, dx, dy)
    nr_rgb = bleed(nr_rgb, nr_a)
    REP["noribbon_reg"] = {"scale": sc, "dx": dx, "dy": dy, "err": round(e, 2)}
    f = np.clip(ndimage.gaussian_filter(zone.astype(np.float32), 3), 0, 1)       # feathered hand-over
    hrgb = rgb * (1 - f[..., None]) + nr_rgb * f[..., None]
    ha = a * (1 - f) + nr_a * f
    save("hair_front", hrgb, ha, parts)

    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "parts.py", "parts": parts}, indent=1))
    (HERE / "parts-report.json").write_text(json.dumps(REP, indent=1))

    # evidence: rest composite vs key art on dark
    comp = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    rest = ["hair_back", "face", "body", "arm_L", "arm_R", "eye_white_L", "eye_white_R", "iris_L", "iris_R", "lash_L", "lash_R", "brow_L", "brow_R", "mouth_closed", "hair_front", "ribbon_tail"]
    m = {q["name"]: q for q in parts}
    for n_ in rest:
        q = m[n_]
        comp.alpha_composite(Image.open(OUT / q["file"]), (q["x"], q["y"]))
    k = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    k.alpha_composite(Image.open(GEN / "L_keyart.png"))
    ca, ka = np.asarray(comp).astype(np.float32)[..., :3], np.asarray(k).astype(np.float32)[..., :3]
    d = np.abs(ca - ka).sum(-1)
    kal = np.asarray(Image.open(GEN / "L_keyart.png"))[..., 3] > 128
    REP["recompose_mean"] = round(float(d[kal].mean()), 2)
    REP["recompose_over_60"] = round(float((d[kal] > 60).mean()), 4)
    sheet = Image.new("RGB", (W * 3, H))
    sheet.paste(k.convert("RGB"), (0, 0))
    sheet.paste(comp.convert("RGB"), (W, 0))
    sheet.paste(Image.fromarray(np.clip(np.repeat(d[..., None], 3, -1) * 2, 0, 255).astype(np.uint8)), (2 * W, 0))
    sheet.resize((W * 3 // 2, H // 2)).save(EV / "recompose.png")
    (HERE / "parts-report.json").write_text(json.dumps(REP, indent=1))
    print(json.dumps(REP, indent=1))


if __name__ == "__main__":
    main()
