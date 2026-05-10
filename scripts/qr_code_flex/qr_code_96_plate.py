"""Flex protocol that paints a small QR-style pattern onto a 96-well plate.

Companion to ``qr_code_384_plate.py`` for cases where you want larger,
more visible wells. Accepts up to an 8 row x 12 column CSV; smaller grids
are centered on the plate. Use ``image_to_csv.py --size 8x12`` to generate
a compatible CSV.
"""

from opentrons import protocol_api

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

metadata = {
    "protocolName": "QR Code on 96-Well Plate",
    "author": "Opentrons",
    "description": (
        "Renders a small QR-style pattern on a 96-well plate using dark "
        "dye for black pixels and water for the white background. Upload "
        "a CSV (max 8 rows x 12 cols) with 0/1 values; smaller grids are "
        "centered. The 8-channel pipette dispenses entire columns at once."
    ),
}

PLATE_ROWS = 8
PLATE_COLS = 12
ROW_LETTERS = "ABCDEFGH"
TRUTHY = {"1", "true", "True", "TRUE", "X", "x", "#", "B", "b"}


def add_parameters(parameters: protocol_api.ParameterContext) -> None:
    parameters.add_csv_file(
        variable_name="qr_csv",
        display_name="QR Code CSV",
        description=(
            "CSV of 0s and 1s. 1 = black pixel (dye), 0 = white pixel "
            "(water). Up to 8 rows x 12 columns. Smaller grids are "
            "centered on the plate."
        ),
    )
    parameters.add_float(
        variable_name="dispense_volume_ul",
        display_name="Volume per well",
        description="Volume dispensed into each well.",
        default=80.0,
        minimum=20.0,
        maximum=180.0,
        unit="uL",
    )
    parameters.add_bool(
        variable_name="fill_white_wells",
        display_name="Fill white wells with water",
        description=(
            "If on, dispense water into 'white' wells so every pixel "
            "in the QR shows a liquid level. If off, only the black "
            "pixels receive liquid."
        ),
        default=True,
    )


def _parse_qr_grid(parsed_csv: list) -> list:
    grid: list[list[int]] = []
    for raw_row in parsed_csv:
        cells: list[int] = []
        for raw_cell in raw_row:
            value = str(raw_cell).strip()
            if value == "":
                continue
            cells.append(1 if value in TRUTHY else 0)
        if cells:
            grid.append(cells)

    if not grid:
        raise ValueError("QR CSV is empty.")

    n_cols = max(len(row) for row in grid)
    for row in grid:
        if len(row) < n_cols:
            row.extend([0] * (n_cols - len(row)))

    if len(grid) > PLATE_ROWS or n_cols > PLATE_COLS:
        raise ValueError(
            f"QR grid is {len(grid)}x{n_cols} which exceeds the "
            f"{PLATE_ROWS}x{PLATE_COLS} 96-well plate. Resize the image "
            f"before exporting (see image_to_csv.py --size 8x12)."
        )
    return grid


def _grid_to_well_lists(grid: list) -> tuple:
    n_rows = len(grid)
    n_cols = len(grid[0])
    row_offset = (PLATE_ROWS - n_rows) // 2
    col_offset = (PLATE_COLS - n_cols) // 2

    black: list[str] = []
    white: list[str] = []
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            well = f"{ROW_LETTERS[r + row_offset]}{c + col_offset + 1}"
            (black if value else white).append(well)
    return black, white


def _grid_to_full_columns(grid: list, value: int) -> list:
    """Return 1-indexed column numbers in the centered grid that are entirely
    filled with the given value (used for fast 8-channel dispense).
    """
    n_rows = len(grid)
    if n_rows != PLATE_ROWS:
        return []
    col_offset = (PLATE_COLS - len(grid[0])) // 2
    full: list[int] = []
    for c in range(len(grid[0])):
        if all(grid[r][c] == value for r in range(n_rows)):
            full.append(c + col_offset + 1)
    return full


def run(protocol: protocol_api.ProtocolContext) -> None:
    grid = _parse_qr_grid(protocol.params.qr_csv.parse_as_csv())
    black_wells, white_wells = _grid_to_well_lists(grid)
    volume = float(protocol.params.dispense_volume_ul)
    fill_white = bool(protocol.params.fill_white_wells)

    full_dye_cols = _grid_to_full_columns(grid, 1)
    full_water_cols = _grid_to_full_columns(grid, 0) if fill_white else []
    full_dye_set = {f"{r}{c}" for c in full_dye_cols for r in ROW_LETTERS}
    full_water_set = {f"{r}{c}" for c in full_water_cols for r in ROW_LETTERS}
    single_black = [w for w in black_wells if w not in full_dye_set]
    single_white = [w for w in white_wells if w not in full_water_set]

    protocol.comment(
        f"QR grid: {len(grid)} rows x {len(grid[0])} cols. "
        f"{len(black_wells)} dye wells, {len(white_wells)} water wells. "
        f"Full dye columns: {full_dye_cols or 'none'}; "
        f"full water columns: {full_water_cols or 'none'}."
    )

    protocol.load_trash_bin("A3")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "C2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")
    tiprack_50_single = protocol.load_labware(
        "opentrons_flex_96_filtertiprack_200ul", "B3"
    )
    tiprack_200_multi = protocol.load_labware(
        "opentrons_flex_96_filtertiprack_200ul", "B2"
    )

    single = protocol.load_instrument(
        "flex_1channel_1000", "right", tip_racks=[tiprack_50_single]
    )
    multi = protocol.load_instrument(
        "flex_8channel_1000", "left", tip_racks=[tiprack_200_multi]
    )

    dye_source = reservoir["A1"]
    water_source = reservoir["A2"]

    dye_liquid = protocol.define_liquid(
        name="Dark dye",
        description="Used for black QR pixels.",
        display_color="#202020",
    )
    water_liquid = protocol.define_liquid(
        name="Water",
        description="Used for white QR pixels (background).",
        display_color="#9CCFFF",
    )
    n_water = len(white_wells) if fill_white else 0
    dye_load = max(int(volume * len(black_wells) * 1.2) + 1000, 1000)
    water_load = max(int(volume * n_water * 1.2) + 1000, 1000)
    dye_source.load_liquid(liquid=dye_liquid, volume=min(dye_load, 14000))
    water_source.load_liquid(liquid=water_liquid, volume=min(water_load, 14000))

    def _multi_columns(source, columns):
        if not columns:
            return
        multi.pick_up_tip()
        for col in columns:
            multi.aspirate(volume, source)
            multi.dispense(volume, plate[f"A{col}"].top(z=-1))
            multi.blow_out(plate[f"A{col}"].top(z=-1))
        multi.drop_tip()

    def _single_wells(source, wells):
        if not wells:
            return
        single.distribute(
            volume,
            source,
            [plate[w] for w in wells],
            new_tip="once",
            disposal_volume=5,
            blow_out=True,
            blowout_location="source well",
        )

    if fill_white:
        protocol.comment("Dispensing water into white columns (8-channel)...")
        _multi_columns(water_source, full_water_cols)
        protocol.comment("Dispensing water into remaining white wells...")
        _single_wells(water_source, single_white)

    protocol.comment("Dispensing dye into black columns (8-channel)...")
    _multi_columns(dye_source, full_dye_cols)
    protocol.comment("Dispensing dye into remaining black wells...")
    _single_wells(dye_source, single_black)

    protocol.comment("QR pattern complete.")
