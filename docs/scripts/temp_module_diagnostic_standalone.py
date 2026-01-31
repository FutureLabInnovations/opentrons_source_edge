#!/usr/bin/env python3
"""
Temperature Module GEN2 - Standalone Diagnostic Script

This script performs direct serial communication diagnostics with the
Temperature Module without requiring the Opentrons robot software stack.

Requirements:
    pip install pyserial

Usage:
    python3 temp_module_diagnostic_standalone.py [--port /dev/ttyACM0]

Author: Opentrons Field Service
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed.")
    print("Install with: pip install pyserial")
    sys.exit(1)


class TempModuleGcodes:
    """G-code commands for Temperature Module"""
    GET_TEMP = "M105"
    SET_TEMP = "M104"
    DEVICE_INFO = "M115"
    GET_RESET_REASON = "M114"
    DISENGAGE = "M18"
    DFU = "dfu"


class TempModuleDiagnostic:
    """
    Standalone diagnostic utility for Opentrons Temperature Module GEN2.
    Communicates directly via USB serial without robot software.
    """

    # Communication parameters
    BAUDRATE = 115200
    TERMINATOR = "\r\n\r\n"
    ACK = "ok\r\nok\r\n"
    TIMEOUT = 3.0
    RETRIES = 3

    # Safe test parameters (won't damage module or burn user)
    SAFE_TEST_TEMP = 30  # °C - Slightly above room temp
    TEMP_TOLERANCE = 2.0  # °C

    def __init__(self, port: str, verbose: bool = False):
        """
        Initialize diagnostic utility.

        Args:
            port: Serial port path (e.g., /dev/ttyACM0 or COM3)
            verbose: Enable verbose output
        """
        self.port = port
        self.verbose = verbose
        self.serial_conn: Optional[serial.Serial] = None
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "port": port,
            "module_type": "Temperature Module GEN2",
            "tests": {},
            "overall_status": "PENDING"
        }

    def log(self, message: str, level: str = "INFO") -> None:
        """Print log message if verbose mode enabled"""
        if self.verbose or level in ["ERROR", "WARN"]:
            print(f"[{level}] {message}")

    @staticmethod
    def find_modules() -> List[Dict[str, Any]]:
        """
        Scan for potential Temperature Modules on USB ports.

        Returns:
            List of dictionaries with port information
        """
        candidates = []
        for port in serial.tools.list_ports.comports():
            # Temperature modules appear as Arduino Leonardo (ATmega32U4)
            is_candidate = False

            # Check by description
            if port.description and ("Arduino" in port.description or
                                     "Leonardo" in port.description):
                is_candidate = True

            # Check by VID:PID (Arduino Leonardo: 2341:8036 or 2341:0036)
            if port.vid == 0x2341 and port.pid in [0x8036, 0x0036]:
                is_candidate = True

            # Check by device name pattern
            if port.device and ("ttyACM" in port.device or "COM" in port.device):
                is_candidate = True

            if is_candidate:
                candidates.append({
                    "port": port.device,
                    "description": port.description or "Unknown",
                    "vid": f"0x{port.vid:04x}" if port.vid else None,
                    "pid": f"0x{port.pid:04x}" if port.pid else None,
                    "serial_number": port.serial_number
                })

        return candidates

    def connect(self) -> bool:
        """
        Establish serial connection to module.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.BAUDRATE,
                timeout=self.TIMEOUT,
                write_timeout=self.TIMEOUT
            )
            # Clear any pending data
            time.sleep(0.5)
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()

            self.log(f"Connected to {self.port}")
            self.results["tests"]["connection"] = {"status": "PASS", "port": self.port}
            return True

        except serial.SerialException as e:
            self.log(f"Failed to connect: {e}", "ERROR")
            self.results["tests"]["connection"] = {"status": "FAIL", "error": str(e)}
            return False

    def disconnect(self) -> None:
        """Close serial connection"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.log("Disconnected")

    def send_command(self, command: str, expect_response: bool = True) -> Optional[str]:
        """
        Send G-code command and receive response.

        Args:
            command: G-code command (without terminator)
            expect_response: Whether to wait for response

        Returns:
            Response string or None on failure
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("Not connected to module")

        full_command = f"{command}{self.TERMINATOR}"
        self.log(f"TX: {repr(command)}")

        for attempt in range(self.RETRIES):
            try:
                # Clear buffers
                self.serial_conn.reset_input_buffer()

                # Send command
                self.serial_conn.write(full_command.encode('ascii'))
                self.serial_conn.flush()

                if not expect_response:
                    return None

                # Read response
                response = b""
                start_time = time.time()

                while time.time() - start_time < self.TIMEOUT:
                    if self.serial_conn.in_waiting:
                        chunk = self.serial_conn.read(self.serial_conn.in_waiting)
                        response += chunk

                        # Check for acknowledgment
                        if self.ACK.encode() in response:
                            break
                    else:
                        time.sleep(0.05)

                response_str = response.decode('ascii', errors='replace').strip()
                self.log(f"RX: {repr(response_str)}")

                if "ok" in response_str.lower():
                    return response_str

            except (serial.SerialException, serial.SerialTimeoutException) as e:
                self.log(f"Attempt {attempt + 1} failed: {e}", "WARN")
                time.sleep(0.5)

        return None

    def parse_temperature_response(self, response: str) -> Dict[str, Optional[float]]:
        """
        Parse M105 temperature response.

        Args:
            response: Raw response string

        Returns:
            Dictionary with 'current' and 'target' temperatures
        """
        result = {"current": None, "target": None}

        # Format: "T:37.000 C:25.123\r\nok\r\nok\r\n"
        for part in response.split():
            if part.startswith("C:"):
                try:
                    result["current"] = float(part[2:])
                except ValueError:
                    pass
            elif part.startswith("T:"):
                value = part[2:]
                if value.lower() != "none":
                    try:
                        result["target"] = float(value)
                    except ValueError:
                        pass

        return result

    def parse_device_info(self, response: str) -> Dict[str, str]:
        """
        Parse M115 device info response.

        Args:
            response: Raw response string

        Returns:
            Dictionary with serial, model, version
        """
        result = {"serial": "UNKNOWN", "model": "UNKNOWN", "version": "UNKNOWN"}

        # Format: "serial:XXX model:XXX version:XXX\r\nok\r\nok\r\n"
        for part in response.replace("\r\n", " ").split():
            if ":" in part:
                key, value = part.split(":", 1)
                if key in result:
                    result[key] = value

        return result

    # ==================== DIAGNOSTIC TESTS ====================

    def test_device_info(self) -> Dict[str, Any]:
        """Test M115 - Get Device Information"""
        test = {"command": "M115", "status": "PENDING"}

        response = self.send_command(TempModuleGcodes.DEVICE_INFO)

        if response:
            test["raw_response"] = response
            info = self.parse_device_info(response)
            test.update(info)

            # Determine generation from model
            model = info.get("model", "")
            if "v2" in model.lower():
                # Check numeric version (v20+ is GEN2)
                try:
                    version_num = int(model.lower().replace("temp_deck_v", "").split(".")[0])
                    test["generation"] = "GEN2" if version_num >= 20 else "GEN1"
                except (ValueError, IndexError):
                    test["generation"] = "GEN2"  # Assume if has v2 prefix
            elif "v1" in model.lower():
                test["generation"] = "GEN1"
            else:
                test["generation"] = "UNKNOWN"

            test["status"] = "PASS"
        else:
            test["status"] = "FAIL"
            test["error"] = "No response received"

        return test

    def test_temperature_reading(self) -> Dict[str, Any]:
        """Test M105 - Get Current Temperature"""
        test = {"command": "M105", "status": "PENDING"}

        response = self.send_command(TempModuleGcodes.GET_TEMP)

        if response:
            test["raw_response"] = response
            temps = self.parse_temperature_response(response)
            test["current_temperature"] = temps["current"]
            test["target_temperature"] = temps["target"]

            # Validate reading is reasonable
            if temps["current"] is not None:
                if -20 <= temps["current"] <= 120:
                    test["status"] = "PASS"
                else:
                    test["status"] = "WARN"
                    test["note"] = f"Temperature {temps['current']}°C outside expected range"
            else:
                test["status"] = "FAIL"
                test["error"] = "Could not parse temperature value"
        else:
            test["status"] = "FAIL"
            test["error"] = "No response received"

        return test

    def test_set_temperature(self, target: float) -> Dict[str, Any]:
        """Test M104 - Set Target Temperature"""
        test = {"command": f"M104 S{target}", "target": target, "status": "PENDING"}

        response = self.send_command(f"{TempModuleGcodes.SET_TEMP} S{target}")

        if response and "ok" in response.lower():
            test["raw_response"] = response
            test["status"] = "PASS"
            test["note"] = "Command accepted"
        else:
            test["status"] = "FAIL"
            test["error"] = "No acknowledgment received"
            test["raw_response"] = response

        return test

    def test_verify_target(self, expected_target: float) -> Dict[str, Any]:
        """Verify target temperature was set correctly"""
        test = {"command": "M105 (verify)", "expected_target": expected_target, "status": "PENDING"}

        # Wait for module to update
        time.sleep(1)

        response = self.send_command(TempModuleGcodes.GET_TEMP)

        if response:
            test["raw_response"] = response
            temps = self.parse_temperature_response(response)
            test["current_temperature"] = temps["current"]
            test["target_temperature"] = temps["target"]

            if temps["target"] is not None:
                if abs(temps["target"] - expected_target) < 1.0:
                    test["status"] = "PASS"
                else:
                    test["status"] = "FAIL"
                    test["error"] = f"Target mismatch: expected {expected_target}, got {temps['target']}"
            else:
                test["status"] = "FAIL"
                test["error"] = "No target temperature reported"
        else:
            test["status"] = "FAIL"
            test["error"] = "No response received"

        return test

    def test_deactivate(self) -> Dict[str, Any]:
        """Test M18 - Deactivate Module"""
        test = {"command": "M18", "status": "PENDING"}

        response = self.send_command(TempModuleGcodes.DISENGAGE)

        if response and "ok" in response.lower():
            test["raw_response"] = response
            test["status"] = "PASS"

            # Verify deactivation
            time.sleep(1)
            verify_response = self.send_command(TempModuleGcodes.GET_TEMP)
            if verify_response:
                temps = self.parse_temperature_response(verify_response)
                test["target_after"] = temps["target"]
                if temps["target"] is None:
                    test["verified"] = True
                else:
                    test["note"] = "Target still set after deactivate"
        else:
            test["status"] = "FAIL"
            test["error"] = "No acknowledgment received"

        return test

    # ==================== MAIN DIAGNOSTIC RUNNER ====================

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """
        Run complete diagnostic test suite.

        Returns:
            Dictionary with all test results
        """
        print("=" * 60)
        print("TEMPERATURE MODULE GEN2 - STANDALONE DIAGNOSTIC")
        print("=" * 60)
        print(f"Port: {self.port}")
        print(f"Timestamp: {self.results['timestamp']}")
        print("=" * 60)

        # Test 1: Connection
        print("\n[1/6] Testing Connection...")
        if not self.connect():
            self.results["overall_status"] = "FAIL"
            return self.results
        print(f"      Result: [PASS]")

        # Test 2: Device Info
        print("\n[2/6] Getting Device Information...")
        device_info = self.test_device_info()
        self.results["tests"]["device_info"] = device_info
        print(f"      Serial: {device_info.get('serial', 'N/A')}")
        print(f"      Model: {device_info.get('model', 'N/A')}")
        print(f"      Firmware: {device_info.get('version', 'N/A')}")
        print(f"      Generation: {device_info.get('generation', 'N/A')}")
        print(f"      Result: [{device_info['status']}]")

        # Test 3: Temperature Reading
        print("\n[3/6] Reading Temperature...")
        temp_reading = self.test_temperature_reading()
        self.results["tests"]["temperature_reading"] = temp_reading
        print(f"      Current: {temp_reading.get('current_temperature', 'N/A')}°C")
        print(f"      Target: {temp_reading.get('target_temperature', 'None')}")
        print(f"      Result: [{temp_reading['status']}]")

        # Test 4: Set Temperature
        print(f"\n[4/6] Setting Temperature to {self.SAFE_TEST_TEMP}°C...")
        set_temp = self.test_set_temperature(self.SAFE_TEST_TEMP)
        self.results["tests"]["set_temperature"] = set_temp
        print(f"      Result: [{set_temp['status']}]")

        # Test 5: Verify Target
        print("\n[5/6] Verifying Target Temperature...")
        verify = self.test_verify_target(self.SAFE_TEST_TEMP)
        self.results["tests"]["verify_target"] = verify
        print(f"      Target Confirmed: {verify.get('target_temperature', 'N/A')}°C")
        print(f"      Result: [{verify['status']}]")

        # Test 6: Deactivate
        print("\n[6/6] Deactivating Module...")
        deactivate = self.test_deactivate()
        self.results["tests"]["deactivate"] = deactivate
        print(f"      Result: [{deactivate['status']}]")

        # Calculate overall status
        all_passed = all(
            test.get("status") in ["PASS", "WARN"]
            for test in self.results["tests"].values()
        )
        self.results["overall_status"] = "PASS" if all_passed else "FAIL"

        # Cleanup
        self.disconnect()

        # Summary
        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 60)
        for test_name, test_result in self.results["tests"].items():
            status = test_result.get("status", "N/A")
            symbol = "PASS" if status == "PASS" else "WARN" if status == "WARN" else "FAIL"
            print(f"  {test_name:.<40} [{symbol}]")
        print("=" * 60)
        print(f"OVERALL STATUS: [{self.results['overall_status']}]")
        print("=" * 60)

        return self.results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Opentrons Temperature Module GEN2 Standalone Diagnostic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 temp_module_diagnostic_standalone.py
  python3 temp_module_diagnostic_standalone.py --port /dev/ttyACM0
  python3 temp_module_diagnostic_standalone.py --scan
  python3 temp_module_diagnostic_standalone.py --output results.json
        """
    )

    parser.add_argument("--port", "-p", type=str, help="Serial port (e.g., /dev/ttyACM0)")
    parser.add_argument("--scan", "-s", action="store_true", help="Scan for modules")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Scan mode
    if args.scan:
        print("Scanning for Temperature Modules...\n")
        modules = TempModuleDiagnostic.find_modules()
        if modules:
            print("Found potential modules:")
            for i, mod in enumerate(modules):
                print(f"  [{i}] {mod['port']}")
                print(f"      Description: {mod['description']}")
                print(f"      VID:PID: {mod['vid']}:{mod['pid']}")
                print()
        else:
            print("No potential Temperature Modules found.")
        return

    # Determine port
    port = args.port
    if not port:
        modules = TempModuleDiagnostic.find_modules()
        if not modules:
            print("No Temperature Modules found. Use --port to specify manually.")
            sys.exit(1)
        elif len(modules) == 1:
            port = modules[0]["port"]
            print(f"Auto-detected module at {port}\n")
        else:
            print("Multiple potential modules found:")
            for i, mod in enumerate(modules):
                print(f"  [{i}] {mod['port']} - {mod['description']}")
            try:
                idx = int(input("Select module number: "))
                port = modules[idx]["port"]
            except (ValueError, IndexError):
                print("Invalid selection.")
                sys.exit(1)

    # Run diagnostic
    diag = TempModuleDiagnostic(port=port, verbose=args.verbose)
    results = diag.run_full_diagnostic()

    # Save results
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"temp_module_diagnostic_{timestamp}.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    # Exit code based on status
    sys.exit(0 if results["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
