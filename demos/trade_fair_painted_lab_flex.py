"""
Opentrons Flex Trade Fair Demo  -  "Painted Lab"
======================================

Autonomous ~2-hour Flex demo that turns six 96-well plates into six
visually distinct mini-experiments. Built around the same proven
volume math as our internal RGYB serial-dilution protocol
(150 uL stock / 75 uL diluent / 75 uL transfer / 4x mix(75)) but with
a different choreography per plate so the booth never shows the same
movement twice in a row.

Plates (in run order):
  1. **Standard Curves**         - four horizontal 1:2 serial-dilution
                                    gradients on one plate (real-lab
                                    standard-curve prep, 4 colours).
  2. **Synergy Matrix**          - 2D dose-response heat-map: red
                                    titrated across the columns, blue
                                    titrated down the rows, yellow
                                    viability indicator in the
                                    experimental zone (Bliss/Loewe
                                    checkerboard layout).
  3. **Multiplex Plate Map**     - four solid-colour column blocks
                                    (red, yellow, blue, green=Y+B),
                                    the way a multiplex assay or
                                    compound library is laid out
                                    before adding samples.
  4. **ELISA Plate Layout**      - cols 1-2 standard curve in red
                                    (vertical 1:2 dilution), cols 3-10
                                    "patient samples" with varying
                                    intensities, col 11 positive
                                    control (yellow), col 12 NTC
                                    blank.
  5. **Mixed-Colour Bouquet**    - four mixed-colour row pairs
                                    (orange=R+Y, green=Y+B,
                                    purple=R+B, brown=R+Y+B) each
                                    serial-diluted across the plate.
  6. **Concentric Rainbow Rings**- single-channel finale: four nested
                                    rings of pure colour radiating
                                    inward (red, yellow, green, blue)
                                    - the "showpiece" plate.

Pipettes (no modules used):
  - left  : Flex 1-Channel 1000 uL  -> sample loading, controls, painting
  - right : Flex 8-Channel 1000 uL  -> bulk fills, serial dilution

Tip strategy (real-lab practice):
  Single-channel rack is sectioned by reagent so a tip never sees more
  than one colour:
      cols 1-3  -> red tips
      cols 4-6  -> yellow tips
      cols 7-9  -> blue tips
      cols 10-12-> wash/water tips
  Tips are NEVER dropped to the trash. After every use the pipette
  mixes 4 x 250 uL in the wash lane (mix(4, 250) + blow_out) and the
  tip is returned to its rack position with pipette.return_tip(). The
  wash water in the dedicated wash lane absorbs trace dye over the
  run; nothing is ever drawn from that lane so contamination stays
  contained there.

Liquids are registered with protocol.define_liquid() and assigned to
their starting wells with well.load_liquid(), so the Opentrons app
shows the booth crew exactly what to load and where during setup.

==============================================================================
MATERIALS  (everything you need at the booth)
==============================================================================

Hardware (already on the robot):
  * Opentrons Flex
  * Flex 8-Channel 1000 uL pipette  (right mount)
  * Flex 1-Channel 1000 uL pipette  (left mount)

Labware (load names are the exact strings the Flex will look up):
  * 6 x thermofisher_96_wellplate_250ul   (custom labware - the 250 uL
        ThermoFisher 96-well plate your robot already has uploaded; same
        load name the internal RGYB serial-dilution protocol uses.
        Slots C1, C2, C3, D1, D2, D3.)
  * 1 x nest_12_reservoir_15ml            (slot B1: dyes + diluent + wash)
  * 3 x opentrons_flex_96_tiprack_1000ul        (slots A1, A2, B2)
  * slot B3 is left empty (movable trash bin lives at A3)

Consumables to prepare before starting:
  At run start the protocol prints a pre-flight comment block in the
  app's run log telling the booth crew EXACTLY how much to pour into
  which lane. The plan is computed inline from ESTIMATED_DRAW_UL plus
  light planning buffers (3% overhead + 0.5 mL dead volume) and auto-
  spreads each reagent across as many 12-mL lanes as needed.

  The default worst-case layout (with current ESTIMATED_DRAW_UL values)
  is approximately:

    A1     : Red Dye   (1:5 in water)         ~11.8 mL
    A2     : Yellow Dye (1:5 in water)        ~ 9.8 mL
    A3, A4 : Blue Dye  (1:5 in water)         ~12.9 mL total (2 lanes)
    A5, A6 : Diluent Water                    ~23.2 mL total (2 lanes)
    A12    : Wash Water (multi-channel tip rinse) ~12 mL

  Total water needed: ~50 mL distilled. Everything lives in the single
  12-channel reservoir - no 50 mL Falcon tubes or bulk reservoirs.

  Always confirm the pre-flight comments before pouring; the actual lane
  assignment may shift if ESTIMATED_DRAW_UL is tuned.

Optional but recommended for booth impact:
  * A white sheet or LED light pad under the Flex deck. The plates light
    up beautifully and gradients read from across the room.
  * A printed placard explaining what visitors are seeing.

No 15 mL or 50 mL Falcon tube adapter is required - the protocol does
not use tubes anywhere.

==============================================================================
SETUP INSTRUCTIONS  (in the order the Opentrons app will walk you through)
==============================================================================

  1. Mount the Flex 1-Channel 1000 uL on the LEFT mount and the
     Flex 8-Channel 1000 uL on the RIGHT mount.
  2. Calibrate the deck and pipettes if the app prompts you.
  3. Load the three opentrons_flex_96_tiprack_1000ul racks into slots A1, A2, B2.
       slot A1 = single-channel tips (will be sectioned by colour - just
                 a full rack of tips; the protocol manages which tips
                 it picks for which dye)
       slots A2 & B2 = multi-channel tip reservoirs (full racks)
  4. Load the NEST 12-channel reservoir (nest_12_reservoir_15ml) into
     slot B1. Slot B3 stays empty.
  5. **Read the run-log pre-flight comments** that the protocol prints
     at run start: each will look like
       "  red:    est. draw 11.00 mL -> total pour 11.83 mL across ['A1']..."
     The Opentrons app's Liquid Setup screen reflects the same plan,
     with a coloured swatch per assigned lane and the matching planned
     volume. Pour exactly what each comment line asks for.
  6. Load 6 empty thermofisher_96_wellplate_250ul plates into slots
     C1, C2, C3, D1, D2 and D3. (This is the custom labware definition you
     have uploaded to the Flex; the app will recognise the load name.)
  7. (Optional) Tune the two runtime parameters in the app:
       * Per-plate viewing delay   - default 60 s
       * Per-plate incubation delay- default 180 s
     Increase both to lengthen the show; decrease to compress.
  8. Hit "Start run" - total runtime is ~2 hours.
"""

