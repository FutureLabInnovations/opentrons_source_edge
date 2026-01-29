# Opentrons Heater-Shaker Module - Complete Technical Analysis

## Executive Summary

The Opentrons Heater-Shaker is a modular laboratory automation device that provides:
- **Temperature control**: 37-95°C heating range
- **Orbital shaking**: 200-3000 RPM range
- **Labware latch**: Motorized plate lock mechanism

---

## 1. Repository Structure

### Primary Repositories

| Repository | Purpose |
|------------|---------|
| `github.com/Opentrons/opentrons` | Host-side Python control software (this repo) |
| `github.com/Opentrons/opentrons-modules` | STM32 firmware for the device |

### Key Directories in This Repository (opentrons)

```
api/src/opentrons/
├── drivers/heater_shaker/           # Low-level serial driver
│   ├── driver.py                    # Main driver with G-code commands
│   ├── abstract.py                  # Abstract interface definition
│   └── simulator.py                 # Software simulator
├── hardware_control/
│   ├── modules/heater_shaker.py     # Hardware control layer
│   └── emulation/heater_shaker.py   # Emulation for testing
├── protocol_engine/commands/heater_shaker/  # Protocol engine commands
│   ├── set_target_temperature.py
│   ├── wait_for_temperature.py
│   ├── set_and_wait_for_shake_speed.py
│   ├── deactivate_heater.py
│   ├── deactivate_shaker.py
│   ├── open_labware_latch.py
│   └── close_labware_latch.py
└── protocol_api/module_contexts.py  # HeaterShakerContext class

shared-data/module/definitions/3/
└── heaterShakerModuleV1.json        # Module specifications
```

### Firmware Repository Structure (opentrons-modules)

```
stm32-modules/
├── heater-shaker/
│   ├── firmware/                    # Device-specific firmware
│   │   ├── system/main.cpp          # Main entry point
│   │   ├── heater_task/             # Heater control (PID, thermistors)
│   │   ├── motor_task/              # Motor control (MCSDK, BLDC)
│   │   ├── host_comms_task/         # USB/UART communication
│   │   └── system/                  # System initialization, FreeRTOS
│   ├── src/                         # Portable code for testing
│   ├── simulator/                   # Host-side simulator
│   └── tests/                       # Unit tests
├── include/heater-shaker/
│   └── heater-shaker/
│       ├── gcodes.hpp               # G-code command definitions
│       ├── messages.hpp             # Internal message types
│       ├── heater_task.hpp          # Heater control logic + PID
│       ├── motor_task.hpp           # Motor control logic
│       ├── host_comms_task.hpp      # Communication handling
│       ├── flash.hpp                # EEPROM/Flash storage
│       └── tasks.hpp                # Task aggregation
└── common/                          # Shared utilities
```

---

## 2. Hardware Specifications

### Microcontroller
- **MCU**: STM32F3 series (STM32F303)
- **Architecture**: ARM Cortex-M4
- **DFU PID**: `df11` (Device Firmware Upgrade)

### Operating Parameters

| Parameter | Min | Max | Precision |
|-----------|-----|-----|-----------|
| Temperature | 37°C | 95°C | 2 decimal places |
| Shake Speed | 200 RPM | 3000 RPM | Integer |
| Control Period | - | 100 ticks (0.1s) | - |

### Physical Dimensions
- **Overall**: 156.25 x 91.75 mm
- **Height**: 82 mm (bare)
- **Labware Offset**: [-0.125, 1.125, 68.275] mm

### Thermistor Configuration
- **Pad A & B sensors**: Safety limit 100°C
- **Board sensor**: Safety limit 60°C
- **Hot threshold**: 48.9°C (triggers LED state changes)

### Motor System
- **Type**: BLDC (Brushless DC) motor
- **SDK**: STMicroelectronics Motor Control SDK (MCSDK v5.4.4)
- **Features**:
  - Kickstart logic for low RPM (overcomes static friction)
  - Homing sequence with solenoid engagement
  - New solenoid: 275-325 RPM home speed
  - Old solenoid: 200-250 RPM home speed

### Plate Lock
- **Timeout**: 4950ms for open/close operations
- **States**: OPENING, IDLE_OPEN, CLOSING, IDLE_CLOSED, IDLE_UNKNOWN

---

## 3. Communication Protocol

### Connection Parameters

```python
BAUDRATE = 115200
TIMEOUT = 40 seconds
TERMINATOR = "\n"
ACKNOWLEDGMENT = "OK\n"
ERROR_KEYWORD = "err"
ASYNC_ERROR_ACK = "async"
```

### G-Code Command Reference

