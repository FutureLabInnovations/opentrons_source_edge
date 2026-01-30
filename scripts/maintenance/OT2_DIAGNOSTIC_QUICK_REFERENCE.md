# OT-2 Diagnostic Quick Reference Card

## Pass/Fail Margins Summary

### Motion System

| Test | PASS | WARNING | FAIL |
|------|------|---------|------|
| **Homing Range (5 iterations)** | < 0.1 mm | 0.1 - 0.3 mm | > 0.3 mm |
| **Homing Std Dev** | < 0.03 mm | 0.03 - 0.08 mm | > 0.08 mm |
| **Position Repeatability 3D** | < 0.1 mm | 0.1 - 0.25 mm | > 0.25 mm |
| **Cross-Deck Max Error** | < 0.5 mm | 0.5 - 1.5 mm | > 1.5 mm |
| **Z Travel Error (100mm move)** | < 1.0 mm | 1.0 - 2.0 mm | > 2.0 mm |
| **Speed Accuracy** | < 10% error | 10 - 20% | > 20% |

### Expected Home Positions

| Axis | Position | Tolerance |
|------|----------|-----------|
| X | 418.0 mm | ± 0.5 mm |
| Y | 353.0 mm | ± 0.5 mm |
| Z | 218.0 mm | ± 0.5 mm |
| A | 218.0 mm | ± 0.5 mm |

### Pipette Tests

| Test | PASS | WARNING | FAIL |
|------|------|---------|------|
| **Plunger Travel** | > 1.0 mm | 0.5 - 1.0 mm | < 0.5 mm |
| **Offset Magnitude** | < 3.0 mm | 3.0 - 5.0 mm | > 5.0 mm |
| **Tip Length** | 20 - 100 mm | Outside range | NaN/missing |

### Module Specifications

#### Temperature Module
| Parameter | Nominal | Acceptable | Fail |
|-----------|---------|------------|------|
| Temp Reading (ambient) | 15-30°C | 5-50°C | Outside/NaN |
| Accuracy | ± 0.5°C | ± 1.0°C | > ± 1.0°C |
| Heat to 37°C | < 3 min | 3-5 min | > 5 min |
| Cool to 4°C | < 8 min | 8-15 min | > 15 min |

#### Magnetic Module
| Parameter | PASS | FAIL |
|-----------|------|------|
| Engage Response | < 2 sec | > 5 sec or no response |
| Disengage Response | < 2 sec | > 5 sec or no response |
| Position Accuracy | ± 0.5 mm | > 1.0 mm |

#### Thermocycler
| Parameter | Nominal | Acceptable | Fail |
|-----------|---------|------------|------|
| Lid Open/Close | < 5 sec | 5-10 sec | > 10 sec |
| Lid to 105°C | < 5 min | 5-10 min | > 10 min |
| Plate to 95°C | < 2 min | 2-5 min | > 5 min |
| Accuracy | ± 0.5°C | ± 1.0°C | > ± 1.0°C |
| Ramp Rate | > 2°C/s | 1-2°C/s | < 1°C/s |

#### Heater-Shaker
| Parameter | Nominal | Acceptable | Fail |
|-----------|---------|------------|------|
| Latch Open/Close | < 2 sec | 2-5 sec | > 5 sec |
| Heat to 37°C | < 3 min | 3-5 min | > 5 min |
| Temp Accuracy | ± 0.5°C | ± 1.0°C | > ± 1.0°C |
| Speed Accuracy | ± 1% | ± 5% | > ± 10% |

### Calibration

| Calibration | PASS | WARNING | FAIL |
|-------------|------|---------|------|
| Deck Matrix Determinant | 0.95 - 1.05 | 0.9-0.95 or 1.05-1.1 | < 0.9 or > 1.1 |
| Deck Matrix Rank | 3 | - | < 3 (singular) |
| Deck Calibration Age | < 3 months | 3-6 months | > 6 months |
| Pipette Offset Age | < 3 months | 3-6 months | > 6 months |

### System Health

| Metric | PASS | WARNING | FAIL |
|--------|------|---------|------|
| Disk Usage | < 80% | 80-95% | > 95% |
| Free Space | > 500 MB | 100-500 MB | < 100 MB |
| Errors (24h) | 0 | 1-10 | > 10 |
| Services | All active | - | Any inactive |

---

## Quick Fixes Cheat Sheet

### Motion Issues

| Symptom | First Action | Second Action |
|---------|--------------|---------------|
| Homing fails | Check M119 switches | Clean/adjust switches |
| Poor repeatability | Check belt tension | Lubricate rails |
| Axis grinding | Clean leadscrew | Check bearings |
| Steps skipping | Increase M907 current | Check pulleys |

### Pipette Issues

| Symptom | First Action | Second Action |
|---------|--------------|---------------|
| Not detected | Reseat pipette | Clean contacts |
| Plunger stuck | Run unstick (M907 B0.5) | Lubricate O-ring |
| Volume inaccurate | Recalibrate | Check O-ring |

### Module Issues

| Symptom | First Action | Second Action |
|---------|--------------|---------------|
| Not detected | Reconnect USB | Update firmware |
| Temp not reaching | Check heat sink | Check fans |
| Slow response | Power cycle | Check connections |

### Calibration Issues

| Symptom | First Action | Second Action |
|---------|--------------|---------------|
| Position errors | Recalibrate deck | Check belt tension |
| Pipette offset large | Recalibrate pipette | Check mount |
| Tips miss wells | Calibrate tip length | Check tip pickup |

---

## Serial Commands Quick Reference

```
# Check positions
M114.2

# Check switches
M119

# Home all
G28.2 X Y Z A B C

# Move to position
G0 X100 Y200 Z100 F18000

# Set motor current
M907 X1.25 Y1.25 Z0.5 A0.5 B0.05 C0.05

# Unstick plunger
M907 B0.5 C0.5
G0 B18 F60
G28.2 B C
M907 B0.05 C0.05

# Reset from error
M999

# Get firmware version
version
```

---

## Escalation Criteria

Escalate to Opentrons Support when:

- ❌ Multiple tests failing in same system
- ❌ Visible electrical/structural damage
- ❌ Cannot achieve spec after adjustments
- ❌ Firmware won't update/boot
- ❌ Safety concerns (overheating, unexpected motion)
- ❌ Module internal failure (Peltier, motor)

**Support:** support@opentrons.com

---

## Maintenance Schedule

| Task | Frequency |
|------|-----------|
| Full diagnostic | Annually |
| Deck calibration check | Quarterly |
| Belt tension check | Quarterly |
| Rail cleaning/lubrication | Quarterly |
| Plunger exercise (idle robots) | Weekly |
| Firmware updates | As released |
| Calibration backup | Before any service |
