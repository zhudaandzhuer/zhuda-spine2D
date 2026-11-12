"""Skins for white models: export the image templates, build a skin from replacement images, make a debug skin.

A skin never touches the skeleton or the animations.  It is a second atlas whose regions have the same names as the
white model's; the runtime loads `<name>.json` with the skin's `<name>.atlas` instead of the white one.

    template/                 one PNG per attachment (the white image, with its transparent margin) + skin.json + GUIDE.md
    skins/<skin>/             the replacement images you paint or generate, same file names
    build/NNN/skins/<skin>/   <name>.atlas + <name>.png + skin-report.json   (written by `spk reskin`)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .atlas import pack


class SkinError(Exception):
    pass


def load_spec(build_dir: Path) -> dict:
    fs = list(build_dir.glob("*.skin.json"))
    if len(fs) != 1:
        raise SkinError(f"{build_dir} has no skin specification (this build is not a white model)")
    return json.loads(fs[0].read_text(encoding="utf-8"))


GUIDE = """# 換皮說明（給負責產圖的人或 agent）

這個資料夾是白模「{name}」（{body_zh}）的**圖片模板**。換皮 = 為每一張模板準備一張同名的圖，放進 `skins/<皮名>/`，再跑 `spk reskin`。骨架與動畫完全不動。

## 規則

1. **檔名相同、長寬比相同。** 解析度可以是模板的整數倍（建議 2×），但每一張的倍數要一致。
2. **軸心不動。** 模板中白色形狀的位置就是零件的位置；你的圖要畫在同一個地方、同樣大小。模板四周的透明留白是給頭髮、衣襬、裝飾超出用的，可以畫進去，但不要把主體移開。
3. **白色形狀要蓋滿。** 關節靠「零件互相重疊」遮住；圖比白模瘦，轉動時會露縫。`spk reskin` 會回報每張圖的覆蓋率。
4. **不透明的實體、乾淨的透明邊。** 不要半透明柔邊、不要陰影、不要背景。
5. **視角零件有 8 張**（`_v0` … `_v7` = {views}）：同一個部位從八個方向看。`_v5/_v6/_v7` 若角色左右對稱，可以不提供，工具會用 `_v3/_v2/_v1` 水平翻轉；不對稱（側分瀏海、單邊飾品）就要自己畫。
6. **管狀肢段只有 1 張**，各角度共用：畫成大致圓柱對稱的袖子、褲管，不要畫只在單側才有的圖案。
7. 光線一律平光、正面打亮；不要畫投射陰影（遠側變暗是程式做的）。

## 檔案

`skin.json` 列出每一張：`attachment`（檔名）、`kind`、`view`／`yaw`、`size`、`pivot`（軸心在圖中的像素位置）、`zh`（說明）、`mirror_of`。
`template_sheet.png` 是全部模板的總覽。

## 流程

```sh
python3 spk.py reskin <專案> --skin <皮名>             # 驗證 + 打包；缺圖會列出來（--fill 用白模補缺，方便分批做）
python3 spk.py --skin <皮名> sheet <專案> --anim turntable --n 8      # 繞一圈看
python3 spk.py --skin <皮名> stress <專案>                              # 關鍵姿勢
python3 spk.py --skin <皮名> play <專案> --cues "idle@0;walk@0.5;turn@2;walk@3.5" --duration 5 --mp4 out.mp4
```

