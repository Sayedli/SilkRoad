from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from silkroad.analytics.logger import AnalyticsStore
from silkroad.app import SilkRoadApp
from silkroad.backtesting.results import BacktestResult


def _fetch_recent_trades(store: Optional[AnalyticsStore], limit: int = 50) -> Optional[pd.DataFrame]:
    if not store:
        return None
    try:
        query = """
        SELECT timestamp, symbol, side, quantity, price, strategy, source
        FROM trades
        ORDER BY timestamp DESC
        LIMIT ?
        """
        df = pd.read_sql_query(query, store.conn, params=(limit,))
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return None


def _fetch_recent_metrics(store: Optional[AnalyticsStore], limit: int = 50) -> Optional[pd.DataFrame]:
    if not store:
        return None
    try:
        query = """
        SELECT run_id, timestamp, metric, value, metadata
        FROM performance
        ORDER BY timestamp DESC
        LIMIT ?
        """
        df = pd.read_sql_query(query, store.conn, params=(limit,))
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return None


def _load_config_preview(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _run_backtest(config_path: Path) -> tuple[BacktestResult, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    app = SilkRoadApp.from_file(str(config_path))
    result = app.run_backtest()
    trades = _fetch_recent_trades(app.analytics)
    metrics = _fetch_recent_metrics(app.analytics)
    return result, trades, metrics


def main() -> None:
    st.set_page_config(page_title="SilkRoad Dashboard", layout="wide")
    st.title("SilkRoad Trading Console")
    st.caption("Backtest strategies, inspect analytics, and iterate on configs from a friendly UI.")

    default_config = "configs/example.paper.yml"
    config_path_input = st.sidebar.text_input("Config path", value=default_config)
    config_path = Path(config_path_input).expanduser().resolve()

    st.sidebar.markdown("### Actions")
    run_backtest_clicked = st.sidebar.button("Run Backtest", type="primary")
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Tips**
\n- Update YAML configs directly in your editor.
\n- Copy configs to experiment: `cp configs/example.paper.yml configs/my_test.yml`.
\n- Analytics database location is defined in the config (`analytics.database`).
        """
    )

    if run_backtest_clicked:
        if not config_path.exists():
            st.error(f"Config file not found: {config_path}")
        else:
            with st.spinner("Running backtest..."):
                try:
                    result, trades, metrics = _run_backtest(config_path)
                except Exception as exc:
                    st.error(f"Backtest failed: {exc}")
                else:
                    st.session_state["last_result"] = result
                    st.session_state["last_trades"] = trades
                    st.session_state["last_metrics"] = metrics
                    st.success("Backtest completed.")

    config_col, preview_col = st.columns([1, 2])
    with config_col:
        st.subheader("Configuration")
        if config_path.exists():
            st.write(f"Using config: `{config_path}`")
        else:
            st.warning("Provided config path does not exist.")
    with preview_col:
        st.subheader("YAML Preview")
        preview = _load_config_preview(config_path)
        if preview:
            st.code(preview, language="yaml")
        else:
            st.info("Select a valid config file to preview its contents.")

    if "last_result" in st.session_state:
        result: BacktestResult = st.session_state["last_result"]
        st.markdown("## Backtest Results")
        metrics_cols = st.columns(4)
        metrics_cols[0].metric("Ending Value", f"${result.ending_value:,.2f}")
        metrics_cols[1].metric("Total Return", f"{result.total_return:.2%}")
        metrics_cols[2].metric("Trades", f"{result.total_trades}")
        sharpe_display = f"{result.sharpe_ratio:.2f}" if result.sharpe_ratio is not None else "n/a"
        metrics_cols[3].metric("Sharpe Ratio", sharpe_display)

        extra_metrics = result.extra_metrics or {}
        if extra_metrics:
            st.markdown("### Additional Metrics")
            extra_df = pd.DataFrame(list(extra_metrics.items()), columns=["Metric", "Value"])
            st.dataframe(extra_df, use_container_width=True, hide_index=True)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("### Price History")
            if result.price_series is not None and not result.price_series.empty:
                price_df = result.price_series.to_frame(name="close")
                st.line_chart(price_df)
            else:
                st.info("Price series not available for this run.")
        with chart_col2:
            st.markdown("### Equity Curve")
            if result.equity_curve is not None and not result.equity_curve.empty:
                equity_df = result.equity_curve.to_frame(name="equity")
                st.line_chart(equity_df)
            else:
                st.info("Equity curve not available.")

        trades_df = st.session_state.get("last_trades")
        metrics_df = st.session_state.get("last_metrics")
        st.markdown("## Analytics")
        analytics_tabs = st.tabs(["Recent Trades", "Performance Logs"])

        with analytics_tabs[0]:
            if trades_df is not None and not trades_df.empty:
                trades_display = trades_df.copy()
                trades_display["timestamp"] = trades_display["timestamp"].dt.tz_localize(None)
                st.dataframe(trades_display, use_container_width=True)
            else:
                st.info("No trades logged yet.")

        with analytics_tabs[1]:
            if metrics_df is not None and not metrics_df.empty:
                metrics_display = metrics_df.copy()
                metrics_display["timestamp"] = metrics_display["timestamp"].dt.tz_localize(None)
                st.dataframe(metrics_display, use_container_width=True)
            else:
                st.info("No performance metrics logged yet.")
    else:
        st.markdown("## Backtest Results")
        st.info("Run a backtest to see metrics, charts, and recent analytics.")


if __name__ == "__main__":
    main()
