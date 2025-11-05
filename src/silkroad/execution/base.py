from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from silkroad.strategy.base import Signal, Strategy


class BrokerClient(Protocol):
    def submit_order(self, symbol: str, side: str, quantity: float) -> None: ...


class ExecutionEngine(ABC):
    """Base execution engine for routing strategy signals to broker clients."""

    symbol: str

    def __init__(self, symbol: str, **kwargs) -> None:
        self.symbol = symbol
        self.extra = kwargs

    @abstractmethod
    def run(self, strategy: Strategy) -> None:
        """Main loop for streaming market data and executing strategy signals."""

    @abstractmethod
    def execute(self, signal: Signal) -> None:
        """Send the given signal to the broker."""
