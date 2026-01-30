# OT-2 Maintenance Service Report

---

## Service Information

| Field | Value |
|-------|-------|
| **Customer Name** | ________________________________ |
| **Customer Location** | ________________________________ |
| **Service Date** | ________________________________ |
| **Technician Name** | ________________________________ |
| **Service Type** | ☐ Annual Maintenance  ☐ Repair  ☐ Installation  ☐ Other: ________ |

---

## Robot Information

| Field | Value |
|-------|-------|
| **Robot Model** | OT-2 |
| **Serial Number** | ________________________________ |
| **Software Version** | ________________________________ |
| **Firmware Version** | ________________________________ |
| **Last Service Date** | ________________________________ |

---

## Pre-Service Condition

### Customer Reported Issues
_Document any issues reported by the customer before service:_

- [ ] No issues reported
- [ ] Motion/Movement issues: ________________________________________________
- [ ] Pipette issues: ________________________________________________
- [ ] Module issues: ________________________________________________
- [ ] Calibration issues: ________________________________________________
- [ ] Software/Connectivity issues: ________________________________________________
- [ ] Other: ________________________________________________

### Initial Visual Inspection
| Component | Condition | Notes |
|-----------|-----------|-------|
| Deck surface | ☐ Good  ☐ Fair  ☐ Poor | |
| Gantry/Rails | ☐ Good  ☐ Fair  ☐ Poor | |
| Pipette mounts | ☐ Good  ☐ Fair  ☐ Poor | |
| Cable management | ☐ Good  ☐ Fair  ☐ Poor | |
| Door/Enclosure | ☐ Good  ☐ Fair  ☐ Poor | |

---

## Diagnostic Test Results

### Executive Summary

| Overall Status | ☐ PASS  ☐ WARNING  ☐ FAIL |
|----------------|---------------------------|

| Metric | Result |
|--------|--------|
| Total Tests Performed | ________ |
| Passed | ________ |
| Failed | ________ |
| Warnings | ________ |
| Test Duration | ________ minutes |

---

### 1. Motion System Tests

| Test | Status | Notes |
|------|--------|-------|
| Limit Switch Verification | ☐ Pass  ☐ Fail  ☐ Warning | |
| Homing Accuracy | ☐ Pass  ☐ Fail  ☐ Warning | Range: ________ mm |
| Position Repeatability | ☐ Pass  ☐ Fail  ☐ Warning | 3D Repeatability: ________ mm |
| Cross-Deck Accuracy | ☐ Pass  ☐ Fail  ☐ Warning | Max error: ________ mm |
| Z-Axis Movement (Left) | ☐ Pass  ☐ Fail  ☐ Warning | |
| Z-Axis Movement (Right) | ☐ Pass  ☐ Fail  ☐ Warning | |

**Motion System Notes:**
_________________________________________________________________________
_________________________________________________________________________

---

### 2. Pipette Tests

#### Left Mount

| Field | Value |
|-------|-------|
| Pipette Model | ________________________________ |
| Pipette Serial | ________________________________ |
| Channels | ☐ Single  ☐ Multi (8-channel)  ☐ 96-channel |
| Volume Range | ________ - ________ µL |

| Test | Status | Notes |
|------|--------|-------|
| Detection | ☐ Pass  ☐ Fail  ☐ N/A | |
| Plunger Movement | ☐ Pass  ☐ Fail  ☐ N/A | Travel: ________ mm |
| Calibration Status | ☐ Pass  ☐ Fail  ☐ N/A | Offset: [____, ____, ____] |
| Tip Pickup | ☐ Pass  ☐ Fail  ☐ N/A | |
| Tip Drop | ☐ Pass  ☐ Fail  ☐ N/A | |

#### Right Mount

| Field | Value |
|-------|-------|
| Pipette Model | ________________________________ |
| Pipette Serial | ________________________________ |
| Channels | ☐ Single  ☐ Multi (8-channel)  ☐ 96-channel |
| Volume Range | ________ - ________ µL |

| Test | Status | Notes |
|------|--------|-------|
| Detection | ☐ Pass  ☐ Fail  ☐ N/A | |
| Plunger Movement | ☐ Pass  ☐ Fail  ☐ N/A | Travel: ________ mm |
| Calibration Status | ☐ Pass  ☐ Fail  ☐ N/A | Offset: [____, ____, ____] |
| Tip Pickup | ☐ Pass  ☐ Fail  ☐ N/A | |
| Tip Drop | ☐ Pass  ☐ Fail  ☐ N/A | |

**Pipette Notes:**
_________________________________________________________________________
_________________________________________________________________________

---

### 3. Module Tests

#### Module Inventory

| Slot | Module Type | Serial Number | Firmware Version |
|------|-------------|---------------|------------------|
| | | | |
| | | | |
| | | | |
| | | | |

#### Temperature Module(s)

| Serial | Status | Temperature Reading | Notes |
|--------|--------|---------------------|-------|
| | ☐ Pass  ☐ Fail  ☐ N/A | ________ °C | |

