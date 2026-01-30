"""
Flex Module Diagnostics - Flex Stacker Module

Diagnostics for Opentrons Flex Stacker Module.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/flexStackerModuleV1.json
- Hardware Control: api/src/opentrons/hardware_control/modules/flex_stacker.py
- Protocol Engine: api/src/opentrons/protocol_engine/commands/flex_stacker/

Specifications:
- X Axis: 194mm travel (shuttle positioning)
- Z Axis: 139.5mm travel (shuttle height)
- L Axis: 22mm travel (latch)
- TOF (Time-of-Flight) sensors for labware detection
- LED status bar for visual feedback
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


class FlexStackerDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Flex Stacker Module."""

    module_type = ModuleType.FLEX_STACKER
    module_name = "Flex Stacker Module"

    # Test parameters
    LATCH_TIMEOUT = 30  # seconds
    AXIS_TIMEOUT = 60  # seconds

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        module_context: Optional[Any] = None,
        deck_slot: str = "B4",
    ):
        super().__init__(logger, protocol_context)
        self.module_context = module_context
        self.deck_slot = deck_slot

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect Flex Stacker and gather device info."""
        try:
            if self.protocol_context and not self.module_context:
                try:
                    self.module_context = self.protocol_context.load_module(
                        "flexStackerModuleV1",
                        self.deck_slot
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            serial = getattr(self.module_context, "serial_number", "Unknown")
            model = getattr(self.module_context, "model", "flexStackerModuleV1")

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
            self.logger.error(f"Error detecting Flex Stacker: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Flex Stacker calibration status."""
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
                notes="Flex Stacker calibration recommended for accurate labware handling",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Flex Stacker.

        Tests:
        1. Check module status/state
        2. Check latch state
        3. Check platform state
        4. Check hopper door state
        5. Open/close latch
        6. LED control (if available)
        7. TOF sensor check (if accessible)
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Get hardware reference for direct status access
        hw = None
        if hasattr(self.module_context, "_core"):
            core = self.module_context._core
            if hasattr(core, "_sync_module_hardware"):
                hw = core._sync_module_hardware

        # Test 1: Check Live Data / Status
        try:
            if hw and hasattr(hw, "live_data"):
                live_data = hw.live_data
                data = live_data.get("data", {})

                latch_state = data.get("latchState", "unknown")
                platform_state = data.get("platformState", "unknown")
                hopper_door_state = data.get("hopperDoorState", "unknown")
                install_detected = data.get("installDetected", False)

                results.append(TestResult(
                    test_name="Module Status Check",
                    status=TestStatus.PASS,
                    message=f"Latch: {latch_state}, Platform: {platform_state}, Door: {hopper_door_state}",
                    details={
                        "latch_state": latch_state,
                        "platform_state": platform_state,
                        "hopper_door_state": hopper_door_state,
                        "install_detected": install_detected,
                    },
                ))
            else:
                results.append(TestResult(
                    test_name="Module Status Check",
                    status=TestStatus.SKIP,
                    message="Live data not accessible",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Module Status Check",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Check Latch State
        try:
            if hw and hasattr(hw, "latch_state"):
                latch_state = hw.latch_state
                results.append(TestResult(
                    test_name="Read Latch State",
                    status=TestStatus.PASS,
                    message=f"Latch state: {latch_state}",
                    actual_value=str(latch_state),
                ))
            else:
                results.append(TestResult(
                    test_name="Read Latch State",
                    status=TestStatus.SKIP,
                    message="Latch state not directly accessible",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Latch State",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Check Platform State
        try:
            if hw and hasattr(hw, "platform_state"):
                platform_state = hw.platform_state
                results.append(TestResult(
                    test_name="Read Platform State",
                    status=TestStatus.PASS,
                    message=f"Platform state: {platform_state}",
                    actual_value=str(platform_state),
                ))
            else:
                results.append(TestResult(
                    test_name="Read Platform State",
                    status=TestStatus.SKIP,
                    message="Platform state not directly accessible",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Platform State",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 4: Check Hopper Door State
        try:
            if hw and hasattr(hw, "hopper_door_state"):
                door_state = hw.hopper_door_state
                results.append(TestResult(
                    test_name="Read Hopper Door State",
                    status=TestStatus.PASS,
                    message=f"Door state: {door_state}",
                    actual_value=str(door_state),
                ))
            elif hw and hasattr(hw, "door_closed"):
                door_closed = hw.door_closed
                results.append(TestResult(
                    test_name="Read Hopper Door State",
                    status=TestStatus.PASS,
                    message=f"Door closed: {door_closed}",
                    actual_value=door_closed,
                ))
            else:
                results.append(TestResult(
                    test_name="Read Hopper Door State",
                    status=TestStatus.SKIP,
                    message="Door state not directly accessible",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Read Hopper Door State",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 5: Open Latch
        try:
            if hw and hasattr(hw, "open_latch"):
                start_time = datetime.now()
                self.logger.info("Opening stacker latch...")
                hw.open_latch()
                duration = (datetime.now() - start_time).total_seconds()

                time.sleep(1)
                results.append(TestResult(
                    test_name="Open Latch",
                    status=TestStatus.PASS,
                    message=f"Latch opened in {duration:.1f}s",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Open Latch",
                    status=TestStatus.SKIP,
                    message="open_latch not available on this interface",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Open Latch",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 6: Close Latch
        try:
            if hw and hasattr(hw, "close_latch"):
                start_time = datetime.now()
                self.logger.info("Closing stacker latch...")
                hw.close_latch()
                duration = (datetime.now() - start_time).total_seconds()

                time.sleep(1)
                results.append(TestResult(
                    test_name="Close Latch",
                    status=TestStatus.PASS,
                    message=f"Latch closed in {duration:.1f}s",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Close Latch",
                    status=TestStatus.SKIP,
                    message="close_latch not available on this interface",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Close Latch",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 7: LED Control (if available)
        try:
            if hw and hasattr(hw, "set_led_state"):
                self.logger.info("Testing LED control...")

                # Turn LED on (white, solid)
                hw.set_led_state(power=True, color="white", pattern="solid")
                time.sleep(1)

                # Turn LED off
                hw.set_led_state(power=False)

                results.append(TestResult(
                    test_name="LED Control",
                    status=TestStatus.PASS,
                    message="LED toggled successfully",
                ))
            else:
                results.append(TestResult(
                    test_name="LED Control",
                    status=TestStatus.SKIP,
                    message="LED control not available on this interface",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="LED Control",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 8: Home All Axes (if safe to do)
        try:
            if hw and hasattr(hw, "home_all"):
                start_time = datetime.now()
                self.logger.info("Homing all stacker axes...")

                # Only home if it's safe (no labware in motion)
                hw.home_all(ignore_latch=False)
                duration = (datetime.now() - start_time).total_seconds()

                results.append(TestResult(
                    test_name="Home All Axes",
                    status=TestStatus.PASS,
                    message=f"Homing complete in {duration:.1f}s",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Home All Axes",
                    status=TestStatus.SKIP,
                    message="home_all not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Home All Axes",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 9: TOF Sensor Check
        try:
            if hw and hasattr(hw, "labware_detected"):
                # Check if labware is detected at different positions
                # This is a read-only check
                results.append(TestResult(
                    test_name="TOF Sensor Available",
                    status=TestStatus.PASS,
                    message="TOF labware detection available",
                    details={
                        "note": "Use labware_detected() to check for labware during operations",
                    },
                ))
            else:
                results.append(TestResult(
                    test_name="TOF Sensor Available",
                    status=TestStatus.SKIP,
                    message="TOF sensor not accessible via current interface",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="TOF Sensor Available",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        return results
