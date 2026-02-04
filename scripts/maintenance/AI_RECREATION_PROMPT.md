# AI Prompt: Create OT-2 Robot Maintenance Service Toolkit

## Context

You are tasked with creating a comprehensive maintenance and service toolkit for the Opentrons OT-2 liquid handling robot. This toolkit will be used by field service technicians to perform annual maintenance, diagnose issues, and generate professional service reports for customers.

## Background Information

### OT-2 Robot Architecture
- **Main Computer**: Raspberry Pi 3 Model B running custom Linux
- **Motor Controller**: Modified Smoothieboard (LPC1769 MCU) running SmoothiewareOT firmware
- **Communication**: UART serial at 115200 baud using G-code protocol
- **Axes**: 6 axes total
  - X: Left/Right gantry (home: 418mm, 80 steps/mm)
  - Y: Front/Back gantry (home: 353mm, 80 steps/mm)
  - Z: Left pipette mount Z (home: 218mm, 400 steps/mm)
  - A: Right pipette mount Z (home: 218mm, 400 steps/mm)
  - B: Left plunger (home: ~19mm, 768 steps/mm)
  - C: Right plunger (home: ~19mm, 768 steps/mm)

### Attached Modules (USB Serial)
- **Temperature Module**: ATmega32u4, range 4-99°C, accuracy ±0.5°C
- **Magnetic Module**: ATmega32u4, engage/disengage magnet
- **Thermocycler**: SAMG55/STM32, lid + plate temperature control, 4-99°C
- **Heater-Shaker**: STM32, 200-3000 RPM, ambient to 95°C

### Key Software Components
- Python API: `/api/src/opentrons/`
- Smoothie Driver: `/api/src/opentrons/drivers/smoothie_drivers/driver_3_0.py`
- Hardware Control: `/api/src/opentrons/hardware_control/`
- Calibration Storage: `/api/src/opentrons/calibration_storage/`
- Robot Server: FastAPI on port 31950

### Calibration Data Locations
- Deck calibration: `/data/opentrons/robot/deck_calibration.json`
- Pipette offsets: `/data/opentrons/robot/pipettes/{left|right}/{pipette_id}.json`
- Tip lengths: `/data/opentrons/tip_lengths/{pipette_id}.json`

---

## Requirements

Create the following deliverables:

### 1. Master Diagnostic Script (`ot2_full_service_diagnostic.py`)

**Purpose**: Comprehensive Python script that tests ALL robot systems and generates JSON report.

**Test Sections Required**:

1. **System Information**
   - Hostname, serial number, software/firmware versions
   - Network info (IP, WiFi SSID)
   - Storage usage
   - Uptime

2. **Motion System Tests**
   - Limit switch verification (all 6 axes)
   - Homing accuracy (5 iterations, measure range/stdev)
   - Position repeatability (10 iterations, calculate 3D repeatability)
   - Cross-deck accuracy (test 5 deck positions)
   - Z-axis movement (both mounts, 100mm travel test)

3. **Pipette Tests** (both mounts)
   - Detection (read EEPROM: M369, M371)
   - Plunger movement (home, travel to bottom, measure distance)
   - Calibration status (check offset files exist and are valid)

4. **Module Tests** (all attached)
   - Temperature Module: read temp, test set/deactivate
   - Magnetic Module: test engage/disengage cycle
   - Thermocycler: test lid open/close, read temperatures
   - Heater-Shaker: test latch open/close, read temp

5. **Calibration Verification**
   - Deck calibration matrix validity (determinant, rank)
   - Pipette offset files
   - Tip length calibrations

6. **System Health**
   - Disk space usage
   - Error logs (last 24 hours)
   - Services status (robot-server, update-server)

**Technical Requirements**:
- Use async/await pattern with opentrons.hardware_control.API
- Generate JSON report with all test results
- Include pass/fail/warning status for each test
- Calculate test duration
- Generate recommendations based on failures
- Support --quick mode (fewer iterations) and --skip-modules flag

