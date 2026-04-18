"""M5: Dash 앱 초기화"""
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="StockBoard",
)

_nav_items = [
    ("보유 종목", "/"),
    ("관심 종목", "/watchlist"),
    ("매매이력",  "/trades"),
    ("카테고리",  "/categories"),
    ("지표 설정", "/settings"),
]

navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand(
            [html.I(className="bi bi-bar-chart-fill me-2"), "StockBoard"],
            href="/",
            className="fw-bold fs-5 text-white",
        ),
        dbc.NavbarToggler(id="navbar-toggler"),
        dbc.Collapse(
            dbc.Nav(
                [dbc.NavItem(dbc.NavLink(label, href=href, active="exact"))
                 for label, href in _nav_items],
                navbar=True,
                className="ms-auto",
            ),
            id="navbar-collapse",
            navbar=True,
        ),
    ], fluid=True),
    color="dark",
    dark=True,
    sticky="top",
    className="mb-3 shadow",
)

app.layout = html.Div([
    dcc.Location(id="url"),
    navbar,
    dbc.Container(dash.page_container, fluid=True, className="pb-5"),
], style={"minHeight": "100vh", "backgroundColor": "#1a1a2e"})
