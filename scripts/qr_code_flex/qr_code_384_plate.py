"""Flex protocol that paints a QR code onto a 384-well plate.

The QR pattern is supplied as a CSV runtime parameter. Each cell is read as
1 (black pixel -> dark dye) or 0 (white pixel -> water). The grid is centered
on the 16x24 plate. Use the companion ``image_to_csv.py`` helper to convert a
QR PNG/JPG into a CSV that this protocol accepts.
"""

from opentrons import protocol_api

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

metadata = {
    "protocolName": "QR Code on 384-Well Plate",
    "author": "Opentrons",
    "description": (
        "Renders a QR code on a 384-well plate using dark dye for black "
        "pixels and water for the white background. Upload a CSV (max "
        "16 rows x 24 cols) with 0/1 values; smaller grids are centered."
    ),
}

PLATE_ROWS = 16
PLATE_COLS = 24
ROW_LETTERS = "ABCDEFGHIJKLMNOP"
TRUTHY = {"1", "true", "True", "TRUE", "X", "x", "#", "B", "b"}


def add_parameters(parameters: protocol_api.ParameterContext) -> None:
    parameters.add_csv_file(
        variable_name="qr_csv",
        display_name="QR Code CSV",
        description=(
            "CSV of 0s and 1s. 1 = black pixel (dye), 0 = white pixel "
            "(water). Up to 16 rows x 24 columns. Smaller grids are "
            "centered on the plate."
        ),
    )
    parameters.add_float(
        variable_name="dispense_volume_ul",
        display_name="Volume per well",
        description="Volume dispensed into each well.",
        default=20.0,
        minimum=5.0,
        maximum=45.0,
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
            f"{PLATE_ROWS}x{PLATE_COLS} 384-well plate. Resize the image "
            f"before exporting (see image_to_csv.py)."
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


def _dispense_into(pipette, source, plate, wells, volume) -> None:
    if not wells:
        return
    targets = [plate[w] for w in wells]
    pipette.distribute(
        volume,
        source,
        targets,
        new_tip="once",
        disposal_volume=2,
        blow_out=True,
        blowout_location="source well",
    )


def run(protocol: protocol_api.ProtocolContext) -> None:
    grid = _parse_qr_grid(protocol.params.qr_csv.parse_as_csv())
    black_wells, white_wells = _grid_to_well_lists(grid)
    volume = float(protocol.params.dispense_volume_ul)
    fill_white = bool(protocol.params.fill_white_wells)

    protocol.comment(
        f"QR grid: {len(grid)} rows x {len(grid[0])} cols. "
        f"{len(black_wells)} dye wells, {len(white_wells)} water wells."
    )

    protocol.load_trash_bin("A3")
    plate = protocol.load_labware("corning_384_wellplate_112ul_flat", "C2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")
    tiprack_a = protocol.load_labware("opentrons_flex_96_filtertiprack_50ul", "B2")
    tiprack_b = protocol.load_labware("opentrons_flex_96_filtertiprack_50ul", "B3")

    pipette = protocol.load_instrument(
        "flex_1channel_50", "right", tip_racks=[tiprack_a, tiprack_b]
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

    plate_volume_ul = max(int(volume * (len(black_wells) + len(white_wells))), 1)
    dye_load = max(int(volume * len(black_wells) * 1.2) + 500, 500)
    water_load = max(int(volume * len(white_wells) * 1.2) + 500, 500)
    dye_source.load_liquid(liquid=dye_liquid, volume=min(dye_load, 14000))
    water_source.load_liquid(liquid=water_liquid, volume=min(water_load, 14000))

    if fill_white and white_wells:
        protocol.comment("Dispensing water into white-pixel wells...")
        _dispense_into(pipette, water_source, plate, white_wells, volume)

    if black_wells:
        protocol.comment("Dispensing dark dye into black-pixel wells...")
        _dispense_into(pipette, dye_source, plate, black_wells, volume)

    protocol.comment(
        f"QR pattern complete. Plate filled with {plate_volume_ul} uL total."
    )