**Acceptance Criteria Constants** (define as class):
```python
class DiagnosticMargins:
    # Motion - based on OT-2 spec: ±0.1mm repeatability
    HOMING_RANGE_PASS = 0.1          # mm
    HOMING_RANGE_WARNING = 0.3       # mm
    REPEATABILITY_3D_PASS = 0.1      # mm
    REPEATABILITY_3D_WARNING = 0.25  # mm
    CROSS_DECK_ERROR_PASS = 0.5      # mm
    CROSS_DECK_ERROR_WARNING = 1.5   # mm

    # Pipettes
    PLUNGER_TRAVEL_MIN_PASS = 1.0    # mm
    PIPETTE_OFFSET_MAGNITUDE_PASS = 3.0  # mm

    # Temperature Module - from datasheet
    TEMP_MODULE_ACCURACY_PASS = 0.5  # °C
    TEMP_MODULE_AMBIENT_MIN = 5.0    # °C
    TEMP_MODULE_AMBIENT_MAX = 50.0   # °C

    # Thermocycler
    TC_LID_TIME_PASS = 5.0           # seconds
    TC_TEMP_ACCURACY_PASS = 0.5      # °C
    TC_RAMP_RATE_PASS = 2.0          # °C/s

    # Heater-Shaker
    HS_SPEED_ACCURACY_PASS = 1.0     # % error
    HS_TEMP_ACCURACY_PASS = 0.5      # °C

    # Calibration
    DECK_MATRIX_DET_MIN = 0.9
    DECK_MATRIX_DET_MAX = 1.1

    # System
    DISK_USAGE_PASS = 80             # %
    ERROR_LOG_COUNT_PASS = 0
    ERROR_LOG_COUNT_WARNING = 10
```

---

### 2. Service Report Generator (`ot2_service_report_generator.py`)

**Purpose**: Convert diagnostic JSON to professional customer-facing reports.

**Output Formats**:
- HTML (styled, printable, with status badges and colors)
- Markdown

**Report Sections**:
- Robot Information (serial, versions, service date)
- Executive Summary (overall status, test counts)
- Recommendations (prioritized: HIGH/MEDIUM/LOW)
- Detailed Test Results (by section)
- System Details

**Features**:
- Color-coded status badges (green=pass, red=fail, yellow=warning)
- Customer name branding option
- Print-friendly CSS
- Summary cards with metrics

---

### 3. Component-Specific Test Scripts

**a. Pipette Test Script** (`ot2_pipette_test.py`)
- Test specific mount (--mount left/right)
- Tests: info, plunger, tip pickup/drop, accuracy, unstick
- Accuracy test: measure plunger travel during aspirate/dispense

**b. Module Test Script** (`ot2_module_test.py`)
- Test all or specific module type (--type temperature/magnetic/thermocycler/heater-shaker)
- Functional tests for each module type

**c. Motion Test Script** (`ot2_motion_test.py`)
- Homing accuracy, position repeatability, cross-deck accuracy, speed tests
- Configurable iterations

**d. Calibration Tool** (`ot2_calibration_tool.py`)
- Actions: status, export, backup, verify, restore
- Validate calibration matrix (determinant, rank)
- Backup/restore calibration data as tar.gz

---

### 4. Troubleshooting Guide (`OT2_TROUBLESHOOTING_GUIDE.md`)

**Structure for EACH diagnostic test**:

1. **Acceptance Criteria** - Table with PASS/WARNING/FAIL thresholds
2. **Failure Symptoms** - What user observes
3. **Root Causes** - List ranked by likelihood (percentage)
4. **Corrective Actions** - Numbered steps with:
   - Tools/materials needed
   - Exact commands or procedures
   - Verification steps
5. **Escalation Criteria** - When to contact support

**Sections to cover**:
- Motion System (limit switches, homing, repeatability, Z-axis)
- Pipettes (detection, plunger, calibration)
- Modules (temp, mag, thermocycler, heater-shaker)
- Calibration (deck, pipette offset, tip length)
- System Health (disk, logs, services)

**Include physical repair procedures**:
- Belt tension adjustment (3-5mm deflection target)
- Pulley set screw tightening
- Rail cleaning and lubrication
- Leadscrew cleaning
- Contact cleaning (IPA + lint-free cloth)
- Switch replacement steps

---

### 5. Quick Reference Card (`OT2_DIAGNOSTIC_QUICK_REFERENCE.md`)

