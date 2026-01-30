"""
Flex Module Diagnostics - Base Diagnostic Class

Provides base functionality for all module diagnostics.
"""
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .logger import DiagnosticLogger, default_logger
from .types import (
    CalibrationStatus,
    FAILURE_MODES,
    ModuleDiagnosticResult,
    ModuleInfo,
    ModuleType,
    SAFE_LIMITS,
    TestResult,
    TestStatus,
)

T = TypeVar("T")


class BaseModuleDiagnostic(ABC):
    """Base class for module diagnostics."""

    module_type: ModuleType
    module_name: str

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
    ):
        self.logger = logger or default_logger
        self.protocol_context = protocol_context
        self.module_context: Optional[Any] = None
        self.result: Optional[ModuleDiagnosticResult] = None
        self.safe_limits = SAFE_LIMITS.get(self.module_type, {})
        self.failure_modes = FAILURE_MODES.get(self.module_type, {})

    @abstractmethod
    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect and identify the module. Returns ModuleInfo if found."""
        pass

    @abstractmethod
    def check_calibration(self) -> CalibrationStatus:
        """Check module calibration status."""
        pass

    @abstractmethod
    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for the module."""
        pass

    def run_diagnostics(self) -> ModuleDiagnosticResult:
        """Run complete diagnostics for this module."""
        self.logger.module_start(self.module_name)

        # Detect module
        self.logger.section("Module Detection")
        module_info = self.detect_module()

        if module_info is None:
            # Module not detected - create minimal result
            self.result = ModuleDiagnosticResult(
                module_info=ModuleInfo(
                    module_type=self.module_type,
                    model="unknown",
                    serial_number="N/A",
                    firmware_version="N/A",
                    hardware_revision="N/A",
                ),
                calibration_status=None,
                overall_status=TestStatus.SKIP,
                notes=f"{self.module_name} not detected",
                recommendations=self.failure_modes.get("not_detected", []),
            )
            self.result.add_test_result(TestResult(
                test_name="Module Detection",
                status=TestStatus.SKIP,
                message=f"{self.module_name} not detected or not installed",
            ))
            self.result.finalize()
            self.logger.test_skip("Module Detection", "Module not found")
            return self.result

        self.logger.test_pass(
            "Module Detection",
            f"Found {module_info.model} (S/N: {module_info.serial_number}, "
            f"FW: {module_info.firmware_version})"
        )

        # Initialize result
        self.result = ModuleDiagnosticResult(
            module_info=module_info,
            calibration_status=None,
        )
        self.result.add_test_result(TestResult(
            test_name="Module Detection",
            status=TestStatus.PASS,
            message=f"Detected {module_info.model}",
            details={
                "serial_number": module_info.serial_number,
                "firmware_version": module_info.firmware_version,
                "hardware_revision": module_info.hardware_revision,
            },
        ))

        # Check calibration
        self.logger.section("Calibration Check")
        try:
            calibration = self.check_calibration()
            self.result.calibration_status = calibration
            if calibration.is_calibrated:
                self.logger.test_pass(
                    "Calibration Status",
                    f"Module is calibrated (offset: {calibration.offset_x}, "
                    f"{calibration.offset_y}, {calibration.offset_z})"
                )
                self.result.add_test_result(TestResult(
                    test_name="Calibration Status",
                    status=TestStatus.PASS,
                    message="Module is calibrated",
                    details={
                        "offset_x": calibration.offset_x,
                        "offset_y": calibration.offset_y,
                        "offset_z": calibration.offset_z,
                        "last_calibrated": str(calibration.last_calibrated),
                    },
                ))
            else:
                self.logger.test_warning(
                    "Calibration Status",
                    "Module not calibrated"
                )
                self.result.add_test_result(TestResult(
                    test_name="Calibration Status",
                    status=TestStatus.WARNING,
                    message="Module not calibrated - calibration recommended",
                ))
                self.result.recommendations.append(
                    "Run module calibration before using in protocols"
                )
        except Exception as e:
            self.logger.test_fail("Calibration Status", str(e))
            self.result.add_test_result(TestResult(
                test_name="Calibration Status",
                status=TestStatus.ERROR,
                message=f"Failed to check calibration: {e}",
            ))

        # Run functional tests
        self.logger.section("Functional Tests")
        try:
            functional_results = self.run_functional_tests()
            for result in functional_results:
                self.result.add_test_result(result)
                if result.status == TestStatus.PASS:
                    self.logger.test_pass(result.test_name, result.message)
                elif result.status == TestStatus.FAIL:
                    self.logger.test_fail(result.test_name, result.message)
                elif result.status == TestStatus.WARNING:
                    self.logger.test_warning(result.test_name, result.message)
                elif result.status == TestStatus.SKIP:
                    self.logger.test_skip(result.test_name, result.message)
        except Exception as e:
            self.logger.error(f"Functional tests failed with error: {e}")
            self.result.add_test_result(TestResult(
                test_name="Functional Tests",
                status=TestStatus.ERROR,
                message=f"Tests aborted due to error: {e}",
            ))

        self.result.finalize()
        self.logger.module_end(
            self.module_name,
            self.result.pass_count,
            self.result.fail_count
        )

        return self.result

    def run_test(
        self,
        test_name: str,
        test_func: Callable[[], T],
        expected_result: Optional[T] = None,
        validator: Optional[Callable[[T], bool]] = None,
    ) -> TestResult:
        """Run a single test with timing and error handling."""
        start_time = self.logger.test_start(test_name)
        try:
            result = test_func()
            duration = (datetime.now() - start_time).total_seconds()

            # Validate result
            if validator is not None:
                if validator(result):
                    return TestResult(
                        test_name=test_name,
                        status=TestStatus.PASS,
                        message="Test passed",
                        duration_seconds=duration,
                        actual_value=result,
                        expected_value=expected_result,
                    )
                else:
                    return TestResult(
                        test_name=test_name,
                        status=TestStatus.FAIL,
                        message=f"Validation failed",
                        duration_seconds=duration,
                        actual_value=result,
                        expected_value=expected_result,
                    )
            elif expected_result is not None:
                if result == expected_result:
                    return TestResult(
                        test_name=test_name,
                        status=TestStatus.PASS,
                        message="Result matches expected",
                        duration_seconds=duration,
                        actual_value=result,
                        expected_value=expected_result,
                    )
                else:
                    return TestResult(
                        test_name=test_name,
                        status=TestStatus.FAIL,
                        message=f"Expected {expected_result}, got {result}",
                        duration_seconds=duration,
                        actual_value=result,
                        expected_value=expected_result,
                    )
            else:
                # No validation, just check for exceptions
                return TestResult(
                    test_name=test_name,
                    status=TestStatus.PASS,
                    message="Test completed successfully",
                    duration_seconds=duration,
                    actual_value=result,
                )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return TestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                message=f"Test error: {e}",
                duration_seconds=duration,
            )

    def wait_with_timeout(
        self,
        condition: Callable[[], bool],
        timeout_seconds: float,
        poll_interval: float = 0.5,
        description: str = "",
    ) -> bool:
        """Wait for a condition with timeout."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            if condition():
                return True
            time.sleep(poll_interval)
        self.logger.warning(
            f"Timeout waiting for {description} after {timeout_seconds}s"
        )
        return False

    def check_temperature_tolerance(
        self,
        actual: float,
        target: float,
        tolerance: float,
    ) -> bool:
        """Check if temperature is within tolerance of target."""
        return abs(actual - target) <= tolerance
