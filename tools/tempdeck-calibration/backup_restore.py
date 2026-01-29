#!/usr/bin/env python3
"""
Temperature Module Backup & Recovery Tool

Creates backups before flashing and can restore if things go wrong.

Usage:
    python backup_restore.py backup COM6      # Backup EEPROM and flash
    python backup_restore.py restore COM6     # Restore from backup
    python backup_restore.py read-info COM6   # Just read serial/model
"""

import sys
import os
import json
import subprocess
import time
import serial
from datetime import datetime
from pathlib import Path

BAUD_RATE = 115200
BACKUP_DIR = Path("backups")

def send_command(ser, cmd):
    """Send command and get response."""
    ser.reset_input_buffer()
    ser.write(f"{cmd}\r\n\r\n".encode())
    time.sleep(0.3)
    return ser.read(2048).decode().strip()

def get_device_info(port):
    """Read device info via M115."""
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
        time.sleep(1)
        response = send_command(ser, "M115")
        ser.close()

        info = {}
        for part in response.replace("ok", "").strip().split():
            if ':' in part:
                key, value = part.split(':', 1)
                info[key.strip()] = value.strip()
        return info
    except Exception as e:
        print(f"Error reading device info: {e}")
        return None

def enter_bootloader(port):
    """Send dfu command to enter bootloader mode."""
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
        time.sleep(0.5)
        ser.write(b"dfu\r\n\r\n")
        time.sleep(0.5)
        ser.close()
        print("Sent 'dfu' command - module entering bootloader...")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error entering bootloader: {e}")
        return False

def find_bootloader_port():
    """Find the bootloader port after dfu command."""
    import serial.tools.list_ports

    print("Searching for bootloader port...")
    for _ in range(5):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            # Bootloader shows up as different VID/PID or description
            if 'bootloader' in p.description.lower() or '2341' in str(p.vid):
                print(f"Found bootloader at {p.device}")
                return p.device
        time.sleep(1)

    # Just return list of ports for user to choose
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")
    return None

def backup_eeprom(port, serial_num):
    """Backup EEPROM contents using avrdude."""
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"eeprom_backup_{serial_num}_{timestamp}.hex"

    cmd = [
        "avrdude",
        "-p", "atmega32u4",
        "-c", "avr109",
        "-P", port,
        "-b", "57600",
        f"-Ueeprom:r:{backup_file}:i"
    ]

    print(f"Backing up EEPROM to {backup_file}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✓ EEPROM backup saved to {backup_file}")
        return backup_file
    else:
        print(f"✗ Backup failed: {result.stderr}")
        return None

def backup_flash(port, serial_num):
    """Backup flash contents using avrdude."""
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"flash_backup_{serial_num}_{timestamp}.hex"

    cmd = [
        "avrdude",
        "-p", "atmega32u4",
        "-c", "avr109",
        "-P", port,
        "-b", "57600",
        f"-Uflash:r:{backup_file}:i"
    ]

    print(f"Backing up flash to {backup_file}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✓ Flash backup saved to {backup_file}")
        return backup_file
    else:
        print(f"✗ Backup failed: {result.stderr}")
        return None

def restore_eeprom(port, backup_file):
    """Restore EEPROM from backup."""
    cmd = [
        "avrdude",
        "-p", "atmega32u4",
        "-c", "avr109",
        "-P", port,
        "-b", "57600",
        f"-Ueeprom:w:{backup_file}:i"
    ]

    print(f"Restoring EEPROM from {backup_file}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✓ EEPROM restored successfully")
        return True
    else:
        print(f"✗ Restore failed: {result.stderr}")
        return False

def restore_flash(port, backup_file):
    """Restore flash from backup."""
    cmd = [
        "avrdude",
        "-p", "atmega32u4",
        "-c", "avr109",
        "-P", port,
        "-b", "57600",
        "-D",  # Don't erase EEPROM!
        f"-Uflash:w:{backup_file}:i"
    ]

    print(f"Restoring flash from {backup_file}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✓ Flash restored successfully")
        return True
    else:
        print(f"✗ Restore failed: {result.stderr}")
        return False

