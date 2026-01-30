"""
Opentrons Flex Module Diagnostics Protocol

This protocol runs comprehensive diagnostics on all connected Flex modules
and generates a service report.

Upload this file to the Opentrons App and run it to validate your modules.

INSTRUCTIONS:
1. Install all modules you want to test on the Flex deck
2. Upload this protocol to the Opentrons App
3. Verify the deck configuration matches your setup
4. Run the protocol
5. Check the run log for results

DECK CONFIGURATION (modify as needed):
- Slot D1: Temperature Module or Heater-Shaker
- Slot C1: Magnetic Block
- Slot D3: Absorbance Plate Reader
- Slots A1+B1: Thermocycler (spans both slots)
- Slot B4: Flex Stacker (if present)

Minimum API Version: 2.16 (required for Flex)
"""
from opentrons import protocol_api
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

# Metadata
metadata = {
    "protocolName": "Flex Module Diagnostics Suite",
    "author": "Opentrons Service Team",
    "description": "Comprehensive diagnostics for all Flex-compatible modules",
    "apiLevel": "2.16"
}

# Configuration - Modify these to match your deck setup
MODULES_TO_TEST = {
    "temperature_module": {"slot": "D1", "enabled": True},
    "heater_shaker": {"slot": "D1", "enabled": False},  # Disable if temp module in D1
    "thermocycler": {"slot": None, "enabled": True},  # Auto-loads to A1+B1
    "absorbance_reader": {"slot": "D3", "enabled": True},
    "magnetic_block": {"slot": "C1", "enabled": True},
    "flex_stacker": {"slot": "B4", "enabled": False},  # Enable if present
}

# Safe test parameters
SAFE_PARAMS = {
    "temp_module_test_temp": 37.0,  # Celsius
    "heater_shaker_test_temp": 37.0,
    "heater_shaker_test_rpm": 200,  # Low speed
    "thermocycler_block_temp": 37.0,
    "thermocycler_lid_temp": 50.0,
    "absorbance_wavelength": 450,  # nm
}

TECHNICIAN_NAME = "Service Technician"  # Replace with your name


def run(protocol: protocol_api.ProtocolContext):
    """Main protocol execution."""
    protocol.comment("=" * 60)
    protocol.comment("OPENTRONS FLEX MODULE DIAGNOSTICS")
    protocol.comment("=" * 60)
    protocol.comment(f"Technician: {TECHNICIAN_NAME}")
    protocol.comment(f"Date: {datetime.now().isoformat()}")
    protocol.comment(f"API Version: {protocol.api_version}")
    protocol.comment("")

    results = []
    modules_tested = 0

    # Test Temperature Module
    if MODULES_TO_TEST["temperature_module"]["enabled"]:
        result = test_temperature_module(protocol)
        results.append(result)
        modules_tested += 1

    # Test Heater-Shaker
    if MODULES_TO_TEST["heater_shaker"]["enabled"]:
        result = test_heater_shaker(protocol)
        results.append(result)
        modules_tested += 1

    # Test Thermocycler
    if MODULES_TO_TEST["thermocycler"]["enabled"]:
        result = test_thermocycler(protocol)
        results.append(result)
        modules_tested += 1

    # Test Absorbance Reader
    if MODULES_TO_TEST["absorbance_reader"]["enabled"]:
        result = test_absorbance_reader(protocol)
        results.append(result)
        modules_tested += 1

    # Test Magnetic Block
    if MODULES_TO_TEST["magnetic_block"]["enabled"]:
        result = test_magnetic_block(protocol)
        results.append(result)
        modules_tested += 1

    # Test Flex Stacker
    if MODULES_TO_TEST["flex_stacker"]["enabled"]:
        result = test_flex_stacker(protocol)
        results.append(result)
        modules_tested += 1

    # Print Summary
    print_summary(protocol, results, modules_tested)


