# %% [markdown]
# # Section 2: Motion System Tests
#
# Tests limit switches, homing accuracy, position repeatability, cross-deck accuracy.
# **Requires hardware connection.**

# %%
import asyncio
import time
import statistics
from common import (
    TestResult, TestStatus, print_header, print_result,
    ON_ROBOT, API, Axis, Mount, Point
)

# Configuration
QUICK_MODE = False  # Set True for fewer iterations

TEST_POSITIONS = {
    "slot_1": Point(x=14.38, y=11.24, z=100),
    "slot_3": Point(x=297.12, y=11.24, z=100),
    "slot_7": Point(x=14.38, y=258.76, z=100),
    "slot_9": Point(x=297.12, y=258.76, z=100),
    "slot_5_center": Point(x=155.75, y=135.0, z=100),
} if ON_ROBOT else {}

results = []

# %% [markdown]
# ### Initialize Hardware

# %%
api = None

async def init_hardware():
    global api
    if not ON_ROBOT:
        print("Not on robot - cannot run motion tests")
        return False
    print("Initializing hardware...")
    api = await API.build_hardware_controller()
    print("Homing...")
    await api.home()
    print("Ready.")
    return True

if ON_ROBOT:
    await init_hardware()

# %% [markdown]
# ### Test: Limit Switches

# %%
async def test_limit_switches():
    start = time.time()
    try:
        await api.home()
        switches = await api._backend._smoothie_driver.switch_state()
        gantry = {k: v for k, v in switches.items() if k in ["X", "Y", "Z", "A"]}

        if all(gantry.values()):
            return TestResult("Limit Switches", TestStatus.PASS,
                            "All triggered at home", {"switches": switches},
                            time.time() - start)
        else:
            failed = [k for k, v in gantry.items() if not v]
            return TestResult("Limit Switches", TestStatus.FAIL,
                            f"Not triggered: {failed}", {"switches": switches},
                            time.time() - start)
    except Exception as e:
        return TestResult("Limit Switches", TestStatus.ERROR, str(e),
                         duration_seconds=time.time() - start)

if api:
    print_header("LIMIT SWITCH TEST")
    r = await test_limit_switches()
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Homing Accuracy

# %%
async def test_homing_accuracy():
    start = time.time()
    iterations = 3 if QUICK_MODE else 5
    positions = []

    try:
        for _ in range(iterations):
            await api.move_rel(mount=Mount.LEFT, delta=Point(-30, -30, -30))
            await api.home()
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)
            positions.append({"X": pos.get(Axis.X, 0), "Y": pos.get(Axis.Y, 0), "Z": pos.get(Axis.Z, 0)})

        stats = {}
        for axis in ["X", "Y", "Z"]:
            vals = [p[axis] for p in positions]
            stats[axis] = {"mean": round(statistics.mean(vals), 4),
                          "range": round(max(vals) - min(vals), 4)}

        max_range = max(s["range"] for s in stats.values())

        if max_range < 0.1:
            status, msg = TestStatus.PASS, f"Excellent (<0.1mm)"
        elif max_range < 0.3:
            status, msg = TestStatus.WARNING, f"Acceptable ({max_range:.3f}mm)"
        else:
            status, msg = TestStatus.FAIL, f"Poor ({max_range:.3f}mm)"

        return TestResult("Homing Accuracy", status, msg,
                         {"iterations": iterations, "stats": stats},
                         time.time() - start)
    except Exception as e:
        return TestResult("Homing Accuracy", TestStatus.ERROR, str(e),
                         duration_seconds=time.time() - start)

if api:
    print_header("HOMING ACCURACY TEST")
    r = await test_homing_accuracy()
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Position Repeatability

