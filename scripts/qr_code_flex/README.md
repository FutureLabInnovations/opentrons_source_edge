# QR Code on a Flex Plate

Paint a QR code (or any binary pattern) onto a 384- or 96-well plate using
dark dye for black pixels and water for the white background.

## Files

- `qr_code_384_plate.py` – Flex protocol for a Corning 384-well flat plate
  (16 × 24 grid). Optional 8-channel water flood for speed.
- `qr_code_96_plate.py` – Flex protocol for a NEST 96-well flat plate
  (8 × 12 grid). Detects fully-black/white columns and uses the 8-channel
  pipette for them automatically.
- `image_to_csv.py` – converts a QR image (PNG/JPG) into the CSV the
  protocols consume. Run locally; needs Pillow (`pip install Pillow`).
- `example_qr.csv` – a 16 × 19 sample pattern for the 384 protocol.

## Picking a plate

| Plate    | Grid    | Real QR support                                |
| -------- | ------- | ---------------------------------------------- |
| 384-well | 16 × 24 | Micro QR up to M3 (15 × 15) is scannable; full QR ≥ 21 × 21 is downsampled (visual only) |
| 96-well  | 8 × 12  | Larger, more visible wells; pixel-art glyphs only |

Opentrons does not ship a 1536-well labware definition, so 21 × 21 (Version 1)
QR codes can't be rendered at 1 module = 1 well on a stock plate.

## Workflow

1. Convert your QR image to CSV:
   - 384-well: `python image_to_csv.py my_qr.png` (default 16×16)
   - 384-well full bleed: `python image_to_csv.py my_qr.png --size 16x24`
   - 96-well: `python image_to_csv.py my_qr.png --size 8x12`
2. Upload the chosen protocol to the Opentrons app and attach the CSV when
   prompted by the runtime parameters.
3. Set per-well volume and toggle "Fill white wells with water". On the
   384 protocol, optionally enable "Fast water fill (8-channel)".
4. Load reservoir A1 with dark dye, A2 with water, then run.

## Deck layout — 384-well protocol

| Slot | Item                                              |
| ---- | ------------------------------------------------- |
| A3   | Trash bin                                         |
| B2   | Flex 50 µL filter tip rack                        |
| B3   | Flex 50 µL filter tip rack                        |
| C2   | Corning 384-well flat plate                       |
| D2   | NEST 12-well 15 mL reservoir – A1: dye, A2: water |

Pipettes: Flex 1-channel 50 µL on the right. Flex 8-channel 50 µL on the
left is required only when "Fast water fill" is enabled.

## Deck layout — 96-well protocol

| Slot | Item                                              |
| ---- | ------------------------------------------------- |
| A3   | Trash bin                                         |
| B2   | Flex 200 µL filter tip rack (8-channel)           |
| B3   | Flex 200 µL filter tip rack (1-channel)           |
| C2   | NEST 96-well flat plate                           |
| D2   | NEST 12-well 15 mL reservoir – A1: dye, A2: water |

Pipettes: Flex 1-channel 1000 µL on the right, Flex 8-channel 1000 µL on
the left.

## CSV format

- `1` = black pixel → dye
- `0` = white pixel → water
- Up to 16 × 24 (384) or 8 × 12 (96). Smaller grids are centered.
