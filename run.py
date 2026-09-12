"""Planification : au plus une tentative par date locale, processus borné à 600 s."""
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

os.umask(0o077)
options = json.loads(Path('/data/options.json').read_text())
if '--startup' in sys.argv and not options.get('run_on_start'):
    print('Collecte programmée à midi (Europe/Paris).')
    sys.exit(0)
with open('/data/collect.lock', 'w') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)
    today = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    marker = Path('/data/last_attempt.txt')
    retry_marker = Path('/data/last_retry.txt')
    retry_token = str(options.get('retry_once') or '').strip()
    manual_retry = ('--startup' in sys.argv and bool(retry_token)
                    and (not retry_marker.exists() or retry_marker.read_text() != retry_token))
    if marker.exists() and marker.read_text() == today and not manual_retry:
        print('Une tentative a déjà eu lieu aujourd’hui. Prochain passage demain.')
        sys.exit(0)
    required = ['email', 'password', 'home_id', 'mqtt_host']
    if any(not options.get(k) for k in required):
        print('Configuration incomplète : renseigner email, password, home_id et mqtt_host.')
        sys.exit(1)
    env = dict(os.environ)
    for option, variable in [('email','HELLOWATT_EMAIL'), ('password','HELLOWATT_PASSWORD'),
        ('home_id','HELLOWATT_HOME_ID'), ('mqtt_host','MQTT_HOST'), ('mqtt_port','MQTT_PORT'),
        ('mqtt_user','MQTT_USER'), ('mqtt_password','MQTT_PASSWORD')]:
        env[variable] = str(options.get(option, ''))
    env['MQTT_TLS'] = '1' if options.get('mqtt_tls') else '0'
    if manual_retry:
        retry_marker.write_text(retry_token)
        print('Nouvel essai manuel demandé dans la configuration.', flush=True)
    marker.write_text(today)
    try:
        result = subprocess.run([sys.executable, '/app/collecteur.py', '--db', '/data/hellowatt.sqlite', '--publish'],
                                env=env, timeout=600, check=False)
        code = result.returncode
    except subprocess.TimeoutExpired:
        print('Délai global de 600 secondes dépassé. Collecteur arrêté.')
        code = 1
    Path('/data/last_run.json').write_text(json.dumps({'date': today, 'success': code == 0}))
    print('Collecte terminée.' if code == 0 else 'Collecte en échec; vérifier les journaux et la date des derniers montants.')
    sys.exit(code)
