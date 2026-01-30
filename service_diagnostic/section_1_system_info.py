# %% [markdown]
# # Section 1: System Information
#
# Gather system info - can run standalone without hardware.

# %%
import json
import socket
import platform
from pathlib import Path
from common import run_shell, print_header, ON_ROBOT

print_header("SYSTEM INFORMATION")

info = {
    "hostname": "",
    "robot_model": "OT-2",
    "serial_number": "",
    "software_version": {},
    "network": {},
    "storage": {},
    "uptime": "",
    "python_version": platform.python_version()
}

# Hostname
try:
    info["hostname"] = socket.gethostname()
    print(f"  Hostname: {info['hostname']}")
except:
    pass

# Serial number
_, stdout, _ = run_shell("cat /var/serial")
info["serial_number"] = stdout or "Unknown"
print(f"  Serial Number: {info['serial_number']}")

# Software version
try:
    version_file = Path("/etc/VERSION.json")
    if version_file.exists():
        with open(version_file) as f:
            info["software_version"] = json.load(f)
        print(f"  Software Version: {info['software_version'].get('opentrons_api_version', 'Unknown')}")
except:
    pass

# Network info
_, ip_output, _ = run_shell("hostname -I")
info["network"]["ip_addresses"] = ip_output.split() if ip_output else []
print(f"  IP Addresses: {', '.join(info['network'].get('ip_addresses', ['N/A']))}")

# Storage info
_, df_output, _ = run_shell("df -h /data | tail -1")
if df_output:
    parts = df_output.split()
    if len(parts) >= 4:
        info["storage"] = {
            "total": parts[1],
            "used": parts[2],
            "available": parts[3],
            "percent_used": parts[4] if len(parts) > 4 else ""
        }
        print(f"  Storage: {info['storage']['used']} / {info['storage']['total']} ({info['storage'].get('percent_used', '')})")

# Uptime
_, uptime_output, _ = run_shell("uptime -p")
info["uptime"] = uptime_output
print(f"  Uptime: {uptime_output}")
print(f"  Python Version: {info['python_version']}")

print("\n--- Results stored in 'info' variable ---")
