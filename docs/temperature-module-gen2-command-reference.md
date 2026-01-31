# Temperature Module GEN2 - Command Reference Quick Card

## Communication Settings

| Parameter | Value |
|-----------|-------|
| Interface | USB CDC/ACM Serial |
| Baud Rate | 115200 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Command Terminator | `\r\n\r\n` |
| Response ACK | `ok\r\nok\r\n` |

---

## G-Code Command Reference

### M105 - Get Temperature

**Request:**
```
M105\r\n\r\n
```

**Response:**
```
T:<target> C:<current>\r\nok\r\nok\r\n
```

**Fields:**
- `T:` Target temperature (°C) or `none` if deactivated
- `C:` Current temperature (°C, 3 decimal precision)

**Example:**
```
→ M105\r\n\r\n
← T:37.000 C:36.823\r\nok\r\nok\r\n
```

---

### M104 - Set Temperature

**Request:**
```
M104 S<temp> [P<kp>] [I<ki>] [D<kd>]\r\n\r\n
```

**Parameters:**
| Param | Required | Type | Range | Description |
|-------|----------|------|-------|-------------|
| S | Yes | Float | -9 to 99 | Target °C |
| P | No | Float | 0+ | PID Kp coefficient |
| I | No | Float | 0+ | PID Ki coefficient |
| D | No | Float | 0+ | PID Kd coefficient |

**Response:**
```
ok\r\nok\r\n
```

**Examples:**
```
→ M104 S37\r\n\r\n
← ok\r\nok\r\n

→ M104 S50 P0.3 I0.02 D0\r\n\r\n
← ok\r\nok\r\n
```

---

### M18 - Disengage/Deactivate

**Request:**
```
M18\r\n\r\n
```

**Behavior:**
- Stops heating/cooling
- If >55°C: actively cools to safe temperature
- Sets target to `none`

**Response:**
```
ok\r\nok\r\n
```

---

### M115 - Get Device Info

**Request:**
```
M115\r\n\r\n
```

**Response:**
```
serial:<serial> model:<model> version:<version>\r\nok\r\nok\r\n
```

**Fields:**
- `serial:` Unique serial number (e.g., `TDV0223010102`)
- `model:` Hardware model (e.g., `temp_deck_v21`)
- `version:` Firmware version (e.g., `v2.1.0`)

**Example:**
```
→ M115\r\n\r\n
← serial:TDV0223010102 model:temp_deck_v21 version:v2.1.0\r\nok\r\nok\r\n
```

---

### M114 - Get Reset Reason

**Request:**
```
M114\r\n\r\n
```

**Response:** Reset reason code (firmware-specific)

**Note:** May return `UnhandledGcode` on older firmware versions.

---

### dfu - Enter Programming Mode

**Request:**
```
dfu\r\n\r\n
```

**Behavior:**
1. Triggers watchdog reset
2. MCU enters bootloader mode
3. USB re-enumerates as bootloader device
4. Serial connection is lost

**Use:** Firmware updates via `avrdude`

---

## Quick Reference Table

| Code | Command | Parameters | Returns |
|------|---------|------------|---------|
| M105 | GET_TEMP | - | T:\<target\> C:\<current\> |
| M104 | SET_TEMP | S\<temp\> [P\<kp\>] [I\<ki\>] [D\<kd\>] | ok |
| M18 | DISENGAGE | - | ok |
| M115 | DEVICE_INFO | - | serial, model, version |
| M114 | GET_RESET_REASON | - | reset code |
| dfu | PROGRAMMING_MODE | - | (disconnects) |

---

## Temperature Status Codes (Host-Side)

| Status | Condition |
|--------|-----------|
| `idle` | No target set (deactivated) |
| `heating` | Target > Current + 0.7°C |
| `cooling` | Target < Current - 0.7°C |
| `holding at target` | \|Target - Current\| < 0.7°C |

---

## Operating Limits

| Parameter | Value |
|-----------|-------|
| Temperature Range (Safe) | 4°C to 95°C |
| Temperature Range (Firmware) | -9°C to 99°C |
| Resolution | 1°C |
| Stability Tolerance | ±0.5°C |

---

## Python Quick Examples

### Using pyserial (Standalone)
```python
import serial

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)

# Get temperature
ser.write(b'M105\r\n\r\n')
response = ser.read(1024).decode()
# Parse: "T:37.000 C:25.123\r\nok\r\nok\r\n"

# Set temperature
ser.write(b'M104 S37\r\n\r\n')
response = ser.read(1024).decode()

# Deactivate
ser.write(b'M18\r\n\r\n')
response = ser.read(1024).decode()

ser.close()
```

### Using Protocol API
```python
from opentrons import protocol_api

def run(protocol: protocol_api.ProtocolContext):
    temp_mod = protocol.load_module('temperature module gen2', 'D1')

    # Set and wait
    temp_mod.set_temperature(37)

    # Set without waiting
    temp_mod.start_set_temperature(37)
    temp_mod.await_temperature(37)

    # Read values
    current = temp_mod.temperature
    target = temp_mod.target
    status = temp_mod.status
    serial = temp_mod.serial_number

    # Deactivate
    temp_mod.deactivate()
```

---

## Error Handling

| Condition | Response/Behavior |
|-----------|-------------------|
| Invalid command | No response or error message |
| Temperature out of range | Command may be clipped or rejected |
| Communication timeout | No ACK received within timeout |
| Module disconnected | Serial port error |

---

## Source References

- Driver: `api/src/opentrons/drivers/temp_deck/driver.py`
- Hardware Control: `api/src/opentrons/hardware_control/modules/tempdeck.py`
- Protocol API: `api/src/opentrons/protocol_api/module_contexts.py:358-441`
- Firmware: `github.com/Opentrons/opentrons-modules/arduino-modules/temp-deck/`
