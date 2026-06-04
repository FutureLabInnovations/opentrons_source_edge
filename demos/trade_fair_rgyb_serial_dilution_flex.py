"""
Opentrons Flex Trade Fair Demo  -  RGYB Serial Dilution (12-channel reservoir)
==============================================================================

Flex port of demos/trade_fair_rgyb_serial_dilution.py. Only the hardware
references change (robot type, pipette load names, tip rack load name,
deck-slot notation, explicit movable trash); the dilution math, the
LaneTracker / WellTracker classes, the smart pour-calculation, and the
wash-and-return tip discipline are all identical to the OT-2 version.

Workflow (3 plates, 3 colours):
  * Plate D1: Red   stock, 1:2 serial dilution cols 1->12
  * Plate D2: Yellow stock, 1:2 serial dilution cols 1->12
  * Plate D3: Blue  stock, 1:2 serial dilution cols 1->12

Per plate:
  1. 1-channel: load 75 uL diluent into every well of cols 2-12.
  2. 1-channel: load 150 uL stock into every well of col 1.
  3. Wash that tip in the wash lane, then RETURN it (never drop).
  4. 8-channel: aspirate 75 uL from col 1, dispense + mix into
     col 2; repeat across cols 1 -> 12 (1:2 serial dilution).
  5. Wash the 8-channel tip column in the wash lane, RETURN them.

Tip discipline:
  * Tips are NEVER dropped to the trash. Every tip is washed in the
    wash lane (mix(4, 250) + blow_out) and returned to its rack
    position with pipette.return_tip().
  * The 1-channel tip used for diluent + stock picks up trace stock
    dye in step 2; the wash before return rinses it back near-clean.
  * Each colour gets its own 1-channel tip and its own 8-channel tip
    column - no cross-colour reuse.

==============================================================================
MATERIALS
==============================================================================

Hardware:
  * Opentrons Flex
  * Flex 1-Channel 1000 uL pipette   (left mount)
  * Flex 8-Channel 1000 uL pipette   (right mount)
  * Flex movable trash bin           (slot A3 - not used for tip drops,
                                      Flex still requires it to be loaded)

Labware:
  * 3 x thermofisher_96_wellplate_250ul    (custom labware, slots D1, D2, D3)
  * 1 x nest_12_reservoir_15ml             (slot C1)
  * 1 x opentrons_flex_96_tiprack_1000ul   (slot B2)

Reservoir layout (slot C1, NEST 12-channel):
   A1  Red dye          (~ 1.7  mL of 1:5 diluted red food colouring)
   A2  Yellow dye       (~ 1.7  mL)
   A3  Blue dye         (~ 1.7  mL)
   A4  Diluent water    (~10.4  mL  - first diluent lane)
   A5  Diluent water    (~10.4  mL  - second diluent lane, auto-rotated)
   A6  Wash water       (~13    mL  - in-place mixing, no draws)
   A7..A12 unused

Reagents to prepare:
  * Red / yellow / blue food colouring, each diluted 1:5 in water;
    pour ~2 mL into A1 / A2 / A3 respectively.
  * Distilled water: pour ~11 mL each into lanes A4 and A5 (diluent),
    plus ~13 mL into lane A6 (tip wash).

Pre-flight comments printed at run start will tell you the exact
amount to pour - those numbers always reflect the current planning
math.

==============================================================================
RUN ORDER  (top of run() prints this same plan to the app's run log)
==============================================================================

  1. Home + rail lights on.
  2. Pre-flight reservoir comment block.
  3. Plate D1 (red)   -> diluent fill -> stock fill -> wash + return tip
                       -> 8-channel serial dilute -> wash + return tips.
  4. Plate D2 (yellow) - same choreography.
  5. Plate D3 (blue)   - same choreography.
  6. End-of-run usage comment block (per-lane uL remaining).
"""

import math

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair - RGYB Serial Dilution (Flex, 12-well reservoir)",
    "author": "FLi / Flex adaptation",
    "description": (
        "Flex port of the OT-2 RGYB serial-dilution demo. NEST 12-channel "
        "reservoir; LaneTracker + WellTracker for liquid-height tracking; "
        "wash-and-return tip discipline (no tips dropped to trash)."
    ),
    "source": "NCBL v0.973 (FLi)",
}

# apiLevel 2.16 supports Flex + define_liquid + load_liquid + load_trash_bin.
requirements = {"robotType": "Flex", "apiLevel": "2.16"}

