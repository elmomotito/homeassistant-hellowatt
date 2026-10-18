# Correctif 0.6.3 — limitations temporaires Hello Watt

- Un HTTP 429 arrête la collecte et conserve les données.
- `Retry-After` est accepté en secondes ou sous forme de date HTTP.
- Le délai effectif est le plus long entre le délai serveur et le backoff local
  (1 h, 3 h, 6 h). Aucun appel n’est fait pendant cette pause, même après
  redémarrage, changement de date ou demande manuelle.
- Quatre essais automatiques maximum par journée locale. Une réussite empêche
  les collectes suivantes de la journée. Les erreurs 401/403 ne bouclent pas.
- Le cron vérifie toutes les dix minutes si une collecte est due ; cela ne
  signifie pas une connexion Hello Watt toutes les dix minutes. Première
  collecte quotidienne à partir de 8 h, sauf demande au démarrage.
- Les appels d’une collecte sont espacés d’au moins une seconde.
- Les calculs des montants, la base SQLite et les identifiants MQTT restent
  identiques. Les checkpoints mensuels sont conservés.

## Installation

Mettre à jour l’application existante vers 0.6.3, sans la désinstaller.
Laisser ses options et son répertoire `/data` en place. Un simple redémarrage
sans mise à jour/reconstruction ne remplace pas les fichiers de l’image.
Après un 429, ne pas multiplier les redémarrages : le planificateur attendra
le délai de reprise. Il est impossible de garantir qu’un serveur distant
cessera de limiter les requêtes.

## Vérification hors ligne

`python3 -m unittest discover -s . -p 'test_*.py'`

30 tests, sans aucun appel Hello Watt : temporisation, reprise, verrou,
limite quotidienne, erreurs définitives, base et archives, MQTT et logements.
