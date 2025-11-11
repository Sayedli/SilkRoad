from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st
import yaml

try:
    import altair as alt
except Exception:  # pragma: no cover - optional dependency
    alt = None

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


def _apply_robinhood_theme() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stAppViewContainer"] {
                background: #05090f;
                color: #f2f5f7;
                font-family: "Inter", "SF Pro Display", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            }
            [data-testid="stSidebar"] {
                background: #0b1117;
                border-right: 1px solid #141b24;
            }
            .stButton>button {
                background: linear-gradient(120deg, #00e676, #00c853);
                color: #030507;
                font-weight: 600;
                border: none;
                border-radius: 999px;
                padding: 0.55rem 1.5rem;
            }
            .stButton>button:hover {
                box-shadow: 0 0 20px rgba(0, 230, 118, 0.35);
            }
            .sr-card {
                background: #0d151f;
                border-radius: 18px;
                padding: 1rem 1.2rem;
                border: 1px solid rgba(255, 255, 255, 0.05);
                box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
                min-height: 120px;
            }
            .sr-card--hero {
                background: linear-gradient(145deg, rgba(0, 200, 120, 0.15), rgba(0, 200, 120, 0.03));
            }
            .sr-card__label {
                color: #8a97a6;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.45rem;
            }
            .sr-card__value {
                font-size: 1.8rem;
                font-weight: 600;
                color: #f4fbff;
            }
            .sr-card__subtext {
                color: #7ed1a1;
                font-size: 0.95rem;
            }
            .sr-status {
                background: rgba(126, 209, 161, 0.1);
                border-radius: 12px;
                padding: 0.75rem 1rem;
                border: 1px solid rgba(0, 230, 118, 0.2);
            }
            .sr-status__label {
                font-size: 0.9rem;
                color: #9fb2c4;
                margin-bottom: 0.25rem;
                display: block;
            }
            .sr-status__value {
                font-weight: 600;
                color: #e9f5ee;
            }
            .sr-activity {
                border-left: 2px solid rgba(0, 230, 118, 0.4);
                padding-left: 0.9rem;
                margin-bottom: 1rem;
            }
            .sr-activity__time {
                font-size: 0.8rem;
                color: #7c8ba1;
            }
            .sr-activity__title {
                font-weight: 600;
                color: #f4fbff;
            }
            .sr-activity__body {
                color: #9fb2c4;
                font-size: 0.9rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_percent(value: float) -> str:
    return f"{value:.2%}"


def _metric_card(column, label: str, value: str, subtext: str = "") -> None:
    column.markdown(
        f"""
        <div class="sr-card sr-card--hero">
            <div class="sr-card__label">{label}</div>
            <div class="sr-card__value">{value}</div>
            <div class="sr-card__subtext">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_card(column, label: str, value: str, detail: str = "") -> None:
    column.markdown(
        f"""
        <div class="sr-card sr-status">
            <span class="sr-status__label">{label}</span>
            <div class="sr-status__value">{value}</div>
            <div class="sr-card__subtext">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_altair_chart(series: pd.Series, value_label: str, color: str) -> Optional["alt.Chart"]:
    if alt is None or series is None or series.empty:
        return None
    df = series.to_frame(name=value_label).reset_index()
    df.rename(columns={"index": "timestamp"}, inplace=True)
    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    return (
        alt.Chart(df)
        .mark_line(color=color, strokeWidth=2)
        .encode(
            x=alt.X("timestamp:T", title=""),
            y=alt.Y(f"{value_label}:Q", title=value_label.replace("_", " ").title()),
            tooltip=["timestamp:T", alt.Tooltip(f"{value_label}:Q", format=".2f")],
        )
        .properties(height=250)
        .interactive()
    )


def _build_activity_feed(
    trades_df: Optional[pd.DataFrame], metrics_df: Optional[pd.DataFrame]
) -> list[dict[str, Any]]:
    feed: list[dict[str, Any]] = []
    if trades_df is not None and not trades_df.empty:
        subset = trades_df.head(5)
        for _, trade in subset.iterrows():
            ts = trade["timestamp"]
            ts_local = ts.tz_localize(None) if hasattr(ts, "tz_localize") else ts
            feed.append(
                {
                    "timestamp": ts_local,
                    "title": f"{trade['side'].upper()} {trade['symbol']}",
                    "body": f"{trade['quantity']} @ {_format_currency(trade['price'])}",
                }
            )
    if metrics_df is not None and not metrics_df.empty:
        subset = metrics_df.head(5)
        for _, metric in subset.iterrows():
            ts = metric["timestamp"]
            ts_local = ts.tz_localize(None) if hasattr(ts, "tz_localize") else ts
            feed.append(
                {
                    "timestamp": ts_local,
                    "title": f"Metric: {metric['metric']}",
                    "body": f"{metric['value']}",
                }
            )
    feed.sort(key=lambda item: item["timestamp"], reverse=True)
    return feed[:6]


def _parse_config_text(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        loaded = yaml.safe_load(raw) or {}
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _gv_label(text: str) -> str:
    safe = text.replace("\\", "\\\\")
    return safe.replace('"', '\\"')


def _build_bot_flow_graph(config: dict[str, Any], config_path: Path) -> str:
    data_cfg = config.get("data", {})
    strategy_cfg = config.get("strategy", {})
    execution_cfg = config.get("execution", {})
    analytics_cfg = config.get("analytics", {})
    risk_cfg = config.get("risk", {})

    config_label = f"Config\\n{config_path.name}"
    data_label = "Data Feed"
    if data_cfg:
        symbol = data_cfg.get("symbol", "n/a")
        interval = data_cfg.get("interval", "n/a")
        source = data_cfg.get("source", "n/a")
        data_label = f"Data Feed\\n{symbol}@{interval}\\n{source}"

    strategy_label = "Strategy"
    if strategy_cfg:
        params = strategy_cfg.get("parameters", {})
        param_summary = ", ".join(f"{k}={v}" for k, v in params.items()) or "No params"
        strategy_label = f"Strategy\\n{strategy_cfg.get('name', 'n/a')}\\n{param_summary}"

    execution_label = "Execution"
    if execution_cfg:
        execution_label = f"Execution\\n{execution_cfg.get('name', 'n/a')}"

    analytics_label = "Analytics"
    if analytics_cfg:
        backend = analytics_cfg.get("backend", "n/a")
        db = analytics_cfg.get("database", "n/a")
        analytics_label = f"Analytics\\n{backend}\\n{db}"

    risk_label = "Risk"
    if risk_cfg:
        max_pos = risk_cfg.get("max_position_size", "n/a")
        max_dd = risk_cfg.get("max_drawdown", "n/a")
        stop = risk_cfg.get("stop_loss_pct", "n/a")
        risk_label = f"Risk\\nmax pos {max_pos}\\nmax dd {max_dd}\\nstop {stop}"

    graph = f"""
digraph {{
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, fontcolor="white"];
    config [label="{_gv_label(config_label)}", fillcolor="#1f77b4"];
    data [label="{_gv_label(data_label)}", fillcolor="#9467bd"];
    strategy [label="{_gv_label(strategy_label)}", fillcolor="#2ca02c"];
    execution [label="{_gv_label(execution_label)}", fillcolor="#ff7f0e"];
    analytics [label="{_gv_label(analytics_label)}", fillcolor="#17becf"];
    risk [label="{_gv_label(risk_label)}", fillcolor="#d62728"];

    config -> data -> strategy -> execution -> analytics;
    strategy -> risk;
    risk -> execution;
}}
"""
    return graph


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
    config_data = _parse_config_text(preview) if preview else {}

    st.markdown("## How the Bot Works")
    if config_data:
        st.caption("This summary is generated from the selected config to show the end-to-end pipeline.")
        pipeline_cols = st.columns(3)

        data_cfg = config_data.get("data", {})
        strategy_cfg = config_data.get("strategy", {})
        execution_cfg = config_data.get("execution", {})
        risk_cfg = config_data.get("risk", {})
        analytics_cfg = config_data.get("analytics", {})
        monitoring_cfg = config_data.get("monitoring", {})

        data_desc = (
            f"{data_cfg.get('symbol', 'n/a')} @ {data_cfg.get('interval', 'n/a')} via {data_cfg.get('source', 'n/a')}"
            if data_cfg
            else "Data feed not configured."
        )
        data_meta = []
        if "lookback" in data_cfg:
            data_meta.append(f"lookback {data_cfg['lookback']}")
        if "poll_interval" in data_cfg:
            data_meta.append(f"poll {data_cfg['poll_interval']}s")
        data_meta_str = ", ".join(data_meta)

        strategy_params = strategy_cfg.get("parameters", {})
        strategy_meta = ", ".join(f"{k}={v}" for k, v in strategy_params.items()) if strategy_params else "No params provided."

        exec_params = execution_cfg.get("parameters", {})
        exec_meta = ", ".join(f"{k}={v}" for k, v in exec_params.items()) if exec_params else "Default parameters."

        risk_bits = []
        if "max_position_size" in risk_cfg:
            risk_bits.append(f"max pos {risk_cfg['max_position_size']}")
        if "max_drawdown" in risk_cfg:
            risk_bits.append(f"max dd {risk_cfg['max_drawdown']}")
        if "stop_loss_pct" in risk_cfg:
            risk_bits.append(f"stop {risk_cfg['stop_loss_pct']}")
        risk_meta = ", ".join(risk_bits) if risk_bits else "No explicit limits."

        analytics_enabled = analytics_cfg.get("enabled", False)
        analytics_desc = "Enabled" if analytics_enabled else "Disabled"
        analytics_backend = analytics_cfg.get("backend", "n/a")
        analytics_db = analytics_cfg.get("database", "n/a")

        monitoring_enabled = monitoring_cfg.get("enabled", False)
        monitoring_channels = ", ".join(monitoring_cfg.get("channels", {}).keys()) or "none"

        with pipeline_cols[0]:
            st.markdown("**Data Feed**")
            st.write(data_desc)
            if data_meta_str:
                st.caption(data_meta_str)
            st.markdown("**Strategy**")
            st.write(strategy_cfg.get("name", "n/a"))
            st.caption(strategy_meta)

        with pipeline_cols[1]:
            st.markdown("**Execution Engine**")
            st.write(execution_cfg.get("name", "n/a"))
            st.caption(exec_meta)
            st.markdown("**Risk Controls**")
            st.write(risk_meta)
            st.caption("Limits applied before orders leave the engine.")

        with pipeline_cols[2]:
            st.markdown("**Analytics & Monitoring**")
            st.write(f"{analytics_desc} · {analytics_backend}")
            if analytics_enabled:
                st.caption(f"DB: {analytics_db}")
            st.markdown("**Monitoring Channels**")
            enabled_text = "Enabled" if monitoring_enabled else "Disabled"
            st.write(f"{enabled_text} ({monitoring_channels})")

        st.markdown("### Bot Flow")
        st.graphviz_chart(_build_bot_flow_graph(config_data, config_path))
    else:
        st.info("Provide a valid config to see how SilkRoad wires data → strategy → execution.")

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
