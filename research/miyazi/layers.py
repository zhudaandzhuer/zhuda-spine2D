"""米丫子 layers: green-screen edits of gen/keyart.png -> registered, keyed, decontaminated RGBA layers on the key art canvas.

    python3 layers.py          -> gen/L_<name>.png (full canvas RGBA) + layers-report.json + evidence/layers/*.png

Registration: each layer is shifted / scaled (search) to best match the key art on the pixels the key art shows of it.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
GEN, EV = HERE / "gen", HERE / "evidence" / "layers"
W, H = 1024, 1536
GREEN = np.array([0, 255, 0], np.float32)


def load(f):
    return np.asarray(Image.open(GEN / f).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32)


def key(rgb):
    """colour-difference matte for a saturated green screen; un-mixes the green from soft edges"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    spill = g - np.maximum(r, b)                       # how green a pixel is beyond its other channels
    bg = np.median(rgb[:8].reshape(-1, 3), 0)
    full = bg[1] - max(bg[0], bg[2])
    a = 1 - np.clip(spill / max(full, 1), 0, 1)
    a = np.where(a < 0.06, 0, a)
    a = np.where(a > 0.94, 1, a)
    # largest pieces only (drop specks), holes inside the subject stay as keyed
    solid = a > 0.5
    lab, n = ndimage.label(solid)
    if n:
        s = ndimage.sum(solid, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(s >= max(60, s.max() * 0.002))[0])
        a = a * ndimage.binary_dilation(keep, iterations=3)
    a3 = a[..., None]
    col = np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), rgb)
    col = np.clip(col, 0, 255)
    # remaining green cast on edges: clamp G to max(R, B) where the pixel is semi-transparent
    # this character has no green anywhere: any pixel greener than its red channel is green-screen spill
    col[..., 1] = np.minimum(col[..., 1], col[..., 0])
    return col, a


def warp(rgb, a, sc, dx, dy):
    im = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
    cx, cy = W / 2, H / 2
    inv = (1 / sc, 0, cx - (cx + dx) / sc, 0, 1 / sc, cy - (cy + dy) / sc)
    o = np.asarray(im.transform((W, H), Image.AFFINE, inv, resample=Image.BICUBIC)).astype(np.float32)
    return o[..., :3], o[..., 3] / 255


def register(rgb, a, kr, ka, weight, scales=(0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03), shift=24):
    """best (scale, dx, dy) by mean colour error where both the layer and its visible part of the key art are opaque"""
    best = None
    small = 2
    kr_s = kr[::small, ::small]
    for sc in scales:
        r2, a2 = warp(rgb, a, sc, 0, 0)
        for dy in range(-shift, shift + 1, 2):
            for dx in range(-shift, shift + 1, 2):
                rr = np.roll(np.roll(r2, dy, 0), dx, 1)[::small, ::small]
                aa = np.roll(np.roll(a2, dy, 0), dx, 1)[::small, ::small]
                m = (aa > 0.95) & weight[::small, ::small]
                if m.sum() < 500:
                    continue
                e = float(np.abs(rr - kr_s).sum(-1)[m].mean())
                if best is None or e < best[0]:
                    best = (e, sc, dx, dy)
    e, sc, dx, dy = best
    for ddx in (-1, 0, 1):                                   # 1 px refine
        for ddy in (-1, 0, 1):
            r2, a2 = warp(rgb, a, sc, dx + ddx, dy + ddy)
            m = (a2 > 0.95) & weight
            e2 = float(np.abs(r2 - kr).sum(-1)[m].mean())
            if e2 < e:
                e, best = e2, (e2, sc, dx + ddx, dy + ddy)
    return best


EYE_LAYERS = {"face": (330, 250, 700, 420)}           # layers re-framed by the model: register on the eyes
REGION = {"face": (380, 330, 650, 560), "hairb": (0, 0, 0, 0)}     # the features; hairb is mostly hidden: keep it unmoved


def eyes(rgb, box, alpha=None):
    """centres of the two dark eye blobs (lashes + iris) inside box -> (left, right)"""
    x0, y0, x1, y1 = box
    L = rgb[..., 0] * 0.3 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11
    m = np.zeros(L.shape, bool)
    m[y0:y1, x0:x1] = L[y0:y1, x0:x1] < 120
    if alpha is not None:
        m &= alpha > 0.9
    m = ndimage.binary_closing(m, iterations=2)
    lab, n = ndimage.label(m)
    s = ndimage.sum(m, lab, range(1, n + 1))
    c = []
    for i in np.argsort(-s)[:2]:
        ys, xs = np.where(lab == i + 1)
        c.append((xs.mean(), ys.mean()))
    return sorted(c)


def register_eyes(rgb, kr, kbox, lbox, a=None, kalpha=None):
    (ka, kb), (la, lb) = eyes(kr, kbox, kalpha), eyes(rgb, lbox, a)
    sc = (kb[0] - ka[0]) / (lb[0] - la[0])
    kc = ((ka[0] + kb[0]) / 2, (ka[1] + kb[1]) / 2)
    lc = ((la[0] + lb[0]) / 2, (la[1] + lb[1]) / 2)
    # warp() scales about the canvas centre then shifts: solve the shift that lands lc on kc
    cx, cy = W / 2, H / 2
    dx = kc[0] - (cx + (lc[0] - cx) * sc)
    dy = kc[1] - (cy + (lc[1] - cy) * sc)
    return sc, dx, dy


EYEBOX = {"key": (350, 220, 680, 330)}


def main(names):
    EV.mkdir(parents=True, exist_ok=True)
    kr, ka = key(load("keyart.png"))
    Image.fromarray(np.dstack([kr, ka * 255]).astype(np.uint8), "RGBA").save(GEN / "L_keyart.png")
    rep = {}
    for name, f in names:
        rgb, a = key(load(f))
        # weight: key-art pixels that are opaque (the layer's visible parts are judged where the key art is the subject)
        weight = ka > 0.95
        if name in REGION:
            x0, y0, x1, y1 = REGION[name]
            box = np.zeros_like(weight)
            box[y0:y1, x0:x1] = True
            weight = weight & box
        if name in EYE_LAYERS:
            sc, dx, dy = register_eyes(rgb, kr, EYEBOX["key"], EYE_LAYERS[name], a, ka)
            e = -1.0
        else:
            e, sc, dx, dy = register(rgb, a, kr, ka, weight) if weight.sum() > 500 else (0.0, 1.0, 0, 0)
        r2, a2 = warp(rgb, a, sc, dx, dy)
        Image.fromarray(np.dstack([r2, a2 * 255]).astype(np.uint8), "RGBA").save(GEN / f"L_{name}.png")
        rep[name] = {"scale": sc, "dx": dx, "dy": dy, "err": round(e, 2)}
        print(name, rep[name], flush=True)
    old = json.loads((HERE / "layers-report.json").read_text()) if (HERE / "layers-report.json").is_file() else {}
    old.update({k: {kk: float(vv) for kk, vv in v.items()} for k, v in rep.items()})
    (HERE / "layers-report.json").write_text(json.dumps(old, indent=1))


if __name__ == "__main__":
    L = [("face", "face_01.png"), ("hairf", "hairf_01.png"), ("hairb", "hairb_01.png"), ("body", "body_01.png"), ("arms", "arms_01.png")]
    if len(sys.argv) > 1:
        L = [x for x in L if x[0] in sys.argv[1:]]
    main(L)
