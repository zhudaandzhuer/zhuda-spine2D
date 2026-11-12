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
SHP = {"far": (335, 380), "near": (560, 360)}        # shoulder pivots (rig.py SH) and elbows (EL)
ELP = {"far": (282, 540), "near": (615, 540)}


def along(side, xx, yy):
    """distance along the upper-arm axis from the shoulder pivot (negative = above / behind the joint)"""
    (sx, sy), (ex, ey) = SHP[side], ELP[side]
    L = np.hypot(ex - sx, ey - sy)
    return ((xx - sx) * (ex - sx) + (yy - sy) * (ey - sy)) / L
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


def smooth_cut(rgb, a, ka, sigma=1.6, zone=None):
    """Smooth + anti-alias the edges a part got from a colour/mask cut INSIDE the key's silhouette (the outer silhouette
    keeps the key's own soft alpha).  New edge pixels take the colour of their opaque neighbours."""
    m = a > 0.5
    sm = ndimage.gaussian_filter(m.astype(np.float32), sigma) > 0.5
    aa = np.clip((ndimage.gaussian_filter(sm.astype(np.float32), 0.7) - 0.5) * 2.2 + 0.5, 0, 1)
    edge = m ^ ndimage.binary_erosion(m, iterations=1)
    cut = ndimage.binary_dilation(edge, iterations=4) & ndimage.binary_erosion(ka > 0.9, iterations=1)
    if zone is not None:
        cut &= zone
    w = m.astype(np.float32)
    num = ndimage.gaussian_filter(rgb * w[..., None], (3, 3, 0))
    den = ndimage.gaussian_filter(w, 3)[..., None]
    fill = np.where(den > 1e-3, num / np.maximum(den, 1e-3), rgb)
    rgb = np.where((cut & ~m)[..., None], fill, rgb)
    return rgb, np.where(cut, aa, a)


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
    _ref = (la > 0.95) & (ka > 0.95) & (yy > 940) & (yy < 1350) & ((B > R + 8) & (B > 100))
    for c_ in range(3):
        mk, sk = kr[..., c_][_ref].mean(), kr[..., c_][_ref].std()
        ml, sl = lr[..., c_][_ref].mean(), lr[..., c_][_ref].std()
        lr[..., c_] = np.clip((lr[..., c_] - ml) * (sk / max(sl, 1e-3)) + mk, 0, 255)
    REP["legs_colour_match"] = True

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
    lav = (B > G + 12) & (B > 170) & ndimage.binary_dilation(clean(ta > 0.5), iterations=6)   # the tee (not the grey-lilac shade on a cuff)
    arm_m, hand_m, wrist = {}, {}, {}
    CUFF = {}
    CORNER = {}
    arm_sil = np.zeros((H, W), bool)
    asil = clean(aa > 0.5, close=2, fill=True)
    tsil = clean(ta > 0.5)
    for side, sel in (("far", far), ("near", near)):
        sil = asil & sel
        # arm = key pixels in the arm silhouette that the torso layer does not explain (or that lie outside it)
        own = vis & ndimage.binary_dilation(sil, iterations=8) & sel & ~ndimage.binary_dilation(tsil, iterations=1) & ~lav & ~dj      # the armhole edge belongs to the torso
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
        CUFF[side] = (hm & vis & (yy < htop + 18), htop)       # the sleeve overlaps the top of the hand's cuff (no seam)
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

    _knit = tor_m & (yy > 700) & (R > B + 15) & (R > 110)
    _cols = np.arange(W)
    HL = np.array([np.where(_knit[:, c])[0].max() if _knit[:, c].any() else -1 for c in _cols], float)
    _v = HL >= 862
    HL = np.interp(_cols, _cols[_v], HL[_v])                    # the cardigan's bottom edge, bridged across the opening
    HLy = HL[None, :]
    _lum = lambda c: c.sum(-1)
    front_of_legs = tor_m | arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"]
    gap = [(466, 700), (466, 950), (465, 990), (462, 1030), (457, 1070), (453, 1110), (448, 1150), (440, 1190), (434, 1230),
           (431, 1310), (427, 1390), (423, 1470), (420, 1510), (414, 1550), (410, 1672)]
    gx = np.interp(yy, [g[1] for g in gap], [g[0] for g in gap])
    # above the crotch the far thigh's inner top is behind the near thigh: give the far leg a rounded inner top
    # (curving from the crotch up and out to x=410 at the hem) and let the near leg own that strip
    t_ = np.clip((1012 - yy) / 140.0, 0, 1)
    gx = np.where(yy < 1012, 462 - (1012 - yy) * 0.25, gx)     # far leg's inner seam: the crotch fabric goes with the near leg
    lfar, lnear = xx < gx, xx >= gx
    TORSO_LOOSE = {}
    KNEE_C = {"far": (342, 1220), "near": (548, 1220)}
    for side, sel in (("far", lfar | ((xx < gx + 4) & (yy < 1150) & (la > 0.5))), ("near", lnear)):
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
        # hidden under the cardigan (above its bottom edge): the clean generated denim.  Visible below it: the key art,
        # except a 6 px band right under the edge, where the key carries the hem's drawn outline -- that band is the
        # generated denim shaded to the key's own brightness (keeps the contact shadow, drops the line)
        hidden_ = sel & (la > 0.5) & (yy > 600) & (yy <= HLy + 1)
        band_ = sel & (la > 0.5) & (yy > HLy + 1) & (yy < HLy + 7) & ~((B > R - 12) & ((R + G + B) < 620) & ((R + G + B) > 250))   # only the drawn outline
        shade = ndimage.gaussian_filter(_lum(kr), 3) / np.maximum(ndimage.gaussian_filter(_lum(lr), 3), 1)
        rgb = np.where((hidden_ & ~(vis & ~tor_m))[..., None], lr, rgb)
        rgb = np.where(band_[..., None], np.clip(lr * np.clip(shade, 0.4, 1.3)[..., None], 0, 255), rgb)
        a = np.where(hidden_ | band_, np.maximum(a, la), a)
        brownish = (R > B + 10) & (yy < HEM_Y + 40) & ~(B > R - 12)
        a = np.where(brownish & (yy < 905) & ~((la > 0.5) & sel), 0.0, a)
        a_pre = a.copy()
        # hidden top (above the hip joint, under the hem): a half-disc round the joint, so a kick / step never swings a
        # corner of it out behind the body.  Pixels the key shows at rest (below the hem line) are kept.
        hx, hy = {"far": (380, 880), "near": (515, 880)}[side]
        row_ = np.where(a[905] > 0.5)[0]
        rr = (row_.max() - row_.min()) / 2.0 + 4 if len(row_) else 60
        dd_ = np.hypot(xx - (row_.max() + row_.min()) / 2.0 if len(row_) else xx - hx, yy - hy)
        disc_ = np.clip((rr - dd_) / 1.5, 0, 1)
        # ball joint: above the joint the thigh is exactly a half-disc (hidden under the cardigan / pelvis at rest)
        a = np.where(yy < hy, np.where(yy > HLy - 2, np.maximum(a_pre * (disc_ > 0), a_pre * disc_), np.maximum(a_pre, la * (la > 0.5)) * disc_), a_pre)
        lrgb = rgb
        rgb = np.where(((yy < hy) & (yy <= HLy - 2) & ~(vis & ~tor_m))[..., None], lr, rgb)   # key pixels stay key
        REP[f"hipdisc_{side}"] = round(float(rr), 1)
        if side == "near":                                                             # soft inner edge over the far leg
            a = np.where((yy < 1150) & (xx >= gx), a * np.clip((xx - gx) / 2.0, 0, 1), a)
        else:                                                                          # far leg's inner edge (seen on kicks):
            dx_ = gx + 3.5 - xx                                                        # opaque under the near leg's soft edge                                                          # anti-aliased, with a drawn-like shade
            a = np.where((yy > 856) & (yy < 1150), a * np.clip(dx_ / 1.5, 0, 1), a)
            pass
        keep = clean(a > 0.3, close=1, fill=False)                       # no floating islands
        a = a * ndimage.binary_dilation(keep, iterations=2)
        kx, ky = KNEE_C[side]
        row = (a[ky] > 0.5)
        xs_ = np.where(row)[0]
        hw = (xs_.max() - xs_.min()) / 2.0
        kcx = (xs_.max() + xs_.min()) / 2.0
        REP[f"knee_{side}"] = [float(kcx), ky, float(hw)]
        disc = ((xx - kcx) / (hw + 1.0)) ** 2 + ((yy - ky) / (hw * 0.9)) ** 2
        tmask = np.clip((1.06 - disc) / 0.12, 0, 1)                  # soft-edged knee cap (ellipse) on the thigh
        tmask = np.where(yy < ky, 1.0, tmask)
        _tc = ndimage.binary_dilation(tor_m, iterations=2)
        a = np.where((yy > 862) & ~_tc, np.minimum(a, np.maximum(ka, 0.0)), a)     # visible below the hem: never wider than the key
        # hidden (generated) vs shown (key) denim: match the generated part's brightness to the key next to it and
        # cross-fade over ~12 px, so a thigh that rotates out from under the hem shows no seam line
        shown_ = vis & ~tor_m & (a > 0.5) & (B > R - 12)
        hid_ = (a > 0.5) & ~(vis & ~tor_m) & (yy < 1000)
        if shown_.any() and hid_.any():
            d_sh = ndimage.distance_transform_edt(~shown_)
            near_ = shown_ & (ndimage.distance_transform_edt(~hid_) < 16)
            lk = _lum(kr)[near_].mean(); ll = _lum(lr)[near_ & (la > 0.5)].mean() if (near_ & (la > 0.5)).any() else lk
            lr_m = np.clip(lr * (lk / max(ll, 1)), 0, 255)
            rgb = np.where(hid_[..., None], lr_m, rgb)
            w_ = np.clip(1 - d_sh / 12.0, 0, 1)[..., None] * hid_[..., None]        # hidden side near the border: lean to key colour
            kb = ndimage.grey_dilation(np.where(shown_[..., None], kr, 0), size=(5, 5, 1))
            rgb = np.where(hid_[..., None] & (d_sh[..., None] < 12), rgb * (1 - w_ * 0.5) + kb * (w_ * 0.5), rgb)
            # the strip right under the hem carries the cardigan's drawn shadow line in the key: on a moving thigh it would
            # show as a stripe.  Clean (matched) denim there, cross-faded into the key below; the rigid seat strip of the
            # pelvis shows the key's own pixels at rest.
            # keep the key's soft contact shadow as a smooth brightness ramp (measured relative to the hem line), not its line
            rel_ = (yy - HLy).astype(int)
            ratio = np.ones(40)
            for r_ in range(40):
                m_ = shown_ & (rel_ == r_) & (la > 0.5)
                if m_.sum() > 5:
                    ratio[r_] = _lum(kr)[m_].mean() / max(_lum(lr_m)[m_].mean(), 1)
            ok_ = ratio != 1.0
            if ok_.any():
                ratio = np.interp(np.arange(40), np.where(ok_)[0], ratio[ok_])
            ratio = ndimage.gaussian_filter1d(ratio, 2)
            ramp = ratio[np.clip(rel_, 0, 39)]
            lr_m = np.clip(lr_m * np.where((rel_ >= 0) & (rel_ < 40), ramp, 1.0)[..., None], 0, 255)
            ft = np.clip((yy - (HLy + 12)) / 14.0, 0, 1)[..., None]
            top_ = (a > 0.02)[..., None] & (yy < HLy + 26)[..., None] & (la > 0.3)[..., None]
            rgb = np.where(top_, lr_m * (1 - ft) + rgb * ft, rgb)
        if side == "far":
            # inner thigh, hidden behind the near leg at rest: a curved extension past the split line, so a lifted near
            # leg uncovers far-leg denim (not background, not a straight edge)
            wext = 30 * np.sqrt(np.clip((918 - yy) / 60.0, 0, 1))           # rounded, ends at the crotch seam
            ext = (yy > 858) & (yy < 918) & (xx >= gx)
            ea = np.clip((gx + wext - xx) / 1.5, 0, 1) * ext
            refm = (a > 0.9) & vis & (yy > 900) & (yy < 1060) & (xx > gx - 60) & (xx < gx) & (la > 0.5)
            gain = np.array([kr[..., c][refm].mean() / max(lr[..., c][refm].mean(), 1) for c in range(3)]) if refm.any() else np.ones(3)
            src_ = np.clip(lr * gain, 0, 255) * 0.92                         # generated denim, matched, a touch darker (inner side)
            rgb = np.where((ea > 0)[..., None] & (a < 0.5)[..., None], src_, rgb)
            REP["far_ext_gain"] = [round(float(g), 3) for g in gain]
            dk = (xx > gx - 14) & (yy > 858) & (yy < 1000) & (_lum(rgb) < 250) & (a > 0)      # crotch shadow line -> denim
            rgb = np.where(dk[..., None], np.clip(lr * gain, 0, 255) * 0.85, rgb)
            a = np.maximum(a, ea * (yy > HLy - 2))
        save(f"leg_{side}", rgb, a, parts)          # one mesh per leg; the knee bends as a narrow crease (rig weights)
    # pelvis: the seat of the jeans from the waistband down to the crotch seam, rigid on the hip bone and drawn over
    # both leg tops.  The thighs pivot underneath it, so their stretched tops never show below the hem.
    from PIL import ImageDraw as _D, ImageFilter as _F
    V = [(282, 760), (568, 760), (568, 872), (540, 884), (505, 902), (480, 914), (462, 918), (444, 914), (420, 902),
         (385, 886), (330, 878), (286, 872)]
    _im = Image.new("L", (W, H), 0)
    _D.Draw(_im).polygon(V, fill=255)
    pz = np.asarray(_im.filter(_F.GaussianBlur(1.2))).astype(np.float32) / 255
    inside = pz > 0.5
    hem_shadow = (yy > 850) & (yy < HEM_Y + 30) & ((R + G + B) < 420) & ~((R > 200) & (R - B < 45))
    own_key = inside & vis & ((leg_m & (B > R - 12) & ((R + G + B) < 620)) | hem_shadow) & ~arm_sil
    fk = np.clip(ndimage.gaussian_filter(own_key.astype(np.float32), 2.5), 0, 1)[..., None]
    prgb = kr * fk + lr * (1 - fk)
    pa = np.maximum(np.where(own_key, ka, 0.0), la) * pz
    tm_ = tor_m & (yy > 700) & (kr[..., 0] > kr[..., 2] + 15) & (kr[..., 0] > 110)     # the cardigan knit only (not the tee)
    cols = np.arange(W)
    tb = np.array([np.where(tm_[:, c])[0].max() if tm_[:, c].any() else -1 for c in cols], float)
    ok_ = tb > 0
    tb = np.interp(cols, cols[ok_], tb[ok_])
    _op = (tb < 862)                                                      # only true hem columns; the opening / placket edge is bridged
    tb = np.where(_op, np.nan, tb); _v = ~np.isnan(tb); tb = np.interp(cols, cols[_v], tb[_v])
    pa = pa * np.clip((tb[None, :] - 4 - yy) / 3.0, 0, 1)
    REP["pelvis_bottom_max"] = float(tb[280:570].max())
    # seat: a band of key pixels just under the hem (where the thighs join the body), rounded bottom edge, rigid on the
    # body.  At rest it is the key itself; when a thigh lifts it covers the thigh's top instead of leaving a cut stump.
    sx_ = (xx - 462) / 150.0
    # buttock: a rounded bulge (deepest mid-hip, curving up to the back outline), shallow at the crotch and front
    bul = np.sqrt(np.clip(1 - ((xx - 522) / 62.0) ** 2, 0, 1))             # 0 at the thigh's back outline (x~584)
    depth = 22 + 0 * bul                    # a thin strip only (soft lower half): the thighs' ball-joint tops do the rest
    sb = HLy + depth
    legvis = vis & leg_m & ~(arm_sil) & (xx > 290) & (xx < 620)
    seat = legvis & (yy > HLy - 8) & (yy < sb + 2)
    _l, _n = ndimage.label(seat)
    if _n > 1:
        seat = _l == 1 + int(np.argmax(ndimage.sum(seat, _l, range(1, _n + 1))))      # no stray specks
    seat = ndimage.binary_opening(seat, iterations=1) | (seat & (yy < HLy + 6))
    sa = np.clip((sb - yy) / 12.0, 0, 1) * seat                          # dissolves into the thigh below over 12 px
    prgb = np.where((sa > 0)[..., None], kr, prgb)
    pa = np.maximum(pa, sa * ka)
    REP["seat_px"] = int((sa > 0.5).sum())
    pa = np.where(vis & (R > B + 15) & (R > 110) & (yy > 830), 0.0, pa)    # cardigan knit is never on the seat (-> torso)
    crotch = np.zeros((H, W), bool)                                      # (a rigid crotch block showed its edges on kicks)
    pa = np.where((yy > HLy + 10) & ~crotch, sa * ka, pa)                # elsewhere below the hem: only the soft seat strip
    cz = crotch & (yy > HLy - 4) & (yy < 925) & vis & (B > R - 16) & ~((R > B + 15) & (R > 110))   # crotch at rest: the key
    shown = vis & ~ndimage.binary_erosion(tor_m, iterations=8)          # key pixels: what the key shows at rest + 8 px under the hem
    # hidden seat (seen only when the cardigan swings): generated denim, its brightness matched to the key around it and
    # cross-faded over 10 px, so no lighter block / edge appears
    den_sh = shown & (B > R - 12) & (pa > 0.5)
    wv = den_sh.astype(np.float32)
    lr_p = lr.copy()
    den_w = ndimage.gaussian_filter(wv, 25)
    for c_ in range(3):                                                   # per channel: hue + brightness
        nk = ndimage.gaussian_filter(kr[..., c_] * wv, 25); nl = ndimage.gaussian_filter(lr[..., c_] * wv, 25)
        g_ = kr[..., c_][den_sh].mean() / max(lr[..., c_][den_sh].mean(), 1) if den_sh.any() else 1.0
        r_ = np.where(den_w > 0.03, nk / np.maximum(nl, 1), g_)
        lr_p[..., c_] = np.clip(lr[..., c_] * np.clip(r_, 0.5, 1.6), 0, 255)
    d_s = ndimage.distance_transform_edt(~shown)
    wk = np.clip(1 - d_s / 10.0, 0, 1)[..., None]
    d_in = ndimage.distance_transform_edt(shown)                         # inside the shown part, distance to the hidden part
    near_b = shown & (d_in < 5)
    kr_c = np.where((near_b & (_lum(kr) < 300))[..., None], lr_p, kr)     # the cardigan's drawn edge line is not denim
    wb = np.clip((d_in - 1) / 5.0, 0, 1)[..., None]
    prgb = np.where(shown[..., None], kr_c * wb + lr_p * (1 - wb), lr_p)
    pa = np.where((xx < 330) & (yy > HLy + 2), 0.0, pa)                  # far side below the hem: the far thigh does it
    cz = cz & (yy < HLy + 14)
    prgb = np.where(cz[..., None], kr, prgb)
    pa = np.where(cz, np.maximum(pa, ka * np.clip((HLy + 14 - yy) / 8.0, 0, 1)), pa)
    # never wider than the jeans themselves (rounded hips, no rectangle corners when the cardigan swings away)
    jeans = ndimage.binary_erosion(la > 0.5, iterations=2) | (vis & (B > R - 12) & (yy > 820))
    jsoft = np.clip(ndimage.gaussian_filter(jeans.astype(np.float32), 1.2) * 1.3, 0, 1)
    pa = pa * jsoft
    # shorts-shaped outline: bottom curves from the hip sides (y~846) down to the crotch (y~918), sides follow the jeans
    hw_ = np.where(xx < 462, 172.0, 140.0)
    u_ = np.clip(np.abs(xx - 462) / hw_, 0, 1)
    bot_ = 846 + 72 * np.cos(np.pi / 2 * u_) ** 1.3
    shorts = np.clip((bot_ - yy) / 1.5, 0, 1) * (yy > 740)
    pa = np.minimum(pa, shorts) if False else pa * shorts
    _sm = ndimage.gaussian_filter((pa > 0.5).astype(np.float32), 9) > 0.5      # rounded corners everywhere
    _sm = _sm | (shown & (pa > 0.5) & (yy > 846))                             # the key-shown crotch keeps its own shape
    pa = pa * np.clip((ndimage.gaussian_filter(_sm.astype(np.float32), 0.8) - 0.5) * 2.2 + 0.5, 0, 1)
    pa = pa * ndimage.binary_opening(pa > 0.3, iterations=2)          # no specks / thin lines
    REP["pelvis_bottom_curve"] = [846, 918]
    save("pelvis", prgb, pa, parts)
    hid_t = (ta > 0.5) & (arm_m["far"] | arm_m["near"] | hand_m["far"] | hand_m["near"] | head_m) & ~leg_m
    rgb, a = piece(tor_m, tr, ta, hid_t)
    a = np.where(leg_m, 0.0, a)
    _cr = (kr[..., 0] > 185) & (kr[..., 0] - kr[..., 2] < 55) & vis
    _outline = ndimage.binary_dilation(_cr, iterations=4) & (yy < HEM_Y + 16)          # the hem's own drawn edge stays
    a = np.where((yy > 850) & ((rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) < 420) & ~_outline, 0.0, a)   # dark specks under the hem
    cream_t = (rgb[..., 0] > 185) & (rgb[..., 0] - rgb[..., 2] < 55)
    warm_t = (rgb[..., 0] > rgb[..., 2] + 15) & (rgb[..., 0] > 110)          # knit (also in shade); denim is never warm
    a = np.where((yy > 866) & (xx > 540) & ~warm_t, 0.0, a)
    lav_t = (rgb[..., 2] > rgb[..., 1] + 8) & (rgb[..., 2] > 150)
    brown_t = (rgb[..., 0] > rgb[..., 2] + 25) & (rgb[..., 0] < 200)
    a = np.where((yy > 760) & ~warm_t & ~lav_t & ~brown_t & ~_outline & (xx > 330) & (xx < 540), 0.0, a)   # denim scraps in the opening
    lab_t, n_t = ndimage.label(a > 0.3)
    if n_t > 1:
        sz_t = ndimage.sum(a > 0.3, lab_t, range(1, n_t + 1))
        main_t = lab_t == 1 + int(np.argmax(sz_t))
        loose = (a > 0.3) & ~main_t & np.isin(lab_t, 1 + np.where(sz_t > 400)[0])
        TORSO_LOOSE["far"] = loose & far
        TORSO_LOOSE["near"] = loose & near
        a = np.where(ndimage.binary_dilation(main_t, iterations=2), a, 0.0)                                          # stray corner spike past the hem
    # where the torso meets an arm, its edge is the generated layer's dark outline: use the key's own knit there and
    # feather the last few px so a swinging sleeve slides out from under a soft edge instead of a drawn line
    nz = ndimage.binary_dilation(arm_m["near"], iterations=14) & (yy < 760) & (ta > 0.5)
    rgb = np.where((nz & ~(a > 0.5))[..., None], tr, rgb)
    a = np.where(nz, np.maximum(a, ta), a)
    rgb, a = smooth_cut(rgb, a, ka, sigma=1.8)
    for side in ("far", "near"):
        t_ = along(side, xx, yy)
        top_ = (t_ < 34) & ndimage.binary_dilation(arm_m[side], iterations=2) & (ka > 0.02) & (np.hypot(xx - SHP[side][0], yy - SHP[side][1]) < 120)
        rgb = np.where(top_[..., None], kr, rgb)
        a = np.where(top_, ka, a)
    # the back of the cardigan behind the near arm hangs straight from the shoulder to the hip (the generated torso
    # layer pinches in there like a vest).  Fill out to that line with the torso's own knit, shifted sideways.
    yb = np.clip((yy - 372) / (752 - 372), 0, 1)
    xback = 585 + (590 - 585) * yb + 10 * np.sin(np.pi * yb)            # slight outward drape
    m0b = a > 0.5
    zb = (yy > 372) & (yy < 752) & (xx < xback) & (xx > 470) & ~m0b
    # (the A-pose armpit gap gets filled too: every clip hangs the arm against it)
    src = np.roll(rgb, 46, axis=1)                                         # knit from 46 px further in
    srca = np.roll(a, 46, axis=1)
    fillk = np.where((along("near", xx, yy) < 36)[..., None] & vis[..., None], kr, src)
    edge_d = np.clip((xback - xx) / 6.0, 0, 1)
    fillk = fillk * (0.9 + 0.1 * edge_d)[..., None]                        # soft shade at the back edge
    rgb = np.where(zb[..., None], fillk, rgb)
    a = np.where(zb, np.clip(srca, 0, 1) * np.clip((xback - xx) / 1.5, 0, 1), a)
    REP["back_fill_px"] = int(zb.sum())
    kab = np.maximum(ka, ndimage.binary_dilation(zb, iterations=2).astype(np.float32))   # silhouette incl. the back fill
    # near shoulder (seen when the arm swings away): one smooth curve from the shoulder top down the side, no corner
    zs = (np.hypot(xx - SHP["near"][0], yy - SHP["near"][1]) < 200) & (yy < 700) & (xx > 480)
    m0 = a > 0.5
    _mc = ndimage.binary_closing(m0, iterations=10) & zs                   # close the dent left at the armpit
    _newc = _mc & ~m0
    rgb = np.where(_newc[..., None], np.roll(rgb, 46, axis=1), rgb)
    m0 = m0 | _mc
    ms = ndimage.gaussian_filter(m0.astype(np.float32), 9.0) > 0.5
    ms = (ms | (m0 & ~zs)) & (kab > 0.3)
    new_ = zs & ms & ~m0
    w_ = m0.astype(np.float32)
    fill_ = ndimage.gaussian_filter(rgb * w_[..., None], (4, 4, 0)) / np.maximum(ndimage.gaussian_filter(w_, 4), 1e-3)[..., None]
    rgb = np.where(new_[..., None], np.where(vis[..., None], kr, fill_), rgb)
    aa_ = np.clip((ndimage.gaussian_filter(ms.astype(np.float32), 0.7) - 0.5) * 2.2 + 0.5, 0, 1)
    a = np.where(zs & (kab > 0.9), aa_, np.where(zs, np.minimum(np.maximum(a, aa_), kab), a))
    _in = ndimage.distance_transform_edt(arm_m["near"])
    _eb = arm_m["near"] & (_in < 7) & (a > 0)                                 # under the near arm's edge: key colour (no sliver)
    rgb = np.where(_eb[..., None], kr, rgb)
    shz = (yy < 640) & ((np.hypot(xx - SHP["near"][0], yy - SHP["near"][1]) < 150) | (np.hypot(xx - SHP["far"][0], yy - SHP["far"][1]) < 150))
    a = np.where(shz, np.minimum(a, kab), a)            # shoulders: never outside the key silhouette
    # no holes / dents in the back behind the near arm (A-pose armpit): close + fill, knit from 46 px further in
    _bz = (yy > 380) & (yy < 760) & (xx > 470)
    _cl = ndimage.binary_fill_holes(ndimage.binary_closing(a > 0.5, iterations=6)) & _bz & ~(a > 0.5)
    rgb = np.where(_cl[..., None], np.roll(rgb, 46, axis=1), rgb)
    a = np.where(_cl, 1.0, a)
    REP["torso_back_holes_px"] = int(_cl.sum())
    # back outline behind the near arm: no dents -- fill out to the convex hull of the right edge (shoulder to hip)
    _rows = np.arange(300, 760)
    _re = np.array([np.where(a[r, 470:] > 0.5)[0].max() + 470 if (a[r, 470:] > 0.5).any() else -1 for r in _rows], float)
    _ok = _re > 0
    pts = [(float(_re[i_]), float(_rows[i_])) for i_ in np.where(_ok)[0]]
    hull = [pts[0]]
    for p_ in pts[1:]:                                   # monotone-chain right hull (rows increasing)
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p_[1] - y1) - (y2 - y1) * (p_[0] - x1) <= 0:      # hull[-1] is left of the chord: drop it
                hull.pop()
            else:
                break
        hull.append(p_)
    hy_ = np.array([h_[1] for h_ in hull]); hx_ = np.array([h_[0] for h_ in hull])
    _tgt = np.zeros(H); _tgt[_rows] = np.interp(_rows, hy_, hx_)
    _dent = (yy >= 300) & (yy < 760) & (xx > 470) & (xx < _tgt[:, None]) & ~(a > 0.5)
    rgb = np.where(_dent[..., None], np.roll(rgb, 40, axis=1), rgb)
    a = np.where(_dent, np.clip((_tgt[:, None] - xx) / 1.5, 0, 1), a)
    REP["torso_back_dent_px"] = int(_dent.sum())
    _m = a > 0.5
    _mo = ndimage.binary_opening(_m, iterations=2)
    _lab, _n = ndimage.label(_mo)
    _mo = _lab == 1 + int(np.argmax(ndimage.sum(_mo, _lab, range(1, _n + 1))))
    _sm = ndimage.gaussian_filter(_mo.astype(np.float32), 2.2) > 0.5          # smooth contour (no ragged colour-cut edge)
    _soft = np.clip((ndimage.gaussian_filter(_sm.astype(np.float32), 0.7) - 0.5) * 2.2 + 0.5, 0, 1)
    _bot = (yy > 840) & (xx > 250) & (xx < 620)                                 # only the hem line itself
    a = np.where(_bot, _soft * np.maximum(np.where(_sm, 1.0, 0.0), a > 0.5) , a)
    rgb = np.where((_bot & _sm & (a > 0) & ~_m)[..., None], ndimage.median_filter(rgb, size=(5, 5, 1)), rgb)
    save("torso", rgb, a, parts)
    skin_c = np.median(kr[hand_m["far"] & vis], 0)
    for side in ("far", "near"):
        cx, top, w = wrist[side]
        stub = np.zeros((H, W), bool)
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
        arm_m[side] = arm_m[side] | TORSO_LOOSE.get(side, np.zeros((H, W), bool))     # loose strips of sleeve-side knit ride on the arm
        cap = (aa > 0.5) & sel & (yy < 560) & ~arm_m[side] & (ka > 0.5)
        rgb, a = piece(arm_m[side], ar, aa, cap)
        _edge = cap & vis & (ndimage.distance_transform_edt(~arm_m[side]) < 14)      # seen through the torso's feathered edge
        rgb = np.where(_edge[..., None], kr, rgb)
        if side == "near":
            capv = cap & vis
            rgb = np.where(capv[..., None], kr, rgb)
            tt = along("near", xx, yy)
            f_ = np.clip((tt - 2) / 30.0, 0, 1)
            a = a * (f_ * f_ * (3 - 2 * f_))
        _k = a > 0.3                                       # keep only the main piece (no opening: it ate thin key slivers)
        _l, _n = ndimage.label(_k)
        _k = _l == 1 + int(np.argmax(ndimage.sum(_k, _l, range(1, _n + 1))))
        _k = ndimage.binary_dilation(ndimage.binary_fill_holes(_k), iterations=1)
        a = np.where(yy > 650, a * _k, a)                       # no stray specks / threads at the cuff (cuff zone only)
        # the torso's armhole line is drawn on the key just outside the torso layer: on the arm it shows as a stray seam
        seam = ndimage.binary_dilation(tsil, iterations=7) & ~ndimage.binary_dilation(tsil, iterations=0) & arm_m[side]
        dark = seam & ((rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) < 520) & (aa > 0.5)
        rgb = np.where(dark[..., None], ar, rgb)
        rgb, a = smooth_cut(rgb, a, ka, sigma=1.4, zone=(yy < CUFF[side][1] - 2))
        cm, ht = CUFF[side]
        cm = cm & ndimage.binary_opening(cm, iterations=2)                 # no thin slivers of the cuff edge
        a = np.where(cm, np.clip((ht + 18 - yy) / 8.0, 0, 1) * ka, a)
        lowz = yy > ht - 70
        _op = ndimage.binary_opening(a > 0.4, iterations=4)
        _op = ndimage.binary_dilation(_op, iterations=1)
        a = np.where(lowz, a * _op, a)
        rgb = np.where(cm[..., None], kr, rgb)
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

    # face: closed eyes / open mouth patches from the registered edits (feathered ellipses over the features only)
    for nm, lay, box in (("eyes_closed", "blink", (355, 128, 470, 192)), ("mouth_open", "talk", (372, 198, 424, 234))):
        er, ea = L(lay)
        dd = np.abs(er - kr).sum(-1)
        x0_, y0_, x1_, y1_ = box
        bm = np.zeros((H, W), bool)
        bm[y0_:y1_, x0_:x1_] = True
        m_ = ndimage.binary_dilation(ndimage.binary_closing((dd > 45) & bm, iterations=3), iterations=5) & bm
        m_ = ndimage.binary_fill_holes(m_)
        f_ = np.clip(ndimage.gaussian_filter(m_.astype(np.float32), 2.5) * 1.6, 0, 1)
        save(nm, er, f_ * ka, parts)
        REP[nm] = int(m_.sum())
    # apple held in the far hand (drawn into the hand) + the same painted apple on the floor
    pr_, pa_ = L("apple")
    dd = np.abs(pr_ - fr).sum(-1)
    cxw, topw, _w = wrist["far"]
    redish = (pr_[..., 0] > 110) & (pr_[..., 0] - pr_[..., 1] > 55)
    leafish = (pr_[..., 1] > pr_[..., 0] + 10) & (pr_[..., 1] < 200)
    zone = (yy > topw - 10) & (yy < topw + 230) & (xx > cxw - 170) & (xx < cxw + 120)
    hm_ = zone & (pa_ > 0.5) & ((dd > 40) | redish | skin(pr_)) & ~arm_m["far"]
    hm_ = clean(hm_, close=3)
    _l, _n = ndimage.label(hm_)                      # only the hand + apple blob (no leftovers of the old open hand)
    _c = ndimage.center_of_mass(redish & hm_)
    if _n > 1:
        hm_ = _l == _l[int(_c[0]), int(_c[1])] if _l[int(_c[0]), int(_c[1])] else _l == 1 + int(np.argmax(ndimage.sum(hm_, _l, range(1, _n + 1))))
    hm_ = ndimage.binary_fill_holes(hm_) & zone & ~ndimage.binary_dilation(arm_m["far"] & (yy < topw - 5), iterations=1)
    REP["held_apple"] = [float(_c[1]), float(_c[0])]
    hm_ = ndimage.binary_dilation(hm_, iterations=1) & (pa_ > 0.02)
    knit_a = (pr_[..., 0] > 200) & (pr_[..., 0] - pr_[..., 2] < 50) & (pr_[..., 1] > 185)       # cream knit of the edit
    core = (skin(pr_) | redish | leafish | ((pr_[..., 0] > 90) & (pr_[..., 0] < 170) & (pr_[..., 1] < 110))) & hm_
    core = clean(core, close=2)
    hm_ = hm_ & (~knit_a | (ndimage.distance_transform_edt(~core) < 20))     # only the cuff right at the hand
    _l, _n = ndimage.label(hm_)
    if _n > 1:
        hm_ = _l == 1 + int(np.argmax(ndimage.sum(hm_, _l, range(1, _n + 1))))
    hm_ = ndimage.binary_opening(hm_, iterations=1) | (hm_ & redish)
    save("hand_apple_far", pr_, np.where(hm_, pa_, 0.0), parts)
    gz = (yy > 1480) & (xx < 300) & (pa_ > 0.3)
    gm = clean(gz & (redish | leafish | (dd > 40)), close=3, fill=True)
    _l, _n = ndimage.label(gm)
    _rc = ndimage.center_of_mass(gz & redish)
    gm = _l == _l[int(_rc[0]), int(_rc[1])]                  # only the apple blob (no shoe-edge diffs)
    gm = ndimage.binary_dilation(gm, iterations=1)
    # contact shadow: whatever darkened green-screen the edit left under the apple becomes a soft dark ellipse
    ys_, xs_ = np.where(gm)
    acx, acy, abot = float(xs_.mean()), float(ys_.mean()), int(ys_.max())
    sh_ = np.clip(1 - (((xx - acx) / 52.0) ** 2 + ((yy - abot + 4) / 11.0) ** 2), 0, 1) * 0.45
    argb = np.where(gm[..., None], pr_, np.zeros_like(pr_) + 20)
    aal = np.maximum(np.where(gm, pa_, 0.0), np.where(gm, 0.0, sh_))
    save("apple", argb, aal, parts)
    REP["apple"] = [acx, acy]
    REP["apple_bottom"] = abot
    cov = np.zeros((H, W), np.float32)
    for q in parts:
        if q["name"].startswith("fist") or q["name"].startswith("apple") or q["name"] in ("hand_apple_far", "eyes_closed", "mouth_open"):
            continue
        pa_ = np.asarray(Image.open(OUT / q["file"])).astype(np.float32)[..., 3] / 255
        sub = cov[q["y"]:q["y"] + q["h"], q["x"]:q["x"] + q["w"]]
        sub[:] = 1 - (1 - sub) * (1 - pa_)
    orph = (ka > 0.3) & (cov < ka - 0.25) & (yy > 820) & (yy < HLy + 12) & (xx > 280) & (xx < 620)
    REP["orphan_px"] = int(orph.sum())
    knit_o = orph & (R > B + 15) & (R > 110) & (yy < HLy + 2)             # cardigan bits -> torso, denim -> pelvis
    for nm_, om_ in (("torso", knit_o), ("pelvis", orph & ~knit_o & ~((R > B + 15) & (R > 110)))):
        if not om_.any():
            continue
        q = [q for q in parts if q["name"] == nm_][0]
        P = np.zeros((H, W, 4), np.float32)
        P[q["y"]:q["y"] + q["h"], q["x"]:q["x"] + q["w"]] = np.asarray(Image.open(OUT / f"{nm_}.png")).astype(np.float32)
        P[..., :3] = np.where(om_[..., None], kr, P[..., :3])
        P[..., 3] = np.where(om_, np.maximum(P[..., 3], ka * 255), P[..., 3])
        parts.remove(q)
        save(nm_, P[..., :3], P[..., 3] / 255, parts)
    REP["orphan_knit_px"] = int(knit_o.sum())
    # global orphan pass: any key pixel no part shows at rest goes to the nearest part (key colour), so the rest pose has
    # no pinholes / notches anywhere (hem, cuffs, hair edges)
    skip_ = lambda n: n.startswith("fist") or n.startswith("apple") or n in ("hand_apple_far", "eyes_closed", "mouth_open")
    cov = np.zeros((H, W), np.float32); masks = {}
    for q in parts:
        if skip_(q["name"]):
            continue
        pa_ = np.zeros((H, W), np.float32)
        pa_[q["y"]:q["y"] + q["h"], q["x"]:q["x"] + q["w"]] = np.asarray(Image.open(OUT / q["file"])).astype(np.float32)[..., 3] / 255
        masks[q["name"]] = pa_ > 0.5
        cov = 1 - (1 - cov) * (1 - pa_)
    orph2 = (ka > 0.5) & (cov < ka - 0.3)
    orph2 = orph2 & ~ndimage.binary_opening(orph2, iterations=6)          # only small gaps (never re-adds big removed areas)
    REP["orphan_global_px"] = int(orph2.sum())
    if orph2.any():
        names_ = list(masks)
        dist = np.stack([ndimage.distance_transform_edt(~masks[n_]) for n_ in names_])
        who = np.argmin(dist, 0)
        for i_, n_ in enumerate(names_):
            om_ = orph2 & (who == i_) & (dist[i_] < 8)
            if not om_.any():
                continue
            q = [q for q in parts if q["name"] == n_][0]
            P = np.zeros((H, W, 4), np.float32)
            P[q["y"]:q["y"] + q["h"], q["x"]:q["x"] + q["w"]] = np.asarray(Image.open(OUT / q["file"])).astype(np.float32)
            P[..., :3] = np.where(om_[..., None], kr, P[..., :3])
            P[..., 3] = np.where(om_, np.maximum(P[..., 3], ka * 255), P[..., 3])
            parts.remove(q)
            save(n_, P[..., :3], P[..., 3] / 255, parts)
    order_out = ["apple", "hand_far", "fist_far", "hand_apple_far", "arm_far", "leg_far", "leg_near", "pelvis",
                 "torso", "hand_near", "fist_near", "arm_near", "head", "eyes_closed", "mouth_open", "ribbon_tail"]
    parts.sort(key=lambda q: order_out.index(q["name"]))
    (OUT / "manifest.json").write_text(json.dumps({"canvas": [W, H], "source": "parts.py", "parts": parts}, indent=1))
    m_ = {q["name"]: q for q in parts}
    c = Image.new("RGBA", (W, H), (30, 35, 50, 255))
    for n_ in order_out:
        if n_.startswith("fist") or n_.startswith("apple") or n_ in ("hand_apple_far", "eyes_closed", "mouth_open"):
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


def _old_apple():
    # (v057 flat apple, kept for reference; not called)
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
