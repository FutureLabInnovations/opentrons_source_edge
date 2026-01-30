# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # OT-2 Full Service Diagnostic Notebook
#
# Comprehensive diagnostic tool for annual maintenance and service reporting.
# Tests ALL system components and generates a detailed JSON report.
#
# ## How to Use
# This file uses Jupyter "percent format" cell markers (`# %%`).
# You can run it in:
# - **Jupyter Notebook/Lab**: Install jupytext, then open this .py file directly
# - **VS Code**: Open and run cells with the Python extension
# - **PyCharm**: Use the Scientific mode to run cells
# - **Command line**: Run the entire script with `python ot2_service_diagnostic_notebook.py`
#
# ## Sections
# 1. **Setup & Imports** - Load dependencies and define helper classes
# 2. **Configuration** - Set test parameters and options
# 3. **Hardware Initialization** - Connect to the robot
# 4. **System Information** - Gather robot info, versions, network, storage
# 5. **Motion System Tests** - Homing, accuracy, repeatability
# 6. **Pipette Tests** - Detection, plunger, calibration
# 7. **Module Tests** - Test all attached modules
# 8. **Calibration Verification** - Deck, pipette, tip length calibrations
# 9. **System Health** - Disk space, logs, services
# 10. **Report Generation** - Generate summary and save report

# %% [markdown]
# ## Section 1: Setup & Imports
#
# Run this cell first to load all dependencies and define helper classes.

# %%
# =============================================================================
# SECTION 1: SETUP & IMPORTS
# =============================================================================

import asyncio
import json
import sys
import os
import subprocess
import statistics
import socket
import platform
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Check if running on robot
try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.types import Axis, CriticalPoint
    from opentrons.types import Mount, Point
    from opentrons.config import get_opentrons_path, robot_configs
    import numpy as np
    ON_ROBOT = True
    print("Running on OT-2 robot - hardware access available")
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Running in simulation mode.")
    print("  Hardware tests will be skipped.")