One-page reference with:
- All pass/fail margins in tables
- Expected home positions
- Module specifications
- Quick fixes cheat sheet (symptom → first action → second action)
- Common serial commands
- Escalation criteria
- Maintenance schedule

---

### 6. Service Report Template (`SERVICE_REPORT_TEMPLATE.md`)

Manual fill-in template with:
- Service information (customer, date, technician)
- Robot information
- Pre-service condition checklist
- All test result sections with checkboxes
- Service actions performed
- Parts replaced table
- Recommendations (High/Medium/Low priority)
- Post-service verification
- Customer sign-off section

---

### 7. Serial Commands Reference (`SERIAL_COMMANDS_REFERENCE.md`)

Complete G-code reference including:
- Connection setup (port, baud, terminator)
- Position commands (M114.2, M119, G28.6)
- Movement commands (G0, G28.2, G90/G91)
- Motor current (M907)
- Pipette EEPROM (M369, M370, M371, M372)
- Module commands (for each module type)
- Error recovery (M999)
- Troubleshooting sequences

---

## Output Format

All Python scripts should:
- Be standalone executable with `if __name__ == "__main__"`
- Use argparse for command-line options
- Generate JSON reports saved to `/data/` directory
- Print progress and summary to console
- Return appropriate exit codes (0=pass, 1=fail)
- Handle missing hardware gracefully (skip tests, don't crash)

All Markdown documents should:
- Use clear headers and tables
- Include practical, actionable information
- Reference specific file paths and commands
- Be printable as standalone documents

---

## Key Technical Details

### G-code Command Format
```
Command terminator: \r\n\r\n
ACK response: ok\r\nok\r\n
Timeout: 12000ms (commands), 30000ms (moves)
```

### Important Serial Commands
```
version              # Firmware version
M114.2               # Current position
M119                 # Limit switch status
G28.2 X Y Z A B C    # Home axes
G0 X100 Y200 F18000  # Move (F = mm/min)
M907 X1.25 Y1.25     # Set motor current
M369 L               # Read left pipette ID
M999                 # Reset from error
```

### Plunger Unstick Procedure
```
M907 B0.5 C0.5       # Increase current
G0 B18 F60           # Move slowly (1mm/s)
G28.2 B C            # Home
M907 B0.05 C0.05     # Reset current
```

### Calibration File Formats

**Deck Calibration** (3x3 attitude matrix):
```json
{
  "attitude": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
  "last_modified": "2024-01-15T10:30:00",
  "source": "user",
  "pipette_calibrated_with": "P20SV202020121511"
}
```

**Pipette Offset**:
```json
{
  "offset": [0.5, -0.3, 1.2],
  "last_modified": "2024-01-15T10:35:00",
  "source": "user"
}
```

---

## Success Criteria

The toolkit should enable a technician to:
1. Run comprehensive diagnostics in < 15 minutes (quick mode) or < 30 minutes (full)
2. Identify failing components with specific pass/fail criteria
3. Follow step-by-step repair procedures
4. Generate professional customer reports
5. Backup and verify calibration data
6. Troubleshoot common issues without external documentation

---

## File Structure

```
scripts/maintenance/
├── ot2_full_service_diagnostic.py      # Master diagnostic
├── ot2_service_report_generator.py     # Report generator
├── ot2_pipette_test.py                 # Pipette tests
├── ot2_module_test.py                  # Module tests
├── ot2_motion_test.py                  # Motion tests
├── ot2_calibration_tool.py             # Calibration management
├── OT2_TROUBLESHOOTING_GUIDE.md        # Repair guide
├── OT2_DIAGNOSTIC_QUICK_REFERENCE.md   # Quick reference
├── SERVICE_REPORT_TEMPLATE.md          # Manual template
└── SERIAL_COMMANDS_REFERENCE.md        # Command reference
```

---

## Notes

- All margin values are based on OT-2 specifications and industry standards for laboratory liquid handlers
- Temperature module accuracy ±0.5°C is from Opentrons datasheet
- Motion repeatability ±0.1mm is from OT-2 specification
- Repair procedures are based on standard electromechanical maintenance practices
- Scripts should work on OT-2 robots running Opentrons software version 6.x and later