# ---------------------------------------------------------------------------
# Test instrumentation
# ---------------------------------------------------------------------------
# When TRAILING_TEST_ENABLED is True, every call routed through
# trailed_aspirate() / trailed_dispense() is split into:
#       1) main step at (vol - TRAILING_VOL_UL)  at the requested location
#       2) protocol.delay(seconds=TRAILING_DELAY_S)
#       3) tail step at TRAILING_VOL_UL          at the same location
# Net volume per logical step is unchanged (vol-eps + eps = vol). Set the
# toggle to False to silently fall back to a single native aspirate/dispense.
TRAILING_TEST_ENABLED = True
TRAILING_VOL_UL       = 0.01
TRAILING_DELAY_S      = 0.5



# ===========================================================================
# Liquid-tracking classes
# ===========================================================================

class LaneExhaustedError(RuntimeError):
    """Raised when a lane cannot satisfy an aspirate without the tip
    rising above the liquid surface. The protocol is configured to
    pour generously so this never fires; if it does, the booth crew
    underfilled the lane."""


class LaneTracker:
    """Tracks remaining volume + liquid-surface height for a single
    12-channel reservoir lane. Flat rectangular trough (no cone math).

    Use aspirate_height(vol_ul) to get a Z target (mm above well floor)
    for the NEXT aspirate of vol_ul uL, and to atomically decrement the
    remaining volume. Raises LaneExhaustedError if the lane is too low -
    the protocol does NOT rotate lanes; every lane is pre-poured with
    enough volume to satisfy its workload + a comfortable buffer.
    """

    def __init__(self, initial_volume_ml, well,
                 safety_margin_mm=2.0, min_height_mm=1.0):
        self.well = well
        self.current_volume_ul = float(initial_volume_ml) * 1000.0
        self.max_volume_ul = float(well.max_volume)
        self.safety_margin_mm = float(safety_margin_mm)
        self.min_height_mm = float(min_height_mm)

        # NEST 12-channel lanes are rectangular troughs. Use
        # well.length x well.width when the labware definition exposes
        # them; fall back to a circle from .diameter otherwise.
        length = getattr(well, "length", None)
        width  = getattr(well, "width",  None)
        if length and width:
            self.area_mm2 = float(length) * float(width)
        else:
            d = float(getattr(well, "diameter", 8.0))
            self.area_mm2 = math.pi * (d / 2.0) ** 2

        # Volume that has to stay behind so the tip never rises above
        # the liquid surface. Anything at or below this is unrecoverable.
        self.unusable_volume_ul = (
            (self.safety_margin_mm + self.min_height_mm) * self.area_mm2
        )

        if self.current_volume_ul > self.max_volume_ul:
            raise ValueError(
                f"LaneTracker({well}): initial {initial_volume_ml} mL "
                f"exceeds lane capacity {self.max_volume_ul / 1000:.1f} mL."
            )

    def surface_height_mm(self):
        return self.current_volume_ul / self.area_mm2

    def can_supply(self, vol_ul):
        """Return True iff aspirating vol_ul would leave the surface
        at or above (min_height_mm + safety_margin_mm)."""
        return (self.current_volume_ul - vol_ul) >= self.unusable_volume_ul

    def aspirate_height(self, vol_ul):
        """Decrement the tracker by vol_ul uL and return the tip target
        height (mm above well floor) for that aspirate - safety_margin_mm
        below the post-aspirate liquid surface so the tip stays submerged.
        Raises LaneExhaustedError if the lane can't safely supply vol_ul."""
        if not self.can_supply(vol_ul):
            raise LaneExhaustedError(
                f"LaneTracker({self.well}): only {self.current_volume_ul:.0f} uL "
                f"remaining ({self.surface_height_mm():.2f} mm surface), need "
                f"{vol_ul:.1f} uL without dropping below "
                f"{self.unusable_volume_ul:.0f} uL safe-floor reserve."
            )
        new_volume_ul = self.current_volume_ul - vol_ul
        new_surface_mm = new_volume_ul / self.area_mm2
        target_mm = new_surface_mm - self.safety_margin_mm
        self.current_volume_ul = new_volume_ul
        return target_mm