class TestStatus(Enum):
    """Test result status codes."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class TestResult:
    """Container for individual test results."""
    name: str
    status: TestStatus
    message: str = ""
    data: Dict[str, Any] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "data": self.data or {},
            "duration_seconds": round(self.duration_seconds, 2)
        }

    def __repr__(self):
        return f"TestResult({self.name}: {self.status.value} - {self.message})"


def run_shell_command(cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def print_section_header(title: str):
    """Print a formatted section header."""
    print("=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_test_result(result: TestResult):
    """Print a formatted test result."""
    status_symbols = {
        TestStatus.PASS: "[PASS]",
        TestStatus.FAIL: "[FAIL]",
        TestStatus.WARNING: "[WARN]",
        TestStatus.SKIPPED: "[SKIP]",
        TestStatus.ERROR: "[ERR ]"
    }
    symbol = status_symbols.get(result.status, "[????]")
    print(f"  {symbol} {result.name}")
    if result.message:
        print(f"         -> {result.message}")


print("\nSetup complete - helper classes and functions loaded")

# %% [markdown]
# ## Section 2: Configuration
#
# Configure the diagnostic options before running tests.
# Modify these variables as needed.

# %%
# =============================================================================
# SECTION 2: CONFIGURATION
# =============================================================================

# --- DIAGNOSTIC OPTIONS ---
# Set to True for fewer test iterations (faster)
QUICK_MODE = False

# Set to True to skip module tests
SKIP_MODULES = False

# Where to save the report
OUTPUT_DIR = "/data/service_reports"

# --- TEST POSITIONS (deck coordinates) ---
if ON_ROBOT:
    TEST_POSITIONS = {
        "slot_1": Point(x=14.38, y=11.24, z=100),
        "slot_3": Point(x=297.12, y=11.24, z=100),
        "slot_7": Point(x=14.38, y=258.76, z=100),
        "slot_9": Point(x=297.12, y=258.76, z=100),
        "slot_5_center": Point(x=155.75, y=135.0, z=100),
    }

    # --- EXPECTED HOME POSITIONS ---
    EXPECTED_HOME = {
        Axis.X: 418.0,
        Axis.Y: 353.0,
        Axis.Z: 218.0,
        Axis.A: 218.0,
    }
else:
    TEST_POSITIONS = {}
    EXPECTED_HOME = {}

# --- GLOBAL STATE ---
# These will store results across sections
api: Optional['API'] = None  # Hardware API instance
start_time = datetime.now()
all_results: List[TestResult] = []  # All test results

# Report structure
report: Dict[str, Any] = {
    "report_type": "OT-2 Full Service Diagnostic",
    "report_version": "1.0",
    "generated_at": start_time.isoformat(),
    "robot_info": {},
    "test_sections": {},
    "summary": {},
    "recommendations": []
}

print("Configuration:")
print(f"  Quick Mode: {QUICK_MODE}")
print(f"  Skip Modules: {SKIP_MODULES}")
print(f"  Output Directory: {OUTPUT_DIR}")
print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nConfiguration loaded")

# %% [markdown]
# ## Section 3: Hardware Initialization
#
# Connect to the OT-2 hardware and home the robot.
#
# **Note:** This will move the gantry to the home position.

# %%
# =============================================================================
# SECTION 3: HARDWARE INITIALIZATION
# =============================================================================

async def initialize_hardware() -> bool:
    """Initialize hardware connection and home the robot."""
    global api

    if not ON_ROBOT:
        print("Not on robot - skipping hardware initialization")
        return False

    try:
        print("Initializing hardware controller...")
        api = await API.build_hardware_controller()
        print("Hardware controller initialized")

        print("Homing robot (this may take a moment)...")
        await api.home()
        print("Robot homed successfully")

        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize: {e}")
        all_results.append(TestResult(
            name="Hardware Initialization",
            status=TestStatus.FAIL,
            message=str(e)
        ))
        return False


# Run initialization
# Note: In Jupyter, you can run this directly. In a script, wrap in asyncio.run()
try:
    # Check if we're in an async context (Jupyter)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # We're in Jupyter or similar async environment
        hardware_ready = await initialize_hardware()
    else:
        hardware_ready = asyncio.run(initialize_hardware())
except RuntimeError:
    hardware_ready = asyncio.run(initialize_hardware())

if hardware_ready:
    print("\nHardware initialization complete - ready for testing")
else:
    print("\nRunning in limited mode - hardware tests will be skipped")

# %% [markdown]
# ## Section 4: System Information
#
# Gather comprehensive system information including:
# - Hostname and serial number
# - Software and firmware versions
# - Network configuration
# - Storage status

# %%
# =============================================================================
# SECTION 4: SYSTEM INFORMATION
# =============================================================================

async def gather_system_info() -> Dict[str, Any]:
    """Gather comprehensive system information."""
    print_section_header("SYSTEM INFORMATION")

    info = {
        "hostname": "",
        "robot_model": "OT-2",
        "serial_number": "",
        "software_version": {},
        "firmware_version": "",
        "network": {},
        "storage": {},
        "uptime": "",
        "python_version": platform.python_version()
    }

    # Hostname
    try:
        info["hostname"] = socket.gethostname()
        print(f"  Hostname: {info['hostname']}")
    except:
        pass

    # Serial number
    try:
        _, stdout, _ = run_shell_command("cat /var/serial")
        info["serial_number"] = stdout.strip() if stdout else "Unknown"
        print(f"  Serial Number: {info['serial_number']}")
    except:
        pass

    # Software version
    try:
        version_file = Path("/etc/VERSION.json")
        if version_file.exists():
            with open(version_file) as f:
                info["software_version"] = json.load(f)
            print(f"  Software Version: {info['software_version'].get('opentrons_api_version', 'Unknown')}")
    except:
        pass

    # Firmware version
    if api:
        try:
            fw_version = await api._backend._smoothie_driver.get_fw_version()
            info["firmware_version"] = fw_version
            print(f"  Firmware Version: {fw_version}")
        except:
            pass

    # Network info
    try:
        _, ip_output, _ = run_shell_command("hostname -I")
        info["network"]["ip_addresses"] = ip_output.split() if ip_output else []

        _, wifi_output, _ = run_shell_command("iwconfig wlan0 2>/dev/null | grep ESSID")
        if "ESSID" in wifi_output:
            ssid = wifi_output.split('ESSID:"')[1].split('"')[0] if 'ESSID:"' in wifi_output else ""
            info["network"]["wifi_ssid"] = ssid

        print(f"  IP Addresses: {', '.join(info['network'].get('ip_addresses', []))}")
    except:
        pass

    # Storage info
    try:
        _, df_output, _ = run_shell_command("df -h /data | tail -1")
        if df_output:
            parts = df_output.split()
            if len(parts) >= 4:
                info["storage"] = {
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "percent_used": parts[4] if len(parts) > 4 else ""
                }
                print(f"  Storage: {info['storage']['used']} / {info['storage']['total']} ({info['storage'].get('percent_used', '')})")
    except:
        pass

    # Uptime
    try:
        _, uptime_output, _ = run_shell_command("uptime -p")
        info["uptime"] = uptime_output
        print(f"  Uptime: {uptime_output}")
    except:
        pass

    print(f"  Python Version: {info['python_version']}")

    report["robot_info"] = info
    print("\nSystem information gathered")
    return info


# Run system info gathering
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        system_info = await gather_system_info()
    else:
        system_info = asyncio.run(gather_system_info())
except RuntimeError:
    system_info = asyncio.run(gather_system_info())

# %% [markdown]
# ## Section 5: Motion System Tests
#
# Test the motion system including:
# - Limit switch verification
# - Homing accuracy
# - Position repeatability
# - Cross-deck accuracy
# - Z-axis movement
#
# **Note:** This section will move the gantry to various positions.

# %%
# =============================================================================
# SECTION 5: MOTION SYSTEM TESTS
# =============================================================================

async def test_limit_switches() -> TestResult:
    """Test all limit switches."""
    start = time.time()

    try:
        await api.home()
        switches = await api._backend._smoothie_driver.switch_state()

        gantry_switches = {k: v for k, v in switches.items() if k in ["X", "Y", "Z", "A"]}
        all_triggered = all(gantry_switches.values())

        if all_triggered:
            return TestResult(
                name="Limit Switch Verification",
                status=TestStatus.PASS,
                message="All gantry limit switches triggered at home",
                data={"switch_states": switches},
                duration_seconds=time.time() - start
            )
        else:
            failed = [k for k, v in gantry_switches.items() if not v]
            return TestResult(
                name="Limit Switch Verification",
                status=TestStatus.FAIL,
                message=f"Switches not triggered: {failed}",
                data={"switch_states": switches},
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Limit Switch Verification",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_homing_accuracy() -> TestResult:
    """Test homing repeatability."""
    start = time.time()

    try:
        iterations = 3 if QUICK_MODE else 5
        positions = []

        for i in range(iterations):
            # Move away
            await api.move_rel(mount=Mount.LEFT, delta=Point(-30, -30, -30))
            # Home
            await api.home()
            # Record position
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)
            positions.append({
                "X": pos.get(Axis.X, 0),
                "Y": pos.get(Axis.Y, 0),
                "Z": pos.get(Axis.Z, 0)
            })

        # Calculate statistics
        stats = {}
        for axis in ["X", "Y", "Z"]:
            values = [p[axis] for p in positions]
            stats[axis] = {
                "mean": round(statistics.mean(values), 4),
                "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
                "range": round(max(values) - min(values), 4)
            }

        max_range = max(s["range"] for s in stats.values())

        if max_range < 0.1:
            status = TestStatus.PASS
            msg = f"Homing repeatability excellent (<0.1mm range)"
        elif max_range < 0.3:
            status = TestStatus.WARNING
            msg = f"Homing repeatability acceptable ({max_range:.3f}mm range)"
        else:
            status = TestStatus.FAIL
            msg = f"Homing repeatability poor ({max_range:.3f}mm range)"

        return TestResult(
            name="Homing Accuracy",
            status=status,
            message=msg,
            data={"iterations": iterations, "statistics": stats, "max_range_mm": max_range},
            duration_seconds=time.time() - start
        )
    except Exception as e:
        return TestResult(
            name="Homing Accuracy",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_position_repeatability() -> TestResult:
    """Test position repeatability."""
    start = time.time()
    iterations = 5 if QUICK_MODE else 10

    try:
        target = TEST_POSITIONS["slot_5_center"]
        home_pos = Point(x=100, y=100, z=150)
        positions = []

        for i in range(iterations):
            await api.move_to(mount=Mount.LEFT, abs_position=home_pos)
            await api.move_to(mount=Mount.LEFT, abs_position=target)
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)
            positions.append({
                "X": pos.get(Axis.X, 0),
                "Y": pos.get(Axis.Y, 0),
                "Z": pos.get(Axis.Z, 0)
            })

        # Calculate 3D repeatability
        stats = {}
        for axis in ["X", "Y", "Z"]:
            values = [p[axis] for p in positions]
            stats[axis] = {
                "mean": round(statistics.mean(values), 4),
                "stdev": round(statistics.stdev(values), 5) if len(values) > 1 else 0,
                "range": round(max(values) - min(values), 5)
            }

        repeatability_3d = (stats["X"]["range"]**2 + stats["Y"]["range"]**2 + stats["Z"]["range"]**2)**0.5

        await api.home()

        if repeatability_3d < 0.1:
            status = TestStatus.PASS
            msg = f"Position repeatability excellent ({repeatability_3d:.4f}mm)"
        elif repeatability_3d < 0.25:
            status = TestStatus.WARNING
            msg = f"Position repeatability acceptable ({repeatability_3d:.4f}mm)"
        else:
            status = TestStatus.FAIL
            msg = f"Position repeatability poor ({repeatability_3d:.4f}mm)"

        return TestResult(
            name="Position Repeatability",
            status=status,
            message=msg,
            data={"iterations": iterations, "statistics": stats, "repeatability_3d_mm": round(repeatability_3d, 5)},
            duration_seconds=time.time() - start
        )
    except Exception as e:
        return TestResult(
            name="Position Repeatability",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_cross_deck_accuracy() -> TestResult:
    """Test accuracy across deck."""
    start = time.time()

    try:
        measurements = []

        for name, target in TEST_POSITIONS.items():
            await api.move_to(mount=Mount.LEFT, abs_position=target)
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)

            actual = Point(pos.get(Axis.X, 0), pos.get(Axis.Y, 0), pos.get(Axis.Z, 0))
            error_3d = ((actual.x - target.x)**2 + (actual.y - target.y)**2 + (actual.z - target.z)**2)**0.5

            measurements.append({
                "position": name,
                "target": {"x": target.x, "y": target.y, "z": target.z},
                "actual": {"x": round(actual.x, 3), "y": round(actual.y, 3), "z": round(actual.z, 3)},
                "error_3d_mm": round(error_3d, 4)
            })

        await api.home()

        max_error = max(m["error_3d_mm"] for m in measurements)
        mean_error = statistics.mean(m["error_3d_mm"] for m in measurements)

        if max_error < 0.5:
            status = TestStatus.PASS
            msg = f"Cross-deck accuracy excellent (max error {max_error:.3f}mm)"
        elif max_error < 1.5:
            status = TestStatus.WARNING
            msg = f"Cross-deck accuracy acceptable (max error {max_error:.3f}mm)"
        else:
            status = TestStatus.FAIL
            msg = f"Cross-deck accuracy poor (max error {max_error:.3f}mm)"

        return TestResult(
            name="Cross-Deck Accuracy",
            status=status,
            message=msg,
            data={"measurements": measurements, "max_error_mm": max_error, "mean_error_mm": round(mean_error, 4)},
            duration_seconds=time.time() - start
        )
    except Exception as e:
        return TestResult(
            name="Cross-Deck Accuracy",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_z_axis_movement() -> TestResult:
    """Test Z-axis movement on both mounts."""
    start = time.time()

    try:
        results = {}

        for mount in [Mount.LEFT, Mount.RIGHT]:
            mount_name = mount.name.lower()
            await api.home()

            # Move down
            await api.move_to(mount=mount, abs_position=Point(200, 200, 50))
            pos_down = await api.current_position(mount=mount, refresh=True)

            # Move up
            await api.move_to(mount=mount, abs_position=Point(200, 200, 150))
            pos_up = await api.current_position(mount=mount, refresh=True)

            z_axis = Axis.Z if mount == Mount.LEFT else Axis.A
            travel = abs(pos_up.get(z_axis, 0) - pos_down.get(z_axis, 0))

            results[mount_name] = {
                "z_travel_mm": round(travel, 2),
                "expected_travel_mm": 100,
                "error_mm": round(abs(travel - 100), 2)
            }

        await api.home()

        max_error = max(r["error_mm"] for r in results.values())

        if max_error < 1.0:
            status = TestStatus.PASS
            msg = "Z-axis movement accurate on both mounts"
        elif max_error < 3.0:
            status = TestStatus.WARNING
            msg = f"Z-axis movement slightly off ({max_error:.2f}mm error)"
        else:
            status = TestStatus.FAIL
            msg = f"Z-axis movement error ({max_error:.2f}mm)"

        return TestResult(
            name="Z-Axis Movement",
            status=status,
            message=msg,
            data=results,
            duration_seconds=time.time() - start
        )
    except Exception as e:
        return TestResult(
            name="Z-Axis Movement",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def run_motion_tests() -> Dict[str, Any]:
    """Run all motion system tests."""
    print_section_header("MOTION SYSTEM TESTS")

    section_results = {"tests": [], "overall_status": "PASS"}

    if not api:
        print("Hardware not available - skipping motion tests")
        section_results["overall_status"] = "SKIPPED"
        return section_results

    # Test 1: Limit Switches
    print("\n  Running: Limit Switch Verification...")
    result = await test_limit_switches()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Test 2: Homing Accuracy
    print("\n  Running: Homing Accuracy...")
    result = await test_homing_accuracy()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Test 3: Position Repeatability
    print("\n  Running: Position Repeatability...")
    result = await test_position_repeatability()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Test 4: Cross-Deck Accuracy
    print("\n  Running: Cross-Deck Accuracy...")
    result = await test_cross_deck_accuracy()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Test 5: Z-Axis Movement
    print("\n  Running: Z-Axis Movement...")
    result = await test_z_axis_movement()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Determine section status
    statuses = [t["status"] for t in section_results["tests"]]
    if "FAIL" in statuses:
        section_results["overall_status"] = "FAIL"
    elif "WARNING" in statuses:
        section_results["overall_status"] = "WARNING"

    report["test_sections"]["motion_system"] = section_results
    print(f"\nMotion system tests complete - Overall: {section_results['overall_status']}")
    return section_results


# Run motion tests
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        motion_results = await run_motion_tests()
    else:
        motion_results = asyncio.run(run_motion_tests())
except RuntimeError:
    motion_results = asyncio.run(run_motion_tests())

# %% [markdown]
# ## Section 6: Pipette Tests
#
# Test both pipette mounts including:
# - Pipette detection
# - Plunger movement
# - Calibration status

# %%
# =============================================================================
# SECTION 6: PIPETTE TESTS
# =============================================================================

async def test_pipette_detection(mount: 'Mount') -> TestResult:
    """Test pipette detection."""
    start = time.time()
    mount_name = mount.name.lower()

    try:
        instruments = api.attached_instruments
        pipette = instruments.get(mount)

        if pipette:
            data = {
                "model": pipette.get("model", "unknown"),
                "name": pipette.get("name", "unknown"),
                "pipette_id": pipette.get("pipette_id", "unknown"),
                "min_volume_ul": pipette.get("min_volume", 0),
                "max_volume_ul": pipette.get("max_volume", 0),
                "channels": pipette.get("channels", 1)
            }
            return TestResult(
                name=f"Pipette Detection ({mount_name})",
                status=TestStatus.PASS,
                message=f"Detected: {data['name']}",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Pipette Detection ({mount_name})",
                status=TestStatus.WARNING,
                message="No pipette attached",
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Pipette Detection ({mount_name})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_pipette_plunger(mount: 'Mount') -> TestResult:
    """Test pipette plunger movement."""
    start = time.time()
    mount_name = mount.name.lower()

    try:
        pipette = api.hardware_pipettes.get(mount)
        if not pipette:
            return TestResult(
                name=f"Pipette Plunger ({mount_name})",
                status=TestStatus.SKIPPED,
                message="No pipette attached",
                duration_seconds=time.time() - start
            )

        # Home plunger
        await api.home_plunger(mount)

        plunger_axis = Axis.of_plunger(mount)
        pos_home = await api.current_position(mount=mount, refresh=True)
        home_pos = pos_home.get(plunger_axis, 0)

        # Prepare for aspirate (moves plunger to bottom)
        await api.prepare_for_aspirate(mount)
        pos_bottom = await api.current_position(mount=mount, refresh=True)
        bottom_pos = pos_bottom.get(plunger_axis, 0)

        travel = abs(home_pos - bottom_pos)

        # Home again
        await api.home_plunger(mount)

        data = {
            "home_position_mm": round(home_pos, 3),
            "bottom_position_mm": round(bottom_pos, 3),
            "travel_mm": round(travel, 3)
        }

        if travel > 1.0:  # Should have meaningful travel
            return TestResult(
                name=f"Pipette Plunger ({mount_name})",
                status=TestStatus.PASS,
                message=f"Plunger travel: {travel:.2f}mm",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Pipette Plunger ({mount_name})",
                status=TestStatus.FAIL,
                message=f"Insufficient plunger travel: {travel:.2f}mm",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Pipette Plunger ({mount_name})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_pipette_calibration(mount: 'Mount') -> TestResult:
    """Check pipette calibration status."""
    start = time.time()
    mount_name = mount.name.lower()

    try:
        instruments = api.attached_instruments
        pipette = instruments.get(mount)

        if not pipette:
            return TestResult(
                name=f"Pipette Calibration ({mount_name})",
                status=TestStatus.SKIPPED,
                message="No pipette attached",
                duration_seconds=time.time() - start
            )

        pip_id = pipette.get("pipette_id")

        # Check calibration files
        cal_path = Path(f"/data/opentrons/robot/pipettes/{mount_name}/{pip_id}.json")

        if cal_path.exists():
            with open(cal_path) as f:
                cal_data = json.load(f)

            offset = cal_data.get("offset", [0, 0, 0])
            last_modified = cal_data.get("last_modified", "unknown")

            data = {
                "offset": offset,
                "last_modified": last_modified,
                "source": cal_data.get("source", "unknown")
            }

            return TestResult(
                name=f"Pipette Calibration ({mount_name})",
                status=TestStatus.PASS,
                message=f"Calibrated (offset: [{offset[0]:.2f}, {offset[1]:.2f}, {offset[2]:.2f}])",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Pipette Calibration ({mount_name})",
                status=TestStatus.WARNING,
                message="Pipette not calibrated",
                data={"calibrated": False},
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Pipette Calibration ({mount_name})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def run_pipette_tests() -> Dict[str, Any]:
    """Run all pipette tests."""
    print_section_header("PIPETTE TESTS")

    section_results = {"tests": [], "overall_status": "PASS"}

    if not api:
        print("Hardware not available - skipping pipette tests")
        section_results["overall_status"] = "SKIPPED"
        return section_results

    for mount in [Mount.LEFT, Mount.RIGHT]:
        mount_name = mount.name.upper()
        print(f"\n  Testing {mount_name} mount pipette...")

        # Detection test
        result = await test_pipette_detection(mount)
        section_results["tests"].append(result.to_dict())
        all_results.append(result)
        print_test_result(result)

        if result.status == TestStatus.PASS:
            # Plunger test
            result = await test_pipette_plunger(mount)
            section_results["tests"].append(result.to_dict())
            all_results.append(result)
            print_test_result(result)

            # Calibration test
            result = await test_pipette_calibration(mount)
            section_results["tests"].append(result.to_dict())
            all_results.append(result)
            print_test_result(result)

    # Determine section status
    statuses = [t["status"] for t in section_results["tests"]]
    if "FAIL" in statuses:
        section_results["overall_status"] = "FAIL"
    elif "WARNING" in statuses:
        section_results["overall_status"] = "WARNING"

    report["test_sections"]["pipettes"] = section_results
    print(f"\nPipette tests complete - Overall: {section_results['overall_status']}")
    return section_results


# Run pipette tests
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        pipette_results = await run_pipette_tests()
    else:
        pipette_results = asyncio.run(run_pipette_tests())
except RuntimeError:
    pipette_results = asyncio.run(run_pipette_tests())

# %% [markdown]
# ## Section 7: Module Tests
#
# Test all attached modules:
# - Temperature Module
# - Magnetic Module
# - Thermocycler
# - Heater-Shaker

# %%
# =============================================================================
# SECTION 7: MODULE TESTS
# =============================================================================

async def test_temperature_module(module) -> TestResult:
    """Test Temperature Module."""
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        current_temp = module.temperature
        target = module.target
        status = module.status
        fw_version = module.device_info.get("version", "unknown")

        data = {
            "serial": serial,
            "firmware_version": fw_version,
            "current_temperature_c": current_temp,
            "target_temperature_c": target,
            "status": status
        }

        if current_temp is not None and 5 <= current_temp <= 50:
            return TestResult(
                name=f"Temperature Module ({serial})",
                status=TestStatus.PASS,
                message=f"Temperature: {current_temp}C, Status: {status}",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Temperature Module ({serial})",
                status=TestStatus.WARNING,
                message=f"Unusual temperature reading: {current_temp}C",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Temperature Module ({serial})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_magnetic_module(module) -> TestResult:
    """Test Magnetic Module."""
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        status = module.status
        fw_version = module.device_info.get("version", "unknown")

        # Test engage/disengage
        await module.engage(height_from_base=5.0)
        await asyncio.sleep(1)
        engaged_status = module.status

        await module.deactivate()
        await asyncio.sleep(1)
        disengaged_status = module.status

        data = {
            "serial": serial,
            "firmware_version": fw_version,
            "initial_status": status,
            "engaged_status": engaged_status,
            "disengaged_status": disengaged_status
        }

        if "engaged" in engaged_status.lower() and "disengaged" in disengaged_status.lower():
            return TestResult(
                name=f"Magnetic Module ({serial})",
                status=TestStatus.PASS,
                message="Engage/disengage cycle successful",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Magnetic Module ({serial})",
                status=TestStatus.WARNING,
                message="Engage/disengage status unclear",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Magnetic Module ({serial})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_thermocycler(module) -> TestResult:
    """Test Thermocycler."""
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        lid_status = module.lid_status
        lid_temp = module.lid_temp
        plate_temp = module.temperature
        fw_version = module.device_info.get("version", "unknown")

        data = {
            "serial": serial,
            "firmware_version": fw_version,
            "lid_status": lid_status,
            "lid_temperature_c": lid_temp,
            "plate_temperature_c": plate_temp
        }

        lid_test_pass = True
        if lid_status != "open":
            try:
                await module.open_lid()
                await asyncio.sleep(2)
                if module.lid_status != "open":
                    lid_test_pass = False
            except:
                lid_test_pass = False

        # Leave lid open for safety
        try:
            await module.deactivate_lid()
            await module.deactivate_block()
        except:
            pass

        if lid_test_pass and lid_temp is not None and plate_temp is not None:
            return TestResult(
                name=f"Thermocycler ({serial})",
                status=TestStatus.PASS,
                message=f"Lid: {module.lid_status}, Lid temp: {lid_temp}C, Plate temp: {plate_temp}C",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Thermocycler ({serial})",
                status=TestStatus.WARNING,
                message="Some functionality limited",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Thermocycler ({serial})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def test_heater_shaker(module) -> TestResult:
    """Test Heater-Shaker."""
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        temp = module.temperature
        speed = module.speed
        latch = module.labware_latch_status
        fw_version = module.device_info.get("version", "unknown")

        data = {
            "serial": serial,
            "firmware_version": fw_version,
            "temperature_c": temp,
            "speed_rpm": speed,
            "labware_latch": latch
        }

        latch_works = True
        try:
            await module.open_labware_latch()
            await asyncio.sleep(1)
            if "open" not in module.labware_latch_status:
                latch_works = False
            await module.close_labware_latch()
            await asyncio.sleep(1)
        except:
            latch_works = False

        # Ensure heater/shaker are off
        try:
            await module.deactivate_heater()
            await module.deactivate_shaker()
        except:
            pass

        if temp is not None and latch_works:
            return TestResult(
                name=f"Heater-Shaker ({serial})",
                status=TestStatus.PASS,
                message=f"Temperature: {temp}C, Latch: functional",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name=f"Heater-Shaker ({serial})",
                status=TestStatus.WARNING,
                message="Some functionality limited",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name=f"Heater-Shaker ({serial})",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


async def run_module_tests() -> Dict[str, Any]:
    """Run all module tests."""
    print_section_header("MODULE TESTS")

    section_results = {"tests": [], "modules_found": 0, "overall_status": "PASS"}

    if SKIP_MODULES:
        print("Skipping module tests (SKIP_MODULES=True)")
        section_results["overall_status"] = "SKIPPED"
        return section_results

    if not api:
        print("Hardware not available - skipping module tests")
        section_results["overall_status"] = "SKIPPED"
        return section_results

    try:
        modules = api.attached_modules
        section_results["modules_found"] = len(modules)

        if not modules:
            print("  No modules detected")
            result = TestResult(
                name="Module Detection",
                status=TestStatus.WARNING,
                message="No modules attached"
            )
            section_results["tests"].append(result.to_dict())
            all_results.append(result)
        else:
            print(f"  Found {len(modules)} module(s)")

            for module in modules:
                module_type = module.name()
                serial = module.device_info.get("serial", "unknown")
                print(f"\n  Testing: {module_type} ({serial})")

                if "temperature" in module_type.lower():
                    result = await test_temperature_module(module)
                elif "magnetic" in module_type.lower():
                    result = await test_magnetic_module(module)
                elif "thermocycler" in module_type.lower():
                    result = await test_thermocycler(module)
                elif "heater" in module_type.lower():
                    result = await test_heater_shaker(module)
                else:
                    result = TestResult(
                        name=f"Unknown Module ({serial})",
                        status=TestStatus.WARNING,
                        message=f"Unknown module type: {module_type}"
                    )

                section_results["tests"].append(result.to_dict())
                all_results.append(result)
                print_test_result(result)

    except Exception as e:
        result = TestResult(
            name="Module Discovery",
            status=TestStatus.ERROR,
            message=str(e)
        )
        section_results["tests"].append(result.to_dict())
        all_results.append(result)

    # Determine section status
    statuses = [t["status"] for t in section_results["tests"]]
    if "FAIL" in statuses:
        section_results["overall_status"] = "FAIL"
    elif "WARNING" in statuses:
        section_results["overall_status"] = "WARNING"

    report["test_sections"]["modules"] = section_results
    print(f"\nModule tests complete - Overall: {section_results['overall_status']}")
    return section_results


# Run module tests
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        module_results = await run_module_tests()
    else:
        module_results = asyncio.run(run_module_tests())
except RuntimeError:
    module_results = asyncio.run(run_module_tests())

# %% [markdown]
# ## Section 8: Calibration Verification
#
# Verify all calibration data:
# - Deck calibration
# - Pipette calibrations
# - Tip length calibrations

# %%
# =============================================================================
# SECTION 8: CALIBRATION VERIFICATION
# =============================================================================

def test_deck_calibration() -> TestResult:
    """Check deck calibration."""
    start = time.time()

    try:
        deck_cal_file = Path("/data/opentrons/robot/deck_calibration.json")

        if not deck_cal_file.exists():
            return TestResult(
                name="Deck Calibration",
                status=TestStatus.WARNING,
                message="Deck not calibrated",
                duration_seconds=time.time() - start
            )

        with open(deck_cal_file) as f:
            cal_data = json.load(f)

        attitude = cal_data.get("attitude", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        last_modified = cal_data.get("last_modified", "unknown")

        # Validate matrix
        if ON_ROBOT:
            arr = np.array(attitude)
            det = np.linalg.det(arr)
            rank = np.linalg.matrix_rank(arr)
            is_identity = np.allclose(arr, np.eye(3))
        else:
            # Simplified check without numpy
            det = 1.0
            rank = 3
            is_identity = attitude == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        data = {
            "last_modified": last_modified,
            "source": cal_data.get("source", "unknown"),
            "determinant": round(float(det), 6),
            "rank": int(rank),
            "is_identity": bool(is_identity),
            "pipette_used": cal_data.get("pipette_calibrated_with", "unknown")
        }

        if rank == 3 and 0.5 < abs(det) < 2.0:
            if is_identity:
                return TestResult(
                    name="Deck Calibration",
                    status=TestStatus.WARNING,
                    message="Deck calibration is identity (may need recalibration)",
                    data=data,
                    duration_seconds=time.time() - start
                )
            else:
                return TestResult(
                    name="Deck Calibration",
                    status=TestStatus.PASS,
                    message=f"Deck calibrated (modified: {last_modified})",
                    data=data,
                    duration_seconds=time.time() - start
                )
        else:
            return TestResult(
                name="Deck Calibration",
                status=TestStatus.FAIL,
                message="Deck calibration matrix invalid",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Deck Calibration",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def test_all_pipette_calibrations() -> TestResult:
    """Check all pipette calibrations."""
    start = time.time()

    try:
        pip_cal_dir = Path("/data/opentrons/robot/pipettes")
        calibrations = {"left": [], "right": []}

        for mount in ["left", "right"]:
            mount_dir = pip_cal_dir / mount
            if mount_dir.exists():
                for cal_file in mount_dir.glob("*.json"):
                    with open(cal_file) as f:
                        cal_data = json.load(f)
                    calibrations[mount].append({
                        "pipette_id": cal_file.stem,
                        "offset": cal_data.get("offset", [0, 0, 0]),
                        "last_modified": cal_data.get("last_modified", "unknown")
                    })

        total_cals = len(calibrations["left"]) + len(calibrations["right"])

        if total_cals > 0:
            return TestResult(
                name="Pipette Calibrations",
                status=TestStatus.PASS,
                message=f"Found {total_cals} pipette calibration(s)",
                data=calibrations,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name="Pipette Calibrations",
                status=TestStatus.WARNING,
                message="No pipette calibrations found",
                data=calibrations,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Pipette Calibrations",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def test_tip_length_calibrations() -> TestResult:
    """Check tip length calibrations."""
    start = time.time()

    try:
        tip_length_dir = Path("/data/opentrons/tip_lengths")
        tip_lengths = {}

        if tip_length_dir.exists():
            for cal_file in tip_length_dir.glob("*.json"):
                with open(cal_file) as f:
                    cal_data = json.load(f)
                tip_lengths[cal_file.stem] = {
                    "tiprack_count": len(cal_data) if isinstance(cal_data, dict) else 0
                }

        if tip_lengths:
            total_tipracks = sum(t["tiprack_count"] for t in tip_lengths.values())
            return TestResult(
                name="Tip Length Calibrations",
                status=TestStatus.PASS,
                message=f"Found {len(tip_lengths)} pipette(s) with {total_tipracks} tiprack calibration(s)",
                data=tip_lengths,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name="Tip Length Calibrations",
                status=TestStatus.WARNING,
                message="No tip length calibrations found",
                data={},
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Tip Length Calibrations",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def run_calibration_tests() -> Dict[str, Any]:
    """Run all calibration tests."""
    print_section_header("CALIBRATION VERIFICATION")

    section_results = {"tests": [], "overall_status": "PASS"}

    # Deck Calibration
    print("\n  Checking: Deck Calibration...")
    result = test_deck_calibration()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Pipette Calibrations
    print("\n  Checking: Pipette Calibrations...")
    result = test_all_pipette_calibrations()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Tip Length Calibrations
    print("\n  Checking: Tip Length Calibrations...")
    result = test_tip_length_calibrations()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Determine section status
    statuses = [t["status"] for t in section_results["tests"]]
    if "FAIL" in statuses:
        section_results["overall_status"] = "FAIL"
    elif "WARNING" in statuses:
        section_results["overall_status"] = "WARNING"

    report["test_sections"]["calibration"] = section_results
    print(f"\nCalibration tests complete - Overall: {section_results['overall_status']}")
    return section_results


# Run calibration tests
calibration_results = run_calibration_tests()

# %% [markdown]
# ## Section 9: System Health
#
# Test overall system health:
# - Disk space
# - Recent error logs
# - Service status

# %%
# =============================================================================
# SECTION 9: SYSTEM HEALTH
# =============================================================================

def test_disk_space() -> TestResult:
    """Check disk space."""
    start = time.time()

    try:
        total, used, free = shutil.disk_usage("/data")
        percent_used = (used / total) * 100

        data = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "percent_used": round(percent_used, 1)
        }

        if percent_used < 80:
            return TestResult(
                name="Disk Space",
                status=TestStatus.PASS,
                message=f"{data['free_gb']}GB free ({percent_used:.1f}% used)",
                data=data,
                duration_seconds=time.time() - start
            )
        elif percent_used < 95:
            return TestResult(
                name="Disk Space",
                status=TestStatus.WARNING,
                message=f"Disk space running low ({percent_used:.1f}% used)",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name="Disk Space",
                status=TestStatus.FAIL,
                message=f"Disk space critical ({percent_used:.1f}% used)",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Disk Space",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def test_error_logs() -> TestResult:
    """Check recent error logs."""
    start = time.time()

    try:
        _, stdout, _ = run_shell_command(
            "journalctl --since '24 hours ago' -p err --no-pager | tail -20"
        )

        error_lines = stdout.strip().split('\n') if stdout.strip() else []
        error_count = len([l for l in error_lines if l.strip()])

        data = {
            "errors_last_24h": error_count,
            "recent_errors": error_lines[-5:] if error_lines else []
        }

        if error_count == 0:
            return TestResult(
                name="Recent Error Logs",
                status=TestStatus.PASS,
                message="No errors in last 24 hours",
                data=data,
                duration_seconds=time.time() - start
            )
        elif error_count < 10:
            return TestResult(
                name="Recent Error Logs",
                status=TestStatus.WARNING,
                message=f"{error_count} error(s) in last 24 hours",
                data=data,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name="Recent Error Logs",
                status=TestStatus.WARNING,
                message=f"{error_count} errors in last 24 hours (elevated)",
                data=data,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Recent Error Logs",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def test_services_status() -> TestResult:
    """Check key services status."""
    start = time.time()

    services = [
        "opentrons-robot-server",
        "opentrons-update-server"
    ]

    try:
        service_status = {}
        all_running = True

        for service in services:
            _, stdout, _ = run_shell_command(f"systemctl is-active {service}")
            is_active = stdout.strip() == "active"
            service_status[service] = "active" if is_active else "inactive"
            if not is_active:
                all_running = False

        if all_running:
            return TestResult(
                name="Services Status",
                status=TestStatus.PASS,
                message="All services running",
                data=service_status,
                duration_seconds=time.time() - start
            )
        else:
            return TestResult(
                name="Services Status",
                status=TestStatus.WARNING,
                message="Some services not running",
                data=service_status,
                duration_seconds=time.time() - start
            )
    except Exception as e:
        return TestResult(
            name="Services Status",
            status=TestStatus.ERROR,
            message=str(e),
            duration_seconds=time.time() - start
        )


def run_system_health_tests() -> Dict[str, Any]:
    """Run all system health tests."""
    print_section_header("SYSTEM HEALTH")

    section_results = {"tests": [], "overall_status": "PASS"}

    # Disk Space
    print("\n  Checking: Disk Space...")
    result = test_disk_space()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Error Logs
    print("\n  Checking: Recent Error Logs...")
    result = test_error_logs()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Services Status
    print("\n  Checking: Services Status...")
    result = test_services_status()
    section_results["tests"].append(result.to_dict())
    all_results.append(result)
    print_test_result(result)

    # Determine section status
    statuses = [t["status"] for t in section_results["tests"]]
    if "FAIL" in statuses:
        section_results["overall_status"] = "FAIL"
    elif "WARNING" in statuses:
        section_results["overall_status"] = "WARNING"

    report["test_sections"]["system_health"] = section_results
    print(f"\nSystem health tests complete - Overall: {section_results['overall_status']}")
    return section_results


# Run system health tests
health_results = run_system_health_tests()

# %% [markdown]
# ## Section 10: Report Generation
#
# Generate the final summary and save the report to a JSON file.

# %%
# =============================================================================
# SECTION 10: REPORT GENERATION
# =============================================================================

def generate_summary() -> Dict[str, Any]:
    """Generate report summary and recommendations."""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Count results
    counts = {
        "total": len(all_results),
        "pass": sum(1 for r in all_results if r.status == TestStatus.PASS),
        "fail": sum(1 for r in all_results if r.status == TestStatus.FAIL),
        "warning": sum(1 for r in all_results if r.status == TestStatus.WARNING),
        "error": sum(1 for r in all_results if r.status == TestStatus.ERROR),
        "skipped": sum(1 for r in all_results if r.status == TestStatus.SKIPPED)
    }

    # Determine overall status
    if counts["fail"] > 0 or counts["error"] > 0:
        overall = "FAIL"
    elif counts["warning"] > 0:
        overall = "WARNING"
    else:
        overall = "PASS"

    report["summary"] = {
        "overall_status": overall,
        "test_counts": counts,
        "duration_seconds": round(duration, 1),
        "completed_at": end_time.isoformat()
    }

    # Generate recommendations
    recommendations = []

    for result in all_results:
        if result.status == TestStatus.FAIL:
            recommendations.append({
                "priority": "HIGH",
                "test": result.name,
                "issue": result.message,
                "action": f"Investigate and resolve: {result.name}"
            })
        elif result.status == TestStatus.WARNING:
            recommendations.append({
                "priority": "MEDIUM",
                "test": result.name,
                "issue": result.message,
                "action": f"Review and address if necessary: {result.name}"
            })

    # Add standard recommendations
    if not any("Deck Calibration" in r["test"] for r in recommendations):
        deck_test = next((r for r in all_results if "Deck Calibration" in r.name), None)
        if deck_test and "identity" in deck_test.message.lower():
            recommendations.append({
                "priority": "MEDIUM",
                "test": "Deck Calibration",
                "issue": "Deck calibration appears to be default",
                "action": "Perform deck calibration for optimal accuracy"
            })

    report["recommendations"] = recommendations
    return report["summary"]


def save_report(output_dir: Optional[str] = None) -> str:
    """Save the full report to JSON file."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"service_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = output_path / filename

    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return str(filepath)


