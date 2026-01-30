# OT-2 Diagnostic Troubleshooting & Repair Guide

## Overview

This guide provides specific corrective actions for each test in the OT-2 Full Service Diagnostic. Each section includes:
- **Acceptance Criteria**: Empirical pass/fail margins
- **Failure Symptoms**: What you'll observe when the test fails
- **Root Causes**: Common reasons for failure
- **Corrective Actions**: Step-by-step fixes ranked by likelihood
- **Escalation Criteria**: When to contact Opentrons support

---

## Table of Contents

1. [Motion System Tests](#1-motion-system-tests)
   - [1.1 Limit Switch Verification](#11-limit-switch-verification)
   - [1.2 Homing Accuracy](#12-homing-accuracy)
   - [1.3 Position Repeatability](#13-position-repeatability)
   - [1.4 Cross-Deck Accuracy](#14-cross-deck-accuracy)
   - [1.5 Z-Axis Movement](#15-z-axis-movement)
2. [Pipette Tests](#2-pipette-tests)
   - [2.1 Pipette Detection](#21-pipette-detection)
   - [2.2 Plunger Movement](#22-plunger-movement)
   - [2.3 Pipette Calibration](#23-pipette-calibration)
3. [Module Tests](#3-module-tests)
   - [3.1 Temperature Module](#31-temperature-module)
   - [3.2 Magnetic Module](#32-magnetic-module)
   - [3.3 Thermocycler](#33-thermocycler)
   - [3.4 Heater-Shaker](#34-heater-shaker)
4. [Calibration Tests](#4-calibration-tests)
   - [4.1 Deck Calibration](#41-deck-calibration)
   - [4.2 Pipette Offset Calibration](#42-pipette-offset-calibration)
   - [4.3 Tip Length Calibration](#43-tip-length-calibration)
5. [System Health](#5-system-health)
   - [5.1 Disk Space](#51-disk-space)
   - [5.2 Error Logs](#52-error-logs)
   - [5.3 Services Status](#53-services-status)

---

## 1. Motion System Tests

### 1.1 Limit Switch Verification

#### Acceptance Criteria

| Condition | Status |
|-----------|--------|
| All gantry switches (X, Y, Z, A) triggered at home position | **PASS** |
| One or more switches not triggered at home | **FAIL** |
| Plunger switches (B, C) not triggered (pipette-dependent) | **WARNING** |

#### Failure Symptoms
- Robot fails to home with "Homing failed" error
- Axis moves continuously without stopping
- Robot reports incorrect position after homing
- Grinding or clicking sounds during homing

#### Root Causes (by likelihood)

1. **Switch not physically triggered** (40%)
   - Mechanical misalignment
   - Debris blocking switch actuator
   - Loose switch mounting

2. **Electrical connection issue** (30%)
   - Loose cable connection
   - Damaged switch cable
   - Corroded connector pins

3. **Damaged switch** (20%)
   - Switch actuator broken
   - Internal switch failure
   - Water/liquid damage

4. **Smoothieboard issue** (10%)
   - Firmware corruption
   - Board-level failure

#### Corrective Actions

**Step 1: Visual Inspection (5 min)**
```
1. Power off robot
2. Manually move gantry to home position
3. Verify switch actuator physically contacts switch
4. Check for debris, dust, or liquid residue
5. Ensure switch is firmly mounted
```

**Step 2: Clean Switch Area (10 min)**
```
Materials: Isopropyl alcohol (70%+), lint-free wipes, compressed air

1. Power off robot, unplug
2. Use compressed air to blow debris from switch area
3. Clean switch and actuator with IPA-dampened wipe
4. Allow to dry completely (2-3 minutes)
5. Reconnect and test
```

**Step 3: Check Electrical Connections (15 min)**
```
1. Power off robot
2. Locate switch cable at Smoothieboard
3. Disconnect and inspect connector pins for:
   - Corrosion (green/white deposits)
   - Bent pins
   - Loose crimps
4. Reconnect firmly, ensure click
5. Trace cable to switch, check for damage
6. Test switch with multimeter (continuity when pressed)
```

**Step 4: Replace Switch (30 min)**
```
Tools: Phillips screwdriver, replacement switch

1. Power off and unplug robot
2. Disconnect switch cable
3. Remove mounting screws (typically 2x M2 or M2.5)
4. Install new switch, ensure proper alignment
5. Route cable avoiding pinch points
6. Reconnect and test
```

**Switch Test via Serial Terminal:**
```
# Connect to Smoothie
screen /dev/ttyAMA0 115200

# Query switch states
M119

# Expected at home: X_min:1 Y_max:1 Z_max:1 A_max:1

# Manual test: press each switch and run M119 again
# Switch should toggle between 0 and 1
```

#### Escalation Criteria
- Multiple switches failing simultaneously
- Switch tests pass but homing still fails
- Visible damage to Smoothieboard
- Switch replacement does not resolve issue

---

### 1.2 Homing Accuracy

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Position range (5 iterations) | < 0.1 mm | 0.1 - 0.3 mm | > 0.3 mm |
| Standard deviation | < 0.03 mm | 0.03 - 0.08 mm | > 0.08 mm |
| Error from expected home | < 1.0 mm | 1.0 - 2.0 mm | > 2.0 mm |

**Expected Home Positions (OT-2):**
| Axis | Expected Position | Tolerance |
|------|-------------------|-----------|
| X | 418.0 mm | ± 0.5 mm |
| Y | 353.0 mm | ± 0.5 mm |
| Z | 218.0 mm | ± 0.5 mm |
| A | 218.0 mm | ± 0.5 mm |

#### Failure Symptoms
- Inconsistent well targeting
- Pipette crashes into labware
- Tips not centered in wells
- Calibration drifts over time

#### Root Causes

1. **Belt tension issues** (35%)
   - Belt too loose: slipping during motion
   - Belt too tight: excessive motor load, premature wear

2. **Mechanical wear** (25%)
   - Worn belt teeth
   - Worn pulley bearings
   - Loose pulley set screws

3. **Motor issues** (20%)
   - Skipping steps (current too low)
   - Motor overheating
   - Encoder drift (if equipped)

4. **Limit switch inconsistency** (15%)
   - Switch hysteresis
   - Intermittent contact

5. **Firmware/configuration** (5%)
   - Incorrect steps/mm
   - Incorrect homing speed

#### Corrective Actions

**Step 1: Check Belt Tension (10 min)**
```
Proper Belt Tension Test:
1. Power off robot
2. Press down on belt at midpoint between pulleys
3. Belt should deflect 3-5mm with moderate finger pressure
4. If too loose: tighten tensioner
5. If too tight: loosen slightly

X-Axis Belt Location: Under gantry, runs left-right
Y-Axis Belt Location: Under deck, runs front-back
Z-Axis Belt Location: On pipette mount carriage
```

**Step 2: Adjust Belt Tension (20 min)**
```
Tools: 2.5mm hex key, tension gauge (optional)

X/Y Belt Adjustment:
1. Locate belt tensioner (spring-loaded pulley)
2. Loosen tensioner mounting screw
3. Adjust position to achieve proper tension
4. Tighten mounting screw
5. Verify tension at multiple points along belt

Target tension: 2-4 lbs/inch deflection
```

**Step 3: Check Pulley Set Screws (15 min)**
```
Tools: 1.5mm or 2mm hex key

1. Locate motor pulleys (X, Y, Z, A motors)
2. Check set screws are tight
3. Verify pulley is aligned with belt
4. If loose:
   - Align pulley flat with motor shaft flat
   - Tighten set screw firmly (but don't strip)
5. Check idler pulleys spin freely
```

**Step 4: Inspect Belt Condition (10 min)**
```
Signs of belt wear:
- Missing or worn teeth
- Fraying edges
- Cracks in belt material
- Shiny/glazed appearance
- Stretched (loose even when tensioned)

If worn: Replace belt (see part numbers below)
```

**Step 5: Adjust Motor Current (Software)**
```python
# If motors are skipping steps, increase current slightly
# Via serial terminal:

# Check current settings
M503

# Increase X/Y current (default 1.25A, max 1.5A)
M907 X1.4 Y1.4

# Test homing
G28.2 X Y

# If successful, save settings
M500
```

**Step 6: Verify Steps/mm Configuration**
```
# Query current steps/mm
M92

# Expected values:
# X: 80 steps/mm
# Y: 80 steps/mm
# Z: 400 steps/mm
# A: 400 steps/mm

# If incorrect, reset to defaults:
M92 X80 Y80 Z400 A400
M500
```

#### Part Numbers
| Part | Opentrons P/N | Description |
|------|---------------|-------------|
| X Belt | OT2-BELT-X | GT2 timing belt, X axis |
| Y Belt | OT2-BELT-Y | GT2 timing belt, Y axis |
| Z Belt | OT2-BELT-Z | GT2 timing belt, Z axis |

---

### 1.3 Position Repeatability

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| 3D Repeatability (10 iterations) | < 0.1 mm | 0.1 - 0.25 mm | > 0.25 mm |
| Individual axis range | < 0.05 mm | 0.05 - 0.15 mm | > 0.15 mm |
| Standard deviation (per axis) | < 0.02 mm | 0.02 - 0.05 mm | > 0.05 mm |

**Industry Standard Reference:**
- Laboratory liquid handlers: typically 0.1 - 0.5 mm repeatability
- OT-2 specification: ± 0.1 mm (100 µm) repeatability

#### Failure Symptoms
- Inconsistent pipetting positions
- Tips missing wells on repeat visits
- Variable aspiration/dispense volumes
- Protocol failures on long runs

#### Root Causes

1. **Mechanical backlash** (30%)
   - Loose belt mesh with pulley
   - Worn linear bearings
   - Play in carriage assembly

2. **Thermal effects** (25%)
   - Metal expansion during operation
   - Motor heating causing drift
   - Ambient temperature changes

3. **Belt issues** (20%)
   - Inconsistent tension
   - Belt stretch under load
   - Pulley eccentricity

4. **Vibration/resonance** (15%)
   - Unstable mounting surface
   - Resonance at certain speeds
   - Loose fasteners

5. **Electrical noise** (10%)
   - Stepper driver issues
   - EMI interference

#### Corrective Actions

**Step 1: Check Linear Bearings (15 min)**
```
1. Power off robot
2. Manually move gantry along each axis
3. Feel for:
   - Rough spots or grinding
   - Excessive play (wiggle perpendicular to motion)
   - Sticking or binding
4. If rough: Clean and lubricate rails
5. If excessive play: Replace bearings
```

**Step 2: Clean and Lubricate Rails (20 min)**
```
Materials:
- Isopropyl alcohol
- Lint-free cloth
- Light machine oil (sewing machine oil) or PTFE lubricant

Procedure:
1. Power off, move gantry to access all rail areas
2. Wipe rails with IPA-dampened cloth to remove debris
3. Apply thin film of lubricant to rails
4. Move gantry back and forth to distribute
5. Wipe excess lubricant
6. Repeat for all axes

DO NOT use: WD-40, grease, or thick oils
```

**Step 3: Check for Loose Fasteners (15 min)**
```
Tools: Appropriate hex keys (2mm, 2.5mm, 3mm)

Critical fasteners to check:
- Motor mount screws
- Pulley set screws
- Carriage mounting screws
- Rail mounting screws
- Belt tensioner screws

Tighten any loose fasteners, but don't over-torque
```

**Step 4: Verify Stable Mounting (5 min)**
```
1. Check robot is on stable, level surface
2. Verify all four feet are in contact with surface
3. Check for vibration sources nearby
4. Consider anti-vibration mat if on shared bench
```

**Step 5: Backlash Compensation (Software)**
```python
# Check current backlash settings
# Via API or config files

# Backlash compensation is configured in robot config
# Location: /data/robot_settings.json

# Typical backlash values:
# X: 0.0 - 0.1 mm
# Y: 0.0 - 0.1 mm
# Z: 0.0 mm (usually not needed)

# Note: Backlash compensation is a workaround
# Root cause should still be addressed
```

**Step 6: Thermal Stabilization**
```
For best repeatability:
1. Power on robot 15-30 minutes before critical work
2. Run a few homing cycles to warm up motors
3. Maintain consistent ambient temperature (18-25°C)
4. Avoid direct sunlight or HVAC drafts on robot
```

---

### 1.4 Cross-Deck Accuracy

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Maximum 3D position error | < 0.5 mm | 0.5 - 1.5 mm | > 1.5 mm |
| Mean position error | < 0.3 mm | 0.3 - 1.0 mm | > 1.0 mm |
| Error consistency (all positions similar) | Yes | Varied | One position very bad |

**Deck Position Reference:**
| Slot | X (mm) | Y (mm) |
|------|--------|--------|
| 1 | 14.38 | 11.24 |
| 2 | 132.38 | 11.24 |
| 3 | 250.38 | 11.24 |
| 4 | 14.38 | 90.24 |
| 5 | 132.38 | 90.24 |
| 6 | 250.38 | 90.24 |
| 7 | 14.38 | 169.24 |
| 8 | 132.38 | 169.24 |
| 9 | 250.38 | 169.24 |
| 10 | 14.38 | 248.24 |
| 11 | 132.38 | 248.24 |

#### Failure Symptoms
- Good accuracy in some areas, poor in others
- Systematic offset (always off in same direction)
- Pipette misses wells at deck edges
- Calibration works in center but fails at corners

#### Root Causes

1. **Deck calibration needed** (40%)
   - Never calibrated
   - Calibration outdated
   - Calibration performed incorrectly

2. **Mechanical squareness** (25%)
   - Gantry not perpendicular to Y axis
   - Deck not level
   - Frame distortion

3. **Belt length mismatch** (15%)
   - Different tension on parallel belts
   - Different stretch characteristics

4. **Thermal gradients** (10%)
   - Uneven heating across deck
   - Module heat affecting nearby positions

5. **Steps/mm calibration** (10%)
   - Incorrect steps per mm value
   - Accumulated error over distance

#### Corrective Actions

**Step 1: Perform Deck Calibration (15 min)**
```
Via Opentrons App:
1. Open Opentrons App
2. Navigate to Robot Settings > Calibration
3. Select "Calibrate Deck"
4. Follow on-screen instructions:
   - Attach calibration probe to pipette
   - Touch three deck positions
   - Confirm each point
5. Save calibration

This corrects for systematic offsets and rotation
```

**Step 2: Verify Deck Calibration Matrix**
```python
# Check calibration file
cat /data/opentrons/robot/deck_calibration.json

# Validate attitude matrix:
# - Should NOT be identity matrix [[1,0,0],[0,1,0],[0,0,1]]
# - Determinant should be close to 1.0 (0.95 - 1.05)
# - Off-diagonal elements typically small (< 0.01)

# Example of good calibration:
{
  "attitude": [
    [1.0002, 0.0015, -0.0003],
    [-0.0012, 0.9998, 0.0008],
    [0.0001, -0.0005, 1.0001]
  ]
}
```

**Step 3: Check Gantry Squareness (30 min)**
```
Tools: Square (machinist's or framing), ruler

Procedure:
1. Home robot
2. Move gantry to Y=150 (center)
3. Measure distance from gantry bar to front frame at both ends
4. Difference should be < 1mm
5. If not square:
   - Check Y belt tensions are equal
   - Check frame for damage/distortion
   - May require realignment (contact Opentrons)
```

**Step 4: Verify Steps/mm Over Full Travel**
```
# Move known distance and measure physically
G28.2 X        # Home X
G0 X100 F6000  # Move to X=100
# Measure actual X position with ruler/caliper

G0 X300 F6000  # Move to X=300
# Measure again

# Calculate actual steps/mm if error is systematic:
# new_steps = old_steps * (commanded_distance / actual_distance)
```

**Step 5: Level the Deck (10 min)**
```
Tools: Bubble level, adjustment shims

1. Place level on deck surface (slot 5 area)
2. Check level in X and Y directions
3. If not level:
   - Adjust robot feet
   - Or shim under low side
4. Verify level at multiple deck positions
```

---

### 1.5 Z-Axis Movement

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Z travel accuracy (100mm move) | < 1.0 mm error | 1.0 - 2.0 mm | > 2.0 mm |
| Both Z axes similar | < 0.5 mm difference | 0.5 - 1.0 mm | > 1.0 mm |
| Smooth motion | Yes | Minor roughness | Grinding/sticking |

**Z-Axis Specifications:**
| Parameter | Value |
|-----------|-------|
| Total travel | ~200 mm |
| Home position | 218.0 mm |
| Steps per mm | 400 |
| Max speed | 125 mm/s |
| Leadscrew pitch | 2 mm |

#### Failure Symptoms
- Pipette crashes into deck or labware
- Z position varies between left and right
- Grinding sound during Z movement
- Inconsistent tip pickup height
- Plunge depth errors

#### Root Causes

1. **Leadscrew issues** (35%)
   - Debris in leadscrew threads
   - Worn leadscrew nut
   - Bent leadscrew

2. **Z limit switch** (25%)
   - Misaligned switch
   - Faulty switch
   - Debris blocking actuator

3. **Z belt/coupling** (20%)
   - Loose coupling between motor and leadscrew
   - Belt slip (belt-driven Z systems)

4. **Motor issues** (15%)
   - Insufficient current
   - Overheating motor
   - Faulty driver

5. **Mechanical binding** (5%)
   - Misaligned Z carriage
   - Damaged linear bearings

#### Corrective Actions

**Step 1: Clean Leadscrew (20 min)**
```
Materials: Stiff brush, IPA, light machine oil

1. Power off robot
2. Move Z to bottom position manually
3. Use brush to remove debris from leadscrew threads
4. Wipe with IPA-dampened cloth
5. Apply thin coat of light oil to threads
6. Move Z up and down to distribute
7. Wipe excess oil
```

**Step 2: Check Z Coupling (15 min)**
```
Tools: 2mm or 2.5mm hex key

1. Locate motor-to-leadscrew coupling
2. Check set screws are tight
3. Verify coupling is not cracked
4. Ensure motor shaft and leadscrew are aligned
5. Tighten set screws if loose
```

**Step 3: Adjust Z Limit Switch (15 min)**
```
1. Home Z axis
2. Check switch is triggered (M119)
3. If not triggered:
   - Adjust switch position
   - Check actuator alignment
   - Clean switch area
4. Switch should trigger 1-2mm before hard stop
```

**Step 4: Check Z Motor Current**
```
# Query current motor currents
M907

# Z axis typically runs at 0.5A
# If skipping steps, increase slightly:
M907 Z0.6 A0.6

# Test movement
G28.2 Z A
G0 Z100 A100 F3000
G0 Z200 A200 F3000

# If working, save:
M500
```

**Step 5: Inspect Leadscrew Nut (20 min)**
```
Signs of worn leadscrew nut:
- Visible play when pushing Z carriage
- Backlash in Z movement
- Noisy operation

If worn:
- Replace leadscrew nut (anti-backlash nut)
- May require partial disassembly
```

---

## 2. Pipette Tests

### 2.1 Pipette Detection

#### Acceptance Criteria

| Condition | Status |
|-----------|--------|
| Pipette detected with correct model/serial | **PASS** |
| No pipette on mount (and none expected) | **PASS** |
| Pipette attached but not detected | **FAIL** |
| Wrong model detected | **FAIL** |
| EEPROM read errors | **FAIL** |

#### Failure Symptoms
- "No pipette attached" error when pipette is attached
- Wrong pipette model shown in app
- Pipette intermittently detected/lost
- EEPROM read errors in logs

#### Root Causes

1. **Connection issues** (45%)
   - Pipette not fully seated
   - Dirty contacts
   - Damaged connector pins

2. **EEPROM corruption** (25%)
   - Data corruption
   - Failed write operation
   - EEPROM chip failure

3. **Cable/wiring issues** (20%)
   - Damaged pipette cable
   - Loose internal connections
   - Broken wires

4. **Pipette hardware failure** (10%)
   - Board-level failure
   - Component failure

#### Corrective Actions

**Step 1: Reseat Pipette (2 min)**
```
1. Power off robot
2. Remove pipette by pressing release button
3. Inspect connector on pipette and mount:
   - Look for bent pins
   - Check for debris
   - Look for corrosion
4. Reattach pipette firmly until click
5. Power on and test
```

**Step 2: Clean Contacts (10 min)**
```
Materials: IPA, cotton swab, lint-free cloth

1. Power off robot
2. Remove pipette
3. Clean mount connector with IPA-dampened swab
4. Clean pipette connector similarly
5. Allow to dry completely
6. Reconnect and test
```

**Step 3: Read Pipette EEPROM via Serial**
```
# Connect to Smoothie
screen /dev/ttyAMA0 115200

# Read left pipette ID
M369 L

# Read right pipette ID
M369 R

# Read left pipette model
M371 L

# Read right pipette model
M371 R

# If returns "no pipette" or garbage:
# - Connection issue
# - EEPROM failure
```

**Step 4: Rewrite EEPROM (if corrupt)**
```
# WARNING: Only if you know the correct serial/model

# Write pipette serial (left mount example)
M370 L P20SV202020121511

# Write pipette model
M372 L p20_single_v2.0

# Verify
M369 L
M371 L
```

**Step 5: Check Pipette Cable (20 min)**
```
1. Power off robot
2. Access pipette mount internals (may require covers off)
3. Trace cable from mount connector to board
4. Look for:
   - Pinched cable
   - Frayed insulation
   - Loose connections
5. Reseat all connectors
6. Flex cable gently while testing continuity
```

---

### 2.2 Plunger Movement

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Plunger travel | > 1.0 mm | 0.5 - 1.0 mm | < 0.5 mm |
| Smooth motion | Yes | Minor resistance | Sticking/grinding |
| Returns to home | Consistently | Occasionally fails | Fails frequently |

**Plunger Position Reference (typical):**
| Pipette | Top | Bottom | Blowout | Drop Tip |
|---------|-----|--------|---------|----------|
| P20 Single | 19.0 | 2.0 | 0.0 | -3.5 |
| P300 Single | 19.0 | 2.0 | 0.0 | -3.5 |
| P1000 Single | 19.0 | 2.0 | 0.0 | -3.5 |
| P20 Multi | 19.0 | 2.0 | 0.0 | -5.5 |
| P300 Multi | 19.0 | 2.0 | 0.0 | -5.5 |

#### Failure Symptoms
- Plunger sticks at certain positions
- Inconsistent aspiration volumes
- Motor skipping/clicking sounds
- Plunger won't home
- Very slow plunger movement

#### Root Causes

1. **Static friction buildup** (35%)
   - Lack of use
   - Cold environment
   - Old lubrication

2. **O-ring issues** (25%)
   - Worn O-rings
   - Dry O-rings
   - Damaged O-rings

3. **Motor/current issues** (20%)
   - Insufficient motor current
   - Motor overheating
   - Driver issues

4. **Mechanical obstruction** (15%)
   - Debris in plunger shaft
   - Bent plunger shaft
   - Damaged internal components

5. **Leadscrew/nut wear** (5%)
   - Worn threads
   - Worn nut

#### Corrective Actions

**Step 1: Unstick Plunger (5 min)**
```python
# Run unstick procedure via serial or API
# Serial method:

# Increase plunger current temporarily
M907 B0.5 C0.5

# Move plunger slowly
G0 B18 F60   # 1mm/s
G0 B10 F60
G0 B18 F60

# Home plunger
G28.2 B C

# Reset to normal current
M907 B0.05 C0.05
```

**Step 2: Lubricate O-rings (15 min)**
```
Materials: Silicone lubricant (food-grade recommended)

1. Remove pipette from robot
2. Eject tip if attached
3. Apply small amount of silicone lubricant to tip end
4. Work plunger up and down manually
5. Wipe excess lubricant
6. Reattach and test

DO NOT use: Petroleum-based lubricants
```

**Step 3: Inspect Plunger Mechanism (20 min)**
```
1. Remove pipette
2. Look into tip end with flashlight
3. Work plunger manually, observe:
   - Smooth movement
   - No debris
   - O-ring condition (visible on single-channel)
4. If debris visible:
   - Carefully clean with appropriate tool
5. If O-ring damaged:
   - Replace pipette or send for service
```

**Step 4: Adjust Plunger Motor Current (Software)**
```
# If plunger still sticking with normal current:

# Check current setting
M907

# Increase plunger current slightly
# Default is 0.05A, can increase to 0.1A for testing
M907 B0.08 C0.08

# Test movement
G28.2 B C
G0 B10 F600
G0 B18 F600

# If works, may leave slightly elevated
# but investigate root cause
```

**Step 5: Exercise Plunger (Preventive)**
```python
# Regular plunger exercise prevents sticking
# Run this weekly on idle robots:

async def exercise_plungers():
    # Home
    await api.home_plunger(Mount.LEFT)
    await api.home_plunger(Mount.RIGHT)

    # Cycle 10 times
    for i in range(10):
        await api.prepare_for_aspirate(Mount.LEFT)
        await api.home_plunger(Mount.LEFT)
        await api.prepare_for_aspirate(Mount.RIGHT)
        await api.home_plunger(Mount.RIGHT)
```

---

### 2.3 Pipette Calibration

#### Acceptance Criteria

| Condition | Status |
|-----------|--------|
| Calibration file exists with valid offset | **PASS** |
| Calibration exists but very old (>6 months) | **WARNING** |
| Offset magnitude > 5mm | **WARNING** |
| No calibration file | **WARNING** |
| Calibration file corrupt | **FAIL** |

**Typical Offset Ranges:**
| Axis | Normal Range | Suspicious | Requires Investigation |
|------|--------------|------------|----------------------|
| X | ± 2.0 mm | ± 2.0 - 5.0 mm | > ± 5.0 mm |
| Y | ± 2.0 mm | ± 2.0 - 5.0 mm | > ± 5.0 mm |
| Z | ± 2.0 mm | ± 2.0 - 5.0 mm | > ± 5.0 mm |

#### Corrective Actions

**Step 1: Perform Pipette Offset Calibration**
```
Via Opentrons App:
1. Ensure deck is calibrated first
2. Navigate to Robot Settings > Calibration
3. Select "Calibrate Pipette Offset"
4. Follow on-screen instructions:
   - Pick up tip
   - Touch calibration point
   - Confirm position
5. Save calibration
```

**Step 2: Verify Calibration File**
```bash
# Check calibration file
cat /data/opentrons/robot/pipettes/left/P20SV*.json

# Validate:
# - offset values are reasonable (< 5mm each axis)
# - last_modified is recent
# - source is "user" (not "default")
```

**Step 3: Reset and Recalibrate**
```bash
# If calibration seems wrong, delete and redo:
rm /data/opentrons/robot/pipettes/left/*.json
rm /data/opentrons/robot/pipettes/right/*.json

# Then recalibrate via app
```

---

## 3. Module Tests

### 3.1 Temperature Module

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Temperature reading | 5 - 50°C (ambient) | Outside range but responding | No reading / NaN |
| Set temperature response | Target set correctly | Slow response | No response |
| Heating to 37°C | Reaches within 5 min | 5-10 min | > 10 min or fails |
| Cooling to 4°C | Reaches within 10 min | 10-15 min | > 15 min or fails |
| Temperature accuracy | ± 0.5°C | ± 0.5 - 1.0°C | > ± 1.0°C |

**Temperature Module Specifications:**
| Parameter | Gen1 | Gen2 |
|-----------|------|------|
| Range | 4 - 96°C | 4 - 99°C |
| Accuracy | ± 0.5°C | ± 0.5°C |
| Uniformity | ± 0.5°C | ± 0.5°C |
| Heating rate | ~2°C/min | ~2.5°C/min |
| Cooling rate | ~1.5°C/min | ~2°C/min |

#### Failure Symptoms
- "Temperature reading unavailable" error
- Temperature doesn't change when set
- Very slow heating/cooling
- Temperature oscillates (hunting)
- Module not detected

#### Root Causes

1. **Connection issues** (30%)
   - Loose USB connection
   - Damaged cable
   - Power supply issues

2. **Thermistor/sensor failure** (25%)
   - Damaged temperature sensor
   - Sensor disconnected
   - Sensor out of calibration

3. **Peltier/heater failure** (20%)
   - Failed Peltier element
   - Failed heater element
   - Failed thermal fuse

4. **Firmware issues** (15%)
   - Outdated firmware
   - Corrupted firmware
   - Communication errors

5. **Thermal issues** (10%)
   - Poor thermal contact
   - Blocked heat sink
   - Fan failure

#### Corrective Actions

**Step 1: Check Connections (5 min)**
```
1. Power off robot
2. Disconnect and reconnect USB cable firmly
3. Check power supply connection
4. Verify module is recognized:
   ls /dev/ot_module_tempdeck*
```

**Step 2: Update Firmware (10 min)**
```
Via Opentrons App:
1. Go to Robot Settings > Attached Modules
2. Check firmware version
3. If update available, click "Update"
4. Wait for update to complete
5. Retest module
```

**Step 3: Clean Heat Sink and Fan (15 min)**
```
Materials: Compressed air, soft brush

1. Power off and unplug module
2. Locate heat sink (usually underneath)
3. Clear dust/debris from heat sink fins
4. Check fan spins freely
5. Clear any blockage around fan
6. Reconnect and test
```

**Step 4: Verify Temperature Sensor (Serial)**
```
# Connect to module
screen /dev/ot_module_tempdeck0 115200

# Query temperature
M105

# Expected response: T:25.0 C:0.0
# T = current temp, C = target temp

# If T is NaN or unreasonable:
# Sensor likely failed - replace module
```

**Step 5: Test Heating/Cooling Cycle**
```
# Set temperature
M104 S37.0

# Monitor temperature (run repeatedly)
M105

# Should reach 37°C within 5 minutes
# If not reaching or very slow:
# - Check Peltier/heater
# - Check thermal paste
# - May need module replacement
```

---

### 3.2 Magnetic Module

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Engage command | Status shows "engaged" | Delayed response | No response |
| Disengage command | Status shows "disengaged" | Delayed response | No response |
| Magnet movement | Audible click, smooth | Weak movement | No movement |
| Position accuracy | ± 0.5 mm | ± 0.5 - 1.0 mm | > 1.0 mm |

**Magnetic Module Specifications:**
| Parameter | Gen1 | Gen2 |
|-----------|------|------|
| Engage height range | 0 - 18 mm | 0 - 16 mm |
| Engage time | < 1 s | < 1 s |
| Magnetic strength | Sufficient for beads | Optimized for beads |

#### Failure Symptoms
- No click sound when engaging
- Beads don't pellet properly
- Engage command times out
- Motor buzzing but no movement
- Module not detected

#### Root Causes

1. **Motor issues** (35%)
   - Motor failure
   - Driver failure
   - Wiring issue

2. **Mechanical jam** (30%)
   - Debris blocking movement
   - Magnet assembly stuck
   - Broken leadscrew/nut

3. **Connection issues** (20%)
   - USB connection
   - Power supply
   - Internal connections

4. **Firmware** (15%)
   - Outdated firmware
   - Communication errors

#### Corrective Actions

**Step 1: Check Connections (5 min)**
```
1. Reconnect USB cable
2. Check power connection
3. Verify detection:
   ls /dev/ot_module_magdeck*
```

**Step 2: Manual Movement Check (10 min)**
```
1. Power off module
2. Locate magnet assembly (visible through deck plate slots)
3. Try to move magnet manually (should have some resistance)
4. Check for visible obstructions
5. If jammed, clear debris
```

**Step 3: Test via Serial (10 min)**
```
screen /dev/ot_module_magdeck0 115200

# Home magnet
G28.2

# Engage to specific height
G0 Z10.0

# Query position
M114.2

# Disengage
G0 Z0

# If no response or errors:
# Motor or driver failure - replace module
```

**Step 4: Firmware Update**
```
Via Opentrons App:
1. Check for firmware updates
2. Apply if available
3. Retest
```

---

### 3.3 Thermocycler

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Lid open/close | < 5 seconds | 5-10 seconds | > 10 seconds or fails |
| Lid temperature | Reaches 105°C in < 5 min | 5-10 min | > 10 min |
| Plate temperature | Reaches 95°C in < 2 min | 2-5 min | > 5 min |
| Temperature accuracy | ± 0.5°C | ± 0.5 - 1.0°C | > ± 1.0°C |
| Ramp rate | > 2°C/s heating | 1-2°C/s | < 1°C/s |

**Thermocycler Specifications:**
| Parameter | Gen1 | Gen2 |
|-----------|------|------|
| Temperature range | 4 - 99°C | 4 - 99°C |
| Lid temperature | Up to 110°C | Up to 110°C |
| Ramp rate (heating) | 3°C/s | 4°C/s |
| Ramp rate (cooling) | 2°C/s | 3°C/s |
| Accuracy | ± 0.5°C | ± 0.3°C |
| Uniformity | ± 0.5°C | ± 0.3°C |

#### Failure Symptoms
- Lid won't open/close
- Grinding sound during lid movement
- Temperature won't reach target
- Very slow ramp rates
- "Thermocycler lid error"
- Plate temperature uneven

#### Root Causes

1. **Lid mechanism** (30%)
   - Motor failure
   - Limit switch issue
   - Mechanical obstruction
   - Gear/belt wear

2. **Heating elements** (25%)
   - Peltier failure
   - Heater element failure
   - Thermal fuse triggered

3. **Temperature sensors** (20%)
   - Sensor failure
   - Poor thermal contact
   - Sensor drift

4. **Connection/power** (15%)
   - Insufficient power
   - USB communication
   - Internal connections

5. **Firmware** (10%)
   - Outdated firmware
   - Error state requiring reset

#### Corrective Actions

**Step 1: Reset Module (5 min)**
```
1. Power cycle the module
2. Check for error states
3. Attempt open/close cycle

# Via serial:
screen /dev/ot_module_thermocycler0 115200

M126  # Open lid
M127  # Close lid
```

**Step 2: Check Lid Mechanism (15 min)**
```
1. Open lid fully
2. Visually inspect:
   - Lid hinge condition
   - Motor/gear area for debris
   - Limit switches
3. Gently test lid movement manually (power off)
4. Clear any obstructions
```

**Step 3: Test Temperature Control**
```
# Set lid temperature
M140 S105

# Set plate temperature
M104 S95

# Monitor (run repeatedly)
M105

# Expected: L:105.0 P:95.0 (or similar)
# Note time to reach temperature
```

**Step 4: Check Thermal Performance**
```
If temperatures are slow or uneven:
1. Check heat sink for dust (external)
2. Check fans are running
3. Verify good thermal contact with plate
4. Check for plate warping

If thermal fuse tripped:
- Module needs service/replacement
```

**Step 5: Firmware Update**
```
Via Opentrons App - always update to latest
```

---

### 3.4 Heater-Shaker

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Labware latch open/close | < 2 seconds | 2-5 seconds | > 5 seconds or fails |
| Temperature heating | Reaches 37°C in < 3 min | 3-5 min | > 5 min |
| Temperature accuracy | ± 0.5°C | ± 0.5 - 1.0°C | > ± 1.0°C |
| Shake start/stop | Immediate response | Delayed | Fails |
| Speed accuracy | ± 5% | ± 5-10% | > ± 10% |
| Vibration/noise | Normal operation | Unusual sounds | Excessive vibration |

**Heater-Shaker Specifications:**
| Parameter | Value |
|-----------|-------|
| Temperature range | Ambient to 95°C |
| Shake speed range | 200 - 3000 RPM |
| Temperature accuracy | ± 0.5°C |
| Speed accuracy | ± 1% |
| Max acceleration | 1500 RPM/s |

#### Failure Symptoms
- Latch won't open/close
- Excessive vibration during shaking
- Speed won't reach target
- Temperature errors
- Unusual grinding or clicking sounds
- Module stops unexpectedly

#### Root Causes

1. **Latch mechanism** (25%)
   - Motor failure
   - Mechanical jam
   - Sensor failure

2. **Shake motor/bearing** (25%)
   - Bearing wear
   - Motor failure
   - Imbalance

3. **Heating system** (20%)
   - Heater failure
   - Sensor failure
   - Thermal fuse

4. **Connection/power** (15%)
   - Power supply issues
   - USB communication
   - Internal connections

5. **Imbalanced load** (15%)
   - Plate not seated properly
   - Uneven liquid distribution

#### Corrective Actions

**Step 1: Check Labware Seating (2 min)**
```
1. Ensure no labware is on module
2. Check latch operation manually (with power off)
3. Place labware and verify proper seating
4. Center labware on plate
```

**Step 2: Test Latch via Serial**
```
screen /dev/ot_module_heatershaker0 115200

# Open latch
M242

# Close latch
M243

# If fails, latch mechanism may be stuck or motor failed
```

**Step 3: Balance Check for Shaking**
```
1. Ensure labware is properly seated and centered
2. Start at low speed (200 RPM)
3. Gradually increase speed
4. Listen/feel for vibration at each speed
5. If excessive vibration:
   - Reposition labware
   - Check liquid distribution is even
   - If persists, bearing may be worn
```

**Step 4: Test Temperature**
```
# Set temperature
M104 S37

# Monitor
M105

# Should reach 37°C in < 3 minutes
```

**Step 5: Speed Verification**
```
# Set speed
M3 S1000

# Query actual speed
M123

# Should be within ± 10 RPM of target
# If far off, motor or encoder issue

# Stop shaking
G28
```

---

## 4. Calibration Tests

### 4.1 Deck Calibration

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| File exists | Yes | - | No |
| Matrix determinant | 0.95 - 1.05 | 0.9 - 0.95 or 1.05 - 1.1 | < 0.9 or > 1.1 |
| Matrix rank | 3 | - | < 3 (singular) |
| Not identity | Calibrated values | Identity matrix | - |
| Age | < 3 months | 3 - 6 months | > 6 months |

#### Corrective Actions

**Recalibrate Deck:**
```
Via Opentrons App:
1. Robot Settings > Calibration > Calibrate Deck
2. Attach calibration probe to left pipette
3. Touch each of 3 calibration points
4. Verify new calibration saved
```

**Backup Before Recalibration:**
```bash
cp /data/opentrons/robot/deck_calibration.json \
   /data/opentrons/robot/deck_calibration.json.backup
```

---

### 4.2 Pipette Offset Calibration

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Offset magnitude | < 3 mm | 3 - 5 mm | > 5 mm |
| File not corrupt | Valid JSON | - | Invalid JSON |
| Reasonable values | All axes reasonable | One axis large | Multiple large |

#### Corrective Actions

**Recalibrate Pipette Offset:**
```
Via Opentrons App:
1. Ensure deck is calibrated first
2. Robot Settings > Calibration > Calibrate Pipette Offset
3. Pick up a tip
4. Touch calibration point
5. Save calibration
```

---

### 4.3 Tip Length Calibration

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Tip length value | 20 - 100 mm (typical) | Outside range | Missing/NaN |
| File exists | Yes | - | No |

**Typical Tip Lengths:**
| Tiprack | Tip Length (mm) |
|---------|-----------------|
| 20µL | ~39 mm |
| 200µL | ~52 mm |
| 300µL | ~52 mm |
| 1000µL | ~85 mm |

#### Corrective Actions

**Recalibrate Tip Length:**
```
Via Opentrons App:
1. Robot Settings > Calibration > Calibrate Tip Length
2. Select tiprack type
3. Pick up tip
4. Touch deck surface
5. Save calibration
```

---

## 5. System Health

### 5.1 Disk Space

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Space used | < 80% | 80 - 95% | > 95% |
| Free space | > 500 MB | 100 - 500 MB | < 100 MB |

#### Corrective Actions

**Step 1: Check Space Usage**
```bash
df -h /data
du -sh /data/* | sort -h
```

**Step 2: Clean Protocol Files**
```bash
# List protocols by size
du -sh /data/protocols/* | sort -h

# Remove old protocols (older than 90 days)
find /data/protocols -mtime +90 -delete
```

**Step 3: Clean Log Files**
```bash
# Truncate large log files
truncate -s 0 /var/log/opentrons-api*.log

# Or use journalctl to clean
journalctl --vacuum-size=100M
```

**Step 4: Clean Run History**
```bash
# Remove old run records
find /data/runs -mtime +30 -delete
```

---

### 5.2 Error Logs

#### Acceptance Criteria

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Errors (24h) | 0 | 1 - 10 | > 10 |
| Critical errors | 0 | 1 - 2 | > 2 |
| Repeated same error | No | Few | Many |

#### Corrective Actions

**Step 1: Review Errors**
```bash
# View recent errors
journalctl --since "24 hours ago" -p err

# Look for patterns:
# - Same error repeating = systematic issue
# - Random errors = may be transient
# - Hardware errors = physical inspection needed
```

**Step 2: Common Error Patterns**

| Error Pattern | Likely Cause | Action |
|---------------|--------------|--------|
| "Smoothie not responding" | Serial communication | Check cable, restart robot-server |
| "Homing failed" | Limit switch or motor | Check switches, belt tension |
| "EEPROM read error" | Pipette connection | Reseat pipette, clean contacts |
| "Module not found" | USB connection | Reconnect module, check cable |
| "Move timed out" | Motor stall | Check for obstructions, belt tension |

**Step 3: Clear Error State**
```bash
# Restart robot server
systemctl restart opentrons-robot-server

# Check status
systemctl status opentrons-robot-server
```

---

### 5.3 Services Status

#### Acceptance Criteria

| Service | Expected Status |
|---------|-----------------|
| opentrons-robot-server | active (running) |
| opentrons-update-server | active (running) |

#### Corrective Actions

**Restart Services:**
```bash
# Restart robot server
systemctl restart opentrons-robot-server

# Restart update server
systemctl restart opentrons-update-server

# Check status
systemctl status opentrons-robot-server
systemctl status opentrons-update-server
```

**Check for Errors:**
```bash
# View service logs
journalctl -u opentrons-robot-server -n 50
journalctl -u opentrons-update-server -n 50
```

**Full System Restart:**
```bash
# If services won't start
reboot
```

---

## Appendix A: Tools Required

| Tool | Purpose |
|------|---------|
| 2mm hex key | Pulley set screws, small fasteners |
| 2.5mm hex key | Motor mounts, belt tensioners |
| 3mm hex key | Frame fasteners |
| Phillips screwdriver (#1, #2) | Covers, limit switches |
| Multimeter | Continuity testing, voltage checks |
| Digital calipers | Position verification |
| Machinist's square | Squareness checks |
| Bubble level | Deck leveling |
| Compressed air | Cleaning |
| Isopropyl alcohol (70%+) | Cleaning contacts and surfaces |
| Lint-free cloths | Wiping |
| Light machine oil | Rail lubrication |
| Silicone lubricant | O-ring lubrication |
| Cotton swabs | Contact cleaning |
| USB-serial adapter | Direct serial access (backup) |

---

## Appendix B: Part Numbers Reference

| Part | Description | Notes |
|------|-------------|-------|
| Limit switches | Microswitch, normally open | X, Y, Z, A, B, C axes |
| GT2 timing belt | 6mm width, various lengths | X, Y, Z axes |
| Linear bearings | LM8UU or equivalent | Gantry rails |
| Leadscrew nut | Anti-backlash type | Z axes |
| Pipette O-rings | Various sizes | Model-specific |

*Contact Opentrons support for specific part numbers*

---

## Appendix C: When to Escalate

Contact Opentrons support if:

1. **Multiple related failures** - Multiple tests failing in same system
2. **Electrical damage** - Visible burn marks, melted components
3. **Structural damage** - Bent frame, cracked components
4. **Firmware issues** - Won't boot, can't update firmware
5. **Repeated failures** - Same issue returns after repair
6. **Safety concerns** - Unexpected movements, overheating
7. **Module internal failure** - Peltier, motor, sensor failures
8. **Out of specification** - Cannot achieve required tolerances after adjustments

**Opentrons Support:** support@opentrons.com

---

*Document Version: 1.0*
*Last Updated: 2024*
