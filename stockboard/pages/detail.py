"""M8: 종목 상세 페이지 — 캔들차트 + 지표 + 매매 이력"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date

import models
import data_fetcher
import indicators

dash.register_page(__name__, path="/detail", name="상세", order=10)

PERIOD_MAP = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}

# ── 차트 생성 ─────────────────────────────────────────────────────────────────

def _build_chart(ticker: str, period_label: str, ind_configs: list) -> go.Figure:
    period = PERIOD_MAP.get(period_label, "6mo")
    df = data_fetcher.get_historical_data(ticker, period)

    has_macd = any(c["indicator"] == "MACD" and c["enabled"] for c in ind_configs)
    rows = 3 if has_macd else 2
    row_heights = [0.6, 0.15, 0.25] if has_macd else [0.75, 0.25]
    specs = [[{"secondary_y": False}]] * rows

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.03,
        specs=specs,
    )

    if df.empty:
        fig.add_annotation(text="데이터 없음", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False,
                           font={"size": 18, "color": "#a0a0c0"})
        return _apply_layout(fig, ticker)

    # 캔들스틱
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=ticker,
        increasing_line_color="#26de81",
        decreasing_line_color="#fc5c65",
    ), row=1, col=1)

    colors = ["#7ecfff", "#ffd32a", "#ff6b81", "#a29bfe", "#fd9644"]

    # 이동평균
    ma_cfg = next((c for c in ind_configs if c["indicator"] == "MA" and c["enabled"]), None)
    if ma_cfg:
        periods = ma_cfg["params"].get("periods", [5, 20, 60, 120])
        ma_df = indicators.calculate_ma(df, periods)
        for i, col in enumerate(ma_df.columns):
            fig.add_trace(go.Scatter(
                x=ma_df.index, y=ma_df[col],
                name=col, line={"color": colors[i % len(colors)], "width": 1},
                opacity=0.8,
            ), row=1, col=1)

    # 볼린저 밴드
    bb_cfg = next((c for c in ind_configs if c["indicator"] == "BB" and c["enabled"]), None)
    if bb_cfg:
        bb = indicators.calculate_bb(df, **bb_cfg["params"])
        if not bb.empty:
            fig.add_trace(go.Scatter(x=bb.index, y=bb["Upper"], name="BB Upper",
                                     line={"color": "#a29bfe", "width": 1, "dash": "dot"},
                                     opacity=0.7), row=1, col=1)
            fig.add_trace(go.Scatter(x=bb.index, y=bb["Lower"], name="BB Lower",
                                     line={"color": "#a29bfe", "width": 1, "dash": "dot"},
                                     fill="tonexty", fillcolor="rgba(162,155,254,0.05)",
                                     opacity=0.7), row=1, col=1)

    # 거래량
    vol_colors = ["#26de81" if c >= o else "#fc5c65"
                  for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량",
                         marker_color=vol_colors, opacity=0.6),
                  row=2, col=1)

    # MACD
    if has_macd:
        macd_cfg = next(c for c in ind_configs if c["indicator"] == "MACD" and c["enabled"])
        macd_df = indicators.calculate_macd(df, **macd_cfg["params"])
        if not macd_df.empty:
            fig.add_trace(go.Scatter(x=macd_df.index, y=macd_df["MACD"],
                                     name="MACD", line={"color": "#7ecfff", "width": 1.5}),
                          row=3, col=1)
            fig.add_trace(go.Scatter(x=macd_df.index, y=macd_df["Signal"],
                                     name="Signal", line={"color": "#ffd32a", "width": 1.5}),
                          row=3, col=1)
            hist_colors = ["#26de81" if v >= 0 else "#fc5c65"
                           for v in macd_df["Histogram"].fillna(0)]
            fig.add_trace(go.Bar(x=macd_df.index, y=macd_df["Histogram"],
                                 name="Histogram", marker_color=hist_colors, opacity=0.7),
                          row=3, col=1)

    return _apply_layout(fig, ticker)


def _apply_layout(fig: go.Figure, ticker: str) -> go.Figure:
    fig.update_layout(
        plot_bgcolor="#12122a",
        paper_bgcolor="#1e1e30",
        font={"color": "#e0e0e0", "size": 11},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.02, "x": 0},
        margin={"l": 50, "r": 20, "t": 40, "b": 20},
        height=560,
        hovermode="x unified",
        title={"text": ticker, "font": {"size": 14}},
    )
    fig.update_xaxes(gridcolor="#2a2a45", showgrid=True)
    fig.update_yaxes(gridcolor="#2a2a45", showgrid=True)
    return fig


# ── 매매 이력 테이블 ──────────────────────────────────────────────────────────

def _trade_table(stock_id: int):
    trades = models.get_trades(stock_id)
    if not trades:
        return html.P("매매 이력이 없습니다.", className="text-muted")

    rows = []
    for t in trades:
        type_badge = dbc.Badge(
            "매수" if t["trade_type"] == "buy" else "매도",
            color="success" if t["trade_type"] == "buy" else "danger",
        )
        rows.append(html.Tr([
            html.Td(t["trade_date"]),
            html.Td(type_badge),
            html.Td(f"{t['quantity']:,.2f}"),
            html.Td(f"{t['price']:,.2f}"),
            html.Td(f"{t['fee']:,.0f}"),
            html.Td(t.get("memo", "") or "-"),
            html.Td([
                dbc.Button("수정", id={"type": "det-edit-trade", "index": t["id"]},
                           color="secondary", size="sm", className="btn-action me-1"),
                dbc.Button("삭제", id={"type": "det-del-trade", "index": t["id"]},
                           color="danger", size="sm", className="btn-action"),
            ]),
        ]))

    return dbc.Table(
        [html.Thead(html.Tr([html.Th(h) for h in
                             ["날짜", "유형", "수량", "단가", "수수료", "메모", ""]])),
         html.Tbody(rows)],
        hover=True, responsive=True, size="sm", className="table-dark",
    )


# ── 레이아웃 ──────────────────────────────────────────────────────────────────

def layout(ticker=None, **_):
    if not ticker:
        return html.Div([
            html.H4("종목 상세", className="page-title"),
            dbc.Alert("티커를 지정하세요. (예: /detail?ticker=AAPL)", color="warning"),
        ])

    ticker = ticker.upper()
    pi = data_fetcher.get_stock_info(ticker)
    stock = models.get_stock_by_ticker(ticker)
    ind_configs = models.get_indicator_configs()

    cur = pi.get("current_price", 0)
    chg = pi.get("change_pct", 0)
    chg_cls = "text-pos" if chg > 0 else ("text-neg" if chg < 0 else "text-neu")
    sign = "+" if chg > 0 else ""

    # 신호
    try:
        df3 = data_fetcher.get_historical_data(ticker, "3mo")
        sigs = indicators.get_signals(df3, ind_configs)
    except Exception:
        sigs = []

    sig_badges = [dbc.Badge(s["description"], color=s["color"],
                            className="signal-badge me-1 mb-1")
                  for s in sigs] or [html.Span("신호 없음", className="text-neu")]

    # 보유 현황
    position_row = html.Span()
    if stock:
        qty, avg = models.calculate_position(stock["id"])
        real_pnl = models.calculate_realized_pnl(stock["id"])
        unreal = (cur - avg) * qty if avg else 0
        unreal_pct = ((cur - avg) / avg * 100) if avg else 0
        position_row = dbc.Row([
            dbc.Col(_stat_card("보유 수량", f"{qty:,.2f}"), md=2),
            dbc.Col(_stat_card("평단가", f"{avg:,.2f}"), md=2),
            dbc.Col(_stat_card("평가금액", f"{cur*qty:,.0f}"), md=2),
            dbc.Col(_stat_card(
                "평가 손익",
                f"{unreal:+,.0f} ({unreal_pct:+.2f}%)",
                "text-pos" if unreal >= 0 else "text-neg"), md=3),
            dbc.Col(_stat_card(
                "실현 손익",
                f"{real_pnl:+,.0f}",
                "text-pos" if real_pnl >= 0 else "text-neg"), md=3),
        ], className="mb-3 g-2")

    return html.Div([
        # 헤더
        dbc.Row([
            dbc.Col([
                html.H4([
                    dbc.Badge(ticker, color="primary", className="me-2"),
                    pi.get("name", ""),
                ], className="page-title mb-1"),
                html.Span(f"{cur:,.2f}", className="fs-4 fw-bold me-3"),
                html.Span(f"{sign}{chg:.2f}%", className=f"fs-5 {chg_cls}"),
            ]),
            dbc.Col([
                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "새로고침"],
                           id="det-refresh", color="secondary", size="sm", className="me-2"),
                dbc.Button([html.I(className="bi bi-plus-lg me-1"), "매매 추가"],
                           id="det-open-trade", color="primary", size="sm",
                           disabled=stock is None),
            ], className="d-flex align-items-start justify-content-end"),
        ], className="mb-2 align-items-start"),

        # 신호 패널
        dbc.Card(dbc.CardBody([
            html.Small("이상 신호", className="text-muted d-block mb-1"),
            html.Div(sig_badges),
        ]), className="mb-3", style={"padding": "8px"}),

        # 보유 현황 통계
        position_row,

        # 차트 기간 선택
        dbc.Row([
            dbc.Col(
                dbc.RadioItems(
                    id="det-period",
                    options=[{"label": p, "value": p} for p in ["1M", "3M", "6M", "1Y"]],
                    value="6M",
                    inline=True,
                    inputClassName="me-1",
                    labelClassName="me-3",
                ),
            ),
        ], className="mb-2"),

        # 차트
        dcc.Graph(id="det-chart", config={"displayModeBar": False},
                  className="chart-container"),

        # 매매 이력
        html.Hr(className="my-4"),
        html.H5("📋 매매 이력", className="mb-3"),
        html.Div(id="det-trade-table"),

        # 상태
        dcc.Store(id="det-ticker", data=ticker),
        dcc.Store(id="det-stock-id", data=stock["id"] if stock else None),
        dcc.Store(id="det-sel-trade-id"),
        dcc.Store(id="det-trigger", data=0),

        # 매매 추가/수정 모달
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="det-trade-modal-title")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("거래 유형"),
                        dbc.RadioItems(
                            id="det-m-type",
                            options=[{"label": "매수", "value": "buy"},
                                     {"label": "매도", "value": "sell"}],
                            value="buy", inline=True,
                        ),
                    ], md=12, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([dbc.Label("거래일 *"),
                             dbc.Input(id="det-m-date", type="date",
                                       value=str(date.today()))], md=6),
                    dbc.Col([dbc.Label("수량 *"),
                             dbc.Input(id="det-m-qty", type="number", min=0)], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("단가 *"),
                             dbc.Input(id="det-m-price", type="number", min=0)], md=6),
                    dbc.Col([dbc.Label("수수료"),
                             dbc.Input(id="det-m-fee", type="number", min=0, value=0)], md=6),
                ], className="mb-3"),
                dbc.Label("메모"),
                dbc.Textarea(id="det-m-memo", rows=2),
                html.Div(id="det-trade-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="det-save-trade", color="primary", className="me-2"),
                dbc.Button("닫기", id="det-close-trade-modal", color="secondary"),
            ]),
        ], id="det-trade-modal", is_open=False, backdrop="static"),

        # 삭제 확인
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("매매 이력 삭제")),
            dbc.ModalBody("이 매매 이력을 삭제하시겠습니까?"),
            dbc.ModalFooter([
                dbc.Button("삭제", id="det-confirm-del-trade", color="danger", className="me-2"),
                dbc.Button("취소", id="det-cancel-del-trade", color="secondary"),
            ]),
        ], id="det-del-trade-modal", is_open=False),

        dbc.Toast(id="det-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),
    ])


def _stat_card(label, value, val_cls=""):
    return html.Div([
        html.Div(label, className="stat-label"),
        html.Div(value, className=f"stat-value {val_cls}"),
    ], className="stat-card")


# ── 콜백 ──────────────────────────────────────────────────────────────────────

@callback(
    Output("det-chart", "figure"),
    Input("det-period", "value"),
    Input("det-trigger", "data"),
    Input("det-refresh", "n_clicks"),
    State("det-ticker", "data"),
    prevent_initial_call=False,
)
def update_chart(period, _trigger, _refresh, ticker):
    if not ticker:
        return go.Figure()
    if ctx.triggered_id == "det-refresh":
        data_fetcher.invalidate(ticker)
    ind_configs = models.get_indicator_configs()
    return _build_chart(ticker, period or "6M", ind_configs)


@callback(
    Output("det-trade-table", "children"),
    Input("det-trigger", "data"),
    State("det-stock-id", "data"),
    prevent_initial_call=False,
)
def update_trade_table(_trigger, stock_id):
    if not stock_id:
        return html.P("보유 등록된 종목이 아닙니다. 보유 종목 페이지에서 추가하세요.",
                      className="text-muted")
    return _trade_table(stock_id)


# 매매 추가 모달 열기
@callback(
    Output("det-trade-modal", "is_open", allow_duplicate=True),
    Output("det-trade-modal-title", "children"),
    Output("det-m-type", "value"),
    Output("det-m-date", "value"),
    Output("det-m-qty", "value"),
    Output("det-m-price", "value"),
    Output("det-m-fee", "value"),
    Output("det-m-memo", "value"),
    Output("det-sel-trade-id", "data"),
    Input("det-open-trade", "n_clicks"),
    Input({"type": "det-edit-trade", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_trade_modal(_add, _edits):
    triggered = ctx.triggered_id
    if triggered == "det-open-trade":
        return True, "매매 추가", "buy", str(date.today()), None, None, 0, "", None

    if isinstance(triggered, dict) and triggered.get("type") == "det-edit-trade":
        if any(n for n in _edits if n):
            tid = triggered["index"]
            t = models.get_trade(tid)
            if t:
                return (True, "매매 수정",
                        t["trade_type"], t["trade_date"],
                        t["quantity"], t["price"], t["fee"],
                        t.get("memo", ""), tid)

    return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update


@callback(
    Output("det-trade-modal", "is_open", allow_duplicate=True),
    Output("det-trade-err", "children"),
    Output("det-trigger", "data", allow_duplicate=True),
    Output("det-toast", "is_open", allow_duplicate=True),
    Output("det-toast", "children", allow_duplicate=True),
    Input("det-save-trade", "n_clicks"),
    State("det-stock-id", "data"),
    State("det-m-type", "value"),
    State("det-m-date", "value"),
    State("det-m-qty", "value"),
    State("det-m-price", "value"),
    State("det-m-fee", "value"),
    State("det-m-memo", "value"),
    State("det-sel-trade-id", "data"),
    State("det-trigger", "data"),
    prevent_initial_call=True,
)
def save_trade(_n, stock_id, trade_type, trade_date, qty, price, fee, memo, sel_tid, trigger):
    if not all([stock_id, trade_date, qty, price]):
        return no_update, "필수 항목을 모두 입력하세요.", no_update, no_update, no_update
    try:
        qty_f = float(qty)
        price_f = float(price)
        fee_f = float(fee or 0)
    except (TypeError, ValueError):
        return no_update, "수치 값이 올바르지 않습니다.", no_update, no_update, no_update

    if sel_tid:
        models.update_trade(sel_tid, trade_type=trade_type, quantity=qty_f,
                            price=price_f, trade_date=trade_date, fee=fee_f, memo=memo or "")
        msg = "매매 이력 수정 완료"
    else:
        models.create_trade(stock_id, trade_type, qty_f, price_f,
                            trade_date, fee_f, memo or "")
        msg = "매매 이력 추가 완료"

    return False, "", (trigger or 0) + 1, True, msg


@callback(
    Output("det-trade-modal", "is_open", allow_duplicate=True),
    Input("det-close-trade-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_trade_modal(_n):
    return False


@callback(
    Output("det-del-trade-modal", "is_open", allow_duplicate=True),
    Output("det-sel-trade-id", "data", allow_duplicate=True),
    Input({"type": "det-del-trade", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_del_trade(clicks):
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "det-del-trade":
        if any(n for n in clicks if n):
            return True, triggered["index"]
    return no_update, no_update


@callback(
    Output("det-del-trade-modal", "is_open", allow_duplicate=True),
    Output("det-trigger", "data", allow_duplicate=True),
    Output("det-toast", "is_open", allow_duplicate=True),
    Output("det-toast", "children", allow_duplicate=True),
    Input("det-confirm-del-trade", "n_clicks"),
    Input("det-cancel-del-trade", "n_clicks"),
    State("det-sel-trade-id", "data"),
    State("det-trigger", "data"),
    prevent_initial_call=True,
)
def execute_del_trade(_conf, _cancel, sel_tid, trigger):
    if ctx.triggered_id == "det-confirm-del-trade" and sel_tid:
        models.delete_trade(sel_tid)
        return False, (trigger or 0) + 1, True, "매매 이력 삭제 완료"
    return False, no_update, no_update, no_update
