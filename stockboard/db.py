"""M1: SQLite 연결 및 테이블 초기화"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "stockboard.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            type       TEXT    NOT NULL CHECK(type IN ('holding','watchlist')),
            color      TEXT    DEFAULT '#6c757d',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stocks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            name        TEXT,
            category_id INTEGER REFERENCES categories(id),
            memo        TEXT    DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trades (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id   INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
            trade_type TEXT    NOT NULL CHECK(trade_type IN ('buy','sell')),
            quantity   REAL    NOT NULL,
            price      REAL    NOT NULL,
            trade_date TEXT    NOT NULL,
            fee        REAL    DEFAULT 0,
            memo       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker           TEXT    NOT NULL,
            name             TEXT,
            category_id      INTEGER REFERENCES categories(id),
            registered_price REAL,
            registered_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            memo             TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS indicator_configs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator   TEXT    NOT NULL UNIQUE,
            params      TEXT    DEFAULT '{}',
            alert_rules TEXT    DEFAULT '{}',
            enabled     INTEGER DEFAULT 1,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    defaults = [
        ("RSI",    json.dumps({"period": 14}),
                   json.dumps({"overbought": 70, "oversold": 30}), 1),
        ("MACD",   json.dumps({"fast": 12, "slow": 26, "signal": 9}),
                   json.dumps({"cross": True}), 1),
        ("BB",     json.dumps({"period": 20, "std": 2}),
                   json.dumps({"breakout": True}), 1),
        ("MA",     json.dumps({"periods": [5, 20, 60, 120]}),
                   json.dumps({"cross": True}), 1),
        ("Volume", json.dumps({"ma_period": 5, "multiplier": 2}),
                   json.dumps({"surge": True}), 1),
    ]
    for name, params, rules, enabled in defaults:
        cur.execute(
            "INSERT OR IGNORE INTO indicator_configs "
            "(indicator, params, alert_rules, enabled) VALUES (?,?,?,?)",
            (name, params, rules, enabled)
        )

    conn.commit()
    conn.close()
