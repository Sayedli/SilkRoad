from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from silkroad.strategy.base import Strategy
from silkroad.execution.base import ExecutionEngine
from silkroad.backtesting.engine import BacktestEngine
from silkroad.analytics import AnalyticsStore
from silkroad.risk.manager import RiskManager


class DataFeedConfig(BaseModel):
    source: str = Field(..., description="Identifier for the data source (e.g., 'ccxt:binance').")
    symbol: str = Field(..., description="Trading symbol, such as 'BTC/USDT'.")
    interval: str = Field("1h", description="Data aggregation interval.")
    lookback: int = Field(365, description="Number of data points to load.")
    poll_interval: float = Field(15.0, description="Seconds between polling updates for streaming feeds.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional feed-specific options.")


class StrategyConfig(BaseModel):
    name: str = Field(..., description="Strategy identifier registered in STRATEGY_REGISTRY.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific settings.")

    def build(self, **overrides: Any) -> Strategy:
        from silkroad.strategy.registry import STRATEGY_REGISTRY

        strategy_cls = STRATEGY_REGISTRY.get(self.name)
        if not strategy_cls:
            raise ValueError(f"Strategy '{self.name}' is not registered.")
        parameters = {**self.parameters, **overrides}
        return strategy_cls(**parameters)


class ExecutionConfig(BaseModel):
    name: str = Field(..., description="Execution engine identifier.")
    parameters: Dict[str, Any] = Field(default_factory=dict)

    def build(self, **overrides: Any) -> ExecutionEngine:
        from silkroad.execution.registry import EXECUTION_REGISTRY

        engine_cls = EXECUTION_REGISTRY.get(self.name)
        if not engine_cls:
            raise ValueError(f"Execution engine '{self.name}' is not registered.")
        parameters = {**self.parameters, **overrides}
        return engine_cls(**parameters)


class BacktestConfig(BaseModel):
    enabled: bool = Field(True)
    starting_cash: float = Field(10_000.0)
    commission: float = Field(0.001)
    slippage: float = Field(0.0, description="Fractional slippage applied to fills during backtests.")

    def build(
        self,
        strategy: Strategy,
        data_feed_config: DataFeedConfig,
        risk_manager: RiskManager | None,
        analytics: AnalyticsStore | None = None,
    ) -> BacktestEngine:
        return BacktestEngine(
            strategy=strategy,
            config=self,
            data_feed_config=data_feed_config,
            risk_manager=risk_manager,
            analytics=analytics,
        )


class RiskConfig(BaseModel):
    max_position_size: float = Field(0.1, description="Maximum fraction of equity per position.")
    max_drawdown: float = Field(0.2, description="Maximum allowed drawdown before halting trading.")
    stop_loss_pct: float = Field(0.05, description="Default stop-loss percentage.")


class MonitoringConfig(BaseModel):
    enabled: bool = Field(True)
    channels: Dict[str, Any] = Field(default_factory=dict, description="Notification integrations.")


class AnalyticsConfig(BaseModel):
    enabled: bool = Field(True)
    backend: str = Field("sqlite", description="Analytics backend identifier (e.g., 'sqlite').")
    database: str = Field("analytics/silkroad.db", description="Database path for analytics store.")


class AppConfig(BaseModel):
    environment: str = Field("development", description="Either 'development', 'paper', or 'production'.")
    data: DataFeedConfig
    strategy: StrategyConfig
    execution: ExecutionConfig
    backtest: Optional[BacktestConfig] = Field(None)
    risk: Optional[RiskConfig] = Field(None)
    monitoring: Optional[MonitoringConfig] = Field(None)
    analytics: Optional[AnalyticsConfig] = Field(None)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file '{config_path}' does not exist.")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as err:
        raise ValueError(f"Invalid configuration format: {err}") from err
