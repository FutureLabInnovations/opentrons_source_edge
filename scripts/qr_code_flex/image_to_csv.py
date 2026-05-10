"""Convert a QR-code image into a CSV that ``qr_code_384_plate.py`` accepts.

A 384-well plate is 16 rows x 24 columns, so the image is downsampled to fit.
Black pixels become ``1`` (dye), white pixels become ``0`` (water).

Usage:
    python image_to_csv.py path/to/qr.png [--out qr.csv] [--size 16x16]
                                          [--threshold 128] [--invert]

Defaults to a 16x16 grid (the QR is square; the protocol centers it on the
plate). Pass ``--size 16x24`` to stretch across the full plate.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.stderr.write(
        "Pillow is required: pip install Pillow\n"
    )
    raise


def parse_size(text: str) -> tuple[int, int]:
    rows_str, _, cols_str = text.lower().partition("x")
    rows = int(rows_str)
    cols = int(cols_str) if cols_str else rows
    if rows < 1 or cols < 1 or rows > 16 or cols > 24:
        raise argparse.ArgumentTypeError(
            "size must be ROWSxCOLS with rows<=16 and cols<=24"
        )
    return rows, cols


def image_to_grid(
    path: Path, rows: int, cols: int, threshold: int, invert: bool
) -> list[list[int]]:
    image = Image.open(path).convert("L")
    image = image.resize((cols, rows), Image.LANCZOS)
    pixels = list(image.getdata())

    grid: list[list[int]] = []
    for r in range(rows):
        row_pixels = pixels[r * cols : (r + 1) * cols]
        row = [1 if (p < threshold) ^ invert else 0 for p in row_pixels]
        grid.append(row)
    return grid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to QR image.")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output CSV path (default: <image>.csv).",
    )
    parser.add_argument(
        "--size", type=parse_size, default=(16, 16),
        help="Grid size as ROWSxCOLS, e.g. 16x16 or 16x24. Default 16x16.",
    )
    parser.add_argument(
        "--threshold", type=int, default=128,
        help="Pixel intensity below which a cell is considered black (0-255).",
    )
    parser.add_argument(
        "--invert", action="store_true",
        help="Treat light pixels as black (use for white-on-black QR codes).",
    )
    args = parser.parse_args()

    rows, cols = args.size
    grid = image_to_grid(args.image, rows, cols, args.threshold, args.invert)

    out_path = args.out or args.image.with_suffix(".csv")
    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerows(grid)

    preview = "\n".join(
        "".join("#" if v else "." for v in row) for row in grid
    )
    print(f"Wrote {out_path} ({rows}x{cols})")
    print(preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
