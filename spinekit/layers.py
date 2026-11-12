"""Layers from images: turn generated or painted pictures into rig-ready parts.

    layers.json  ->  parts/*.png + parts/manifest.json + parts/keyart.png + review images

What it does, per part and in this order:
  source   a full-canvas image file, the key art itself, or "@other_part" (pixel-identical reuse)
  key      remove a solid chroma background: true alpha on antialiased edges, colour un-mixed (no green halo)
  align    register the part to the key art (generated parts drift by a few pixels / a percent of scale)
  polygon  keep only what lies inside a polygon (holes allowed, feathered edge)
  fade     feather one side of the part to nothing (eyelid patch top, fringe top)
  clean    drop specks

It never invents pixels.  Anything that is hidden in the key art (neck under the chin, scalp under the
fringe, eye white behind the socket) has to exist in a source image; `seam candidates` in the report and
`coverage.png` show where it does not.

Needs only numpy + Pillow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class LayerError(Exception):
    pass


# ------------------------------------------------------------------------------------------- helpers
def _hex(c) -> Tuple[int, int, int]:
    if isinstance(c, (list, tuple)):
        return tuple(int(v) for v in c[:3])
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _dilate(m: np.ndarray, n: int = 1) -> np.ndarray:
    out = m
    for _ in range(n):
        p = np.pad(out, 1)
        out = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
    return out


def _erode(m: np.ndarray, n: int = 1) -> np.ndarray:
    return ~_dilate(~m, n)


def _propagate(rgb: np.ndarray, known: np.ndarray, iterations: int):
    """Spread colours of `known` pixels outward. Returns (rgb, reached_mask)."""
    rgb = rgb.copy()
    known = known.copy()
    for _ in range(iterations):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        pk = np.pad(known, 1)
        pc = np.pad(rgb * known[..., None], ((1, 1), (1, 1), (0, 0)))
        h, w = known.shape
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if dy == 1 and dx == 1:
                    continue
                k = pk[dy:dy + h, dx:dx + w]
                acc += pc[dy:dy + h, dx:dx + w]
                cnt += k
        grow = (~known) & (cnt > 0)
        if not grow.any():
            break
        rgb[grow] = acc[grow] / cnt[grow][..., None]
        known |= grow
    return rgb, known


def _shift(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Translate an image array by whole pixels, filling with zeros."""
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    x0, x1 = max(0, dx), min(w, w + dx)
    y0, y1 = max(0, dy), min(h, h + dy)
    if x0 < x1 and y0 < y1:
        out[y0:y1, x0:x1] = a[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out


def _bbox(alpha: np.ndarray, thr: int = 0) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.nonzero(alpha > thr)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


# --------------------------------------------------------------------------------------- background
def detect_background(rgba: np.ndarray) -> Dict:
    """Classify what surrounds the subject: real alpha, a solid colour, a baked checkerboard, or unknown."""
    h, w = rgba.shape[:2]
    f = max(3, min(h, w) // 100)
    border = np.concatenate([rgba[:f].reshape(-1, 4), rgba[-f:].reshape(-1, 4), rgba[:, :f].reshape(-1, 4), rgba[:, -f:].reshape(-1, 4)])
    if (border[:, 3] < 250).mean() > 0.5:
        return {"kind": "alpha"}
    q = (border[:, :3] // 16).astype(np.int32)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    order = np.argsort(-counts)
    top = counts[order[0]] / len(keys)
    med = lambda k: tuple(int(v) for v in np.median(border[keys == k][:, :3], axis=0))
    c0 = med(vals[order[0]])
    if len(order) > 1:
        c1 = med(vals[order[1]])
        second = counts[order[1]] / len(keys)
        grey = lambda c: max(c) - min(c) < 14
        if top < 0.8 and second > 0.2 and grey(c0) and grey(c1) and 12 < abs(sum(c0) - sum(c1)) / 3 < 110:
            return {"kind": "checker", "colors": [c0, c1]}
    if top > 0.6:
        return {"kind": "solid", "color": c0, "share": round(float(top), 3)}
    return {"kind": "unknown", "color": c0, "share": round(float(top), 3)}


def _border_connected(mask: np.ndarray) -> np.ndarray:
    """Pixels of `mask` connected to the image border (computed at 1/4 size, then grown back)."""
    small = mask[::4, ::4]
    seed = np.zeros_like(small)
    seed[0, :], seed[-1, :], seed[:, 0], seed[:, -1] = small[0, :], small[-1, :], small[:, 0], small[:, -1]
    while True:
        grown = _dilate(seed) & small
        if (grown == seed).all():
            break
        seed = grown
    reach = np.kron(seed, np.ones((4, 4), bool))[:mask.shape[0], :mask.shape[1]]
    if reach.shape != mask.shape:
        reach = np.pad(reach, ((0, mask.shape[0] - reach.shape[0]), (0, mask.shape[1] - reach.shape[1])), mode="edge")
    return _dilate(reach, 3) & mask


def chroma_key(rgba: np.ndarray, bg: Sequence[int], lo: float = 0.07, hi: float = 0.30, mode: str = "global") -> Tuple[np.ndarray, Dict]:
    """Remove a solid background colour and return true alpha with un-mixed colour.

    Saturated backgrounds (green, magenta, blue ...) use a colour-difference matte: alpha comes from how much the
    background's own channel(s) exceed the others, the pixel is un-mixed with that alpha, and any remaining excess of
    the key channel is removed.  This handles antialiased edges, wide soft fades and blurry blobs alike.  It treats
    anything in the character that is the background's colour as transparent -- pick a colour the character lacks.

    Neutral backgrounds (white, grey, black) cannot be separated from soft edges that way; they fall back to a
    distance key with edge un-mixing, which is fine for hard-edged art and unreliable for soft fades.

    mode 'border' keeps enclosed areas (only background connected to the image border is removed).
    """
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    a_in = rgba[..., 3].astype(np.float32) / 255.0
    B = np.array(bg, np.float32) / 255.0
    keych = B > 0.5
    s_bg = float(B[keych].min() - B[~keych].max()) if keych.any() and (~keych).any() else 0.0
    if s_bg >= 0.3:
        method = "colour-difference"
        spill = rgb[..., keych].min(-1) - rgb[..., ~keych].max(-1)
        alpha = 1.0 - np.clip(spill / s_bg, 0, 1)
        if mode == "border":
            alpha = np.where(_border_connected(alpha < 0.98), alpha, 1.0)
        safe = np.maximum(alpha, 1e-3)[..., None]
        fg = np.clip((rgb - (1 - safe) * B) / safe, 0, 1)
        excess = np.clip(fg[..., keych].min(-1) - fg[..., ~keych].max(-1), 0, 1)       # despill what is left
        fg[..., keych] -= excess[..., None] * (alpha < 0.999)[..., None]
        out_rgb = np.where((alpha >= 0.999)[..., None], rgb, fg)
        # Refinement.  The matte above over-estimates alpha for colours whose key channel is weak (reds, pinks, skin):
        # a 50 % pink reads as 63 %.  Where a pixel is demonstrably a blend of the background and the solid colour
        # found deeper inside the shape, take alpha from that blend instead.  Pixels that are NOT on that colour line
        # (an outline, a highlight, a different material) are left alone, so dark edges are never eaten.
        box = _bbox((alpha > 0).astype(np.uint8))
        if box:
            pad = 4
            x0, y0, x1, y1 = max(0, box[0] - pad), max(0, box[1] - pad), min(rgb.shape[1], box[2] + pad), min(rgb.shape[0], box[3] + pad)
            c_rgb, c_a = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
            core = _erode(c_a >= 0.999, 8)
            if core.any():
                F, reached = _propagate(c_rgb, core, 40)
                d_fb = F - B
                den = (d_fb ** 2).sum(-1) + 1e-6
                a_proj = np.clip(((c_rgb - B) * d_fb).sum(-1) / den, 0, 1)
                resid = np.sqrt(((c_rgb - B - a_proj[..., None] * d_fb) ** 2).sum(-1))
                blend = reached & ~core & (resid < 0.05) & (a_proj < 0.985) & (den > 0.09)
                c_a2 = np.where(blend, a_proj, c_a)
                alpha[y0:y1, x0:x1] = c_a2
                out_rgb[y0:y1, x0:x1] = np.where(blend[..., None], F, out_rgb[y0:y1, x0:x1])
    else:
        method = "distance (neutral background: soft fades may keep a tint)"
        d = np.sqrt(((rgb - B) ** 2).sum(-1))
        bgmask = d < lo
        if mode == "border":
            bgmask = _border_connected(bgmask)
        core = (d > hi) & ~bgmask
        core &= ~_dilate(~core, 2)                             # the outermost 2 px of solid colour are treated as mixed
        band = ~bgmask & ~core
        F, reached = _propagate(rgb, core, 10)
        num = ((rgb - B) * (F - B)).sum(-1)
        den = ((F - B) ** 2).sum(-1) + 1e-6
        a_proj = np.clip(num / den, 0, 1)
        a_soft = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
        alpha = np.where(core, 1.0, np.where(band & reached, a_proj, np.where(band, a_soft, 0.0)))
        safe = np.maximum(a_soft, 1e-3)[..., None]
        unmixed = np.clip((rgb - (1 - safe) * B) / safe, 0, 1)
        out_rgb = np.where(core[..., None], rgb, np.where((band & reached)[..., None], F, unmixed))
    alpha = alpha * a_in
    alpha[alpha < 2 / 255] = 0
    out = np.dstack([np.clip(np.rint(out_rgb * 255), 0, 255), np.rint(alpha * 255)]).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    # Wide translucent areas (not just antialiased edges): there the true colour cannot be separated from the background
    # with certainty, and hues drift (pink reads olive on green).  Measure them so the caller can warn.
    soft = (alpha > 0.05) & (alpha < 0.95)
    wide = _erode(soft, 2)
    shape_px = max(1, int((alpha > 0.05).sum()))
    stats = {"background": "#%02x%02x%02x" % tuple(int(v) for v in bg), "method": method, "removed_fraction": round(float((alpha == 0).mean()), 4),
             "soft_edge_fraction": round(float(soft.mean()), 4), "translucent_share": round(float(wide.sum()) / shape_px, 4)}
    return out, stats


# ------------------------------------------------------------------------------------------ shaping
def polygon_mask(size: Tuple[int, int], polygon: Sequence[Sequence[float]], holes: Sequence[Sequence[Sequence[float]]] = (), feather: float = 1.0) -> np.ndarray:
    """Float mask (H, W) in [0,1]; drawn at 4x and reduced so edges are antialiased; `feather` blurs it further (px)."""
    W, H = size
    s = 4
    im = Image.new("L", (W * s, H * s), 0)
    d = ImageDraw.Draw(im)
    d.polygon([(x * s, y * s) for x, y in polygon], fill=255)
    for hole in holes or ():
        d.polygon([(x * s, y * s) for x, y in hole], fill=0)
    im = im.resize((W, H), Image.LANCZOS)
    if feather and feather > 0:
        im = im.filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(im, np.float32) / 255.0


def edge_fade(alpha: np.ndarray, fade: Dict[str, float]) -> np.ndarray:
    """Multiply alpha by linear ramps measured from the part's own bounding box: {'top': 9} -> 0 at the top edge, 1 after 9 px."""
    box = _bbox(alpha)
    if not box:
        return alpha
    x0, y0, x1, y1 = box
    a = alpha.astype(np.float32)
    yy, xx = np.mgrid[0:alpha.shape[0], 0:alpha.shape[1]]
    for side, px in fade.items():
        px = float(px)
        if px <= 0:
            continue
        if side == "top":
            a *= np.clip((yy - y0) / px, 0, 1)
        elif side == "bottom":
            a *= np.clip((y1 - 1 - yy) / px, 0, 1)
        elif side == "left":
            a *= np.clip((xx - x0) / px, 0, 1)
        elif side == "right":
            a *= np.clip((x1 - 1 - xx) / px, 0, 1)
        else:
            raise LayerError(f"fade side '{side}' (use top/bottom/left/right)")
    return np.rint(a).astype(np.uint8)


def despeckle(rgba: np.ndarray, radius: int = 2) -> Tuple[np.ndarray, int]:
    """Remove isolated blobs thinner than ~2*radius px (stray pixels a key or a model leaves behind)."""
    solid = rgba[..., 3] > 24
    survivors = _dilate(_erode(solid, radius), radius + 3)
    drop = (rgba[..., 3] > 0) & ~survivors
    out = rgba.copy()
    out[drop] = 0
    return out, int(drop.sum())


# ---------------------------------------------------------------------------------------- alignment
def _scale_about(rgba: np.ndarray, s: float) -> np.ndarray:
    box = _bbox(rgba[..., 3])
    if not box or abs(s - 1) < 1e-6:
        return rgba
    x0, y0, x1, y1 = box
    crop = Image.fromarray(rgba[y0:y1, x0:x1], "RGBA")
    nw, nh = max(1, round(crop.width * s)), max(1, round(crop.height * s))
    crop = crop.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (rgba.shape[1], rgba.shape[0]), (0, 0, 0, 0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    canvas.paste(crop, (round(cx - nw / 2), round(cy - nh / 2)))
    return np.asarray(canvas).copy()


class _Samples:
    """Pixels of a part (and of the 2 px ring just outside it) used to score a placement against the key art."""

    def __init__(self, part: np.ndarray, budget: int):
        op = part[..., 3] > 230
        solid = part[..., 3] > 128
        rgb, reached = _propagate(part[..., :3].astype(np.float32), solid, 3)
        ring = _dilate(solid, 2) & ~solid & reached
        ys, xs = np.nonzero(op)
        st = max(1, int(np.sqrt(max(1, len(ys)) / budget)))
        keep = (ys % st == 0) & (xs % st == 0)
        self.ys, self.xs = ys[keep], xs[keep]
        self.rgb = part[self.ys, self.xs, :3].astype(np.float32)
        rys, rxs = np.nonzero(ring)
        st2 = max(1, int(np.sqrt(max(1, len(rys)) / max(2000, budget // 4))))
        keep2 = (rys + rxs) % st2 == 0
        self.rys, self.rxs = rys[keep2], rxs[keep2]
        self.ring_rgb = rgb[self.rys, self.rxs]

    def score(self, key_rgb: np.ndarray, key_a: np.ndarray, dx: int, dy: int, tol: float, occ: Optional[np.ndarray] = None) -> Tuple[float, float, float]:
        """(score, match) with the part moved by (dx, dy).

        match         mean over the part's pixels of max(0, 1 - (colour error / tol)^2): exact agreement counts 1,
                      "a similar colour" counts little.  Pixels covered by parts already placed above this one
                      (`occ`) do not vote: back hair must not be "matched" by the fringe lying on top of it.
        continuation  the same on the ring just OUTSIDE the part, against the part's own edge colour.  A uniform strand
                      slides along itself for free; a wrong position shows because the key art keeps going past its end.
        outside       share of the part lying where the key art is empty.  The key art is the composite of every part,
                      so this is impossible when the part is placed right; it costs the most.
        """
        H, W = key_a.shape
        n = len(self.ys)
        if n == 0:
            return 0.0, 0.0, 0.0
        y, x = self.ys + dy, self.xs + dx
        inb = (y >= 0) & (y < H) & (x >= 0) & (x < W)
        yc, xc = np.clip(y, 0, H - 1), np.clip(x, 0, W - 1)
        ka = key_a[yc, xc]
        vis = inb if occ is None else inb & ~occ[yc, xc]          # pixels another (already placed) part covers cannot vote
        err = np.abs(self.rgb - key_rgb[yc, xc]).max(-1)
        match = float((np.clip(1.0 - (err / tol) ** 2, 0, 1) * ((ka > 200) & vis)).sum()) / n
        outside = float(((ka < 40) | ~inb).sum()) / n
        cont = 0.0
        if len(self.rys):
            y2, x2 = self.rys + dy, self.rxs + dx
            in2 = (y2 >= 0) & (y2 < H) & (x2 >= 0) & (x2 < W)
            y2, x2 = np.clip(y2, 0, H - 1), np.clip(x2, 0, W - 1)
            v2 = in2 if occ is None else in2 & ~occ[y2, x2]
            e2 = np.abs(self.ring_rgb - key_rgb[y2, x2]).max(-1)
            cont = float((np.clip(1.0 - (e2 / tol) ** 2, 0, 1) * ((key_a[y2, x2] > 200) & v2)).sum()) / len(self.rys)
        return match - 0.5 * cont - 2.0 * outside, match, float(vis.sum()) / n


def _near(cands, eps, k=1):
    """Candidates within eps of the best score, smallest move first: a generated part rarely drifts far, and along a
    uniform strand every position scores the same."""
    top = max(c[0] for c in cands)
    return sorted((c for c in cands if c[0] >= top - eps), key=lambda c: (abs(c[-2]) + abs(c[-1]), -c[0]))[:k]


def align_to(key: np.ndarray, part: np.ndarray, search: int = 24, scales: Sequence[float] = (1.0,), tol: float = 24.0, occluded: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict]:
    """Find the shift (and optional scale) that makes the part coincide with the key art.

    occluded: bool (H, W) of pixels covered by parts that lie above this one and are already placed.
    The objective (see _Samples.score) is always evaluated on real, un-reduced pixels -- only fewer of them: first on
    a 3 px lattice of shifts, then densely around the three best.  Always confirm the result on recompose.png.
    """
    key_rgb, key_a = key[..., :3].astype(np.float32), key[..., 3]
    per_scale = []
    for s in sorted(set(list(scales) + [1.0])):
        p = _scale_about(part, s)
        if _bbox(p[..., 3]) is None:
            continue
        coarse_s, fine_s = _Samples(p, 12000), _Samples(p, 50000)
        lattice = [(*coarse_s.score(key_rgb, key_a, dx, dy, tol, occluded), dx, dy) for dy in range(-search, search + 1, 3) for dx in range(-search, search + 1, 3)]
        seeds = _near(lattice, 0.01, k=3)
        dense = {}
        for c in seeds:
            for dy in range(c[-1] - 3, c[-1] + 4):
                for dx in range(c[-2] - 3, c[-2] + 4):
                    if (dx, dy) not in dense:
                        dense[(dx, dy)] = (*fine_s.score(key_rgb, key_a, dx, dy, tol, occluded), dx, dy)
        best = _near(list(dense.values()), 0.0005)[0]
        # how much better is the chosen spot than anything at least 6 px away?  small margin = weakly constrained
        far = [c[0] for c in lattice if max(abs(c[-2] - best[-2]), abs(c[-1] - best[-1])) >= 6]
        margin = best[0] - max(far) if far else 1.0
        per_scale.append((best[0], best[1], best[2], best[3], best[4], s, p, margin))
    if not per_scale:
        return part, {"dx": 0, "dy": 0, "scale": 1.0, "match": 0.0, "visible": 0.0, "margin": 0.0, "confident": False, "constraint": "none"}
    top = max(t[0] for t in per_scale)
    score, match, visible, dx, dy, s, p, margin = min((t for t in per_scale if t[0] >= top - 0.002), key=lambda t: abs(t[5] - 1.0))
    base = _Samples(part, 50000).score(key_rgb, key_a, 0, 0, tol, occluded)
    reasons = []
    rivals = [t[5] for t in per_scale if abs(t[5] - s) > 1e-9 and t[0] >= score - 0.004]
    if rivals:
        reasons.append(f"its scale cannot be told from the key art (scale {min(rivals, key=lambda v: abs(v - s))} fits about as well as {s})")
    if visible < 0.10:
        reasons.append(f"only {visible:.0%} of it is visible in the key art")
    if margin < 0.012:
        reasons.append("the fit is almost as good several pixels away")
    info = {"dx": int(dx), "dy": int(dy), "scale": s, "match": round(match, 4), "visible": round(visible, 3), "score": round(score, 4), "score_before": round(base[0], 4),
            "margin": round(float(margin), 4), "constraint": "weak" if reasons else "ok", "why": "; ".join(reasons), "confident": bool(not reasons and score >= base[0] - 1e-6)}
    return _shift(p, dx, dy), info


# ------------------------------------------------------------------------------------------- audits
def seam_candidates(layers: Sequence[Tuple[str, np.ndarray]], min_overlap: int = 6) -> List[Dict]:
    """Where two parts meet on screen, does the lower one continue underneath the upper one?

    layers: [(name, alpha uint8 full canvas)] in draw order (setup-visible parts only).
    For every pair that is visibly adjacent, `underpaint` is how much of the upper part's edge strip (the
    `min_overlap` px next to their shared border) has the lower part beneath it.  Low values are butt joints: the
    moment either part moves, whatever lies behind both shows through the gap.
    """
    masks = [(n, a[::2, ::2] > 128) for n, a in layers]
    if not masks:
        return []
    owner = np.zeros(masks[0][1].shape, np.int32)              # top-most visible part per pixel (1-based)
    for k, (_, m) in enumerate(masks, start=1):
        owner[m] = k
    k_px = max(1, int(round(min_overlap / 2)))                 # half resolution
    pairs: Dict[Tuple[int, int], np.ndarray] = {}
    H, W = owner.shape
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        a = owner[max(0, dy):H + min(0, dy), max(0, dx):W + min(0, dx)]
        b = owner[max(0, -dy):H + min(0, -dy), max(0, -dx):W + min(0, -dx)]
        diff = (a != b) & (a > 0) & (b > 0) & (a > b)             # a = upper side pixel, b = its lower neighbour
        ys, xs = np.nonzero(diff)
        ys, xs = ys + max(0, dy), xs + max(0, dx)
        ups, lows = owner[ys, xs], b[diff]
        for u, l in set(zip(ups.tolist(), lows.tolist())):
            sel = (ups == u) & (lows == l)
            cur = pairs.setdefault((u, l), np.zeros(owner.shape, bool))
            cur[ys[sel], xs[sel]] = True
    out = []
    for (u, l), border in pairs.items():
        n = int(border.sum())
        if n < 10:
            continue
        # the strip of the upper part that lies within min_overlap px of the shared border: is the lower part under it?
        ys, xs = np.nonzero(border)
        y0, y1, x0, x1 = max(0, ys.min() - k_px - 1), min(H, ys.max() + k_px + 2), max(0, xs.min() - k_px - 1), min(W, xs.max() + k_px + 2)
        strip = _dilate(border[y0:y1, x0:x1], k_px) & (owner[y0:y1, x0:x1] == u)
        frac = float(masks[l - 1][1][y0:y1, x0:x1][strip].mean()) if strip.any() else 1.0
        risk = "SEAM" if frac < 0.5 else ("partial" if frac < 0.85 else "ok")
        row = {"upper": masks[u - 1][0], "lower": masks[l - 1][0], "border_px": n * 2, "underpaint": round(frac, 2), "risk": risk}
        if risk != "ok" and strip.any():
            # other parts lying under the same strip: tells you WHAT would show in the gap (fine for iris->eye white, wrong for neck->back hair)
            row["backed_by"] = [masks[o - 1][0] for o in range(1, u) if o != l and masks[o - 1][1][y0:y1, x0:x1][strip].mean() >= 0.8]
        out.append(row)
    out.sort(key=lambda r: (r["underpaint"], -r["border_px"]))
    return out


def coverage_image(layers: Sequence[Tuple[str, np.ndarray]], width: int = 640) -> Image.Image:
    """How many parts cover each pixel.  1 = nothing underneath (a hole if that part moves); 2+ = underpaint exists."""
    count = np.zeros(layers[0][1].shape, np.int32)
    for _, a in layers:
        count += (a > 128)
    palette = np.array([(14, 18, 24), (64, 84, 150), (54, 160, 150), (226, 200, 90), (240, 120, 80)], np.uint8)
    img = Image.fromarray(palette[np.clip(count, 0, 4)], "RGB")
    s = width / img.width
    img = img.resize((width, max(1, round(img.height * s))), Image.NEAREST)
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.load_default(size=13)
    except TypeError:
        f = ImageFont.load_default()
    for k, label in enumerate(("1 layer: no underpaint", "2 layers", "3 layers", "4+ layers")):
        d.rectangle((6, 6 + k * 18, 18, 18 + k * 18), fill=tuple(int(v) for v in palette[k + 1]))
        d.text((24, 5 + k * 18), label, fill=(235, 240, 245), font=f)
    return img


def grid_overlay(im: Image.Image, step: int = 50, crop: Optional[Sequence[int]] = None, width: int = 1400) -> Image.Image:
    """Draw a labelled coordinate grid so pixel positions can be read off the picture (labels are source pixels)."""
    im = im.convert("RGBA")
    x0, y0 = 0, 0
    if crop:
        x0, y0, w, h = (int(v) for v in crop)
        im = im.crop((x0, y0, x0 + w, y0 + h))
    bg = Image.new("RGBA", im.size, (120, 130, 142, 255))
    im = Image.alpha_composite(bg, im).convert("RGB")
    s = min(4.0, max(1.0, width / im.width))
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    try:
        f = ImageFont.load_default(size=12)
    except TypeError:
        f = ImageFont.load_default()
    W, H = im.size
    gx = (x0 // step) * step
    while gx <= x0 + W / s:
        if gx >= x0:
            X = (gx - x0) * s
            major = gx % (step * 2) == 0
            d.line((X, 0, X, H), fill=(255, 255, 255, 120 if major else 60), width=1)
            d.line((X + 1, 0, X + 1, H), fill=(0, 0, 0, 70 if major else 30), width=1)
            if major:
                d.rectangle((X + 2, 1, X + 2 + 7 * len(str(gx)), 14), fill=(0, 0, 0, 150))
                d.text((X + 3, 1), str(gx), fill=(255, 255, 120, 255), font=f)
        gx += step
    gy = (y0 // step) * step
    while gy <= y0 + H / s:
        if gy >= y0:
            Y = (gy - y0) * s
            major = gy % (step * 2) == 0
            d.line((0, Y, W, Y), fill=(255, 255, 255, 120 if major else 60), width=1)
            d.line((0, Y + 1, W, Y + 1), fill=(0, 0, 0, 70 if major else 30), width=1)
            if major:
                d.rectangle((1, Y + 2, 2 + 7 * len(str(gy)), Y + 15), fill=(0, 0, 0, 150))
                d.text((2, Y + 2), str(gy), fill=(120, 255, 255, 255), font=f)
        gy += step
    return im


def audit_parts(root: Path, manifest: Dict, min_overlap: int = 6) -> Dict:
    """Seam candidates + coverage map for any parts/ folder (used by both `spk art` and `spk layers`)."""
    W, H = manifest["canvas"]
    layers = []
    for p in manifest["parts"]:
        if p.get("hidden"):
            continue
        a = np.zeros((H, W), np.uint8)
        im = np.asarray(Image.open(root / "parts" / p["file"]).convert("RGBA"))
        a[p["y"]:p["y"] + p["h"], p["x"]:p["x"] + p["w"]] = im[..., 3]
        layers.append((p["name"], a))
    ev = root / "evidence" / "art"
    ev.mkdir(parents=True, exist_ok=True)
    coverage_image(layers).save(ev / "coverage.png")
    seams = seam_candidates(layers, min_overlap)
    return {"seam_candidates": [s for s in seams if s["risk"] != "ok"], "pairs_checked": len(seams), "coverage": str(ev / "coverage.png")}


# -------------------------------------------------------------------------------------------- build
def _load(path: Path, canvas: Tuple[int, int], resize: bool) -> np.ndarray:
    if not path.is_file():
        raise LayerError(f"source image not found: {path}")
    im = Image.open(path).convert("RGBA")
    if im.size != tuple(canvas):
        if not resize:
            raise LayerError(f"{path.name} is {im.size}, canvas is {tuple(canvas)}; generate at canvas size or set \"resize\": true")
        im = im.resize(tuple(canvas), Image.LANCZOS)
    return np.asarray(im).copy()


def build_layers(root: Path, spec_path: Path) -> Dict:
    from .sheets import flatten, on_backgrounds, parts_sheet
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    base = spec_path.parent
    if "parts" not in spec or not spec["parts"]:
        raise LayerError("layers spec has no parts")
    key_file = spec.get("keyart")
    if "canvas" in spec:
        W, H = spec["canvas"]
    elif key_file:
        W, H = Image.open(base / key_file).size
    else:
        raise LayerError("give \"canvas\": [W, H] or a \"keyart\" image")
    resize = bool(spec.get("resize", False))
    bg_opt = spec.get("background")
    defaults = spec.get("defaults", {})
    cache: Dict[str, np.ndarray] = {}
    report = {"canvas": [W, H], "keying": [], "alignment": [], "cleanup": [], "warnings": []}

    def source(rel: str, do_key) -> np.ndarray:
        ck = f"{rel}|{do_key}"
        if ck in cache:
            return cache[ck].copy()
        img = _load(base / rel, (W, H), resize)
        det = detect_background(img)
        if det["kind"] == "checker":
            raise LayerError(f"{rel}: the transparency checkerboard is baked into the pixels (colours {det['colors']}); regenerate on a solid colour that does not occur in the character")
        if do_key:
            colour = None
            if isinstance(do_key, str) and do_key not in ("auto", "true"):
                colour = _hex(do_key)
            elif det["kind"] == "solid":
                colour = det["color"]
            elif det["kind"] == "alpha":
                colour = None
            else:
                raise LayerError(f"{rel}: cannot find a solid background to remove (border is {det}); give \"background\": \"#rrggbb\"")
            if colour is not None:
                img, st = chroma_key(img, colour, mode=spec.get("key_mode", "global"))
                st["source"] = rel
                report["keying"].append(st)
                if st["translucent_share"] > 0.03:
                    report["warnings"].append(f"{rel}: {st['translucent_share']:.0%} of the shape is translucent (soft fade, blur, glow). Colour there is an estimate and drifts toward or away from the background hue "
                                              f"(pink turns olive on green). Keep generated layers opaque: cut soft details from the key art by polygon, and make fades with \"fade\" in layers.json")
        elif det["kind"] == "solid":
            report["warnings"].append(f"{rel}: opaque solid background ({det['color']}) and keying is off -- the part will carry its background")
        cache[ck] = img
        return img.copy()

    key_img = source(key_file, bg_opt if bg_opt else False) if key_file else None
    full: Dict[str, np.ndarray] = {}
    manifest = {"canvas": [W, H], "source": spec_path.name, "parts": []}
    parts_dir = root / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    for old in parts_dir.glob("*.png"):
        old.unlink()
    preview_polys = []
    names = [p.get("name") for p in spec["parts"]]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise LayerError("every part needs a unique \"name\"")

    def shape(p, img):
        """Polygon / holes / fade / despeckle: everything that happens in canvas coordinates after placement."""
        name = p["name"]
        if p.get("polygon"):
            m = polygon_mask((W, H), p["polygon"], p.get("holes", ()), float(p.get("feather", defaults.get("feather", 1.0))))
            img[..., 3] = np.rint(img[..., 3] * m).astype(np.uint8)
            preview_polys.append((name, p["polygon"], p.get("holes", ())))
        elif p.get("holes"):
            m = np.ones((H, W), np.float32)
            for hole in p["holes"]:
                m = m * (1.0 - polygon_mask((W, H), hole, (), float(p.get("feather", 1.0))))
            img[..., 3] = np.rint(img[..., 3] * m).astype(np.uint8)
            preview_polys.append((name, None, p["holes"]))
        if p.get("fade"):
            img[..., 3] = edge_fade(img[..., 3], p["fade"])
        r = p.get("despeckle", defaults.get("despeckle", 0))
        if r:
            img, removed = despeckle(img, int(r))
            if removed:
                report["cleanup"].append({"part": name, "speck_pixels_removed": removed})
        img[img[..., 3] == 0, :3] = 0
        return img

    # Pass 1 (front to back): place every part that comes from its own image.  Parts in front are fully visible, so
    # they register reliably; each one then becomes an occluder for the parts behind it.
    occ = np.zeros((H, W), bool)
    for p in reversed(spec["parts"]):
        name = p["name"]
        src = p.get("source", defaults.get("source", "keyart"))
        if src.startswith("@"):
            continue
        if src == "keyart":
            if key_img is None:
                raise LayerError(f"{name}: source is the key art but the spec has no \"keyart\"")
            img = key_img.copy()
        else:
            want_key = p.get("key", defaults.get("key", bg_opt if bg_opt else False))
            img = source(src, want_key)
            al = p.get("align", defaults.get("align", False))
            if p.get("place"):
                # manual placement (after looking at recompose.png): {"dx": px, "dy": px, "scale": 1.0}; replaces align
                pl = p["place"]
                img = _shift(_scale_about(img, float(pl.get("scale", 1.0))), int(pl.get("dx", 0)), int(pl.get("dy", 0)))
                report["alignment"].append({"part": name, "dx": int(pl.get("dx", 0)), "dy": int(pl.get("dy", 0)), "scale": float(pl.get("scale", 1.0)), "constraint": "manual", "confident": True})
            elif al and key_img is not None and not p.get("hidden"):
                opts = al if isinstance(al, dict) else {}
                scales = (0.98, 0.99, 1.0, 1.01, 1.02) if opts.get("scale", False) else (1.0,)
                img, info = align_to(key_img, img, search=int(opts.get("search", 24)), scales=scales, occluded=_dilate(occ, 2))
                info["part"] = name
                report["alignment"].append(info)
                if not info["confident"]:
                    report["warnings"].append(f"{name}: placement is weakly constrained ({info['why']}), so the key art cannot pin it down. Kept dx={info['dx']} dy={info['dy']} scale={info['scale']}; "
                                              f"look at recompose.png and, if it is off, set \"place\": {{\"dx\":…, \"dy\":…, \"scale\":…}} for this part")
            elif al and p.get("hidden"):
                report["warnings"].append(f"{name}: hidden alternates are not in the key art and cannot be aligned to it; generate them as an edit of the visible attachment so they share its position")
        img = shape(p, img)
        full[name] = img
        if not p.get("hidden"):
            occ |= img[..., 3] > 128
    report["alignment"].reverse()

    # Pass 2 (back to front): parts copied from another part ("@name"), then write everything in draw order.
    for p in spec["parts"]:
        name = p["name"]
        src = p.get("source", defaults.get("source", "keyart"))
        if src.startswith("@"):
            if src[1:] not in full:
                raise LayerError(f"{name}: source {src} must name an earlier part that has its own image")
            full[name] = shape(p, full[src[1:]].copy())
        img = full[name]
        box = _bbox(img[..., 3])
        if not box:
            raise LayerError(f"{name}: nothing left after cutting (check polygon coordinates / keying)")
        pad = 2
        x0, y0, x1, y1 = max(0, box[0] - pad), max(0, box[1] - pad), min(W, box[2] + pad), min(H, box[3] + pad)
        Image.fromarray(img[y0:y1, x0:x1], "RGBA").save(parts_dir / f"{name}.png")
        entry = {"name": name, "file": f"{name}.png", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
        if p.get("hidden"):
            entry["hidden"] = True
        manifest["parts"].append(entry)
    (parts_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    ev = root / "evidence" / "art"
    ev.mkdir(parents=True, exist_ok=True)
    comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for e in manifest["parts"]:
        if not e.get("hidden"):
            comp = Image.alpha_composite(comp, Image.fromarray(full[e["name"]], "RGBA"))
    if key_img is not None:
        key_pil = Image.fromarray(key_img, "RGBA")
        key_pil.save(parts_dir / "keyart.png")
        A, Bm = np.asarray(flatten(key_pil, "mid")).astype(int), np.asarray(flatten(comp, "mid")).astype(int)
        diff = np.abs(A - Bm).max(axis=2)
        heat = Image.fromarray(np.clip(diff * 4, 0, 255).astype(np.uint8), "L")
        heat = Image.merge("RGB", (heat, Image.new("L", heat.size, 0), Image.new("L", heat.size, 40)))
        tile = 460
        size = (tile, round(H * tile / W))
        sheet = Image.new("RGB", (tile * 3 + 16, size[1] + 8), (12, 16, 22))
        for i, im in enumerate((flatten(key_pil, "mid"), flatten(comp, "mid"), heat)):
            sheet.paste(im.resize(size, Image.LANCZOS), (4 + i * (tile + 4), 4))
        sheet.save(ev / "recompose.png")
        over = diff > 24
        ys, xs = np.nonzero(over)
        report["recompose"] = {"max_diff": int(diff.max()), "pixels_over_24": int(over.sum()), "fraction": round(float(over.mean()), 6),
                               "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None, "sheet": str(ev / "recompose.png")}
        on_backgrounds(key_pil).save(ev / "keyart_bg.png")
        prev = flatten(key_pil, "mid").convert("RGBA")
    else:
        comp.save(parts_dir / "keyart.png")
        report["warnings"].append("no key art given: parts/keyart.png is the recomposition, so `spk fidelity` only proves the rig matches the parts, not an approved picture")
        on_backgrounds(comp).save(ev / "keyart_bg.png")
        prev = flatten(comp, "mid").convert("RGBA")
    if preview_polys:
        d = ImageDraw.Draw(prev, "RGBA")
        try:
            f = ImageFont.load_default(size=13)
        except TypeError:
            f = ImageFont.load_default()
        for i, (name, poly, holes) in enumerate(preview_polys):
            col = [(255, 90, 90), (90, 220, 255), (255, 220, 80), (150, 255, 140), (255, 140, 240)][i % 5]
            if poly:
                d.line([tuple(q) for q in poly] + [tuple(poly[0])], fill=col + (255,), width=2)
                d.text((poly[0][0] + 3, poly[0][1] + 2), name, fill=col + (255,), font=f)
            for hole in holes or ():
                d.line([tuple(q) for q in hole] + [tuple(hole[0])], fill=col + (200,), width=1)
        prev.convert("RGB").save(ev / "layers_preview.png")
    parts_sheet(root, manifest).save(ev / "parts_sheet.png")
    report.update(audit_parts(root, manifest, int(spec.get("min_overlap", 6))))
    report["parts"] = len(manifest["parts"])
    report["review"] = [str(ev / n) for n in ("keyart_bg.png", "parts_sheet.png", "coverage.png") + (("recompose.png",) if key_img is not None else ()) + (("layers_preview.png",) if preview_polys else ())]
    return report
