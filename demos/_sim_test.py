"""
End-to-end mock simulation for the trade-fair demo protocols.

Run with::

    python3 demos/_sim_test.py

The real Opentrons simulator is the ground truth, but it needs the
`opentrons` package installed and is slow. This harness stubs out the
Opentrons API with lightweight mock objects that are faithful enough to
*execute* each protocol's run() body start to finish - which catches
runtime errors the constant/class-level smoke test cannot, e.g. tuple
unpack mismatches, attribute typos, off-by-one indexing into wells(),
or RTP attribute names that do not match between add_parameters() and
run().

Each mock method is a no-op that returns chainable stubs; geometry
attributes (length/width/diameter/depth/max_volume) carry realistic
values so the LaneTracker / WellTracker math runs for real.

Exits non-zero if any protocol raises while running. Filename starts
with underscore so the Opentrons app does not load it as a protocol.
"""

import importlib.util
import math
import sys
import types


# ---------------------------------------------------------------------------
# Mock Opentrons API
# ---------------------------------------------------------------------------

class _Location:
    """Return value of well.bottom()/well.top(); carries a back-reference
    to the well so pipette calls can still reach geometry if needed."""

    def __init__(self, well, z):
        self.well = well
        self.point = (0.0, 0.0, z)


class _Well:
    def __init__(self, name, parent, *, rectangular, max_volume):
        self.name = name
        self._parent = parent
        self.max_volume = float(max_volume)
        if rectangular:
            self.length = 8.35      # NEST 12-channel lane x-dim
            self.width = 71.25      # NEST 12-channel lane y-dim
            self.diameter = None
            self.depth = 26.85
        else:
            self.length = None
            self.width = None
            self.diameter = 6.5     # generic 96-well circular
            self.depth = 14.3

    @property
    def parent(self):
        return self._parent

    def bottom(self, z=0.0):
        return _Location(self, z)

    def top(self, z=0.0):
        return _Location(self, self.depth + z)

    def load_liquid(self, liquid, volume):
        if volume < 0:
            raise ValueError(f"load_liquid negative volume on {self.name}")
        if volume > self.max_volume + 1e-6:
            raise ValueError(
                f"load_liquid {volume} uL exceeds {self.name} max "
                f"{self.max_volume} uL"
            )

    def __repr__(self):
        return f"{self._parent}:{self.name}"


_ROWS = "ABCDEFGH"
_N_ROWS, _N_COLS = 8, 12


class _Labware:
    def __init__(self, load_name, location, label, *, rectangular, max_volume):
        self.load_name = load_name
        self.parent = location           # slot label (e.g. "C1" or 4)
        self._label = label
        # Build 96 (or 12-lane reservoir) wells in COLUMN-MAJOR order,
        # which is how Opentrons' Labware.wells() returns them.
        self._by_name = {}
        self._ordered = []
        n_cols = _N_COLS
        n_rows = 1 if "reservoir" in load_name else _N_ROWS
        for col in range(1, n_cols + 1):
            for row_i in range(n_rows):
                name = f"{_ROWS[row_i]}{col}"
                w = _Well(name, self, rectangular=rectangular,
                          max_volume=max_volume)
                self._by_name[name] = w
                self._ordered.append(w)

    def wells(self):
        return list(self._ordered)

    def wells_by_name(self):
        return dict(self._by_name)

    def columns(self):
        # list of 12 columns, each a list of its rows (top->bottom)
        n_rows = 1 if "reservoir" in self.load_name else _N_ROWS
        cols = []
        for col in range(1, _N_COLS + 1):
            cols.append([self._by_name[f"{_ROWS[r]}{col}"] for r in range(n_rows)])
        return cols

    def __getitem__(self, name):
        return self._by_name[name]

    def __repr__(self):
        return f"Labware({self._label or self.load_name}@{self.parent})"


class _FlowRate:
    def __init__(self):
        self.aspirate = 0
        self.dispense = 0
        self.blow_out = 0


