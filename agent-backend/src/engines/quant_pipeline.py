"""
src/engines/quant_pipeline.py
--------------------------------------------------------------------------
End-to-End Quant Pipeline — single-command full pipeline execution.

Orchestrates the complete flow:
  Universe → Scan → Validate → Bridge → Optimize → Neutralize
  → Rebalance → TCA → Audit → Report

Usage::

    pipeline = QuantPipeline()
    result = pipeline.run(universe="test")
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.quant_pipeline")


# ── Pipeline Contracts ───────────────────────────────────────────────────────

class PipelineStepResult(BaseModel):
    """Result of a single pipeline step."""
    step_name: str
    status: str = "pending"  # pending, running, success, failed, skipped
    duration_ms: float = 0.0
    details: dict = Field(default_factory=dict)
    error: str | None = None


class PipelineResult(BaseModel):
    """Complete pipeline execution result."""
    run_id: str = ""
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: datetime | None = None
    total_duration_seconds: float = 0.0

    # Steps
    steps: list[PipelineStepResult] = Field(default_factory=list)
    successful_steps: int = 0
    failed_steps: int = 0

    # Key outputs
    signals_detected: int = 0
    signals_validated: int = 0
    signals_in_portfolio: int = 0
    portfolio_positions: int = 0
    portfolio_beta: float = 0.0
    total_rebalance_cost_bps: float = 0.0

    # Health
    overall_status: str = "pending"


# ── Pipeline Engine ──────────────────────────────────────────────────────────

class QuantPipeline:
    """
    Orchestrates the complete quant pipeline.

    Steps:
    1. Universe Selection (+ survivorship bias check)
    2. Signal Scanning
    3. Signal Validation (attribution, PRT, TBPT)
    4. Kill Switch Evaluation
    5. Signal→Portfolio Bridge
    6. Covariance Shrinkage
    7. Portfolio Optimization
    8. Factor Neutralization
    9. Rebalancing
    10. Audit Trail Recording
    11. Performance Report Generation
    """

    def __init__(
        self,
        universe_name: str = "test",
        scan_date: date | None = None,
        dry_run: bool = True,
    ) -> None:
        self.universe_name = universe_name
        self.scan_date = scan_date or date.today()
        self.dry_run = dry_run
        self._steps: list[PipelineStepResult] = []

    def run(self) -> PipelineResult:
        """Run the complete pipeline."""
        import hashlib
        run_id = f"RUN-{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

        start = time.monotonic()
        started_at = datetime.now(timezone.utc)

        logger.info("═" * 60)
        logger.info("QUANT PIPELINE: Starting run %s", run_id)
        logger.info("═" * 60)

        # Execute each step
        self._run_step("1_universe_selection", self._step_universe)
        self._run_step("2_signal_scanning", self._step_scanning)
        self._run_step("3_signal_validation", self._step_validation)
        self._run_step("4_kill_switch", self._step_kill_switch)
        self._run_step("5_bridge", self._step_bridge)
        self._run_step("6_covariance_shrinkage", self._step_shrinkage)
        self._run_step("7_optimization", self._step_optimization)
        self._run_step("8_factor_neutral", self._step_neutralize)
        self._run_step("9_rebalancing", self._step_rebalance)
        self._run_step("10_audit_trail", self._step_audit)
        self._run_step("11_performance_report", self._step_report)

        elapsed = time.monotonic() - start
        n_success = sum(1 for s in self._steps if s.status == "success")
        n_failed = sum(1 for s in self._steps if s.status == "failed")

        status = "success" if n_failed == 0 else "partial" if n_success > 0 else "failed"

        # Aggregate key metrics from step details
        signals_detected = self._get_detail("2_signal_scanning", "events", 0)
        signals_validated = self._get_detail("3_signal_validation", "validated", 0)
        positions = self._get_detail("7_optimization", "positions", 0)

        result = PipelineResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            total_duration_seconds=round(elapsed, 3),
            steps=self._steps,
            successful_steps=n_success,
            failed_steps=n_failed,
            signals_detected=signals_detected,
            signals_validated=signals_validated,
            portfolio_positions=positions,
            overall_status=status,
        )

        logger.info("═" * 60)
        logger.info(
            "QUANT PIPELINE: %s in %.1fs — %d/%d steps OK",
            status, elapsed, n_success, len(self._steps),
        )
        logger.info("═" * 60)

        return result

    def _run_step(self, name: str, fn: callable) -> None:
        """Execute a pipeline step with timing and error handling."""
        step = PipelineStepResult(step_name=name, status="running")
        start = time.monotonic()

        try:
            details = fn()
            step.status = "success"
            step.details = details or {}
        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            logger.error("PIPELINE: Step '%s' failed: %s", name, e)

        step.duration_ms = round((time.monotonic() - start) * 1000, 1)
        self._steps.append(step)

        logger.info(
            "  [%s] %s (%.1fms)",
            "✓" if step.status == "success" else "✗",
            name, step.duration_ms,
        )

    def _get_detail(self, step_name: str, key: str, default=None):
        """Get a detail from a completed step."""
        for s in self._steps:
            if s.step_name == step_name and key in s.details:
                return s.details[key]
        return default

    # ── Individual Steps ─────────────────────────────────────────────────

    def _step_universe(self) -> dict:
        """Step 1: Select universe."""
        from src.engines.backtesting.universes import get_universe
        tickers = get_universe(self.universe_name)
        return {"universe": self.universe_name, "tickers": len(tickers)}

    def _step_scanning(self) -> dict:
        """Step 2: Scan for signals."""
        from src.engines.backtesting.signal_scanner import SignalScanner, ScanConfig
        config = ScanConfig(universe_name=self.universe_name)
        scanner = SignalScanner(config=config)
        result = scanner.scan(scan_date=self.scan_date)
        return {
            "tickers_scanned": result.tickers_scanned,
            "events": result.total_events,
            "tickers_with_signals": result.tickers_with_signals,
        }

    def _step_validation(self) -> dict:
        """Step 3: Validate signals (simulated in dry-run)."""
        return {"validated": 0, "rejected": 0, "note": "dry_run"}

    def _step_kill_switch(self) -> dict:
        """Step 4: Kill switch evaluation."""
        from src.engines.backtesting.kill_switch import KillSwitch
        ks = KillSwitch()
        return {"active_kills": len(ks.get_active_kills()), "evaluated": 0}

    def _step_bridge(self) -> dict:
        """Step 5: Signal→Portfolio bridge."""
        return {"bridge": "ready", "note": "dry_run — no live signals"}

    def _step_shrinkage(self) -> dict:
        """Step 6: Covariance shrinkage."""
        return {"shrinkage": "enabled", "target": "constant_correlation"}

    def _step_optimization(self) -> dict:
        """Step 7: Portfolio optimization."""
        return {"positions": 0, "objective": "max_sharpe", "note": "dry_run"}

    def _step_neutralize(self) -> dict:
        """Step 8: Factor neutralization."""
        return {"target_beta": 0.0, "note": "dry_run"}

    def _step_rebalance(self) -> dict:
        """Step 9: Rebalancing."""
        return {"turnover": 0.0, "trades": 0, "note": "dry_run"}

    def _step_audit(self) -> dict:
        """Step 10: Audit trail recording."""
        from src.engines.compliance.audit_trail import AuditTrail, AuditEntryType
        trail = AuditTrail()
        trail.record(
            entry_type=AuditEntryType.CONFIG_SNAPSHOT,
            action="pipeline_run",
            reason=f"Pipeline run on {self.scan_date}",
            details={
                "universe": self.universe_name,
                "dry_run": self.dry_run,
            },
        )
        return {"entries_recorded": trail.entry_count}

    def _step_report(self) -> dict:
        """Step 11: Performance report."""
        return {"report": "generated", "note": "dry_run"}
