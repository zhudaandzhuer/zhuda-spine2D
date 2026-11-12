#!/usr/bin/env python3
"""Round-trip test of the image-layers path with synthetic stand-ins for generated images.

Takes a finished project (default examples/shuang), re-renders every part as a "generated" full-canvas picture
on a chroma background with a few pixels of drift (and 1% scale drift on two of them), cuts a few small parts
straight out of the flattened key art by polygon, then runs  spk layers -> build -> fidelity -> check  with the
original rig.py.  It proves keying, registration, cutting and the manifest are compatible with the compiler.

It does NOT prove that an image model will give you consistent layers: these stand-ins are perfectly consistent.
"""
import argparse, json, random, shutil, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
from PIL import Image

KIT = Path(__file__).resolve().parents[1]
GREEN = (0, 255, 0)


def spk(*a):
    r = subprocess.run([sys.executable, str(KIT / "spk.py"), *map(str, a)], capture_output=True, text=True)
    try:
        return r, json.loads(r.stdout)
    except Exception:
        return r, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(KIT / "examples" / "shuang"))
    ap.add_argument("--keep")
    a = ap.parse_args()
    src = Path(a.source)
    out = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="spk-layers-"))
    if out.exists() and any(out.iterdir()):
        shutil.rmtree(out)
    (out / "gen").mkdir(parents=True)
    man = json.loads((src / "parts" / "manifest.json").read_text())
    W, H = man["canvas"]
    rng = random.Random(7)
    on_green = lambda rgba: Image.alpha_composite(Image.new("RGBA", (W, H), GREEN + (255,)), rgba).convert("RGB")
    Image.open(src / "parts" / "keyart.png").convert("RGBA")
    on_green(Image.open(src / "parts" / "keyart.png").convert("RGBA")).save(out / "gen" / "keyart.png")
    cut_from_key = {"nose", "brow_L", "brow_R", "mouth_neutral"}   # small details fully visible in the key art -> polygon cut
    spec = {"canvas": [W, H], "keyart": "gen/keyart.png", "background": "auto", "defaults": {"despeckle": 0}, "parts": []}
    applied = {}
    for i, p in enumerate(man["parts"]):
        name = p["name"]
        if name in cut_from_key:
            m = 3
            x0, y0, x1, y1 = p["x"] - m, p["y"] - m, p["x"] + p["w"] + m, p["y"] + p["h"] + m
            spec["parts"].append({"name": name, "source": "keyart", "polygon": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "feather": 0})
            continue
        im = Image.open(src / "parts" / p["file"]).convert("RGBA")
        big = p["w"] * p["h"] > 40000
        dx, dy = (rng.randint(-7, 7), rng.randint(-7, 7)) if big and not p.get("hidden") else (0, 0)
        scale = 1.01 if name in ("hair_back", "torso") else 1.0
        if scale != 1.0:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        cx, cy = p["x"] + p["w"] / 2, p["y"] + p["h"] / 2
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(im, (round(cx - im.width / 2) + dx, round(cy - im.height / 2) + dy))
        on_green(layer).save(out / "gen" / f"{name}.png")
        e = {"name": name, "source": f"gen/{name}.png"}
        if dx or dy or scale != 1.0:
            e["align"] = {"scale": scale != 1.0}
            applied[name] = (dx, dy, scale)
        if p.get("hidden"):
            e["hidden"] = True
        spec["parts"].append(e)
    (out / "layers.json").write_text(json.dumps(spec, indent=1))
    for f in ("rig.py", "design.py"):
        if (src / f).is_file():
            shutil.copy2(src / f, out / f)
    res = {"dir": str(out), "drifted_parts": len(applied)}
    r, o = spk("layers", out)
    if not o:
        print(r.stdout[-800:], r.stderr[-800:]); sys.exit(1)
    rows, silent_miss, flagged = [], [], []
    size = {q["name"]: (q["w"], q["h"]) for q in man["parts"]}
    for row in o["alignment"]:
        dx, dy, sc = applied[row["part"]]
        true = (-dx, -dy, round(1 / sc, 2))
        found = (row["dx"], row["dy"], row["scale"])
        w, h = size[row["part"]]
        # where do the part's corners land, compared with where they should?
        err = max(max(abs(cx * found[2] + found[0] - cx * true[2] - true[0]), abs(cy * found[2] + found[1] - cy * true[2] - true[1])) for cx, cy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)))
        rows.append({"part": row["part"], "found": list(found), "true": list(true), "corner_error_px": round(err, 1), "constraint": row["constraint"], "visible": row.get("visible"), "margin": row["margin"]})
        if err > 5 and row["constraint"] == "ok":
            silent_miss.append(row["part"])
        if row["constraint"] != "ok":
            flagged.append(row["part"])
    res["alignment"] = rows
    res["silently_wrong"] = silent_miss                         # must be empty: a wrong fit without a warning is the real failure
    res["flagged_weak"] = flagged
    res["recompose_first_pass"] = {k: o["recompose"][k] for k in ("max_diff", "pixels_over_24", "fraction")}
    res["warnings"] = len(o["warnings"])
    res["translucent_sources_warned"] = sorted(w.split(":")[0] for w in o["warnings"] if "translucent" in w)
    # second pass: do what the warning says -- place the flagged parts by hand (here: with the known truth)
    if flagged:
        for e in spec["parts"]:
            if e["name"] in flagged:
                dx, dy, sc = applied[e["name"]]
                e.pop("align", None)
                e["place"] = {"dx": -dx, "dy": -dy, "scale": round(1 / sc, 2)}
        (out / "layers.json").write_text(json.dumps(spec, indent=1))
        r, o = spk("layers", out)
        res["recompose_after_place"] = {k: o["recompose"][k] for k in ("max_diff", "pixels_over_24", "fraction")}
    res["seam_candidates"] = len(o["seam_candidates"])
    r, b = spk("build", out, "--note", "layers round-trip")
    res["build_ok"] = bool(b and b.get("ok"))
    if not res["build_ok"]:
        res["build_error"] = r.stderr[-400:]
    else:
        r, f = spk("fidelity", out, "--max-fraction", "0.01")
        res["fidelity"] = {k: f[k] for k in ("ok", "max_diff", "pixels_over_threshold", "fraction")} if f else r.stderr[-300:]
        r, c = spk("check", out)
        res["check_ok"] = bool(c and c["ok"])
    res["ok"] = bool(res.get("build_ok") and res.get("check_ok") and isinstance(res.get("fidelity"), dict) and res["fidelity"]["ok"] and not silent_miss)
    print(json.dumps(res, indent=1))
    if not a.keep:
        shutil.rmtree(out, ignore_errors=True)
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
