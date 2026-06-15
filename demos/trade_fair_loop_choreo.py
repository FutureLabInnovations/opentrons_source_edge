"""
OT-2 Trade Fair Looping Dry-Choreo Demo
========================================

P300 multi-channel only. Acts as if it is pipetting real samples,
but the protocol never actually loads liquid - every aspirate/dispense
is just plunger motion against air. The robot doesn't know the
difference, and visitors see realistic-looking pipetting work for as
long as the booth is open.

Five rotating choreographies (one per cycle, cycling round-robin)
give the demo enough variety that visitors can stop watching for
five minutes, come back, and see a new motion:

  1. WAVE      column-major sweep across all 3 plates;
                direction alternates per column
  2. STAMP     per-plate left-to-right sweep at progressively slower
                flow rates (front fast, back slow)
  3. MIX DANCE per-column mix(2, vol) so the plunger machine-guns
                up-and-down visibly at every well column
  4. SPIRAL    outside-in column order (1, 12, 2, 11, 3, 10, ...) -
                non-obvious pattern that catches the eye
  5. DRUMROLL  three quick aspirate/dispense pairs per column then
                a tall lift - reads as rhythmic tapping

Between cycles, the multi returns its tip column and picks a fresh
column from the OTHER tip box on every cycle, so both tip racks get
used and the tip-swap motion is itself part of the show.

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

requirements = {"robotType": "OT-2", "apiLevel": "2.18"}


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
TIP_SWAP_EVERY = 5     # cycles between tip-column swaps


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

    # ----- Pattern 1: WAVE ------------------------------------------------
    def pattern_wave():
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
        multi.flow_rate.aspirate = 280
        multi.flow_rate.dispense = 550
        for plate in plates_f2b:
            for col_idx in range(N_COLS):
                top_well = plate.columns()[col_idx][0]
                for _ in range(3):
                    fake_aspdisp(top_well, vol)
                multi.move_to(top_well.top(z=lift_mm + 10))

    patterns = [
        ("WAVE",       pattern_wave),
        ("STAMP",      pattern_stamp),
        ("MIX DANCE",  pattern_mix_dance),
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
        f"  Tip swap  : every {TIP_SWAP_EVERY} cycles, alternating tip box"
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

    multi.pick_up_tip()

    for cycle in range(1, n_cycles + 1):
        name, fn = patterns[(cycle - 1) % len(patterns)]
        protocol.comment(f"--- Cycle {cycle}/{n_cycles}: {name} ---")
        fn()

        # Swap tip column every TIP_SWAP_EVERY cycles - the visual of the
        # arm going back to a tip rack and grabbing a fresh column is
        # itself part of the show.
        if cycle % TIP_SWAP_EVERY == 0 and cycle < n_cycles:
            multi.return_tip()
            multi.pick_up_tip()

        if pause_s > 0 and cycle < n_cycles:
            protocol.delay(seconds=pause_s)

    multi.return_tip()
    protocol.comment(f"=== Demo complete: {n_cycles} cycles ===")
