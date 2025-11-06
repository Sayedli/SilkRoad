from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import backtrader as bt  # type: ignore
import pandas as pd
from uuid import uuid4

from silkroad.analytics.logger import AnalyticsStore, PerformanceRecord
from silkroad.backtesting.backtrader_bridge import StrategyBridge
from silkroad.backtesting.results import BacktestResult
from silkroad.data import build_data_feed
from silkroad.strategy.base import Strategy

if TYPE_CHECKING:
    from silkroad.config.settings import BacktestConfig, DataFeedConfig
    from silkroad.risk.manager import RiskManager


class BacktestEngine:
    """Backtrader-powered engine for evaluating strategies on historical data feeds."""

    def __init__(
        self,
        strategy: Strategy,
        config: "BacktestConfig",
        data_feed_config: "DataFeedConfig",
        risk_manager: Optional["RiskManager"],
        analytics: Optional[AnalyticsStore] = None,
    ) -> None:
        self.strategy = strategy
        self.config = config
        self.data_feed_config = data_feed_config
        self.risk_manager = risk_manager
        self.analytics = analytics

    def run(self) -> BacktestResult:
        if not self.config.enabled:
            raise RuntimeError("Backtesting is disabled in the current configuration.")

        history = self._load_history()
        prepared_history = history.copy()
        self.strategy.prepare(prepared_history)
        prepared_history = prepared_history[~prepared_history.index.duplicated(keep="last")]
        try:
            prepared_history.index = prepared_history.index.tz_localize(None)
        except TypeError:
            pass

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.config.starting_cash)
        cerebro.broker.setcommission(commission=self.config.commission)
        if self.config.slippage:
            cerebro.broker.set_slippage_perc(self.config.slippage)

        data_feed = bt.feeds.PandasData(dataname=prepared_history)
        cerebro.adddata(data_feed, name=self.data_feed_config.symbol)
        cerebro.addstrategy(
            StrategyBridge,
            silkroad_strategy=self.strategy,
            history=prepared_history,
            risk_manager=self.risk_manager,
            analytics=self.analytics,
            symbol=self.data_feed_config.symbol,
        )
        cerebro.addanalyzer(bt.analyzers.SharpeRatio_A, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Days, _name="returns")

        strategies = cerebro.run()
        bridge: StrategyBridge = strategies[0]

        ending_value = cerebro.broker.getvalue()
        total_return = (ending_value / self.config.starting_cash) - 1
        trade_analysis = bridge.analyzers.trades.get_analysis()
        total_trades = (
            trade_analysis.get("total", {}).get("closed", 0) if hasattr(bridge.analyzers, "trades") else 0
        )
        sharpe_ratio = None
        if hasattr(bridge.analyzers, "sharpe"):
            sharpe_ratio = bridge.analyzers.sharpe.get_analysis().get("sharperatio")

        run_id = uuid4().hex
        completed_at = pd.Timestamp.utcnow().to_pydatetime()
        extra_metrics = {}
        if hasattr(bridge.analyzers, "returns"):
            returns = bridge.analyzers.returns.get_analysis()
            if returns:
                extra_metrics["avg_daily_return"] = float(pd.Series(list(returns.values())).mean())

        result = BacktestResult(
            strategy_name=self.strategy.name,
            starting_cash=self.config.starting_cash,
            ending_value=ending_value,
            total_return=total_return,
            total_trades=total_trades,
            sharpe_ratio=sharpe_ratio,
            run_id=run_id,
            completed_at=completed_at,
            extra_metrics=extra_metrics,
        )

        if self.analytics:
            self.analytics.log_performance(
                PerformanceRecord(
                    run_id=run_id,
                    timestamp=completed_at,
                    metric="total_return",
                    value=total_return,
                    metadata={"strategy": self.strategy.name},
                )
            )
            if sharpe_ratio is not None:
                self.analytics.log_performance(
                    PerformanceRecord(
                        run_id=run_id,
                        timestamp=completed_at,
                        metric="sharpe_ratio",
                        value=sharpe_ratio,
                        metadata={"strategy": self.strategy.name},
                    )
                )
        return result

    def _load_history(self) -> pd.DataFrame:
        feed = build_data_feed(
            source=self.data_feed_config.source,
            symbol=self.data_feed_config.symbol,
            interval=self.data_feed_config.interval,
            lookback=self.data_feed_config.lookback,
            poll_interval=self.data_feed_config.poll_interval,
            **self.data_feed_config.parameters,
        )
        history = feed.load_history()
        history = history.sort_index()
        return history
