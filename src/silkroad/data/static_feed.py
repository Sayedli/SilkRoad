from __future__ import annotations

from typing import Iterable

import pandas as pd

from silkroad.data.base import MarketDataFeed, MarketSnapshot


class StaticFeed(MarketDataFeed):
    """In-memory data feed for tests and dry runs."""

    def __init__(self, symbol: str, interval: str, lookback: int, data: pd.DataFrame | None = None) -> None:
        super().__init__(symbol=symbol, interval=interval, lookback=lookback)
        if data is None:
            index = pd.date_range(end=pd.Timestamp.utcnow(), periods=lookback, freq=interval)
            self.data = pd.DataFrame(
                {
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1.0,
                },
                index=index,
            )
        else:
            self.data = data

    def load_history(self) -> pd.DataFrame:
        return self.data.copy()

    def stream(self) -> Iterable[MarketSnapshot]:
        yield MarketSnapshot(self.data.copy())
