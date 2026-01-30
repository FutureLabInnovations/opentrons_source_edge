# Opentrons Flex Module Diagnostics Suite

A comprehensive diagnostics package for validating all Opentrons Flex-compatible modules. This suite provides automated testing, pass/fail reporting, and service documentation generation.

## Supported Modules

| Module | Type | Diagnostic Coverage |
|--------|------|---------------------|
| **Temperature Module Gen2** | Active | Temperature control, sensor validation, deactivation |
| **Heater-Shaker Module** | Active | Heating, shaking, latch operations, sensor validation |
| **Thermocycler Module Gen2** | Active | Lid operations, block/lid temperature, profile execution |
| **Absorbance Plate Reader** | Active | Initialization, wavelength configuration, measurement |
| **Magnetic Block** | Passive | Physical inspection guidance, workflow verification |
| **Flex Stacker Module** | Active | Latch, platform state, axis homing, LED control |
| **HEPA/UV Module** | Active | Fan control, UV activation (with safety checks) |

> **Note**: Only Thermocycler Gen2 is compatible with Flex. Gen1 cannot be used with the gripper.

## Quick Start

### Option 1: Run as Opentrons Protocol (Recommended)

1. **Upload the protocol** to your Opentrons App:
   - Use `protocols/diagnostic_protocol.py`
   - This runs diagnostics through the standard Protocol API

2. **Configure modules** in the protocol:
   ```python
   # Edit MODULES_TO_TEST in diagnostic_protocol.py
   MODULES_TO_TEST = {
       "temperature_module": {"slot": "D1", "enabled": True},
       "heater_shaker": {"slot": "D1", "enabled": False},
       "thermocycler": {"slot": None, "enabled": True},
       # ... etc
   }
   ```

3. **Run the protocol** and check the run log for results

### Option 2: Use as Python Package

```python
from flex_module_diagnostics import DiagnosticsRunner

def run(protocol):
    runner = DiagnosticsRunner(
        protocol_context=protocol,
        technician_name="Your Name"
    )

    # Run all detected modules
    report = runner.run_detected_modules()

    # Or run specific modules
    report = runner.run_all_diagnostics(
        modules=["temperature_module", "thermocycler"],
        skip_modules=["hepa_uv"]
    )
```

## Directory Structure

```
flex-module-diagnostics/
├── __init__.py              # Package initialization
├── runner.py                # Master diagnostics runner
├── README.md                # This file
├── diagnostics/
│   ├── __init__.py
│   ├── temperature_module.py
│   ├── heater_shaker.py
│   ├── thermocycler.py
│   ├── absorbance_reader.py
│   ├── magnetic_block.py
│   ├── flex_stacker.py
│   └── hepa_uv.py
├── protocols/
│   ├── __init__.py
│   └── diagnostic_protocol.py   # Upload this to Opentrons App
├── reports/                 # Generated reports go here
└── utils/
    ├── __init__.py
    ├── base.py              # Base diagnostic class
    ├── logger.py            # Logging utilities
    └── types.py             # Type definitions
```

## Diagnostic Tests by Module

### Temperature Module
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Detection | Detect and read serial number | S/N readable |
| Temperature Sensor | Read current temperature | Valid reading (-40°C to 150°C) |
| Set Temperature | Heat to 37°C | Within ±1°C of target |
| Deactivate | Stop heating | Status returns to idle |

### Heater-Shaker Module
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Detection | Detect and read serial number | S/N readable |
| Temperature Sensor | Read current temperature | Valid reading |
| Speed Sensor | Read current RPM | Valid reading |
| Latch Open/Close | Test labware latch | Status changes correctly |
| Heating | Heat to 37°C | Within ±1°C of target |
| Shaking | Shake at 200 RPM | Within ±50 RPM of target |
| Deactivate | Stop all operations | Status returns to idle |

### Thermocycler Module
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Detection | Detect and read serial number | S/N readable |
| Block/Lid Sensors | Read temperatures | Valid readings |
| Open/Close Lid | Test lid mechanism | Position changes correctly |
| Block Temperature | Heat block to 37°C | Within ±1°C of target |
| Lid Temperature | Heat lid to 50°C | Within ±2°C of target |
| Temperature Profile | Execute simple profile | Profile completes |
| Deactivate | Stop all operations | Lid opens, temps deactivate |

### Absorbance Plate Reader
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Detection | Detect and read serial number | S/N readable |
| Lid Status | Check lid presence | Status readable |
| Device Status | Check plate presence | Status readable |
| Supported Wavelengths | Query wavelength range | Returns list |
| Initialize Single Mode | Configure measurement | Initialization succeeds |
| Initialize Multi Mode | Configure multi-wavelength | Initialization succeeds |
| Open/Close Lid | Test lid with gripper | Lid moves correctly |
| Perform Read | Execute measurement | Data returned (if plate present) |