def create_full_backup(port):
    """Create complete backup of module before any modifications."""
    print("="*50)
    print("CREATING FULL BACKUP")
    print("="*50)

    # First get device info while in normal mode
    info = get_device_info(port)
    if not info:
        print("✗ Could not read device info. Is module connected?")
        return None

    serial_num = info.get('serial', 'UNKNOWN')
    model = info.get('model', 'UNKNOWN')

    print(f"Module: {serial_num} ({model})")

    # Save device info
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    info_file = BACKUP_DIR / f"device_info_{serial_num}_{timestamp}.json"
    with open(info_file, 'w') as f:
        json.dump(info, f, indent=2)
    print(f"✓ Device info saved to {info_file}")

    # Enter bootloader
    if not enter_bootloader(port):
        return None

    # Find bootloader port
    bl_port = find_bootloader_port()
    if not bl_port:
        print("✗ Could not find bootloader port")
        print("  Please manually enter the bootloader port:")
        bl_port = input("  Port: ").strip()

    # Backup EEPROM
    eeprom_backup = backup_eeprom(bl_port, serial_num)

    # Need to re-enter bootloader for flash backup (it reboots after each operation)
    print("\nRe-entering bootloader for flash backup...")
    time.sleep(3)  # Wait for reboot

    # Try to re-enter bootloader
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
        time.sleep(1)
        ser.write(b"dfu\r\n\r\n")
        ser.close()
        time.sleep(2)
    except:
        pass

    bl_port = find_bootloader_port() or bl_port

    # Backup flash
    flash_backup = backup_flash(bl_port, serial_num)

    print("\n" + "="*50)
    print("BACKUP COMPLETE")
    print("="*50)
    print(f"Device Info: {info_file}")
    print(f"EEPROM:      {eeprom_backup}")
    print(f"Flash:       {flash_backup}")
    print("\nKeep these files safe! You can restore if anything goes wrong.")

    return {
        'serial': serial_num,
        'info_file': str(info_file),
        'eeprom_backup': str(eeprom_backup),
        'flash_backup': str(flash_backup)
    }

def list_backups():
    """List available backups."""
    if not BACKUP_DIR.exists():
        print("No backups found.")
        return []

    backups = {}
    for f in BACKUP_DIR.glob("*"):
        # Parse filename to get serial
        parts = f.stem.split('_')
        if len(parts) >= 3:
            backup_type = parts[0]  # eeprom, flash, or device
            serial = parts[2] if parts[1] == 'backup' or parts[1] == 'info' else parts[1]

            if serial not in backups:
                backups[serial] = []
            backups[serial].append(f)

    print("Available backups:")
    for serial, files in backups.items():
        print(f"\n  {serial}:")
        for f in sorted(files):
            print(f"    - {f.name}")

    return backups

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_restore.py backup <PORT>    - Create full backup")
        print("  python backup_restore.py restore <PORT>   - Restore from backup")
        print("  python backup_restore.py list             - List backups")
        print("  python backup_restore.py read-info <PORT> - Read device info")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "list":
        list_backups()

    elif command == "read-info":
        if len(sys.argv) < 3:
            print("Usage: python backup_restore.py read-info <PORT>")
            sys.exit(1)
        port = sys.argv[2]
        info = get_device_info(port)
        if info:
            print("Device Info:")
            for k, v in info.items():
                print(f"  {k}: {v}")

    elif command == "backup":
        if len(sys.argv) < 3:
            print("Usage: python backup_restore.py backup <PORT>")
            sys.exit(1)
        port = sys.argv[2]
        create_full_backup(port)

    elif command == "restore":
        if len(sys.argv) < 3:
            print("Usage: python backup_restore.py restore <PORT>")
            sys.exit(1)
        port = sys.argv[2]

        backups = list_backups()
        if not backups:
            print("No backups available to restore.")
            sys.exit(1)

        print("\nEnter the serial number of the module to restore:")
        serial = input("Serial: ").strip()

        if serial not in backups:
            print(f"No backups found for {serial}")
            sys.exit(1)

        # Find most recent backups
        eeprom_file = None
        flash_file = None
        for f in sorted(backups[serial], reverse=True):
            if 'eeprom' in f.name and eeprom_file is None:
                eeprom_file = f
            if 'flash' in f.name and flash_file is None:
                flash_file = f

        print(f"\nWill restore:")
        print(f"  EEPROM: {eeprom_file}")
        print(f"  Flash:  {flash_file}")

        confirm = input("\nProceed? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Aborted.")
            sys.exit(0)

        # Enter bootloader
        enter_bootloader(port)
        bl_port = find_bootloader_port() or port

        # Restore EEPROM first (contains serial/model)
        if eeprom_file:
            restore_eeprom(bl_port, eeprom_file)

        # Re-enter bootloader
        time.sleep(3)
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=2)
            time.sleep(1)
            ser.write(b"dfu\r\n\r\n")
            ser.close()
            time.sleep(2)
        except:
            pass
        bl_port = find_bootloader_port() or bl_port

        # Restore flash
        if flash_file:
            restore_flash(bl_port, flash_file)

        print("\n✓ Restore complete!")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
