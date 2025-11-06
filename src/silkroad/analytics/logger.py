from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class TradeRecord:
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    strategy: str
    source: str


@dataclass
class PerformanceRecord:
    run_id: str
    timestamp: datetime
    metric: str
    value: float
    metadata: Dict[str, Any] | None = None


class AnalyticsStore:
    """Lightweight SQLite-backed store for trades and performance metrics."""

    def __init__(self, database: str) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                strategy TEXT NOT NULL,
                source TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                metadata TEXT
            )
            """
        )
        self.conn.commit()

    def log_trade(self, record: TradeRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO trades (timestamp, symbol, side, quantity, price, strategy, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.timestamp.isoformat(),
                record.symbol,
                record.side,
                record.quantity,
                record.price,
                record.strategy,
                record.source,
            ),
        )
        self.conn.commit()

    def log_performance(self, record: PerformanceRecord) -> None:
        metadata_json: Optional[str] = None
        if record.metadata:
            try:
                import json

                metadata_json = json.dumps(record.metadata)
            except TypeError:
                metadata_json = None
        self.conn.execute(
            """
            INSERT INTO performance (run_id, timestamp, metric, value, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.timestamp.isoformat(),
                record.metric,
                record.value,
                metadata_json,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
