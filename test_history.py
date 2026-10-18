import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', str(Path(__file__).parent/'hellowatt_daily/collecteur.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        c.ensure_schema(self.db)

    def tearDown(self):
        self.db.close()

    def test_migration_preserves_money(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE days(home TEXT, day TEXT, cost TEXT, subscription TEXT, injection TEXT, PRIMARY KEY(home,day))')
        db.execute("INSERT INTO days VALUES ('1','2026-09-01','2','0.7','0')")
        c.ensure_schema(db)
        c.ensure_schema(db)
        self.assertEqual(db.execute('SELECT cost,injection,consumption_kwh FROM days').fetchone(), ('2', '0', None))
        db.close()

    def test_energy_fields_and_dates(self):
        base = {'datetime': '2026-03-29T00:00:00+01:00', 'eurosDetailed': {'HP': 2, 'subscription': .8},
                'kwhDetailed': {'HP': 10, 'HC': 2}, 'injectionValueEur': 0, 'injectionValueKwh': 0,
                'solarProductionValueKwh': 100, 'negativeKwhDetailed': {'injection': 999}}
        rows = c.normalize({'values': [base]}, date(2026, 3, 30))
        self.assertEqual(rows[0], ('2026-03-29', '2.8', '0.8', '0', '12', '0', '100', None, {'eur': {'HP':'2'}, 'kwh': {'HP':'10','HC':'2'}}))
        self.assertEqual(c.normalize({'values': [base]}, date(2026, 3, 29)), [])
        base['datetime'] = '2025-12-31T00:00:00+01:00'
        self.assertEqual(c.normalize({'values': [base]}, date(2026, 3, 30)), [])

    def test_corrections_null_and_zero(self):
        c.save(self.db, '1', [('2026-01-01', '2', '.5', '1', '12', '3')])
        c.save(self.db, '1', [('2026-01-01', None, None, '0', None, '0')])
        state = c.summary(self.db, '1', '2026-01')
        self.assertEqual((state['electricite'], state['consommation_kwh'], state['injection_kwh']), (2, 12, 0))
        c.save(self.db, '1', [('2026-01-01', '3', None, None, '15', None)])
        self.assertEqual(c.summary(self.db, '1', '2026-01')['consommation_kwh'], 15)
        self.assertEqual(self.db.execute('SELECT count(*) FROM days').fetchone()[0], 1)

    def test_year_rollover_preserves_archive(self):
        c.save(self.db, '1', [('2026-01-01', '2', '.5', '1', '12', '3'),
                               ('2026-12-31', '4', '.5', '0', '20', '0')])
        before = c.archives(self.db, '1', date(2027, 1, 1))['2026']
        c.save(self.db, '1', [('2027-01-01', '5', '.5', '2', '25', '4')])
        after = c.archives(self.db, '1', date(2027, 1, 2))
        self.assertEqual(after['2026'], before)
        self.assertEqual(len(before['jours']), 365)
        self.assertEqual(len(before['mois']), 12)
        self.assertEqual(before['consommation_kwh'], 32)
        self.assertEqual(after['2027']['electricite'], 5)
        self.assertEqual(c.daily_details(self.db, '1', date(2027, 1, 1))['electricite_veille'], 4)

    def test_missing_days_and_leap_year(self):
        history = c.archives(self.db, '1', date(2029, 1, 1))
        self.assertEqual(len(history['2028']['jours']), 366)
        self.assertIsNone(history['2028']['mois'][0]['consommation_kwh'])
        self.assertIsNone(history['2028']['jours'][0]['injection'])
        self.assertEqual(history['2029']['jours'], [])

    def test_fetch_plan_resume_and_rotation(self):
        first = c.collection_plan(self.db, '1', date(2026, 9, 12))
        self.assertEqual(len(first), 9)
        self.assertEqual(first[:2], [date(2026, 9, 1), date(2026, 8, 1)])
        for month in first:
            self.db.execute('INSERT INTO fetched_months_v061 VALUES (?,?,?)', ('1', month.isoformat()[:7], '2026-09-12'))
        follow = c.collection_plan(self.db, '1', date(2026, 9, 13))
        self.assertEqual(len(follow), 3)
        self.assertEqual(follow[-1], date(2026, 1, 1))
        self.db.execute("UPDATE fetched_months_v061 SET fetched_on='2026-09-13' WHERE month='2026-01'")
        self.assertEqual(c.collection_plan(self.db, '1', date(2026, 9, 14))[-1], date(2026, 2, 1))
        self.assertLessEqual(len(c.collection_plan(self.db, '2', date(2029, 1, 1))), 12)
        self.assertIn(date(2027, 1, 1), c.collection_plan(self.db, '1', date(2027, 1, 1)))

    def test_mqtt_units_archives_and_compatibility(self):
        modules = {name: types.ModuleType(name) for name in ('paho', 'paho.mqtt', 'paho.mqtt.publish')}
        captured = []
        modules['paho.mqtt.publish'].multiple = lambda messages, **kwargs: captured.extend(messages)
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'MQTT_HOST': 'test', 'MQTT_USER': ''}):
            c.publish({}, '1', c.archives(self.db, '1', date(2027, 1, 1)))
        configs = {json.loads(m['payload'])['unique_id']: json.loads(m['payload'])
                   for m in captured if m['topic'].endswith('/config')}
        self.assertEqual(len(configs), 20)
        self.assertEqual(configs['hellowatt_1_electricite']['unit_of_measurement'], 'EUR')
        self.assertEqual(configs['hellowatt_1_consommation_kwh']['unit_of_measurement'], 'kWh')
        self.assertIn('hellowatt_1_historique_2026', configs)
        self.assertIn('hellowatt_1_historique_2027', configs)
        self.assertTrue(all(m['retain'] for m in captured))

    def test_partial_run_checkpoint_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'history.sqlite'
            with sqlite3.connect(path) as db:
                c.save(db, '1', [('2026-01-01', '2', '.5', '1')])
            class FakeClient:
                def login(self, *args): pass
                def close(self): pass
                def month(self, home, month):
                    if month.month == 1:
                        return {'values': [], 'isFetchOngoing': False}
                    raise c.CollectError('HTTP 500')
            with patch.object(c, 'Client', FakeClient), patch.object(c, 'collection_plan', return_value=[date(2026,1,1), date(2026,2,1)]), \
                 patch.dict(os.environ, {'HELLOWATT_HOME_ID':'1','HELLOWATT_EMAIL':'fake','HELLOWATT_PASSWORD':'fake'}), \
                 patch.object(sys, 'argv', ['collector','--db',str(path)]):
                with self.assertRaises(c.CollectError): c.main()
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT month FROM fetched_months_v061').fetchall(), [('2026-01',)])
                self.assertEqual(db.execute('SELECT cost FROM days').fetchone()[0], '2')
            with sqlite3.connect(str(path)+'.avant-0.5.0.bak') as backup:
                self.assertEqual(backup.execute('SELECT cost FROM days').fetchone()[0], '2')


if __name__ == '__main__':
    unittest.main()
