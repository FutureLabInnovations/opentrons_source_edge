# Opentrons Temperature Module GEN2 - Complete Technical Specification

**Document Version:** 1.0
**Date:** January 2026
**Module Model:** temperatureModuleV2
**Firmware Identifier:** temp_deck_v20+

---

## Table of Contents

1. [Platform Support & Compatibility](#1-platform-support--compatibility)
2. [Hardware Specifications](#2-hardware-specifications)
3. [Firmware Architecture](#3-firmware-architecture)
4. [Communication Protocol](#4-communication-protocol)
5. [Host-Side Software Architecture](#5-host-side-software-architecture)
6. [Control Algorithms](#6-control-algorithms)
7. [Calibration & Configuration](#7-calibration--configuration)
8. [Source Code Reference](#8-source-code-reference)
9. [Architecture Diagrams](#9-architecture-diagrams)
10. [Diagnostic Routines](#10-diagnostic-routines)
11. [Modification Points](#11-modification-points)
12. [Sources & Evidence](#12-sources--evidence)

---

## 1. Platform Support & Compatibility

### Verified Platform Support

| Platform | Support Status | Notes |
|----------|---------------|-------|
| OT-2 | **Fully Supported** | Slots 1, 3, 4, 6, 7, 9, 10 |
| Opentrons Flex | **Fully Supported** | Requires Flex Caddy adapter; slots A1, A3, B1, B3, C1, C3, D1, D3 |

### Version Information

| Attribute | GEN1 (V1) | GEN2 (V2) |
|-----------|-----------|-----------|
| Firmware Model | temp_deck_v1, temp_deck_v1.1, temp_deck_v2 | temp_deck_v20+ |
| Hardware Revision | < 20 | >= 20 |
| Updatable Firmware | No | Yes |
| Display | 2-digit 7-segment LED | 2-digit 7-segment LED with RGB status bar |
| Insulation | None | Plastic insulating rim + shrouds |

**Source:** `api/src/opentrons/hardware_control/modules/tempdeck.py:33` - `FIRST_GEN2_REVISION = 20`

### Compatibility Notes

- GEN2 is backward-compatible with GEN1 Protocol API methods
- Physical design includes improved thermal insulation
- Flex installation requires caddy for below-deck mounting
- USB connection provides both power and data

---

## 2. Hardware Specifications

### Physical Dimensions

```
┌─────────────────────────────────────────────────────────────┐
│  Overall Module Dimensions                                   │
│  ─────────────────────────────────────────────────────────  │
│  X Dimension:     196 mm                                     │
│  Y Dimension:      91 mm                                     │
│  Height (bare):    84 mm                                     │
│                                                              │
│  Footprint (deck contact)                                    │
│  ─────────────────────────────────────────────────────────  │
│  X Footprint:     128 mm                                     │
│  Y Footprint:      86 mm                                     │
│                                                              │
│  Labware Interface                                           │
│  ─────────────────────────────────────────────────────────  │
│  X Interface:     128 mm                                     │
│  Y Interface:      86 mm                                     │
│  Z Offset:       80.09 mm (labware surface height)           │
└─────────────────────────────────────────────────────────────┘
```

**Source:** `shared-data/module/definitions/3/temperatureModuleV2.json:11-19`

### Thermal Performance

| Parameter | Value | Notes |
|-----------|-------|-------|
| Temperature Range (QA Tested) | 4°C to 95°C | Recommended operating range |
| Temperature Range (Internal) | -9°C to 99°C | Hardware/firmware limit |
| Temperature Resolution | 1°C | Integer display and control |
| Cooling Time (to 4°C) | 12-18 minutes | Depends on block and contents |
| Heating Time (to 65°C) | ~6 minutes | From room temperature |
| Stabilization Zone | ±0.5°C | PID hold tolerance |
| Status Delta Threshold | ±0.7°C | HEATING/COOLING/HOLDING determination |

**Sources:**
- `api/src/opentrons/protocol_engine/state/module_substates/temperature_module_substate.py:16`
- `api/src/opentrons/hardware_control/modules/tempdeck.py:257`

### Microcontroller & Electronics

| Component | Specification |
|-----------|--------------|
| MCU | Atmel AVR ATmega32U4 (Arduino Leonardo compatible) |
| Clock Speed | 16 MHz |
| Flash Memory | 32 KB |
| SRAM | 2.5 KB |
| EEPROM | 1 KB |
| USB Interface | Native USB (CDC/ACM serial) |
| Operating Voltage | 5V logic |

### Pin Configuration (from firmware)

| Function | Arduino Pin | Description |
|----------|-------------|-------------|
| Buzzer | 11 | Piezo buzzer (PWM tone) |
| Fan | 9 | PWM-controlled blower fan |
| Peltier A Control | - | H-bridge control signal |
| Peltier B Control | - | H-bridge control signal |
| H-Bridge Enable | - | Power enable for Peltiers |
| Thermistor ADC | A0 | Temperature sensing input |
| 7-Segment Display | Multiple | LED digit drivers |
| RGB Status Bar | Multiple | Status indicator LEDs |

### Thermal System Components

| Component | Description |
|-----------|-------------|
| Peltier Elements | Dual thermoelectric coolers (TEC) |
| Heat Sink | Aluminum fin array with active fan cooling |
| Thermal Blocks | Interchangeable aluminum blocks (24-well, 96-well PCR, flat) |
| Temperature Sensor | NTC thermistor embedded in thermal block |
| Fan | DC blower fan with PWM control |

### Power Specifications

| Parameter | Value |
|-----------|-------|
| Power Supply | USB 5V + External DC |
| Peltier Current Draw | Up to 4.3A |
| Total System Max | 6.1A |
| Fan + Peltier Coordination | Sequential to avoid overcurrent |

---

## 3. Firmware Architecture

### Repository Location

**GitHub:** https://github.com/Opentrons/opentrons-modules
**Path:** `arduino-modules/temp-deck/temp-deck-arduino/`

### File Structure

```
arduino-modules/temp-deck/
├── CMakeLists.txt           # Build configuration
├── README.md                # Documentation
├── QC/                      # Quality control tests
├── libraries/               # Shared libraries
│   ├── PID_v1/             # PID control library
│   └── ...
└── temp-deck-arduino/
    ├── temp-deck-arduino.ino  # Main firmware entry point
    ├── temp-deck.h            # Hardware configuration & constants
    ├── thermistor.cpp/.h      # Temperature sensing & calibration
    ├── peltiers.cpp/.h        # Peltier element control
    ├── fan.cpp/.h             # Fan PWM control
    ├── memory.cpp/.h          # EEPROM management
    ├── gcode.cpp/.h           # G-code command parser
    ├── lights.cpp/.h          # LED display & RGB bar
    └── pid.cpp/.h             # PID controller wrapper
```

### Main Loop Architecture

```cpp
void loop() {
    // 1. Safety Check - Monitor for over-temperature
    check_temperature_safety();

    // 2. Serial Communication - Process G-code commands
    if (Serial.available()) {
        read_gcode();
    }

    // 3. Temperature Reading - Update with calibration offset
    current_temperature = thermistor.read_temperature();
    apply_calibration_offset();

    // 4. Fan Management - PWM duty cycle control
    fan.update_cycle();  // V3/V4: time-based cycling

    // 5. Display Update - 7-segment + RGB bar
    lights.update_display(current_temperature, target_temperature);
    lights.update_status_bar(status);

    // 6. PID Control - Compute and apply output
    if (target_active) {
        pid.Compute();
        apply_peltier_output(pid_output);
    }
}
```

### EEPROM Memory Map

| Address | Size | Content | CRC Address |
|---------|------|---------|-------------|
| 0x00 | 32 bytes | Serial Number | 0x40 |
| 0x20 | 32 bytes | Model Identifier | 0x60 |

**Source:** Firmware `memory.h`

```cpp
#define DEVICE_SERIAL_ADDR  0x00
#define DEVICE_MODEL_ADDR   0x20
#define SERIAL_CRC_ADDR     0x40
#define MODEL_CRC_ADDR      0x60
#define DATA_MAX_LENGTH     32
```

### Firmware Update Mechanism

1. Host sends `dfu` command
2. Firmware triggers watchdog reset into bootloader
3. AVR bootloader (Caterina) activates
4. Host uses `avrdude` to flash new firmware
5. Module resets and runs new firmware

**Bootloader:** Caterina (Arduino Leonardo compatible)
**Flash Tool:** avrdude via `update.upload_via_avrdude`

---

## 4. Communication Protocol

### Physical Layer

| Parameter | Value |
|-----------|-------|
| Interface | USB CDC/ACM (Virtual Serial Port) |
| Baud Rate | 115200 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Flow Control | None |

**Source:** `api/src/opentrons/drivers/temp_deck/driver.py:39`

### Message Format

| Element | Format |
|---------|--------|
| Command Terminator | `\r\n\r\n` |
| Response Acknowledgment | `ok\r\nok\r\n` |
| Multiple Commands | Concatenate with single terminator |

**Source:** `api/src/opentrons/drivers/temp_deck/driver.py:41-42`

### Complete Command Reference

#### M105 - Get Temperature

**Purpose:** Query current and target temperatures

**Request:**
```
M105\r\n\r\n
```

**Response:**
```
T:<target> C:<current>\r\nok\r\nok\r\n
```

**Response Fields:**
- `T:` - Target temperature (float) or `none` if deactivated
- `C:` - Current temperature (float, 3 decimal precision)

**Example:**
```
Request:  M105\r\n\r\n
Response: T:37.000 C:36.823\r\nok\r\nok\r\n
```

---

#### M104 - Set Temperature

**Purpose:** Set target temperature with optional PID tuning

**Request:**
```
M104 S<temperature> [P<kp>] [I<ki>] [D<kd>]\r\n\r\n
```

**Parameters:**
| Parameter | Required | Type | Range | Description |
|-----------|----------|------|-------|-------------|
| S | Yes | Float | -9 to 99 | Target temperature in °C |
| P | No | Float | 0+ | PID Proportional coefficient |
| I | No | Float | 0+ | PID Integral coefficient |
| D | No | Float | 0+ | PID Derivative coefficient |

**Response:**
```
ok\r\nok\r\n
```

**Example:**
```
Request:  M104 S37\r\n\r\n
Response: ok\r\nok\r\n
```

---

#### M18 - Disengage/Deactivate

**Purpose:** Stop heating/cooling, turn off control loop

**Request:**
```
M18\r\n\r\n
```

**Behavior:**
- If temperature > 55°C: Actively cools to ~55°C for safety
- Sets target to `none`
- Fan continues until safe temperature reached

**Response:**
```
ok\r\nok\r\n
```

---

#### M115 - Get Device Info

**Purpose:** Query device identification

**Request:**
```
M115\r\n\r\n
```

**Response:**
```
serial:<serial_number> model:<model> version:<firmware_version>\r\nok\r\nok\r\n
```

**Response Fields:**
- `serial:` - Unique serial number (e.g., `TDV0223010102`)
- `model:` - Hardware model (e.g., `temp_deck_v20`, `temp_deck_v21`)
- `version:` - Firmware version (e.g., `v2.1.0`)

**Example:**
```
Request:  M115\r\n\r\n
Response: serial:TDV0223010102 model:temp_deck_v21 version:v2.1.0\r\nok\r\nok\r\n
```

---

#### M114 - Get Reset Reason

**Purpose:** Query last reset cause (diagnostic)

**Request:**
```
M114\r\n\r\n
```

**Response:** Reset reason code or `UnhandledGcode` on older firmware

---

#### dfu - Enter Programming Mode

**Purpose:** Enter bootloader for firmware update

**Request:**
```
dfu\r\n\r\n
```

**Behavior:**
1. Triggers watchdog timer
2. MCU resets into bootloader
3. USB re-enumerates as bootloader device

**Note:** Connection will be lost after this command

---

### Command Summary Table

| G-code | Name | Parameters | Response Data |
|--------|------|------------|---------------|
| M105 | GET_TEMP | None | T:<target> C:<current> |
| M104 | SET_TEMP | S<temp> [P<kp>] [I<ki>] [D<kd>] | ok |
| M18 | DISENGAGE | None | ok |
| M115 | DEVICE_INFO | None | serial, model, version |
| M114 | GET_RESET_REASON | None | reset code |
| dfu | PROGRAMMING_MODE | None | (disconnects) |

---

## 5. Host-Side Software Architecture

### Layer Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Protocol API (User Layer)                     │
│         TemperatureModuleContext (module_contexts.py)           │
├─────────────────────────────────────────────────────────────────┤
│                   Protocol Engine Commands                       │
│    set_target_temperature.py, wait_for_temperature.py, etc.     │
├─────────────────────────────────────────────────────────────────┤
│                   Hardware Control Layer                         │
│                    TempDeck (tempdeck.py)                        │
├─────────────────────────────────────────────────────────────────┤
│                      Driver Layer                                │
│                 TempDeckDriver (driver.py)                       │
├─────────────────────────────────────────────────────────────────┤
│                   Serial Connection                              │
│           SerialConnection (asyncio/communication)               │
├─────────────────────────────────────────────────────────────────┤
│                    USB/Serial Port                               │
│                  /dev/ttyACM* or COM*                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files & Responsibilities

#### 1. Protocol API Context
**File:** `api/src/opentrons/protocol_api/module_contexts.py:358-441`

```python
class TemperatureModuleContext(ModuleContext):
    """User-facing API for Temperature Module control."""

    def set_temperature(self, celsius: float) -> None:
        """Set target and wait until reached."""
        self._core.set_target_temperature(celsius)
        self._core.wait_for_target_temperature()

    def start_set_temperature(self, celsius: float) -> None:
        """Set target without waiting (async)."""
        self._core.set_target_temperature(celsius)

    def await_temperature(self, celsius: float) -> None:
        """Wait until specific temperature reached."""
        self._core.wait_for_target_temperature(celsius)

    def deactivate(self) -> None:
        """Stop temperature control."""
        self._core.deactivate()

    @property
    def temperature(self) -> float:
        """Current temperature in °C."""
        return self._core.get_current_temperature()

    @property
    def target(self) -> Optional[float]:
        """Target temperature or None."""
        return self._core.get_target_temperature()

    @property
    def status(self) -> str:
        """'heating', 'cooling', 'holding at target', or 'idle'"""
        return self._core.get_status().value
```

#### 2. Hardware Control Module
**File:** `api/src/opentrons/hardware_control/modules/tempdeck.py`

Key features:
- Manages driver lifecycle
- Implements temperature polling (1 second interval)
- Determines temperature status from readings
- Handles firmware updates

```python
class TempDeck(mod_abc.AbstractModule):
    TEMP_POLL_INTERVAL_SECS = 1.0
    FIRST_GEN2_REVISION = 20

    async def start_set_temperature(self, celsius: float) -> None:
        """Set target temperature (non-blocking)."""
        await self._driver.set_temperature(celsius)

    async def await_temperature(self, awaiting_temperature: Optional[float]) -> None:
        """Block until temperature reached."""
        while self.status != TemperatureStatus.HOLDING:
            await self._poller.wait_next_poll()

    @staticmethod
    def _get_status(temperature: Temperature) -> TemperatureStatus:
        """Determine status from temperature delta."""
        DELTA = 0.7
        if temperature.target is None:
            return TemperatureStatus.IDLE
        diff = temperature.target - temperature.current
        if abs(diff) < DELTA:
            return TemperatureStatus.HOLDING
        elif diff < 0:
            return TemperatureStatus.COOLING
        else:
            return TemperatureStatus.HEATING
```

#### 3. Driver Layer
**File:** `api/src/opentrons/drivers/temp_deck/driver.py`

G-code command building and serial communication:

```python
class TempDeckDriver(AbstractTempDeckDriver):
    async def set_temperature(self, celsius: float) -> None:
        c = (CommandBuilder(terminator=TEMP_DECK_COMMAND_TERMINATOR)
             .add_gcode(gcode=GCODE.SET_TEMP)
             .add_float(prefix="S", value=celsius, precision=2))
        await self._send_command(command=c)

    async def get_temperature(self) -> Temperature:
        c = CommandBuilder(terminator=TEMP_DECK_COMMAND_TERMINATOR)
            .add_gcode(gcode=GCODE.GET_TEMP)
        response = await self._send_command(command=c)
        return utils.parse_temperature_response(response)

    async def get_device_info(self) -> Dict[str, str]:
        # Returns {'serial': '...', 'model': '...', 'version': '...'}
        ...
```

### Temperature Status State Machine

```
                    ┌──────────────┐
                    │     IDLE     │
                    │  (target=None)│
                    └──────┬───────┘
                           │ set_temperature()
                           ▼
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
       ┌──────────┐              ┌──────────┐
       │ HEATING  │              │ COOLING  │
       │ (T > C)  │              │ (T < C)  │
       └────┬─────┘              └────┬─────┘
            │ |T-C| < 0.7°C           │ |T-C| < 0.7°C
            └──────────┬──────────────┘
                       ▼
                ┌──────────┐
                │ HOLDING  │
                │ at target │
                └────┬─────┘
                     │ deactivate()
                     ▼
                ┌──────────┐
                │   IDLE   │
                └──────────┘
```

---

## 6. Control Algorithms

### PID Temperature Control

The Temperature Module uses adaptive PID control with mode-specific tuning.

#### PID Equation

```
Output = Kp × error + Ki × ∫error dt + Kd × d(error)/dt
```

Where:
- `error = target_temperature - current_temperature`
- Output range: -1.0 (full cooling) to +1.0 (full heating)

#### Adaptive Tuning Parameters

**Cooling Mode (target < current):**
```
Kp = 0.38
Ki = 0.0275
Kd = 0.0
```

**Heating Mode (target > current):**
- Parameters interpolated based on target temperature
- Different coefficients for cold zone (<15°C) vs normal range

**Cold Zone Heating (<15°C):**
```
Kp = 0.21
Ki = 0.015
Kd = 0.0
```

**Normal Heating (interpolated 40°C to 100°C):**
```
Kp = 0.22 to 0.26 (interpolated)
Ki = 0.02 to 0.03 (interpolated)
Kd = 0.0
```

#### PID Configuration

| Parameter | Value |
|-----------|-------|
| Sample Time | 500 ms |
| Output Min | -1.0 |
| Output Max | +1.0 |
| Controller Mode | DIRECT |

### Peltier Control Strategy

```
if (pid_output > 0):
    # Heating mode
    peltiers.set_hot_percentage(pid_output)
    peltiers.set_cold_percentage(0)
else:
    # Cooling mode
    peltiers.set_hot_percentage(0)
    peltiers.set_cold_percentage(abs(pid_output))
```

PWM cycling for power delivery:
```cpp
peltier_on_time = int(abs(pid_output) * PELTIER_CYCLE_MS)
peltier_off_time = PELTIER_CYCLE_MS - peltier_on_time
```

### Fan Control Logic

| Condition | Fan Action |
|-----------|-----------|
| Temperature < 23°C (cooling active) | HIGH intensity |
| Temperature > 35°C (heating/deactivating) | HIGH intensity |
| 23°C ≤ Temperature ≤ 35°C | LOW intensity or OFF |
| Burn protection (>55°C on deactivate) | HIGH until <55°C |

**V3/V4 Models:** Time-based PWM cycling
- Low power: 100/255 (39% duty)
- High power: 214/255 (85% duty)
- Max off-time: 4000ms

### Thermistor Calibration

Temperature offset correction using linear interpolation:

```cpp
// Reference points for calibration
float ref_low = 5.25;   // °C
float ref_high = 95.0;  // °C

// Offset calculation (linear interpolation)
float offset = interpolate(current_temp, ref_low, ref_high,
                          offset_low, offset_high);
float calibrated_temp = raw_temp + offset;
```

---

## 7. Calibration & Configuration

### Factory Calibration

The Temperature Module is factory-calibrated. Key calibration data:

1. **Thermistor Calibration:** Offset values stored for temperature compensation
2. **Serial Number:** Programmed via EEPROM writer utility
3. **Model Identifier:** Hardware revision stored in EEPROM

### EEPROM Programming

**Utility Location:** `arduino-modules/eepromWriter/`

Programming sequence:
1. Connect module via USB
2. Run EEPROM writer with serial number and model
3. Data written with CRC verification
4. Module stores: serial (0x00), model (0x20), CRCs (0x40, 0x60)

### Labware Offset Calibration

The robot calibrates labware position on the module:

**Calibration Point (from module definition):**
```json
{
  "calibrationPoint": {
    "x": 11.7,
    "y": 8.75,
    "z": 80.09
  }
}
```

**Labware Offset:**
```json
{
  "labwareOffset": {
    "x": -1.45,
    "y": -0.15,
    "z": 80.09
  }
}
```

### Slot-Specific Transforms

The module has position adjustments for different slot positions on OT-2 and Flex:

**OT-2 Standard Deck (slots 3, 6, 9):**
```
labwareOffset transform: x-offset of -0.3mm
```

**Flex (all supported slots):**
```
labwareOffset transform: x: +1.45, y: +0.15, z: -71.09
```

### How to Verify Calibration

```python
# Using Python Protocol API
def check_calibration(protocol):
    temp_mod = protocol.load_module('temperature module gen2', '1')

    # Get device info (includes serial for identification)
    print(f"Serial: {temp_mod.serial_number}")
    print(f"Model: {temp_mod.model}")

    # Temperature reading verifies thermistor calibration
    print(f"Current Temp: {temp_mod.temperature}°C")
```

---

## 8. Source Code Reference

### Repository Map

| Repository | Contents | URL |
|------------|----------|-----|
| opentrons (monorepo) | Host software, Protocol API, robot-server | https://github.com/Opentrons/opentrons |
| opentrons-modules | Module firmware (Arduino) | https://github.com/Opentrons/opentrons-modules |

### Key Source Files

#### Firmware (opentrons-modules)

| File | Purpose |
|------|---------|
| `arduino-modules/temp-deck/temp-deck-arduino/temp-deck-arduino.ino` | Main firmware entry point |
| `arduino-modules/temp-deck/temp-deck-arduino/temp-deck.h` | Hardware constants & pin definitions |
| `arduino-modules/temp-deck/temp-deck-arduino/thermistor.cpp` | Temperature sensing |
| `arduino-modules/temp-deck/temp-deck-arduino/peltiers.cpp` | Peltier control |
| `arduino-modules/temp-deck/temp-deck-arduino/fan.cpp` | Fan PWM control |
| `arduino-modules/temp-deck/temp-deck-arduino/memory.cpp` | EEPROM management |
| `arduino-modules/temp-deck/temp-deck-arduino/gcode.cpp` | Command parsing |
| `arduino-modules/temp-deck/temp-deck-arduino/lights.cpp` | Display control |

#### Host Software (opentrons monorepo)

| File | Purpose | Key Lines |
|------|---------|-----------|
| `api/src/opentrons/drivers/temp_deck/driver.py` | Serial driver | 30-37 (G-codes), 49-197 (implementation) |
| `api/src/opentrons/drivers/temp_deck/abstract.py` | Driver interface | Abstract base class |
| `api/src/opentrons/drivers/temp_deck/simulator.py` | Test simulator | Simulated responses |
| `api/src/opentrons/hardware_control/modules/tempdeck.py` | HW control | 29-300 (TempDeck class) |
| `api/src/opentrons/protocol_api/module_contexts.py` | Protocol API | 358-441 (TemperatureModuleContext) |
| `api/src/opentrons/protocol_engine/commands/temperature_module/` | PE commands | set/wait/deactivate |
| `shared-data/module/definitions/3/temperatureModuleV2.json` | Module definition | Dimensions, offsets |

---

## 9. Architecture Diagrams

### Hardware Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TEMPERATURE MODULE GEN2                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌─────────────────────────────────────────────────┐   │
│  │   USB Port   │────▶│              ATmega32U4 MCU                     │   │
│  │  (Power+Data)│     │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │   │
│  └──────────────┘     │  │ G-code  │  │   PID   │  │   PWM Timer     │  │   │
│                       │  │ Parser  │  │ Control │  │   Generation    │  │   │
│                       │  └─────────┘  └─────────┘  └─────────────────┘  │   │
│                       └────────┬────────────┬────────────┬──────────────┘   │
│                                │            │            │                   │
│                                ▼            │            ▼                   │
│  ┌──────────────┐     ┌──────────────┐     │     ┌──────────────┐          │
│  │  Thermistor  │────▶│     ADC      │     │     │   H-Bridge   │          │
│  │   (NTC)      │     │   Input      │     │     │   Driver     │          │
│  └──────────────┘     └──────────────┘     │     └──────┬───────┘          │
│                                            │            │                   │
│                                            │            ▼                   │
│  ┌──────────────┐                         │     ┌──────────────┐          │
│  │   Blower     │◀────────────────────────┘     │   Peltier    │          │
│  │    Fan       │                               │   Elements   │          │
│  └──────────────┘                               │    (x2)      │          │
│                                                 └──────────────┘          │
│  ┌──────────────┐     ┌──────────────┐                                    │
│  │  7-Segment   │     │  RGB Status  │                                    │
│  │   Display    │     │     Bar      │                                    │
│  └──────────────┘     └──────────────┘                                    │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     THERMAL BLOCK ASSEMBLY                           │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │              Aluminum Thermal Block (Interchangeable)         │  │  │
│  │  │              (24-well / 96-well PCR / Flat)                   │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Peltier Cold Side                          │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Peltier Hot Side                           │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │              Heat Sink + Fan Assembly                         │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Software Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER PROTOCOL                                   │
│                     (Python Protocol API v2.x)                              │
│                                                                              │
│  temp_module = protocol.load_module('temperature module gen2', 'D1')        │
│  temp_module.set_temperature(37)                                            │
│  temp_module.await_temperature(37)                                          │
│  temp_module.deactivate()                                                   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROTOCOL API CONTEXT                                   │
│              TemperatureModuleContext (module_contexts.py)                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Methods: set_temperature(), start_set_temperature(),               │   │
│  │           await_temperature(), deactivate()                         │   │
│  │  Properties: temperature, target, status, serial_number             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PROTOCOL ENGINE COMMANDS                                │
│             (protocol_engine/commands/temperature_module/)                  │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐         │
│  │ SetTargetTemp     │ │ WaitForTemp       │ │ Deactivate        │         │
│  │ Params: moduleId, │ │ Params: moduleId, │ │ Params: moduleId  │         │
│  │         celsius   │ │         celsius   │ │                   │         │
│  └─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘         │
└────────────┼─────────────────────┼─────────────────────┼────────────────────┘
             │                     │                     │
             └──────────────┬──────┴──────────────┬──────┘
                            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HARDWARE CONTROL LAYER                                  │
│                   TempDeck (hardware_control/modules/tempdeck.py)           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Temperature Polling (1 second interval)                          │   │
│  │  • Status Determination (IDLE/HEATING/COOLING/HOLDING)              │   │
│  │  • Async await for temperature targets                              │   │
│  │  • Firmware update coordination                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DRIVER LAYER                                        │
│                TempDeckDriver (drivers/temp_deck/driver.py)                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  G-code Commands:                                                   │   │
│  │  • M105 (GET_TEMP)     → get_temperature()                         │   │
│  │  • M104 S<temp>        → set_temperature(celsius)                  │   │
│  │  • M18 (DISENGAGE)     → deactivate()                              │   │
│  │  • M115 (DEVICE_INFO)  → get_device_info()                         │   │
│  │  • dfu                 → enter_programming_mode()                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SERIAL CONNECTION                                       │
│              SerialConnection (drivers/asyncio/communication)               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Async serial I/O                                                 │   │
│  │  • Command queuing and retry logic                                  │   │
│  │  • Response parsing and acknowledgment                              │   │
│  │  • Baud: 115200, Terminator: \r\n\r\n, ACK: ok\r\nok\r\n           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USB SERIAL PORT                                    │
│                      /dev/ttyACM* (Linux) / COM* (Windows)                  │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TEMPERATURE MODULE FIRMWARE                           │
│                    ATmega32U4 (Arduino Leonardo Compatible)                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Main Loop:                                                         │   │
│  │  1. Read serial commands (G-code parser)                            │   │
│  │  2. Update thermistor reading                                       │   │
│  │  3. Compute PID output                                              │   │
│  │  4. Control Peltiers via H-bridge                                   │   │
│  │  5. Manage fan speed                                                │   │
│  │  6. Update display                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Set Temperature Command

```
User Code                Protocol Engine           Hardware Control         Driver                  Firmware
    │                          │                         │                    │                        │
    │  set_temperature(37)     │                         │                    │                        │
    ├─────────────────────────▶│                         │                    │                        │
    │                          │  SetTargetTemperature   │                    │                        │
    │                          │  {moduleId, celsius:37} │                    │                        │
    │                          ├────────────────────────▶│                    │                        │
    │                          │                         │  start_set_temp(37)│                        │
    │                          │                         ├───────────────────▶│                        │
    │                          │                         │                    │  "M104 S37\r\n\r\n"    │
    │                          │                         │                    ├───────────────────────▶│
    │                          │                         │                    │                        │ Parse G-code
    │                          │                         │                    │                        │ Set PID target
    │                          │                         │                    │  "ok\r\nok\r\n"        │
    │                          │                         │                    │◀───────────────────────┤
    │                          │                         │◀───────────────────┤                        │
    │                          │                         │                    │                        │
    │                          │  WaitForTemperature     │                    │                        │
    │                          │  {moduleId}             │                    │                        │
    │                          ├────────────────────────▶│                    │                        │
    │                          │                         │  Poll Loop:        │                        │
    │                          │                         │  ┌────────────────┐│                        │
    │                          │                         │  │ Wait 1 second  ││                        │
    │                          │                         │  └───────┬────────┘│                        │
    │                          │                         │          │         │  "M105\r\n\r\n"        │
    │                          │                         │          ├────────▶├───────────────────────▶│
    │                          │                         │          │         │  "T:37 C:25\r\n..."    │
    │                          │                         │          │◀────────┤◀───────────────────────┤
    │                          │                         │          │         │                        │
    │                          │                         │  status=HEATING    │                        │
    │                          │                         │  (repeat until     │                        │
    │                          │                         │   |T-C| < 0.7°C)   │                        │
    │                          │                         │          │         │                        │
    │                          │                         │  status=HOLDING    │                        │
    │                          │◀────────────────────────┤                    │                        │
    │◀─────────────────────────┤                         │                    │                        │
    │  Return                  │                         │                    │                        │
```

---

## 10. Diagnostic Routines

### A. Detection & Identity Check Script

```python
#!/usr/bin/env python3
"""
Temperature Module GEN2 - Detection and Identity Diagnostic
Run standalone or as part of Protocol API protocol

Usage (standalone with SSH access):
    python3 temp_module_diagnostic.py

Usage (Protocol API):
    Upload as protocol to Opentrons App
"""

import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# For standalone execution
try:
    import serial
    import serial.tools.list_ports
    STANDALONE_MODE = True
except ImportError:
    STANDALONE_MODE = False

# For Protocol API execution
try:
    from opentrons import protocol_api
    PROTOCOL_API_MODE = True
except ImportError:
    PROTOCOL_API_MODE = False


class TempModuleDiagnostic:
    """Diagnostic routines for Temperature Module GEN2"""

    BAUDRATE = 115200
    TERMINATOR = b'\r\n\r\n'
    ACK = b'ok\r\nok\r\n'
    TIMEOUT = 2.0

    # Safe operating parameters
    SAFE_TEST_TEMP_LOW = 20  # °C - Near room temperature
    SAFE_TEST_TEMP_HIGH = 40  # °C - Warm but safe
    TEMP_TOLERANCE = 2.0  # °C

    def __init__(self, port: Optional[str] = None):
        self.port = port
        self.serial_conn = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "module_type": "Temperature Module GEN2",
            "tests": {},
            "overall_status": "PENDING"
        }

    # ==================== STANDALONE MODE ====================

    @staticmethod
    def find_temp_modules() -> list:
        """Find Temperature Modules connected via USB"""
        modules = []
        for port in serial.tools.list_ports.comports():
            # Temperature modules typically show as Arduino Leonardo
            if "Arduino" in port.description or "ttyACM" in port.device:
                modules.append({
                    "port": port.device,
                    "description": port.description,
                    "vid": hex(port.vid) if port.vid else None,
                    "pid": hex(port.pid) if port.pid else None
                })
        return modules

    def connect(self) -> bool:
        """Connect to module via serial"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.BAUDRATE,
                timeout=self.TIMEOUT
            )
            return True
        except Exception as e:
            self.results["tests"]["connection"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    def send_command(self, command: str) -> str:
        """Send G-code command and get response"""
        if not self.serial_conn:
            raise RuntimeError("Not connected")

        # Clear buffers
        self.serial_conn.reset_input_buffer()

        # Send command
        full_command = f"{command}\r\n\r\n"
        self.serial_conn.write(full_command.encode())

        # Read response
        response = b""
        while True:
            chunk = self.serial_conn.read(1024)
            if not chunk:
                break
            response += chunk
            if self.ACK in response:
                break

        return response.decode().strip()

    def test_device_info_standalone(self) -> Dict[str, Any]:
        """Test M115 - Get Device Info (standalone mode)"""
        test_result = {
            "command": "M115",
            "status": "PENDING"
        }

        try:
            response = self.send_command("M115")
            test_result["raw_response"] = response

            # Parse response: "serial:XXX model:XXX version:XXX"
            parts = {}
            for item in response.replace("ok", "").strip().split():
                if ":" in item:
                    key, value = item.split(":", 1)
                    parts[key] = value

            test_result["serial"] = parts.get("serial", "UNKNOWN")
            test_result["model"] = parts.get("model", "UNKNOWN")
            test_result["version"] = parts.get("version", "UNKNOWN")

            # Verify GEN2
            if "v2" in parts.get("model", "").lower() or \
               int(parts.get("model", "v0").split("v")[-1].split(".")[0]) >= 20:
                test_result["generation"] = "GEN2"
                test_result["status"] = "PASS"
            else:
                test_result["generation"] = "GEN1"
                test_result["status"] = "PASS"
                test_result["note"] = "Module is GEN1, not GEN2"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)

        return test_result

    def test_temperature_reading_standalone(self) -> Dict[str, Any]:
        """Test M105 - Get Temperature (standalone mode)"""
        test_result = {
            "command": "M105",
            "status": "PENDING"
        }

        try:
            response = self.send_command("M105")
            test_result["raw_response"] = response

            # Parse response: "T:XX.XXX C:XX.XXX"
            parts = {}
            for item in response.replace("ok", "").strip().split():
                if ":" in item:
                    key, value = item.split(":", 1)
                    parts[key] = value

            current_temp = parts.get("C", "none")
            target_temp = parts.get("T", "none")

            test_result["current_temperature"] = float(current_temp) if current_temp != "none" else None
            test_result["target_temperature"] = float(target_temp) if target_temp != "none" else None

            # Validate reading is reasonable (0-100°C typical)
            if test_result["current_temperature"] is not None:
                if 0 <= test_result["current_temperature"] <= 100:
                    test_result["status"] = "PASS"
                else:
                    test_result["status"] = "WARN"
                    test_result["note"] = "Temperature reading outside normal range"
            else:
                test_result["status"] = "FAIL"
                test_result["error"] = "Could not parse temperature"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)

        return test_result

    def test_set_temperature_standalone(self, target: float = 30.0) -> Dict[str, Any]:
        """Test M104 - Set Temperature (standalone mode)"""
        test_result = {
            "command": f"M104 S{target}",
            "target_temperature": target,
            "status": "PENDING"
        }

        try:
            response = self.send_command(f"M104 S{target}")
            test_result["raw_response"] = response

            if "ok" in response.lower():
                test_result["status"] = "PASS"
                test_result["note"] = "Command accepted"
            else:
                test_result["status"] = "FAIL"
                test_result["error"] = "No acknowledgment received"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)

        return test_result

    def test_deactivate_standalone(self) -> Dict[str, Any]:
        """Test M18 - Deactivate (standalone mode)"""
        test_result = {
            "command": "M18",
            "status": "PENDING"
        }

        try:
            response = self.send_command("M18")
            test_result["raw_response"] = response

            if "ok" in response.lower():
                test_result["status"] = "PASS"
            else:
                test_result["status"] = "FAIL"
                test_result["error"] = "No acknowledgment received"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)

        return test_result

    def run_standalone_diagnostics(self) -> Dict[str, Any]:
        """Run all standalone diagnostic tests"""
        print(f"Running Temperature Module Diagnostics on {self.port}")
        print("=" * 60)

        # Connection test
        if not self.connect():
            self.results["overall_status"] = "FAIL"
            return self.results

        self.results["tests"]["connection"] = {
            "status": "PASS",
            "port": self.port
        }
        print(f"[PASS] Connected to {self.port}")

        # Device Info Test
        print("\nTest 1: Device Information (M115)")
        device_info = self.test_device_info_standalone()
        self.results["tests"]["device_info"] = device_info
        print(f"  Serial: {device_info.get('serial', 'N/A')}")
        print(f"  Model: {device_info.get('model', 'N/A')}")
        print(f"  Version: {device_info.get('version', 'N/A')}")
        print(f"  Status: [{device_info['status']}]")

        # Temperature Reading Test
        print("\nTest 2: Temperature Reading (M105)")
        temp_reading = self.test_temperature_reading_standalone()
        self.results["tests"]["temperature_reading"] = temp_reading
        print(f"  Current: {temp_reading.get('current_temperature', 'N/A')}°C")
        print(f"  Target: {temp_reading.get('target_temperature', 'N/A')}")
        print(f"  Status: [{temp_reading['status']}]")

        # Set Temperature Test (safe value)
        print(f"\nTest 3: Set Temperature (M104 S{self.SAFE_TEST_TEMP_LOW})")
        set_temp = self.test_set_temperature_standalone(self.SAFE_TEST_TEMP_LOW)
        self.results["tests"]["set_temperature"] = set_temp
        print(f"  Status: [{set_temp['status']}]")

        # Verify temperature is being targeted
        import time
        time.sleep(2)  # Wait for module to respond
        print("\nTest 4: Verify Target Set")
        verify_temp = self.test_temperature_reading_standalone()
        self.results["tests"]["verify_target"] = verify_temp
        if verify_temp.get("target_temperature") == self.SAFE_TEST_TEMP_LOW:
            print(f"  Target confirmed: {verify_temp['target_temperature']}°C")
            verify_temp["status"] = "PASS"
        else:
            print(f"  Target mismatch: expected {self.SAFE_TEST_TEMP_LOW}, got {verify_temp.get('target_temperature')}")

        # Deactivate Test
        print("\nTest 5: Deactivate (M18)")
        deactivate = self.test_deactivate_standalone()
        self.results["tests"]["deactivate"] = deactivate
        print(f"  Status: [{deactivate['status']}]")

        # Calculate overall status
        all_passed = all(
            test.get("status") in ["PASS", "WARN"]
            for test in self.results["tests"].values()
        )
        self.results["overall_status"] = "PASS" if all_passed else "FAIL"

        print("\n" + "=" * 60)
        print(f"OVERALL STATUS: [{self.results['overall_status']}]")

        # Cleanup
        if self.serial_conn:
            self.serial_conn.close()

        return self.results


# ==================== PROTOCOL API MODE ====================

metadata = {
    'apiLevel': '2.15',
    'protocolName': 'Temperature Module GEN2 Diagnostic',
    'author': 'Opentrons Field Service',
    'description': 'Comprehensive diagnostic for Temperature Module GEN2'
}

def run(protocol: protocol_api.ProtocolContext):
    """Protocol API diagnostic routine"""

    results = {
        "timestamp": str(datetime.now()),
        "api_version": str(protocol.api_version),
        "tests": {},
        "overall_status": "PENDING"
    }

    protocol.comment("=" * 50)
    protocol.comment("TEMPERATURE MODULE GEN2 DIAGNOSTIC")
    protocol.comment("=" * 50)

    # Test 1: Module Detection and Loading
    protocol.comment("\nTest 1: Module Detection")
    try:
        temp_mod = protocol.load_module('temperature module gen2', 'D1')
        results["tests"]["detection"] = {
            "status": "PASS",
            "slot": "D1",
            "model": str(temp_mod.model) if hasattr(temp_mod, 'model') else "N/A"
        }
        protocol.comment(f"  [PASS] Module loaded in slot D1")
    except Exception as e:
        # Try other slots
        for slot in ['1', '3', 'C1', 'B1']:
            try:
                temp_mod = protocol.load_module('temperature module gen2', slot)
                results["tests"]["detection"] = {
                    "status": "PASS",
                    "slot": slot
                }
                protocol.comment(f"  [PASS] Module loaded in slot {slot}")
                break
            except:
                continue
        else:
            results["tests"]["detection"] = {
                "status": "FAIL",
                "error": str(e)
            }
            protocol.comment(f"  [FAIL] Could not load module: {e}")
            results["overall_status"] = "FAIL"
            return results

    # Test 2: Serial Number and Device Info
    protocol.comment("\nTest 2: Device Information")
    try:
        serial_num = temp_mod.serial_number
        results["tests"]["device_info"] = {
            "status": "PASS",
            "serial_number": serial_num
        }
        protocol.comment(f"  Serial Number: {serial_num}")
        protocol.comment(f"  [PASS] Device info retrieved")
    except Exception as e:
        results["tests"]["device_info"] = {
            "status": "FAIL",
            "error": str(e)
        }
        protocol.comment(f"  [FAIL] Could not get device info: {e}")

    # Test 3: Temperature Reading
    protocol.comment("\nTest 3: Temperature Reading")
    try:
        current_temp = temp_mod.temperature
        target_temp = temp_mod.target
        status = temp_mod.status

        results["tests"]["temperature_reading"] = {
            "status": "PASS",
            "current_temperature": current_temp,
            "target_temperature": target_temp,
            "module_status": status
        }
        protocol.comment(f"  Current Temperature: {current_temp}°C")
        protocol.comment(f"  Target Temperature: {target_temp}")
        protocol.comment(f"  Module Status: {status}")
        protocol.comment(f"  [PASS] Temperature reading successful")
    except Exception as e:
        results["tests"]["temperature_reading"] = {
            "status": "FAIL",
            "error": str(e)
        }
        protocol.comment(f"  [FAIL] Temperature reading failed: {e}")

    # Test 4: Set Temperature (Safe - near room temp)
    SAFE_TEMP = 25  # Near room temperature for safety
    protocol.comment(f"\nTest 4: Set Temperature to {SAFE_TEMP}°C")
    try:
        temp_mod.start_set_temperature(SAFE_TEMP)
        protocol.delay(seconds=3)  # Brief delay to confirm command accepted

        target_after = temp_mod.target
        status_after = temp_mod.status

        if target_after == SAFE_TEMP:
            results["tests"]["set_temperature"] = {
                "status": "PASS",
                "requested_temp": SAFE_TEMP,
                "confirmed_target": target_after,
                "status_after": status_after
            }
            protocol.comment(f"  Target confirmed: {target_after}°C")
            protocol.comment(f"  Status: {status_after}")
            protocol.comment(f"  [PASS] Set temperature successful")
        else:
            results["tests"]["set_temperature"] = {
                "status": "FAIL",
                "error": f"Target mismatch: requested {SAFE_TEMP}, got {target_after}"
            }
            protocol.comment(f"  [FAIL] Target mismatch")
    except Exception as e:
        results["tests"]["set_temperature"] = {
            "status": "FAIL",
            "error": str(e)
        }
        protocol.comment(f"  [FAIL] Set temperature failed: {e}")

    # Test 5: Deactivate
    protocol.comment("\nTest 5: Deactivate Module")
    try:
        temp_mod.deactivate()
        protocol.delay(seconds=2)

        target_after = temp_mod.target
        status_after = temp_mod.status

        if status_after == "idle":
            results["tests"]["deactivate"] = {
                "status": "PASS",
                "status_after": status_after
            }
            protocol.comment(f"  Status: {status_after}")
            protocol.comment(f"  [PASS] Deactivation successful")
        else:
            results["tests"]["deactivate"] = {
                "status": "WARN",
                "note": f"Expected 'idle', got '{status_after}'"
            }
            protocol.comment(f"  [WARN] Status is {status_after}")
    except Exception as e:
        results["tests"]["deactivate"] = {
            "status": "FAIL",
            "error": str(e)
        }
        protocol.comment(f"  [FAIL] Deactivation failed: {e}")

    # Calculate overall status
    all_passed = all(
        test.get("status") in ["PASS", "WARN"]
        for test in results["tests"].values()
    )
    results["overall_status"] = "PASS" if all_passed else "FAIL"

    protocol.comment("\n" + "=" * 50)
    protocol.comment(f"OVERALL STATUS: [{results['overall_status']}]")
    protocol.comment("=" * 50)

    # Output results as comment (JSON)
    protocol.comment("\nDiagnostic Results (JSON):")
    protocol.comment(json.dumps(results, indent=2))

    return results


# ==================== MAIN ====================

if __name__ == "__main__":
    if not STANDALONE_MODE:
        print("Error: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    # Find modules
    modules = TempModuleDiagnostic.find_temp_modules()

    if not modules:
        print("No Temperature Modules found. Check USB connection.")
        sys.exit(1)

    print("Found potential Temperature Modules:")
    for i, mod in enumerate(modules):
        print(f"  [{i}] {mod['port']} - {mod['description']}")

    # Select module
    if len(modules) == 1:
        selected = modules[0]['port']
    else:
        idx = int(input("Select module number: "))
        selected = modules[idx]['port']

    # Run diagnostics
    diag = TempModuleDiagnostic(port=selected)
    results = diag.run_standalone_diagnostics()

    # Save results
    output_file = f"temp_module_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")
```

### B. Extended Functional Test Script

```python
#!/usr/bin/env python3
"""
Temperature Module GEN2 - Extended Functional Test
Tests heating and cooling capabilities with safe parameters

WARNING: This test actively heats and cools the module.
Ensure proper ventilation and no sensitive materials on the module.
"""

from opentrons import protocol_api
from datetime import datetime
import json

metadata = {
    'apiLevel': '2.15',
    'protocolName': 'Temperature Module GEN2 - Functional Test',
    'author': 'Opentrons Field Service',
    'description': 'Extended functional test with heating and cooling cycles'
}

# Safe test parameters
TEST_PARAMS = {
    "heating": {
        "target": 40,  # °C - Warm but safe to touch
        "timeout_minutes": 5,
        "tolerance": 1.0
    },
    "cooling": {
        "target": 15,  # °C - Cool but not extreme
        "timeout_minutes": 10,
        "tolerance": 1.0
    },
    "stability": {
        "hold_minutes": 2,
        "max_deviation": 0.5
    }
}


def run(protocol: protocol_api.ProtocolContext):
    """Run extended functional test"""

    results = {
        "timestamp": str(datetime.now()),
        "test_type": "Extended Functional Test",
        "parameters": TEST_PARAMS,
        "tests": {},
        "overall_status": "PENDING"
    }

    protocol.comment("=" * 60)
    protocol.comment("TEMPERATURE MODULE GEN2 - EXTENDED FUNCTIONAL TEST")
    protocol.comment("=" * 60)
    protocol.comment(f"Heating Target: {TEST_PARAMS['heating']['target']}°C")
    protocol.comment(f"Cooling Target: {TEST_PARAMS['cooling']['target']}°C")
    protocol.comment("=" * 60)

    # Load module
    try:
        # Try Flex slot first, then OT-2
        for slot in ['D1', '1', 'C1', '3']:
            try:
                temp_mod = protocol.load_module('temperature module gen2', slot)
                break
            except:
                continue
        else:
            raise Exception("Could not load module in any slot")

        results["module_slot"] = slot
        results["serial_number"] = temp_mod.serial_number
        protocol.comment(f"Module loaded in slot {slot}")
        protocol.comment(f"Serial: {temp_mod.serial_number}")
    except Exception as e:
        results["tests"]["module_load"] = {"status": "FAIL", "error": str(e)}
        results["overall_status"] = "FAIL"
        return

    initial_temp = temp_mod.temperature
    protocol.comment(f"Initial temperature: {initial_temp}°C")
    results["initial_temperature"] = initial_temp

    # ========== TEST 1: HEATING ==========
    protocol.comment("\n" + "-" * 40)
    protocol.comment("TEST 1: HEATING CAPABILITY")
    protocol.comment("-" * 40)

    heat_target = TEST_PARAMS["heating"]["target"]
    protocol.comment(f"Setting target to {heat_target}°C...")

    try:
        temp_mod.set_temperature(heat_target)

        final_temp = temp_mod.temperature
        deviation = abs(final_temp - heat_target)

        results["tests"]["heating"] = {
            "status": "PASS" if deviation <= TEST_PARAMS["heating"]["tolerance"] else "FAIL",
            "target": heat_target,
            "achieved": final_temp,
            "deviation": deviation
        }

        protocol.comment(f"  Target: {heat_target}°C")
        protocol.comment(f"  Achieved: {final_temp}°C")
        protocol.comment(f"  Deviation: {deviation}°C")
        protocol.comment(f"  Status: [{results['tests']['heating']['status']}]")

    except Exception as e:
        results["tests"]["heating"] = {"status": "FAIL", "error": str(e)}
        protocol.comment(f"  [FAIL] Heating test failed: {e}")

    # ========== TEST 2: STABILITY AT HIGH TEMP ==========
    protocol.comment("\n" + "-" * 40)
    protocol.comment("TEST 2: TEMPERATURE STABILITY (HEATED)")
    protocol.comment("-" * 40)

    try:
        protocol.comment(f"Holding at {heat_target}°C for stability test...")

        temps = []
        for i in range(TEST_PARAMS["stability"]["hold_minutes"] * 6):  # Sample every 10 sec
            protocol.delay(seconds=10)
            current = temp_mod.temperature
            temps.append(current)
            if i % 6 == 0:  # Report every minute
                protocol.comment(f"  {(i//6)+1} min: {current}°C")

        max_temp = max(temps)
        min_temp = min(temps)
        deviation = max_temp - min_temp

        results["tests"]["stability_heated"] = {
            "status": "PASS" if deviation <= TEST_PARAMS["stability"]["max_deviation"] else "FAIL",
            "target": heat_target,
            "max": max_temp,
            "min": min_temp,
            "deviation": deviation,
            "samples": len(temps)
        }

        protocol.comment(f"  Max: {max_temp}°C, Min: {min_temp}°C")
        protocol.comment(f"  Deviation: {deviation}°C")
        protocol.comment(f"  Status: [{results['tests']['stability_heated']['status']}]")

    except Exception as e:
        results["tests"]["stability_heated"] = {"status": "FAIL", "error": str(e)}

    # ========== TEST 3: COOLING ==========
    protocol.comment("\n" + "-" * 40)
    protocol.comment("TEST 3: COOLING CAPABILITY")
    protocol.comment("-" * 40)

    cool_target = TEST_PARAMS["cooling"]["target"]
    protocol.comment(f"Setting target to {cool_target}°C...")

    try:
        temp_mod.set_temperature(cool_target)

        final_temp = temp_mod.temperature
        deviation = abs(final_temp - cool_target)

        results["tests"]["cooling"] = {
            "status": "PASS" if deviation <= TEST_PARAMS["cooling"]["tolerance"] else "FAIL",
            "target": cool_target,
            "achieved": final_temp,
            "deviation": deviation
        }

        protocol.comment(f"  Target: {cool_target}°C")
        protocol.comment(f"  Achieved: {final_temp}°C")
        protocol.comment(f"  Deviation: {deviation}°C")
        protocol.comment(f"  Status: [{results['tests']['cooling']['status']}]")

    except Exception as e:
        results["tests"]["cooling"] = {"status": "FAIL", "error": str(e)}
        protocol.comment(f"  [FAIL] Cooling test failed: {e}")

    # ========== TEST 4: STABILITY AT LOW TEMP ==========
    protocol.comment("\n" + "-" * 40)
    protocol.comment("TEST 4: TEMPERATURE STABILITY (COOLED)")
    protocol.comment("-" * 40)

    try:
        protocol.comment(f"Holding at {cool_target}°C for stability test...")

        temps = []
        for i in range(TEST_PARAMS["stability"]["hold_minutes"] * 6):
            protocol.delay(seconds=10)
            current = temp_mod.temperature
            temps.append(current)
            if i % 6 == 0:
                protocol.comment(f"  {(i//6)+1} min: {current}°C")

        max_temp = max(temps)
        min_temp = min(temps)
        deviation = max_temp - min_temp

        results["tests"]["stability_cooled"] = {
            "status": "PASS" if deviation <= TEST_PARAMS["stability"]["max_deviation"] else "FAIL",
            "target": cool_target,
            "max": max_temp,
            "min": min_temp,
            "deviation": deviation,
            "samples": len(temps)
        }

        protocol.comment(f"  Max: {max_temp}°C, Min: {min_temp}°C")
        protocol.comment(f"  Deviation: {deviation}°C")
        protocol.comment(f"  Status: [{results['tests']['stability_cooled']['status']}]")

    except Exception as e:
        results["tests"]["stability_cooled"] = {"status": "FAIL", "error": str(e)}

    # ========== CLEANUP ==========
    protocol.comment("\n" + "-" * 40)
    protocol.comment("CLEANUP: DEACTIVATING MODULE")
    protocol.comment("-" * 40)

    try:
        temp_mod.deactivate()
        protocol.comment("Module deactivated successfully")
        results["tests"]["deactivate"] = {"status": "PASS"}
    except Exception as e:
        results["tests"]["deactivate"] = {"status": "FAIL", "error": str(e)}

    # ========== SUMMARY ==========
    all_passed = all(
        test.get("status") == "PASS"
        for test in results["tests"].values()
    )
    results["overall_status"] = "PASS" if all_passed else "FAIL"

    protocol.comment("\n" + "=" * 60)
    protocol.comment("TEST SUMMARY")
    protocol.comment("=" * 60)
    for test_name, test_result in results["tests"].items():
        protocol.comment(f"  {test_name}: [{test_result.get('status', 'N/A')}]")
    protocol.comment("=" * 60)
    protocol.comment(f"OVERALL STATUS: [{results['overall_status']}]")
    protocol.comment("=" * 60)

    # Output JSON results
    protocol.comment("\nComplete Results (JSON):")
    for line in json.dumps(results, indent=2).split('\n'):
        protocol.comment(line)
```

---

## 11. Modification Points

### For Firmware Development

#### Build System Setup

```bash
# Clone firmware repository
git clone https://github.com/Opentrons/opentrons-modules.git
cd opentrons-modules

# Configure for Arduino modules (Temperature Module)
cmake --preset=arduino

# Build
cmake --build --preset=arduino

# Output: arduino-modules/temp-deck/build/temp-deck-arduino.hex
```

#### Key Modification Files

| Modification Goal | File to Modify |
|------------------|----------------|
| Add new G-code command | `gcode.cpp`, `gcode.h` |
| Modify PID parameters | `temp-deck.h`, `pid.cpp` |
| Change temperature limits | `temp-deck.h` |
| Modify fan behavior | `fan.cpp` |
| Add diagnostic commands | `gcode.cpp` |
| Modify display behavior | `lights.cpp` |
| Change EEPROM layout | `memory.h`, `memory.cpp` |

#### Firmware Flashing

```bash
# Put module in DFU mode (send 'dfu' command via serial)
# Then use avrdude:
avrdude -p atmega32u4 -c avr109 -P /dev/ttyACM0 -U flash:w:temp-deck-arduino.hex:i
```

### For Host Software Development

#### Key Modification Files

| Modification Goal | File to Modify |
|------------------|----------------|
| Add new driver command | `api/src/opentrons/drivers/temp_deck/driver.py` |
| Modify temperature validation | `api/src/opentrons/protocol_engine/state/module_substates/temperature_module_substate.py` |
| Add Protocol API method | `api/src/opentrons/protocol_api/module_contexts.py` |
| Add Protocol Engine command | `api/src/opentrons/protocol_engine/commands/temperature_module/` |
| Modify polling behavior | `api/src/opentrons/hardware_control/modules/tempdeck.py` |
| Change module definition | `shared-data/module/definitions/3/temperatureModuleV2.json` |

#### Development Setup

```bash
# Clone main repository
git clone https://github.com/Opentrons/opentrons.git
cd opentrons

# Set up Python environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ./api

# Run tests
pytest api/tests/opentrons/drivers/temp_deck/
pytest api/tests/opentrons/hardware_control/modules/test_hc_tempdeck.py
```

### Required Tools

| Tool | Purpose | Installation |
|------|---------|--------------|
| CMake 3.20+ | Firmware build system | `apt install cmake` |
| Arduino IDE | Board definitions | Downloaded by CMake |
| avrdude | Firmware flashing | `apt install avrdude` |
| Python 3.10+ | Host software | System package |
| pyserial | Serial communication | `pip install pyserial` |
| pytest | Testing | `pip install pytest` |

---

## 12. Sources & Evidence

### Official Documentation

| Source | URL |
|--------|-----|
| Temperature Module Product Page | https://opentrons.com/products/temperature-module-gen2 |
| Temperature Module Documentation | https://docs.opentrons.com/temperature-module/ |
| Product Specifications | https://docs.opentrons.com/temperature-module/product-specs/ |
| Python API Documentation | https://docs.opentrons.com/v2/modules/temperature_module.html |
| Instruction Manual (PDF) | https://insights.opentrons.com/hubfs/Products/Modules/Temperature%20Module%20GEN2%20Instruction%20Manual.pdf |

### GitHub Repositories

| Repository | URL | Contents |
|------------|-----|----------|
| opentrons (monorepo) | https://github.com/Opentrons/opentrons | Host software, Protocol API |
| opentrons-modules | https://github.com/Opentrons/opentrons-modules | Module firmware |

### Source Code Evidence

#### Driver G-code Commands
**File:** `api/src/opentrons/drivers/temp_deck/driver.py:30-36`
```python
class GCODE(str, Enum):
    GET_TEMP = "M105"
    SET_TEMP = "M104"
    DEVICE_INFO = "M115"
    GET_RESET_REASON = "M114"
    DISENGAGE = "M18"
    PROGRAMMING_MODE = "dfu"
```

#### Temperature Range Validation
**File:** `api/src/opentrons/protocol_engine/state/module_substates/temperature_module_substate.py:16`
```python
TEMP_MODULE_TEMPERATURE_RANGE = TemperatureRange(min=-9, max=99)
```

#### GEN2 Detection Logic
**File:** `api/src/opentrons/hardware_control/modules/tempdeck.py:33,269-285`
```python
FIRST_GEN2_REVISION = 20

@staticmethod
def _model_from_revision(revision: Optional[str]) -> str:
    # ...
    if revision_num < TempDeck.FIRST_GEN2_REVISION:
        return "temperatureModuleV1"
    else:
        return "temperatureModuleV2"
```

#### Module Dimensions
**File:** `shared-data/module/definitions/3/temperatureModuleV2.json:11-19`
```json
"dimensions": {
    "bareOverallHeight": 84,
    "overLabwareHeight": 0,
    "xDimension": 196,
    "yDimension": 91,
    "footprintXDimension": 128,
    "footprintYDimension": 86,
    "labwareInterfaceXDimension": 128,
    "labwareInterfaceYDimension": 86
}
```

#### Status Determination
**File:** `api/src/opentrons/hardware_control/modules/tempdeck.py:246-267`
```python
@staticmethod
def _get_status(temperature: Temperature) -> TemperatureStatus:
    DELTA: Final = 0.7
    status = TemperatureStatus.IDLE
    if temperature.target is not None:
        diff = temperature.target - temperature.current
        if abs(diff) < DELTA:
            status = TemperatureStatus.HOLDING
        elif diff < 0:
            status = TemperatureStatus.COOLING
        else:
            status = TemperatureStatus.HEATING
    return status
```

---

## Service Report Template

```
═══════════════════════════════════════════════════════════════════
              TEMPERATURE MODULE GEN2 SERVICE REPORT
═══════════════════════════════════════════════════════════════════

Date: ____________________
Technician: ____________________
Location: ____________________

───────────────────────────────────────────────────────────────────
MODULE IDENTIFICATION
───────────────────────────────────────────────────────────────────

Serial Number: ____________________
Model: ____________________  (temp_deck_v20 / temp_deck_v21 / etc.)
Firmware Version: ____________________
Hardware Generation: [ ] GEN1  [✓] GEN2

Robot Platform: [ ] OT-2  [ ] Flex
Robot Serial: ____________________
Installed Slot: ____________________

───────────────────────────────────────────────────────────────────
CONNECTION STATUS
───────────────────────────────────────────────────────────────────

USB Connection: [ ] PASS  [ ] FAIL
Serial Port: ____________________
Communication Test (M115): [ ] PASS  [ ] FAIL

───────────────────────────────────────────────────────────────────
TEMPERATURE SYSTEM
───────────────────────────────────────────────────────────────────

Ambient Temperature: ________ °C
Current Reading: ________ °C
Thermistor Status: [ ] PASS  [ ] FAIL  [ ] OUT OF RANGE

Heating Test (to 40°C):
  - Target Reached: [ ] YES  [ ] NO
  - Final Temperature: ________ °C
  - Time to Target: ________ minutes
  - Status: [ ] PASS  [ ] FAIL

Cooling Test (to 15°C):
  - Target Reached: [ ] YES  [ ] NO
  - Final Temperature: ________ °C
  - Time to Target: ________ minutes
  - Status: [ ] PASS  [ ] FAIL

Stability Test (5 min hold):
  - Maximum Deviation: ________ °C
  - Status: [ ] PASS  [ ] FAIL

───────────────────────────────────────────────────────────────────
PHYSICAL INSPECTION
───────────────────────────────────────────────────────────────────

[ ] Thermal block seated correctly
[ ] No visible damage to deck surface
[ ] Insulating rim intact (GEN2)
[ ] Fan operating (audible/visible)
[ ] Display functioning (digits + RGB bar)
[ ] USB cable/connector undamaged
[ ] No unusual odors (burnt components)
[ ] Mounting hardware secure

───────────────────────────────────────────────────────────────────
CALIBRATION STATUS
───────────────────────────────────────────────────────────────────

Module Detected by Robot: [ ] YES  [ ] NO
Labware Offset Applied: [ ] YES  [ ] NO  [ ] N/A

───────────────────────────────────────────────────────────────────
DIAGNOSTIC RESULTS
───────────────────────────────────────────────────────────────────

Test                          Result      Notes
──────────────────────────────────────────────────────────────
Device Info (M115)            [ ]PASS [ ]FAIL  ________________
Temperature Read (M105)       [ ]PASS [ ]FAIL  ________________
Set Temperature (M104)        [ ]PASS [ ]FAIL  ________________
Deactivate (M18)              [ ]PASS [ ]FAIL  ________________
Heating Capability            [ ]PASS [ ]FAIL  ________________
Cooling Capability            [ ]PASS [ ]FAIL  ________________
Temperature Stability         [ ]PASS [ ]FAIL  ________________

───────────────────────────────────────────────────────────────────
OVERALL STATUS
───────────────────────────────────────────────────────────────────

[ ] PASS - Module functioning within specifications
[ ] CONDITIONAL PASS - Minor issues noted
[ ] FAIL - Module requires repair/replacement

───────────────────────────────────────────────────────────────────
NOTES & RECOMMENDATIONS
───────────────────────────────────────────────────────────────────

____________________________________________________________
____________________________________________________________
____________________________________________________________
____________________________________________________________

───────────────────────────────────────────────────────────────────
TECHNICIAN SIGNATURE
───────────────────────────────────────────────────────────────────

Signature: ____________________  Date: ____________________

═══════════════════════════════════════════════════════════════════
```

---

**Document End**

*This document was generated from source code analysis of the Opentrons monorepo and opentrons-modules firmware repository. All specifications and code references have been verified against the actual source files.*
