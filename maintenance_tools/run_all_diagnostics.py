#!/usr/bin/env python3
"""
Opentrons Module Diagnostic Master Runner
==========================================
Central hub for running diagnostics on all Opentrons modules

Usage:
    python run_all_diagnostics.py --module tempdeck --port COM6
    python run_all_diagnostics.py --module magdeck --port COM6 --full-test
    python run_all_diagnostics.py --list

Supported Modules:
    - tempdeck    : Temperature Module (TempDeck) v1/v2
    - magdeck     : Magnetic Module (MagDeck) v1/v2
    - thermocycler: Thermocycler Module Gen1/Gen2
    - heatershaker: Heater-Shaker Module
    - flexstacker : Flex Stacker Module (Flex only)

Connection: USB Serial via COM port
Default Port: COM6 (Windows) or /dev/ttyUSB0 (Linux)
"""

import argparse
import sys
import os
from datetime import datetime

# Import diagnostic modules
try:
    from diagnose_temperature_module import TemperatureModuleDiagnostic
    from diagnose_magnetic_module import MagneticModuleDiagnostic
    from diagnose_thermocycler import ThermocyclerDiagnostic
    from diagnose_heater_shaker import HeaterShakerDiagnostic
    from diagnose_flex_stacker import FlexStackerDiagnostic
except ImportError as e:
    print(f"Error importing diagnostic modules: {e}")
    print("Make sure all diagnostic scripts are in the same directory.")
    sys.exit(1)


# Module mapping
MODULES = {
    'tempdeck': {
        'name': 'Temperature Module (TempDeck)',
        'class': TemperatureModuleDiagnostic,
        'description': 'Temperature control module for heating/cooling samples',
        'compatible': ['OT-2', 'Flex']
    },
    'magdeck': {
        'name': 'Magnetic Module (MagDeck)',
        'class': MagneticModuleDiagnostic,
        'description': 'Magnetic bead separation module',
        'compatible': ['OT-2', 'Flex']
    },
    'thermocycler': {
        'name': 'Thermocycler Module',
        'class': ThermocyclerDiagnostic,
        'description': 'PCR thermal cycling module (Gen1/Gen2)',
        'compatible': ['OT-2', 'Flex']
    },
    'heatershaker': {
        'name': 'Heater-Shaker Module',
        'class': HeaterShakerDiagnostic,
        'description': 'Combined heating and orbital shaking module',
        'compatible': ['OT-2', 'Flex']
    },
    'flexstacker': {
        'name': 'Flex Stacker Module',
        'class': FlexStackerDiagnostic,
        'description': 'Automated plate stacking module',
        'compatible': ['Flex']
    }
}


def list_modules():
    """Print list of available modules."""
    print("\n" + "=" * 70)
    print("AVAILABLE OPENTRONS MODULES FOR DIAGNOSTIC")
    print("=" * 70 + "\n")

    for key, info in MODULES.items():
        print(f"  {key:15} - {info['name']}")
        print(f"                    {info['description']}")
        print(f"                    Compatible: {', '.join(info['compatible'])}")
        print()

    print("=" * 70)
    print("\nUsage Examples:")
    print("  python run_all_diagnostics.py --module tempdeck --port COM6")
    print("  python run_all_diagnostics.py --module thermocycler --port COM6 --full-test")
    print("  python run_all_diagnostics.py --module heatershaker --port /dev/ttyUSB0 -f -s")
    print()


def detect_port():
    """Attempt to detect available serial ports."""
    import serial.tools.list_ports

    ports = list(serial.tools.list_ports.comports())

    if not ports:
        return None

    print("\nAvailable serial ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device}: {port.description}")

    return ports


def print_banner():
    """Print the main banner."""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║     OPENTRONS MODULE DIAGNOSTIC TOOL                             ║
    ║     Maintenance & Testing Suite                                  ║
    ║     January 2026                                                 ║
    ║                                                                  ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                  ║
    ║  Supported Modules:                                              ║
    ║    - Temperature Module (TempDeck)                               ║
    ║    - Magnetic Module (MagDeck)                                   ║
    ║    - Thermocycler (Gen1/Gen2)                                    ║
    ║    - Heater-Shaker                                               ║
    ║    - Flex Stacker (Flex only)                                    ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)


