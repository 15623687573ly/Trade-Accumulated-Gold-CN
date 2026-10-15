"""黄金积存金实时监控。

用法（在仓库根目录）:
  python3 -m monitor              常驻运行（systemd 托管）
  python3 -m monitor --once       跑一轮：抓银行页 + 出计划，打印而不推送
  python3 -m monitor --dry-run    常驻运行但只打日志不推送
  python3 -m monitor --stats      查看模拟盘战绩
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List

from .config import BANK_NAMES, BJ, Settings  # 先导入：把 skill scripts 加入 sys.path

from net_proxy import apply_proxy

from .accounts import Accounts, format_leaderboard
from .ai import axis_m_from_view, format_view
from .alerts import AlertEngine, format_plan
from .scorecard import evaluate as evaluate_scorecard, format_summary as scorecard_summary
from .market import Market
from .notify import Notifier
from .paper import PaperBook
from .store import Store, utc_now
from .strategy import build_plan

log = logging.getLogger("monitor")

DEFAULT_AXIS_M = {"axis": "震荡", "note": "无有效 AI 消息面判断，默认震荡"}
SHORT_STRATEGIES = {"short": "短线日内", "short_ai": "短线日内+AI"}
DAILY_VIEW_MAX_AGE_HOURS = 18
MACRO_REFRESH_SECONDS = 1800
JIN10_KEEP_HOURS = 36   # 数据库里保留多久的相关快讯（网页展示 + AI 上下文）   # 日线账户 09:05 运行时可用的 AI 判断最长时效（08:40 失败时可用前一晚 20:00 的）


class Monitor:
    def __init__(self, settings: Settings, dry_run: bool):
        self.settings = settings
        self.store = Store(settings.db_path)
        self.market = Market(settings, self.store)
        self.alerts = AlertEngine(settings, self.store)
        # 短线两个账户：原版（消息面固定震荡，作对照）与 AI 版（AxisM 来自 AI 判断）
        self.short_books = {key: PaperBook(settings, self.store, key, label)
                            for key, label in SHORT_STRATEGIES.items() if key in settings.strategies}
        self.short_enabled = bool(self.short_books)
        self.accounts = Accounts(settings, self.store, [k for k in settings.strategies if k not in SHORT_STRATEGIES])
        self.notifier = Notifier(settings, dry_run=dry_run)
        self._ai_thread: threading.Thread = None
        self._macro_at = None
        self._jin10_at = None
        self._jin10_seen: set = set()
        self._ai_results: "queue.Queue[Dict[str, str]]" = queue.Queue()
        self.analysts: Dict[str, "AIAnalyst"] = {}
        from .ai import AIAnalyst, detect_analysts
        for name, backend in detect_analysts(settings):
            try:
                self.analysts[name] = AIAnalyst(settings, self.store, backend, analyst=name)
            except Exception as exc:
                log.warning("%s 初始化失败，跳过: %s", name, exc)
        if self.analysts:
            log.info("AI 消息面分析已启用：%s；策略使用 %s 的判断",
                     "、".join(a.model_label for a in self.analysts.values()), settings.ai_strategy_source)

    @property
    def ai(self) -> bool:
        return bool(self.analysts)

    def ai_running(self) -> bool:
        return bool(self._ai_thread and self._ai_thread.is_alive())

    def recent_jin10(self) -> List[Dict]:
        """主线程调用（AI 后台线程不能用这里的 SQLite 连接）：给 AI 的金十快讯——
        24 小时内金十标红的重要快讯（最多 60 条）+ 6 小时内其他相关快讯（最多 20 条），新→旧。"""
        now = datetime.now(BJ)
        day = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        six = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        flashes = self.store.get_state("jin10_flash", [])
        important = [x for x in flashes if x["important"] and x["time_bj"] >= day][:60]
        other = [x for x in flashes if not x["important"] and x["time_bj"] >= six][:20]
        chosen = sorted(important + other, key=lambda x: x["time_bj"], reverse=True)
        return [{"time_bj": x["time_bj"], "important": x["important"], "text": x["text"][:160]} for x in chosen]

    def ai_context(self, snap, plan, jin10_recent=None) -> Dict:
        """给 AI 的上下文：行情 + 代码算出的点位 + 经济日历与宏观行情（均为程序直取，无需浏览器）。"""
        ctx = {
            "now_bj": datetime.now(BJ).strftime("%Y-%m-%d %H:%M"), "xauusd": snap["xauusd"],
            "change_pct": snap.get("change_pct"), "day_high": snap.get("day_high"), "day_low": snap.get("day_low"),
            "signals_tradingview": snap.get("signals"), "bank_price_cny_per_gram": snap.get("bank_est"),
            "usdcny": (snap.get("fx") or {}).get("rate"),
        }
        try:
            import macro_data
            macro = macro_data.snapshot()
            ctx["macro"] = {"quotes": macro.get("quotes"), "hard_events_24h": macro.get("hard_events_24h"),
                            "calendar": macro.get("calendar"), "errors": macro.get("errors")}
        except Exception as exc:
            ctx["macro"] = {"errors": [str(exc)]}
        ctx["jin10_flash_recent"] = jin10_recent or []
        if plan and plan.get("ok"):
            ctx["levels_by_code"] = {"resistance": [round(r["price"], 1) for r in plan["resistance"]],
                                     "support": [round(s["price"], 1) for s in plan["support"]],
                                     "intraday_pivot": round(plan["pivot"], 1)}
        return ctx

    def run_ai_if_due(self, snap, force: bool = False) -> List[Dict[str, str]]:
        """AI 分析在后台线程跑（一次 2-3 分钟），监控主循环不等待；完成后的推送在下一轮取出。"""
        if not self.ai:
            return []
        events: List[Dict[str, str]] = []
        while not self._ai_results.empty():
            events.append(self._ai_results.get_nowait())
        if self.ai_running():
            return events
        due = {name: ("手动" if force else a.due()) for name, a in self.analysts.items()}
        due = {name: trigger for name, trigger in due.items() if trigger}
        if not due:
            return events
        base_plan = build_plan(snap, axis_m=DEFAULT_AXIS_M, spread_cny=self.settings.spread_cny,
                               sell_fee_rate=self.settings.sell_fee_rate, ratio_bank=self.settings.paper_bank)
        self._ai_thread = threading.Thread(target=self._ai_worker, args=(dict(snap), base_plan, due, self.recent_jin10()),
                                           name="ai-analysis", daemon=True)
        self._ai_thread.start()
        return events

    def _ai_worker(self, snap, base_plan, due: Dict[str, str], jin10_recent=None) -> None:
        """同一份上下文交给各分析师并发判断（同一 run_id），全部完成后合并成一条推送。"""
        from concurrent.futures import ThreadPoolExecutor
        run_id = utc_now().isoformat(timespec="seconds")
        log.info("AI 消息面分析开始（%s，后台并发）", "、".join(f"{n}:{t}" for n, t in due.items()))
        try:
            context = self.ai_context(snap, base_plan, jin10_recent)
        except Exception:
            log.exception("AI 上下文准备失败")
            for name in due:   # 记为失败：30 分钟后再试，避免每分钟重试
                self.analysts[name]._failed_at = utc_now()
            return

        def run_one(name: str):
            store = Store(self.settings.db_path)      # 每个线程自己的 SQLite 连接
            try:
                return name, self.analysts[name].analyze(context, due[name], store=store, run_id=run_id)
            except Exception:
                log.exception("%s 分析线程异常", name)
                return name, None
            finally:
                store.conn.close()

        with ThreadPoolExecutor(max_workers=len(due)) as pool:
            views = dict(pool.map(run_one, due))
        done = {n: v for n, v in views.items() if v}
        if not done:
            return
        from .ai import ANALYST_NAMES
        title = "🧠" + "｜".join(f"{ANALYST_NAMES.get(n, n)}短期{axis_m_from_view(v)['axis']}" for n, v in done.items())
        parts = [f"## {ANALYST_NAMES.get(n, n)}\n\n{format_view(v)}" for n, v in done.items()]
        if len(done) >= 2:
            vs = list(done.values())
            agree = [f for f, label in (("bias_short", "短期"), ("bias_long", "中长期")) if vs[0][f] == vs[1][f]]
            parts.insert(0, "**两个 AI 判断**：" + ("、".join({"bias_short": "短期", "bias_long": "中长期"}[f] for f in agree) + "一致" if agree else "方向全部分歧")
                         + f"；策略使用：{self.settings.ai_strategy_source}")
        self._ai_results.put({"key": f"ai:{run_id}", "title": title, "body": "\n\n---\n\n".join(parts)})

    def wait_for_ai(self) -> None:
        if self._ai_thread:
            self._ai_thread.join()

    def publish_for_web(self, snap, plan, plan_base=None, plan_source: str = "base") -> None:
        """网页端只读数据库：把本轮行情与计划存一份，网页不自己联网。"""
        keep = ("xauusd", "change_pct", "day_high", "day_low", "bank_est", "signals", "market_open", "fx")
        payload = {k: snap.get(k) for k in keep}
        payload["ts"] = snap["ts"].isoformat()
        payload["plan"] = plan
        payload["plan_base"] = plan_base
        payload["plan_source"] = plan_source
        self.store.set_state("web_snapshot", json.loads(json.dumps(payload, ensure_ascii=False, default=str)))

    def request_ai_after_data_release(self) -> None:
        """美国重要数据（日历重大/重要两级）公布后约 10 分钟触发一次 AI，同一时刻公布的多项合并为一次。"""
        if not self.analysts:
            return
        calendar = (self.store.get_state("web_macro") or {}).get("calendar") or []
        now = utc_now()
        delay = timedelta(minutes=self.settings.ai_event_delay_minutes)
        done = set(self.store.get_state("ai_event_triggers", []))
        due_times = {}
        for e in calendar:
            if e.get("country") != "US" or e.get("tier", 3) > 2:
                continue
            at = datetime.fromisoformat(e["time_utc"])
            if at + delay <= now <= at + delay + timedelta(minutes=50) and e["time_utc"] not in done:
                due_times.setdefault(e["time_utc"], []).append(e)
        for time_utc, events in sorted(due_times.items()):
            names = "、".join(e["title"] for e in events[:3])
            for analyst in self.analysts.values():
                analyst.request_refresh(f"数据公布 {events[0]['time_bj']} {names}", min_gap_minutes=15)
            done.add(time_utc)
            log.info("重要数据已公布，触发 AI：%s %s", events[0]["time_bj"], names)
        if due_times:
            self.store.set_state("ai_event_triggers", sorted(done)[-50:])

    def poll_jin10_if_due(self, market_open: bool) -> None:
        """金十快讯：每 2 分钟抓一次，存下与金价相关的条目；金十标红的重要快讯（10 分钟内）在交易时段触发 AI。"""
        if not self.settings.jin10_enabled:
            return
        if self._jin10_at and (utc_now() - self._jin10_at).total_seconds() < self.settings.jin10_poll_seconds:
            return
        self._jin10_at = utc_now()
        stored = self.store.get_state("jin10_flash", [])
        try:
            import jin10_flash
            # 翻页到上次抓到的位置；首次启动或停机后自动补齐最近 24 小时
            full = not self.store.get_state("jin10_backfilled")
            since = None if full else max((x["time_bj"] for x in stored), default=None)
            items = jin10_flash.fetch_since(since)
            if full:
                self.store.set_state("jin10_backfilled", True)
        except Exception as exc:
            log.warning("金十快讯抓取失败: %s", exc)
            return
        seen = self._jin10_seen | {x["id"] for x in stored}
        new = [x for x in items if x["id"] not in seen]
        self._jin10_seen.update(x["id"] for x in items)
        if len(self._jin10_seen) > 2000:
            self._jin10_seen = {x["id"] for x in items}
        related = [x for x in new if jin10_flash.is_gold_related(x)]
        if not related:
            return
        cutoff = (datetime.now(BJ) - timedelta(hours=JIN10_KEEP_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
        merged = sorted({x["id"]: x for x in related + stored}.values(), key=lambda x: x["time_bj"], reverse=True)
        self.store.set_state("jin10_flash", [x for x in merged if x["time_bj"] >= cutoff])
        if len(related) > 20:
            log.info("金十快讯补抓：新增相关快讯 %d 条", len(related))

        now_bj = datetime.now(BJ)
        fresh = [x for x in related if x["important"]
                 and now_bj - datetime.strptime(x["time_bj"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BJ) <= timedelta(minutes=10)]
        if not (fresh and market_open and self.analysts):
            return
        caps = self.store.get_state("jin10_ai_triggers", {})
        today = now_bj.strftime("%Y-%m-%d")
        if caps.get(today, 0) >= self.settings.jin10_ai_daily_cap:
            log.info("金十重要快讯，但今日快讯触发已达上限 %d 次：%s", self.settings.jin10_ai_daily_cap, fresh[0]["text"][:40])
            return
        reason = f"金十快讯：{fresh[0]['text'][:30]}"
        for analyst in self.analysts.values():
            analyst.request_refresh(reason, min_gap_minutes=self.settings.jin10_ai_gap_minutes)
        self.store.set_state("jin10_ai_triggers", {today: caps.get(today, 0) + 1})
        log.info("金十重要快讯触发 AI：%s", fresh[0]["text"][:60])

    def refresh_macro_if_due(self) -> None:
        """网页宏观面板：美元指数/美债/离岸人民币 + 经济日历，每 30 分钟取一次（约 2 秒，无需浏览器）。"""
        if self._macro_at and (utc_now() - self._macro_at).total_seconds() < MACRO_REFRESH_SECONDS:
            return
        self._macro_at = utc_now()
        try:
            import macro_data
            self.store.set_state("web_macro", macro_data.snapshot())
        except Exception as exc:
            log.warning("宏观数据刷新失败: %s", exc)

    def current_view(self, max_age_hours: float):
        """策略使用的 AI 判断：按 GOLD_AI_STRATEGY_SOURCE 取 claude / codex / 两者共识。"""
        if not self.analysts:
            return None
        source = self.settings.ai_strategy_source
        if source == "consensus":
            from .ai import consensus_view
            return consensus_view({n: a.latest(max_age_hours) for n, a in self.analysts.items()})
        analyst = self.analysts.get(source)
        return analyst.latest(max_age_hours) if analyst else None

    def tick(self, force_bank: bool = False, force_ai: bool = False):
        events: List[Dict[str, str]] = []
        self.market.refresh_fx_if_due()
        snap = self.market.snapshot()
        if snap.get("xauusd") is None:
            log.warning("本轮取价全部失败: %s", snap["errors"])
            return snap, None, events

        # AI 分析期间两个 CLI 同时占内存，银行校准（Chromium）顺延到分析结束后
        if snap["market_open"] and (force_bank or (self.market.bank_due() and not self.ai_running())):
            log.info("校准银行换算比（Chromium）…")
            issues = self.market.calibrate_banks(snap["xauusd"])
            events += self.alerts.premium_events(issues)
            snap = self.market.snapshot()  # 用新换算比重算积存金估值

        self.store.add_tick(snap)
        self.poll_jin10_if_due(snap["market_open"])
        if not snap["market_open"]:
            self.publish_for_web(snap, None)
            return snap, None, events

        self.request_ai_after_data_release()
        events += self.run_ai_if_due(snap, force=force_ai)
        cost = {"spread_cny": self.settings.spread_cny, "sell_fee_rate": self.settings.sell_fee_rate,
                "ratio_bank": self.settings.paper_bank}
        base_plan = build_plan(snap, axis_m=DEFAULT_AXIS_M, **cost)
        view = self.current_view(self.settings.ai_view_max_age_hours)
        ai_plan = (build_plan(snap, axis_m=axis_m_from_view(view), **cost)
                   if view else None)
        plan = ai_plan or base_plan   # 提醒、摘要、网页展示：有 AI 判断时用 AI 版
        if self.short_enabled:
            alert_events = self.alerts.check(snap, plan)
            if self.ai and any(e["key"].startswith("move:") for e in alert_events):
                for analyst in self.analysts.values():
                    analyst.request_refresh(f"{int(self.settings.move_window_minutes)}分钟异动", min_gap_minutes=30)
            events += alert_events
            if "short" in self.short_books:
                events += self.short_books["short"].on_tick(snap, base_plan)
            if "short_ai" in self.short_books:
                # AI 判断过期时不开新仓，但已有持仓照常止损/止盈
                events += self.short_books["short_ai"].on_tick(snap, ai_plan or {"ok": False})
        events += self.accounts.run_daily(snap, self.current_view(DAILY_VIEW_MAX_AGE_HOURS))
        self.publish_for_web(snap, plan, base_plan, "ai" if ai_plan else "base")
        self.refresh_macro_if_due()
        events += self.digest_if_due(snap, plan)
        events += self.weekly_report_if_due(snap)
        return snap, plan, events

    def leaderboard_text(self, snap) -> str:
        price = (snap.get("bank_est") or {}).get(self.settings.paper_bank)
        short = {label: self.store.trade_stats(self.settings.paper_bank, key)
                 for key, label in SHORT_STRATEGIES.items() if key in self.short_books}
        return format_leaderboard(self.accounts.leaderboard(price), price, short)

    def weekly_report_if_due(self, snap) -> List[Dict[str, str]]:
        now_bj = datetime.now(BJ)
        weekday, hour = self.settings.weekly_report_bj
        if now_bj.weekday() != weekday or now_bj.hour != hour:
            return []
        key = f"weekly:{now_bj:%Y-%m-%d}"
        if not self.alerts.cooled_down(key, 24 * 60):
            return []
        body = self.leaderboard_text(snap)
        if self.ai:
            body += "\n\n" + scorecard_summary(evaluate_scorecard(self.store.conn))
        return [{"key": key, "title": f"🏆模拟盘周报 {now_bj:%m-%d}", "body": body}]

    def digest_if_due(self, snap, plan) -> List[Dict[str, str]]:
        now_bj = datetime.now(BJ)
        if now_bj.hour not in self.settings.digest_hours_bj:
            return []
        key = f"digest:{now_bj:%Y-%m-%d}:{now_bj.hour}"
        if not self.alerts.cooled_down(key, 24 * 60):
            return []
        return [{"key": key, "title": f"📊黄金计划 {now_bj:%H:%M} XAUUSD {snap['xauusd']:.0f}",
                 "body": format_plan(snap, plan) + "\n\n---\n\n" + self.leaderboard_text(snap)}]

    def dispatch(self, events: List[Dict[str, str]]) -> None:
        """同一轮多条提醒合并为一条推送，节省额度。"""
        if not events:
            return
        title = events[0]["title"] if len(events) == 1 else f"{events[0]['title']} 等{len(events)}条"
        body = "\n\n---\n\n".join(f"### {e['title']}\n\n{e['body']}" for e in events)
        delivered = self.notifier.send(title, body)
        for e in events:
            self.store.add_alert(e["key"], e["title"], e["body"], delivered)

    def run_forever(self) -> None:
        log.info("监控启动：推送通道=%s，每 %ss 一轮，模拟盘=%s", self.notifier.channel,
                 self.settings.tick_seconds, BANK_NAMES[self.settings.paper_bank])
        first = True
        while True:
            started = time.monotonic()
            try:
                snap, plan, events = self.tick()
                if first and plan:
                    events.insert(0, {"key": f"startup:{utc_now().isoformat()}", "title": "✅黄金监控已启动",
                                      "body": format_plan(snap, plan)})
                    first = False
                self.dispatch(events)
                if snap.get("xauusd"):
                    log.info("XAUUSD %.2f open=%s 事件=%d %s", snap["xauusd"], snap["market_open"], len(events),
                             plan["action"] if plan and plan.get("ok") else "")
            except Exception:
                log.exception("本轮异常，下一轮继续")
            time.sleep(max(1.0, self.settings.tick_seconds - (time.monotonic() - started)))


def print_stats(monitor: Monitor) -> None:
    bank = monitor.settings.paper_bank
    snap = monitor.market.snapshot()
    print(monitor.leaderboard_text(snap))
    print("\n各策略规则：")
    for b in monitor.accounts.leaderboard(None):
        print(f"- {b['name']}：{b['description']}")
    if monitor.ai:
        u = monitor.store.conn.execute(
            "SELECT COUNT(*) n, SUM(error IS NOT NULL) failed, COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, "
            "COALESCE(SUM(web_searches),0) s FROM ai_views WHERE ts >= date('now','-30 day')").fetchone()
        print("\n" + scorecard_summary(evaluate_scorecard(monitor.store.conn)))
        print(f"\nAI 分析（近 30 天）：{u['n']} 次（失败 {u['failed'] or 0}），输入 {u['i']:,} / 输出 {u['o']:,} tokens，联网搜索 {u['s']} 次")
    print("\n最近成交：")
    for f in monitor.store.conn.execute("SELECT * FROM account_fills ORDER BY ts DESC LIMIT 15").fetchall():
        print(f"  {f['ts'][:16]} [{f['strategy']}] {'买' if f['side'] == 'buy' else '卖'} {f['grams']:.2f}g @ {f['price']:.2f} ｜ {f['reason']}")
    for key, book in monitor.short_books.items():
        print(f"\n{book.label} 逐笔：")
        for t in monitor.store.all_trades(bank, key):
            print(f"#{t['id']} {t['status']:<6} {t['opened_at']} 入 {t['entry_cny']:.2f} × {t['grams']:g}g "
                  f"止损 {t['stop_cny']:.2f} T1 {t['t1_cny']:.2f} T2 {t['t2_cny']:.2f} "
                  f"已实现 {t['realized_cny']:+.2f} {t['close_reason'] or ''}")


def main() -> int:
    parser = argparse.ArgumentParser(description="黄金积存金实时监控")
    parser.add_argument("--once", action="store_true", help="跑一轮并打印计划（不推送）")
    parser.add_argument("--dry-run", action="store_true", help="只打日志不推送")
    parser.add_argument("--stats", action="store_true", help="打印模拟盘战绩")
    parser.add_argument("--ai-now", action="store_true", help="配合 --once：立即跑一次 AI 消息面分析")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    apply_proxy()
    monitor = Monitor(Settings(), dry_run=args.dry_run or args.once)

    if args.stats:
        print_stats(monitor)
        return 0
    if args.once:
        if args.ai_now and not monitor.ai:
            print("AI 未启用：没有 ANTHROPIC_API_KEY，本机也找不到 claude 命令")
            return 1
        snap, plan, events = monitor.tick(force_bank=True, force_ai=args.ai_now)
        if args.ai_now:   # --once 时等后台分析完成，再跑一轮让策略用上新判断
            monitor.wait_for_ai()
            snap, plan, more = monitor.tick()
            events += more
        if plan:
            print(format_plan(snap, plan))
        else:
            print(f"休市或取价失败：market_open={snap.get('market_open')} errors={snap.get('errors')}")
        print(f"\n本轮触发事件 {len(events)} 条：")
        for e in events:
            body = e["body"] if e["key"].startswith("ai:") else e["body"][:120]
            print(f"- {e['title']}：{body}")
        return 0
    monitor.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
