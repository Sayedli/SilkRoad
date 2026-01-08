from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st
import yaml

TRENDING_REGIONS = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "DE": "Germany",
    "IN": "India",
}

WATCHLISTS = {
    "US Mega Caps": [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "description": "Consumer hardware + services"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ", "description": "Cloud + enterprise software"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ", "description": "Search + AI advertising"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ", "description": "E-commerce + AWS cloud"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "exchange": "NASDAQ", "description": "Social + VR"},
    ],
    "EV & Chips": [
        {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ", "description": "EV leader with energy storage"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "exchange": "NASDAQ", "description": "AI & GPU powerhouse"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "exchange": "NASDAQ", "description": "CPU + GPU challenger"},
        {"symbol": "ON", "name": "ON Semiconductor", "exchange": "NASDAQ", "description": "Auto & industrial silicon"},
    ],
    "US ETFs": [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "exchange": "NYSE", "description": "S&P 500 market beta"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ", "description": "Nasdaq-100 growth exposure"},
        {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "exchange": "NYSE", "description": "US small caps"},
        {"symbol": "ARKK", "name": "ARK Innovation ETF", "exchange": "NYSE", "description": "Disruptive tech basket"},
    ],
}

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


@st.cache_data(ttl=300)
def _fetch_trending_symbols(region: str, limit: int = 8) -> list[dict[str, Any]]:
    endpoint = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"
    try:
        response = requests.get(endpoint, params={"count": limit}, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    results = payload.get("finance", {}).get("result") or []
    if not results:
        return []

    quotes = results[0].get("quotes", [])[:limit]
    trending: list[dict[str, Any]] = []
    for quote in quotes:
        symbol = quote.get("symbol")
        if not symbol:
            continue
        trending.append(
            {
                "symbol": symbol,
                "name": quote.get("shortName") or quote.get("longName") or "Unknown",
                "change_pct": quote.get("regularMarketChangePercent"),
            }
        )
    return trending


@st.cache_data(ttl=60)
def _fetch_quote_snapshot(symbol: str) -> Optional[dict[str, Any]]:
    endpoint = "https://query1.finance.yahoo.com/v7/finance/quote"
    try:
        response = requests.get(endpoint, params={"symbols": symbol}, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    result = (payload.get("quoteResponse") or {}).get("result") or []
    if not result:
        return None
    quote = result[0]
    return {
        "price": quote.get("regularMarketPrice"),
        "change": quote.get("regularMarketChange"),
        "change_percent": quote.get("regularMarketChangePercent"),
        "exchange": quote.get("fullExchangeName"),
        "currency": quote.get("currency"),
        "as_of": quote.get("regularMarketTime"),
    }


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_percent(value: float) -> str:
    return f"{value:.2%}"


def _format_change(value: Optional[float]) -> str:
    if value is None:
        return "0.00%"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _set_selected_instrument(symbol: str, name: str, source_hint: str = "") -> None:
    st.session_state["selected_instrument"] = {
        "symbol": symbol,
        "name": name,
        "source_hint": source_hint,
    }


def _render_selected_instrument_notice() -> None:
    instrument = st.session_state.get("selected_instrument")
    if not instrument:
        return
    source_hint = instrument.get("source_hint") or "Choose a data feed that lists this ticker (polygon, alpaca, etc.)."
    quote = _fetch_quote_snapshot(instrument["symbol"])
    price = quote.get("price") if quote else None
    change = quote.get("change_percent") if quote else None
    quote_text = (
        f"{_format_currency(price)} ({_format_change(change)} intraday)"
        if price is not None
        else "Real-time quote unavailable."
    )
    st.markdown(
        f"""
        <div class="sr-card sr-card--hero">
            <div class="sr-card__label">Instrument focus</div>
            <div class="sr-card__value">{instrument['symbol']} · {instrument['name']}</div>
            <div class="sr-card__subtext">{quote_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(source_hint)
    st.code(
        f"""data:
  source: <your_equities_feed>
  symbol: "{instrument['symbol']}"
""",
        language="yaml",
    )


def _render_stock_explorer(trending: list[dict[str, Any]]) -> None:
    st.markdown("## Stock Explorer")
    focus = st.session_state.get("selected_instrument")
    if focus:
        st.success(f"Current focus: {focus['symbol']} · {focus['name']}")
    st.caption(
        "Browse live trending tickers or curated watchlists. Buttons below set the instrument focus."
    )
    explorer_cols = st.columns(2)

    with explorer_cols[0]:
        st.markdown("### Trending Right Now")
        if trending:
            for item in trending:
                symbol = item["symbol"]
                change = _format_change(item.get("change_pct"))
                st.markdown(f"**{symbol}** · {item['name']} — {change}")
                if st.button(f"Focus {symbol}", key=f"trend-btn-{symbol}"):
                    _set_selected_instrument(
                        symbol,
                        item["name"],
                        "Use an equities data feed (polygon/alpaca/custom) before running.",
                    )
                    st.success(f"{symbol} set as instrument focus.")
                    st.experimental_rerun()
        else:
            st.info("Trending feed unavailable; try the watchlists or refresh the page.")

    with explorer_cols[1]:
        st.markdown("### Curated Watchlists")
        watchlist_name = st.selectbox(
            "Collection", list(WATCHLISTS.keys()), key="explorer_watchlist_choice"
        )
        watch_items = WATCHLISTS[watchlist_name]
        for company in watch_items:
            description = company.get("description", "")
            st.markdown(
                f"**{company['symbol']}** · {company['name']} ({company.get('exchange', 'n/a')})  \n"
                f"{description}"
            )
            if st.button(
                f"Focus {company['symbol']}", key=f"watchlist-btn-{watchlist_name}-{company['symbol']}"
            ):
                _set_selected_instrument(
                    company["symbol"],
                    company["name"],
                    f"Exchange: {company.get('exchange', 'n/a')}. Ensure your data feed supports it.",
                )
                st.success(f"{company['symbol']} set as instrument focus.")
                st.experimental_rerun()
        st.caption("Focused tickers update the instructions below the config preview.")


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
    st.caption("Pick what to trade, test your idea, and review results in plain language.")
    _apply_robinhood_theme()

    default_config = "configs/example.paper.yml"
    config_path_input = st.sidebar.text_input("Config path", value=default_config)
    config_path = Path(config_path_input).expanduser().resolve()

    st.sidebar.markdown("### Quick Actions")
    run_backtest_clicked = st.sidebar.button("Run Backtest", type="primary")
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Tips (plain-English)**
\n- Think of the config as your "bot recipe."
\n- Duplicate the sample recipe to try changes: `cp configs/example.paper.yml configs/my_test.yml`.
\n- Your trade history and stats are saved automatically.
        """
    )
    st.sidebar.markdown("### What This Tracks")
    st.sidebar.write(
        "- Price chart + account growth\n"
        "- Trades the bot would make\n"
        "- Performance stats (wins, losses, risk)"
    )

    st.sidebar.markdown("### What People Are Watching")
    region_choice = st.sidebar.selectbox(
        "Market", list(TRENDING_REGIONS.keys()), format_func=lambda code: TRENDING_REGIONS[code]
    )
    trending_symbols = _fetch_trending_symbols(region_choice)
    stock_explorer_trending = trending_symbols
    if trending_symbols:
        option_indices = list(range(len(trending_symbols)))

        def _format_option(idx: int) -> str:
            item = trending_symbols[idx]
            change_txt = _format_change(item.get("change_pct"))
            return f"{item['symbol']} · {item['name']} ({change_txt})"

        selected_idx = st.sidebar.selectbox(
            "Top movers right now", option_indices, format_func=_format_option
        )
        selected = trending_symbols[selected_idx]
        change_text = _format_change(selected.get("change_pct"))
        st.sidebar.markdown(f"**Selected:** `{selected['symbol']}` ({change_text})")
        if st.sidebar.button("Focus selected trending symbol", key="sidebar_focus_trending"):
            _set_selected_instrument(
                selected["symbol"],
                selected["name"],
                "Pick a data feed that supports equities (e.g., polygon, alpaca, or your custom adapter).",
            )
            st.sidebar.success(f"{selected['symbol']} ready—update `data.symbol` to this ticker.")
            st.experimental_rerun()
        st.sidebar.caption("Use this to fill your pick below.")
    else:
        st.sidebar.info("Trending list unavailable right now.")

    st.sidebar.markdown("### Starter Watchlists")
    watchlist_names = list(WATCHLISTS.keys())
    selected_watchlist = st.sidebar.selectbox("Collection", watchlist_names, key="watchlist_collection")
    collection = WATCHLISTS[selected_watchlist]
    collection_indices = list(range(len(collection)))

    def _format_watchlist_option(idx: int) -> str:
        item = collection[idx]
        return f"{item['symbol']} · {item['name']} ({item['exchange']})"

    selected_company_idx = st.sidebar.selectbox(
        "Company", collection_indices, format_func=_format_watchlist_option, key="watchlist_company"
    )
    selected_company = collection[selected_company_idx]
    st.sidebar.write(selected_company["description"])
    if st.sidebar.button("Focus selected company", key="sidebar_focus_watchlist"):
        _set_selected_instrument(
            selected_company["symbol"],
            selected_company["name"],
            f"Exchange: {selected_company['exchange']}. Choose a data feed that supports this venue.",
        )
        st.sidebar.success(f"{selected_company['symbol']} ready—update `data.symbol` accordingly.")
        st.experimental_rerun()
    st.sidebar.caption("Pick a company here, then update it in your config when you are ready.")

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
        st.subheader("Your Bot Recipe")
        if config_path.exists():
            st.write(f"Using recipe: `{config_path}`")
        else:
            st.warning("Recipe file not found.")
    with preview_col:
        st.subheader("Recipe Preview")
        preview = _load_config_preview(config_path)
        if preview:
            st.code(preview, language="yaml")
        else:
            st.info("Pick a valid recipe file to preview its contents.")
    config_data = _parse_config_text(preview) if preview else {}

    st.markdown("## What This Bot Trades")
    if st.session_state.get("selected_instrument"):
        _render_selected_instrument_notice()
    else:
        st.info("Pick a company on the left to fill in your trade symbol.")

    _render_stock_explorer(stock_explorer_trending)

    st.markdown("## How the Bot Works (Simple View)")
    if config_data:
        st.caption("A quick summary of your setup: data → strategy → simulated trading.")
        data_col, execution_col, telemetry_col = st.columns(3)

        data_cfg = config_data.get("data", {})
        strategy_cfg = config_data.get("strategy", {})
        execution_cfg = config_data.get("execution", {})
        risk_cfg = config_data.get("risk", {})
        analytics_cfg = config_data.get("analytics", {})
        monitoring_cfg = config_data.get("monitoring", {}) or {}

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
        monitoring_channels = ", ".join((monitoring_cfg.get("channels") or {}).keys()) or "none"

        _status_card(
            data_col,
            "Market Data",
            data_desc,
            data_meta_str or "Waiting for price updates.",
        )
        _status_card(
            data_col,
            "Trade Style",
            strategy_cfg.get("name", "n/a"),
            strategy_meta,
        )

        _status_card(
            execution_col,
            "Trading Mode",
            execution_cfg.get("name", "n/a"),
            exec_meta,
        )
        _status_card(
            execution_col,
            "Safety Rules",
            risk_meta,
            "Limits applied before any trade.",
        )

        _status_card(
            telemetry_col,
            "Stats & History",
            f"{analytics_desc} · {analytics_backend}",
            f"DB: {analytics_db}" if analytics_enabled else "Off",
        )
        enabled_text = "Enabled" if monitoring_enabled else "Disabled"
        _status_card(
            telemetry_col,
            "Alerts",
            f"{enabled_text}",
            f"Channels: {monitoring_channels}",
        )

        st.markdown("### Data → Strategy → Trades")
        st.graphviz_chart(_build_bot_flow_graph(config_data, config_path))
    else:
        st.info("Add a valid recipe file to see your bot flow.")

    if "last_result" in st.session_state:
        result: BacktestResult = st.session_state["last_result"]
        st.markdown("## Test Results")
        hero_cols = st.columns(4)
        starting_cash = result.starting_cash
        pnl = result.ending_value - starting_cash
        pnl_text = f"{_format_currency(pnl)} vs start"
        _metric_card(hero_cols[0], "Ending Value", _format_currency(result.ending_value), pnl_text)
        _metric_card(
            hero_cols[1],
            "Overall Gain",
            _format_percent(result.total_return),
            "Since run start",
        )
        _metric_card(hero_cols[2], "Trades", str(result.total_trades), "Fills executed")
        sharpe_display = f"{result.sharpe_ratio:.2f}" if result.sharpe_ratio is not None else "n/a"
        completed_label = result.completed_at.strftime("%b %d · %H:%M")
        _metric_card(hero_cols[3], "Risk-Adjusted", sharpe_display, f"Run completed {completed_label}")

        extra_metrics = result.extra_metrics or {}
        if extra_metrics:
            st.markdown("### Additional Metrics")
            extra_df = pd.DataFrame(list(extra_metrics.items()), columns=["Metric", "Value"])
            st.dataframe(extra_df, use_container_width=True, hide_index=True)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("### Price History")
            if result.price_series is not None and not result.price_series.empty:
                chart = _build_altair_chart(result.price_series, "price", "#8fffc2")
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
                else:
                    price_df = result.price_series.to_frame(name="price")
                    st.line_chart(price_df, use_container_width=True)
            else:
                st.info("Price series not available for this run.")
        with chart_col2:
            st.markdown("### Equity Curve")
            if result.equity_curve is not None and not result.equity_curve.empty:
                chart = _build_altair_chart(result.equity_curve, "equity", "#66c2ff")
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
                else:
                    equity_df = result.equity_curve.to_frame(name="equity")
                    st.line_chart(equity_df, use_container_width=True)
            else:
                st.info("Equity curve not available.")

        trades_df = st.session_state.get("last_trades")
        metrics_df = st.session_state.get("last_metrics")
        st.markdown("## Activity & History")
        analytics_tabs = st.tabs(["Recent Activity", "Recent Trades", "Performance Logs"])

        with analytics_tabs[0]:
            activity = _build_activity_feed(trades_df, metrics_df)
            if activity:
                for item in activity:
                    timestamp = (
                        item["timestamp"].strftime("%b %d · %H:%M")
                        if isinstance(item["timestamp"], datetime)
                        else str(item["timestamp"])
                    )
                    st.markdown(
                        f"""
                        <div class="sr-activity">
                            <div class="sr-activity__time">{timestamp}</div>
                            <div class="sr-activity__title">{item['title']}</div>
                            <div class="sr-activity__body">{item['body']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No fills or performance events captured yet.")

        with analytics_tabs[1]:
            if trades_df is not None and not trades_df.empty:
                trades_display = trades_df.copy()
                trades_display["timestamp"] = trades_display["timestamp"].dt.tz_localize(None)
                st.dataframe(trades_display, use_container_width=True)
            else:
                st.info("No trades logged yet.")

        with analytics_tabs[2]:
            if metrics_df is not None and not metrics_df.empty:
                metrics_display = metrics_df.copy()
                metrics_display["timestamp"] = metrics_display["timestamp"].dt.tz_localize(None)
                st.dataframe(metrics_display, use_container_width=True)
            else:
                st.info("No performance metrics logged yet.")
    else:
        st.markdown("## Test Results")
        st.info("Run a backtest to see charts, trades, and stats.")


if __name__ == "__main__":
    main()