# %%
async def test_position_repeatability():
    start = time.time()
    iterations = 5 if QUICK_MODE else 10
    target = TEST_POSITIONS["slot_5_center"]
    home_pos = Point(x=100, y=100, z=150)
    positions = []

    try:
        for _ in range(iterations):
            await api.move_to(mount=Mount.LEFT, abs_position=home_pos)
            await api.move_to(mount=Mount.LEFT, abs_position=target)
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)
            positions.append({"X": pos.get(Axis.X, 0), "Y": pos.get(Axis.Y, 0), "Z": pos.get(Axis.Z, 0)})

        stats = {}
        for axis in ["X", "Y", "Z"]:
            vals = [p[axis] for p in positions]
            stats[axis] = {"range": round(max(vals) - min(vals), 5)}

        rep_3d = (stats["X"]["range"]**2 + stats["Y"]["range"]**2 + stats["Z"]["range"]**2)**0.5
        await api.home()

        if rep_3d < 0.1:
            status, msg = TestStatus.PASS, f"Excellent ({rep_3d:.4f}mm)"
        elif rep_3d < 0.25:
            status, msg = TestStatus.WARNING, f"Acceptable ({rep_3d:.4f}mm)"
        else:
            status, msg = TestStatus.FAIL, f"Poor ({rep_3d:.4f}mm)"

        return TestResult("Position Repeatability", status, msg,
                         {"iterations": iterations, "repeatability_3d_mm": round(rep_3d, 5)},
                         time.time() - start)
    except Exception as e:
        return TestResult("Position Repeatability", TestStatus.ERROR, str(e),
                         duration_seconds=time.time() - start)

if api:
    print_header("POSITION REPEATABILITY TEST")
    r = await test_position_repeatability()
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Cross-Deck Accuracy

# %%
async def test_cross_deck():
    start = time.time()
    measurements = []

    try:
        for name, target in TEST_POSITIONS.items():
            await api.move_to(mount=Mount.LEFT, abs_position=target)
            pos = await api.current_position(mount=Mount.LEFT, refresh=True)
            actual = Point(pos.get(Axis.X, 0), pos.get(Axis.Y, 0), pos.get(Axis.Z, 0))
            error = ((actual.x - target.x)**2 + (actual.y - target.y)**2 + (actual.z - target.z)**2)**0.5
            measurements.append({"position": name, "error_mm": round(error, 4)})

        await api.home()
        max_err = max(m["error_mm"] for m in measurements)

        if max_err < 0.5:
            status, msg = TestStatus.PASS, f"Excellent (max {max_err:.3f}mm)"
        elif max_err < 1.5:
            status, msg = TestStatus.WARNING, f"Acceptable (max {max_err:.3f}mm)"
        else:
            status, msg = TestStatus.FAIL, f"Poor (max {max_err:.3f}mm)"

        return TestResult("Cross-Deck Accuracy", status, msg,
                         {"measurements": measurements},
                         time.time() - start)
    except Exception as e:
        return TestResult("Cross-Deck Accuracy", TestStatus.ERROR, str(e),
                         duration_seconds=time.time() - start)

if api:
    print_header("CROSS-DECK ACCURACY TEST")
    r = await test_cross_deck()
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Test: Z-Axis Movement

# %%
async def test_z_axis():
    start = time.time()
    z_results = {}

    try:
        for mount in [Mount.LEFT, Mount.RIGHT]:
            await api.home()
            await api.move_to(mount=mount, abs_position=Point(200, 200, 50))
            pos_down = await api.current_position(mount=mount, refresh=True)
            await api.move_to(mount=mount, abs_position=Point(200, 200, 150))
            pos_up = await api.current_position(mount=mount, refresh=True)

            z_axis = Axis.Z if mount == Mount.LEFT else Axis.A
            travel = abs(pos_up.get(z_axis, 0) - pos_down.get(z_axis, 0))
            z_results[mount.name.lower()] = {"travel_mm": round(travel, 2), "error_mm": round(abs(travel - 100), 2)}

        await api.home()
        max_err = max(r["error_mm"] for r in z_results.values())

        if max_err < 1.0:
            status, msg = TestStatus.PASS, "Accurate on both mounts"
        elif max_err < 3.0:
            status, msg = TestStatus.WARNING, f"Slightly off ({max_err:.2f}mm)"
        else:
            status, msg = TestStatus.FAIL, f"Error ({max_err:.2f}mm)"

        return TestResult("Z-Axis Movement", status, msg, z_results, time.time() - start)
    except Exception as e:
        return TestResult("Z-Axis Movement", TestStatus.ERROR, str(e),
                         duration_seconds=time.time() - start)

if api:
    print_header("Z-AXIS MOVEMENT TEST")
    r = await test_z_axis()
    results.append(r)
    print_result(r)

# %% [markdown]
# ### Summary

# %%
print("\n" + "=" * 60)
print(" MOTION TEST RESULTS")
print("=" * 60)
for r in results:
    print_result(r)