完整說明與驗收標準：工具包 `docs/38-reskin.md`。
"""


def _sheet(images: Dict[str, Image.Image], cols: int = 10, tile: int = 120) -> Image.Image:
    names = list(images)
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tile + 6) + 6, rows * (tile + 22) + 6), (40, 46, 56))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.load_default(size=11)
    except TypeError:
        f = ImageFont.load_default()
    for i, n in enumerate(names):
        im = images[n].convert("RGBA")
        im.thumbnail((tile, tile), Image.LANCZOS)
        x, y = 6 + (i % cols) * (tile + 6), 6 + (i // cols) * (tile + 22)
        bg = Image.new("RGBA", (tile, tile), (70, 80, 96, 255))
        bg.alpha_composite(im, ((tile - im.width) // 2, (tile - im.height) // 2))
        sheet.paste(bg.convert("RGB"), (x, y))
        d.text((x + 2, y + tile + 3), n[:18], fill=(225, 230, 238), font=f)
    return sheet


def export_template(root: Path, build_dir: Path, out: Path) -> dict:
    spec = load_spec(build_dir)
    tdir = out / "template"
    tdir.mkdir(parents=True, exist_ok=True)
    images = {}
    for a in spec["attachments"]:
        src = root / "parts" / a["file"]
        shutil.copy2(src, tdir / f"{a['attachment']}.png")
        images[a["attachment"]] = Image.open(src)
    (out / "skin.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "GUIDE.md").write_text(GUIDE.format(name=spec["name"], body_zh=spec.get("body_zh", ""), views="、".join(f"{c}（{spec['view_meaning'][c]}）" for c in spec["views"])), encoding="utf-8")
    _sheet(images).save(out / "template_sheet.png")
    return {"ok": True, "template": str(tdir), "images": len(images), "spec": str(out / "skin.json"), "guide": str(out / "GUIDE.md"), "sheet": str(out / "template_sheet.png"),
            "views_per_view_part": len(spec["views"]), "may_be_mirrored": sum(1 for a in spec["attachments"] if a.get("mirror_of"))}


HUES = [(232, 76, 61), (241, 148, 49), (241, 196, 15), (120, 200, 80), (46, 204, 173), (52, 152, 219), (125, 100, 220), (220, 90, 190)]


def make_debug_skin(root: Path, build_dir: Path, out: Path) -> dict:
    """A skin that makes mistakes visible: every view image is tinted by its direction and stamped with its code
    (F, FR, R ...), left-side parts are blue, right-side parts are red.  If the stamps you see do not match the way the
    figure faces, view switching is wrong; if a blue arm shows up on the figure's right, sides are wrong."""
    spec = load_spec(build_dir)
    out.mkdir(parents=True, exist_ok=True)
    for a in spec["attachments"]:
        im = Image.open(root / "parts" / a["file"]).convert("RGBA")
        arr = np.asarray(im).astype(np.float32)
        lum = arr[..., :3].mean(-1, keepdims=True) / 255.0
        n = a["attachment"]
        if a["kind"] == "view":
            col = HUES[spec["views"].index(a["view"])]
        elif n.endswith("_L") or "_L_" in n or n.rsplit("_", 1)[0].endswith("_L"):
            col = (70, 130, 235)
        elif n.endswith("_R") or "_R_" in n or n.rsplit("_", 1)[0].endswith("_R"):
            col = (235, 80, 80)
        elif a["kind"] == "shadow":
            col = None
        else:
            col = (150, 160, 175)
        if col is not None:
            arr[..., :3] = np.clip(np.array(col, np.float32) * (0.45 + 0.6 * lum), 0, 255)
        res = Image.fromarray(arr.astype(np.uint8), "RGBA")
        if a["kind"] == "view":
            d = ImageDraw.Draw(res)
            size = max(10, int(min(res.size) * 0.34))
            try:
                f = ImageFont.load_default(size=size)
            except TypeError:
                f = ImageFont.load_default()
            box = d.textbbox((0, 0), a["view"], font=f)
            px, py = a["pivot"]
            d.text((px - (box[2] - box[0]) / 2 - box[0], py - (box[3] - box[1]) / 2 - box[1]), a["view"], fill=(255, 255, 255, 255), font=f, stroke_width=2, stroke_fill=(20, 20, 30, 255))
            res.putalpha(im.getchannel("A"))                 # stamps stay inside the silhouette
        res.save(out / f"{n}.png")
    return {"ok": True, "skin_source": str(out), "images": len(spec["attachments"])}


