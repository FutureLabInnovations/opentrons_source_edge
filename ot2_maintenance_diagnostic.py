#!/usr/bin/env python3
"""
OT-2 Maintenance Diagnostic Script
===================================
Run this script on your OT-2 to perform a comprehensive diagnostic check.

Usage (on robot via SSH):
    python3 ot2_maintenance_diagnostic.py

Or via Jupyter notebook on the robot.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Check if running on actual robot
try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.types import Axis
    from opentrons.types import Mount, Point
    from opentrons.config import get_opentrons_path
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Some tests will be simulated.")


class OT2Diagnostic:
    """Comprehensive OT-2 diagnostic class."""

    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "warnings": [],
            "errors": [],
            "summary": {}
        }
        self.api: Optional[API] = None

    async def initialize(self) -> bool:
        """Initialize hardware connection."""
        if not ON_ROBOT:
            self.results["warnings"].append("Running in simulation mode")
            return False

        try:
            self.api = await API.build_hardware_controller()
            self.results["tests"]["initialization"] = {"status": "PASS", "message": "Hardware initialized"}
            return True
        except Exception as e:
            self.results["tests"]["initialization"] = {"status": "FAIL", "error": str(e)}
            self.results["errors"].append(f"Failed to initialize hardware: {e}")
            return False

    async def test_firmware_version(self) -> Dict[str, Any]:
        """Check firmware versions."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                fw_version = await self.api._backend._smoothie_driver.get_fw_version()
                result["data"]["smoothie_version"] = fw_version
                result["status"] = "PASS"
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"
            result["message"] = "No hardware connection"

        self.results["tests"]["firmware_version"] = result
        return result

    async def test_homing(self) -> Dict[str, Any]:
        """Test homing all axes."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                await self.api.home()
                position = await self.api.current_position(mount=Mount.LEFT)
                result["data"]["position_after_home"] = {
                    str(k): v for k, v in position.items()
                }
                result["status"] = "PASS"
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"

        self.results["tests"]["homing"] = result
        return result

    async def test_limit_switches(self) -> Dict[str, Any]:
        """Check limit switch states."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                switches = await self.api._backend._smoothie_driver.switch_state()
                result["data"]["switches"] = switches
                # After homing, all switches should be triggered
                all_homed = all(switches.values())
                result["status"] = "PASS" if all_homed else "WARNING"
                if not all_homed:
                    unhomed = [k for k, v in switches.items() if not v]
                    result["warning"] = f"Axes not at home: {unhomed}"
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"

        self.results["tests"]["limit_switches"] = result
        return result

    async def test_movement(self) -> Dict[str, Any]:
        """Test basic movement functionality."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                # Move to center of deck
                await self.api.move_to(
                    mount=Mount.LEFT,
                    abs_position=Point(200, 150, 100)
                )
                pos1 = await self.api.current_position(mount=Mount.LEFT)

                # Move relative
                await self.api.move_rel(
                    mount=Mount.LEFT,
                    delta=Point(10, 10, -10)
                )
                pos2 = await self.api.current_position(mount=Mount.LEFT)

                # Return home
                await self.api.home()

                result["data"]["test_positions"] = {
                    "center": {str(k): v for k, v in pos1.items()},
                    "after_rel_move": {str(k): v for k, v in pos2.items()}
                }
                result["status"] = "PASS"
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"

        self.results["tests"]["movement"] = result
        return result

    async def test_attached_instruments(self) -> Dict[str, Any]:
        """Check attached pipettes."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                instruments = self.api.attached_instruments
                result["data"]["instruments"] = {}

                for mount, info in instruments.items():
                    if info:
                        result["data"]["instruments"][mount.name] = {
                            "model": info.get("model", "unknown"),
                            "name": info.get("name", "unknown"),
                            "pipette_id": info.get("pipette_id", "unknown"),
                            "tip_length": info.get("tip_length", 0)
                        }

                if result["data"]["instruments"]:
                    result["status"] = "PASS"
                else:
                    result["status"] = "WARNING"
                    result["warning"] = "No pipettes attached"
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"

        self.results["tests"]["attached_instruments"] = result
        return result

    def test_calibration_files(self) -> Dict[str, Any]:
        """Check calibration file status."""
        result = {"status": "UNKNOWN", "data": {}}

        try:
            cal_paths = {
                "deck_calibration": Path("/data/opentrons/robot/deck_calibration.json"),
                "pipette_calibration_dir": Path("/data/opentrons/robot/pipettes"),
                "tip_lengths_dir": Path("/data/opentrons/tip_lengths")
            }

            result["data"]["calibration_files"] = {}

            for name, path in cal_paths.items():
                if path.exists():
                    if path.is_file():
                        with open(path) as f:
                            data = json.load(f)
                        result["data"]["calibration_files"][name] = {
                            "exists": True,
                            "last_modified": data.get("last_modified", "unknown"),
                            "source": data.get("source", "unknown")
                        }
                    else:
                        # Directory
                        files = list(path.glob("**/*.json"))
                        result["data"]["calibration_files"][name] = {
                            "exists": True,
                            "file_count": len(files)
                        }
                else:
                    result["data"]["calibration_files"][name] = {"exists": False}

            # Check if deck calibration exists
            if result["data"]["calibration_files"].get("deck_calibration", {}).get("exists"):
                result["status"] = "PASS"
            else:
                result["status"] = "WARNING"
                result["warning"] = "Deck calibration not found"
                self.results["warnings"].append("Deck calibration file missing")
        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)

        self.results["tests"]["calibration_files"] = result
        return result

    async def test_attached_modules(self) -> Dict[str, Any]:
        """Check attached modules."""
        result = {"status": "UNKNOWN", "data": {}}

        if self.api:
            try:
                modules = self.api.attached_modules
                result["data"]["modules"] = []

                for module in modules:
                    module_info = {
                        "type": module.name(),
                        "serial": module.device_info.get("serial", "unknown"),
                        "model": module.model(),
                        "firmware_version": module.device_info.get("version", "unknown")
                    }

                    # Get module-specific status
                    if hasattr(module, "temperature"):
                        module_info["temperature"] = module.temperature
                    if hasattr(module, "target"):
                        module_info["target_temperature"] = module.target
                    if hasattr(module, "status"):
                        module_info["status"] = module.status

                    result["data"]["modules"].append(module_info)

                result["status"] = "PASS"
                result["data"]["module_count"] = len(modules)
            except Exception as e:
                result["status"] = "FAIL"
                result["error"] = str(e)
        else:
            result["status"] = "SKIPPED"

        self.results["tests"]["attached_modules"] = result
        return result

    def test_system_info(self) -> Dict[str, Any]:
        """Gather system information."""
        result = {"status": "PASS", "data": {}}

        try:
            # Read version file if available
            version_file = Path("/etc/VERSION.json")
            if version_file.exists():
                with open(version_file) as f:
                    result["data"]["version"] = json.load(f)

            # Check disk space
            import shutil
            total, used, free = shutil.disk_usage("/data")
            result["data"]["disk_space"] = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "percent_used": round((used / total) * 100, 1)
            }

            if result["data"]["disk_space"]["percent_used"] > 90:
                result["status"] = "WARNING"
                result["warning"] = "Disk space low"
                self.results["warnings"].append("Disk space usage above 90%")
        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)

        self.results["tests"]["system_info"] = result
        return result

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all diagnostic tests."""
        print("=" * 60)
        print("OT-2 MAINTENANCE DIAGNOSTIC")
        print("=" * 60)
        print(f"Started at: {self.results['timestamp']}")
        print()

        # Initialize
        print("Initializing hardware...")
        await self.initialize()
        print()

        # Run tests
        tests = [
            ("Firmware Version", self.test_firmware_version),
            ("System Info", lambda: asyncio.coroutine(lambda: self.test_system_info())()),
            ("Calibration Files", lambda: asyncio.coroutine(lambda: self.test_calibration_files())()),
            ("Attached Instruments", self.test_attached_instruments),
            ("Attached Modules", self.test_attached_modules),
            ("Homing", self.test_homing),
            ("Limit Switches", self.test_limit_switches),
            ("Movement", self.test_movement),
        ]

        for test_name, test_func in tests:
            print(f"Running: {test_name}...", end=" ")
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                    if asyncio.iscoroutine(result):
                        result = await result
                status = result.get("status", "UNKNOWN")
                print(f"[{status}]")
            except Exception as e:
                print(f"[ERROR: {e}]")
                self.results["errors"].append(f"{test_name}: {e}")

        # Generate summary
        self.generate_summary()

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.results['summary']['total_tests']}")
        print(f"Passed: {self.results['summary']['passed']}")
        print(f"Warnings: {self.results['summary']['warnings']}")
        print(f"Failed: {self.results['summary']['failed']}")
        print(f"Skipped: {self.results['summary']['skipped']}")
        print()

        if self.results["warnings"]:
            print("WARNINGS:")
            for w in self.results["warnings"]:
                print(f"  - {w}")
            print()

        if self.results["errors"]:
            print("ERRORS:")
            for e in self.results["errors"]:
                print(f"  - {e}")
            print()

        overall = "PASS" if self.results['summary']['failed'] == 0 else "FAIL"
        print(f"Overall Status: {overall}")

        return self.results

    def generate_summary(self):
        """Generate test summary."""
        summary = {
            "total_tests": 0,
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "skipped": 0
        }

        for test_name, test_result in self.results["tests"].items():
            summary["total_tests"] += 1
            status = test_result.get("status", "UNKNOWN")
            if status == "PASS":
                summary["passed"] += 1
            elif status == "WARNING":
                summary["warnings"] += 1
            elif status == "FAIL":
                summary["failed"] += 1
            elif status == "SKIPPED":
                summary["skipped"] += 1

        self.results["summary"] = summary

    def save_report(self, filepath: str = "/data/maintenance_report.json"):
        """Save diagnostic report to file."""
        try:
            with open(filepath, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"Report saved to: {filepath}")
        except Exception as e:
            print(f"Failed to save report: {e}")


async def main():
    """Main entry point."""
    diagnostic = OT2Diagnostic()
    results = await diagnostic.run_all_tests()

    # Save report
    diagnostic.save_report()

    # Return exit code based on results
    if results["summary"]["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
