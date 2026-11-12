"""米丫子 full body: generated layers -> keyed, registered RGBA on the key art canvas (gen/L_*.png) + report.

Layers come back either on green or already transparent; both are handled.  Registration = small search on scale and
shift against the key art, judged on the pixels both show.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
GEN = HERE / "gen"
W, H = 941, 1672
SRC = {"key": "key.png", "torso": "torso_01.png", "legs": "legs_01.png", "arms": "arms_01.png", "head": "head_01.png", "fists": "fists_01.png", "blink": "blink_01.png", "talk": "talk_01.png", "apple": "apple_01.png"}


def despill(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    out = rgb.copy()
    out[..., 1] = np.minimum(g, r - np.maximum(r - b, 0) * 0.25)
    return out


def bleed(rgb, a, r=4):
    w = (a > 0.9).astype(np.float32)
    num = ndimage.uniform_filter(rgb * w[..., None], size=(2 * r + 1, 2 * r + 1, 1))
    den = ndimage.uniform_filter(w, size=2 * r + 1)[..., None]
    est = np.where(den > 1e-3, num / np.maximum(den, 1e-3), rgb)
    return np.where((a < 0.9)[..., None], est, rgb)


def load(f):
    im = Image.open(GEN / f)
    im = im.convert("RGBA").resize((W, H), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)
    rgb, al = arr[..., :3], arr[..., 3] / 255
    if al.min() < 0.5:                                   # came back transparent
        a = al
        # drop faint specks / halos
        solid = a > 0.5
        lab, n = ndimage.label(solid)
        if n:
            s = ndimage.sum(solid, lab, range(1, n + 1))
            keep = np.isin(lab, 1 + np.where(s >= max(80, s.max() * 0.002))[0])
            a = a * ndimage.binary_dilation(keep, iterations=2)
    else:                                                # green screen
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        bg = np.median(rgb[:6].reshape(-1, 3), 0)
        full = bg[1] - max(bg[0], bg[2])
        a = 1 - np.clip((g - np.maximum(r, b)) / max(full, 1), 0, 1)
        a = np.where(a < 0.06, 0, np.where(a > 0.94, 1, a))
        solid = a > 0.5
        lab, n = ndimage.label(solid)
        if n:
            s = ndimage.sum(solid, lab, range(1, n + 1))
            keep = np.isin(lab, 1 + np.where(s >= max(80, s.max() * 0.002))[0])
            a = a * ndimage.binary_dilation(keep, iterations=3)
        a3 = a[..., None]
        rgb = np.clip(np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), rgb), 0, 255)
    rgb = despill(bleed(rgb, a))
    return rgb, a


def warp(rgb, a, sc, dx, dy):
    im = Image.fromarray(np.clip(np.dstack([rgb, a * 255]), 0, 255).astype(np.uint8), "RGBA")
    cx, cy = W / 2, H / 2
    o = np.asarray(im.transform((W, H), Image.AFFINE, (1 / sc, 0, cx - (cx + dx) / sc, 0, 1 / sc, cy - (cy + dy) / sc), resample=Image.BICUBIC)).astype(np.float32)
    return o[..., :3], o[..., 3] / 255


def register(rgb, a, kr, ka):
    best = None
    S = 3
    for sc in (0.98, 0.99, 1.0, 1.01, 1.02):
        r2, a2 = warp(rgb, a, sc, 0, 0)
        for dy in range(-15, 16, 3):
            for dx in range(-15, 16, 3):
                rr = np.roll(np.roll(r2, dy, 0), dx, 1)[::S, ::S]
                aa = np.roll(np.roll(a2, dy, 0), dx, 1)[::S, ::S]
                m = (aa > 0.95) & (ka[::S, ::S] > 0.95)
                if m.sum() < 300:
                    continue
                e = float(np.abs(rr - kr[::S, ::S]).sum(-1)[m].mean())
                if best is None or e < best[0]:
                    best = (e, sc, dx, dy)
    e, sc, dx, dy = best
    for ddx in (-1, 0, 1):
        for ddy in (-1, 0, 1):
            r2, a2 = warp(rgb, a, sc, dx + ddx, dy + ddy)
            m = (a2 > 0.95) & (ka > 0.95)
            e2 = float(np.abs(r2 - kr).sum(-1)[m].mean())
            if e2 < best[0]:
                best = (e2, sc, dx + ddx, dy + ddy)
    return best


def main(names):
    kr, ka = load(SRC["key"])
    Image.fromarray(np.clip(np.dstack([kr, ka * 255]), 0, 255).astype(np.uint8), "RGBA").save(GEN / "L_key.png")
    rep_f = HERE / "layers-report.json"
    rep = json.loads(rep_f.read_text()) if rep_f.is_file() else {}
    for n in names:
        rgb, a = load(SRC[n])
        e, sc, dx, dy = register(rgb, a, kr, ka)
        rgb, a = warp(rgb, a, sc, dx, dy)
        Image.fromarray(np.clip(np.dstack([rgb, a * 255]), 0, 255).astype(np.uint8), "RGBA").save(GEN / f"L_{n}.png")
        rep[n] = {"scale": sc, "dx": dx, "dy": dy, "err": round(e, 2)}
        print(n, rep[n], flush=True)
    rep_f.write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or ["torso", "legs", "arms", "head", "fists"])
