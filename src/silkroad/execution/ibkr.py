from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ib_insync import IB, MarketOrder, Stock, util  # type: ignore

from silkroad.analytics.logger import TradeRecord
from silkroad.execution.base import ExecutionEngine
from silkroad.monitoring.notifications import Notifier, PrintNotifier
from silkroad.risk.manager import RiskManager
from silkroad.strategy.base import Signal, Strategy

from .registry import register_execution_engine


@dataclass
class IBKRConnectionConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 123
    exchange: str = "SMART"
    currency: str = "USD"
    poll_interval: float = 10.0


class IBKRExecutionEngine(ExecutionEngine):
    """Execution engine that routes orders through Interactive Brokers via ib_insync."""

    def __init__(
        self,
        symbol: str,
        risk_manager: RiskManager | None = None,
        notifier: Notifier | None = None,
        analytics=None,
        data_feed=None,
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
        self.connection = IBKRConnectionConfig(
            host=kwargs.get("host", "127.0.0.1"),
            port=int(kwargs.get("port", 7497)),
            client_id=int(kwargs.get("client_id", 123)),
            exchange=kwargs.get("exchange", "SMART"),
            currency=kwargs.get("currency", "USD"),
            poll_interval=float(kwargs.get("poll_interval", 10.0)),
        )
        self.ib = IB()
        self.contract = Stock(self.symbol, self.connection.exchange, self.connection.currency)

    def run(self, strategy: Strategy) -> None:
        self._ensure_connection()
        if self.data_feed is not None:
            history = self.data_feed.load_history()
            strategy.prepare(history.copy())
            try:
                for snapshot in self.data_feed.stream():
                    signal = strategy.generate_signal(snapshot)
                    if self.risk_manager and not self.risk_manager.validate(signal):
                        if self.notifier:
                            self.notifier.send(f"[IBKR] Risk blocked {signal.side} signal.")
                        continue
                    price = float(snapshot.history().iloc[-1]["close"])
                    self.execute(signal, price)
                    self.ib.sleep(self.connection.poll_interval)
            finally:
                self.disconnect()
        else:
            raise RuntimeError("IBKRExecutionEngine requires a data feed to generate trading signals.")

    def execute(self, signal: Signal, price: float | None = None) -> None:
        if signal.side == "hold":
            return

        self._ensure_connection()
        execution_price = price or self._fetch_last_price()
        if execution_price is None:
            raise RuntimeError("Unable to retrieve market price for order sizing.")

        target_percent = signal.size if signal.side == "buy" else -signal.size
        target_percent = max(-1.0, min(1.0, target_percent))
        target_quantity = self._target_shares(target_percent, execution_price)
        current_position = self._current_position()
        delta = target_quantity - current_position

        if abs(delta) < 1e-6:
            return

        order_side = "BUY" if delta > 0 else "SELL"
        quantity = abs(int(round(delta)))
        if quantity == 0:
            return

        order = MarketOrder(order_side, quantity)
        trade = self.ib.placeOrder(self.contract, order)
        while not trade.isDone():
            self.ib.waitOnUpdate(timeout=1)

        fills = list(trade.fills)
        if self.notifier:
            self.notifier.send(
                f"[IBKR] {order_side} {quantity} {self.symbol} "
                f"@ {fills[-1].execution.price if fills else execution_price:.2f}"
            )

        if self.analytics and fills:
            for fill in fills:
                fill_time = fill.execution.time.replace(tzinfo=None)
                self.analytics.log_trade(
                    TradeRecord(
                        timestamp=fill_time,
                        symbol=self.symbol,
                        side="buy" if fill.execution.side == "BOT" else "sell",
                        quantity=abs(fill.execution.shares),
                        price=fill.execution.price,
                        strategy=signal.metadata.get("strategy", "unknown") if signal.metadata else "unknown",
                        source="ibkr",
                    )
                )

    def _ensure_connection(self) -> None:
        if self.ib.isConnected():
            return
        self.ib.connect(
            host=self.connection.host,
            port=self.connection.port,
            clientId=self.connection.client_id,
        )

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    def _fetch_last_price(self) -> Optional[float]:
        ticker = self.ib.reqMktData(self.contract, "", False, False)
        for _ in range(10):
            self.ib.waitOnUpdate(timeout=1)
            price = ticker.marketPrice()
            if price and price > 0:
                self.ib.cancelMktData(ticker)
                return float(price)
        self.ib.cancelMktData(ticker)
        return None

    def _target_shares(self, target_percent: float, price: float) -> float:
        account_value = self._account_value()
        target_value = account_value * target_percent
        return target_value / price

    def _account_value(self) -> float:
        summary = self.ib.accountSummary()
        df = util.df(summary)
        net_liq = df[df.tag == "NetLiquidation"]
        if net_liq.empty:
            raise RuntimeError("Unable to retrieve NetLiquidation from IB account summary.")
        return float(net_liq.value.iloc[0])

    def _current_position(self) -> float:
        positions = self.ib.positions()
        for position in positions:
            if position.contract.secType == "STK" and position.contract.symbol == self.symbol:
                return float(position.position)
        return 0.0

    def __del__(self) -> None:
        try:
            self.disconnect()
        except Exception:
            pass


register_execution_engine("ibkr")(IBKRExecutionEngine)
