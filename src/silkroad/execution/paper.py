from __future__ import annotations

from datetime import datetime

from silkroad.analytics.logger import TradeRecord
from silkroad.data.base import MarketDataFeed
from silkroad.execution.base import ExecutionEngine
from silkroad.monitoring.notifications import Notifier, PrintNotifier
from silkroad.risk.manager import RiskManager
from silkroad.strategy.base import Signal, Strategy

from .registry import register_execution_engine


class PaperTradingEngine(ExecutionEngine):
    """Simulated execution loop for validating strategies without real capital."""

    def __init__(
        self,
        symbol: str,
        data_feed: MarketDataFeed,
        risk_manager: RiskManager | None = None,
        notifier: Notifier | None = None,
        analytics=None,
        **kwargs,
    ) -> None:
        resolved_risk = risk_manager or RiskManager()
        resolved_notifier = notifier or PrintNotifier()
        super().__init__(
            symbol=symbol,
            data_feed=data_feed,
            risk_manager=resolved_risk,
            notifier=resolved_notifier,
            analytics=analytics,
            **kwargs,
        )

    def run(self, strategy: Strategy) -> None:
        history = self.data_feed.load_history()
        strategy.prepare(history.copy())
        for snapshot in self.data_feed.stream():
            signal = strategy.generate_signal(snapshot)
            if self.risk_manager and not self.risk_manager.validate(signal):
                self.notifier.send(f"Risk constraints blocked {signal.side} signal.")
                continue
            price = float(snapshot.history().iloc[-1]["close"])
            self.execute(signal, price)

    def execute(self, signal: Signal, price: float | None = None) -> None:
        price_display = f" @ {price:.2f}" if price is not None else ""
        self.notifier.send(f"[PAPER] {signal.side.upper()} {signal.size:.4f} {self.symbol}{price_display}")
        if self.analytics and price is not None:
            quantity = signal.size
            self.analytics.log_trade(
                TradeRecord(
                    timestamp=datetime.utcnow(),
                    symbol=self.symbol,
                    side=signal.side,
                    quantity=quantity,
                    price=price,
                    strategy=signal.metadata.get("strategy", "unknown") if signal.metadata else "unknown",
                    source="paper",
                )
            )


register_execution_engine("paper")(PaperTradingEngine)