class WellTracker:
    """Tracks volume accumulated in a destination well and reports the
    safe lift-off height after each dispense (current surface + 1 mm)
    so the tip touches off without re-submerging."""

    def __init__(self, well, initial_volume_ul=0.0, lift_margin_mm=1.0):
        self.well = well
        self.current_volume_ul = float(initial_volume_ul)
        self.max_volume_ul = float(well.max_volume)
        self.lift_margin_mm = float(lift_margin_mm)
        d = float(getattr(well, "diameter", 6.0))
        self.area_mm2 = math.pi * (d / 2.0) ** 2

    def surface_height_mm(self):
        return self.current_volume_ul / self.area_mm2

    def add(self, vol_ul):
        new_volume_ul = self.current_volume_ul + vol_ul
        if new_volume_ul > self.max_volume_ul:
            raise ValueError(
                f"WellTracker({self.well}): would overflow well "
                f"(max {self.max_volume_ul} uL, attempted {new_volume_ul:.1f})."
            )
        self.current_volume_ul = new_volume_ul
        return self.surface_height_mm() + self.lift_margin_mm


# ===========================================================================
# Constants
# ===========================================================================

PLATE_LOAD_NAME = "thermofisher_96_wellplate_250ul"   # custom labware
STOCK_UL    = 150     # initial stock per col-1 well
DILUENT_UL  = 75      # diluent in every other well
XFER_UL     = 75      # serial dilution transfer
MIX_UL      = 75      # in-well mix volume
MIX_REPS    = 4
WASH_MIX_UL = 250     # tip-wash in-place mix volume

# Smart-planning buffers
OVERHEAD_FRACTION = 0.03
DEAD_VOLUME_UL    = 500     # 0.5 mL per reagent
LANE_USABLE_UL    = 13_000  # 13 mL working fill per NEST lane


# ===========================================================================
# Protocol
# ===========================================================================

