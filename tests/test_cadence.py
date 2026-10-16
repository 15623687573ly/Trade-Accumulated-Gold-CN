"""周期复查按变化启动，统一预算覆盖定时、消息、失败和取消。"""
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch

from monitor.config import Settings
from monitor.store import Store,utc_now
from monitor.ai import AIAnalyst,MarketView
from monitor.cadence import request_periodic,allowed,usage
from monitor.ai_events import read
from monitor.controls import set_enabled


class CadenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.settings=replace(Settings(),db_path=Path(self.temp.name)/'cadence.db',ai_trading_mode='six_account',
            ai_max_runs_per_day=120,ai_urgent_reserve=2,ai_short_review_minutes=0,ai_periodic_min_move_pct=.4,
            ai_review_max_idle_minutes=240,ai_schedule_bj=())
        self.store=Store(self.settings.db_path)
        self.a=AIAnalyst(self.settings,self.store,'codex','codex')
        self.now=utc_now()

    def tearDown(self):
        self.store.conn.close();self.temp.cleanup()

    def view(self,minutes):
        self.store.conn.execute('INSERT INTO ai_views(ts,xauusd,analyst,error) VALUES(?,?,?,NULL)',
            ((self.now-timedelta(minutes=minutes)).isoformat(),4000,'codex'))
        self.store.conn.commit()

    def test_immediate_check_skips_small_change_then_triggers_once(self):
        self.view(1)
        request_periodic(self.settings,self.store,{'codex':self.a},{'xauusd':4004},self.now)
        self.assertFalse(read(self.store.conn,'codex')['pending'])
        request_periodic(self.settings,self.store,{'codex':self.a},{'xauusd':4020},self.now)
        request_periodic(self.settings,self.store,{'codex':self.a},{'xauusd':4020},self.now)
        self.assertEqual(len(read(self.store.conn,'codex')['pending']),1)
        self.assertIsNotNone(self.a.due())

    def test_no_minimum_interval_and_four_hour_fallback(self):
        self.view(1)
        request_periodic(self.settings,self.store,{'codex':self.a},{'xauusd':4050},self.now)
        self.assertEqual(len(read(self.store.conn,'codex')['pending']),1)
        self.store.conn.execute("DELETE FROM state WHERE key='ai_events:codex'")
        self.store.conn.execute('DELETE FROM ai_views');self.store.conn.commit()
        self.view(241)
        request_periodic(self.settings,self.store,{'codex':self.a},{'xauusd':4000},self.now)
        self.assertEqual(len(read(self.store.conn,'codex')['pending']),1)

    def test_normal_budget_reserves_two_urgent_slots_then_stops_everything(self):
        for _ in range(118):
            self.store.conn.execute("INSERT INTO ai_runs(analyst,started_at,status) VALUES(?,?,'failed')",('codex',self.now.isoformat()))
        self.store.conn.commit()
        self.a.request_refresh('routine',0,event_id='periodic:test')
        self.assertIsNone(self.a.due())
        self.assertFalse(allowed(self.settings,self.store.conn,'codex',self.now))
        self.a.request_refresh('actual release',0,event_id='calendar:test')
        self.assertIsNotNone(self.a.due())
        for _ in range(2):
            self.store.conn.execute("INSERT INTO ai_runs(analyst,started_at,status) VALUES(?,?,'cancelled')",('codex',self.now.isoformat()))
        self.store.conn.commit()
        self.assertIsNone(self.a.due())
        self.assertEqual(len(read(self.store.conn,'codex')['pending']),2)
        self.assertTrue(allowed(self.settings,self.store.conn,'codex',self.now+timedelta(days=1),['calendar:test']))

    def test_counts_failure_and_cancel_and_never_double_counts_matching_view(self):
        self.a._run_codex=Mock(side_effect=RuntimeError('offline'))
        self.a.analyze({'xauusd':4000},'test')
        self.assertEqual(usage(self.store.conn,'codex',utc_now()),1)
        def cancelled(*args):
            set_enabled(self.store.conn,'codex',False)
            raise RuntimeError('cancelled')
        self.a._run_codex=cancelled
        self.a.analyze({'xauusd':4000},'test')
        self.assertEqual(usage(self.store.conn,'codex',utc_now()),2)
        self.assertEqual(self.store.conn.execute("SELECT COUNT(*) FROM ai_runs WHERE status='cancelled'").fetchone()[0],1)

    def test_budget_day_uses_beijing_midnight_and_manual_override(self):
        now=datetime(2026,10,16,16,1,tzinfo=timezone.utc)
        self.store.conn.execute("INSERT INTO ai_runs(analyst,started_at,status) VALUES(?,?,'completed')",('codex',(now-timedelta(minutes=2)).isoformat()))
        self.store.conn.commit()
        self.assertEqual(usage(self.store.conn,'codex',now),0)
        self.assertTrue(allowed(replace(self.settings,ai_max_runs_per_day=1),self.store.conn,'codex',now,manual=True))


if __name__=='__main__':unittest.main()
