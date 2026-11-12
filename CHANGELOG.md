# Changelog

## 2.7.0 — 2026-11-12 · front-facing performers: showcase characters and streamers

- New white model `vtuber`: a face made of parts on the head (eyes with open / half / closed images, iris gaze, brows, nose, mouth shapes, blush, fringe), nine camera-facing clips (`front_idle`, `talk`, `idol`, `greet`, `bow`, `cheer`, `present`, `heart`, `spin`), twelve live parameters, hair links simulated by the runtime.
- Engine: surface face parts, state slots and alpha slots, `rchain` (runtime-physics chains under a baked anchor), parameter clips (`param=True`: deltas from the rest pose, no draw order, no tint), `key_all=True` for clips that parameters are laid over.
- Viewer: parameter tracks (additive, time = value), drivers (pointer follow, idle wander, automatic blink, talking mouth, expressions), camera presets.
- `spk check`: a clip must key every property a parameter clip adds to (found the hard way: without it the chest shrank to a sliver within seconds of live use).
- The enclosing rule now also orders the setup pose (`heroine`, `mage` rebuilt); the reach guard handles feet placed relative to the body.

## 2.6.0 — 2026-11-12 · shield warrior and mage

- Two more white models: `knight` (shield with eight views, sword blade, pauldrons, plume; block / slash / bash) and `mage` (pointed hat, robe that encloses the legs, wide sleeves, tall staff; cast / channel).
- Engine: carry poses (`HOLDS`) for whatever a body holds; class actions that keep the same arm when facing left; `encloses` (limbs inside a robe or sleeve never draw above it); tubes drawn at true length; plates use their edge-on view only near edge-on; facing read from the more level axis; long-axis alignment and a shear clamp for slivers.
- Fixed: the enclosing rule iterated a set, so two builds of the same model could differ in draw order. Now reproducible under any hash seed.
- All seven models rebuilt; self-test 72 checks.

## 2.5.0 — 2026-11-12 · five skinnable white models

- `figure3d` rewritten as a white-model engine: body presets (`hero`, `heroine`, `chibi`, `brute`, `mascot`), add-ons (rigid parts, simulated chains, cloth panels, a skirt cone pushed by the thighs, a bag on a strap), **eight view images** for head / chest / pelvis / feet with automatic switching (hysteresis + minimum dwell), content-aware ellipse mapping, reach guard, key reduction, bake report.
- `motions3d`: the whole clip set (idle, walk, run, jump, wave, pick, turn, turntable, kung-fu, dance) scales with the body.
- Asymmetric bodies face left through `_L` clip variants instead of mirroring; viewer and gait gate understand both modes.
- Skins: `spk skin` (templates + spec + guide), `spk skin --debug` (direction-stamped skin), `spk reskin` (validates and packs an alternate atlas; mirrors missing left views; `--fill`), global `--skin NAME` for every render/export command.
- Fixed: a stepped key and the key after it could trade places when times were not on the 4-decimal grid (the new value was lost). Regression test added.
- `spk check` reports which slot hitches at a loop seam; draw-order keys list only moving slots.
- `examples/mannequin` removed (superseded by `examples/whitemodels`).

## 2.4.0 — 2026-11-11 · choreography: kung-fu and dance

- `figure3d.Choreo`: pose-to-pose keys in 3D. Planted feet are world IK targets (they cannot slide), free legs are posed by joint angles and blended in world space with their knee direction, pivots turn a foot in place, the body's ground point can travel. Arrival easing per key (`snap` for strikes). `reach_report()` lists moments a foot target is beyond the leg.
- `examples/mannequin`: `kungfu` (stance, jab, cross, front kick, roundhouse, spinning back kick, bow-stance punch, walk back; 6.1 s) and `dance` (side steps, reach, a full turn on one foot, pose, sway; 6.6 s).
- Leg IK accepts an explicit knee direction (`pole`).
- Not done: motion-capture import. Hand-keying is the limit on how complex a routine gets.

## 2.3.0 — 2026-11-11 · motion authored in 3D, baked to 2D

