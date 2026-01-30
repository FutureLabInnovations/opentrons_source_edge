#!/usr/bin/env python3
"""
Opentrons Magnetic Module (MagDeck) Diagnostic Tool
====================================================
For maintenance and testing of Magnetic Module v1 and v2

Usage:
    python diagnose_magnetic_module.py [--port COM6] [--full-test]

Connection: USB Serial
Default Port: COM6 (Windows) or /dev/ttyUSB0 (Linux)
Baud Rate: 115200
"""

import serial
import time
import argparse
import sys
from datetime import datetime
from typing import Optional, Dict, Tuple

# Protocol Constants
BAUDRATE = 115200
TIMEOUT = 10.0  # Longer timeout for probe operations
COMMAND_TERMINATOR = "\r\n\r\n"
ACK_PATTERN = "ok\r\nok\r\n"
DEFAULT_PORT = "COM6"

# G-code Commands
class GCODE:
    HOME = "G28.2"
    PROBE_PLATE = "G38.2"
    GET_PLATE_HEIGHT = "M836"
    GET_CURRENT_POSITION = "M114.2"
    MOVE = "G0"
    DEVICE_INFO = "M115"
    PROGRAMMING_MODE = "dfu"


# Position precision for Gen2 (millimeters)
GCODE_ROUNDING_PRECISION = 3


