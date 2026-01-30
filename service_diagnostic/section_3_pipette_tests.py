# %% [markdown]
# # Section 3: Pipette Tests
#
# Tests pipette detection, plunger movement, and calibration status.
# **Requires hardware connection.**

# %%
import asyncio
import time
import json
from pathlib import Path
from common import (
    TestResult, TestStatus, print_header, print_result,
    ON_ROBOT, API, Axis, Mount
)

results = []

# %% [markdown]
# ### Initialize Hardware

# %%
api = None

async def init_hardware():
    global api
    if not ON_ROBOT:
        print("Not on robot - cannot run pipette tests")
        return False
    print("Initializing hardware...")
    api = await API.build_hardware_controller()
    await api.home()
    print("Ready.")
    return True

if ON_ROBOT:
    await init_hardware()

# %% [markdown]
# ### Test: Pipette Detection (LEFT)

# %%
async def test_detection(mount):
    start = time.time()
    mount_name = mount.name.lower()

    try:
        pipette = api.attached_instruments.get(mount)
        if pipette:
            data = {
                "model": pipette.get("model", "unknown"),
                "name": pipette.get("name", "unknown"),
                "pipette_id": pipette.get("pipette_id", "unknown"),
                "channels": pipette.get("channels", 1)
            }
            return TestResult(f"Pipette Detection ({mount_name})", TestStatus.PASS,
                            f"Detected: {data['name']}", data, time.time() - start)
        else:
            return TestResult(f"Pipette Detection ({mount_name})", TestStatus.WARNING,
                            "No pipette attached", duration_seconds=time.time() - start)
    except Exception as e:
        return TestResult(f"Pipette Detection ({mount_name})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

if api:
    print_header("LEFT PIPETTE DETECTION")
    r = await test_detection(Mount.LEFT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Pipette Detection (RIGHT)

# %%
if api:
    print_header("RIGHT PIPETTE DETECTION")
    r = await test_detection(Mount.RIGHT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Plunger Movement (LEFT)

# %%
async def test_plunger(mount):
    start = time.time()
    mount_name = mount.name.lower()

    try:
        pipette = api.hardware_pipettes.get(mount)
        if not pipette:
            return TestResult(f"Plunger ({mount_name})", TestStatus.SKIPPED,
                            "No pipette", duration_seconds=time.time() - start)

        await api.home_plunger(mount)
        plunger_axis = Axis.of_plunger(mount)
        pos_home = await api.current_position(mount=mount, refresh=True)
        home_pos = pos_home.get(plunger_axis, 0)

        await api.prepare_for_aspirate(mount)
        pos_bottom = await api.current_position(mount=mount, refresh=True)
        bottom_pos = pos_bottom.get(plunger_axis, 0)

        travel = abs(home_pos - bottom_pos)
        await api.home_plunger(mount)

        if travel > 1.0:
            return TestResult(f"Plunger ({mount_name})", TestStatus.PASS,
                            f"Travel: {travel:.2f}mm",
                            {"travel_mm": round(travel, 3)}, time.time() - start)
        else:
            return TestResult(f"Plunger ({mount_name})", TestStatus.FAIL,
                            f"Insufficient travel: {travel:.2f}mm",
                            {"travel_mm": round(travel, 3)}, time.time() - start)
    except Exception as e:
        return TestResult(f"Plunger ({mount_name})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

if api:
    print_header("LEFT PLUNGER TEST")
    r = await test_plunger(Mount.LEFT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Plunger Movement (RIGHT)

# %%
if api:
    print_header("RIGHT PLUNGER TEST")
    r = await test_plunger(Mount.RIGHT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Calibration Status (LEFT)

# %%
def test_calibration(mount):
    start = time.time()
    mount_name = mount.name.lower()

    try:
        pipette = api.attached_instruments.get(mount)
        if not pipette:
            return TestResult(f"Calibration ({mount_name})", TestStatus.SKIPPED,
                            "No pipette", duration_seconds=time.time() - start)

        pip_id = pipette.get("pipette_id")
        cal_path = Path(f"/data/opentrons/robot/pipettes/{mount_name}/{pip_id}.json")

        if cal_path.exists():
            with open(cal_path) as f:
                cal_data = json.load(f)
            offset = cal_data.get("offset", [0, 0, 0])
            return TestResult(f"Calibration ({mount_name})", TestStatus.PASS,
                            f"Offset: [{offset[0]:.2f}, {offset[1]:.2f}, {offset[2]:.2f}]",
                            {"offset": offset}, time.time() - start)
        else:
            return TestResult(f"Calibration ({mount_name})", TestStatus.WARNING,
                            "Not calibrated", duration_seconds=time.time() - start)
    except Exception as e:
        return TestResult(f"Calibration ({mount_name})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

if api:
    print_header("LEFT CALIBRATION CHECK")
    r = test_calibration(Mount.LEFT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Calibration Status (RIGHT)

# %%
if api:
    print_header("RIGHT CALIBRATION CHECK")
    r = test_calibration(Mount.RIGHT)
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Summary

# %%
print("\n" + "=" * 60)
print(" PIPETTE TEST RESULTS")
print("=" * 60)
for r in results:
    print_result(r)
