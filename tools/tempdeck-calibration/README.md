# Temperature Module Calibration Tool

A Windows GUI application for calibrating Opentrons Temperature Module Gen2 units.

## Features

- Connect to Temperature Module via USB serial
- Live temperature reading display
- Calculate calibration offset from reference thermometer
- Store calibrations in local database (by serial number)
- Generate printable labels with QR codes
- Export calibration history to CSV
- Future-ready: Supports M303 command when firmware is modified

## Quick Start

### Option 1: Run from Python

```bash
# Install dependencies
pip install pyserial qrcode pillow

# Run the tool
python tempdeck_calibration_tool.py
```

### Option 2: Build Standalone .exe (Recommended for Distribution)

```bash
# Install PyInstaller
pip install pyinstaller

# Build single executable
pyinstaller --onefile --windowed --name "TempDeck_Calibration_Tool" tempdeck_calibration_tool.py

# The .exe will be in the 'dist' folder
```

## Calibration Procedure

### Equipment Needed

1. Computer with USB port
2. Temperature Module Gen2
3. USB cable (Type B)
4. Calibrated reference thermometer (NIST traceable recommended)
5. Thermal paste or thermal pad (optional, for better probe contact)

### Step-by-Step Instructions

#### 1. Setup

1. Connect the Temperature Module to your computer via USB
2. Power on the module (USB provides power)
3. Launch the Calibration Tool

#### 2. Connect

1. Select the correct COM port from the dropdown
2. Click **Connect**
3. Verify the serial number and model are displayed

#### 3. Stabilize Temperature

1. Allow the module to sit at room temperature for **5 minutes**
2. Do NOT set a target temperature - leave it idle
3. Watch the temperature reading stabilize (should stop changing)

#### 4. Measure Reference Temperature

1. Place your reference thermometer probe flat on the **center** of the aluminum plate
2. Wait for the reference thermometer to stabilize (1-2 minutes)
3. Note the reference thermometer reading

#### 5. Calculate Offset

1. Enter the reference thermometer reading in the tool
2. Click **Calculate Offset**
3. The offset will be displayed (should typically be between -3°C and +3°C)

#### 6. Save Calibration

1. Enter your name (technician field)
2. Add any notes (optional)
3. Click **Save Calibration**

#### 7. Generate Label

1. Click **Generate Label** to preview the calibration label
2. Click **Save Label Image** to save as PNG
3. Print the label and attach to the module

## Calibration Data

### Storage Location

Calibrations are stored in `calibration_database.json` in the same folder as the tool.

### Data Format

```json
{
  "calibrations": {
    "TDV03P1234": {
      "serial": "TDV03P1234",
      "model": "temp_deck_v20",
      "offset": 1.5,
      "technician": "John Smith",
      "notes": "Annual calibration",
      "timestamp": "2024-01-15T14:30:00",
      "date": "2024-01-15",
      "time": "14:30:00"
    }
  }
}
```

### QR Code Contents

The QR code on each label contains:

```json
{
  "type": "tempdeck_calibration",
  "serial": "TDV03P1234",
  "offset": 1.5,
  "date": "2024-01-15",
  "version": "1.0"
}
```

## How to Apply Calibration

### For Customers

Since the calibration is stored externally (not in the module), customers have these options:

#### Option A: Use This Tool

Run the calibration tool, connect the module, and the stored offset will be loaded automatically. The tool displays the corrected temperature.

#### Option B: Manual Adjustment

When setting temperatures in protocols, adjust by the offset:

- If offset is **+1.5°C**: Module reads low, so set target 1.5°C lower
- If offset is **-1.0°C**: Module reads high, so set target 1.0°C higher

**Example:** Label shows offset +1.5°C. To achieve 37.0°C actual:
- Set protocol temperature to: 37.0 - 1.5 = **35.5°C**

#### Option C: Modified Firmware (Future)

With modified firmware supporting M303:
- Offset is stored in module EEPROM
- Automatically applied by firmware
- No manual adjustment needed

## Troubleshooting

### Cannot Connect to Module

1. Check USB cable connection
2. Verify correct COM port selected (may need to try different ports)
3. Close other programs that may be using the serial port
4. Try unplugging and reconnecting the module

### Large Offset Warning

Offsets larger than ±5°C may indicate:
- Incorrect reference thermometer reading
- Temperature not stabilized
- Module hardware fault

Verify your reference thermometer is calibrated and try again.

### No COM Ports Listed

1. Install USB drivers if needed
2. Check Device Manager for unknown devices
3. Try a different USB port or cable

## File Outputs

| File | Description |
|------|-------------|
| `calibration_database.json` | All calibration records |
| `calibration_label_SERIAL.png` | Individual label images |
| `calibrations_YYYYMMDD.csv` | Exported spreadsheet |

## Technical Notes

### Communication Protocol

- Baud rate: 115200
- Commands: Standard G-code (M105, M115, etc.)
- Terminator: `\r\n\r\n`

### Temperature Module Commands Used

| Command | Description |
|---------|-------------|
| M105 | Get current temperature |
| M115 | Get device info (serial, model) |
| M303 | Get/set calibration offset (future firmware) |

## Version History

- **v1.0.0** - Initial release
  - Serial connection and temperature reading
  - Offset calculation
  - Local database storage
  - Label generation with QR codes
  - CSV export

## License

Internal tool for Opentrons service use.
