from __future__ import annotations

from typing import Any

from silkroad.data.base import MarketDataFeed
from silkroad.data.ccxt_feed import CCXTFeed


def build_data_feed(source: str, symbol: str, interval: str, lookback: int, **kwargs: Any) -> MarketDataFeed:
    if source.startswith("ccxt:"):
        exchange_id = source.split(":", maxsplit=1)[1]
        return CCXTFeed(
            exchange_id=exchange_id,
            symbol=symbol,
            interval=interval,
            lookback=lookback,
            poll_interval=kwargs.get("poll_interval", 5.0),
        )
    raise ValueError(f"Unsupported data source '{source}'.")
