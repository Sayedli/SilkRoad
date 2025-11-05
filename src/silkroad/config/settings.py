from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from silkroad.strategy.base import Strategy
from silkroad.execution.base import ExecutionEngine
from silkroad.backtesting.engine import BacktestEngine


class DataFeedConfig(BaseModel):
    source: str = Field(..., description="Identifier for the data source (e.g., 'ccxt:binance').")
    symbol: str = Field(..., description="Trading symbol, such as 'BTC/USDT'.")
    interval: str = Field("1h", description="Data aggregation interval.")
    lookback: int = Field(365, description="Number of data points to load.")


class StrategyConfig(BaseModel):
    name: str = Field(..., description="Strategy identifier registered in STRATEGY_REGISTRY.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific settings.")

    def build(self) -> Strategy:
        from silkroad.strategy.registry import STRATEGY_REGISTRY

        strategy_cls = STRATEGY_REGISTRY.get(self.name)
        if not strategy_cls:
            raise ValueError(f"Strategy '{self.name}' is not registered.")
        return strategy_cls(**self.parameters)


class ExecutionConfig(BaseModel):
    name: str = Field(..., description="Execution engine identifier.")
    parameters: Dict[str, Any] = Field(default_factory=dict)

    def build(self) -> ExecutionEngine:
        from silkroad.execution.registry import EXECUTION_REGISTRY

        engine_cls = EXECUTION_REGISTRY.get(self.name)
        if not engine_cls:
            raise ValueError(f"Execution engine '{self.name}' is not registered.")
        return engine_cls(**self.parameters)


class BacktestConfig(BaseModel):
    enabled: bool = Field(True)
    starting_cash: float = Field(10_000.0)
    commission: float = Field(0.001)

    def build(self, strategy: Strategy) -> BacktestEngine:
        return BacktestEngine(strategy=strategy, config=self)


class RiskConfig(BaseModel):
    max_position_size: float = Field(0.1, description="Maximum fraction of equity per position.")
    max_drawdown: float = Field(0.2, description="Maximum allowed drawdown before halting trading.")
    stop_loss_pct: float = Field(0.05, description="Default stop-loss percentage.")


class MonitoringConfig(BaseModel):
    enabled: bool = Field(True)
    channels: Dict[str, Any] = Field(default_factory=dict, description="Notification integrations.")


class AppConfig(BaseModel):
    environment: str = Field("development", description="Either 'development', 'paper', or 'production'.")
    data: DataFeedConfig
    strategy: StrategyConfig
    execution: ExecutionConfig
    backtest: Optional[BacktestConfig] = Field(None)
    risk: Optional[RiskConfig] = Field(None)
    monitoring: Optional[MonitoringConfig] = Field(None)


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
