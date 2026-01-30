#!/usr/bin/env python3
"""
OT-2 Calibration Verification and Export Tool
==============================================
Verifies calibration status, exports calibration data, and provides
backup/restore functionality.

Usage (on robot via SSH):
    python3 ot2_calibration_tool.py status          # Show calibration status
    python3 ot2_calibration_tool.py export          # Export all calibrations
    python3 ot2_calibration_tool.py backup          # Create full backup
    python3 ot2_calibration_tool.py verify          # Verify calibration integrity
    python3 ot2_calibration_tool.py restore FILE    # Restore from backup
"""

import asyncio
import argparse
import json
import shutil
import tarfile
import sys
import os
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Calibration paths
CAL_ROOT = Path("/data/opentrons")
ROBOT_CAL_DIR = CAL_ROOT / "robot"
TIP_LENGTH_DIR = CAL_ROOT / "tip_lengths"
PIPETTE_CAL_DIR = ROBOT_CAL_DIR / "pipettes"
DECK_CAL_FILE = ROBOT_CAL_DIR / "deck_calibration.json"


class CalibrationTool:
    """Tool for managing OT-2 calibration data."""

    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "calibrations": {},
            "warnings": [],
            "errors": []
        }

    def _read_json_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Safely read a JSON calibration file."""
        try:
            if filepath.exists():
                with open(filepath, "r") as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            self.results["errors"].append(f"Invalid JSON in {filepath}: {e}")
        except Exception as e:
            self.results["errors"].append(f"Error reading {filepath}: {e}")
        return None

    def _validate_attitude_matrix(self, matrix: List[List[float]]) -> Dict[str, Any]:
        """Validate a 3x3 attitude matrix."""
        result = {
            "valid": False,
            "is_identity": False,
            "determinant": None,
            "rank": None,
            "issues": []
        }

        try:
            arr = np.array(matrix)

            # Check shape
            if arr.shape != (3, 3):
                result["issues"].append(f"Invalid shape: {arr.shape}, expected (3, 3)")
                return result

            # Calculate properties
            det = np.linalg.det(arr)
            rank = np.linalg.matrix_rank(arr)
            identity = np.eye(3)

            result["determinant"] = float(det)
            result["rank"] = int(rank)
            result["is_identity"] = np.allclose(arr, identity)

            # Validate
            if rank != 3:
                result["issues"].append(f"Singular matrix (rank {rank})")
            elif abs(det) < 0.5 or abs(det) > 2.0:
                result["issues"].append(f"Unusual determinant: {det:.4f}")
            else:
                result["valid"] = True

        except Exception as e:
            result["issues"].append(f"Error: {e}")

        return result

    def _validate_offset(self, offset: List[float], name: str) -> Dict[str, Any]:
        """Validate a calibration offset."""
        result = {
            "valid": False,
            "magnitude": None,
            "issues": []
        }

        try:
            if len(offset) != 3:
                result["issues"].append(f"Invalid offset length: {len(offset)}")
                return result

            magnitude = np.sqrt(sum(x**2 for x in offset))
            result["magnitude"] = float(magnitude)

            # Check for reasonable values
            if magnitude > 10.0:  # More than 10mm offset is suspicious
                result["issues"].append(f"Large offset magnitude: {magnitude:.2f}mm")
            elif any(abs(x) > 5.0 for x in offset):
                result["issues"].append(f"Large individual offset value")

            if not result["issues"]:
                result["valid"] = True

        except Exception as e:
            result["issues"].append(f"Error: {e}")

        return result

    def get_deck_calibration(self) -> Dict[str, Any]:
        """Get and validate deck calibration."""
        result = {
            "exists": False,
            "data": None,
            "validation": None
        }

        data = self._read_json_file(DECK_CAL_FILE)
        if data:
            result["exists"] = True
            result["data"] = data

            # Validate attitude matrix
            if "attitude" in data:
                result["validation"] = self._validate_attitude_matrix(data["attitude"])

        return result

    def get_pipette_calibrations(self) -> Dict[str, Any]:
        """Get all pipette offset calibrations."""
        result = {
            "left": {},
            "right": {}
        }

        for mount in ["left", "right"]:
            mount_dir = PIPETTE_CAL_DIR / mount
            if mount_dir.exists():
                for cal_file in mount_dir.glob("*.json"):
                    pipette_id = cal_file.stem
                    data = self._read_json_file(cal_file)
                    if data:
                        validation = None
                        if "offset" in data:
                            validation = self._validate_offset(data["offset"], pipette_id)
                        result[mount][pipette_id] = {
                            "data": data,
                            "validation": validation
                        }

        return result

    def get_tip_length_calibrations(self) -> Dict[str, Any]:
        """Get all tip length calibrations."""
        result = {}

        if TIP_LENGTH_DIR.exists():
            for cal_file in TIP_LENGTH_DIR.glob("*.json"):
                pipette_id = cal_file.stem
                data = self._read_json_file(cal_file)
                if data:
                    result[pipette_id] = {
                        "data": data,
                        "tiprack_count": len(data) if isinstance(data, dict) else 0
                    }

        return result

    def show_status(self) -> Dict[str, Any]:
        """Display comprehensive calibration status."""
        print("\n" + "=" * 70)
        print("OT-2 CALIBRATION STATUS")
        print("=" * 70)

        # Deck calibration
        print("\n" + "-" * 40)
        print("DECK CALIBRATION")
        print("-" * 40)

        deck_cal = self.get_deck_calibration()
        self.results["calibrations"]["deck"] = deck_cal

        if not deck_cal["exists"]:
            print("  Status: NOT CALIBRATED")
            self.results["warnings"].append("Deck not calibrated")
        else:
            data = deck_cal["data"]
            print(f"  Status: CALIBRATED")
            print(f"  Source: {data.get('source', 'unknown')}")
            print(f"  Last Modified: {data.get('last_modified', 'unknown')}")
            print(f"  Pipette Used: {data.get('pipette_calibrated_with', 'unknown')}")

            if "attitude" in data:
                print(f"  Attitude Matrix:")
                for row in data["attitude"]:
                    print(f"    {row}")

            validation = deck_cal["validation"]
            if validation:
                print(f"\n  Validation:")
                print(f"    Valid: {validation['valid']}")
                print(f"    Identity: {validation['is_identity']}")
                print(f"    Determinant: {validation['determinant']:.6f}")
                print(f"    Rank: {validation['rank']}")
                if validation["issues"]:
                    print(f"    Issues: {validation['issues']}")
                    self.results["warnings"].extend(validation["issues"])

        # Pipette calibrations
        print("\n" + "-" * 40)
        print("PIPETTE OFFSET CALIBRATIONS")
        print("-" * 40)

        pipette_cals = self.get_pipette_calibrations()
        self.results["calibrations"]["pipettes"] = pipette_cals

        for mount in ["left", "right"]:
            print(f"\n  {mount.upper()} MOUNT:")
            if not pipette_cals[mount]:
                print("    No calibrations found")
            else:
                for pip_id, cal_info in pipette_cals[mount].items():
                    data = cal_info["data"]
                    offset = data.get("offset", [0, 0, 0])
                    print(f"    Pipette: {pip_id}")
                    print(f"      Offset: [{offset[0]:.4f}, {offset[1]:.4f}, {offset[2]:.4f}]")
                    print(f"      Source: {data.get('source', 'unknown')}")
                    print(f"      Last Modified: {data.get('last_modified', 'unknown')}")

                    validation = cal_info["validation"]
                    if validation and not validation["valid"]:
                        print(f"      WARNING: {validation['issues']}")
                        self.results["warnings"].append(f"Pipette {pip_id}: {validation['issues']}")

        # Tip length calibrations
        print("\n" + "-" * 40)
        print("TIP LENGTH CALIBRATIONS")
        print("-" * 40)

        tip_cals = self.get_tip_length_calibrations()
        self.results["calibrations"]["tip_lengths"] = tip_cals

        if not tip_cals:
            print("  No tip length calibrations found")
        else:
            for pip_id, cal_info in tip_cals.items():
                print(f"\n  Pipette: {pip_id}")
                print(f"    Tipracks calibrated: {cal_info['tiprack_count']}")

                if isinstance(cal_info["data"], dict):
                    for tiprack_uri, tip_data in cal_info["data"].items():
                        if isinstance(tip_data, dict):
                            print(f"      {tiprack_uri}:")
                            print(f"        Length: {tip_data.get('tipLength', 'unknown')}mm")
                            print(f"        Source: {tip_data.get('source', 'unknown')}")

        # Summary
        print("\n" + "-" * 40)
        print("SUMMARY")
        print("-" * 40)

        total_pipette_cals = sum(len(pipette_cals[m]) for m in ["left", "right"])
        total_tip_cals = len(tip_cals)

        print(f"  Deck calibration: {'YES' if deck_cal['exists'] else 'NO'}")
        print(f"  Pipette calibrations: {total_pipette_cals}")
        print(f"  Tip length calibrations: {total_tip_cals}")
        print(f"  Warnings: {len(self.results['warnings'])}")
        print(f"  Errors: {len(self.results['errors'])}")

        if self.results["warnings"]:
            print("\n  Warnings:")
            for w in self.results["warnings"]:
                print(f"    - {w}")

        if self.results["errors"]:
            print("\n  Errors:")
            for e in self.results["errors"]:
                print(f"    - {e}")

        print("=" * 70)

        return self.results

    def export_calibrations(self, output_dir: Optional[str] = None) -> str:
        """Export all calibration data to JSON files."""
        if output_dir is None:
            output_dir = f"/data/calibration_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 60)
        print(f"EXPORTING CALIBRATIONS TO: {output_path}")
        print("=" * 60)

        exported_files = []

        # Export deck calibration
        if DECK_CAL_FILE.exists():
            dest = output_path / "deck_calibration.json"
            shutil.copy(DECK_CAL_FILE, dest)
            exported_files.append(str(dest))
            print(f"  Exported: deck_calibration.json")

        # Export pipette calibrations
        for mount in ["left", "right"]:
            mount_dir = PIPETTE_CAL_DIR / mount
            if mount_dir.exists():
                dest_dir = output_path / "pipettes" / mount
                dest_dir.mkdir(parents=True, exist_ok=True)
                for cal_file in mount_dir.glob("*.json"):
                    dest = dest_dir / cal_file.name
                    shutil.copy(cal_file, dest)
                    exported_files.append(str(dest))
                    print(f"  Exported: pipettes/{mount}/{cal_file.name}")

        # Export tip lengths
        if TIP_LENGTH_DIR.exists():
            dest_dir = output_path / "tip_lengths"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for cal_file in TIP_LENGTH_DIR.glob("*.json"):
                dest = dest_dir / cal_file.name
                shutil.copy(cal_file, dest)
                exported_files.append(str(dest))
                print(f"  Exported: tip_lengths/{cal_file.name}")

        # Write manifest
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "robot_type": "OT-2",
            "files": exported_files
        }
        manifest_file = output_path / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  Exported: manifest.json")

        print(f"\n  Total files exported: {len(exported_files)}")
        print(f"  Export location: {output_path}")

        return str(output_path)

    def create_backup(self, output_file: Optional[str] = None) -> str:
        """Create a compressed backup of all calibration data."""
        if output_file is None:
            output_file = f"/data/calibration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"

        print("\n" + "=" * 60)
        print(f"CREATING BACKUP: {output_file}")
        print("=" * 60)

        try:
            with tarfile.open(output_file, "w:gz") as tar:
                # Add robot calibration directory
                if ROBOT_CAL_DIR.exists():
                    tar.add(ROBOT_CAL_DIR, arcname="robot")
                    print(f"  Added: robot/")

                # Add tip lengths
                if TIP_LENGTH_DIR.exists():
                    tar.add(TIP_LENGTH_DIR, arcname="tip_lengths")
                    print(f"  Added: tip_lengths/")

                # Add metadata
                metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "robot_type": "OT-2",
                    "backup_version": "1.0"
                }
                metadata_str = json.dumps(metadata, indent=2)

                import io
                metadata_bytes = metadata_str.encode('utf-8')
                tarinfo = tarfile.TarInfo(name="metadata.json")
                tarinfo.size = len(metadata_bytes)
                tar.addfile(tarinfo, io.BytesIO(metadata_bytes))
                print(f"  Added: metadata.json")

            file_size = os.path.getsize(output_file)
            print(f"\n  Backup created: {output_file}")
            print(f"  Size: {file_size / 1024:.2f} KB")

        except Exception as e:
            print(f"ERROR: Backup failed: {e}")
            self.results["errors"].append(f"Backup failed: {e}")
            return ""

        return output_file

    def restore_backup(self, backup_file: str, dry_run: bool = True) -> bool:
        """Restore calibration data from backup."""
        print("\n" + "=" * 60)
        print(f"RESTORING FROM: {backup_file}")
        if dry_run:
            print("  (DRY RUN - no changes will be made)")
        print("=" * 60)

        if not os.path.exists(backup_file):
            print(f"ERROR: Backup file not found: {backup_file}")
            return False

        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                members = tar.getmembers()
                print(f"\n  Contents ({len(members)} files):")

                for member in members:
                    print(f"    {member.name}")

                if not dry_run:
                    confirm = input("\n  Proceed with restore? (yes/no): ").strip().lower()
                    if confirm != "yes":
                        print("  Restore cancelled")
                        return False

                    # Extract to calibration directory
                    tar.extractall(CAL_ROOT)
                    print("\n  Restore complete!")
                else:
                    print("\n  Run with --confirm to actually restore")

        except Exception as e:
            print(f"ERROR: Restore failed: {e}")
            self.results["errors"].append(f"Restore failed: {e}")
            return False

        return True

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify integrity of all calibration files."""
        print("\n" + "=" * 60)
        print("CALIBRATION INTEGRITY VERIFICATION")
        print("=" * 60)

        issues = []

        # Check deck calibration
        print("\n  Checking deck calibration...")
        deck_cal = self.get_deck_calibration()
        if deck_cal["exists"]:
            validation = deck_cal["validation"]
            if validation and not validation["valid"]:
                issues.append(f"Deck calibration: {validation['issues']}")
                print(f"    ISSUE: {validation['issues']}")
            else:
                print("    OK")
        else:
            print("    NOT FOUND (optional)")

        # Check pipette calibrations
        print("\n  Checking pipette calibrations...")
        pipette_cals = self.get_pipette_calibrations()
        for mount in ["left", "right"]:
            for pip_id, cal_info in pipette_cals[mount].items():
                validation = cal_info["validation"]
                if validation and not validation["valid"]:
                    issues.append(f"Pipette {pip_id} ({mount}): {validation['issues']}")
                    print(f"    {pip_id} ({mount}): ISSUE - {validation['issues']}")
                else:
                    print(f"    {pip_id} ({mount}): OK")

        if not any(pipette_cals[m] for m in ["left", "right"]):
            print("    No pipette calibrations found")

        # Check tip length calibrations
        print("\n  Checking tip length calibrations...")
        tip_cals = self.get_tip_length_calibrations()
        for pip_id, cal_info in tip_cals.items():
            data = cal_info["data"]
            if isinstance(data, dict):
                for tiprack, tip_data in data.items():
                    if isinstance(tip_data, dict):
                        tip_length = tip_data.get("tipLength")
                        if tip_length is not None:
                            if tip_length < 20 or tip_length > 100:
                                issues.append(f"Tip length for {pip_id}/{tiprack}: unusual value {tip_length}mm")
                                print(f"    {pip_id}/{tiprack}: ISSUE - unusual length {tip_length}mm")
                            else:
                                print(f"    {pip_id}/{tiprack}: OK ({tip_length}mm)")

        if not tip_cals:
            print("    No tip length calibrations found")

        # Summary
        print("\n" + "-" * 40)
        print("VERIFICATION SUMMARY")
        print("-" * 40)

        if issues:
            print(f"  Issues found: {len(issues)}")
            for issue in issues:
                print(f"    - {issue}")
            self.results["warnings"].extend(issues)
        else:
            print("  All calibrations valid")

        print("=" * 60)

        return {"valid": len(issues) == 0, "issues": issues}


def main():
    parser = argparse.ArgumentParser(description="OT-2 Calibration Tool")
    parser.add_argument("action", choices=["status", "export", "backup", "verify", "restore"],
                        help="Action to perform")
    parser.add_argument("--output", "-o", help="Output file/directory path")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm restore action (skip dry run)")
    parser.add_argument("file", nargs="?", help="Backup file for restore action")

    args = parser.parse_args()

    tool = CalibrationTool()

    if args.action == "status":
        tool.show_status()
    elif args.action == "export":
        tool.export_calibrations(args.output)
    elif args.action == "backup":
        tool.create_backup(args.output)
    elif args.action == "verify":
        result = tool.verify_integrity()
        return 0 if result["valid"] else 1
    elif args.action == "restore":
        if not args.file:
            print("ERROR: Backup file required for restore action")
            return 1
        dry_run = not args.confirm
        tool.restore_backup(args.file, dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
