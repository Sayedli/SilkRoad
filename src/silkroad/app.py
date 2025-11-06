from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .analytics import AnalyticsStore
from .config.settings import AppConfig, load_config
from .data import build_data_feed, MarketDataFeed
from .execution.base import ExecutionEngine
from .monitoring.notifications import Notifier, PrintNotifier
from .risk.manager import RiskLimits, RiskManager
from .strategy.base import Strategy
from .backtesting.engine import BacktestEngine
from .backtesting.results import BacktestResult


@dataclass
class SilkRoadApp:
    """Orchestrates configuration, strategy selection, and execution/backtesting lifecycle."""

    config: AppConfig
    strategy: Strategy
    data_feed: MarketDataFeed
    execution_engine: ExecutionEngine
    risk_manager: RiskManager
    notifier: Notifier
    analytics: Optional[AnalyticsStore]
    backtest_engine: Optional[BacktestEngine] = None

    @classmethod
    def from_file(cls, path: str) -> "SilkRoadApp":
        config = load_config(path)
        data_feed = build_data_feed(
            source=config.data.source,
            symbol=config.data.symbol,
            interval=config.data.interval,
            lookback=config.data.lookback,
            poll_interval=config.data.poll_interval,
            **config.data.parameters,
        )
        strategy = config.strategy.build()
        risk_limits = None
        if config.risk:
            risk_limits = RiskLimits(
                max_position_fraction=config.risk.max_position_size,
                max_drawdown=config.risk.max_drawdown,
                stop_loss_pct=config.risk.stop_loss_pct,
            )
        risk_manager = RiskManager(limits=risk_limits)
        notifier: Notifier = PrintNotifier()
        analytics_store: Optional[AnalyticsStore] = None
        if config.analytics and config.analytics.enabled:
            if config.analytics.backend != "sqlite":
                raise ValueError(f"Unsupported analytics backend '{config.analytics.backend}'.")
            analytics_store = AnalyticsStore(config.analytics.database)
        execution = config.execution.build(
            symbol=config.data.symbol,
            data_feed=data_feed,
            risk_manager=risk_manager,
            notifier=notifier,
            analytics=analytics_store,
        )
        backtester = (
            config.backtest.build(
                strategy=strategy,
                data_feed_config=config.data,
                risk_manager=risk_manager,
                analytics=analytics_store,
            )
            if config.backtest
            else None
        )
        return cls(
            config=config,
            strategy=strategy,
            data_feed=data_feed,
            execution_engine=execution,
            risk_manager=risk_manager,
            notifier=notifier,
            analytics=analytics_store,
            backtest_engine=backtester,
        )

    def run_live(self) -> None:
        if not self.execution_engine:
            raise RuntimeError("Execution engine is not configured.")
        self.execution_engine.run(self.strategy)

    def run_backtest(self) -> BacktestResult:
        if not self.backtest_engine:
            raise RuntimeError("Backtest engine is not configured.")
        return self.backtest_engine.run()
