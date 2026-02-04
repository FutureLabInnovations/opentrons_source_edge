# AI Prompt: Create Opentrons Flex Robot Maintenance Service Toolkit

## Important Instructions

**DO NOT ASSUME OR HALLUCINATE SPECIFICATIONS.** You must research and verify ALL technical information by:

1. **Searching the Opentrons GitHub repositories** (https://github.com/Opentrons)
2. **Reading actual source code** to find real values
3. **Fetching official documentation** when available
4. **Explicitly stating when information cannot be verified**

If you cannot find authoritative information for a specification, clearly mark it as "NEEDS VERIFICATION" rather than guessing.

---

## Task Overview

Create a comprehensive maintenance and service toolkit for the **Opentrons Flex** liquid handling robot. This toolkit will be used by field service technicians to perform annual maintenance, diagnose issues, and generate professional service reports.

---

## Research Phase (REQUIRED FIRST)

Before writing any code or documentation, you MUST research and document the following by reading actual source files:

### 1. Hardware Architecture
Search the Opentrons repositories to find:
- What processor/computer runs the Flex? (NOT Raspberry Pi - that's OT-2)
- What motor controller is used? (CAN bus? Different from OT-2's Smoothieboard)
- How many axes? What are they called?
- What is the communication protocol? (G-code? Different?)
- What are the actual home positions for each axis?
- What are the steps per mm values?

**Search locations:**
- `ot3-firmware/` repository
- `opentrons/hardware/` directory
- `opentrons/api/src/opentrons/hardware_control/` - look for OT3-specific code
- Configuration files and constants

### 2. Module Specifications
For each module type (Temperature, Magnetic, Thermocycler, Heater-Shaker, Absorbance Reader):
- What MCU does it use?
- What is the communication interface?
- What are the actual temperature ranges and accuracy specs?
- What firmware commands does it accept?

**Search locations:**
- `opentrons-modules/` repository
- Module driver code in API
- Module firmware source

### 3. Calibration System
Research the actual calibration:
- Where are calibration files stored on Flex?
- What is the file format?
- What calibration types exist? (deck, pipette, gripper, modules?)
- How does the calibration matrix work?

**Search locations:**
- `api/src/opentrons/calibration_storage/ot3/`
- Robot configuration files

### 4. Acceptance Criteria
Find ACTUAL specifications - do not guess:
- What is the specified repeatability? (Find in docs or specs)
- What are module accuracy specifications? (Find in datasheets or code)
- What tolerances are used in the existing code?

**Search locations:**
- Test files often contain expected tolerances
- Hardware control code may have constants
- Official Opentrons documentation

---

## Deliverables to Create

After completing research, create:

### 1. Master Diagnostic Script
Python script that tests all Flex systems:

**Research required before writing:**
- How to initialize Flex hardware (different from OT-2)
- What API classes to use for Flex vs OT-2
- Actual axis names and positions
- How to communicate with Flex firmware

**Test sections:**
- System information (serial, versions, etc.)
- Motion system (research actual axes first)
- Pipettes (Flex uses different pipettes - 1, 8, 96 channel)
- Gripper (Flex-specific - OT-2 doesn't have this)
- Modules
- Calibration verification
- System health

**Important:** Use constants class for all margins, but populate with RESEARCHED values, not assumptions.

### 2. Service Report Generator
- HTML and Markdown output
- Professional formatting
- Must work with actual diagnostic output structure

### 3. Troubleshooting Guide
For each diagnostic test, document:
- Acceptance criteria (FROM RESEARCH)
- Failure symptoms
- Root causes
- Corrective actions
- Escalation criteria

**Research required:**
- Actual mechanical components in Flex
- How to access and service them
- What tools are needed
- Part numbers if available

### 4. Quick Reference Card
- All margins in table format (FROM RESEARCH)
- Common commands (FOR FLEX, not OT-2)
- Maintenance schedule

### 5. Command Reference
- Research actual Flex communication protocol
- Document real commands (may be different from G-code)
- Include module commands

---

## Key Differences to Research: Flex vs OT-2

The Flex is significantly different from OT-2. Research these differences:

| Aspect | OT-2 | Flex (RESEARCH) |
|--------|------|-----------------|
| Main computer | Raspberry Pi 3 | ? (Research) |
| Motor controller | Smoothieboard (UART) | ? (Likely CAN-based) |
| Communication | G-code over serial | ? (Research) |
| Axes | X, Y, Z, A, B, C | ? (Research) |
| Gripper | None | Has gripper (research details) |
| Pipettes | Gen1/Gen2 | Flex-specific pipettes |
| Deck slots | 11 slots | 12 slots (different layout) |
| Modules | Gen1/Gen2 | Gen3 modules |

---

## Research Commands

Use these to find information:

```bash
# Find Flex-specific hardware control
grep -r "OT3" --include="*.py" /path/to/opentrons/

# Find axis definitions
grep -r "class.*Axis" --include="*.py" /path/to/opentrons/

# Find home positions
grep -r "home_position" --include="*.py" /path/to/opentrons/

# Find calibration storage
ls -la api/src/opentrons/calibration_storage/ot3/

# Find CAN bus communication
grep -r "can_bus" --include="*.py" /path/to/opentrons/

# Find gripper code
grep -r "gripper" --include="*.py" /path/to/opentrons/hardware_control/
```

---

## Output Requirements

### Code Quality
- All Python scripts must be executable
- Use async/await patterns appropriate for Flex
- Handle hardware not present gracefully
- Generate JSON reports

### Documentation Quality
- All specifications must cite source (file path or URL)
- Mark unverified information clearly
- Include "Last Verified" date

### File Structure
```
scripts/maintenance/
├── flex_full_service_diagnostic.py
├── flex_service_report_generator.py
├── flex_pipette_test.py
├── flex_gripper_test.py          # Flex-specific
├── flex_module_test.py
├── flex_motion_test.py
├── flex_calibration_tool.py
├── FLEX_TROUBLESHOOTING_GUIDE.md
├── FLEX_DIAGNOSTIC_QUICK_REFERENCE.md
├── FLEX_SERVICE_REPORT_TEMPLATE.md
├── FLEX_COMMANDS_REFERENCE.md
└── SPECIFICATIONS_SOURCES.md     # Document where each spec came from
```

---

## Verification Checklist

Before finalizing, verify:

- [ ] All axis names are correct for Flex
- [ ] Home positions are from actual source code
- [ ] Communication protocol is correct (not assumed G-code)
- [ ] Module specs are from datasheets or code
- [ ] Calibration file paths are correct for Flex
- [ ] Gripper functionality is included
- [ ] 96-channel pipette support is included
- [ ] All margins cite their source

---

## Example of Proper Research Documentation

**GOOD:**
```python
# Flex X-axis home position
# Source: api/src/opentrons/hardware_control/ot3_api.py, line 423
# Verified: 2024-01-15
HOME_X = 477.2  # mm
```

**BAD:**
```python
# X-axis home position (assumed similar to OT-2)
HOME_X = 418.0  # mm  # WRONG - this is OT-2 value
```

---

## Summary

1. **RESEARCH FIRST** - Read actual source code
2. **VERIFY SPECIFICATIONS** - Don't assume from OT-2
3. **DOCUMENT SOURCES** - Cite where each value came from
4. **MARK UNCERTAINTIES** - If you can't verify, say so
5. **TEST ON ACTUAL HARDWARE** - If possible

The goal is accurate, verifiable documentation - not comprehensive guessing.
