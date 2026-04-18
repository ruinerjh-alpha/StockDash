"""M2: DB CRUD 함수"""
import json
from db import get_connection


# ── Category ─────────────────────────────────────────────────────────────────────────────

def get_categories(type_filter=None):
    conn = get_connection()
    if type_filter:
        rows = conn.execute(
            "SELECT * FROM categories WHERE type=? ORDER BY name", (type_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY type, name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category(cat_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_category(name: str, type_: str, color: str = "#6c757d") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO categories (name, type, color) VALUES (?,?,?)",
        (name, type_, color)
    )
    conn.commit()
    cat_id = cur.lastrowid
    conn.close()
    return cat_id


def update_category(cat_id: int, name: str = None, color: str = None):
    conn = get_connection()
    if name is not None:
        conn.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
    if color is not None:
        conn.execute("UPDATE categories SET color=? WHERE id=?", (color, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()


def category_has_items(cat_id: int) -> bool:
    conn = get_connection()
    s = conn.execute("SELECT COUNT(*) FROM stocks WHERE category_id=?", (cat_id,)).fetchone()[0]
    w = conn.execute("SELECT COUNT(*) FROM watchlist WHERE category_id=?", (cat_id,)).fetchone()[0]
    conn.close()
    return (s + w) > 0


# ── Stocks (Holdings) ─────────────────────────────────────────────────────────────────

def get_stocks(category_id=None):
    conn = get_connection()
    if category_id is not None:
        rows = conn.execute("""
            SELECT s.*, c.name AS category_name, c.color AS category_color
            FROM stocks s LEFT JOIN categories c ON s.category_id=c.id
            WHERE s.category_id=? ORDER BY s.ticker
        """, (category_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.*, c.name AS category_name, c.color AS category_color
            FROM stocks s LEFT JOIN categories c ON s.category_id=c.id
            ORDER BY s.ticker
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stock(stock_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM stocks WHERE id=?", (stock_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stock_by_ticker(ticker: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM stocks WHERE ticker=?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_stock(ticker: str, name: str, category_id: int, memo: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO stocks (ticker, name, category_id, memo) VALUES (?,?,?,?)",
        (ticker, name, category_id, memo)
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_stock(stock_id: int, name: str = None, category_id: int = None, memo: str = None):
    conn = get_connection()
    if name is not None:
        conn.execute("UPDATE stocks SET name=? WHERE id=?", (name, stock_id))
    if category_id is not None:
        conn.execute("UPDATE stocks SET category_id=? WHERE id=?", (category_id, stock_id))
    if memo is not None:
        conn.execute("UPDATE stocks SET memo=? WHERE id=?", (memo, stock_id))
    conn.commit()
    conn.close()


def delete_stock(stock_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM stocks WHERE id=?", (stock_id,))
    conn.commit()
    conn.close()


# ── Trades ────────────────────────────────────────────────────────────────────────────

def get_trades(stock_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trades WHERE stock_id=? ORDER BY trade_date, id",
        (stock_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade(trade_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_trade(stock_id: int, trade_type: str, quantity: float,
                 price: float, trade_date: str, fee: float = 0, memo: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO trades (stock_id,trade_type,quantity,price,trade_date,fee,memo) "
        "VALUES (?,?,?,?,?,?,?)",
        (stock_id, trade_type, quantity, price, trade_date, fee, memo)
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def update_trade(trade_id: int, **kwargs):
    allowed = {"trade_type", "quantity", "price", "trade_date", "fee", "memo"}
    fields, values = [], []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return
    values.append(trade_id)
    conn = get_connection()
    conn.execute(f"UPDATE trades SET {', '.join(fields)} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_trade(trade_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def calculate_position(stock_id: int):
    """FIFO 기반 평균 매수가 및 보유 수량 계산. (quantity, avg_price) 반환"""
    trades = get_trades(stock_id)
    total_qty = 0.0
    total_cost = 0.0
    for t in trades:
        if t["trade_type"] == "buy":
            total_qty += t["quantity"]
            total_cost += t["quantity"] * t["price"] + t["fee"]
        else:
            if total_qty > 0:
                avg = total_cost / total_qty
                total_qty -= t["quantity"]
                total_cost = max(avg * total_qty, 0)
    if total_qty <= 0:
        return 0.0, 0.0
    return round(total_qty, 4), round(total_cost / total_qty, 4)


def get_all_trades_enriched() -> list:
    """전체 종목 매매이력 + FIFO 기반 실현손익 계산"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.id, t.stock_id, t.trade_type, t.quantity, t.price,
               t.trade_date, t.fee, t.memo,
               s.ticker, s.name AS stock_name,
               c.name AS category_name, c.color AS category_color
        FROM trades t
        JOIN stocks s ON t.stock_id = s.id
        LEFT JOIN categories c ON s.category_id = c.id
        ORDER BY t.stock_id, t.trade_date, t.id
    """).fetchall()
    conn.close()

    from collections import defaultdict
    stock_trades: dict = defaultdict(list)
    for r in rows:
        stock_trades[r["stock_id"]].append(dict(r))

    enriched = []
    for trades in stock_trades.values():
        avg_price = 0.0
        total_qty = 0.0
        total_cost = 0.0
        for t in trades:
            fee = t.get("fee") or 0
            if t["trade_type"] == "buy":
                total_qty += t["quantity"]
                total_cost += t["quantity"] * t["price"] + fee
                avg_price = total_cost / total_qty if total_qty else 0
                t["avg_buy_price"] = round(avg_price, 0)
                t["realized_pnl"] = None
                t["return_rate"] = None
            else:
                t["avg_buy_price"] = round(avg_price, 0)
                realized = (t["price"] - avg_price) * t["quantity"] - fee
                t["realized_pnl"] = round(realized, 0)
                t["return_rate"] = round(
                    (t["price"] - avg_price) / avg_price * 100, 2
                ) if avg_price else None
                total_qty = max(total_qty - t["quantity"], 0)
                total_cost = avg_price * total_qty if total_qty > 0 else 0
            enriched.append(t)

    enriched.sort(key=lambda x: (x["trade_date"], x["id"]), reverse=True)
    return enriched


def calculate_realized_pnl(stock_id: int) -> float:
    trades = get_trades(stock_id)
    avg_price = 0.0
    total_qty = 0.0
    total_cost = 0.0
    realized = 0.0
    for t in trades:
        if t["trade_type"] == "buy":
            total_qty += t["quantity"]
            total_cost += t["quantity"] * t["price"]
            avg_price = total_cost / total_qty if total_qty else 0
        else:
            realized += (t["price"] - avg_price) * t["quantity"] - t["fee"]
            total_qty -= t["quantity"]
            if total_qty > 0:
                total_cost = avg_price * total_qty
            else:
                total_qty = 0.0
                total_cost = 0.0
    return round(realized, 2)


# ── Watchlist ───────────────────────────────────────────────────────────────────────────

def get_watchlist(category_id=None):
    conn = get_connection()
    if category_id is not None:
        rows = conn.execute("""
            SELECT w.*, c.name AS category_name, c.color AS category_color
            FROM watchlist w LEFT JOIN categories c ON w.category_id=c.id
            WHERE w.category_id=? ORDER BY w.ticker
        """, (category_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT w.*, c.name AS category_name, c.color AS category_color
            FROM watchlist w LEFT JOIN categories c ON w.category_id=c.id
            ORDER BY w.ticker
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_watchlist_item(item_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM watchlist WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_watchlist_item(ticker: str, name: str, category_id: int,
                          registered_price: float, memo: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO watchlist (ticker,name,category_id,registered_price,memo) "
        "VALUES (?,?,?,?,?)",
        (ticker, name, category_id, registered_price, memo)
    )
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return iid


def update_watchlist_item(item_id: int, **kwargs):
    allowed = {"name", "category_id", "registered_price", "memo"}
    fields, values = [], []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return
    values.append(item_id)
    conn = get_connection()
    conn.execute(f"UPDATE watchlist SET {', '.join(fields)} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_watchlist_item(item_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# ── Indicator Configs ────────────────────────────────────────────────────────────────────

def get_indicator_configs():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM indicator_configs ORDER BY indicator"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["params"] = json.loads(d["params"])
        d["alert_rules"] = json.loads(d["alert_rules"])
        result.append(d)
    return result


def get_indicator_config(indicator: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM indicator_configs WHERE indicator=?", (indicator,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["params"] = json.loads(d["params"])
        d["alert_rules"] = json.loads(d["alert_rules"])
        return d
    return None


def upsert_indicator_config(indicator: str, params: dict,
                             alert_rules: dict, enabled: bool = True):
    conn = get_connection()
    conn.execute(
        "INSERT INTO indicator_configs (indicator,params,alert_rules,enabled) "
        "VALUES (?,?,?,?) ON CONFLICT(indicator) DO UPDATE SET "
        "params=excluded.params, alert_rules=excluded.alert_rules, "
        "enabled=excluded.enabled, updated_at=CURRENT_TIMESTAMP",
        (indicator, json.dumps(params), json.dumps(alert_rules), 1 if enabled else 0)
    )
    conn.commit()
    conn.close()


def toggle_indicator(indicator: str, enabled: bool):
    conn = get_connection()
    conn.execute(
        "UPDATE indicator_configs SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE indicator=?",
        (1 if enabled else 0, indicator)
    )
    conn.commit()
    conn.close()


def delete_indicator_config(indicator: str):
    conn = get_connection()
    conn.execute("DELETE FROM indicator_configs WHERE indicator=?", (indicator,))
    conn.commit()
    conn.close()
