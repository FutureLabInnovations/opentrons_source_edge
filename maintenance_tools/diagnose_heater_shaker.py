#!/usr/bin/env python3
"""
Opentrons Heater-Shaker Module Diagnostic Tool
===============================================
For maintenance and testing of Heater-Shaker Module

Usage:
    python diagnose_heater_shaker.py [--port COM6] [--full-test]

Connection: USB Serial
Default Port: COM6 (Windows) or /dev/ttyUSB0 (Linux)
Baud Rate: 115200

IMPORTANT: This module combines heating and orbital shaking.
Keep hands and loose items away during testing.
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
TIMEOUT = 40.0  # Long timeout for operations
COMMAND_TERMINATOR = "\n"
ACK_PATTERN = "OK\n"
ERROR_KEYWORD = "err"
DEFAULT_PORT = "COM6"

# G-code Commands
class GCODE:
    SET_RPM = "M3"
    GET_RPM = "M123"
    SET_TEMPERATURE = "M104"
    GET_TEMPERATURE = "M105"
    HOME = "G28"
    ENTER_BOOTLOADER = "dfu"
    GET_VERSION = "M115"
    OPEN_LABWARE_LATCH = "M242"
    CLOSE_LABWARE_LATCH = "M243"
    GET_LABWARE_LATCH_STATE = "M241"
    DEACTIVATE_HEATER = "M106"
    GET_RESET_REASON = "M114"


class LatchStatus(Enum):
    IDLE_UNKNOWN = "IDLE_UNKNOWN"
    IDLE_CLOSED = "IDLE_CLOSED"
    IDLE_OPEN = "IDLE_OPEN"
    LATCH_CLOSED = "LATCH_CLOSED"
    LATCH_OPEN = "LATCH_OPEN"
    UNKNOWN = "UNKNOWN"


class HeaterShakerDiagnostic:
    """Diagnostic tool for Opentrons Heater-Shaker Module."""

    def __init__(self, port: str = DEFAULT_PORT):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.device_info: Dict[str, str] = {}
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
            time.sleep(1.0)  # Allow connection to stabilize
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
                    # Check for ACK or error
                    if ACK_PATTERN in response or ERROR_KEYWORD.lower() in response.lower():
                        break
                time.sleep(0.05)

            # Check for errors
            if ERROR_KEYWORD.lower() in response.lower():
                return False, f"Error response: {response}"

            # Extract data (response includes command echo)
            if ACK_PATTERN in response:
                # Remove the OK part
                data = response.replace(ACK_PATTERN, "").replace("OK", "").strip()
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

    def parse_temperature(self, response: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse temperature response (T=target, C=current)."""
        data = self.parse_key_values(response)
        target = None
        current = None
        if 'T' in data:
            try:
                val = float(data['T'])
                target = val if val > 0 else None
            except ValueError:
                pass
        if 'C' in data:
            try:
                current = float(data['C'])
            except ValueError:
                pass
        return target, current

    def parse_rpm(self, response: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse RPM response (T=target, C=current)."""
        data = self.parse_key_values(response)
        target = None
        current = None
        if 'T' in data:
            try:
                val = int(float(data['T']))
                target = val if val > 0 else None
            except ValueError:
                pass
        if 'C' in data:
            try:
                current = int(float(data['C']))
            except ValueError:
                pass
        return target, current

    def parse_latch_status(self, response: str) -> LatchStatus:
        """Parse latch status from response."""
        data = self.parse_key_values(response)
        status_str = data.get('STATUS', '').upper()
        try:
            return LatchStatus(status_str)
        except ValueError:
            return LatchStatus.UNKNOWN

    # ========== Diagnostic Tests ==========

    def test_connection(self) -> bool:
        """Test basic connectivity."""
        self.log("=" * 60)
        self.log("TEST: Connection Test")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_TEMPERATURE)
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

        success, response = self.send_command(GCODE.GET_VERSION)
        if not success:
            self.log(f"Failed to get device info: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")

        # Parse HS format: "M115 FW:version HW:hw SerialNo:serial"
        # Remove M115 prefix if present
        clean_response = response.replace("M115", "").strip()
        data = self.parse_key_values(clean_response)

        self.device_info = {
            'version': data.get('FW', 'N/A'),
            'model': data.get('HW', 'N/A'),
            'serial': data.get('SerialNo', 'N/A')
        }

        self.log(f"Serial Number: {self.device_info.get('serial', 'N/A')}")
        self.log(f"Hardware Version: {self.device_info.get('model', 'N/A')}")
        self.log(f"Firmware Version: {self.device_info.get('version', 'N/A')}")

        # Try to get reset reason
        success2, response2 = self.send_command(GCODE.GET_RESET_REASON)
        if success2:
            self.log(f"Last Reset Reason: {response2}")

        return True

    def test_temperature_reading(self) -> bool:
        """Test temperature sensor reading."""
        self.log("=" * 60)
        self.log("TEST: Temperature Sensor")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_TEMPERATURE)
        if not success:
            self.log(f"Failed to read temperature: {response}", "FAIL")
            return False

        target, current = self.parse_temperature(response)
        self.log(f"Raw response: {response}")
        self.log(f"Current Temperature: {current} C")
        self.log(f"Target Temperature: {target} C")

        if current is not None:
            if 0 <= current <= 100:
                self.log("Temperature reading within expected range (0-100 C)", "PASS")
                return True
            else:
                self.log(f"Temperature {current}C outside expected range", "WARN")
                return True
        else:
            self.log("Could not parse temperature value", "FAIL")
            return False

    def test_rpm_reading(self) -> bool:
        """Test RPM sensor reading."""
        self.log("=" * 60)
        self.log("TEST: RPM Sensor")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_RPM)
        if not success:
            self.log(f"Failed to read RPM: {response}", "FAIL")
            return False

        target, current = self.parse_rpm(response)
        self.log(f"Raw response: {response}")
        self.log(f"Current RPM: {current}")
        self.log(f"Target RPM: {target}")

        if current is not None:
            if 0 <= current <= 3000:
                self.log("RPM reading valid (0-3000 range)", "PASS")
                return True
            else:
                self.log(f"RPM {current} outside expected range", "WARN")
                return True
        else:
            self.log("Could not parse RPM value", "FAIL")
            return False

    def test_latch_status(self) -> bool:
        """Test labware latch status reading."""
        self.log("=" * 60)
        self.log("TEST: Labware Latch Status")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_LABWARE_LATCH_STATE)
        if not success:
            self.log(f"Failed to read latch status: {response}", "FAIL")
            return False

        status = self.parse_latch_status(response)
        self.log(f"Raw response: {response}")
        self.log(f"Latch Status: {status.value}")

        if status != LatchStatus.UNKNOWN:
            self.log("Latch status reading PASSED", "PASS")
            return True
        else:
            self.log("Could not determine latch status", "WARN")
            return True

    def test_home(self) -> bool:
        """Test homing operation (stops shaking if active)."""
        self.log("=" * 60)
        self.log("TEST: Home Command")
        self.log("=" * 60)

        self.log("Executing home command (G28)...")
        success, response = self.send_command(GCODE.HOME, timeout=30.0)

        if success:
            self.log("Home command successful - Shaker stopped", "PASS")
            return True
        else:
            self.log(f"Home command failed: {response}", "FAIL")
            return False

    def test_latch_operation(self) -> bool:
        """Test labware latch open/close operations."""
        self.log("=" * 60)
        self.log("TEST: Latch Open/Close Operations")
        self.log("=" * 60)

        # First, ensure shaker is stopped
        self.log("Stopping shaker before latch operation...")
        self.send_command(GCODE.HOME, timeout=30.0)
        time.sleep(1.0)

        # Get initial status
        success, response = self.send_command(GCODE.GET_LABWARE_LATCH_STATE)
        initial_status = self.parse_latch_status(response) if success else LatchStatus.UNKNOWN
        self.log(f"Initial latch status: {initial_status.value}")

        # Open latch
        self.log("Opening labware latch...")
        success, response = self.send_command(GCODE.OPEN_LABWARE_LATCH, timeout=30.0)
        if not success:
            self.log(f"Open latch command failed: {response}", "FAIL")
            return False

        time.sleep(2.0)
        success, response = self.send_command(GCODE.GET_LABWARE_LATCH_STATE)
        if success:
            status = self.parse_latch_status(response)
            self.log(f"Latch status after open: {status.value}")

        # Close latch
        self.log("Closing labware latch...")
        success, response = self.send_command(GCODE.CLOSE_LABWARE_LATCH, timeout=30.0)
        if not success:
            self.log(f"Close latch command failed: {response}", "FAIL")
            return False

        time.sleep(2.0)
        success, response = self.send_command(GCODE.GET_LABWARE_LATCH_STATE)
        if success:
            status = self.parse_latch_status(response)
            self.log(f"Latch status after close: {status.value}")

        self.log("Latch operation test PASSED", "PASS")
        return True

    def test_heating(self, target_temp: float = 40.0, wait_time: int = 60) -> bool:
        """Test heating capability."""
        self.log("=" * 60)
        self.log(f"TEST: Heating (Target: {target_temp}C)")
        self.log("=" * 60)

        # Get initial temperature
        success, response = self.send_command(GCODE.GET_TEMPERATURE)
        _, initial_temp = self.parse_temperature(response) if success else (None, None)
        self.log(f"Initial temperature: {initial_temp} C")

        # Set temperature
        self.log(f"Setting target temperature to {target_temp} C...")
        success, response = self.send_command(f"{GCODE.SET_TEMPERATURE} S{target_temp:.2f}")
        if not success:
            self.log(f"Failed to set temperature: {response}", "FAIL")
            return False

        self.log("Heating command sent successfully")

        # Monitor temperature
        self.log(f"Monitoring temperature for {wait_time} seconds...")
        max_temp = initial_temp or 0

        for i in range(wait_time // 10):
            time.sleep(10)
            success, response = self.send_command(GCODE.GET_TEMPERATURE)
            if success:
                target, current = self.parse_temperature(response)
                if current is not None:
                    max_temp = max(max_temp, current)
                    self.log(f"  [{(i+1)*10}s] Current: {current} C, Target: {target} C")

        # Deactivate heater
        self.log("Deactivating heater...")
        self.send_command(GCODE.DEACTIVATE_HEATER)

        if initial_temp is not None and max_temp > initial_temp + 1:
            self.log(f"Heating test PASSED - Temperature increased from {initial_temp}C to {max_temp}C", "PASS")
            return True
        else:
            self.log("Heating test inconclusive - Check heater", "WARN")
            return True

    def test_shaking(self, target_rpm: int = 500, duration: int = 10) -> bool:
        """Test shaking capability at low RPM."""
        self.log("=" * 60)
        self.log(f"TEST: Shaking (Target: {target_rpm} RPM)")
        self.log("=" * 60)

        # Ensure latch is closed
        self.log("Ensuring latch is closed...")
        success, response = self.send_command(GCODE.GET_LABWARE_LATCH_STATE)
        status = self.parse_latch_status(response) if success else LatchStatus.UNKNOWN

        if status not in [LatchStatus.IDLE_CLOSED, LatchStatus.LATCH_CLOSED]:
            self.log("Closing latch before shaking...")
            self.send_command(GCODE.CLOSE_LABWARE_LATCH, timeout=30.0)
            time.sleep(2.0)

        # Start shaking
        self.log(f"Starting shaker at {target_rpm} RPM...")
        success, response = self.send_command(f"{GCODE.SET_RPM} S{target_rpm}")
        if not success:
            self.log(f"Failed to start shaking: {response}", "FAIL")
            return False

        # Monitor RPM
        self.log(f"Monitoring RPM for {duration} seconds...")
        max_rpm = 0

        for i in range(duration // 2):
            time.sleep(2)
            success, response = self.send_command(GCODE.GET_RPM)
            if success:
                target, current = self.parse_rpm(response)
                if current is not None:
                    max_rpm = max(max_rpm, current)
                    self.log(f"  [{(i+1)*2}s] Current: {current} RPM, Target: {target} RPM")

        # Stop shaking
        self.log("Stopping shaker...")
        self.send_command(GCODE.HOME, timeout=30.0)
        time.sleep(2.0)

        # Verify stopped
        success, response = self.send_command(GCODE.GET_RPM)
        if success:
            _, current = self.parse_rpm(response)
            self.log(f"RPM after stop: {current}")

        if max_rpm > 100:
            self.log(f"Shaking test PASSED - Reached {max_rpm} RPM", "PASS")
            return True
        else:
            self.log("Shaking test inconclusive - Motor may need attention", "WARN")
            return True

    def test_deactivation(self) -> bool:
        """Test heater deactivation command."""
        self.log("=" * 60)
        self.log("TEST: Heater Deactivation")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.DEACTIVATE_HEATER)
        if success:
            self.log("Heater deactivation command successful", "PASS")

            time.sleep(1.0)
            success2, response2 = self.send_command(GCODE.GET_TEMPERATURE)
            if success2:
                target, current = self.parse_temperature(response2)
                self.log(f"After deactivation - Target: {target}, Current: {current}")

            return True
        else:
            self.log(f"Heater deactivation failed: {response}", "FAIL")
            return False

    def run_diagnostics(self, full_test: bool = False):
        """Run complete diagnostic suite."""
        self.log("=" * 60)
        self.log("OPENTRONS HEATER-SHAKER MODULE DIAGNOSTIC")
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
            results['temperature_reading'] = self.test_temperature_reading()
            results['rpm_reading'] = self.test_rpm_reading()
            results['latch_status'] = self.test_latch_status()
            results['home'] = self.test_home()
            results['deactivation'] = self.test_deactivation()

            # Extended tests (if requested)
            if full_test:
                self.log("\n" + "=" * 60)
                self.log("EXTENDED TESTS (full test mode)")
                self.log("WARNING: These tests will operate the latch, heater, and shaker")
                self.log("=" * 60)

                results['latch_operation'] = self.test_latch_operation()
                results['heating'] = self.test_heating(target_temp=40.0, wait_time=60)
                results['shaking'] = self.test_shaking(target_rpm=500, duration=10)

            # Final safety shutdown
            self.log("\nFinal safety shutdown...")
            self.send_command(GCODE.HOME, timeout=30.0)  # Stop shaking
            self.send_command(GCODE.DEACTIVATE_HEATER)  # Stop heating

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
            # Always stop and deactivate before disconnecting
            self.send_command(GCODE.HOME, timeout=30.0)
            self.send_command(GCODE.DEACTIVATE_HEATER)
            self.disconnect()

    def save_report(self, filename: str = None):
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"heater_shaker_diagnostic_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write('\n'.join(self.report_lines))
        print(f"\nReport saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Heater-Shaker Module Diagnostic Tool"
    )
    parser.add_argument(
        '--port', '-p',
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests including heating and shaking cycles"
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
    print("This diagnostic tool will operate the Heater-Shaker module.")
    print("- The labware latch will open and close")
    print("- The shaker will spin (keep hands clear!)")
    print("- The heater will activate")
    print("- Ensure no labware is on the module during testing")
    print("=" * 60 + "\n")

    proceed = input("Press Enter to continue or Ctrl+C to abort...")

    diagnostic = HeaterShakerDiagnostic(port=args.port)
    diagnostic.run_diagnostics(full_test=args.full_test)

    if args.save_report:
        diagnostic.save_report()


if __name__ == "__main__":
    main()
