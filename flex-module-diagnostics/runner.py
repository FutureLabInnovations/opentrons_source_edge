"""
Flex Module Diagnostics - Master Diagnostics Runner

This module provides the main entry point for running diagnostics on
Opentrons Flex modules. It can run diagnostics for all modules or
specific modules, and generates comprehensive service reports.

Usage (within a protocol):
    from flex_module_diagnostics import DiagnosticsRunner
    runner = DiagnosticsRunner(protocol_context)
    report = runner.run_all_diagnostics()

Usage (standalone with hardware access):
    runner = DiagnosticsRunner()
    runner.run_module_diagnostic("temperature_module", deck_slot="D1")
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .diagnostics import (
    TemperatureModuleDiagnostic,
    HeaterShakerDiagnostic,
    ThermocyclerDiagnostic,
    AbsorbanceReaderDiagnostic,
    MagneticBlockDiagnostic,
    FlexStackerDiagnostic,
    HepaUVDiagnostic,
)
from .utils.base import BaseModuleDiagnostic
from .utils.logger import DiagnosticLogger
from .utils.types import (
    ModuleDiagnosticResult,
    ModuleType,
    RobotInfo,
    ServiceReport,
    TestStatus,
)


# Mapping of module names to diagnostic classes
MODULE_DIAGNOSTICS: Dict[str, Type[BaseModuleDiagnostic]] = {
    "temperature_module": TemperatureModuleDiagnostic,
    "heater_shaker": HeaterShakerDiagnostic,
    "thermocycler": ThermocyclerDiagnostic,
    "absorbance_reader": AbsorbanceReaderDiagnostic,
    "magnetic_block": MagneticBlockDiagnostic,
    "flex_stacker": FlexStackerDiagnostic,
    "hepa_uv": HepaUVDiagnostic,
}

# Default deck slots for each module type
DEFAULT_SLOTS = {
    "temperature_module": "D1",
    "heater_shaker": "D1",
    "thermocycler": "A1",  # Thermocycler spans A1+B1
    "absorbance_reader": "D3",
    "magnetic_block": "C1",
    "flex_stacker": "B4",
    "hepa_uv": None,  # Not a deck module
}


class DiagnosticsRunner:
    """Master diagnostics runner for Flex modules."""

    def __init__(
        self,
        protocol_context: Optional[Any] = None,
        hardware_control: Optional[Any] = None,
        technician_name: str = "Service Technician",
        output_dir: Optional[Path] = None,
        log_level: int = 20,  # logging.INFO
    ):
        """Initialize the diagnostics runner.

        Args:
            protocol_context: Opentrons Protocol API context (if running as protocol)
            hardware_control: Direct hardware control access (for HEPA/UV)
            technician_name: Name of technician running diagnostics
            output_dir: Directory for output files (default: current directory)
            log_level: Logging level (default: INFO)
        """
        self.protocol_context = protocol_context
        self.hardware_control = hardware_control
        self.technician_name = technician_name
        self.output_dir = output_dir or Path(".")

        # Create logger
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"flex_diagnostics_{timestamp}.log"
        self.logger = DiagnosticLogger(
            name="FlexDiagnostics",
            log_file=log_file,
            console_level=log_level,
        )

        self.results: List[ModuleDiagnosticResult] = []
        self.robot_info: Optional[RobotInfo] = None

    def get_robot_info(self) -> RobotInfo:
        """Get information about the robot."""
        if self.protocol_context:
            try:
                # Try to get robot info from protocol context
                api_version = str(getattr(self.protocol_context, "api_version", "Unknown"))
                robot_type = str(getattr(self.protocol_context, "robot_type", "Unknown"))

                # Try to get more detailed info
                robot_id = "Unknown"
                software_version = "Unknown"

                if hasattr(self.protocol_context, "_hw_manager"):
                    hw = self.protocol_context._hw_manager
                    if hasattr(hw, "hardware"):
                        hardware = hw.hardware
                        if hasattr(hardware, "get_fw_version"):
                            software_version = str(hardware.get_fw_version())

                return RobotInfo(
                    robot_id=robot_id,
                    robot_name=robot_type,
                    software_version=software_version,
                    api_version=api_version,
                )
            except Exception as e:
                self.logger.warning(f"Could not get detailed robot info: {e}")

        return RobotInfo(
            robot_id="Unknown",
            robot_name="Opentrons Flex",
            software_version="Unknown",
            api_version="2.16+",  # Minimum for Flex
        )

    def run_module_diagnostic(
        self,
        module_name: str,
        deck_slot: Optional[str] = None,
        module_context: Optional[Any] = None,
    ) -> ModuleDiagnosticResult:
        """Run diagnostics for a specific module.

        Args:
            module_name: Name of the module (e.g., "temperature_module")
            deck_slot: Deck slot where module is located
            module_context: Pre-loaded module context (optional)

        Returns:
            ModuleDiagnosticResult with all test results
        """
        if module_name not in MODULE_DIAGNOSTICS:
            raise ValueError(f"Unknown module: {module_name}. "
                           f"Available: {list(MODULE_DIAGNOSTICS.keys())}")

        diagnostic_class = MODULE_DIAGNOSTICS[module_name]
        slot = deck_slot or DEFAULT_SLOTS.get(module_name)

        self.logger.info(f"Running diagnostics for {module_name}")

        # Create diagnostic instance with appropriate parameters
        if module_name == "hepa_uv":
            diagnostic = diagnostic_class(
                logger=self.logger,
                protocol_context=self.protocol_context,
                hardware_control=self.hardware_control,
            )
        elif module_name == "thermocycler":
            diagnostic = diagnostic_class(
                logger=self.logger,
                protocol_context=self.protocol_context,
                module_context=module_context,
            )
        else:
            diagnostic = diagnostic_class(
                logger=self.logger,
                protocol_context=self.protocol_context,
                module_context=module_context,
                deck_slot=slot,
            )

        result = diagnostic.run_diagnostics()
        self.results.append(result)
        return result

    def run_all_diagnostics(
        self,
        modules: Optional[List[str]] = None,
        skip_modules: Optional[List[str]] = None,
    ) -> ServiceReport:
        """Run diagnostics for all (or specified) modules.

        Args:
            modules: List of specific modules to test (default: all)
            skip_modules: List of modules to skip

        Returns:
            ServiceReport with all results
        """
        self.logger.info("=" * 70)
        self.logger.info("OPENTRONS FLEX MODULE DIAGNOSTICS SUITE")
        self.logger.info("=" * 70)
        self.logger.info(f"Technician: {self.technician_name}")
        self.logger.info(f"Date: {datetime.now().isoformat()}")
        self.logger.info("")

        # Get robot info
        self.robot_info = self.get_robot_info()
        self.logger.info(f"Robot: {self.robot_info.robot_name}")
        self.logger.info(f"Software Version: {self.robot_info.software_version}")
        self.logger.info(f"API Version: {self.robot_info.api_version}")
        self.logger.info("")

        # Determine which modules to test
        modules_to_test = modules or list(MODULE_DIAGNOSTICS.keys())
        if skip_modules:
            modules_to_test = [m for m in modules_to_test if m not in skip_modules]

        self.logger.info(f"Modules to test: {', '.join(modules_to_test)}")
        self.logger.info("")

        # Run diagnostics for each module
        self.results = []
        for module_name in modules_to_test:
            try:
                self.run_module_diagnostic(module_name)
            except Exception as e:
                self.logger.error(f"Failed to run diagnostics for {module_name}: {e}")

        # Create service report
        report = self._create_service_report()

        # Save reports
        self._save_reports(report)

        # Print summary
        self._print_summary(report)

        return report

    def run_detected_modules(self) -> ServiceReport:
        """Run diagnostics only for modules that are detected/connected.

        This method first attempts to detect which modules are present,
        then runs diagnostics only on those modules.
        """
        self.logger.info("Scanning for connected modules...")

        detected_modules = []

        # Try to detect each module type
        for module_name, diagnostic_class in MODULE_DIAGNOSTICS.items():
            try:
                if module_name == "hepa_uv":
                    diagnostic = diagnostic_class(
                        logger=self.logger,
                        hardware_control=self.hardware_control,
                    )
                elif module_name == "thermocycler":
                    diagnostic = diagnostic_class(
                        logger=self.logger,
                        protocol_context=self.protocol_context,
                    )
                else:
                    diagnostic = diagnostic_class(
                        logger=self.logger,
                        protocol_context=self.protocol_context,
                        deck_slot=DEFAULT_SLOTS.get(module_name),
                    )

                module_info = diagnostic.detect_module()
                if module_info and not module_info.is_simulated:
                    detected_modules.append(module_name)
                    self.logger.info(f"  ✓ {module_name}: Detected")
                else:
                    self.logger.info(f"  ○ {module_name}: Not detected")

            except Exception as e:
                self.logger.debug(f"  ✗ {module_name}: Error - {e}")

        if not detected_modules:
            self.logger.warning("No modules detected. Running all diagnostics anyway.")
            return self.run_all_diagnostics()

        self.logger.info(f"\nRunning diagnostics for {len(detected_modules)} detected modules")
        return self.run_all_diagnostics(modules=detected_modules)

    def _create_service_report(self) -> ServiceReport:
        """Create a service report from diagnostic results."""
        report = ServiceReport(
            robot_info=self.robot_info or self.get_robot_info(),
            technician_name=self.technician_name,
        )

        for result in self.results:
            report.add_module_result(result)
            if result.module_info.serial_number != "N/A":
                report.detected_modules.append(result.module_info)

        # Compile recommendations
        for result in self.results:
            report.recommendations.extend(result.recommendations)

        return report

    def _save_reports(self, report: ServiceReport) -> None:
        """Save reports to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_path = self.output_dir / f"flex_diagnostics_{timestamp}.json"
        try:
            json_data = self._report_to_dict(report)
            with open(json_path, "w") as f:
                json.dump(json_data, f, indent=2, default=str)
            self.logger.info(f"JSON report saved: {json_path}")
        except Exception as e:
            self.logger.error(f"Failed to save JSON report: {e}")

        # Save Markdown report
        md_path = self.output_dir / f"flex_diagnostics_{timestamp}.md"
        try:
            md_content = self._generate_markdown_report(report)
            with open(md_path, "w") as f:
                f.write(md_content)
            self.logger.info(f"Markdown report saved: {md_path}")
        except Exception as e:
            self.logger.error(f"Failed to save Markdown report: {e}")

    def _report_to_dict(self, report: ServiceReport) -> Dict[str, Any]:
        """Convert service report to dictionary for JSON serialization."""
        return {
            "report_date": report.report_date.isoformat(),
            "technician_name": report.technician_name,
            "overall_status": report.overall_status.value,
            "robot_info": {
                "robot_id": report.robot_info.robot_id,
                "robot_name": report.robot_info.robot_name,
                "software_version": report.robot_info.software_version,
                "api_version": report.robot_info.api_version,
            },
            "summary": {
                "total_tests": report.total_tests,
                "passed": report.total_pass,
                "failed": report.total_fail,
                "modules_tested": len(report.module_results),
            },
            "module_results": [
                {
                    "module_type": result.module_info.module_type.value,
                    "model": result.module_info.model,
                    "serial_number": result.module_info.serial_number,
                    "firmware_version": result.module_info.firmware_version,
                    "deck_slot": result.module_info.deck_slot,
                    "overall_status": result.overall_status.value,
                    "calibration": {
                        "is_calibrated": result.calibration_status.is_calibrated,
                        "notes": result.calibration_status.notes,
                    } if result.calibration_status else None,
                    "tests": [
                        {
                            "name": test.test_name,
                            "status": test.status.value,
                            "message": test.message,
                            "duration_seconds": test.duration_seconds,
                            "expected": test.expected_value,
                            "actual": test.actual_value,
                            "details": test.details,
                        }
                        for test in result.test_results
                    ],
                    "recommendations": result.recommendations,
                }
                for result in report.module_results
            ],
            "recommendations": report.recommendations,
        }

    def _generate_markdown_report(self, report: ServiceReport) -> str:
        """Generate a Markdown service report."""
        lines = [
            "# Opentrons Flex Module Diagnostics Report",
            "",
            "## Summary",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Date | {report.report_date.strftime('%Y-%m-%d %H:%M:%S')} |",
            f"| Technician | {report.technician_name} |",
            f"| Robot | {report.robot_info.robot_name} |",
            f"| Robot ID | {report.robot_info.robot_id} |",
            f"| Software Version | {report.robot_info.software_version} |",
            f"| API Version | {report.robot_info.api_version} |",
            f"| Overall Status | **{report.overall_status.value}** |",
            "",
            "## Test Results Overview",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Tests | {report.total_tests} |",
            f"| Passed | {report.total_pass} |",
            f"| Failed | {report.total_fail} |",
            f"| Modules Tested | {len(report.module_results)} |",
            "",
        ]

        # Module Results Table
        lines.extend([
            "## Module Status Summary",
            "",
            "| Module | Model | Serial Number | Firmware | Status | Pass/Fail |",
            "|--------|-------|---------------|----------|--------|-----------|",
        ])

        for result in report.module_results:
            status_emoji = "✓" if result.overall_status == TestStatus.PASS else "✗"
            lines.append(
                f"| {result.module_info.module_type.value} | "
                f"{result.module_info.model} | "
                f"{result.module_info.serial_number} | "
                f"{result.module_info.firmware_version} | "
                f"{status_emoji} {result.overall_status.value} | "
                f"{result.pass_count}/{result.total_tests} |"
            )

        lines.append("")

        # Detailed Results per Module
        lines.extend([
            "## Detailed Test Results",
            "",
        ])

        for result in report.module_results:
            lines.extend([
                f"### {result.module_info.module_type.value}",
                "",
                f"**Model:** {result.module_info.model}  ",
                f"**Serial:** {result.module_info.serial_number}  ",
                f"**Firmware:** {result.module_info.firmware_version}  ",
                f"**Slot:** {result.module_info.deck_slot or 'N/A'}  ",
                "",
            ])

            # Calibration status
            if result.calibration_status:
                cal = result.calibration_status
                cal_status = "Calibrated" if cal.is_calibrated else "Not Calibrated"
                lines.extend([
                    f"**Calibration:** {cal_status}  ",
                ])
                if cal.is_calibrated and cal.offset_x is not None:
                    lines.append(
                        f"**Offset:** ({cal.offset_x:.3f}, {cal.offset_y:.3f}, {cal.offset_z:.3f})  "
                    )
                if cal.notes:
                    lines.append(f"**Notes:** {cal.notes}  ")
                lines.append("")

            # Test results table
            lines.extend([
                "| Test | Status | Duration | Message |",
                "|------|--------|----------|---------|",
            ])

            for test in result.test_results:
                status_emoji = {
                    TestStatus.PASS: "✓",
                    TestStatus.FAIL: "✗",
                    TestStatus.SKIP: "○",
                    TestStatus.WARNING: "⚠",
                    TestStatus.ERROR: "!",
                }.get(test.status, "?")

                duration = f"{test.duration_seconds:.2f}s" if test.duration_seconds else "-"
                message = test.message[:50] + "..." if len(test.message) > 50 else test.message

                lines.append(
                    f"| {test.test_name} | "
                    f"{status_emoji} {test.status.value} | "
                    f"{duration} | "
                    f"{message} |"
                )

            lines.append("")

            # Recommendations for this module
            if result.recommendations:
                lines.extend([
                    "**Recommendations:**",
                    "",
                ])
                for rec in result.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        # Overall Recommendations
        if report.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for rec in report.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # Footer
        lines.extend([
            "---",
            "",
            f"*Report generated by Flex Module Diagnostics Suite*  ",
            f"*https://github.com/Opentrons/opentrons*",
        ])

        return "\n".join(lines)

    def _print_summary(self, report: ServiceReport) -> None:
        """Print a summary of the diagnostic results."""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("DIAGNOSTICS COMPLETE")
        self.logger.info("=" * 70)
        self.logger.info("")
        self.logger.info(f"Overall Status: {report.overall_status.value}")
        self.logger.info(f"Tests Passed: {report.total_pass}/{report.total_tests}")
        self.logger.info(f"Tests Failed: {report.total_fail}/{report.total_tests}")
        self.logger.info("")

        for result in report.module_results:
            status = "PASS" if result.overall_status == TestStatus.PASS else "FAIL"
            self.logger.info(
                f"  {result.module_info.module_type.value}: {status} "
                f"({result.pass_count}/{result.total_tests})"
            )

        if report.recommendations:
            self.logger.info("")
            self.logger.info("Recommendations:")
            for rec in report.recommendations[:5]:  # Show first 5
                self.logger.info(f"  - {rec}")
            if len(report.recommendations) > 5:
                self.logger.info(f"  ... and {len(report.recommendations) - 5} more")

        self.logger.info("")
        self.logger.info(f"Reports saved to: {self.output_dir}")