| G-Code | Name | Description | Format |
|--------|------|-------------|--------|
| **M3** | SET_RPM | Set shake speed | `M3 S<rpm>\n` |
| **M123** | GET_RPM | Query RPM | `M123\n` → `M123 C:<current> T:<target> OK\n` |
| **M104** | SET_TEMPERATURE | Set target temp | `M104 S<temp>\n` |
| **M105** | GET_TEMPERATURE | Query temp | `M105\n` → `M105 C:<current> T:<target> OK\n` |
| **G28** | HOME | Stop shaking, home | `G28\n` |
| **M242** | OPEN_LABWARE_LATCH | Open plate lock | `M242\n` |
| **M243** | CLOSE_LABWARE_LATCH | Close plate lock | `M243\n` |
| **M241** | GET_LABWARE_LATCH_STATE | Query latch | `M241\n` → `M241 STATUS:<state> OK\n` |
| **M106** | DEACTIVATE_HEATER | Stop heating | `M106\n` |
| **M115** | GET_VERSION | Device info | `M115\n` → `FW:<ver> HW:<model> SerialNo:<sn> OK\n` |
| **M114** | GET_RESET_REASON | Debug info | `M114\n` → `M114 Last Reset Reason: <hex> OK\n` |
| **dfu** | ENTER_BOOTLOADER | DFU mode | `dfu\n` |

### Additional Firmware Commands (not all exposed in host driver)

| G-Code | Name | Description |
|--------|------|-------------|
| M204 | SET_ACCELERATION | Set RPM/s acceleration |
| M116 | SET_OFFSET_CONSTANTS | Temperature calibration B, C |
| M117 | GET_OFFSET_CONSTANTS | Read calibration values |
| M994 | IDENTIFY_MODULE_START_LED | Blink white LED |
| M995 | IDENTIFY_MODULE_STOP_LED | Stop LED blink |
| M411 | GET_ERROR_STATE | Read error bitmap |
| M413 | CLEAR_ERROR_STATE | Clear errors |
| M996 | SET_SERIAL_NUMBER | Write serial (manufacturing) |
| M241.D | GET_PLATE_LOCK_STATE_DEBUG | Extended latch status |
| M994.D | SET_LED_DEBUG | Direct LED color control |

### Response Parsing Examples

```python
# Temperature response: "M105 C:25.5 T:37.0"
# Parsed to: Temperature(current=25.5, target=37.0)

# RPM response: "M123 C:1500 T:2000"
# Parsed to: RPM(current=1500, target=2000)

# Latch status: "M241 STATUS:IDLE_CLOSED"
# Parsed to: HeaterShakerLabwareLatchStatus.IDLE_CLOSED

# Device info: "FW:2.1.0 HW:A SerialNo:HSM12345"
# Parsed to: {"version": "2.1.0", "model": "A", "serial": "HSM12345"}
```

---

## 4. Software Architecture

