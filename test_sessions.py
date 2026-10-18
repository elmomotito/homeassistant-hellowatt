import tempfile
import json
import stat
import unittest
from pathlib import Path
from unittest.mock import Mock
from test_retries import c

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'session.json'
    def client(self):
        client=c.Client();self.addCleanup(client.close);return client
    def seed(self, client):
        client.session_path=self.path;client.session_owner='owner';client.authenticated=True
        client.session.cookies.set('sessionid','FAKE',domain='www.hellowatt.fr',path='/',secure=True)
        client.session.cookies.set('csrftoken','CSRF_FAKE',domain='.hellowatt.fr',path='/')
        client.save_session()
    def test_private_roundtrip_preserves_cookie_scope(self):
        a=self.client();self.seed(a)
        b=self.client();b.session_path=self.path;b.session_owner='owner'
        self.assertTrue(b.load_session())
        self.assertEqual(len(b.session.cookies),2)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        self.assertNotIn('password',self.path.read_text())
    def test_wrong_owner_and_expired_cookie_rejected(self):
        a=self.client();self.seed(a);a.session_owner='different'
        self.assertFalse(a.load_session())
        data=json.loads(self.path.read_text());data['cookies'][0]['expires']=1
        self.path.write_text(json.dumps(data));a.session_owner='owner'
        self.assertFalse(a.load_session())
    def test_invalid_file_and_external_domain_rejected(self):
        a=self.client();a.session_path=self.path;a.session_owner='owner'
        self.path.write_text('broken');self.assertFalse(a.load_session())
        self.path.write_text(json.dumps({'owner':'owner','cookies':[{'name':'sessionid','value':'fake','domain':'attacker.invalid'}]}))
        self.assertFalse(a.load_session())
    def test_valid_session_skips_login_and_keeps_explicit_home(self):
        a=self.client();a.load_session=Mock(return_value=True)
        a.discover_home=Mock(return_value='123');a.login=Mock();a.save_session=Mock()
        self.assertEqual(a.authenticate('a','b',self.path,['123'],'123'),'123')
        a.login.assert_not_called();a.discover_home.assert_called_once()
    def test_expired_session_logs_in_once(self):
        a=self.client();a.load_session=Mock(return_value=True)
        a.discover_home=Mock(side_effect=[c.SessionExpired('expired'),'123'])
        a.login=Mock();a.save_session=Mock()
        self.assertEqual(a.authenticate('a','b',self.path),'123');a.login.assert_called_once_with('a','b')
    def test_429_and_403_never_trigger_reconnection(self):
        for error in [c.TemporaryError('429',100),c.CollectError('403')]:
            a=self.client();a.load_session=Mock(return_value=True)
            a.discover_home=Mock(side_effect=error);a.login=Mock()
            with self.assertRaises(type(error)):a.authenticate('a','b',self.path)
            a.login.assert_not_called()
    def test_mid_collection_expiry_reconnects_at_most_once(self):
        a=self.client();a.session_path=self.path;a.session_owner='owner'
        a.reconnected=False;a.credentials=('a','b');a.login=Mock();a.save_session=Mock()
        a._month=Mock(side_effect=[c.SessionExpired('expired'),{'values':[]},c.SessionExpired('expired')])
        self.assertEqual(a.month('123',None),{'values':[]})
        with self.assertRaises(c.SessionExpired):a.month('123',None)
        a.login.assert_called_once_with('a','b')
