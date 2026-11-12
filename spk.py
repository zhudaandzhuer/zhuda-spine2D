#!/usr/bin/env python3
"""spk -- one command surface for building and verifying Spine 4.2 characters.

    python3 spk.py doctor                      environment check (read-only)
    python3 spk.py init   DIR [--name N]       new character project from the template
    python3 spk.py art    PROJECT              art.py/SVG -> parts/*.png + manifest + key art
    python3 spk.py layers PROJECT              generated/painted images + layers.json -> the same parts/ (key, align, cut, audit)
    python3 spk.py key IMAGE --out F           remove a solid background from one image
    python3 spk.py grid IMAGE                  labelled pixel grid, for reading coordinates off a picture
    python3 spk.py build  PROJECT              rig.py -> build/NNN/{name}.json/.atlas/.png (never overwrites)
    python3 spk.py fidelity PROJECT            native setup pose vs key art, at art resolution (rig gate A)
    python3 spk.py shot   PROJECT ...          one native frame
    python3 spk.py sheet  PROJECT --anim A     native contact sheet across an animation
    python3 spk.py stress PROJECT              native sheet of the rig's range-of-motion poses
    python3 spk.py play   PROJECT --cues ...   real AnimationState playback (mix/queue/events/physics) -> frames, sheet, gif/mp4
    python3 spk.py check  PROJECT              numeric gate (structure, weights, flips, loop seams, physics, mixes)
    python3 spk.py compare PROJECT --a N --b M same-camera before/after sheet between two builds
    python3 spk.py preview PROJECT             local live viewer for a human
    python3 spk.py export PROJECT --html F     single-file interactive preview;  --zip F  release package
    python3 spk.py util NAME ...               audit | inventory | compact | repack | smooth | gait | boundary

Every image this tool writes is evidence to LOOK AT, not a verdict.  Exit code 0 means "the tool ran and
its numeric checks passed", never "the character looks right".
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))


def die(msg: str, code: int = 1):
    print(f"spk: {msg}", file=sys.stderr)
    sys.exit(code)


def run_node(script: str, args: list, capture: bool = False):
    node = shutil.which("node")
    if not node:
        die("node not found (Node.js >= 18 is required)")
    cmd = [node, str(KIT / "tools" / script)] + [str(a) for a in args]
    return subprocess.run(cmd, cwd=str(KIT), capture_output=capture, text=True)


# ------------------------------------------------------------------------------------------- project
class Project:
    def __init__(self, path: str):
        self.root = Path(path).resolve()
        if not (self.root / "rig.py").is_file() and not (self.root / "build").is_dir():
            die(f"{self.root} is not a character project (no rig.py / build/)")

    def builds(self):
        d = self.root / "build"
        return sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.isdigit()) if d.is_dir() else []

    def latest(self):
        b = self.builds()
        return b[-1] if b else None

    def build_dir(self, which=None) -> Path:
        which = which or self.latest()
        if not which:
            die("no build yet: run `spk build`")
        d = self.root / "build" / str(which).zfill(3)
        if not d.is_dir():
            die(f"build {which} not found (have: {', '.join(self.builds())})")
        return d

    def assets(self, which=None):
        d = self.build_dir(which)
        skin = os.environ.get("SPK_SKIN")
        js = [p for p in d.glob("*.json") if not p.name.endswith((".contract.json", ".stress.json", ".skin.json")) and p.name not in ("build-receipt.json", "bake-report.json") and not p.name.startswith("check")]
        if len(js) != 1:
            die(f"expected exactly one skeleton json in {d}, found {[p.name for p in js]}")
        j = js[0]
        out = {"dir": d, "json": j, "atlas": j.with_suffix(".atlas"), "png": j.with_suffix(".png"), "contract": j.with_name(j.stem + ".contract.json"), "stress": j.with_name(j.stem + ".stress.json"), "name": j.stem, "id": d.name}
        if skin:
            sd = d / "skins" / skin
            if not (sd / (j.stem + ".atlas")).is_file():
                die(f"skin '{skin}' has not been built for {d.name}: run `spk reskin {self.root} --skin {skin}`")
            out.update({"dir": sd, "json": sd / j.name, "atlas": sd / (j.stem + ".atlas"), "png": sd / (j.stem + ".png"), "contract": sd / (j.stem + ".contract.json"), "stress": sd / (j.stem + ".stress.json")})
        return out

    def evidence(self, which=None) -> Path:
        d = self.root / "evidence" / self.build_dir(which).name
        if os.environ.get("SPK_SKIN"):
            d = d / ("skin_" + os.environ["SPK_SKIN"])
        d.mkdir(parents=True, exist_ok=True)
        return d


def load_contract(assets) -> dict:
    return json.loads(assets["contract"].read_text()) if assets["contract"].is_file() else {}


def src_to_world_frame(contract: dict, rect):
    """Source-pixel rect (x, y, w, h; y down) -> world frame used by the viewer."""
    src = contract.get("source")
    if not src:
        die("this build has no source mapping in its contract; pass frames in world units via --world-frame")
    ox, oy = src["origin"]
    x, y, w, h = rect
    return {"x": x - ox, "y": oy - (y + h), "width": w, "height": h}


# ---------------------------------------------------------------------------------------------- doctor
def cmd_doctor(a):
    r = {"python": sys.version.split()[0], "python_ok": sys.version_info >= (3, 9)}
    for mod in ("PIL", "numpy"):
        r[mod] = bool(importlib.util.find_spec(mod))
    r["node"] = shutil.which("node")
    if r["node"]:
        v = subprocess.run([r["node"], "--version"], capture_output=True, text=True).stdout.strip()
        r["node_version"] = v
        r["node_ok"] = int(v.lstrip("v").split(".")[0]) >= 18
        r["node_ts_ok"] = int(v.lstrip("v").split(".")[0]) >= 22  # needed only by the optional spine42 CLI
    r["vendored_runtime"] = (KIT / "node_modules/@esotericsoftware/spine-webgl/dist/iife/spine-webgl.js").is_file() and (KIT / "node_modules/@esotericsoftware/spine-core/dist/index.js").is_file()
    probe = run_node("probe.mjs", [], capture=True) if r["node"] else None
    try:
        r["native_capture"] = json.loads(probe.stdout.strip().splitlines()[-1]) if probe and probe.stdout.strip() else {"ok": False, "error": (probe.stderr if probe else "no node")[-400:]}
    except Exception:
        r["native_capture"] = {"ok": False, "error": (probe.stdout + probe.stderr)[-400:]}
    r["ffmpeg"] = shutil.which("ffmpeg")
    missing = []
    if not r["python_ok"]: missing.append("Python >= 3.9")
    if not r["PIL"]: missing.append("Pillow (pip install pillow)")
    if not r["numpy"]: missing.append("numpy (pip install numpy)")
    if not r.get("node_ok"): missing.append("Node.js >= 18")
    if not r["vendored_runtime"]: missing.append("vendored Spine runtime (restore node_modules/ from the kit, or `npm ci` in the kit root)")
    if not r["native_capture"].get("ok"): missing.append("Playwright + Chromium for native capture (see message in native_capture.error); until fixed, visuals are limited to `spk shot --software` diagnostics")
    r["missing"] = missing
    r["ok"] = not missing
    print(json.dumps(r, indent=1, ensure_ascii=False))
    sys.exit(0 if r["ok"] else 1)


# ------------------------------------------------------------------------------------------------ init
def cmd_init(a):
    dest = Path(a.dir).resolve()
    if dest.exists():
        die(f"{dest} already exists; choose a new directory")
    shutil.copytree(KIT / "templates" / "project", dest)
    name = a.name or dest.name.replace(" ", "_")
    for f in ("rig.py", "art.py", "BRIEF.md", "WORKLOG.md"):
        p = dest / f
        if p.is_file():
            p.write_text(p.read_text(encoding="utf-8").replace("__NAME__", name), encoding="utf-8")
    print(json.dumps({"ok": True, "project": str(dest), "name": name, "next": ["fill BRIEF.md", "edit art.py (or drop layered PNGs + parts/manifest.json)", f"python3 spk.py art {dest}", f"python3 spk.py build {dest}"]}, indent=1))


# ------------------------------------------------------------------------------------------------- art
def cmd_art(a):
    from PIL import Image
    import numpy as np
    root = Path(a.project).resolve()
    svg = root / (a.svg or "art/character.svg")
    art_py = root / "art.py"
    if art_py.is_file() and not a.no_script:
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(KIT), os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep), SPK_KIT=str(KIT))
        r = subprocess.run([sys.executable, str(art_py), "--out", str(svg)], cwd=str(root), env=env, capture_output=True, text=True)
        if r.returncode:
            die("art.py failed:\n" + (r.stderr or r.stdout)[-2000:])
    if not svg.is_file():
        die(f"{svg} not found (write art.py or an SVG with data-part groups)")
    work = root / ".work" / "raster"
    shutil.rmtree(work, ignore_errors=True)
    r = run_node("raster_svg.mjs", ["--svg", svg, "--out", work], capture=True)
    if r.returncode:
        die("SVG rasterisation failed:\n" + (r.stderr or r.stdout)[-1500:])
    info = json.loads((work / "_parts.json").read_text())
    W, H = info["canvas"]
    parts_dir = root / "parts"
    parts_dir.mkdir(exist_ok=True)
    for old in parts_dir.glob("*.png"):
        old.unlink()
    manifest = {"canvas": [W, H], "source": str(svg.relative_to(root)), "parts": []}
    pad = 2
    recompose = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hidden = set(info.get("hidden", []))
    empty = []
    for name in info["parts"]:
        im = Image.open(work / f"{name}.png").convert("RGBA")
        box = im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
        if not box:
            empty.append(name)
            continue
        pd = int(info.get("pads", {}).get(name, pad))
        x0, y0, x1, y1 = max(0, box[0] - pd), max(0, box[1] - pd), min(W, box[2] + pd), min(H, box[3] + pd)
        crop = im.crop((x0, y0, x1, y1))
        crop.save(parts_dir / f"{name}.png")
        manifest["parts"].append({"name": name, "file": f"{name}.png", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, **({"hidden": True} if name in hidden else {})})
        if name not in hidden:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(crop, (x0, y0))
            recompose = Image.alpha_composite(recompose, layer)
    if empty:
        die("parts rendered empty (nothing visible): " + ", ".join(empty))
    (parts_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    key = Image.open(work / "_keyart.png").convert("RGBA")
    key.save(parts_dir / "keyart.png")
    # recomposition check: stacked parts must equal the one-pass key art (proves no part lost or shifted pixels)
    d = np.abs(np.asarray(key).astype(int) - np.asarray(recompose).astype(int)).max(axis=2)
    report = {"ok": True, "parts": len(manifest["parts"]), "canvas": [W, H], "recompose_max_diff": int(d.max()), "recompose_pixels_over_24": int((d > 24).sum()),
              "keyart": str(parts_dir / "keyart.png"), "review": [str(root / "evidence" / "art" / "keyart_bg.png"), str(root / "evidence" / "art" / "parts_sheet.png")]}
    ev = root / "evidence" / "art"
    ev.mkdir(parents=True, exist_ok=True)
    from spinekit.sheets import on_backgrounds, parts_sheet
    from spinekit.layers import audit_parts
    on_backgrounds(key).save(ev / "keyart_bg.png")
    parts_sheet(root, manifest).save(ev / "parts_sheet.png")
    audit = audit_parts(root, manifest)
    report["seam_candidates"] = audit["seam_candidates"]
    report["review"].append(audit["coverage"])
    report["pairs_checked"] = audit["pairs_checked"]
    report["note"] = "seam candidates: visibly adjacent parts where the lower one does not continue under the upper one; they matter only if the two move independently"
    print(json.dumps(report, indent=1))


# ----------------------------------------------------------------------------------------------- skins
def cmd_skin(a):
    """White-model image templates for a skin, or an automatic debug skin."""
    from spinekit import skins
    p = Project(a.project)
    try:
        if a.debug:
            src = p.root / "skins" / "debug"
            rep = skins.make_debug_skin(p.root, p.build_dir(a.build), src)
            rep["reskin"] = {k: v for k, v in skins.reskin(p.root, p.build_dir(a.build), "debug", src).items() if k != "attachments"}
            rep["next"] = [f"python3 spk.py --skin debug sheet {p.root} --anim turntable --n 8", f"python3 spk.py --skin debug stress {p.root}"]
        else:
            rep = skins.export_template(p.root, p.build_dir(a.build), Path(a.template).resolve() if a.template else p.root / "skin")
            rep["next"] = [f"paint or generate one image per template into {p.root / 'skins' / '<skin name>'} (same file names)", f"python3 spk.py reskin {p.root} --skin <skin name>"]
    except skins.SkinError as e:
        die(f"skin: {e}")
    print(json.dumps(rep, indent=1, ensure_ascii=False))


def cmd_reskin(a):
    """Validate replacement images against the templates and pack them as an alternate atlas."""
    from spinekit import skins
    p = Project(a.project)
    src = Path(a.src).resolve() if a.src else p.root / "skins" / a.skin
    try:
        rep = skins.reskin(p.root, p.build_dir(a.build), a.skin, src, fill=a.fill)
    except skins.SkinError as e:
        die(f"reskin: {e}")
    rows = rep.pop("attachments")
    rep["lowest_cover"] = sorted(({"attachment": r["attachment"], "covers_white_shape": r["covers_white_shape"]} for r in rows if not r["origin"].startswith("white")), key=lambda r: r["covers_white_shape"])[:6]
    rep["visual_verdict"] = "NOT_EVALUATED -- render it: spk --skin %s sheet / stress / play" % a.skin
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    if not rep["ok"]:
        sys.exit(1)


# ---------------------------------------------------------------------------------------------- layers
def cmd_layers(a):
    """Generated / painted images -> parts (chroma key, registration, mask cutting, manifest, audits)."""
    from spinekit.layers import LayerError, build_layers
    root = Path(a.project).resolve()
    if a.init:
        src = KIT / "templates" / "imagegen"
        root.mkdir(parents=True, exist_ok=True)
        made = []
        for name, dest in (("layers.halfbody.json", "layers.json"), ("PROMPTS.md", "PROMPTS.md")):
            d = root / dest
            if d.exists():
                die(f"{d} already exists; not overwriting")
            shutil.copy2(src / name, d)
            made.append(str(d))
        (root / "gen").mkdir(exist_ok=True)
        print(json.dumps({"ok": True, "created": made + [str(root / "gen")], "next": ["generate images into gen/ following PROMPTS.md", "edit layers.json (use `spk grid` to read coordinates)", f"python3 spk.py layers {root}"]}, indent=1))
        return
    spec = root / (a.spec or "layers.json")
    if not spec.is_file():
        die(f"{spec} not found (create one with `spk layers {a.project} --init`)")
    try:
        report = build_layers(root, spec)
    except LayerError as e:
        die(f"layers: {e}")
    report = {"ok": True, **report, "visual_verdict": "NOT_EVALUATED -- open the review images"}
    print(json.dumps(report, indent=1, ensure_ascii=False))


def cmd_key(a):
    """Remove a solid background from one image (true alpha on soft edges, colour un-mixed)."""
    import numpy as np
    from PIL import Image
    from spinekit.layers import LayerError, chroma_key, detect_background
    src, out = Path(a.image).resolve(), Path(a.out).resolve()
    if out == src or out.exists():
        die("--out must be a new file")
    img = np.asarray(Image.open(src).convert("RGBA")).copy()
    det = detect_background(img)
    if det["kind"] == "checker":
        die(f"the transparency checkerboard is baked into the pixels ({det['colors']}); regenerate on a solid colour")
    if a.bg == "auto":
        if det["kind"] == "alpha":
            die("image already has a transparent border; nothing to key")
        if det["kind"] != "solid":
            die(f"no solid background found on the border ({det}); pass --bg #rrggbb")
        colour = det["color"]
    else:
        colour = tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    res, stats = chroma_key(img, colour, lo=a.lo, hi=a.hi, mode=a.mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(res, "RGBA").save(out)
    from spinekit.sheets import on_backgrounds
    view = out.with_name(out.stem + ".view.png")
    on_backgrounds(Image.fromarray(res, "RGBA")).save(view)
    note = "translucent areas are estimates: hues drift there (pink turns olive on green); keep generated layers opaque" if stats.get("translucent_share", 0) > 0.03 else None
    print(json.dumps({"ok": True, "out": str(out), "view": str(view), "detected": det, **stats, **({"warning": note} if note else {}), "visual_verdict": "NOT_EVALUATED -- open the view (dark / light / green)"}, indent=1))


def cmd_grid(a):
    """Overlay a labelled pixel grid on an image so coordinates can be read off it."""
    from PIL import Image
    from spinekit.layers import grid_overlay
    src = Path(a.image).resolve()
    out = Path(a.out).resolve() if a.out else src.with_name(src.stem + ".grid.png")
    crop = [int(v) for v in a.crop.split(",")] if a.crop else None
    grid_overlay(Image.open(src), a.step, crop).save(out)
    print(json.dumps({"ok": True, "grid": str(out), "step": a.step, "crop": crop, "note": "labels are source-image pixels (x yellow along the top, y cyan down the left)"}, indent=1))


# ----------------------------------------------------------------------------------------------- build
def cmd_build(a):
    from spinekit import Rig, RigError
    root = Path(a.project).resolve()
    rig_py = root / "rig.py"
    if not rig_py.is_file():
        die(f"{rig_py} not found")
    spec = importlib.util.spec_from_file_location("project_rig", rig_py)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root))
    try:
        spec.loader.exec_module(mod)
        name = getattr(mod, "NAME", root.name)
        rig = Rig(name, root)
        mod.build(rig)
        existing = sorted(p.name for p in (root / "build").glob("[0-9][0-9][0-9]") if p.is_dir()) if (root / "build").is_dir() else []
        nxt = f"{(int(existing[-1]) + 1) if existing else 1:03d}"
        out = root / "build" / nxt
        receipt = rig.compile(out)
    except RigError as e:
        die(f"rig error: {e}")
    # contract gets the source mapping so capture tools can frame in art pixels
    cpath = out / f"{name}.contract.json"
    c = json.loads(cpath.read_text())
    c["source"] = {"canvas": list(rig.canvas_size), "origin": list(rig.origin)}
    cpath.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.note:
        (out / "NOTE.txt").write_text(a.note + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "build": nxt, "dir": str(out), "counts": receipt["counts"], "atlas": receipt["atlas"], "bytes": receipt["bytes"], "visual_verdict": "NOT_EVALUATED"}, indent=1))


# -------------------------------------------------------------------------------------------- captures
def parse_track_specs(anim, time, also, loop_default=True):
    tracks = []
    if anim:
        tracks.append({"track": 0, "anim": anim, "time": float(time or 0), "loop": loop_default})
    for i, spec in enumerate(also or []):
        # name@time[#track]
        nm, _, rest = spec.partition("@")
        t, _, tr = rest.partition("#")
        tracks.append({"track": int(tr) if tr else i + 1, "anim": nm, "time": float(t or 0), "loop": False})
    return tracks


def parse_pose(s):
    pose = {}
    for item in filter(None, (s or "").split(";")):
        key, _, val = item.partition("=")
        bone, _, prop = key.strip().rpartition(".")
        pose.setdefault(bone, {})[prop] = float(val)
    return pose


def parse_look(s):
    out = {}
    for item in filter(None, (s or "").split(";")):
        nm, _, val = item.partition("=")
        x, y = val.split(",")
        out[nm.strip()] = [float(x), float(y)]
    return out


def common_capture_args(p):
    p.add_argument("--build", help="build id (default: latest)")
    p.add_argument("--size", default="640x800", help="capture size WxH in px")
    p.add_argument("--frame", help="camera frame in SOURCE pixels: x,y,w,h (close-ups: e.g. the face)")
    p.add_argument("--bones", action="store_true", help="overlay bones")
    p.add_argument("--mesh", action="store_true", help="overlay mesh triangles")
    p.add_argument("--bg", default="dark", help="dark | light | both | #rrggbb (applied when composing sheets)")
    p.add_argument("--physics", action="store_true", help="simulate physics constraints up to the sampled time (deterministic)")


def capture(project: Project, plan: dict, out: Path, which=None) -> dict:
    assets = project.assets(which)
    out.mkdir(parents=True, exist_ok=True)
    plan_file = out / "plan.json"
    plan_file.write_text(json.dumps(plan, indent=1))
    args = ["--json", assets["json"], "--atlas", assets["atlas"], "--plan", plan_file, "--out", out]
    if assets["contract"].is_file():
        args += ["--contract", assets["contract"]]
    r = run_node("capture.mjs", args, capture=True)
    if not (out / "capture.json").is_file():
        die("native capture failed:\n" + (r.stderr or r.stdout)[-1500:])
    receipt = json.loads((out / "capture.json").read_text())
    if not receipt.get("ok"):
        bad = [s for s in receipt["shots"] + receipt["plays"] if s["status"] != "VERIFIED"]
        print(json.dumps({"capture_failed": bad[:5], "pageErrors": receipt.get("pageErrors")}, indent=1), file=sys.stderr)
        die("capture produced FAILED shots (see above); fix before using these images as evidence")
    return receipt


def base_plan(project, a, which=None):
    w, h = (int(v) for v in a.size.lower().split("x"))
    plan = {"size": [w, h], "bg": "transparent", "debug": {"bones": a.bones, "mesh": a.mesh}, "shots": [], "plays": []}
    if a.frame:
        contract = load_contract(project.assets(which))
        plan["frame"] = src_to_world_frame(contract, [float(v) for v in a.frame.split(",")])
    return plan


def cmd_shot(a):
    from spinekit.sheets import compose_sheet
    project = Project(a.project)
    plan = base_plan(project, a, a.build)
    tracks = parse_track_specs(a.anim, a.time, a.also, loop_default=not a.no_loop)
    seek = {"tracks": tracks, "physics": "simulate" if a.physics else "none", "pose": parse_pose(a.pose), "look": parse_look(a.look)}
    name = a.name or ("setup" if not tracks else "_".join(f"{t['anim']}@{t['time']:g}" for t in tracks))
    name = name.replace("/", "-")
    plan["shots"].append({"name": name, "seek": seek, "label": name})
    out = project.evidence(a.build) / "shots" / name
    receipt = capture(project, plan, out, a.build)
    img = compose_sheet([(out / s["file"], s["label"]) for s in receipt["shots"]], bg=a.bg, tile=max(int(a.size.split("x")[0]), 320), cols=2 if a.bg == "both" else 1)
    dest = Path(a.out).resolve() if a.out else out / f"{name}.view.png"
    img.save(dest)
    print(json.dumps({"ok": True, "view": str(dest), "raw": str(out / receipt["shots"][0]["file"]), "status": receipt["shots"][0]["status"], "visual_verdict": "NOT_EVALUATED -- open the image"}, indent=1))


def anim_info(assets):
    doc = json.loads(assets["json"].read_text())
    out = {}
    for nm, anim in doc.get("animations", {}).items():
        dur = 0.0
        def walk(o):
            nonlocal dur
            if isinstance(o, dict):
                if "time" in o and isinstance(o["time"], (int, float)):
                    dur = max(dur, o["time"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(anim)
        switches = sorted({k.get("time", 0) for s in anim.get("slots", {}).values() for k in s.get("attachment", [])} | {k.get("time", 0) for k in anim.get("drawOrder", [])})
        out[nm] = {"duration": dur, "switches": switches}
    return out


def cmd_sheet(a):
    from spinekit.sheets import compose_sheet
    project = Project(a.project)
    assets = project.assets(a.build)
    info = anim_info(assets)
    if a.anim not in info:
        die(f"unknown animation '{a.anim}' (have: {', '.join(info)})")
    dur = info[a.anim]["duration"]
    contract = load_contract(assets)
    loop = bool(contract.get("animations", {}).get(a.anim, {}).get("loop", False))
    if a.times:
        times = [float(t) for t in a.times.split(",")]
    else:
        n = a.n
        times = [dur * i / (n - 1) for i in range(n)] if n > 1 else [0.0]
    if a.boundaries:
        for t in info[a.anim]["switches"]:
            times += [max(0, t - 1 / 30), t, min(dur, t + 1 / 30)]
    times = sorted({round(t, 4) for t in times})
    plan = base_plan(project, a, a.build)
    under = []
    if a.over:
        # sample an overlay (e.g. blink) on top of a base loop
        under = [{"track": 0, "anim": a.over, "time": 0.0, "loop": True}]
    for t in times:
        tracks = ([dict(under[0], time=t)] if under else []) + [{"track": 1 if under else 0, "anim": a.anim, "time": t, "loop": loop}]
        plan["shots"].append({"name": f"{a.anim.replace('/', '-')}_{t:07.3f}", "label": f"{a.anim} {t:.2f}s", "seek": {"tracks": tracks, "physics": "simulate" if a.physics else "none", "look": parse_look(a.look)}})
    tag = a.tag or ("face" if a.frame else "full")
    out = project.evidence(a.build) / "sheets" / f"{a.anim.replace('/', '-')}_{tag}"
    shutil.rmtree(out, ignore_errors=True)
    receipt = capture(project, plan, out, a.build)
    img = compose_sheet([(out / s["file"], s["label"]) for s in receipt["shots"]], bg=a.bg, tile=a.tile, cols=a.cols)
    dest = out.parent / f"{a.anim.replace('/', '-')}_{tag}.png"
    img.save(dest)
    print(json.dumps({"ok": True, "sheet": str(dest), "frames": len(times), "duration": dur, "loop": loop, "physics": a.physics, "times": times, "visual_verdict": "NOT_EVALUATED -- open the sheet and describe what you see"}, indent=1))


def cmd_stress(a):
    from spinekit.sheets import compose_sheet
    project = Project(a.project)
    assets = project.assets(a.build)
    poses = json.loads(assets["stress"].read_text())["poses"] if assets["stress"].is_file() else []
    if a.only:
        poses = [p for p in poses if any(p["name"].startswith(o) for o in a.only.split(","))]
    if not poses:
        die("no stress poses (declare them in rig.py with rig.stress(...))")
    plan = base_plan(project, a, a.build)
    plan["shots"].append({"name": "setup", "label": "setup", "seek": {"tracks": []}})
    for p in poses:
        plan["shots"].append({"name": p["name"], "label": p["label"], "seek": dict(p["seek"], physics="none")})
    tag = a.tag or ("face" if a.frame else "full")
    out = project.evidence(a.build) / "stress" / tag
    shutil.rmtree(out, ignore_errors=True)
    receipt = capture(project, plan, out, a.build)
    img = compose_sheet([(out / s["file"], s["label"]) for s in receipt["shots"]], bg=a.bg, tile=a.tile, cols=a.cols)
    dest = out.parent / f"stress_{tag}.png"
    img.save(dest)
    print(json.dumps({"ok": True, "sheet": str(dest), "poses": [p["name"] for p in poses], "visual_verdict": "NOT_EVALUATED -- open the sheet"}, indent=1))


def cmd_play(a):
    from spinekit.sheets import compose_sheet, write_gif
    project = Project(a.project)
    cues = []
    for item in filter(None, a.cues.split(";")):
        # anim@time[~mix][#track]   |   -@time#track  (empty animation = stop overlay)
        body, _, tr = item.partition("#")
        body, _, mix = body.partition("~")
        nm, _, at = body.partition("@")
        cue = {"at": float(at or 0), "track": int(tr) if tr else 0}
        if nm.strip() in ("-", ""):
            cue["empty"] = True
        else:
            cue["anim"] = nm.strip()
            contract = load_contract(project.assets(a.build))
            cue["loop"] = bool(contract.get("animations", {}).get(cue["anim"], {}).get("loop", False))
        if mix:
            cue["mix"] = float(mix)
        cues.append(cue)
    look = {}
    for item in filter(None, (a.look_keys or "").split(";")):
        nm, _, val = item.partition(":")
        look[nm] = [[float(v) for v in k.split(",")] for k in val.split("|")]
    plan = base_plan(project, a, a.build)
    name = a.name or "play"
    plan["plays"].append({"name": name, "fps": a.fps, "duration": a.duration, "cues": cues, "physics": not a.no_physics, "look": look, "startX": a.start_x, "facing": a.facing})
    out = project.evidence(a.build) / "plays" / name
    shutil.rmtree(out, ignore_errors=True)
    receipt = capture(project, plan, out, a.build)
    row = receipt["plays"][0]
    frames = [out / name / f["file"] for f in row["frames"]]
    step = max(1, round(len(frames) / a.sheet))
    picks = list(range(0, len(frames), step))
    labels = []
    for i in picks:
        f = row["frames"][i]
        t0 = next((t for t in f["tracks"] if t["track"] == 0), None)
        lab = f"{f['clock']:.2f}s " + (f"{t0['animation']}" + (f"<{t0['mixingFrom']}" if t0 and t0["mixingFrom"] else "") if t0 else "")
        labels.append(lab)
    sheet = compose_sheet(list(zip([frames[i] for i in picks], labels)), bg=a.bg, tile=a.tile, cols=a.cols)
    dest = out.parent / f"{name}.png"
    sheet.save(dest)
    result = {"ok": True, "sheet": str(dest), "frames_dir": str(out / name), "frames": len(frames), "fps": a.fps, "events": row.get("events", []), "visual_verdict": "NOT_EVALUATED -- open the sheet (and the gif/mp4 at normal speed if you can)"}
    if a.gif:
        g = Path(a.gif).resolve()
        write_gif(frames, g, a.fps, a.bg if a.bg != "both" else "dark", width=a.gif_width)
        result["gif"] = str(g)
    if a.mp4:
        if not shutil.which("ffmpeg"):
            die("ffmpeg not found; cannot write mp4 (use --gif)")
        from spinekit.sheets import flatten_frames
        flat = out / "_flat"
        flatten_frames(frames, flat, a.bg if a.bg != "both" else "dark")
        m = Path(a.mp4).resolve()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(flat / "f-%04d.png"), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(m)], check=True)
        shutil.rmtree(flat, ignore_errors=True)
        result["mp4"] = str(m)
    print(json.dumps(result, indent=1))


# -------------------------------------------------------------------------------------------- fidelity
def cmd_fidelity(a):
    """Rig gate A: the native setup pose, rendered at art resolution, must reproduce the key art."""
    import numpy as np
    from PIL import Image
    from spinekit.sheets import flatten
    project = Project(a.project)
    assets = project.assets(a.build)
    contract = load_contract(assets)
    key_path = project.root / "parts" / "keyart.png"
    if not key_path.is_file() or "source" not in contract:
        die("fidelity needs parts/keyart.png and a build made by `spk build`")
    W, H = contract["source"]["canvas"]
    plan = {"size": [W, H], "bg": "transparent", "frame": src_to_world_frame(contract, [0, 0, W, H]), "debug": {"bones": False, "mesh": False}, "shots": [{"name": "setup", "label": "setup", "seek": {"tracks": []}}], "plays": []}
    out = project.evidence(a.build) / "fidelity"
    shutil.rmtree(out, ignore_errors=True)
    capture(project, plan, out, a.build)
    native = Image.open(out / "setup.png").convert("RGBA")
    key = Image.open(key_path).convert("RGBA")
    A, B = np.asarray(flatten(key, "mid")).astype(int), np.asarray(flatten(native, "mid")).astype(int)
    diff = np.abs(A - B).max(axis=2)
    over = diff > a.threshold
    ys, xs = np.nonzero(over)
    box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    heat = Image.fromarray(np.clip(diff * 4, 0, 255).astype(np.uint8), "L")
    heat = Image.merge("RGB", (heat, Image.new("L", heat.size, 0), Image.new("L", heat.size, 40)))
    tile = 520
    sc = tile / W
    size = (tile, round(H * sc))
    sheet = Image.new("RGB", (tile * 3 + 16, size[1] + 8), (12, 16, 22))
    for i, im in enumerate((flatten(key, "mid"), flatten(native, "mid"), heat)):
        sheet.paste(im.resize(size, Image.LANCZOS), (4 + i * (tile + 4), 4))
    dest = out.parent / "fidelity.png"
    sheet.save(dest)
    frac = float(over.mean())
    ok = frac <= a.max_fraction
    print(json.dumps({"ok": ok, "sheet": str(dest), "columns": ["key art", "native setup pose", "difference x4"], "max_diff": int(diff.max()), "pixels_over_threshold": int(over.sum()), "fraction": round(frac, 6), "bbox": box,
                      "note": "differences should be antialiasing-thin lines only; blobs mean a part is misplaced, mis-owned or mis-ordered"}, indent=1))
    sys.exit(0 if ok else 1)



# ----------------------------------------------------------------------------------------------- check
def static_checks(assets) -> dict:
    doc = json.loads(assets["json"].read_text())
    errors, warnings = [], []
    names = [b["name"] for b in doc.get("bones", [])]
    if len(set(names)) != len(names):
        errors.append("duplicate bone names")
    seen = set()
    for b in doc.get("bones", []):
        if "parent" in b and b["parent"] not in seen:
            errors.append(f"bone {b['name']}: parent {b['parent']} not declared before it")
        seen.add(b["name"])
    slots = [s["name"] for s in doc.get("slots", [])]
    if len(set(slots)) != len(slots):
        errors.append("duplicate slot names")
    for s in doc.get("slots", []):
        if s["bone"] not in seen:
            errors.append(f"slot {s['name']}: unknown bone {s['bone']}")
    atlas_regions = set()
    lines = assets["atlas"].read_text().splitlines()
    for i, ln in enumerate(lines):
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if ln.strip() and ":" not in ln and (nxt.startswith("bounds:") or nxt.startswith("rotate:") or nxt.startswith("xy:") or nxt.startswith("index:")):
            atlas_regions.add(ln.strip())
    used = set()
    for skin in doc.get("skins", []):
        for slot, atts in skin.get("attachments", {}).items():
            if slot not in slots:
                errors.append(f"skin {skin['name']}: unknown slot {slot}")
            for nm, att in atts.items():
                if att.get("type", "region") in ("region", "mesh"):
                    path = att.get("path", att.get("name", nm))
                    used.add(path)
                    if path not in atlas_regions:
                        errors.append(f"attachment {slot}/{nm}: region '{path}' missing from atlas")
    for s in doc.get("slots", []):
        att = s.get("attachment")
        if att and not any(att in skin.get("attachments", {}).get(s["name"], {}) for skin in doc.get("skins", [])):
            errors.append(f"slot {s['name']}: setup attachment '{att}' not in any skin")
    unused = sorted(atlas_regions - used)
    if unused:
        warnings.append(f"atlas regions not referenced by any attachment (candidates only): {unused[:8]}")
    from PIL import Image
    pages = [ln.strip() for i, ln in enumerate(lines) if i + 1 < len(lines) and lines[i + 1].startswith("size:")]
    page_sizes, png_bytes = [], 0
    for pg in pages:
        f = assets["dir"] / pg
        if not f.is_file():
            errors.append(f"atlas page missing: {pg}")
            continue
        im = Image.open(f)
        page_sizes.append(list(im.size))
        png_bytes += f.stat().st_size
        if im.mode != "RGBA":
            warnings.append(f"atlas page {pg} mode is {im.mode} (expected RGBA with real alpha)")
    ev = doc.get("events", {})
    for nm, anim in doc.get("animations", {}).items():
        for e in anim.get("events", []):
            if e["name"] not in ev:
                errors.append(f"animation {nm}: undeclared event {e['name']}")
    # Laid-over parameter clips add to the current pose.  Every other clip must therefore key each property a parameter clip
    # touches, or the additions accumulate frame after frame (a chest that slowly shrinks to a sliver).
    con = {}
    try:
        con = json.loads(Path(assets["contract"]).read_text(encoding="utf-8"))
    except Exception:
        pass
    if con.get("parameters"):
        comp = {"rotate": ("r",), "translate": ("tx", "ty"), "translatex": ("tx",), "translatey": ("ty",), "scale": ("sx", "sy"), "scalex": ("sx",), "scaley": ("sy",),
                "shear": ("hx", "hy"), "shearx": ("hx",), "sheary": ("hy",)}

        def props(anim):
            out = set()
            for b_, tls in anim.get("bones", {}).items():
                for tl in tls:
                    out |= {(b_, c_) for c_ in comp.get(tl, ())}
            for s_, tls in anim.get("slots", {}).items():
                if "rgba" in tls:
                    out.add((s_, "rgba"))
            return out
        pclips = {q["clip"] for q in con["parameters"]}
        need = set()
        for c_ in pclips:
            if c_ not in doc.get("animations", {}):
                errors.append(f"parameter clip '{c_}' is not in the skeleton")
                continue
            need |= props(doc["animations"][c_])
            if "drawOrder" in doc["animations"][c_]:
                errors.append(f"{c_}: a parameter clip must not key the draw order")
        for name_, anim in doc.get("animations", {}).items():
            if name_ in pclips:
                continue
            missing = sorted(need - props(anim))
            if missing:
                errors.append(f"{name_}: does not key {len(missing)} properties that parameter clips add to (first: {missing[0][0]}.{missing[0][1]}); laid-over parameters would accumulate every frame")
    return {"errors": errors, "warnings": warnings, "atlas_pages": page_sizes, "atlas_regions": len(atlas_regions), "json_bytes": assets["json"].stat().st_size, "png_bytes": png_bytes,
            "gpu_rgba8_bytes": sum(w * h * 4 for w, h in page_sizes)}


def cmd_check(a):
    project = Project(a.project)
    assets = project.assets(a.build)
    st = static_checks(assets)
    out = assets["dir"] / "check-report.json"
    args = ["--json", assets["json"], "--atlas", assets["atlas"], "--out", assets["dir"] / "check-sweep.json", "--fps", a.fps]
    if assets["contract"].is_file():
        args += ["--contract", assets["contract"]]
    r = run_node("sweep.mjs", args, capture=True)
    try:
        sweep = json.loads(r.stdout)
    except Exception:
        die("sweep failed:\n" + (r.stderr or r.stdout)[-1500:])
    sm = subprocess.run([sys.executable, str(KIT / "tools" / "py" / "motion_smoothness.py"), str(assets["json"]), "--warn-only", "--report", str(assets["dir"] / "check-smoothness.json")], capture_output=True, text=True)
    smooth = {}
    try:
        smooth = json.loads((assets["dir"] / "check-smoothness.json").read_text())
    except Exception:
        smooth = {"note": "motion_smoothness did not produce a report", "stderr": sm.stderr[-300:]}
    errors = st["errors"] + sweep.get("errors", [])
    warnings = st["warnings"] + sweep.get("warnings", [])
    sm_issues = smooth.get("issues") or smooth.get("findings") or []
    report = {"build": assets["id"], "ok": not errors, "errors": errors, "warnings": warnings, "static": {k: v for k, v in st.items() if k not in ("errors", "warnings")}, "sweep": sweep, "smoothness_issues": sm_issues[:20],
              "scope": "numeric gate only -- structure, weights, triangle flips, loop seams, physics stability, mixes. It cannot see pixels or judge performance."}
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    brief = {"build": assets["id"], "ok": report["ok"], "errors": errors, "warnings": warnings, "counts": sweep.get("counts"), "static": report["static"],
             "animations": sweep.get("animations"), "smoothness_issues": len(sm_issues), "report": str(out)}
    print(json.dumps(brief, indent=1, ensure_ascii=False))
    sys.exit(0 if report["ok"] else 1)


# --------------------------------------------------------------------------------------------- compare
def cmd_compare(a):
    from spinekit.sheets import compose_pairs
    project = Project(a.project)
    A, B = project.assets(a.a), project.assets(a.b)
    times = [float(t) for t in a.times.split(",")] if a.times else [0.0]
    out = project.evidence(a.b) / "compare" / f"{A['id']}_vs_{B['id']}_{(a.anim or 'setup').replace('/', '-')}"
    shutil.rmtree(out, ignore_errors=True)
    files = {}
    for side, which in (("a", A["id"]), ("b", B["id"])):
        plan = base_plan(project, a, which)
        for t in times:
            tracks = [{"track": 0, "anim": a.anim, "time": t, "loop": True}] if a.anim else []
            plan["shots"].append({"name": f"t{t:07.3f}", "label": f"{a.anim or 'setup'} {t:.2f}s", "seek": {"tracks": tracks, "physics": "simulate" if a.physics else "none", "look": parse_look(a.look), "pose": parse_pose(a.pose)}})
        rec = capture(project, plan, out / side, which)
        files[side] = [(out / side / s["file"], s["label"]) for s in rec["shots"]]
    img, metrics = compose_pairs(files["a"], files["b"], f"build {A['id']}", f"build {B['id']}", bg=a.bg, tile=a.tile)
    dest = out.parent / (out.name + ".png")
    img.save(dest)
    print(json.dumps({"ok": True, "sheet": str(dest), "metrics": metrics, "note": "metrics locate differences; the verdict (IMPROVED / UNCHANGED / WORSE) comes from looking"}, indent=1))


# --------------------------------------------------------------------------------------------- preview
def cmd_preview(a):
    import functools
    import http.server
    project = Project(a.project)
    assets = project.assets(a.build)
    roots = {"kit": KIT, "p": assets["dir"]}

    class H(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            parts = [p for p in path.split("/") if p and p not in (".", "..")]
            root = roots.get(parts[0]) if parts else None
            return str(root.joinpath(*parts[1:])) if root else str(KIT / "viewer" / "404")

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *args):
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H) as srv:
        q = f"json=/p/{assets['json'].name}&atlas=/p/{assets['atlas'].name}" + (f"&contract=/p/{assets['contract'].name}" if assets["contract"].is_file() else "")
        print(f"Preview (build {assets['id']}): http://127.0.0.1:{srv.server_port}/kit/viewer/index.html?{q}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


# ---------------------------------------------------------------------------------------------- export
def data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def cmd_export(a):
    project = Project(a.project)
    assets = project.assets(a.build)
    result = {"ok": True, "build": assets["id"]}
    if a.html:
        html = (KIT / "viewer" / "index.html").read_text(encoding="utf-8")
        runtime = (KIT / "node_modules/@esotericsoftware/spine-webgl/dist/iife/spine-webgl.js").read_text(encoding="utf-8")
        viewer = (KIT / "viewer" / "viewer.js").read_text(encoding="utf-8")
        # Everything is embedded as base64 data URIs (no network, no URL-special characters); the viewer restores
        # UTF-8 for text, because the Spine downloader decodes base64 with atob (Latin-1).
        text_uri = lambda f, mime: data_uri(f, mime)
        atlas_lines = assets["atlas"].read_text().splitlines()
        pages = [ln.strip() for i, ln in enumerate(atlas_lines) if i + 1 < len(atlas_lines) and atlas_lines[i + 1].startswith("size:")]
        raw = {assets["json"].name: text_uri(assets["json"], "application/json"), assets["atlas"].name: text_uri(assets["atlas"], "text/plain")}
        for pg in dict.fromkeys(pages):
            raw[pg] = data_uri(assets["dir"] / pg, "image/png")
        cfg = {"json": assets["json"].name, "atlas": assets["atlas"].name, "raw": raw}
        if assets["contract"].is_file():
            raw[assets["contract"].name] = text_uri(assets["contract"], "application/json")
            cfg["contract"] = assets["contract"].name
        contract = load_contract(assets)
        title = a.title or contract.get("title") or assets["name"]
        if a.cdn:
            rt = '<script src="https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-webgl@4.2.119/dist/iife/spine-webgl.min.js"></script>'
        else:
            rt = "<script>/* Spine Runtimes (c) Esoteric Software LLC -- see Spine Runtimes License Agreement: http://esotericsoftware.com/spine-runtimes-license */\n" + runtime.replace("</script>", "<\\/script>") + "</script>"
        html = html.replace('<script src="../node_modules/@esotericsoftware/spine-webgl/dist/iife/spine-webgl.js"></script>', rt)
        html = html.replace('<script src="viewer.js"></script>', "<script>window.SPK_CONFIG=" + json.dumps(cfg).replace("</", "<\\/") + ";</script>\n<script>" + viewer.replace("</script>", "<\\/script>") + "</script>")
        html = html.replace("<title>Spine 原生預覽</title>", f"<title>{title}</title>")
        dest = Path(a.html).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        result["html"] = str(dest)
        result["html_bytes"] = dest.stat().st_size
    if a.zip:
        dest = Path(a.zip).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        manifest = {}
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            atlas_lines = assets["atlas"].read_text().splitlines()
            pages = [assets["dir"] / ln.strip() for i, ln in enumerate(atlas_lines) if i + 1 < len(atlas_lines) and atlas_lines[i + 1].startswith("size:")]
            for f in [assets["json"], assets["atlas"], *pages, assets["contract"]]:
                if f.is_file():
                    z.write(f, f"{assets['name']}/{f.name}")
                    manifest[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
            z.writestr(f"{assets['name']}/SHA256SUMS.json", json.dumps(manifest, indent=1))
            z.writestr(f"{assets['name']}/README.txt", f"{assets['name']} -- Spine {load_contract(assets).get('spine', '4.2')} runtime package (build {assets['id']}).\n"
                       "Files: skeleton .json, .atlas, .png page (straight alpha unless the atlas says pma:true), and .contract.json\n"
                       "(tracks, loops, mixes, look controller) which your controller must honour. Using the Spine Runtimes requires a Spine Editor license.\n")
        with zipfile.ZipFile(dest) as z:
            bad = z.testzip()
            if bad:
                die(f"zip CRC failure in {bad}")
        result["zip"] = str(dest)
        result["sha256"] = manifest
    if not a.html and not a.zip:
        die("nothing to export: pass --html FILE and/or --zip FILE")
    print(json.dumps(result, indent=1))


# ------------------------------------------------------------------------------------------------ util
UTILS = {"audit": "audit_package.py", "inventory": "spine_audit.py", "compact": "compact_spine_json.py", "repack": "repack_spine_atlas.py", "smooth": "motion_smoothness.py", "gait": "gait_curve.py", "boundary": "boundary_plan.py", "frames": "compare_frames.py"}


def cmd_util(a):
    if a.tool not in UTILS:
        die(f"unknown util '{a.tool}' (have: {', '.join(UTILS)})")
    sys.exit(subprocess.run([sys.executable, str(KIT / "tools" / "py" / UTILS[a.tool])] + a.rest).returncode)


def cmd_software(a):
    """Diagnostic CPU render (no browser). Never delivery evidence."""
    project = Project(a.project)
    assets = project.assets(a.build)
    out = Path(a.out).resolve() if a.out else project.evidence(a.build) / "software" / f"{(a.anim or 'setup').replace('/', '-')}_{a.time:g}.png"
    args = ["--json", assets["json"], "--atlas", assets["atlas"], "--out", out, "--time", a.time]
    if a.anim:
        args += ["--anim", a.anim]
    if a.bones:
        args += ["--bones", "1"]
    r = run_node("softrender.mjs", args, capture=True)
    if r.returncode:
        die("software render failed:\n" + (r.stderr or r.stdout)[-1200:])
    print(json.dumps({"ok": True, "image": str(out), "renderer": "software (diagnostic only, not delivery evidence)"}, indent=1))


def main():
    p = argparse.ArgumentParser(prog="spk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skin", dest="use_skin", help="render with a skin built by `spk reskin` (put it BEFORE the command: spk --skin NAME sheet ...)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="environment check").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("init", help="new project from template"); s.add_argument("dir"); s.add_argument("--name"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("art", help="art.py / SVG -> parts + manifest + key art"); s.add_argument("project"); s.add_argument("--svg"); s.add_argument("--no-script", action="store_true"); s.set_defaults(fn=cmd_art)
    s = sub.add_parser("skin", help="white model: export the image templates for a skin, or build a debug skin"); s.add_argument("project"); s.add_argument("--template", help="output folder (default PROJECT/skin)"); s.add_argument("--debug", action="store_true", help="generate and build the direction-stamped debug skin"); s.add_argument("--build"); s.set_defaults(fn=cmd_skin)
    s = sub.add_parser("reskin", help="white model: build a skin (alternate atlas) from replacement images"); s.add_argument("project"); s.add_argument("--skin", required=True); s.add_argument("--from", dest="src", help="folder with the images (default PROJECT/skins/<skin>)"); s.add_argument("--fill", action="store_true", help="keep the white template where an image is missing"); s.add_argument("--build"); s.set_defaults(fn=cmd_reskin)
    s = sub.add_parser("layers", help="generated/painted images + layers.json -> parts + manifest + audits"); s.add_argument("project"); s.add_argument("--spec"); s.add_argument("--init", action="store_true", help="write a starter layers.json + PROMPTS.md into the project"); s.set_defaults(fn=cmd_layers)
    s = sub.add_parser("key", help="remove a solid background from one image"); s.add_argument("image"); s.add_argument("--out", required=True); s.add_argument("--bg", default="auto", help="auto | #rrggbb"); s.add_argument("--mode", default="global", choices=["global", "border"]); s.add_argument("--lo", type=float, default=0.07); s.add_argument("--hi", type=float, default=0.30); s.set_defaults(fn=cmd_key)
    s = sub.add_parser("grid", help="labelled coordinate grid over an image"); s.add_argument("image"); s.add_argument("--step", type=int, default=50); s.add_argument("--crop", help="x,y,w,h"); s.add_argument("--out"); s.set_defaults(fn=cmd_grid)
    s = sub.add_parser("build", help="compile rig.py into a new build/NNN"); s.add_argument("project"); s.add_argument("--note", help="one line: what changed in this build"); s.set_defaults(fn=cmd_build)

    s = sub.add_parser("shot", help="one native frame"); s.add_argument("project"); common_capture_args(s)
    s.add_argument("--anim"); s.add_argument("--time", type=float, default=0.0); s.add_argument("--also", action="append", help="overlay: name@time[#track] (repeatable)")
    s.add_argument("--pose", help='additive bone offsets: "head.rot=8;chest.y=3"'); s.add_argument("--look", help='controller input: "look=0.8,0.2"'); s.add_argument("--no-loop", action="store_true"); s.add_argument("--name"); s.add_argument("--out"); s.set_defaults(fn=cmd_shot)

    s = sub.add_parser("sheet", help="native contact sheet across one animation"); s.add_argument("project"); common_capture_args(s)
    s.add_argument("--anim", required=True); s.add_argument("--n", type=int, default=12); s.add_argument("--times"); s.add_argument("--boundaries", action="store_true", help="add frames around attachment/draw-order switches")
    s.add_argument("--over", help="sample --anim as an overlay on top of this looping base animation"); s.add_argument("--look"); s.add_argument("--tile", type=int, default=280); s.add_argument("--cols", type=int, default=0); s.add_argument("--tag"); s.set_defaults(fn=cmd_sheet)

    s = sub.add_parser("stress", help="native sheet of range-of-motion poses"); s.add_argument("project"); common_capture_args(s)
    s.add_argument("--only", help="comma-separated name prefixes"); s.add_argument("--tile", type=int, default=280); s.add_argument("--cols", type=int, default=0); s.add_argument("--tag"); s.set_defaults(fn=cmd_stress)

    s = sub.add_parser("play", help="real playback with mixing/queue/physics at fixed dt"); s.add_argument("project"); common_capture_args(s)
    s.add_argument("--cues", required=True, help='"idle@0;nod@1.0~0.2;idle@2.3~0.3;blink@0.5#1"  (anim@time[~mix][#track], "-@t#1" clears a track)')
    s.add_argument("--duration", type=float, default=3.0); s.add_argument("--fps", type=int, default=30); s.add_argument("--no-physics", action="store_true")
    s.add_argument("--start-x", type=float, default=0.0, help="skeleton x at the start (locomotion clips move it)"); s.add_argument("--facing", type=int, default=1, help="1 or -1")
    s.add_argument("--look-keys", help='"look:0,0,0|1.0,1,0|2.0,-1,0.2" (time,x,y keys)'); s.add_argument("--sheet", type=int, default=12, help="frames on the summary sheet")
    s.add_argument("--tile", type=int, default=280); s.add_argument("--cols", type=int, default=0); s.add_argument("--name"); s.add_argument("--gif"); s.add_argument("--gif-width", type=int, default=360); s.add_argument("--mp4"); s.set_defaults(fn=cmd_play)

    s = sub.add_parser("fidelity", help="native setup pose vs key art (rig gate A)"); s.add_argument("project"); s.add_argument("--build"); s.add_argument("--threshold", type=int, default=40); s.add_argument("--max-fraction", type=float, default=0.004); s.set_defaults(fn=cmd_fidelity)
    s = sub.add_parser("check", help="numeric gate"); s.add_argument("project"); s.add_argument("--build"); s.add_argument("--fps", default="30"); s.set_defaults(fn=cmd_check)

    s = sub.add_parser("compare", help="before/after between two builds, same camera"); s.add_argument("project"); common_capture_args(s)
    s.add_argument("--a", required=True); s.add_argument("--b", required=True); s.add_argument("--anim"); s.add_argument("--times"); s.add_argument("--look"); s.add_argument("--pose"); s.add_argument("--tile", type=int, default=300); s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("preview", help="serve the live viewer"); s.add_argument("project"); s.add_argument("--build"); s.add_argument("--port", type=int, default=0); s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("export", help="single-file HTML preview and/or runtime zip"); s.add_argument("project"); s.add_argument("--build"); s.add_argument("--html"); s.add_argument("--zip"); s.add_argument("--title"); s.add_argument("--cdn", action="store_true", help="load the runtime from jsDelivr instead of inlining it"); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("software", help="diagnostic CPU render (no browser)"); s.add_argument("project"); s.add_argument("--build"); s.add_argument("--anim"); s.add_argument("--time", type=float, default=0.0); s.add_argument("--bones", action="store_true"); s.add_argument("--out"); s.set_defaults(fn=cmd_software)
    s = sub.add_parser("util", help="audit | inventory | compact | repack | smooth | gait | boundary | frames"); s.add_argument("tool"); s.add_argument("rest", nargs=argparse.REMAINDER); s.set_defaults(fn=cmd_util)
    a = p.parse_args()
    if a.use_skin:
        os.environ["SPK_SKIN"] = a.use_skin
    a.fn(a)


if __name__ == "__main__":
    main()
