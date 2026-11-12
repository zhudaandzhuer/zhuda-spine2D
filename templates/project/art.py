#!/usr/bin/env python3
"""__NAME__ -- layered art in code.  `spk art` runs this file and cuts one PNG per art.part().

Rules that keep the rig honest:
  * order of art.part() calls = draw order, back to front
  * draw every part COMPLETE, including what other parts cover (hidden pixels appear the moment a bone moves)
  * coordinates are canvas pixels (x right, y down) -- the same numbers rig.py uses for pivots
  * alternates for one slot (mouth shapes, hand poses) get hidden=True except the setup one

Replace the starter creature below with your character.  If your art comes from an image model or a
painter instead, delete this file and provide parts/*.png + parts/manifest.json (see docs/10-art.md).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:                                                               # `spk art` puts the kit on PYTHONPATH
    from spinekit.svgart import Art, smooth, ribbon, path, circle, ellipse, group
except ImportError:
    sys.exit("run this through the kit:  python3 <kit>/spk.py art <project>")

W, H = 600, 700


def build() -> Art:
    art = Art(W, H)
    soft = art.blur(6)
    # tail (behind the body)
    art.part("tail", path(ribbon([(380, 520), (440, 500), (490, 450), (510, 390), (500, 340)], [46, 44, 38, 30, 0]), fill="#e9a25a", stroke="#8a5a2b", sw=3))
    # body
    body = smooth([(300, 330), (380, 360), (410, 470), (390, 590), (300, 620), (210, 590), (190, 470), (220, 360)])
    art.part("body", path(body, fill="#f2b56b", stroke="#8a5a2b", sw=3), group(ellipse(300, 500, 70, 80, fill="#fbe3bf"), clip_path=art.clip(body)))
    # ears (behind the head)
    for s, x in (("L", 215), ("R", 385)):
        art.part(f"ear_{s}", path(smooth([(x - 34, 190), (x, 70), (x + 34, 190)], tension=0.2), fill="#f2b56b", stroke="#8a5a2b", sw=3),
                 path(smooth([(x - 16, 180), (x, 104), (x + 16, 180)], tension=0.2), fill="#f6c9c0"))
    # head
    head = smooth([(300, 120), (400, 160), (430, 250), (390, 330), (300, 352), (210, 330), (170, 250), (200, 160)])
    art.part("head", path(head, fill="#f2b56b", stroke="#8a5a2b", sw=3),
             group(ellipse(300, 300, 80, 46, fill="#fbe3bf"), ellipse(300, 150, 90, 30, fill="#ffffff", opacity=0.25, filter=soft), clip_path=art.clip(head)),
             path(smooth([(286, 286), (300, 296), (314, 286)], closed=False), stroke="#5b3a1c", sw=4), ellipse(300, 276, 12, 8, fill="#5b3a1c"))
    # eyes: open (setup) and closed (alternate attachment in the same slot)
    for s, x in (("L", 250), ("R", 350)):
        art.part(f"eye_{s}_open", circle(x, 236, 15, fill="#2b1d12"), circle(x - 5, 230, 5, fill="#ffffff"))
        art.part(f"eye_{s}_closed", path(smooth([(x - 15, 236), (x, 244), (x + 15, 236)], closed=False), stroke="#2b1d12", sw=5), hidden=True)
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "art" / "character.svg"))
    a = ap.parse_args()
    build().save(a.out)
    print(a.out)
