"""
Smoke test for the rgyb scripts' liquid-tracking classes and constants.

Run with::

    python3 demos/_smoke_test_rgyb.py

Stubs out the `opentrons` package so the rgyb modules can import without
the real Opentrons API installed, then exercises LaneTracker /
WellTracker math + a few constants. Returns non-zero on failure so it
can sit in a CI step. Not loaded by the protocols themselves; the
filename starts with underscore to keep the Opentrons app from picking
it up as a protocol.
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
