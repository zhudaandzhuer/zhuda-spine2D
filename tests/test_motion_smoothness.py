"""Regression tests for the Spine temporal smoothness gate."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "py"))
import motion_smoothness as motion


def codes(report):
    return {item["code"] for item in report["issues"]}


class MotionSmoothnessTests(unittest.TestCase):
    def test_sparse_linear_reversal_is_rejected(self):
        data = {
            "animations": {
                "idle": {
                    "bones": {
                        "head": {
                            "translate": [
                                {"y": 0},
                                {"time": 1, "y": 3},
                                {"time": 2, "y": 0},
                            ]
                        }
                    }
                }
            }
        }
        report = motion.analyze(data)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("SPARSE_LINEAR_VELOCITY_JUMP", codes(report))

    def test_dense_60hz_sampled_motion_passes(self):
        keys = []
        for frame in range(121):
            t = frame / 60
            keys.append(
                {
                    "time": round(t, 6),
                    "y": round(1.5 * (1 - math.cos(math.pi * t)), 6),
                }
            )
        data = {"animations": {"idle": {"bones": {"head": {"translate": keys}}}}}
        report = motion.analyze(data)
        self.assertEqual(report["status"], "PASS", report["issues"])

    def test_low_rate_linear_deform_is_rejected(self):
        keys = []
        for frame in range(31):
            t = frame / 15
            keys.append(
                {
                    "time": round(t, 6),
                    "vertices": [round(math.sin(t), 6), round(math.cos(t), 6)],
                }
            )
        data = {
            "animations": {
                "idle": {
                    "attachments": {
                        "default": {
                            "body": {
                                "body": {
                                    "deform": keys
                                }
                            }
                        }
                    }
                }
            }
        }
        report = motion.analyze(data)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("LOW_RATE_LINEAR_DEFORM", codes(report))

    def test_sparse_authored_curve_is_not_forced_to_dense_keys(self):
        data = {
            "animations": {
                "greet": {
                    "bones": {
                        "arm": {
                            "rotate": [
                                {"value": 0, "curve": [0.25, 0, 0.75, 1]},
                                {"time": 0.8, "value": 35, "curve": [0.25, 0, 0.75, 1]},
                                {"time": 1.6, "value": 0},
                            ]
                        }
                    }
                }
            }
        }
        report = motion.analyze(data)
        self.assertEqual(report["status"], "PASS", report["issues"])

    def test_stepped_continuous_motion_is_rejected(self):
        data = {
            "animations": {
                "greet": {
                    "bones": {
                        "arm": {
                            "rotate": [
                                {"value": 0, "curve": "stepped"},
                                {"time": 0.4, "value": 25},
                            ]
                        }
                    }
                }
            }
        }
        report = motion.analyze(data)
        self.assertIn("STEPPED_CONTINUOUS_TRACK", codes(report))

    def test_non_monotonic_key_times_are_rejected(self):
        data = {
            "animations": {
                "broken": {
                    "bones": {
                        "root": {
                            "translate": [
                                {"time": 0, "x": 0},
                                {"time": 0.5, "x": 1},
                                {"time": 0.5, "x": 2},
                            ]
                        }
                    }
                }
            }
        }
        report = motion.analyze(data)
        self.assertIn("NON_MONOTONIC_TIME", codes(report))


if __name__ == "__main__":
    unittest.main()
