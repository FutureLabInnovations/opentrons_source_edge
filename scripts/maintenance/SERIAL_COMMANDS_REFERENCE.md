# OT-2 Direct Serial Terminal Maintenance Commands

## Connection Setup

### Serial Port Configuration
```
Port: /dev/ttyAMA0
Baud Rate: 115200
Data Bits: 8
Parity: None
Stop Bits: 1
Flow Control: None
Line Ending: CR+LF (\r\n)
Command Terminator: \r\n\r\n (double CRLF)
```

### Connecting via SSH + Screen
```bash
# SSH to robot
ssh root@<robot-ip>

# Connect to Smoothie
screen /dev/ttyAMA0 115200

# Exit screen: Ctrl+A then K, then Y
```

### Connecting via Python (for scripting)
```python
import serial

ser = serial.Serial(
    port='/dev/ttyAMA0',
    baudrate=115200,
    timeout=5
)

def send_command(cmd):
    ser.write(f"{cmd}\r\n\r\n".encode())
    response = ser.read_until(b'ok\r\nok\r\n').decode()
    return response

# Example
print(send_command("M114.2"))
```

---

## Essential Maintenance Commands

### System Information
```
version                  # Get firmware version
M115                     # Get firmware version (alternative)
config-get sd            # Check if SD card is present
```

### Position and Status
```
M114.2                   # Get current position (all axes)
                         # Response: X:418.000 Y:353.000 Z:218.000 A:218.000 B:19.000 C:19.000

M119                     # Get limit switch status
                         # Response: X_min:1 Y_max:1 Z_max:1 A_max:1 B_max:1 C_max:1

G28.6                    # Get homing status (which axes are homed)
```

### Homing Commands
```
G28.2 X Y Z A B C        # Home all axes
G28.2 X                  # Home X axis only
G28.2 Y                  # Home Y axis only
G28.2 Z A                # Home both Z axes
G28.2 B C                # Home both plungers
```

### Movement Commands
```
G0 X100 Y200 Z100 F18000 # Move to position at 300mm/s (F = mm/min)
G0 X100                  # Move X only
G91                      # Set relative coordinate mode
G0 X10 Y10               # Move relative 10mm in X and Y
G90                      # Set absolute coordinate mode (default)
```

### Speed Control
```
M203.1 X600 Y400 Z125 A125 B40 C40   # Set max speeds (mm/s)
M204 S10000                           # Set acceleration (mm/s²)
M120                                  # Push (save) current speed
M121                                  # Pop (restore) saved speed
```

### Motor Current Control
```
M907 X1.25 Y1.25 Z0.5 A0.5 B0.05 C0.05  # Set running current (Amps)

# Current reference table:
#   X/Y: 0.7A (low) to 1.25A (high)
#   Z/A: 0.1A (low) to 0.5A (high)
#   B/C: 0.05A (normal) to 0.5A (unsticking)
```

### Motor Enable/Disable
```
M17                      # Enable all motors (engage)
M18                      # Disable all motors (disengage)
M18 X                    # Disable X motor only
```

### Dwell (Delay)
```
G4 P1.0                  # Wait 1 second
G4 P0.5                  # Wait 0.5 seconds
```

### Wait for Completion
```
M400                     # Wait for all moves to complete
```

---

## Diagnostic Commands

### Probe/Touch Detection
```
G38.2 F1000 Z-100        # Probe Z axis downward at 1000mm/min until contact
                         # Response: Z:xxx.xxx (position where contact detected)
```

### Error Recovery
```
M999                     # Reset from error state
                         # Use after motor stall or other errors
```

### Temperature Sensors (if equipped)
```
M105                     # Read temperature sensors
```

---

## Pipette EEPROM Commands

### Read Pipette Information
```
M369 L                   # Read left pipette ID
M369 R                   # Read right pipette ID
                         # Response: Serial: P20SV202020121511

M371 L                   # Read left pipette model
M371 R                   # Read right pipette model
                         # Response: Model: p20_single_v2.0
```

### Write Pipette Information (CAUTION)
```
M370 L P20SV202020121511 # Write left pipette serial
M370 R P1KSV2020021505   # Write right pipette serial

M372 L p20_single_v2.0   # Write left pipette model
M372 R p1000_single_v2.0 # Write right pipette model
```

---

## Calibration-Related Commands

### Steps Per Millimeter
```
M92 X80 Y80 Z400 A400 B768 C768    # Set steps/mm for each axis
                                    # Default values shown
```

### Axis Configuration
```
# These are typically set in firmware, but can be queried/modified:
config-get alpha_steps_per_mm       # Get X steps/mm
config-get beta_steps_per_mm        # Get Y steps/mm
config-get gamma_steps_per_mm       # Get Z steps/mm
```

---

## Safety and Limits

### Soft Limits
```
# Axis travel limits (approximate):
# X: 0 to 418mm
# Y: 0 to 353mm
# Z: 0 to 218mm (left mount)
# A: 0 to 218mm (right mount)
# B/C: varies by pipette
```

