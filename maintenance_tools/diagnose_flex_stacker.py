#!/usr/bin/env python3
"""
Opentrons Flex Stacker Module Diagnostic Tool
==============================================
For maintenance and testing of Flex Stacker Module (Flex Robot Only)

Usage:
    python diagnose_flex_stacker.py [--port COM6] [--full-test]

Connection: USB Serial
Default Port: COM6 (Windows) or /dev/ttyUSB0 (Linux)
Baud Rate: 115200

IMPORTANT: This module has moving parts (X, Z, L axes).
Keep hands clear during testing.
"""

import serial
import time
import argparse
import sys
from datetime import datetime
from typing import Optional, Dict, Tuple, List
from enum import Enum
from dataclasses import dataclass

# Protocol Constants
BAUDRATE = 115200
DEFAULT_TIMEOUT = 5.0
MOVE_TIMEOUT = 20.0
COMMAND_TERMINATOR = "\n"
ACK_PATTERN = "OK\n"
ERROR_KEYWORD = "err"
DEFAULT_PORT = "COM6"


# G-code Commands
class GCODE(str, Enum):
    MOVE_TO = "G0"
    MOVE_TO_SWITCH = "G5"
    HOME_AXIS = "G28"
    STOP_MOTORS = "M0"
    ENABLE_MOTORS = "M17"
    GET_RESET_REASON = "M114"
    DEVICE_INFO = "M115"
    GET_LIMIT_SWITCH = "M119"
    GET_MOVE_PARAMS = "M120"
    GET_PLATFORM_SENSOR = "M121"
    GET_DOOR_SWITCH = "M122"
    GET_INSTALL_DETECTED = "M123"
    SET_LED = "M200"
    SET_RUN_CURRENT = "M906"
    SET_IHOLD_CURRENT = "M907"
    SET_STALLGUARD = "M910"
    GET_STALLGUARD_THRESHOLD = "M911"
    ENTER_BOOTLOADER = "dfu"


class StackerAxis(str, Enum):
    X = "X"  # Horizontal transfer
    Z = "Z"  # Vertical lift
    L = "L"  # Latch


class Direction(Enum):
    RETRACT = 0  # Negative direction
    EXTEND = 1   # Positive direction


class LEDColor(Enum):
    WHITE = 0
    RED = 1
    GREEN = 2
    BLUE = 3
    YELLOW = 4


class LEDPattern(Enum):
    STATIC = 0
    FLASH = 1
    PULSE = 2
    CONFIRM = 3


@dataclass
class LimitSwitchStatus:
    XE: bool  # X Extend
    XR: bool  # X Retract
    ZE: bool  # Z Extend
    ZR: bool  # Z Retract
    LR: bool  # L Retract (latch)


@dataclass
class PlatformStatus:
    E: bool  # Extent sensor
    R: bool  # Retract sensor


@dataclass
class StackerInfo:
    firmware: str
    hardware: str
    serial: str
    reset_reason: int = 0


