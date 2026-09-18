"""Install only our frontend file and register it through the HA WebSocket API."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

URL_PATH = '/local/hellowatt/hello-watt-cost-card.js'
LEGACY_PATH = '/local/hello-watt-cost-card.js'


class RegistrationError(Exception):
    pass


def install_file(source, config_dir):
    content = source.read_bytes()
    www = config_dir / 'www'
    new_www = not www.exists()
    target = www / 'hellowatt' / 'hello-watt-cost-card.js'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != content:
        # Atomic replacement: a browser never receives a half-written module.
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
                name = out.name
                out.write(content)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(name, 0o644)
            os.replace(name, target)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
    return URL_PATH + '?v=' + hashlib.sha256(content).hexdigest()[:12], new_www


def register_resource(ws, token, url):
    hello = json.loads(ws.recv())
    if hello.get('type') != 'auth_required':
        raise RegistrationError('Authentification Home Assistant inattendue')
    ws.send(json.dumps({'type': 'auth', 'access_token': token}))
    if json.loads(ws.recv()).get('type') != 'auth_ok':
        raise RegistrationError('Authentification Home Assistant refusée')
    next_id = 0

    def command(kind, **fields):
        nonlocal next_id
        next_id += 1
        ws.send(json.dumps(dict(id=next_id, type=kind, **fields)))
        # No event subscriptions; ignore a bounded number of unrelated messages.
        for _ in range(20):
            reply = json.loads(ws.recv())
            if reply.get('id') != next_id:
                continue
            if not reply.get('success'):
                # Never print raw replies (may contain sensitive information).
                raise RegistrationError('Commande Lovelace refusée : ' + kind)
            return reply.get('result')
        raise RegistrationError('Réponse Lovelace absente')

    info = command('lovelace/info')
    if info.get('resource_mode', info.get('mode')) == 'yaml':
        raise RegistrationError('Ressources gérées en YAML : déclaration manuelle nécessaire')
    resources = command('lovelace/resources')
    matching = []
    for resource in resources:
        parts = urlsplit(resource.get('url', ''))
        if not parts.netloc and not parts.scheme and parts.path in (URL_PATH, LEGACY_PATH):
            matching.append(resource)
    if len(matching) > 1:
        raise RegistrationError('Plusieurs ressources Hello Watt existent : conserver une seule entrée manuellement')
    if matching:
        existing = matching[0]
        if existing['url'] == url and existing.get('type') == 'module':
            return 'déjà à jour'
        command('lovelace/resources/update', resource_id=existing['id'], url=url, res_type='module')
        return 'mise à jour'
    command('lovelace/resources/create', url=url, res_type='module')
    return 'ajoutée'


def main():
    options = json.loads(Path('/data/options.json').read_text())
    if not options.get('install_card', True):
        print('Installation automatique de la carte désactivée.')
        return
    url, new_www = install_file(Path('/app/frontend/hello-watt-cost-card.js'), Path('/homeassistant'))
    print('Carte Hello Watt copiée. Ressource module : ' + url, flush=True)
    if new_www:
        print('Dossier www créé : si /local renvoie 404, un redémarrage de Home Assistant peut être nécessaire. Aucun redémarrage automatique.', flush=True)
    token = os.environ.get('SUPERVISOR_TOKEN')
    if not token:
        print('Jeton Supervisor absent : ajouter la ressource manuellement.', flush=True)
        return
    import websocket
    # HA may still be starting. Bounded retries in this independent process.
    for attempt in range(6):
        ws = None
        try:
            ws = websocket.create_connection(
                'ws://supervisor/core/websocket', timeout=10,
                header={'Authorization': 'Bearer ' + token}, suppress_origin=True,
                http_no_proxy=['supervisor'],
            )
            result = register_resource(ws, token, url)
            print('Ressource Hello Watt ' + result + '. Actualiser le navigateur puis ajouter la carte.', flush=True)
            return
        except RegistrationError as exc:
            print(str(exc) + '. Ressource module à déclarer : ' + url, flush=True)
            return
        except Exception:
            if attempt == 5:
                print('API Home Assistant inaccessible : ajouter la ressource manuellement ou redémarrer uniquement cette application. La collecte reste active.', flush=True)
        finally:
            if ws is not None:
                ws.close()
        if attempt < 5:
            time.sleep(20)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Installation problems must never block the independent collector.
        print('Installation de la carte impossible : vérifier le montage homeassistant_config et consulter le README. La collecte reste active.', flush=True)
