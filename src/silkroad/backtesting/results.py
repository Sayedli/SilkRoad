from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd


@dataclass
class BacktestResult:
    strategy_name: str
    starting_cash: float
    ending_value: float
    total_return: float
    total_trades: int
    sharpe_ratio: Optional[float]
    run_id: str
    completed_at: datetime
    extra_metrics: Dict[str, float]
    price_series: Optional[pd.Series] = None
    equity_curve: Optional[pd.Series] = None