import math
import time

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair - Painted Lab (Flex)",
    "author": "Opentrons Demo",
    "description": (
        "Six 96-well plates, six lab-style colour workflows. Built on the "
        "proven 150/75/75 uL serial-dilution math but with distinct "
        "choreography per plate. Liquids are registered for app setup."
    ),
}

# 2.18+ is required for runtime parameters (add_parameters / protocol.params).
# define_liquid() and load_liquid() are available from 2.14+, so 2.18 covers both.

requirements = {"robotType": "Flex",  "apiLevel": "2.18"}


# ---------------------------------------------------------------------------
# Pre-flight booth pause (opt-in)
# ---------------------------------------------------------------------------
# When True, the protocol calls protocol.pause() right after the pre-flight
# comment block so the booth crew can double-check the lane fills against
# the printed plan before the run actually starts. Press "Resume" in the
# Opentrons app to continue. Default OFF so unattended booth runs work.
PRE_FLIGHT_PAUSE = False
PRE_FLIGHT_PAUSE_MSG = (
    "Verify each reservoir lane is poured to the planned volume above, "
    "then press Resume to start the run."
)
# ---------------------------------------------------------------------------
# Test instrumentation
# ---------------------------------------------------------------------------
# When TRAILING_TEST_ENABLED is True, every call routed through
# trailed_aspirate() / trailed_dispense() is split into:
#       1) main step at (vol - pipette.min_volume) at the requested location
#       2) protocol.delay(seconds=TRAILING_DELAY_S)
#       3) tail step at pipette.min_volume          at the same location
# The tail volume is always the pipette's hardware minimum (Flex 1k = 5 uL,
# OT-2 P300 GEN2 = 20 uL, etc.) so the visualizer reliably renders the tip
# height after the larger main draw. Net volume per step is unchanged.
TRAILING_TEST_ENABLED = True
TRAILING_DELAY_S      = 0.5



# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# NEST 12-channel reservoir layout.
# Reagent lanes are assigned at run time, based on each reagent's estimated
# total draw across the demo. A12 stays reserved for the multi-channel
# tip-wash bath (no draws, nothing read out of it).
ASSIGNABLE_LANES = [f"A{i}" for i in range(1, 12)]   # A1..A11
WASH_LANE        = "A12"

# Safe usable volume per 12-channel reservoir lane. The NEST spec is 15 mL;
# 12 mL leaves a small headroom so the multi-channel never pulls air.
WORKING_LANE_CAPACITY_UL = 12_000

# Planning buffers applied on top of each reagent's worst-case draw, so we
# always pour slightly more than the protocol expects to use.
OVERHEAD_FRACTION          = 0.03    # 3% overhead on the estimated draw
DEAD_VOLUME_PER_REAGENT_UL = 500     # 0.5 mL dead volume per reagent

# Worst-case total drawn per reagent across all six plates (uL). These are
# eyeballed sums of every aspirate_from_sources() call in the workflows below
# (multi-channel calls count 8x). Re-derive whenever a workflow's per-well
# volumes change.
ESTIMATED_DRAW_UL = {
    "red":    11_000,
    "yellow":  9_000,
    "blue":   12_000,
    "water":  22_000,
}

# Single-channel tip-rack sections (1-indexed column ranges, inclusive).
TIP_SECTIONS = {
    "red":    (1, 3),
    "yellow": (4, 6),
    "blue":   (7, 9),
    "wash":   (10, 12),
}


# P300 lower limit; any computed volume below this is skipped.
MIN_DISPENSE_UL = 20

# Plate geometry. thermofisher_96_wellplate_250ul is the custom 250 uL
# 96-well labware definition uploaded to the Flex (same load name the
# lab's internal RGYB serial-dilution protocol uses).
PLATE_LOAD_NAME = "thermofisher_96_wellplate_250ul"
N_ROWS, N_COLS  = 8, 12

# Proven serial-dilution volume math (from the lab's internal protocol).
STOCK_UL    = 150
DILUENT_UL  = 75
XFER_UL     = 75
MIX_UL      = 75
MIX_REPS    = 4

# Sub-stock volumes for two- and three-colour mixes (so stock col 1 still
# ends up at 150 uL total, matching the proven dilution math).
HALF_STOCK_UL  = STOCK_UL // 2   # 75 uL for two-colour mixes (75 + 75 = 150)
THIRD_STOCK_UL = STOCK_UL // 3   # 50 uL for three-colour mixes (50*3 = 150)


# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------

PLATE_PARAM_NAMES = [
    "run_plate_1_curves",
    "run_plate_2_synergy",
    "run_plate_3_multiplex",
    "run_plate_4_elisa",
    "run_plate_5_bouquet",
    "run_plate_6_rings",
]
PLATE_PARAM_LABELS = [
    "Plate 1 - Standard Curves",
    "Plate 2 - Synergy Matrix",
    "Plate 3 - Multiplex Blocks",
    "Plate 4 - ELISA Layout",
    "Plate 5 - Mixed Bouquet",
    "Plate 6 - Concentric Rings",
]

def add_parameters(parameters):
    parameters.add_int(
        variable_name="viewing_delay_s",
        display_name="Per-plate viewing delay",
        description="Pause after each finished plate. Increase to extend the demo runtime.",
        default=60,
        minimum=0,
        maximum=600,
        unit="s",
    )
    parameters.add_int(
        variable_name="incubation_delay_s",
        display_name="Per-plate incubation delay",
        description="Per-plate pause that mimics an assay incubation (e.g. standard-curve settling).",
        default=180,
        minimum=0,
        maximum=900,
        unit="s",
    )
    for name, label in zip(PLATE_PARAM_NAMES, PLATE_PARAM_LABELS):
        parameters.add_bool(
            variable_name=name,
            display_name=label,
            description=f"Set to OFF to skip {label.lower()} this run.",
            default=True,
        )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

