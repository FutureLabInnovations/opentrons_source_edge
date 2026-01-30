#!/usr/bin/env python3
"""
OT-2 Pipette Maintenance and Accuracy Test Script
==================================================
Tests pipette functionality, accuracy, and performs maintenance procedures.

Usage (on robot via SSH):
    python3 ot2_pipette_test.py --mount left
    python3 ot2_pipette_test.py --mount right --test plunger
    python3 ot2_pipette_test.py --mount left --test accuracy --volume 100

Tests available:
    - info: Display pipette information and calibration status
    - plunger: Test plunger movement and motor
    - tip: Test tip pickup and drop
    - accuracy: Test aspiration/dispense accuracy (requires tips)
    - unstick: Run plunger unsticking procedure
    - all: Run all tests
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.types import Axis, CriticalPoint
    from opentrons.types import Mount, Point
    from opentrons.config import get_opentrons_path
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Tests will be simulated.")


class PipetteTest:
    """Pipette maintenance and testing class."""

    def __init__(self, mount: Mount):
        self.mount = mount
        self.api: Optional[API] = None
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "mount": mount.name,
            "tests": {},
            "pipette_info": {},
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
            print(f"Hardware initialized, homed successfully")
            return True
        except Exception as e:
            self.results["errors"].append(f"Initialization failed: {e}")
            print(f"ERROR: Failed to initialize hardware: {e}")
            return False

    async def get_pipette_info(self) -> Dict[str, Any]:
        """Get detailed pipette information."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        try:
            instruments = self.api.attached_instruments
            pipette_info = instruments.get(self.mount)

            if not pipette_info:
                result["status"] = "FAIL"
                result["error"] = f"No pipette attached on {self.mount.name} mount"
                self.results["errors"].append(result["error"])
                return result

            # Extract pipette details
            result["data"] = {
                "model": pipette_info.get("model", "unknown"),
                "name": pipette_info.get("name", "unknown"),
                "pipette_id": pipette_info.get("pipette_id", "unknown"),
                "min_volume": pipette_info.get("min_volume", 0),
                "max_volume": pipette_info.get("max_volume", 0),
                "channels": pipette_info.get("channels", 1),
                "tip_length": pipette_info.get("tip_length", 0),
                "has_tip": pipette_info.get("has_tip", False),
                "aspirate_flow_rate": pipette_info.get("aspirate_flow_rate", 0),
                "dispense_flow_rate": pipette_info.get("dispense_flow_rate", 0),
            }

            # Get calibration status
            try:
                from opentrons.calibration_storage import ot2 as cal_storage
                pip_id = pipette_info.get("pipette_id")
                if pip_id:
                    offset = cal_storage.get_pipette_offset(pip_id, self.mount)
                    if offset:
                        result["data"]["calibration"] = {
                            "offset": list(offset.offset),
                            "source": str(offset.source),
                            "last_modified": str(offset.last_modified) if offset.last_modified else None
                        }
                    else:
                        result["data"]["calibration"] = {"status": "not calibrated"}
                        self.results["warnings"].append(f"Pipette {pip_id} not calibrated")
            except Exception as e:
                result["data"]["calibration"] = {"error": str(e)}

            self.results["pipette_info"] = result["data"]
            result["status"] = "PASS"

            # Print info
            print("\n" + "=" * 50)
            print(f"PIPETTE INFORMATION - {self.mount.name.upper()} MOUNT")
            print("=" * 50)
            for key, value in result["data"].items():
                if key != "calibration":
                    print(f"  {key}: {value}")
            if "calibration" in result["data"]:
                print(f"  calibration: {json.dumps(result['data']['calibration'], indent=4)}")
            print("=" * 50)

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            self.results["errors"].append(f"Failed to get pipette info: {e}")

        self.results["tests"]["pipette_info"] = result
        return result

    async def test_plunger(self) -> Dict[str, Any]:
        """Test plunger movement."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("PLUNGER TEST")
        print("-" * 40)

        try:
            # Get current plunger position
            pos_before = await self.api.current_position(mount=self.mount)
            plunger_axis = Axis.of_plunger(self.mount)
            plunger_pos_before = pos_before.get(plunger_axis, 0)

            print(f"  Initial plunger position: {plunger_pos_before:.3f} mm")

            # Home plunger
            print("  Homing plunger...")
            await self.api.home_plunger(self.mount)

            pos_after_home = await self.api.current_position(mount=self.mount)
            plunger_pos_after_home = pos_after_home.get(plunger_axis, 0)
            print(f"  Position after home: {plunger_pos_after_home:.3f} mm")

            # Get pipette for plunger positions
            pipette = self.api.hardware_pipettes[self.mount]
            if pipette:
                positions = pipette.plunger_positions
                print(f"  Plunger positions:")
                print(f"    Top: {positions.top:.3f} mm")
                print(f"    Bottom: {positions.bottom:.3f} mm")
                print(f"    Blow out: {positions.blow_out:.3f} mm")
                print(f"    Drop tip: {positions.drop_tip:.3f} mm")

                # Move to bottom position
                print("  Moving to bottom position...")
                await self.api.prepare_for_aspirate(self.mount)

                pos_at_bottom = await self.api.current_position(mount=self.mount)
                plunger_pos_bottom = pos_at_bottom.get(plunger_axis, 0)
                print(f"  Position at bottom: {plunger_pos_bottom:.3f} mm")

                result["data"] = {
                    "home_position": plunger_pos_after_home,
                    "bottom_position": plunger_pos_bottom,
                    "plunger_range": abs(plunger_pos_after_home - plunger_pos_bottom),
                    "plunger_positions": {
                        "top": positions.top,
                        "bottom": positions.bottom,
                        "blow_out": positions.blow_out,
                        "drop_tip": positions.drop_tip
                    }
                }

            # Home again
            await self.api.home_plunger(self.mount)
            result["status"] = "PASS"
            print("  Plunger test: PASS")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Plunger test: FAIL - {e}")
            self.results["errors"].append(f"Plunger test failed: {e}")

        self.results["tests"]["plunger"] = result
        return result

    async def test_tip_pickup_drop(self, tiprack_position: Optional[Point] = None) -> Dict[str, Any]:
        """Test tip pickup and drop functionality."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("TIP PICKUP/DROP TEST")
        print("-" * 40)

        # Default tiprack position (slot 1, A1)
        if tiprack_position is None:
            tiprack_position = Point(x=14.38, y=74.24, z=64.69)

        try:
            pipette = self.api.hardware_pipettes[self.mount]
            if not pipette:
                result["status"] = "FAIL"
                result["error"] = "No pipette attached"
                return result

            # Check if tip already attached
            if pipette.has_tip:
                print("  WARNING: Tip already attached, dropping first...")
                await self.api.drop_tip(self.mount)

            print(f"  Moving to tiprack position: {tiprack_position}")
            await self.api.move_to(
                mount=self.mount,
                abs_position=tiprack_position + Point(0, 0, 20)  # 20mm above
            )

            print("  MANUAL STEP: Please place tiprack in slot 1")
            print("  Press Enter when ready to pick up tip (or 'skip' to skip)...")

            user_input = input("  > ").strip().lower()
            if user_input == "skip":
                result["status"] = "SKIPPED"
                result["message"] = "User skipped tip test"
                print("  Tip test skipped")
                return result

            # Pick up tip
            print("  Picking up tip...")
            default_tip_length = 50.0  # Default tip length in mm

            await self.api.move_to(
                mount=self.mount,
                abs_position=tiprack_position
            )

            await self.api.pick_up_tip(
                mount=self.mount,
                tip_length=default_tip_length,
                presses=1,
                increment=0
            )

            # Verify tip attached
            if pipette.has_tip:
                print("  Tip pickup: SUCCESS")
                result["data"]["tip_pickup"] = "success"
            else:
                print("  Tip pickup: FAILED - no tip detected")
                result["data"]["tip_pickup"] = "failed"

            # Move up
            await self.api.move_rel(
                mount=self.mount,
                delta=Point(0, 0, 50)
            )

            # Drop tip
            print("  Dropping tip...")
            await self.api.drop_tip(self.mount)

            if not pipette.has_tip:
                print("  Tip drop: SUCCESS")
                result["data"]["tip_drop"] = "success"
            else:
                print("  Tip drop: FAILED - tip still detected")
                result["data"]["tip_drop"] = "failed"

            # Home after test
            await self.api.home()

            if result["data"].get("tip_pickup") == "success" and result["data"].get("tip_drop") == "success":
                result["status"] = "PASS"
                print("  Tip test: PASS")
            else:
                result["status"] = "FAIL"
                print("  Tip test: FAIL")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Tip test: FAIL - {e}")
            self.results["errors"].append(f"Tip test failed: {e}")

        self.results["tests"]["tip_pickup_drop"] = result
        return result

    async def test_unstick_plunger(self) -> Dict[str, Any]:
        """Run plunger unsticking procedure."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print("PLUNGER UNSTICK PROCEDURE")
        print("-" * 40)

        try:
            # Get smoothie driver
            driver = self.api._backend._smoothie_driver

            # Determine axis
            axis = "B" if self.mount == Mount.LEFT else "C"
            print(f"  Running unstick on axis {axis}...")
            print("  (Moving plunger slowly with high current to break static friction)")

            await driver.unstick_axes(
                axes=axis,
                distance=1.0,  # 1mm movement
                speed=1.0      # 1mm/s very slow
            )

            print("  Unstick procedure complete")
            print("  Homing plunger...")

            await self.api.home_plunger(self.mount)

            result["status"] = "PASS"
            result["data"] = {
                "axis": axis,
                "distance": 1.0,
                "speed": 1.0
            }
            print("  Unstick test: PASS")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Unstick test: FAIL - {e}")
            self.results["errors"].append(f"Unstick procedure failed: {e}")

        self.results["tests"]["unstick"] = result
        return result

    async def test_accuracy(self, volume: float = 100.0) -> Dict[str, Any]:
        """Test aspiration/dispense accuracy."""
        result = {"status": "UNKNOWN", "data": {}}

        if not self.api:
            result["status"] = "SKIPPED"
            return result

        print("\n" + "-" * 40)
        print(f"ACCURACY TEST - {volume} µL")
        print("-" * 40)

        try:
            pipette = self.api.hardware_pipettes[self.mount]
            if not pipette:
                result["status"] = "FAIL"
                result["error"] = "No pipette attached"
                return result

            # Check volume is within range
            max_vol = pipette.working_volume
            min_vol = pipette.min_volume

            if volume > max_vol:
                result["status"] = "FAIL"
                result["error"] = f"Volume {volume}µL exceeds pipette max {max_vol}µL"
                return result

            if volume < min_vol:
                result["status"] = "FAIL"
                result["error"] = f"Volume {volume}µL below pipette min {min_vol}µL"
                return result

            print(f"  Pipette range: {min_vol} - {max_vol} µL")
            print(f"  Test volume: {volume} µL")

            # Check for tip
            if not pipette.has_tip:
                print("  WARNING: No tip attached. Pick up a tip first.")
                print("  Press Enter after picking up tip (or 'skip' to skip)...")
                user_input = input("  > ").strip().lower()
                if user_input == "skip":
                    result["status"] = "SKIPPED"
                    return result

            # Prepare for aspirate
            print("  Preparing for aspirate...")
            await self.api.prepare_for_aspirate(self.mount)

            # Get plunger position before aspirate
            plunger_axis = Axis.of_plunger(self.mount)
            pos_before = await self.api.current_position(mount=self.mount)
            plunger_before = pos_before.get(plunger_axis, 0)

            # Aspirate
            print(f"  Aspirating {volume} µL...")
            await self.api.aspirate(mount=self.mount, volume=volume)

            pos_after_asp = await self.api.current_position(mount=self.mount)
            plunger_after_asp = pos_after_asp.get(plunger_axis, 0)

            plunger_travel_asp = abs(plunger_after_asp - plunger_before)
            print(f"  Plunger travel during aspirate: {plunger_travel_asp:.4f} mm")

            # Dispense
            print(f"  Dispensing {volume} µL...")
            await self.api.dispense(mount=self.mount, volume=volume)

            pos_after_disp = await self.api.current_position(mount=self.mount)
            plunger_after_disp = pos_after_disp.get(plunger_axis, 0)

            plunger_travel_disp = abs(plunger_after_disp - plunger_after_asp)
            print(f"  Plunger travel during dispense: {plunger_travel_disp:.4f} mm")

            # Calculate accuracy
            travel_difference = abs(plunger_travel_asp - plunger_travel_disp)
            accuracy_percent = (1 - (travel_difference / plunger_travel_asp)) * 100 if plunger_travel_asp > 0 else 0

            result["data"] = {
                "volume_tested": volume,
                "plunger_travel_aspirate_mm": round(plunger_travel_asp, 4),
                "plunger_travel_dispense_mm": round(plunger_travel_disp, 4),
                "travel_difference_mm": round(travel_difference, 4),
                "mechanical_accuracy_percent": round(accuracy_percent, 2)
            }

            print(f"\n  Results:")
            print(f"    Aspirate travel: {plunger_travel_asp:.4f} mm")
            print(f"    Dispense travel: {plunger_travel_disp:.4f} mm")
            print(f"    Difference: {travel_difference:.4f} mm")
            print(f"    Mechanical accuracy: {accuracy_percent:.2f}%")

            if accuracy_percent >= 99.0:
                result["status"] = "PASS"
                print("  Accuracy test: PASS")
            elif accuracy_percent >= 95.0:
                result["status"] = "WARNING"
                print("  Accuracy test: WARNING (95-99%)")
                self.results["warnings"].append(f"Accuracy slightly degraded: {accuracy_percent:.2f}%")
            else:
                result["status"] = "FAIL"
                print(f"  Accuracy test: FAIL (<95%)")
                self.results["errors"].append(f"Poor accuracy: {accuracy_percent:.2f}%")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Accuracy test: FAIL - {e}")
            self.results["errors"].append(f"Accuracy test failed: {e}")

        self.results["tests"]["accuracy"] = result
        return result

    async def run_all_tests(self, volume: float = 100.0) -> Dict[str, Any]:
        """Run all pipette tests."""
        print("\n" + "=" * 60)
        print(f"OT-2 PIPETTE MAINTENANCE TEST - {self.mount.name.upper()} MOUNT")
        print("=" * 60)

        if not await self.initialize():
            return self.results

        await self.get_pipette_info()
        await self.test_plunger()
        await self.test_unstick_plunger()
        await self.test_tip_pickup_drop()
        await self.test_accuracy(volume)

        # Summary
        self.generate_summary()
        return self.results

    def generate_summary(self):
        """Generate test summary."""
        total = len(self.results["tests"])
        passed = sum(1 for t in self.results["tests"].values() if t.get("status") == "PASS")
        failed = sum(1 for t in self.results["tests"].values() if t.get("status") == "FAIL")
        warnings = sum(1 for t in self.results["tests"].values() if t.get("status") == "WARNING")
        skipped = sum(1 for t in self.results["tests"].values() if t.get("status") == "SKIPPED")

        self.results["summary"] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "skipped": skipped,
            "overall": "PASS" if failed == 0 else "FAIL"
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Total tests: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Warnings: {warnings}")
        print(f"  Skipped: {skipped}")
        print(f"  Overall: {self.results['summary']['overall']}")
        print("=" * 60)

    def save_report(self, filepath: Optional[str] = None):
        """Save test report to file."""
        if filepath is None:
            filepath = f"/data/pipette_test_{self.mount.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\nReport saved to: {filepath}")
        except Exception as e:
            print(f"Failed to save report: {e}")


async def main():
    parser = argparse.ArgumentParser(description="OT-2 Pipette Maintenance Test")
    parser.add_argument("--mount", choices=["left", "right"], default="left",
                        help="Pipette mount to test (default: left)")
    parser.add_argument("--test", choices=["info", "plunger", "tip", "accuracy", "unstick", "all"],
                        default="all", help="Test to run (default: all)")
    parser.add_argument("--volume", type=float, default=100.0,
                        help="Volume for accuracy test in µL (default: 100)")

    args = parser.parse_args()

    mount = Mount.LEFT if args.mount == "left" else Mount.RIGHT
    tester = PipetteTest(mount)

    if not await tester.initialize():
        print("Failed to initialize, exiting")
        return 1

    if args.test == "all":
        await tester.run_all_tests(args.volume)
    elif args.test == "info":
        await tester.get_pipette_info()
    elif args.test == "plunger":
        await tester.test_plunger()
    elif args.test == "tip":
        await tester.test_tip_pickup_drop()
    elif args.test == "accuracy":
        await tester.test_accuracy(args.volume)
    elif args.test == "unstick":
        await tester.test_unstick_plunger()

    tester.save_report()

    return 0 if tester.results.get("summary", {}).get("overall") != "FAIL" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
