"""
opentrons_protocol_mock - lightweight mock of the Opentrons protocol API
=======================================================================

Drop-in test harness for Opentrons Python protocols. Stubs out the
``opentrons`` package with mock objects faithful enough to *execute*
each protocol's ``run()`` body start to finish, without needing the
real ``opentrons`` package installed and without spinning up a
simulator.

What it catches that constant-level smoke tests cannot:

* tuple-unpack mismatches (``for a, b, c in things`` against 4-tuples)
* attribute typos (``protocol.params.viewng_delay_s``)
* off-by-one indexing into ``plate.wells()`` or ``plate.columns()``
* RTP variable_name drift between ``add_parameters()`` and ``run()``
* over-volume aspirate / dispense (exceeds ``pipette.max_volume``)
* picking up / returning tips out of order
* loading a labware into a duplicate slot
* over-fill in ``well.load_liquid()``

What it does NOT cover (these need the real Opentrons simulator):

* labware-definition correctness (calibration, deck height, footprint)
* pipette-physics accuracy (flow rate effects, droplet behavior)
* deck-conflict checks (modules colliding, tip rack reach)
* version-gated API features (``apiLevel`` requirements)

This module is intentionally a single file with no external
dependencies so it can be copy-pasted into any Opentrons protocol
project. Public API:

  - ``install_mocks()``         - patch sys.modules so ``import opentrons``
                                  in the protocol gives the mocks
  - ``load_protocol(path)``     - import a protocol file as a module
  - ``simulate(mod, ...)``      - execute its ``run()`` against a mock
                                  ProtocolContext, return # of comments

Typical usage::

    from opentrons_protocol_mock import install_mocks, load_protocol, simulate

    install_mocks()
    mod = load_protocol("protocols/my_protocol.py")
    n = simulate(mod, param_overrides={"sample_count": 4})
    print(f"{n} comments emitted")

The mocks are deliberately permissive: any unknown attribute returns a
no-op stub so a protocol that exercises a method not modelled here
still imports and runs (it just doesn't get validated for that call).
Pull-request improvements welcome.
"""

import importlib.util
import math
import sys
import types


# ---------------------------------------------------------------------------
# Mock Opentrons API
# ---------------------------------------------------------------------------

class MockLocation:
    """Return value of ``well.bottom()`` / ``well.top()``. Carries a back-
    reference to the parent well so the caller can still reach geometry
    (e.g. for ``move_to(well.top())`` followed by another call)."""

    def __init__(self, well, z):
        self.well = well
        self.point = (0.0, 0.0, z)


class MockWell:
    """Geometry-faithful mock of a single well. Override
    ``length``/``width``/``diameter``/``depth``/``max_volume`` per
    labware type as needed (or pass ``rectangular=True`` for trough-style
    wells)."""

    def __init__(self, name, parent, *, rectangular, max_volume,
                 length=8.35, width=71.25, depth_rect=26.85,
                 diameter=6.5, depth_round=14.3):
        self.name = name
        self._parent = parent
        self.max_volume = float(max_volume)
        if rectangular:
            self.length = length
            self.width = width
            self.diameter = None
            self.depth = depth_rect
        else:
            self.length = None
            self.width = None
            self.diameter = diameter
            self.depth = depth_round

    @property
    def parent(self):
        return self._parent

    def bottom(self, z=0.0):
        return MockLocation(self, z)

    def top(self, z=0.0):
        return MockLocation(self, self.depth + z)

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
_DEFAULT_N_ROWS, _DEFAULT_N_COLS = 8, 12


class MockLabware:
    """Mock of a 96-well plate or 12-channel reservoir. Wells are built
    in COLUMN-MAJOR order to match Opentrons' ``Labware.wells()`` (the
    most common indexing bug source)."""

    def __init__(self, load_name, location, label, *, rectangular,
                 max_volume, n_rows=None, n_cols=_DEFAULT_N_COLS):
        self.load_name = load_name
        self.parent = location
        self._label = label
        if n_rows is None:
            n_rows = 1 if "reservoir" in load_name else _DEFAULT_N_ROWS
        self._n_rows = n_rows
        self._n_cols = n_cols
        self._by_name = {}
        self._ordered = []
        for col in range(1, n_cols + 1):
            for row_i in range(n_rows):
                name = f"{_ROWS[row_i]}{col}"
                w = MockWell(name, self, rectangular=rectangular,
                             max_volume=max_volume)
                self._by_name[name] = w
                self._ordered.append(w)

    def wells(self):
        return list(self._ordered)

    def wells_by_name(self):
        return dict(self._by_name)

    def columns(self):
        cols = []
        for col in range(1, self._n_cols + 1):
            cols.append([self._by_name[f"{_ROWS[r]}{col}"]
                         for r in range(self._n_rows)])
        return cols

    def __getitem__(self, name):
        return self._by_name[name]

    def __repr__(self):
        return f"Labware({self._label or self.load_name}@{self.parent})"


class MockFlowRate:
    def __init__(self):
        self.aspirate = 0
        self.dispense = 0
        self.blow_out = 0