class _Instrument:
    def __init__(self, load_name, mount, tip_racks):
        self.name = load_name
        self.mount = mount
        self.tip_racks = list(tip_racks or [])
        self.flow_rate = _FlowRate()
        self._has_tip = False
        if "1000" in load_name:
            self.min_volume, self.max_volume = 5.0, 1000.0
        elif "p300" in load_name or "300" in load_name:
            self.min_volume, self.max_volume = 20.0, 300.0
        else:
            self.min_volume, self.max_volume = 1.0, 1000.0

    # --- tip handling ---
    def pick_up_tip(self, location=None):
        if self._has_tip:
            raise RuntimeError(f"{self.name}: pick_up_tip while tip already on")
        self._has_tip = True

    def return_tip(self):
        if not self._has_tip:
            raise RuntimeError(f"{self.name}: return_tip with no tip")
        self._has_tip = False

    def drop_tip(self, location=None):
        if not self._has_tip:
            raise RuntimeError(f"{self.name}: drop_tip with no tip")
        self._has_tip = False

    # --- liquid handling (validate against pipette volume envelope) ---
    def _check_vol(self, action, volume):
        if volume < 0:
            raise ValueError(f"{self.name}: {action} negative volume {volume}")
        # Opentrons rejects volumes above the pipette max outright.
        if volume > self.max_volume + 1e-6:
            raise ValueError(
                f"{self.name}: {action} {volume:.2f} uL exceeds max "
                f"{self.max_volume} uL"
            )

    def aspirate(self, volume, location=None, rate=1.0):
        self._check_vol("aspirate", volume)

    def dispense(self, volume, location=None, rate=1.0):
        self._check_vol("dispense", volume)

    def mix(self, reps, volume, location=None, rate=1.0):
        self._check_vol("mix", volume)

    def blow_out(self, location=None):
        pass

    def move_to(self, location):
        pass


class _Liquid:
    def __init__(self, name, description, display_color):
        self.name = name
        self.description = description
        self.display_color = display_color


class _Params:
    """Namespace populated from add_parameters() defaults."""


class _ParameterContext:
    """Captures add_int / add_bool / add_float calls so the harness can
    build a params namespace from their defaults - exactly the values the
    Opentrons app would feed a default run."""

    def __init__(self):
        self.values = {}

    def _add(self, variable_name, default, **kw):
        self.values[variable_name] = default

    def add_int(self, variable_name, default, **kw):
        self._add(variable_name, default)

    def add_float(self, variable_name, default, **kw):
        self._add(variable_name, default)

    def add_bool(self, variable_name, default, **kw):
        self._add(variable_name, default)

    def add_str(self, variable_name, default, **kw):
        self._add(variable_name, default)


class _ProtocolContext:
    def __init__(self, params):
        self.params = params
        self.comments = []
        self.deck = {}

    def load_labware(self, load_name, location, label=None):
        rectangular = "reservoir" in load_name
        max_volume = 15000.0 if rectangular else 250.0
        if "tiprack" in load_name:
            max_volume = 300.0
        lw = _Labware(load_name, location, label,
                      rectangular=rectangular, max_volume=max_volume)
        self.deck[str(location)] = lw
        return lw

    def load_instrument(self, load_name, mount, tip_racks=None):
        return _Instrument(load_name, mount, tip_racks)

    def load_trash_bin(self, location):
        return object()

    def define_liquid(self, name, description=None, display_color=None):
        return _Liquid(name, description, display_color)

    def comment(self, msg):
        self.comments.append(str(msg))

    def delay(self, seconds=0, minutes=0, msg=None):
        pass

    def pause(self, msg=None):
        pass

    def home(self):
        pass

    def set_rail_lights(self, on):
        pass


def _stub_opentrons():
    if "opentrons" in sys.modules:
        return
    ot = types.ModuleType("opentrons")
    pa = types.ModuleType("opentrons.protocol_api")
    pa.ProtocolContext = _ProtocolContext
    ot.protocol_api = pa
    sys.modules["opentrons"] = ot
    sys.modules["opentrons.protocol_api"] = pa


def _load(name):
    spec = importlib.util.spec_from_file_location(name, f"demos/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _simulate(mod, overrides=None):
    """Build a params namespace from add_parameters() (if present) and
    execute run() against the mock context. `overrides` patches param
    values (and module-level constants for protocols without RTPs).
    Returns the comment count."""
    overrides = overrides or {}
    params = _Params()
    if hasattr(mod, "add_parameters"):
        pc = _ParameterContext()
        mod.add_parameters(pc)
        for k, v in pc.values.items():
            setattr(params, k, v)
        # Speed up the run: zero out the delay parameters if present.
        for delay_attr in ("viewing_delay_s", "incubation_delay_s"):
            if hasattr(params, delay_attr):
                setattr(params, delay_attr, 0)
        for k, v in overrides.items():
            setattr(params, k, v)
    ctx = _ProtocolContext(params)
    mod.run(ctx)
    return len(ctx.comments)


def main() -> int:
    _stub_opentrons()
    failures = 0
    for name in (
        "trade_fair_painted_lab",
        "trade_fair_painted_lab_flex",
        "trade_fair_rgyb_serial_dilution",
        "trade_fair_rgyb_serial_dilution_flex",
        "trade_fair_color_matrix",
        "trade_fair_nest_flat",
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
