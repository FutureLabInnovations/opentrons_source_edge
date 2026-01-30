"""
Flex Module Diagnostics - Type Definitions

Defines data structures for diagnostic results, test cases, and service reports.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TestStatus(str, Enum):
    """Status of a diagnostic test."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ModuleType(str, Enum):
    """Supported Flex module types."""
    TEMPERATURE_MODULE = "temperatureModuleType"
    THERMOCYCLER = "thermocyclerModuleType"
    HEATER_SHAKER = "heaterShakerModuleType"
    MAGNETIC_BLOCK = "magneticBlockType"
    ABSORBANCE_READER = "absorbanceReaderType"
    FLEX_STACKER = "flexStackerModuleType"
    HEPA_UV = "hepaUVType"


@dataclass
class ModuleInfo:
    """Information about a detected module."""
    module_type: ModuleType
    model: str
    serial_number: str
    firmware_version: str
    hardware_revision: str
    usb_port: Optional[str] = None
    deck_slot: Optional[str] = None
    is_simulated: bool = False


@dataclass
class CalibrationStatus:
    """Calibration status for a module."""
    is_calibrated: bool
    last_calibrated: Optional[datetime] = None
    offset_x: Optional[float] = None
    offset_y: Optional[float] = None
    offset_z: Optional[float] = None
    calibration_source: Optional[str] = None
    notes: str = ""


@dataclass
class TestResult:
    """Result of a single diagnostic test."""
    test_name: str
    status: TestStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None


@dataclass
class ModuleDiagnosticResult:
    """Complete diagnostic result for a module."""
    module_info: ModuleInfo
    calibration_status: Optional[CalibrationStatus]
    test_results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    overall_status: TestStatus = TestStatus.PASS
    notes: str = ""
    recommendations: List[str] = field(default_factory=list)

    def add_test_result(self, result: TestResult) -> None:
        """Add a test result and update overall status."""
        self.test_results.append(result)
        if result.status == TestStatus.FAIL:
            self.overall_status = TestStatus.FAIL
        elif result.status == TestStatus.ERROR and self.overall_status != TestStatus.FAIL:
            self.overall_status = TestStatus.ERROR
        elif result.status == TestStatus.WARNING and self.overall_status == TestStatus.PASS:
            self.overall_status = TestStatus.WARNING

    def finalize(self) -> None:
        """Mark the diagnostic as complete."""
        self.end_time = datetime.now()

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.test_results if r.status == TestStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.test_results if r.status == TestStatus.FAIL)

    @property
    def total_tests(self) -> int:
        return len(self.test_results)


@dataclass
class RobotInfo:
    """Information about the Flex robot."""
    robot_id: str
    robot_name: str
    software_version: str
    api_version: str
    ip_address: Optional[str] = None
    serial_number: Optional[str] = None


@dataclass
class ServiceReport:
    """Complete service report for a diagnostics run."""
    robot_info: RobotInfo
    technician_name: str
    report_date: datetime = field(default_factory=datetime.now)
    module_results: List[ModuleDiagnosticResult] = field(default_factory=list)
    detected_modules: List[ModuleInfo] = field(default_factory=list)
    undetected_expected_modules: List[str] = field(default_factory=list)
    overall_status: TestStatus = TestStatus.PASS
    notes: str = ""
    recommendations: List[str] = field(default_factory=list)

    def add_module_result(self, result: ModuleDiagnosticResult) -> None:
        """Add a module result and update overall status."""
        self.module_results.append(result)
        if result.overall_status == TestStatus.FAIL:
            self.overall_status = TestStatus.FAIL
        elif result.overall_status == TestStatus.ERROR and self.overall_status != TestStatus.FAIL:
            self.overall_status = TestStatus.ERROR

    @property
    def total_pass(self) -> int:
        return sum(r.pass_count for r in self.module_results)

    @property
    def total_fail(self) -> int:
        return sum(r.fail_count for r in self.module_results)

    @property
    def total_tests(self) -> int:
        return sum(r.total_tests for r in self.module_results)


