"""
OT-2 Trade Fair Looping Demo  -  Multi + 3 Falcons + 3 Flat Plates
==================================================================

Minimal-hardware booth choreography. The P300 multi-channel sweeps
across three 96-well plates, visiting three 50 mL falcon tubes
between plates, for N cycles. Designed to be visually engaging from
across the booth: the arm sweeps in a clear left-to-right rhythm,
alternating direction every other cycle so the motion never feels
static.

Works DRY (the default) - no liquid required, the pipette just
visits each position with a hover-and-pause pattern. Or WET (set
dispense_volume_ul > 0): one of eight channels gets liquid from the
falcon (the other seven are over air); only row A of each plate
ends up actually filled. Still visually interesting wet, but use dry
for an all-day booth run since dry has zero consumables.

==============================================================================
MATERIALS
==============================================================================

Hardware:
  * Opentrons OT-2
  * P300 Multi-Channel GEN2 (right mount; the only pipette used)
  * 1 movable trash bin (slot 12 - OT-2 fixed)

Labware:
  * 3 x corning_96_wellplate_360ul_flat        (slots 1, 2, 3)
  * 1 x opentrons_6_tuberack_falcon_50ml_conical (slot 4)
        - load 3 tubes at A1, A2, A3 (top row); B1/B2/B3 stay empty
  * 1 x opentrons_96_tiprack_300ul             (slot 5)

Reagents (only if running wet):
  * Tube A1: red dye (~50 mL)
  * Tube A2: yellow dye
  * Tube A3: blue dye

Deck layout (front view):
   slot 1  | slot 2  | slot 3      (front row - the 3 plates, left to right)
   slot 4  | slot 5  | -           (mid row - tubes + tip rack)
   -       | -       | -
   -       | -       | trash       (back row - just the trash)

==============================================================================
RUNTIME PARAMETERS
==============================================================================

  n_cycles                Cycles to run. Default 10 (~15 min dry).
  dispense_volume_ul      0 = dry pipetting (default). 1-200 = wet.
  inter_cycle_pause_s     Seconds between cycles. 0 = continuous loop.
  column_lift_mm          Lift height between columns. Higher = more dramatic.

==============================================================================
WHAT VISITORS SEE
==============================================================================

Each cycle:
  1. Multi picks up a tip column (once, at the very start)
  2. Arm visits falcon A1, hovers, dips
  3. Sweeps across all 12 columns of plate 1 (left -> right on even
     cycles, right -> left on odd cycles)
  4. Visits falcon A2, sweeps plate 2 (opposite direction)
  5. Visits falcon A3, sweeps plate 3
  6. Brief pause, then repeat from step 2

After n_cycles, the tip is returned to the rack and the run ends.
"""

from opentrons import protocol_api

metadata = {
    "protocolName": "Trade Fair Looping Demo (Multi + Falcons + 3 Plates)",
    "author": "FLi",
    "description": (
        "Minimal-hardware looping choreography. P300 multi sweeps 3 plates "
        "from 3 falcon tubes for N cycles. Runs dry by default, or wet."
    ),
}

requirements = {"robotType": "OT-2", "apiLevel": "2.18"}


# Module-level defaults (RTPs override at run-time)
DEFAULT_N_CYCLES = 10
DEFAULT_DISPENSE_UL = 0          # 0 = dry mode
DEFAULT_PAUSE_S = 2
DEFAULT_LIFT_MM = 30
N_COLS = 12                      # 96-well plate has 12 columns


def add_parameters(parameters):
    parameters.add_int(
        variable_name="n_cycles",
        display_name="Cycles to run",
        description="How many full sweep cycles before the run ends.",
        default=DEFAULT_N_CYCLES,
        minimum=1, maximum=1000,
    )
    parameters.add_int(
        variable_name="dispense_volume_ul",
        display_name="Dispense vol (0=dry)",
        description="Per-column volume. 0 = dry, no liquid.",
        default=DEFAULT_DISPENSE_UL,
        minimum=0, maximum=200,
        unit="uL",
    )
    parameters.add_int(
        variable_name="inter_cycle_pause_s",
        display_name="Pause between cycles",
        description="Quick pause between cycles for visual rhythm.",
        default=DEFAULT_PAUSE_S,
        minimum=0, maximum=60,
        unit="s",
    )
    parameters.add_int(
        variable_name="column_lift_mm",
        display_name="Lift between cols",
        description="How high the pipette lifts between columns.",
        default=DEFAULT_LIFT_MM,
        minimum=5, maximum=80,
        unit="mm",
    )