def run(protocol: protocol_api.ProtocolContext):


    # ---------------- test-instrumentation wrappers ----------------
    # See module-level TRAILING_TEST_ENABLED to disable.
    # Always splits the call into (main + delay + tail), where the tail is
    # exactly pipette.min_volume - the smallest hardware-legal volume the
    # pipette can deliver. The visualizer renders the tip height after the
    # main draw during the delay. Net volume per step = vol_ul.
    def trailed_aspirate(pipette, vol_ul, location):
        if not TRAILING_TEST_ENABLED:
            pipette.aspirate(vol_ul, location)
            return
        eps = float(pipette.min_volume)
        pipette.aspirate(vol_ul - eps, location)
        protocol.delay(seconds=TRAILING_DELAY_S)
        pipette.aspirate(eps,           location)

    def trailed_dispense(pipette, vol_ul, location):
        if not TRAILING_TEST_ENABLED:
            pipette.dispense(vol_ul, location)
            return
        eps = float(pipette.min_volume)
        pipette.dispense(vol_ul - eps, location)
        protocol.delay(seconds=TRAILING_DELAY_S)
        pipette.dispense(eps,           location)

    viewing_delay_s    = protocol.params.viewing_delay_s
    incubation_delay_s = protocol.params.incubation_delay_s

    # =====================================================================
    # Liquid definitions (shown in the app's Liquid Setup screen)
    # =====================================================================
    red_dye = protocol.define_liquid(
        name="Red Dye",
        description=(
            "Red food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A1 before starting."
        ),
        display_color="#e60026",
    )
    yellow_dye = protocol.define_liquid(
        name="Yellow Dye",
        description=(
            "Yellow food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A2 before starting."
        ),
        display_color="#ffd400",
    )
    blue_dye = protocol.define_liquid(
        name="Blue Dye",
        description=(
            "Blue food colouring diluted 1:5 in distilled water. "
            "Pour ~12 mL into reservoir lane A3 before starting."
        ),
        display_color="#0066cc",
    )
    diluent_water = protocol.define_liquid(
        name="Diluent Water",
        description=(
            "Distilled water. Serial-dilution buffer. Pour ~12 mL into "
            "EACH of lanes A4, A5, A6 (the protocol auto-rotates lanes "
            "as they empty)."
        ),
        display_color="#bfe6ff",
    )
    wash_water = protocol.define_liquid(
        name="Wash Water",
        description=(
            "Distilled water for multi-channel tip rinsing between "
            "colours. Pour ~12 mL into lane A12. Stays in place for the "
            "whole run."
        ),
        display_color="#cccccc",
    )

    # =====================================================================
    # Labware
    # =====================================================================
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "B1")

    plates = [
        protocol.load_labware(PLATE_LOAD_NAME, slot, f"plate {i + 1}")
        for i, slot in enumerate(["C1", "C2", "C3", "D1", "D2", "D3"])
    ]

    rack_single  = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "A1", "single tips")
    rack_multi_a = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "A2", "multi tips A")
    rack_multi_b = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "B2", "multi tips B")
    # Flex requires an explicit movable trash bin.
    protocol.load_trash_bin("A3")

    # =====================================================================
    # Sourcing plan + Liquid Setup annotations
    # =====================================================================
    # Same idea as the NCBL v13 pre-flight loop: assign reservoir lanes to
    # each reagent based on its estimated worst-case draw plus a light
    # overhead + dead-volume buffer, fill each lane up to working capacity,
    # park any remainder in the next lane.
    plan = {}
    cursor = 0
    for reagent in ("red", "yellow", "blue", "water"):
        estimated   = float(ESTIMATED_DRAW_UL[reagent])
        with_buffer = estimated * (1.0 + OVERHEAD_FRACTION) + DEAD_VOLUME_PER_REAGENT_UL
        n_lanes     = max(1, math.ceil(with_buffer / WORKING_LANE_CAPACITY_UL))

        if cursor + n_lanes > len(ASSIGNABLE_LANES):
            raise RuntimeError(
                f"Sourcing plan: not enough free lanes for '{reagent}'. "
                f"Needs {n_lanes} lane(s); only "
                f"{len(ASSIGNABLE_LANES) - cursor} remain in {ASSIGNABLE_LANES}."
            )
        lanes = ASSIGNABLE_LANES[cursor:cursor + n_lanes]
        cursor += n_lanes

        starts, remaining = [], with_buffer
        for _ in lanes:
            fill = min(remaining, float(WORKING_LANE_CAPACITY_UL))
            starts.append(fill)
            remaining -= fill

        plan[reagent] = {
            "lanes": lanes,
            "planned_start_per_lane": starts,
            "estimated_draw_ul": estimated,
            "with_buffer_ul": with_buffer,
        }
    plan["_wash"] = {"lane": WASH_LANE}

    liquid_objects = {
        "red":    red_dye,
        "yellow": yellow_dye,
        "blue":   blue_dye,
        "water":  diluent_water,
    }

    # Tell the app where each reagent starts and how much to pour. The app
    # draws a coloured swatch on each annotated lane.
    for reagent in ("red", "yellow", "blue", "water"):
        for lane, start_ul in zip(plan[reagent]["lanes"],
                                  plan[reagent]["planned_start_per_lane"]):
            reservoir[lane].load_liquid(liquid_objects[reagent], start_ul)
    reservoir[plan["_wash"]["lane"]].load_liquid(wash_water, WORKING_LANE_CAPACITY_UL)

    # =====================================================================
    # Pipettes
    # =====================================================================
    flex_s = protocol.load_instrument("flex_1channel_1000", "left",
                                     tip_racks=[rack_single])
    flex_m = protocol.load_instrument("flex_8channel_1000",  "right",
                                     tip_racks=[rack_multi_a, rack_multi_b])

    flex_s.flow_rate.aspirate = 100
    flex_s.flow_rate.dispense = 200
    flex_m.flow_rate.aspirate = 100
    flex_m.flow_rate.dispense = 200

    # =====================================================================
    # Source tracking + within-aspirate lane splitting
    # =====================================================================
    # Per-lane remaining-volume tracker. Ported from the NCBL v13 protocol's
    # reservoir_remaining_ul + aspirate_from_sources() pattern: an aspirate
    # call can span multiple lanes, taking what's left in the current lane
    # and continuing the *same* aspirate from the next one. Multi-channel
    # draws are tracked at 8x consumption (one lane fills all 8 channels in
    # parallel for that vol_per_channel).
    remaining_ul = {}
    for reagent in ("red", "yellow", "blue", "water"):
        for lane, start in zip(plan[reagent]["lanes"],
                               plan[reagent]["planned_start_per_lane"]):
            remaining_ul[lane] = float(start)
    current_lane_idx = {r: 0 for r in ("red", "yellow", "blue", "water")}

    # Cache the per-lane cross-section so tip-height math is one multiply.
    # NEST 12-channel lanes are rectangular troughs; well.length x well.width.
    lane_area_mm2: dict = {}
    for lane in list(remaining_ul.keys()) + [plan["_wash"]["lane"]]:
        well = reservoir[lane]
        length = float(getattr(well, "length", None) or 8.0)
        width  = float(getattr(well, "width",  None) or 70.0)
        lane_area_mm2[lane] = length * width

    # Constants for the aspirate-Z calc. The tip sits ASPIRATE_SAFETY_MM
    # below the post-aspirate meniscus, never closer than ASPIRATE_MIN_Z_MM
    # to the floor (so a small overshoot does not crash the tip).
    ASPIRATE_SAFETY_MM = 1.5
    ASPIRATE_MIN_Z_MM  = 1.0

    def lane_aspirate_z(lane: str, vol_ul_to_draw: float) -> float:
        """Return the tip Z target (mm above lane floor) for an upcoming
        aspirate of `vol_ul_to_draw` total uL from `lane`. Does not
        decrement the tracker - the caller updates remaining_ul[]
        after the actual pipette.aspirate succeeds."""
        post_volume_ul = max(0.0, remaining_ul[lane] - vol_ul_to_draw)
        post_surface_mm = post_volume_ul / lane_area_mm2[lane]
        return max(ASPIRATE_MIN_Z_MM, post_surface_mm - ASPIRATE_SAFETY_MM)

    def _advance_lane(reagent: str) -> None:
        current_lane_idx[reagent] += 1

    def _current_lane(reagent: str):
        lanes = plan[reagent]["lanes"]
        if current_lane_idx[reagent] >= len(lanes):
            return None
        return lanes[current_lane_idx[reagent]]

    def aspirate_from_sources(pipette, vol_per_channel_ul: float,
                              reagent: str, channels: int = 1) -> None:
        """Aspirate `vol_per_channel_ul` per channel from `reagent`'s
        assigned lane(s), splitting the call across lanes if the current
        lane runs low mid-aspirate. Updates `remaining_ul` using the
        8x-consumption model for multi-channel calls (channels=8).

        Safe-split guard: a within-call split is only taken if BOTH the
        portion drawn from this lane and the remainder still to be drawn
        from the next lane will be >= 2 x pipette.min_volume (so each
        portion is itself splittable by the trailed wrapper). If the
        current lane can't satisfy that, we abandon what is left in it
        and advance - the lane reserves at the bottom are budgeted into
        the per-lane planning math, so this is just dead volume."""
        # 2x because the trailed wrapper itself further splits each
        # aspirate into (step - min) + min, and both halves must be
        # >= pipette.min_volume.
        min_splittable_per_channel = 2.0 * float(pipette.min_volume)

        remaining_per_channel = float(vol_per_channel_ul)
        while remaining_per_channel > 0:
            lane = _current_lane(reagent)
            if lane is None:
                raise RuntimeError(
                    f"'{reagent}' exhausted across {plan[reagent]['lanes']}; "
                    f"need {remaining_per_channel:.1f} uL/channel more. "
                    "Refill the assigned lane(s) or bump ESTIMATED_DRAW_UL."
                )
            available_total = remaining_ul.get(lane, 0.0)
            available_per_channel = available_total / channels

            # Case 1: this lane satisfies the entire remaining call. Take
            # the whole thing and we're done.
            if available_per_channel >= remaining_per_channel:
                total_drawn = remaining_per_channel * channels
                z = lane_aspirate_z(lane, total_drawn)
                trailed_aspirate(
                    pipette, remaining_per_channel, reservoir[lane].bottom(z)
                )
                remaining_ul[lane] = max(0.0, available_total - total_drawn)
                remaining_per_channel = 0.0
                continue

            # Case 2: lane can't cover the rest. To safely split, BOTH
            # halves (what we take here, and what we still owe) must be
            # >= min_splittable_per_channel.
            leftover_after_this_lane = remaining_per_channel - available_per_channel
            if (available_per_channel < min_splittable_per_channel
                    or leftover_after_this_lane < min_splittable_per_channel):
                # Splitting would create a sub-min portion. Abandon what's
                # left in this lane (it stays as dead volume) and advance.
                _advance_lane(reagent)
                continue

            # Safe split: take everything this lane can give.
            z = lane_aspirate_z(lane, available_total)
            trailed_aspirate(
                pipette, available_per_channel, reservoir[lane].bottom(z)
            )
            remaining_ul[lane] = 0.0
            remaining_per_channel = leftover_after_this_lane
            _advance_lane(reagent)

    def dispense_and_lift(pipette, vol_ul: int, well, lift_z: int = -2):
        # Proven touch-off-without-touch-tip: dispense above the surface
        # (well.top(z=-5)), then hover at top(z=lift_z) so any hanging
        # droplet drops into the well instead of being dragged.
        trailed_dispense(pipette, vol_ul, well.top(z=-5))
        pipette.move_to(well.top(z=lift_z))

    # =====================================================================
    # Tip helpers (sectioned single-channel + multi-channel wash & reuse)
    # =====================================================================
    def section_wells(start_col, end_col):
        return [f"{row}{col}"
                for col in range(start_col, end_col + 1)
                for row in "ABCDEFGH"]

    tip_pools = {color: section_wells(s, e) for color, (s, e) in TIP_SECTIONS.items()}
    tip_index = {color: 0 for color in tip_pools}

    def pick_single_tip(color: str) -> None:
        if tip_index[color] >= len(tip_pools[color]):
            raise RuntimeError(
                f"Out of {color} tips - section exhausted "
                f"({tip_index[color]}/{len(tip_pools[color])})."
            )
        well_name = tip_pools[color][tip_index[color]]
        tip_index[color] += 1
        flex_s.pick_up_tip(rack_single.wells_by_name()[well_name])

    multi_columns = []
    for rack in (rack_multi_a, rack_multi_b):
        for col in range(12):
            multi_columns.append(rack.columns()[col][0])
    multi_idx = {"next": 0}

    def multi_pick_fresh():
        if multi_idx["next"] >= len(multi_columns):
            raise RuntimeError("Out of multi-channel tip columns.")
        target = multi_columns[multi_idx["next"]]
        multi_idx["next"] += 1
        flex_m.pick_up_tip(target)

    def _wash_well():
        return reservoir[plan["_wash"]["lane"]]

    def multi_wash():
        # mix(4, 250) is the proven internal-protocol wash pattern. Wash
        # water lives in the dedicated wash lane (plan["_wash"]["lane"]) -
        # it slowly picks up trace dye over the run, but nothing is ever
        # drawn from it, so contamination stays inside that one lane.
        wash_well = _wash_well()
        flex_m.mix(4, 250, wash_well.bottom(2))
        flex_m.blow_out(wash_well.top(-3))

    def single_wash():
        # Same idea as multi_wash, scaled to the single-channel pipette.
        wash_well = _wash_well()
        flex_s.mix(4, 250, wash_well.bottom(2))
        flex_s.blow_out(wash_well.top(-3))

    def finish_multi():
        # Always wash + return - booth-wide rule: tips are NEVER trashed.
        multi_wash()
        flex_m.return_tip()

    def single_finish(wash: bool = True):
        # Always return; wash if the tip touched concentrated reagent
        # (pass wash=False for tips that only ever saw plain water).
        if wash:
            single_wash()
        flex_s.return_tip()

    # =====================================================================
    # Common building blocks
    # =====================================================================
    def multi_prefill_diluent(plate, first_col: int, last_col_exclusive: int,
                              vol_per_col: int):
        """Multi-channel: pre-load `vol_per_col` of water into each
        column in [first_col, last_col_exclusive). All 8 rows of each
        column fill in one shot."""
        multi_pick_fresh()
        for col in range(first_col, last_col_exclusive):
            aspirate_from_sources(flex_m, vol_per_col, "water", channels=8)
            dispense_and_lift(flex_m, vol_per_col, plate.columns()[col][0])
        finish_multi()

    def multi_serial_dilute(plate, first_col: int, last_col_exclusive: int):
        """Multi-channel 1:2 serial dilution across [first_col,
        last_col_exclusive). Tips are sacrificed at the end (they have
        seen every colour in the column-1 stocks)."""
        multi_pick_fresh()
        for col in range(first_col, last_col_exclusive - 1):
            src = plate.columns()[col][0].bottom(2)
            dst = plate.columns()[col + 1][0].bottom(2)
            trailed_aspirate(flex_m, XFER_UL, src)
            trailed_dispense(flex_m, XFER_UL, dst)
            flex_m.mix(MIX_REPS, MIX_UL, dst)
            flex_m.blow_out(plate.columns()[col + 1][0].top(z=-2))
        finish_multi()

    def single_dispense_color(color: str, lane: str, wells, vol_ul: int,
                              mix_after: bool = False):
        """Single-channel: pick a tip from `color`'s section, dispense
        `vol_ul` of `lane` into each well, optionally mix the last
        well, then drop the tip."""
        pick_single_tip(color)
        for w in wells:
            target = w if hasattr(w, "top") else plate_lookup(w)
            aspirate_from_sources(flex_s, vol_ul, lane)
            if mix_after and w is wells[-1]:
                trailed_dispense(flex_s, vol_ul, target.bottom(2))
                flex_s.mix(2, MIX_UL, target.bottom(2))
                flex_s.move_to(target.top(z=-2))
            else:
                dispense_and_lift(flex_s, vol_ul, target)
        single_finish()

    # tiny inline helper for the workflows below
    def plate_lookup(_):  # pragma: no cover - placeholder, never called
        raise RuntimeError("single_dispense_color was passed a non-Well")

    # =====================================================================
    # WORKFLOW 1: Standard Curves (four horizontal 1:2 dilution gradients)
    # =====================================================================
    # Real lab analog: parallel standard-curve preparation, four samples
    # done in technical-duplicate row pairs (A/B, C/D, E/F, G/H).
    def plate_standard_curves(plate, plate_idx: int):
        protocol.comment(
            f"=== Plate {plate_idx + 1} | STANDARD CURVES (4 colours) ==="
        )

        # 1) Multi-channel: water in cols 2..12.
        multi_prefill_diluent(plate, 1, N_COLS, DILUENT_UL)

        # 2) Single-channel: four stocks into column 1 (row pairs).
        col1 = {"A": plate["A1"], "B": plate["B1"], "C": plate["C1"],
                "D": plate["D1"], "E": plate["E1"], "F": plate["F1"],
                "G": plate["G1"], "H": plate["H1"]}

        # Pure-colour stocks: red A/B, yellow C/D, blue E/F.
        for tip_color, lane, wells in [
            ("red",    "red",    [col1["A"], col1["B"]]),
            ("yellow", "yellow", [col1["C"], col1["D"]]),
            ("blue",   "blue",   [col1["E"], col1["F"]]),
        ]:
            pick_single_tip(tip_color)
            for w in wells:
                aspirate_from_sources(flex_s, STOCK_UL, lane)
                dispense_and_lift(flex_s, STOCK_UL, w)
            single_finish()

        # Purple (R + B) into G/H: red half first, then blue half + mix.
        pick_single_tip("red")
        for w in (col1["G"], col1["H"]):
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "red")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("blue")
        for w in (col1["G"], col1["H"]):
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "blue")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
            flex_s.mix(2, MIX_UL, w.bottom(2))
            flex_s.move_to(w.top(z=-2))
        single_finish()

        # 3) Multi-channel: 1:2 serial dilution cols 1..11 (col 12 blank).
        multi_serial_dilute(plate, 0, N_COLS - 1)

    # =====================================================================
    # WORKFLOW 2: Synergy Matrix (2D dose-response checkerboard)
    # =====================================================================
    # Real lab analog: Bliss / Loewe drug-synergy checkerboard. Compound A
    # (red) titrated across columns; compound B (blue) titrated down rows;
    # yellow viability indicator added in the experimental zone.
    def plate_synergy_matrix(plate, plate_idx: int):
        base_ul   = 30   # assay-buffer base
        max_red   = 60   # peak at col 0
        max_blue  = 50   # peak at row H
        indicator = 20   # yellow

        protocol.comment(
            f"=== Plate {plate_idx + 1} | SYNERGY MATRIX (2D dose-response) ==="
        )

        # 1) Multi-channel: assay-buffer base in every column.
        multi_pick_fresh()
        for col in range(N_COLS):
            aspirate_from_sources(flex_m, base_ul, "water", channels=8)
            dispense_and_lift(flex_m, base_ul, plate.columns()[col][0])
        finish_multi()

        # 2) Multi-channel: red gradient across columns.
        multi_pick_fresh()
        for col in range(N_COLS):
            v = round(max_red * (N_COLS - 1 - col) / (N_COLS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            aspirate_from_sources(flex_m, v, "red", channels=8)
            dispense_and_lift(flex_m, v, plate.columns()[col][0])
        finish_multi()

        # 3) Single-channel: blue gradient down rows.
        pick_single_tip("blue")
        for r_idx, row_letter in enumerate("ABCDEFGH"):
            v = round(max_blue * r_idx / (N_ROWS - 1))
            if v < MIN_DISPENSE_UL:
                continue
            for col in range(N_COLS):
                w = plate.wells_by_name()[f"{row_letter}{col + 1}"]
                aspirate_from_sources(flex_s, v, "blue")
                dispense_and_lift(flex_s, v, w)
        single_finish()

        # 4) Single-channel: yellow indicator in the central experimental
        #    zone (skip A/H rows and 1/12 columns, the classic "edge-
        #    effect" exclusion).
        pick_single_tip("yellow")
        for r in "BCDEFG":
            for c in range(1, N_COLS - 1):
                w = plate.wells_by_name()[f"{r}{c + 1}"]
                aspirate_from_sources(flex_s, indicator, "yellow")
                dispense_and_lift(flex_s, indicator, w)
        single_finish()

    # =====================================================================
    # WORKFLOW 3: Multiplex Plate Map (four solid-colour column blocks)
    # =====================================================================
    # Real lab analog: assay-plate layout for a 4-condition multiplex or
    # a compound-library plate map. Each three-column block represents a
    # different reagent / compound family.
    def plate_multiplex_blocks(plate, plate_idx: int):
        block_ul  = 80    # primary reagent volume in each well

        protocol.comment(
            f"=== Plate {plate_idx + 1} | MULTIPLEX PLATE MAP (4 blocks) ==="
        )

        blocks = [
            ("red",     "red",    range(0, 3),  None),
            ("yellow",  "yellow", range(3, 6),  None),
            ("blue",    "blue",   range(6, 9),  None),
            ("yellow",  "yellow", range(9, 12), "blue_overlay"),  # -> green
        ]

        for tip_label, lane, cols, overlay in blocks:
            multi_pick_fresh()
            for col in cols:
                aspirate_from_sources(flex_m, block_ul, lane, channels=8)
                dispense_and_lift(flex_m, block_ul, plate.columns()[col][0])
            finish_multi()
            if overlay == "blue_overlay":
                # Y + B = green
                multi_pick_fresh()
                for col in cols:
                    aspirate_from_sources(flex_m, block_ul, "blue", channels=8)
                    dispense_and_lift(flex_m, block_ul, plate.columns()[col][0])
                finish_multi()

    # =====================================================================
    # WORKFLOW 4: ELISA Plate Layout
    # =====================================================================
    # Real lab analog: textbook ELISA plate. Cols 1-2 are duplicate
    # standard-curve points (8 standards per column, top->bottom
    # 1:2 dilution series). Cols 3-10 are "patient samples" with varying
    # intensity. Col 11 is the positive control (high yellow). Col 12
    # is the no-template / blank control.
    def plate_elisa_layout(plate, plate_idx: int):
        std_col_stock_ul   = 100   # red stock in row A of cols 1 & 2
        std_dil_ul         = 50
        std_xfer_ul        = 50
        sample_base_ul     = 60    # diluent in sample cols
        pos_ctrl_ul        = 80    # yellow in col 11
        blank_ul           = 80    # water in col 12

        protocol.comment(
            f"=== Plate {plate_idx + 1} | ELISA LAYOUT (standard+samples+ctrls) ==="
        )

        # 1) Single-channel vertical standard curves in cols 1 & 2.
        #    Diluent in rows B-H of cols 1-2 first, then stock in A1/A2,
        #    then top->bottom 1:2 dilution.
        pick_single_tip("wash")
        for col_letter in ("1", "2"):
            for row in "BCDEFGH":
                w = plate.wells_by_name()[f"{row}{col_letter}"]
                aspirate_from_sources(flex_s, std_dil_ul, "water")
                dispense_and_lift(flex_s, std_dil_ul, w)
        single_finish()

        pick_single_tip("red")
        for col_letter in ("1", "2"):
            top_well = plate.wells_by_name()[f"A{col_letter}"]
            aspirate_from_sources(flex_s, std_col_stock_ul, "red")
            dispense_and_lift(flex_s, std_col_stock_ul, top_well)
        # 1:2 vertical dilution down each std column.
        for col_letter in ("1", "2"):
            for r_idx in range(N_ROWS - 1):
                src = plate.wells_by_name()[f"{'ABCDEFGH'[r_idx]}{col_letter}"]
                dst = plate.wells_by_name()[f"{'ABCDEFGH'[r_idx + 1]}{col_letter}"]
                trailed_aspirate(flex_s, std_xfer_ul, src.bottom(2))
                trailed_dispense(flex_s, std_xfer_ul, dst.bottom(2))
                flex_s.mix(2, std_xfer_ul, dst.bottom(2))
                flex_s.move_to(dst.top(z=-2))
        single_finish()

        # 2) Multi-channel diluent base in cols 3-10 (the sample region).
        multi_pick_fresh()
        for col in range(2, 10):
            aspirate_from_sources(flex_m, sample_base_ul, "water", channels=8)
            dispense_and_lift(flex_m, sample_base_ul, plate.columns()[col][0])
        finish_multi()

        # 3) Single-channel "sample" pattern: red dye spotted at varying
        #    volumes that look like real biological variability (a few
        #    bright "positive" samples, several mid-range, some near-blank).
        sample_pattern = {  # well_name -> uL of red
            "A3":  60, "B3":  40, "C3":  25, "D3":  70, "E3":  20, "F3":  35, "G3":  25, "H3":  30,
            "A4":  35, "B4":  55, "C4":  30, "D4":  20, "E4":  40, "F4":  60, "G4":  30, "H4":  20,
            "A5":  20, "B5":  25, "C5":  50, "D5":  40, "E5":  30, "F5":  20, "G5":  40, "H5":  35,
            "A6":  45, "B6":  30, "C6":  20, "D6":  60, "E6":  35, "F6":  30, "G6":  50, "H6":  25,
            "A7":  25, "B7":  60, "C7":  40, "D7":  30, "E7":  55, "F7":  25, "G7":  30, "H7":  40,
            "A8":  30, "B8":  35, "C8":  25, "D8":  50, "E8":  20, "F8":  40, "G8":  35, "H8":  20,
            "A9":  40, "B9":  20, "C9":  60, "D9":  25, "E9":  30, "F9":  50, "G9":  20, "H9":  30,
            "A10": 25, "B10": 45, "C10": 35, "D10": 30, "E10": 25, "F10": 40, "G10": 30, "H10": 25,
        }
        pick_single_tip("red")
        for w_name, vol in sample_pattern.items():
            if vol < MIN_DISPENSE_UL:
                continue
            w = plate.wells_by_name()[w_name]
            aspirate_from_sources(flex_s, vol, "red")
            dispense_and_lift(flex_s, vol, w)
        single_finish()

        # 4) Multi-channel: positive control (yellow) in col 11.
        multi_pick_fresh()
        aspirate_from_sources(flex_m, pos_ctrl_ul, "yellow", channels=8)
        dispense_and_lift(flex_m, pos_ctrl_ul, plate.columns()[10][0])
        finish_multi()

        # 5) Multi-channel: NTC blank (water) in col 12.
        multi_pick_fresh()
        aspirate_from_sources(flex_m, blank_ul, "water", channels=8)
        dispense_and_lift(flex_m, blank_ul, plate.columns()[11][0])
        finish_multi()

    # =====================================================================
    # WORKFLOW 5: Mixed-Colour Bouquet (four mixed-colour row-pair curves)
    # =====================================================================
    # Real lab analog: parallel standard curves of mixed-reagent samples
    # (e.g. comparing two-component formulations). Each row pair is a
    # different secondary colour formed by mixing two or three primaries
    # in column 1, then 1:2 serial-diluted out to column 12.
    def plate_mixed_bouquet(plate, plate_idx: int):
        protocol.comment(
            f"=== Plate {plate_idx + 1} | MIXED-COLOUR BOUQUET "
            f"(orange/green/purple/brown) ==="
        )

        # 1) Diluent in cols 2..12.
        multi_prefill_diluent(plate, 1, N_COLS, DILUENT_UL)

        # 2) Mix four secondary colours into column 1 (row pairs).
        ab = (plate["A1"], plate["B1"])
        cd = (plate["C1"], plate["D1"])
        ef = (plate["E1"], plate["F1"])
        gh = (plate["G1"], plate["H1"])

        # Orange (A,B) = red + yellow
        pick_single_tip("red")
        for w in ab:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "red")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("yellow")
        for w in ab:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "yellow")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
            flex_s.mix(2, MIX_UL, w.bottom(2))
            flex_s.move_to(w.top(z=-2))
        single_finish()

        # Green (C,D) = yellow + blue
        pick_single_tip("yellow")
        for w in cd:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "yellow")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("blue")
        for w in cd:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "blue")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
            flex_s.mix(2, MIX_UL, w.bottom(2))
            flex_s.move_to(w.top(z=-2))
        single_finish()

        # Purple (E,F) = red + blue
        pick_single_tip("red")
        for w in ef:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "red")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("blue")
        for w in ef:
            aspirate_from_sources(flex_s, HALF_STOCK_UL, "blue")
            trailed_dispense(flex_s, HALF_STOCK_UL, w.bottom(2))
            flex_s.mix(2, MIX_UL, w.bottom(2))
            flex_s.move_to(w.top(z=-2))
        single_finish()

        # Brown (G,H) = red + yellow + blue (50 uL each = 150 uL stock)
        pick_single_tip("red")
        for w in gh:
            aspirate_from_sources(flex_s, THIRD_STOCK_UL, "red")
            trailed_dispense(flex_s, THIRD_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("yellow")
        for w in gh:
            aspirate_from_sources(flex_s, THIRD_STOCK_UL, "yellow")
            trailed_dispense(flex_s, THIRD_STOCK_UL, w.bottom(2))
        single_finish()
        pick_single_tip("blue")
        for w in gh:
            aspirate_from_sources(flex_s, THIRD_STOCK_UL, "blue")
            trailed_dispense(flex_s, THIRD_STOCK_UL, w.bottom(2))
            flex_s.mix(2, MIX_UL, w.bottom(2))
            flex_s.move_to(w.top(z=-2))
        single_finish()

        # 3) Multi-channel: serial dilution cols 1..11 (col 12 blank).
        multi_serial_dilute(plate, 0, N_COLS - 1)

    # =====================================================================
    # WORKFLOW 6: Concentric Rainbow Rings (single-channel finale)
    # =====================================================================
    # The showpiece. Four nested rings of pure colour radiating inward.
    # Single-channel paints every well one at a time - slow but
    # mesmerising to watch, and a great closing "wow" plate.
    def plate_concentric_rings(plate, plate_idx: int):
        protocol.comment(
            f"=== Plate {plate_idx + 1} | CONCENTRIC RAINBOW RINGS (finale) ==="
        )

        # Build the four nested ring sets.
        rows_alpha = "ABCDEFGH"
        rings = []
        n_rings = min(N_ROWS, N_COLS) // 2   # = 4 for an 8x12 plate
        for k in range(n_rings):
            wells = []
            for c in range(k, N_COLS - k):
                wells.append(f"{rows_alpha[k]}{c + 1}")
                wells.append(f"{rows_alpha[N_ROWS - 1 - k]}{c + 1}")
            for r in range(k + 1, N_ROWS - 1 - k):
                wells.append(f"{rows_alpha[r]}{k + 1}")
                wells.append(f"{rows_alpha[r]}{N_COLS - k}")
            # de-dup while preserving order
            seen = set()
            uniq = []
            for w in wells:
                if w not in seen:
                    seen.add(w)
                    uniq.append(w)
            rings.append(uniq)

        # Per-ring colour spec: (tip_color, lane, volume_uL, secondary_mix)
        # The outer-to-inner palette is red -> yellow -> green (Y+B) -> blue,
        # which reads as a rainbow on the white-paper backdrop.
        ring_specs = [
            ("red",    "red",    80, None),
            ("yellow", "yellow", 80, None),
            ("yellow", "yellow", 50, ("blue",  50)),   # green = Y + B
            ("blue",   "blue",   80, None),
        ]

        for ring_wells, (tip, lane, vol, secondary) in zip(rings, ring_specs):
            pick_single_tip(tip)
            for w_name in ring_wells:
                w = plate.wells_by_name()[w_name]
                aspirate_from_sources(flex_s, vol, lane)
                dispense_and_lift(flex_s, vol, w)
            single_finish()
            if secondary is not None:
                sec_lane, sec_vol = secondary
                pick_single_tip(sec_lane)
                for w_name in ring_wells:
                    w = plate.wells_by_name()[w_name]
                    aspirate_from_sources(flex_s, sec_vol, sec_lane)
                    trailed_dispense(flex_s, sec_vol, w.bottom(2))
                    flex_s.mix(2, MIX_UL, w.bottom(2))
                    flex_s.move_to(w.top(z=-2))
                single_finish()

    # =====================================================================
    # Run sequence
    # =====================================================================
    workflow_sequence = [
        plate_standard_curves,
        plate_synergy_matrix,
        plate_multiplex_blocks,
        plate_elisa_layout,
        plate_mixed_bouquet,
        plate_concentric_rings,
    ]

    # =====================================================================
    # Pre-flight: reservoir sourcing plan (printed to the app's run log)
    # =====================================================================
    protocol.comment("=== Reservoir sourcing plan (NEST 12-channel, slot B1) ===")
    for reagent in ("red", "yellow", "blue", "water"):
        info = plan[reagent]
        per_lane = ", ".join(
            f"{lane}: pour {start / 1000:.2f} mL"
            for lane, start in zip(info["lanes"], info["planned_start_per_lane"])
        )
        protocol.comment(
            f"  {reagent:>6}: est. draw {info['estimated_draw_ul'] / 1000:.2f} mL "
            f"-> total pour {info['with_buffer_ul'] / 1000:.2f} mL across "
            f"{info['lanes']} | {per_lane}"
        )
    protocol.comment(
        f"  wash:   pour ~{WORKING_LANE_CAPACITY_UL / 1000:.0f} mL into "
        f"{plan['_wash']['lane']} (no draws, stays in place)"
    )
    protocol.comment(
        "Buffers: "
        f"+{OVERHEAD_FRACTION * 100:.0f}% overhead, "
        f"+{DEAD_VOLUME_PER_REAGENT_UL} uL dead volume per reagent."
    )

    if PRE_FLIGHT_PAUSE:
        protocol.pause(PRE_FLIGHT_PAUSE_MSG)
    protocol.home()
    protocol.set_rail_lights(True)   # booth lights on

    _run_started_at = time.time()
    _plate_times = []   # (label, seconds, was_run)
    plate_enabled = [
        getattr(protocol.params, name, True) for name in PLATE_PARAM_NAMES
    ]

    for i, (plate, workflow, label, enabled) in enumerate(
        zip(plates, workflow_sequence, PLATE_PARAM_LABELS, plate_enabled)
    ):
        if not enabled:
            protocol.comment(f"  (skipped: {label})")
            _plate_times.append((label, 0.0, False))
            continue

        _plate_started_at = time.time()
        workflow(plate, i)
        _plate_times.append((label, time.time() - _plate_started_at, True))

        if incubation_delay_s > 0:
            protocol.delay(
                seconds=incubation_delay_s,
                msg=f"Plate {i + 1}: simulated assay incubation",
            )
        if viewing_delay_s > 0:
            protocol.delay(
                seconds=viewing_delay_s,
                msg=f"Plate {i + 1}: showing finished plate",
            )

    _run_seconds = time.time() - _run_started_at
    _plates_run = sum(1 for _, _, was_run in _plate_times if was_run)
    protocol.comment(
        f"=== Timing summary: {_plates_run}/{len(plates)} plates in "
        f"{_run_seconds/60:.1f} min ({_run_seconds:.0f} s) ==="
    )
    for _label, _secs, _was_run in _plate_times:
        if _was_run:
            protocol.comment(
                f"  {_label:<32}: {_secs/60:5.2f} min ({_secs:5.0f} s)"
            )
        else:
            protocol.comment(f"  {_label:<32}: (skipped)")

    protocol.comment("=== End-of-run reservoir usage (uL remaining per lane) ===")
    for reagent in ("red", "yellow", "blue", "water"):
        lanes = plan[reagent]["lanes"]
        starts = plan[reagent]["planned_start_per_lane"]
        per_lane = []
        total_drawn = 0.0
        for lane, start in zip(lanes, starts):
            left = remaining_ul.get(lane, 0.0)
            drawn = max(0.0, start - left)
            total_drawn += drawn
            per_lane.append(f"{lane}: {left:.0f} left / drew {drawn:.0f}")
        protocol.comment(
            f"  {reagent:>6}: drew {total_drawn/1000:.2f} mL total | "
            + "; ".join(per_lane)
        )
    protocol.comment(
        "Demo complete - thanks for visiting the Future Lab Innovations booth!"
    )