### Magnetic Block (Passive Module)
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Loaded | Verify protocol configuration | Module context created |
| Labware Support | Check labware loading | Method available |
| Physical Inspection | Manual verification | See checklist |
| Magnetic Function | Manual verification | Beads separate correctly |

> **Important**: Magnetic Block has no electronic communication. Physical and magnetic function must be verified manually.

### Flex Stacker Module
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Module Detection | Detect and read serial number | S/N readable |
| Module Status | Read latch/platform/door state | States readable |
| Open/Close Latch | Test latch mechanism | State changes correctly |
| Home All Axes | Home X, Z, L axes | Homing completes |
| LED Control | Test status LED | LED toggles |
| TOF Sensor | Verify sensor availability | Sensor accessible |

### HEPA/UV Module
| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Fan State | Read fan status/RPM | State readable |
| UV State | Read UV status/safety | State readable |
| Activate Fan | Run at 50% duty cycle | Fan spins up |
| Deactivate Fan | Stop fan | Fan stops |
| UV Safety Check | Verify interlocks | Safety relay status readable |
| UV Light Test | Brief UV activation | UV activates (if safe) |

> **Important**: HEPA/UV uses CAN bus, not USB. Requires direct hardware access.

## Output Reports

The diagnostics suite generates two report formats:

### JSON Report
Machine-readable format for automated processing:
```json
{
  "report_date": "2024-01-15T10:30:00",
  "technician_name": "Service Tech",
  "overall_status": "PASS",
  "robot_info": {...},
  "module_results": [...]
}
```

### Markdown Report
Human-readable service report with:
- Summary table
- Module status overview
- Detailed test results per module
- Recommendations
- Signature line for technician

## Safe Operating Limits

All tests use conservative parameters:

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| Temperature test point | 37°C | Body temp, fast to reach, safe |
| Heater-Shaker RPM | 200 | Minimum speed, safe without labware |
| Thermocycler lid temp | 50°C | Low enough for quick testing |
| UV test duration | 5 seconds | Brief test, safety verified first |
| Fan duty cycle | 50% | Moderate speed for verification |

## Troubleshooting

### Module Not Detected

1. **Check USB/CAN connection** - Verify cable is properly connected
2. **Check deck seating** - Ensure module is properly placed
3. **Restart robot** - Power cycle and rescan modules
4. **Check port** - Try different USB port on robot

### Temperature Not Reaching Target

1. **Check thermal block** - Clean any debris
2. **Check ventilation** - Ensure vents are clear
3. **Check ambient temperature** - May affect heat/cool times
4. **Check thermal paste** - May need service attention

### Thermocycler Lid Issues

1. **Check for obstructions** - Nothing blocking lid path
2. **Check lid seal** - Inspect for damage
3. **Listen for motor** - Should hear motor when operating

### HEPA/UV Not Responding

1. **Check CAN bus** - Not a USB module
2. **Check enclosure** - Must be properly closed
3. **Safety interlocks** - Verify all engaged

## Evidence / API References

This diagnostics suite was built using:

### Official Documentation
- [Flex Modules Overview](https://docs.opentrons.com/flex/modules/)
- [Temperature Module](https://docs.opentrons.com/v2/new_modules.html#temperature-module)
- [Thermocycler Module](https://docs.opentrons.com/v2/new_modules.html#thermocycler-module)
- [Heater-Shaker Module](https://docs.opentrons.com/v2/new_modules.html#heater-shaker-module)
- [Magnetic Block](https://docs.opentrons.com/flex/modules/magnetic-block/)
- [Absorbance Plate Reader](https://docs.opentrons.com/v2/absorbance_plate_reader.html)

### Source Code References
- Module Contexts: `api/src/opentrons/protocol_api/module_contexts.py`
- Hardware Control: `api/src/opentrons/hardware_control/modules/`
- Module Types: `shared-data/python/opentrons_shared_data/module/types.py`
- Module Definitions: `shared-data/module/definitions/3/`
- Protocol Engine Commands: `api/src/opentrons/protocol_engine/commands/`
- HEPA/UV Control: `hardware/opentrons_hardware/hardware_control/hepa_uv_settings.py`

## Requirements

- Opentrons Flex robot
- Software version compatible with API 2.16+
- Python 3.10+
- Modules to be tested installed on deck

## License

Part of the Opentrons open-source project.
