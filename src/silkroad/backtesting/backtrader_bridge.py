from __future__ import annotations

import backtrader as bt  # type: ignore
import pandas as pd

from silkroad.analytics.logger import AnalyticsStore, TradeRecord
from silkroad.data.base import MarketSnapshot
from silkroad.risk.manager import RiskManager
from silkroad.strategy.base import Signal, Strategy


class StrategyBridge(bt.Strategy):  # type: ignore[misc]
    params = dict(
        silkroad_strategy=None,
        history=None,
        risk_manager=None,
        analytics=None,
        symbol=None,
    )

    def __init__(self) -> None:
        if self.p.silkroad_strategy is None:
            raise ValueError("StrategyBridge requires 'silkroad_strategy' parameter.")
        if self.p.history is None:
            raise ValueError("StrategyBridge requires 'history' parameter.")
        self.strategy: Strategy = self.p.silkroad_strategy
        self.history_df: pd.DataFrame = self.p.history
        self.risk_manager: RiskManager | None = self.p.risk_manager
        self.analytics: AnalyticsStore | None = self.p.analytics
        self.symbol: str = self.p.symbol or getattr(self.data, "symbol", "UNKNOWN")
        self.orders: list = []

    def next(self) -> None:
        current_dt = self.datas[0].datetime.datetime(0)
        truncated_history = self.history_df.loc[: current_dt]
        if truncated_history.empty:
            return
        snapshot = MarketSnapshot(truncated_history)
        signal: Signal = self.strategy.generate_signal(snapshot)

        if self.risk_manager and not self.risk_manager.validate(signal):
            return

        if signal.side == "buy":
            self.order_target_percent(target=min(1.0, signal.size))
        elif signal.side == "sell":
            self.order_target_percent(target=-min(1.0, signal.size))
        else:
            return

    def notify_order(self, order: bt.Order) -> None:  # type: ignore[override]
        if order.status in [order.Completed, order.Partial]:
            if self.analytics:
                executed_dt = bt.num2date(order.executed.dt)
                self.analytics.log_trade(
                    TradeRecord(
                        timestamp=executed_dt,
                        symbol=self.symbol,
                        side="buy" if order.isbuy() else "sell",
                        quantity=abs(order.executed.size),
                        price=order.executed.price,
                        strategy=self.strategy.name,
                        source="backtest",
                    )
                )

    def stop(self) -> None:
        pass
