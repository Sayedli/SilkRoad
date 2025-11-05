from __future__ import annotations

from dataclasses import dataclass

from silkroad.strategy.base import Signal


@dataclass
class RiskLimits:
    max_position_fraction: float = 0.1
    max_drawdown: float = 0.2
    stop_loss_pct: float = 0.05


class RiskManager:
    """Applies simple risk constraints prior to executing trades."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def validate(self, signal: Signal) -> bool:
        # Placeholder for more sophisticated sizing logic.
        if signal.size > self.limits.max_position_fraction:
            return False
        return True
