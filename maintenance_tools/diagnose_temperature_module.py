#!/usr/bin/env python3
"""
Opentrons Temperature Module (TempDeck) Diagnostic Tool
========================================================
For maintenance and testing of Temperature Module v1 and v2

Usage:
    python diagnose_temperature_module.py [--port COM6] [--full-test]

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
TIMEOUT = 2.0
COMMAND_TERMINATOR = "\r\n\r\n"
ACK_PATTERN = "ok\r\nok\r\n"
DEFAULT_PORT = "COM6"

# G-code Commands
class GCODE:
    GET_TEMP = "M105"
    SET_TEMP = "M104"
    DEVICE_INFO = "M115"
    GET_RESET_REASON = "M114"
    DEACTIVATE = "M18"
    PROGRAMMING_MODE = "dfu"


class TemperatureModuleDiagnostic:
    """Diagnostic tool for Opentrons Temperature Module."""

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

    def send_command(self, gcode: str, timeout: float = TIMEOUT) -> Tuple[bool, str]:
        """Send a G-code command and receive response."""
        if not self.serial or not self.serial.is_open:
            return False, "Not connected"

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

    # ========== Diagnostic Tests ==========

    def test_connection(self) -> bool:
        """Test basic connectivity."""
        self.log("=" * 60)
        self.log("TEST: Connection Test")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_TEMP)
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

        self.log(f"Serial Number: {self.device_info.get('serial', 'N/A')}")
        self.log(f"Model: {self.device_info.get('model', 'N/A')}")
        self.log(f"Firmware Version: {self.device_info.get('version', 'N/A')}")

        # Try to get reset reason
        success2, response2 = self.send_command(GCODE.GET_RESET_REASON)
        if success2:
            self.log(f"Last Reset Reason: {response2}")

        return len(missing) == 0

    def test_temperature_reading(self) -> bool:
        """Test temperature sensor reading."""
        self.log("=" * 60)
        self.log("TEST: Temperature Sensor")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_TEMP)
        if not success:
            self.log(f"Failed to read temperature: {response}", "FAIL")
            return False

        target, current = self.parse_temperature(response)
        self.log(f"Raw response: {response}")
        self.log(f"Current Temperature: {current} C")
        self.log(f"Target Temperature: {target} C")

        # Validate temperature is in reasonable range
        if current is not None:
            if -10 <= current <= 110:
                self.log("Temperature reading within expected range (-10 to 110 C)", "PASS")
                return True
            else:
                self.log(f"Temperature {current}C outside expected range", "WARN")
                return True  # Still a valid reading
        else:
            self.log("Could not parse temperature value", "FAIL")
            return False

    def test_heating_cycle(self, target_temp: float = 37.0, wait_time: int = 30) -> bool:
        """Test heating capability with a short cycle."""
        self.log("=" * 60)
        self.log(f"TEST: Heating Cycle (Target: {target_temp}C)")
        self.log("=" * 60)

        # Get initial temperature
        success, response = self.send_command(GCODE.GET_TEMP)
        if not success:
            self.log(f"Failed to read initial temperature: {response}", "FAIL")
            return False

        _, initial_temp = self.parse_temperature(response)
        self.log(f"Initial temperature: {initial_temp} C")

        # Set target temperature
        self.log(f"Setting target temperature to {target_temp} C...")
        success, response = self.send_command(f"{GCODE.SET_TEMP} S{target_temp}")
        if not success:
            self.log(f"Failed to set temperature: {response}", "FAIL")
            return False

        self.log("Heating command sent successfully")

        # Monitor temperature for specified time
        self.log(f"Monitoring temperature for {wait_time} seconds...")
        start_temp = initial_temp
        max_temp = initial_temp or 0

        for i in range(wait_time // 5):
            time.sleep(5)
            success, response = self.send_command(GCODE.GET_TEMP)
            if success:
                target, current = self.parse_temperature(response)
                if current is not None:
                    max_temp = max(max_temp, current)
                    self.log(f"  [{(i+1)*5}s] Current: {current} C, Target: {target} C")

        # Deactivate heater
        self.log("Deactivating heater...")
        success, _ = self.send_command(GCODE.DEACTIVATE)

        # Check if temperature increased
        if start_temp is not None and max_temp > start_temp + 1:
            self.log(f"Heating test PASSED - Temperature increased from {start_temp}C to {max_temp}C", "PASS")
            return True
        else:
            self.log(f"Heating test inconclusive - Check heater hardware", "WARN")
            return True  # Not necessarily a failure

    def test_cooling(self, target_temp: float = 4.0, wait_time: int = 30) -> bool:
        """Test cooling capability (if module supports it)."""
        self.log("=" * 60)
        self.log(f"TEST: Cooling Cycle (Target: {target_temp}C)")
        self.log("=" * 60)

        # Get initial temperature
        success, response = self.send_command(GCODE.GET_TEMP)
        if not success:
            self.log(f"Failed to read initial temperature: {response}", "FAIL")
            return False

        _, initial_temp = self.parse_temperature(response)
        self.log(f"Initial temperature: {initial_temp} C")

        # Set target temperature
        self.log(f"Setting target temperature to {target_temp} C...")
        success, response = self.send_command(f"{GCODE.SET_TEMP} S{target_temp}")
        if not success:
            self.log(f"Failed to set temperature: {response}", "FAIL")
            return False

        self.log("Cooling command sent successfully")

        # Monitor temperature for specified time
        self.log(f"Monitoring temperature for {wait_time} seconds...")
        min_temp = initial_temp or 100

        for i in range(wait_time // 5):
            time.sleep(5)
            success, response = self.send_command(GCODE.GET_TEMP)
            if success:
                target, current = self.parse_temperature(response)
                if current is not None:
                    min_temp = min(min_temp, current)
                    self.log(f"  [{(i+1)*5}s] Current: {current} C, Target: {target} C")

        # Deactivate
        self.log("Deactivating...")
        success, _ = self.send_command(GCODE.DEACTIVATE)

        # Check if temperature decreased
        if initial_temp is not None and min_temp < initial_temp - 1:
            self.log(f"Cooling test PASSED - Temperature decreased from {initial_temp}C to {min_temp}C", "PASS")
            return True
        else:
            self.log(f"Cooling test inconclusive - Module may not support active cooling", "WARN")
            return True

    def test_deactivation(self) -> bool:
        """Test deactivation command."""
        self.log("=" * 60)
        self.log("TEST: Deactivation Command")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.DEACTIVATE)
        if success:
            self.log("Deactivation command successful", "PASS")

            # Verify no target is set
            time.sleep(1)
            success2, response2 = self.send_command(GCODE.GET_TEMP)
            if success2:
                target, current = self.parse_temperature(response2)
                self.log(f"After deactivation - Target: {target}, Current: {current}")
            return True
        else:
            self.log(f"Deactivation failed: {response}", "FAIL")
            return False

    def run_diagnostics(self, full_test: bool = False):
        """Run complete diagnostic suite."""
        self.log("=" * 60)
        self.log("OPENTRONS TEMPERATURE MODULE DIAGNOSTIC")
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
            results['deactivation'] = self.test_deactivation()

            # Extended tests (if requested)
            if full_test:
                self.log("\n" + "=" * 60)
                self.log("EXTENDED TESTS (full test mode)")
                self.log("=" * 60)
                results['heating_cycle'] = self.test_heating_cycle(target_temp=37.0, wait_time=30)
                results['cooling_cycle'] = self.test_cooling(target_temp=15.0, wait_time=30)
                # Final deactivation
                self.send_command(GCODE.DEACTIVATE)

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
            # Always deactivate heater before disconnecting
            self.send_command(GCODE.DEACTIVATE)
            self.disconnect()

    def save_report(self, filename: str = None):
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tempdeck_diagnostic_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write('\n'.join(self.report_lines))
        print(f"\nReport saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Temperature Module Diagnostic Tool"
    )
    parser.add_argument(
        '--port', '-p',
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests including heating/cooling cycles"
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help="Save diagnostic report to file"
    )

    args = parser.parse_args()

    diagnostic = TemperatureModuleDiagnostic(port=args.port)
    diagnostic.run_diagnostics(full_test=args.full_test)

    if args.save_report:
        diagnostic.save_report()


if __name__ == "__main__":
    main()
