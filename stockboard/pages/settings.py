"""M9: 지표 설정 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import dash
from dash import html, dcc, Input, Output, State, callback, ctx, ALL, no_update
import dash_bootstrap_components as dbc

import models

dash.register_page(__name__, path="/settings", name="지표 설정", order=3)

BUILTIN = {"RSI", "MACD", "BB", "MA", "Volume"}


def _indicator_description(ind: str) -> str:
    desc = {
        "RSI": "상대 강도 지수 — 과매수/과매도 감지",
        "MACD": "이동 평균 수렴·발산 — 골든/데드크로스",
        "BB": "볼린저 밴드 — 상단 돌파 / 하단 이탈",
        "MA": "이동 평균선 — 단기/장기 크로스",
        "Volume": "거래량 — 평균 대비 급증 감지",
    }
    return desc.get(ind, "사용자 정의 지표")


def _build_rows(configs):
    rows = []
    for cfg in configs:
        ind = cfg["indicator"]
        is_builtin = ind in BUILTIN
        enabled = bool(cfg["enabled"])

        rows.append(html.Tr([
            html.Td(dbc.Badge(ind, color="primary" if is_builtin else "secondary")),
            html.Td(_indicator_description(ind),
                    style={"fontSize": "0.85rem", "color": "#a0a0c0"}),
            html.Td(html.Code(json.dumps(cfg["params"], ensure_ascii=False),
                              style={"fontSize": "0.78rem", "color": "#7ecfff"})),
            html.Td(html.Code(json.dumps(cfg["alert_rules"], ensure_ascii=False),
                              style={"fontSize": "0.78rem", "color": "#ffd32a"})),
            html.Td(
                dbc.Switch(
                    id={"type": "set-toggle", "index": ind},
                    value=enabled,
                    label="ON" if enabled else "OFF",
                    className="mb-0",
                )
            ),
            html.Td([
                dbc.Button("수정", id={"type": "set-edit-btn", "index": ind},
                           color="secondary", size="sm", className="btn-action me-1"),
                dbc.Button("삭제", id={"type": "set-del-btn", "index": ind},
                           color="danger", size="sm", className="btn-action",
                           disabled=is_builtin,
                           title="기본 지표는 삭제할 수 없습니다." if is_builtin else ""),
            ]),
        ], className="align-middle"))
    return rows


def layout():
    configs = models.get_indicator_configs()
    return html.Div([
        html.H4("⚙️ 지표 설정", className="page-title"),

        dbc.Card([
            dbc.CardHeader(html.Span("활성화된 지표 목록", className="fw-bold")),
            dbc.CardBody(
                dbc.Table(
                    [html.Thead(html.Tr([
                        html.Th("지표"), html.Th("설명"), html.Th("파라미터"),
                        html.Th("이상 신호 규칙"), html.Th("활성화"), html.Th(""),
                    ])),
                     html.Tbody(id="set-table-body",
                                children=_build_rows(configs))],
                    hover=True, responsive=True, size="sm", className="table-dark",
                )
            ),
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader(html.Span("사용자 정의 지표 추가", className="fw-bold")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([dbc.Label("지표명 *"),
                             dbc.Input(id="set-new-name", placeholder="예: EMA")], md=3),
                    dbc.Col([dbc.Label("파라미터 (JSON) *"),
                             dbc.Input(id="set-new-params",
                                       placeholder='{"period": 21}')], md=4),
                    dbc.Col([dbc.Label("이상 신호 규칙 (JSON)"),
                             dbc.Input(id="set-new-rules",
                                       placeholder='{"threshold": 0.5}')], md=4),
                    dbc.Col([dbc.Label("\u00a0"),
                             dbc.Button("추가", id="set-add-custom", color="primary",
                                        className="d-block")], md=1),
                ], className="g-2"),
                html.Div(id="set-add-err", className="text-danger mt-2"),
            ]),
        ], className="mb-4"),

        dcc.Store(id="set-sel-ind"),
        dcc.Store(id="set-trigger", data=0),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="set-modal-title")),
            dbc.ModalBody([
                dbc.Label("파라미터 (JSON) *"),
                dbc.Textarea(id="set-m-params", rows=4,
                             style={"fontFamily": "monospace"}),
                dbc.Label("이상 신호 규칙 (JSON)", className="mt-3"),
                dbc.Textarea(id="set-m-rules", rows=4,
                             style={"fontFamily": "monospace"}),
                html.Div(id="set-edit-err", className="text-danger mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("저장", id="set-save", color="primary", className="me-2"),
                dbc.Button("닫기", id="set-close-modal", color="secondary"),
            ]),
        ], id="set-modal", is_open=False, backdrop="static"),

        dbc.Toast(id="set-toast", header="알림", is_open=False, duration=3000,
                  style={"position": "fixed", "top": 80, "right": 20, "zIndex": 9999}),
    ])


@callback(
    Output("set-table-body", "children"),
    Input("set-trigger", "data"),
    prevent_initial_call=False,
)
def refresh_table(_t):
    return _build_rows(models.get_indicator_configs())


@callback(
    Output("set-toast", "is_open", allow_duplicate=True),
    Output("set-toast", "children", allow_duplicate=True),
    Input({"type": "set-toggle", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def toggle_indicator(values):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update
    ind = triggered["index"]
    triggered_props = ctx.triggered
    if not triggered_props:
        return no_update, no_update
    new_val = triggered_props[0]["value"]
    models.toggle_indicator(ind, bool(new_val))
    state = "활성화" if new_val else "비활성화"
    return True, f"{ind} {state} 완료"


@callback(
    Output("set-modal", "is_open", allow_duplicate=True),
    Output("set-modal-title", "children"),
    Output("set-m-params", "value"),
    Output("set-m-rules", "value"),
    Output("set-sel-ind", "data"),
    Input({"type": "set-edit-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_edit_modal(clicks):
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "set-edit-btn":
        if any(n for n in clicks if n):
            ind = triggered["index"]
            cfg = models.get_indicator_config(ind)
            if cfg:
                return (True, f"{ind} 설정 수정",
                        json.dumps(cfg["params"], indent=2, ensure_ascii=False),
                        json.dumps(cfg["alert_rules"], indent=2, ensure_ascii=False),
                        ind)
    return no_update, no_update, no_update, no_update, no_update


@callback(
    Output("set-modal", "is_open", allow_duplicate=True),
    Output("set-edit-err", "children"),
    Output("set-trigger", "data", allow_duplicate=True),
    Output("set-toast", "is_open", allow_duplicate=True),
    Output("set-toast", "children", allow_duplicate=True),
    Input("set-save", "n_clicks"),
    State("set-m-params", "value"),
    State("set-m-rules", "value"),
    State("set-sel-ind", "data"),
    State("set-trigger", "data"),
    prevent_initial_call=True,
)
def save_config(_n, params_str, rules_str, ind, trigger):
    if not ind:
        return no_update, "오류", no_update, no_update, no_update
    try:
        params = json.loads(params_str or "{}")
        rules = json.loads(rules_str or "{}")
    except json.JSONDecodeError as e:
        return no_update, f"JSON 오류: {e}", no_update, no_update, no_update

    cfg = models.get_indicator_config(ind)
    enabled = bool(cfg["enabled"]) if cfg else True
    models.upsert_indicator_config(ind, params, rules, enabled)
    return False, "", (trigger or 0) + 1, True, f"{ind} 설정 저장 완료"


@callback(
    Output("set-modal", "is_open", allow_duplicate=True),
    Input("set-close-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_modal(_n):
    return False


@callback(
    Output("set-add-err", "children"),
    Output("set-trigger", "data", allow_duplicate=True),
    Output("set-toast", "is_open", allow_duplicate=True),
    Output("set-toast", "children", allow_duplicate=True),
    Output("set-new-name", "value"),
    Output("set-new-params", "value"),
    Output("set-new-rules", "value"),
    Input("set-add-custom", "n_clicks"),
    State("set-new-name", "value"),
    State("set-new-params", "value"),
    State("set-new-rules", "value"),
    State("set-trigger", "data"),
    prevent_initial_call=True,
)
def add_custom(_n, name, params_str, rules_str, trigger):
    if not name or not name.strip():
        return "지표명을 입력하세요.", no_update, no_update, no_update, no_update, no_update, no_update
    try:
        params = json.loads(params_str or "{}")
    except json.JSONDecodeError:
        return "파라미터 JSON 오류", no_update, no_update, no_update, no_update, no_update, no_update
    try:
        rules = json.loads(rules_str or "{}")
    except json.JSONDecodeError:
        return "신호 규칙 JSON 오류", no_update, no_update, no_update, no_update, no_update, no_update

    ind_name = name.strip().upper()
    models.upsert_indicator_config(ind_name, params, rules, True)
    return "", (trigger or 0) + 1, True, f"'{ind_name}' 추가 완료", "", "", ""


@callback(
    Output("set-trigger", "data", allow_duplicate=True),
    Output("set-toast", "is_open", allow_duplicate=True),
    Output("set-toast", "children", allow_duplicate=True),
    Input({"type": "set-del-btn", "index": ALL}, "n_clicks"),
    State("set-trigger", "data"),
    prevent_initial_call=True,
)
def delete_indicator(clicks, trigger):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update, no_update
    if not any(n for n in clicks if n):
        return no_update, no_update, no_update
    ind = triggered["index"]
    if ind in BUILTIN:
        return no_update, True, "기본 지표는 삭제할 수 없습니다."
    models.delete_indicator_config(ind)
    return (trigger or 0) + 1, True, f"'{ind}' 삭제 완료"
