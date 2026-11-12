"""Weight fields.

A weight field is a callable `field(rig, sx, sy) -> {bone_name: weights}` evaluated on arrays of
*source-pixel* coordinates (the same y-down pixel space the art is drawn in).  Fields are analytic, so two
parts that share a field move identically wherever they overlap -- this is what keeps eyelashes glued to
the face or a collar glued to the chest without hand-painting weights.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

Field = Callable[[object, np.ndarray, np.ndarray], Dict[str, np.ndarray]]


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _seg_project(px, py, ax, ay, bx, by):
    """Per-point parameter t in [0,1] along segment AB, distance to it, and signed side (+ = left of A->B in y-down px)."""
    dx, dy = bx - ax, by - ay
    L2 = max(dx * dx + dy * dy, 1e-9)
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0.0, 1.0)
    qx, qy = ax + t * dx, ay + t * dy
    dist = np.hypot(px - qx, py - qy)
    side = np.sign((px - ax) * dy - (py - ay) * dx)
    return t, dist, side


def _polyline(rig, bones: Sequence[str]):
    pts = [rig.bones[bones[0]].at]
    for i, name in enumerate(bones):
        b = rig.bones[name]
        nxt = rig.bones[bones[i + 1]].at if i + 1 < len(bones) else b.tip_px()
        pts.append(nxt)
    return pts


def _chain_param(rig, bones, sx, sy):
    """Arc-length parameter along the chain polyline, distance to it and signed side for every point."""
    pts = _polyline(rig, bones)
    lens = [float(np.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])) for i in range(len(bones))]
    cum = np.concatenate([[0.0], np.cumsum(lens)])
    best_d = np.full(sx.shape, np.inf)
    best_u = np.zeros(sx.shape)
    best_side = np.zeros(sx.shape)
    for i in range(len(bones)):
        t, d, side = _seg_project(sx, sy, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        better = d < best_d
        best_d = np.where(better, d, best_d)
        best_u = np.where(better, cum[i] + t * lens[i], best_u)
        best_side = np.where(better, side, best_side)
    # points beyond the first joint (above the root) get a negative parameter so a root blend can act on them
    ax, ay, bx, by = pts[0][0], pts[0][1], pts[1][0], pts[1][1]
    dx, dy = bx - ax, by - ay
    L = max(float(np.hypot(dx, dy)), 1e-9)
    before = ((sx - ax) * dx + (sy - ay) * dy) / L
    best_u = np.where(before < 0, before, best_u)
    return best_u, best_d, best_side, cum, lens


def chain(bones: Sequence[str], blend: float = 0.5, root: Optional[str] = None, root_blend: float = 0.5) -> Field:
    """Smooth weights along a bone chain (hair lock, arm, tail, spine).

    blend       width of the cross-fade around each joint, as a fraction of the shorter adjacent bone
    root        optional bone that owns everything before the first joint (e.g. 'head' above a hair lock);
                the hand-over is centred on the first joint and `root_blend` bone-lengths wide.
    """
    bones = list(bones)

    def field(rig, sx, sy):
        u, _, _, cum, lens = _chain_param(rig, bones, sx, sy)
        w = {b: np.zeros(sx.shape) for b in bones}
        w[bones[0]] = np.ones(sx.shape)
        for i in range(1, len(bones)):
            half = max(1e-6, blend * min(lens[i - 1], lens[i]) * 0.5)
            s = smoothstep((u - (cum[i] - half)) / (2 * half))
            # hand over from bone i-1 (and everything before) to bone i
            for j in range(i):
                w[bones[j]] = w[bones[j]] * (1 - s)
            w[bones[i]] = s
        if root:
            half = max(1e-6, root_blend * lens[0] * 0.5)
            s = smoothstep((u + half) / (2 * half))
            for b in bones:
                w[b] = w[b] * s
            w[root] = w.get(root, np.zeros(sx.shape)) + (1 - s)
        return w

    return field


def sheet(chains: Sequence[Sequence[str]], blend: float = 0.5, root: Optional[str] = None, root_blend: float = 0.5) -> Field:
    """Cloth-like weights for a surface driven by several roughly parallel chains (back hair, cape, skirt).

    Chains must be listed in spatial order (e.g. left to right).  Each point is weighted along its two
    neighbouring chains and cross-faded by its distance to each.
    """
    chains = [list(c) for c in chains]
    fields = [chain(c, blend=blend, root=root, root_blend=root_blend) for c in chains]

    def field(rig, sx, sy):
        dists = [_chain_param(rig, c, sx, sy)[1] for c in chains]
        per = [f(rig, sx, sy) for f in fields]
        out: Dict[str, np.ndarray] = {}
        if len(chains) == 1:
            return per[0]
        D = np.stack(dists)  # (n_chains, n_points)
        order = np.argsort(D, axis=0)
        i0, i1 = order[0], order[1]
        d0 = np.take_along_axis(D, i0[None], 0)[0]
        d1 = np.take_along_axis(D, i1[None], 0)[0]
        # only blend between spatial neighbours; otherwise the nearest chain wins
        neighbour = np.abs(i0 - i1) == 1
        t = np.where(neighbour, d0 / np.maximum(d0 + d1, 1e-9), 0.0)
        t = smoothstep(t * 2) * 0.5  # t in [0, .5]: equal share exactly midway between two chains
        for ci, w in enumerate(per):
            share = np.where(i0 == ci, 1 - t, 0.0) + np.where((i1 == ci) & neighbour, t, 0.0)
            for b, arr in w.items():
                out[b] = out.get(b, np.zeros(sx.shape)) + arr * share
        return out

    return field


def depth(base: str, front: str, z: Callable[[np.ndarray, np.ndarray], np.ndarray], back: Optional[str] = None) -> Field:
    """Parallax weights for pseudo-3D turning.

    `front` is a bone that a look controller displaces; `back` (optional) is displaced the opposite way.
    z(sx, sy) returns depth in [-1, 1]: +1 moves fully with `front`, 0 stays with `base`, -1 moves with `back`.
    """

    def field(rig, sx, sy):
        zz = np.clip(np.asarray(z(sx, sy), dtype=float), -1.0, 1.0)
        f = np.clip(zz, 0, 1)
        out = {base: 1 - np.abs(zz), front: f}
        if back:
            out[back] = np.clip(-zz, 0, 1)
        else:
            out[base] = 1 - f
        return out

    return field


def rigid(bone: str) -> Field:
    return lambda rig, sx, sy: {bone: np.ones(sx.shape)}


def nearest(bones: Sequence[str], power: float = 2.0, k: int = 3) -> Field:
    """Inverse-distance weights to bone segments.  A blunt tool: prefer chain/sheet/depth when they fit."""
    bones = list(bones)

    def field(rig, sx, sy):
        ds = []
        for name in bones:
            b = rig.bones[name]
            tip = b.tip_px()
            _, d, _ = _seg_project(sx, sy, b.at[0], b.at[1], tip[0], tip[1])
            ds.append(d)
        D = np.stack(ds)
        W = 1.0 / np.power(np.maximum(D, 1.0), power)
        if k < len(bones):
            kth = np.sort(W, axis=0)[-k]
            W = np.where(W >= kth, W, 0.0)
        return {b: W[i] for i, b in enumerate(bones)}

    return field


def blend(a: Field, b: Field, mask: Callable[[np.ndarray, np.ndarray], np.ndarray]) -> Field:
    """(1-mask)*a + mask*b.  mask(sx, sy) in [0,1].  Example: rigid head cap that hands over to hair chains lower down."""

    def field(rig, sx, sy):
        m = np.clip(np.asarray(mask(sx, sy), dtype=float), 0, 1)
        wa, wb = normalize(a(rig, sx, sy)), normalize(b(rig, sx, sy))
        out: Dict[str, np.ndarray] = {}
        for k2, v in wa.items():
            out[k2] = out.get(k2, 0) + v * (1 - m)
        for k2, v in wb.items():
            out[k2] = out.get(k2, 0) + v * m
        return out

    return field


def layered(inner: Field, base: str, front: str, z: Callable, back: Optional[str] = None, remap: Optional[Dict[str, str]] = None) -> Field:
    """Apply parallax depth on top of another field: the share `inner` gives to `base` is split by depth."""
    d = depth(base, front, z, back)

    def field(rig, sx, sy):
        wi = normalize(inner(rig, sx, sy))
        wd = d(rig, sx, sy)
        out = {k2: v.copy() for k2, v in wi.items() if k2 != base}
        share = wi.get(base, np.zeros(sx.shape))
        for k2, v in wd.items():
            out[k2] = out.get(k2, 0) + v * share
        return out

    return field


def normalize(w: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    total = None
    for v in w.values():
        total = v.copy() if total is None else total + v
    total = np.maximum(total, 1e-9)
    return {k: v / total for k, v in w.items()}


def finalize(w: Dict[str, np.ndarray], max_influences: int = 4, prune: float = 0.015) -> List[List[tuple]]:
    """-> per-vertex [(bone, weight), ...], normalised, pruned, capped, heaviest first."""
    w = normalize(w)
    names = list(w)
    W = np.stack([w[n] for n in names])  # (bones, verts)
    out = []
    for v in range(W.shape[1]):
        col = [(names[i], float(W[i, v])) for i in range(len(names)) if W[i, v] > prune]
        if not col:
            i = int(np.argmax(W[:, v]))
            col = [(names[i], 1.0)]
        col.sort(key=lambda x: -x[1])
        col = col[:max_influences]
        s = sum(x[1] for x in col)
        out.append([(n, x / s) for n, x in col])
    return out
