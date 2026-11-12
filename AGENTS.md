# Agents: start at `SKILL.md`

This folder is one skill. Read `SKILL.md` first; it routes you to the single doc you need for the task.

- One command surface: `python3 spk.py <command>` (`python3 spk.py --help`).
- First time on a machine: `python3 spk.py doctor`.
- Self-test of the kit itself: `python3 tests/selftest.py`.
- Do not edit `node_modules/` (vendored, pinned runtime), `spine42/` (snapshot, see its PROVENANCE.md) or `fixtures/`.
- Character projects can live anywhere; create them with `python3 spk.py init <dir>`.
