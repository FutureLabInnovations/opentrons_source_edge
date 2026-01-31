"""
Temperature Module GEN2 - Protocol API Diagnostic

Upload this protocol to the Opentrons App to run diagnostics
on a Temperature Module GEN2 connected to an OT-2 or Flex robot.

This protocol performs:
1. Module detection and identification
2. Temperature reading verification
3. Set temperature command test (safe 25°C)
4. Deactivation test
5. Generates diagnostic report

Author: Opentrons Field Service
API Level: 2.15+
"""

from opentrons import protocol_api
from datetime import datetime
import json

metadata = {
    'apiLevel': '2.15',
    'protocolName': 'Temperature Module GEN2 Diagnostic',
    'author': 'Opentrons Field Service',
    'description': 'Comprehensive diagnostic for Temperature Module GEN2'
}

# Configuration
CONFIG = {
    # Slots to try for module detection (Flex first, then OT-2)
    'SLOTS_TO_TRY': ['D1', 'D3', 'C1', 'C3', 'B1', 'B3', 'A1', 'A3',
                    '1', '3', '4', '6', '7', '9', '10'],

    # Safe test temperature (won't damage samples or burn user)
    'TEST_TEMPERATURE': 25,  # °C

    # Verification delay after commands
    'VERIFY_DELAY_SEC': 3,

    # Enable extended tests (heating/cooling)
    'EXTENDED_TESTS': False,

    # Extended test parameters (only used if EXTENDED_TESTS=True)
    'EXTENDED_HEAT_TARGET': 40,  # °C
    'EXTENDED_COOL_TARGET': 15,  # °C
    'STABILITY_HOLD_SEC': 60,
}


