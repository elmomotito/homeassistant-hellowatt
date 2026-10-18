from pathlib import Path
import importlib.util, unittest
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('c',str(Path(__file__).parent/'hellowatt_daily/collecteur.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class Tests(unittest.TestCase):
 def test_unique(self):
  for payload in [[{'id':123}],{'results':[{'id':'123'}]},{'homes':[{'id':123}]}]:self.assertEqual(c.select_home(payload),'123')
 def test_existing(self):self.assertEqual(c.select_home([{'id':1},{'id':2}],['2']),'2')
 def test_errors(self):
  for data in [[],[{'id':1},{'id':2}],{'unexpected':3},[{'id':True}],[{'id':'../3'}],{'results':[{'id':1}],'next':'/page2'}]:
   with self.assertRaises(c.CollectError):c.select_home(data)
 def test_http(self):
  client=c.Client.__new__(c.Client);client.request=Mock(return_value=Mock(status_code=200,json=lambda:[{'id':123}]))
  self.assertEqual(client.discover_home(),'123');self.assertEqual(client.request.call_args.args,('GET','/api/homes'))
 def test_redirect(self):
  client=c.Client.__new__(c.Client);client.request=Mock(side_effect=[Mock(status_code=302,headers={'Location':'https://other.invalid/'}),Mock(status_code=200)])
  with self.assertRaises(c.CollectError):client.discover_home()
  self.assertEqual(client.request.call_count,1)
if __name__=='__main__':unittest.main()
