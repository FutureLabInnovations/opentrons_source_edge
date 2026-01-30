# Opentrons OT-2 and Flex Robot Architecture Guide
## Comprehensive Maintenance Documentation - January 2026

---

## Table of Contents
1. [Hardware Overview](#hardware-overview)
2. [OT-2 Architecture](#ot-2-architecture)
3. [Flex (OT-3) Architecture](#flex-ot-3-architecture)
4. [Module Communication Protocols](#module-communication-protocols)
5. [Module Reference Guide](#module-reference-guide)
6. [Diagnostic Commands Reference](#diagnostic-commands-reference)

---

## Hardware Overview

### OT-2 Robot
- **Main Computer**: Raspberry Pi 3 Model B running Linux
- **Motor Controller**: Modified Smoothieboard running custom Smoothieware firmware
- **Communication**: UART serial connection between Raspberry Pi and Smoothieboard
- **Protocol**: G-code based commands
- **Motors**: 6 stepper motors (X, Y, Z, A, B, C axes)
- **Power**: 36 VDC for motors

### Flex (OT-3) Robot
- **Processor**: STM32-based MCUs with DFU bootloader
- **Communication**: CAN FD (Flexible Data-rate) bus
- **CAN Bitrate**: 500,000 bps
- **Architecture**: Distributed nodes with unique NodeIds
- **Motion**: Linear stepper motors (36 VDC hybrid bipolar)

---

## OT-2 Architecture

### Motion System
| Axis | Function | Max Speed | Default Current |
|------|----------|-----------|-----------------|
| X | Left/right motion | 600 mm/s | High/Low modes |
| Y | Forward/back motion | 400 mm/s | High/Low modes |
| Z | Left pipette up/down | 125 mm/s | High/Low modes |
| A | Right pipette up/down | 125 mm/s | High/Low modes |
| B | Left pipette plunger | 40 mm/s | High/Low modes |
| C | Right pipette plunger | 40 mm/s | High/Low modes |

### Key Source Files
- Smoothie Driver: `/api/src/opentrons/drivers/smoothie_drivers/driver_3_0.py`
- Motor Constants: `/api/src/opentrons/drivers/smoothie_drivers/constants.py`
- Default Config: `/api/src/opentrons/config/defaults_ot2.py`

---

## Flex (OT-3) Architecture

### CAN Bus Node IDs
| Node | ID (Hex) | Description |
|------|----------|-------------|
| Host | 0x10 | Main control computer |
| Gantry X | 0x30 | X-axis motor controller |
| Gantry Y | 0x40 | Y-axis motor controller |
| Head | 0x50 | Head assembly |
| Pipette Left | 0x60 | Left pipette mount |
| Pipette Right | 0x70 | Right pipette mount |
| Gripper | 0x20 | Gripper assembly |
| HEPA/UV | 0x32 | HEPA/UV module |

### Key Source Files
- CAN Constants: `/hardware/opentrons_hardware/firmware_bindings/constants.py`
- CAN Messenger: `/hardware/opentrons_hardware/drivers/can_bus/can_messenger.py`
- Arbitration ID: `/hardware/opentrons_hardware/firmware_bindings/arbitration_id.py`

---

## Module Communication Protocols

All modules use serial UART communication with the following common parameters:

| Parameter | Value |
|-----------|-------|
| Baud Rate | 115200 |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |
| Flow Control | None |

### Command Format
Commands follow G-code format with module-specific terminators:

```
COMMAND [PARAM:VALUE ...] <TERMINATOR>
```

### Response Format
Responses use key-value pairs:
```
KEY:VALUE KEY:VALUE ... <ACK>
```

---

## Module Reference Guide

### 1. Temperature Module (TempDeck)

**Connection Parameters:**
- Baud Rate: 115200
- Terminator: `\r\n\r\n`
- ACK: `ok\r\nok\r\n`
- Timeout: 1 second
- Retries: 3

**G-code Commands:**
| Command | G-code | Description | Example |
|---------|--------|-------------|---------|
| Get Temperature | M105 | Query current/target temp | `M105\r\n\r\n` |
| Set Temperature | M104 | Set target temperature (C) | `M104 S65\r\n\r\n` |
| Get Device Info | M115 | Query firmware/serial | `M115\r\n\r\n` |
| Get Reset Reason | M114 | Query last reset cause | `M114\r\n\r\n` |
| Deactivate | M18 | Turn off heating/cooling | `M18\r\n\r\n` |
| Enter DFU | dfu | Enter bootloader mode | `dfu\r\n\r\n` |

**Response Examples:**
- Temperature: `T:65 C:25` (T=target, C=current)
- Device Info: `serial:TDV01P12345678 model:v20 version:2.0.0`

---

### 2. Magnetic Module (MagDeck)

**Connection Parameters:**
- Baud Rate: 115200
- Terminator: `\r\n\r\n`
- ACK: `ok\r\nok\r\n`
- Timeout: 10 seconds (includes probe time)
- Retries: 3

**G-code Commands:**
| Command | G-code | Description | Example |
|---------|--------|-------------|---------|
| Home | G28.2 | Home magnet to position 0 | `G28.2\r\n\r\n` |
| Probe Plate | G38.2 | Probe deck plate distance | `G38.2\r\n\r\n` |
| Get Plate Height | M836 | Query calculated plate height | `M836\r\n\r\n` |
| Get Position | M114.2 | Query current Z position | `M114.2\r\n\r\n` |
| Move | G0 | Move to Z position | `G0 Z12.345\r\n\r\n` |
| Get Device Info | M115 | Query device information | `M115\r\n\r\n` |
| Enter DFU | dfu | Enter bootloader mode | `dfu\r\n\r\n` |

**Position Units:**
- Gen1: Half-millimeters ("short mm")
- Gen2: Millimeters

---

### 3. Thermocycler Module

**Connection Parameters:**
- Baud Rate: 115200 (normal), 1200 (bootloader)
- Gen1 Terminator: `\r\n`
- Gen2 Terminator: `\n`
- Gen1 ACK: `ok\r\nok\r\n`
- Gen2 ACK: ` OK\n`
- Timeout: 40 seconds
- Retries: 3

**G-code Commands:**
| Command | G-code | Description | Example |
|---------|--------|-------------|---------|
| Open Lid | M126 | Open thermocycler lid | `M126\r\n` |
| Close Lid | M127 | Close thermocycler lid | `M127\r\n` |
| Plate Lift | M128 | Lift plate (Gen2 only) | `M128\r\n` |
| Get Lid Status | M119 | Query lid open/closed | `M119\r\n` |
| Set Lid Temp | M140 | Set lid temperature | `M140 S105\r\n` |
| Get Lid Temp | M141 | Query lid temperature | `M141\r\n` |
| Set Plate Temp | M104 | Set plate temperature | `M104 S95 H30 V50\r\n` |
| Get Plate Temp | M105 | Query plate temperature | `M105\r\n` |
| Set Ramp Rate | M566 | Set temp ramp (Gen1 only) | `M566 S2.5\r\n` |
| Deactivate All | M18 | Turn off all heaters | `M18\r\n` |
| Deactivate Lid | M108 | Turn off lid heater | `M108\r\n` |
| Deactivate Block | M14 | Turn off plate heater | `M14\r\n` |
| Get Device Info | M115 | Query device information | `M115\r\n` |
| Jog Lid | M240.D | Move lid by angle (Gen2) | `M240.D 20 O\r\n` |

**Temperature Limits:**
- Lid: 37-110 C
- Plate: 0-99 C

**Gen1 vs Gen2 Detection:**
- Gen1: M115 response does NOT start with "M115"
- Gen2: M115 response STARTS with "M115"

---

### 4. Heater-Shaker Module

**Connection Parameters:**
- Baud Rate: 115200
- Terminator: `\n`
- ACK: `OK\n`
- Error Keyword: `err`
- Timeout: 40 seconds
- Retries: 0 (no retries)

**G-code Commands:**
| Command | G-code | Description | Example |
|---------|--------|-------------|---------|
| Set RPM | M3 | Set shaker speed | `M3 S2500\n` |
| Get RPM | M123 | Query current/target RPM | `M123\n` |
| Set Temperature | M104 | Set heater temperature | `M104 S65.25\n` |
| Get Temperature | M105 | Query temperature | `M105\n` |
| Home | G28 | Home shaker (stops motion) | `G28\n` |
| Open Latch | M242 | Open labware latch | `M242\n` |
| Close Latch | M243 | Close labware latch | `M243\n` |
| Get Latch State | M241 | Query latch status | `M241\n` |
| Deactivate Heater | M106 | Turn off heater | `M106\n` |
| Get Device Info | M115 | Query device information | `M115\n` |
| Get Reset Reason | M114 | Query reset reason | `M114\n` |
| Enter DFU | dfu | Enter bootloader mode | `dfu\n` |

**Labware Latch States:**
- IDLE_UNKNOWN
- IDLE_CLOSED
- IDLE_OPEN
- LATCH_CLOSED
- LATCH_OPEN

---

### 5. Flex Stacker Module (Flex Only)

**Connection Parameters:**
- Baud Rate: 115200
- Terminator: `\n`
- ACK: `OK\n`
- Error Keyword: `err`
- Timeout: 5 seconds (20 for moves)
- Retries: 2

**G-code Commands:**
| Command | G-code | Description |
|---------|--------|-------------|
| Move To | G0 | Move axis to position |
| Move To Switch | G5 | Move until limit switch |
| Home Axis | G28 | Home specified axis |
| Stop Motors | M0 | Emergency stop all motors |
| Enable Motors | M17 | Enable specified axis motors |
| Get Reset Reason | M114 | Query reset reason |
| Get Device Info | M115 | Query device information |
| Get Limit Switch | M119 | Query all limit switches |
| Get Move Params | M120 | Query motion parameters |
| Get Platform Sensor | M121 | Query platform sensors |
| Get Door Switch | M122 | Query door closed state |
| Get Install Detected | M123 | Query installation status |
| Set LED | M200 | Control LED status bar |
| Set Run Current | M906 | Set motor run current |
| Set Hold Current | M907 | Set motor hold current |
| Set Stallguard | M910 | Configure stall detection |

**Axes:**
- X: Horizontal transfer
- Z: Vertical lift
- L: Latch mechanism

---

### 6. Absorbance Reader Module (Flex Only)

**Note:** The Absorbance Reader uses HID (Human Interface Device) protocol, not serial G-code.
It requires the `byonoy` library for communication.

**Key Functions:**
- `get_device_information()`: Query serial, firmware, model
- `get_lid_status()`: Check if lid is open/closed
- `get_available_wavelengths()`: List supported wavelengths
- `initialize_measurement()`: Configure measurement mode
- `get_measurement()`: Perform optical measurement
- `get_plate_presence()`: Check if plate is present

---

## Diagnostic Commands Reference

### Quick Health Check Commands

**Temperature Module:**
```
M115\r\n\r\n  # Get device info
M105\r\n\r\n  # Get current temperature
```

**Magnetic Module:**
```
M115\r\n\r\n  # Get device info
M114.2\r\n\r\n # Get current position
G28.2\r\n\r\n  # Home magnet
```

**Thermocycler:**
```
M115\r\n      # Get device info (check Gen1 vs Gen2)
M119\r\n      # Get lid status
M105\r\n      # Get plate temperature
M141\r\n      # Get lid temperature
```

**Heater-Shaker:**
```
M115\n        # Get device info
M105\n        # Get temperature
M123\n        # Get RPM
M241\n        # Get latch status
```

**Flex Stacker:**
```
M115\n        # Get device info
M119\n        # Get all limit switches
M121\n        # Get platform sensors
M122\n        # Get door status
```

---

## Source Code References

| Component | Path |
|-----------|------|
| Temperature Module Driver | `/api/src/opentrons/drivers/temp_deck/driver.py` |
| Magnetic Module Driver | `/api/src/opentrons/drivers/mag_deck/driver.py` |
| Thermocycler Driver | `/api/src/opentrons/drivers/thermocycler/driver.py` |
| Heater-Shaker Driver | `/api/src/opentrons/drivers/heater_shaker/driver.py` |
| Flex Stacker Driver | `/api/src/opentrons/drivers/flex_stacker/driver.py` |
| Absorbance Reader Driver | `/api/src/opentrons/drivers/absorbance_reader/driver.py` |
| Shared Utilities | `/api/src/opentrons/drivers/utils.py` |
| Module Definitions | `/shared-data/module/definitions/` |

---

## Safety Notes

1. **Always deactivate heaters before disconnecting modules**
2. **Home modules before performing move operations**
3. **Never force the Thermocycler lid - use motor commands**
4. **Allow modules to cool before handling**
5. **Disconnect power before any physical maintenance**

---

*Document generated for Opentrons maintenance procedures - January 2026*
