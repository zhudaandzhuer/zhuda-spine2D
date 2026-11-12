"""Review images: contact sheets, before/after pairs, part sheets, gifs.

These only arrange native captures so they can be looked at; nothing here renders the character.
Frames are never stretched: every tile keeps the capture's aspect ratio.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BGS = {"dark": (27, 36, 48), "light": (233, 237, 242), "green": (63, 111, 90), "mid": (120, 128, 138)}


def _font(size=13):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _bg(name):
    if isinstance(name, tuple):
        return name
    if name in BGS:
        return BGS[name]
    if isinstance(name, str) and name.startswith("#") and len(name) == 7:
        return tuple(int(name[i:i + 2], 16) for i in (1, 3, 5))
    return BGS["dark"]


def flatten(im: Image.Image, bg) -> Image.Image:
    base = Image.new("RGBA", im.size, _bg(bg) + (255,))
    return Image.alpha_composite(base, im.convert("RGBA")).convert("RGB")


def on_backgrounds(im: Image.Image, names=("dark", "light", "green"), width=420) -> Image.Image:
    """Same image on several backgrounds -- the quickest way to see edge contamination and holes."""
    s = width / im.width
    size = (width, max(1, round(im.height * s)))
    small = im.resize(size, Image.LANCZOS)
    out = Image.new("RGB", (size[0] * len(names), size[1]), (0, 0, 0))
    for i, n in enumerate(names):
        out.paste(flatten(small, n), (i * size[0], 0))
    return out


def compose_sheet(items: Sequence[Tuple[Path, str]], bg="dark", tile=280, cols=0) -> Image.Image:
    """items: [(png path, label)].  bg 'both' shows every frame on dark and light."""
    bgs = ["dark", "light"] if bg == "both" else [bg]
    tiles: List[Tuple[Image.Image, str]] = []
    for path, label in items:
        im = Image.open(path).convert("RGBA")
        s = tile / im.width
        im = im.resize((tile, max(1, round(im.height * s))), Image.LANCZOS)
        for b in bgs:
            tiles.append((flatten(im, b), label))
    if not tiles:
        raise ValueError("no frames")
    th = tiles[0][0].height
    label_h = 18
    if not cols:
        cols = min(len(tiles), max(1, 1680 // (tile + 4)))
        if bg == "both" and cols % 2:
            cols = max(2, cols - 1)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tile + 4) + 4, rows * (th + label_h + 4) + 4), (12, 16, 22))
    d = ImageDraw.Draw(sheet)
    f = _font(13)
    for i, (im, label) in enumerate(tiles):
        x, y = 4 + (i % cols) * (tile + 4), 4 + (i // cols) * (th + label_h + 4)
        sheet.paste(im, (x, y + label_h))
        d.text((x + 3, y + 2), label[: max(8, tile // 7)], fill=(225, 232, 240), font=f)
    return sheet


def compose_pairs(a: Sequence[Tuple[Path, str]], b: Sequence[Tuple[Path, str]], name_a: str, name_b: str, bg="dark", tile=300):
    """Before | after | difference heat-map, one row per sample.  Returns (image, metrics)."""
    rows, metrics = [], []
    for (pa, label), (pb, _) in zip(a, b):
        ia, ib = Image.open(pa).convert("RGBA"), Image.open(pb).convert("RGBA")
        if ia.size != ib.size:
            raise ValueError("captures differ in size; compare needs identical camera/size")
        diff = np.abs(np.asarray(ia).astype(int) - np.asarray(ib).astype(int)).max(axis=2)
        ys, xs = np.nonzero(diff > 24)
        box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
        metrics.append({"sample": label, "max_diff": int(diff.max()), "changed_px": int((diff > 24).sum()), "changed_fraction": round(float((diff > 24).mean()), 5), "bbox": box})
        heat = Image.fromarray(np.clip(diff * 3, 0, 255).astype(np.uint8), "L")
        heat = Image.merge("RGB", (heat, Image.new("L", heat.size, 0), Image.eval(heat, lambda v: 255 - v if v > 0 else 0)))
        s = tile / ia.width
        size = (tile, max(1, round(ia.height * s)))
        rows.append((flatten(ia.resize(size, Image.LANCZOS), bg), flatten(ib.resize(size, Image.LANCZOS), bg), heat.resize(size, Image.LANCZOS), label))
    th = rows[0][0].height
    label_h = 18
    sheet = Image.new("RGB", (3 * (tile + 4) + 4, len(rows) * (th + label_h + 4) + 4), (12, 16, 22))
    d = ImageDraw.Draw(sheet)
    f = _font(13)
    for r, (ia, ib, heat, label) in enumerate(rows):
        y = 4 + r * (th + label_h + 4)
        for c, (im, cap) in enumerate(((ia, f"{name_a}  {label}"), (ib, f"{name_b}  {label}"), (heat, "difference"))):
            x = 4 + c * (tile + 4)
            sheet.paste(im, (x, y + label_h))
            d.text((x + 3, y + 2), cap[: tile // 7], fill=(225, 232, 240), font=f)
    return sheet, metrics


def parts_sheet(root: Path, manifest: dict, tile=150, cols=8) -> Image.Image:
    """Every part on a mid-grey checker at a common scale cap, with its name: shows stray pixels and missing underpaint."""
    parts = manifest["parts"]
    rows = (len(parts) + cols - 1) // cols
    label_h = 16
    sheet = Image.new("RGB", (cols * (tile + 4) + 4, rows * (tile + label_h + 4) + 4), (12, 16, 22))
    d = ImageDraw.Draw(sheet)
    f = _font(11)
    for i, p in enumerate(parts):
        im = Image.open(root / "parts" / p["file"]).convert("RGBA")
        s = min(tile / im.width, tile / im.height, 1.5)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        cell = Image.new("RGBA", (tile, tile), (0, 0, 0, 255))
        cd = ImageDraw.Draw(cell)
        for yy in range(0, tile, 15):
            for xx in range(0, tile, 15):
                cd.rectangle((xx, yy, xx + 14, yy + 14), fill=(96, 104, 114, 255) if (xx // 15 + yy // 15) % 2 else (132, 140, 150, 255))
        cell.alpha_composite(im, ((tile - im.width) // 2, (tile - im.height) // 2))
        x, y = 4 + (i % cols) * (tile + 4), 4 + (i // cols) * (tile + label_h + 4)
        sheet.paste(cell.convert("RGB"), (x, y + label_h))
        d.text((x + 2, y + 1), p["name"][:22], fill=(225, 232, 240), font=f)
    return sheet


def flatten_frames(frames: Sequence[Path], out: Path, bg="dark"):
    out.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(frames):
        flatten(Image.open(f), bg).save(out / f"f-{i:04d}.png")


def write_gif(frames: Sequence[Path], dest: Path, fps: int, bg="dark", width=360):
    ims = []
    for f in frames:
        im = flatten(Image.open(f), bg)
        s = width / im.width
        ims.append(im.resize((width, max(1, round(im.height * s))), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE, colors=128))
    dest.parent.mkdir(parents=True, exist_ok=True)
    ims[0].save(dest, save_all=True, append_images=ims[1:], duration=round(1000 / fps), loop=0, optimize=False)
