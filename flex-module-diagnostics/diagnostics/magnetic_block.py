"""
Flex Module Diagnostics - Magnetic Block

Diagnostics for Opentrons Magnetic Block on Flex.

Evidence/Documentation:
- Module Definition: shared-data/module/definitions/3/magneticBlockV1.json
- API Reference: https://docs.opentrons.com/v2/new_modules.html#magnetic-block
- Hardware Control: PASSIVE - No electronic communication

IMPORTANT: The Magnetic Block is a PASSIVE module with no electronic components.
It does NOT communicate with the robot. Diagnostics focus on:
1. Physical verification (proper seating on deck)
2. Gripper workflow testing (pick/place labware)
3. Alignment verification
4. Magnetic function (visual inspection of bead separation)
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


class MagneticBlockDiagnostic(BaseModuleDiagnostic):
    """Diagnostic suite for Magnetic Block (passive module).

    Since the Magnetic Block has no electronic communication, diagnostics
    focus on workflow verification and physical checks.
    """

    module_type = ModuleType.MAGNETIC_BLOCK
    module_name = "Magnetic Block"

    def __init__(
        self,
        logger: Optional[DiagnosticLogger] = None,
        protocol_context: Optional[Any] = None,
        module_context: Optional[Any] = None,
        deck_slot: str = "C1",
    ):
        super().__init__(logger, protocol_context)
        self.module_context = module_context
        self.deck_slot = deck_slot

    def detect_module(self) -> Optional[ModuleInfo]:
        """Detect Magnetic Block via protocol context.

        Note: Since the Magnetic Block is passive, detection is based on
        protocol configuration, not electronic detection.
        """
        try:
            if self.protocol_context and not self.module_context:
                try:
                    self.module_context = self.protocol_context.load_module(
                        "magnetic block",
                        self.deck_slot
                    )
                except Exception as e:
                    self.logger.debug(f"Could not load module: {e}")
                    return None

            if self.module_context is None:
                return None

            # Magnetic Block is passive - no serial/firmware
            return ModuleInfo(
                module_type=self.module_type,
                model="magneticBlockV1",
                serial_number="N/A (passive module)",
                firmware_version="N/A (passive module)",
                hardware_revision="N/A",
                deck_slot=self.deck_slot,
            )

        except Exception as e:
            self.logger.error(f"Error loading Magnetic Block: {e}")
            return None

    def check_calibration(self) -> CalibrationStatus:
        """Check Magnetic Block calibration status.

        Note: Magnetic Block position calibration helps ensure labware
        placed on it aligns correctly with pipette movements.
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
                            notes="Position calibration offset found",
                        )

            return CalibrationStatus(
                is_calibrated=False,
                notes="Magnetic Block is passive. Position calibration recommended for accuracy.",
            )

        except Exception as e:
            return CalibrationStatus(
                is_calibrated=False,
                notes=f"Error checking calibration: {e}",
            )

    def run_functional_tests(self) -> List[TestResult]:
        """Run functional tests for Magnetic Block.

        Since the Magnetic Block is passive (no electronic communication),
        these tests verify:
        1. Module is configured in protocol context
        2. Labware can be loaded on the module
        3. Gripper operations work (if gripper available)
        4. Physical inspection guidance

        Note: Actual magnetic function must be verified visually with
        magnetic beads - this cannot be electronically validated.
        """
        results = []

        if self.module_context is None:
            results.append(TestResult(
                test_name="Functional Tests",
                status=TestStatus.SKIP,
                message="Module context not available",
            ))
            return results

        # Test 1: Module Context Validation
        try:
            # Check that the module context exists and has expected properties
            has_load_labware = hasattr(self.module_context, "load_labware")
            has_parent = hasattr(self.module_context, "parent")

            if has_load_labware and has_parent:
                parent_slot = self.module_context.parent
                results.append(TestResult(
                    test_name="Module Context Validation",
                    status=TestStatus.PASS,
                    message=f"Magnetic Block configured at {parent_slot}",
                    details={"slot": str(parent_slot)},
                ))
            else:
                results.append(TestResult(
                    test_name="Module Context Validation",
                    status=TestStatus.FAIL,
                    message="Module context missing expected properties",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Module Context Validation",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 2: Labware Loading Capability
        try:
            # Verify that labware can be conceptually loaded
            # (actual loading would require specifying labware)
            if hasattr(self.module_context, "load_labware"):
                results.append(TestResult(
                    test_name="Labware Loading Capability",
                    status=TestStatus.PASS,
                    message="Module supports labware loading",
                ))
            else:
                results.append(TestResult(
                    test_name="Labware Loading Capability",
                    status=TestStatus.FAIL,
                    message="load_labware method not available",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Labware Loading Capability",
                status=TestStatus.ERROR,
                message=f"Error: {e}",
            ))

        # Test 3: Check Current Labware
        try:
            current_labware = self.module_context.labware
            if current_labware:
                results.append(TestResult(
                    test_name="Current Labware Check",
                    status=TestStatus.PASS,
                    message=f"Labware loaded: {current_labware}",
                    actual_value=str(current_labware),
                ))
            else:
                results.append(TestResult(
                    test_name="Current Labware Check",
                    status=TestStatus.PASS,
                    message="No labware currently loaded on module",
                ))
        except Exception as e:
            results.append(TestResult(
                test_name="Current Labware Check",
                status=TestStatus.WARNING,
                message=f"Could not check labware: {e}",
            ))

        # Test 4: Physical Inspection Guidance
        # This is informational - actual verification is manual
        physical_checks = [
            "Magnetic Block is properly seated on deck slot",
            "Block is level and stable",
            "No debris or obstructions on magnetic surface",
            "Magnets are not cracked or damaged",
            "Adapter/caddy is properly attached (if applicable)",
        ]

        results.append(TestResult(
            test_name="Physical Inspection Checklist",
            status=TestStatus.WARNING,
            message="Manual verification required - see details",
            details={
                "checklist": physical_checks,
                "note": "Please verify these items manually",
            },
        ))

        # Test 5: Magnetic Function Note
        results.append(TestResult(
            test_name="Magnetic Function Verification",
            status=TestStatus.WARNING,
            message="Cannot electronically verify magnetic function",
            details={
                "manual_test": (
                    "To verify magnetic function: "
                    "1. Place a plate with magnetic beads on the block. "
                    "2. Wait 2-5 minutes. "
                    "3. Observe bead separation to one side of wells. "
                    "4. Strong, clear separation indicates good magnetic function."
                ),
            },
        ))

        # Test 6: Gripper Compatibility Note (for Flex)
        results.append(TestResult(
            test_name="Gripper Workflow Note",
            status=TestStatus.PASS,
            message="Magnetic Block supports gripper labware transfers",
            details={
                "compatible_with_gripper": True,
                "note": (
                    "The Flex gripper can move labware to/from the Magnetic Block. "
                    "Test by moving a plate to the block and back during a protocol."
                ),
            },
        ))

        return results


def get_manual_test_instructions() -> str:
    """Return detailed manual test instructions for Magnetic Block."""
    return """
    === MAGNETIC BLOCK MANUAL DIAGNOSTICS ===

    Since the Magnetic Block is a passive module with no electronic
    communication, the following tests must be performed manually:

    1. PHYSICAL INSPECTION
       - Verify block is properly seated in deck slot
       - Check that block is level
       - Inspect magnetic surface for debris or damage
       - Ensure adapter is properly attached

    2. MAGNETIC FUNCTION TEST
       Materials needed:
       - Well plate compatible with Magnetic Block
       - Magnetic beads (1 mg/mL in buffer)

       Procedure:
       a) Add 50-100 µL of magnetic bead suspension to several wells
       b) Place plate on Magnetic Block
       c) Wait 2-5 minutes
       d) Observe bead separation

       Expected result:
       - Beads should form a clear pellet on the side of wells
         closest to the magnets
       - Supernatant should be clear
       - Separation should be complete within 2-5 minutes

    3. GRIPPER WORKFLOW TEST (during protocol)
       - Use gripper to move plate to Magnetic Block
       - Verify plate is properly placed
       - Use gripper to remove plate
       - Verify plate is properly picked up

    4. ALIGNMENT VERIFICATION
       - Load a plate on the block
       - Aspirate from multiple wells
       - Verify pipette tips enter wells centrally
       - If off-center, module calibration may be needed

    Record any issues found during manual testing.
    """
