"""M10: 매매이력 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta

import models

dash.register_page(__name__, path="/trades", name="매매이력", order=5)

_PERIOD_OPTS = [
    {"label": "전체 기간", "value": "0"},
    {"label": "최근 1개월", "value": "30"},
    {"label": "최근 3개월", "value": "90"},
    {"label": "최근 6개월", "value": "180"},
    {"label": "최근 1년",   "value": "365"},
]

_TYPE_OPTS = [
    {"label": "전체",  "value": "ALL"},
    {"label": "매수",  "value": "buy"},
    {"label": "매도",  "value": "sell"},
]


def _ticker_opts():
    stocks = models.get_stocks()
    return [{"label": "전체 종목", "value": "ALL"}] + [
        {"label": f"{s['name'] or s['ticker']} ({s['ticker']})", "value": s["ticker"]}
        for s in stocks
    ]


def _apply_filters(trades, period, ticker, type_):
    result = trades
    if period and period != "0":
        cutoff = (datetime.now() - timedelta(days=int(period))).strftime("%Y-%m-%d")
        result = [t for t in result if t["trade_date"] >= cutoff]
    if ticker and ticker != "ALL":
        result = [t for t in result if t["ticker"] == ticker]
    if type_ and type_ != "ALL":
        result = [t for t in result if t["trade_type"] == type_]
    return result


def _summary_cards(trades):
    total_buy  = sum(t["quantity"] * t["price"] for t in trades if t["trade_type"] == "buy")
    total_sell = sum(t["quantity"] * t["price"] for t in trades if t["trade_type"] == "sell")
    sell_pnls  = [t["realized_pnl"]  for t in trades if t["trade_type"] == "sell" and t["realized_pnl"]  is not None]
    sell_rates = [t["return_rate"]   for t in trades if t["trade_type"] == "sell" and t["return_rate"]   is not None]
    total_pnl  = sum(sell_pnls)
    avg_rate   = sum(sell_rates) / len(sell_rates) if sell_rates else None

    pnl_color  = "success" if total_pnl >= 0 else "danger"
    rate_color = "success" if (avg_rate or 0) >= 0 else "danger"

    def _r(v):
        if v is None:
            return "-"
        s = "+" if v >= 0 else ""
        return f"{s}{v:.2f}%"

    def _p(v):
        s = "+" if v >= 0 else ""
        return f"{s}{v:,.0f}원"

    cards = [
        ("원 매수금액", f"{total_buy:,.0f}원",   "primary"),
        ("원 매도금액", f"{total_sell:,.0f}원",  "info"),
        ("실현손익",    _p(total_pnl),           pnl_color),
        ("평균수익률",  _r(avg_rate),            rate_color),
    ]
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P(label, className="text-muted small mb-1"),
            html.H5(value, className=f"text-{color} fw-bold mb-0"),
        ])), md=3)
        for label, value, color in cards
    ], className="g-2 mb-3")


def _trade_table(trades):
    if not trades:
        return html.P("조건에 맞는 매매이력이 없습니다.",
                      className="text-muted text-center py-4")

    rows = []
    for t in trades:
        is_buy  = t["trade_type"] == "buy"
        badge   = (dbc.Badge("매수", color="success", pill=True)
                   if is_buy else dbc.Badge("매도", color="danger", pill=True))

        cat_color = t.get("category_color") or "#6c757d"
        cat_dot   = html.Span(style={
            "display": "inline-block", "width": 8, "height": 8,
            "borderRadius": "50%", "backgroundColor": cat_color,
            "marginRight": 4, "verticalAlign": "middle",
        })

        pnl  = t.get("realized_pnl")
        rate = t.get("return_rate")

        if pnl is not None:
            pc   = "text-success" if pnl >= 0 else "text-danger"
            pnl_cell = html.Span(f"{'+'if pnl>=0 else ''}{pnl:,.0f}원", className=pc)
        else:
            pnl_cell = html.Span("-", className="text-muted")

        if rate is not None:
            rc    = "text-success" if rate >= 0 else "text-danger"
            rate_cell = html.Span(f"{'+'if rate>=0 else ''}{rate:.2f}%", className=rc)
        else:
            rate_cell = html.Span("-", className="text-muted")

        avg_bp = t.get("avg_buy_price")
        avg_cell = (f"{avg_bp:,.0f}원" if avg_bp else "-") if not is_buy else html.Span("-", className="text-muted")

        rows.append(html.Tr([
            html.Td(t["trade_date"], style={"whiteSpace": "nowrap"}),
            html.Td([
                html.Span(t.get("stock_name") or t["ticker"], className="fw-semibold d-block"),
                html.Small(t["ticker"], className="text-muted"),
            ]),
            html.Td([cat_dot, t.get("category_name") or "-"]),
            html.Td(badge, className="text-center"),
            html.Td(f"{t['quantity']:,.0f}주"),
            html.Td(f"{t['price']:,.0f}원",              style={"whiteSpace": "nowrap"}),
            html.Td(f"{t['quantity']*t['price']:,.0f}원", style={"whiteSpace": "nowrap"}),
            html.Td(avg_cell,   style={"whiteSpace": "nowrap"}),
            html.Td(pnl_cell,   style={"whiteSpace": "nowrap"}),
            html.Td(rate_cell),
            html.Td(
                dbc.Button("삭제", id={"type": "trade-del-btn", "index": t["id"]},
                           color="outline-danger", size="sm"),
                className="text-center",
            ),
        ]))

    return dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("날짜"), html.Th("종목"), html.Th("카테고리"),
                html.Th("구분", className="text-center"),
                html.Th("수량"), html.Th("단가"), html.Th("매매금액"),
                html.Th("평균매입가"), html.Th("실현손익"), html.Th("수익률"),
                html.Th(""),
            ]), className="table-secondary"),
            html.Tbody(rows),
        ],
        className="table-dark table-hover table-bordered align-middle mb-0",
        responsive=True,
    )


def layout():
    return html.Div([
        html.H4("📋 매매이력", className="page-title"),

        dbc.Row([
            dbc.Col(dbc.Select(id="tr-period", options=_PERIOD_OPTS, value="0"), md=2),
            dbc.Col(dbc.Select(id="tr-ticker", options=_ticker_opts(), value="ALL"), md=3),
            dbc.Col(dbc.Select(id="tr-type",   options=_TYPE_OPTS,    value="ALL"), md=2),
            dbc.Col(
                dbc.Button("새로고침", id="tr-refresh", color="secondary",
                           outline=True, size="sm"),
                md="auto", className="d-flex align-items-center",
            ),
        ], className="mb-3 g-2"),

        html.Div(id="tr-summary"),
        html.Div(id="tr-table"),

        dcc.Store(id="tr-trigger", data=0),
        dcc.Store(id="tr-sel-id"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("매매이력 삭제")),
            dbc.ModalBody(id="tr-del-body"),
            dbc.ModalFooter([
                dbc.Button("삭제", id="tr-del-confirm", color="danger", className="me-2"),
                dbc.Button("취소", id="tr-del-cancel", color="secondary"),
            ]),
        ], id="tr-del-modal", is_open=False),

        dbc.Toast(id="tr-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("tr-summary", "children"),
    Output("tr-table",   "children"),
    Input("tr-trigger",  "data"),
    Input("tr-refresh",  "n_clicks"),
    Input("tr-period",   "value"),
    Input("tr-ticker",   "value"),
    Input("tr-type",     "value"),
    prevent_initial_call=False,
)
def render_table(_trigger, _refresh, period, ticker, type_):
    all_trades = models.get_all_trades_enriched()
    filtered   = _apply_filters(all_trades, period, ticker, type_)
    return _summary_cards(filtered), _trade_table(filtered)


@callback(
    Output("tr-del-modal", "is_open",     allow_duplicate=True),
    Output("tr-del-body",  "children"),
    Output("tr-sel-id",    "data"),
    Input({"type": "trade-del-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_del_modal(n_clicks):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update, no_update
    if not any(n for n in n_clicks if n):
        return no_update, no_update, no_update

    trade_id = triggered["index"]
    trade    = models.get_trade(trade_id)
    if not trade:
        return no_update, no_update, no_update

    stock      = models.get_stock(trade["stock_id"])
    type_label = "매수" if trade["trade_type"] == "buy" else "매도"

    body = html.Div([
        html.P("아래 매매이력을 삭제하시겠습니까?", className="mb-2"),
        dbc.Table([
            html.Tbody([
                html.Tr([html.Td("종목", className="text-muted"),
                         html.Td(f"{stock['name']} ({stock['ticker']})")]),
                html.Tr([html.Td("구분", className="text-muted"), html.Td(type_label)]),
                html.Tr([html.Td("날짜", className="text-muted"), html.Td(trade["trade_date"])]),
                html.Tr([html.Td("수량", className="text-muted"),
                         html.Td(f"{trade['quantity']:,.0f}주")]),
                html.Tr([html.Td("단가", className="text-muted"),
                         html.Td(f"{trade['price']:,.0f}원")]),
            ])
        ], size="sm", className="table-dark table-bordered mb-2"),
        html.P("※ 삭제 시 보유 포지션(수량·평단가)이 변경됩니다.",
               className="text-warning small mb-0"),
    ])
    return True, body, trade_id


@callback(
    Output("tr-del-modal",  "is_open",  allow_duplicate=True),
    Output("tr-trigger",    "data",     allow_duplicate=True),
    Output("tr-toast",      "is_open",  allow_duplicate=True),
    Output("tr-toast",      "children", allow_duplicate=True),
    Input("tr-del-confirm", "n_clicks"),
    Input("tr-del-cancel",  "n_clicks"),
    State("tr-sel-id",      "data"),
    State("tr-trigger",     "data"),
    prevent_initial_call=True,
)
def execute_delete(_confirm, _cancel, sel_id, trigger):
    if ctx.triggered_id == "tr-del-confirm" and sel_id:
        models.delete_trade(sel_id)
        return False, (trigger or 0) + 1, True, "매매이력이 삭제되었습니다."
    return False, no_update, no_update, no_update
