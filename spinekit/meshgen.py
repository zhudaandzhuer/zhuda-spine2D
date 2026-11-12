"""Mesh generation for Spine mesh attachments.

`grid_mesh` builds a regular grid over a part image, drops cells that hold no visible pixels, and returns
vertices with the hull first and in loop order -- the layout the Spine JSON format (and the Editor) expects.
A grid is deliberate: it is deterministic, deforms predictably under bone chains, and the texture's own alpha
defines the silhouette, so vertices never have to trace the outline.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def _fill_holes(occ: np.ndarray) -> np.ndarray:
    """Mark empty cells that are not 4-connected to the outside as occupied."""
    h, w = occ.shape
    pad = np.zeros((h + 2, w + 2), dtype=bool)
    pad[1:-1, 1:-1] = occ
    outside = np.zeros_like(pad)
    stack = [(0, 0)]
    outside[0, 0] = True
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h + 2 and 0 <= xx < w + 2 and not outside[yy, xx] and not pad[yy, xx]:
                outside[yy, xx] = True
                stack.append((yy, xx))
    return ~outside[1:-1, 1:-1]


def _components(occ: np.ndarray) -> int:
    seen = np.zeros_like(occ)
    count = 0
    h, w = occ.shape
    for y0 in range(h):
        for x0 in range(w):
            if occ[y0, x0] and not seen[y0, x0]:
                count += 1
                stack = [(y0, x0)]
                seen[y0, x0] = True
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and occ[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True
                            stack.append((yy, xx))
    return count


def _remove_pinches(occ: np.ndarray) -> np.ndarray:
    """A grid corner shared only by two diagonal cells would put one vertex on the hull twice; fill one neighbour."""
    occ = occ.copy()
    changed = True
    while changed:
        changed = False
        h, w = occ.shape
        for y in range(h - 1):
            for x in range(w - 1):
                a, b, c, d = occ[y, x], occ[y, x + 1], occ[y + 1, x], occ[y + 1, x + 1]
                if a and d and not b and not c:
                    occ[y, x + 1] = True
                    changed = True
                elif b and c and not a and not d:
                    occ[y, x] = True
                    changed = True
        if changed:
            occ = _fill_holes(occ)
    return occ


def grid_mesh(alpha: np.ndarray, step: float = 32.0, cols: int = 0, rows: int = 0, margin: int = 3, threshold: int = 6, cull: bool = True) -> Dict:
    """Build a grid mesh for an (h, w) uint8 alpha image.

    Returns dict(points=[(px, py)...] in image pixels (y down), uvs=[u, v, ...], triangles=[...], hull=int, edges=[...]).
    Hull vertices come first, in loop order.
    """
    h, w = alpha.shape
    nx = cols or max(1, int(np.ceil(w / step)))
    ny = rows or max(1, int(np.ceil(h / step)))
    xs = np.linspace(0, w, nx + 1)
    ys = np.linspace(0, h, ny + 1)
    occ = np.ones((ny, nx), dtype=bool)
    if cull:
        solid = alpha > threshold
        for j in range(ny):
            y0, y1 = max(0, int(np.floor(ys[j])) - margin), min(h, int(np.ceil(ys[j + 1])) + margin)
            for i in range(nx):
                x0, x1 = max(0, int(np.floor(xs[i])) - margin), min(w, int(np.ceil(xs[i + 1])) + margin)
                occ[j, i] = bool(solid[y0:y1, x0:x1].any())
        if not occ.any():
            occ[:] = True
        occ = _fill_holes(occ)
        occ = _remove_pinches(occ)
        if _components(occ) != 1:  # disjoint islands: fall back to the full rectangle (always valid)
            occ[:] = True

    # Directed boundary edges (image space is y-down; trace with the solid on the left -> a single closed loop).
    nxt: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for j in range(ny):
        for i in range(nx):
            if not occ[j, i]:
                continue
            if j == 0 or not occ[j - 1, i]:
                nxt[(i, j)] = (i + 1, j)  # top edge, left -> right
            if i == nx - 1 or not occ[j, i + 1]:
                nxt[(i + 1, j)] = (i + 1, j + 1)  # right edge, down
            if j == ny - 1 or not occ[j + 1, i]:
                nxt[(i + 1, j + 1)] = (i, j + 1)  # bottom edge, right -> left
            if i == 0 or not occ[j, i - 1]:
                nxt[(i, j + 1)] = (i, j)  # left edge, up
    start = min(nxt)  # deterministic
    loop = [start]
    cur = nxt[start]
    while cur != start:
        loop.append(cur)
        cur = nxt[cur]
        if len(loop) > len(nxt) + 1:
            raise RuntimeError("hull tracing failed")
    if len(loop) != len(nxt):
        raise RuntimeError("mesh hull is not a single loop")

    index: Dict[Tuple[int, int], int] = {g: k for k, g in enumerate(loop)}
    for j in range(ny):
        for i in range(nx):
            if occ[j, i]:
                for g in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                    if g not in index:
                        index[g] = len(index)
    order = sorted(index, key=index.get)
    points = [(float(xs[i]), float(ys[j])) for i, j in order]
    uvs: List[float] = []
    for px, py in points:
        uvs += [round(px / w, 5), round(py / h, 5)]
    triangles: List[int] = []
    for j in range(ny):
        for i in range(nx):
            if occ[j, i]:
                a, b, c, d = index[(i, j)], index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]
                if (i + j) % 2 == 0:
                    triangles += [a, b, c, a, c, d]
                else:
                    triangles += [a, b, d, b, c, d]
    hull = len(loop)
    edges: List[int] = []
    for k in range(hull):
        edges += [k * 2, ((k + 1) % hull) * 2]
    return {"points": points, "uvs": uvs, "triangles": triangles, "hull": hull, "edges": edges, "cells": int(occ.sum()), "grid": (nx, ny)}
