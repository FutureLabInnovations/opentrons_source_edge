# Firmware Patch Instructions for Temperature Module Gen2

This document explains how to add M303 calibration support to the Temperature Module Gen2 firmware.

## Overview

The patch adds:
- **M303 command** - Get/set/save temperature calibration offset
- **EEPROM storage** - Calibration persists at address 0x80
- **Automatic application** - Offset applied to all temperature readings

## Files to Modify

```
arduino-modules/temp-deck/temp-deck-arduino/
├── gcode.h          ← Replace with patched version
├── gcode.cpp        ← Replace with patched version
├── memory.h         ← Replace with patched version
├── memory.cpp       ← Replace with patched version
└── temp-deck-arduino.ino  ← Apply changes below
```

## Changes to temp-deck-arduino.ino

### 1. Add Global Variable (near top of file, after includes)

Find the global variables section and add:

```cpp
// ============================================================================
// CALIBRATION OFFSET (NEW)
// ============================================================================
float calibration_offset = 0.0;  // Loaded from EEPROM on startup
```

### 2. Load Calibration in setup()

In the `setup()` function, after `memory` is initialized, add:

```cpp
void setup() {
    // ... existing setup code ...

    // [NEW] Load calibration offset from EEPROM
    calibration_offset = memory.read_calibration_offset();

    // ... rest of setup ...
}
```

### 3. Add M303 Handler in the Command Switch

Find the switch statement that handles G-code commands (likely in a function called `read_gcode()` or in the main `loop()`). Add a new case:

```cpp
switch (gcode.code) {

    // ... existing cases ...

    // [NEW] M303 - Calibration offset
    case GCODE_CALIBRATION:
        if (gcode.read_number('R')) {
            // M303 R - Reset offset to 0
            calibration_offset = 0.0;
            if (gcode.read_number('S')) {
                // M303 R S - Reset and save to EEPROM
                memory.clear_calibration();
            }
            gcode.print_calibration_offset(calibration_offset);
        }
        else if (gcode.read_number('O')) {
            // M303 O## - Set offset
            float new_offset = gcode.parsed_number;

            // Validate range
            if (new_offset >= -10.0 && new_offset <= 10.0) {
                calibration_offset = new_offset;

                if (gcode.read_number('S')) {
                    // M303 O## S - Set and save to EEPROM
                    memory.write_calibration_offset(calibration_offset);
                }
                gcode.print_calibration_offset(calibration_offset);
            }
            else {
                gcode.print_warning("offset must be -10 to +10");
            }
        }
        else {
            // M303 - Just report current offset
            gcode.print_calibration_offset(calibration_offset);
        }
        gcode.send_ack();
        break;

    // ... rest of switch ...
}
```

### 4. Apply Offset to Temperature Reading

Find where `thermistor.temperature()` is called and the result is used. This is typically in the main loop. The temperature needs the offset applied.

**Option A: Create a helper function (recommended)**

Add this function before `loop()`:

```cpp
/*
 * Get calibrated temperature reading
 * Applies the calibration offset to the raw thermistor reading
 */
float get_calibrated_temperature() {
    return thermistor.temperature() + calibration_offset;
}
```

Then replace all instances of:
```cpp
thermistor.temperature()
```
with:
```cpp
get_calibrated_temperature()
```

**Option B: Apply inline**

Wherever temperature is used, add the offset:

```cpp
// Before:
float current_temp = thermistor.temperature();

// After:
float current_temp = thermistor.temperature() + calibration_offset;
```

### 5. Key Places to Apply Offset

Search for these patterns and ensure offset is applied:

1. **M105 temperature reporting:**
```cpp
// Find code like:
gcode.print_targetting_temperature(target_temperature, thermistor.temperature());
gcode.print_stablizing_temperature(thermistor.temperature());

// Change to:
gcode.print_targetting_temperature(target_temperature, get_calibrated_temperature());
gcode.print_stablizing_temperature(get_calibrated_temperature());
```

2. **PID input:**
```cpp
// Find the PID update, something like:
Input = thermistor.temperature();

// Change to:
Input = get_calibrated_temperature();
```

3. **Safety checks:**
```cpp
// Temperature limit checks should use calibrated value:
if (get_calibrated_temperature() > MAX_SAFE_TEMP) { ... }
```

4. **Display update:**
```cpp
// LED display should show calibrated temp:
lights.display_number(get_calibrated_temperature());
```

## M303 Command Reference

After patching, these commands will work:

| Command | Action |
|---------|--------|
| `M303` | Get current offset → `O:0.00 ok` |
| `M303 O1.5` | Set offset to +1.5°C (temporary, lost on reboot) |
| `M303 O1.5 S` | Set offset to +1.5°C and save to EEPROM (permanent) |
| `M303 O-0.5 S` | Set offset to -0.5°C and save (permanent) |
| `M303 R` | Reset offset to 0 (temporary) |
| `M303 R S` | Reset offset to 0 and clear EEPROM (permanent) |

## EEPROM Memory Map

```
Address   Size   Content
────────────────────────────────
0x00-0x1F  32    Serial number (existing)
0x20-0x3F  32    Model number (existing)
0x40-0x5F  32    Serial CRC (existing)
0x60-0x7F  32    Model CRC (existing)
0x80-0x83   4    Calibration offset (float) [NEW]
0x84        1    Calibration valid flag (0xCA = valid) [NEW]
0x85        1    Calibration CRC [NEW]
0x86-0xFF  ...   Unused
```

## Verification

After flashing, verify the patch works:

1. **Check M303 responds:**
   ```
   Send: M303
   Expect: O:0.00 ok
   ```

2. **Set temporary offset:**
   ```
   Send: M303 O2.0
   Expect: O:2.00 ok
   ```

3. **Verify M105 reflects offset:**
   ```
   Send: M105
   Expect: Temperature should be 2°C higher than before
   ```

4. **Save to EEPROM:**
   ```
   Send: M303 O1.5 S
   Expect: O:1.50 ok
   ```

5. **Power cycle and verify persistence:**
   ```
   Send: M303
   Expect: O:1.50 ok (offset survived reboot)
   ```

## Troubleshooting

**M303 not recognized:**
- Verify GCODE_CALIBRATION is defined in gcode.h
- Verify "M303" is added to COMMAND_CODES array in gcode.cpp
- Verify TOTAL_GCODE_COMMAND_CODES is 7 (not 6)

**Offset not applied to temperature:**
- Check that get_calibrated_temperature() is used everywhere
- Verify calibration_offset variable is global

**Offset not persisting after reboot:**
- Check that 'S' parameter triggers memory.write_calibration_offset()
- Verify EEPROM addresses don't conflict with existing data
- Check memory.has_valid_calibration() returns true after write
