"""Zhuda skin painter: turns generated Zhuda art (turnaround sheets, prop sheets, material swatches)
into one image per white-model template, at 2x the template resolution.

    python3 -I zhuda_skin.py <model> [<model> ...]      -> examples/whitemodels/<model>/skins/zhuda/

Rules it follows (docs/38-reskin.md): same file names, same proportions (exact 2x), cover the white
shape, opaque with clean edges, flat light. View parts (head/chest/pelvis/feet/shield) get 8 images;
v5-v7 are mirrors of v3-v1 because Zhuda is left-right symmetric.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from scipy import ndimage

HERE = Path(__file__).resolve().parent
KIT = HERE.parent.parent
GEN = HERE / "gen"
SCALE = 2
OUTLINE = np.array([140, 84, 72], float)      # warm brown line of the reference art
PINK = (250, 198, 198)          # matched to the head art's skin (median 252,204,204)
SKIN_NAME = "zhuda"


# ------------------------------------------------------------------------------------------ sheets
def clean_alpha(im: Image.Image) -> Image.Image:
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    al = a[..., 3]
    solid = al > 160
    lab, n = ndimage.label(solid)
    if n:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(sizes >= max(400, sizes.max() * 0.004))[0])
    else:
        keep = solid
    keep = ndimage.binary_fill_holes(keep)
    keep = ndimage.binary_erosion(keep, iterations=1)         # drop the coloured fringe of the matte
    out = a.copy()
    out[..., 3] = np.where(keep, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def cut_sheet(path: Path, n: int):
    """Split a horizontal sheet into n objects (left to right) by the columns that carry art."""
    im = clean_alpha(Image.open(path))
    al = np.asarray(im)[..., 3] > 0
    cols = al.sum(0) > 2
    runs, x = [], 0
    W = len(cols)
    while x < W:
        if cols[x]:
            s = x
            while x < W and cols[x]:
                x += 1
            runs.append((s, x))
        else:
            x += 1
    # merge runs separated by tiny gaps until we have n
    while len(runs) > n:
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        i = int(np.argmin(gaps))
        runs[i:i + 2] = [(runs[i][0], runs[i + 1][1])]
    if len(runs) != n:
        raise SystemExit(f"{path.name}: found {len(runs)} objects, expected {n}")
    out = []
    for s, e in runs:
        sub = im.crop((s, 0, e, im.height))
        out.append(sub.crop(sub.getbbox()))
    return out


def cut_grid(path: Path, rows: int, cols: int, inset=0.12):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    tiles = []
    for r in range(rows):
        for c in range(cols):
            x0, y0, x1, y1 = c * W / cols, r * H / rows, (c + 1) * W / cols, (r + 1) * H / rows
            dx, dy = (x1 - x0) * inset, (y1 - y0) * inset
            tiles.append(im.crop((int(x0 + dx), int(y0 + dy), int(x1 - dx), int(y1 - dy))))
    return tiles


# ------------------------------------------------------------------------------------------ materials
class Mat:
    """Flat cartoon material: a base colour plus (optionally) a shrunk swatch texture blended in."""

    def __init__(self, rgb, tex: Image.Image = None, tex_amount=0.0, tex_scale=0.35):
        self.rgb = np.array(rgb, float)
        self.tex, self.amount, self.tscale = tex, tex_amount, tex_scale

    def fill(self, w, h):
        base = np.ones((h, w, 3)) * self.rgb
        if self.tex is None or self.amount <= 0:
            return base
        t = self.tex.resize((max(8, int(self.tex.width * self.tscale)), max(8, int(self.tex.height * self.tscale))), Image.LANCZOS)
        reps = (h // t.height + 1, w // t.width + 1)
        tt = np.tile(np.asarray(t, float), (reps[0], reps[1], 1))[:h, :w]
        return base * (1 - self.amount) + tt * self.amount


def load_materials():
    tiles = cut_grid(GEN / "materials_01.png", 3, 4)
    names = ["skin", "belly", "hoof", "knit", "denim", "hoodie", "stripe", "bandana", "steel", "velvet", "wood", "pinkknit"]
    sw = dict(zip(names, tiles))
    med = {k: tuple(np.median(np.asarray(v, float).reshape(-1, 3), 0)) for k, v in sw.items()}
    M = {
        "skin": Mat(PINK),
        "belly": Mat((250, 214, 205)),
        "hoof": Mat((112, 66, 52)),
        "knit": Mat(med["knit"], sw["knit"], 0.55, 0.22),
        "pinkknit": Mat(med["pinkknit"], sw["pinkknit"], 0.55, 0.22),
        "denim": Mat(med["denim"], sw["denim"], 0.45, 0.4),
        "hoodie": Mat(med["hoodie"], sw["hoodie"], 0.3, 0.4),
        "stripe": Mat(med["stripe"], sw["stripe"], 1.0, 0.16),
        "bandana": Mat(med["bandana"], sw["bandana"], 1.0, 0.25),
        "red": Mat((214, 72, 66)),
        "steel": Mat((196, 204, 214), sw["steel"], 0.35, 0.3),
        "velvet": Mat((92, 52, 140)),
        "capered": Mat((178, 52, 52)),
        "wood": Mat(med["wood"], sw["wood"], 0.6, 0.3),
        "gold": Mat((236, 190, 80)),
        "cream": Mat((250, 236, 214)),
        "brownleather": Mat((150, 96, 60)),
        "white": Mat((250, 250, 248)),
    }
    return M


# ------------------------------------------------------------------------------------------ template helpers
import os
ROOT = Path(os.environ.get("ZHUDA_MODELS", str(KIT / "examples" / "whitemodels")))


def template(model, att):
    return Image.open(ROOT / model / "parts" / f"{att}.png").convert("RGBA")


def up(tm: Image.Image):
    return tm.resize((tm.width * SCALE, tm.height * SCALE), Image.LANCZOS)


def outline_rgba(rgb, alpha, width=None):
    """Draw the warm brown cartoon line just inside the silhouette."""
    width = width or max(2, SCALE + 1)
    inside = alpha > 127
    inner = ndimage.binary_erosion(inside, iterations=width)
    edge = inside & ~inner
    rgb = rgb.copy()
    rgb[edge] = rgb[edge] * 0.15 + OUTLINE * 0.85
    return rgb


def shade_from_template(tu: np.ndarray, amount=0.16):
    L = tu[..., :3].mean(-1)
    return np.clip(1.0 - amount + amount * (L - 140) / 115.0, 1.0 - amount * 1.4, 1.02)[..., None]


def flat_part(model, att, mat: Mat, line=True, shade=True, shade_amount=0.16):
    tu = np.asarray(up(template(model, att))).astype(float)
    h, w = tu.shape[:2]
    a = tu[..., 3]
    rgb = mat.fill(w, h)
    if shade:
        rgb = rgb * shade_from_template(tu, shade_amount)
    if line:
        rgb = outline_rgba(rgb, a)
    alpha = np.where(a > 127, 255, np.where(a > 40, a, 0))
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), "RGBA")


def mapped_part(model, att, art: Image.Image, box=(0, 0, 1, 1), under: Mat = None, pad=0.0, line=True):
    """Stretch a region of an art image over the white shape and cut it to the shape (body sections)."""
    tu = np.asarray(up(template(model, att))).astype(float)
    h, w = tu.shape[:2]
    a = tu[..., 3]
    ys, xs = np.where(a > 40)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bw, bh = x1 - x0, y1 - y0
    x0, x1 = int(x0 - bw * pad), int(x1 + bw * pad)
    y0, y1 = int(y0 - bh * pad), int(y1 + bh * pad)
    W, H = art.size
    crop = art.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))).resize((x1 - x0, y1 - y0), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if under is not None:
        canvas.paste(Image.fromarray(under.fill(w, h).astype(np.uint8), "RGB").convert("RGBA"), (0, 0))
    canvas.alpha_composite(crop, (x0, y0)) if x0 >= 0 and y0 >= 0 else canvas.paste(crop, (x0, y0), crop)
    rgb = np.asarray(canvas)[..., :3].astype(float)
    if line:
        rgb = outline_rgba(rgb, a)
    alpha = np.where(a > 127, 255, np.where(a > 40, a, 0))
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")


def fitted_part(model, att, art: Image.Image, target=0.985, max_scale=1.6, align="center", core=None):
    """Place art (with its own silhouette: ears, snout...) so it covers the white shape, smallest scale first."""
    tm = up(template(model, att))
    w, h = tm.size
    ta = np.asarray(tm)[..., 3] > 40
    ys, xs = np.where(ta)
    tx0, tx1, ty0, ty1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    # core = fractional box of the art that should land on the white shape (excludes ears etc.)
    cx0, cy0, cx1, cy1 = core or (0, 0, 1, 1)
    aw, ah = art.size
    corew, coreh = (cx1 - cx0) * aw, (cy1 - cy0) * ah
    base = max((tx1 - tx0) / corew, (ty1 - ty0) / coreh)
    best = None
    for s in np.arange(1.0, max_scale, 0.02):
        sc = base * s
        rw, rh = max(1, int(aw * sc)), max(1, int(ah * sc))
        im = art.resize((rw, rh), Image.LANCZOS)
        ccx = (cx0 + cx1) / 2 * rw
        ccy = (cy0 + cy1) / 2 * rh
        for dx in (0, -2, 2, -4, 4, -7, 7):
            ox, oy = int(round(tcx - ccx)) + dx * SCALE, int(round(tcy - ccy))
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(im, (ox, oy), im)
            sa = np.asarray(canvas)[..., 3] > 40
            cov = (sa & ta).sum() / ta.sum()
            if best is None or cov > best[0] + 1e-4:
                best = (cov, canvas)
            if cov >= target:
                return canvas, cov
    return best[1], best[0]


def mirror(im):
    return ImageOps.mirror(im)


# ------------------------------------------------------------------------------------------ model recipes
VIEW_SRC = [0, 1, 2, 3, 4]          # v0..v4 come from sheet columns 0..4; v5..v7 mirror v3..v1


def eight(images5):
    return images5 + [mirror(images5[3]), mirror(images5[2]), mirror(images5[1])]


def spec(model):
    return json.loads((ROOT / model / "skin" / "skin.json").read_text())


def paint(model, recipe, M, sheets):
    out = ROOT / model / "skins" / SKIN_NAME
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    sp = spec(model)
    for a in sp["attachments"]:
        n = a["attachment"]
        if a["kind"] == "shadow":
            continue
        im = recipe(n, a, M, sheets)
        if im is None:
            continue
        cov = None
        if isinstance(im, tuple):
            im, cov = im
        tm = template(model, n)
        assert im.size == (tm.width * SCALE, tm.height * SCALE), (n, im.size, tm.size)
        im.save(out / f"{n}.png")
        report[n] = round(float(cov), 3) if cov is not None else None
    (out / "_paint_report.json").write_text(json.dumps(report, indent=1))
    return out, report


def ear_part(model, att, M):
    """pig ear: skin with a darker inner ear, cartoon outline"""
    tu = np.asarray(up(template(model, att))).astype(float)
    h, w = tu.shape[:2]
    a = tu[..., 3]
    rgb = M["skin"].fill(w, h) * shade_from_template(tu)
    inside = a > 127
    inner = ndimage.binary_erosion(inside, iterations=max(3, int(min(w, h) * 0.16)))
    ys, xs = np.where(inner)
    if len(ys):
        cy = ys.mean()
        inner &= (np.arange(h)[:, None] > cy - (ys.max() - ys.min()) * 0.25)      # inner ear in the lower part
        rgb[inner] = np.array([236, 140, 150])
    rgb = outline_rgba(rgb, a)
    alpha = np.where(a > 127, 255, np.where(a > 40, a, 0))
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")


def ribbon_part(model, att, mat, frac=0.62):
    """narrower ribbon inside a tube template (covers ~frac of the white shape, rounded by row)"""
    im = flat_part(model, att, mat, line=False)
    arr = np.asarray(im).copy()
    a = arr[..., 3] > 127
    for y in range(a.shape[0]):
        xs = np.where(a[y])[0]
        if len(xs) < 2:
            continue
        c, half = (xs[0] + xs[-1]) / 2, (xs[-1] - xs[0]) / 2 * frac
        keep = np.abs(np.arange(a.shape[1]) - c) <= half
        arr[y, ~keep, 3] = 0
    rgb = outline_rgba(arr[..., :3].astype(float), arr[..., 3].astype(float))
    arr[..., :3] = rgb
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def tint(im: Image.Image, src_rgb, dst_rgb):
    """recolour so that src_rgb becomes dst_rgb (per-channel gain), keeping alpha"""
    a = np.asarray(im).astype(float)
    g = np.array(dst_rgb, float) / np.maximum(np.array(src_rgb, float), 1)
    a[..., :3] = np.clip(a[..., :3] * g, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def cloth_panel(model, att, mat, top=0.6, bottom=1.0, wave=0.0):
    """a cloth panel (cape) painted as a trapezoid over the panel's ellipse: narrow at the top, full at the hem"""
    tu = np.asarray(up(template(model, att))).astype(float)
    h, w = tu.shape[:2]
    a = tu[..., 3] > 40
    ys, xs = np.where(a)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, bw = (x0 + x1) / 2, (x1 - x0)
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip((yy - y0) / max(1, y1 - y0), 0, 1)
    half = bw / 2 * (top + (bottom - top) * t)
    hem = y1 - (wave * bw * 0.04) * (1 + np.cos((xx - x0) / max(bw, 1) * 2 * np.pi * 3)) / 2
    m = (np.abs(xx - cx) <= half) & (yy >= y0) & (yy <= hem)
    rgb = mat.fill(w, h) * (0.94 + 0.06 * np.cos((xx - cx) / max(bw, 1) * np.pi * 4))[..., None]   # soft folds
    alpha = np.where(m, 255, 0).astype(float)
    rgb = outline_rgba(rgb, alpha)
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")


def cloth_rect(model, att, mat, corner=0.22):
    """a cloth piece that reads the same upside down: rounded rectangle over the panel's bounding box"""
    tu = np.asarray(up(template(model, att))).astype(float)
    h, w = tu.shape[:2]
    a = tu[..., 3] > 40
    ys, xs = np.where(a)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    im = Image.new("L", (w, h), 0)
    r = int(min(x1 - x0, y1 - y0) * corner)
    ImageDraw.Draw(im).rounded_rectangle((x0, y0, x1, y1), radius=r, fill=255)
    alpha = np.asarray(im).astype(float)
    xx = np.arange(w)[None, :]
    rgb = mat.fill(w, h) * (0.94 + 0.06 * np.cos((xx - (x0 + x1) / 2) / max(x1 - x0, 1) * np.pi * 4))[..., None]
    rgb = outline_rgba(rgb, alpha)
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")