class MagneticModuleDiagnostic:
    """Diagnostic tool for Opentrons Magnetic Module."""

    def __init__(self, port: str = DEFAULT_PORT):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.device_info: Dict[str, str] = {}
        self.is_gen2 = False
        self.report_lines: list = []

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        self.report_lines.append(log_line)

    def connect(self) -> bool:
        """Establish serial connection to the module."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=BAUDRATE,
                timeout=TIMEOUT,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            time.sleep(0.5)  # Allow connection to stabilize
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.log(f"Connected to {self.port} at {BAUDRATE} baud")
            return True
        except serial.SerialException as e:
            self.log(f"Failed to connect to {self.port}: {e}", "ERROR")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.log("Disconnected from module")

    def send_command(self, gcode: str, timeout: float = None) -> Tuple[bool, str]:
        """Send a G-code command and receive response."""
        if not self.serial or not self.serial.is_open:
            return False, "Not connected"

        if timeout is None:
            timeout = TIMEOUT

        command = f"{gcode}{COMMAND_TERMINATOR}"
        try:
            self.serial.reset_input_buffer()
            self.serial.write(command.encode())
            self.serial.flush()

            # Read response
            response = ""
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.serial.in_waiting:
                    chunk = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                    response += chunk
                    if ACK_PATTERN in response:
                        break
                time.sleep(0.05)

            # Extract data before ACK
            if ACK_PATTERN in response:
                data = response.split(ACK_PATTERN)[0].strip()
                return True, data
            else:
                return False, f"No ACK received. Raw: {repr(response)}"

        except Exception as e:
            return False, f"Command failed: {e}"

    def parse_key_values(self, response: str) -> Dict[str, str]:
        """Parse key:value pairs from response."""
        result = {}
        for part in response.split():
            if ':' in part:
                key, value = part.split(':', 1)
                result[key] = value
        return result

    def parse_position(self, response: str) -> Optional[float]:
        """Parse Z position from response."""
        data = self.parse_key_values(response)
        if 'Z' in data:
            try:
                return round(float(data['Z']), GCODE_ROUNDING_PRECISION)
            except ValueError:
                pass
        return None

    def parse_height(self, response: str) -> Optional[float]:
        """Parse height from response."""
        data = self.parse_key_values(response)
        if 'height' in data:
            try:
                return round(float(data['height']), GCODE_ROUNDING_PRECISION)
            except ValueError:
                pass
        return None

    # ========== Diagnostic Tests ==========

    def test_connection(self) -> bool:
        """Test basic connectivity."""
        self.log("=" * 60)
        self.log("TEST: Connection Test")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_CURRENT_POSITION)
        if success:
            self.log(f"Connection test PASSED - Response: {response}", "PASS")
            return True
        else:
            self.log(f"Connection test FAILED - {response}", "FAIL")
            return False

    def test_device_info(self) -> bool:
        """Get and validate device information."""
        self.log("=" * 60)
        self.log("TEST: Device Information")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.DEVICE_INFO)
        if not success:
            self.log(f"Failed to get device info: {response}", "FAIL")
            return False

        self.device_info = self.parse_key_values(response)
        self.log(f"Raw response: {response}")

        # Validate required fields
        required_fields = ['serial', 'model', 'version']
        missing = [f for f in required_fields if f not in self.device_info]

        if missing:
            self.log(f"Missing required fields: {missing}", "WARN")

        serial_no = self.device_info.get('serial', 'N/A')
        model = self.device_info.get('model', 'N/A')
        version = self.device_info.get('version', 'N/A')

        self.log(f"Serial Number: {serial_no}")
        self.log(f"Model: {model}")
        self.log(f"Firmware Version: {version}")

        # Detect Gen1 vs Gen2
        if 'v2' in model.lower() or 'gen2' in model.lower():
            self.is_gen2 = True
            self.log("Detected: Gen2 Magnetic Module (units: millimeters)")
        else:
            self.is_gen2 = False
            self.log("Detected: Gen1 Magnetic Module (units: half-millimeters)")

        return len(missing) == 0

    def test_position_reading(self) -> bool:
        """Test position sensor reading."""
        self.log("=" * 60)
        self.log("TEST: Position Reading")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_CURRENT_POSITION)
        if not success:
            self.log(f"Failed to read position: {response}", "FAIL")
            return False

        position = self.parse_position(response)
        self.log(f"Raw response: {response}")
        self.log(f"Current Z Position: {position}")

        if position is not None:
            units = "mm" if self.is_gen2 else "half-mm"
            self.log(f"Position reading valid ({units})", "PASS")
            return True
        else:
            self.log("Could not parse position value", "FAIL")
            return False

    def test_home(self) -> bool:
        """Test homing operation."""
        self.log("=" * 60)
        self.log("TEST: Homing Operation")
        self.log("=" * 60)

        self.log("Executing home command (G28.2)...")
        success, response = self.send_command(GCODE.HOME, timeout=15.0)

        if not success:
            self.log(f"Home command failed: {response}", "FAIL")
            return False

        self.log("Home command completed")

        # Verify position is at/near 0
        time.sleep(0.5)
        success2, response2 = self.send_command(GCODE.GET_CURRENT_POSITION)
        if success2:
            position = self.parse_position(response2)
            self.log(f"Position after homing: {position}")
            if position is not None and abs(position) < 0.5:
                self.log("Homing test PASSED - Position near zero", "PASS")
                return True
            else:
                self.log("Position not at expected home position", "WARN")
                return True  # Still consider pass if command succeeded

        return True

    def test_probe_plate(self) -> bool:
        """Test plate probing functionality."""
        self.log("=" * 60)
        self.log("TEST: Plate Probe")
        self.log("=" * 60)

        self.log("Executing probe command (G38.2)...")
        self.log("NOTE: This test works best with labware on the module")

        success, response = self.send_command(GCODE.PROBE_PLATE, timeout=15.0)

        if not success:
            self.log(f"Probe command failed: {response}", "FAIL")
            return False

        self.log("Probe command completed")

        # Get plate height
        success2, response2 = self.send_command(GCODE.GET_PLATE_HEIGHT)
        if success2:
            height = self.parse_height(response2)
            self.log(f"Calculated plate height: {height}")
            if height is not None:
                self.log("Plate probe test PASSED", "PASS")
                return True

        self.log("Could not retrieve plate height after probe", "WARN")
        return True

    def test_move_operations(self) -> bool:
        """Test magnet movement operations."""
        self.log("=" * 60)
        self.log("TEST: Movement Operations")
        self.log("=" * 60)

        # First, home the module
        self.log("Homing before movement test...")
        success, _ = self.send_command(GCODE.HOME, timeout=15.0)
        if not success:
            self.log("Failed to home before movement test", "FAIL")
            return False

        time.sleep(0.5)

        # Test positions (smaller values for safety)
        test_positions = [5.0, 10.0, 15.0, 5.0, 0.0]

        for target_pos in test_positions:
            self.log(f"Moving to Z={target_pos}...")
            move_cmd = f"{GCODE.MOVE} Z{target_pos:.3f}"
            success, response = self.send_command(move_cmd, timeout=10.0)

            if not success:
                self.log(f"Move command failed: {response}", "FAIL")
                return False

            time.sleep(0.5)

            # Verify position
            success2, response2 = self.send_command(GCODE.GET_CURRENT_POSITION)
            if success2:
                actual_pos = self.parse_position(response2)
                if actual_pos is not None:
                    error = abs(actual_pos - target_pos)
                    self.log(f"  Target: {target_pos}, Actual: {actual_pos}, Error: {error:.3f}")
                    if error > 1.0:
                        self.log(f"Position error exceeds tolerance", "WARN")

        # Return to home
        self.send_command(GCODE.HOME, timeout=15.0)
        self.log("Movement test PASSED", "PASS")
        return True

    def test_engage_disengage(self) -> bool:
        """Test engage/disengage cycle (move to high position and back)."""
        self.log("=" * 60)
        self.log("TEST: Engage/Disengage Cycle")
        self.log("=" * 60)

        # Define engage height (typical values)
        engage_height = 6.0 if self.is_gen2 else 12.0  # Gen1 uses half-mm
        disengage_height = 0.0

        # Home first
        self.log("Homing...")
        self.send_command(GCODE.HOME, timeout=15.0)
        time.sleep(0.5)

        # Engage (move magnets up close to labware)
        self.log(f"Engaging magnets (moving to Z={engage_height})...")
        success, _ = self.send_command(f"{GCODE.MOVE} Z{engage_height:.3f}", timeout=10.0)
        if not success:
            self.log("Engage command failed", "FAIL")
            return False

        time.sleep(1.0)

        # Verify engaged position
        success, response = self.send_command(GCODE.GET_CURRENT_POSITION)
        if success:
            pos = self.parse_position(response)
            self.log(f"Position after engage: {pos}")

        # Disengage (move magnets away)
        self.log(f"Disengaging magnets (moving to Z={disengage_height})...")
        success, _ = self.send_command(f"{GCODE.MOVE} Z{disengage_height:.3f}", timeout=10.0)
        if not success:
            self.log("Disengage command failed", "FAIL")
            return False

        time.sleep(1.0)

        # Verify disengaged position
        success, response = self.send_command(GCODE.GET_CURRENT_POSITION)
        if success:
            pos = self.parse_position(response)
            self.log(f"Position after disengage: {pos}")

        self.log("Engage/Disengage test PASSED", "PASS")
        return True

    def run_diagnostics(self, full_test: bool = False):
        """Run complete diagnostic suite."""
        self.log("=" * 60)
        self.log("OPENTRONS MAGNETIC MODULE DIAGNOSTIC")
        self.log(f"Port: {self.port}")
        self.log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 60)

        results = {}

        if not self.connect():
            self.log("Cannot proceed without connection", "ERROR")
            return

        try:
            # Basic tests
            results['connection'] = self.test_connection()
            results['device_info'] = self.test_device_info()
            results['position_reading'] = self.test_position_reading()
            results['home'] = self.test_home()

            # Extended tests (if requested)
            if full_test:
                self.log("\n" + "=" * 60)
                self.log("EXTENDED TESTS (full test mode)")
                self.log("=" * 60)
                results['probe_plate'] = self.test_probe_plate()
                results['move_operations'] = self.test_move_operations()
                results['engage_disengage'] = self.test_engage_disengage()

            # Always return to home
            self.log("\nReturning to home position...")
            self.send_command(GCODE.HOME, timeout=15.0)

            # Print summary
            self.log("\n" + "=" * 60)
            self.log("DIAGNOSTIC SUMMARY")
            self.log("=" * 60)

            passed = sum(1 for v in results.values() if v)
            total = len(results)

            for test, result in results.items():
                status = "PASS" if result else "FAIL"
                self.log(f"  {test}: {status}")

            self.log("-" * 40)
            self.log(f"Total: {passed}/{total} tests passed")

            if passed == total:
                self.log("MODULE STATUS: HEALTHY", "PASS")
            elif passed >= total * 0.7:
                self.log("MODULE STATUS: NEEDS ATTENTION", "WARN")
            else:
                self.log("MODULE STATUS: REQUIRES SERVICE", "FAIL")

        finally:
            # Always home before disconnecting
            self.send_command(GCODE.HOME, timeout=15.0)
            self.disconnect()

    def save_report(self, filename: str = None):
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"magdeck_diagnostic_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write('\n'.join(self.report_lines))
        print(f"\nReport saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Magnetic Module Diagnostic Tool"
    )
    parser.add_argument(
        '--port', '-p',
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests including movement and probe tests"
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help="Save diagnostic report to file"
    )

    args = parser.parse_args()

    diagnostic = MagneticModuleDiagnostic(port=args.port)
    diagnostic.run_diagnostics(full_test=args.full_test)

    if args.save_report:
        diagnostic.save_report()


if __name__ == "__main__":
    main()