def run(protocol: protocol_api.ProtocolContext):


    # ---------------- test-instrumentation wrappers ----------------
    # See module-level TRAILING_TEST_ENABLED to disable.
    # The tail step uses max(TRAILING_VOL_UL, pipette.min_volume), so on
    # pipettes with a hardware floor above 0.01 uL (e.g. Flex 1k = 5 uL),
    # the 0.01 uL request is silently bumped up to the pipette minimum.
    # Net volume per logical step is unchanged either way.
    def _trailed_eps(pipette):
        return max(TRAILING_VOL_UL,
                   float(getattr(pipette, "min_volume", TRAILING_VOL_UL)))

    def trailed_aspirate(pipette, vol_ul, location):
        if not TRAILING_TEST_ENABLED:
            pipette.aspirate(vol_ul, location)
            return
        eps = _trailed_eps(pipette)
        if vol_ul < 2 * eps:
            # Volume too small to split into (main + tail) without one
            # half going below the pipette minimum; fall back to native.
            pipette.aspirate(vol_ul, location)
            return
        pipette.aspirate(vol_ul - eps, location)
        protocol.delay(seconds=TRAILING_DELAY_S)
        pipette.aspirate(eps,           location)

    def trailed_dispense(pipette, vol_ul, location):
        if not TRAILING_TEST_ENABLED:
            pipette.dispense(vol_ul, location)
            return
        eps = _trailed_eps(pipette)
        if vol_ul < 2 * eps:
            pipette.dispense(vol_ul, location)
            return
        pipette.dispense(vol_ul - eps, location)
        protocol.delay(seconds=TRAILING_DELAY_S)
        pipette.dispense(eps,           location)

    # -----------------------------------------------------------------------
    # Labware (Flex deck uses letter+number slot notation)
    # -----------------------------------------------------------------------
    tips_1000 = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "B2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml",           "C1")

    target_plate_1 = protocol.load_labware(PLATE_LOAD_NAME, "D1", "plate-1 red")
    target_plate_2 = protocol.load_labware(PLATE_LOAD_NAME, "D2", "plate-2 yellow")
    target_plate_3 = protocol.load_labware(PLATE_LOAD_NAME, "D3", "plate-3 blue")
    plates = [target_plate_1, target_plate_2, target_plate_3]

    # Flex requires an explicit trash bin even if we never drop tips.
    protocol.load_trash_bin("A3")

    # -----------------------------------------------------------------------
    # Pipettes (Flex 1-channel + Flex 8-channel, both 1000 uL)
    # -----------------------------------------------------------------------
    flex_s = protocol.load_instrument(
        "flex_1channel_1000", "left",  tip_racks=[tips_1000]
    )
    flex_m = protocol.load_instrument(
        "flex_8channel_1000", "right", tip_racks=[tips_1000]
    )

    # -----------------------------------------------------------------------
    # Smart calculations (per-reagent need + pour recommendation)
    # -----------------------------------------------------------------------
    # Compute the per-lane unusable reserve from the actual reservoir
    # geometry. This is the volume that has to stay behind so the tip
    # never rises above the liquid surface (= safety_margin + min_height
    # mm above the floor, times the lane cross-section). Pour budgets
    # below include this reserve per assigned lane so we always have
    # enough USABLE volume to satisfy every aspirate.
    _probe = reservoir["A1"]
    _lane_length = float(getattr(_probe, "length", None) or 8.0)
    _lane_width  = float(getattr(_probe, "width",  None) or 70.0)
    LANE_AREA_MM2          = _lane_length * _lane_width
    LANE_UNUSABLE_RESERVE  = (2.0 + 1.0) * LANE_AREA_MM2   # safety + min_height

    n_plates = len(plates)

    diluent_need_per_plate_ul = 11 * 8 * DILUENT_UL          # 11 cols * 8 rows
    diluent_total_need_ul     = diluent_need_per_plate_ul * n_plates

    # Iteratively pick the smallest lane count whose per-lane pour
    # (need_share + per-lane reserve + buffers) still fits inside the
    # working lane capacity. Pour budget grows with lane count because
    # each extra lane adds its own unusable reserve.
    n_diluent_lanes = 1
    while True:
        pour_total = (
            diluent_total_need_ul * (1.0 + OVERHEAD_FRACTION)
            + DEAD_VOLUME_UL
            + LANE_UNUSABLE_RESERVE * n_diluent_lanes
        )
        if pour_total / n_diluent_lanes <= LANE_USABLE_UL:
            break
        n_diluent_lanes += 1
        if n_diluent_lanes > 10:
            raise RuntimeError(
                "Could not fit diluent budget within 10 lanes - bump "
                "LANE_USABLE_UL or check the cross-section calculation."
            )
    diluent_pour_ul  = pour_total
    diluent_per_lane = diluent_pour_ul / n_diluent_lanes

    # One lane per colour. Pour budget = need + 3% overhead + dead-volume
    # + lane reserve, with a hard 5 mL floor (booth-spec minimum) so the
    # lane stays comfortably full for the entire 8 x 150 uL stock load.
    stock_need_per_colour_ul = 8 * STOCK_UL                  # 8 wells * 150 uL
    stock_pour_ul            = max(
        5_000.0,
        stock_need_per_colour_ul * (1.0 + OVERHEAD_FRACTION)
        + DEAD_VOLUME_UL
        + LANE_UNUSABLE_RESERVE,
    )

    DILUENT_LANE_NAMES = ["A4", "A5", "A6", "A7"][:n_diluent_lanes]
    WASH_LANE_NAME     = "A6" if n_diluent_lanes <= 2 else "A12"
    # Make sure wash lane never collides with diluent lanes
    while WASH_LANE_NAME in DILUENT_LANE_NAMES:
        WASH_LANE_NAME = "A" + str(int(WASH_LANE_NAME[1:]) + 1)

    # -----------------------------------------------------------------------
    # Liquid definitions (Liquid Setup screen in the app)
    # -----------------------------------------------------------------------
    red_dye    = protocol.define_liquid(
        "Red Dye",    "1:5 diluted red food colouring",    "#e60026"
    )
    yellow_dye = protocol.define_liquid(
        "Yellow Dye", "1:5 diluted yellow food colouring", "#ffd400"
    )
    blue_dye   = protocol.define_liquid(
        "Blue Dye",   "1:5 diluted blue food colouring",   "#0066cc"
    )
    diluent    = protocol.define_liquid(
        "Diluent Water",  "Distilled water, serial-dilution buffer", "#bfe6ff"
    )
    wash_water = protocol.define_liquid(
        "Wash Water",     "Distilled water, multi-channel tip wash", "#cccccc"
    )

    reservoir["A1"].load_liquid(red_dye,    stock_pour_ul)
    reservoir["A2"].load_liquid(yellow_dye, stock_pour_ul)
    reservoir["A3"].load_liquid(blue_dye,   stock_pour_ul)
    for lane in DILUENT_LANE_NAMES:
        reservoir[lane].load_liquid(diluent, diluent_per_lane)
    reservoir[WASH_LANE_NAME].load_liquid(wash_water, LANE_USABLE_UL)

    # -----------------------------------------------------------------------
    # Pre-flight comment block (printed to the app's run log)
    # -----------------------------------------------------------------------
    protocol.comment("=== Reservoir sourcing plan (NEST 12-channel, slot C1) ===")
    protocol.comment(
        f"  A1 Red dye   : pour ~{stock_pour_ul / 1000:.2f} mL "
        f"(need {stock_need_per_colour_ul / 1000:.2f} mL + buffer)"
    )
    protocol.comment(
        f"  A2 Yellow dye: pour ~{stock_pour_ul / 1000:.2f} mL"
    )
    protocol.comment(
        f"  A3 Blue dye  : pour ~{stock_pour_ul / 1000:.2f} mL"
    )
    protocol.comment(
        f"  {DILUENT_LANE_NAMES} Diluent: pour ~{diluent_per_lane / 1000:.2f} mL "
        f"each ({n_diluent_lanes} lane(s); need "
        f"{diluent_total_need_ul / 1000:.2f} mL total + buffer)"
    )
    protocol.comment(
        f"  {WASH_LANE_NAME} Wash    : pour ~{LANE_USABLE_UL / 1000:.0f} mL "
        "(no draws, in-place mix only)"
    )

    # -----------------------------------------------------------------------
    # Liquid trackers
    # -----------------------------------------------------------------------
    colour_trackers = {
        "red":    LaneTracker(stock_pour_ul / 1000, reservoir["A1"]),
        "yellow": LaneTracker(stock_pour_ul / 1000, reservoir["A2"]),
        "blue":   LaneTracker(stock_pour_ul / 1000, reservoir["A3"]),
    }
    diluent_trackers = [
        LaneTracker(diluent_per_lane / 1000, reservoir[lane])
        for lane in DILUENT_LANE_NAMES
    ]
    diluent_idx = [0]   # index of current diluent lane

    def aspirate_diluent(vol_ul):
        """Returns (well, Z target mm) for the next diluent aspirate.
        Auto-rotates to the next lane when can_supply() returns False
        (i.e. before the tip would rise above the liquid surface)."""
        while diluent_idx[0] < len(diluent_trackers):
            t = diluent_trackers[diluent_idx[0]]
            if t.can_supply(vol_ul):
                return t.well, t.aspirate_height(vol_ul)
            diluent_idx[0] += 1
        raise RuntimeError(
            "Diluent exhausted across all "
            f"{len(diluent_trackers)} lane(s). Refill "
            f"{DILUENT_LANE_NAMES} or bump the planning buffer."
        )

    # Destination-well tracker (every well of every plate)
    well_trackers = {}
    for plate in plates:
        for well in plate.wells():
            well_trackers[well] = WellTracker(well)

    # -----------------------------------------------------------------------
    # Wash helper (mix(4, 250) in place, no net consumption)
    # -----------------------------------------------------------------------
    wash_well = reservoir[WASH_LANE_NAME]

    def wash_tip(pipette):
        # In-place wash. 8-channel still does mix(4, 250) - the wash
        # lane is a wide trough so all 8 channels reach into the same lane.
        pipette.move_to(wash_well.bottom(z=2))
        pipette.mix(4, WASH_MIX_UL, wash_well.bottom(z=2))
        pipette.blow_out(wash_well.top(z=-2))

    # -----------------------------------------------------------------------
    # Per-(plate, colour) workflow
    # -----------------------------------------------------------------------
    def run_one_plate(plate, colour_name, single_tip_index, multi_tip_col_index):
        """Diluent fill + stock fill + tip wash & return + 1:2 serial
        dilution + multi-tip wash & return. Tips are NEVER trashed."""
        colour_tracker = colour_trackers[colour_name]
        single_tip_well = tips_1000.wells()[single_tip_index]
        multi_tip_top   = tips_1000.wells()[multi_tip_col_index * 8]
        # (8-channel pipette picks a whole column starting at the top
        #  well of the chosen tip-rack column; column index 1 = wells[8])

        protocol.comment(
            f"\n=== Plate {plate.parent}: {colour_name} | "
            f"single-tip wells[{single_tip_index}], "
            f"multi-tip column {multi_tip_col_index} ==="
        )

        # ----- 1. 1-channel: diluent into every well of cols 2..12 -----
        flex_s.pick_up_tip(single_tip_well)
        protocol.comment(f"  Loading {DILUENT_UL} uL diluent into 88 wells (cols 2-12)")
        for i in range(8, 96):  # wells 8..95 in column-major order = cols 2..12
            dst_well   = plate.wells()[i]
            src_well, src_z = aspirate_diluent(DILUENT_UL)
            trailed_aspirate(flex_s, DILUENT_UL, src_well.bottom(src_z))
            trailed_dispense(flex_s, DILUENT_UL, dst_well.top(z=-5))
            lift_z = well_trackers[dst_well].add(DILUENT_UL)
            flex_s.move_to(dst_well.bottom(z=lift_z))

        # ----- 2. 1-channel: stock into every well of col 1 -----
        protocol.comment(f"  Loading {STOCK_UL} uL {colour_name} stock into col 1 (8 wells)")
        for i in range(8):
            dst_well = plate.wells()[i]
            src_z    = colour_tracker.aspirate_height(STOCK_UL)
            trailed_aspirate(flex_s, STOCK_UL, colour_tracker.well.bottom(src_z))
            trailed_dispense(flex_s, STOCK_UL, dst_well.top(z=-5))
            lift_z   = well_trackers[dst_well].add(STOCK_UL)
            flex_s.move_to(dst_well.bottom(z=lift_z))

        # ----- 3. Wash the 1-channel tip, RETURN it (never drop) -----
        protocol.comment("  Washing 1-channel tip + returning to rack")
        wash_tip(flex_s)
        flex_s.return_tip()

        # ----- 4. 8-channel: 1:2 serial dilution cols 1 -> 12 -----
        protocol.comment(
            f"  8-channel serial dilution: {XFER_UL} uL transfer "
            f"+ mix({MIX_REPS}, {MIX_UL}) across 11 column transfers"
        )
        flex_m.pick_up_tip(multi_tip_top)
        temp_well = 0   # index of column-1 top (A1)
        for _ in range(11):
            src_well = plate.wells()[temp_well]
            temp_well += 8
            dst_well = plate.wells()[temp_well]
            trailed_aspirate(flex_m, XFER_UL, src_well.bottom(z=2))
            trailed_dispense(flex_m, XFER_UL, dst_well.top(z=-5))
            flex_m.mix(MIX_REPS, MIX_UL, dst_well.bottom(z=2))
            # Update trackers for all 8 destination wells in this column.
            # The lift-off height uses the A-row well as the reference;
            # all 8 wells in the column receive ~equal volume.
            for ch in range(8):
                well_trackers[plate.wells()[temp_well + ch]].add(XFER_UL)
            lift_z = well_trackers[dst_well].surface_height_mm() + 1.0
            flex_m.move_to(dst_well.bottom(z=lift_z))

        # ----- 5. Wash the 8-channel tip column, RETURN it -----
        protocol.comment("  Washing 8-channel tips + returning to rack")
        wash_tip(flex_m)
        flex_m.return_tip()

    # -----------------------------------------------------------------------
    # Run order
    # -----------------------------------------------------------------------
    protocol.home()
    protocol.set_rail_lights(True)

    run_one_plate(target_plate_1, "red",    single_tip_index=0, multi_tip_col_index=1)
    run_one_plate(target_plate_2, "yellow", single_tip_index=1, multi_tip_col_index=2)
    run_one_plate(target_plate_3, "blue",   single_tip_index=2, multi_tip_col_index=3)

    # -----------------------------------------------------------------------
    # End-of-run usage report
    # -----------------------------------------------------------------------
    protocol.comment("\n=== End-of-run reservoir usage (uL remaining per lane) ===")
    for name in ("red", "yellow", "blue"):
        t = colour_trackers[name]
        protocol.comment(
            f"  {name:>6} ({t.well}): {t.current_volume_ul:7.0f} uL left "
            f"({t.current_volume_ul / 1000:.2f} mL)"
        )
    for lane_name, t in zip(DILUENT_LANE_NAMES, diluent_trackers):
        protocol.comment(
            f"  diluent ({lane_name}): {t.current_volume_ul:7.0f} uL left "
            f"({t.current_volume_ul / 1000:.2f} mL)"
        )
    protocol.comment(
        f"  wash    ({WASH_LANE_NAME}): in-place mixing only, no consumption"
    )
    protocol.comment(
        "Protocol complete. All tips returned to the rack (none discarded)."
    )
