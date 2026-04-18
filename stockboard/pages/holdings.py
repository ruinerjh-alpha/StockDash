"""M6: 보유 종목 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc
import json
from datetime import date

import models
import data_fetcher
import indicators

dash.register_page(__name__, path="/", name="보유 종목", order=0)


def _fmt_price(v, currency=""):
    if v is None or v == 0:
        return "-"
    if abs(v) >= 1_000_000:
        return f"{currency}{v:,.0f}"
    if abs(v) >= 1:
        return f"{currency}{v:,.2f}"
    return f"{currency}{v:.4f}"


def _pct_span(pct):
    cls = "text-pos" if pct > 0 else ("text-neg" if pct < 0 else "text-neu")
    sign = "+" if pct > 0 else ""
    return html.Span(f"{sign}{pct:.2f}%", className=cls)


def _signal_badges(sigs):
    if not sigs:
        return html.Span("-", className="text-neu")
    return html.Span([
        dbc.Badge(s["description"], color=s["color"],
                  className="signal-badge me-1")
        for s in sigs
    ])


def _build_stock_row(stock, price_info, qty, avg_price, sigs):
    sid = stock["id"]
    ticker = stock["ticker"]
    cur = price_info.get("current_price", 0)
    chg = price_info.get("change_pct", 0)

    unreal_amt = (cur - avg_price) * qty if avg_price and qty else 0
    unreal_pct = ((cur - avg_price) / avg_price * 100) if avg_price else 0
    total_val = cur * qty

    no_position = (qty == 0 and avg_price == 0)

    action_btns = []
    if no_position:
        action_btns.append(
            dbc.Button("매입 입력", id={"type": "hld-pos-btn", "index": sid},
                       color="outline-warning", size="sm", className="btn-action me-1")
        )
    else:
        action_btns.append(
            dbc.Button("매매", id={"type": "hld-trade-btn", "index": sid},
                       color="outline-info", size="sm", className="btn-action me-1")
        )
    action_btns += [
        dbc.Button("수정", id={"type": "hld-edit-btn", "index": sid},
                   color="secondary", size="sm", className="btn-action me-1"),
        dbc.Button("삭제", id={"type": "hld-del-btn", "index": sid},
                   color="danger", size="sm", className="btn-action"),
    ]

    return html.Tr([
        html.Td(dcc.Link(ticker, href=f"/detail?ticker={ticker}",
                         className="ticker-link")),
        html.Td(stock.get("name", ""), style={"fontSize": "0.85rem"}),
        html.Td(_fmt_price(cur)),
        html.Td(_pct_span(chg)),
        html.Td(_fmt_price(avg_price) if avg_price else "-"),
        html.Td(f"{qty:,.2f}" if qty else "-"),
        html.Td(_fmt_price(total_val) if total_val else "-"),
        html.Td(
            html.Span(_fmt_price(abs(unreal_amt)),
                      className="text-pos" if unreal_amt >= 0 else "text-neg")
            if avg_price else html.Span("-")
        ),
        html.Td(
            _pct_span(unreal_pct) if avg_price else html.Span("-")
        ),
        html.Td(_signal_badges(sigs)),
        html.Td(action_btns),
    ], className="align-middle")


def _stock_table(stocks, ind_configs, prices=None):
    if not stocks:
        return html.P("종목이 없습니다. 종목을 추가하세요.", className="text-muted mt-3")

    if prices is None:
        prices = data_fetcher.get_batch_info([s["ticker"] for s in stocks])

    rows = []
    for s in stocks:
        ticker = s["ticker"]
        qty, avg = models.calculate_position(s["id"])
        pi = prices.get(ticker, {})
        try:
            df = data_fetcher.get_historical_data(ticker, "3mo")
            sigs = indicators.get_signals(df, ind_configs)
        except Exception:
            sigs = []
        rows.append(_build_stock_row(s, pi, qty, avg, sigs))

    return dbc.Table(
        [html.Thead(html.Tr([
            html.Th("티커"), html.Th("종목명"), html.Th("현재가"),
            html.Th("등락"), html.Th("평단가"), html.Th("수량"),
            html.Th("평가금액"), html.Th("평가 손익"), html.Th("수익률"), html.Th("신호"),
            html.Th(""),
        ])),
         html.Tbody(rows)],
        hover=True, responsive=True,
        size="sm", className="table-dark mt-2",
    )


def _summary_card(stocks, prices, label="전체"):
    total_invest = 0.0
    total_eval = 0.0
    for s in stocks:
        qty, avg = models.calculate_position(s["id"])
        if qty <= 0:
            continue
        cur = prices.get(s["ticker"], {}).get("current_price", 0)
        total_invest += avg * qty
        total_eval += cur * qty

    total_pnl = total_eval - total_invest
    total_pct = (total_pnl / total_invest * 100) if total_invest else 0
    pnl_cls = "text-success" if total_pnl >= 0 else "text-danger"
    sign = "+" if total_pnl >= 0 else ""

    def _stat(title, value, cls=""):
        return dbc.Col(dbc.Card(dbc.CardBody([
            html.Small(title, className="text-muted d-block mb-1"),
            html.Span(value, className=f"fw-bold fs-6 {cls}"),
        ]), style={"backgroundColor": "#12122a", "border": "1px solid #3a3a60"}),
        xs=6, md=3, className="mb-2")

    return dbc.Row([
        _stat(f"[{label}] 투자금액", f"{total_invest:,.0f}"),
        _stat(f"[{label}] 평가금액",  f"{total_eval:,.0f}"),
        _stat(f"[{label}] 평가 손익", f"{sign}{total_pnl:,.0f}", pnl_cls),
        _stat(f"[{label}] 수익률",    f"{sign}{total_pct:.2f}%", pnl_cls),
    ], className="mb-3")


def _tab_content(stocks, ind_configs, prices, label):
    return html.Div([
        _summary_card(stocks, prices, label),
        _stock_table(stocks, ind_configs),
    ])


def _build_tabs(ind_configs):
    categories = models.get_categories("holding")
    all_stocks = models.get_stocks()

    if not categories:
        return html.Div([
            html.P("카테고리가 없습니다. 먼저 카테고리를 추가하세요.",
                   className="text-muted"),
            dbc.Button("카테고리 관리", href="/categories", color="outline-primary"),
        ])

    prices = data_fetcher.get_batch_info([s["ticker"] for s in all_stocks])

    tabs = []
    tabs.append(dbc.Tab(
        _tab_content(all_stocks, ind_configs, prices, "전체"),
        label=f"전체 ({len(all_stocks)})",
        tab_id="tab-all",
    ))
    for cat in categories:
        stocks_in = [s for s in all_stocks if s["category_id"] == cat["id"]]
        tabs.append(dbc.Tab(
            _tab_content(stocks_in, ind_configs, prices, cat["name"]),
            label=f"{cat['name']} ({len(stocks_in)})",
            tab_id=f"tab-cat-{cat['id']}",
        ))

    return dbc.Tabs(tabs, active_tab="tab-all")


def _category_options(type_="holding"):
    return [{"label": c["name"], "value": c["id"]}
            for c in models.get_categories(type_)]


def layout():
    online = True
    try:
        stocks = models.get_stocks()
        if stocks:
            info = data_fetcher.get_stock_info(stocks[0]["ticker"])
            online = info.get("online", True)
    except Exception:
        online = True

    return html.Div([
        dbc.Row([
            dbc.Col(html.H4("📊 보유 종목", className="page-title mb-0"), width="auto"),
            dbc.Col([
                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "새로고침"],
                           id="hld-refresh", color="secondary", size="sm",
                           className="me-2"),
                dbc.Button([html.I(className="bi bi-plus-lg me-1"), "종목 추가"],
                           id="hld-open-add", color="primary", size="sm"),
            ], className="d-flex align-items-center justify-content-end"),
        ], className="mb-3 align-items-center"),

        dbc.Alert("⚠️ 인터넷 연결 없음 — 캐시 데이터로 표시됩니다.",
                  color="warning", is_open=not online,
                  dismissable=True, className="mb-2"),

        dcc.Loading(
            html.Div(id="hld-tabs-area"),
            type="circle", color="#6c63ff",
        ),

        dcc.Store(id="hld-sel-stock-id"),
        dcc.Store(id="hld-sel-trade-id"),
        dcc.Store(id="hld-m-results-store"),
        dcc.Store(id="hld-m-sel-ticker"),
        dcc.Store(id="hld-m-sel-name"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="hld-stock-modal-title")),
            dbc.ModalBody([
                html.Div(id="hld-m-search-section", children=[
                    dbc.Label("종목 검색"),
                    dbc.InputGroup([
                        dbc.Input(
                            id="hld-m-search",
                            placeholder="종목명 또는 티커 입력 (예: 삼성전자, AAPL)",
                            autocomplete="off",
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-search")],
                            id="hld-m-search-btn",
                            color="primary",
                        ),
                    ], className="mb-1"),
                    html.Div(
                        id="hld-m-results-list",
                        style={
                            "maxHeight": "200px", "overflowY": "auto",
                            "border": "1px solid #3a3a60", "borderRadius": "6px",
                            "marginBottom": "8px",
                        },
                    ),
                ]),
                html.Div(id="hld-m-selected-card", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("카테고리 *"),
                        dcc.Dropdown(id="hld-m-cat", placeholder="선택"),
                    ], md=12, className="mb-3"),
                ]),
                dbc.Label("메모"),
                dbc.Textarea(id="hld-m-memo", rows=2),
                html.Div(id="hld-stock-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="hld-save-stock", color="primary", className="me-2"),
                dbc.Button("닫기", id="hld-close-stock-modal", color="secondary"),
            ]),
        ], id="hld-stock-modal", is_open=False, backdrop="static", size="lg"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("삭제 확인")),
            dbc.ModalBody("이 종목과 모든 매매 이력을 삭제하시겠습니까?"),
            dbc.ModalFooter([
                dbc.Button("삭제", id="hld-confirm-del", color="danger", className="me-2"),
                dbc.Button("취소", id="hld-cancel-del", color="secondary"),
            ]),
        ], id="hld-del-modal", is_open=False),

        dbc.Toast(id="hld-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="hld-pos-modal-title")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("평단가"),
                        dbc.Input(id="hld-pos-avg", type="number", min=0,
                                  placeholder="매입 평균가"),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("수량"),
                        dbc.Input(id="hld-pos-qty", type="number", min=0,
                                  placeholder="보유 수량"),
                    ], md=6),
                ], className="mb-3 g-2"),
                dbc.Card(dbc.CardBody(
                    dbc.Row([
                        dbc.Col([
                            html.Small("현재가", className="text-muted d-block"),
                            html.Span(id="hld-pos-cur-display", className="fw-bold"),
                        ]),
                        dbc.Col([
                            html.Small("평가금액", className="text-muted d-block"),
                            html.Span(id="hld-pos-eval-amt", className="fw-bold"),
                        ]),
                        dbc.Col([
                            html.Small("평가 손익", className="text-muted d-block"),
                            html.Span(id="hld-pos-eval-pnl"),
                        ]),
                    ])
                ), className="mb-2",
                style={"backgroundColor": "#12122a", "border": "1px solid #3a3a60"}),
                html.Div(id="hld-pos-err", className="text-danger mt-1"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="hld-pos-save", color="primary", className="me-2"),
                dbc.Button("닫기", id="hld-pos-close", color="secondary"),
            ]),
        ], id="hld-pos-modal", is_open=False, backdrop="static"),

        dcc.Store(id="hld-pos-stock-id"),
        dcc.Store(id="hld-pos-cur-price"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="hld-trade-modal-title")),
            dbc.ModalBody([
                dbc.Card(dbc.CardBody(
                    dbc.Row([
                        dbc.Col([html.Small("현재가", className="text-muted d-block"),
                                 html.Span(id="hld-trade-cur-price-display", className="fw-bold")]),
                        dbc.Col([html.Small("보유수량", className="text-muted d-block"),
                                 html.Span(id="hld-trade-cur-qty-display", className="fw-bold")]),
                        dbc.Col([html.Small("평단가", className="text-muted d-block"),
                                 html.Span(id="hld-trade-cur-avg-display", className="fw-bold")]),
                        dbc.Col([html.Small("평가금액", className="text-muted d-block"),
                                 html.Span(id="hld-trade-cur-eval-display", className="fw-bold")]),
                    ])
                ), className="mb-3",
                style={"backgroundColor": "#12122a", "border": "1px solid #3a3a60"}),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("거래 유형"),
                        dbc.RadioItems(
                            id="hld-trade-type",
                            options=[{"label": "  매수", "value": "buy"},
                                     {"label": "  매도", "value": "sell"}],
                            value="buy",
                            inline=True,
                            className="mb-1",
                        ),
                    ], md=12, className="mb-2"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("수량"),
                        dbc.Input(id="hld-trade-qty", type="number", min=0,
                                  placeholder="거래 수량"),
                    ], md=4),
                    dbc.Col([
                        dbc.Label("단가"),
                        dbc.Input(id="hld-trade-price", type="number", min=0,
                                  placeholder="거래 단가"),
                    ], md=4),
                    dbc.Col([
                        dbc.Label("날짜"),
                        dbc.Input(id="hld-trade-date", type="date"),
                    ], md=4),
                ], className="mb-3 g-2"),
                html.Hr(style={"borderColor": "#3a3a60"}),
                html.Small("거래 후 예상 포지션", className="text-muted"),
                dbc.Card(dbc.CardBody(
                    dbc.Row([
                        dbc.Col([html.Small("보유수량", className="text-muted d-block"),
                                 html.Span(id="hld-trade-new-qty", className="fw-bold")]),
                        dbc.Col([html.Small("평단가", className="text-muted d-block"),
                                 html.Span(id="hld-trade-new-avg", className="fw-bold")]),
                        dbc.Col([html.Small("평가금액", className="text-muted d-block"),
                                 html.Span(id="hld-trade-new-eval", className="fw-bold")]),
                        dbc.Col([html.Small("평가 손익", className="text-muted d-block"),
                                 html.Span(id="hld-trade-new-pnl")]),
                        dbc.Col([html.Small("수익률", className="text-muted d-block"),
                                 html.Span(id="hld-trade-new-pct")]),
                    ])
                ), className="mt-2",
                style={"backgroundColor": "#0d0d1a", "border": "1px solid #3a3a60"}),
                html.Div(id="hld-trade-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="hld-trade-save", color="primary", className="me-2"),
                dbc.Button("닫기", id="hld-trade-close", color="secondary"),
            ]),
        ], id="hld-trade-modal", is_open=False, backdrop="static", size="lg"),

        dcc.Store(id="hld-trade-stock-id"),
        dcc.Store(id="hld-trade-cur-qty-store"),
        dcc.Store(id="hld-trade-cur-avg-store"),
        dcc.Store(id="hld-trade-cur-price-store"),
        dcc.Store(id="hld-trigger", data=0),
    ])


@callback(
    Output("hld-tabs-area", "children"),
    Input("hld-trigger", "data"),
    Input("hld-refresh", "n_clicks"),
    prevent_initial_call=False,
)
def render_tabs(_trigger, _refresh):
    ind_configs = models.get_indicator_configs()
    return _build_tabs(ind_configs)


@callback(
    Output("hld-stock-modal", "is_open", allow_duplicate=True),
    Output("hld-stock-modal-title", "children"),
    Output("hld-m-search", "value"),
    Output("hld-m-results-list", "children"),
    Output("hld-m-results-store", "data"),
    Output("hld-m-sel-ticker", "data"),
    Output("hld-m-sel-name", "data"),
    Output("hld-m-selected-card", "children"),
    Output("hld-m-search-section", "style"),
    Output("hld-m-cat", "options"),
    Output("hld-m-cat", "value"),
    Output("hld-m-memo", "value"),
    Output("hld-sel-stock-id", "data"),
    Input("hld-open-add", "n_clicks"),
    Input({"type": "hld-edit-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_stock_modal(_add, _edits):
    triggered = ctx.triggered_id
    opts = _category_options("holding")
    show = {"display": "block"}
    hide = {"display": "none"}

    if triggered == "hld-open-add":
        return (True, "종목 추가",
                "", [], [],
                None, None, "",
                show,
                opts, None, "",
                None)

    if isinstance(triggered, dict) and triggered.get("type") == "hld-edit-btn":
        if not any(n for n in _edits if n):
            return (no_update,) * 13
        sid = triggered["index"]
        s = models.get_stock(sid)
        if not s:
            return (no_update,) * 13
        ticker = s["ticker"]
        name = s["name"] or ticker
        pi = data_fetcher.get_stock_info(ticker)
        card = _selected_card(ticker, name, pi)
        return (True, f"종목 수정 — {ticker}",
                "", [], [],
                ticker, name, card,
                hide,
                opts, s["category_id"], s["memo"] or "",
                sid)

    return (no_update,) * 13


@callback(
    Output("hld-m-results-list", "children", allow_duplicate=True),
    Output("hld-m-results-store", "data", allow_duplicate=True),
    Input("hld-m-search-btn", "n_clicks"),
    Input("hld-m-search", "n_submit"),
    State("hld-m-search", "value"),
    prevent_initial_call=True,
)
def do_search(_btn, _submit, query):
    if not query or not query.strip():
        return [], []
    results = data_fetcher.search_tickers(query.strip())
    if not results:
        return [html.P("검색 결과가 없습니다.", className="text-muted small p-2")], []
    items = []
    for i, r in enumerate(results):
        items.append(
            dbc.ListGroupItem(
                [
                    html.Span(r["name"], className="fw-semibold me-2"),
                    dbc.Badge(r["ticker"], color="primary", className="me-1"),
                    dbc.Badge(r["exchange"], color="secondary", className="me-1",
                              style={"fontSize": "0.7rem"}),
                    html.Span(r["type"], className="text-muted",
                              style={"fontSize": "0.75rem"}),
                ],
                id={"type": "hld-result-item", "index": i},
                action=True,
                className="py-2 px-3",
                style={"cursor": "pointer", "backgroundColor": "#1e1e30",
                       "borderColor": "#3a3a60", "color": "#e0e0e0"},
            )
        )
    return dbc.ListGroup(items, flush=True), results


@callback(
    Output("hld-m-sel-ticker", "data", allow_duplicate=True),
    Output("hld-m-sel-name", "data", allow_duplicate=True),
    Output("hld-m-selected-card", "children", allow_duplicate=True),
    Output("hld-m-results-list", "children", allow_duplicate=True),
    Output("hld-m-search", "value", allow_duplicate=True),
    Input({"type": "hld-result-item", "index": ALL}, "n_clicks"),
    State("hld-m-results-store", "data"),
    prevent_initial_call=True,
)
def select_result(clicks, results):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not results:
        return no_update, no_update, no_update, no_update, no_update
    if not any(n for n in clicks if n):
        return no_update, no_update, no_update, no_update, no_update
    idx = triggered["index"]
    if idx >= len(results):
        return no_update, no_update, no_update, no_update, no_update
    r = results[idx]
    name = r["name"]
    if r.get("_src") == "naver" and r.get("_code"):
        ticker, pi = data_fetcher.resolve_krx_ticker(r["_code"])
        if not name or name == r["_code"]:
            name = pi.get("name", name)
    else:
        ticker = r["ticker"]
        pi = data_fetcher.get_stock_info(ticker)
    card = _selected_card(ticker, name, pi)
    return ticker, name, card, [], ""


@callback(
    Output("hld-stock-modal", "is_open", allow_duplicate=True),
    Output("hld-stock-err", "children"),
    Output("hld-tabs-area", "children", allow_duplicate=True),
    Output("hld-toast", "is_open", allow_duplicate=True),
    Output("hld-toast", "children", allow_duplicate=True),
    Input("hld-save-stock", "n_clicks"),
    State("hld-m-sel-ticker", "data"),
    State("hld-m-sel-name", "data"),
    State("hld-m-cat", "value"),
    State("hld-m-memo", "value"),
    State("hld-sel-stock-id", "data"),
    prevent_initial_call=True,
)
def save_stock(_n, ticker, name, cat_id, memo, sel_id):
    if not ticker:
        return no_update, "종목을 검색하여 선택하세요.", no_update, no_update, no_update
    if not cat_id:
        return no_update, "카테고리를 선택하세요.", no_update, no_update, no_update
    ticker = data_fetcher.normalize_ticker(ticker)
    resolved_name = name or data_fetcher.get_stock_name(ticker)
    if sel_id:
        models.update_stock(sel_id, name=resolved_name,
                            category_id=cat_id, memo=memo or "")
        msg = f"{ticker} 수정 완료"
    else:
        if models.get_stock_by_ticker(ticker):
            return no_update, f"{ticker} 은(는) 이미 보유 종목에 등록되어 있습니다.", no_update, no_update, no_update
        models.create_stock(ticker, resolved_name, cat_id, memo or "")
        msg = f"{ticker} 추가 완료"
    tabs = _build_tabs(models.get_indicator_configs())
    return False, "", tabs, True, msg


def _selected_card(ticker: str, name: str, pi: dict):
    cur = pi.get("current_price", 0)
    chg = pi.get("change_pct", 0)
    chg_cls = "text-pos" if chg > 0 else ("text-neg" if chg < 0 else "text-neu")
    sign = "+" if chg > 0 else ""
    online = pi.get("online", True)
    return dbc.Alert(
        [
            html.Div([
                dbc.Badge(ticker, color="primary", className="me-2 fs-6"),
                html.Span(name, className="fw-semibold me-3"),
            ], className="mb-1"),
            html.Div([
                html.Span(f"{cur:,.2f}" if cur else "가격 조회 불가",
                          className="fs-5 fw-bold me-2"),
                html.Span(f"{sign}{chg:.2f}%", className=chg_cls),
                html.Span(" ⚠️ 오프라인", className="text-warning ms-2")
                if not online else "",
            ]),
        ],
        color="dark",
        style={"border": "1px solid #3a3a60", "backgroundColor": "#12122a"},
    )


@callback(
    Output("hld-stock-modal", "is_open", allow_duplicate=True),
    Input("hld-close-stock-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_stock_modal(_n):
    return False


@callback(
    Output("hld-del-modal", "is_open", allow_duplicate=True),
    Output("hld-sel-stock-id", "data", allow_duplicate=True),
    Input({"type": "hld-del-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_del_modal(del_clicks):
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "hld-del-btn":
        if any(n for n in del_clicks if n):
            return True, triggered["index"]
    return no_update, no_update


@callback(
    Output("hld-del-modal", "is_open", allow_duplicate=True),
    Output("hld-tabs-area", "children", allow_duplicate=True),
    Output("hld-toast", "is_open", allow_duplicate=True),
    Output("hld-toast", "children", allow_duplicate=True),
    Input("hld-confirm-del", "n_clicks"),
    Input("hld-cancel-del", "n_clicks"),
    State("hld-sel-stock-id", "data"),
    prevent_initial_call=True,
)
def execute_delete(_confirm, _cancel, sel_id):
    if ctx.triggered_id == "hld-confirm-del" and sel_id:
        s = models.get_stock(sel_id)
        ticker = s["ticker"] if s else str(sel_id)
        models.delete_stock(sel_id)
        tabs = _build_tabs(models.get_indicator_configs())
        return False, tabs, True, f"{ticker} 삭제 완료"
    return False, no_update, no_update, no_update


@callback(
    Output("hld-pos-modal", "is_open"),
    Output("hld-pos-modal-title", "children"),
    Output("hld-pos-stock-id", "data"),
    Output("hld-pos-cur-price", "data"),
    Output("hld-pos-cur-display", "children"),
    Output("hld-pos-avg", "value"),
    Output("hld-pos-qty", "value"),
    Input({"type": "hld-pos-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_pos_modal(clicks):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n for n in clicks if n):
        return (no_update,) * 7
    sid = triggered["index"]
    s = models.get_stock(sid)
    if not s:
        return (no_update,) * 7
    ticker = s["ticker"]
    name = s["name"] or ticker
    pi = data_fetcher.get_stock_info(ticker)
    cur = pi.get("current_price", 0)
    cur_txt = f"{cur:,.0f}" if cur else "조회 불가"
    return True, f"{ticker} ({name}) — 매입 정보 입력", sid, cur, cur_txt, None, None


@callback(
    Output("hld-pos-eval-amt", "children"),
    Output("hld-pos-eval-pnl", "children"),
    Input("hld-pos-avg", "value"),
    Input("hld-pos-qty", "value"),
    State("hld-pos-cur-price", "data"),
    prevent_initial_call=True,
)
def calc_pos_values(avg, qty, cur):
    cur = float(cur or 0)
    avg = float(avg or 0)
    qty = float(qty or 0)
    if qty <= 0:
        return "-", "-"
    eval_amt = cur * qty
    pnl = (cur - avg) * qty
    pnl_pct = ((cur - avg) / avg * 100) if avg else 0
    cls = "text-success" if pnl >= 0 else "text-danger"
    sign = "+" if pnl >= 0 else ""
    return (
        f"{eval_amt:,.0f}",
        html.Span(f"{sign}{pnl:,.0f} ({sign}{pnl_pct:.2f}%)", className=cls),
    )


@callback(
    Output("hld-pos-modal", "is_open", allow_duplicate=True),
    Output("hld-pos-err", "children"),
    Output("hld-tabs-area", "children", allow_duplicate=True),
    Output("hld-toast", "is_open", allow_duplicate=True),
    Output("hld-toast", "children", allow_duplicate=True),
    Input("hld-pos-save", "n_clicks"),
    State("hld-pos-stock-id", "data"),
    State("hld-pos-avg", "value"),
    State("hld-pos-qty", "value"),
    prevent_initial_call=True,
)
def save_pos(_n, stock_id, avg, qty):
    if not avg or not qty:
        return no_update, "평단가와 수량을 모두 입력하세요.", no_update, no_update, no_update
    avg, qty = float(avg), float(qty)
    if avg <= 0 or qty <= 0:
        return no_update, "0보다 큰 값을 입력하세요.", no_update, no_update, no_update
    models.create_trade(stock_id, "buy", qty, avg, str(date.today()))
    tabs = _build_tabs(models.get_indicator_configs())
    s = models.get_stock(stock_id)
    ticker = s["ticker"] if s else ""
    return False, "", tabs, True, f"{ticker} 매입 정보 저장 완료"


@callback(
    Output("hld-pos-modal", "is_open", allow_duplicate=True),
    Input("hld-pos-close", "n_clicks"),
    prevent_initial_call=True,
)
def close_pos_modal(_n):
    return False


@callback(
    Output("hld-trade-modal", "is_open"),
    Output("hld-trade-modal-title", "children"),
    Output("hld-trade-stock-id", "data"),
    Output("hld-trade-cur-qty-store", "data"),
    Output("hld-trade-cur-avg-store", "data"),
    Output("hld-trade-cur-price-store", "data"),
    Output("hld-trade-cur-price-display", "children"),
    Output("hld-trade-cur-qty-display", "children"),
    Output("hld-trade-cur-avg-display", "children"),
    Output("hld-trade-cur-eval-display", "children"),
    Output("hld-trade-price", "value"),
    Output("hld-trade-qty", "value"),
    Output("hld-trade-date", "value"),
    Output("hld-trade-type", "value"),
    Input({"type": "hld-trade-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_trade_modal(clicks):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict) or not any(n for n in clicks if n):
        return (no_update,) * 14
    sid = triggered["index"]
    s = models.get_stock(sid)
    if not s:
        return (no_update,) * 14
    ticker = s["ticker"]
    name = s["name"] or ticker
    qty, avg = models.calculate_position(sid)
    pi = data_fetcher.get_stock_info(ticker)
    cur = pi.get("current_price", 0)
    eval_val = cur * qty
    return (
        True,
        f"{ticker} ({name}) — 매매 입력",
        sid, qty, avg, cur,
        f"{cur:,.0f}",
        f"{qty:,.4f}",
        f"{avg:,.0f}" if avg else "-",
        f"{eval_val:,.0f}" if eval_val else "-",
        cur or None,
        None,
        str(date.today()),
        "buy",
    )


@callback(
    Output("hld-trade-new-qty", "children"),
    Output("hld-trade-new-avg", "children"),
    Output("hld-trade-new-eval", "children"),
    Output("hld-trade-new-pnl", "children"),
    Output("hld-trade-new-pct", "children"),
    Input("hld-trade-qty", "value"),
    Input("hld-trade-price", "value"),
    Input("hld-trade-type", "value"),
    State("hld-trade-cur-qty-store", "data"),
    State("hld-trade-cur-avg-store", "data"),
    State("hld-trade-cur-price-store", "data"),
    prevent_initial_call=True,
)
def preview_trade(t_qty, t_price, t_type, cur_qty, cur_avg, cur_price):
    cur_qty   = float(cur_qty   or 0)
    cur_avg   = float(cur_avg   or 0)
    cur_price = float(cur_price or 0)
    t_qty     = float(t_qty     or 0)
    t_price   = float(t_price   or 0)
    if t_qty <= 0:
        return "-", "-", "-", "-", "-"
    if t_type == "buy":
        new_qty = cur_qty + t_qty
        new_avg = (cur_avg * cur_qty + t_price * t_qty) / new_qty if new_qty else 0
    else:
        new_qty = max(cur_qty - t_qty, 0)
        new_avg = cur_avg
    new_eval = cur_price * new_qty
    new_pnl  = (cur_price - new_avg) * new_qty if new_avg else 0
    new_pct  = ((cur_price - new_avg) / new_avg * 100) if new_avg else 0
    pnl_cls  = "text-success" if new_pnl >= 0 else "text-danger"
    sign     = "+" if new_pnl >= 0 else ""
    return (
        f"{new_qty:,.4f}",
        f"{new_avg:,.0f}" if new_avg else "-",
        f"{new_eval:,.0f}",
        html.Span(f"{sign}{new_pnl:,.0f}", className=pnl_cls),
        html.Span(f"{sign}{new_pct:.2f}%", className=pnl_cls),
    )


@callback(
    Output("hld-trade-modal", "is_open", allow_duplicate=True),
    Output("hld-trade-err", "children"),
    Output("hld-tabs-area", "children", allow_duplicate=True),
    Output("hld-toast", "is_open", allow_duplicate=True),
    Output("hld-toast", "children", allow_duplicate=True),
    Input("hld-trade-save", "n_clicks"),
    State("hld-trade-stock-id", "data"),
    State("hld-trade-type", "value"),
    State("hld-trade-qty", "value"),
    State("hld-trade-price", "value"),
    State("hld-trade-date", "value"),
    State("hld-trade-cur-qty-store", "data"),
    prevent_initial_call=True,
)
def save_trade(_n, stock_id, t_type, t_qty, t_price, t_date, cur_qty):
    if not t_qty or not t_price:
        return no_update, "수량과 단가를 입력하세요.", no_update, no_update, no_update
    t_qty, t_price = float(t_qty), float(t_price)
    if t_qty <= 0 or t_price <= 0:
        return no_update, "0보다 큰 값을 입력하세요.", no_update, no_update, no_update
    if t_type == "sell" and t_qty > float(cur_qty or 0):
        return no_update, f"매도 수량({t_qty:,.4f})이 보유 수량({float(cur_qty or 0):,.4f})을 초과합니다.", no_update, no_update, no_update
    trade_date = t_date or str(date.today())
    models.create_trade(stock_id, t_type, t_qty, t_price, trade_date)
    tabs = _build_tabs(models.get_indicator_configs())
    s = models.get_stock(stock_id)
    ticker = s["ticker"] if s else ""
    label = "매수" if t_type == "buy" else "매도"
    return False, "", tabs, True, f"{ticker} {label} {t_qty:,.4f}주 저장 완료"


@callback(
    Output("hld-trade-modal", "is_open", allow_duplicate=True),
    Input("hld-trade-close", "n_clicks"),
    prevent_initial_call=True,
)
def close_trade_modal(_n):
    return False
