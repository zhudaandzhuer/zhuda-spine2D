"""Paint the Zhuda skin for the given white models.   python3 -I run.py hero heroine ..."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zhuda_skin import (GEN, cut_sheet, ear_part, fitted_part, flat_part, load_materials, mapped_part, mirror, paint, ribbon_part)  # noqa: E402

VIEW = re.compile(r"^(.*)_v(\d)$")
# fraction of the head art that is "the head ball" (ears stick out above, snout to the right in profile)
HEAD_CORE = {0: (0.04, 0.17, 0.96, 1.0), 1: (0.02, 0.17, 0.90, 1.0), 2: (0.0, 0.15, 0.86, 1.0),
             3: (0.02, 0.17, 0.95, 1.0), 4: (0.02, 0.17, 0.98, 1.0)}


def views(arts5):
    """art for v0..v7 (v5..v7 = mirrored v3..v1)"""
    return arts5 + [mirror(arts5[3]), mirror(arts5[2]), mirror(arts5[1])]


def src_view(v):
    return [0, 1, 2, 3, 4, 3, 2, 1][v]


def load_sheets():
    S = {}
    S["head"] = views(cut_sheet(GEN / "head_turn_01.png", 5))
    from zhuda_skin import tint
    S["torso"] = views([tint(t, (250, 175, 174), (250, 200, 199)) for t in cut_sheet(GEN / "torso_turn_01.png", 5)])
    for name, n in (("torso_overalls", 5), ("torso_hoodie", 5), ("torso_stripe", 5), ("torso_armor", 5), ("torso_robe", 5),
                    ("head_beanie", 5), ("head_helmet", 5), ("head_bald", 5), ("shield", 5)):
        p = GEN / f"{name}_01.png"
        if p.is_file():
            S[name] = views(cut_sheet(p, n))
    return S


def body_recipe(model, torso="torso", head="head", limb="skin", leg="skin", extras=None):
    extras = extras or {}

    def r(n, a, M, S):
        if n in extras:
            return extras[n](n, a, M, S)
        m = VIEW.match(n)
        if m:
            part, v = m.group(1), int(m.group(2))
            if part == "head":
                return fitted_part(model, n, S[head][v], core=HEAD_CORE[src_view(v)] if not (v >= 5) else mirror_core(HEAD_CORE[src_view(v)]))
            if part == "chest":
                return mapped_part(model, n, S[torso][v], (0, 0.0, 1, 0.64), under=M["skin"] if torso == "torso" else None, pad=0.0, line=torso != "torso")
            if part == "pelvis":
                return mapped_part(model, n, S[torso][v], (0, 0.40, 1, 1.0), under=M["skin"] if torso == "torso" else None, line=torso != "torso")
            if part.startswith("foot"):
                return flat_part(model, n, M["hoof"])
            if part == "shield":
                return extras_missing(n)
        if n == "waist":
            return flat_part(model, n, M[WAIST.get(torso, "skin")], line=False, shade_amount=SKIN_SHADE)
        if n.startswith(("hand_",)):
            return flat_part(model, n, M["hoof"])
        if n.startswith(("upperarm", "forearm", "elbow", "shoulder", "wrist")):
            return flat_part(model, n, M[limb], line=limb != "skin", shade_amount=0.16 if limb != "skin" else SKIN_SHADE)
        if n.startswith(("thigh", "shin", "knee", "hip", "ankle")):
            return flat_part(model, n, M[leg], line=leg != "skin", shade_amount=0.16 if leg != "skin" else SKIN_SHADE)
        if n == "neck":
            return flat_part(model, n, M["skin"], line=False, shade_amount=SKIN_SHADE)
        raise SystemExit(f"{model}: no recipe for {n}")
    return r


def mirror_core(c):
    x0, y0, x1, y1 = c
    return (1 - x1, y0, 1 - x0, y1)


def extras_missing(n):
    raise SystemExit(f"no art for {n}")


def mat(name):
    return lambda n, a, M, S: flat_part(MODEL, n, M[name])


RECIPES = {}
SKIN_SHADE = 0.04          # bare skin limbs: almost flat, so balls and tubes read as one limb
WAIST = {"torso": "skin", "torso_overalls": "denim", "torso_hoodie": "hoodie", "torso_stripe": "stripe", "torso_armor": "red", "torso_robe": "velvet"}


def hero():
    ex = {n: mat("knit") for n in ["scarf_1", "scarf_2", "scarf_3", "scarf_j1", "scarf_j2", "scarf_j3"]}
    return body_recipe("hero", extras=ex)


RECIPES["hero"] = hero


def heroine():
    ex = {n: (lambda n, a, M, S: ribbon_part("heroine", n, M["red"])) for n in ["ponytail_1", "ponytail_2", "ponytail_3"]}
    ex.update({n: mat("red") for n in ["ponytail_j1", "ponytail_j2", "ponytail_j3"]})
    ex["skirt_1"] = mat("denim")
    return body_recipe("heroine", torso="torso_overalls", extras=ex)


def chibi():
    ex = {n: mat("pinkknit") for n in ["pigtail_L_1", "pigtail_L_2", "pigtail_R_1", "pigtail_R_2", "pigtail_L_j1", "pigtail_L_j2", "pigtail_R_j1", "pigtail_R_j2"]}
    return body_recipe("chibi", torso="torso_hoodie", head="head_beanie", limb="hoodie", extras=ex)


def brute():
    from zhuda_skin import cloth_rect
    ex = {"cape_1": lambda n, a, M, S: cloth_rect(MODEL, n, M["capered"]),
          "cape_2": lambda n, a, M, S: cloth_rect(MODEL, n, M["capered"]), "club": mat("wood"), "club_cap": mat("wood")}
    return body_recipe("brute", torso="torso_stripe", limb="stripe", leg="denim", extras=ex)


def head_crop(S, v, box):
    """part of the Zhuda head art (front view), keeping only what differs from the bare skin (ear / snout)"""
    art = S["head"][v]
    W, H = art.size
    return art.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)))


def mascot():
    ex = {n: mat("skin") for n in ["tail_1", "tail_2", "tail_j1", "tail_j2"]}
    ex["bag"] = mat("brownleather")
    ex["bag_strap"] = mat("brownleather")
    ex["snout"] = lambda n, a, M, S: mapped_part("mascot", n, head_crop(S, 0, (0.31, 0.45, 0.67, 0.73)), under=M["skin"])
    ex["ear_L"] = lambda n, a, M, S: ear_part("mascot", n, M)
    ex["ear_R"] = lambda n, a, M, S: ear_part("mascot", n, M)
    return body_recipe("mascot", head="head_bald", extras=ex)


def knight():
    ex = {n: mat("red") for n in ["plume_1", "plume_2", "plume_j1", "plume_j2"]}
    ex.update({"pauldron_L": mat("steel"), "pauldron_R": mat("steel"), "sword": mat("steel"), "sword_guard": mat("gold")})
    for v in range(8):
        ex[f"shield_v{v}"] = (lambda v: lambda n, a, M, S: fitted_part("knight", n, S["shield"][v], target=0.99))(v)
    return body_recipe("knight", torso="torso_armor", head="head_helmet", limb="steel", leg="steel", extras=ex)


def mage():
    ex = {n: mat("velvet") for n in ["robe_1", "sleeve_L", "sleeve_R", "hat_brim", "hat_1", "hat_2", "hat_j1", "hat_j2"]}
    ex.update({"staff": mat("wood"), "staff_cap": mat("gold")})
    return body_recipe("mage", torso="torso_robe", extras=ex)


# ---------------------------------------------------------------- vtuber: face parts on a front head
from PIL import Image, ImageDraw  # noqa: E402
import numpy as np  # noqa: E402
from zhuda_skin import SCALE, template, up, outline_rgba, shade_from_template  # noqa: E402

BROWN = (92, 52, 40, 255)
BEAD = (40, 26, 24, 255)


def canvas_of(model, n):
    t = up(template(model, n))
    a = np.asarray(t)[..., 3] > 40
    ys, xs = np.where(a)
    return Image.new("RGBA", t.size, (0, 0, 0, 0)), (xs.min(), ys.min(), xs.max(), ys.max())


def eye(n, kind):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = 5 * SCALE, 6 * SCALE
    if kind == "open":
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=BEAD)
    elif kind == "half":
        d.chord((cx - rx, cy - ry, cx + rx, cy + ry), 0, 180, fill=BEAD)
    else:
        d.arc((cx - rx - 2, cy - ry, cx + rx + 2, cy + ry), 20, 160, fill=BROWN, width=2 * SCALE)
    return im


def iris(n):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy = (x0 + x1) / 2 - 1.5 * SCALE, (y0 + y1) / 2 - 2 * SCALE
    r = 2.2 * SCALE
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
    return im


def mouth(n):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    if n == "mouth_closed":
        d.arc((cx - w * 0.35, cy - h * 1.2, cx + w * 0.35, cy + h * 0.5), 30, 150, fill=BROWN, width=int(1.6 * SCALE))
    elif n == "mouth_smile":
        d.arc((cx - w * 0.45, cy - h * 1.3, cx + w * 0.45, cy + h * 0.55), 20, 160, fill=BROWN, width=int(1.8 * SCALE))
    else:
        k = {"mouth_open1": 0.55, "mouth_open2": 0.8, "mouth_open3": 1.0}[n]
        box = (cx - w * 0.42, cy - h * 0.5 * k, cx + w * 0.42, cy + h * 0.5 * k)
        d.ellipse(box, fill=(150, 52, 58, 255), outline=BROWN, width=SCALE)
        d.ellipse((cx - w * 0.22, cy, cx + w * 0.22, cy + h * 0.42 * k), fill=(240, 130, 140, 255))
    return im


def brow(n):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy, w = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0
    d.line((cx - w * 0.3, cy + SCALE, cx + w * 0.3, cy - SCALE), fill=BROWN, width=int(2 * SCALE))
    return im


def blob(n, rgb, frac=0.85):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * frac, (y1 - y0) * frac
    d.ellipse((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), fill=rgb + (255,))
    return im


def nostrils(n):
    im, (x0, y0, x1, y1) = canvas_of("vtuber", n)
    d = ImageDraw.Draw(im)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for sx in (-1, 1):
        x = cx + sx * 4.2 * SCALE
        d.ellipse((x - 2 * SCALE, cy - 3 * SCALE, x + 2 * SCALE, cy + 3 * SCALE), fill=(110, 50, 52, 255))
    return im


def setup_boxes(model):
    """world boxes of the region attachments in the setup pose (spine-core, via the kit's node_modules)"""
    import glob, json, os, shutil, subprocess
    from zhuda_skin import ROOT, KIT
    b = sorted(glob.glob(str(ROOT / model / "build" / "*" / f"{model}.json")))[-1]
    tool = KIT / "tools" / "_zhuda_boxes.mjs"
    shutil.copy(Path(__file__).resolve().parent / "setup_boxes.mjs", tool)
    try:
        out = subprocess.run(["node", str(tool), b, b[:-5] + ".atlas"], capture_output=True, text=True, check=True).stdout
    finally:
        os.remove(tool)
    return json.loads(out)


def vt_head(n, a, M, S):
    """blank pink face + Zhuda's snout (under the nose part) and blush (beside it); positions read from the setup pose"""
    im = flat_part("vtuber", n, M["skin"], shade_amount=0.06)
    W, H = im.size
    bx = setup_boxes("vtuber")
    hd, nose, mouth = bx["head"], bx["nose"], bx["mouth"]
    eye = bx["eye_L"]
    top = hd["cy"] + hd["h"] / 2

    def at(wx, wy):
        return W / 2 + (wx - hd["cx"]) * SCALE, (top - wy) * SCALE
    d = ImageDraw.Draw(im)
    # snout between the eyes and the mouth, as wide as the eye spacing
    sy = (eye["cy"] + mouth["cy"]) / 2 - (eye["cy"] - mouth["cy"]) * 0.05
    rx = abs(eye["cx"] - bx["eye_R"]["cx"]) * 0.62
    ry = rx * 0.68
    cx, cy = at(nose["cx"], sy)
    d.ellipse((cx - rx * SCALE, cy - ry * SCALE, cx + rx * SCALE, cy + ry * SCALE), fill=(238, 136, 148, 255), outline=(140, 84, 72, 255), width=int(1.5 * SCALE))
    for side in (-1, 1):
        bcx, bcy = at(nose["cx"] + side * rx * 2.0, sy + ry * 0.1)
        r1, r2 = rx * 0.62 * SCALE, rx * 0.42 * SCALE
        d.ellipse((bcx - r1, bcy - r2, bcx + r1, bcy + r2), fill=(246, 160, 166, 255))
    return im


def vtuber():
    ex = {}
    for side in "LR":
        ex[f"eye_{side}_open"] = (lambda n, a, M, S: eye(n, "open"))
        ex[f"eye_{side}_half"] = (lambda n, a, M, S: eye(n, "half"))
        ex[f"eye_{side}_closed"] = (lambda n, a, M, S: eye(n, "closed"))
        ex[f"iris_{side}_on"] = (lambda n, a, M, S: iris(n))
        ex[f"brow_{side}"] = (lambda n, a, M, S: brow(n))
        ex[f"cheek_{side}"] = (lambda n, a, M, S: blob(n, (240, 120, 132)))
        ex[f"ear_{side}"] = mat("skin")
        ex[f"sidebang_{side}"] = (lambda n, a, M, S: ear_part("vtuber", n, M))
        for i in (1, 2, 3):
            ex[f"lock_{side}_{i}"] = (lambda n, a, M, S: ribbon_part("vtuber", n, M["knit"], 0.75))
    for m in ("mouth_closed", "mouth_smile", "mouth_open1", "mouth_open2", "mouth_open3"):
        ex[m] = (lambda n, a, M, S: mouth(n))
    ex["nose"] = lambda n, a, M, S: nostrils(n)
    ex["head"] = vt_head
    ex["hair_cap"] = mat("knit")
    ex["bangs"] = mat("knit")
    for i in (1, 2, 3):
        ex[f"hair_back_{i}"] = mat("knit")
    ex["skirt_1"] = mat("red")
    return body_recipe("vtuber", torso="torso_stripe", extras=ex)


RECIPES.update(vtuber=vtuber)
RECIPES.update(heroine=heroine, chibi=chibi, brute=brute, mascot=mascot, knight=knight, mage=mage)

if __name__ == "__main__":
    M = load_materials()
    S = load_sheets()
    for MODEL in sys.argv[1:]:
        out, rep = paint(MODEL, RECIPES[MODEL](), M, S)
        low = sorted(((v, k) for k, v in rep.items() if v is not None))[:5]
        print(MODEL, out, "lowest fitted cover:", low)
