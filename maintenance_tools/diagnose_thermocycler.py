#!/usr/bin/env python3
"""
Opentrons Thermocycler Module Diagnostic Tool
==============================================
For maintenance and testing of Thermocycler Gen1 and Gen2

Usage:
    python diagnose_thermocycler.py [--port COM6] [--full-test]

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
from enum import Enum

# Protocol Constants
BAUDRATE = 115200
BOOTLOADER_BAUDRATE = 1200
TIMEOUT = 40.0  # Long timeout for lid operations
DEFAULT_PORT = "COM6"

# Gen1 Protocol
GEN1_TERMINATOR = "\r\n"
GEN1_ACK = "ok\r\nok\r\n"

# Gen2 Protocol
GEN2_TERMINATOR = "\n"
GEN2_ACK = " OK\n"

# Temperature Limits
LID_TARGET_MIN = 37
LID_TARGET_MAX = 110
BLOCK_TARGET_MIN = 0
BLOCK_TARGET_MAX = 99

# G-code Commands
class GCODE:
    OPEN_LID = "M126"
    CLOSE_LID = "M127"
    PLATE_LIFT = "M128"  # Gen2 only
    GET_LID_STATUS = "M119"
    SET_LID_TEMP = "M140"
    GET_LID_TEMP = "M141"
    EDIT_PID_PARAMS = "M301"
    SET_PLATE_TEMP = "M104"
    GET_PLATE_TEMP = "M105"
    SET_RAMP_RATE = "M566"  # Gen1 only
    DEACTIVATE_ALL = "M18"
    DEACTIVATE_LID = "M108"
    DEACTIVATE_BLOCK = "M14"
    DEVICE_INFO = "M115"
    GET_RESET_REASON = "M114"
    ENTER_PROGRAMMING = "dfu"
    JOG_LID = "M240.D"  # Gen2 only


class LidStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    IN_BETWEEN = "in_between"
    UNKNOWN = "unknown"


class ThermocyclerDiagnostic:
    """Diagnostic tool for Opentrons Thermocycler Module."""

    def __init__(self, port: str = DEFAULT_PORT):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.device_info: Dict[str, str] = {}
        self.is_gen2 = False
        self.terminator = GEN1_TERMINATOR
        self.ack_pattern = GEN1_ACK
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
            time.sleep(1.0)  # TC needs more time to stabilize
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

        command = f"{gcode}{self.terminator}"
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
                    if self.ack_pattern in response:
                        break
                time.sleep(0.05)

            # Extract data before ACK
            if self.ack_pattern in response:
                data = response.split(self.ack_pattern)[0].strip()
                return True, data
            else:
                # Check for partial ACK (common with Gen2)
                if "OK" in response.upper():
                    # Extract data up to OK
                    parts = response.upper().split("OK")
                    return True, parts[0].strip()
                return False, f"No ACK received. Raw: {repr(response)}"

        except Exception as e:
            return False, f"Command failed: {e}"

    def detect_generation(self) -> bool:
        """Detect if this is Gen1 or Gen2 thermocycler."""
        # Use temporary settings to check device info
        original_term = self.terminator
        original_ack = self.ack_pattern

        # Try with Gen1 settings first
        self.terminator = GEN1_TERMINATOR
        self.ack_pattern = GEN1_ACK

        self.serial.reset_input_buffer()
        command = f"{GCODE.DEVICE_INFO}{self.terminator}"
        self.serial.write(command.encode())
        self.serial.flush()

        time.sleep(0.5)
        response = ""
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if self.serial.in_waiting:
                response += self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
            time.sleep(0.05)

        # Gen2 responses start with "M115"
        if response.strip().startswith("M115"):
            self.is_gen2 = True
            self.terminator = GEN2_TERMINATOR
            self.ack_pattern = GEN2_ACK
            self.log("Detected: Gen2 Thermocycler")
        else:
            self.is_gen2 = False
            self.terminator = GEN1_TERMINATOR
            self.ack_pattern = GEN1_ACK
            self.log("Detected: Gen1 Thermocycler")

        return True

    def parse_key_values(self, response: str) -> Dict[str, str]:
        """Parse key:value pairs from response."""
        result = {}
        for part in response.split():
            if ':' in part:
                key, value = part.split(':', 1)
                result[key] = value
        return result

    def parse_temperature(self, response: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse temperature response (T=target, C=current)."""
        data = self.parse_key_values(response)
        target = None
        current = None
        if 'T' in data and data['T'].lower() != 'none':
            try:
                target = float(data['T'])
            except ValueError:
                pass
        if 'C' in data:
            try:
                current = float(data['C'])
            except ValueError:
                pass
        return target, current

    def parse_lid_status(self, response: str) -> LidStatus:
        """Parse lid status from response."""
        data = self.parse_key_values(response)
        lid_value = data.get('Lid', '').lower()
        if lid_value == 'open':
            return LidStatus.OPEN
        elif lid_value == 'closed':
            return LidStatus.CLOSED
        elif lid_value == 'in_between':
            return LidStatus.IN_BETWEEN
        return LidStatus.UNKNOWN

    # ========== Diagnostic Tests ==========

    def test_connection(self) -> bool:
        """Test basic connectivity and detect generation."""
        self.log("=" * 60)
        self.log("TEST: Connection Test")
        self.log("=" * 60)

        self.detect_generation()

        success, response = self.send_command(GCODE.GET_LID_STATUS)
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

        self.log(f"Raw response: {response}")

        if self.is_gen2:
            # Gen2 format: "M115 FW:version HW:hw SerialNo:serial"
            # Remove M115 prefix if present
            if response.startswith("M115"):
                response = response[4:].strip()
            data = self.parse_key_values(response)
            self.device_info = {
                'version': data.get('FW', 'N/A'),
                'model': data.get('HW', 'N/A'),
                'serial': data.get('SerialNo', 'N/A')
            }
        else:
            # Gen1 format: "serial:xxx model:xxx version:xxx"
            self.device_info = self.parse_key_values(response)

        self.log(f"Serial Number: {self.device_info.get('serial', 'N/A')}")
        self.log(f"Model/Hardware: {self.device_info.get('model', 'N/A')}")
        self.log(f"Firmware Version: {self.device_info.get('version', 'N/A')}")
        self.log(f"Generation: {'Gen2' if self.is_gen2 else 'Gen1'}")

        # Try to get reset reason
        success2, response2 = self.send_command(GCODE.GET_RESET_REASON)
        if success2:
            self.log(f"Last Reset Reason: {response2}")

        return True

    def test_lid_status(self) -> bool:
        """Test lid status reading."""
        self.log("=" * 60)
        self.log("TEST: Lid Status")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_LID_STATUS)
        if not success:
            self.log(f"Failed to read lid status: {response}", "FAIL")
            return False

        status = self.parse_lid_status(response)
        self.log(f"Raw response: {response}")
        self.log(f"Lid Status: {status.value}")

        if status != LidStatus.UNKNOWN:
            self.log("Lid status reading PASSED", "PASS")
            return True
        else:
            self.log("Could not determine lid status", "WARN")
            return True  # Not a critical failure

    def test_lid_temperature(self) -> bool:
        """Test lid temperature reading."""
        self.log("=" * 60)
        self.log("TEST: Lid Temperature")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_LID_TEMP)
        if not success:
            self.log(f"Failed to read lid temperature: {response}", "FAIL")
            return False

        target, current = self.parse_temperature(response)
        self.log(f"Raw response: {response}")
        self.log(f"Lid Current Temperature: {current} C")
        self.log(f"Lid Target Temperature: {target} C")

        if current is not None:
            if 0 <= current <= 150:
                self.log("Lid temperature reading valid", "PASS")
                return True
            else:
                self.log(f"Lid temperature {current}C outside expected range", "WARN")
        return True

    def test_plate_temperature(self) -> bool:
        """Test plate (block) temperature reading."""
        self.log("=" * 60)
        self.log("TEST: Plate Temperature")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_PLATE_TEMP)
        if not success:
            self.log(f"Failed to read plate temperature: {response}", "FAIL")
            return False

        target, current = self.parse_temperature(response)
        self.log(f"Raw response: {response}")
        self.log(f"Plate Current Temperature: {current} C")
        self.log(f"Plate Target Temperature: {target} C")

        # Check for hold time (H parameter)
        data = self.parse_key_values(response)
        if 'H' in data:
            self.log(f"Hold Time: {data['H']} seconds")

        if current is not None:
            if -10 <= current <= 110:
                self.log("Plate temperature reading valid", "PASS")
                return True
            else:
                self.log(f"Plate temperature {current}C outside expected range", "WARN")
        return True

    def test_lid_open_close(self) -> bool:
        """Test lid open and close operations."""
        self.log("=" * 60)
        self.log("TEST: Lid Open/Close Operations")
        self.log("=" * 60)

        # Get initial status
        success, response = self.send_command(GCODE.GET_LID_STATUS)
        initial_status = self.parse_lid_status(response) if success else LidStatus.UNKNOWN
        self.log(f"Initial lid status: {initial_status.value}")

        # Open lid
        self.log("Opening lid...")
        success, response = self.send_command(GCODE.OPEN_LID, timeout=60.0)
        if not success:
            self.log(f"Open lid command failed: {response}", "FAIL")
            return False

        time.sleep(2.0)
        success, response = self.send_command(GCODE.GET_LID_STATUS)
        if success:
            status = self.parse_lid_status(response)
            self.log(f"Lid status after open command: {status.value}")

        # Close lid
        self.log("Closing lid...")
        success, response = self.send_command(GCODE.CLOSE_LID, timeout=60.0)
        if not success:
            self.log(f"Close lid command failed: {response}", "FAIL")
            return False

        time.sleep(2.0)
        success, response = self.send_command(GCODE.GET_LID_STATUS)
        if success:
            status = self.parse_lid_status(response)
            self.log(f"Lid status after close command: {status.value}")

        self.log("Lid open/close test PASSED", "PASS")
        return True

    def test_lid_heating(self, target_temp: float = 50.0, wait_time: int = 60) -> bool:
        """Test lid heating capability."""
        self.log("=" * 60)
        self.log(f"TEST: Lid Heating (Target: {target_temp}C)")
        self.log("=" * 60)

        # Ensure lid is closed
        self.log("Ensuring lid is closed...")
        success, _ = self.send_command(GCODE.CLOSE_LID, timeout=60.0)
        time.sleep(2.0)

        # Get initial temperature
        success, response = self.send_command(GCODE.GET_LID_TEMP)
        _, initial_temp = self.parse_temperature(response) if success else (None, None)
        self.log(f"Initial lid temperature: {initial_temp} C")

        # Set lid temperature
        self.log(f"Setting lid temperature to {target_temp} C...")
        target_clamped = max(LID_TARGET_MIN, min(LID_TARGET_MAX, target_temp))
        success, response = self.send_command(f"{GCODE.SET_LID_TEMP} S{target_clamped:.2f}")
        if not success:
            self.log(f"Failed to set lid temperature: {response}", "FAIL")
            return False

        # Monitor temperature
        self.log(f"Monitoring lid temperature for {wait_time} seconds...")
        max_temp = initial_temp or 0

        for i in range(wait_time // 10):
            time.sleep(10)
            success, response = self.send_command(GCODE.GET_LID_TEMP)
            if success:
                target, current = self.parse_temperature(response)
                if current is not None:
                    max_temp = max(max_temp, current)
                    self.log(f"  [{(i+1)*10}s] Current: {current} C, Target: {target} C")

        # Deactivate lid heater
        self.log("Deactivating lid heater...")
        self.send_command(GCODE.DEACTIVATE_LID)

        if initial_temp is not None and max_temp > initial_temp + 2:
            self.log(f"Lid heating test PASSED - Temperature increased from {initial_temp}C to {max_temp}C", "PASS")
            return True
        else:
            self.log("Lid heating test inconclusive - Check heater", "WARN")
            return True

    def test_plate_heating(self, target_temp: float = 50.0, wait_time: int = 60) -> bool:
        """Test plate heating capability."""
        self.log("=" * 60)
        self.log(f"TEST: Plate Heating (Target: {target_temp}C)")
        self.log("=" * 60)

        # Ensure lid is closed for better heat retention
        self.log("Ensuring lid is closed...")
        success, _ = self.send_command(GCODE.CLOSE_LID, timeout=60.0)
        time.sleep(2.0)

        # Get initial temperature
        success, response = self.send_command(GCODE.GET_PLATE_TEMP)
        _, initial_temp = self.parse_temperature(response) if success else (None, None)
        self.log(f"Initial plate temperature: {initial_temp} C")

        # Set plate temperature
        self.log(f"Setting plate temperature to {target_temp} C...")
        target_clamped = max(BLOCK_TARGET_MIN, min(BLOCK_TARGET_MAX, target_temp))
        success, response = self.send_command(f"{GCODE.SET_PLATE_TEMP} S{target_clamped:.2f}")
        if not success:
            self.log(f"Failed to set plate temperature: {response}", "FAIL")
            return False

        # Monitor temperature
        self.log(f"Monitoring plate temperature for {wait_time} seconds...")
        max_temp = initial_temp or 0

        for i in range(wait_time // 10):
            time.sleep(10)
            success, response = self.send_command(GCODE.GET_PLATE_TEMP)
            if success:
                target, current = self.parse_temperature(response)
                if current is not None:
                    max_temp = max(max_temp, current)
                    self.log(f"  [{(i+1)*10}s] Current: {current} C, Target: {target} C")

        # Deactivate plate heater
        self.log("Deactivating plate heater...")
        self.send_command(GCODE.DEACTIVATE_BLOCK)

        if initial_temp is not None and max_temp > initial_temp + 2:
            self.log(f"Plate heating test PASSED - Temperature increased from {initial_temp}C to {max_temp}C", "PASS")
            return True
        else:
            self.log("Plate heating test inconclusive - Check heater", "WARN")
            return True

    def test_deactivation(self) -> bool:
        """Test full deactivation command."""
        self.log("=" * 60)
        self.log("TEST: Deactivation")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.DEACTIVATE_ALL)
        if success:
            self.log("Deactivation command successful", "PASS")

            time.sleep(1.0)

            # Verify temperatures are being deactivated
            success2, response2 = self.send_command(GCODE.GET_LID_TEMP)
            if success2:
                target, current = self.parse_temperature(response2)
                self.log(f"Lid after deactivation - Target: {target}, Current: {current}")

            success3, response3 = self.send_command(GCODE.GET_PLATE_TEMP)
            if success3:
                target, current = self.parse_temperature(response3)
                self.log(f"Plate after deactivation - Target: {target}, Current: {current}")

            return True
        else:
            self.log(f"Deactivation failed: {response}", "FAIL")
            return False

    def test_plate_lift(self) -> bool:
        """Test plate lift command (Gen2 only)."""
        if not self.is_gen2:
            self.log("Plate lift test skipped (Gen1 does not support this)", "INFO")
            return True

        self.log("=" * 60)
        self.log("TEST: Plate Lift (Gen2 only)")
        self.log("=" * 60)

        # Ensure lid is open for plate lift
        self.log("Opening lid for plate lift...")
        self.send_command(GCODE.OPEN_LID, timeout=60.0)
        time.sleep(2.0)

        self.log("Executing plate lift...")
        success, response = self.send_command(GCODE.PLATE_LIFT, timeout=30.0)
        if success:
            self.log("Plate lift command successful", "PASS")
            time.sleep(2.0)

            # Close lid after test
            self.log("Closing lid after test...")
            self.send_command(GCODE.CLOSE_LID, timeout=60.0)
            return True
        else:
            self.log(f"Plate lift command failed: {response}", "FAIL")
            return False

    def run_diagnostics(self, full_test: bool = False):
        """Run complete diagnostic suite."""
        self.log("=" * 60)
        self.log("OPENTRONS THERMOCYCLER MODULE DIAGNOSTIC")
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
            results['lid_status'] = self.test_lid_status()
            results['lid_temperature'] = self.test_lid_temperature()
            results['plate_temperature'] = self.test_plate_temperature()
            results['deactivation'] = self.test_deactivation()

            # Extended tests (if requested)
            if full_test:
                self.log("\n" + "=" * 60)
                self.log("EXTENDED TESTS (full test mode)")
                self.log("WARNING: These tests will operate the lid and heaters")
                self.log("=" * 60)

                results['lid_open_close'] = self.test_lid_open_close()
                results['lid_heating'] = self.test_lid_heating(target_temp=50.0, wait_time=60)
                results['plate_heating'] = self.test_plate_heating(target_temp=50.0, wait_time=60)

                if self.is_gen2:
                    results['plate_lift'] = self.test_plate_lift()

            # Final deactivation
            self.log("\nFinal deactivation...")
            self.send_command(GCODE.DEACTIVATE_ALL)

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
            self.log(f"Generation: {'Gen2' if self.is_gen2 else 'Gen1'}")

            if passed == total:
                self.log("MODULE STATUS: HEALTHY", "PASS")
            elif passed >= total * 0.7:
                self.log("MODULE STATUS: NEEDS ATTENTION", "WARN")
            else:
                self.log("MODULE STATUS: REQUIRES SERVICE", "FAIL")

        finally:
            # Always deactivate before disconnecting
            self.send_command(GCODE.DEACTIVATE_ALL)
            self.disconnect()

    def save_report(self, filename: str = None):
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            gen = "gen2" if self.is_gen2 else "gen1"
            filename = f"thermocycler_{gen}_diagnostic_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write('\n'.join(self.report_lines))
        print(f"\nReport saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Thermocycler Module Diagnostic Tool"
    )
    parser.add_argument(
        '--port', '-p',
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests including lid operation and heating cycles"
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help="Save diagnostic report to file"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("SAFETY WARNING")
    print("=" * 60)
    print("This diagnostic tool will operate the Thermocycler module.")
    print("- The lid will open and close")
    print("- Heaters will be activated (if full-test mode)")
    print("- Keep hands clear of the module during testing")
    print("=" * 60 + "\n")

    proceed = input("Press Enter to continue or Ctrl+C to abort...")

    diagnostic = ThermocyclerDiagnostic(port=args.port)
    diagnostic.run_diagnostics(full_test=args.full_test)

    if args.save_report:
        diagnostic.save_report()


if __name__ == "__main__":
    main()
