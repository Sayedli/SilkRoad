from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Protocol

import pandas as pd


class MarketData(Protocol):
    def history(self) -> pd.DataFrame: ...


@dataclass
class Signal:
    side: str  # "buy", "sell", or "hold"
    size: float
    metadata: Dict[str, Any] | None = None


class Strategy(ABC):
    """Base strategy interface. Each strategy consumes market data and emits trading signals."""

    name: str

    @abstractmethod
    def prepare(self, data: pd.DataFrame) -> None:
        """Perform any preprocessing prior to generating signals."""

    @abstractmethod
    def generate_signal(self, data: MarketData) -> Signal:
        """Return the next trading signal based on the latest market snapshot."""
