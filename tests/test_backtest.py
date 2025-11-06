from silkroad.app import SilkRoadApp


def test_backtest_returns_result(tmp_path):
    sample_config = tmp_path / "config.yml"
    sample_config.write_text(
        """
environment: development
data:
  source: static
  symbol: TEST/USDT
  interval: 1h
  lookback: 120
strategy:
  name: momentum
  parameters:
    fast_window: 5
    slow_window: 10
    threshold: 0.1
    order_size: 0.1
execution:
  name: paper
  parameters: {}
backtest:
  enabled: true
  starting_cash: 10000
  commission: 0.0005
  slippage: 0.0001
""",
        encoding="utf-8",
    )

    app = SilkRoadApp.from_file(str(sample_config))
    result = app.run_backtest()

    assert result.strategy_name == "momentum"
    assert result.starting_cash == 10000