def print_summary():
    """Print summary to console."""
    summary = report["summary"]
    counts = summary["test_counts"]

    print("\n" + "=" * 70)
    print(" DIAGNOSTIC COMPLETE - SUMMARY")
    print("=" * 70)

    # Overall status
    print(f"\n  Overall Status: {summary['overall_status']}")
    print(f"  Duration: {summary['duration_seconds']:.1f} seconds")

    print(f"\n  Test Results:")
    print(f"    Total:    {counts['total']}")
    print(f"    Passed:   {counts['pass']}")
    print(f"    Failed:   {counts['fail']}")
    print(f"    Warnings: {counts['warning']}")
    print(f"    Errors:   {counts['error']}")
    print(f"    Skipped:  {counts['skipped']}")

    if report["recommendations"]:
        print(f"\n  Recommendations ({len(report['recommendations'])}):\n")
        for rec in report["recommendations"][:5]:
            print(f"    [{rec['priority']}] {rec['test']}")
            print(f"       -> {rec['action']}")
        if len(report["recommendations"]) > 5:
            print(f"\n    ... and {len(report['recommendations']) - 5} more")

    print("\n" + "=" * 70)


# Generate summary
print_section_header("GENERATING REPORT")
summary = generate_summary()

# Print summary
print_summary()

