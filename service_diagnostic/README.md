# OT-2 Service Diagnostic - Jupyter Sections

Run each section independently in Jupyter, VS Code, or any IDE that supports `# %%` cell markers.

## Sections

| File | Description | Requires Hardware |
|------|-------------|-------------------|
| `section_1_system_info.py` | Hostname, versions, network, storage | No |
| `section_2_motion_tests.py` | Limit switches, homing, repeatability | Yes |
| `section_3_pipette_tests.py` | Detection, plunger, calibration | Yes |
| `section_4_module_tests.py` | Temp/Mag/TC/HS modules | Yes |
| `section_5_calibration.py` | Deck, pipette, tip length cals | No |
| `section_6_system_health.py` | Disk space, logs, services | No |

## Usage

### In Jupyter
```bash
cd service_diagnostic
jupyter notebook
# Open any section_*.py file
```

### In VS Code
1. Open any `section_*.py` file
2. Click "Run Cell" above each `# %%` marker

### From Command Line
```bash
cd service_diagnostic
python section_1_system_info.py  # Runs entire section
```

## Notes

- Each section is self-contained
- Hardware sections initialize their own connection
- Results are stored in `results` list variable
- Modify `QUICK_MODE = True` for faster tests
