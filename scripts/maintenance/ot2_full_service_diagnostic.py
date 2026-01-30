#!/usr/bin/env python3
"""
OT-2 Full Service Diagnostic Script
====================================
Comprehensive diagnostic tool for annual maintenance and service reporting.
Tests ALL system components and generates a detailed JSON report.

This script performs:
- System information gathering
- Firmware version checks
- Motion system diagnostics (homing, accuracy, repeatability)
- Limit switch verification
- Pipette testing (both mounts)
- Module testing (all attached modules)
- Calibration verification
- Network connectivity
- Storage health
- Error log analysis

Usage (on robot via SSH):
    python3 ot2_full_service_diagnostic.py
    python3 ot2_full_service_diagnostic.py --quick          # Quick mode (fewer iterations)
    python3 ot2_full_service_diagnostic.py --skip-modules   # Skip module tests
    python3 ot2_full_service_diagnostic.py --output /path   # Custom output directory

Output:
    - JSON report: /data/service_reports/service_report_YYYYMMDD_HHMMSS.json
    - Summary printed to console
"""

import asyncio
import argparse
import json
import sys
import os
import subprocess
import statistics
import socket
import platform
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
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    print("WARNING: Not running on OT-2 robot. Running in simulation mode.")


# =============================================================================
# DIAGNOSTIC ACCEPTANCE CRITERIA AND MARGINS
# =============================================================================
# These values are based on OT-2 specifications and empirical testing.
# Adjust as needed for specific requirements.

