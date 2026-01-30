# %% [markdown]
# # Section 5: Calibration Verification
#
# Checks deck calibration, pipette calibrations, and tip length calibrations.
# **Can run without hardware - reads calibration files.**

# %%
import json
import time
from pathlib import Path
from common import TestResult, TestStatus, print_header, print_result, ON_ROBOT

if ON_ROBOT:
    import numpy as np

results = []

# %% [markdown]
# ### Test: Deck Calibration

# %%
def test_deck_calibration():
    start = time.time()
    deck_cal_file = Path("/data/opentrons/robot/deck_calibration.json")

    if not deck_cal_file.exists():
        return TestResult("Deck Calibration", TestStatus.WARNING,
                         "Deck not calibrated", duration_seconds=time.time() - start)

    try:
        with open(deck_cal_file) as f:
            cal_data = json.load(f)

        attitude = cal_data.get("attitude", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        last_modified = cal_data.get("last_modified", "unknown")

        if ON_ROBOT:
            arr = np.array(attitude)
            det = np.linalg.det(arr)
            rank = np.linalg.matrix_rank(arr)
            is_identity = np.allclose(arr, np.eye(3))
        else:
            det, rank = 1.0, 3
            is_identity = attitude == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        data = {"last_modified": last_modified, "determinant": round(float(det), 6),
                "is_identity": bool(is_identity)}

        if rank == 3 and 0.5 < abs(det) < 2.0:
            if is_identity:
                return TestResult("Deck Calibration", TestStatus.WARNING,
                                "Identity matrix (needs calibration)", data, time.time() - start)
            else:
                return TestResult("Deck Calibration", TestStatus.PASS,
                                f"Calibrated ({last_modified})", data, time.time() - start)
        else:
            return TestResult("Deck Calibration", TestStatus.FAIL,
                            "Invalid matrix", data, time.time() - start)
    except Exception as e:
        return TestResult("Deck Calibration", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("DECK CALIBRATION")
r = test_deck_calibration()
results.append(r)
print_result(r)

# %% [markdown]
# ### Test: Pipette Calibrations

# %%
def test_pipette_calibrations():
    start = time.time()
    pip_cal_dir = Path("/data/opentrons/robot/pipettes")
    calibrations = {"left": [], "right": []}

    try:
        for mount in ["left", "right"]:
            mount_dir = pip_cal_dir / mount
            if mount_dir.exists():
                for cal_file in mount_dir.glob("*.json"):
                    with open(cal_file) as f:
                        cal_data = json.load(f)
                    calibrations[mount].append({
                        "pipette_id": cal_file.stem,
                        "offset": cal_data.get("offset", [0, 0, 0])
                    })

        total = len(calibrations["left"]) + len(calibrations["right"])

        if total > 0:
            return TestResult("Pipette Calibrations", TestStatus.PASS,
                            f"Found {total} calibration(s)", calibrations, time.time() - start)
        else:
            return TestResult("Pipette Calibrations", TestStatus.WARNING,
                            "No calibrations found", calibrations, time.time() - start)
    except Exception as e:
        return TestResult("Pipette Calibrations", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("PIPETTE CALIBRATIONS")
r = test_pipette_calibrations()
results.append(r)
print_result(r)

# %% [markdown]
# ### Test: Tip Length Calibrations

# %%
def test_tip_lengths():
    start = time.time()
    tip_dir = Path("/data/opentrons/tip_lengths")
    tip_lengths = {}

    try:
        if tip_dir.exists():
            for cal_file in tip_dir.glob("*.json"):
                with open(cal_file) as f:
                    cal_data = json.load(f)
                tip_lengths[cal_file.stem] = {
                    "tiprack_count": len(cal_data) if isinstance(cal_data, dict) else 0
                }

        if tip_lengths:
            total = sum(t["tiprack_count"] for t in tip_lengths.values())
            return TestResult("Tip Length Calibrations", TestStatus.PASS,
                            f"{len(tip_lengths)} pipette(s), {total} tiprack(s)",
                            tip_lengths, time.time() - start)
        else:
            return TestResult("Tip Length Calibrations", TestStatus.WARNING,
                            "No tip lengths found", {}, time.time() - start)
    except Exception as e:
        return TestResult("Tip Length Calibrations", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("TIP LENGTH CALIBRATIONS")
r = test_tip_lengths()
results.append(r)
print_result(r)

# %% [markdown]
# ### Summary

# %%
print("\n" + "=" * 60)
print(" CALIBRATION CHECK RESULTS")
print("=" * 60)
for r in results:
    print_result(r)