def run(protocol: protocol_api.ProtocolContext):
    n_cycles = getattr(protocol.params, "n_cycles", DEFAULT_N_CYCLES)
    vol      = getattr(protocol.params, "dispense_volume_ul", DEFAULT_DISPENSE_UL)
    pause_s  = getattr(protocol.params, "inter_cycle_pause_s", DEFAULT_PAUSE_S)
    lift_mm  = getattr(protocol.params, "column_lift_mm", DEFAULT_LIFT_MM)
    dry      = (vol == 0)

    # =====================================================================
    # Labware
    # =====================================================================
    plate_1 = protocol.load_labware("corning_96_wellplate_360ul_flat", 1, "plate 1")
    plate_2 = protocol.load_labware("corning_96_wellplate_360ul_flat", 2, "plate 2")
    plate_3 = protocol.load_labware("corning_96_wellplate_360ul_flat", 3, "plate 3")
    tube_rack = protocol.load_labware(
        "opentrons_6_tuberack_falcon_50ml_conical", 4, "falcon tubes",
    )
    tip_rack  = protocol.load_labware("opentrons_96_tiprack_300ul", 5, "tips")

    # =====================================================================
    # Pipette
    # =====================================================================
    multi = protocol.load_instrument(
        "p300_multi_gen2", "right", tip_racks=[tip_rack],
    )
    multi.flow_rate.aspirate = 100
    multi.flow_rate.dispense = 200

    # =====================================================================
    # Sources + destinations
    # =====================================================================
    tubes = [tube_rack["A1"], tube_rack["A2"], tube_rack["A3"]]
    plates = [plate_1, plate_2, plate_3]

    # Register liquids for the Opentrons app's Liquid Setup screen. The
    # display colour shows on the deck preview even in dry mode, which
    # makes the booth crew's set-up smoother. load_liquid() only runs
    # when actually pre-pouring (wet mode).
    color_specs = [
        ("Red dye",    "1:5 red food colouring",    "#e60026"),
        ("Yellow dye", "1:5 yellow food colouring", "#ffd400"),
        ("Blue dye",   "1:5 blue food colouring",   "#0066cc"),
    ]
    for tube, (name, desc, color) in zip(tubes, color_specs):
        liquid = protocol.define_liquid(name, desc, color)
        if not dry:
            tube.load_liquid(liquid, 50_000)   # 50 mL pre-fill per tube

    # =====================================================================
    # Pre-flight comment block
    # =====================================================================
    protocol.comment("=== Trade Fair Looping Demo (minimal hardware) ===")
    protocol.comment(
        f"  Mode    : {'dry pipetting (no liquid)' if dry else f'wet, {vol} uL per column'}"
    )
    protocol.comment(f"  Cycles  : {n_cycles}")
    protocol.comment(f"  Pause   : {pause_s} s between cycles")
    protocol.comment(f"  Lift    : {lift_mm} mm between columns")
    protocol.comment(f"  Sources : 3 falcon tubes (A1, A2, A3)")
    protocol.comment(f"  Plates  : 3 flat 96-well (slots 1, 2, 3)")

    # Rough runtime estimate: ~3 s per column move dry, ~5 s wet, plus
    # tube visits and inter-cycle pauses.
    sec_per_col   = 2.5 if dry else 4.5
    sec_per_tube  = 3.0
    moves_per_cyc = len(plates) * (N_COLS * sec_per_col + sec_per_tube)
    total_min     = (moves_per_cyc + pause_s) * n_cycles / 60.0
    protocol.comment(f"  Estimated runtime: ~{total_min:.0f} min")

    if not dry:
        protocol.comment(
            "  NOTE wet mode: only one of eight channels is over a tube during "
            "aspirate, so only row A of each plate ends up filled."
        )

    # =====================================================================
    # Choreography helpers
    # =====================================================================
    def visit_tube(tube):
        """Hover above the tube, dip toward the rim, lift. In wet mode,
        also aspirate one cycle's worth of dispense."""
        multi.move_to(tube.top(z=lift_mm))
        protocol.delay(seconds=0.4)
        if dry:
            multi.move_to(tube.top(z=5))
            protocol.delay(seconds=0.3)
        else:
            multi.aspirate(vol * N_COLS, tube.bottom(z=5))
        multi.move_to(tube.top(z=lift_mm))

    def sweep_plate(plate, cycle_idx):
        """Visit every column of `plate` with a hover-dispense-lift
        rhythm. Direction alternates each cycle so the booth never
        sees the same motion twice in a row."""
        cols = list(range(N_COLS))
        if cycle_idx % 2 == 1:
            cols.reverse()
        for col_idx in cols:
            col_top = plate.columns()[col_idx][0]
            multi.move_to(col_top.top(z=lift_mm))
            if dry:
                protocol.delay(seconds=0.15)
                multi.move_to(col_top.top(z=-2))
                protocol.delay(seconds=0.1)
            else:
                multi.dispense(vol, col_top.top(z=-5))
        # Clean lift-off at the end of the sweep.
        last_col = plate.columns()[cols[-1]][0]
        multi.move_to(last_col.top(z=lift_mm))

    # =====================================================================
    # Run sequence
    # =====================================================================
    protocol.home()
    protocol.set_rail_lights(True)

    multi.pick_up_tip()

    for cycle in range(1, n_cycles + 1):
        protocol.comment(f"--- Cycle {cycle}/{n_cycles} ---")
        for tube, plate in zip(tubes, plates):
            visit_tube(tube)
            sweep_plate(plate, cycle)

        if pause_s > 0 and cycle < n_cycles:
            protocol.delay(
                seconds=pause_s,
                msg=f"Cycle {cycle}/{n_cycles} done - pause",
            )

    multi.return_tip()
    protocol.comment(f"=== Demo complete: {n_cycles} cycles ===")