# Pipette spec table - extend as needed for new pipette types.
_PIPETTE_SPECS = {
    "p10":             (1.0, 10.0),
    "p20":             (1.0, 20.0),
    "p50":             (5.0, 50.0),
    "p300":           (20.0, 300.0),
    "p1000":          (100.0, 1000.0),
    "flex_1channel_50":    (1.0, 50.0),
    "flex_1channel_1000":  (5.0, 1000.0),
    "flex_8channel_50":    (1.0, 50.0),
    "flex_8channel_1000":  (5.0, 1000.0),
    "flex_96channel_1000": (5.0, 1000.0),
}


def _resolve_pipette_spec(load_name):
    for key, spec in _PIPETTE_SPECS.items():
        if key in load_name:
            return spec
    return (1.0, 1000.0)   # permissive fallback


class MockInstrument:
    """Mock pipette with tip-state tracking and volume-envelope checks
    (real Opentrons raises on `aspirate > pipette.max_volume`; we mirror
    that). Sub-min aspirates are allowed because the real engine treats
    them as warnings, not errors."""

    def __init__(self, load_name, mount, tip_racks):
        self.name = load_name
        self.mount = mount
        self.tip_racks = list(tip_racks or [])
        self.flow_rate = MockFlowRate()
        self._has_tip = False
        self.min_volume, self.max_volume = _resolve_pipette_spec(load_name)

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

    # --- liquid handling ---
    def _check_vol(self, action, volume):
        if volume < 0:
            raise ValueError(f"{self.name}: {action} negative volume {volume}")
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


class MockLiquid:
    def __init__(self, name, description, display_color):
        self.name = name
        self.description = description
        self.display_color = display_color


class MockParams:
    """Empty namespace populated from add_parameters() defaults at
    simulate() time. ``getattr(params, "name", default)`` works as
    expected because Python attribute lookup falls back to the default."""


class MockParameterContext:
    """Captures add_int / add_bool / add_float / add_str calls so the
    harness can build a MockParams namespace from their defaults -
    exactly the values the Opentrons app would feed a default run."""

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


class MockProtocolContext:
    """Mock of opentrons.protocol_api.ProtocolContext. Tracks every
    ``protocol.comment(...)`` for later inspection; everything else
    is a no-op that returns a useful stub."""

    def __init__(self, params):
        self.params = params
        self.comments = []
        self.deck = {}

    def load_labware(self, load_name, location, label=None):
        slot = str(location)
        if slot in self.deck:
            raise RuntimeError(
                f"load_labware: slot {slot} already occupied by "
                f"{self.deck[slot]}"
            )
        rectangular = "reservoir" in load_name
        if rectangular:
            max_volume = 15000.0
        elif "tiprack" in load_name:
            max_volume = 1000.0 if "1000" in load_name else 300.0
        elif "tuberack" in load_name:
            if "50ml" in load_name:
                max_volume = 50_000.0
            elif "15ml" in load_name:
                max_volume = 15_000.0
            elif "2ml" in load_name:
                max_volume = 2_000.0
            else:
                max_volume = 2_000.0
        else:
            max_volume = 250.0   # generic flat / round 96-well default
        lw = MockLabware(load_name, location, label,
                         rectangular=rectangular, max_volume=max_volume)
        self.deck[slot] = lw
        return lw

    def load_instrument(self, load_name, mount, tip_racks=None):
        return MockInstrument(load_name, mount, tip_racks)

    def load_trash_bin(self, location):
        return object()

    def load_waste_chute(self):
        return object()

    def define_liquid(self, name, description=None, display_color=None):
        return MockLiquid(name, description, display_color)

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_mocks():
    """Insert mock ``opentrons`` modules into ``sys.modules`` so the
    next ``import opentrons.protocol_api`` (from a protocol file) sees
    the mocks. Idempotent."""
    if "opentrons" in sys.modules and getattr(
        sys.modules["opentrons"], "_is_opentrons_mock", False
    ):
        return
    ot = types.ModuleType("opentrons")
    ot._is_opentrons_mock = True
    pa = types.ModuleType("opentrons.protocol_api")
    pa.ProtocolContext = MockProtocolContext
    ot.protocol_api = pa
    sys.modules["opentrons"] = ot
    sys.modules["opentrons.protocol_api"] = pa


def load_protocol(path):
    """Import a protocol .py file by filesystem path and return the
    module object. ``install_mocks()`` should be called first."""
    import os
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def simulate(mod, param_overrides=None, zero_delays=True):
    """Build a params namespace from ``add_parameters()`` (if present),
    apply ``param_overrides``, then execute ``run()`` against a fresh
    ``MockProtocolContext``. Returns the number of comments emitted.

    Raises whatever the protocol raises (so callers can use try/except
    or pytest's ``raises``)."""
    param_overrides = param_overrides or {}
    params = MockParams()
    if hasattr(mod, "add_parameters"):
        pc = MockParameterContext()
        mod.add_parameters(pc)
        for k, v in pc.values.items():
            setattr(params, k, v)
        if zero_delays:
            for delay_attr in ("viewing_delay_s", "incubation_delay_s"):
                if hasattr(params, delay_attr):
                    setattr(params, delay_attr, 0)
        for k, v in param_overrides.items():
            setattr(params, k, v)
    ctx = MockProtocolContext(params)
    mod.run(ctx)
    return len(ctx.comments)


__all__ = [
    "install_mocks",
    "load_protocol",
    "simulate",
    "MockProtocolContext",
    "MockLabware",
    "MockWell",
    "MockLocation",
    "MockInstrument",
    "MockFlowRate",
    "MockLiquid",
    "MockParams",
    "MockParameterContext",
]