def run(protocol: protocol_api.ProtocolContext):
    """Main protocol execution"""

    # Initialize results structure
    results = {
        'timestamp': str(datetime.now()),
        'api_version': str(protocol.api_version),
        'robot_type': 'Flex' if 'D1' in CONFIG['SLOTS_TO_TRY'][0] else 'OT-2',
        'tests': {},
        'overall_status': 'PENDING'
    }

    # Header
    protocol.comment('=' * 55)
    protocol.comment('  TEMPERATURE MODULE GEN2 DIAGNOSTIC')
    protocol.comment('=' * 55)
    protocol.comment(f'  Timestamp: {results["timestamp"]}')
    protocol.comment(f'  API Version: {results["api_version"]}')
    protocol.comment('=' * 55)

    # ==================== TEST 1: MODULE DETECTION ====================
    protocol.comment('')
    protocol.comment('-' * 55)
    protocol.comment('TEST 1: MODULE DETECTION')
    protocol.comment('-' * 55)

    temp_mod = None
    loaded_slot = None

    for slot in CONFIG['SLOTS_TO_TRY']:
        try:
            temp_mod = protocol.load_module('temperature module gen2', slot)
            loaded_slot = slot
            protocol.comment(f'  Module loaded in slot {slot}')
            break
        except Exception:
            continue

    if temp_mod is None:
        # Try without generation specifier
        for slot in CONFIG['SLOTS_TO_TRY']:
            try:
                temp_mod = protocol.load_module('temperature module', slot)
                loaded_slot = slot
                protocol.comment(f'  Module loaded in slot {slot} (any generation)')
                break
            except Exception:
                continue

    if temp_mod is None:
        results['tests']['detection'] = {
            'status': 'FAIL',
            'error': 'No Temperature Module found in any slot'
        }
        results['overall_status'] = 'FAIL'
        protocol.comment('  [FAIL] No Temperature Module detected')
        protocol.comment('')
        protocol.comment('Results:')
        protocol.comment(json.dumps(results, indent=2))
        return

    results['tests']['detection'] = {
        'status': 'PASS',
        'slot': loaded_slot
    }
    protocol.comment(f'  Status: [PASS]')

    # ==================== TEST 2: DEVICE INFORMATION ====================
    protocol.comment('')
    protocol.comment('-' * 55)
    protocol.comment('TEST 2: DEVICE INFORMATION')
    protocol.comment('-' * 55)

    try:
        serial_number = temp_mod.serial_number
        model = str(temp_mod.model) if hasattr(temp_mod, 'model') else 'N/A'

        results['tests']['device_info'] = {
            'status': 'PASS',
            'serial_number': serial_number,
            'model': model
        }
        results['serial_number'] = serial_number
        results['model'] = model

        protocol.comment(f'  Serial Number: {serial_number}')
        protocol.comment(f'  Model: {model}')
        protocol.comment(f'  Status: [PASS]')

    except Exception as e:
        results['tests']['device_info'] = {
            'status': 'FAIL',
            'error': str(e)
        }
        protocol.comment(f'  [FAIL] Could not retrieve device info: {e}')

    # ==================== TEST 3: TEMPERATURE READING ====================
    protocol.comment('')
    protocol.comment('-' * 55)
    protocol.comment('TEST 3: TEMPERATURE READING')
    protocol.comment('-' * 55)

    try:
        current_temp = temp_mod.temperature
        target_temp = temp_mod.target
        status = temp_mod.status

        # Validate reading is reasonable
        temp_valid = 0 <= current_temp <= 100

        results['tests']['temperature_reading'] = {
            'status': 'PASS' if temp_valid else 'WARN',
            'current_temperature': current_temp,
            'target_temperature': target_temp,
            'module_status': status
        }

        protocol.comment(f'  Current Temperature: {current_temp}°C')
        protocol.comment(f'  Target Temperature: {target_temp}')
        protocol.comment(f'  Module Status: {status}')
        protocol.comment(f'  Status: [{"PASS" if temp_valid else "WARN"}]')

        if not temp_valid:
            protocol.comment(f'  Warning: Temperature reading {current_temp}°C outside expected range')

    except Exception as e:
        results['tests']['temperature_reading'] = {
            'status': 'FAIL',
            'error': str(e)
        }
        protocol.comment(f'  [FAIL] Temperature reading failed: {e}')

    # ==================== TEST 4: SET TEMPERATURE ====================
    protocol.comment('')
    protocol.comment('-' * 55)
    protocol.comment(f'TEST 4: SET TEMPERATURE ({CONFIG["TEST_TEMPERATURE"]}°C)')
    protocol.comment('-' * 55)

    try:
        test_temp = CONFIG['TEST_TEMPERATURE']

        # Use non-blocking set
        temp_mod.start_set_temperature(test_temp)
        protocol.comment(f'  Command sent: set_temperature({test_temp})')

        # Wait for command to take effect
        protocol.delay(seconds=CONFIG['VERIFY_DELAY_SEC'])

        # Verify target was set
        target_after = temp_mod.target
        status_after = temp_mod.status

        if target_after == test_temp:
            results['tests']['set_temperature'] = {
                'status': 'PASS',
                'requested': test_temp,
                'confirmed_target': target_after,
                'status_after': status_after
            }
            protocol.comment(f'  Target confirmed: {target_after}°C')
            protocol.comment(f'  Module status: {status_after}')
            protocol.comment(f'  Status: [PASS]')
        else:
            results['tests']['set_temperature'] = {
                'status': 'FAIL',
                'requested': test_temp,
                'actual_target': target_after,
                'error': f'Target mismatch: expected {test_temp}, got {target_after}'
            }
            protocol.comment(f'  [FAIL] Target mismatch: expected {test_temp}, got {target_after}')

    except Exception as e:
        results['tests']['set_temperature'] = {
            'status': 'FAIL',
            'error': str(e)
        }
        protocol.comment(f'  [FAIL] Set temperature failed: {e}')

    # ==================== TEST 5: DEACTIVATE ====================
    protocol.comment('')
    protocol.comment('-' * 55)
    protocol.comment('TEST 5: DEACTIVATE MODULE')
    protocol.comment('-' * 55)

    try:
        temp_mod.deactivate()
        protocol.comment('  Deactivate command sent')

        protocol.delay(seconds=CONFIG['VERIFY_DELAY_SEC'])

        target_after = temp_mod.target
        status_after = temp_mod.status

        if status_after == 'idle':
            results['tests']['deactivate'] = {
                'status': 'PASS',
                'target_after': target_after,
                'status_after': status_after
            }
            protocol.comment(f'  Module status: {status_after}')
            protocol.comment(f'  Status: [PASS]')
        else:
            results['tests']['deactivate'] = {
                'status': 'WARN',
                'target_after': target_after,
                'status_after': status_after,
                'note': f'Expected "idle", got "{status_after}"'
            }
            protocol.comment(f'  [WARN] Status is "{status_after}", expected "idle"')

    except Exception as e:
        results['tests']['deactivate'] = {
            'status': 'FAIL',
            'error': str(e)
        }
        protocol.comment(f'  [FAIL] Deactivate failed: {e}')

    # ==================== EXTENDED TESTS (Optional) ====================
    if CONFIG['EXTENDED_TESTS']:
        protocol.comment('')
        protocol.comment('-' * 55)
        protocol.comment('EXTENDED TEST: HEATING CAPABILITY')
        protocol.comment('-' * 55)

        try:
            heat_target = CONFIG['EXTENDED_HEAT_TARGET']
            protocol.comment(f'  Heating to {heat_target}°C...')

            temp_mod.set_temperature(heat_target)  # Blocking

            final_temp = temp_mod.temperature
            deviation = abs(final_temp - heat_target)

            results['tests']['extended_heating'] = {
                'status': 'PASS' if deviation <= 2.0 else 'FAIL',
                'target': heat_target,
                'achieved': final_temp,
                'deviation': deviation
            }

            protocol.comment(f'  Target: {heat_target}°C')
            protocol.comment(f'  Achieved: {final_temp}°C')
            protocol.comment(f'  Deviation: {deviation}°C')
            protocol.comment(f'  Status: [{"PASS" if deviation <= 2.0 else "FAIL"}]')

        except Exception as e:
            results['tests']['extended_heating'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            protocol.comment(f'  [FAIL] Heating test failed: {e}')

        # Cooling test
        protocol.comment('')
        protocol.comment('-' * 55)
        protocol.comment('EXTENDED TEST: COOLING CAPABILITY')
        protocol.comment('-' * 55)

        try:
            cool_target = CONFIG['EXTENDED_COOL_TARGET']
            protocol.comment(f'  Cooling to {cool_target}°C...')

            temp_mod.set_temperature(cool_target)  # Blocking

            final_temp = temp_mod.temperature
            deviation = abs(final_temp - cool_target)

            results['tests']['extended_cooling'] = {
                'status': 'PASS' if deviation <= 2.0 else 'FAIL',
                'target': cool_target,
                'achieved': final_temp,
                'deviation': deviation
            }

            protocol.comment(f'  Target: {cool_target}°C')
            protocol.comment(f'  Achieved: {final_temp}°C')
            protocol.comment(f'  Deviation: {deviation}°C')
            protocol.comment(f'  Status: [{"PASS" if deviation <= 2.0 else "FAIL"}]')

        except Exception as e:
            results['tests']['extended_cooling'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            protocol.comment(f'  [FAIL] Cooling test failed: {e}')

        # Final deactivate
        try:
            temp_mod.deactivate()
        except Exception:
            pass

    # ==================== SUMMARY ====================
    # Calculate overall status
    all_passed = all(
        test.get('status') in ['PASS', 'WARN']
        for test in results['tests'].values()
    )
    results['overall_status'] = 'PASS' if all_passed else 'FAIL'

    protocol.comment('')
    protocol.comment('=' * 55)
    protocol.comment('  DIAGNOSTIC SUMMARY')
    protocol.comment('=' * 55)

    for test_name, test_result in results['tests'].items():
        status = test_result.get('status', 'N/A')
        if status == 'PASS':
            marker = 'PASS'
        elif status == 'WARN':
            marker = 'WARN'
        else:
            marker = 'FAIL'
        protocol.comment(f'  {test_name:.<35} [{marker}]')

    protocol.comment('-' * 55)
    protocol.comment(f'  OVERALL STATUS: [{results["overall_status"]}]')
    protocol.comment('=' * 55)

    # Output complete results as JSON
    protocol.comment('')
    protocol.comment('Complete Results (JSON):')
    for line in json.dumps(results, indent=2).split('\n'):
        protocol.comment(line)

    return results
