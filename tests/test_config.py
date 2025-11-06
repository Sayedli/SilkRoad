from silkroad.app import SilkRoadApp


def test_example_config_loads(tmp_path):
    sample_config = tmp_path / "config.yml"
    sample_config.write_text(
        """
environment: development
data:
  source: static
  symbol: BTC/USDT
  interval: 1h
  lookback: 50
strategy:
  name: momentum
  parameters: {}
execution:
  name: paper
  parameters: {}
""",
        encoding="utf-8",
    )

    app = SilkRoadApp.from_file(str(sample_config))
    assert app.strategy.name == "momentum"