#### Magnetic Module(s)

| Serial | Status | Engage Test | Disengage Test | Notes |
|--------|--------|-------------|----------------|-------|
| | ☐ Pass  ☐ Fail  ☐ N/A | ☐ Pass  ☐ Fail | ☐ Pass  ☐ Fail | |

#### Thermocycler

| Serial | Status | Lid Test | Temp Reading | Notes |
|--------|--------|----------|--------------|-------|
| | ☐ Pass  ☐ Fail  ☐ N/A | ☐ Pass  ☐ Fail | Lid: __°C Plate: __°C | |

#### Heater-Shaker

| Serial | Status | Latch Test | Temp Reading | Notes |
|--------|--------|------------|--------------|-------|
| | ☐ Pass  ☐ Fail  ☐ N/A | ☐ Pass  ☐ Fail | ________ °C | |

**Module Notes:**
_________________________________________________________________________
_________________________________________________________________________

---

### 4. Calibration Verification

| Calibration | Status | Last Modified | Notes |
|-------------|--------|---------------|-------|
| Deck Calibration | ☐ Valid  ☐ Invalid  ☐ Missing | ______________ | |
| Left Pipette Offset | ☐ Valid  ☐ Invalid  ☐ Missing | ______________ | |
| Right Pipette Offset | ☐ Valid  ☐ Invalid  ☐ Missing | ______________ | |
| Tip Lengths | ☐ Valid  ☐ Invalid  ☐ Missing | ______________ | |

**Calibration Notes:**
_________________________________________________________________________
_________________________________________________________________________

---

### 5. System Health

| Test | Status | Value | Notes |
|------|--------|-------|-------|
| Disk Space | ☐ Pass  ☐ Fail  ☐ Warning | ________ GB free (___%) | |
| Error Logs (24h) | ☐ Pass  ☐ Fail  ☐ Warning | ________ errors | |
| Robot Server | ☐ Running  ☐ Stopped | | |
| Update Server | ☐ Running  ☐ Stopped | | |
| Network Connectivity | ☐ Pass  ☐ Fail | IP: ______________ | |

**System Notes:**
_________________________________________________________________________
_________________________________________________________________________

---

## Service Actions Performed

### Maintenance Tasks

- [ ] Ran full diagnostic suite
- [ ] Cleaned deck surface
- [ ] Inspected and cleaned gantry rails
- [ ] Checked belt tension
- [ ] Verified limit switch operation
- [ ] Inspected cable routing and connections
- [ ] Tested all attached modules
- [ ] Verified calibration status
- [ ] Updated software/firmware (if applicable)
- [ ] Backed up calibration data
- [ ] Other: ________________________________________________

### Repairs/Replacements

| Component | Action | Part Number | Notes |
|-----------|--------|-------------|-------|
| | | | |
| | | | |
| | | | |

### Calibration Performed

- [ ] Deck calibration
- [ ] Left pipette offset calibration
- [ ] Right pipette offset calibration
- [ ] Tip length calibration (Left)
- [ ] Tip length calibration (Right)
- [ ] Module calibration: ________________________________________________

---

## Recommendations

### High Priority (Action Required)

| Issue | Recommendation | Timeline |
|-------|----------------|----------|
| | | |
| | | |

### Medium Priority (Suggested)

| Issue | Recommendation | Timeline |
|-------|----------------|----------|
| | | |
| | | |

### Low Priority (For Consideration)

| Issue | Recommendation | Timeline |
|-------|----------------|----------|
| | | |

---

## Post-Service Verification

| Check | Status |
|-------|--------|
| All tests passing | ☐ Yes  ☐ No  ☐ N/A |
| Robot homes correctly | ☐ Yes  ☐ No |
| Pipettes detected | ☐ Yes  ☐ No  ☐ N/A |
| Modules functional | ☐ Yes  ☐ No  ☐ N/A |
| Calibration valid | ☐ Yes  ☐ No |
| Customer walked through results | ☐ Yes  ☐ No |

---

## Customer Sign-Off

**Post-Service Robot Condition:**
☐ Robot returned to full operational status
☐ Robot operational with noted limitations
☐ Robot requires follow-up service

**Customer Acknowledgment:**

_I acknowledge that the service has been completed as described above._

**Customer Signature:** ________________________________  **Date:** ______________

**Customer Name (Print):** ________________________________

---

## Technician Notes

_Additional observations, recommendations, or follow-up items:_

_________________________________________________________________________
_________________________________________________________________________
_________________________________________________________________________
_________________________________________________________________________
_________________________________________________________________________

---

## Service Completion

| Field | Value |
|-------|-------|
| **Service Completed** | ________________________________ (Date/Time) |
| **Technician Signature** | ________________________________ |
| **Next Recommended Service** | ________________________________ |

---

**Attachments:**
- [ ] Diagnostic JSON report
- [ ] Calibration backup file
- [ ] Photos (if applicable)
- [ ] Other: ________________________________________________

---

*Document Version: 1.0*
*Template Date: 2024*
