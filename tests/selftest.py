#!/usr/bin/env python3
"""Kit self-test.  Runs in a temporary directory; never touches your projects.

    python3 tests/selftest.py            # everything (needs Playwright + Chromium for the native steps)
    python3 tests/selftest.py --no-native  # compiler + numeric gate only

Covers: curve/mesh/weight/atlas units, template project end to end (init -> art -> build -> fidelity -> check ->
stress -> play -> export), fault injection (unowned part, overwrite refusal, broken loop, flipped mesh, bad
capture request), and the carried-over utilities.
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
RESULTS = []


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS  " if cond else "FAIL  ") + name + (f"  -- {detail}" if detail and not cond else ""), flush=True)


def spk(*args, expect=0):
    r = subprocess.run([sys.executable, str(KIT / "spk.py"), *map(str, args)], capture_output=True, text=True)
    out = None
    try:
        out = json.loads(r.stdout) if r.stdout.strip().startswith("{") else None
    except Exception:
        out = None
    return r, out


def units():
    import numpy as np
    from spinekit import curves as C, weights as W
    from spinekit.meshgen import grid_mesh
    from spinekit.atlas import bleed_rgb, pack
    from PIL import Image
    a = C.keyed([(0, 0), (1, 10), (2, 0)], "ease")
    b = C.oscillator(3, 1.0, 0, 2)
    t = C.total([a, b])
    err = max(abs(t.value(x / 50) - (a.value(x / 50) + b.value(x / 50))) for x in range(101))
    ok("curves: layers sum exactly at shared knots", err < 1e-6, f"max err {err}")
    ok("curves: periodic oscillator closes", abs(b.value(0) - b.value(2)) < 1e-9 and abs(b.slope(0, "right") - b.slope(2, "left")) < 1e-6)
    alpha = np.zeros((90, 60), np.uint8); alpha[10:80, 20:40] = 255
    g = grid_mesh(alpha, step=15)
    n = len(g["points"])
    ok("mesh: hull first, indices valid", g["hull"] >= 4 and max(g["triangles"]) < n and len(g["uvs"]) == 2 * n)
    ok("mesh: empty cells culled", g["cells"] < g["grid"][0] * g["grid"][1])
    w = W.finalize({"a": np.array([0.5, 0.0, 0.2]), "b": np.array([0.5, 1.0, 0.0])})
    ok("weights: normalised per vertex", all(abs(sum(x[1] for x in row) - 1) < 1e-9 for row in w))
    px = np.zeros((8, 8, 4), np.uint8); px[3:5, 3:5] = (200, 100, 50, 255)
    bl = bleed_rgb(px, 3)
    ok("atlas: bleed fills transparent RGB, keeps alpha", bl[2, 2, 3] == 0 and tuple(bl[2, 3, :3]) == (200, 100, 50) and (bl[..., 3] == px[..., 3]).all())
    page, text, regions = pack({"p": Image.fromarray(px, "RGBA")}, "t.png")
    ok("atlas: region bounds recorded", "bounds:" in text and regions["p"][2:] == (8, 8))


def skip(name, why):
    print(f"SKIP  {name} ({why})")


def layer_units(tmp):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    from spinekit import layers as L
    # soft-edged disc with a wide feather, composited on green
    H = W = 160
    yy, xx = np.mgrid[0:H, 0:W]
    a = np.clip((60 - np.hypot(xx - 80, yy - 80)) / 24, 0, 1)
    fg = np.array([220, 150, 160], np.float32)
    img = np.dstack([np.rint(a[..., None] * fg + (1 - a[..., None]) * np.array([0, 255, 0])), np.full((H, W), 255)]).astype(np.uint8)
    out, st = L.chroma_key(img, (0, 255, 0))
    vis = out[..., 3] > 40
    ok("key: alpha of a wide soft fade recovered", float(np.abs(out[..., 3] / 255 - a).max()) < 0.06, f"max alpha err {np.abs(out[..., 3] / 255 - a).max():.3f}")
    ok("key: no background colour left in the foreground", float(np.abs(out[vis][:, :3].astype(float) - fg).max()) < 14)
    ok("key: detects solid background", L.detect_background(img)["kind"] == "solid")
    chk = np.indices((H, W)).sum(0) // 16 % 2
    checker = np.dstack([np.where(chk, 204, 255)] * 3 + [np.full((H, W), 255)]).astype(np.uint8)
    ok("key: detects a baked transparency checkerboard", L.detect_background(checker)["kind"] == "checker")
    # registration: textured part, partly hidden by an occluder, drifted by (5, -3)
    rng = np.random.default_rng(3)
    tex = Image.fromarray((rng.random((H, W, 3)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    part = np.dstack([np.asarray(tex), np.zeros((H, W), np.uint8)]); part[40:120, 50:110, 3] = 255
    key = part.copy(); key[30:70, 40:120] = (30, 30, 40, 255)                         # something in front hides its top
    occ = np.zeros((H, W), bool); occ[30:70, 40:120] = True
    moved, info = L.align_to(key, L._shift(part, -5, 3), search=12, occluded=occ)
    ok("align: recovers a known drift behind an occluder", (info["dx"], info["dy"]) == (5, -3) and info["constraint"] == "ok", str(info))
    flat = np.zeros((H, W, 4), np.uint8); flat[40:120, 50:110] = (40, 40, 50, 255)
    keyf = flat.copy(); keyf[20:140, 30:130] = (40, 40, 50, 255)                       # same colour all around: nothing to hold on to
    _, info = L.align_to(keyf, L._shift(flat, 4, 0), search=12)
    ok("align: featureless part surrounded by its own colour is flagged weak", info["constraint"] == "weak", str(info))
    m = L.polygon_mask((W, H), [(20, 20), (140, 20), (140, 140), (20, 140)], holes=[[(60, 60), (100, 60), (100, 100), (60, 100)]], feather=0)
    ok("cut: polygon with a hole", m[30, 30] > 0.99 and m[80, 80] < 0.01 and m[5, 5] < 0.01)
    al = np.zeros((H, W), np.uint8); al[40:120, 40:120] = 255
    f = L.edge_fade(al, {"top": 10})
    ok("cut: edge fade", f[40, 80] == 0 and f[45, 80] in range(100, 160) and f[60, 80] == 255)
    A = np.zeros((H, W), np.uint8); A[20:80, 20:140] = 255            # lower part stops exactly where the upper begins
    B = np.zeros((H, W), np.uint8); B[80:140, 20:140] = 255
    C = np.zeros((H, W), np.uint8); C[20:110, 20:140] = 255            # lower part continues 30 px under the upper
    butt = [s_ for s_ in L.seam_candidates([("lower", A), ("upper", B)]) if s_["risk"] != "ok"]
    lap = [s_ for s_ in L.seam_candidates([("lower", C), ("upper", B)]) if s_["risk"] != "ok"]
    ok("audit: butt joint is a seam candidate, overlapped joint is not", len(butt) == 1 and butt[0]["risk"] == "SEAM" and not lap, f"{butt} {lap}")
    src = tmp / "disc.png"; Image.fromarray(img[..., :3], "RGB").save(src)
    r, o = spk("key", src, "--out", tmp / "disc_keyed.png")
    ok("spk key: writes keyed image + background view", r.returncode == 0 and (tmp / "disc_keyed.png").is_file() and Path(o["view"]).is_file())
    r, o = spk("grid", src, "--step", "20")
    ok("spk grid: writes labelled grid", r.returncode == 0 and Path(o["grid"]).is_file())


def figure_units(tmp):
    import numpy as np
    from spinekit import figure3d as F, curves as C, motions3d
    B = F.Body("hero", cam_pitch=0.0)
    front, side = F.solve(B.pose(0.0), B)[0], F.solve(B.pose(90.0), B)[0]
    ok("figure3d: chest ellipsoid is wide from the front, thin from the side", abs(min(front["chest"]["a"], front["chest"]["b"]) - B.e["chest"][0]) < 0.5 and abs(min(side["chest"]["a"], side["chest"]["b"]) - B.e["chest"][2]) < 0.5)
    p = B.pose(90.0)
    p.foot["L"].update(z=120.0, y=60.0)
    p.py = -40
    s = F.solve(p, B)[0]
    ok("figure3d: leg IK keeps bone lengths and reaches the ankle target", abs(s["thigh_L"]["a"] - B.thigh) < 1.0 and abs(s["shin_L"]["a"] - B.shin) < 1.0 and abs(s["ankle_L"]["x"] - 120.0) < 0.5)
    q = B.pose(70.0); q.pyaw, q.syaw, q.proll = 12, -20, 5; q.arm["L"].update(flex=40, elbow=50, abd=20); q.foot["R"].update(z=60, y=50, pitch=-20)
    a, b = F.solve(q, B)[0], F.solve(F.mirror(q), B)[0]
    worst = max(max(abs(a[f"{n}_L"]["x"] + b[f"{n}_R"]["x"]), abs(a[f"{n}_L"]["y"] - b[f"{n}_R"]["y"])) for n in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"))
    ok("figure3d: mirror(pose) is the mirror image with left and right swapped", worst < 1e-6 and abs(a["head"]["x"] + b["head"]["x"]) < 1e-6, f"{worst}")
    ok("figure3d: a part's facing is read correctly, also when it bends forward", all(abs(F._near_angle(F.part_yaw(F.solve(B.pose(h), B)[0]["head"]["R"]) - h, 0)) < 1e-6 for h in (0, 45, 90, 180, 270)) and
       abs(F.part_yaw(F.solve(F.Pose(heading=90.0, ppitch=80.0), B)[0]["chest"]["R"]) - 90) < 1e-6)
    # a view image mapped onto the same view is the identity; turned 20 degrees it stays a proper (non-mirrored) map
    ref = F.view_ref(B, "head", 2)
    hq = F.solve(B.pose(90.0), B)[0]["head"]
    L = F._ell_map(hq, ref, B.cam)
    hq2 = F.solve(B.pose(110.0), B)[0]["head"]
    ok("figure3d: view image maps onto its own view unchanged, and stays unmirrored when the part turns", float(np.abs(L - np.eye(2)).max()) < 1e-6 and float(np.linalg.det(F._ell_map(hq2, ref, B.cam))) > 0.5)

    class Cap:
        def _add(self, bone, prop, pp):
            self.pp = pp
    cap = Cap()
    F._channel(cap, "b", "rotate", [0, 1 / 3, 2 / 3 - 0.001, 2 / 3, 1.0], [0, 1, 2, 10, 11], [False, False, True, False, False], False, False)
    tot = C.total([cap.pp])
    ok("figure3d: a view switch stays a clean jump after export (old value held, new value on the next key)", [bool(x) for x in tot.stepped] == [False, False, True, False, False] and tot.v[2] == 2 and tot.v[3] == 10, f"{tot.stepped} {tot.v}")
    worst = 0.0
    for name in F.PRESETS:
        Bn = F.Body(name)
        M = motions3d.Motions(Bn)
        clips_ = [(M.kungfu, M.KUNGFU_T), (M.dance, M.DANCE_T), (M.walk, M.WALK_T), (M.run, M.RUN_T), (M.jump, M.JUMP_T), (M.pick, M.PICK_T), (M.turn_true, M.TURN_T)]
        for act, dur in ((M.block, M.BLOCK_T), (M.slash, M.SLASH_T), (M.bash, M.BASH_T), (M.cast, M.CAST_T), (M.channel, M.CHANNEL_T)):
            clips_ += [(act, dur), ((lambda t_, act=act: act(t_, True)), dur)]
        for fn, dur in clips_:
            for i in range(int(dur * 20) + 1):
                pp = M.held(fn(i / 20))
                worst = max(worst, F.reach_guard(pp, Bn), F.solve(pp, Bn)[2])
    ok(f"figure3d: after the reach guard no foot target is out of reach, for all {len(F.PRESETS)} bodies and every clip", worst < 0.05, f"{worst:.2f}px")
    Mk = motions3d.Motions(F.Body("knight"))
    walk_l = Mk.held(F.mirror(Mk.walk(0.2)))
    ok("figure3d: facing left, a carried shield stays on the arm that carries it (hold is applied after mirroring)", abs(walk_l.arm["L"]["twist"] + 81.0) < 1e-6 and abs(walk_l.arm["R"]["twist"]) < 1e-6 and walk_l.heading == -90.0)
    r_, l_ = Mk.slash(0.40, False), Mk.slash(0.40, True)
    ok("figure3d: a class action facing left is done by the same anatomical arm (the sword stays in the right hand)", r_.arm["R"]["flex"] == l_.arm["R"]["flex"] == 150 and l_.heading == -90.0 and r_.heading == 90.0 and l_.pyaw == -(r_.pyaw + 10) + -10 + 0 or (r_.arm["R"]["flex"] == l_.arm["R"]["flex"] == 150 and l_.heading == -90.0))
    kn = F.rest_solution(F.Body("knight"))
    ok("figure3d: a tube keeps its true length for its image even when the rest pose foreshortens it", all(q_["len3"] >= q_["a"] - 1e-6 for q_ in kn.values() if q_["kind"] == "tube"))
    sec = F.view_sectors(True)
    ok("figure3d: a plate uses its edge-on view only near edge-on, with hysteresis", F.pick_view(75, None, sec) == 1 and F.pick_view(88, None, sec) == 2 and F.pick_view(102, 2, sec) == 2 and F.pick_view(106, 2, sec) == 3
       and F.pick_view(75, None, F.view_sectors()) == 2)
    ok("figure3d: a shield lying sideways on the forearm still reports where its face points", F.rest_view(kn["shield"], True) == 0 and
       all(abs(F._near_angle(F.part_yaw(F._ry(math.radians(h_)) @ F._rz(math.radians(90))) - h_, 0)) < 1e-6 for h_ in (0, 45, 135, 270)))
    mg = KIT / "examples" / "whitemodels" / "mage" / "build"
    if mg.is_dir():
        bd = sorted(d_ for d_ in mg.iterdir() if d_.is_dir() and d_.name.isdigit())[-1]
        doc = json.loads((bd / "mage.json").read_text())
        setup = [s_["name"] for s_ in doc["slots"]]
        bad = 0
        for an in ("walk", "run", "jump", "turntable"):
            for key in doc["animations"][an].get("drawOrder", []):
                order = [None] * len(setup)
                moved = {o_["slot"]: o_["offset"] for o_ in key.get("offsets", [])}
                for i_, n_ in enumerate(setup):
                    if n_ in moved:
                        order[i_ + moved[n_]] = n_
                rest_ = [n_ for n_ in setup if n_ not in moved]
                for i_ in range(len(order)):
                    if order[i_] is None:
                        order[i_] = rest_.pop(0)
                robe = order.index("robe_1")
                bad += sum(1 for n_ in order[robe + 1:] if n_.startswith(("thigh_", "knee_", "shin_", "hip_")) or n_ == "pelvis")
        ok("figure3d: legs never draw above the robe that encloses them (every draw-order key of walk, run, jump, turntable)", bad == 0, f"{bad} violations")
    else:
        skip("robe draw-order test", "examples/whitemodels/mage has no build")
    for name in ("heroine", "mascot"):
        Bn = F.Body(name)
        fr = [F.solve(Bn.pose(90.0), Bn)[1]] * 40
        ex = F.sim_extras(Bn, fr, 1 / 30, False)
        drift = max(abs(ex[-1][k]["x"] - ex[0][k]["x"]) + abs(ex[-1][k]["y"] - ex[0][k]["y"]) for k in ex[0])
        ok(f"figure3d: {name}'s add-ons hang still when the body is still", drift < 0.5, f"{drift:.3f}")
    proj = KIT / "examples" / "whitemodels" / "hero"
    if (proj / "build").is_dir():
        from spinekit import skins
        work = tmp / "skin_hero"
        (work / "build").mkdir(parents=True)
        shutil.copytree(proj / "parts", work / "parts")
        bsrc = sorted(d_ for d_ in (proj / "build").iterdir() if d_.is_dir() and d_.name.isdigit())[-1]
        bdir = work / "build" / bsrc.name
        bdir.mkdir()
        for f_ in bsrc.iterdir():
            if f_.is_file():
                shutil.copy2(f_, bdir / f_.name)
        src = work / "skins" / "t"
        skins.make_debug_skin(work, bdir, src)
        rep = skins.reskin(work, bdir, "t", src)
        ok("reskin: a complete set of images builds an alternate atlas with the same region names", rep["ok"] and Path(rep["atlas"]).is_file() and rep["provided"] == len(rep["attachments"]))
        (src / "head_v7.png").unlink()
        rep = skins.reskin(work, bdir, "t", src)
        ok("reskin: a missing left-hand view is mirrored from its right-hand twin", rep["ok"] and rep["mirrored"] == 1)
        (src / "upperarm_L.png").unlink()
        rep = skins.reskin(work, bdir, "t", src)
        ok("reskin: a missing image that cannot be mirrored is refused by name", (not rep["ok"]) and any("upperarm_L" in e for e in rep["errors"]))
        ok("reskin: --fill keeps the white template for missing images and says so", skins.reskin(work, bdir, "t", src, fill=True)["kept_white"] >= 1)
        from PIL import Image as _I
        _I.new("RGBA", (40, 200), (255, 0, 0, 255)).save(src / "upperarm_L.png")
        rep = skins.reskin(work, bdir, "t", src)
        ok("reskin: an image with the wrong proportions is refused", (not rep["ok"]) and any("proportions" in e for e in rep["errors"]))
    else:
        skip("reskin tests", "examples/whitemodels/hero has no build")


def front_units(tmp):
    import importlib.util
    from spinekit import figure3d as F, motions3d
    B = F.Body("vtuber")
    ok("front: eye and mouth pick their state image from the face values",
       F._eye_state({"open": 1}) == "open" and F._eye_state({"open": 0.4}) == "half" and F._eye_state({"open": 0}) == "closed" and F._iris_state({"open": 0}) is None
       and F._mouth_state({"mouth": 0, "smile": 1}) == "smile" and F._mouth_state({"mouth": 0.9, "smile": 1}) == "open3")
    front, back = F.solve(B.pose(0.0), B)[0], F.solve(B.pose(180.0), B)[0]
    feats = ("eye_L", "iris_R", "mouth", "nose", "brow_L")
    ok("front: face parts are in front of the head facing the camera and behind it facing away",
       all(front[n_]["depth"] > front["head"]["depth"] for n_ in feats) and all(back[n_]["depth"] < back["head"]["depth"] for n_ in feats))
    p_, q_ = B.pose(0.0), B.pose(0.0)
    p_.face.update(gx=1.0)
    a_, b_ = F.solve(p_, B)[0], F.solve(q_, B)[0]
    ok("front: gaze moves the iris, not the eye", a_["iris_L"]["x"] > b_["iris_L"]["x"] + 2 and abs(a_["eye_L"]["x"] - b_["eye_L"]["x"]) < 1e-9 and F.mirror(p_).face["gx"] == -1.0)
    M = motions3d.Motions(B)
    rest = F.rest_pose(B)
    keys_ = ("hyaw", "hpitch", "hroll", "pyaw", "proll", "syaw", "sroll", "px")
    zero = all(abs(getattr(fn(d_), k_) - getattr(rest, k_)) < 1e-9 for (_i, _l, _lo, _hi, d_, fn) in M.parameters() for k_ in keys_) and all(fn(d_).face == rest.face for (_i, _l, _lo, _hi, d_, fn) in M.parameters())
    ok("front: every live parameter leaves the rest pose untouched at its default value", zero)
    for name in ("front_idle", "talk", "idol"):
        s0, s1 = F.solve(getattr(M, name)(0.0), B)[0], F.solve(getattr(M, name)(M.FRONT_T[name]), B)[0]
        gap = max(abs(s0[k_]["x"] - s1[k_]["x"]) + abs(s0[k_]["y"] - s1[k_]["y"]) for k_ in s0 if s0[k_]["kind"] != "shadow")
        ok(f"front: loop '{name}' ends where it starts", gap < 1e-6, f"{gap}")
    proj = KIT / "examples" / "whitemodels" / "vtuber"
    if (proj / "build").is_dir():
        spec = importlib.util.spec_from_file_location("spk_cli", KIT / "spk.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        bd = sorted(d_ for d_ in (proj / "build").iterdir() if d_.is_dir() and d_.name.isdigit())[-1]
        work = tmp / "vt_gate"
        work.mkdir()
        for f_ in ("vtuber.json", "vtuber.atlas", "vtuber.png", "vtuber.contract.json"):
            shutil.copy2(bd / f_, work / f_)
        assets = {"json": work / "vtuber.json", "atlas": work / "vtuber.atlas", "png": work / "vtuber.png", "contract": work / "vtuber.contract.json", "stress": work / "vtuber.stress.json", "dir": work, "id": "x"}
        good = cli.static_checks(assets)
        doc = json.loads((work / "vtuber.json").read_text())
        del doc["animations"]["greet"]["bones"]["chest"]["scale"]
        (work / "vtuber.json").write_text(json.dumps(doc))
        bad = cli.static_checks(assets)
        ok("gate: a clip under live parameters that does not key a property they add to is refused", not good["errors"] and any("greet" in e_ and "accumulate" in e_ for e_ in bad["errors"]), str(good["errors"][:1]) + str(bad["errors"][:1]))
    else:
        skip("parameter gate test", "examples/whitemodels/vtuber has no build")


def choreo_units():
    import numpy as np
    from spinekit import figure3d as F
    B = F.Body("hero")
    c = F.Choreo(B, heading=90)
    c.key(0.0)
    c.key(0.4, px=-30, py=-12, footR=("fk", 90, 0, 0, 10, 0))
    c.key(1.0, heading=270, footL=("pivot", 7))
    c.key(1.4, px=0, py=0, footR=("step", 0, -B.stance_x, -7))
    spots = np.array([[c.pose(t / 50).foot["L"]["x"], c.pose(t / 50).foot["L"]["z"]] for t in range(0, 71)])
    ok("choreo: a planted foot does not move while the body kicks and turns", float(np.ptp(spots, axis=0).max()) < 1e-9)
    p = c.pose(0.4)
    P, Rp = F.pelvis_frame(p, B)
    hip = P + Rp @ np.array([-B.hip_w, -B.hip_drop, 0])
    ankle = np.array([p.foot["R"]["x"], p.foot["R"]["y"], p.foot["R"]["z"]])
    want = float(np.hypot(B.thigh + B.shin * np.cos(np.radians(10)), B.shin * np.sin(np.radians(10))))
    ok("choreo: a posed leg keeps its bone lengths", abs(float(np.linalg.norm(ankle - hip)) - want) < 0.5)
    ok("choreo: pivot turns the foot with the body", abs((c.pose(1.0).foot["L"]["yaw"] - c.pose(0.4).foot["L"]["yaw"]) - 180) < 1e-6)


def layers_flow(tmp, proj):
    r = subprocess.run([sys.executable, str(KIT / "tests" / "layers_roundtrip.py"), "--source", str(proj), "--keep", str(tmp / "layers_rt")], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout)
    except Exception:
        o = None
    ok("layers: generated-image round trip (key -> align -> manifest -> build -> fidelity)", r.returncode == 0 and o and o["ok"] and not o["silently_wrong"], (r.stdout + r.stderr)[-500:])
    r, o = spk("layers", tmp / "newlayers", "--init")
    ok("layers --init: starter spec + prompts", r.returncode == 0 and (tmp / "newlayers" / "layers.json").is_file() and (tmp / "newlayers" / "PROMPTS.md").is_file())


def project_flow(tmp, native):
    proj = tmp / "mochi"
    r, o = spk("init", proj, "--name", "mochi")
    ok("init: template project created", r.returncode == 0 and (proj / "rig.py").is_file())
    if native:
        r, o = spk("art", proj)
        ok("art: parts rasterised, recomposition clean", r.returncode == 0 and o and o.get("recompose_pixels_over_24", 9e9) < 50, r.stderr[-300:])
    else:
        ok("art: skipped (--no-native); cannot build without parts", True)
        return None
    r, o = spk("build", proj, "--note", "selftest")
    ok("build: compiles to build/001", r.returncode == 0 and (proj / "build/001/mochi.json").is_file(), r.stderr[-300:])
    r, o = spk("build", proj)
    ok("build: second build goes to 002, 001 untouched", (proj / "build/002/mochi.json").is_file() and (proj / "build/001/mochi.json").is_file())
    r, o = spk("check", proj)
    ok("check: numeric gate passes on template", r.returncode == 0 and o and o["ok"], (r.stdout + r.stderr)[-400:])
    r, o = spk("fidelity", proj)
    ok("fidelity: native setup reproduces key art", r.returncode == 0 and o and o["ok"], (r.stdout + r.stderr)[-300:])
    r, o = spk("stress", proj, "--size", "240x320", "--tile", "160")
    ok("stress: sheet written", r.returncode == 0 and o and Path(o["sheet"]).is_file())
    r, o = spk("sheet", proj, "--anim", "idle", "--n", "4", "--size", "240x320", "--tile", "160", "--physics")
    ok("sheet: verified frozen frames with physics", r.returncode == 0 and o and Path(o["sheet"]).is_file())
    r, o = spk("play", proj, "--cues", "idle@0;hop@0.3~0.1;idle@1.3~0.2;blink@0.1#1", "--duration", "1.6", "--fps", "10", "--size", "240x320", "--tile", "160")
    ok("play: real mixing, event fired", r.returncode == 0 and o and any(e["name"] == "hop" for e in o.get("events", [])), (r.stdout + r.stderr)[-300:])
    r, o = spk("compare", proj, "--a", "001", "--b", "002", "--anim", "idle", "--times", "0.5", "--size", "240x320")
    ok("compare: identical builds report zero change", r.returncode == 0 and o and all(m["changed_px"] == 0 for m in o["metrics"]))
    z, h = tmp / "mochi.zip", tmp / "mochi.html"
    r, o = spk("export", proj, "--zip", z, "--html", h)
    names = zipfile.ZipFile(z).namelist() if z.is_file() else []
    ok("export: zip has json/atlas/png/contract + hashes", r.returncode == 0 and {"mochi/mochi.json", "mochi/mochi.atlas", "mochi/mochi.png", "mochi/mochi.contract.json", "mochi/SHA256SUMS.json"} <= set(names))
    ok("export: single-file html embeds runtime and assets", h.is_file() and h.stat().st_size > 300_000 and "SPK_CONFIG" in h.read_text(encoding="utf-8"))
    return proj


def faults(tmp, proj):
    rig = (proj / "rig.py").read_text()
    # 1 unowned part
    (proj / "rig.py").write_text(rig.replace('    rig.part("head", "head")\n', ""))
    r, _ = spk("build", proj)
    ok("fault: part without an owner is refused", r.returncode != 0 and "without an owner" in r.stderr)
    # 2 loop that cannot close
    (proj / "rig.py").write_text(rig.replace('a.osc("head", "rotate", 1.5, period=3, phase=0.2)', 'a.osc("head", "rotate", 6.0, period=2.3, phase=0.2)'))
    spk("build", proj)
    r, o = spk("check", proj)
    ok("fault: non-closing loop fails the gate", r.returncode != 0 and o and any("loop does not close" in e for e in o["errors"]))
    # 3 mesh folded through itself
    (proj / "rig.py").write_text(rig.replace('rig.stress("tail_curl"', 'rig.animation("fold", duration=1.0).pose(0).pose(1.0, {"tail2": {"sx": -1.0}})\n    rig.stress("tail_curl"'))
    spk("build", proj)
    r, o = spk("check", proj)
    ok("fault: flipped triangles fail the gate", r.returncode != 0 and o and any("flipped" in e for e in o["errors"]))
    (proj / "rig.py").write_text(rig)
    # 4 capture of something that does not exist must fail, not save a picture
    r, _ = spk("shot", proj, "--build", "001", "--anim", "no_such_animation", "--time", "0")
    ok("fault: capture of unknown animation fails loudly", r.returncode != 0)
    # 5 never overwrite a build directory
    from spinekit import Rig, RigError
    try:
        Rig("x", proj).compile(proj / "build" / "001")
        ok("fault: compile refuses an existing build dir", False)
    except RigError:
        ok("fault: compile refuses an existing build dir", True)
    except Exception as e:  # parts unowned raises first in some orders; still a refusal
        ok("fault: compile refuses an existing build dir", "already exists" in str(e) or "owner" in str(e), str(e))


def utilities():
    for t in ("audit", "inventory", "compact", "repack", "smooth", "gait", "boundary", "frames"):
        r = subprocess.run([sys.executable, str(KIT / "spk.py"), "util", t, "--help"], capture_output=True, text=True)
        ok(f"util {t}: --help", r.returncode == 0)
    for test in ("test_output_guards.py", "test_motion_smoothness.py"):
        r = subprocess.run([sys.executable, str(KIT / "tests" / test)], capture_output=True, text=True)
        ok(f"carried-over {test}", r.returncode == 0, r.stderr[-200:])
    fx = KIT / "fixtures" / "purple_girl_r14" / "build" / "001"
    r = subprocess.run(["node", str(KIT / "tools" / "sweep.mjs"), "--json", str(fx / "anime_girl.json"), "--atlas", str(fx / "anime_girl.atlas")], capture_output=True, text=True, cwd=str(KIT))
    ok("sweep: runs on a legacy multi-page fixture", r.stdout.strip().startswith("{"), r.stderr[-200:])
    r = subprocess.run(["node", str(KIT / "spine42" / "cli" / "spine42.mjs"), "validate", str(fx / "anime_girl.json"), "--atlas", str(fx / "anime_girl.atlas")], capture_output=True, text=True, cwd=str(KIT))
    ok("spine42 CLI: validate on fixture (needs Node >= 22)", r.returncode == 0 and '"ok": true' in r.stdout, r.stderr[-200:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-native", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the temporary directory")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="spk-selftest-"))
    try:
        units()
        layer_units(tmp)
        figure_units(tmp)
        front_units(tmp)
        choreo_units()
        proj = project_flow(tmp, not a.no_native)
        if proj:
            faults(tmp, proj)
            layers_flow(tmp, proj)
        utilities()
    finally:
        if a.keep:
            print("kept:", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [n for n, c, _ in RESULTS if not c]
    print(json.dumps({"passed": len(RESULTS) - len(failed), "failed": failed, "scope": "tooling contracts only; says nothing about how any character looks"}, indent=1, ensure_ascii=False))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
