from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from silkroad.analytics import AnalyticsStore
    from silkroad.data import MarketDataFeed
    from silkroad.monitoring.notifications import Notifier
    from silkroad.risk.manager import RiskManager

from silkroad.strategy.base import Signal, Strategy


class BrokerClient(Protocol):
    def submit_order(self, symbol: str, side: str, quantity: float) -> None: ...


class ExecutionEngine(ABC):
    """Base execution engine for routing strategy signals to broker clients."""

    symbol: str

    def __init__(
        self,
        symbol: str,
        data_feed: Optional["MarketDataFeed"] = None,
        risk_manager: Optional["RiskManager"] = None,
        notifier: Optional["Notifier"] = None,
        analytics: Optional["AnalyticsStore"] = None,
        **kwargs,
    ) -> None:
        self.symbol = symbol
        self.data_feed = data_feed
        self.risk_manager = risk_manager
        self.notifier = notifier
        self.analytics = analytics
        self.extra = kwargs

    @abstractmethod
    def run(self, strategy: Strategy) -> None:
        """Main loop for streaming market data and executing strategy signals."""

    @abstractmethod
    def execute(self, signal: Signal, price: float | None = None) -> None:
        """Send the given signal to the broker."""
