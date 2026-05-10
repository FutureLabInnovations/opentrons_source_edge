# QR Code on a 384-Well Plate (Flex)

Paints a QR code onto a Corning 384-well flat plate using dark dye for black
pixels and water for the white background.

## Files

- `qr_code_384_plate.py` – Flex protocol. Upload to the Opentrons app or ODD.
- `image_to_csv.py` – converts a QR image (PNG/JPG) into the CSV the protocol
  consumes. Run locally; requires Pillow (`pip install Pillow`).
- `example_qr.csv` – a 16×19 sample pattern you can upload directly.

## Deck layout

| Slot | Item                                       |
| ---- | ------------------------------------------ |
| A3   | Trash bin                                  |
| B2   | Flex 50 µL filter tip rack                 |
| B3   | Flex 50 µL filter tip rack                 |
| C2   | Corning 384-well flat plate                |
| D2   | NEST 12-well 15 mL reservoir – A1: dye, A2: water |

Pipette: Flex 1-channel 50 µL on the right mount.

## Workflow

1. Convert your QR image to CSV: `python image_to_csv.py my_qr.png`.
   This downsamples the image to a 16×16 grid by default. Use
   `--size 16x24` to fill the full plate.
2. Upload `qr_code_384_plate.py` to the Opentrons app and attach the CSV when
   prompted by the runtime parameters.
3. Choose the per-well volume (default 20 µL) and whether to fill the white
   pixels with water (default on).
4. Load reservoir A1 with dark dye, A2 with water, then run.

## CSV format

- `1` = black pixel → dye
- `0` = white pixel → water
- Up to 16 rows × 24 columns. Smaller grids are centered automatically.
