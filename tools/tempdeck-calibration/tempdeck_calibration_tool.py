#!/usr/bin/env python3
"""
Opentrons Temperature Module Calibration Tool

A GUI application for calibrating Temperature Module Gen2 units.
Stores calibration offsets locally and generates printable labels with QR codes.

Usage:
    python tempdeck_calibration_tool.py

Requirements:
    pip install pyserial qrcode pillow

To build as standalone .exe:
    pip install pyinstaller
    pyinstaller --onefile --windowed tempdeck_calibration_tool.py
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import io

# Serial communication
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. Run: pip install pyserial")

# QR Code generation
try:
    import qrcode
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print("Warning: qrcode/pillow not installed. Run: pip install qrcode pillow")


# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "Temperature Module Calibration Tool"
APP_VERSION = "1.0.0"
BAUD_RATE = 115200
COMMAND_TERMINATOR = "\r\n\r\n"
SERIAL_TIMEOUT = 2.0
DATABASE_FILE = "calibration_database.json"

# Temperature limits
TEMP_MIN = -9.0
TEMP_MAX = 99.0
OFFSET_MAX = 10.0  # Maximum allowed offset


# =============================================================================
# Serial Communication
# =============================================================================

class TempDeckConnection:
    """Handles serial communication with the Temperature Module."""

    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.device_info: Dict[str, str] = {}

    def get_available_ports(self) -> list:
        """List available COM ports."""
        if not SERIAL_AVAILABLE:
            return []
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port: str) -> bool:
        """Connect to the Temperature Module."""
        try:
            self.serial = serial.Serial(
                port=port,
                baudrate=BAUD_RATE,
                timeout=SERIAL_TIMEOUT
            )
            self.port = port
            time.sleep(1)  # Wait for connection to stabilize

            # Verify it's a Temperature Module
            info = self.get_device_info()
            if info and 'serial' in info:
                self.device_info = info
                return True
            else:
                self.disconnect()
                return False

        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the module."""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.serial = None
        self.port = None
        self.device_info = {}

    def send_command(self, command: str) -> Optional[str]:
        """Send a G-code command and return the response."""
        if not self.serial or not self.serial.is_open:
            return None

        try:
            self.serial.reset_input_buffer()
            self.serial.write(f"{command}{COMMAND_TERMINATOR}".encode())
            time.sleep(0.2)
            response = self.serial.read(1024).decode().strip()
            return response
        except Exception as e:
            print(f"Command error: {e}")
            return None

    def get_device_info(self) -> Optional[Dict[str, str]]:
        """Get device information (M115)."""
        response = self.send_command("M115")
        if not response:
            return None

        info = {}
        # Parse "serial:XXX model:YYY version:ZZZ"
        for part in response.replace("ok", "").strip().split():
            if ':' in part:
                key, value = part.split(':', 1)
                info[key.strip()] = value.strip()

        return info if info else None

    def get_temperature(self) -> Optional[Dict[str, float]]:
        """Get current temperature (M105)."""
        response = self.send_command("M105")
        if not response:
            return None

        result = {}
        # Parse "T:25.0 C:24.5" or "T:none C:24.5"
        for part in response.replace("ok", "").strip().split():
            if ':' in part:
                key, value = part.split(':', 1)
                key = key.strip()
                value = value.strip()
                if value.lower() != 'none':
                    try:
                        result[key] = float(value)
                    except ValueError:
                        pass

        return result if result else None

    def set_temperature(self, celsius: float) -> bool:
        """Set target temperature (M104)."""
        if celsius < TEMP_MIN or celsius > TEMP_MAX:
            return False
        response = self.send_command(f"M104 S{celsius:.1f}")
        return response is not None and "ok" in response.lower()

    def deactivate(self) -> bool:
        """Turn off the module (M18)."""
        response = self.send_command("M18")
        return response is not None and "ok" in response.lower()

    # Future M303 support
    def get_calibration_offset(self) -> Optional[float]:
        """Get calibration offset (M303) - requires modified firmware."""
        response = self.send_command("M303")
        if not response or "error" in response.lower():
            return None

        # Parse "O:1.50"
        for part in response.split():
            if part.startswith("O:"):
                try:
                    return float(part[2:])
                except ValueError:
                    pass
        return None

    def set_calibration_offset(self, offset: float, save: bool = True) -> bool:
        """Set calibration offset (M303) - requires modified firmware."""
        cmd = f"M303 O{offset:.2f}"
        if save:
            cmd += " S"
        response = self.send_command(cmd)
        return response is not None and "ok" in response.lower()

    def supports_m303(self) -> bool:
        """Check if firmware supports M303 calibration command."""
        response = self.send_command("M303")
        return response is not None and "O:" in response


