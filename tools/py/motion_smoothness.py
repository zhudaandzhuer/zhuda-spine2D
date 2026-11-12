#!/usr/bin/env python3
"""Conservative temporal smoothness gate for Spine JSON animation timelines.

The gate does not rewrite art or motion. It catches common sources of visible
stutter in generated rigs: stepped continuous tracks, low-rate baked deform
tracks, duplicate/non-monotonic key times, and sparse piecewise-linear velocity
jumps. Custom Spine curves are treated as authored interpolation and are not
forced to a particular key density.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

EPS = 1e-9


def _time(key: dict[str, Any]) -> float:
    return float(key.get("time", 0.0))


def _curve_kind(key: dict[str, Any]) -> str:
    if "curve" not in key:
        return "linear"
    return "stepped" if key.get("curve") == "stepped" else "custom"


def _timeline_times(keys: list[dict[str, Any]]) -> list[float]:
    return [_time(key) for key in keys]


def _issue(code: str, animation: str, track: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "animation": animation, "track": track, **details}


def _validate_times(
    animation: str,
    track: str,
    keys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    times = _timeline_times(keys)
    for index in range(1, len(times)):
        if not math.isfinite(times[index]) or not math.isfinite(times[index - 1]):
            issues.append(_issue("NON_FINITE_TIME", animation, track, index=index))
        elif times[index] <= times[index - 1]:
            issues.append(
                _issue(
                    "NON_MONOTONIC_TIME",
                    animation,
                    track,
                    index=index,
                    previous=times[index - 1],
                    current=times[index],
                )
            )
    return issues


def _dense_enough(times: list[float], target_fps: float) -> bool:
    if len(times) < 2:
        return True
    budget = 1.10 / target_fps
    return max(b - a for a, b in zip(times, times[1:])) <= budget + EPS


def _numeric_fields(kind: str, keys: list[dict[str, Any]]) -> list[tuple[str, float]]:
    if kind == "rotate":
        if any("value" in key for key in keys):
            return [("value", 0.0)]
        return [("angle", 0.0)]
    if kind == "translate":
        return [("x", 0.0), ("y", 0.0)]
    if kind == "scale":
        return [("x", 1.0), ("y", 1.0)]
    if kind == "shear":
        return [("x", 0.0), ("y", 0.0)]
    return []


def _linear_velocity_issues(
    animation: str,
    track: str,
    kind: str,
    keys: list[dict[str, Any]],
    target_fps: float,
) -> list[dict[str, Any]]:
    if len(keys) < 3:
        return []
    times = _timeline_times(keys)
    if any(b <= a for a, b in zip(times, times[1:])) or _dense_enough(times, target_fps):
        return []

    issues: list[dict[str, Any]] = []
    budget = 1.10 / target_fps
    for field, default in _numeric_fields(kind, keys):
        values = [float(key.get(field, default)) for key in keys]
        amplitude = max(values) - min(values)
        if amplitude <= 1e-6:
            continue
        slopes: list[float] = []
        for index in range(len(keys) - 1):
            dt = times[index + 1] - times[index]
            slopes.append((values[index + 1] - values[index]) / dt)
        for index in range(1, len(keys) - 1):
            # A curve on the outgoing key controls interpolation to the next key.
            left_kind = _curve_kind(keys[index - 1])
            right_kind = _curve_kind(keys[index])
            if left_kind != "linear" or right_kind != "linear":
                continue
            left_dt = times[index] - times[index - 1]
            right_dt = times[index + 1] - times[index]
            if min(left_dt, right_dt) <= budget:
                continue
            before, after = slopes[index - 1], slopes[index]
            scale = max(abs(before), abs(after), amplitude / max(times[-1] - times[0], EPS), EPS)
            jump_ratio = abs(after - before) / scale
            reverses = before * after <= 0 and abs(before - after) > EPS
            if jump_ratio >= 0.55 and (reverses or jump_ratio >= 0.85):
                issues.append(
                    _issue(
                        "SPARSE_LINEAR_VELOCITY_JUMP",
                        animation,
                        track,
                        field=field,
                        time=times[index],
                        beforeVelocity=round(before, 6),
                        afterVelocity=round(after, 6),
                        jumpRatio=round(jump_ratio, 4),
                    )
                )
    return issues


def _iter_deform_timelines(anim: dict[str, Any]) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    for skin, slots in anim.get("attachments", {}).items():
        if not isinstance(slots, dict):
            continue
        for slot, attachments in slots.items():
            if not isinstance(attachments, dict):
                continue
            for attachment, timeline in attachments.items():
                if isinstance(timeline, dict) and isinstance(timeline.get("deform"), list):
                    yield f"attachments/{skin}/{slot}/{attachment}/deform", timeline["deform"]

    # Older Spine JSON layout.
    for skin, slots in anim.get("deform", {}).items():
        if not isinstance(slots, dict):
            continue
        for slot, attachments in slots.items():
            if not isinstance(attachments, dict):
                continue
            for attachment, keys in attachments.items():
                if isinstance(keys, list):
                    yield f"deform/{skin}/{slot}/{attachment}", keys


def _deform_issues(
    animation: str,
    track: str,
    keys: list[dict[str, Any]],
    target_fps: float,
) -> list[dict[str, Any]]:
    issues = _validate_times(animation, track, keys)
    if len(keys) < 2 or issues:
        return issues
    times = _timeline_times(keys)
    for index, key in enumerate(keys[:-1]):
        if _curve_kind(key) == "stepped":
            issues.append(
                _issue(
                    "STEPPED_CONTINUOUS_TRACK",
                    animation,
                    track,
                    index=index,
                    time=times[index],
                )
            )
    if len(keys) >= 4 and all(_curve_kind(key) == "linear" for key in keys[:-1]):
        gaps = [b - a for a, b in zip(times, times[1:])]
        max_gap = max(gaps)
        if max_gap > 1.10 / target_fps + EPS:
            median_gap = statistics.median(gaps)
            issues.append(
                _issue(
                    "LOW_RATE_LINEAR_DEFORM",
                    animation,
                    track,
                    keys=len(keys),
                    medianFPS=round(1.0 / median_gap, 3) if median_gap > EPS else None,
                    maxGapSeconds=round(max_gap, 6),
                    targetFPS=target_fps,
                )
            )
    return issues


def analyze(data: dict[str, Any], target_fps: float = 60.0) -> dict[str, Any]:
    if not math.isfinite(target_fps) or target_fps < 24 or target_fps > 240:
        raise ValueError("target_fps must be between 24 and 240")

    issues: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    animations = data.get("animations", {})
    if not isinstance(animations, dict):
        raise ValueError("animations must be an object")

    for animation, anim in animations.items():
        if not isinstance(anim, dict):
            continue
        bones = anim.get("bones", {})
        if isinstance(bones, dict):
            for bone, timelines in bones.items():
                if not isinstance(timelines, dict):
                    continue
                for kind in ("rotate", "translate", "scale", "shear"):
                    keys = timelines.get(kind)
                    if not isinstance(keys, list) or not keys:
                        continue
                    track = f"bones/{bone}/{kind}"
                    issues.extend(_validate_times(animation, track, keys))
                    if len(keys) >= 2:
                        times = _timeline_times(keys)
                        if all(b > a for a, b in zip(times, times[1:])):
                            gaps = [b - a for a, b in zip(times, times[1:])]
                            metrics.append(
                                {
                                    "animation": animation,
                                    "track": track,
                                    "keys": len(keys),
                                    "maxGapSeconds": round(max(gaps), 6),
                                    "customCurveSegments": sum(_curve_kind(k) == "custom" for k in keys[:-1]),
                                }
                            )
                    for index, key in enumerate(keys[:-1]):
                        if _curve_kind(key) == "stepped":
                            issues.append(
                                _issue(
                                    "STEPPED_CONTINUOUS_TRACK",
                                    animation,
                                    track,
                                    index=index,
                                    time=_time(key),
                                )
                            )
                    issues.extend(_linear_velocity_issues(animation, track, kind, keys, target_fps))

        for track, keys in _iter_deform_timelines(anim):
            issues.extend(_deform_issues(animation, track, keys, target_fps))
            if len(keys) >= 2:
                times = _timeline_times(keys)
                if all(b > a for a, b in zip(times, times[1:])):
                    gaps = [b - a for a, b in zip(times, times[1:])]
                    metrics.append(
                        {
                            "animation": animation,
                            "track": track,
                            "keys": len(keys),
                            "maxGapSeconds": round(max(gaps), 6),
                            "customCurveSegments": sum(_curve_kind(k) == "custom" for k in keys[:-1]),
                        }
                    )

    return {
        "status": "PASS" if not issues else "FAIL",
        "targetFPS": target_fps,
        "animations": len(animations),
        "issues": issues,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skeleton", type=Path)
    parser.add_argument("--target-fps", type=float, default=60.0)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--warn-only", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.skeleton.read_text())
    report = analyze(data, args.target_fps)
    report["input"] = str(args.skeleton)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" or args.warn_only else 2


if __name__ == "__main__":
    sys.exit(main())
