#!/usr/bin/env python3
"""White model "vtuber" -- every part image (all eight views of the view parts) drawn by spinekit.figure3d."""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    from spinekit.svgart import Art
    from spinekit import figure3d as F
except ImportError:
    sys.exit("run this through the kit:  python3 <kit>/spk.py art <project>")

PRESET, W, H, ORIGIN = "vtuber", 760, 840, (380, 770)


def build() -> Art:
    art = Art(W, H)
    F.draw(art, F.Body(PRESET), ORIGIN)
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "art" / "character.svg"))
    a = ap.parse_args()
    build().save(a.out)
    print(a.out)
