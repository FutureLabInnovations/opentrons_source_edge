"""
Flex Module Diagnostics - Absorbance Plate Reader

Diagnostics for Opentrons Absorbance Plate Reader on Flex.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/absorbanceReaderV1.json
- API Reference: https://docs.opentrons.com/v2/absorbance_plate_reader.html
- Protocol API: api/src/opentrons/protocol_api/module_contexts.py (AbsorbanceReaderContext)
- Hardware Control: api/src/opentrons/hardware_control/modules/absorbance_reader.py

Specifications:
- Single and Multi wavelength modes
- Wavelength range: Typically 350-1000nm (model dependent)
- Requires gripper for lid operations
- Plate presence detection
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


class AbsorbanceReaderDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Absorbance Plate Reader."""

    module_type = ModuleType.ABSORBANCE_READER
    module_name = "Absorbance Plate Reader"

    # Common test wavelengths (safe values that most readers support)
    TEST_WAVELENGTHS = [450, 562]  # Common for ELISA assays
    READ_TIMEOUT = 60  # seconds

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        module_context: Optional[Any] = None,
        deck_slot: str = "D3",
    ):
        super().__init__(logger, protocol_context)
        self.module_context = module_context
        self.deck_slot = deck_slot

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect Absorbance Reader and gather device info."""
        try:
            if self.protocol_context and not self.module_context:
                try:
                    self.module_context = self.protocol_context.load_module(
                        "absorbance reader",
                        self.deck_slot
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            serial = getattr(self.module_context, "serial_number", "Unknown")
            model = getattr(self.module_context, "model", "absorbanceReaderV1")

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
            self.logger.error(f"Error detecting Absorbance Reader: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Absorbance Reader calibration status.

        Note: Absorbance Reader has factory calibration for optics.
        Module position calibration is separate.
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
                            notes="Module calibration offset found. Optical calibration is factory-set.",
                        )

            return CalibrationStatus(
                is_calibrated=False,
                notes="Module position calibration recommended. Optical calibration is factory-set.",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Absorbance Plate Reader.

        Tests:
        1. Check device status
        2. Check lid status
        3. Check plate presence
        4. Get supported wavelengths
        5. Open lid (requires gripper)
        6. Close lid (requires gripper)
        7. Initialize for single wavelength read
        8. Perform test read (if plate present)
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Test 1: Check if lid is on
        try:
            lid_on = self.module_context.is_lid_on()
            results.append(TestResult(
                test_name="Check Lid Presence",
                status=TestStatus.PASS,
                message=f"Lid is {'on' if lid_on else 'off'}",
                actual_value=lid_on,
            ))
        except Exception as e:
            results.append(TestResult(
                test_name="Check Lid Presence",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Check device info/status from hardware if available
        try:
            if hasattr(self.module_context, "_core"):
                core = self.module_context._core
                if hasattr(core, "_sync_module_hardware"):
                    hw = core._sync_module_hardware
                    if hasattr(hw, "live_data"):
                        live_data = hw.live_data
                        device_status = live_data.get("data", {}).get("deviceStatus", "unknown")
                        plate_presence = live_data.get("data", {}).get("platePresence", "unknown")
                        lid_status = live_data.get("data", {}).get("lidStatus", "unknown")

                        results.append(TestResult(
                            test_name="Device Status Check",
                            status=TestStatus.PASS,
                            message=f"Device: {device_status}, Plate: {plate_presence}, Lid: {lid_status}",
                            details={
                                "device_status": device_status,
                                "plate_presence": plate_presence,
                                "lid_status": lid_status,
                            },
                        ))
                    else:
                        results.append(TestResult(
                            test_name="Device Status Check",
                            status=TestStatus.SKIP,
                            message="Live data not accessible",
                        ))
        except Exception as e:
            results.append(TestResult(
                test_name="Device Status Check",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Get Supported Wavelengths
        supported_wavelengths = []
        try:
            if hasattr(self.module_context, "_core"):
                core = self.module_context._core
                if hasattr(core, "_sync_module_hardware"):
                    hw = core._sync_module_hardware
                    if hasattr(hw, "supported_wavelengths"):
                        supported_wavelengths = hw.supported_wavelengths

            if supported_wavelengths:
                results.append(TestResult(
                    test_name="Get Supported Wavelengths",
                    status=TestStatus.PASS,
                    message=f"Supported wavelengths: {supported_wavelengths}",
                    actual_value=supported_wavelengths,
                ))
            else:
                results.append(TestResult(
                    test_name="Get Supported Wavelengths",
                    status=TestStatus.WARNING,
                    message="Could not retrieve supported wavelengths",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Get Supported Wavelengths",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 4: Open Lid (requires gripper in Flex)
        try:
            start_time = datetime.now()
            self.logger.info("Opening absorbance reader lid...")
            self.module_context.open_lid()
            duration = (datetime.now() - start_time).total_seconds()

            # Verify lid opened
            time.sleep(1)
            lid_on = self.module_context.is_lid_on()

            if not lid_on:
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.PASS,
                    message=f"Lid opened in {duration:.1f}s",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.FAIL,
                    message="Lid still appears to be on",
                    duration_seconds=duration,
                ))
        except Exception as e:
            error_msg = str(e)
            if "gripper" in error_msg.lower():
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.SKIP,
                    message="Lid operation requires gripper which may not be attached",
                ))
            else:
                results.append(TestResult(
                    test_name="Open Lid",
                    status=TestStatus.ERROR,
                    message=f"Error: {e}",
                ))

        # Test 5: Close Lid (requires gripper)
        try:
            start_time = datetime.now()
            self.logger.info("Closing absorbance reader lid...")
            self.module_context.close_lid()
            duration = (datetime.now() - start_time).total_seconds()

            time.sleep(1)
            lid_on = self.module_context.is_lid_on()

            if lid_on:
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.PASS,
                    message=f"Lid closed in {duration:.1f}s",
                    duration_seconds=duration,
                ))
            else:
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.FAIL,
                    message="Lid does not appear to be on",
                    duration_seconds=duration,
                ))
        except Exception as e:
            error_msg = str(e)
            if "gripper" in error_msg.lower():
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.SKIP,
                    message="Lid operation requires gripper which may not be attached",
                ))
            else:
                results.append(TestResult(
                    test_name="Close Lid",
                    status=TestStatus.ERROR,
                    message=f"Error: {e}",
                ))

        # Test 6: Initialize for Single Wavelength Measurement
        test_wavelength = self.TEST_WAVELENGTHS[0]
        if supported_wavelengths and test_wavelength not in supported_wavelengths:
            # Use first available wavelength
            test_wavelength = supported_wavelengths[0]

        try:
            start_time = datetime.now()
            self.logger.info(f"Initializing for measurement at {test_wavelength}nm...")

            self.module_context.initialize(
                mode="single",
                wavelengths=[test_wavelength],
            )

            duration = (datetime.now() - start_time).total_seconds()
            results.append(TestResult(
                test_name="Initialize Single Mode",
                status=TestStatus.PASS,
                message=f"Initialized for {test_wavelength}nm in {duration:.1f}s",
                duration_seconds=duration,
                details={"wavelength": test_wavelength, "mode": "single"},
            ))

        except Exception as e:
            results.append(TestResult(
                test_name="Initialize Single Mode",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 7: Initialize for Multi Wavelength (if supported)
        if len(supported_wavelengths) >= 2:
            test_wavelengths_multi = supported_wavelengths[:2]
            try:
                start_time = datetime.now()
                self.logger.info(f"Initializing for multi-wavelength measurement...")

                self.module_context.initialize(
                    mode="multi",
                    wavelengths=test_wavelengths_multi,
                )

                duration = (datetime.now() - start_time).total_seconds()
                results.append(TestResult(
                    test_name="Initialize Multi Mode",
                    status=TestStatus.PASS,
                    message=f"Initialized for {test_wavelengths_multi}nm in {duration:.1f}s",
                    duration_seconds=duration,
                    details={"wavelengths": test_wavelengths_multi, "mode": "multi"},
                ))

            except Exception as e:
                results.append(TestResult(
                    test_name="Initialize Multi Mode",
                    status=TestStatus.ERROR,
                    message=f"Error: {e}",
                ))
        else:
            results.append(TestResult(
                test_name="Initialize Multi Mode",
                status=TestStatus.SKIP,
                message="Not enough supported wavelengths for multi mode test",
            ))

        # Test 8: Perform Test Read (only if plate is present)
        try:
            # Re-initialize for single wavelength read
            self.module_context.initialize(
                mode="single",
                wavelengths=[test_wavelength],
            )

            start_time = datetime.now()
            self.logger.info("Performing test read...")

            # Perform read
            read_result = self.module_context.read()
            duration = (datetime.now() - start_time).total_seconds()

            if read_result:
                results.append(TestResult(
                    test_name="Perform Absorbance Read",
                    status=TestStatus.PASS,
                    message=f"Read completed in {duration:.1f}s",
                    duration_seconds=duration,
                    details={"wavelength": test_wavelength, "has_data": bool(read_result)},
                ))
            else:
                results.append(TestResult(
                    test_name="Perform Absorbance Read",
                    status=TestStatus.WARNING,
                    message="Read completed but no data returned (plate may be empty/absent)",
                    duration_seconds=duration,
                ))

        except Exception as e:
            error_msg = str(e).lower()
            if "plate" in error_msg or "empty" in error_msg:
                results.append(TestResult(
                    test_name="Perform Absorbance Read",
                    status=TestStatus.SKIP,
                    message="Read skipped - no plate present",
                ))
            else:
                results.append(TestResult(
                    test_name="Perform Absorbance Read",
                    status=TestStatus.ERROR,
                    message=f"Error: {e}",
                ))

        return results