def test_temperature_module(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Temperature Module."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("TEMPERATURE MODULE DIAGNOSTICS")
    protocol.comment("-" * 40)

    result = {
        "module": "Temperature Module",
        "tests": [],
        "overall_pass": True,
    }

    try:
        slot = MODULES_TO_TEST["temperature_module"]["slot"]
        temp_mod = protocol.load_module("temperature module gen2", slot)

        # Test 1: Module Detection
        result["serial_number"] = temp_mod.serial_number
        result["tests"].append({
            "name": "Module Detection",
            "status": "PASS",
            "message": f"Detected S/N: {temp_mod.serial_number}",
        })
        protocol.comment(f"✓ Detected: S/N {temp_mod.serial_number}")

        # Test 2: Read Temperature
        current_temp = temp_mod.temperature
        result["tests"].append({
            "name": "Read Temperature",
            "status": "PASS",
            "message": f"Current: {current_temp}°C",
        })
        protocol.comment(f"✓ Temperature sensor: {current_temp}°C")

        # Test 3: Set Temperature
        test_temp = SAFE_PARAMS["temp_module_test_temp"]
        protocol.comment(f"  Setting temperature to {test_temp}°C...")
        temp_mod.set_temperature(test_temp)
        final_temp = temp_mod.temperature

        if abs(final_temp - test_temp) <= 1.0:
            result["tests"].append({
                "name": "Set Temperature",
                "status": "PASS",
                "message": f"Reached {final_temp}°C",
            })
            protocol.comment(f"✓ Temperature control: Reached {final_temp}°C")
        else:
            result["tests"].append({
                "name": "Set Temperature",
                "status": "FAIL",
                "message": f"Expected {test_temp}, got {final_temp}",
            })
            protocol.comment(f"✗ Temperature control: Failed to reach target")
            result["overall_pass"] = False

        # Test 4: Deactivate
        temp_mod.deactivate()
        result["tests"].append({
            "name": "Deactivate",
            "status": "PASS",
            "message": "Module deactivated",
        })
        protocol.comment("✓ Module deactivated")

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def test_heater_shaker(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Heater-Shaker Module."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("HEATER-SHAKER MODULE DIAGNOSTICS")
    protocol.comment("-" * 40)

    result = {
        "module": "Heater-Shaker Module",
        "tests": [],
        "overall_pass": True,
    }

    try:
        slot = MODULES_TO_TEST["heater_shaker"]["slot"]
        hs_mod = protocol.load_module("heaterShakerModuleV1", slot)

        # Test 1: Module Detection
        result["serial_number"] = hs_mod.serial_number
        result["tests"].append({
            "name": "Module Detection",
            "status": "PASS",
            "message": f"Detected S/N: {hs_mod.serial_number}",
        })
        protocol.comment(f"✓ Detected: S/N {hs_mod.serial_number}")

        # Test 2: Read Sensors
        current_temp = hs_mod.current_temperature
        current_speed = hs_mod.current_speed
        result["tests"].append({
            "name": "Read Sensors",
            "status": "PASS",
            "message": f"Temp: {current_temp}°C, Speed: {current_speed} RPM",
        })
        protocol.comment(f"✓ Sensors: {current_temp}°C, {current_speed} RPM")

        # Test 3: Latch Operations
        protocol.comment("  Testing latch operations...")
        hs_mod.open_labware_latch()
        protocol.comment("✓ Latch opened")

        hs_mod.close_labware_latch()
        result["tests"].append({
            "name": "Latch Operations",
            "status": "PASS",
            "message": "Open/Close successful",
        })
        protocol.comment("✓ Latch closed")

        # Test 4: Heating
        test_temp = SAFE_PARAMS["heater_shaker_test_temp"]
        protocol.comment(f"  Setting temperature to {test_temp}°C...")
        hs_mod.set_and_wait_for_temperature(test_temp)
        final_temp = hs_mod.current_temperature

        if abs(final_temp - test_temp) <= 1.0:
            result["tests"].append({
                "name": "Heating",
                "status": "PASS",
                "message": f"Reached {final_temp}°C",
            })
            protocol.comment(f"✓ Heating: Reached {final_temp}°C")
        else:
            result["tests"].append({
                "name": "Heating",
                "status": "FAIL",
                "message": f"Expected {test_temp}, got {final_temp}",
            })
            result["overall_pass"] = False

        # Test 5: Shaking
        test_rpm = SAFE_PARAMS["heater_shaker_test_rpm"]
        protocol.comment(f"  Testing shake at {test_rpm} RPM...")
        hs_mod.set_and_wait_for_shake_speed(test_rpm)
        protocol.delay(seconds=5)
        hs_mod.deactivate_shaker()
        result["tests"].append({
            "name": "Shaking",
            "status": "PASS",
            "message": f"Shook at {test_rpm} RPM",
        })
        protocol.comment(f"✓ Shaking: Tested at {test_rpm} RPM")

        # Cleanup
        hs_mod.deactivate_heater()
        hs_mod.open_labware_latch()
        result["tests"].append({
            "name": "Deactivate",
            "status": "PASS",
            "message": "Module deactivated",
        })
        protocol.comment("✓ Module deactivated")

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def test_thermocycler(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Thermocycler Module."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("THERMOCYCLER MODULE DIAGNOSTICS")
    protocol.comment("-" * 40)

    result = {
        "module": "Thermocycler Module",
        "tests": [],
        "overall_pass": True,
    }

    try:
        # Thermocycler auto-loads to A1+B1
        tc_mod = protocol.load_module("thermocycler module gen2")

        # Test 1: Module Detection
        result["serial_number"] = tc_mod.serial_number
        result["tests"].append({
            "name": "Module Detection",
            "status": "PASS",
            "message": f"Detected S/N: {tc_mod.serial_number}",
        })
        protocol.comment(f"✓ Detected: S/N {tc_mod.serial_number}")

        # Test 2: Read Temperatures
        block_temp = tc_mod.block_temperature
        lid_temp = tc_mod.lid_temperature
        result["tests"].append({
            "name": "Read Temperatures",
            "status": "PASS",
            "message": f"Block: {block_temp}°C, Lid: {lid_temp}°C",
        })
        protocol.comment(f"✓ Temperatures: Block {block_temp}°C, Lid {lid_temp}°C")

        # Test 3: Lid Operations
        protocol.comment("  Testing lid operations...")
        tc_mod.open_lid()
        result["tests"].append({
            "name": "Open Lid",
            "status": "PASS",
            "message": "Lid opened",
        })
        protocol.comment("✓ Lid opened")

        tc_mod.close_lid()
        result["tests"].append({
            "name": "Close Lid",
            "status": "PASS",
            "message": "Lid closed",
        })
        protocol.comment("✓ Lid closed")

        # Test 4: Block Temperature
        test_block_temp = SAFE_PARAMS["thermocycler_block_temp"]
        protocol.comment(f"  Setting block to {test_block_temp}°C...")
        tc_mod.set_block_temperature(test_block_temp, hold_time_seconds=5)
        final_block = tc_mod.block_temperature

        if abs(final_block - test_block_temp) <= 1.0:
            result["tests"].append({
                "name": "Block Temperature",
                "status": "PASS",
                "message": f"Reached {final_block}°C",
            })
            protocol.comment(f"✓ Block temperature: Reached {final_block}°C")
        else:
            result["tests"].append({
                "name": "Block Temperature",
                "status": "FAIL",
                "message": f"Expected {test_block_temp}, got {final_block}",
            })
            result["overall_pass"] = False

        # Test 5: Lid Temperature
        test_lid_temp = SAFE_PARAMS["thermocycler_lid_temp"]
        protocol.comment(f"  Setting lid to {test_lid_temp}°C...")
        tc_mod.set_lid_temperature(test_lid_temp)
        final_lid = tc_mod.lid_temperature

        if abs(final_lid - test_lid_temp) <= 2.0:
            result["tests"].append({
                "name": "Lid Temperature",
                "status": "PASS",
                "message": f"Reached {final_lid}°C",
            })
            protocol.comment(f"✓ Lid temperature: Reached {final_lid}°C")
        else:
            result["tests"].append({
                "name": "Lid Temperature",
                "status": "FAIL",
                "message": f"Expected {test_lid_temp}, got {final_lid}",
            })
            result["overall_pass"] = False

        # Test 6: Simple Profile
        protocol.comment("  Running quick temperature profile...")
        simple_profile = [
            {"temperature": 37, "hold_time_seconds": 3},
            {"temperature": 40, "hold_time_seconds": 3},
        ]
        tc_mod.execute_profile(steps=simple_profile, repetitions=1)
        result["tests"].append({
            "name": "Temperature Profile",
            "status": "PASS",
            "message": "Profile executed successfully",
        })
        protocol.comment("✓ Temperature profile completed")

        # Cleanup
        tc_mod.deactivate()
        tc_mod.open_lid()
        result["tests"].append({
            "name": "Deactivate",
            "status": "PASS",
            "message": "Module deactivated",
        })
        protocol.comment("✓ Module deactivated, lid open")

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def test_absorbance_reader(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Absorbance Plate Reader."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("ABSORBANCE READER DIAGNOSTICS")
    protocol.comment("-" * 40)

    result = {
        "module": "Absorbance Plate Reader",
        "tests": [],
        "overall_pass": True,
    }

    try:
        slot = MODULES_TO_TEST["absorbance_reader"]["slot"]
        abs_mod = protocol.load_module("absorbance reader", slot)

        # Test 1: Module Detection
        result["serial_number"] = abs_mod.serial_number
        result["tests"].append({
            "name": "Module Detection",
            "status": "PASS",
            "message": f"Detected S/N: {abs_mod.serial_number}",
        })
        protocol.comment(f"✓ Detected: S/N {abs_mod.serial_number}")

        # Test 2: Check Lid Status
        lid_on = abs_mod.is_lid_on()
        result["tests"].append({
            "name": "Lid Status",
            "status": "PASS",
            "message": f"Lid is {'on' if lid_on else 'off'}",
        })
        protocol.comment(f"✓ Lid status: {'on' if lid_on else 'off'}")

        # Test 3: Initialize Measurement
        test_wavelength = SAFE_PARAMS["absorbance_wavelength"]
        protocol.comment(f"  Initializing for {test_wavelength}nm measurement...")
        abs_mod.initialize(mode="single", wavelengths=[test_wavelength])
        result["tests"].append({
            "name": "Initialize",
            "status": "PASS",
            "message": f"Initialized for {test_wavelength}nm",
        })
        protocol.comment(f"✓ Initialized for {test_wavelength}nm measurement")

        # Test 4: Lid Operations (requires gripper)
        try:
            protocol.comment("  Testing lid operations (requires gripper)...")
            abs_mod.open_lid()
            result["tests"].append({
                "name": "Open Lid",
                "status": "PASS",
                "message": "Lid opened with gripper",
            })
            protocol.comment("✓ Lid opened")

            abs_mod.close_lid()
            result["tests"].append({
                "name": "Close Lid",
                "status": "PASS",
                "message": "Lid closed with gripper",
            })
            protocol.comment("✓ Lid closed")

        except Exception as e:
            if "gripper" in str(e).lower():
                result["tests"].append({
                    "name": "Lid Operations",
                    "status": "SKIP",
                    "message": "Requires gripper",
                })
                protocol.comment("○ Lid operations skipped (requires gripper)")
            else:
                raise

        # Test 5: Test Read (if plate present)
        try:
            protocol.comment("  Attempting test read...")
            read_result = abs_mod.read()
            result["tests"].append({
                "name": "Test Read",
                "status": "PASS",
                "message": "Read completed successfully",
            })
            protocol.comment("✓ Test read completed")
        except Exception as e:
            if "plate" in str(e).lower() or "empty" in str(e).lower():
                result["tests"].append({
                    "name": "Test Read",
                    "status": "SKIP",
                    "message": "No plate present",
                })
                protocol.comment("○ Test read skipped (no plate)")
            else:
                raise

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def test_magnetic_block(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Magnetic Block (passive module)."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("MAGNETIC BLOCK DIAGNOSTICS")
    protocol.comment("-" * 40)
    protocol.comment("Note: Magnetic Block is passive - no electronic tests")

    result = {
        "module": "Magnetic Block",
        "tests": [],
        "overall_pass": True,
    }

    try:
        slot = MODULES_TO_TEST["magnetic_block"]["slot"]
        mag_block = protocol.load_module("magnetic block", slot)

        # Test 1: Module Loaded
        result["tests"].append({
            "name": "Module Loaded",
            "status": "PASS",
            "message": f"Loaded in slot {slot}",
        })
        protocol.comment(f"✓ Magnetic Block loaded in slot {slot}")

        # Test 2: Labware Loading Capability
        if hasattr(mag_block, "load_labware"):
            result["tests"].append({
                "name": "Labware Support",
                "status": "PASS",
                "message": "Can load labware",
            })
            protocol.comment("✓ Labware loading available")
        else:
            result["tests"].append({
                "name": "Labware Support",
                "status": "WARNING",
                "message": "load_labware not available",
            })

        # Physical checks reminder
        result["tests"].append({
            "name": "Physical Inspection",
            "status": "WARNING",
            "message": "Manual verification required",
        })
        protocol.comment("")
        protocol.comment("MANUAL VERIFICATION REQUIRED:")
        protocol.comment("  1. Block is properly seated on deck")
        protocol.comment("  2. Block is level and stable")
        protocol.comment("  3. Magnetic surface is clean")
        protocol.comment("  4. No visible damage to magnets")
        protocol.comment("")
        protocol.comment("MAGNETIC FUNCTION TEST:")
        protocol.comment("  To verify: Add magnetic beads to wells,")
        protocol.comment("  wait 2-5 min, observe bead separation")

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def test_flex_stacker(protocol: protocol_api.ProtocolContext) -> Dict[str, Any]:
    """Run diagnostics on Flex Stacker Module."""
    protocol.comment("")
    protocol.comment("-" * 40)
    protocol.comment("FLEX STACKER DIAGNOSTICS")
    protocol.comment("-" * 40)

    result = {
        "module": "Flex Stacker",
        "tests": [],
        "overall_pass": True,
    }

    try:
        slot = MODULES_TO_TEST["flex_stacker"]["slot"]
        stacker = protocol.load_module("flexStackerModuleV1", slot)

        # Test 1: Module Detection
        serial = getattr(stacker, "serial_number", "Unknown")
        result["serial_number"] = serial
        result["tests"].append({
            "name": "Module Detection",
            "status": "PASS",
            "message": f"Detected S/N: {serial}",
        })
        protocol.comment(f"✓ Detected: S/N {serial}")

        # Note: Detailed stacker tests require low-level hardware access
        result["tests"].append({
            "name": "Basic Functionality",
            "status": "PASS",
            "message": "Module loaded successfully",
        })
        protocol.comment("✓ Module loaded and ready")

        protocol.comment("")
        protocol.comment("Note: Full stacker diagnostics require")
        protocol.comment("direct hardware access. Use the host-side")
        protocol.comment("diagnostic tool for complete testing.")

    except Exception as e:
        result["tests"].append({
            "name": "Module Test",
            "status": "ERROR",
            "message": str(e),
        })
        result["overall_pass"] = False
        protocol.comment(f"✗ Error: {e}")

    return result


def print_summary(
    protocol: protocol_api.ProtocolContext,
    results: List[Dict[str, Any]],
    modules_tested: int
) -> None:
    """Print diagnostic summary."""
    protocol.comment("")
    protocol.comment("=" * 60)
    protocol.comment("DIAGNOSTICS SUMMARY")
    protocol.comment("=" * 60)
    protocol.comment("")

    total_tests = sum(len(r["tests"]) for r in results)
    passed_tests = sum(
        sum(1 for t in r["tests"] if t["status"] == "PASS")
        for r in results
    )
    failed_tests = sum(
        sum(1 for t in r["tests"] if t["status"] == "FAIL")
        for r in results
    )
    all_passed = all(r["overall_pass"] for r in results)

    protocol.comment(f"Modules Tested: {modules_tested}")
    protocol.comment(f"Total Tests: {total_tests}")
    protocol.comment(f"Passed: {passed_tests}")
    protocol.comment(f"Failed: {failed_tests}")
    protocol.comment(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    protocol.comment("")

    for r in results:
        status = "PASS" if r["overall_pass"] else "FAIL"
        test_count = len(r["tests"])
        pass_count = sum(1 for t in r["tests"] if t["status"] == "PASS")
        protocol.comment(f"  {r['module']}: {status} ({pass_count}/{test_count})")
        if "serial_number" in r:
            protocol.comment(f"    S/N: {r['serial_number']}")

    protocol.comment("")
    protocol.comment("=" * 60)
    protocol.comment("DIAGNOSTICS COMPLETE")
    protocol.comment("=" * 60)
