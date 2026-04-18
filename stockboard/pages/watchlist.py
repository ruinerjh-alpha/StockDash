"""M7: 관심 종목 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc
from datetime import date

import models
import data_fetcher
import indicators

dash.register_page(__name__, path="/watchlist", name="관심 종목", order=1)


def _pct_span(pct):
    cls = "text-pos" if pct > 0 else ("text-neg" if pct < 0 else "text-neu")
    sign = "+" if pct > 0 else ""
    return html.Span(f"{sign}{pct:.2f}%", className=cls)


def _signal_badges(sigs):
    if not sigs:
        return html.Span("-", className="text-neu")
    return html.Span([dbc.Badge(s["description"], color=s["color"],
                                className="signal-badge me-1")
                      for s in sigs])


def _build_rows(items, ind_configs):
    rows = []
    for item in items:
        ticker = item["ticker"]
        pi = data_fetcher.get_stock_info(ticker)
        cur = pi.get("current_price", 0)
        chg = pi.get("change_pct", 0)
        reg_price = item.get("registered_price") or 0
        since_reg = ((cur - reg_price) / reg_price * 100) if reg_price else 0

        try:
            df = data_fetcher.get_historical_data(ticker, "3mo")
            sigs = indicators.get_signals(df, ind_configs)
        except Exception:
            sigs = []

        iid = item["id"]
        rows.append(html.Tr([
            html.Td(dcc.Link(ticker, href=f"/detail?ticker={ticker}",
                             className="ticker-link")),
            html.Td(item.get("name", ""), style={"fontSize": "0.85rem"}),
            html.Td(f"{cur:,.2f}" if cur else "-"),
            html.Td(_pct_span(chg)),
            html.Td(f"{reg_price:,.2f}" if reg_price else "-"),
            html.Td(_pct_span(since_reg) if reg_price else html.Span("-")),
            html.Td(item.get("category_name", "-")),
            html.Td(_signal_badges(sigs)),
            html.Td([
                dbc.Button("전환", id={"type": "wl-convert-btn", "index": iid},
                           color="success", size="sm", className="btn-action me-1",
                           title="보유 종목으로 전환"),
                dbc.Button("수정", id={"type": "wl-edit-btn", "index": iid},
                           color="secondary", size="sm", className="btn-action me-1"),
                dbc.Button("삭제", id={"type": "wl-del-btn", "index": iid},
                           color="danger", size="sm", className="btn-action"),
            ]),
        ], className="align-middle"))
    return rows


def _build_table(items, ind_configs):
    if not items:
        return html.P("관심 종목이 없습니다.", className="text-muted mt-3")
    return dbc.Table(
        [html.Thead(html.Tr([
            html.Th("티커"), html.Th("종목명"), html.Th("현재가"), html.Th("전일등락"),
            html.Th("등록가"), html.Th("등록후 등락"), html.Th("카테고리"),
            html.Th("신호"), html.Th(""),
        ])),
         html.Tbody(_build_rows(items, ind_configs))],
        hover=True, responsive=True, size="sm", className="table-dark mt-2",
    )


def _cat_options():
    return [{"label": c["name"], "value": c["id"]}
            for c in models.get_categories("watchlist")]


def _holding_cat_options():
    return [{"label": c["name"], "value": c["id"]}
            for c in models.get_categories("holding")]


def layout():
    cats = models.get_categories("watchlist")
    cat_filter_opts = [{"label": "전체", "value": "all"}] + \
                      [{"label": c["name"], "value": c["id"]} for c in cats]
    return html.Div([
        dbc.Row([
            dbc.Col(html.H4("👁 관심 종목", className="page-title mb-0"), width="auto"),
            dbc.Col([
                dbc.Select(id="wl-cat-filter", options=cat_filter_opts,
                           value="all", style={"width": 180}),
            ], className="d-flex align-items-center"),
            dbc.Col([
                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "새로고침"],
                           id="wl-refresh", color="secondary", size="sm", className="me-2"),
                dbc.Button([html.I(className="bi bi-plus-lg me-1"), "종목 추가"],
                           id="wl-open-add", color="primary", size="sm"),
            ], className="d-flex align-items-center justify-content-end"),
        ], className="mb-3 align-items-center"),

        html.Div(id="wl-table-area"),

        dcc.Store(id="wl-sel-id"),
        dcc.Store(id="wl-trigger", data=0),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="wl-modal-title")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([dbc.Label("티커 *"),
                             dbc.Input(id="wl-m-ticker",
                                       placeholder="예: 035720.KS")], md=6),
                    dbc.Col([dbc.Label("종목명"),
                             dbc.Input(id="wl-m-name",
                                       placeholder="자동 조회")], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("현재가 (등록가)"),
                             dbc.Input(id="wl-m-reg-price", disabled=True)], md=6),
                    dbc.Col([dbc.Label("카테고리 *"),
                             dcc.Dropdown(id="wl-m-cat", placeholder="선택")], md=6),
                ], className="mb-3"),
                dbc.Label("메모"),
                dbc.Textarea(id="wl-m-memo", rows=2),
                html.Div(id="wl-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="wl-save", color="primary", className="me-2"),
                dbc.Button("닫기", id="wl-close-modal", color="secondary"),
            ]),
        ], id="wl-modal", is_open=False, backdrop="static"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("보유 종목으로 전환")),
            dbc.ModalBody([
                html.P(id="wl-convert-ticker-display", className="fw-bold"),
                dbc.Row([
                    dbc.Col([dbc.Label("보유 카테고리 *"),
                             dcc.Dropdown(id="wl-convert-cat",
                                          placeholder="선택")], md=12,
                            className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([dbc.Label("매수일 *"),
                             dbc.Input(id="wl-convert-date", type="date",
                                       value=str(date.today()))], md=6),
                    dbc.Col([dbc.Label("수량 *"),
                             dbc.Input(id="wl-convert-qty", type="number", min=0)], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("매수가 *"),
                             dbc.Input(id="wl-convert-price", type="number", min=0)], md=6),
                    dbc.Col([dbc.Label("수수료"),
                             dbc.Input(id="wl-convert-fee", type="number",
                                       min=0, value=0)], md=6),
                ], className="mb-3"),
                html.Div(id="wl-convert-err", className="text-danger"),
            ]),
            dbc.ModalFooter([
                dbc.Button("전환", id="wl-confirm-convert", color="success", className="me-2"),
                dbc.Button("취소", id="wl-cancel-convert", color="secondary"),
            ]),
        ], id="wl-convert-modal", is_open=False, backdrop="static"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("삭제 확인")),
            dbc.ModalBody("관심 종목에서 삭제하시겠습니까?"),
            dbc.ModalFooter([
                dbc.Button("삭제", id="wl-confirm-del", color="danger", className="me-2"),
                dbc.Button("취소", id="wl-cancel-del", color="secondary"),
            ]),
        ], id="wl-del-modal", is_open=False),

        dbc.Toast(id="wl-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),
    ])


@callback(
    Output("wl-table-area", "children"),
    Input("wl-trigger", "data"),
    Input("wl-cat-filter", "value"),
    Input("wl-refresh", "n_clicks"),
    prevent_initial_call=False,
)
def render_table(_t, cat_filter, _r):
    ind_configs = models.get_indicator_configs()
    cat_id = None if cat_filter == "all" else cat_filter
    items = models.get_watchlist(cat_id)
    return _build_table(items, ind_configs)


@callback(
    Output("wl-modal", "is_open", allow_duplicate=True),
    Output("wl-modal-title", "children"),
    Output("wl-m-ticker", "value"),
    Output("wl-m-name", "value"),
    Output("wl-m-reg-price", "value"),
    Output("wl-m-cat", "options"),
    Output("wl-m-cat", "value"),
    Output("wl-m-memo", "value"),
    Output("wl-sel-id", "data"),
    Input("wl-open-add", "n_clicks"),
    Input({"type": "wl-edit-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_modal(_add, _edits):
    triggered = ctx.triggered_id
    opts = _cat_options()

    if triggered == "wl-open-add":
        return True, "관심 종목 추가", "", "", "", opts, None, "", None

    if isinstance(triggered, dict) and triggered.get("type") == "wl-edit-btn":
        iid = triggered["index"]
        item = models.get_watchlist_item(iid)
        if not item:
            return no_update, no_update, no_update, no_update, no_update, opts, no_update, no_update, no_update
        return (True, f"수정 — {item['ticker']}",
                item["ticker"], item["name"] or "",
                str(item.get("registered_price", "")),
                opts, item["category_id"], item["memo"] or "", iid)
    return no_update, no_update, no_update, no_update, no_update, opts, no_update, no_update, no_update


@callback(
    Output("wl-m-name", "value", allow_duplicate=True),
    Output("wl-m-reg-price", "value", allow_duplicate=True),
    Input("wl-m-ticker", "n_blur"),
    State("wl-m-ticker", "value"),
    State("wl-sel-id", "data"),
    prevent_initial_call=True,
)
def lookup_ticker(_b, ticker, sel_id):
    if not ticker or sel_id:
        return no_update, no_update
    t = ticker.strip()
    if t.isdigit() and len(t) == 6:
        _, pi = data_fetcher.resolve_krx_ticker(t)
    else:
        pi = data_fetcher.get_stock_info(t.upper())
    return pi.get("name", ""), str(pi.get("current_price", ""))


@callback(
    Output("wl-modal", "is_open", allow_duplicate=True),
    Output("wl-err", "children"),
    Output("wl-trigger", "data", allow_duplicate=True),
    Output("wl-toast", "is_open", allow_duplicate=True),
    Output("wl-toast", "children", allow_duplicate=True),
    Input("wl-save", "n_clicks"),
    State("wl-m-ticker", "value"),
    State("wl-m-name", "value"),
    State("wl-m-cat", "value"),
    State("wl-m-memo", "value"),
    State("wl-sel-id", "data"),
    State("wl-trigger", "data"),
    prevent_initial_call=True,
)
def save_watchlist(_n, ticker, name, cat_id, memo, sel_id, trigger):
    if not ticker:
        return no_update, "티커를 입력하세요.", no_update, no_update, no_update
    if not cat_id:
        return no_update, "카테고리를 선택하세요.", no_update, no_update, no_update
    ticker = data_fetcher.normalize_ticker(ticker)
    pi = data_fetcher.get_stock_info(ticker)
    resolved_name = name or pi.get("name") or data_fetcher.get_stock_name(ticker)

    if sel_id:
        models.update_watchlist_item(sel_id, name=resolved_name,
                                     category_id=cat_id, memo=memo or "")
        msg = f"{ticker} 수정 완료"
    else:
        models.create_watchlist_item(ticker, resolved_name, cat_id,
                                     pi.get("current_price", 0), memo or "")
        msg = f"{ticker} 관심 종목 추가 완료"

    return False, "", (trigger or 0) + 1, True, msg


@callback(
    Output("wl-modal", "is_open", allow_duplicate=True),
    Input("wl-close-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_modal(_n):
    return False


@callback(
    Output("wl-convert-modal", "is_open", allow_duplicate=True),
    Output("wl-convert-ticker-display", "children"),
    Output("wl-convert-cat", "options"),
    Output("wl-sel-id", "data", allow_duplicate=True),
    Input({"type": "wl-convert-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_convert_modal(clicks):
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "wl-convert-btn":
        if any(n for n in clicks if n):
            iid = triggered["index"]
            item = models.get_watchlist_item(iid)
            if item:
                h_opts = _holding_cat_options()
                return True, f"티커: {item['ticker']} — {item.get('name','')}", h_opts, iid
    return no_update, no_update, no_update, no_update


@callback(
    Output("wl-convert-modal", "is_open", allow_duplicate=True),
    Output("wl-convert-err", "children"),
    Output("wl-trigger", "data", allow_duplicate=True),
    Output("wl-toast", "is_open", allow_duplicate=True),
    Output("wl-toast", "children", allow_duplicate=True),
    Input("wl-confirm-convert", "n_clicks"),
    Input("wl-cancel-convert", "n_clicks"),
    State("wl-sel-id", "data"),
    State("wl-convert-cat", "value"),
    State("wl-convert-date", "value"),
    State("wl-convert-qty", "value"),
    State("wl-convert-price", "value"),
    State("wl-convert-fee", "value"),
    State("wl-trigger", "data"),
    prevent_initial_call=True,
)
def execute_convert(_conf, _cancel, sel_id, h_cat, trade_date, qty, price, fee, trigger):
    if ctx.triggered_id == "wl-cancel-convert":
        return False, "", no_update, no_update, no_update
    if not all([sel_id, h_cat, trade_date, qty, price]):
        return no_update, "모든 필수 항목을 입력하세요.", no_update, no_update, no_update
    item = models.get_watchlist_item(sel_id)
    if not item:
        return False, "", no_update, no_update, no_update
    ticker = item["ticker"]
    pi = data_fetcher.get_stock_info(ticker)
    stock_id = models.create_stock(ticker, item["name"] or pi.get("name", ticker),
                                   h_cat, item.get("memo", ""))
    models.create_trade(stock_id, "buy", float(qty), float(price),
                        trade_date, float(fee or 0))
    models.delete_watchlist_item(sel_id)
    return False, "", (trigger or 0) + 1, True, f"{ticker} 보유 종목으로 전환 완료"


@callback(
    Output("wl-del-modal", "is_open", allow_duplicate=True),
    Output("wl-sel-id", "data", allow_duplicate=True),
    Input({"type": "wl-del-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_del_modal(clicks):
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "wl-del-btn":
        if any(n for n in clicks if n):
            return True, triggered["index"]
    return no_update, no_update


@callback(
    Output("wl-del-modal", "is_open", allow_duplicate=True),
    Output("wl-trigger", "data", allow_duplicate=True),
    Output("wl-toast", "is_open", allow_duplicate=True),
    Output("wl-toast", "children", allow_duplicate=True),
    Input("wl-confirm-del", "n_clicks"),
    Input("wl-cancel-del", "n_clicks"),
    State("wl-sel-id", "data"),
    State("wl-trigger", "data"),
    prevent_initial_call=True,
)
def execute_del(_conf, _cancel, sel_id, trigger):
    if ctx.triggered_id == "wl-confirm-del" and sel_id:
        models.delete_watchlist_item(sel_id)
        return False, (trigger or 0) + 1, True, "삭제 완료"
    return False, no_update, no_update, no_update
