# Publier la version 0.6.2

Copier le contenu de ce dossier à la racine du dépôt `elmomotito/homeassistant-hellowatt` : `repository.yaml`, `README.md`, `docs/` et surtout le dossier complet `hellowatt_daily/`. Ne pas créer un niveau de dossier supplémentaire.

Le dossier `hellowatt_daily/frontend/` et `install_card.py` sont nécessaires : envoyer seulement le README ou le JS ne suffit pas. Conserver les éventuels autres fichiers de votre dépôt (licence, workflows…).

Après publication : actualiser le magasin Home Assistant, mettre à jour l’application vers 0.6.2 sans la désinstaller, puis vérifier ses journaux. Les données persistantes et les identifiants existants sont conservés par une mise à jour normale. Actualiser le navigateur et ajouter une carte manuelle `type: custom:hello-watt-cost-card`.

La version demande le montage de configuration et l’accès à l’API Home Assistant pour installer la carte. L’option `install_card` est activée par défaut, y compris si elle n’existait pas dans l’ancienne configuration. Aucun redémarrage de Home Assistant n’est déclenché.

Les tests locaux passent. L’installation complète reste à valider sur Home Assistant ; aucun fichier n’a été publié sur GitHub ou déployé sur votre instance par cette préparation.
