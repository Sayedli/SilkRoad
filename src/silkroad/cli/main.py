from __future__ import annotations

import click

from silkroad.app import SilkRoadApp


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), required=True, help="Path to YAML config file.")
@click.pass_context
def app(ctx: click.Context, config: str) -> None:
    """SilkRoad trading bot CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@app.command()
@click.pass_context
def backtest(ctx: click.Context) -> None:
    config_path = ctx.obj["config_path"]
    silkroad = SilkRoadApp.from_file(config_path)
    result = silkroad.run_backtest()
    click.echo(
        f"Backtest complete | strategy={result.strategy_name} | total_return={result.total_return:.2%} "
        f"| sharpe={result.sharpe_ratio if result.sharpe_ratio is not None else 'n/a'} "
        f"| trades={result.total_trades}"
    )


@app.command()
@click.pass_context
def live(ctx: click.Context) -> None:
    config_path = ctx.obj["config_path"]
    silkroad = SilkRoadApp.from_file(config_path)
    silkroad.run_live()
