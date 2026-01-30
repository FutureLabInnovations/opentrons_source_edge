#!/usr/bin/env python3
"""
OT-2 Motion Accuracy and Repeatability Test Script
===================================================
Tests gantry motion accuracy, repeatability, and identifies potential issues.

Usage (on robot via SSH):
    python3 ot2_motion_test.py                     # Run all tests
    python3 ot2_motion_test.py --test repeatability
    python3 ot2_motion_test.py --test accuracy
    python3 ot2_motion_test.py --test speed
    python3 ot2_motion_test.py --iterations 10     # More test iterations
"""

import asyncio
import argparse
import json
import sys
import time
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.types import Axis
    from opentrons.types import Mount, Point
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Tests will be simulated.")


class MotionTest:
    """Motion accuracy and repeatability testing class."""

    # Standard test positions (deck coordinates in mm)
    TEST_POSITIONS = {
        "slot_1_center": Point(x=64.88, y=42.74, z=100),
        "slot_5_center": Point(x=181.0, y=181.0, z=100),
        "slot_9_center": Point(x=297.12, y=319.26, z=100),
        "slot_11_center": Point(x=64.88, y=319.26, z=100),
        "slot_3_center": Point(x=297.12, y=42.74, z=100),
        "center_deck": Point(x=181.0, y=181.0, z=100),
    }

    # Homed positions for comparison
    EXPECTED_HOME = {
        Axis.X: 418.0,
        Axis.Y: 353.0,
        Axis.Z: 218.0,
        Axis.A: 218.0,
    }

    def __init__(self, mount: Mount = Mount.LEFT):
        self.mount = mount
        self.api: Optional[API] = None
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "mount": mount.name,
            "tests": {},
            "warnings": [],
            "errors": []
        }

    async def initialize(self) -> bool:
        """Initialize hardware connection."""
        if not ON_ROBOT:
            print("Simulation mode - no hardware connection")
            return False

        try:
            self.api = await API.build_hardware_controller()
            await self.api.home()
            print("Hardware initialized and homed")
            return True
        except Exception as e:
            self.results["errors"].append(f"Initialization failed: {e}")
            print(f"ERROR: Failed to initialize hardware: {e}")
            return False

    async def get_current_position(self) -> Dict[Axis, float]:
        """Get current machine position."""
        if not self.api:
            return {}
        return await self.api.current_position(mount=self.mount, refresh=True)

    async def test_homing_accuracy(self) -> Dict[str, Any]:
        """Test homing repeatability and accuracy."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("HOMING ACCURACY TEST")
        print("-" * 40)

        try:
            iterations = 5
            home_positions = []

            for i in range(iterations):
                # Move away from home
                await self.api.move_rel(
                    mount=self.mount,
                    delta=Point(-50, -50, -50)
                )

                # Home again
                await self.api.home()

                # Record position
                pos = await self.get_current_position()
                home_positions.append({
                    "X": pos.get(Axis.X, 0),
                    "Y": pos.get(Axis.Y, 0),
                    "Z": pos.get(Axis.Z, 0),
                    "A": pos.get(Axis.A, 0)
                })
                print(f"  Iteration {i + 1}: X={pos.get(Axis.X):.3f} Y={pos.get(Axis.Y):.3f} Z={pos.get(Axis.Z):.3f}")

            # Calculate statistics
            axes_stats = {}
            for axis in ["X", "Y", "Z", "A"]:
                values = [p[axis] for p in home_positions]
                expected = self.EXPECTED_HOME.get(Axis[axis], 0)

                axes_stats[axis] = {
                    "expected": expected,
                    "mean": statistics.mean(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "range": max(values) - min(values),
                    "error_from_expected": abs(statistics.mean(values) - expected)
                }

            result["data"] = {
                "iterations": iterations,
                "positions": home_positions,
                "statistics": axes_stats
            }

            # Check tolerances
            max_range = max(s["range"] for s in axes_stats.values())
            max_error = max(s["error_from_expected"] for s in axes_stats.values())

            print(f"\n  Statistics:")
            for axis, stats in axes_stats.items():
                print(f"    {axis}: mean={stats['mean']:.3f}, stdev={stats['stdev']:.4f}, range={stats['range']:.4f}")

            if max_range < 0.1 and max_error < 1.0:
                result["status"] = "PASS"
                print(f"\n  Homing accuracy: PASS (range < 0.1mm, error < 1.0mm)")
            elif max_range < 0.5 and max_error < 2.0:
                result["status"] = "WARNING"
                print(f"\n  Homing accuracy: WARNING (range {max_range:.3f}mm)")
                self.results["warnings"].append(f"Homing repeatability slightly degraded: {max_range:.3f}mm range")
            else:
                result["status"] = "FAIL"
                print(f"\n  Homing accuracy: FAIL (range {max_range:.3f}mm)")
                self.results["errors"].append(f"Poor homing repeatability: {max_range:.3f}mm range")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Homing test: FAIL - {e}")
            self.results["errors"].append(f"Homing test failed: {e}")

        self.results["tests"]["homing_accuracy"] = result
        return result

    async def test_position_repeatability(self, iterations: int = 10) -> Dict[str, Any]:
        """Test position repeatability by moving to same point multiple times."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print(f"POSITION REPEATABILITY TEST ({iterations} iterations)")
        print("-" * 40)

        try:
            target = self.TEST_POSITIONS["center_deck"]
            home_position = self.TEST_POSITIONS["slot_1_center"] + Point(0, 0, 50)

            measured_positions = []

            for i in range(iterations):
                # Move to home position
                await self.api.move_to(mount=self.mount, abs_position=home_position)

                # Move to target
                await self.api.move_to(mount=self.mount, abs_position=target)

                # Record position
                pos = await self.get_current_position()
                measured = {
                    "X": pos.get(Axis.X, 0),
                    "Y": pos.get(Axis.Y, 0),
                    "Z": pos.get(Axis.Z, 0)
                }
                measured_positions.append(measured)

                if (i + 1) % 5 == 0:
                    print(f"  Completed {i + 1}/{iterations} iterations")

            # Calculate statistics
            stats = {}
            for axis in ["X", "Y", "Z"]:
                values = [p[axis] for p in measured_positions]
                stats[axis] = {
                    "mean": statistics.mean(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "range": max(values) - min(values)
                }

            result["data"] = {
                "target": {"x": target.x, "y": target.y, "z": target.z},
                "iterations": iterations,
                "statistics": stats
            }

            # Calculate 3D repeatability (RMS of ranges)
            repeatability_3d = (stats["X"]["range"]**2 + stats["Y"]["range"]**2 + stats["Z"]["range"]**2)**0.5

            print(f"\n  Results:")
            print(f"    X: mean={stats['X']['mean']:.4f}, stdev={stats['X']['stdev']:.5f}, range={stats['X']['range']:.5f}")
            print(f"    Y: mean={stats['Y']['mean']:.4f}, stdev={stats['Y']['stdev']:.5f}, range={stats['Y']['range']:.5f}")
            print(f"    Z: mean={stats['Z']['mean']:.4f}, stdev={stats['Z']['stdev']:.5f}, range={stats['Z']['range']:.5f}")
            print(f"    3D repeatability: {repeatability_3d:.5f} mm")

            result["data"]["repeatability_3d_mm"] = repeatability_3d

            if repeatability_3d < 0.1:
                result["status"] = "PASS"
                print(f"\n  Repeatability test: PASS (<0.1mm)")
            elif repeatability_3d < 0.3:
                result["status"] = "WARNING"
                print(f"\n  Repeatability test: WARNING ({repeatability_3d:.3f}mm)")
                self.results["warnings"].append(f"Position repeatability slightly degraded: {repeatability_3d:.3f}mm")
            else:
                result["status"] = "FAIL"
                print(f"\n  Repeatability test: FAIL ({repeatability_3d:.3f}mm)")
                self.results["errors"].append(f"Poor position repeatability: {repeatability_3d:.3f}mm")

            # Return home
            await self.api.home()

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Repeatability test: FAIL - {e}")
            self.results["errors"].append(f"Repeatability test failed: {e}")

        self.results["tests"]["position_repeatability"] = result
        return result

    async def test_cross_deck_accuracy(self) -> Dict[str, Any]:
        """Test accuracy across the entire deck area."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("CROSS-DECK ACCURACY TEST")
        print("-" * 40)

        try:
            measurements = []

            for name, target in self.TEST_POSITIONS.items():
                print(f"  Moving to {name}...")

                # Move to position
                await self.api.move_to(mount=self.mount, abs_position=target)

                # Get actual position
                pos = await self.get_current_position()
                actual = Point(
                    x=pos.get(Axis.X, 0),
                    y=pos.get(Axis.Y, 0),
                    z=pos.get(Axis.Z, 0)
                )

                # Calculate error
                error_x = actual.x - target.x
                error_y = actual.y - target.y
                error_z = actual.z - target.z
                error_3d = (error_x**2 + error_y**2 + error_z**2)**0.5

                measurement = {
                    "position": name,
                    "target": {"x": target.x, "y": target.y, "z": target.z},
                    "actual": {"x": actual.x, "y": actual.y, "z": actual.z},
                    "error": {"x": error_x, "y": error_y, "z": error_z, "3d": error_3d}
                }
                measurements.append(measurement)

                print(f"    Target: ({target.x:.1f}, {target.y:.1f}, {target.z:.1f})")
                print(f"    Actual: ({actual.x:.3f}, {actual.y:.3f}, {actual.z:.3f})")
                print(f"    Error:  ({error_x:.4f}, {error_y:.4f}, {error_z:.4f}) 3D: {error_3d:.4f}mm")

            # Calculate overall statistics
            errors_3d = [m["error"]["3d"] for m in measurements]
            max_error = max(errors_3d)
            mean_error = statistics.mean(errors_3d)

            result["data"] = {
                "measurements": measurements,
                "max_error_3d_mm": max_error,
                "mean_error_3d_mm": mean_error
            }

            print(f"\n  Summary:")
            print(f"    Max 3D error: {max_error:.4f} mm")
            print(f"    Mean 3D error: {mean_error:.4f} mm")

            if max_error < 1.0:
                result["status"] = "PASS"
                print(f"\n  Cross-deck accuracy: PASS (<1.0mm)")
            elif max_error < 2.0:
                result["status"] = "WARNING"
                print(f"\n  Cross-deck accuracy: WARNING ({max_error:.3f}mm)")
                self.results["warnings"].append(f"Cross-deck accuracy degraded: {max_error:.3f}mm max error")
            else:
                result["status"] = "FAIL"
                print(f"\n  Cross-deck accuracy: FAIL ({max_error:.3f}mm)")
                self.results["errors"].append(f"Poor cross-deck accuracy: {max_error:.3f}mm max error")

            # Return home
            await self.api.home()

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Cross-deck test: FAIL - {e}")
            self.results["errors"].append(f"Cross-deck test failed: {e}")

        self.results["tests"]["cross_deck_accuracy"] = result
        return result

    async def test_speed_accuracy(self) -> Dict[str, Any]:
        """Test movement timing at different speeds."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("SPEED ACCURACY TEST")
        print("-" * 40)

        try:
            start_pos = Point(x=100, y=100, z=100)
            end_pos = Point(x=300, y=300, z=100)
            distance = ((end_pos.x - start_pos.x)**2 + (end_pos.y - start_pos.y)**2)**0.5

            speeds = [100, 200, 300, 400, 500]  # mm/s
            timing_results = []

            for speed in speeds:
                # Move to start
                await self.api.move_to(mount=self.mount, abs_position=start_pos)

                # Time the move
                start_time = time.time()
                await self.api.move_to(mount=self.mount, abs_position=end_pos, speed=speed)
                elapsed = time.time() - start_time

                actual_speed = distance / elapsed if elapsed > 0 else 0
                speed_error = abs(actual_speed - speed) / speed * 100

                timing = {
                    "requested_speed": speed,
                    "distance_mm": distance,
                    "elapsed_time_s": elapsed,
                    "actual_speed": actual_speed,
                    "speed_error_percent": speed_error
                }
                timing_results.append(timing)

                print(f"  Speed {speed} mm/s: actual={actual_speed:.1f} mm/s, error={speed_error:.1f}%")

            result["data"] = {
                "distance_mm": distance,
                "timing_results": timing_results
            }

            # Check speed accuracy
            max_error = max(t["speed_error_percent"] for t in timing_results)

            if max_error < 10:
                result["status"] = "PASS"
                print(f"\n  Speed accuracy: PASS (<10% error)")
            elif max_error < 20:
                result["status"] = "WARNING"
                print(f"\n  Speed accuracy: WARNING ({max_error:.1f}% max error)")
                self.results["warnings"].append(f"Speed accuracy slightly off: {max_error:.1f}% max error")
            else:
                result["status"] = "FAIL"
                print(f"\n  Speed accuracy: FAIL ({max_error:.1f}% max error)")
                self.results["errors"].append(f"Poor speed accuracy: {max_error:.1f}% max error")

            await self.api.home()

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Speed test: FAIL - {e}")
            self.results["errors"].append(f"Speed test failed: {e}")

        self.results["tests"]["speed_accuracy"] = result
        return result

    async def test_limit_switches(self) -> Dict[str, Any]:
        """Test all limit switches."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("LIMIT SWITCH TEST")
        print("-" * 40)

        try:
            # Home first
            await self.api.home()

            # Check switches at home
            switches = await self.api._backend._smoothie_driver.switch_state()

            result["data"]["switch_states"] = switches

            print("  Switch states (at home position):")
            all_triggered = True
            for axis, state in switches.items():
                status = "TRIGGERED" if state else "OPEN"
                print(f"    {axis}: {status}")
                if not state and axis in ["X", "Y", "Z", "A"]:
                    all_triggered = False

            if all_triggered:
                result["status"] = "PASS"
                print("\n  Limit switches: PASS (all triggered at home)")
            else:
                result["status"] = "FAIL"
                print("\n  Limit switches: FAIL (not all triggered at home)")
                self.results["errors"].append("Not all limit switches triggered at home position")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Limit switch test: FAIL - {e}")
            self.results["errors"].append(f"Limit switch test failed: {e}")

        self.results["tests"]["limit_switches"] = result
        return result

    async def run_all_tests(self, iterations: int = 10) -> Dict[str, Any]:
        """Run all motion tests."""
        print("\n" + "=" * 60)
        print("OT-2 MOTION ACCURACY AND REPEATABILITY TEST")
        print("=" * 60)

        if not await self.initialize():
            return self.results

        await self.test_limit_switches()
        await self.test_homing_accuracy()
        await self.test_position_repeatability(iterations)
        await self.test_cross_deck_accuracy()
        await self.test_speed_accuracy()

        # Generate summary
        self.generate_summary()
        return self.results

    def generate_summary(self):
        """Generate test summary."""
        total = len(self.results["tests"])
        passed = sum(1 for t in self.results["tests"].values() if t.get("status") == "PASS")
        failed = sum(1 for t in self.results["tests"].values() if t.get("status") == "FAIL")
        warnings = sum(1 for t in self.results["tests"].values() if t.get("status") == "WARNING")

        self.results["summary"] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "overall": "PASS" if failed == 0 else "FAIL"
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Total tests: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Warnings: {warnings}")
        print(f"  Overall: {self.results['summary']['overall']}")

        if self.results["warnings"]:
            print("\n  Warnings:")
            for w in self.results["warnings"]:
                print(f"    - {w}")

        if self.results["errors"]:
            print("\n  Errors:")
            for e in self.results["errors"]:
                print(f"    - {e}")

        print("=" * 60)

    def save_report(self, filepath: Optional[str] = None):
        """Save test report to file."""
        if filepath is None:
            filepath = f"/data/motion_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\nReport saved to: {filepath}")
        except Exception as e:
            print(f"Failed to save report: {e}")


async def main():
    parser = argparse.ArgumentParser(description="OT-2 Motion Accuracy Test")
    parser.add_argument("--mount", choices=["left", "right"], default="left",
                        help="Mount to use for testing (default: left)")
    parser.add_argument("--test", choices=["homing", "repeatability", "accuracy", "speed", "switches", "all"],
                        default="all", help="Specific test to run (default: all)")
    parser.add_argument("--iterations", type=int, default=10,
                        help="Number of iterations for repeatability test (default: 10)")

    args = parser.parse_args()

    mount = Mount.LEFT if args.mount == "left" else Mount.RIGHT
    tester = MotionTest(mount)

    if not await tester.initialize():
        print("Failed to initialize, exiting")
        return 1

    if args.test == "all":
        await tester.run_all_tests(args.iterations)
    elif args.test == "homing":
        await tester.test_homing_accuracy()
    elif args.test == "repeatability":
        await tester.test_position_repeatability(args.iterations)
    elif args.test == "accuracy":
        await tester.test_cross_deck_accuracy()
    elif args.test == "speed":
        await tester.test_speed_accuracy()
    elif args.test == "switches":
        await tester.test_limit_switches()

    tester.generate_summary()
    tester.save_report()

    return 0 if tester.results.get("summary", {}).get("overall") != "FAIL" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
