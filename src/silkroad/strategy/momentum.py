from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .base import Signal, Strategy
from .registry import register_strategy


@dataclass
class MomentumStrategy(Strategy):
    name: str = "momentum"
    fast_window: int = 20
    slow_window: int = 50
    threshold: float = 0.0

    def prepare(self, data: pd.DataFrame) -> None:
        data["fast_ma"] = data["close"].rolling(self.fast_window).mean()
        data["slow_ma"] = data["close"].rolling(self.slow_window).mean()
        data["spread"] = data["fast_ma"] - data["slow_ma"]

    def generate_signal(self, data) -> Signal:
        history = data.history()
        latest = history.iloc[-1]
        spread = latest.get("spread")
        if spread is None:
            return Signal(side="hold", size=0.0, metadata={"reason": "spread-not-computed"})

        if spread > self.threshold:
            return Signal(side="buy", size=1.0, metadata={"spread": spread})
        if spread < -self.threshold:
            return Signal(side="sell", size=1.0, metadata={"spread": spread})
        return Signal(side="hold", size=0.0, metadata={"spread": spread})


register_strategy(MomentumStrategy.name)(MomentumStrategy)
