"""Procedural layered art as SVG.

An `Art` is a canvas of named parts.  Each part becomes one transparent PNG (`spk art`), and the order
parts are added is the draw order, back to front.  Draw every part COMPLETE -- including the area other
parts will cover (shoulder under the hair, neck under the chin): hidden pixels are what a rig reveals
the moment something moves.

All coordinates are canvas pixels, x right, y down -- the same numbers rig.py uses for bone pivots.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

Pt = Tuple[float, float]


def f(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def smooth(pts: Sequence[Pt], closed: bool = True, tension: float = 0.5) -> str:
    """Path through all points with Catmull-Rom smoothing (tension 0 = polygon, 0.5 = natural)."""
    n = len(pts)
    if n < 2:
        raise ValueError("need at least 2 points")
    get = (lambda i: pts[i % n]) if closed else (lambda i: pts[max(0, min(n - 1, i))])
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    if closed:
        d.append("Z")
    return "".join(d)


def poly(pts: Sequence[Pt], closed: bool = True) -> str:
    return "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + ("Z" if closed else "")


def mirror(pts: Sequence[Pt], cx: float) -> List[Pt]:
    """Mirror points across the vertical line x = cx (order reversed so winding is preserved)."""
    return [(2 * cx - x, y) for x, y in reversed(pts)]


def shift(pts: Sequence[Pt], dx: float = 0, dy: float = 0) -> List[Pt]:
    return [(x + dx, y + dy) for x, y in pts]


def ribbon(center: Sequence[Pt], widths: Sequence[float], tension: float = 0.5) -> str:
    """Closed tapering shape around a centre line: widths[i] is the full width at center[i] (0 = pointed)."""
    import math
    left, right = [], []
    n = len(center)
    for i, (x, y) in enumerate(center):
        x0, y0 = center[max(0, i - 1)]
        x1, y1 = center[min(n - 1, i + 1)]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        w = widths[i] / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return smooth(left + right[::-1], closed=True, tension=tension)


def attrs(**kw) -> str:
    out = []
    for k, v in kw.items():
        if v is None or v is False:
            continue
        out.append(f'{k.rstrip("_").replace("_", "-")}="{f(v) if isinstance(v, (int, float)) else v}"')
    return " ".join(out)


def path(d: str, fill: str = "none", stroke: Optional[str] = None, sw: Optional[float] = None, opacity: Optional[float] = None, **kw) -> str:
    return f'<path d="{d}" {attrs(fill=fill, stroke=stroke, stroke_width=sw, opacity=opacity, stroke_linecap="round" if stroke else None, stroke_linejoin="round" if stroke else None, **kw)}/>'


def circle(cx, cy, r, fill="none", **kw) -> str:
    return f"<circle {attrs(cx=cx, cy=cy, r=r, fill=fill, **kw)}/>"


def ellipse(cx, cy, rx, ry, fill="none", **kw) -> str:
    return f"<ellipse {attrs(cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, **kw)}/>"


def group(*content: str, **kw) -> str:
    return f"<g {attrs(**kw)}>" + "".join(content) + "</g>"


class Art:
    def __init__(self, width: int, height: int):
        self.w, self.h = int(width), int(height)
        self._defs: List[str] = []
        self._parts: List[Tuple[str, str, bool]] = []
        self._n = 0

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    # ---- paint servers / effects ---------------------------------------------------------------
    def linear(self, x1, y1, x2, y2, stops: Iterable[tuple]) -> str:
        """stops: (offset 0..1, color[, opacity]).  Coordinates are canvas pixels."""
        i = self._id("lg")
        s = "".join(f'<stop offset="{f(o[0])}" stop-color="{o[1]}"' + (f' stop-opacity="{f(o[2])}"' if len(o) > 2 else "") + "/>" for o in stops)
        self._defs.append(f'<linearGradient id="{i}" gradientUnits="userSpaceOnUse" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}">{s}</linearGradient>')
        return f"url(#{i})"

    def radial(self, cx, cy, r, stops: Iterable[tuple], fx=None, fy=None, transform: Optional[str] = None) -> str:
        i = self._id("rg")
        s = "".join(f'<stop offset="{f(o[0])}" stop-color="{o[1]}"' + (f' stop-opacity="{f(o[2])}"' if len(o) > 2 else "") + "/>" for o in stops)
        extra = (f' fx="{f(fx)}" fy="{f(fy)}"' if fx is not None else "") + (f' gradientTransform="{transform}"' if transform else "")
        self._defs.append(f'<radialGradient id="{i}" gradientUnits="userSpaceOnUse" cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"{extra}>{s}</radialGradient>')
        return f"url(#{i})"

    def blur(self, std: float) -> str:
        i = self._id("bl")
        self._defs.append(f'<filter id="{i}" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="{f(std)}"/></filter>')
        return f"url(#{i})"

    def clip(self, d: str, rule: str = "nonzero") -> str:
        i = self._id("cp")
        self._defs.append(f'<clipPath id="{i}"><path d="{d}" clip-rule="{rule}"/></clipPath>')
        return f"url(#{i})"

    def mask_fade(self, x1, y1, x2, y2, stops: Iterable[tuple]) -> str:
        """Luminance mask from a linear gradient (white = visible): use to feather a part's edge."""
        g = self.linear(x1, y1, x2, y2, stops)
        i = self._id("mk")
        self._defs.append(f'<mask id="{i}" maskUnits="userSpaceOnUse" x="0" y="0" width="{self.w}" height="{self.h}"><rect x="0" y="0" width="{self.w}" height="{self.h}" fill="{g}"/></mask>')
        return f"url(#{i})"

    # ---- parts ---------------------------------------------------------------------------------
    def part(self, name: str, *content: str, hidden: bool = False, pad: int = 2):
        """Add a part (drawn above all earlier parts).  hidden=True: an alternate attachment, not shown in the setup key art.
        pad: transparent margin (px) kept around the part's pixels when it is cut out."""
        if any(q[0] == name for q in self._parts):
            raise ValueError(f"duplicate part '{name}'")
        self._parts.append((name, "".join(content), hidden, int(pad)))

    def svg(self) -> str:
        body = "".join('<g data-part="%s" data-pad="%d"%s>%s</g>' % (n, pd, ' data-hidden="1"' if h else "", c) for n, c, h, pd in self._parts)
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}"><defs>{"".join(self._defs)}</defs>{body}</svg>'

    def save(self, path) -> None:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.svg(), encoding="utf-8")
