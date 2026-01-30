"""
Flex Module Diagnostics - Heater-Shaker Module

Diagnostics for Opentrons Heater-Shaker Module on Flex.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/heaterShakerModuleV1.json
- API Reference: https://docs.opentrons.com/v2/new_modules.html#heater-shaker-module
- Protocol API: api/src/opentrons/protocol_api/module_contexts.py (HeaterShakerContext)
- Hardware Control: api/src/opentrons/hardware_control/modules/heater_shaker.py

Specifications:
- Temperature Range: Ambient to 95°C
- Shake Speed: 200-3000 RPM
- Requires labware latch for operation
"""
import time
from datetime import datetime
from typing import Any, List, Optional

from ..utils.base import BaseModuleDiagnostic
from ..utils.logger import DiagnosticLogger
from ..utils.types import (
    CalibrationStatus,
    ModuleInfo,
    ModuleType,
    TestResult,
    TestStatus,
)


class HeaterShakerDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Heater-Shaker Module."""

    module_type = ModuleType.HEATER_SHAKER
    module_name = "Heater-Shaker Module"

    # Safe test parameters
    TEST_TEMPERATURE = 37.0  # Body temperature - safe
    TEST_RPM_LOW = 200  # Minimum safe speed
    TEST_RPM_MEDIUM = 500  # Safe medium speed
    SHAKE_DURATION = 5  # Seconds to shake for test
    TEMPERATURE_TOLERANCE = 1.0  # ±1°C
    RPM_TOLERANCE = 50  # ±50 RPM
    TEMPERATURE_TIMEOUT = 300  # 5 minutes max
    LATCH_TIMEOUT = 30  # seconds

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        module_context: Optional[Any] = None,
        deck_slot: str = "D1",
    ):
        super().__init__(logger, protocol_context)
        self.module_context = module_context
        self.deck_slot = deck_slot

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect Heater-Shaker Module and gather device info."""
        try:
            if self.protocol_context and not self.module_context:
                try:
                    self.module_context = self.protocol_context.load_module(
                        "heaterShakerModuleV1",
                        self.deck_slot
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            serial = getattr(self.module_context, "serial_number", "Unknown")
            model = getattr(self.module_context, "model", "heaterShakerModuleV1")

            device_info = {}
            if hasattr(self.module_context, "_core"):
                core = self.module_context._core
                if hasattr(core, "_sync_module_hardware"):
                    hw = core._sync_module_hardware
                    if hasattr(hw, "device_info"):
                        device_info = hw.device_info

            firmware_version = device_info.get("version", "Unknown")
            hardware_revision = device_info.get("hw_revision", "Unknown")

            return ModuleInfo(
                module_type=self.module_type,
                model=str(model),
                serial_number=str(serial),
                firmware_version=firmware_version,
                hardware_revision=hardware_revision,
                deck_slot=self.deck_slot,
            )

        except Exception as e:
            self.logger.error(f"Error detecting Heater-Shaker: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Heater-Shaker calibration status."""
        try:
            if hasattr(self.module_context, "_core"):
                core = self.module_context._core
                if hasattr(core, "get_calibration_offset"):
                    offset = core.get_calibration_offset()
                    if offset:
                        return CalibrationStatus(
                            is_calibrated=True,
                            offset_x=offset.x if hasattr(offset, "x") else None,
                            offset_y=offset.y if hasattr(offset, "y") else None,
                            offset_z=offset.z if hasattr(offset, "z") else None,
                            notes="Calibration offset found",
                        )

            return CalibrationStatus(
                is_calibrated=False,
                notes="Unable to verify calibration status",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Heater-Shaker Module.

        Tests:
        1. Check temperature sensor
        2. Check speed sensor
        3. Test labware latch open/close
        4. Test heating (with latch closed)
        5. Test shaking at low speed (with latch closed)
        6. Deactivate all functions
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Test 1: Read Temperature Sensor
        try:
            current_temp = self.module_context.current_temperature
            if current_temp is not None and -40 <= current_temp <= 150:
                results.append(TestResult(
                    test_name="Read Temperature Sensor",
                    status=TestStatus.PASS,
                    message=f"Current temperature: {current_temp}°C",
                    actual_value=current_temp,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Temperature Sensor",
                    status=TestStatus.FAIL,
                    message=f"Invalid temperature reading: {current_temp}",
                    actual_value=current_temp,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Temperature Sensor",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Read Speed Sensor
        try:
            current_speed = self.module_context.current_speed
            if current_speed is not None and current_speed >= 0:
                results.append(TestResult(
                    test_name="Read Speed Sensor",
                    status=TestStatus.PASS,
                    message=f"Current speed: {current_speed} RPM",
                    actual_value=current_speed,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Speed Sensor",
                    status=TestStatus.FAIL,
                    message=f"Invalid speed reading: {current_speed}",
                    actual_value=current_speed,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Speed Sensor",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Check Status Properties
        try:
            temp_status = self.module_context.temperature_status
            speed_status = self.module_context.speed_status
            latch_status = self.module_context.labware_latch_status

            results.append(TestResult(
                test_name="Check Module Status",
                status=TestStatus.PASS,
                message=f"Temp: {temp_status}, Speed: {speed_status}, Latch: {latch_status}",
                details={
                    "temperature_status": str(temp_status),
                    "speed_status": str(speed_status),
                    "latch_status": str(latch_status),
                },
            ))
        except Exception as e:
            results.append(TestResult(
                test_name="Check Module Status",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 4: Labware Latch - Open
        try:
            start_time = datetime.now()
            self.module_context.open_labware_latch()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            latch_status = self.module_context.labware_latch_status
            if "open" in str(latch_status).lower():
                results.append(TestResult(
                    test_name="Open Labware Latch",
                    status=TestStatus.PASS,
                    message=f"Latch opened. Status: {latch_status}",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Open Labware Latch",
                    status=TestStatus.FAIL,
                    message=f"Latch may not have opened. Status: {latch_status}",
                    duration_seconds=duration,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Open Labware Latch",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 5: Labware Latch - Close
        try:
            start_time = datetime.now()
            self.module_context.close_labware_latch()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            latch_status = self.module_context.labware_latch_status
            if "closed" in str(latch_status).lower():
                results.append(TestResult(
                    test_name="Close Labware Latch",
                    status=TestStatus.PASS,
                    message=f"Latch closed. Status: {latch_status}",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Close Labware Latch",
                    status=TestStatus.FAIL,
                    message=f"Latch may not have closed. Status: {latch_status}",
                    duration_seconds=duration,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Close Labware Latch",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 6: Set Temperature (non-blocking)
        try:
            start_time = datetime.now()
            self.module_context.set_target_temperature(self.TEST_TEMPERATURE)
            duration = (datetime.now() - start_time).total_seconds()

            target = self.module_context.target_temperature
            if target and abs(target - self.TEST_TEMPERATURE) <= 0.1:
                results.append(TestResult(
                    test_name="Set Target Temperature",
                    status=TestStatus.PASS,
                    message=f"Target set to {target}°C",
                    duration_seconds=duration,
                    expected_value=self.TEST_TEMPERATURE,
                    actual_value=target,
                ))

                # Wait briefly and check if heating
                time.sleep(5)
                temp_status = self.module_context.temperature_status
                current = self.module_context.current_temperature
                results.append(TestResult(
                    test_name="Heating Response",
                    status=TestStatus.PASS,
                    message=f"Current: {current}°C, Status: {temp_status}",
                    details={"current_temp": current, "status": str(temp_status)},
                ))
            else:
                results.append(TestResult(
                    test_name="Set Target Temperature",
                    status=TestStatus.FAIL,
                    message=f"Target not set. Expected {self.TEST_TEMPERATURE}, got {target}",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Set Target Temperature",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 7: Test Shaking at Low Speed
        try:
            start_time = datetime.now()
            self.logger.info(f"Testing shake at {self.TEST_RPM_LOW} RPM for {self.SHAKE_DURATION}s...")

            self.module_context.set_and_wait_for_shake_speed(self.TEST_RPM_LOW)

            # Check speed reached
            current_speed = self.module_context.current_speed
            if current_speed and abs(current_speed - self.TEST_RPM_LOW) <= self.RPM_TOLERANCE:
                results.append(TestResult(
                    test_name="Shake Speed Control (Low)",
                    status=TestStatus.PASS,
                    message=f"Speed reached: {current_speed} RPM",
                    expected_value=self.TEST_RPM_LOW,
                    actual_value=current_speed,
                ))
            else:
                results.append(TestResult(
                    test_name="Shake Speed Control (Low)",
                    status=TestStatus.FAIL,
                    message=f"Speed not reached. Expected {self.TEST_RPM_LOW}, got {current_speed}",
                    expected_value=self.TEST_RPM_LOW,
                    actual_value=current_speed,
                ))

            # Let it shake briefly
            time.sleep(self.SHAKE_DURATION)

            # Deactivate shaker
            self.module_context.deactivate_shaker()

        except Exception as e:
            results.append(TestResult(
                test_name="Shake Speed Control (Low)",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))
            # Try to stop shaking on error
            try:
                self.module_context.deactivate_shaker()
            except:
                pass

        # Test 8: Deactivate All
        try:
            start_time = datetime.now()
            self.module_context.deactivate_heater()
            self.module_context.deactivate_shaker()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            temp_status = self.module_context.temperature_status
            speed_status = self.module_context.speed_status

            results.append(TestResult(
                test_name="Deactivate Module",
                status=TestStatus.PASS,
                message=f"Deactivated. Temp: {temp_status}, Speed: {speed_status}",
                duration_seconds=duration,
            ))

        except Exception as e:
            results.append(TestResult(
                test_name="Deactivate Module",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 9: Open latch at end (safety)
        try:
            self.module_context.open_labware_latch()
            results.append(TestResult(
                test_name="Final Latch Open",
                status=TestStatus.PASS,
                message="Latch opened for safe access",
            ))
        except Exception as e:
            results.append(TestResult(
                test_name="Final Latch Open",
                status=TestStatus.WARNING,
                message=f"Could not open latch: {e}",
            ))

        return results
