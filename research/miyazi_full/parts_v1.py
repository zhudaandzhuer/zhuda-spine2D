"""米丫子 full body: registered layers (gen/L_*.png) -> parts/ + manifest (draw order back to front).

Visible pixels always come from the key art; generated layers only fill what is hidden at rest.
  arms  = key pixels outside the (arm-less) torso silhouette + the shoulder part of the arms layer that agrees with the key
  hands = strict-skin pixels of the arm below the cuff, with a small wrist stub under the cuff
  fists = where the fists layer differs from the key, around each hand
  legs  = key denim / shoes (+ everything below the hem), split at the crotch; hidden hips from the legs layer
  torso = the rest below the chin; hidden shoulders / sides from the torso layer
  head  = key pixels inside the head layer silhouette (hair, face, neck to the collar)
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
GEN, OUT, EV = HERE / "gen", HERE / "parts", HERE / "evidence" / "parts"
W, H = 941, 1672
SPLIT_X = 466
HEM_Y = 868
REP = {}


def L(n):
    a = np.asarray(Image.open(GEN / f"L_{n}.png")).astype(np.float32)
    return a[..., :3], a[..., 3] / 255


def save(name, rgb, a, parts):
    a = np.where(a < 0.01, 0, np.clip(a, 0, 1))
    ys, xs = np.where(a > 0)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    arr = np.clip(np.dstack([rgb, a * 255])[y0:y1, x0:x1], 0, 255)
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    parts.append({"name": name, "file": f"{name}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})


def skin(rgb):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (R > 185) & (R - G > 28) & (R - B > 36) & (G > 130) & (B > 110)


def clean(m, close=2, fill=True):
    m = ndimage.binary_closing(m, iterations=close)
    if fill:
        m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if n > 1:
        s = ndimage.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, 1 + np.where(s >= s.max() * 0.05)[0])
    return m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        f.unlink()
    parts = []
    yy, xx = np.mgrid[0:H, 0:W]
    kr, ka = L("key")
    vis = ka > 0.5
    soft = ka > 0.02
    tr, ta = L("torso")
    lr, la = L("legs")
    ar, aa = L("arms")
    hr, ha = L("head")
    fr, fa = L("fists")
    R, G, B = kr[..., 0], kr[..., 1], kr[..., 2]
    far, near = xx < SPLIT_X, xx >= SPLIT_X

    head_sil = clean(ha > 0.5)
    tor_sil = clean(ta > 0.5)
    denim = (B > R + 8) & (B > 100)
    shoe = (R > 205) & (G > 205) & (B > 200) & (yy > 1380)

    head_m = clean(vis & head_sil, close=1, fill=False)
    head_zone = ndimage.binary_dilation(head_m, iterations=4) & soft & (yy < 360)
    head_alpha = np.where(head_zone, ka, 0.0)

    dj = denim | shoe
    from PIL import ImageDraw

    def poly(pts):
        im = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).polygon(pts, fill=255)
        return np.asarray(im) > 127

    # hand-traced on 3x grids of the key art (evidence/parts/grids): sleeve inner crease, cuff bottom edge
    P = {"far": [(240, 420), (300, 432), (330, 440), (360, 456), (383, 480), (379, 540), (373, 600), (376, 650), (384, 700),
                 (360, 735), (330, 760), (305, 790), (285, 822), (250, 830), (200, 800), (140, 760), (150, 600), (200, 480)],
         "near": [(590, 330), (612, 345), (618, 400), (612, 450), (622, 520), (628, 580), (640, 640), (650, 700), (645, 760),
                  (662, 800), (700, 820), (760, 800), (760, 600), (700, 400), (640, 320)]}
    HP = {"far": [(192, 786), (248, 783), (272, 800), (260, 845), (238, 885), (226, 930), (196, 930), (176, 885), (174, 840), (184, 805)],
          "near": [(656, 808), (716, 794), (728, 830), (736, 872), (722, 930), (688, 932), (668, 885), (656, 842)]}
    CUFF = {"far": ((196, 792), (270, 808)), "near": ((660, 818), (715, 800))}
    dj = denim | shoe
    lav = (B > G + 12) & (B > 170)
    arm_m, hand_m, wrist = {}, {}, {}
    arm_sil = np.zeros((H, W), bool)
    for side in ("far", "near"):
        (x0, y0), (x1, y1) = CUFF[side]
        cy = y0 + (y1 - y0) * np.clip((xx - x0) / (x1 - x0), 0, 1)
        hm = soft & poly(HP[side]) & (yy > cy)
        hand_m[side] = hm
        am = vis & poly(P[side]) & ~hm & ~lav & ~dj
        am = clean(am, close=2)
        arm_m[side] = am
        arm_sil |= am | hm
        ys, xs = np.where(hm & vis)
        top = ys.min()
        tx = xs[ys < top + 8]
        wrist[side] = (float(tx.mean()), float(top), float(max(10, (tx.max() - tx.min()) / 2)))
    leg_m = vis & (dj | ((yy > HEM_Y + 6) & ndimage.binary_dilation(dj, iterations=12)) | (yy > HEM_Y + 30)) & ~head_m & ~arm_sil & (yy > 700)
    tor_m = vis & ~head_m & ~leg_m & ~ndimage.binary_dilation(arm_sil, iterations=1) & (yy > 250)
    REP["px"] = {"head": int(head_m.sum()), "legs": int(leg_m.sum()), "arm_far": int(arm_m["far"].sum()), "arm_near": int(arm_m["near"].sum()),
                 "hand_far": int(hand_m["far"].sum()), "hand_near": int(hand_m["near"].sum()), "torso": int(tor_m.sum())}

    def piece(m, fill_rgb, fill_a, hidden=None):
        rgb = np.where(m[..., None], kr, fill_rgb)
        a = np.where(m, ka, 0.0)
        if hidden is not None:
            a = np.maximum(a, np.where(hidden & ~m, fill_a, 0.0))
        edge = ndimage.binary_dilation(m, iterations=2) & ~vis & soft & ~head_zone
        a = np.where(edge, ka, a)
        rgb = np.where(edge[..., None], kr, rgb)
        return rgb, a

    front_of_legs = tor_m | arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"]
    gap = [(466, 700), (466, 950), (465, 990), (462, 1030), (457, 1070), (453, 1110), (448, 1150), (440, 1190), (434, 1230),
           (431, 1310), (427, 1390), (423, 1470), (420, 1510), (414, 1550), (410, 1672)]
    gx = np.interp(yy, [g[1] for g in gap], [g[0] for g in gap])
    lfar, lnear = xx < gx, xx >= gx
    for side, sel in (("far", lfar), ("near", lnear)):
        hid = (la > 0.5) & sel & (yy < HEM_Y + 40) & front_of_legs
        rgb, a = piece(leg_m & sel, lr, la, hid)
        save(f"leg_{side}", rgb, a, parts)
    hid_t = (ta > 0.5) & (arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"] | head_m) & ~leg_m
    rgb, a = piece(tor_m, tr, ta, hid_t)
    a = np.where(leg_m, 0.0, a)
    save("torso", rgb, a, parts)
    skin_c = np.median(kr[hand_m["far"] & vis], 0)
    for side in ("far", "near"):
        cx, top, w = wrist[side]
        stub = (((xx - cx) / (w * 0.9)) ** 2 + ((yy - top) / 28.0) ** 2 < 1) & (yy < top + 6)
        rgb, a = piece(hand_m[side], kr, ka)
        rgb = np.where((stub & ~hand_m[side])[..., None], skin_c, rgb)
        a = np.maximum(a, stub.astype(np.float32))
        save(f"hand_{side}", rgb, a, parts)
        d = np.abs(fr - kr).sum(-1)
        near_hand = ((xx - cx) ** 2 + (yy - (top + 50)) ** 2) < 110 ** 2
        fm = ((d > 60) & (fa > 0.5) & skin(fr) & near_hand) | (hand_m[side] & (fa > 0.5) & skin(fr) & (d < 40))
        fm = clean(fm, close=2)
        fm = ndimage.binary_dilation(fm, iterations=1) & (fa > 0.02)
        frgb = np.where((stub & ~fm)[..., None], skin_c, fr)
        fal = np.maximum(np.where(fm, fa, 0.0), stub.astype(np.float32))
        save(f"fist_{side}", frgb, fal, parts)
        REP[f"wrist_{side}"] = [cx, top]
    for side, sel in (("far", far), ("near", near)):
        cap = (aa > 0.5) & sel & (yy < 520) & tor_m & ndimage.binary_dilation(arm_m[side], iterations=18)
        rgb, a = piece(arm_m[side], ar, aa, cap)
        save(f"arm_{side}", rgb, a, parts)
        REP[f"arm_{side}_cap_px"] = int((cap & ~arm_m[side]).sum())
    save("head", kr, head_alpha, parts)
    red = (ka > 0.3) & (R > 120) & (R - G > 60) & (R - B > 50) & (xx > 500) & (xx < 680) & (yy < 420)
    red = ndimage.binary_closing(red, iterations=2)
    lab, n = ndimage.label(red)
    sz = ndimage.sum(red, lab, range(1, n + 1))
    red = np.isin(lab, 1 + np.where(sz > 100)[0])
    ys, xs = np.where(red)
    knot_y = int(np.percentile(ys, 15))
    tails = ndimage.binary_dilation(red & (yy > knot_y + 25), iterations=2) & soft
    save("ribbon_tail", kr, np.where(tails, ka, 0.0), parts)
    REP["ribbon"] = {"knot_y": knot_y, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}

    # apple prop (drawn): simple anime apple, picked up in the `pickup` clip
    S = 4
    im = Image.new("RGBA", (90 * S, 96 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6 * S, 18 * S, 84 * S, 92 * S), fill=(214, 52, 58, 255), outline=(110, 30, 30, 255), width=3 * S)
    d.ellipse((20 * S, 30 * S, 38 * S, 50 * S), fill=(245, 150, 150, 255))
    d.line((45 * S, 22 * S, 50 * S, 4 * S), fill=(110, 70, 40, 255), width=4 * S)
    d.ellipse((50 * S, 4 * S, 74 * S, 16 * S), fill=(90, 160, 70, 255), outline=(50, 100, 40, 255), width=2 * S)
    im = im.resize((90, 96), Image.LANCZOS)
    arr = np.zeros((H, W, 4), np.float32)
    ax0, ay0 = 150, 1540
    arr[ay0:ay0 + 96, ax0:ax0 + 90] = np.asarray(im).astype(np.float32)
    save("apple", arr[..., :3], arr[..., 3] / 255, parts)
    held = np.zeros((H, W, 4), np.float32)
    hx0, hy0 = int(REP["wrist_far"][0]) - 50, int(REP["wrist_far"][1]) + 70
    held[hy0:hy0 + 96, hx0:hx0 + 90] = np.asarray(im).astype(np.float32)
    save("apple_held", held[..., :3], held[..., 3] / 255, parts)
    REP["apple"] = [ax0 + 45, ay0 + 50]

    order_out = ["apple", "leg_far", "leg_near", "torso", "hand_far", "fist_far", "arm_far", "hand_near", "fist_near", "arm_near", "apple_held", "head", "ribbon_tail"]
    parts.sort(key=lambda q: order_out.index(q["name"]))
    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "parts.py", "parts": parts}, indent=1))

    m_ = {q["name"]: q for q in parts}
    c = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    for n_ in order_out:
        if n_.startswith("fist") or n_.startswith("apple"):
            continue
        q = m_[n_]
        c.alpha_composite(Image.open(OUT / q["file"]), (q["x"], q["y"]))
    k = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    k.alpha_composite(Image.open(GEN / "L_key.png"))
    d = np.abs(np.asarray(c).astype(np.float32)[..., :3] - np.asarray(k).astype(np.float32)[..., :3]).sum(-1)
    REP["recompose_mean"] = round(float(d[soft].mean()), 2)
    REP["recompose_over_60"] = round(float((d[soft] > 60).mean()), 4)
    sh = Image.new("RGB", (W * 3, H))
    sh.paste(k.convert("RGB"), (0, 0))
    sh.paste(c.convert("RGB"), (W, 0))
    sh.paste(Image.fromarray(np.clip(np.repeat(d[..., None], 3, -1) * 2, 0, 255).astype(np.uint8)), (2 * W, 0))
    sh.resize((W * 3 // 2, H // 2)).save(EV / "recompose.png")
    (HERE / "parts-report.json").write_text(json.dumps(REP, indent=1))
    print(json.dumps(REP))


if __name__ == "__main__":
    main()
