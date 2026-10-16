"""Browser integration using a temporary database and local server only."""
import importlib.util
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

from monitor.config import Settings
from monitor.__main__ import Monitor
from monitor.ai import AIAnalyst, MarketView
from monitor.store import utc_now
from monitor.web import Handler, ThreadingHTTPServer
from monitor.controls import control


@unittest.skipUnless(importlib.util.find_spec("playwright"), "Playwright is optional")
class DashboardBrowserTests(unittest.TestCase):
    def test_render_compare_switch_and_reload(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(Settings(), db_path=Path(tmp) / "test.db", ai_analysts=("claude", "codex"),
                               ai_backend="api", anthropic_api_key="", codex_cli="missing-codex", claude_cli="missing-claude")
            monitor = Monitor(settings, True)
            market = {"ts": utc_now(), "market_open": True, "xauusd": 4000, "change_pct": .3,
                      "day_high": 4100, "day_low": 3900, "day_open": 3998,
                      "fx": {"rate": 7.1234, "fetched_at": utc_now().isoformat()},
                      "bank_est": {"zheshang": 1000, "minsheng": 1001},
                      "ratings": {"30m": .6, "1h": .6, "4h": .6, "1d": .6},
                      "signals": {"30m": "买入", "1H": "买入", "4H": "买入"},
                      "execution_quote": {"price": 1000, "source": "jd_latest_price_api", "quote_at": utc_now().isoformat(),
                                          "fetched_at": utc_now().isoformat(), "product_sku": "test-jd"},
                      "ratios": {"zheshang": {"ratio": .25}}, "tv": {"ema20_1h": 3998, "sma20_1d": 3999}}
            views = {}
            for name in ("claude", "codex"):
                analyst = AIAnalyst(settings, monitor.store, "codex", analyst=name)
                data = MarketView(bias_short="bullish", bias_long="bullish", confidence="medium",
                                  p_up_3d=.7, p_down_3d=.1, p_up_3m=.7, p_down_3m=.1,
                                  hard_risk_event=False, hard_risk_note="", drivers=[], upcoming_events=[], summary="浏览器测试判断")
                analyst._run_codex = Mock(return_value=("test notes", [], data))
                analyst.analyze({"xauusd": 4000}, "test", run_id="test-round")
                views[name] = analyst.latest(1)
            cost = {"spread_cny": 0, "sell_fee_rate": .004, "ratio_bank": "zheshang"}
            plans = {name: monitor.build_ai_led_plan(market, v, cost) for name, v in views.items()}
            monitor.store.add_tick(market)
            for name in ("claude", "codex"):
                monitor.short_books[f"{name}:short_ai"].on_tick(market, plans[name])
            monitor.publish_for_web(market, plans["claude"], ai_plans=plans)
            monitor.store.set_state("ai_inputs", {"at": utc_now().isoformat(), "context_chars": 4200,
                "news_count": 18, "max_searches": 0, "macro_at": utc_now().isoformat(),
                "jd_research": {"funds": {"status": "fresh"}, "orders": {"status": "stale"}}})
            now = utc_now()
            monitor.store.set_state("web_macro", {"fetched_at": now.isoformat(),
                "quotes_fetched_at": now.isoformat(), "calendar_fetched_at": now.isoformat(),
                "calendar_refresh_seconds": 60,
                "quotes": {"美元指数": {"value": 100.1, "change_pct": .3},
                    "美国10年期国债收益率": {"value": 4.123, "change_pct": -.2},
                    "美国2年期国债收益率": {"value": 3.456, "change_pct": -.1},
                    "离岸人民币 USD/CNH": {"value": 7.1245, "change_pct": .02}},
                "calendar": [{"time_utc": (now + timedelta(minutes=10)).isoformat(), "country": "US", "tier": 1,
                    "title": "Inflation Rate YoY", "released": False, "forecast": 2.5, "previous": 2.7},
                    {"time_utc": (now - timedelta(hours=1)).isoformat(), "country": "US", "tier": 2,
                    "title": "Retail Sales MoM", "released": True, "actual": 0, "forecast": .3, "previous": .1}]})
            monitor.store.set_state("jin10_flash", [
                {"id": "important", "important": True, "time_bj": "2026-10-16 10:00:00", "text": "重要黄金消息测试"},
                {"id": "normal", "important": False, "time_bj": "2026-10-16 09:59:00", "text": "普通黄金消息测试"}])
            for kind, row in (("funds", {"publishTime": now.timestamp() * 1000,
                "longPositionRatio": 60, "shortPositionRatio": 40, "tradingVolume": 2000000}),
                ("orders", {"time": now.timestamp(), "price": 900,
                    "levels": [{"price": 899, "ol": 3.2, "os": 1.1}]})):
                monitor.store.set_state("jd_research:" + kind, {"fetched_at": now.isoformat(),
                    "raw": {"success": True, "code": "0000", "data": [json.dumps(row)]}})
            class LocalHandler(Handler):
                password = ""
                def log_message(self, *args): pass
            LocalHandler.settings = settings
            server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                    try:
                        page = browser.new_page(viewport={"width": 1280, "height": 900})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(f"http://127.0.0.1:{server.server_port}")
                        page.get_by_role("switch", name="Claude 操盘").wait_for()
                        page.get_by_role("tab", name="操盘对比", exact=True).click()
                        page.get_by_text("同类策略对比", exact=True).wait_for()
                        self.assertEqual(page.locator("#panel-compare tbody tr").count(), 4)
                        self.assertEqual(page.locator("#panel-compare").get_by_text("AI 定投", exact=True).count(), 0)
                        page.get_by_text("3 个对照账户", exact=True).wait_for()
                        page.get_by_role("switch", name="Claude 操盘").click()
                        page.wait_for_function("document.querySelector('#panel-compare [aria-label=\"Claude 操盘\"]').getAttribute('aria-checked') === 'false'")
                        self.assertFalse(control(monitor.store.conn, "claude")["enabled"])
                        self.assertTrue(control(monitor.store.conn, "codex")["enabled"])
                        page.reload()
                        page.get_by_role("switch", name="Claude 操盘").wait_for()
                        self.assertEqual(page.get_by_role("switch", name="Claude 操盘").get_attribute("aria-checked"), "false")
                        page.get_by_role("tab", name="AI", exact=True).click()
                        page.get_by_text("模型已关闭；以上为历史判断，持仓仅保留风控", exact=True).wait_for()
                        page.get_by_text("共同分析数据", exact=True).wait_for()
                        self.assertIn("快讯 18 条", page.locator("#panel-ai").inner_text())
                        self.assertIn("挂单 源数据过期", page.locator("#panel-ai").inner_text())
                        page.get_by_role("switch", name="Claude 操盘").click()
                        page.get_by_text("已重新开启，等待新判断；以上判断不用于开仓", exact=True).wait_for()
                        page.get_by_role("tab", name="行情", exact=True).click()
                        market_panel = page.locator("#panel-market")
                        market_panel.get_by_role("heading", name="宏观指标", exact=True).wait_for()
                        self.assertIn("美国 CPI 年率", market_panel.inner_text())
                        self.assertNotIn("美国零售销售月率", market_panel.inner_text())
                        market_panel.get_by_role("button", name="已公布", exact=True).click()
                        self.assertIn("实际 0", market_panel.inner_text())
                        market_panel.get_by_role("button", name="待公布", exact=True).click()
                        market_panel.get_by_role("button", name="只看重要", exact=True).click()
                        self.assertIn("重要黄金消息测试", market_panel.inner_text())
                        self.assertNotIn("普通黄金消息测试", market_panel.inner_text())
                        self.assertEqual(market_panel.get_by_text("参考数据可用", exact=True).count(), 2)
                        self.assertIn("多单 60.0%", market_panel.inner_text())
                        self.assertIn("价格数据积累中", page.locator("#price-chart").inner_text())
                        self.assertEqual(market_panel.locator(".cluster-row").first.locator(":scope > div").count(), 2)
                        page.evaluate("window.scrollTo(0,0)")
                        page.screenshot(path="/tmp/gold-market-desktop.png", full_page=True)
                        page.set_viewport_size({"width": 390, "height": 844})
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                        page.evaluate("window.scrollTo(0,0)")
                        page.screenshot(path="/tmp/gold-market-mobile.png", full_page=True)
                        page.evaluate("renderMarket({...DATA, macro:{...DATA.macro,quotes_fetched_at:'2000-01-01T00:00:00Z',refresh_errors:{calendar:'TimeoutError'}}})")
                        self.assertIn("更新延迟", market_panel.inner_text())
                        self.assertIn("刷新失败 · 保留旧值", market_panel.inner_text())
                        page.evaluate("renderMarket({...DATA,macro:{},jd_research:{},jin10:[]})")
                        self.assertIn("日历尚未获取", market_panel.inner_text())
                        self.assertIn("暂无可用资金事件", market_panel.inner_text())
                        page.evaluate("renderMarket(DATA)")
                        page.set_viewport_size({"width": 1280, "height": 900})
                        page.get_by_role("tab", name="记录", exact=True).click()
                        page.get_by_role("combobox", name="筛选模型").select_option("claude")
                        page.get_by_role("combobox", name="筛选时间").select_option("7")
                        self.assertGreater(page.get_by_text("查看决策依据", exact=True).count(), 0)
                        page.get_by_role("tab", name="策略", exact=True).click()
                        page.get_by_role("button", name="全部 7 个策略", exact=True).click()
                        page.get_by_role("button", name="对照组", exact=True).click()
                        page.get_by_role("button", name="AI 账户", exact=True).click()
                        page.get_by_role("tab", name="操盘对比", exact=True).click()
                        page.screenshot(path="/tmp/gold-ai-comparison-desktop.png", full_page=True)
                        page.set_viewport_size({"width": 390, "height": 844})
                        page.wait_for_timeout(250)
                        self.assertTrue(page.locator("#panel-compare .compare-mobile").is_visible())
                        self.assertFalse(page.locator("#panel-compare .compare-desktop").is_visible())
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                        page.screenshot(path="/tmp/gold-ai-comparison-mobile.png", full_page=True)
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(3)
                monitor.store.conn.close()


if __name__ == "__main__":
    unittest.main()
