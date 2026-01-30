#!/usr/bin/env python3
"""
OT-2 Module Maintenance and Diagnostic Script
==============================================
Tests all attached modules: Temperature Module, Magnetic Module,
Thermocycler, and Heater-Shaker.

Usage (on robot via SSH):
    python3 ot2_module_test.py                    # Test all modules
    python3 ot2_module_test.py --type temperature # Test only temp modules
    python3 ot2_module_test.py --type magnetic    # Test only mag modules
    python3 ot2_module_test.py --type thermocycler
    python3 ot2_module_test.py --type heater-shaker
"""

import asyncio
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.modules import (
        MagDeck, TempDeck, Thermocycler, HeaterShaker
    )
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Tests will be simulated.")


class ModuleTest:
    """Module maintenance and testing class."""

    def __init__(self):
        self.api: Optional[API] = None
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "modules": [],
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
            print("Hardware initialized successfully")
            return True
        except Exception as e:
            self.results["errors"].append(f"Initialization failed: {e}")
            print(f"ERROR: Failed to initialize hardware: {e}")
            return False

    async def discover_modules(self) -> List[Dict[str, Any]]:
        """Discover and list all attached modules."""
        modules_info = []

        if not self.api:
            return modules_info

        print("\n" + "=" * 60)
        print("DISCOVERING ATTACHED MODULES")
        print("=" * 60)

        try:
            modules = self.api.attached_modules

            if not modules:
                print("  No modules detected")
                self.results["warnings"].append("No modules attached")
                return modules_info

            for i, module in enumerate(modules):
                info = {
                    "index": i,
                    "type": module.name(),
                    "model": module.model(),
                    "serial": module.device_info.get("serial", "unknown"),
                    "firmware_version": module.device_info.get("version", "unknown"),
                    "port": module.port,
                    "usb_port": getattr(module, "usb_port", None)
                }

                # Get module-specific status
                if hasattr(module, "temperature"):
                    info["current_temperature"] = module.temperature
                if hasattr(module, "target"):
                    info["target_temperature"] = module.target
                if hasattr(module, "status"):
                    info["status"] = module.status
                if hasattr(module, "speed"):
                    info["speed"] = module.speed
                if hasattr(module, "lid_status"):
                    info["lid_status"] = module.lid_status

                modules_info.append(info)

                print(f"\n  Module {i + 1}: {info['type']}")
                print(f"    Model: {info['model']}")
                print(f"    Serial: {info['serial']}")
                print(f"    Firmware: {info['firmware_version']}")
                print(f"    Port: {info['port']}")
                if "current_temperature" in info:
                    print(f"    Temperature: {info['current_temperature']}°C")
                if "status" in info:
                    print(f"    Status: {info['status']}")

            self.results["modules"] = modules_info
            print(f"\n  Total modules found: {len(modules_info)}")

        except Exception as e:
            print(f"  ERROR discovering modules: {e}")
            self.results["errors"].append(f"Module discovery failed: {e}")

        return modules_info

    async def test_temperature_module(self, module) -> Dict[str, Any]:
        """Test Temperature Module functionality."""
        result = {"status": "UNKNOWN", "data": {}, "module_serial": module.device_info.get("serial")}

        print("\n" + "-" * 40)
        print(f"TEMPERATURE MODULE TEST - {module.device_info.get('serial', 'unknown')}")
        print("-" * 40)

        try:
            # Get current state
            current_temp = module.temperature
            target_temp = module.target
            status = module.status

            result["data"]["initial_state"] = {
                "temperature": current_temp,
                "target": target_temp,
                "status": status
            }
            print(f"  Current temperature: {current_temp}°C")
            print(f"  Target temperature: {target_temp}°C")
            print(f"  Status: {status}")

            # Test temperature set (room temp - safe)
            test_temp = 25.0
            print(f"\n  Setting temperature to {test_temp}°C...")

            await module.start_set_temperature(test_temp)
            await asyncio.sleep(2)

            new_target = module.target
            print(f"  New target: {new_target}°C")

            if abs(new_target - test_temp) < 0.5:
                print("  Temperature set command: PASS")
                result["data"]["set_temperature_test"] = "pass"
            else:
                print("  Temperature set command: FAIL")
                result["data"]["set_temperature_test"] = "fail"

            # Deactivate
            print("  Deactivating heater...")
            await module.deactivate()
            await asyncio.sleep(1)

            final_status = module.status
            print(f"  Final status: {final_status}")

            result["data"]["final_state"] = {
                "temperature": module.temperature,
                "target": module.target,
                "status": final_status
            }

            # Check for temperature sensor accuracy
            if current_temp is not None and 10 <= current_temp <= 45:
                result["status"] = "PASS"
                print("  Temperature Module test: PASS")
            else:
                result["status"] = "WARNING"
                result["warning"] = f"Temperature reading unusual: {current_temp}°C"
                print(f"  Temperature Module test: WARNING - unusual reading {current_temp}°C")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Temperature Module test: FAIL - {e}")
            self.results["errors"].append(f"Temperature module test failed: {e}")

        return result

    async def test_magnetic_module(self, module) -> Dict[str, Any]:
        """Test Magnetic Module functionality."""
        result = {"status": "UNKNOWN", "data": {}, "module_serial": module.device_info.get("serial")}

        print("\n" + "-" * 40)
        print(f"MAGNETIC MODULE TEST - {module.device_info.get('serial', 'unknown')}")
        print("-" * 40)

        try:
            # Get current state
            status = module.status
            current_height = getattr(module, "current_height", None)

            result["data"]["initial_state"] = {
                "status": status,
                "height": current_height
            }
            print(f"  Status: {status}")
            print(f"  Current height: {current_height}")

            # Test engage/disengage cycle
            print("\n  Testing engage...")
            await module.engage(height_from_base=10.0)
            await asyncio.sleep(2)

            engaged_status = module.status
            print(f"  Status after engage: {engaged_status}")

            if "engaged" in engaged_status.lower():
                result["data"]["engage_test"] = "pass"
                print("  Engage test: PASS")
            else:
                result["data"]["engage_test"] = "warning"
                print("  Engage test: WARNING")

            # Disengage
            print("  Testing disengage...")
            await module.deactivate()
            await asyncio.sleep(2)

            disengaged_status = module.status
            print(f"  Status after disengage: {disengaged_status}")

            if "disengaged" in disengaged_status.lower():
                result["data"]["disengage_test"] = "pass"
                print("  Disengage test: PASS")
            else:
                result["data"]["disengage_test"] = "warning"
                print("  Disengage test: WARNING")

            result["data"]["final_state"] = {
                "status": disengaged_status
            }

            if result["data"].get("engage_test") == "pass" and result["data"].get("disengage_test") == "pass":
                result["status"] = "PASS"
                print("  Magnetic Module test: PASS")
            else:
                result["status"] = "WARNING"
                print("  Magnetic Module test: WARNING")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Magnetic Module test: FAIL - {e}")
            self.results["errors"].append(f"Magnetic module test failed: {e}")

        return result

    async def test_thermocycler(self, module) -> Dict[str, Any]:
        """Test Thermocycler functionality."""
        result = {"status": "UNKNOWN", "data": {}, "module_serial": module.device_info.get("serial")}

        print("\n" + "-" * 40)
        print(f"THERMOCYCLER TEST - {module.device_info.get('serial', 'unknown')}")
        print("-" * 40)

        try:
            # Get current state
            lid_status = module.lid_status
            lid_temp = module.lid_temp
            plate_temp = module.temperature
            lid_target = module.lid_target
            plate_target = module.target
            status = module.status

            result["data"]["initial_state"] = {
                "lid_status": lid_status,
                "lid_temperature": lid_temp,
                "plate_temperature": plate_temp,
                "lid_target": lid_target,
                "plate_target": plate_target,
                "status": status
            }

            print(f"  Lid status: {lid_status}")
            print(f"  Lid temperature: {lid_temp}°C")
            print(f"  Plate temperature: {plate_temp}°C")
            print(f"  Status: {status}")

            # Test lid open/close
            print("\n  Testing lid movement...")

            if lid_status != "open":
                print("  Opening lid...")
                await module.open_lid()
                await asyncio.sleep(3)

            new_lid_status = module.lid_status
            print(f"  Lid status: {new_lid_status}")

            if new_lid_status == "open":
                result["data"]["lid_open_test"] = "pass"
                print("  Lid open test: PASS")
            else:
                result["data"]["lid_open_test"] = "fail"
                print("  Lid open test: FAIL")

            print("  Closing lid...")
            await module.close_lid()
            await asyncio.sleep(3)

            closed_status = module.lid_status
            print(f"  Lid status: {closed_status}")

            if closed_status == "closed":
                result["data"]["lid_close_test"] = "pass"
                print("  Lid close test: PASS")
            else:
                result["data"]["lid_close_test"] = "fail"
                print("  Lid close test: FAIL")

            # Open lid again for safety
            await module.open_lid()

            # Deactivate all
            print("  Deactivating heaters...")
            await module.deactivate_lid()
            await module.deactivate_block()

            result["data"]["final_state"] = {
                "lid_status": module.lid_status,
                "lid_temperature": module.lid_temp,
                "plate_temperature": module.temperature
            }

            # Determine overall result
            if (result["data"].get("lid_open_test") == "pass" and
                result["data"].get("lid_close_test") == "pass"):
                result["status"] = "PASS"
                print("  Thermocycler test: PASS")
            else:
                result["status"] = "FAIL"
                print("  Thermocycler test: FAIL")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Thermocycler test: FAIL - {e}")
            self.results["errors"].append(f"Thermocycler test failed: {e}")

        return result

    async def test_heater_shaker(self, module) -> Dict[str, Any]:
        """Test Heater-Shaker functionality."""
        result = {"status": "UNKNOWN", "data": {}, "module_serial": module.device_info.get("serial")}

        print("\n" + "-" * 40)
        print(f"HEATER-SHAKER TEST - {module.device_info.get('serial', 'unknown')}")
        print("-" * 40)

        try:
            # Get current state
            temperature = module.temperature
            target_temp = module.target_temperature
            speed = module.speed
            target_speed = module.target_speed
            labware_latch = module.labware_latch_status
            status = module.status

            result["data"]["initial_state"] = {
                "temperature": temperature,
                "target_temperature": target_temp,
                "speed": speed,
                "target_speed": target_speed,
                "labware_latch": labware_latch,
                "status": status
            }

            print(f"  Temperature: {temperature}°C")
            print(f"  Speed: {speed} RPM")
            print(f"  Labware latch: {labware_latch}")
            print(f"  Status: {status}")

            # Test labware latch
            print("\n  Testing labware latch...")

            print("  Opening latch...")
            await module.open_labware_latch()
            await asyncio.sleep(2)

            if module.labware_latch_status == "idle_open":
                result["data"]["latch_open_test"] = "pass"
                print("  Latch open: PASS")
            else:
                result["data"]["latch_open_test"] = "fail"
                print("  Latch open: FAIL")

            print("  Closing latch...")
            await module.close_labware_latch()
            await asyncio.sleep(2)

            if module.labware_latch_status == "idle_closed":
                result["data"]["latch_close_test"] = "pass"
                print("  Latch close: PASS")
            else:
                result["data"]["latch_close_test"] = "fail"
                print("  Latch close: FAIL")

            # Brief shake test (low speed, short duration)
            print("\n  Testing shake function (200 RPM for 3 seconds)...")
            print("  WARNING: Ensure labware is secured!")

            user_input = input("  Press Enter to test shake, or 'skip' to skip: ").strip().lower()

            if user_input != "skip":
                await module.set_speed(rpm=200)
                await asyncio.sleep(3)

                current_speed = module.speed
                print(f"  Current speed: {current_speed} RPM")

                if current_speed > 100:
                    result["data"]["shake_test"] = "pass"
                    print("  Shake test: PASS")
                else:
                    result["data"]["shake_test"] = "fail"
                    print("  Shake test: FAIL")

                # Stop shaking
                print("  Stopping shake...")
                await module.deactivate_shaker()
                await asyncio.sleep(2)
            else:
                result["data"]["shake_test"] = "skipped"
                print("  Shake test: SKIPPED")

            # Deactivate all
            await module.deactivate_heater()
            await module.deactivate_shaker()

            result["data"]["final_state"] = {
                "temperature": module.temperature,
                "speed": module.speed,
                "status": module.status
            }

            # Determine overall result
            if (result["data"].get("latch_open_test") == "pass" and
                result["data"].get("latch_close_test") == "pass"):
                result["status"] = "PASS"
                print("  Heater-Shaker test: PASS")
            else:
                result["status"] = "FAIL"
                print("  Heater-Shaker test: FAIL")

        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)
            print(f"  Heater-Shaker test: FAIL - {e}")
            self.results["errors"].append(f"Heater-Shaker test failed: {e}")

        return result

    async def run_all_tests(self, module_type: Optional[str] = None) -> Dict[str, Any]:
        """Run tests on all attached modules or specified type."""
        print("\n" + "=" * 60)
        print("OT-2 MODULE MAINTENANCE TEST")
        print("=" * 60)

        if not await self.initialize():
            return self.results

        modules_info = await self.discover_modules()

        if not modules_info:
            print("\nNo modules to test")
            return self.results

        # Get actual module objects
        modules = self.api.attached_modules

        for module in modules:
            module_name = module.name().lower()

            # Filter by type if specified
            if module_type:
                if module_type == "temperature" and "temperature" not in module_name:
                    continue
                elif module_type == "magnetic" and "magnetic" not in module_name:
                    continue
                elif module_type == "thermocycler" and "thermocycler" not in module_name:
                    continue
                elif module_type == "heater-shaker" and "heater" not in module_name:
                    continue

            # Run appropriate test
            serial = module.device_info.get("serial", "unknown")

            if "temperature" in module_name:
                result = await self.test_temperature_module(module)
                self.results["tests"][f"temperature_{serial}"] = result
            elif "magnetic" in module_name:
                result = await self.test_magnetic_module(module)
                self.results["tests"][f"magnetic_{serial}"] = result
            elif "thermocycler" in module_name:
                result = await self.test_thermocycler(module)
                self.results["tests"][f"thermocycler_{serial}"] = result
            elif "heater" in module_name:
                result = await self.test_heater_shaker(module)
                self.results["tests"][f"heater_shaker_{serial}"] = result

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
            "total_modules": len(self.results["modules"]),
            "tests_run": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "overall": "PASS" if failed == 0 else "FAIL"
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Modules found: {len(self.results['modules'])}")
        print(f"  Tests run: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Warnings: {warnings}")
        print(f"  Overall: {self.results['summary']['overall']}")
        print("=" * 60)

    def save_report(self, filepath: Optional[str] = None):
        """Save test report to file."""
        if filepath is None:
            filepath = f"/data/module_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\nReport saved to: {filepath}")
        except Exception as e:
            print(f"Failed to save report: {e}")


async def main():
    parser = argparse.ArgumentParser(description="OT-2 Module Maintenance Test")
    parser.add_argument("--type", choices=["temperature", "magnetic", "thermocycler", "heater-shaker"],
                        help="Test only specific module type")

    args = parser.parse_args()

    tester = ModuleTest()
    await tester.run_all_tests(args.type)
    tester.save_report()

    return 0 if tester.results.get("summary", {}).get("overall") != "FAIL" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
