# spine42 CLI — provenance

Snapshot of the agent-facing CLI and libraries of **Zhuda Spine Workstation** (`projects/Spine研發基地/workstation`).

- upstream commit: `1ce9e6f` ("fix(spine-runtime): persist rig sidecars and exact loop endpoints"), 85 commits, **with the uncommitted working-tree changes present on 2026-10-03** in `cli/softwareRenderFrame.mjs`, `src/core/editorCommands.ts`, `src/lib/animationOps.js`, `src/lib/artPack.js`, `src/lib/semanticRig.js`
- copied: `cli/*.mjs`, `src/lib/*.js`, `src/core/*.ts` — byte-identical to that working tree
- not copied: the GUI (`index.html`, `src/main.js`, `src/style.css`), its ~150 UI/corpus tests, `dist/`, `node_modules/`, the corpora the tests need

The workstation repository stays the source of truth for this code. Update this folder by re-copying from it; do not develop here.

Runs on the kit's vendored runtime (`node_modules/@esotericsoftware/*` 4.2.119, `pngjs` 7). Needs Node ≥ 22 (imports `.ts` directly).
`render-frame` in browser mode needs `playwright-core`; in this kit use `python3 spk.py shot` instead.
