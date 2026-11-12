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
    denim = ((B > R + 8) & (B > 100)) | ((B > R + 5) & (B > 50) & (yy > 820)) | ((R + G + B < 270) & (B >= R) & (yy > 820))
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
    dj = denim | shoe
    lav = (B > G + 12) & (B > 170)
    arm_m, hand_m, wrist = {}, {}, {}
    arm_sil = np.zeros((H, W), bool)
    asil = clean(aa > 0.5, close=2, fill=True)
    tsil = clean(ta > 0.5)
    for side, sel in (("far", far), ("near", near)):
        sil = asil & sel
        # arm = key pixels in the arm silhouette that the torso layer does not explain (or that lie outside it)
        own = vis & sil & ~ndimage.binary_dilation(tsil, iterations=1) & ~lav & ~dj      # the armhole edge belongs to the torso
        own = clean(own, close=3)
        warm = (R - G > 16) & (R > 120)                       # skin / its shading; the cream knit has R-G about 8
        hm = own & warm & (yy > 700)
        hm = clean(ndimage.binary_opening(hm, iterations=1), close=4)
        lab_, n_ = ndimage.label(hm)
        if n_ > 1:
            hm = lab_ == 1 + int(np.argmax(ndimage.sum(hm, lab_, range(1, n_ + 1))))
        hm = ndimage.binary_fill_holes(ndimage.binary_closing(hm, iterations=3))
        hm = ndimage.binary_dilation(hm, iterations=2) & soft & ndimage.binary_dilation(sil, iterations=3) & (yy > 700)
        hand_m[side] = hm
        htop = np.where(hm.any(1))[0].min()
        arm_m[side] = own & ~hm & (yy < htop + 40)
        arm_m[side] = clean(arm_m[side], close=1, fill=False)
        arm_sil |= own | hm
        ys, xs = np.where(hm & vis)
        top = ys.min()
        tx = xs[ys < top + 8]
        wrist[side] = (float(tx.mean()), float(top), float(max(10, (tx.max() - tx.min()) / 2)))
    beige = (R > B + 25) & (R > 150) & (yy < HEM_Y + 40)             # the cardigan's hem / corner flap is never a leg
    leg_m = vis & (dj | ((yy > HEM_Y + 6) & ndimage.binary_dilation(dj, iterations=12)) | (yy > HEM_Y + 30)) & ~head_m & ~arm_sil & (yy > 700) & ~beige
    tor_m = vis & ~head_m & ~leg_m & ~ndimage.binary_dilation(arm_sil, iterations=1) & (yy > 250) & ~((yy < 340) & ~tsil)
    REP["px"] = {"head": int(head_m.sum()), "legs": int(leg_m.sum()), "arm_far": int(arm_m["far"].sum()), "arm_near": int(arm_m["near"].sum()),
                 "hand_far": int(hand_m["far"].sum()), "hand_near": int(hand_m["near"].sum()), "torso": int(tor_m.sum())}

    def piece(m, fill_rgb, fill_a, hidden=None):
        rgb = np.where(m[..., None], kr, fill_rgb)
        a = np.where(m, ka, 0.0)
        if hidden is not None:
            a = np.maximum(a, np.where(hidden & ~m, fill_a, 0.0))
        edge = ndimage.binary_dilation(m, iterations=2) & ~vis & soft & ~head_zone & (ka > 0.08) & ~ndimage.binary_dilation(hand_m["far"] | hand_m["near"], iterations=4)
        a = np.where(edge, ka, a)
        rgb = np.where(edge[..., None], kr, rgb)
        return rgb, a

    front_of_legs = tor_m | arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"]
    gap = [(466, 700), (466, 950), (465, 990), (462, 1030), (457, 1070), (453, 1110), (448, 1150), (440, 1190), (434, 1230),
           (431, 1310), (427, 1390), (423, 1470), (420, 1510), (414, 1550), (410, 1672)]
    gx = np.interp(yy, [g[1] for g in gap], [g[0] for g in gap])
    # above the crotch the far thigh's inner top is behind the near thigh: give the far leg a rounded inner top
    # (curving from the crotch up and out to x=410 at the hem) and let the near leg own that strip
    t_ = np.clip((1012 - yy) / 140.0, 0, 1)
    gx = np.where(yy < 1012, 462 - (1012 - yy) * 0.25, gx)     # far leg's inner seam: the crotch fabric goes with the near leg
    lfar, lnear = xx < gx, xx >= gx
    for side, sel in (("far", lfar), ("near", lnear)):
        hid = (la > 0.5) & sel & (yy < HEM_Y + 40) & front_of_legs
        cream = (R > 200) & (R - B < 45) & (yy < 905)                 # the cardigan hem must never ride on a leg
        rgb, a = piece(leg_m & sel & ~cream, lr, la, hid & ~cream)
        # the hip of each leg, hidden under the cardigan at rest, comes entirely from the generated legs layer (clean
        # denim to the waistband), split at the crotch line; the key art's deep shadow pixels there are not used
        TOP = HEM_Y + 30
        hipzone = (yy < TOP) & sel & (la > 0.5) & (yy > 600)
        dark_key = (R + G + B) < 260
        denimish = (B > R - 12) & ((R + G + B) < 620)
        use_layer = hipzone & (~vis | ~leg_m | dark_key | tor_m | ~denimish)
        hemband = sel & (yy >= TOP) & (yy < TOP + 24) & (la > 0.5) & ~denimish & ~ndimage.binary_dilation(shoe, iterations=2)
        use_layer |= hemband
        rgb = np.where(use_layer[..., None], lr, rgb)
        a = np.where(use_layer, la, a)
        # soften the join between key pixels and layer pixels across the hem line
        # one clean fabric under the hem: generated denim at the top, feathered into the key art by y=905
        f_ = np.clip((yy - 880) / 25.0, 0, 1)[..., None] * (leg_m & sel)[..., None]
        rgb = lr * (1 - f_) + rgb * f_
        a = np.where((yy < 905) & (la > 0.5) & sel, np.maximum(a, la), a)
        brownish = (R > B + 10) & (yy < HEM_Y + 40) & ~(B > R - 12)
        a = np.where(brownish & (yy < 905) & ~((la > 0.5) & sel), 0.0, a)
        a = np.where(yy < 852, 0.0, a) * np.where(yy < 868, (yy - 852) / 16.0, 1.0)   # tops end just under the hem (the seat piece covers above)
        keep = clean(a > 0.3, close=1, fill=False)                       # no floating islands
        a = a * ndimage.binary_dilation(keep, iterations=2)
        save(f"leg_{side}", rgb, a, parts)
    # pelvis: the seat of the jeans from the waistband down to the crotch seam, rigid on the hip bone and drawn over
    # both leg tops.  The thighs pivot underneath it, so their stretched tops never show below the hem.
    from PIL import ImageDraw as _D, ImageFilter as _F
    V = [(282, 760), (568, 760), (568, 872), (540, 884), (505, 902), (480, 914), (462, 918), (444, 914), (420, 902),
         (385, 886), (330, 878), (286, 872)]
    _im = Image.new("L", (W, H), 0)
    _D.Draw(_im).polygon(V, fill=255)
    pz = np.asarray(_im.filter(_F.GaussianBlur(1.2))).astype(np.float32) / 255
    inside = pz > 0.5
    own_key = inside & vis & leg_m & (B > R - 12) & ((R + G + B) < 620)
    prgb = np.where(own_key[..., None], kr, lr)
    pa = np.where(own_key, ka, la) * pz
    save("pelvis", prgb, pa, parts)
    hid_t = (ta > 0.5) & (arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"] | head_m) & ~leg_m
    rgb, a = piece(tor_m, tr, ta, hid_t)
    a = np.where(leg_m, 0.0, a)
    a = np.where((yy > 850) & ((rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) < 420), 0.0, a)   # dark specks / outline bits under the hem
    a = np.where((yy > 866) & (xx > 540), 0.0, a)                                          # stray corner spike past the hem
    # where the torso meets an arm, its edge is the generated layer's dark outline: use the key's own knit there and
    # feather the last few px so a swinging sleeve slides out from under a soft edge instead of a drawn line
    arm_any = ndimage.binary_dilation(arm_m["far"] | arm_m["near"], iterations=3)
    inner = ndimage.distance_transform_edt(a > 0.5)
    band = arm_any & (inner < 7) & (a > 0)
    rgb = np.where(band[..., None] & vis[..., None], kr, rgb)
    a = np.where(band, a * np.clip(inner / 6.0, 0, 1), a)
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
        fm = (fa > 0.5) & ndimage.binary_dilation(hand_m[side], iterations=14) & (yy > top + 4) & ((fr[..., 0] - fr[..., 1] > 14) | (d > 60))
        fm = clean(fm, close=2)
        fm = ndimage.binary_dilation(fm, iterations=1) & (fa > 0.02)
        frgb = np.where((stub & ~fm)[..., None], skin_c, fr)
        fal = np.maximum(np.where(fm, fa, 0.0), stub.astype(np.float32))
        save(f"fist_{side}", frgb, fal, parts)
        REP[f"wrist_{side}"] = [cx, top]
    for side, sel in (("far", far), ("near", near)):
        cap = (aa > 0.5) & sel & ndimage.binary_dilation(tsil, iterations=3) & ndimage.binary_dilation(arm_m[side], iterations=40)   # hidden behind the torso (overlaps the arm's own edge: no 1-px gap)
        rgb, a = piece(arm_m[side], ar, aa, cap)
        # the torso's armhole line is drawn on the key just outside the torso layer: on the arm it shows as a stray seam
        seam = ndimage.binary_dilation(tsil, iterations=7) & ~ndimage.binary_dilation(tsil, iterations=0) & arm_m[side]
        dark = seam & ((rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) < 520) & (aa > 0.5)
        rgb = np.where(dark[..., None], ar, rgb)
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

    order_out = ["apple", "leg_far", "leg_near", "pelvis", "hand_far", "fist_far", "arm_far", "hand_near", "fist_near", "arm_near", "torso", "apple_held", "head", "ribbon_tail"]
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
