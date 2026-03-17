"""
src/engines/backtesting/calibration_store.py
--------------------------------------------------------------------------
Versioned config store for calibrated signal configurations.

Saves/loads calibration versions as JSON files under configs/calibrations/.
Provides methods to apply a calibrated config to the live SignalRegistry.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from src.engines.alpha_signals.registry import SignalRegistry
from src.engines.backtesting.calibration_models import (
    CalibrationVersion,
    CalibratedSignalConfig,
)

logger = logging.getLogger("365advisers.calibrator.store")

# Default storage directory
_DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "calibrations"


class CalibrationStore:
    """
    JSON-based versioned config store.

    Usage::

        store = CalibrationStore()
        store.save_version(version)
        latest = store.load_latest()
        store.apply_to_registry(latest, registry)
    """

    def __init__(self, store_dir: Path | str | None = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else _DEFAULT_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save_version(self, version: CalibrationVersion) -> Path:
        """Save a calibration version to disk."""
        filename = f"signal_engine_{version.version}.json"
        path = self.store_dir / filename

        data = version.model_dump(mode="json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"CALIBRATION-STORE: Saved {version.version} to {path}")
        return path

    def load_version(self, tag: str) -> CalibrationVersion | None:
        """Load a specific version by tag (e.g., 'v2.1')."""
        filename = f"signal_engine_{tag}.json"
        path = self.store_dir / filename

        if not path.exists():
            logger.warning(f"CALIBRATION-STORE: Version {tag} not found at {path}")
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CalibrationVersion(**data)

    def load_latest(self) -> CalibrationVersion | None:
        """Load the most recently saved version."""
        versions = self.get_history()
        if not versions:
            return None
        return self.load_version(versions[-1][0])

    def get_history(self) -> list[tuple[str, str]]:
        """
        List all saved versions with timestamps.

        Returns
        -------
        list[tuple[str, str]]
            [(version_tag, created_at), ...] sorted by creation time.
        """
        history = []
        for path in sorted(self.store_dir.glob("signal_engine_v*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tag = data.get("version", path.stem.replace("signal_engine_", ""))
                created = data.get("created_at", "unknown")
                history.append((tag, str(created)))
            except Exception:
                continue

        return history

    def get_next_version_tag(self) -> str:
        """Generate the next version tag (e.g., v1.0, v1.1, v2.0)."""
        history = self.get_history()
        if not history:
            return "v1.0"

        latest_tag = history[-1][0]
        # Parse version
        try:
            parts = latest_tag.lstrip("v").split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return f"v{major}.{minor + 1}"
        except (ValueError, IndexError):
            return "v1.0"

    def apply_to_registry(
        self,
        version: CalibrationVersion,
        registry: SignalRegistry,
    ) -> int:
        """
        Apply calibrated configs to the live SignalRegistry.

        Returns the number of signals updated.
        """
        updated = 0

        for config in version.signal_configs:
            signal_def = registry.get(config.signal_id)
            if signal_def is None:
                continue

            # Update weight
            if config.weight != signal_def.weight:
                signal_def.weight = config.weight
                updated += 1

            # Update threshold if provided and different
            if config.threshold is not None and config.threshold != signal_def.threshold:
                signal_def.threshold = config.threshold

            # Update strong threshold
            if config.strong_threshold is not None:
                signal_def.strong_threshold = config.strong_threshold

            # Update enabled status
            signal_def.enabled = config.enabled

        logger.info(f"CALIBRATION-STORE: Applied {version.version} to registry ({updated} signals updated)")
        return updated

    def snapshot_registry(self, registry: SignalRegistry) -> list[CalibratedSignalConfig]:
        """Export current registry state as a list of CalibratedSignalConfig."""
        configs: list[CalibratedSignalConfig] = []
        for signal_def in registry.get_all():
            configs.append(CalibratedSignalConfig(
                signal_id=signal_def.id,
                weight=signal_def.weight,
                threshold=signal_def.threshold,
                strong_threshold=signal_def.strong_threshold,
                enabled=signal_def.enabled,
            ))
        return configs
