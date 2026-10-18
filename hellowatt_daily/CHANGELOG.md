# 0.6.4
- Session authentifiée conservée dans /data avec permissions 0600 et cookies limités au domaine Hello Watt.
- Réutilisation après redémarrage ; une reconnexion seulement en cas de session expirée (401 ou redirection de connexion).
- Aucun nouvel essai de connexion sur 429/403 ; pauses serveur conservées.
- Diagnostics HTTP 429 sans cookies, identifiants ni corps de réponse.
- 37 tests hors ligne, dont sept scénarios de session.

# 0.6.3

- Reprise différée persistante après HTTP 429, respect de Retry-After.
- Quatre essais automatiques maximum ; distinction échec/réussite.
- Espacement des appels ; conservation des historiques et options.

## 0.6.2

- Carte Hello Watt embarquée, installation et enregistrement automatique de la ressource au démarrage (désactivable avec `install_card`).
- Mise à jour de la ressource existante sans doublon et cache versionné ; recours manuel pour les ressources YAML.
- Installation indépendante de la collecte, sans modification directe de `.storage` ni redémarrage de Home Assistant.
- Moyennes import/injection en pointillés ; suppression de la phrase des prix moyens par kWh.
- README mis à jour pour la carte incluse.

# 0.6.1

- Conservation de toutes les plages de `eurosDetailed` et `kwhDetailed`, hors abonnement déjà stocké séparément.
- Nouveaux attributs journaliers `tarifs_eur` et `tarifs_kwh` ; compatibilité `tempo_eur` / `tempo_kwh` conservée.
- Remplacement du détail d’une journée lorsque Hello Watt le corrige.
- Rattrapage progressif des archives pour récupérer les plages manquantes, sans suppression de l’historique des montants.
- Aucune conversion kWh × tarif ni changement d’authentification / MQTT.
