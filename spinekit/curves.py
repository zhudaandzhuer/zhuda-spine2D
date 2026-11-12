"""Animation curves.

Every animated channel (one bone property, one slot alpha, ...) is a sum of *layers*.  A layer is a
piecewise cubic Hermite curve.  Because a Spine 4.2 bezier key whose control points sit at 1/3 and 2/3 of
the key interval is exactly a cubic polynomial in time, layers can be summed at the union of their key
times and exported without baking dense keys: the result is exact for keyed layers and accurate to
<0.1% of amplitude for oscillator layers (sampled 8 keys per period).
"""
from __future__ import annotations

import bisect
import math
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

EPS = 1e-9


class PP:
    """Piecewise cubic Hermite.  t: knots, v: values, mr[i]: slope leaving knot i, ml[i]: slope arriving at knot i."""

    def __init__(self, t: Sequence[float], v: Sequence[float], mr: Sequence[float], ml: Sequence[float], stepped: Optional[Sequence[bool]] = None):
        if len(t) == 0:
            raise ValueError("curve needs at least one key")
        for a, b in zip(t, t[1:]):
            if b - a <= EPS:
                raise ValueError(f"key times must be strictly increasing (got {a} then {b})")
        self.t, self.v, self.mr, self.ml = list(map(float, t)), list(map(float, v)), list(map(float, mr)), list(map(float, ml))
        self.stepped = list(stepped) if stepped else [False] * len(self.t)

    # -- evaluation ---------------------------------------------------------------------------------
    def _seg(self, x: float) -> int:
        return max(0, min(len(self.t) - 2, bisect.bisect_right(self.t, x) - 1))

    def value(self, x: float) -> float:
        t = self.t
        if len(t) == 1 or x <= t[0]:
            return self.v[0]
        if x >= t[-1]:
            return self.v[-1]
        i = self._seg(x)
        if self.stepped[i]:
            return self.v[i]
        h = t[i + 1] - t[i]
        s = (x - t[i]) / h
        h00 = 2 * s**3 - 3 * s**2 + 1
        h10 = s**3 - 2 * s**2 + s
        h01 = -2 * s**3 + 3 * s**2
        h11 = s**3 - s**2
        return h00 * self.v[i] + h10 * h * self.mr[i] + h01 * self.v[i + 1] + h11 * h * self.ml[i + 1]

    def slope(self, x: float, side: str) -> float:
        """Derivative at x, approaching from 'left' or 'right'."""
        t = self.t
        if len(t) == 1:
            return 0.0
        if side == "right":
            if x < t[0] - EPS or x >= t[-1] - EPS:
                return 0.0
            i = max(0, min(len(t) - 2, bisect.bisect_right(t, x + EPS) - 1))
        else:
            if x <= t[0] + EPS or x > t[-1] + EPS:
                return 0.0
            i = max(0, min(len(t) - 2, bisect.bisect_left(t, x - EPS) - 1))
        if self.stepped[i]:
            return 0.0
        h = t[i + 1] - t[i]
        s = min(1.0, max(0.0, (x - t[i]) / h))
        d00 = (6 * s**2 - 6 * s) / h
        d10 = 3 * s**2 - 4 * s + 1
        d01 = (-6 * s**2 + 6 * s) / h
        d11 = 3 * s**2 - 2 * s
        return d00 * self.v[i] + d10 * self.mr[i] + d01 * self.v[i + 1] + d11 * self.ml[i + 1]


def keyed(keys: Sequence[Tuple], ease: str = "ease", loop: bool = False) -> PP:
    """Build a layer from (time, value[, ease]) keys.

    ease (applies to the segment leaving the key):
      'ease'   slow-in/slow-out between keys (zero slope at both keys)   -- pose-to-pose default
      'smooth' Catmull-Rom through the keys (periodic when loop=True and first == last value)
      'linear' constant speed        'in' slow start        'out' slow stop        'hold' stepped
    """
    keys = sorted(keys, key=lambda k: k[0])
    t = [float(k[0]) for k in keys]
    v = [float(k[1]) for k in keys]
    e = [(k[2] if len(k) > 2 and k[2] else ease) for k in keys]
    n = len(t)
    mr, ml, stepped = [0.0] * n, [0.0] * n, [False] * n
    periodic = loop and n > 2 and abs(v[0] - v[-1]) < 1e-9

    def cr(i: int) -> float:  # Catmull-Rom slope at knot i
        if 0 < i < n - 1:
            return (v[i + 1] - v[i - 1]) / (t[i + 1] - t[i - 1])
        if periodic:
            span = (t[1] - t[0]) + (t[-1] - t[-2])
            return (v[1] - v[-2]) / span
        return 0.0

    for i in range(n - 1):
        h = t[i + 1] - t[i]
        s = (v[i + 1] - v[i]) / h
        mode = e[i]
        if mode == "linear":
            mr[i], ml[i + 1] = s, s
        elif mode == "ease":
            mr[i], ml[i + 1] = 0.0, 0.0
        elif mode == "in":
            mr[i], ml[i + 1] = 0.0, 1.5 * s
        elif mode == "out":
            mr[i], ml[i + 1] = 1.5 * s, 0.0
        elif mode == "smooth":
            mr[i], ml[i + 1] = cr(i), cr(i + 1)
        elif mode == "hold":
            stepped[i] = True
        else:
            raise ValueError(f"unknown ease '{mode}'")
    return PP(t, v, mr, ml, stepped)


