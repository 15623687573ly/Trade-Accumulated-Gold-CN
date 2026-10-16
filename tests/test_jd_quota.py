"""Offline quota, cache and error classification checks; never call JD or a model."""
import io
import json
import tempfile
import time
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from monitor.store import Store
from monitor.jd_research import snapshot, public_entry, quota_view, ProviderError
from monitor.web import jd_reference


class JDQuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'jd.db'
        self.store=Store(self.path);self.now=datetime(2026,10,16,2,tzinfo=timezone.utc);self.clock=self.now

    def tearDown(self): self.store.conn.close();self.tmp.cleanup()

    def response(self,endpoint,key):
        stamp=self.clock.timestamp()
        row=({'publishTime':stamp*1000,'longPositionRatio':60,'shortPositionRatio':40,'tradingVolume':100} if endpoint=='bomb' else
             {'time':stamp,'price':4000,'levels':[{'price':3990,'ol':30,'os':20}]})
        return {'success':True,'code':'0000','data':[json.dumps(row)]}

    def count(self): return self.store.conn.execute('SELECT COUNT(*) FROM jd_research_requests').fetchone()[0]

    def test_local_cap_shared_by_both_endpoints_and_persists_across_restart(self):
        with patch('monitor.jd_research.fetch',side_effect=self.response) as fetch:
            snapshot(self.store,'test-key',self.now,daily_cap=3)
            self.clock=self.now+timedelta(minutes=16)
            result=snapshot(self.store,'test-key',self.clock,daily_cap=3)
            self.assertEqual(fetch.call_count,3);self.assertEqual(result['quota']['used_today'],3)
            self.assertEqual(result['quota']['status'],'budget_exhausted')
            another=Store(self.path)
            try: snapshot(another,'test-key',self.now+timedelta(hours=2),daily_cap=3)
            finally: another.conn.close()
            self.assertEqual(fetch.call_count,3)
            self.clock=self.now+timedelta(days=1)
            result=snapshot(self.store,'test-key',self.clock,daily_cap=3)
            self.assertEqual(fetch.call_count,5);self.assertEqual(result['quota']['used_today'],2)

    def test_failure_counts_and_zero_cap_does_not_dispatch(self):
        with patch('monitor.jd_research.fetch',side_effect=TimeoutError) as fetch:
            result=snapshot(self.store,'test-key',self.now,daily_cap=1)
            self.assertEqual(fetch.call_count,1);self.assertEqual(self.count(),1)
            self.assertEqual(result['quota']['status'],'budget_exhausted')
            snapshot(self.store,'test-key',self.now+timedelta(days=1),daily_cap=0)
            self.assertEqual(fetch.call_count,1)

    def test_provider_daily_quota_stops_both_interfaces_for_24_hours_not_midnight(self):
        raw={'success':False,'code':'429','message':'今日调用额度已达上限(50次) test-secret-key'}
        with patch('monitor.jd_research.fetch',return_value=raw) as fetch:
            first=snapshot(self.store,'test-secret-key',self.now)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(first['funds']['status'],'quota_exhausted');self.assertEqual(first['orders']['status'],'quota_exhausted')
            snapshot(self.store,'test-secret-key',self.now+timedelta(minutes=16))
            snapshot(self.store,'test-secret-key',self.now+timedelta(hours=15))
            self.assertEqual(fetch.call_count,1);self.assertEqual(self.count(),1)
            values=''.join(r[0] for r in self.store.conn.execute('SELECT value FROM state'))
            self.assertNotIn('test-secret-key',values+json.dumps(first))
        self.clock=self.now+timedelta(hours=25)
        with patch('monitor.jd_research.fetch',side_effect=self.response) as fetch:
            result=snapshot(self.store,'test-secret-key',self.clock)
            self.assertEqual(fetch.call_count,2);self.assertEqual(result['quota']['status'],'available')
            self.assertEqual(result['funds']['status'],'fresh')

    def test_http_429_classified_without_saving_response_body(self):
        body=json.dumps({'message':'今日额度已达上限 key=test-secret-key'}).encode()
        error=urllib.error.HTTPError('https://test',429,'quota',{},io.BytesIO(body))
        with patch('monitor.jd_research.urllib.request.urlopen',side_effect=error) as fetch:
            result=snapshot(self.store,'test-secret-key',self.now)
        self.assertEqual(fetch.call_count,1);self.assertEqual(result['quota']['status'],'quota_exhausted')
        self.assertNotIn('test-secret-key',json.dumps(result))
        self.assertEqual(self.store.conn.execute('SELECT error_type FROM jd_research_requests').fetchone()[0],'ProviderDailyQuota')

    def test_generic_rate_limit_retries_after_15_minutes(self):
        with patch('monitor.jd_research.fetch',return_value={'success':False,'code':429,'message':'too many requests'}) as fetch:
            first=snapshot(self.store,'key',self.now)
            self.assertEqual(first['quota']['status'],'rate_limited')
            snapshot(self.store,'key',self.now+timedelta(minutes=14))
            self.assertEqual(fetch.call_count,1)
        self.clock=self.now+timedelta(minutes=16)
        with patch('monitor.jd_research.fetch',side_effect=self.response) as fetch:
            self.assertEqual(snapshot(self.store,'key',self.clock)['orders']['status'],'fresh')
            self.assertEqual(fetch.call_count,2)

    def test_error_never_becomes_source_stale_when_no_successful_cache(self):
        with patch('monitor.jd_research.fetch',side_effect=TimeoutError): snapshot(self.store,'key',self.now)
        result=public_entry(self.store.conn,'funds',self.now+timedelta(hours=2))
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['fetched_at']);self.assertIsNotNone(result['attempted_at'])
        page=jd_reference(self.store.conn)
        self.assertEqual(page['funds']['status'],'unavailable')

    def test_valid_old_cache_survives_failed_refresh_with_separate_error_and_success_time(self):
        with patch('monitor.jd_research.fetch',side_effect=self.response): first=snapshot(self.store,'key',self.now)
        with patch('monitor.jd_research.fetch',side_effect=TimeoutError):
            second=snapshot(self.store,'key',self.now+timedelta(minutes=16))
        self.assertEqual(second['funds']['status'],'fresh')
        self.assertEqual(second['funds']['refresh_status'],'unavailable')
        self.assertEqual(second['funds']['fetched_at'],first['funds']['fetched_at'])
        self.assertNotEqual(second['funds']['attempted_at'],first['funds']['attempted_at'])
        late=self.now+timedelta(minutes=70)
        fund=public_entry(self.store.conn,'funds',late)
        order=public_entry(self.store.conn,'orders',late)
        self.assertEqual(fund['status'],'cache_stale');self.assertNotIn('long_pct',fund)
        self.assertEqual(order['status'],'stale');self.assertNotIn('reference_price',order)

    def test_provider_empty_data_is_not_fetch_failure(self):
        with patch('monitor.jd_research.fetch',return_value={'success':True,'code':'0000','data':[]}): result=snapshot(self.store,'key',self.now)
        self.assertEqual(result['funds']['status'],'no_data')
        self.assertIsNotNone(result['funds']['fetched_at'])

    def test_concurrent_snapshots_share_reservations_and_cache(self):
        def fetch(endpoint,key): time.sleep(.03);return self.response(endpoint,key)
        def run(_):
            store=Store(self.path)
            try: return snapshot(store,'key',self.now,daily_cap=2)
            finally: store.conn.close()
        with patch('monitor.jd_research.fetch',side_effect=fetch) as request:
            with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run,range(2)))
            self.assertEqual(request.call_count,2)
        self.assertEqual(self.count(),2)
        self.assertEqual({r[0] for r in self.store.conn.execute('SELECT kind FROM jd_research_requests')},{'funds','orders'})

    def test_small_clock_skew_does_not_bypass_cache(self):
        with patch('monitor.jd_research.fetch',side_effect=self.response) as fetch:
            snapshot(self.store,'key',self.now)
            snapshot(self.store,'key',self.now-timedelta(milliseconds=1))
        self.assertEqual(fetch.call_count,2)


if __name__=='__main__':unittest.main()