# =============================================================================
# Calibration Database
# =============================================================================

class CalibrationDatabase:
    """Manages local storage of calibration data."""

    def __init__(self, filepath: str = DATABASE_FILE):
        self.filepath = Path(filepath)
        self.data: Dict[str, Any] = {"calibrations": {}, "metadata": {}}
        self.load()

    def load(self):
        """Load database from file."""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Error loading database: {e}")
                self.data = {"calibrations": {}, "metadata": {}}

    def save(self):
        """Save database to file."""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving database: {e}")

    def get_calibration(self, serial: str) -> Optional[Dict[str, Any]]:
        """Get calibration data for a specific serial number."""
        return self.data["calibrations"].get(serial)

    def set_calibration(self, serial: str, offset: float, technician: str = "",
                        notes: str = "", model: str = ""):
        """Store calibration data for a module."""
        self.data["calibrations"][serial] = {
            "serial": serial,
            "model": model,
            "offset": offset,
            "technician": technician,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        self.save()

    def delete_calibration(self, serial: str):
        """Delete calibration data for a module."""
        if serial in self.data["calibrations"]:
            del self.data["calibrations"][serial]
            self.save()

    def get_all_calibrations(self) -> Dict[str, Any]:
        """Get all stored calibrations."""
        return self.data["calibrations"]

    def export_csv(self, filepath: str):
        """Export all calibrations to CSV."""
        with open(filepath, 'w') as f:
            f.write("Serial,Model,Offset,Technician,Date,Time,Notes\n")
            for cal in self.data["calibrations"].values():
                f.write(f"{cal.get('serial', '')},{cal.get('model', '')},"
                        f"{cal.get('offset', 0)},{cal.get('technician', '')},"
                        f"{cal.get('date', '')},{cal.get('time', '')},"
                        f"\"{cal.get('notes', '')}\"\n")


# =============================================================================
# Label Generator
# =============================================================================

class LabelGenerator:
    """Generates printable calibration labels with QR codes."""

    LABEL_WIDTH = 400
    LABEL_HEIGHT = 200

    @staticmethod
    def generate_qr_data(serial: str, offset: float, date: str) -> str:
        """Generate data string for QR code."""
        return json.dumps({
            "type": "tempdeck_calibration",
            "serial": serial,
            "offset": offset,
            "date": date,
            "version": "1.0"
        })

    @staticmethod
    def create_label(serial: str, model: str, offset: float,
                     technician: str = "", date: str = None) -> Optional[Image.Image]:
        """Create a printable label image."""
        if not QR_AVAILABLE:
            return None

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Create label image
        label = Image.new('RGB', (LabelGenerator.LABEL_WIDTH,
                                   LabelGenerator.LABEL_HEIGHT), 'white')
        draw = ImageDraw.Draw(label)

        # Try to use a nice font, fall back to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 16)
            font_medium = ImageFont.truetype("arial.ttf", 14)
            font_small = ImageFont.truetype("arial.ttf", 11)
        except:
            font_large = ImageFont.load_default()
            font_medium = font_large
            font_small = font_large

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(LabelGenerator.generate_qr_data(serial, offset, date))
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((100, 100))

        # Draw border
        draw.rectangle([0, 0, LabelGenerator.LABEL_WIDTH-1,
                       LabelGenerator.LABEL_HEIGHT-1], outline='black', width=2)

        # Draw header
        draw.rectangle([0, 0, LabelGenerator.LABEL_WIDTH-1, 28], fill='#333333')
        draw.text((10, 5), "TEMPERATURE MODULE CALIBRATION", fill='white', font=font_medium)

        # Paste QR code
        label.paste(qr_img, (LabelGenerator.LABEL_WIDTH - 115, 40))

        # Draw text content
        y = 40
        draw.text((15, y), f"S/N: {serial}", fill='black', font=font_large)
        y += 25
        draw.text((15, y), f"Model: {model}", fill='black', font=font_small)
        y += 20

        # Offset with color indicator
        offset_color = '#006400' if offset >= 0 else '#8B0000'  # Dark green / dark red
        offset_str = f"+{offset:.2f}" if offset >= 0 else f"{offset:.2f}"
        draw.text((15, y), f"Offset: {offset_str} °C", fill=offset_color, font=font_large)
        y += 25

        draw.text((15, y), f"Date: {date}", fill='black', font=font_small)
        y += 18
        if technician:
            draw.text((15, y), f"Tech: {technician}", fill='black', font=font_small)

        # Instructions at bottom
        draw.line([(10, LabelGenerator.LABEL_HEIGHT - 30),
                   (LabelGenerator.LABEL_WIDTH - 10, LabelGenerator.LABEL_HEIGHT - 30)],
                  fill='gray', width=1)
        draw.text((15, LabelGenerator.LABEL_HEIGHT - 25),
                  "Scan QR for calibration data", fill='gray', font=font_small)

        return label

    @staticmethod
    def save_label(label: Image.Image, filepath: str):
        """Save label to file."""
        label.save(filepath)

    @staticmethod
    def get_label_tk(label: Image.Image) -> ImageTk.PhotoImage:
        """Convert label to tkinter-compatible image."""
        return ImageTk.PhotoImage(label)


# =============================================================================
# Main GUI Application
# =============================================================================

class CalibrationApp:
    """Main application window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("700x750")
        self.root.resizable(True, True)

        # Initialize components
        self.connection = TempDeckConnection()
        self.database = CalibrationDatabase()

        # State variables
        self.current_temp = tk.StringVar(value="--.-")
        self.target_temp = tk.StringVar(value="--.-")
        self.reference_temp = tk.StringVar(value="")
        self.calculated_offset = tk.StringVar(value="--")
        self.serial_number = tk.StringVar(value="")
        self.model_number = tk.StringVar(value="")
        self.technician_name = tk.StringVar(value="")
        self.notes = tk.StringVar(value="")
        self.selected_port = tk.StringVar(value="")
        self.m303_supported = tk.BooleanVar(value=False)
        self.save_to_eeprom = tk.BooleanVar(value=False)

        # Temperature polling
        self.polling = False
        self.poll_thread: Optional[threading.Thread] = None

        # Label image reference (prevent garbage collection)
        self.label_image = None
        self.label_photo = None

        # Build UI
        self._create_ui()
        self._refresh_ports()

    def _create_ui(self):
        """Create the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # === Step 1: Connection ===
        conn_frame = ttk.LabelFrame(main_frame, text="Step 1: Connect to Module", padding="10")
        conn_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        conn_frame.columnconfigure(1, weight=1)

        ttk.Label(conn_frame, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.selected_port, width=15)
        self.port_combo.grid(row=0, column=1, sticky="w", padx=(5, 10))

        ttk.Button(conn_frame, text="Refresh", command=self._refresh_ports, width=8).grid(row=0, column=2, padx=2)
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self._toggle_connection, width=10)
        self.connect_btn.grid(row=0, column=3, padx=2)

        # Device info
        info_frame = ttk.Frame(conn_frame)
        info_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        ttk.Label(info_frame, text="Serial:").grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, textvariable=self.serial_number, font=('Consolas', 10, 'bold')).grid(row=0, column=1, sticky="w", padx=(5, 20))
        ttk.Label(info_frame, text="Model:").grid(row=0, column=2, sticky="w")
        ttk.Label(info_frame, textvariable=self.model_number, font=('Consolas', 10)).grid(row=0, column=3, sticky="w", padx=5)

        # M303 support indicator
        self.m303_label = ttk.Label(info_frame, text="", foreground="gray")
        self.m303_label.grid(row=0, column=4, sticky="e", padx=(20, 0))

        # === Step 2: Calibrate ===
        cal_frame = ttk.LabelFrame(main_frame, text="Step 2: Calibrate", padding="10")
        cal_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        cal_frame.columnconfigure(1, weight=1)

        # Current temperature display
        temp_frame = ttk.Frame(cal_frame)
        temp_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(temp_frame, text="Module Temperature:", font=('Arial', 11)).pack(side="left")
        self.temp_display = ttk.Label(temp_frame, textvariable=self.current_temp,
                                       font=('Consolas', 24, 'bold'), foreground='#0066cc')
        self.temp_display.pack(side="left", padx=10)
        ttk.Label(temp_frame, text="°C", font=('Arial', 14)).pack(side="left")

        # Reference temperature input
        ref_frame = ttk.Frame(cal_frame)
        ref_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

        ttk.Label(ref_frame, text="Reference Thermometer Reading:", font=('Arial', 11)).pack(side="left")
        ref_entry = ttk.Entry(ref_frame, textvariable=self.reference_temp, width=10, font=('Consolas', 14))
        ref_entry.pack(side="left", padx=10)
        ttk.Label(ref_frame, text="°C", font=('Arial', 11)).pack(side="left")

        ttk.Button(ref_frame, text="Calculate Offset", command=self._calculate_offset).pack(side="left", padx=20)

        # Calculated offset display
        offset_frame = ttk.Frame(cal_frame)
        offset_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)

        ttk.Label(offset_frame, text="Calculated Offset:", font=('Arial', 11)).pack(side="left")
        self.offset_display = ttk.Label(offset_frame, textvariable=self.calculated_offset,
                                         font=('Consolas', 20, 'bold'), foreground='#006400')
        self.offset_display.pack(side="left", padx=10)
        ttk.Label(offset_frame, text="°C", font=('Arial', 12)).pack(side="left")

        # === Step 3: Save ===
        save_frame = ttk.LabelFrame(main_frame, text="Step 3: Save Calibration", padding="10")
        save_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        save_frame.columnconfigure(1, weight=1)

        ttk.Label(save_frame, text="Technician:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(save_frame, textvariable=self.technician_name, width=30).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(save_frame, text="Notes:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(save_frame, textvariable=self.notes, width=50).grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        # Save options
        options_frame = ttk.Frame(save_frame)
        options_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 5))

        self.eeprom_check = ttk.Checkbutton(options_frame, text="Save to module EEPROM (M303 - requires modified firmware)",
                                             variable=self.save_to_eeprom, state="disabled")
        self.eeprom_check.pack(side="left")

        # Save button
        btn_frame = ttk.Frame(save_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)

        self.save_btn = ttk.Button(btn_frame, text="Save Calibration", command=self._save_calibration, state="disabled")
        self.save_btn.pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Export All to CSV", command=self._export_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="View Database", command=self._view_database).pack(side="left", padx=5)

        # === Label Preview ===
        label_frame = ttk.LabelFrame(main_frame, text="Label Preview", padding="10")
        label_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        main_frame.rowconfigure(3, weight=1)

        self.label_canvas = tk.Canvas(label_frame, width=400, height=200, bg='white',
                                       highlightthickness=1, highlightbackground='gray')
        self.label_canvas.pack(pady=10)

        label_btn_frame = ttk.Frame(label_frame)
        label_btn_frame.pack()

        ttk.Button(label_btn_frame, text="Generate Label", command=self._generate_label).pack(side="left", padx=5)
        ttk.Button(label_btn_frame, text="Save Label Image", command=self._save_label).pack(side="left", padx=5)
        ttk.Button(label_btn_frame, text="Copy Data", command=self._copy_data).pack(side="left", padx=5)

        # === Instructions ===
        instr_frame = ttk.LabelFrame(main_frame, text="Instructions", padding="10")
        instr_frame.grid(row=4, column=0, sticky="ew")

        instructions = """1. Connect the Temperature Module via USB and select the COM port
2. Wait for the module temperature to stabilize (approximately 5 minutes at room temperature)
3. Place a calibrated reference thermometer probe on the center of the aluminum plate
4. Enter the reference thermometer reading and click "Calculate Offset"
5. Enter your name and any notes, then click "Save Calibration"
6. Generate and print a label to attach to the module"""

        ttk.Label(instr_frame, text=instructions, justify="left", wraplength=650).pack(anchor="w")

    def _refresh_ports(self):
        """Refresh the list of available COM ports."""
        ports = self.connection.get_available_ports()
        self.port_combo['values'] = ports
        if ports and not self.selected_port.get():
            self.selected_port.set(ports[0])

    def _toggle_connection(self):
        """Connect or disconnect from the module."""
        if self.connection.serial and self.connection.serial.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        """Connect to the selected port."""
        port = self.selected_port.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return

        self.connect_btn.config(state="disabled")
        self.root.update()

        if self.connection.connect(port):
            # Update UI with device info
            info = self.connection.device_info
            self.serial_number.set(info.get('serial', 'Unknown'))
            self.model_number.set(info.get('model', 'Unknown'))

            # Check M303 support
            if self.connection.supports_m303():
                self.m303_supported.set(True)
                self.m303_label.config(text="M303 Supported", foreground="green")
                self.eeprom_check.config(state="normal")
            else:
                self.m303_supported.set(False)
                self.m303_label.config(text="M303 Not Available", foreground="gray")
                self.eeprom_check.config(state="disabled")

            # Load existing calibration if available
            existing = self.database.get_calibration(info.get('serial', ''))
            if existing:
                self.calculated_offset.set(f"{existing['offset']:+.2f}")
                self.technician_name.set(existing.get('technician', ''))
                self.notes.set(existing.get('notes', ''))

            self.connect_btn.config(text="Disconnect", state="normal")
            self._start_polling()
        else:
            messagebox.showerror("Connection Failed",
                               f"Could not connect to Temperature Module on {port}\n\n"
                               "Make sure:\n"
                               "- The module is powered on\n"
                               "- The USB cable is connected\n"
                               "- No other program is using the port")
            self.connect_btn.config(state="normal")

    def _disconnect(self):
        """Disconnect from the module."""
        self._stop_polling()
        self.connection.disconnect()

        self.serial_number.set("")
        self.model_number.set("")
        self.current_temp.set("--.-")
        self.m303_label.config(text="")
        self.connect_btn.config(text="Connect")
        self.eeprom_check.config(state="disabled")

    def _start_polling(self):
        """Start polling temperature in background."""
        self.polling = True
        self.poll_thread = threading.Thread(target=self._poll_temperature, daemon=True)
        self.poll_thread.start()

    def _stop_polling(self):
        """Stop temperature polling."""
        self.polling = False
        if self.poll_thread:
            self.poll_thread.join(timeout=2)

    def _poll_temperature(self):
        """Background thread to poll temperature."""
        while self.polling:
            try:
                temp = self.connection.get_temperature()
                if temp:
                    current = temp.get('C', 0)
                    target = temp.get('T')

                    self.root.after(0, lambda c=current: self.current_temp.set(f"{c:.1f}"))
                    if target is not None:
                        self.root.after(0, lambda t=target: self.target_temp.set(f"{t:.1f}"))
                    else:
                        self.root.after(0, lambda: self.target_temp.set("--.-"))
            except Exception as e:
                print(f"Polling error: {e}")

            time.sleep(1.0)

    def _calculate_offset(self):
        """Calculate the calibration offset."""
        try:
            reference = float(self.reference_temp.get())
            current = float(self.current_temp.get())

            offset = reference - current

            if abs(offset) > OFFSET_MAX:
                messagebox.showwarning("Large Offset",
                    f"Calculated offset ({offset:.2f}°C) exceeds ±{OFFSET_MAX}°C.\n\n"
                    "This may indicate:\n"
                    "- Incorrect reference reading\n"
                    "- Module hardware fault\n"
                    "- Temperature not stabilized\n\n"
                    "Please verify and try again.")
                return

            self.calculated_offset.set(f"{offset:+.2f}")

            # Update display color based on offset
            if abs(offset) < 1.0:
                self.offset_display.config(foreground='#006400')  # Green - good
            elif abs(offset) < 2.0:
                self.offset_display.config(foreground='#FF8C00')  # Orange - acceptable
            else:
                self.offset_display.config(foreground='#8B0000')  # Red - significant

            self.save_btn.config(state="normal")

        except ValueError:
            messagebox.showerror("Error", "Please enter valid temperature values")

    def _save_calibration(self):
        """Save the calibration to the database."""
        serial = self.serial_number.get()
        if not serial:
            messagebox.showerror("Error", "No module connected")
            return

        try:
            offset = float(self.calculated_offset.get())
        except ValueError:
            messagebox.showerror("Error", "Please calculate offset first")
            return

        # Save to database
        self.database.set_calibration(
            serial=serial,
            offset=offset,
            technician=self.technician_name.get(),
            notes=self.notes.get(),
            model=self.model_number.get()
        )

        # Save to EEPROM if supported and selected
        if self.save_to_eeprom.get() and self.m303_supported.get():
            if self.connection.set_calibration_offset(offset, save=True):
                messagebox.showinfo("Success",
                    f"Calibration saved!\n\n"
                    f"Serial: {serial}\n"
                    f"Offset: {offset:+.2f}°C\n\n"
                    f"Saved to: Local database + Module EEPROM")
            else:
                messagebox.showwarning("Partial Success",
                    f"Calibration saved to local database.\n\n"
                    f"Failed to save to module EEPROM.\n"
                    f"The M303 command may not be fully implemented.")
        else:
            messagebox.showinfo("Success",
                f"Calibration saved to local database!\n\n"
                f"Serial: {serial}\n"
                f"Offset: {offset:+.2f}°C")

        # Auto-generate label
        self._generate_label()

    def _generate_label(self):
        """Generate the label preview."""
        if not QR_AVAILABLE:
            messagebox.showerror("Error", "QR code generation requires: pip install qrcode pillow")
            return

        serial = self.serial_number.get() or "UNKNOWN"
        model = self.model_number.get() or "temp_deck"

        try:
            offset = float(self.calculated_offset.get())
        except ValueError:
            offset = 0.0

        self.label_image = LabelGenerator.create_label(
            serial=serial,
            model=model,
            offset=offset,
            technician=self.technician_name.get()
        )

        if self.label_image:
            self.label_photo = ImageTk.PhotoImage(self.label_image)
            self.label_canvas.delete("all")
            self.label_canvas.create_image(0, 0, anchor="nw", image=self.label_photo)

    def _save_label(self):
        """Save the label image to a file."""
        if not self.label_image:
            messagebox.showerror("Error", "Please generate a label first")
            return

        serial = self.serial_number.get() or "label"
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
            initialfilename=f"calibration_label_{serial}.png"
        )

        if filename:
            self.label_image.save(filename)
            messagebox.showinfo("Saved", f"Label saved to:\n{filename}")

    def _copy_data(self):
        """Copy calibration data to clipboard."""
        serial = self.serial_number.get()
        offset = self.calculated_offset.get()

        data = f"Serial: {serial}\nOffset: {offset}°C\nDate: {datetime.now().strftime('%Y-%m-%d')}"

        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        messagebox.showinfo("Copied", "Calibration data copied to clipboard")

    def _export_csv(self):
        """Export all calibrations to CSV."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
            initialfilename=f"calibrations_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if filename:
            self.database.export_csv(filename)
            messagebox.showinfo("Exported", f"Calibrations exported to:\n{filename}")

    def _view_database(self):
        """Open a window to view all stored calibrations."""
        view_window = tk.Toplevel(self.root)
        view_window.title("Calibration Database")
        view_window.geometry("600x400")

        # Create treeview
        columns = ("Serial", "Model", "Offset", "Technician", "Date")
        tree = ttk.Treeview(view_window, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column("Serial", width=120)
        tree.column("Model", width=120)
        tree.column("Offset", width=80)
        tree.column("Technician", width=100)
        tree.column("Date", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(view_window, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate data
        for cal in self.database.get_all_calibrations().values():
            tree.insert("", "end", values=(
                cal.get('serial', ''),
                cal.get('model', ''),
                f"{cal.get('offset', 0):+.2f}°C",
                cal.get('technician', ''),
                cal.get('date', '')
            ))

    def on_closing(self):
        """Handle window close."""
        self._stop_polling()
        self.connection.disconnect()
        self.root.destroy()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Application entry point."""
    root = tk.Tk()

    # Set app icon (if available)
    try:
        root.iconbitmap("icon.ico")
    except:
        pass

    app = CalibrationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