### Homing Sequence
The OT-2 follows a specific homing sequence for safety:
1. Z and A axes raise first (to clear deck)
2. X axis homes (left limit)
3. Y axis homes (back limit)
4. B and C axes home last (plungers)

---

## Troubleshooting Commands

### Motor Stall Detection
```
# If you see "Homing failed" or similar errors:
M999                     # Reset error state
G28.2 X Y Z A            # Try homing again
```

### Plunger Issues
```
# Unstick plunger (move slowly with high current):
M907 B0.5                # Increase plunger current
G0 B18 F60               # Move plunger slowly (1mm/s)
G28.2 B                  # Home plunger
M907 B0.05               # Reset to normal current
```

### Check for Mechanical Binding
```
M18                      # Disable motors
# Manually move gantry - should move freely
M17                      # Re-enable motors
G28.2 X Y Z A            # Re-home
```

---

## Common Maintenance Sequences

### Full System Check
```bash
# 1. Get system info
version
M114.2
M119

# 2. Home all axes
G28.2 X Y Z A B C

# 3. Check positions after home
M114.2

# 4. Test movement
G0 X200 Y200 Z100 F18000
M400
M114.2
G0 X100 Y100 Z150 F18000
M400

# 5. Return home
G28.2 X Y Z A B C
```

### Pipette Check
```bash
# Read pipette info
M369 L
M371 L
M369 R
M371 R

# Home plungers
G28.2 B C

# Test plunger movement
G0 B10 F2400    # Move left plunger
G0 C10 F2400    # Move right plunger
G28.2 B C       # Home plungers
```

### Quick Motion Test
```bash
# Home first
G28.2 X Y Z A B C

# Move to center
G0 X200 Y175 Z100 F18000
M400

# Test corners
G0 X50 Y50 F18000
M400
G0 X350 Y50 F18000
M400
G0 X350 Y300 F18000
M400
G0 X50 Y300 F18000
M400

# Return home
G28.2 X Y Z A B C
```

---

## Module Commands (via USB serial)

Each module has its own serial port. Connect via:
```bash
screen /dev/ot_module_tempdeck0 115200      # Temperature Module
screen /dev/ot_module_magdeck0 115200       # Magnetic Module
screen /dev/ot_module_thermocycler0 115200  # Thermocycler
screen /dev/ot_module_heatershaker0 115200  # Heater-Shaker
```

### Temperature Module
```
M104 S37.0        # Set temperature to 37°C
M105              # Read temperature (T:current C:target)
M18               # Deactivate heater
M115              # Get device info
M836              # Get plate height
```

### Magnetic Module
```
G28.2             # Home magnet
G0 Z20.0          # Engage magnet (height in mm)
G0 Z0             # Disengage magnet
M114.2            # Get current position
M115              # Get device info
```

### Thermocycler
```
M126              # Open lid
M127              # Close lid
M140 S105         # Set lid temperature
M104 S95          # Set plate temperature
M105              # Read temperatures
M18               # Deactivate all heaters
M115              # Get device info
```

### Heater-Shaker
```
M3 S1000          # Set shake speed (RPM)
M123              # Query current RPM
M104 S37          # Set temperature
M105              # Query temperature
M242              # Open labware latch
M243              # Close labware latch
G28               # Home (stop shaking)
M18               # Deactivate heater
M115              # Get device info
```

---

## Response Codes

| Response | Meaning |
|----------|---------|
| `ok` | Command accepted |
| `error:xxx` | Error occurred |
| `!!` | Emergency stop or critical error |
| `ALARM` | Safety limit triggered |

---

## Tips for Serial Debugging

1. **Always wait for `ok`** before sending next command
2. **Use M400** after moves to ensure completion before querying position
3. **Home after power cycle** - position is lost on power off
4. **Monitor M119** if homing fails - switch may not be triggering
5. **Use M999** to recover from error states
6. **Lower speeds (F value)** for more precise debugging
7. **Log everything** - redirect output to file for analysis

---

## Emergency Procedures

### Emergency Stop
```
M112              # Emergency stop (requires power cycle to recover)
```

### Reset After Error
```
M999              # Clear error state
G28.2 X Y Z A     # Re-home axes
```

### Manual Recovery
1. Power off robot
2. Manually move gantry to center (check for obstructions)
3. Power on
4. Run `G28.2 X Y Z A B C` to home

---

## Reference: Axis Mapping

| Axis | Function | Home Position | Max Speed |
|------|----------|---------------|-----------|
| X | Left/Right (gantry) | 418.0 mm | 600 mm/s |
| Y | Front/Back (gantry) | 353.0 mm | 400 mm/s |
| Z | Left mount up/down | 218.0 mm | 125 mm/s |
| A | Right mount up/down | 218.0 mm | 125 mm/s |
| B | Left plunger | ~19.0 mm | 40 mm/s |
| C | Right plunger | ~19.0 mm | 40 mm/s |