def reskin(root: Path, build_dir: Path, skin: str, src: Path, fill: bool = False) -> dict:
    spec = load_spec(build_dir)
    name = spec["name"]
    if not src.is_dir():
        raise SkinError(f"skin source folder not found: {src}")
    images: Dict[str, Image.Image] = {}
    rows, errors, warnings, scales = [], [], [], []
    for a in spec["attachments"]:
        n = a["attachment"]
        tmpl = Image.open(root / "parts" / a["file"]).convert("RGBA")
        f = src / f"{n}.png"
        origin = "provided"
        if f.is_file():
            im = Image.open(f).convert("RGBA")
        elif a.get("mirror_of") and (src / f"{a['mirror_of']}.png").is_file():
            im, origin = ImageOps.mirror(Image.open(src / f"{a['mirror_of']}.png").convert("RGBA")), f"mirrored from {a['mirror_of']}"
        elif fill or a["kind"] == "shadow":
            im, origin = tmpl, "white template (not skinned)"
            if a["kind"] != "shadow":
                warnings.append(f"{n}: no image; kept the white template")
        else:
            errors.append(f"{n}: missing ({a.get('zh', '')}); expected {f.name}" + (f" or {a['mirror_of']}.png to mirror" if a.get("mirror_of") else ""))
            continue
        tw, th = tmpl.size
        rw, rh = im.width / tw, im.height / th
        if abs(rw - rh) / max(rw, 1e-6) > 0.03:
            errors.append(f"{n}: {im.size} does not keep the template's proportions {tmpl.size} (the pivot would move)")
            continue
        if rw < 0.5:
            warnings.append(f"{n}: only {rw:.2f}x the template resolution")
        ta = np.asarray(tmpl.getchannel("A").resize(im.size, Image.LANCZOS)) > 40
        sa = np.asarray(im.getchannel("A")) > 40
        cover = float((ta & sa).sum()) / max(1, int(ta.sum()))
        outside = float((sa & ~ta).sum()) / max(1, int(sa.sum()))
        border = np.concatenate([sa[0], sa[-1], sa[:, 0], sa[:, -1]])
        row = {"attachment": n, "origin": origin, "size": list(im.size), "scale": round(rw, 3), "covers_white_shape": round(cover, 3), "outside_white_shape": round(outside, 3), "touches_border": round(float(border.mean()), 3)}
        if origin != "white template (not skinned)":
            scales.append(rw)
            if not sa.any():
                errors.append(f"{n}: the image is fully transparent")
                continue
            if sa.all():
                warnings.append(f"{n}: no transparent pixels at all (background not removed?)")
            if cover < 0.6 and a["kind"] != "shadow":
                warnings.append(f"{n}: covers only {cover:.0%} of the white shape -- gaps will show at the joints")
            if border.mean() > 0.25:
                warnings.append(f"{n}: the art runs into the image border on {border.mean():.0%} of it (cut off?)")
        rows.append(row)
        images[n] = im
    if scales and max(scales) / min(scales) > 1.15:
        warnings.append(f"images use different resolutions ({min(scales):.2f}x to {max(scales):.2f}x): texel density will be uneven")
    report = {"ok": not errors, "skin": skin, "name": name, "errors": errors, "warnings": warnings, "attachments": rows,
              "provided": sum(1 for r in rows if r["origin"] == "provided"), "mirrored": sum(1 for r in rows if r["origin"].startswith("mirrored")), "kept_white": sum(1 for r in rows if r["origin"].startswith("white"))}
    if errors:
        return report
    out = build_dir / "skins" / skin
    out.mkdir(parents=True, exist_ok=True)
    page, atlas_text, _ = pack(images, f"{name}.png", padding=4, bleed=6)
    page.save(out / f"{name}.png")
    (out / f"{name}.atlas").write_text(atlas_text, encoding="utf-8")
    # the skin folder is a complete runtime set: the same skeleton + contract next to the new atlas (hard links when possible)
    import os
    for f in (f"{name}.json", f"{name}.contract.json", f"{name}.stress.json"):
        srcf, dst = build_dir / f, out / f
        if not srcf.is_file():
            continue
        if dst.exists():
            dst.unlink()
        try:
            os.link(srcf, dst)
        except OSError:
            shutil.copy2(srcf, dst)
    report.update(atlas=str(out / f"{name}.atlas"), page=str(out / f"{name}.png"), page_size=list(page.size))
    (out / "skin-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
