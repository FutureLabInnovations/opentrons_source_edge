# Opentrons Module Maintenance & Diagnostic Tools

Standalone diagnostic scripts for testing and maintaining Opentrons OT-2 and Flex robot modules via direct USB serial connection.

## Supported Modules

| Module | Script | OT-2 | Flex |
|--------|--------|------|------|
| Temperature Module | `diagnose_temperature_module.py` | Yes | Yes |
| Magnetic Module | `diagnose_magnetic_module.py` | Yes | Yes |
| Thermocycler | `diagnose_thermocycler.py` | Yes | Yes |
| Heater-Shaker | `diagnose_heater_shaker.py` | Yes | Yes |
| Flex Stacker | `diagnose_flex_stacker.py` | No | Yes |

## Quick Start

### 1. Install Requirements

```bash
pip install -r requirements.txt
```

### 2. Connect Module

Connect the module to your computer via USB cable. Note the COM port:
- **Windows**: `COM3`, `COM6`, etc. (check Device Manager)
- **Linux**: `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
- **macOS**: `/dev/cu.usbserial-*`, `/dev/tty.usbmodem*`

### 3. Run Diagnostic

```bash
# Basic diagnostic (sensor readings only)
python diagnose_temperature_module.py --port COM6

# Full test (includes heating/motor operations)
python diagnose_temperature_module.py --port COM6 --full-test

# Save report to file
python diagnose_temperature_module.py --port COM6 --full-test --save-report
```

### 4. Using Master Runner

```bash
# List available modules
python run_all_diagnostics.py --list

# Detect available serial ports
python run_all_diagnostics.py --detect-ports

# Run specific module diagnostic
python run_all_diagnostics.py --module tempdeck --port COM6

# Full test with report
python run_all_diagnostics.py --module thermocycler --port COM6 -f -s
```

## Module-Specific Usage

### Temperature Module

```bash
python diagnose_temperature_module.py --port COM6 --full-test
```

Tests:
- Connection and device info
- Temperature sensor reading
- Heating cycle (37C)
- Cooling cycle (15C)
- Deactivation

### Magnetic Module

```bash
python diagnose_magnetic_module.py --port COM6 --full-test
```

Tests:
- Connection and device info
- Position reading
- Homing operation
- Plate probe
- Movement operations
- Engage/disengage cycle

### Thermocycler

```bash
python diagnose_thermocycler.py --port COM6 --full-test
```

Tests:
- Connection and generation detection (Gen1/Gen2)
- Device info
- Lid status
- Lid and plate temperature reading
- Lid open/close operations
- Lid heating cycle
- Plate heating cycle
- Plate lift (Gen2 only)

### Heater-Shaker

```bash
python diagnose_heater_shaker.py --port COM6 --full-test
```

Tests:
- Connection and device info
- Temperature reading
- RPM reading
- Latch status
- Home command
- Latch open/close
- Heating cycle
- Shaking cycle (500 RPM)

### Flex Stacker

```bash
python diagnose_flex_stacker.py --port COM6 --full-test
```

Tests:
- Connection and device info
- Limit switch status (all axes)
- Platform sensors
- Door switch
- Installation detection
- Motor enable/stop
- LED control
- Z-axis homing and movement

## Communication Protocol Reference

All modules use serial UART with these common parameters:

| Parameter | Value |
|-----------|-------|
| Baud Rate | 115200 |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |

Module-specific terminators:

| Module | Terminator | ACK Pattern |
|--------|------------|-------------|
| Temperature Module | `\r\n\r\n` | `ok\r\nok\r\n` |
| Magnetic Module | `\r\n\r\n` | `ok\r\nok\r\n` |
| Thermocycler Gen1 | `\r\n` | `ok\r\nok\r\n` |
| Thermocycler Gen2 | `\n` | ` OK\n` |
| Heater-Shaker | `\n` | `OK\n` |
| Flex Stacker | `\n` | `OK\n` |

## Safety Warnings

1. **Disconnect power** before any physical maintenance
2. **Deactivate heaters** before disconnecting modules
3. **Home modules** before performing move operations
4. **Keep hands clear** when running motor tests
5. **Remove labware** before running full diagnostic tests
6. **Allow cooling** before handling heated modules

## Troubleshooting

### Connection Issues

1. Check USB cable connection
2. Verify correct COM port
3. Ensure no other software is using the port
4. Try different USB port
5. Check Windows Device Manager for driver issues

### No Response from Module

1. Increase timeout: Most scripts have configurable timeout
2. Check baud rate matches (115200)
3. Reset module by power cycling
4. Check for firmware issues

### Partial Responses

1. Module may need firmware update
2. Check cable for damage
3. Try reducing baud rate if supported

## Report Format

Diagnostic reports include:
- Timestamp
- Module identification (serial, model, firmware)
- Test results (PASS/FAIL/WARN)
- Sensor readings
- Error messages (if any)
- Summary and recommendations

## Architecture Documentation

See `ARCHITECTURE_GUIDE.md` for detailed technical information about:
- OT-2 and Flex robot architecture
- Module communication protocols
- G-code command reference
- Source code locations

## Support

For issues with these diagnostic tools:
- Check the Opentrons GitHub: https://github.com/Opentrons
- Review module documentation in the repository
- Contact Opentrons support for hardware issues
