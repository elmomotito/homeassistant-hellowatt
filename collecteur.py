"""Collecte ponctuelle Hello Watt. Identifiants via variables d'environnement.
Sans --publish : sauvegarde locale uniquement. --import permet un essai hors ligne.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = 'https://www.hellowatt.fr'
TZ = ZoneInfo('Europe/Paris')
HISTORY_START = date(2026, 1, 1)
METRICS = ('electricite', 'abonnement', 'injection', 'consommation_kwh', 'injection_kwh')
COLUMNS = 'day,cost,subscription,injection,consumption_kwh,injection_kwh'


class CollectError(RuntimeError):
    """Message contrôlé localement, sans contenu reçu du serveur."""


def error_message(exc):
    if isinstance(exc, CollectError):
        return 'Collecte échouée : ' + str(exc)
    return 'Collecte échouée (' + type(exc).__name__ + ').'


def amount(v):
    n = Decimal(str(v))
    if isinstance(v, bool) or not n.is_finite():
        raise ValueError('Montant invalide')
    return str(n)


def normalize(payload, today):
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get('values'), list):
        raise ValueError('Réponse de consommation inattendue')
    result, seen = [], set()
    for row in payload['values']:
        dt = datetime.fromisoformat(row['datetime'].replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Date sans fuseau horaire')
        day = dt.astimezone(TZ).date()
        if day >= today or day < HISTORY_START:
            continue
        if day in seen:
            raise ValueError('Plusieurs mesures pour une même journée')
        seen.add(day)
        detail = row.get('eurosDetailed') or {}
        cost = subscription = None
        if detail:
            if 'subscription' not in detail:
                raise ValueError('Abonnement absent : calcul suspendu')
            subscription = amount(detail['subscription'])
            cost = str(sum((Decimal(amount(v)) for v in detail.values()), Decimal(0)))
        injection = row.get('injectionValueEur')
        kwh = row.get('kwhDetailed') or {}
        consumption = str(sum((Decimal(amount(v)) for v in kwh.values()), Decimal(0))) if kwh else None
        exported = row.get('injectionValueKwh')
        result.append((day.isoformat(), cost, subscription,
                       amount(injection) if injection is not None else None,
                       consumption, amount(exported) if exported is not None else None))
    return result


class Client:
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'HelloWatt-HA-personal-collector/0.1'

    def request(self, method, path, **kwargs):
        # Ne jamais suivre une redirection vers une autre origine avec des identifiants.
        response = self.session.request(method, BASE + path, timeout=(10, 45),
                                        allow_redirects=False, **kwargs)
        if response.status_code >= 400:
            raise CollectError(f'Hello Watt HTTP {response.status_code}; aucune nouvelle tentative automatique')
        return response

    def login(self, email, password):
        print('Étape 1/5 : préparation de la connexion Hello Watt.', flush=True)
        response = self.request('GET', '/accounts/login/')
        csrf = next((c.value for c in self.session.cookies if c.name == 'csrftoken'), None)
        if not csrf:
            raise CollectError(f'Cookie CSRF absent après ouverture du formulaire (HTTP {response.status_code}).')
        print('Étape 2/5 : authentification Hello Watt.', flush=True)
        response = self.request('POST', '/accounts/login/',
            data={'login': email, 'password': password},
            headers={'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest',
                     'Origin': BASE, 'Referer': BASE + '/accounts/login/'})
        if response.status_code != 200:
            raise CollectError(f'Réponse de connexion inattendue (HTTP {response.status_code}).')
        data = response.json()
        # La réponse de login peut contenir le mot de passe : ne pas la conserver ni la journaliser.
        if data.get('location') != '/login/redirect/' or not any(
                c.name == 'sessionid' for c in self.session.cookies):
            raise CollectError('Connexion non confirmée; vérifier les identifiants ou le formulaire')

    def month(self, home_id, start):
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        response = self.request('GET', f'/api/homes/{home_id}/sge_measures/conso_daily',
            params={'startDate': datetime.combine(start, datetime.min.time(), TZ).isoformat(),
                    'endDate': datetime.combine(end, datetime.min.time(), TZ).isoformat()},
            headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
        if response.status_code != 200:
            raise CollectError(f'Session non acceptée pour les données (HTTP {response.status_code}).')
        return response.json()

    def close(self):
        self.session.cookies.clear()
        self.session.close()


def ensure_schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS days (home TEXT, day TEXT, cost TEXT, subscription TEXT, injection TEXT, PRIMARY KEY(home,day))')
    columns = {row[1] for row in db.execute('PRAGMA table_info(days)')}
    for column in ('consumption_kwh', 'injection_kwh'):
        if column not in columns:
            db.execute(f'ALTER TABLE days ADD COLUMN {column} TEXT')
    db.execute('CREATE TABLE IF NOT EXISTS fetched_months (home TEXT, month TEXT, fetched_on TEXT, PRIMARY KEY(home,month))')


def save(db, home_id, rows):
    ensure_schema(db)
    for row in rows:
        if len(row) == 4:  # Compatibilité des imports monétaires antérieurs.
            row = (*row, None, None)
        db.execute("""INSERT INTO days (home,day,cost,subscription,injection,consumption_kwh,injection_kwh)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(home,day) DO UPDATE SET
            cost=COALESCE(excluded.cost,days.cost),
            subscription=COALESCE(excluded.subscription,days.subscription),
            injection=COALESCE(excluded.injection,days.injection),
            consumption_kwh=COALESCE(excluded.consumption_kwh,days.consumption_kwh),
            injection_kwh=COALESCE(excluded.injection_kwh,days.injection_kwh)""",
            (home_id, *row))


def aggregate(rows):
    output = {}
    for index, name in enumerate(METRICS, 1):
        valid = [(row[0], Decimal(row[index])) for row in rows if row[index] is not None]
        precision = 3 if name.endswith('_kwh') else 2
        output[name] = round(float(sum((v for _, v in valid), Decimal(0))), precision) if valid else None
        output[name+'_derniere_date'] = valid[-1][0] if valid else None
        output[name+'_jours'] = len(valid)
    return output


def summary(db, home_id, month):
    rows = db.execute(f'SELECT {COLUMNS} FROM days WHERE home=? AND day LIKE ? ORDER BY day',
                      (home_id, month+'-%')).fetchall()
    return {'mois': month, 'devise': 'EUR', **aggregate(rows)}


def dated_days(rows, start, end):
    by_day = {row[0]: row[1:] for row in rows}
    result = []
    for i in range(max(0, (end-start).days)):
        day = (start+timedelta(days=i)).isoformat()
        values = by_day.get(day, (None,)*len(METRICS))
        result.append({'date': day, **{key: float(Decimal(value)) if value is not None else None
                                      for key, value in zip(METRICS, values)}})
    return result


def daily_details(db, home_id, today):
    start = today.replace(day=1)
    rows = db.execute(f'SELECT {COLUMNS} FROM days WHERE home=? AND day>=? AND day<? ORDER BY day',
                      (home_id, start.isoformat(), today.isoformat())).fetchall()
    yesterday = today-timedelta(days=1)
    previous = db.execute(f'SELECT {COLUMNS} FROM days WHERE home=? AND day=?',
                          (home_id, yesterday.isoformat())).fetchall()
    amounts = aggregate(previous)
    return {'jours': dated_days(rows, start, today), 'date_veille': yesterday.isoformat(),
            **{key+'_veille': amounts[key] for key in METRICS if key != 'abonnement'}}


def month_starts(today):
    current = HISTORY_START
    while current <= today.replace(day=1):
        yield current
        current = (current.replace(day=28)+timedelta(days=4)).replace(day=1)


def collection_plan(db, home_id, today):
    months = list(month_starts(today))
    fetched = dict(db.execute('SELECT month,fetched_on FROM fetched_months WHERE home=?', (home_id,)))
    recent = list(reversed(months[-2:]))
    missing = [m for m in months if m not in recent and m.isoformat()[:7] not in fetched]
    # Douze mois maximum par passage, reprise automatique des mois restants.
    plan = (recent+missing)[:12]
    if not missing:
        old = [m for m in months if m not in recent]
        if old:
            plan.append(min(old, key=lambda m: (fetched.get(m.isoformat()[:7], ''), m)))
    return plan


def archives(db, home_id, today):
    result = {}
    fetched = dict(db.execute('SELECT month,fetched_on FROM fetched_months WHERE home=?', (home_id,)))
    for year in range(HISTORY_START.year, today.year+1):
        start, end = date(year, 1, 1), min(date(year+1, 1, 1), today)
        rows = db.execute(f'SELECT {COLUMNS} FROM days WHERE home=? AND day>=? AND day<? ORDER BY day',
                          (home_id, start.isoformat(), end.isoformat())).fetchall()
        months = []
        for number in range(1, 13):
            first = date(year, number, 1)
            if first > today.replace(day=1):
                break
            key = first.isoformat()[:7]
            monthly = [r for r in rows if r[0].startswith(key+'-')]
            limit = min((first.replace(day=28)+timedelta(days=4)).replace(day=1), today)
            months.append({'mois': key, 'date': first.isoformat(),
                           'jours_attendus': max(0, (limit-first).days),
                           'recupere_le': fetched.get(key), **aggregate(monthly)})
        result[str(year)] = {'annee': str(year), 'devise': 'EUR', 'unite_energie': 'kWh',
                             'jours_attendus': (end-start).days,
                             'jours': dated_days(rows, start, end), 'mois': months,
                             'jours_enregistres': sum(any(v is not None for v in r[1:]) for r in rows),
                             'mois_recuperes': sum(m['recupere_le'] is not None for m in months),
                             'mois_attendus': len(months), **aggregate(rows)}
    return result


def publish(state, home_id, history=None):
    import paho.mqtt.publish as mqtt
    host = os.environ['MQTT_HOST']
    prefix = 'hellowatt/' + home_id
    device = {'identifiers': ['hellowatt_'+home_id], 'name': 'Hello Watt', 'manufacturer': 'Collecteur personnel'}
    messages = []
    for key, label in [('electricite', 'Électricité mensuelle abonnement inclus'),
                       ('injection', 'Revenu injection mensuel'),
                       ('electricite_veille', 'Électricité de la veille abonnement inclus'),
                       ('injection_veille', 'Revenu injection de la veille'),
                       ('consommation_kwh', 'Consommation réseau mensuelle'),
                       ('injection_kwh', 'Injection réseau mensuelle'),
                       ('consommation_kwh_veille', 'Consommation réseau de la veille'),
                       ('injection_kwh_veille', 'Injection réseau de la veille'),
                       ('electricite_annee', 'Électricité annuelle abonnement inclus'),
                       ('injection_annee', 'Revenu injection annuel'),
                       ('consommation_kwh_annee', 'Consommation réseau annuelle'),
                       ('injection_kwh_annee', 'Injection réseau annuelle')]:
        config = {'name': label, 'unique_id': 'hellowatt_'+home_id+'_'+key,
            'state_topic': prefix+'/state', 'value_template': '{{ value_json.'+key+' }}',
            'unit_of_measurement': 'kWh' if '_kwh' in key else 'EUR',
            'device_class': 'energy' if '_kwh' in key else 'monetary',
            'availability_topic': prefix+'/state',
            'availability_template': "{{ 'online' if value_json."+key+" is not none else 'offline' }}",
            'json_attributes_topic': prefix+'/state', 'device': device}
        messages.append({'topic': 'homeassistant/sensor/hellowatt_'+home_id+'/'+key+'/config', 'payload': json.dumps(config), 'qos': 1, 'retain': True})
    messages.append({'topic': prefix+'/state', 'payload': json.dumps(state), 'qos': 1, 'retain': True})
    for year, data in (history or {}).items():
        topic = prefix+'/archives/'+year
        config = {'name': 'Historique '+year, 'unique_id': 'hellowatt_'+home_id+'_historique_'+year,
                  'state_topic': topic, 'value_template': '{{ value_json.jours_enregistres }}',
                  'unit_of_measurement': 'jours', 'icon': 'mdi:calendar-month',
                  'json_attributes_topic': topic, 'device': device}
        messages.append({'topic': 'homeassistant/sensor/hellowatt_'+home_id+'/historique_'+year+'/config',
                         'payload': json.dumps(config), 'qos': 1, 'retain': True})
        messages.append({'topic': topic, 'payload': json.dumps(data), 'qos': 1, 'retain': True})
    auth = {'username': os.environ['MQTT_USER'], 'password': os.environ.get('MQTT_PASSWORD', '')} if os.environ.get('MQTT_USER') else None
    tls = {} if os.environ.get('MQTT_TLS') == '1' else None
    mqtt.multiple(messages, hostname=host, port=int(os.environ.get('MQTT_PORT', '8883' if tls is not None else '1883')),
                  auth=auth, tls=tls, client_id='hellowatt-collector-'+home_id)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--import', dest='import_file', type=Path)
    p.add_argument('--publish', action='store_true')
    p.add_argument('--date', help='Date de référence AAAA-MM-JJ (import uniquement)')
    p.add_argument('--db', type=Path, default=Path('hellowatt.sqlite'))
    args = p.parse_args()
    if args.date and not args.import_file:
        p.error('--date est réservé aux imports')
    today = datetime.fromisoformat(args.date).date() if args.date else datetime.now(TZ).date()
    home_id = os.environ.get('HELLOWATT_HOME_ID', '')
    if not home_id.isdigit():
        p.error('HELLOWATT_HOME_ID doit contenir le numéro du logement')
    os.umask(0o077)
    start = today.replace(day=1)
    # Sauvegarde unique de la base existante avant ajout des colonnes kWh.
    backup = args.db.with_name(args.db.name+'.avant-0.3.0.bak')
    if args.db.exists() and not backup.exists():
        with sqlite3.connect(args.db) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    with sqlite3.connect(args.db) as db:
        ensure_schema(db)
        db.commit()
        if args.import_file:
            rows = normalize(json.loads(args.import_file.read_text(encoding='utf-8-sig')), today)
            save(db, home_id, rows)
            db.commit()
        else:
            client = Client()
            try:
                client.login(os.environ['HELLOWATT_EMAIL'], os.environ['HELLOWATT_PASSWORD'])
                plan = collection_plan(db, home_id, today)
                for month in plan:
                    print('Étape 3/5 : récupération du mois '+month.strftime('%Y-%m')+'.', flush=True)
                    payload = client.month(home_id, month)
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    rows = normalize(payload, today)
                    # Ne pas mélanger les périodes si le serveur retourne une autre plage.
                    rows = [r for r in rows if r[0].startswith(month.strftime('%Y-%m')+'-')]
                    save(db, home_id, rows)
                    if not payload.get('isFetchOngoing', False):
                        db.execute('INSERT INTO fetched_months VALUES (?,?,?) ON CONFLICT(home,month) DO UPDATE SET fetched_on=excluded.fetched_on',
                                   (home_id, month.strftime('%Y-%m'), today.isoformat()))
                    db.commit()  # Chaque mois terminé est conservé même si le suivant échoue.
            finally:
                client.close()
        print('Étape 4/5 : calcul des historiques journaliers, mensuels et annuels.', flush=True)
        state = summary(db, home_id, start.strftime('%Y-%m'))
        state.update(daily_details(db, home_id, today))
        history = archives(db, home_id, today)
        annual = history[str(today.year)]
        state.update({key+'_annee': annual[key] for key in METRICS})
        state['annee'] = str(today.year)
        state['mois_historique'] = annual['mois']
        state['annees'] = [{k: v for k, v in data.items() if k not in ('jours', 'mois')}
                           for data in history.values()]
        state['historique_debut'] = HISTORY_START.isoformat()
        state['mois_recuperes'] = sum(a['mois_recuperes'] for a in history.values())
        state['mois_attendus'] = sum(a['mois_attendus'] for a in history.values())
    state['collecte_reussie_a'] = datetime.now(TZ).isoformat()
    state['mode'] = 'import' if args.import_file else 'connecte'
    if args.publish:
        print('Étape 5/5 : publication MQTT.', flush=True)
        publish(state, home_id, history)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Aucune réponse HTTP, URL authentifiée ou information de connexion dans les logs.
        print(error_message(exc) + ' Les données enregistrées sont conservées.', file=sys.stderr)
        sys.exit(1)