- `spinekit.figure3d`: pose a ball-and-tube human in 3D (joint angles, leg IK on the ground), project every frame, and bake a flat Spine rig: translate / rotate / scale / shear per part, draw order by camera depth, depth tint. One texture set serves every view angle.
- New example `examples/mannequin`: white mannequin with `idle, walk, run, jump, wave, pick, turn, turntable` (walk seen through 360 degrees). The turn is a real stepping rotation through the front view.
- Compiler: shear timelines, slot colour keys (`Animation.color`), complete draw-order keys (`Animation.draw_order_list`).
- `spk play --start-x / --facing`; the viewer starts scripted playback at an offset.
- Honest scope: this answers "the motion was ugly" with a neutral figure whose motion comes from body mechanics. It does not make the earlier drawn characters prettier.

## 2.2.0 — 2026-11-11 · locomotion: walk, wave, turn

- New example `examples/xiaoshuang`: a full-body chibi character drawn in code (35 parts) with two-bone IK legs, head and torso pseudo-3D turning, 38 physics constraints, and `idle / walk / wave / turn / blink`.
- Facing is controller state: the `turn` clip passes through a left-right symmetric pose and fires `flip`; the controller mirrors the skeleton (`events.<name>.action = "toggle_facing"`). No paper-flip.
- Contract: `animations.<name>.speed` + `.feet` (in-place locomotion), `patrol`, `frame_portrait`. The viewer moves the skeleton, mirrors it on the event, resets physics, and has a walk-back-and-forth demo.
- `spk check` gait gate: per planted foot, stance share and skate distance per stance (error above 3 px).
- Compiler: constraints are emitted in declaration order across types (IK before a foot-levelling transform). Existing example rebuilt byte-identical.

## 2.1.0 — 2026-11-11 · generated / painted images → parts

- `spk layers`: one spec (`layers.json`) turns generated or painted pictures into the same `parts/` folder `spk art` writes — chroma key (colour-difference matte: antialiased edges, wide soft fades, blurry blobs), visibility-aware registration to the key art (front-to-back, with weak-constraint warnings and a manual `place` override), polygon cutting with holes and feather, edge fades, `@part` pixel-identical reuse, despeckle, recomposition check.
- Hidden-area audit for both art paths: `seam_candidates` (visibly adjacent parts whose lower one does not continue underneath, with what would show in the gap) and `coverage.png`.
- `spk key` (single-image keying with a dark/light/green check view; detects baked checkerboards) and `spk grid` (labelled pixel grid for reading polygon coordinates).
- `templates/imagegen/`: prompt templates per layer and a half-body `layers.json` starter; `spk layers DIR --init`.
- `docs/15-imagegen-layers.md`; self-test grows from 36 to 49 checks; `tests/layers_roundtrip.py`.
- Validated with synthetic stand-ins (existing parts re-rendered on chroma with drift), **not** with real image-model output — see the doc's last section.
- Known limit, found by looking at the result: single-colour keying cannot recover colours inside wide translucent areas (a blurred pink mouth on green came out olive). The tool measures and warns (`translucent_share`); the rule is opaque layers, soft details cut from the key art.

## 2.0.0 — 2026-11-11 · reorganised for agents

- One entry point (`SKILL.md`) and one CLI (`spk.py`) replace four overlapping knowledge trees and fifteen loose scripts.
- New from-zero compiler `spinekit`: bones, alpha-culled grid meshes, analytic weight fields, look/gaze controllers (transform constraints), Spine 4.2 physics, layered animation with exact bezier export, atlas packing with transparent-RGB bleed, controller contract.
- New procedural art path (`spinekit.svgart` + `spk art`) alongside the existing layered-PNG path.
- Native capture rewritten: offline vendored runtime, verified renderer state per frame, frozen seeks with deterministic physics, real AnimationState playback (`spk play`), art-space close-ups (`--frame`), before/after (`spk compare`), key-art fidelity gate (`spk fidelity`).
- Numeric gate `spk check`: structure, weights, flips/collapse by slot+attachment identity, loop seam position and velocity, time-stepped physics, real mixes.
- Project template with BRIEF / WORKLOG, per-build immutable outputs, evidence folders.
- Carried over unchanged: audit, inventory, compact, repack, smoothness, gait, boundary, frame-compare utilities; spine42 CLI snapshot; three regression characters.
- Validated end to end on `examples/shuang` (76 bones, 21 weighted meshes, 12 transform constraints, 49 physics constraints, 11 animations).

Earlier history (2026-08 … 2026-10: build-spine-character, spine2d-master vNext merge, workstation 0.4 → 1.0-dev) lives in the original `spine2D/` folder; see `MIGRATION.md`.
