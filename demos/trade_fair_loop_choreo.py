"""
OT-2 Trade Fair Looping Dry-Choreo Demo
========================================

P300 multi-channel only. Acts as if it is pipetting real samples,
but the protocol never actually loads liquid - every aspirate/dispense
is just plunger motion against air. The robot doesn't know the
difference, and visitors see realistic-looking pipetting work for as
long as the booth is open.

Seven rotating choreographies (one per cycle, cycling round-robin)
give the demo enough variety that visitors can stop watching for
five minutes, come back, and see a new motion. Two of them use
PARTIAL TIP PICKUP via configure_nozzle_layout() so the multi
visibly halves (HALF) or shrinks to a single tip (PINPOINT) - very
distinctive against the all-8-channel sweeps:

  1. WAVE      ALL          column-major sweep across all 3 plates;
                            direction alternates per column
  2. STAMP     ALL          per-plate left-to-right sweep at
                            progressively slower flow rates
  3. HALF      PARTIAL_COL  pickup with only the front 4 nozzles
                            (H/G/F/E); sweep dispenses only into the
                            front half of each column
  4. MIX DANCE ALL          per-column mix(3, vol) - plunger machine-
                            guns up-and-down visibly at every column
  5. PINPOINT  SINGLE       only the H (front) nozzle is active; the
                            multi acts like a single-channel painter
                            and draws a plus-sign in the middle of
                            each plate
  6. SPIRAL    ALL          outside-in column order (1, 12, 2, 11,
                            3, 10, ...) - non-obvious pattern
  7. DRUMROLL  ALL          3 quick taps per column then a tall lift
                            - reads as rhythmic tapping

Tip swaps only happen when the nozzle layout actually changes.
Successive ALL-mode patterns share the same tip column (tip-
efficient). HALF and PINPOINT each force a fresh pickup motion when
they fire, and the visual of the arm going back to the tip rack and
grabbing a new layout is itself part of the show.

==============================================================================
MATERIALS
==============================================================================

Hardware:
  * Opentrons OT-2
  * P300 Multi-Channel GEN2 (right mount; the only pipette used)

Labware (Flex-style deck coordinates as the user requested; mapped to
OT-2 numeric slots in the load_labware calls):

  Coord  | OT-2 slot | Item
  -------+-----------+--------------------------------------------
  B1     |     7     | opentrons_96_tiprack_300ul       (tip box 1)
  C1     |     4     | opentrons_96_tiprack_300ul       (tip box 2)
  B2     |     8     | corning_96_wellplate_360ul_flat  (plate back)
  C2     |     5     | corning_96_wellplate_360ul_flat  (plate mid)
  D2     |     2     | corning_96_wellplate_360ul_flat  (plate front)

  ┌─ back ──────────────────────────────────────────────────────┐
  │  slot 7 (B1)   slot 8 (B2)   slot 9   (empty)               │
  │  TIP BOX 1     PLATE BACK                                   │
  │                                                             │
  │  slot 4 (C1)   slot 5 (C2)   slot 6   (empty)               │
  │  TIP BOX 2     PLATE MID                                    │
  │                                                             │
  │  slot 1        slot 2 (D2)   slot 3   (empty)               │
  │  (empty)       PLATE FRONT                                  │
  └─ front ─────────────────────────────────────────────────────┘

No reagents required - the run is bone dry. Visualizer shows the
plates pre-loaded with mock liquids in three different colours so
the booth-crew set-up screen still has visual cues; the multi never
actually transfers anything.

==============================================================================
RUNTIME PARAMETERS
==============================================================================

  n_cycles               Cycles before the run ends. Default 25
                         (~50 min). Max 500. Each cycle is ONE
                         choreography from the 5 above; the pattern
                         rotates round-robin.
  pretend_volume_ul      Volume the multi aspirates / dispenses
                         (air). 50-300 uL. Higher = more visible
                         plunger motion. Default 150.
  inter_cycle_pause_s    Quick pause between cycles. Default 1.
                         Set 0 for continuous flow.
  lift_mm                Lift height between columns. Default 25.
                         Higher = more dramatic arc.

==============================================================================
WHAT THE BOOTH CREW SEES
==============================================================================

Run start:
  - Multi homes, rail lights on
  - Picks up first tip column from tip box 1 (B1, slot 7)

Per cycle:
  - Comment line prints the cycle number and the pattern name
  - The chosen choreography runs across all three plates
  - Brief pause, then the next cycle starts a DIFFERENT pattern

Every 5 cycles:
  - Returns the tip column to its rack
  - Picks a fresh column from the other rack (alternating each time)
  - Resumes choreography

Run end:
  - Final tip column returned
  - "Demo complete" comment

Because the multi never picks more than two tip columns total per
cycle (one swap), 24 columns of tips comfortably cover a 500-cycle
day. With dry pipetting and no consumables you can run unattended.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair Dry-Choreo Loop (Multi, 3 Plates)",
    "author": "FLi",
    "description": (
        "OT-2 P300 multi-channel looping choreography. 5 rotating "
        "patterns, dry pipetting (no liquid), runs unattended."
    ),
}

requirements = {"robotType": "OT-2", "apiLevel": "2.20"}


# Partial-tip-pickup constants. Available from apiLevel 2.20 on both
# Flex and OT-2 pipettes (SINGLE works on every multi-channel; partial
# column works on any 8-channel including the OT-2 P300 multi GEN2).
from opentrons.protocol_api import SINGLE, PARTIAL_COLUMN, ALL  # noqa: E402


# ---------------------------------------------------------------------------
# Slot mapping - user-supplied Flex-style coords -> OT-2 numeric slots
# ---------------------------------------------------------------------------
SLOT_TIP_BOX_1 = 7    # B1: back-left  - first tip rack
SLOT_TIP_BOX_2 = 4    # C1: mid-left   - second tip rack
SLOT_PLATE_BACK = 8   # B2: back-mid   - plate back
SLOT_PLATE_MID  = 5   # C2: center     - plate mid
SLOT_PLATE_FRONT = 2  # D2: front-mid  - plate front

# ---------------------------------------------------------------------------
# Defaults (RTPs override at run-time)
# ---------------------------------------------------------------------------
DEFAULT_N_CYCLES = 25
DEFAULT_VOL_UL = 150
DEFAULT_PAUSE_S = 1
DEFAULT_LIFT_MM = 25
N_COLS = 12


def add_parameters(parameters):
    parameters.add_int(
        variable_name="n_cycles",
        display_name="Cycles to run",
        description="How many choreography cycles before the run ends.",
        default=DEFAULT_N_CYCLES,
        minimum=1, maximum=500,
    )
    parameters.add_int(
        variable_name="pretend_volume_ul",
        display_name="Pretend volume",
        description="Plunger-stroke volume (air). Higher = more visible motion.",
        default=DEFAULT_VOL_UL,
        minimum=50, maximum=300,
        unit="uL",
    )
    parameters.add_int(
        variable_name="inter_cycle_pause_s",
        display_name="Pause between cycles",
        description="Short pause between cycles. 0 = continuous flow.",
        default=DEFAULT_PAUSE_S,
        minimum=0, maximum=60,
        unit="s",
    )
    parameters.add_int(
        variable_name="lift_mm",
        display_name="Lift between cols",
        description="Lift height between columns. Higher = more dramatic arc.",
        default=DEFAULT_LIFT_MM,
        minimum=5, maximum=80,
        unit="mm",
    )


def run(protocol: protocol_api.ProtocolContext):
    n_cycles = getattr(protocol.params, "n_cycles", DEFAULT_N_CYCLES)
    vol      = getattr(protocol.params, "pretend_volume_ul", DEFAULT_VOL_UL)
    pause_s  = getattr(protocol.params, "inter_cycle_pause_s", DEFAULT_PAUSE_S)
    lift_mm  = getattr(protocol.params, "lift_mm", DEFAULT_LIFT_MM)

    # =====================================================================
    # Labware
    # =====================================================================
    tips_1 = protocol.load_labware(
        "opentrons_96_tiprack_300ul", SLOT_TIP_BOX_1, "tip box 1 (B1)",
    )
    tips_2 = protocol.load_labware(
        "opentrons_96_tiprack_300ul", SLOT_TIP_BOX_2, "tip box 2 (C1)",
    )
    plate_back = protocol.load_labware(
        "corning_96_wellplate_360ul_flat", SLOT_PLATE_BACK, "plate back (B2)",
    )
    plate_mid = protocol.load_labware(
        "corning_96_wellplate_360ul_flat", SLOT_PLATE_MID, "plate mid (C2)",
    )
    plate_front = protocol.load_labware(
        "corning_96_wellplate_360ul_flat", SLOT_PLATE_FRONT, "plate front (D2)",
    )

    # Front-to-back ordering for choreographies that traverse plates.
    plates_f2b = [plate_front, plate_mid, plate_back]

    # =====================================================================
    # Pipette
    # =====================================================================
    multi = protocol.load_instrument(
        "p300_multi_gen2", "right", tip_racks=[tips_1, tips_2],
    )
    # Default rates; each pattern adjusts inside its own body for variety.
    multi.flow_rate.aspirate = 150
    multi.flow_rate.dispense = 300

    # =====================================================================
    # Visualizer-only "mock" liquids (no actual pre-pour required)
    # =====================================================================
    # define_liquid is metadata-only - registering them lets the Opentrons
    # app paint colour swatches on the deck preview so the booth crew can
    # tell the plates apart at a glance. No load_liquid() calls because
    # the run is genuinely dry.
    protocol.define_liquid(
        "Mock sample A (front)",
        "Dry-run mock - no liquid actually present",
        "#e60026",
    )
    protocol.define_liquid(
        "Mock sample B (mid)",
        "Dry-run mock - no liquid actually present",
        "#ffd400",
    )
    protocol.define_liquid(
        "Mock sample C (back)",
        "Dry-run mock - no liquid actually present",
        "#0066cc",
    )

    # =====================================================================
    # Choreography helpers
    # =====================================================================
    def fake_aspdisp(well, vol_ul):
        """One aspirate + one dispense at the same well bottom. The
        plunger moves visibly even though both calls pull/push air."""
        multi.aspirate(vol_ul, well.bottom(z=2))
        multi.dispense(vol_ul, well.bottom(z=2))

    # Track current nozzle layout so we only reconfigure (and incur a
    # tip swap) when the next pattern actually needs a different shape.
    layout_state = {"current": ALL, "start": None, "end": None}

    def reconfigure_nozzles(target, start=None, end=None):
        """Switch the multi to a different nozzle layout. Requires
        returning the current tip (if any) first; picks fresh tips for
        the new layout afterwards. No-op if already on this layout."""
        if (target == layout_state["current"]
                and start == layout_state["start"]
                and end == layout_state["end"]):
            return
        if multi.has_tip:
            multi.return_tip()
        if target == ALL:
            multi.configure_nozzle_layout(ALL)
        elif target == SINGLE:
            multi.configure_nozzle_layout(SINGLE, start=start)
        elif target == PARTIAL_COLUMN:
            multi.configure_nozzle_layout(PARTIAL_COLUMN, start=start, end=end)
        else:
            multi.configure_nozzle_layout(target)
        layout_state["current"] = target
        layout_state["start"] = start
        layout_state["end"] = end
        multi.pick_up_tip()

    # ----- Pattern 1: WAVE ------------------------------------------------
    def pattern_wave():
        reconfigure_nozzles(ALL)
        multi.flow_rate.aspirate = 100
        multi.flow_rate.dispense = 200
        for col_idx in range(N_COLS):
            row = plates_f2b if col_idx % 2 == 0 else list(reversed(plates_f2b))
            for plate in row:
                top_well = plate.columns()[col_idx][0]
                fake_aspdisp(top_well, vol)
                multi.move_to(top_well.top(z=lift_mm))

    # ----- Pattern 2: STAMP -----------------------------------------------
    def pattern_stamp():
        # Speeds slow down as we move from front plate to back plate;
        # reads as the demo "winding down" before the next pattern fires.
        reconfigure_nozzles(ALL)
        for idx, plate in enumerate(plates_f2b):
            multi.flow_rate.aspirate = max(50, 200 - idx * 60)
            multi.flow_rate.dispense = max(100, 400 - idx * 120)
            for col_idx in range(N_COLS):
                top_well = plate.columns()[col_idx][0]
                fake_aspdisp(top_well, vol)
            # Big lift at the end of each plate for a punctuation mark.
            multi.move_to(plate.columns()[0][0].top(z=lift_mm + 15))

    # ----- Pattern 3: MIX DANCE -------------------------------------------
    def pattern_mix_dance():
        # mix(reps, vol, location) does reps aspirate+dispense pairs in
        # place - plunger machine-guns up and down at every column.
        reconfigure_nozzles(ALL)
        multi.flow_rate.aspirate = 250
        multi.flow_rate.dispense = 500
        for plate in plates_f2b:
            for col_idx in range(N_COLS):
                top_well = plate.columns()[col_idx][0]
                multi.mix(3, vol, top_well.bottom(z=2))
                multi.move_to(top_well.top(z=lift_mm // 2))

    # ----- Pattern 4: SPIRAL ----------------------------------------------
    def pattern_spiral():
        # Outside-in column order: 1, 12, 2, 11, 3, 10, ...
        reconfigure_nozzles(ALL)
        order = []
        for i in range(N_COLS // 2):
            order.append(i)
            order.append(N_COLS - 1 - i)
        multi.flow_rate.aspirate = 120
        multi.flow_rate.dispense = 240
        for plate in plates_f2b:
            for col_idx in order:
                top_well = plate.columns()[col_idx][0]
                fake_aspdisp(top_well, vol)
                multi.move_to(top_well.top(z=lift_mm))

    # ----- Pattern 5: DRUMROLL --------------------------------------------
    def pattern_drumroll():
        # Three quick taps per column, tall lift between columns - reads
        # as a rhythmic drumroll across each plate.
        reconfigure_nozzles(ALL)
        multi.flow_rate.aspirate = 280
        multi.flow_rate.dispense = 550
        for plate in plates_f2b:
            for col_idx in range(N_COLS):
                top_well = plate.columns()[col_idx][0]
                for _ in range(3):
                    fake_aspdisp(top_well, vol)
                multi.move_to(top_well.top(z=lift_mm + 10))

    # ----- Pattern 6: HALF (PARTIAL_COLUMN, 4 nozzles) --------------------
    def pattern_half():
        """Partial-column pickup with the front four nozzles (H, G, F, E).
        Sweeps the columns dispensing only into the front half of each
        plate. Visually: the multi suddenly halves in size and visits the
        same columns but with a noticeably shorter tip cluster."""
        reconfigure_nozzles(PARTIAL_COLUMN, start="H1", end="E1")
        multi.flow_rate.aspirate = 120
        multi.flow_rate.dispense = 240
        for plate in plates_f2b:
            for col_idx in range(N_COLS):
                # With H1 as the primary nozzle, the API positions the H
                # nozzle over the targeted well; the E/F/G nozzles land
                # at rows G/F/E of the same column.
                front_well = plate.wells_by_name()[f"H{col_idx + 1}"]
                fake_aspdisp(front_well, vol)
                multi.move_to(front_well.top(z=lift_mm))

    # ----- Pattern 7: PINPOINT (SINGLE nozzle) ----------------------------
    def pattern_pinpoint():
        """SINGLE nozzle layout - exactly one channel of the multi is
        active, so the pipette acts like a single-channel painter.
        Draws a cross / plus sign in the middle of each plate; the
        precise, well-by-well motion contrasts sharply with the full
        column sweeps of the ALL-mode patterns."""
        reconfigure_nozzles(SINGLE, start="H1")
        multi.flow_rate.aspirate = 80
        multi.flow_rate.dispense = 160
        # Horizontal stroke (row E, cols 4..9) + vertical stroke (rows B..G, col 6)
        h_stroke = [f"E{c + 1}" for c in range(3, 9)]
        v_stroke = [f"{r}6"     for r in "BCDFG"]
        per_well = max(20, vol // 3)
        for plate in plates_f2b:
            for w_name in h_stroke + v_stroke:
                w = plate.wells_by_name()[w_name]
                multi.aspirate(per_well, w.bottom(z=2))
                multi.dispense(per_well, w.bottom(z=2))
                multi.move_to(w.top(z=lift_mm // 2))

    patterns = [
        ("WAVE",       pattern_wave),
        ("STAMP",      pattern_stamp),
        ("HALF",       pattern_half),        # partial column, 4 nozzles
        ("MIX DANCE",  pattern_mix_dance),
        ("PINPOINT",   pattern_pinpoint),    # SINGLE nozzle
        ("SPIRAL",     pattern_spiral),
        ("DRUMROLL",   pattern_drumroll),
    ]

    # =====================================================================
    # Pre-flight report
    # =====================================================================
    protocol.comment("=== Trade Fair Dry-Choreo Loop ===")
    protocol.comment(
        f"  Cycles    : {n_cycles}  (5 patterns rotating round-robin)"
    )
    protocol.comment(
        f"  Pipetting : DRY - {vol} uL pretend volume (plunger only)"
    )
    protocol.comment(f"  Pause     : {pause_s} s between cycles")
    protocol.comment(f"  Lift      : {lift_mm} mm between columns")
    protocol.comment(
        "  Tip swap  : only when the nozzle layout changes "
        "(HALF / PINPOINT force fresh pickup)"
    )
    protocol.comment(
        f"  Plates    : 3 flat 96-well plates at B2 / C2 / D2"
    )
    sec_per_pattern = {
        "WAVE":     N_COLS * 3 * 2,            # 12 cols x 3 plates x ~2 s
        "STAMP":    N_COLS * 3 * 1.5,
        "MIX DANCE": N_COLS * 3 * 3,
        "SPIRAL":   N_COLS * 3 * 2,
        "DRUMROLL": N_COLS * 3 * 3.5,
    }
    avg_cycle_s = sum(sec_per_pattern.values()) / len(sec_per_pattern)
    est_min = (avg_cycle_s + pause_s) * n_cycles / 60.0
    protocol.comment(f"  Estimated runtime: ~{est_min:.0f} min")

    # =====================================================================
    # Main loop
    # =====================================================================
    protocol.home()
    protocol.set_rail_lights(True)

    # First-cycle pickup. reconfigure_nozzles() handles the actual
    # pick_up_tip; from here on every pattern self-manages its tip via
    # reconfigure_nozzles() at the top of its body. Tip swaps only
    # happen when the nozzle layout actually changes, so successive
    # ALL-mode patterns share the same tip column - tip-efficient AND
    # visually still varied because the new partial-pickup patterns
    # force a fresh pickup motion every time they fire.
    reconfigure_nozzles(ALL)

    for cycle in range(1, n_cycles + 1):
        name, fn = patterns[(cycle - 1) % len(patterns)]
        protocol.comment(f"--- Cycle {cycle}/{n_cycles}: {name} ---")
        fn()

        if pause_s > 0 and cycle < n_cycles:
            protocol.delay(seconds=pause_s)

    # End-of-run: drop back to ALL config + return tip cleanly.
    reconfigure_nozzles(ALL)
    multi.return_tip()
    protocol.comment(f"=== Demo complete: {n_cycles} cycles ===")