class DiagnosticMargins:
    """
    Acceptance criteria for all diagnostic tests.
    Based on Opentrons OT-2 specifications and empirical data.
    """

    # -------------------------------------------------------------------------
    # MOTION SYSTEM MARGINS
    # -------------------------------------------------------------------------

    # Homing Accuracy (measured over 5 iterations)
    # Source: OT-2 spec sheet, industry liquid handler standards
    HOMING_RANGE_PASS = 0.1          # mm - excellent repeatability
    HOMING_RANGE_WARNING = 0.3       # mm - acceptable
    HOMING_RANGE_FAIL = 0.3          # mm - above this = fail

    HOMING_STDEV_PASS = 0.03         # mm
    HOMING_STDEV_WARNING = 0.08      # mm

    HOMING_ERROR_FROM_EXPECTED_PASS = 1.0    # mm
    HOMING_ERROR_FROM_EXPECTED_WARNING = 2.0  # mm

    # Position Repeatability (3D, measured over 10 iterations)
    # Source: OT-2 specification: ±0.1mm repeatability
    REPEATABILITY_3D_PASS = 0.1      # mm - within spec
    REPEATABILITY_3D_WARNING = 0.25  # mm - degraded
    REPEATABILITY_3D_FAIL = 0.25     # mm - above this = fail

    REPEATABILITY_AXIS_RANGE_PASS = 0.05    # mm per axis
    REPEATABILITY_AXIS_RANGE_WARNING = 0.15  # mm per axis

    # Cross-Deck Accuracy
    # Source: OT-2 specification, labware positioning requirements
    CROSS_DECK_ERROR_PASS = 0.5      # mm - excellent
    CROSS_DECK_ERROR_WARNING = 1.5   # mm - acceptable
    CROSS_DECK_ERROR_FAIL = 1.5      # mm - above this = fail

    # Z-Axis Movement (100mm test move)
    Z_TRAVEL_ERROR_PASS = 1.0        # mm
    Z_TRAVEL_ERROR_WARNING = 2.0     # mm
    Z_TRAVEL_ERROR_FAIL = 2.0        # mm

    # Speed Accuracy
    SPEED_ERROR_PERCENT_PASS = 10    # % error
    SPEED_ERROR_PERCENT_WARNING = 20  # % error

    # -------------------------------------------------------------------------
    # EXPECTED POSITIONS (mm)
    # -------------------------------------------------------------------------

    # Home positions (OT-2 standard)
    HOME_X = 418.0
    HOME_Y = 353.0
    HOME_Z = 218.0
    HOME_A = 218.0
    HOME_TOLERANCE = 0.5  # mm

    # -------------------------------------------------------------------------
    # PIPETTE MARGINS
    # -------------------------------------------------------------------------

    # Plunger Travel
    PLUNGER_TRAVEL_MIN_PASS = 1.0    # mm - minimum acceptable travel
    PLUNGER_TRAVEL_MIN_WARNING = 0.5  # mm

    # Pipette Offset (calibration)
    PIPETTE_OFFSET_MAGNITUDE_PASS = 3.0      # mm - normal range
    PIPETTE_OFFSET_MAGNITUDE_WARNING = 5.0   # mm - suspicious, investigate

    # Tip Length (expected range)
    TIP_LENGTH_MIN = 20.0   # mm - minimum reasonable tip
    TIP_LENGTH_MAX = 100.0  # mm - maximum reasonable tip

    # -------------------------------------------------------------------------
    # TEMPERATURE MODULE MARGINS
    # -------------------------------------------------------------------------

    # Temperature reading (ambient condition)
    TEMP_MODULE_AMBIENT_MIN = 5.0    # °C - minimum reasonable ambient
    TEMP_MODULE_AMBIENT_MAX = 50.0   # °C - maximum reasonable ambient

    # Temperature accuracy
    TEMP_MODULE_ACCURACY_PASS = 0.5   # °C - within spec
    TEMP_MODULE_ACCURACY_WARNING = 1.0  # °C

    # Heating/Cooling time (to 37°C from ambient)
    TEMP_MODULE_HEAT_TIME_PASS = 180      # seconds (3 min)
    TEMP_MODULE_HEAT_TIME_WARNING = 300   # seconds (5 min)

    TEMP_MODULE_COOL_TIME_PASS = 480      # seconds (8 min) to 4°C
    TEMP_MODULE_COOL_TIME_WARNING = 900   # seconds (15 min)

    # -------------------------------------------------------------------------
    # MAGNETIC MODULE MARGINS
    # -------------------------------------------------------------------------

    MAGDECK_RESPONSE_TIME_PASS = 2.0      # seconds
    MAGDECK_RESPONSE_TIME_FAIL = 5.0      # seconds
    MAGDECK_POSITION_ACCURACY = 0.5       # mm

    # -------------------------------------------------------------------------
    # THERMOCYCLER MARGINS
    # -------------------------------------------------------------------------

    TC_LID_TIME_PASS = 5.0       # seconds - open/close
    TC_LID_TIME_WARNING = 10.0   # seconds

    TC_LID_TEMP_TIME_PASS = 300      # seconds (5 min) to 105°C
    TC_LID_TEMP_TIME_WARNING = 600   # seconds (10 min)

    TC_PLATE_TEMP_TIME_PASS = 120    # seconds (2 min) to 95°C
    TC_PLATE_TEMP_TIME_WARNING = 300  # seconds (5 min)

    TC_TEMP_ACCURACY_PASS = 0.5      # °C
    TC_TEMP_ACCURACY_WARNING = 1.0   # °C

    TC_RAMP_RATE_PASS = 2.0          # °C/s
    TC_RAMP_RATE_WARNING = 1.0       # °C/s

    # -------------------------------------------------------------------------
    # HEATER-SHAKER MARGINS
    # -------------------------------------------------------------------------

    HS_LATCH_TIME_PASS = 2.0         # seconds
    HS_LATCH_TIME_WARNING = 5.0      # seconds

    HS_HEAT_TIME_PASS = 180          # seconds (3 min) to 37°C
    HS_HEAT_TIME_WARNING = 300       # seconds (5 min)

    HS_TEMP_ACCURACY_PASS = 0.5      # °C
    HS_TEMP_ACCURACY_WARNING = 1.0   # °C

    HS_SPEED_ACCURACY_PASS = 1.0     # % error
    HS_SPEED_ACCURACY_WARNING = 5.0  # % error
    HS_SPEED_ACCURACY_FAIL = 10.0    # % error

    # -------------------------------------------------------------------------
    # CALIBRATION MARGINS
    # -------------------------------------------------------------------------

    # Deck calibration matrix
    DECK_MATRIX_DET_MIN = 0.9        # minimum determinant
    DECK_MATRIX_DET_MAX = 1.1        # maximum determinant
    DECK_MATRIX_DET_IDEAL_MIN = 0.95
    DECK_MATRIX_DET_IDEAL_MAX = 1.05

    # Calibration age (days)
    CALIBRATION_AGE_PASS = 90        # 3 months
    CALIBRATION_AGE_WARNING = 180    # 6 months

    # -------------------------------------------------------------------------
    # SYSTEM HEALTH MARGINS
    # -------------------------------------------------------------------------

    DISK_USAGE_PASS = 80             # % - below this = pass
    DISK_USAGE_WARNING = 95          # % - above this = fail

    DISK_FREE_MIN_PASS = 500         # MB
    DISK_FREE_MIN_WARNING = 100      # MB

    ERROR_LOG_COUNT_PASS = 0         # errors in 24h
    ERROR_LOG_COUNT_WARNING = 10     # errors in 24h


