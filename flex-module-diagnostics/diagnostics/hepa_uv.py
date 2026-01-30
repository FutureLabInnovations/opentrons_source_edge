"""
Flex Module Diagnostics - HEPA/UV Module

Diagnostics for Opentrons HEPA/UV Module on Flex.

Evidence/Documentation:
- Hardware Control: hardware/opentrons_hardware/hardware_control/hepa_uv_settings.py
- CAN Bus Communication: Uses NodeId.hepa_uv for messaging

Specifications:
- HEPA fan with variable duty cycle (0-100%)
- UV light with configurable duration
- Safety interlocks for UV activation
- CAN bus communication (not USB like other modules)

Note: HEPA/UV module communicates via CAN bus, not standard USB module interface.
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


class HepaUVDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for HEPA/UV Module.

    Note: This module communicates via CAN bus and requires special
    hardware control access, which may not be available through the
    standard protocol context.
    """

    module_type = ModuleType.HEPA_UV
    module_name = "HEPA/UV Module"

    # Safe test parameters
    TEST_FAN_DUTY_CYCLE = 50  # 50% power for testing
    TEST_UV_DURATION = 5  # 5 seconds for test
    FAN_SPINUP_TIME = 3  # seconds to wait for fan to spin up

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        hardware_control: Optional[Any] = None,
    ):
        super().__init__(logger, protocol_context)
        self.hardware_control = hardware_control
        self.deck_slot = "N/A (enclosure module)"

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect HEPA/UV Module.

        Note: HEPA/UV uses CAN bus, not USB. Detection may require
        direct hardware control access.
        """
        try:
            # HEPA/UV module detection is different from USB modules
            # It's detected via CAN bus at system level

            if self.hardware_control:
                # Try to access HEPA/UV state through hardware control
                if hasattr(self.hardware_control, "get_hepa_fan_state"):
                    try:
                        fan_state = self.hardware_control.get_hepa_fan_state()
                        if fan_state is not None:
                            return ModuleInfo(
                                module_type=self.module_type,
                                model="hepaUVModuleV1",
                                serial_number="CAN-connected",
                                firmware_version="See system firmware",
                                hardware_revision="Unknown",
                            )
                    except Exception:
                        pass

            # If we can't detect via hardware control, check if robot
            # has HEPA/UV capability
            if self.protocol_context:
                # Check if the robot is a Flex with enclosure
                robot_type = getattr(self.protocol_context, "robot_type", None)
                if robot_type and "flex" in str(robot_type).lower():
                    # Flex may have HEPA/UV - report as possibly present
                    return ModuleInfo(
                        module_type=self.module_type,
                        model="hepaUVModuleV1",
                        serial_number="Unknown (CAN module)",
                        firmware_version="Unknown",
                        hardware_revision="Unknown",
                        is_simulated=True,  # Mark as simulated since we can't confirm
                    )

            self.logger.info(
                "HEPA/UV module not detected. This module requires CAN bus access."
            )
            return None

        except Exception as e:
            self.logger.error(f"Error detecting HEPA/UV Module: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check HEPA/UV calibration status.

        Note: HEPA/UV module does not have position calibration like
        other modules. Its function is environmental (air filtration/UV).
        """
        return CalibrationStatus(
            is_calibrated=True,  # N/A but report as OK
            notes="HEPA/UV module does not require position calibration. "
                  "Verify filter condition and UV bulb during maintenance.",
        )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for HEPA/UV Module.

        Tests:
        1. Read fan state
        2. Read UV state
        3. Activate fan at test duty cycle
        4. Deactivate fan
        5. Check UV safety interlocks (read-only)
        6. Brief UV activation test (only if safe)

        IMPORTANT: UV tests should only be run with proper safety precautions.
        The enclosure must be closed and safety interlocks engaged.
        """
        results = []

        # Check if we have hardware control access
        if not self.hardware_control:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="HEPA/UV requires direct hardware control access (CAN bus). "
                        "Tests skipped - module may still be functional.",
            ))
            return results

        # Test 1: Read Fan State
        try:
            if hasattr(self.hardware_control, "get_hepa_fan_state"):
                fan_state = self.hardware_control.get_hepa_fan_state()
                if fan_state:
                    fan_on = fan_state.get("fan_on", False)
                    duty_cycle = fan_state.get("duty_cycle", 0)
                    fan_rpm = fan_state.get("fan_rpm", 0)

                    results.append(TestResult(
                        test_name="Read Fan State",
                        status=TestStatus.PASS,
                        message=f"Fan: {'ON' if fan_on else 'OFF'}, "
                                f"Duty: {duty_cycle}%, RPM: {fan_rpm}",
                        details={
                            "fan_on": fan_on,
                            "duty_cycle": duty_cycle,
                            "fan_rpm": fan_rpm,
                        },
                    ))
                else:
                    results.append(TestResult(
                        test_name="Read Fan State",
                        status=TestStatus.FAIL,
                        message="Could not read fan state",
                    ))
            else:
                results.append(TestResult(
                    test_name="Read Fan State",
                    status=TestStatus.SKIP,
                    message="get_hepa_fan_state not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Fan State",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Read UV State
        try:
            if hasattr(self.hardware_control, "get_hepa_uv_state"):
                uv_state = self.hardware_control.get_hepa_uv_state()
                if uv_state:
                    uv_on = uv_state.get("uv_light_on", False)
                    uv_duration = uv_state.get("uv_duration_s", 0)
                    remaining = uv_state.get("remaining_time_s", 0)
                    safety_relay = uv_state.get("safety_relay_active", False)

                    results.append(TestResult(
                        test_name="Read UV State",
                        status=TestStatus.PASS,
                        message=f"UV: {'ON' if uv_on else 'OFF'}, "
                                f"Duration: {uv_duration}s, Safety: {'Active' if safety_relay else 'Inactive'}",
                        details={
                            "uv_on": uv_on,
                            "uv_duration_s": uv_duration,
                            "remaining_time_s": remaining,
                            "safety_relay_active": safety_relay,
                        },
                    ))
                else:
                    results.append(TestResult(
                        test_name="Read UV State",
                        status=TestStatus.FAIL,
                        message="Could not read UV state",
                    ))
            else:
                results.append(TestResult(
                    test_name="Read UV State",
                    status=TestStatus.SKIP,
                    message="get_hepa_uv_state not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read UV State",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Activate Fan
        try:
            if hasattr(self.hardware_control, "set_hepa_fan_state"):
                start_time = datetime.now()
                self.logger.info(f"Activating fan at {self.TEST_FAN_DUTY_CYCLE}% duty cycle...")

                self.hardware_control.set_hepa_fan_state(
                    fan_on=True,
                    duty_cycle=self.TEST_FAN_DUTY_CYCLE
                )

                # Wait for fan to spin up
                time.sleep(self.FAN_SPINUP_TIME)
                duration = (datetime.now() - start_time).total_seconds()

                # Read current state
                fan_state = self.hardware_control.get_hepa_fan_state()
                if fan_state and fan_state.get("fan_on"):
                    current_rpm = fan_state.get("fan_rpm", 0)
                    results.append(TestResult(
                        test_name="Activate Fan",
                        status=TestStatus.PASS,
                        message=f"Fan running at {current_rpm} RPM",
                        duration_seconds=duration,
                        details={"rpm": current_rpm, "duty_cycle": self.TEST_FAN_DUTY_CYCLE},
                    ))
                else:
                    results.append(TestResult(
                        test_name="Activate Fan",
                        status=TestStatus.FAIL,
                        message="Fan did not activate",
                        duration_seconds=duration,
                    ))
            else:
                results.append(TestResult(
                    test_name="Activate Fan",
                    status=TestStatus.SKIP,
                    message="set_hepa_fan_state not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Activate Fan",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 4: Deactivate Fan
        try:
            if hasattr(self.hardware_control, "set_hepa_fan_state"):
                start_time = datetime.now()
                self.logger.info("Deactivating fan...")

                self.hardware_control.set_hepa_fan_state(fan_on=False, duty_cycle=0)
                time.sleep(2)  # Wait for fan to spin down
                duration = (datetime.now() - start_time).total_seconds()

                fan_state = self.hardware_control.get_hepa_fan_state()
                if fan_state and not fan_state.get("fan_on"):
                    results.append(TestResult(
                        test_name="Deactivate Fan",
                        status=TestStatus.PASS,
                        message="Fan deactivated",
                        duration_seconds=duration,
                    ))
                else:
                    results.append(TestResult(
                        test_name="Deactivate Fan",
                        status=TestStatus.WARNING,
                        message="Fan may still be running",
                        duration_seconds=duration,
                    ))
            else:
                results.append(TestResult(
                    test_name="Deactivate Fan",
                    status=TestStatus.SKIP,
                    message="set_hepa_fan_state not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Deactivate Fan",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 5: UV Safety Check
        try:
            if hasattr(self.hardware_control, "get_hepa_uv_state"):
                uv_state = self.hardware_control.get_hepa_uv_state()
                if uv_state:
                    safety_relay = uv_state.get("safety_relay_active", False)

                    if safety_relay:
                        results.append(TestResult(
                            test_name="UV Safety Interlock",
                            status=TestStatus.PASS,
                            message="Safety relay is active - UV can be enabled",
                        ))
                    else:
                        results.append(TestResult(
                            test_name="UV Safety Interlock",
                            status=TestStatus.WARNING,
                            message="Safety relay inactive - enclosure may be open. "
                                    "UV cannot be activated until safety conditions are met.",
                        ))
                else:
                    results.append(TestResult(
                        test_name="UV Safety Interlock",
                        status=TestStatus.SKIP,
                        message="Could not check UV safety state",
                    ))
            else:
                results.append(TestResult(
                    test_name="UV Safety Interlock",
                    status=TestStatus.SKIP,
                    message="UV state check not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="UV Safety Interlock",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 6: UV Activation Test (only if safety allows)
        # NOTE: This test should only run if safety conditions are met
        try:
            if hasattr(self.hardware_control, "set_hepa_uv_state"):
                # First check if it's safe to activate UV
                uv_state = self.hardware_control.get_hepa_uv_state()
                if uv_state and uv_state.get("safety_relay_active"):
                    self.logger.info(f"Testing UV light for {self.TEST_UV_DURATION}s...")
                    self.logger.warning("UV LIGHT WILL ACTIVATE - ENSURE ENCLOSURE IS CLOSED")

                    start_time = datetime.now()
                    self.hardware_control.set_hepa_uv_state(
                        uv_light_on=True,
                        uv_duration_s=self.TEST_UV_DURATION
                    )

                    # Wait for test duration plus margin
                    time.sleep(self.TEST_UV_DURATION + 2)
                    duration = (datetime.now() - start_time).total_seconds()

                    # Verify UV turned off
                    uv_state = self.hardware_control.get_hepa_uv_state()
                    uv_on = uv_state.get("uv_light_on", True) if uv_state else True

                    if not uv_on:
                        results.append(TestResult(
                            test_name="UV Light Test",
                            status=TestStatus.PASS,
                            message=f"UV test completed and auto-shutoff confirmed",
                            duration_seconds=duration,
                        ))
                    else:
                        # Force UV off if still on
                        self.hardware_control.set_hepa_uv_state(
                            uv_light_on=False,
                            uv_duration_s=0
                        )
                        results.append(TestResult(
                            test_name="UV Light Test",
                            status=TestStatus.WARNING,
                            message="UV test completed but manual shutoff needed",
                            duration_seconds=duration,
                        ))
                else:
                    results.append(TestResult(
                        test_name="UV Light Test",
                        status=TestStatus.SKIP,
                        message="UV test skipped - safety interlocks not engaged. "
                                "Close enclosure and retry if UV testing is needed.",
                    ))
            else:
                results.append(TestResult(
                    test_name="UV Light Test",
                    status=TestStatus.SKIP,
                    message="UV control not available",
                ))
        except Exception as e:
            # Ensure UV is off on error
            try:
                if hasattr(self.hardware_control, "set_hepa_uv_state"):
                    self.hardware_control.set_hepa_uv_state(
                        uv_light_on=False,
                        uv_duration_s=0
                    )
            except:
                pass

            results.append(TestResult(
                test_name="UV Light Test",
                status=TestStatus.ERROR,
                message=f"Error (UV has been turned off): {e}",
            ))

        return results
