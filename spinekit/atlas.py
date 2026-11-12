"""Texture atlas packing for Spine 4.2 (.atlas + single PNG page).

Regions are never trimmed, rotated or rescaled, so mesh UVs and region sizes stay trivially correct.
Straight-alpha pages get their fully transparent pixels' RGB bled outward from the nearest visible pixel:
under LINEAR filtering the GPU mixes neighbouring texels, and transparent texels with black or white RGB
are what cause dark/light fringes when a character is drawn smaller than its source size.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
from PIL import Image


def bleed_rgb(rgba: np.ndarray, iterations: int = 6) -> np.ndarray:
    """Spread RGB of visible pixels into alpha==0 pixels (alpha untouched)."""
    out = rgba.astype(np.float32).copy()
    known = rgba[..., 3] > 0
    if known.all() or not known.any():
        return rgba
    rgb = out[..., :3] * known[..., None]
    for _ in range(iterations):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                k = np.roll(np.roll(known, dy, 0), dx, 1)
                c = np.roll(np.roll(rgb, dy, 0), dx, 1)
                # do not wrap around the borders
                if dy == 1: k[0, :] = False
                if dy == -1: k[-1, :] = False
                if dx == 1: k[:, 0] = False
                if dx == -1: k[:, -1] = False
                acc += c * k[..., None]
                cnt += k
        grow = (~known) & (cnt > 0)
        if not grow.any():
            break
        rgb[grow] = acc[grow] / cnt[grow][..., None]
        known = known | grow
    res = rgba.copy()
    fill = rgba[..., 3] == 0
    res[..., :3][fill] = np.clip(np.rint(rgb[fill]), 0, 255).astype(np.uint8)
    return res


def _skyline_pack(sizes: List[Tuple[int, int]], width: int, height: int) -> List[Tuple[int, int]] | None:
    """Bottom-left skyline.  sizes already include padding.  Returns positions or None if it does not fit."""
    sky = [(0, 0, width)]  # (x, y, w) segments
    pos: List[Tuple[int, int]] = []
    for w, h in sizes:
        best = None
        for i, (sx, _, _) in enumerate(sky):
            if sx + w > width:
                continue
            y, remaining, j = 0, w, i
            while remaining > 0 and j < len(sky):
                y = max(y, sky[j][1])
                remaining -= sky[j][2]
                j += 1
            if remaining > 0 or y + h > height:
                continue
            if best is None or (y, sx) < (best[0], best[1]):
                best = (y, sx, i)
        if best is None:
            return None
        y, x, i = best
        pos.append((x, y))
        new = (x, y + h, w)
        end = x + w
        out = sky[:i]
        out.append(new)
        j = i
        while j < len(sky):
            sx, sy, sw = sky[j]
            if sx + sw <= end:
                j += 1
                continue
            if sx < end:
                out.append((end, sy, sx + sw - end))
            else:
                out.append((sx, sy, sw))
            j += 1
        sky = out
    return pos


def pack(images: Dict[str, Image.Image], page_name: str, padding: int = 4, bleed: int = 6, pma: bool = False, max_size: int = 4096, pot: bool = True) -> Tuple[Image.Image, str, Dict[str, Tuple[int, int, int, int]]]:
    """Pack RGBA images into one page.  Returns (page image, atlas text, {name: (x, y, w, h)})."""
    names = sorted(images, key=lambda n: (-images[n].height, -images[n].width, n))
    sizes = [(images[n].width + padding * 2, images[n].height + padding * 2) for n in names]
    area = sum(w * h for w, h in sizes)
    widest, tallest = max(w for w, _ in sizes), max(h for _, h in sizes)
    candidates = []
    dims = [256, 512, 1024, 2048, 4096, 8192] if pot else list(range(256, max_size + 1, 128))
    for w in dims:
        for h in dims:
            if w <= max_size and h <= max_size and w >= widest and h >= tallest and w * h >= area:
                candidates.append((w * h, max(w, h), w, h))
    placed = None
    for _, _, w, h in sorted(candidates):
        placed = _skyline_pack(sizes, w, h)
        if placed:
            W, H = w, h
            break
    if not placed:
        raise ValueError(f"parts do not fit one {max_size}x{max_size} page; reduce art scale or split the character")
    page = np.zeros((H, W, 4), dtype=np.uint8)
    regions: Dict[str, Tuple[int, int, int, int]] = {}
    for n, (x, y) in zip(names, placed):
        im = images[n].convert("RGBA")
        a = np.asarray(im)
        ph, pw = a.shape[0] + padding * 2, a.shape[1] + padding * 2
        cell = np.zeros((ph, pw, 4), dtype=np.uint8)
        cell[padding:padding + a.shape[0], padding:padding + a.shape[1]] = a
        if not pma and bleed > 0:
            cell = bleed_rgb(cell, iterations=max(bleed, padding))
        page[y:y + ph, x:x + pw] = cell
        regions[n] = (x + padding, y + padding, a.shape[1], a.shape[0])
    if pma:
        f = page.astype(np.float32)
        f[..., :3] = np.rint(f[..., :3] * f[..., 3:4] / 255.0)
        page = f.astype(np.uint8)
    lines = [page_name, f"size:{W},{H}", "filter:Linear,Linear", f"pma:{'true' if pma else 'false'}"]
    for n in sorted(regions):
        x, y, w, h = regions[n]
        lines += [n, f"bounds:{x},{y},{w},{h}"]
    return Image.fromarray(page, "RGBA"), "\n".join(lines) + "\n", regions
