import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).parent/'hellowatt_daily'
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
c=load('collecteur');s=load('run')
NOW=datetime(2026,10,18,8,tzinfo=timezone.utc).timestamp()

class HttpTests(unittest.TestCase):
    def client(self, code, headers=None):
        client=c.Client.__new__(c.Client)
        client.session=SimpleNamespace(request=Mock(return_value=SimpleNamespace(status_code=code,headers=headers or {})))
        client._network_errors=(TimeoutError,ConnectionError)
        client._last_request=None
        return client
    def test_retry_after_delta_and_http_date(self):
        self.assertEqual(c.retry_after_seconds('7200',NOW),7200)
        self.assertEqual(c.retry_after_seconds('Sun, 18 Oct 2026 10:00:00 GMT',NOW),7200)
        self.assertEqual(c.retry_after_seconds('Sun, 18 Oct 2026 07:00:00 GMT',NOW),0)
        for x in [None,'bad','-2','nan','inf']:
            self.assertEqual(c.retry_after_seconds(x,NOW),3600)
    def test_429_stops_after_one_request_and_keeps_retry_after(self):
        client=self.client(429,{'Retry-After':'7200'})
        with patch.object(c.time,'time',return_value=NOW):
            with self.assertRaises(c.TemporaryError) as caught:client.request('GET','/accounts/login/')
        self.assertEqual(caught.exception.next_allowed_at,NOW+7200)
        self.assertEqual(client.session.request.call_count,1)
        self.assertNotIn('password',str(caught.exception))
    def test_auth_failure_not_automatically_retried(self):
        for code in (401,403,404):
            with self.assertRaises(c.CollectError) as caught:self.client(code).request('POST','/accounts/login/')
            self.assertNotIsInstance(caught.exception,c.TemporaryError)
    def test_server_errors_and_network_timeout_are_transient(self):
        for code in (408,500,502,503,504):
            with self.assertRaises(c.TemporaryError):self.client(code).request('GET','/test')
        client=self.client(200);client.session.request.side_effect=TimeoutError('sensitive detail')
        with self.assertRaises(c.TemporaryError) as caught:client.request('GET','/test')
        self.assertNotIn('sensitive detail',str(caught.exception))
    def test_pacing(self):
        client=self.client(200);client._last_request=100
        with patch.object(c.time,'monotonic',return_value=100.2),patch.object(c.time,'sleep') as sleep:
            client.request('GET','/test')
        self.assertAlmostEqual(sleep.call_args.args[0],.8)
    def test_failure_status_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(c.os.environ,{'HELLOWATT_STATUS_FILE':tmp+'/status.json'}):
            c.write_failure_status(c.TemporaryError('password secret',NOW+7200))
            data=json.loads(Path(tmp+'/status.json').read_text())
            self.assertEqual(data,{'retryable':True,'next_allowed_at':NOW+7200})

class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=NOW
        (self.root/'options.json').write_text(json.dumps({'email':'test@example.invalid','password':'fake','mqtt_host':'example.invalid','run_on_start':True}))
        self.calls=[]
    def execute(self,code=0,delay=None,timeout=False):
        def call(command,**kwargs):
            self.calls.append(command)
            if delay is not None:Path(kwargs['env']['HELLOWATT_STATUS_FILE']).write_text(json.dumps({'next_allowed_at':self.now+delay}))
            if timeout:raise subprocess.TimeoutExpired(command,600)
            return SimpleNamespace(returncode=code)
        return call
    def run_collector(self,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return s.run(self.root,ROOT,startup=kwargs.pop('startup',False),clock=lambda:self.now,**kwargs)
    def state(self):return json.loads((self.root/'scheduler_state.json').read_text())
    def test_success_only_once_a_day(self):
        self.run_collector(execute=self.execute())
        self.run_collector(execute=self.execute(),startup=True)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.state()['last_success_date'],'2026-10-18')
    def test_failure_can_retry_later_and_success_is_persisted(self):
        self.run_collector(execute=self.execute(75,7200))
        self.now+=3600;self.run_collector(execute=self.execute(),startup=True)
        self.assertEqual(len(self.calls),1)
        self.now+=3600;self.run_collector(execute=self.execute())
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.state()['last_success_date'],'2026-10-18')
    def test_max_four_automatic_attempts(self):
        for index in range(4):
            self.run_collector(execute=self.execute(75))
            self.now=self.state()['next_allowed_at']
        # Four backoffs have crossed midnight; check cap on the failed date.
        state=self.state();check=datetime(2026,10,18,23,59,tzinfo=s.TZ).timestamp()
        state['next_allowed_at']=0
        self.assertFalse(s.due(state,check)[0])
        self.assertEqual(len(self.calls),4)
    def test_long_server_pause_survives_midnight_and_manual_retry(self):
        self.run_collector(execute=self.execute(75,172800))
        self.now+=86400
        opts=json.loads((self.root/'options.json').read_text());opts['retry_once']='new-token';(self.root/'options.json').write_text(json.dumps(opts))
        self.run_collector(execute=self.execute(),startup=True)
        self.assertEqual(len(self.calls),1)
    def test_permanent_failure_does_not_repeat(self):
        self.run_collector(execute=self.execute(1));self.now+=3601
        self.run_collector(execute=self.execute())
        self.assertEqual(len(self.calls),1)
    def test_legacy_failed_attempt_does_not_block_all_day(self):
        (self.root/'last_attempt.txt').write_text('2026-10-18')
        (self.root/'last_run.json').write_text(json.dumps({'date':'2026-10-18','success':False}))
        self.run_collector(execute=self.execute());self.assertEqual(len(self.calls),1)
    def test_legacy_success_is_respected(self):
        (self.root/'last_run.json').write_text(json.dumps({'date':'2026-10-18','success':True}))
        self.run_collector(execute=self.execute());self.assertEqual(len(self.calls),0)
    def test_no_scheduled_login_before_eight(self):
        self.now=datetime(2026,10,18,7,59,tzinfo=s.TZ).timestamp()
        self.run_collector(execute=self.execute());self.assertEqual(len(self.calls),0)
    def test_timeout_gets_bounded_retry(self):
        self.run_collector(execute=self.execute(timeout=True));self.assertEqual(self.state()['terminal_failure'],False)
        self.assertEqual(self.state()['next_allowed_at'],self.now+3600)
    def test_huge_pause_is_not_shortened_by_log_formatting(self):
        self.run_collector(execute=self.execute(75,1e100));self.assertEqual(self.state()['next_allowed_at'],1e100)
    def test_lock_prevents_parallel_collectors(self):
        import fcntl
        with (self.root/'collect.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.run_collector(execute=self.execute())
        self.assertEqual(len(self.calls),0)

if __name__=='__main__':unittest.main()