# Safe operating limits for each module type
SAFE_LIMITS = {
    ModuleType.TEMPERATURE_MODULE: {
        "min_temp": 4.0,  # Celsius
        "max_temp": 95.0,
        "test_temp": 37.0,  # Safe test temperature
        "temp_tolerance": 1.0,
        "temp_timeout_seconds": 300,
    },
    ModuleType.THERMOCYCLER: {
        "min_block_temp": 4.0,
        "max_block_temp": 99.0,
        "min_lid_temp": 37.0,
        "max_lid_temp": 110.0,
        "test_block_temp": 37.0,
        "test_lid_temp": 50.0,
        "temp_tolerance": 1.0,
        "temp_timeout_seconds": 300,
    },
    ModuleType.HEATER_SHAKER: {
        "min_temp": 25.0,  # Room temperature
        "max_temp": 95.0,
        "min_rpm": 200,
        "max_rpm": 3000,
        "test_temp": 37.0,
        "test_rpm": 500,  # Safe low speed
        "test_duration_seconds": 10,
        "temp_tolerance": 1.0,
        "rpm_tolerance": 50,
    },
    ModuleType.ABSORBANCE_READER: {
        "supported_wavelengths": [450, 562, 600, 650],  # Common wavelengths
        "read_timeout_seconds": 60,
    },
    ModuleType.FLEX_STACKER: {
        "max_stack_count": 5,
        "latch_timeout_seconds": 30,
    },
    ModuleType.HEPA_UV: {
        "min_duty_cycle": 10,
        "max_duty_cycle": 100,
        "test_duty_cycle": 50,
        "test_uv_duration_seconds": 5,
        "fan_spinup_seconds": 3,
    },
}


# Common failure modes and troubleshooting
FAILURE_MODES = {
    ModuleType.TEMPERATURE_MODULE: {
        "not_detected": [
            "Check USB cable connection between module and robot",
            "Verify module is properly seated on deck",
            "Check for damaged USB port on module",
            "Try different USB port on robot",
            "Restart robot and rescan modules",
        ],
        "temp_not_reaching": [
            "Ensure thermal block is clean and free of debris",
            "Check for obstructions around module vents",
            "Verify ambient temperature is within operating range",
            "Check for damaged peltier or heatsink",
        ],
        "calibration_failed": [
            "Clean calibration probe and module surface",
            "Ensure robot is on stable, level surface",
            "Recalibrate pipettes before module calibration",
        ],
    },
    ModuleType.THERMOCYCLER: {
        "not_detected": [
            "Check USB cable connection",
            "Verify module is in slot A1+B1 (spans two slots)",
            "Restart robot and rescan modules",
        ],
        "lid_not_opening": [
            "Check for obstructions around lid mechanism",
            "Verify lid motor is functional",
            "Check for physical damage to lid hinge",
        ],
        "temp_not_reaching": [
            "Ensure block surface is clean",
            "Check lid seal condition",
            "Verify thermal paste is intact",
        ],
    },
    ModuleType.HEATER_SHAKER: {
        "not_detected": [
            "Check USB cable connection",
            "Verify module is properly seated on deck",
            "Check deck adapter/caddy seating",
        ],
        "latch_not_closing": [
            "Check for labware misalignment",
            "Verify labware is compatible",
            "Inspect latch mechanism for debris",
        ],
        "shaking_unstable": [
            "Verify labware is properly seated",
            "Check latch is fully closed",
            "Reduce shake speed for heavy labware",
        ],
    },
    ModuleType.ABSORBANCE_READER: {
        "not_detected": [
            "Check USB cable connection",
            "Verify module is properly positioned",
            "Restart robot and rescan",
        ],
        "read_failed": [
            "Verify plate is properly inserted",
            "Check lid is closed",
            "Clean optical sensors",
            "Verify wavelength is supported",
        ],
    },
    ModuleType.MAGNETIC_BLOCK: {
        "gripper_issues": [
            "Verify magnetic block is properly seated on deck",
            "Check deck slot alignment",
            "Ensure no obstructions around block",
            "Recalibrate gripper if needed",
        ],
    },
    ModuleType.FLEX_STACKER: {
        "not_detected": [
            "Check USB cable connection",
            "Verify module is properly positioned",
            "Check hopper door sensor",
        ],
        "stacking_failed": [
            "Verify labware is compatible",
            "Check for obstructions in hopper",
            "Inspect latch mechanism",
            "Verify TOF sensors are clean",
        ],
    },
    ModuleType.HEPA_UV: {
        "not_detected": [
            "Check CAN bus connection",
            "Verify enclosure is properly closed",
            "Restart robot",
        ],
        "fan_not_running": [
            "Check for obstructions in fan intake/exhaust",
            "Verify power supply",
            "Check fan motor",
        ],
        "uv_not_activating": [
            "Verify safety interlocks are engaged",
            "Check UV bulb condition",
            "Verify door is closed",
        ],
    },
}