def run_diagnostic(module_key: str, port: str, full_test: bool, save_report: bool):
    """Run diagnostic for specified module."""
    if module_key not in MODULES:
        print(f"Error: Unknown module '{module_key}'")
        print("Use --list to see available modules")
        return False

    module_info = MODULES[module_key]
    diagnostic_class = module_info['class']

    print(f"\nStarting diagnostic for: {module_info['name']}")
    print(f"Port: {port}")
    print(f"Full Test: {'Yes' if full_test else 'No'}")
    print("-" * 50)

    try:
        diagnostic = diagnostic_class(port=port)
        diagnostic.run_diagnostics(full_test=full_test)

        if save_report:
            diagnostic.save_report()

        return True

    except Exception as e:
        print(f"\nError running diagnostic: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_service_report(results: dict, output_file: str = None):
    """Generate a comprehensive service report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = []
    report.append("=" * 70)
    report.append("OPENTRONS MODULE SERVICE REPORT")
    report.append(f"Generated: {timestamp}")
    report.append("=" * 70)
    report.append("")

    for module_name, module_result in results.items():
        report.append(f"\n{module_name}")
        report.append("-" * 40)
        if module_result.get('tested', False):
            report.append(f"  Status: {'PASS' if module_result.get('passed', False) else 'FAIL'}")
            if module_result.get('details'):
                for key, value in module_result['details'].items():
                    report.append(f"  {key}: {value}")
        else:
            report.append("  Status: NOT TESTED")
        report.append("")

    report.append("=" * 70)
    report.append("END OF REPORT")
    report.append("=" * 70)

    report_text = '\n'.join(report)
    print(report_text)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        print(f"\nReport saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Opentrons Module Diagnostic Master Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_diagnostics.py --list
  python run_all_diagnostics.py --module tempdeck --port COM6
  python run_all_diagnostics.py --module thermocycler --port COM6 --full-test
  python run_all_diagnostics.py --module heatershaker --port /dev/ttyUSB0 -f -s

For Windows: Use COM ports (COM3, COM6, etc.)
For Linux: Use /dev/ttyUSB0, /dev/ttyACM0, etc.
For macOS: Use /dev/cu.usbserial-*, /dev/tty.usbmodem*, etc.
        """
    )

    parser.add_argument(
        '--module', '-m',
        choices=list(MODULES.keys()),
        help="Module to diagnose"
    )
    parser.add_argument(
        '--port', '-p',
        default='COM6',
        help="Serial port (default: COM6)"
    )
    parser.add_argument(
        '--full-test', '-f',
        action='store_true',
        help="Run extended tests (motors, heating, etc.)"
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help="Save diagnostic report to file"
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help="List available modules"
    )
    parser.add_argument(
        '--detect-ports',
        action='store_true',
        help="Detect available serial ports"
    )

    args = parser.parse_args()

    print_banner()

    if args.list:
        list_modules()
        return

    if args.detect_ports:
        detect_port()
        return

    if not args.module:
        print("Error: Please specify a module with --module")
        print("Use --list to see available modules")
        parser.print_help()
        return

    # Safety confirmation for full tests
    if args.full_test:
        print("\n" + "!" * 70)
        print("WARNING: Full test mode will:")
        print("  - Operate motors and mechanical components")
        print("  - Activate heaters")
        print("  - Move the module through its range of motion")
        print("!")
        print("Ensure:")
        print("  - No labware is on the module")
        print("  - Hands are clear of moving parts")
        print("  - Module is properly secured")
        print("!" * 70 + "\n")

        response = input("Continue with full test? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Full test cancelled.")
            return

    run_diagnostic(
        module_key=args.module,
        port=args.port,
        full_test=args.full_test,
        save_report=args.save_report
    )


if __name__ == "__main__":
    main()
