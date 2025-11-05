from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class MarketSnapshot:
    """Wrapper exposing a moving history window to strategy objects."""

    _history: pd.DataFrame

    def history(self) -> pd.DataFrame:
        return self._history


class MarketDataFeed(ABC):
    symbol: str
    interval: str
    lookback: int

    def __init__(self, symbol: str, interval: str, lookback: int) -> None:
        self.symbol = symbol
        self.interval = interval
        self.lookback = lookback

    @abstractmethod
    def load_history(self) -> pd.DataFrame:
        """Return a DataFrame with historical OHLCV data."""

    @abstractmethod
    def stream(self) -> Iterable[MarketSnapshot]:
        """Yield new market snapshots in chronological order."""
