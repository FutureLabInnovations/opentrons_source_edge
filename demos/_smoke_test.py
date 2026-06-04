"""
Smoke test for the trade-fair demo scripts: import, class behavior,
and module constants.

Run with::

    python3 demos/_smoke_test_rgyb.py

Stubs out the `opentrons` package so the rgyb + painted_lab modules
can import without the real Opentrons API installed, then runs:

  rgyb:
      LaneTracker math + LaneExhaustedError boundary
      WellTracker overflow
      key volume constants
  painted_lab:
      module imports cleanly
      ESTIMATED_DRAW_UL has all 4 reagents
      TIP_SECTIONS covers cols 1-12 exactly once
      key volume constants

Returns non-zero on failure. Filename starts with underscore so the
Opentrons app doesn't pick it up as a protocol.
"""

import importlib.util
import sys
import types


def _stub_opentrons() -> None:
    if "opentrons" in sys.modules:
        return
    ot = types.ModuleType("opentrons")
    pa = types.ModuleType("opentrons.protocol_api")

    class _PC:  # ProtocolContext placeholder for type-hint evaluation
        pass

    pa.ProtocolContext = _PC
    ot.protocol_api = pa
    sys.modules["opentrons"] = ot
    sys.modules["opentrons.protocol_api"] = pa


