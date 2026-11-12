"""Expression parts for Zhuda (front), drawn at canvas coordinates to match the key art's line weight and colours.
python3 face_parts.py  ->  gen/face/*.png (full canvas, true alpha)"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "gen" / "face"
W, H = 1024, 1536
SS = 4                                   # supersample for clean anti-aliased strokes
BEAD = (34, 22, 22, 255)
LINE = (128, 50, 38, 255)                # mouth / brow stroke (sampled from the key art smile)
INNER = (150, 46, 52, 255)
TONGUE = (240, 128, 140, 255)
TEAR = (120, 190, 240, 255)
TEAR_LINE = (70, 130, 200, 255)
EYE = {"L": (301, 476), "R": (718, 476)}
MOUTH = (509, 744)
LW = 11                                  # stroke width of the key art's smile


def canvas():
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def S(*v):
    return [x * SS for x in v]


def save(im, name):
    im.resize((W, H), Image.LANCZOS).save(OUT / f"{name}.png")


def arc_points(cx, cy, rx, ry, a0, a1, n=40):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def stroke(d, pts, w=LW, fill=LINE):
    p = [(x * SS, y * SS) for x, y in pts]
    d.line(p, fill=fill, width=int(w * SS), joint="curve")
    r = w * SS / 2
    for x, y in (p[0], p[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def eyes(kind):
    for s, (cx, cy) in EYE.items():
        im, d = canvas()
        if kind == "closed":                       # blink: a gentle downward curve
            stroke(d, arc_points(cx, cy - 6, 30, 16, 200, 340), w=10)
        elif kind == "happy":                      # ^ ^
            stroke(d, arc_points(cx, cy + 14, 30, 26, 200, 340), w=10)
        elif kind == "wide":                       # surprised: bigger bead + highlight
            d.ellipse(S(cx - 40, cy - 42, cx + 40, cy + 42), fill=BEAD)
            d.ellipse(S(cx + 2, cy - 30, cx + 22, cy - 10), fill=(255, 255, 255, 255))
        elif kind == "sad":                        # lower half of the bead under a droopy lid line
            d.chord(S(cx - 33, cy - 30, cx + 33, cy + 36), 0, 180, fill=BEAD)
            stroke(d, [(cx - 36, cy + 2), (cx + 36, cy + 2)], w=8)
        elif kind == "cry":                        # > <
            sg = 1 if s == "L" else -1
            stroke(d, [(cx - 26 * sg, cy - 22), (cx + 22 * sg, cy), (cx - 26 * sg, cy + 22)], w=10)
        save(im, f"eye_{s}_{kind}")


def brows(kind):
    for s, (cx, cy) in EYE.items():
        sg = 1 if s == "L" else -1                 # +1 = screen-left eye (inner side is +x)
        im, d = canvas()
        y = cy - 62
        if kind == "angry":                        # inner end low
            pts = [(cx - 34 * sg, y - 14), (cx + 30 * sg, y + 10)]
        elif kind == "sad":                        # inner end high
            pts = [(cx - 34 * sg, y + 10), (cx + 30 * sg, y - 14)]
        elif kind == "up":                         # surprised / confused: raised arch
            pts = arc_points(cx, y - 4, 32, 12, 200, 340)
        else:                                      # soft (calm)
            pts = arc_points(cx, y + 6, 30, 10, 200, 340)
        stroke(d, pts, w=9)
        save(im, f"brow_{s}_{kind}")


def mouths():
    cx, cy = MOUTH
    shapes = {}
    im, d = canvas(); stroke(d, arc_points(cx, cy - 34, 64, 46, 25, 155)); shapes["smile"] = im
    im, d = canvas(); stroke(d, [(cx - 34, cy), (cx + 34, cy)], w=10); shapes["flat"] = im
    im, d = canvas(); stroke(d, arc_points(cx, cy + 34, 52, 30, 205, 335)); shapes["frown"] = im
    # laugh: open D shape with tongue
    im, d = canvas()
    poly = [(cx - 70, cy - 22)] + arc_points(cx, cy - 22, 70, 62, 0, 180)[::-1][::-1]
    d.polygon([(x * SS, y * SS) for x, y in arc_points(cx, cy - 22, 70, 62, 0, 180)], fill=INNER)
    d.chord(S(cx - 40, cy + 2, cx + 40, cy + 70), 180, 360, fill=TONGUE)
    d.chord(S(cx - 70, cy - 84, cx + 70, cy + 40), 0, 180, fill=None, outline=LINE, width=8 * SS)
    d.line(S(cx - 70, cy - 22, cx + 70, cy - 22), fill=LINE, width=8 * SS)
    shapes["laugh"] = im
    # talk: small and medium open ovals
    for name, rx, ry in (("open_s", 36, 22), ("open_m", 46, 38), ("o", 30, 34)):
        im, d = canvas()
        d.ellipse(S(cx - rx, cy - ry, cx + rx, cy + ry), fill=INNER, outline=LINE, width=7 * SS)
        if ry >= 26 and name != "o":
            d.chord(S(cx - rx * 0.6, cy, cx + rx * 0.6, cy + ry * 1.6), 180, 360, fill=TONGUE)
        shapes[name] = im
    # wail (crying): wide open frown
    im, d = canvas()
    pts = arc_points(cx, cy + 40, 60, 52, 200, 340)
    d.polygon([(x * SS, y * SS) for x, y in pts], fill=INNER, outline=LINE)
    stroke(d, pts + [pts[0]], w=8)
    shapes["wail"] = im
    for k, v in shapes.items():
        save(v, f"mouth_{k}")


def extras():
    im, d = canvas()                               # stronger blush for shy / laugh (opaque soft pink ovals)
    for cx in (236, 794):
        d.ellipse(S(cx - 74, 545, cx + 74, 640), fill=(244, 128, 140, 255))
        for i in range(3):                         # three little shy strokes
            x = cx - 30 + i * 30
            stroke(d, [(x + 6, 568), (x - 6, 606)], w=6, fill=(214, 92, 108, 255))
    save(im, "blush_shy")
    for s, (cx, cy) in EYE.items():                # tear stream under each eye
        im, d = canvas()
        top = cy + 34
        d.rounded_rectangle(S(cx - 14, top, cx + 14, top + 150), radius=14 * SS, fill=TEAR, outline=TEAR_LINE, width=4 * SS)
        save(im, f"tear_{s}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for k in ("closed", "happy", "wide", "sad", "cry"):
        eyes(k)
    for k in ("angry", "sad", "up", "soft"):
        brows(k)
    mouths()
    extras()
    print(sorted(p.name for p in OUT.glob("*.png")))
