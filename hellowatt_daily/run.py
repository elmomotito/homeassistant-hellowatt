"""Une collecte réussie par jour ; reprises transitoires limitées et persistantes."""
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Paris')
MAX_ATTEMPTS = 4
BACKOFF = (3600, 10800, 21600, 43200)


def read_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def format_due(value):
    try:
        return datetime.fromtimestamp(value, TZ).isoformat(timespec='minutes')
    except (ValueError, OverflowError, OSError):
        return 'la fin du délai demandé par le serveur'


def due(state, now, startup=False, manual=False):
    today = datetime.fromtimestamp(now, TZ).date().isoformat()
    same_day = state.get('date') == today
    # Le délai serveur s'applique aussi après redémarrage, à minuit et en manuel.
    if now < state.get('next_allowed_at', 0):
        return False, 'cooldown'
    if not manual and state.get('last_success_date') == today:
        return False, 'success'
    if same_day and not manual:
        if state.get('terminal_failure') or state.get('attempts', 0) >= MAX_ATTEMPTS:
            return False, 'limit'
    if not startup and not manual and not (same_day and state.get('attempts', 0)):
        if datetime.fromtimestamp(now, TZ).hour < 8:
            return False, 'scheduled'
    return True, 'ready'


def run(data_dir=Path('/data'), app_dir=Path('/app'), startup=False, clock=time.time,
        execute=subprocess.run):
    os.umask(0o077)
    options = read_json(data_dir/'options.json')
    if startup and not options.get('run_on_start'):
        print('Collecte quotidienne à partir de 8 h ; reprises éventuelles toutes les 10 min.')
        return 0
    with (data_dir/'collect.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        state_path = data_dir/'scheduler_state.json'
        state = read_json(state_path)
        legacy = read_json(data_dir/'last_run.json')
        if not state and legacy.get('success') is True:
            state['last_success_date'] = legacy.get('date')
        now = clock()
        today = datetime.fromtimestamp(now, TZ).date().isoformat()
        retry_token = str(options.get('retry_once') or '').strip()
        retry_marker = data_dir/'last_retry.txt'
        manual = startup and bool(retry_token) and (
            not retry_marker.exists() or retry_marker.read_text() != retry_token)
        allowed, reason = due(state, now, startup, manual)
        if not allowed:
            if startup:
                if reason == 'cooldown':
                    when = format_due(state['next_allowed_at'])
                    print('Pause respectée : aucun appel Hello Watt avant '+when+'.')
                else:
                    print({'success':'Collecte déjà réussie aujourd’hui.',
                           'limit':'Limite quotidienne atteinte ou erreur non transitoire ; prochain passage demain.',
                           'scheduled':'Collecte programmée à partir de 8 h.'}.get(reason, reason))
            return 0
        if any(not options.get(k) for k in ('email', 'password', 'mqtt_host')):
            print('Configuration incomplète : renseigner email, password et mqtt_host.')
            return 1
        attempts = state.get('attempts', 0) if state.get('date') == today else 0
        attempts += 1
        # Écrit avant de démarrer : un redémarrage ne contourne pas la pause.
        state.update(date=today, attempts=attempts, next_allowed_at=now+BACKOFF[min(attempts-1, 3)], terminal_failure=False)
        atomic_json(state_path, state)
        if manual:
            retry_marker.write_text(retry_token)
            print('Nouvel essai manuel demandé ; les délais serveur restent respectés.')
        (data_dir/'last_attempt.txt').write_text(today)
        status_path = data_dir/'collector_status.json'
        status_path.unlink(missing_ok=True)
        env = dict(os.environ)
        for option, variable in [('email','HELLOWATT_EMAIL'), ('password','HELLOWATT_PASSWORD'),
            ('home_id','HELLOWATT_HOME_ID'), ('mqtt_host','MQTT_HOST'), ('mqtt_port','MQTT_PORT'),
            ('mqtt_user','MQTT_USER'), ('mqtt_password','MQTT_PASSWORD')]:
            env[variable] = str(options.get(option, ''))
        env['MQTT_TLS'] = '1' if options.get('mqtt_tls') else '0'
        env['HELLOWATT_STATUS_FILE'] = str(status_path)
        print(f'Collecte : essai {attempts}/{MAX_ATTEMPTS} de la journée.', flush=True)
        try:
            result = execute([sys.executable, str(app_dir/'collecteur.py'), '--db', str(data_dir/'hellowatt.sqlite'), '--publish'], env=env, timeout=600, check=False)
            code = result.returncode
        except subprocess.TimeoutExpired:
            print('Délai global de 600 secondes dépassé. Collecteur arrêté.')
            code = 75
        finished = clock()
        status = read_json(status_path)
        if code == 0:
            state.update(last_success_date=today, next_allowed_at=0, terminal_failure=False)
            print('Collecte terminée.')
        else:
            retryable = code == 75
            state['terminal_failure'] = not retryable
            state['next_allowed_at'] = max(finished+BACKOFF[min(attempts-1, 3)], status.get('next_allowed_at', 0))
            if retryable and attempts < MAX_ATTEMPTS:
                when = format_due(state['next_allowed_at'])
                print('Collecte différée. Prochain essai au plus tôt '+when+' ; historique conservé.')
            else:
                print('Collecte en échec ; arrêt des reprises automatiques pour cette journée. Historique conservé.')
        atomic_json(state_path, state)
        atomic_json(data_dir/'last_run.json', {'date':today, 'success':code == 0, 'attempts':attempts,
            'next_allowed_at':state['next_allowed_at'], 'finished_at':finished})
        return code


if __name__ == '__main__':
    sys.exit(run(startup='--startup' in sys.argv))
