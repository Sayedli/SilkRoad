from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config.settings import AppConfig, load_config
from .execution.base import ExecutionEngine
from .strategy.base import Strategy
from .backtesting.engine import BacktestEngine


@dataclass
class SilkRoadApp:
    """Orchestrates configuration, strategy selection, and execution/backtesting lifecycle."""

    config: AppConfig
    strategy: Strategy
    execution_engine: ExecutionEngine
    backtest_engine: Optional[BacktestEngine] = None

    @classmethod
    def from_file(cls, path: str) -> "SilkRoadApp":
        config = load_config(path)
        strategy = config.strategy.build()
        execution = config.execution.build()
        backtester = config.backtest.build(strategy) if config.backtest else None
        return cls(config=config, strategy=strategy, execution_engine=execution, backtest_engine=backtester)

    def run_live(self) -> None:
        if not self.execution_engine:
            raise RuntimeError("Execution engine is not configured.")
        self.execution_engine.run(self.strategy)

    def run_backtest(self) -> None:
        if not self.backtest_engine:
            raise RuntimeError("Backtest engine is not configured.")
        self.backtest_engine.run()
