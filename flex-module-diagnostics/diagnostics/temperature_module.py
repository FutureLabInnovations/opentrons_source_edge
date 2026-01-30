"""
Flex Module Diagnostics - Temperature Module

Diagnostics for Opentrons Temperature Module (Gen2) on Flex.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/temperatureModuleV2.json
- API Reference: https://docs.opentrons.com/v2/new_modules.html#temperature-module
- Protocol API: api/src/opentrons/protocol_api/module_contexts.py (TemperatureModuleContext)
- Hardware Control: api/src/opentrons/hardware_control/modules/tempdeck.py

Specifications:
- Temperature Range: 4°C to 95°C
- Accuracy: ±1°C
- Compatible with Flex only (temperatureModuleV2)
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


class TemperatureModuleDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Temperature Module."""

    module_type = ModuleType.TEMPERATURE_MODULE
    module_name = "Temperature Module"

    # Safe test parameters
    TEST_TEMPERATURE = 37.0  # Body temperature - safe and fast to reach
    TEMPERATURE_TOLERANCE = 1.0  # ±1°C
    TEMPERATURE_TIMEOUT = 300  # 5 minutes max

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
        """Detect Temperature Module and gather device info."""
        try:
            # If we have a protocol context, try to load the module
            if self.protocol_context and not self.module_context:
                try:
                    self.module_context = self.protocol_context.load_module(
                        "temperature module gen2",
                        self.deck_slot
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            # Get module information
            serial = getattr(self.module_context, "serial_number", "Unknown")
            model = getattr(self.module_context, "model", "temperatureModuleV2")

            # Try to get device_info if available (hardware layer)
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
            self.logger.error(f"Error detecting Temperature Module: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Temperature Module calibration status.

        Note: Temperature Module calibration stores offset data that helps
        align labware on the module with pipette movements.
        """
        try:
            # Try to access calibration data
            # On Flex, calibration data is stored per module serial number
            if hasattr(self.module_context, "_core"):
                core = self.module_context._core
                # Check if calibration offset exists
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

            # If we can't access calibration data directly, report as unknown
            return CalibrationStatus(
                is_calibrated=False,
                notes="Unable to verify calibration status. Run calibration if needed.",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Temperature Module.

        Tests:
        1. Read current temperature - verify sensor works
        2. Set temperature and wait - verify heating/cooling works
        3. Check temperature status transitions
        4. Deactivate and verify
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Test 1: Read Current Temperature
        try:
            start_time = datetime.now()
            current_temp = self.module_context.temperature
            duration = (datetime.now() - start_time).total_seconds()

            if current_temp is not None and -40 <= current_temp <= 150:
                results.append(TestResult(
                    test_name="Read Temperature Sensor",
                    status=TestStatus.PASS,
                    message=f"Current temperature: {current_temp}°C",
                    duration_seconds=duration,
                    actual_value=current_temp,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Temperature Sensor",
                    status=TestStatus.FAIL,
                    message=f"Invalid temperature reading: {current_temp}",
                    duration_seconds=duration,
                    actual_value=current_temp,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Temperature Sensor",
                status=TestStatus.ERROR,
                message=f"Error reading temperature: {e}",
            ))

        # Test 2: Check Status Property
        try:
            status = self.module_context.status
            valid_statuses = ["idle", "heating", "cooling", "holding at target", "error"]
            if str(status).lower() in valid_statuses or status in valid_statuses:
                results.append(TestResult(
                    test_name="Check Module Status",
                    status=TestStatus.PASS,
                    message=f"Status: {status}",
                    actual_value=str(status),
                ))
            else:
                results.append(TestResult(
                    test_name="Check Module Status",
                    status=TestStatus.WARNING,
                    message=f"Unknown status: {status}",
                    actual_value=str(status),
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Check Module Status",
                status=TestStatus.ERROR,
                message=f"Error checking status: {e}",
            ))

        # Test 3: Set Temperature and Wait
        try:
            start_time = datetime.now()
            self.logger.info(f"Setting temperature to {self.TEST_TEMPERATURE}°C...")

            # Use start_set_temperature (non-blocking) for more control
            if hasattr(self.module_context, "start_set_temperature"):
                self.module_context.start_set_temperature(self.TEST_TEMPERATURE)
            else:
                self.module_context.set_temperature(self.TEST_TEMPERATURE)

            # Verify target was set
            target = self.module_context.target
            if target is None or abs(target - self.TEST_TEMPERATURE) > 0.1:
                results.append(TestResult(
                    test_name="Set Target Temperature",
                    status=TestStatus.FAIL,
                    message=f"Target not set correctly. Expected {self.TEST_TEMPERATURE}, got {target}",
                    expected_value=self.TEST_TEMPERATURE,
                    actual_value=target,
                ))
            else:
                results.append(TestResult(
                    test_name="Set Target Temperature",
                    status=TestStatus.PASS,
                    message=f"Target set to {target}°C",
                    actual_value=target,
                ))

                # Wait for temperature with timeout
                self.logger.info("Waiting for temperature to stabilize...")
                start_wait = datetime.now()
                reached_target = False

                while (datetime.now() - start_wait).total_seconds() < self.TEMPERATURE_TIMEOUT:
                    current = self.module_context.temperature
                    if current and abs(current - self.TEST_TEMPERATURE) <= self.TEMPERATURE_TOLERANCE:
                        reached_target = True
                        break
                    time.sleep(2)

                duration = (datetime.now() - start_time).total_seconds()
                final_temp = self.module_context.temperature

                if reached_target:
                    results.append(TestResult(
                        test_name="Temperature Control",
                        status=TestStatus.PASS,
                        message=f"Reached {final_temp}°C in {duration:.1f}s",
                        duration_seconds=duration,
                        expected_value=self.TEST_TEMPERATURE,
                        actual_value=final_temp,
                        details={"time_to_target": duration},
                    ))
                else:
                    results.append(TestResult(
                        test_name="Temperature Control",
                        status=TestStatus.FAIL,
                        message=f"Timeout: temp is {final_temp}°C after {duration:.1f}s",
                        duration_seconds=duration,
                        expected_value=self.TEST_TEMPERATURE,
                        actual_value=final_temp,
                    ))

        except Exception as e:
            results.append(TestResult(
                test_name="Temperature Control",
                status=TestStatus.ERROR,
                message=f"Error during temperature control test: {e}",
            ))

        # Test 4: Deactivate Module
        try:
            start_time = datetime.now()
            self.module_context.deactivate()
            duration = (datetime.now() - start_time).total_seconds()

            # Verify deactivation
            time.sleep(1)
            status = self.module_context.status
            target = self.module_context.target

            if target is None or str(status).lower() == "idle":
                results.append(TestResult(
                    test_name="Deactivate Module",
                    status=TestStatus.PASS,
                    message=f"Module deactivated successfully. Status: {status}",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Deactivate Module",
                    status=TestStatus.WARNING,
                    message=f"Deactivation may not be complete. Status: {status}, Target: {target}",
                    duration_seconds=duration,
                ))

        except Exception as e:
            results.append(TestResult(
                test_name="Deactivate Module",
                status=TestStatus.ERROR,
                message=f"Error deactivating module: {e}",
            ))

        return results


def run_standalone_diagnostic(deck_slot: str = "D1") -> None:
    """Run Temperature Module diagnostic as standalone script.

    This can be used for quick testing without the full diagnostics suite.
    """
    from ..utils.logger import DiagnosticLogger
    from pathlib import Path

    logger = DiagnosticLogger(
        name="TempModuleDiag",
        log_file=Path("temp_module_diagnostic.log"),
    )

    logger.info("Temperature Module Standalone Diagnostic")
    logger.info("=" * 50)
    logger.info("")
    logger.info("Note: This script requires a protocol context to run.")
    logger.info("Use the diagnostic protocol (protocols/diagnostic_protocol.py)")
    logger.info("to run this diagnostic on your Flex.")
    logger.info("")
    logger.info("To run via protocol:")
    logger.info("  1. Upload protocols/diagnostic_protocol.py to Opentrons App")
    logger.info("  2. Configure deck layout with Temperature Module")
    logger.info("  3. Run the protocol")
