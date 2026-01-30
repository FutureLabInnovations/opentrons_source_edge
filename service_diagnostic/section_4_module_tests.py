# %% [markdown]
# # Section 4: Module Tests
#
# Tests attached modules: Temperature, Magnetic, Thermocycler, Heater-Shaker.
# **Requires hardware connection.**

# %%
import asyncio
import time
from common import (
    TestResult, TestStatus, print_header, print_result,
    ON_ROBOT, API
)

results = []

# %% [markdown]
# ### Initialize Hardware

# %%
api = None

async def init_hardware():
    global api
    if not ON_ROBOT:
        print("Not on robot - cannot run module tests")
        return False
    print("Initializing hardware...")
    api = await API.build_hardware_controller()
    print("Ready.")
    return True

if ON_ROBOT:
    await init_hardware()

# %% [markdown]
# ### Detect Modules

# %%
modules = []

if api:
    modules = api.attached_modules
    print(f"Found {len(modules)} module(s):")
    for m in modules:
        print(f"  - {m.name()} (serial: {m.device_info.get('serial', 'unknown')})")
else:
    print("No hardware connection")

# %% [markdown]
# ### Test: Temperature Module

# %%
async def test_temp_module(module):
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        temp = module.temperature
        status = module.status
        data = {"serial": serial, "temperature_c": temp, "status": status}

        if temp is not None and 5 <= temp <= 50:
            return TestResult(f"Temp Module ({serial})", TestStatus.PASS,
                            f"Temp: {temp}C, Status: {status}", data, time.time() - start)
        else:
            return TestResult(f"Temp Module ({serial})", TestStatus.WARNING,
                            f"Unusual temp: {temp}C", data, time.time() - start)
    except Exception as e:
        return TestResult(f"Temp Module ({serial})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

for m in modules:
    if "temperature" in m.name().lower():
        print_header(f"TEMPERATURE MODULE TEST")
        r = await test_temp_module(m)
        results.append(r)
        print_result(r)

# %% [markdown]
# ### Test: Magnetic Module

# %%
async def test_mag_module(module):
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        await module.engage(height_from_base=5.0)
        await asyncio.sleep(1)
        engaged = module.status

        await module.deactivate()
        await asyncio.sleep(1)
        disengaged = module.status

        data = {"serial": serial, "engaged": engaged, "disengaged": disengaged}

        if "engaged" in engaged.lower() and "disengaged" in disengaged.lower():
            return TestResult(f"Mag Module ({serial})", TestStatus.PASS,
                            "Engage/disengage OK", data, time.time() - start)
        else:
            return TestResult(f"Mag Module ({serial})", TestStatus.WARNING,
                            "Status unclear", data, time.time() - start)
    except Exception as e:
        return TestResult(f"Mag Module ({serial})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

for m in modules:
    if "magnetic" in m.name().lower():
        print_header(f"MAGNETIC MODULE TEST")
        r = await test_mag_module(m)
        results.append(r)
        print_result(r)

# %% [markdown]
# ### Test: Thermocycler

# %%
async def test_thermocycler(module):
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        lid_status = module.lid_status
        lid_temp = module.lid_temp
        plate_temp = module.temperature

        data = {"serial": serial, "lid_status": lid_status,
                "lid_temp_c": lid_temp, "plate_temp_c": plate_temp}

        lid_ok = True
        if lid_status != "open":
            try:
                await module.open_lid()
                await asyncio.sleep(2)
                lid_ok = module.lid_status == "open"
            except:
                lid_ok = False

        try:
            await module.deactivate_lid()
            await module.deactivate_block()
        except:
            pass

        if lid_ok and lid_temp is not None:
            return TestResult(f"Thermocycler ({serial})", TestStatus.PASS,
                            f"Lid: {module.lid_status}, Temps OK", data, time.time() - start)
        else:
            return TestResult(f"Thermocycler ({serial})", TestStatus.WARNING,
                            "Limited functionality", data, time.time() - start)
    except Exception as e:
        return TestResult(f"Thermocycler ({serial})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

for m in modules:
    if "thermocycler" in m.name().lower():
        print_header(f"THERMOCYCLER TEST")
        r = await test_thermocycler(m)
        results.append(r)
        print_result(r)

# %% [markdown]
# ### Test: Heater-Shaker

# %%
async def test_heater_shaker(module):
    start = time.time()
    serial = module.device_info.get("serial", "unknown")

    try:
        temp = module.temperature
        latch = module.labware_latch_status

        data = {"serial": serial, "temperature_c": temp, "latch": latch}

        latch_ok = True
        try:
            await module.open_labware_latch()
            await asyncio.sleep(1)
            latch_ok = "open" in module.labware_latch_status
            await module.close_labware_latch()
        except:
            latch_ok = False

        try:
            await module.deactivate_heater()
            await module.deactivate_shaker()
        except:
            pass

        if temp is not None and latch_ok:
            return TestResult(f"Heater-Shaker ({serial})", TestStatus.PASS,
                            f"Temp: {temp}C, Latch OK", data, time.time() - start)
        else:
            return TestResult(f"Heater-Shaker ({serial})", TestStatus.WARNING,
                            "Limited functionality", data, time.time() - start)
    except Exception as e:
        return TestResult(f"Heater-Shaker ({serial})", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

for m in modules:
    if "heater" in m.name().lower():
        print_header(f"HEATER-SHAKER TEST")
        r = await test_heater_shaker(m)
        results.append(r)
        print_result(r)

# %% [markdown]
# ### Summary

# %%
print("\n" + "=" * 60)
print(" MODULE TEST RESULTS")
print("=" * 60)
if not results:
    print("  No modules tested")
for r in results:
    print_result(r)
