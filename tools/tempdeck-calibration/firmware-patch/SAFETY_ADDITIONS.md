# Safety Additions for Firmware Patch

Add these additional safety checks to `temp-deck-arduino.ino`:

## 1. Sanity Check on Calibrated Temperature

Add this check wherever the calibrated temperature is used:

```cpp
/*
 * Get calibrated temperature with sanity check
 *
 * If the calibrated reading is physically impossible,
 * fall back to uncalibrated reading and log warning.
 */
float get_calibrated_temperature() {
    float raw_temp = thermistor.temperature();
    float calibrated_temp = raw_temp + calibration_offset;

    // Sanity check: if calibrated temp is way outside possible range,
    // something is wrong - use raw temp instead
    if (calibrated_temp < -20.0 || calibrated_temp > 120.0) {
        // Log warning (will show up in M105 response as warning)
        gcode.print_warning("CAL_SANITY_FAIL");
        return raw_temp;  // Fall back to uncalibrated
    }

    return calibrated_temp;
}
```

## 2. Offset Validation in M303 Handler

Already included, but double-check this is present:

```cpp
case GCODE_CALIBRATION:
    if (gcode.read_number('O')) {
        float new_offset = gcode.parsed_number;

        // SAFETY: Reject unreasonable offsets
        if (new_offset < -10.0 || new_offset > 10.0) {
            gcode.print_warning("OFFSET_OUT_OF_RANGE");
            gcode.send_ack();
            break;
        }

        // ... rest of handler
    }
```

## 3. EEPROM Corruption Recovery

In `setup()`, add recovery for corrupted calibration:

```cpp
void setup() {
    // ... existing setup ...

    // Load calibration with corruption check
    if (memory.has_valid_calibration()) {
        calibration_offset = memory.read_calibration_offset();

        // Double-check the loaded value is sane
        if (calibration_offset < -10.0 || calibration_offset > 10.0) {
            // Corrupted! Reset to safe default
            calibration_offset = 0.0;
            memory.clear_calibration();
        }
    } else {
        calibration_offset = 0.0;
    }
}
```

## 4. Add M303 D - Diagnostic Command

Add a diagnostic subcommand to help troubleshoot:

```cpp
case GCODE_CALIBRATION:
    if (gcode.read_number('D')) {
        // M303 D - Diagnostic: show raw vs calibrated
        float raw = thermistor.temperature();
        float cal = raw + calibration_offset;

        Serial.print("RAW:");
        Serial.print(raw, 2);
        Serial.print(" OFFSET:");
        Serial.print(calibration_offset, 2);
        Serial.print(" CAL:");
        Serial.print(cal, 2);
        Serial.print(" VALID:");
        Serial.print(memory.has_valid_calibration() ? "Y" : "N");
        Serial.print(" ");
    }
    // ... rest of cases
```

## 5. Watchdog Protection During EEPROM Write

EEPROM writes are slow. Add watchdog reset during write:

```cpp
bool Memory::write_calibration_offset(float offset) {
    // Validate range
    if (offset < -10.0 || offset > 10.0) {
        return false;
    }

    // Disable watchdog during EEPROM write (it's slow)
    wdt_disable();

    // Write offset value (4 bytes)
    EEPROM.put(ADDRESS_CALIBRATION_OFFSET, offset);

    // Write CRC
    uint8_t crc = _calculate_calibration_crc(offset);
    EEPROM.write(ADDRESS_CALIBRATION_CRC, crc);

    // Write validity flag LAST
    EEPROM.write(ADDRESS_CALIBRATION_FLAG, CALIBRATION_VALID_FLAG);

    // Re-enable watchdog
    wdt_enable(WDTO_4S);

    return true;
}
```

## 6. Safe Mode Check

Add a "safe mode" that ignores calibration if a certain condition is met (e.g., button held during boot):

```cpp
bool safe_mode = false;

void setup() {
    // Check for safe mode (e.g., if pin is grounded during boot)
    pinMode(SAFE_MODE_PIN, INPUT_PULLUP);
    if (digitalRead(SAFE_MODE_PIN) == LOW) {
        safe_mode = true;
        calibration_offset = 0.0;  // Ignore stored calibration
    }

    // ... rest of setup
}
```

Note: You'll need to define `SAFE_MODE_PIN` to an unused GPIO. Check the schematic for available pins.

## Summary of Safety Features

| Feature | Purpose | Risk Mitigated |
|---------|---------|----------------|
| Offset range limit (-10 to +10) | Prevent absurd values | Typos, malicious input |
| CRC validation | Detect corruption | Power loss, bit rot |
| Sanity check on result | Catch impossible temps | Corrupted offset |
| Valid flag written last | Atomic writes | Interrupted writes |
| Watchdog disable during write | Prevent reset mid-write | Slow EEPROM |
| Diagnostic command (M303 D) | Debug issues | Troubleshooting |
| Safe mode | Emergency recovery | Bad calibration |
| Backup tool | Full recovery | Any failure |
