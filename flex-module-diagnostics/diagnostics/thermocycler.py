"""
Flex Module Diagnostics - Thermocycler Module

Diagnostics for Opentrons Thermocycler Module Gen2 on Flex.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/thermocyclerModuleV2.json
- API Reference: https://docs.opentrons.com/v2/new_modules.html#thermocycler-module
- Protocol API: api/src/opentrons/protocol_api/module_contexts.py (ThermocyclerContext)
- Hardware Control: api/src/opentrons/hardware_control/modules/thermocycler.py

IMPORTANT: Only Thermocycler Gen2 is compatible with Flex (Gen1 cannot be used with gripper).

Specifications:
- Block Temperature Range: 4°C to 99°C
- Lid Temperature Range: 37°C to 110°C
- Occupies slots A1+B1 on Flex deck
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


class ThermocyclerDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Thermocycler Module (Gen2)."""

    module_type = ModuleType.THERMOCYCLER
    module_name = "Thermocycler Module Gen2"

    # Safe test parameters
    TEST_BLOCK_TEMP = 37.0  # Body temperature - safe and fast
    TEST_LID_TEMP = 50.0  # Low lid temperature for testing
    TEMPERATURE_TOLERANCE = 1.0  # ±1°C
    BLOCK_TIMEOUT = 300  # 5 minutes max
    LID_TIMEOUT = 180  # 3 minutes max
    LID_OPERATION_TIMEOUT = 60  # 1 minute for lid operations

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        module_context: Optional[Any] = None,
    ):
        super().__init__(logger, protocol_context)
        self.module_context = module_context
        # Thermocycler always occupies A1+B1 on Flex
        self.deck_slot = "A1"

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect Thermocycler Module and gather device info."""
        try:
            if self.protocol_context and not self.module_context:
                try:
                    # Thermocycler loads without specifying slot on Flex
                    self.module_context = self.protocol_context.load_module(
                        "thermocycler module gen2"
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            serial = getattr(self.module_context, "serial_number", "Unknown")
            model = getattr(self.module_context, "model", "thermocyclerModuleV2")

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
            self.logger.error(f"Error detecting Thermocycler: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Thermocycler calibration status.

        Note: Thermocycler calibration is typically done at factory level.
        """
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
                notes="Thermocycler calibration is factory-set",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Thermocycler Module.

        Tests:
        1. Read block temperature sensor
        2. Read lid temperature sensor
        3. Check lid position
        4. Open lid operation
        5. Close lid operation
        6. Set block temperature
        7. Set lid temperature
        8. Simple profile execution (if time permits)
        9. Deactivate all
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Test 1: Read Block Temperature
        try:
            block_temp = self.module_context.block_temperature
            if block_temp is not None and -40 <= block_temp <= 150:
                results.append(TestResult(
                    test_name="Read Block Temperature",
                    status=TestStatus.PASS,
                    message=f"Block temperature: {block_temp}°C",
                    actual_value=block_temp,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Block Temperature",
                    status=TestStatus.FAIL,
                    message=f"Invalid block temperature: {block_temp}",
                    actual_value=block_temp,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Block Temperature",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Read Lid Temperature
        try:
            lid_temp = self.module_context.lid_temperature
            if lid_temp is not None and -40 <= lid_temp <= 150:
                results.append(TestResult(
                    test_name="Read Lid Temperature",
                    status=TestStatus.PASS,
                    message=f"Lid temperature: {lid_temp}°C",
                    actual_value=lid_temp,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Lid Temperature",
                    status=TestStatus.FAIL,
                    message=f"Invalid lid temperature: {lid_temp}",
                    actual_value=lid_temp,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Lid Temperature",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Check Lid Position
        try:
            lid_position = self.module_context.lid_position
            valid_positions = ["open", "closed", "unknown"]
            if str(lid_position).lower() in valid_positions:
                results.append(TestResult(
                    test_name="Check Lid Position",
                    status=TestStatus.PASS,
                    message=f"Lid position: {lid_position}",
                    actual_value=str(lid_position),
                ))
            else:
                results.append(TestResult(
                    test_name="Check Lid Position",
                    status=TestStatus.WARNING,
                    message=f"Unknown lid position: {lid_position}",
                    actual_value=str(lid_position),
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Check Lid Position",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 4: Check Status Properties
        try:
            block_status = self.module_context.block_temperature_status
            lid_status = self.module_context.lid_temperature_status

            results.append(TestResult(
                test_name="Check Temperature Status",
                status=TestStatus.PASS,
                message=f"Block: {block_status}, Lid: {lid_status}",
                details={
                    "block_status": str(block_status),
                    "lid_status": str(lid_status),
                },
            ))
        except Exception as e:
            results.append(TestResult(
                test_name="Check Temperature Status",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 5: Open Lid
        try:
            start_time = datetime.now()
            self.logger.info("Opening thermocycler lid...")
            self.module_context.open_lid()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            lid_position = self.module_context.lid_position
            if "open" in str(lid_position).lower():
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.PASS,
                    message=f"Lid opened. Position: {lid_position}",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.FAIL,
                    message=f"Lid may not have opened. Position: {lid_position}",
                    duration_seconds=duration,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Open Lid",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 6: Close Lid
        try:
            start_time = datetime.now()
            self.logger.info("Closing thermocycler lid...")
            self.module_context.close_lid()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            lid_position = self.module_context.lid_position
            if "closed" in str(lid_position).lower():
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.PASS,
                    message=f"Lid closed. Position: {lid_position}",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.FAIL,
                    message=f"Lid may not have closed. Position: {lid_position}",
                    duration_seconds=duration,
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Close Lid",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 7: Set Block Temperature
        try:
            start_time = datetime.now()
            self.logger.info(f"Setting block temperature to {self.TEST_BLOCK_TEMP}°C...")

            self.module_context.set_block_temperature(
                temperature=self.TEST_BLOCK_TEMP,
                hold_time_seconds=5,
            )

            duration = (datetime.now() - start_time).total_seconds()
            block_temp = self.module_context.block_temperature

            if block_temp and abs(block_temp - self.TEST_BLOCK_TEMP) <= self.TEMPERATURE_TOLERANCE:
                results.append(TestResult(
                    test_name="Set Block Temperature",
                    status=TestStatus.PASS,
                    message=f"Block reached {block_temp}°C in {duration:.1f}s",
                    duration_seconds=duration,
                    expected_value=self.TEST_BLOCK_TEMP,
                    actual_value=block_temp,
                ))
            else:
                results.append(TestResult(
                    test_name="Set Block Temperature",
                    status=TestStatus.FAIL,
                    message=f"Block temp {block_temp}°C not within tolerance of {self.TEST_BLOCK_TEMP}°C",
                    duration_seconds=duration,
                    expected_value=self.TEST_BLOCK_TEMP,
                    actual_value=block_temp,
                ))

        except Exception as e:
            results.append(TestResult(
                test_name="Set Block Temperature",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 8: Set Lid Temperature (non-blocking for faster test)
        try:
            start_time = datetime.now()
            self.logger.info(f"Setting lid temperature to {self.TEST_LID_TEMP}°C...")

            # Use set_lid_temperature (which waits) or the non-blocking version
            if hasattr(self.module_context, "set_lid_temperature"):
                # This blocks until temperature is reached
                self.module_context.set_lid_temperature(self.TEST_LID_TEMP)
                duration = (datetime.now() - start_time).total_seconds()
                lid_temp = self.module_context.lid_temperature

                if lid_temp and abs(lid_temp - self.TEST_LID_TEMP) <= self.TEMPERATURE_TOLERANCE:
                    results.append(TestResult(
                        test_name="Set Lid Temperature",
                        status=TestStatus.PASS,
                        message=f"Lid reached {lid_temp}°C in {duration:.1f}s",
                        duration_seconds=duration,
                        expected_value=self.TEST_LID_TEMP,
                        actual_value=lid_temp,
                    ))
                else:
                    results.append(TestResult(
                        test_name="Set Lid Temperature",
                        status=TestStatus.FAIL,
                        message=f"Lid temp {lid_temp}°C not within tolerance",
                        expected_value=self.TEST_LID_TEMP,
                        actual_value=lid_temp,
                    ))
            else:
                results.append(TestResult(
                    test_name="Set Lid Temperature",
                    status=TestStatus.SKIP,
                    message="set_lid_temperature not available",
                ))

        except Exception as e:
            results.append(TestResult(
                test_name="Set Lid Temperature",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 9: Simple Profile (optional - short profile)
        try:
            self.logger.info("Running simple temperature profile...")
            start_time = datetime.now()

            # Very short profile for testing
            simple_profile = [
                {"temperature": 37, "hold_time_seconds": 3},
                {"temperature": 40, "hold_time_seconds": 3},
                {"temperature": 37, "hold_time_seconds": 3},
            ]

            self.module_context.execute_profile(
                steps=simple_profile,
                repetitions=1,
            )

            duration = (datetime.now() - start_time).total_seconds()
            results.append(TestResult(
                test_name="Execute Temperature Profile",
                status=TestStatus.PASS,
                message=f"Profile completed in {duration:.1f}s",
                duration_seconds=duration,
                details={"steps": len(simple_profile), "repetitions": 1},
            ))

        except Exception as e:
            results.append(TestResult(
                test_name="Execute Temperature Profile",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 10: Deactivate All
        try:
            start_time = datetime.now()
            self.logger.info("Deactivating thermocycler...")
            self.module_context.deactivate()
            duration = (datetime.now() - start_time).total_seconds()

            results.append(TestResult(
                test_name="Deactivate Module",
                status=TestStatus.PASS,
                message="Module deactivated",
                duration_seconds=duration,
            ))

        except Exception as e:
            results.append(TestResult(
                test_name="Deactivate Module",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 11: Open lid at end (for access)
        try:
            self.module_context.open_lid()
            results.append(TestResult(
                test_name="Final Lid Open",
                status=TestStatus.PASS,
                message="Lid opened for safe access",
            ))
        except Exception as e:
            results.append(TestResult(
                test_name="Final Lid Open",
                status=TestStatus.WARNING,
                message=f"Could not open lid: {e}",
            ))

        return results