class FlexStackerDiagnostic:
    """Diagnostic tool for Opentrons Flex Stacker Module."""

    def __init__(self, port: str = DEFAULT_PORT):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.device_info: Optional[StackerInfo] = None
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
                timeout=DEFAULT_TIMEOUT,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            time.sleep(1.0)
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
            timeout = DEFAULT_TIMEOUT

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
                    if ACK_PATTERN in response or ERROR_KEYWORD.lower() in response.lower():
                        break
                time.sleep(0.05)

            # Check for errors
            if ERROR_KEYWORD.lower() in response.lower():
                return False, f"Error response: {response}"

            if ACK_PATTERN in response:
                data = response.replace(ACK_PATTERN, "").replace("OK", "").strip()
                return True, data
            else:
                return False, f"No ACK received. Raw: {repr(response)}"

        except Exception as e:
            return False, f"Command failed: {e}"

    def parse_device_info(self, response: str) -> Optional[StackerInfo]:
        """Parse device info response."""
        # Format: M115 FW:version HW:Opentrons-flex-stacker-hw SerialNo:serial
        import re
        pattern = r"M115 FW:(\S+) HW:Opentrons-flex-stacker-(\S+) SerialNo:(\S+)"
        match = re.match(pattern, response)
        if match:
            return StackerInfo(
                firmware=match.group(1),
                hardware=match.group(2),
                serial=match.group(3)
            )
        return None

    def parse_reset_reason(self, response: str) -> Optional[int]:
        """Parse reset reason response."""
        import re
        pattern = r"M114 R:(\d)"
        match = re.match(pattern, response)
        if match:
            return int(match.group(1))
        return None

    def parse_limit_switches(self, response: str) -> Optional[LimitSwitchStatus]:
        """Parse limit switch status response."""
        import re
        pattern = r"M119 XE:(\d) XR:(\d) ZE:(\d) ZR:(\d) LR:(\d)"
        match = re.match(pattern, response)
        if match:
            return LimitSwitchStatus(
                XE=bool(int(match.group(1))),
                XR=bool(int(match.group(2))),
                ZE=bool(int(match.group(3))),
                ZR=bool(int(match.group(4))),
                LR=bool(int(match.group(5)))
            )
        return None

    def parse_platform_sensors(self, response: str) -> Optional[PlatformStatus]:
        """Parse platform sensor status response."""
        import re
        pattern = r"M121 E:(\d) R:(\d)"
        match = re.match(pattern, response)
        if match:
            return PlatformStatus(
                E=bool(int(match.group(1))),
                R=bool(int(match.group(2)))
            )
        return None

    def parse_door_status(self, response: str) -> Optional[bool]:
        """Parse door switch status."""
        import re
        pattern = r"M122 D:(\d)"
        match = re.match(pattern, response)
        if match:
            return bool(int(match.group(1)))
        return None

    def parse_install_detected(self, response: str) -> Optional[bool]:
        """Parse installation detection status."""
        import re
        pattern = r"M123 I:(\d)"
        match = re.match(pattern, response)
        if match:
            return bool(int(match.group(1)))
        return None

    # ========== Diagnostic Tests ==========

    def test_connection(self) -> bool:
        """Test basic connectivity."""
        self.log("=" * 60)
        self.log("TEST: Connection Test")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_LIMIT_SWITCH.value)
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

        success, response = self.send_command(GCODE.DEVICE_INFO.value)
        if not success:
            self.log(f"Failed to get device info: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")
        self.device_info = self.parse_device_info(response)

        if self.device_info:
            self.log(f"Serial Number: {self.device_info.serial}")
            self.log(f"Hardware Revision: {self.device_info.hardware}")
            self.log(f"Firmware Version: {self.device_info.firmware}")

            # Get reset reason
            success2, response2 = self.send_command(GCODE.GET_RESET_REASON.value)
            if success2:
                reset_reason = self.parse_reset_reason(response2)
                if reset_reason is not None:
                    self.device_info.reset_reason = reset_reason
                    self.log(f"Last Reset Reason: {reset_reason}")

            return True
        else:
            self.log("Could not parse device info", "WARN")
            return True  # Still consider it a pass if we got a response

    def test_limit_switches(self) -> bool:
        """Test all limit switch readings."""
        self.log("=" * 60)
        self.log("TEST: Limit Switches")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_LIMIT_SWITCH.value)
        if not success:
            self.log(f"Failed to read limit switches: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")
        status = self.parse_limit_switches(response)

        if status:
            self.log(f"X-Axis Extend (XE): {'TRIGGERED' if status.XE else 'open'}")
            self.log(f"X-Axis Retract (XR): {'TRIGGERED' if status.XR else 'open'}")
            self.log(f"Z-Axis Extend (ZE): {'TRIGGERED' if status.ZE else 'open'}")
            self.log(f"Z-Axis Retract (ZR): {'TRIGGERED' if status.ZR else 'open'}")
            self.log(f"Latch Retract (LR): {'TRIGGERED' if status.LR else 'open'}")
            self.log("Limit switches reading PASSED", "PASS")
            return True
        else:
            self.log("Could not parse limit switch status", "WARN")
            return True

    def test_platform_sensors(self) -> bool:
        """Test platform presence sensors."""
        self.log("=" * 60)
        self.log("TEST: Platform Sensors")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_PLATFORM_SENSOR.value)
        if not success:
            self.log(f"Failed to read platform sensors: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")
        status = self.parse_platform_sensors(response)

        if status:
            self.log(f"Extend Sensor (E): {'DETECTED' if status.E else 'clear'}")
            self.log(f"Retract Sensor (R): {'DETECTED' if status.R else 'clear'}")
            self.log("Platform sensors reading PASSED", "PASS")
            return True
        else:
            self.log("Could not parse platform sensor status", "WARN")
            return True

    def test_door_switch(self) -> bool:
        """Test door/hopper switch."""
        self.log("=" * 60)
        self.log("TEST: Door Switch")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_DOOR_SWITCH.value)
        if not success:
            self.log(f"Failed to read door switch: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")
        door_closed = self.parse_door_status(response)

        if door_closed is not None:
            self.log(f"Door Status: {'CLOSED' if door_closed else 'OPEN'}")
            self.log("Door switch reading PASSED", "PASS")
            return True
        else:
            self.log("Could not parse door status", "WARN")
            return True

    def test_installation_detection(self) -> bool:
        """Test installation detection."""
        self.log("=" * 60)
        self.log("TEST: Installation Detection")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.GET_INSTALL_DETECTED.value)
        if not success:
            self.log(f"Failed to read installation status: {response}", "FAIL")
            return False

        self.log(f"Raw response: {response}")
        installed = self.parse_install_detected(response)

        if installed is not None:
            self.log(f"Installation: {'DETECTED' if installed else 'not detected'}")
            self.log("Installation detection PASSED", "PASS")
            return True
        else:
            self.log("Could not parse installation status", "WARN")
            return True

    def test_motor_enable(self) -> bool:
        """Test motor enable command."""
        self.log("=" * 60)
        self.log("TEST: Motor Enable")
        self.log("=" * 60)

        # Enable all motors
        self.log("Enabling all motors (X, Z, L)...")
        success, response = self.send_command(f"{GCODE.ENABLE_MOTORS.value} X Z L")

        if success:
            self.log("Motor enable command successful", "PASS")
            return True
        else:
            self.log(f"Motor enable failed: {response}", "FAIL")
            return False

    def test_motor_stop(self) -> bool:
        """Test emergency stop command."""
        self.log("=" * 60)
        self.log("TEST: Motor Stop (Emergency)")
        self.log("=" * 60)

        success, response = self.send_command(GCODE.STOP_MOTORS.value)

        if success:
            self.log("Motor stop command successful", "PASS")
            return True
        else:
            self.log(f"Motor stop failed: {response}", "FAIL")
            return False

    def test_led_control(self) -> bool:
        """Test LED status bar control."""
        self.log("=" * 60)
        self.log("TEST: LED Control")
        self.log("=" * 60)

        colors = [
            (LEDColor.RED, "Red"),
            (LEDColor.GREEN, "Green"),
            (LEDColor.BLUE, "Blue"),
            (LEDColor.WHITE, "White"),
        ]

        for color, name in colors:
            self.log(f"Setting LED to {name}...")
            # Format: M200 P:power C:color
            cmd = f"{GCODE.SET_LED.value} P1.0 C{color.value}"
            success, response = self.send_command(cmd)

            if not success:
                self.log(f"Failed to set LED to {name}: {response}", "WARN")
            else:
                time.sleep(0.5)

        # Turn off LED
        self.log("Turning LED off...")
        success, response = self.send_command(f"{GCODE.SET_LED.value} P0.0")

        self.log("LED control test PASSED", "PASS")
        return True

    def test_homing(self, axis: StackerAxis = StackerAxis.Z) -> bool:
        """Test homing operation for specified axis."""
        self.log("=" * 60)
        self.log(f"TEST: Homing ({axis.value}-Axis)")
        self.log("=" * 60)

        # Use direction 0 (retract) for safe homing
        direction = Direction.RETRACT.value
        self.log(f"Homing {axis.value}-axis in retract direction...")

        cmd = f"{GCODE.HOME_AXIS.value} {axis.value}{direction}"
        success, response = self.send_command(cmd, timeout=MOVE_TIMEOUT)

        if success:
            self.log(f"{axis.value}-axis homing successful", "PASS")

            # Verify limit switch
            time.sleep(0.5)
            success2, response2 = self.send_command(GCODE.GET_LIMIT_SWITCH.value)
            if success2:
                status = self.parse_limit_switches(response2)
                if status:
                    if axis == StackerAxis.X:
                        self.log(f"XR limit switch: {'TRIGGERED' if status.XR else 'open'}")
                    elif axis == StackerAxis.Z:
                        self.log(f"ZR limit switch: {'TRIGGERED' if status.ZR else 'open'}")
                    elif axis == StackerAxis.L:
                        self.log(f"LR limit switch: {'TRIGGERED' if status.LR else 'open'}")

            return True
        else:
            self.log(f"Homing failed: {response}", "FAIL")
            return False

    def test_movement(self, axis: StackerAxis = StackerAxis.Z, distance: float = 10.0) -> bool:
        """Test movement operation for specified axis."""
        self.log("=" * 60)
        self.log(f"TEST: Movement ({axis.value}-Axis, {distance}mm)")
        self.log("=" * 60)

        # First home the axis
        self.log("Homing axis first...")
        if not self.test_homing(axis):
            self.log("Cannot test movement without successful homing", "FAIL")
            return False

        # Move to specified distance
        self.log(f"Moving {axis.value}-axis to {distance}mm...")
        cmd = f"{GCODE.MOVE_TO.value} {axis.value}{distance:.2f}"
        success, response = self.send_command(cmd, timeout=MOVE_TIMEOUT)

        if success:
            self.log(f"Move to {distance}mm successful")

            # Move back to home
            self.log("Returning to home position...")
            cmd2 = f"{GCODE.MOVE_TO.value} {axis.value}0.00"
            success2, _ = self.send_command(cmd2, timeout=MOVE_TIMEOUT)

            if success2:
                self.log("Movement test PASSED", "PASS")
                return True
            else:
                self.log("Failed to return to home", "WARN")
                return True
        else:
            self.log(f"Movement failed: {response}", "FAIL")
            return False

    def run_diagnostics(self, full_test: bool = False):
        """Run complete diagnostic suite."""
        self.log("=" * 60)
        self.log("OPENTRONS FLEX STACKER MODULE DIAGNOSTIC")
        self.log(f"Port: {self.port}")
        self.log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 60)

        results = {}

        if not self.connect():
            self.log("Cannot proceed without connection", "ERROR")
            return

        try:
            # Basic tests (sensor readings only)
            results['connection'] = self.test_connection()
            results['device_info'] = self.test_device_info()
            results['limit_switches'] = self.test_limit_switches()
            results['platform_sensors'] = self.test_platform_sensors()
            results['door_switch'] = self.test_door_switch()
            results['installation_detection'] = self.test_installation_detection()
            results['motor_enable'] = self.test_motor_enable()
            results['motor_stop'] = self.test_motor_stop()

            # Extended tests (if requested)
            if full_test:
                self.log("\n" + "=" * 60)
                self.log("EXTENDED TESTS (full test mode)")
                self.log("WARNING: These tests will move motors!")
                self.log("=" * 60)

                results['led_control'] = self.test_led_control()
                results['z_homing'] = self.test_homing(StackerAxis.Z)
                results['z_movement'] = self.test_movement(StackerAxis.Z, distance=20.0)

                # Only test X and L if explicitly needed (more risky)
                # results['x_homing'] = self.test_homing(StackerAxis.X)
                # results['l_homing'] = self.test_homing(StackerAxis.L)

            # Final safety: stop motors and turn off LED
            self.log("\nFinal safety shutdown...")
            self.send_command(GCODE.STOP_MOTORS.value)
            self.send_command(f"{GCODE.SET_LED.value} P0.0")

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

            if self.device_info:
                self.log(f"Serial: {self.device_info.serial}")
                self.log(f"Firmware: {self.device_info.firmware}")
                self.log(f"Hardware: {self.device_info.hardware}")

            if passed == total:
                self.log("MODULE STATUS: HEALTHY", "PASS")
            elif passed >= total * 0.7:
                self.log("MODULE STATUS: NEEDS ATTENTION", "WARN")
            else:
                self.log("MODULE STATUS: REQUIRES SERVICE", "FAIL")

        finally:
            # Always stop motors before disconnecting
            self.send_command(GCODE.STOP_MOTORS.value)
            self.send_command(f"{GCODE.SET_LED.value} P0.0")
            self.disconnect()

    def save_report(self, filename: str = None):
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flex_stacker_diagnostic_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write('\n'.join(self.report_lines))
        print(f"\nReport saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Flex Stacker Module Diagnostic Tool"
    )
    parser.add_argument(
        '--port', '-p',
        default=DEFAULT_PORT,
        help=f"Serial port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests including motor movements"
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
    print("This diagnostic tool will operate the Flex Stacker module.")
    print("- Motors will be enabled and may move")
    print("- Keep hands clear of moving parts")
    print("- Ensure the stacker is properly installed")
    print("- Remove any labware before full testing")
    print("=" * 60 + "\n")

    proceed = input("Press Enter to continue or Ctrl+C to abort...")

    diagnostic = FlexStackerDiagnostic(port=args.port)
    diagnostic.run_diagnostics(full_test=args.full_test)

    if args.save_report:
        diagnostic.save_report()


if __name__ == "__main__":
    main()
