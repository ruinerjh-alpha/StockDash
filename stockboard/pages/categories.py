"""M6: 카테고리 관리 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc

import models

dash.register_page(__name__, path="/categories", name="카테고리", order=2)

COLOR_OPTIONS = [
    "#6c757d", "#0d6efd", "#198754", "#dc3545", "#ffc107",
    "#0dcaf0", "#fd7e14", "#6f42c1", "#d63384", "#20c997",
]


def _cat_list(type_: str):
    cats = models.get_categories(type_)
    if not cats:
        return html.P("카테고리가 없습니다.", className="text-muted small mt-2")

    items = []
    for c in cats:
        cid = c["id"]
        has_items = models.category_has_items(cid)
        items.append(dbc.ListGroupItem(
            [
                html.Span(style={
                    "display": "inline-block", "width": 14, "height": 14,
                    "borderRadius": "50%", "backgroundColor": c["color"],
                    "verticalAlign": "middle", "marginRight": 8,
                }),
                html.Span(c["name"], className="fw-semibold"),
                dbc.Badge("종목 있음", color="warning", pill=True,
                          className="ms-2 float-end")
                if has_items else "",
            ],
            id={"type": f"cat-item-{type_}", "index": cid},
            action=True,
            className="py-2 px-3",
            style={"backgroundColor": "#1e1e30", "color": "#e0e0e0",
                   "borderColor": "#3a3a60", "cursor": "pointer"},
        ))
    return dbc.ListGroup(items, flush=True, className="rounded")


def _action_panel(type_: str):
    """선택된 카테고리에 대한 수정·삭제 패널 (초기에는 숨김)."""
    return html.Div(
        [
            html.Hr(style={"borderColor": "#3a3a60", "margin": "12px 0"}),
            dbc.Row([
                dbc.Col(
                    html.Span(id=f"cat-{type_}-sel-name",
                              className="fw-bold text-info"),
                    className="d-flex align-items-center",
                ),
                dbc.Col([
                    dbc.Button("수정", id=f"cat-{type_}-edit-btn",
                               color="secondary", size="sm", className="me-2"),
                    dbc.Button("삭제", id=f"cat-{type_}-del-btn",
                               color="danger", size="sm"),
                ], width="auto"),
            ], className="align-items-center g-2"),
        ],
        id=f"cat-{type_}-panel",
        style={"display": "none"},
    )


def _color_radios(id_: str, value: str = "#6c757d"):
    return dbc.RadioItems(
        id=id_,
        options=[{"label": html.Span(style={
            "display": "inline-block", "width": 20, "height": 20,
            "borderRadius": "50%", "backgroundColor": c,
            "marginLeft": 4, "verticalAlign": "middle",
        }), "value": c} for c in COLOR_OPTIONS],
        value=value,
        inline=True,
        className="mb-2",
    )


def layout():
    return html.Div([
        html.H4("🗂 카테고리 관리", className="page-title"),

        dbc.Row([
            # 보유 종목 카테고리
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("보유 종목 카테고리", className="fw-bold"),
                        dbc.Button("+ 추가", id="cat-add-holding", color="primary",
                                   size="sm", className="float-end"),
                    ]),
                    dbc.CardBody([
                        html.Div(id="cat-holding-list"),
                        _action_panel("holding"),
                    ]),
                ]),
            ], md=6),

            # 관심 종목 카테고리
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("관심 종목 카테고리", className="fw-bold"),
                        dbc.Button("+ 추가", id="cat-add-watchlist", color="primary",
                                   size="sm", className="float-end"),
                    ]),
                    dbc.CardBody([
                        html.Div(id="cat-watchlist-list"),
                        _action_panel("watchlist"),
                    ]),
                ]),
            ], md=6),
        ]),

        dcc.Store(id="cat-sel-id"),
        dcc.Store(id="cat-sel-type"),
        dcc.Store(id="cat-trigger", data=0),

        # 추가/수정 모달
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="cat-modal-title")),
            dbc.ModalBody([
                dbc.Label("카테고리 이름 *"),
                dbc.Input(id="cat-m-name", placeholder="이름 입력", className="mb-3"),
                dbc.Label("색상"),
                _color_radios("cat-m-color"),
                html.Div(id="cat-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="cat-save", color="primary", className="me-2"),
                dbc.Button("닫기", id="cat-close-modal", color="secondary"),
            ]),
        ], id="cat-modal", is_open=False, backdrop="static"),

        # 삭제 확인 모달
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("삭제 확인")),
            dbc.ModalBody(id="cat-del-confirm-body"),
            dbc.ModalFooter([
                dbc.Button("삭제", id="cat-del-confirm-btn", color="danger", className="me-2"),
                dbc.Button("취소", id="cat-del-cancel-btn", color="secondary"),
            ]),
        ], id="cat-del-modal", is_open=False),

        dbc.Toast(id="cat-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),
    ])


# ── 콜백 ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("cat-holding-list", "children"),
    Output("cat-watchlist-list", "children"),
    Input("cat-trigger", "data"),
    prevent_initial_call=False,
)
def render_lists(_t):
    return _cat_list("holding"), _cat_list("watchlist")


# ── 행 클릭 → 카테고리 선택 ─────────────────────────────────────────────────────────

@callback(
    Output("cat-holding-panel", "style"),
    Output("cat-holding-sel-name", "children"),
    Output("cat-watchlist-panel", "style"),
    Output("cat-watchlist-sel-name", "children"),
    Output("cat-sel-id", "data"),
    Output("cat-sel-type", "data"),
    Input({"type": "cat-item-holding", "index": ALL}, "n_clicks"),
    Input({"type": "cat-item-watchlist", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_category(clicks_h, clicks_w):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update, no_update, no_update, no_update, no_update
    if not any(n for n in (clicks_h + clicks_w) if n):
        return no_update, no_update, no_update, no_update, no_update, no_update

    cid = triggered["index"]
    type_ = "holding" if "holding" in triggered["type"] else "watchlist"
    c = models.get_category(cid)
    if not c:
        return no_update, no_update, no_update, no_update, no_update, no_update

    show = {"display": "block"}
    hide = {"display": "none"}
    label = f"선택: {c['name']}"

    if type_ == "holding":
        return show, label, hide, "", cid, "holding"
    else:
        return hide, "", show, label, cid, "watchlist"


# ── 수정 버튼 → 모달 열기 ───────────────────────────────────────────────────────────

@callback(
    Output("cat-modal", "is_open", allow_duplicate=True),
    Output("cat-modal-title", "children"),
    Output("cat-m-name", "value"),
    Output("cat-m-color", "value"),
    Output("cat-sel-id", "data", allow_duplicate=True),
    Output("cat-sel-type", "data", allow_duplicate=True),
    Input("cat-add-holding", "n_clicks"),
    Input("cat-add-watchlist", "n_clicks"),
    Input("cat-holding-edit-btn", "n_clicks"),
    Input("cat-watchlist-edit-btn", "n_clicks"),
    State("cat-sel-id", "data"),
    State("cat-sel-type", "data"),
    prevent_initial_call=True,
)
def open_modal(_ah, _aw, _eh, _ew, sel_id, sel_type):
    triggered = ctx.triggered_id

    if triggered == "cat-add-holding":
        return True, "보유 카테고리 추가", "", COLOR_OPTIONS[0], None, "holding"
    if triggered == "cat-add-watchlist":
        return True, "관심 카테고리 추가", "", COLOR_OPTIONS[0], None, "watchlist"

    if triggered in ("cat-holding-edit-btn", "cat-watchlist-edit-btn"):
        if not sel_id:
            return no_update, no_update, no_update, no_update, no_update, no_update
        c = models.get_category(sel_id)
        if not c:
            return no_update, no_update, no_update, no_update, no_update, no_update
        label = "보유" if sel_type == "holding" else "관심"
        return True, f"{label} 카테고리 수정 — {c['name']}", c["name"], c["color"], no_update, no_update

    return no_update, no_update, no_update, no_update, no_update, no_update


@callback(
    Output("cat-modal", "is_open", allow_duplicate=True),
    Output("cat-err", "children"),
    Output("cat-trigger", "data", allow_duplicate=True),
    Output("cat-holding-panel", "style", allow_duplicate=True),
    Output("cat-watchlist-panel", "style", allow_duplicate=True),
    Output("cat-toast", "is_open", allow_duplicate=True),
    Output("cat-toast", "children", allow_duplicate=True),
    Input("cat-save", "n_clicks"),
    State("cat-m-name", "value"),
    State("cat-m-color", "value"),
    State("cat-sel-id", "data"),
    State("cat-sel-type", "data"),
    State("cat-trigger", "data"),
    prevent_initial_call=True,
)
def save_category(_n, name, color, sel_id, sel_type, trigger):
    if not name or not name.strip():
        return no_update, "이름을 입력하세요.", no_update, no_update, no_update, no_update, no_update

    hide = {"display": "none"}
    if sel_id:
        models.update_category(sel_id, name=name.strip(), color=color)
        msg = f"'{name}' 수정 완료"
    else:
        if not sel_type:
            return no_update, "오류: 유형 없음", no_update, no_update, no_update, no_update, no_update
        models.create_category(name.strip(), sel_type, color)
        msg = f"'{name}' 추가 완료"

    return False, "", (trigger or 0) + 1, hide, hide, True, msg


@callback(
    Output("cat-modal", "is_open", allow_duplicate=True),
    Input("cat-close-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_modal(_n):
    return False


# ── 삭제 버튼 → 확인 모달 ──────────────────────────────────────────────────────────

@callback(
    Output("cat-del-modal", "is_open", allow_duplicate=True),
    Output("cat-del-confirm-body", "children"),
    Input("cat-holding-del-btn", "n_clicks"),
    Input("cat-watchlist-del-btn", "n_clicks"),
    State("cat-sel-id", "data"),
    prevent_initial_call=True,
)
def open_del_confirm(_h, _w, sel_id):
    if not sel_id:
        return no_update, no_update
    c = models.get_category(sel_id)
    if not c:
        return no_update, no_update
    if models.category_has_items(sel_id):
        return no_update, no_update
    return True, f"'{c['name']}' 카테고리를 삭제하시겠습니까?"


@callback(
    Output("cat-toast", "is_open", allow_duplicate=True),
    Output("cat-toast", "children", allow_duplicate=True),
    Input("cat-holding-del-btn", "n_clicks"),
    Input("cat-watchlist-del-btn", "n_clicks"),
    State("cat-sel-id", "data"),
    prevent_initial_call=True,
)
def warn_has_items(_h, _w, sel_id):
    if not sel_id:
        return no_update, no_update
    if models.category_has_items(sel_id):
        return True, "종목이 있는 카테고리는 삭제할 수 없습니다."
    return no_update, no_update


@callback(
    Output("cat-del-modal", "is_open", allow_duplicate=True),
    Output("cat-trigger", "data", allow_duplicate=True),
    Output("cat-holding-panel", "style", allow_duplicate=True),
    Output("cat-watchlist-panel", "style", allow_duplicate=True),
    Output("cat-toast", "is_open", allow_duplicate=True),
    Output("cat-toast", "children", allow_duplicate=True),
    Input("cat-del-confirm-btn", "n_clicks"),
    Input("cat-del-cancel-btn", "n_clicks"),
    State("cat-sel-id", "data"),
    State("cat-trigger", "data"),
    prevent_initial_call=True,
)
def execute_delete(_confirm, _cancel, sel_id, trigger):
    hide = {"display": "none"}
    if ctx.triggered_id == "cat-del-confirm-btn" and sel_id:
        c = models.get_category(sel_id)
        name = c["name"] if c else str(sel_id)
        models.delete_category(sel_id)
        return False, (trigger or 0) + 1, hide, hide, True, f"'{name}' 삭제 완료"
    return False, no_update, no_update, no_update, no_update, no_update
