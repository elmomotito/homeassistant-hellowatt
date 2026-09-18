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
