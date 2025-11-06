from __future__ import annotations

from typing import Any

from silkroad.data.base import MarketDataFeed
from silkroad.data.ccxt_feed import CCXTFeed
from silkroad.data.static_feed import StaticFeed


def build_data_feed(source: str, symbol: str, interval: str, lookback: int, **kwargs: Any) -> MarketDataFeed:
    if source.startswith("ccxt:"):
        exchange_id = source.split(":", maxsplit=1)[1]
        poll_interval = kwargs.pop("poll_interval", 5.0)
        return CCXTFeed(
            exchange_id=exchange_id,
            symbol=symbol,
            interval=interval,
            lookback=lookback,
            poll_interval=poll_interval,
            **kwargs,
        )
    if source == "static":
        data = kwargs.get("data")
        return StaticFeed(symbol=symbol, interval=interval, lookback=lookback, data=data)
    raise ValueError(f"Unsupported data source '{source}'.")