# %%
# Save report to file
try:
    report_path = save_report()
    print(f"\nReport saved to: {report_path}")
except Exception as e:
    print(f"\nCould not save report: {e}")
    print("  You can still access the report data via the 'report' variable.")

# %% [markdown]
# ## View Full Report
#
# Run this cell to view the complete report data.

# %%
# View the full report as formatted JSON
print(json.dumps(report, indent=2, default=str))

# %% [markdown]
# ## View All Test Results
#
# Run this cell to see all test results in a list.

# %%
# Display all test results
print("\nAll Test Results:")
print("-" * 70)
for result in all_results:
    status_symbols = {
        TestStatus.PASS: "[PASS]",
        TestStatus.FAIL: "[FAIL]",
        TestStatus.WARNING: "[WARN]",
        TestStatus.SKIPPED: "[SKIP]",
        TestStatus.ERROR: "[ERR ]"
    }
    symbol = status_symbols.get(result.status, "[????]")
    print(f"{symbol} {result.name}")
    print(f"       {result.message}")
    print(f"       Duration: {result.duration_seconds:.2f}s")
    print()

# %% [markdown]
# ## Cleanup (Optional)
#
# Run this cell to properly disconnect from hardware when done.

# %%
# Cleanup - disconnect from hardware
async def cleanup():
    if api:
        try:
            # Home the robot before disconnecting
            await api.home()
            print("Robot homed")

            # Clean up
            await api.clean_up()
            print("Hardware disconnected")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    else:
        print("No hardware connection to clean up")


try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        await cleanup()
    else:
        asyncio.run(cleanup())
except RuntimeError:
    asyncio.run(cleanup())

# %% [markdown]
# ---
#
# ## Running as a Script
#
# You can also run this entire file as a script from the command line:
#
# ```bash
# python ot2_service_diagnostic_notebook.py
# ```
#
# To modify options, edit the Configuration section (Section 2) before running.
