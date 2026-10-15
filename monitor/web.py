"""网页看板：只读 SQLite，展示行情、计划、AI 判断与多策略模拟盘战绩。

  python3 -m monitor.web                    默认只监听 127.0.0.1:8080（经 SSH 隧道访问）
  GOLD_WEB_HOST=0.0.0.0 python3 -m monitor.web   对外监听，必须设置 GOLD_WEB_PASSWORD

纯标准库实现，独立进程运行；网页不联网取数，全部来自监控程序写入的数据库。
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import BANK_NAMES, Settings
from .scorecard import evaluate as evaluate_scorecard
from .strategies import REGISTRY

log = logging.getLogger("monitor.web")

STATIC = Path(__file__).resolve().parent / "static"
SERIES_ORDER = ["hold", "dca", "dca_smart", "position", "dca_smart_ai", "position_ai"]   # 颜色槽位固定跟随策略


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def get_state(conn: sqlite3.Connection, key: str) -> Any:
    row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def hourly_prices(conn: sqlite3.Connection, bank: str, since: str) -> List[Dict[str, Any]]:
    """积存金估值按小时取最后一笔，用于重建各账户净值曲线。"""
    column = "zheshang_est" if bank == "zheshang" else "minsheng_est"
    rows = conn.execute(
        f"SELECT ts, {column} p FROM ticks WHERE rowid IN (SELECT MAX(rowid) FROM ticks WHERE ts >= ? "
        f"AND {column} IS NOT NULL GROUP BY substr(ts,1,13)) ORDER BY ts",
        (since,),
    ).fetchall()
    return [{"ts": r["ts"], "p": r["p"]} for r in rows]


def equity_curves(conn: sqlite3.Connection, settings: Settings) -> Dict[str, Any]:
    """按成交记录重建每个账户的持仓，再用每小时积存金估值算净值（按「现在全卖」扣手续费）。"""
    if not table_exists(conn, "accounts"):
        return {"series": [], "start": None}
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    started = [a for a in accounts if json.loads(a["state_json"]).get("start_index", -1) >= 0]
    if not started:
        return {"series": [], "start": None}
    start = min(a["started_at"] for a in started)
    prices = hourly_prices(conn, settings.paper_bank, start)
    fee = settings.sell_fee_rate
    series = []
    for acct in started:
        fills = conn.execute("SELECT * FROM account_fills WHERE strategy=? ORDER BY ts", (acct["strategy"],)).fetchall()
        cash, grams, k, points = acct["budget"], 0.0, 0, []
        for pt in prices:
            if pt["ts"] < acct["started_at"]:
                continue
            while k < len(fills) and fills[k]["ts"] <= pt["ts"]:
                f = fills[k]
                if f["side"] == "buy":
                    cash -= f["grams"] * f["price"]
                    grams += f["grams"]
                else:
                    cash += f["grams"] * f["price"] - f["fee"]
                    grams -= f["grams"]
                k += 1
            value = cash + grams * pt["p"] * (1 - fee)
            points.append([pt["ts"], round(value / acct["budget"] - 1, 6)])
        series.append({"key": acct["strategy"], "name": acct["name"], "points": points})
    series.sort(key=lambda s: SERIES_ORDER.index(s["key"]) if s["key"] in SERIES_ORDER else 99)
    return {"series": series, "start": start}


def leaderboard(conn: sqlite3.Connection, settings: Settings, price: Optional[float]) -> List[Dict[str, Any]]:
    if not table_exists(conn, "accounts"):
        return []
    fee = settings.sell_fee_rate
    board = []
    for acct in conn.execute("SELECT * FROM accounts").fetchall():
        state = json.loads(acct["state_json"])
        started = state.get("start_index", -1) >= 0
        cls = REGISTRY.get(acct["strategy"])
        grams, cash, cost = state["grams"], state["cash"], state["cost"]
        value = cash + grams * price * (1 - fee) if price else None
        values = [r["value"] for r in conn.execute(
            "SELECT value FROM account_equity WHERE strategy=? ORDER BY day", (acct["strategy"],)).fetchall()]
        peak, mdd = 0.0, 0.0
        for v in values + ([value] if value is not None else []):
            peak = max(peak, v)
            if peak:
                mdd = max(mdd, 1 - v / peak)
        f = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(fee),0) fee FROM account_fills WHERE strategy=?",
                         (acct["strategy"],)).fetchone()
        board.append({
            "key": acct["strategy"], "name": acct["name"], "started": started,
            "started_at": acct["started_at"] if started else None,
            "requires_ai": bool(cls and cls.requires_ai), "description": cls.description if cls else "",
            "horizon": cls.horizon if cls else "",
            "budget": acct["budget"], "value": value,
            "return": (value / acct["budget"] - 1) if value is not None else None, "max_drawdown": mdd,
            "grams": grams, "cash": cash, "avg_cost": cost / grams if grams > 1e-9 else None,
            "fills": f["c"], "fees": f["fee"],
        })
    board.sort(key=lambda b: (not b["started"], -(b["return"] or 0)))
    return board


SHORT_LABELS = {"short": "短线日内", "short_ai": "短线日内+AI"}


def short_paper(conn: sqlite3.Connection, bank: str, strategy: str, price: Optional[float], fee_rate: float) -> Dict[str, Any]:
    rows = conn.execute("SELECT * FROM paper_trades WHERE bank=? AND strategy=? ORDER BY id DESC LIMIT 20",
                        (bank, strategy)).fetchall()
    closed = [r["realized_cny"] for r in conn.execute(
        "SELECT realized_cny FROM paper_trades WHERE bank=? AND strategy=? AND status='closed'", (bank, strategy)).fetchall()]
    wins = [p for p in closed if p > 0]
    losses = [p for p in closed if p <= 0]
    open_row = conn.execute(
        "SELECT * FROM paper_trades WHERE bank=? AND strategy=? AND status='open' ORDER BY id DESC LIMIT 1",
        (bank, strategy)).fetchone()
    open_pos = None
    if open_row:
        unrealized = (price * (1 - fee_rate) - open_row["entry_cny"]) * open_row["open_grams"] if price else None
        open_pos = {k: open_row[k] for k in ("id", "opened_at", "entry_cny", "grams", "open_grams", "stop_cny",
                                              "t1_cny", "t2_cny", "t1_hit", "realized_cny")}
        open_pos["unrealized"] = unrealized
    first_tick = conn.execute("SELECT MIN(ts) t FROM ticks").fetchone()["t"]
    return {
        "key": strategy, "label": SHORT_LABELS.get(strategy, strategy),
        "trades": len(closed), "win_rate": len(wins) / len(closed) if closed else None,
        "total_pnl": round(sum(closed), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "open": open_pos, "running_since": first_tick,
        "recent": [{k: r[k] for k in ("id", "status", "opened_at", "entry_cny", "grams", "stop_cny", "t1_cny",
                                       "t2_cny", "realized_cny", "close_reason", "closed_at")} for r in rows],
    }


def price_history(conn: sqlite3.Connection) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    day = conn.execute(
        "SELECT ts, xauusd FROM ticks WHERE rowid IN (SELECT MAX(rowid) FROM ticks WHERE ts >= ? AND market_open=1 "
        "GROUP BY substr(ts,1,15)) ORDER BY ts", ((now - timedelta(hours=24)).isoformat(timespec="seconds"),)).fetchall()
    week = conn.execute(
        "SELECT ts, xauusd FROM ticks WHERE rowid IN (SELECT MAX(rowid) FROM ticks WHERE ts >= ? AND market_open=1 "
        "GROUP BY substr(ts,1,13)) ORDER BY ts", ((now - timedelta(days=7)).isoformat(timespec="seconds"),)).fetchall()
    return {"1d": [[r["ts"], r["xauusd"]] for r in day if r["xauusd"]],
            "7d": [[r["ts"], r["xauusd"]] for r in week if r["xauusd"]]}


ANALYST_NAMES = {"claude": "Claude", "codex": "Codex"}


def ai_section(conn: sqlite3.Connection, settings: Settings) -> Dict[str, Any]:
    if not table_exists(conn, "ai_views"):
        return {"enabled": False, "latest": None, "analysts": [], "history": []}
    has_analyst = "analyst" in {r[1] for r in conn.execute("PRAGMA table_info(ai_views)")}
    names = [n for n in settings.ai_analysts] if has_analyst else ["claude"]
    analysts = []
    for name in names:
        row = (conn.execute("SELECT * FROM ai_views WHERE error IS NULL AND analyst=? ORDER BY ts DESC LIMIT 1", (name,))
               if has_analyst else conn.execute("SELECT * FROM ai_views WHERE error IS NULL ORDER BY ts DESC LIMIT 1")).fetchone()
        if row:
            analysts.append({**json.loads(row["view_json"]), "analyst": name, "name": ANALYST_NAMES.get(name, name),
                             "ts": row["ts"], "model": row["model"], "sources": json.loads(row["sources_json"] or "[]")[:12]})
    history = conn.execute(f"SELECT ts, trigger, view_json, error{', analyst' if has_analyst else ''} FROM ai_views "
                           "ORDER BY ts DESC LIMIT 20").fetchall()

    def brief(r):
        v = json.loads(r["view_json"]) if r["view_json"] else {}
        return {"ts": r["ts"], "trigger": r["trigger"], "error": r["error"],
                "analyst": ANALYST_NAMES.get(r["analyst"], r["analyst"]) if has_analyst else "Claude",
                "bias_short": v.get("bias_short"), "bias_long": v.get("bias_long"), "confidence": v.get("confidence")}
    return {"enabled": True, "latest": analysts[0] if analysts else None, "analysts": analysts,
            "strategy_source": settings.ai_strategy_source, "history": [brief(r) for r in history]}


def dashboard(settings: Settings) -> Dict[str, Any]:
    conn = connect(settings.db_path)
    try:
        snap = get_state(conn, "web_snapshot") or {}
        price = (snap.get("bank_est") or {}).get(settings.paper_bank)
        fills = conn.execute(
            "SELECT * FROM account_fills ORDER BY ts DESC LIMIT 20").fetchall() if table_exists(conn, "account_fills") else []
        alerts = conn.execute("SELECT ts, title, delivered FROM alerts ORDER BY ts DESC LIMIT 20").fetchall()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bank": settings.paper_bank, "bank_name": BANK_NAMES[settings.paper_bank],
            "sell_fee_rate": settings.sell_fee_rate, "snapshot": snap,
            "leaderboard": leaderboard(conn, settings, price),
            "equity": equity_curves(conn, settings),
            "short": [short_paper(conn, settings.paper_bank, key, price, settings.sell_fee_rate)
                      for key in SHORT_LABELS if key in settings.strategies],
            "prices": price_history(conn),
            "ai": ai_section(conn, settings),
            "scorecard": evaluate_scorecard(conn),
            "macro": get_state(conn, "web_macro"),
            "jin10": (get_state(conn, "jin10_flash") or [])[:30],
            "fills": [{k: r[k] for k in ("strategy", "ts", "side", "grams", "price", "fee", "reason")} for r in fills],
            "alerts": [{"ts": r["ts"], "title": r["title"], "delivered": bool(r["delivered"])} for r in alerts],
            "strategy_names": {k: cls.name for k, cls in REGISTRY.items()},
            "series_order": SERIES_ORDER,
        }
    finally:
        conn.close()


AUTH_FAIL_LIMIT = 10            # 同一 IP 在窗口内最多输错次数
AUTH_FAIL_WINDOW = 600          # 秒
_auth_failures: Dict[str, deque] = defaultdict(deque)
_auth_lock = threading.Lock()


def _locked_out(ip: str) -> bool:
    now = time.monotonic()
    with _auth_lock:
        q = _auth_failures[ip]
        while q and now - q[0] > AUTH_FAIL_WINDOW:
            q.popleft()
        return len(q) >= AUTH_FAIL_LIMIT


def _record_failure(ip: str) -> None:
    with _auth_lock:
        _auth_failures[ip].append(time.monotonic())


class Handler(BaseHTTPRequestHandler):
    settings: Settings
    password: str
    server_version = "gold-dashboard"
    sys_version = ""

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def _authorized(self) -> bool:
        if not self.password:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            _, _, given = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        return hmac.compare_digest(given.encode(), self.password.encode())

    def _send(self, code: int, body: bytes, content_type: str, extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        ip = self.client_address[0]
        if _locked_out(ip):
            self._send(429, "尝试次数过多，请 10 分钟后再试".encode(), "text/plain; charset=utf-8")
            return
        if not self._authorized():
            if self.headers.get("Authorization"):
                _record_failure(ip)
                log.warning("密码错误：%s", ip)
            self._send(401, "需要密码".encode(), "text/plain; charset=utf-8",
                       {"WWW-Authenticate": 'Basic realm="gold-monitor", charset="UTF-8"'})
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/dashboard":
            try:
                body = json.dumps(dashboard(self.settings), ensure_ascii=False, default=str).encode()
                self._send(200, body, "application/json; charset=utf-8")
            except Exception as exc:
                log.exception("dashboard 失败")
                self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    host = os.environ.get("GOLD_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("GOLD_WEB_PORT", "8080"))
    password = os.environ.get("GOLD_WEB_PASSWORD", "").strip()
    if host not in ("127.0.0.1", "localhost", "::1") and len(password) < 12:
        log.error("对外监听 %s 时必须在 .env 设置至少 12 位的 GOLD_WEB_PASSWORD，已拒绝启动", host)
        return 1
    Handler.settings, Handler.password = settings, password
    server = ThreadingHTTPServer((host, port), Handler)
    log.info("网页看板已启动：http://%s:%d %s", host, port, "（已启用密码）" if password else "（仅本机）")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