def _load(path: str):
    spec = importlib.util.spec_from_file_location(path, f"demos/{path}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Well:
    """Stub well matching the attributes LaneTracker / WellTracker read."""

    def __init__(self, length=8.35, width=71.25, diameter=None,
                 depth=26.85, max_volume=15_000):
        self.length = length
        self.width = width
        self.diameter = diameter
        self.depth = depth
        self.max_volume = max_volume

    def __repr__(self) -> str:
        return f"_Well(L={self.length}, W={self.width}, D={self.diameter})"


def _check_lane_tracker(mod) -> None:
    well = _Well()
    t = mod.LaneTracker(10.0, well)
    assert abs(t.area_mm2 - well.length * well.width) < 1e-6
    assert t.current_volume_ul == 10_000.0

    # First aspirate: z should be ~14.68 mm with safety_margin_mm=2,
    # min_height_mm=1 on a 595 mm² lane (rgyb defaults).
    z = t.aspirate_height(75)
    expected_z = (9925 / t.area_mm2) - 2.0
    assert abs(z - expected_z) < 1e-6, (z, expected_z)
    assert t.current_volume_ul == 9925

    # Drain until exhausted - reserve is (1+2)*area ~= 1785 uL.
    # 10000-1785 = 8215 usable -> 8215/75 = 109.5 aspirates total
    # (one already taken). Walk until LaneExhaustedError.
    n = 1
    try:
        while True:
            t.aspirate_height(75)
            n += 1
    except mod.LaneExhaustedError:
        pass
    assert 100 <= n <= 115, n   # tight band - regression detector


def _check_well_tracker(mod) -> None:
    w = _Well(length=None, width=None, diameter=6.5,
              depth=14.3, max_volume=250)
    wt = mod.WellTracker(w)
    wt.add(100)
    wt.add(100)
    raised = False
    try:
        wt.add(100)   # 300 > 250
    except ValueError:
        raised = True
    assert raised, "WellTracker did not raise on overflow"


def _check_constants(mod) -> None:
    assert mod.STOCK_UL == 150
    assert mod.DILUENT_UL == 75
    assert mod.XFER_UL == 75
    assert mod.MIX_UL == 75
    assert mod.MIX_REPS == 4
    assert mod.WASH_MIX_UL == 250
    assert mod.WASH_MIX_REPS == 4
    assert mod.TRAILING_TEST_ENABLED is True
    assert mod.OVERHEAD_FRACTION == 0.03
    assert mod.DEAD_VOLUME_UL == 500
    assert mod.LANE_USABLE_UL == 13_000


def _check_smart_calc(mod) -> None:
    """Reproduce the rgyb planner math by hand and verify it matches the
    constants. Catches regressions in the smart-calc block that would
    quietly change pour recommendations."""
    area_mm2 = 8.35 * 71.25
    reserve = (2.0 + 1.0) * area_mm2

    need = 11 * 8 * mod.DILUENT_UL * 3
    assert need == 19_800

    n = 1
    while True:
        pour = need * (1 + mod.OVERHEAD_FRACTION) + mod.DEAD_VOLUME_UL + reserve * n
        if pour / n <= mod.LANE_USABLE_UL:
            break
        n += 1
        if n > 10:
            raise RuntimeError("Smart-calc converged outside expected band")
    assert n == 2, f"diluent lane count = {n} (expected 2)"
    assert 12_200 < pour / n < 12_300, f"diluent pour/lane = {pour/n:.0f}"

    stock_need = 8 * mod.STOCK_UL
    stock_pour = max(
        5_000.0,
        stock_need * (1 + mod.OVERHEAD_FRACTION) + mod.DEAD_VOLUME_UL + reserve,
    )
    assert stock_pour == 5_000.0, f"stock pour = {stock_pour} (expected 5000.0)"


def _check_painted_lab_constants(mod) -> None:
    # All four primary reagents represented in the estimate table.
    assert set(mod.ESTIMATED_DRAW_UL) == {"red", "yellow", "blue", "water"}, \
        mod.ESTIMATED_DRAW_UL
    # Each estimated draw is a positive integer microlitre count.
    for k, v in mod.ESTIMATED_DRAW_UL.items():
        assert isinstance(v, int) and v > 0, (k, v)

    # Tip sections cover cols 1..12 with no gaps or overlaps.
    covered = []
    for color, (start, end) in mod.TIP_SECTIONS.items():
        covered.extend(range(start, end + 1))
    assert sorted(covered) == list(range(1, 13)), covered
    # And exactly four sections - red, yellow, blue, wash.
    assert set(mod.TIP_SECTIONS) == {"red", "yellow", "blue", "wash"}, \
        mod.TIP_SECTIONS

    # PLATE_PARAM_NAMES + PLATE_PARAM_LABELS must agree on length and
    # cover all six plates (the run loop zips them together).
    assert len(mod.PLATE_PARAM_NAMES) == 6, mod.PLATE_PARAM_NAMES
    assert len(mod.PLATE_PARAM_LABELS) == 6, mod.PLATE_PARAM_LABELS
    for name in mod.PLATE_PARAM_NAMES:
        assert name.startswith("run_plate_"), name

    # PLATE_MINUTES_ESTIMATE must cover every label exactly.
    assert set(mod.PLATE_MINUTES_ESTIMATE) == set(mod.PLATE_PARAM_LABELS), (
        mod.PLATE_MINUTES_ESTIMATE.keys(), mod.PLATE_PARAM_LABELS,
    )
    for label, minutes in mod.PLATE_MINUTES_ESTIMATE.items():
        assert isinstance(minutes, int) and minutes > 0, (label, minutes)

    # Volume constants match the painted_lab values.
    assert mod.STOCK_UL == 150
    assert mod.DILUENT_UL == 75
    assert mod.XFER_UL == 75
    assert mod.MIX_UL == 75
    assert mod.MIX_REPS == 4
    assert mod.HALF_STOCK_UL == 75
    assert mod.THIRD_STOCK_UL == 50
    assert mod.MIN_DISPENSE_UL == 20
    assert mod.WASH_MIX_UL == 250
    assert mod.WASH_MIX_REPS == 4

    # Planner buffers.
    assert mod.OVERHEAD_FRACTION == 0.03
    assert mod.DEAD_VOLUME_PER_REAGENT_UL == 500
    assert mod.WORKING_LANE_CAPACITY_UL == 12_000


def main() -> int:
    _stub_opentrons()
    failures = 0
    for name in (
        "trade_fair_rgyb_serial_dilution",
        "trade_fair_rgyb_serial_dilution_flex",
    ):
        try:
            mod = _load(name)
            _check_lane_tracker(mod)
            _check_well_tracker(mod)
            _check_constants(mod)
            _check_smart_calc(mod)
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: AssertionError - {e}")
        except Exception as e:   # noqa: BLE001
            failures += 1
            print(f"FAIL  {name}: {type(e).__name__} - {e}")

    for name in (
        "trade_fair_painted_lab",
        "trade_fair_painted_lab_flex",
    ):
        try:
            mod = _load(name)
            _check_painted_lab_constants(mod)
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: AssertionError - {e}")
        except Exception as e:   # noqa: BLE001
            failures += 1
            print(f"FAIL  {name}: {type(e).__name__} - {e}")
    return failures


if __name__ == "__main__":
    sys.exit(main())
