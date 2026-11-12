# Third-party components

| Component | Version | Where | License |
|---|---|---|---|
| Spine Runtimes (spine-core, spine-webgl) | 4.2.119 | `node_modules/@esotericsoftware/` (JS only; source maps and type declarations removed) | Spine Runtimes License Agreement — `node_modules/@esotericsoftware/spine-core/LICENSE`. Integrating the runtimes requires each user to hold their own Spine Editor license; redistribution must keep the license and copyright notice. |
| pngjs | 7.0.0 | `node_modules/pngjs/` | MIT — `node_modules/pngjs/LICENSE` |
| Playwright (not bundled) | ≥ 1.55 | resolved at run time (`PLAYWRIGHT_MODULE`, kit `node_modules`, global npm) | Apache-2.0 |

`spk export --html` inlines the Spine WebGL runtime into the exported file together with its license notice.
Fixtures under `fixtures/` are the owner's own regression characters (the Alice artwork derives from John Tenniel's public-domain illustrations).