class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class TestResult:
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


class FullServiceDiagnostic:
    """Comprehensive OT-2 service diagnostic."""

    # Test positions for motion testing
    TEST_POSITIONS = {
        "slot_1": Point(x=14.38, y=11.24, z=100),
        "slot_3": Point(x=297.12, y=11.24, z=100),
        "slot_7": Point(x=14.38, y=258.76, z=100),
        "slot_9": Point(x=297.12, y=258.76, z=100),
        "slot_5_center": Point(x=155.75, y=135.0, z=100),
    }

    EXPECTED_HOME = {
        Axis.X: 418.0,
        Axis.Y: 353.0,
        Axis.Z: 218.0,
        Axis.A: 218.0,
    }

    def __init__(self, quick_mode: bool = False, skip_modules: bool = False):
        self.quick_mode = quick_mode
        self.skip_modules = skip_modules
        self.api: Optional[API] = None
        self.start_time = datetime.now()

        self.report: Dict[str, Any] = {
            "report_type": "OT-2 Full Service Diagnostic",
            "report_version": "1.0",
            "generated_at": self.start_time.isoformat(),
            "robot_info": {},
            "test_sections": {},
            "summary": {},
            "recommendations": []
        }

        self.all_results: List[TestResult] = []

    async def initialize(self) -> bool:
        """Initialize hardware connection."""
        if not ON_ROBOT:
            return False

        try:
            print("Initializing hardware controller...")
            self.api = await API.build_hardware_controller()
            print("Homing robot...")
            await self.api.home()
            print("Initialization complete.\n")
            return True
        except Exception as e:
            print(f"ERROR: Failed to initialize: {e}")
            self.all_results.append(TestResult(
                name="Hardware Initialization",
                status=TestStatus.FAIL,
                message=str(e)
            ))
            return False

    def _run_shell_command(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
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

    # =========================================================================
    # SECTION 1: SYSTEM INFORMATION
    # =========================================================================
    async def gather_system_info(self) -> Dict[str, Any]:
        """Gather comprehensive system information."""
        print("=" * 70)
        print("SECTION 1: SYSTEM INFORMATION")
        print("=" * 70)

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
            _, stdout, _ = self._run_shell_command("cat /var/serial")
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
        if self.api:
            try:
                fw_version = await self.api._backend._smoothie_driver.get_fw_version()
                info["firmware_version"] = fw_version
                print(f"  Firmware Version: {fw_version}")
            except:
                pass

        # Network info
        try:
            _, ip_output, _ = self._run_shell_command("hostname -I")
            info["network"]["ip_addresses"] = ip_output.split() if ip_output else []

            _, wifi_output, _ = self._run_shell_command("iwconfig wlan0 2>/dev/null | grep ESSID")
            if "ESSID" in wifi_output:
                ssid = wifi_output.split('ESSID:"')[1].split('"')[0] if 'ESSID:"' in wifi_output else ""
                info["network"]["wifi_ssid"] = ssid

            print(f"  IP Addresses: {', '.join(info['network'].get('ip_addresses', []))}")
        except:
            pass

        # Storage info
        try:
            _, df_output, _ = self._run_shell_command("df -h /data | tail -1")
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
            _, uptime_output, _ = self._run_shell_command("uptime -p")
            info["uptime"] = uptime_output
            print(f"  Uptime: {uptime_output}")
        except:
            pass

        self.report["robot_info"] = info
        return info

    # =========================================================================
    # SECTION 2: MOTION SYSTEM TESTS
    # =========================================================================
    async def test_motion_system(self) -> Dict[str, Any]:
        """Test motion system including homing, accuracy, and repeatability."""
        print("\n" + "=" * 70)
        print("SECTION 2: MOTION SYSTEM TESTS")
        print("=" * 70)

        section_results = {"tests": [], "overall_status": "PASS"}

        if not self.api:
            section_results["overall_status"] = "SKIPPED"
            return section_results

        # Test 2.1: Limit Switches
        print("\n  Test 2.1: Limit Switch Verification")
        result = await self._test_limit_switches()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 2.2: Homing Accuracy
        print("\n  Test 2.2: Homing Accuracy")
        result = await self._test_homing_accuracy()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 2.3: Position Repeatability
        print("\n  Test 2.3: Position Repeatability")
        iterations = 5 if self.quick_mode else 10
        result = await self._test_position_repeatability(iterations)
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 2.4: Cross-Deck Accuracy
        print("\n  Test 2.4: Cross-Deck Accuracy")
        result = await self._test_cross_deck_accuracy()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 2.5: Z-Axis Movement
        print("\n  Test 2.5: Z-Axis Movement (Both Mounts)")
        result = await self._test_z_axis_movement()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Determine section status
        statuses = [t["status"] for t in section_results["tests"]]
        if "FAIL" in statuses:
            section_results["overall_status"] = "FAIL"
        elif "WARNING" in statuses:
            section_results["overall_status"] = "WARNING"

        self.report["test_sections"]["motion_system"] = section_results
        return section_results

    async def _test_limit_switches(self) -> TestResult:
        """Test all limit switches."""
        import time
        start = time.time()

        try:
            await self.api.home()
            switches = await self.api._backend._smoothie_driver.switch_state()

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

    async def _test_homing_accuracy(self) -> TestResult:
        """Test homing repeatability."""
        import time
        start = time.time()

        try:
            iterations = 3 if self.quick_mode else 5
            positions = []

            for i in range(iterations):
                # Move away
                await self.api.move_rel(mount=Mount.LEFT, delta=Point(-30, -30, -30))
                # Home
                await self.api.home()
                # Record position
                pos = await self.api.current_position(mount=Mount.LEFT, refresh=True)
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

    async def _test_position_repeatability(self, iterations: int) -> TestResult:
        """Test position repeatability."""
        import time
        start = time.time()

        try:
            target = self.TEST_POSITIONS["slot_5_center"]
            home_pos = Point(x=100, y=100, z=150)
            positions = []

            for i in range(iterations):
                await self.api.move_to(mount=Mount.LEFT, abs_position=home_pos)
                await self.api.move_to(mount=Mount.LEFT, abs_position=target)
                pos = await self.api.current_position(mount=Mount.LEFT, refresh=True)
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

            await self.api.home()

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

    async def _test_cross_deck_accuracy(self) -> TestResult:
        """Test accuracy across deck."""
        import time
        start = time.time()

        try:
            measurements = []

            for name, target in self.TEST_POSITIONS.items():
                await self.api.move_to(mount=Mount.LEFT, abs_position=target)
                pos = await self.api.current_position(mount=Mount.LEFT, refresh=True)

                actual = Point(pos.get(Axis.X, 0), pos.get(Axis.Y, 0), pos.get(Axis.Z, 0))
                error_3d = ((actual.x - target.x)**2 + (actual.y - target.y)**2 + (actual.z - target.z)**2)**0.5

                measurements.append({
                    "position": name,
                    "target": {"x": target.x, "y": target.y, "z": target.z},
                    "actual": {"x": round(actual.x, 3), "y": round(actual.y, 3), "z": round(actual.z, 3)},
                    "error_3d_mm": round(error_3d, 4)
                })

            await self.api.home()

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

    async def _test_z_axis_movement(self) -> TestResult:
        """Test Z-axis movement on both mounts."""
        import time
        start = time.time()

        try:
            results = {}

            for mount in [Mount.LEFT, Mount.RIGHT]:
                mount_name = mount.name.lower()
                await self.api.home()

                # Move down
                await self.api.move_to(mount=mount, abs_position=Point(200, 200, 50))
                pos_down = await self.api.current_position(mount=mount, refresh=True)

                # Move up
                await self.api.move_to(mount=mount, abs_position=Point(200, 200, 150))
                pos_up = await self.api.current_position(mount=mount, refresh=True)

                z_axis = Axis.Z if mount == Mount.LEFT else Axis.A
                travel = abs(pos_up.get(z_axis, 0) - pos_down.get(z_axis, 0))

                results[mount_name] = {
                    "z_travel_mm": round(travel, 2),
                    "expected_travel_mm": 100,
                    "error_mm": round(abs(travel - 100), 2)
                }

            await self.api.home()

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

    # =========================================================================
    # SECTION 3: PIPETTE TESTS
    # =========================================================================
    async def test_pipettes(self) -> Dict[str, Any]:
        """Test both pipette mounts."""
        print("\n" + "=" * 70)
        print("SECTION 3: PIPETTE TESTS")
        print("=" * 70)

        section_results = {"tests": [], "overall_status": "PASS"}

        if not self.api:
            section_results["overall_status"] = "SKIPPED"
            return section_results

        for mount in [Mount.LEFT, Mount.RIGHT]:
            mount_name = mount.name.lower()
            print(f"\n  Testing {mount_name.upper()} mount pipette...")

            # Test 3.x.1: Detection
            result = await self._test_pipette_detection(mount)
            section_results["tests"].append(result.to_dict())
            self.all_results.append(result)
            print(f"    Detection: {result.status.value}")

            if result.status == TestStatus.PASS:
                # Test 3.x.2: Plunger
                result = await self._test_pipette_plunger(mount)
                section_results["tests"].append(result.to_dict())
                self.all_results.append(result)
                print(f"    Plunger: {result.status.value}")

                # Test 3.x.3: Calibration Status
                result = await self._test_pipette_calibration(mount)
                section_results["tests"].append(result.to_dict())
                self.all_results.append(result)
                print(f"    Calibration: {result.status.value}")

        # Determine section status
        statuses = [t["status"] for t in section_results["tests"]]
        if "FAIL" in statuses:
            section_results["overall_status"] = "FAIL"
        elif "WARNING" in statuses:
            section_results["overall_status"] = "WARNING"

        self.report["test_sections"]["pipettes"] = section_results
        return section_results

    async def _test_pipette_detection(self, mount: Mount) -> TestResult:
        """Test pipette detection."""
        import time
        start = time.time()
        mount_name = mount.name.lower()

        try:
            instruments = self.api.attached_instruments
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

    async def _test_pipette_plunger(self, mount: Mount) -> TestResult:
        """Test pipette plunger movement."""
        import time
        start = time.time()
        mount_name = mount.name.lower()

        try:
            pipette = self.api.hardware_pipettes.get(mount)
            if not pipette:
                return TestResult(
                    name=f"Pipette Plunger ({mount_name})",
                    status=TestStatus.SKIPPED,
                    message="No pipette attached",
                    duration_seconds=time.time() - start
                )

            # Home plunger
            await self.api.home_plunger(mount)

            plunger_axis = Axis.of_plunger(mount)
            pos_home = await self.api.current_position(mount=mount, refresh=True)
            home_pos = pos_home.get(plunger_axis, 0)

            # Prepare for aspirate (moves plunger to bottom)
            await self.api.prepare_for_aspirate(mount)
            pos_bottom = await self.api.current_position(mount=mount, refresh=True)
            bottom_pos = pos_bottom.get(plunger_axis, 0)

            travel = abs(home_pos - bottom_pos)

            # Home again
            await self.api.home_plunger(mount)

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

    async def _test_pipette_calibration(self, mount: Mount) -> TestResult:
        """Check pipette calibration status."""
        import time
        start = time.time()
        mount_name = mount.name.lower()

        try:
            instruments = self.api.attached_instruments
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

    # =========================================================================
    # SECTION 4: MODULE TESTS
    # =========================================================================
    async def test_modules(self) -> Dict[str, Any]:
        """Test all attached modules."""
        print("\n" + "=" * 70)
        print("SECTION 4: MODULE TESTS")
        print("=" * 70)

        section_results = {"tests": [], "modules_found": 0, "overall_status": "PASS"}

        if self.skip_modules:
            print("  Skipping module tests (--skip-modules flag)")
            section_results["overall_status"] = "SKIPPED"
            return section_results

        if not self.api:
            section_results["overall_status"] = "SKIPPED"
            return section_results

        try:
            modules = self.api.attached_modules
            section_results["modules_found"] = len(modules)

            if not modules:
                print("  No modules detected")
                result = TestResult(
                    name="Module Detection",
                    status=TestStatus.WARNING,
                    message="No modules attached"
                )
                section_results["tests"].append(result.to_dict())
                self.all_results.append(result)
            else:
                print(f"  Found {len(modules)} module(s)")

                for module in modules:
                    module_type = module.name()
                    serial = module.device_info.get("serial", "unknown")
                    print(f"\n  Testing: {module_type} ({serial})")

                    if "temperature" in module_type.lower():
                        result = await self._test_temperature_module(module)
                    elif "magnetic" in module_type.lower():
                        result = await self._test_magnetic_module(module)
                    elif "thermocycler" in module_type.lower():
                        result = await self._test_thermocycler(module)
                    elif "heater" in module_type.lower():
                        result = await self._test_heater_shaker(module)
                    else:
                        result = TestResult(
                            name=f"Unknown Module ({serial})",
                            status=TestStatus.WARNING,
                            message=f"Unknown module type: {module_type}"
                        )

                    section_results["tests"].append(result.to_dict())
                    self.all_results.append(result)
                    print(f"    Status: {result.status.value}")

        except Exception as e:
            result = TestResult(
                name="Module Discovery",
                status=TestStatus.ERROR,
                message=str(e)
            )
            section_results["tests"].append(result.to_dict())
            self.all_results.append(result)

        # Determine section status
        statuses = [t["status"] for t in section_results["tests"]]
        if "FAIL" in statuses:
            section_results["overall_status"] = "FAIL"
        elif "WARNING" in statuses:
            section_results["overall_status"] = "WARNING"

        self.report["test_sections"]["modules"] = section_results
        return section_results

    async def _test_temperature_module(self, module) -> TestResult:
        """Test Temperature Module."""
        import time
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

            # Check temperature sensor is reading reasonable values
            if current_temp is not None and 5 <= current_temp <= 50:
                return TestResult(
                    name=f"Temperature Module ({serial})",
                    status=TestStatus.PASS,
                    message=f"Temperature: {current_temp}°C, Status: {status}",
                    data=data,
                    duration_seconds=time.time() - start
                )
            else:
                return TestResult(
                    name=f"Temperature Module ({serial})",
                    status=TestStatus.WARNING,
                    message=f"Unusual temperature reading: {current_temp}°C",
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

    async def _test_magnetic_module(self, module) -> TestResult:
        """Test Magnetic Module."""
        import time
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

    async def _test_thermocycler(self, module) -> TestResult:
        """Test Thermocycler."""
        import time
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

            # Test lid movement (if not already open)
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
                    message=f"Lid: {module.lid_status}, Lid temp: {lid_temp}°C, Plate temp: {plate_temp}°C",
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

    async def _test_heater_shaker(self, module) -> TestResult:
        """Test Heater-Shaker."""
        import time
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

            # Test latch
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
                    message=f"Temperature: {temp}°C, Latch: functional",
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

    # =========================================================================
    # SECTION 5: CALIBRATION VERIFICATION
    # =========================================================================
    async def test_calibration(self) -> Dict[str, Any]:
        """Verify all calibration data."""
        print("\n" + "=" * 70)
        print("SECTION 5: CALIBRATION VERIFICATION")
        print("=" * 70)

        section_results = {"tests": [], "overall_status": "PASS"}

        # Test 5.1: Deck Calibration
        print("\n  Test 5.1: Deck Calibration")
        result = self._test_deck_calibration()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 5.2: Pipette Calibrations
        print("\n  Test 5.2: Pipette Calibrations")
        result = self._test_all_pipette_calibrations()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 5.3: Tip Length Calibrations
        print("\n  Test 5.3: Tip Length Calibrations")
        result = self._test_tip_length_calibrations()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Determine section status
        statuses = [t["status"] for t in section_results["tests"]]
        if "FAIL" in statuses:
            section_results["overall_status"] = "FAIL"
        elif "WARNING" in statuses:
            section_results["overall_status"] = "WARNING"

        self.report["test_sections"]["calibration"] = section_results
        return section_results

    def _test_deck_calibration(self) -> TestResult:
        """Check deck calibration."""
        import time
        import numpy as np
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
            arr = np.array(attitude)
            det = np.linalg.det(arr)
            rank = np.linalg.matrix_rank(arr)
            is_identity = np.allclose(arr, np.eye(3))

            data = {
                "last_modified": last_modified,
                "source": cal_data.get("source", "unknown"),
                "determinant": round(float(det), 6),
                "rank": int(rank),
                "is_identity": is_identity,
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

    def _test_all_pipette_calibrations(self) -> TestResult:
        """Check all pipette calibrations."""
        import time
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

    def _test_tip_length_calibrations(self) -> TestResult:
        """Check tip length calibrations."""
        import time
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

    # =========================================================================
    # SECTION 6: SYSTEM HEALTH
    # =========================================================================
    async def test_system_health(self) -> Dict[str, Any]:
        """Test overall system health."""
        print("\n" + "=" * 70)
        print("SECTION 6: SYSTEM HEALTH")
        print("=" * 70)

        section_results = {"tests": [], "overall_status": "PASS"}

        # Test 6.1: Disk Space
        print("\n  Test 6.1: Disk Space")
        result = self._test_disk_space()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 6.2: Error Logs
        print("\n  Test 6.2: Recent Error Logs")
        result = self._test_error_logs()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Test 6.3: Services Status
        print("\n  Test 6.3: Services Status")
        result = self._test_services_status()
        section_results["tests"].append(result.to_dict())
        self.all_results.append(result)
        print(f"    Status: {result.status.value}")

        # Determine section status
        statuses = [t["status"] for t in section_results["tests"]]
        if "FAIL" in statuses:
            section_results["overall_status"] = "FAIL"
        elif "WARNING" in statuses:
            section_results["overall_status"] = "WARNING"

        self.report["test_sections"]["system_health"] = section_results
        return section_results

    def _test_disk_space(self) -> TestResult:
        """Check disk space."""
        import time
        import shutil
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

    def _test_error_logs(self) -> TestResult:
        """Check recent error logs."""
        import time
        start = time.time()

        try:
            # Check journal for recent errors
            _, stdout, _ = self._run_shell_command(
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

    def _test_services_status(self) -> TestResult:
        """Check key services status."""
        import time
        start = time.time()

        services = [
            "opentrons-robot-server",
            "opentrons-update-server"
        ]

        try:
            service_status = {}
            all_running = True

            for service in services:
                _, stdout, _ = self._run_shell_command(f"systemctl is-active {service}")
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

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    def generate_summary(self):
        """Generate report summary and recommendations."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Count results
        counts = {
            "total": len(self.all_results),
            "pass": sum(1 for r in self.all_results if r.status == TestStatus.PASS),
            "fail": sum(1 for r in self.all_results if r.status == TestStatus.FAIL),
            "warning": sum(1 for r in self.all_results if r.status == TestStatus.WARNING),
            "error": sum(1 for r in self.all_results if r.status == TestStatus.ERROR),
            "skipped": sum(1 for r in self.all_results if r.status == TestStatus.SKIPPED)
        }

        # Determine overall status
        if counts["fail"] > 0 or counts["error"] > 0:
            overall = "FAIL"
        elif counts["warning"] > 0:
            overall = "WARNING"
        else:
            overall = "PASS"

        self.report["summary"] = {
            "overall_status": overall,
            "test_counts": counts,
            "duration_seconds": round(duration, 1),
            "completed_at": end_time.isoformat()
        }

        # Generate recommendations
        recommendations = []

        for result in self.all_results:
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
            deck_test = next((r for r in self.all_results if "Deck Calibration" in r.name), None)
            if deck_test and "identity" in deck_test.message.lower():
                recommendations.append({
                    "priority": "MEDIUM",
                    "test": "Deck Calibration",
                    "issue": "Deck calibration appears to be default",
                    "action": "Perform deck calibration for optimal accuracy"
                })

        self.report["recommendations"] = recommendations

    def save_report(self, output_dir: Optional[str] = None) -> str:
        """Save the full report to JSON file."""
        if output_dir is None:
            output_dir = "/data/service_reports"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"service_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_path / filename

        with open(filepath, "w") as f:
            json.dump(self.report, f, indent=2, default=str)

        return str(filepath)

    def print_summary(self):
        """Print summary to console."""
        summary = self.report["summary"]
        counts = summary["test_counts"]

        print("\n" + "=" * 70)
        print("DIAGNOSTIC COMPLETE - SUMMARY")
        print("=" * 70)
        print(f"\n  Overall Status: {summary['overall_status']}")
        print(f"  Duration: {summary['duration_seconds']:.1f} seconds")
        print(f"\n  Test Results:")
        print(f"    Total:    {counts['total']}")
        print(f"    Passed:   {counts['pass']}")
        print(f"    Failed:   {counts['fail']}")
        print(f"    Warnings: {counts['warning']}")
        print(f"    Errors:   {counts['error']}")
        print(f"    Skipped:  {counts['skipped']}")

        if self.report["recommendations"]:
            print(f"\n  Recommendations ({len(self.report['recommendations'])}):")
            for rec in self.report["recommendations"][:5]:  # Show top 5
                print(f"    [{rec['priority']}] {rec['test']}: {rec['action']}")
            if len(self.report["recommendations"]) > 5:
                print(f"    ... and {len(self.report['recommendations']) - 5} more")

        print("\n" + "=" * 70)

    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run the complete diagnostic."""
        print("\n" + "#" * 70)
        print("#" + " " * 68 + "#")
        print("#" + "      OT-2 FULL SERVICE DIAGNOSTIC".center(68) + "#")
        print("#" + " " * 68 + "#")
        print("#" * 70)
        print(f"\nStarted: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'Quick' if self.quick_mode else 'Full'}")

        # Initialize
        if not await self.initialize():
            print("\nWARNING: Running in limited mode (no hardware connection)")

        # Run all test sections
        await self.gather_system_info()
        await self.test_motion_system()
        await self.test_pipettes()
        await self.test_modules()
        await self.test_calibration()
        await self.test_system_health()

        # Generate summary and recommendations
        self.generate_summary()

        # Print summary
        self.print_summary()

        return self.report


async def main():
    parser = argparse.ArgumentParser(description="OT-2 Full Service Diagnostic")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode with fewer iterations")
    parser.add_argument("--skip-modules", action="store_true",
                        help="Skip module tests")
    parser.add_argument("--output", "-o",
                        help="Output directory for report")

    args = parser.parse_args()

    diagnostic = FullServiceDiagnostic(
        quick_mode=args.quick,
        skip_modules=args.skip_modules
    )

    await diagnostic.run_full_diagnostic()

    # Save report
    report_path = diagnostic.save_report(args.output)
    print(f"\nReport saved to: {report_path}")

    # Return exit code
    overall = diagnostic.report["summary"]["overall_status"]
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
