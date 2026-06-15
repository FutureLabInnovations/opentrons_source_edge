"""
End-to-end mock simulation for the trade-fair demo protocols.

Run with::

    python3 demos/_sim_test.py

Uses the reusable ``demos/opentrons_protocol_mock.py`` library (drop-in
for any Opentrons protocol project) to execute every demo's ``run()``
against mock Opentrons objects. Catches runtime errors the constant /
class-level smoke test cannot, e.g. tuple unpack mismatches, attribute
typos, off-by-one indexing into wells(), or RTP attribute names that
do not match between add_parameters() and run().

Exits non-zero if any protocol raises while running. Filename starts
with underscore so the Opentrons app does not load it as a protocol.
"""

import importlib.util
import os
import sys

# Local-import the mock library (sibling file in demos/).
_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_SPEC = importlib.util.spec_from_file_location(
    "opentrons_protocol_mock",
    os.path.join(_HERE, "opentrons_protocol_mock.py"),
)
_LIB = importlib.util.module_from_spec(_LIB_SPEC)
_LIB_SPEC.loader.exec_module(_LIB)


def _load(name):
    return _LIB.load_protocol(os.path.join(_HERE, f"{name}.py"))


def _simulate(mod, overrides=None):
    return _LIB.simulate(mod, param_overrides=overrides)


def main() -> int:
    _LIB.install_mocks()
    failures = 0
    for name in (
        "trade_fair_painted_lab",
        "trade_fair_painted_lab_flex",
        "trade_fair_rgyb_serial_dilution",
        "trade_fair_rgyb_serial_dilution_flex",
        "trade_fair_color_matrix",
        "trade_fair_nest_flat",
        "trade_fair_loop_demo",
    ):
        try:
            mod = _load(name)
            n = _simulate(mod)
            print(f"PASS  {name}: run() completed, {n} comments emitted")
        except Exception as e:   # noqa: BLE001
            failures += 1
            import traceback
            print(f"FAIL  {name}: {type(e).__name__} - {e}")
            traceback.print_exc()

    # Loop demo wet-mode pass (default exercises dry; wet has its own
    # aspirate/dispense path and the row-A-only caveat comment).
    try:
        mod = _load("trade_fair_loop_demo")
        n = _simulate(mod, overrides={
            "n_cycles": 2,
            "dispense_volume_ul": 20,   # wet
            "inter_cycle_pause_s": 0,
        })
        print(f"PASS  trade_fair_loop_demo [wet]: run() completed, {n} comments")
    except Exception as e:   # noqa: BLE001
        failures += 1
        import traceback
        print(f"FAIL  trade_fair_loop_demo [wet]: {type(e).__name__} - {e}")
        traceback.print_exc()

    # Second pass for the painted_lab pair: exercise the skip-plate and
    # trailing-off branches (those have their own tuple shapes / report
    # paths the default run never reaches).
    for name in ("trade_fair_painted_lab", "trade_fair_painted_lab_flex"):
        try:
            mod = _load(name)
            n = _simulate(mod, overrides={
                "trailing_test_enabled": False,
                "run_plate_2_synergy": False,
                "run_plate_5_bouquet": False,
            })
            print(f"PASS  {name} [skip+notrail]: run() completed, {n} comments")
        except Exception as e:   # noqa: BLE001
            failures += 1
            import traceback
            print(f"FAIL  {name} [skip+notrail]: {type(e).__name__} - {e}")
            traceback.print_exc()

    return failures


if __name__ == "__main__":
    sys.exit(main())