def sampled(fn: Callable[[float], float], t0: float, t1: float, n: int, dfn: Optional[Callable[[float], float]] = None) -> PP:
    """Sample a smooth function into n Hermite segments (slopes from dfn or central differences)."""
    n = max(1, int(n))
    t = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    v = [fn(x) for x in t]
    if dfn is None:
        d = (t1 - t0) / n * 1e-3
        m = [(fn(x + d) - fn(x - d)) / (2 * d) for x in t]
    else:
        m = [dfn(x) for x in t]
    return PP(t, v, m, m)


def oscillator(amp: float, period: float, t0: float, t1: float, phase: float = 0.0, bias: float = 0.0, per_period: int = 8) -> PP:
    """bias + amp*sin(2*pi*(t/period - phase)).  phase in cycles: 0.25 delays the wave by a quarter period."""
    w = 2 * math.pi / period
    f = lambda x: bias + amp * math.sin(w * x - 2 * math.pi * phase)
    df = lambda x: amp * w * math.cos(w * x - 2 * math.pi * phase)
    n = max(2, int(math.ceil((t1 - t0) / period * per_period)))
    return sampled(f, t0, t1, n, df)


def total(layers: Iterable[PP], base: float = 0.0, extra_knots: Iterable[float] = ()) -> PP:
    """Exact sum of layers at the union of their knots (plus `base`)."""
    layers = list(layers)
    knots = sorted({round(x, 6) for L in layers for x in L.t} | {round(x, 6) for x in extra_knots})
    if not knots:
        knots = [0.0]
    v = [base + sum(L.value(x) for L in layers) for x in knots]
    mr = [sum(L.slope(x, "right") for L in layers) for x in knots]
    ml = [sum(L.slope(x, "left") for L in layers) for x in knots]
    stepped = [False] * len(knots)
    if len(layers) == 1 and any(layers[0].stepped):
        for i, x in enumerate(knots[:-1]):
            stepped[i] = layers[0].stepped[layers[0]._seg(x + EPS)]
    return PP(knots, v, mr, ml, stepped)


def r(x: float, nd: int = 4) -> float:
    y = round(float(x), nd)
    return int(y) if y == int(y) else y


def segment_curve(pp: PP, i: int) -> Optional[object]:
    """Spine 4.2 curve for the segment leaving knot i: None (linear), 'stepped', or [cx1, cy1, cx2, cy2]."""
    if pp.stepped[i]:
        return "stepped"
    t0, t1, v0, v1 = pp.t[i], pp.t[i + 1], pp.v[i], pp.v[i + 1]
    h = t1 - t0
    s = (v1 - v0) / h
    scale = max(1e-6, abs(v1 - v0), abs(pp.mr[i] * h), abs(pp.ml[i + 1] * h))
    if abs(pp.mr[i] - s) * h < 1e-4 * scale + 1e-7 and abs(pp.ml[i + 1] - s) * h < 1e-4 * scale + 1e-7:
        return None
    return [r(t0 + h / 3), r(v0 + pp.mr[i] * h / 3), r(t1 - h / 3), r(v1 - pp.ml[i + 1] * h / 3)]


def is_static(pp: PP, neutral: float) -> bool:
    return all(abs(x - neutral) < 1e-6 for x in pp.v) and all(abs(m) < 1e-6 for m in pp.mr + pp.ml)


def export_1(pp: PP, value_key: str = "value", default: float = 0.0) -> List[dict]:
    out = []
    for i, x in enumerate(pp.t):
        k = {}
        if x:
            k["time"] = r(x)
        if abs(pp.v[i] - default) > 1e-9:
            k[value_key] = r(pp.v[i])
        if i < len(pp.t) - 1:
            c = segment_curve(pp, i)
            if c is not None:
                k["curve"] = c
        out.append(k)
    return out


def export_2(a: PP, b: PP, names=("x", "y"), default: float = 0.0) -> List[dict]:
    """Two-component timeline (translate/scale/shear).  a and b must share knots (use `total(..., extra_knots=)`)."""
    assert a.t == b.t, "components must share knots"
    out = []
    for i, x in enumerate(a.t):
        k = {}
        if x:
            k["time"] = r(x)
        for pp, nm in ((a, names[0]), (b, names[1])):
            if abs(pp.v[i] - default) > 1e-9:
                k[nm] = r(pp.v[i])
        if i < len(a.t) - 1:
            ca, cb = segment_curve(a, i), segment_curve(b, i)
            if ca == "stepped" or cb == "stepped":
                k["curve"] = "stepped"
            elif ca is not None or cb is not None:
                def lin(pp):
                    h = pp.t[i + 1] - pp.t[i]
                    return [r(pp.t[i] + h / 3), r(pp.v[i] + (pp.v[i + 1] - pp.v[i]) / 3), r(pp.t[i + 1] - h / 3), r(pp.v[i + 1] - (pp.v[i + 1] - pp.v[i]) / 3)]
                k["curve"] = (ca or lin(a)) + (cb or lin(b))
        out.append(k)
    return out
