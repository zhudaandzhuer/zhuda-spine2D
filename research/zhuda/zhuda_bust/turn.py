"""Turn views for the bust: the sheet's own side view (側面平視) + a generated 3/4 in-between, on the front canvas.

    python3 turn.py prep     -> gen/side_clean.png (side panel at 3x, registered on the front canvas, annotations removed)
    (extract.py calls add_turn() to cut parts turn_q, turn_side and their mirrors)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
K = 3
SIDE_BOX = (140, 508, 480, 826)          # same size as the front panel box, bottom on the body's crop line


def side_panel():
    im = Image.open(HERE / "src" / "sheet_pitch.png").convert("RGB").crop(SIDE_BOX)
    return np.asarray(im.resize((im.width * K, im.height * K), Image.LANCZOS)).astype(np.float32)


def thin_removed(alpha, r=5):
    """drop thin strokes attached to the figure (the measuring bracket at the snout); keep the body and its outline"""
    core = alpha > 0.5
    opened = ndimage.binary_opening(core, structure=np.ones((r * 2 + 1, r * 2 + 1)))
    lab, n = ndimage.label(opened)
    big = lab == 1 + int(np.argmax(ndimage.sum(opened, lab, range(1, n + 1))))
    keep = ndimage.binary_dilation(big, iterations=r + 2)
    return alpha * keep


# head-anchored registration onto the front canvas: (src top, src chin) -> front (59, 701); x keeps the body centre
FRONT_TOP, FRONT_CHIN, CROP_Y = 59, 701, 927


def register_head(rgb, top, chin, cx_src, cx_dst=506):
    s = (FRONT_CHIN - FRONT_TOP) / float(chin - top)
    H, W = rgb.shape[:2]
    im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    bg = tuple(int(v) for v in rgb[5, 5])
    # dst = (src - (cx_src, chin)) * s + (cx_dst, FRONT_CHIN)  ->  src = (dst - (cx_dst, FRONT_CHIN)) / s + (cx_src, chin)
    out = im.transform((W, H), Image.AFFINE, (1 / s, 0, cx_src - cx_dst / s, 0, 1 / s, chin - FRONT_CHIN / s), resample=Image.BICUBIC, fillcolor=bg)
    return np.asarray(out).astype(np.float32), s


def add_turn(ex, parts, H, W, report):
    """cut turn_q / turn_side (+ mirrored _R) from gen/turn_q_reg.png and gen/side_clean.png"""
    out = {}
    for name, f, top, chin, cxs in (("turn_q", "turn_q_fit.png", 78, 665, 488), ("turn_side", "side_clean.png", 118, 718, 506)):
        p = HERE / "gen" / f
        if not p.is_file():
            continue
        rgb = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
        rgb, sc = register_head(rgb, top, chin, cxs)
        a, bg = ex.pig_alpha(rgb)
        a[CROP_Y + 1:] = 0.0                                     # same bottom cut as the front body
        a = thin_removed(a)
        rgb, a = ex.decontam(rgb, a, bg)
        ex.save_part(name, ex.rgba(rgb, a), parts)
        m_rgb, m_a = rgb[:, ::-1], a[:, ::-1]                    # the design is symmetric: turning right = mirror
        ex.save_part(name + "_R", ex.rgba(m_rgb, m_a), parts)
        ys, xs = np.where(a > 0.5)
        out[name] = {"scale": round(sc, 4), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
    report["turn"] = out


def prep():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ex", HERE / "extract.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)
    s = side_panel()
    a, bg = ex.pig_alpha(s)
    a = thin_removed(a)
    clean = s * a[..., None] + bg * (1 - a[..., None])
    Image.fromarray(np.clip(clean, 0, 255).astype(np.uint8)).save(HERE / "gen" / "side_clean.png")
    ys, xs = np.where(a > 0.5)
    print("side bbox", xs.min(), ys.min(), xs.max(), ys.max())


if __name__ == "__main__" and sys.argv[1:] == ["prep"]:
    prep()