### Host-Side Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Protocol API Layer                          │
│            HeaterShakerContext (module_contexts.py)             │
│  Methods: set_and_wait_for_shake_speed(), set_target_temperature│
│           open_labware_latch(), close_labware_latch()           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Protocol Engine Layer                          │
│  Commands: SetAndWaitForShakeSpeed, SetTargetTemperature, etc.  │
│  (protocol_engine/commands/heater_shaker/*.py)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Hardware Control Layer                          │
│               HeaterShaker (modules/heater_shaker.py)           │
│  State management, polling, status tracking, error handling     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Driver Layer                                │
│             HeaterShakerDriver (drivers/heater_shaker/)         │
│  G-code command construction, serial communication              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Serial Connection Layer                          │
│        AsyncResponseSerialConnection (asyncio/communication/)   │
│  Async serial I/O, response parsing, error detection            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [ USB/Serial Port ]
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FIRMWARE (STM32F3)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Firmware Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        main.cpp                               │
│  HardwareInit() → Start tasks → vTaskStartScheduler()        │
└───────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ system_task   │   │  heater_task  │   │  motor_task   │
│               │   │               │   │               │
│ - LED control │   │ - PID control │   │ - BLDC motor  │
│ - Error mgmt  │   │ - Thermistors │   │ - MCSDK       │
│ - Serial num  │   │ - Power ctrl  │   │ - Plate lock  │
│ - System info │   │ - Safety      │   │ - Homing      │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │  host_comms_task  │
                    │                   │
                    │ - USB CDC         │
                    │ - UART            │
                    │ - G-code parsing  │
                    │ - Message routing │
                    └───────────────────┘
                              │
                              ▼
                      [USB/UART Port]
```

### FreeRTOS Task Structure

| Task | Priority | Stack | Purpose |
|------|----------|-------|---------|
| system_task | Normal | Static | System management, LEDs |
| heater_task | Normal | Static | Temperature PID control |
| heater_hardware_task | Normal | Static | ADC conversions |
| motor_task | Normal | Static | Motor command processing |
| motor_control_task | High | Static | Real-time motor control |
| host_comms_task | Normal | Static | USB/UART communication |

### Message Queue Flow

```
Host sends: "M104 S75.0\n"
     │
     ▼
┌─────────────────────────────────────┐
│    host_comms_task receives         │
│    Parses G-code → SetTemperature   │
│    Creates SetTemperatureMessage    │
└─────────────────────────────────────┘
     │
     ▼ (via FreeRTOS message queue)
┌─────────────────────────────────────┐
│    heater_task receives             │
│    Validates temperature range      │
│    Sets PID target                  │
│    Starts heating                   │
└─────────────────────────────────────┘
     │
     ▼ (acknowledgment)
┌─────────────────────────────────────┐
│    host_comms_task sends            │
│    "M104 OK\n"                      │
└─────────────────────────────────────┘
```

---

## 5. Control Systems

### Heater PID Controller

```cpp
// Default PID constants
KP = 0.97
KI = 0.102
KD = 1.901

// Constraints
Parameter range: -200 to 200
Output range: -1.0 to 1.0
Control period: 100 ticks (0.1 seconds)

// Control equation
error = setpoint - pad_temperature()
output = pid.compute(error)
policy.set_power_output(output)
```

### Temperature Calibration

The firmware applies a linear offset correction to thermistor readings:

```
Plate_Temperature = ((B + 1) * Measured_Temp) + C

Default values:
B = -0.0259
C = 0.6755
```

These calibration constants are stored in FLASH and can be updated via M116/M117 commands.

### Motor State Machine

```
STOPPED_UNKNOWN ──┬──► HOMING_MOVING_TO_HOME_SPEED
                  │              │
                  │              ▼
                  │    HOMING_COASTING_TO_STOP
                  │              │
                  ▼              ▼
              RUNNING ◄──── STOPPED_HOMED
                  │
                  ▼
                ERROR
```

---

## 6. Persistent Storage

### FLASH Memory Contents

| Data | Description | Default |
|------|-------------|---------|
| Serial Number | 24-character string | Unique per device |
| Calibration B | Temperature offset multiplier | -0.0259 |
| Calibration C | Temperature offset constant | 0.6755 |
| Write Flag | Indicates valid calibration data | 0/1 |

### Reading/Writing Calibration

```python
# Host-side (not exposed in standard driver, but firmware supports):
# M117\n  - Get offset constants
# M116 B-0.0259 C0.6755\n  - Set offset constants
```

---

## 7. Safety Features

### Temperature Safety
- Maximum pad temperature: 100°C (hard limit)
- Maximum board temperature: 60°C
- Automatic heater cutoff on over-temperature

### Error Conditions (Error Bitmap)
- Thermistor disconnection/short
- Open circuit detection
- Short circuit detection
- Overcurrent protection
- Power latch failures

### Error Priority
Circuit errors are prioritized over sensor errors for diagnostics.

### LED Status Indicators
| State | LED Behavior |
|-------|-------------|
| Idle | Off |
| Heating | Solid (hot mode) |
| Holding | Solid (holding mode) |
| Shaking | Pulse |
| Error | Red indication |
| Identifying | White blink |

---

## 8. Firmware Build Process

### Prerequisites
- CMake (modern, 3.16+)
- ARM GCC toolchain (arm-none-eabi-gcc)
- STM32CubeF3 HAL libraries
- FreeRTOS
- STM32 Motor Control SDK (MCSDK v5.4.4)
- dfu-util (for firmware upload)
- OpenOCD (for debugging)

### Build Commands

```bash
# Configure for cross-compilation (STM32 target)
cmake --preset stm32-cross

# Build firmware
cmake --build ./build-stm32-cross --target heater-shaker

# Flash firmware
cmake --build ./build-stm32-cross --target heater-shaker-image-flash

# Debug with GDB
cmake --build ./build-stm32-cross --target heater-shaker-debug

# Host-side testing
cmake --preset stm32-host
cmake --build ./build-stm32-host --target heater-shaker-build-and-test

# Run simulator
cmake --build ./build-stm32-host --target heater-shaker-simulator
```

### Firmware Update from Host

```python
# The device enters DFU mode via "dfu" command
# Update is performed using dfu-util
# Command: dfu-util -a 0 -s 0x08000000:leave -D<firmware.bin> -R
```

The host-side update mechanism:
1. Send `dfu\n` command to enter bootloader
2. Device enumerates as DFU device (PID: df11)
3. Use `dfu-util` to flash new firmware
4. Device reboots automatically

---

## 9. Modification Points

### To Add a New G-Code Command

**Firmware side:**
1. Add command to `gcodes.hpp` (command structure and parsing)
2. Add message type to `messages.hpp`
3. Add handler in appropriate task (heater_task.hpp, motor_task.hpp, etc.)
4. Add response handling in host_comms_task

**Host side:**
1. Add G-code enum in `drivers/heater_shaker/driver.py:GCODE`
2. Add method in `HeaterShakerDriver` class
3. Add parsing in `drivers/utils.py` if needed
4. Expose in `hardware_control/modules/heater_shaker.py`
5. (Optional) Add protocol engine command

### To Modify Temperature Control

Files to change:
- `heater_task.hpp` - PID constants, control logic
- `heater_hardware.c/.h` - ADC configuration, thermistor readings
- `flash.hpp` - Calibration storage

### To Modify Motor Control

Files to change:
- `motor_task.hpp` - Motor state machine, speed handling
- `motor_hardware.c/.h` - Motor driver interface
- `mc_parameters.h` - Motor characteristics
- `pmsm_motor_parameters.h` - BLDC motor parameters
- MCSDK configuration files

### To Add New Hardware Feature

1. Create new task files in `firmware/`
2. Add message types in `messages.hpp`
3. Add G-code support in `gcodes.hpp`
4. Register task in `main.cpp`
5. Add host-side driver support

---

## 10. Development Tools

### Debugging

```bash
# Start OpenOCD + GDB session
cmake --build ./build-stm32-cross --target heater-shaker-debug
```

### Simulator

The firmware includes a host-compilable simulator that accepts G-code via stdin:

```bash
# Build simulator
cmake --build ./build-stm32-host --target heater-shaker-simulator

# Run simulator
./build-stm32-host/heater-shaker/simulator/heater-shaker-simulator
# Then type G-codes:
M115
M104 S75.0
M105
```

### Host-Side Testing

```python
# Use the emulator for testing without hardware
from opentrons.hardware_control.emulation.heater_shaker import HeaterShakerEmulator

# Or use the simulating driver
from opentrons.drivers.heater_shaker.simulator import SimulatingDriver
```

### Code Quality

```bash
# Format code (clang-format, Google C++ style)
cmake --build ./build-stm32-host --target heater-shaker-format

# Lint code (clang-tidy)
cmake --build ./build-stm32-host --target heater-shaker-lint

# Run tests (Catch2)
cmake --build ./build-stm32-host --target heater-shaker-build-and-test
```

---

## 11. Quick Reference

### Typical Command Sequence

```
1. Connect at 115200 baud
2. M115\n → Get device info
3. M243\n → Close latch
4. M104 S75.0\n → Set temperature to 75°C
5. M3 S2000\n → Set shake speed to 2000 RPM
6. M105\n → Poll temperature (repeat until T reached)
7. M123\n → Poll RPM (repeat until T reached)
8. ... run experiment ...
9. M106\n → Deactivate heater
10. G28\n → Stop shaking, home
11. M242\n → Open latch
```

### Key Files Summary

| Purpose | Host File | Firmware File |
|---------|-----------|---------------|
| Main entry | - | firmware/system/main.cpp |
| G-code defs | drivers/heater_shaker/driver.py | include/heater-shaker/heater-shaker/gcodes.hpp |
| Messages | - | include/heater-shaker/heater-shaker/messages.hpp |
| Serial comm | drivers/asyncio/communication/ | firmware/host_comms_task/ |
| Heater control | hardware_control/modules/heater_shaker.py | include/heater-shaker/heater-shaker/heater_task.hpp |
| Motor control | - | include/heater-shaker/heater-shaker/motor_task.hpp |
| Module specs | shared-data/module/definitions/3/ | - |

---

## 12. Connection Details Template

Fill in when connecting to your device:

```
Port: /dev/ttyACM0 (Linux) or COM3 (Windows) or /dev/tty.usbmodem* (Mac)
Baud rate: 115200
Connection type: USB CDC (Virtual COM Port)
Terminator: \n (newline)
Acknowledgment: OK\n
```

### Test Commands

```bash
# Linux/Mac - test connection
echo "M115" > /dev/ttyACM0 && cat /dev/ttyACM0

# Or use screen/minicom
screen /dev/ttyACM0 115200

# Python quick test
import serial
s = serial.Serial('/dev/ttyACM0', 115200, timeout=5)
s.write(b'M115\n')
print(s.read_until(b'OK\n'))
```

---

*Document generated from analysis of Opentrons source code repositories*
*Last updated: Analysis performed on opentrons repository*
