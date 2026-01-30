"""
Opentrons Flex Module Diagnostics Suite

A comprehensive diagnostics package for validating Opentrons Flex modules.

Supported Modules:
- Temperature Module (Gen2)
- Heater-Shaker Module
- Thermocycler Module (Gen2 only on Flex)
- Absorbance Plate Reader
- Magnetic Block (passive - workflow testing)
- Flex Stacker Module
- HEPA/UV Module

Usage:
    # In a protocol
    from flex_module_diagnostics import DiagnosticsRunner

    def run(protocol):
        runner = DiagnosticsRunner(
            protocol_context=protocol,
            technician_name="Your Name"
        )
        report = runner.run_all_diagnostics()

    # For specific modules
    runner.run_module_diagnostic("temperature_module", deck_slot="D1")
"""

from .runner import DiagnosticsRunner
from .diagnostics import (
    TemperatureModuleDiagnostic,
    HeaterShakerDiagnostic,
    ThermocyclerDiagnostic,
    AbsorbanceReaderDiagnostic,
    MagneticBlockDiagnostic,
    FlexStackerDiagnostic,
    HepaUVDiagnostic,
)
from .utils.types import (
    ModuleType,
    TestStatus,
    ModuleInfo,
    TestResult,
    ModuleDiagnosticResult,
    ServiceReport,
)

__version__ = "1.0.0"
__all__ = [
    "DiagnosticsRunner",
    "TemperatureModuleDiagnostic",
    "HeaterShakerDiagnostic",
    "ThermocyclerDiagnostic",
    "AbsorbanceReaderDiagnostic",
    "MagneticBlockDiagnostic",
    "FlexStackerDiagnostic",
    "HepaUVDiagnostic",
    "ModuleType",
    "TestStatus",
    "ModuleInfo",
    "TestResult",
    "ModuleDiagnosticResult",
    "ServiceReport",
]
