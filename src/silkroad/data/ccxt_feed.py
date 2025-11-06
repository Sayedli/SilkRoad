from __future__ import annotations

import time
from typing import Iterable, List

import ccxt  # type: ignore
import pandas as pd

from silkroad.data.base import MarketDataFeed, MarketSnapshot


class CCXTFeed(MarketDataFeed):
    """CCXT-backed data feed for centralized exchanges like Binance or Coinbase."""

    def __init__(
        self,
        exchange_id: str,
        symbol: str,
        interval: str,
        lookback: int,
        poll_interval: float = 5.0,
        **client_kwargs,
    ) -> None:
        super().__init__(symbol=symbol, interval=interval, lookback=lookback)
        try:
            exchange_cls = getattr(ccxt, exchange_id)
        except AttributeError as exc:
            raise ValueError(f"Exchange '{exchange_id}' is not supported by ccxt.") from exc
        self.client: ccxt.Exchange = exchange_cls(**client_kwargs)
        self.poll_interval = poll_interval
        self._history_cache: pd.DataFrame | None = None

    def load_history(self) -> pd.DataFrame:
        limit = self.lookback
        ohlcv: List[List[float]] = self.client.fetch_ohlcv(self.symbol, timeframe=self.interval, limit=limit)
        data = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        data["timestamp"] = pd.to_datetime(data["timestamp"], unit="ms", utc=True)
        data.set_index("timestamp", inplace=True)
        data.sort_index(inplace=True)
        self._history_cache = data.copy()
        return data

    def stream(self) -> Iterable[MarketSnapshot]:
        if self._history_cache is None:
            history = self.load_history()
        else:
            history = self._history_cache.copy()

        while True:
            yield MarketSnapshot(history)
            time.sleep(self.poll_interval)
            latest = self.client.fetch_ohlcv(self.symbol, timeframe=self.interval, limit=2)
            last_row = pd.DataFrame(latest, columns=["timestamp", "open", "high", "low", "close", "volume"])
            last_row["timestamp"] = pd.to_datetime(last_row["timestamp"], unit="ms", utc=True)
            last_row.set_index("timestamp", inplace=True)
            history = pd.concat([history, last_row]).drop_duplicates()
            history = history.iloc[-self.lookback :]
            self._history_cache = history.copy()
