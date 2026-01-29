# Build and Flash Instructions

How to compile the modified firmware and flash it to a Temperature Module Gen2.

## Prerequisites

### 1. Arduino IDE
Download from: https://www.arduino.cc/en/software

### 2. Board Support
In Arduino IDE:
1. Go to **Tools → Board → Boards Manager**
2. Search for "Arduino AVR Boards"
3. Install it (includes ATmega32u4 support)

### 3. Select Board
1. Go to **Tools → Board → Arduino AVR Boards**
2. Select **Arduino Leonardo** (uses same ATmega32u4 chip)

## Get the Source Code

### Option A: Clone from Opentrons
```bash
git clone https://github.com/Opentrons/opentrons-modules.git
cd opentrons-modules/arduino-modules/temp-deck/temp-deck-arduino
```

### Option B: Download ZIP
1. Go to https://github.com/Opentrons/opentrons-modules
2. Click **Code → Download ZIP**
3. Extract and navigate to `arduino-modules/temp-deck/temp-deck-arduino`

## Apply the Patch

1. **Replace these files** with the patched versions from this folder:
   - `gcode.h`
   - `gcode.cpp`
   - `memory.h`
   - `memory.cpp`

2. **Modify `temp-deck-arduino.ino`** following `PATCH_INSTRUCTIONS.md`

## Compile

1. Open `temp-deck-arduino.ino` in Arduino IDE
2. Go to **Sketch → Verify/Compile** (or press Ctrl+R)
3. Fix any errors (usually missing libraries or typos)
4. Note the .hex file location shown in output

### Finding the .hex File

After successful compile, Arduino IDE shows something like:
```
Sketch uses 15000 bytes (52%) of program storage space.
"/tmp/arduino_build_123456/temp-deck-arduino.ino.hex"
```

Copy this .hex file - you'll need it for flashing.

## Flash the Module

### Method 1: Using the Calibration Tool (Recommended)

The calibration tool can flash firmware:
1. Connect module via USB
2. Open calibration tool
3. Use **Tools → Flash Firmware** (if implemented)
4. Select your .hex file

### Method 2: Using avrdude Directly

#### Step 1: Put Module in Bootloader Mode

Connect to module via serial and send:
```
dfu
```

The module will reset into bootloader mode. You have about 8 seconds to flash.

#### Step 2: Find the Bootloader Port

**Windows:**
- Open Device Manager
- Look for new COM port (e.g., COM7)

**Linux:**
```bash
ls /dev/ttyACM*
# or
dmesg | tail
```

**Mac:**
```bash
ls /dev/cu.usbmodem*
```

#### Step 3: Flash with avrdude

**Windows:**
```cmd
avrdude -v -patmega32u4 -cavr109 -PCOM7 -b57600 -D -Uflash:w:temp-deck-arduino.ino.hex:i
```

**Linux/Mac:**
```bash
avrdude -v -patmega32u4 -cavr109 -P/dev/ttyACM0 -b57600 -D -Uflash:w:temp-deck-arduino.ino.hex:i
```

### Important Flags Explained

| Flag | Meaning |
|------|---------|
| `-p atmega32u4` | Target chip |
| `-c avr109` | Bootloader protocol |
| `-P COM7` | Serial port (change to yours) |
| `-b 57600` | Baud rate |
| `-D` | **CRITICAL: Don't erase EEPROM** (preserves serial/model/calibration) |
| `-U flash:w:file.hex:i` | Write hex file to flash |

### Expected Output

```
avrdude: AVR device initialized and ready to accept instructions
avrdude: Device signature = 0x1e9587 (ATmega32U4)
avrdude: reading input file "temp-deck-arduino.ino.hex"
avrdude: writing flash (15000 bytes)
avrdude: 15000 bytes of flash written
avrdude: verifying flash memory against temp-deck-arduino.ino.hex
avrdude: 15000 bytes of flash verified

avrdude done.  Thank you.
```

## Verify the Flash

After flashing, the module reboots automatically. Test it:

```
# Connect via serial (115200 baud)

# Check device info (should show serial/model - proves EEPROM preserved)
M115
→ serial:TDV03PXXXX model:temp_deck_v20 version:v2.x.x ok

# Check M303 works (NEW command)
M303
→ O:0.00 ok

# Test setting offset
M303 O1.5
→ O:1.50 ok

# Check temperature reflects offset
M105
→ T:none C:26.50 ok  (should be ~1.5° higher than actual)
```

## Troubleshooting

### "avrdude: butterfly_recv(): programmer is not responding"

- Bootloader timed out (8 second window)
- Solution: Send `dfu` again and flash immediately

### "avrdude: ser_open(): can't open device"

- Wrong COM port
- Solution: Check Device Manager for correct port

### "avrdude: verification error"

- Flash corrupted
- Solution: Try again, check USB cable

### Module doesn't respond after flash

- Flash may have failed
- Solution: Put in bootloader mode (hold reset while plugging USB), reflash

### Serial/Model shows as blank after flash

- EEPROM was erased (forgot -D flag!)
- Solution: Re-run eepromWriter to restore serial/model

## Batch Flashing Multiple Modules

Create a script for production:

**Windows (flash_module.bat):**
```batch
@echo off
echo Flashing Temperature Module...
echo.
echo 1. Send 'dfu' command to module
echo 2. Press Enter when ready
pause

avrdude -v -patmega32u4 -cavr109 -P%1 -b57600 -D -Uflash:w:temp-deck-calibrated.hex:i

echo.
echo Flash complete. Verify with M303 command.
pause
```

Usage: `flash_module.bat COM7`

**Linux (flash_module.sh):**
```bash
#!/bin/bash
PORT=${1:-/dev/ttyACM0}
echo "Flashing to $PORT..."
echo "Send 'dfu' to module, then press Enter"
read

avrdude -v -patmega32u4 -cavr109 -P$PORT -b57600 -D -Uflash:w:temp-deck-calibrated.hex:i

echo "Flash complete. Verify with M303 command."
```

Usage: `./flash_module.sh /dev/ttyACM0`

## Creating a Pre-built .hex for Distribution

Once you've verified the patched firmware works:

1. Compile in Arduino IDE
2. Copy the .hex file to a known location
3. Rename to something clear: `temp-deck-v2.0.1-calibration.hex`
4. Distribute this file to service team
5. They only need avrdude to flash, not Arduino IDE

## Safety Notes

1. **Always use -D flag** - Preserves EEPROM (serial, model, calibration)
2. **Don't interrupt flashing** - Can brick the module
3. **Keep original firmware backup** - In case you need to restore
4. **Test thoroughly** - Before deploying to customers
