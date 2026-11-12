"""米丫子 face states -> canvas-space parts.

Every state is an edit of the same bald face crop (gen/facecrop_x3.png = face_01 (300,230)+ x3).  Each state image is
registered back onto that crop (ECC on the part of the face it did not change), then cut as a feathered patch
(skin + feature) that covers the base face's own feature, so swapping states never shows what is underneath.
Open eyes are three layers so the gaze can move: eye_white patch, iris, upper lashes.
Brows are lifted off the base face (the face is in-painted there) so BrowY can move them.

    python3 states.py   (after layers.py)   ->  gen/P_*.png (full-canvas RGBA) + states-report.json + evidence/states/*.png
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
GEN, EV = HERE / "gen", HERE / "evidence" / "states"
W, H = 1024, 1536
CW, CH = 1260, 900                                  # crop space (x3)
CROP_O, CROP_K = (300, 230), 3
REG = json.loads((HERE / "layers-report.json").read_text())["face"]


def to_canvas_matrix():
    s, dx, dy = REG["scale"], REG["dx"], REG["dy"]
    k = s / CROP_K
    tx = CROP_O[0] * s + 512 * (1 - s) + dx
    ty = CROP_O[1] * s + 768 * (1 - s) + dy
    # vertical correction measured on the jaw: the generated face is 4.5 % taller below the eyes than the key art
    ky, y0 = YFIX
    return np.array([[k, 0, tx], [0, k * ky, y0 + (ty - y0) * ky]], np.float64)


YFIX = (0.955, 270.0)


def warp_to_canvas(rgba):
    M = to_canvas_matrix()
    return cv2.warpAffine(rgba, M, (W, H), flags=cv2.INTER_AREA if M[0, 0] < 1 else cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def load_crop(f):
    return np.asarray(Image.open(GEN / f).convert("RGB").resize((CW, CH), Image.LANCZOS)).astype(np.float32)


def ecc_register(img, ref, mask):
    """affine that maps img onto ref, solved coarse (1/4) then fine (1/2), on the masked (unchanged) region"""
    g = lambda x: cv2.cvtColor(np.clip(x, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    warp = np.eye(2, 3, dtype=np.float32)
    for f in (0.25, 0.5):
        size = (int(CW * f), int(CH * f))
        a = cv2.GaussianBlur(cv2.resize(g(ref), size), (5, 5), 0)
        b = cv2.GaussianBlur(cv2.resize(g(img), size), (5, 5), 0)
        mk = cv2.resize(mask.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
        w = warp.copy()
        w[:, 2] *= f
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6)
        try:
            _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, crit, mk, 1)
        except cv2.error:
            pass
        w[:, 2] /= f
        warp = w
    sx, sy = np.hypot(*warp[:, 0]), np.hypot(*warp[:, 1])
    if abs(sx - 1) > 0.06 or abs(sy - 1) > 0.06 or np.abs(warp[:, 2]).max() > 40:      # diverged: translation only
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            _, warp = cv2.findTransformECC(cv2.resize(g(ref), (CW // 2, CH // 2)), cv2.resize(g(img), (CW // 2, CH // 2)), warp, cv2.MOTION_TRANSLATION,
                                           (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), cv2.resize(mask.astype(np.uint8), (CW // 2, CH // 2), interpolation=cv2.INTER_NEAREST), 5)
            warp[:, 2] *= 2
        except cv2.error:
            warp = np.eye(2, 3, dtype=np.float32)
    out = cv2.warpAffine(img, warp, (CW, CH), flags=cv2.INTER_CUBIC + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    return out, warp


def ellipse(cx, cy, rx, ry, feather):
    yy, xx = np.mgrid[0:CH, 0:CW]
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return np.clip((1 - d) * min(rx, ry) / feather, 0, 1)


def lum(x):
    return x[..., 0] * 0.3 + x[..., 1] * 0.59 + x[..., 2] * 0.11


def save_canvas(name, rgb, a):
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.float32)
    c = warp_to_canvas(rgba)
    c[..., 1] = np.minimum(c[..., 1], c[..., 0])                         # no green anywhere on this character
    Image.fromarray(np.clip(c, 0, 255).astype(np.uint8), "RGBA").save(GEN / f"P_{name}.png")
    return c


EYE = {"L": (315, 298, 200, 112), "R": (915, 290, 200, 112)}       # cx, cy, rx, ry in crop space (lashes included)
MOUTH = (630, 700, 150, 112)


def main():
    EV.mkdir(parents=True, exist_ok=True)
    ref = load_crop("facecrop_x3.png")
    rep = {}
    yy, xx = np.mgrid[0:CH, 0:CW]
    upper = (yy < 470) & (xx > 120) & (xx < 1140)                     # forehead + eyes
    lower = (yy > 450) & (xx > 300) & (xx < 960)                      # nose, mouth, chin
    face_skin = (lum(ref) > 150) & (ref[..., 1] > 120) & (ref[..., 0] > ref[..., 1])
    sheets = []

    states = {}
    for f, kind in (("st_eyes_closed", "eye"), ("st_eyes_half", "eye"), ("st_eyes_smile", "eye"), ("st_eyes_white", "eye"),
                    ("st_mouth_a", "mouth"), ("st_mouth_aa", "mouth"), ("st_mouth_o", "mouth"), ("st_mouth_smile", "mouth")):
        img = load_crop(f + ".png")
        if kind == "eye":
            not_eyes = np.ones((CH, CW), bool)
            for (ecx, ecy, erx, ery) in EYE.values():
                not_eyes &= ellipse(ecx, ecy - 40, erx + 40, ery + 110, 1) <= 0
            keep = not_eyes & (lum(ref) > 60) & ((ref[..., 1] > 100) | (lum(ref) < 140))
        else:
            keep = upper & face_skin
        out, warp = ecc_register(img, ref, keep)
        d = np.abs(out - ref).sum(-1)
        rep[f] = {"warp": warp.round(4).tolist(), "residual_on_unchanged": round(float(d[keep].mean()), 2)}
        states[f] = out

    # ---------------- eyes
    white = states["st_eyes_white"]
    for s, (cx, cy, rx, ry) in EYE.items():
        patch_a = ellipse(cx, cy, rx, ry, 26)
        # white patch: sclera + lashes on skin, covers the base eye completely
        save_canvas(f"eye_white_{s}", white, patch_a)
        # iris: what the base face has that the white state does not, inside the eye opening, minus the lashes
        diff = np.abs(ref - white).sum(-1)
        Lr, Lw = lum(ref), lum(white)
        lash = (Lr < 105) & (Lw < 105) & (patch_a > 0.5)
        mx_, mn_ = ref.max(-1), ref.min(-1)
        warm = (mx_ - mn_ > 55) & (ref[..., 0] > ref[..., 2])          # saturated amber / rose iris colours
        iris = (diff > 60) & (patch_a > 0.6) & ~lash & (warm | (Lr < 90))
        iris = ndimage.binary_opening(iris, iterations=2)
        lab, n = ndimage.label(iris)
        iris = lab == 1 + int(np.argmax(ndimage.sum(iris, lab, range(1, n + 1))))
        iris = ndimage.binary_fill_holes(ndimage.binary_closing(iris, iterations=4))
        ys0, xs0 = np.where(iris)
        r_ = 0.62 * np.ptp(ys0)                                             # keep a round iris (drop lid / lash bits beside it)
        iris &= (xx - xs0.mean()) ** 2 + ((yy - ys0.mean()) * 0.9) ** 2 < r_ ** 2
        ia = np.clip(ndimage.gaussian_filter(ndimage.binary_dilation(iris, iterations=2).astype(np.float32), 1.2) * 1.5, 0, 1)
        save_canvas(f"iris_{s}", ref, ia)
        ys, xs = np.where(iris)
        rep[f"iris_{s}"] = {"cx": float(xs.mean()), "cy": float(ys.mean()), "w": int(np.ptp(xs)), "h": int(np.ptp(ys))}
        # upper lashes over the iris: dark pixels in the top part of the opening, from the base face
        top_band = yy < (ys.mean() + 0.05 * np.ptp(ys))
        lm = (Lr < 110) & (patch_a > 0.3) & top_band
        lm = ndimage.binary_opening(lm, iterations=1)
        la = np.clip(ndimage.gaussian_filter(lm.astype(np.float32), 0.9) * 1.4, 0, 1)
        save_canvas(f"lash_{s}", ref, la)
        for k in ("closed", "half", "smile"):
            save_canvas(f"eye_{k}_{s}", states[f"st_eyes_{k}"], patch_a)
    # ---------------- mouths (closed = the base face's own mouth area, as a patch too, so all mouths swap in one slot)
    cx, cy, rx, ry = MOUTH
    ma = ellipse(cx, cy, rx, ry, 30)
    save_canvas("mouth_closed", ref, ma)
    for k in ("a", "aa", "o", "smile"):
        save_canvas(f"mouth_{k}", states[f"st_mouth_{k}"], ma)

    # ---------------- brows: lifted off the face layer (canvas space), the face is in-painted underneath
    face = np.asarray(Image.open(GEN / "L_face.png")).astype(np.float32)
    ky, y0 = YFIX
    face = cv2.warpAffine(face, np.array([[1, 0, 0], [0, ky, y0 * (1 - ky)]], np.float64), (W, H), flags=cv2.INTER_CUBIC, borderValue=0)
    rgb, a = face[..., :3], face[..., 3] / 255
    Lf = lum(rgb)
    skin_ref = np.median(rgb[(a > 0.95) & (Lf > 170)], 0)
    M = to_canvas_matrix()
    brows = {}
    for s, (cx, cy, rx, ry) in EYE.items():
        bx, by = M @ np.array([cx, cy - 165, 1.0])
        bw, bh = rx * M[0, 0] * 1.1, 34
        box = np.zeros((H, W), bool)
        box[int(by - bh):int(by + bh), int(bx - bw):int(bx + bw)] = True
        inner = ndimage.binary_erosion(a > 0.9, iterations=18)          # keep away from the head outline at the temples
        m = box & inner & (Lf < np.median(Lf[box & inner]) - 12)
        m = ndimage.binary_opening(m, iterations=1)
        lab, n = ndimage.label(m)
        if n:
            sz = ndimage.sum(m, lab, range(1, n + 1))
            m = np.isin(lab, 1 + np.where(sz >= max(40, sz.max() * 0.25))[0])
        brows[s] = m
        ys, xs = np.where(m)
        rep[f"brow_{s}"] = {"cx": float(xs.mean()), "cy": float(ys.mean()), "w": int(np.ptp(xs)), "px": int(m.sum())}
        ba = np.clip(ndimage.gaussian_filter(ndimage.binary_dilation(m, iterations=2).astype(np.float32), 1.0) * 1.5, 0, 1)
        Image.fromarray(np.clip(np.dstack([rgb, ba * 255]), 0, 255).astype(np.uint8), "RGBA").save(GEN / f"P_brow_{s}.png")
    allb = ndimage.binary_dilation(brows["L"] | brows["R"], iterations=5)
    inp = cv2.inpaint(np.clip(rgb, 0, 255).astype(np.uint8), allb.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA).astype(np.float32)
    sm = ndimage.gaussian_filter(inp, sigma=(4, 4, 0))
    w_ = ndimage.gaussian_filter(allb.astype(np.float32), 2.5)[..., None]
    rgb2 = inp * (1 - w_) + sm * w_
    Image.fromarray(np.clip(np.dstack([rgb2, a * 255]), 0, 255).astype(np.uint8), "RGBA").save(GEN / "P_face.png")

    # ---------------- blush overlay (soft pink, for Cheek): centred under each eye
    for s, (cx, cy, rx, ry) in EYE.items():
        pass
    bl = np.zeros((CH, CW), np.float32)
    for s, (cx, cy, rx, ry) in EYE.items():
        bl = np.maximum(bl, np.clip(1 - np.sqrt(((xx - cx) / 150) ** 2 + ((yy - (cy + 170)) / 80) ** 2), 0, 1) ** 1.6)
    pink = np.ones((CH, CW, 3), np.float32) * np.array([240, 130, 140], np.float32)
    save_canvas("blush", pink, bl * 0.8)

    (HERE / "states-report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v.get("residual_on_unchanged", v) for k, v in rep.items()}, indent=1))


if __name__ == "__main__":
    main()
