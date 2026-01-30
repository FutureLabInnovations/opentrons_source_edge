"""
Flex Module Diagnostics - Logging Utilities

Provides timestamped logging for diagnostic operations.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class DiagnosticLogger:
    """Logger for diagnostic operations with timestamps and structured output."""

    def __init__(
        self,
        name: str = "FlexDiagnostics",
        log_file: Optional[Path] = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_format = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(file_level)
            file_format = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def test_start(self, test_name: str) -> datetime:
        """Log test start and return start time."""
        start_time = datetime.now()
        self.info(f"▶ Starting test: {test_name}")
        return start_time

    def test_pass(self, test_name: str, message: str = "") -> None:
        """Log test passed."""
        msg = f"✓ PASS: {test_name}"
        if message:
            msg += f" - {message}"
        self.info(msg)

    def test_fail(self, test_name: str, message: str = "") -> None:
        """Log test failed."""
        msg = f"✗ FAIL: {test_name}"
        if message:
            msg += f" - {message}"
        self.error(msg)

    def test_skip(self, test_name: str, reason: str = "") -> None:
        """Log test skipped."""
        msg = f"⊘ SKIP: {test_name}"
        if reason:
            msg += f" - {reason}"
        self.warning(msg)

    def test_warning(self, test_name: str, message: str = "") -> None:
        """Log test warning."""
        msg = f"⚠ WARNING: {test_name}"
        if message:
            msg += f" - {message}"
        self.warning(msg)

    def module_start(self, module_name: str) -> None:
        """Log start of module diagnostics."""
        self.info("=" * 60)
        self.info(f"MODULE DIAGNOSTICS: {module_name}")
        self.info("=" * 60)

    def module_end(self, module_name: str, passed: int, failed: int) -> None:
        """Log end of module diagnostics."""
        total = passed + failed
        self.info("-" * 40)
        self.info(f"Module {module_name}: {passed}/{total} tests passed")
        self.info("-" * 40)

    def section(self, title: str) -> None:
        """Log a section header."""
        self.info(f"\n--- {title} ---")


# Default logger instance
default_logger = DiagnosticLogger()
