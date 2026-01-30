"""
Shared utilities for OT-2 service diagnostics.
"""

import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum

# Check if running on robot
try:
    from opentrons.hardware_control import API
    from opentrons.hardware_control.types import Axis
    from opentrons.types import Mount, Point
    import numpy as np
    ON_ROBOT = True
except ImportError:
    ON_ROBOT = False
    API = None
    Axis = None
    Mount = None
    Point = None


class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str = ""
    data: Dict[str, Any] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "data": self.data or {},
            "duration_seconds": round(self.duration_seconds, 2)
        }

    def __repr__(self):
        return f"[{self.status.value}] {self.name}: {self.message}"


def run_shell(cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def print_header(title: str):
    print("=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(result: TestResult):
    symbols = {
        TestStatus.PASS: "[PASS]",
        TestStatus.FAIL: "[FAIL]",
        TestStatus.WARNING: "[WARN]",
        TestStatus.SKIPPED: "[SKIP]",
        TestStatus.ERROR: "[ERR ]"
    }
    print(f"  {symbols.get(result.status, '[??]')} {result.name}")
    if result.message:
        print(f"       -> {result.message}")
