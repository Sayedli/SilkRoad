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
    order_size: float = 0.1

    def prepare(self, data: pd.DataFrame) -> None:
        data["fast_ma"] = data["close"].rolling(self.fast_window).mean()
        data["slow_ma"] = data["close"].rolling(self.slow_window).mean()
        data["spread"] = data["fast_ma"] - data["slow_ma"]

    def generate_signal(self, data) -> Signal:
        history = data.history()
        latest = history.iloc[-1]
        spread = latest.get("spread")
        price = float(latest.get("close")) if not pd.isna(latest.get("close")) else 0.0
        metadata = {"spread": spread, "price": price, "strategy": self.name}
        if spread is None or pd.isna(spread):
            metadata["reason"] = "spread-not-computed"
            return Signal(side="hold", size=0.0, metadata=metadata)
        if spread > self.threshold:
            return Signal(side="buy", size=self.order_size, metadata=metadata)
        if spread < -self.threshold:
            return Signal(side="sell", size=self.order_size, metadata=metadata)
        return Signal(side="hold", size=0.0, metadata=metadata)


register_strategy(MomentumStrategy.name)(MomentumStrategy)
