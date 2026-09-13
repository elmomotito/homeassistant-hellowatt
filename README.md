# Hello Watt pour Home Assistant

[![Ajouter le dépôt à Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Felmomotito%2Fhomeassistant-hellowatt)

Retrouvez vos données Hello Watt dans Home Assistant, avec une **collecte quotidienne à 8 h**, un **logement détecté automatiquement** et un **historique conservé depuis janvier 2026**.

**Version 0.6.0 · Projet non officiel, indépendant de Hello Watt.**

## Données disponibles

| Donnée | Unité |
|---|---|
| Coût de l’électricité importée, abonnement inclus | € |
| Revenu de l’électricité injectée sur le réseau | € |
| Consommation sur le réseau | kWh |
| Injection sur le réseau | kWh |
| Production solaire | kWh |
| Valorisation solaire fournie par Hello Watt | € |

Ces six mesures sont disponibles pour **la veille, le mois courant et l’année courante**. Les journées et les mois précédents restent accessibles dans les attributs des capteurs d’historique.

Le module conserve également la part de l’abonnement et le détail des **six tarifs Tempo : bleu, blanc et rouge, en heures pleines et creuses**, lorsque Hello Watt les fournit.

![Exemple de dashboard Home Assistant : coûts, tarifs Tempo et statistiques solaires](docs/images/dashboard-hellowatt.png)

*Exemple avec une carte personnalisée, non incluse dans ce dépôt. Le module fournit les données ; il ne crée pas ce dashboard. Les estimations du jour visibles sur la capture sont calculées par la carte à partir de capteurs locaux.*

## Prérequis

- **Home Assistant avec le magasin d’applications**, typiquement Home Assistant OS, sur une machine ARM64 ou x86-64.
- Un compte **Hello Watt avec adresse e-mail et mot de passe**, dont les données sont déjà visibles sur le site.
- Un broker **MQTT**, par exemple Mosquitto, et l’intégration MQTT configurée dans Home Assistant.
- Un accès Internet fonctionnel depuis la machine Home Assistant.

L’installation se fait depuis le magasin Home Assistant, **sans HACS, sans Samba et sans installer Python manuellement**. Home Assistant Container seul ne dispose pas du magasin requis.

> Une connexion Hello Watt uniquement via Google/Apple ou exigeant une validation interactive n’est pas prise en charge. Les données solaires doivent déjà être disponibles sur votre compte pour être récupérées.

## Installation

### 1. Préparer MQTT

Si MQTT fonctionne déjà chez vous, utilisez vos identifiants habituels et passez à l’étape suivante.

Sinon :

1. Installez **Mosquitto broker** depuis le magasin d’applications, puis démarrez-le.
2. Configurez l’intégration **MQTT** dans **Paramètres → Appareils et services**.
3. Créez un utilisateur dédié dans **Paramètres → Personnes → Utilisateurs**, par exemple `hellowatt_mqtt`, avec un mot de passe et sans droits administrateur. Activez le mode avancé de votre profil si l’onglet Utilisateurs n’apparaît pas.

Avec le Mosquitto officiel, cet utilisateur sert à la connexion MQTT. Avec un autre broker, utilisez les accès créés sur ce broker. [Documentation Mosquitto](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md).

### 2. Ajouter le dépôt et installer Hello Watt

Cliquez sur le bouton **Ajouter le dépôt à Home Assistant** en haut de cette page, puis confirmez dans votre instance.

Vous pouvez aussi passer par **Paramètres → Applications → Magasin d’applications → ⋮ → Dépôts** et ajouter :

```text
https://github.com/elmomotito/homeassistant-hellowatt
```

Actualisez le magasin si nécessaire, ouvrez **Hello Watt — collecte quotidienne**, puis cliquez sur **Installer**. La première construction peut prendre quelques minutes.

### 3. Renseigner les accès

Dans l’onglet **Configuration** de l’application, renseignez vos accès Hello Watt et MQTT :

```yaml
email: "votre-adresse@example.com"
password: "VOTRE_MOT_DE_PASSE_HELLO_WATT"
home_id: ""
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: hellowatt_mqtt
mqtt_password: "VOTRE_MOT_DE_PASSE_MQTT"
mqtt_tls: false
run_on_start: true
retry_once: ""
```

- **`home_id`** : laissez vide. Le logement est détecté après connexion. Aucun passage par les outils de développement n’est nécessaire.
- **`mqtt_host`** : conservez `core-mosquitto` avec le Mosquitto officiel ; sinon indiquez votre broker.
- **`mqtt_port` / `mqtt_tls`** : l’exemple utilise le MQTT local sans TLS. Pour un broker TLS, activez `mqtt_tls` et adaptez le port, souvent `8883`.
- **`run_on_start: true`** : permet le premier essai au démarrage.

Saisissez les mots de passe normalement, sans encodage. Ne les ajoutez jamais aux fichiers du dépôt GitHub.

**Plusieurs logements ?** Le module conserve celui déjà présent dans sa base si ce choix est unique. Sinon, les journaux affichent les numéros disponibles : renseignez celui souhaité dans `home_id`. Un numéro renseigné manuellement reste prioritaire.

### 4. Démarrer et vérifier

Enregistrez la configuration, démarrez l’application et consultez les **Journaux**. Le premier passage se connecte à Hello Watt, récupère les mois disponibles depuis janvier 2026, puis publie les capteurs MQTT.

Après le message **« Collecte terminée. »**, cherchez l’appareil **Hello Watt** dans **Paramètres → Appareils et services → MQTT**.

Remettez ensuite :

```yaml
run_on_start: false
retry_once: ""
```

Gardez l’application **démarrée** et activez son **démarrage automatique**. Elle lancera les prochaines collectes à **8 h, heure de Paris**, avec adaptation à l’heure d’été/hiver. Aucun redémarrage complet de Home Assistant n’est nécessaire.

## Fonctionnement quotidien

- Le script se connecte une fois par passage, collecte les données, les sauvegarde puis se termine. Seul le planificateur reste actif jusqu’au lendemain.
- Une tentative automatique au maximum est autorisée par journée. En cas d’échec, les anciennes données sont conservées.
- Le **jour en cours est exclu** : la dernière journée attendue est celle de la veille, sous réserve qu’elle soit disponible chez Hello Watt.
- Le premier passage rattrape l’historique depuis le **1er janvier 2026**, avec un maximum de douze mois interrogés par passage. Le rattrapage continue lors des passages suivants si nécessaire.
- Les collectes suivantes relisent les périodes récentes et revisitent progressivement les anciens mois pour récupérer les corrections.
- Les années précédentes sont conservées : en 2027, les données de 2026 restent présentes.

## Capteurs et historique

Le module crée **18 capteurs de montants et d’énergie** : six mesures × trois périodes. Il publie également **un capteur d’historique par année**.

Les identifiants exacts des entités dépendent de Home Assistant. Retrouvez-les sur les fiches des capteurs.

| Attribut | Contenu |
|---|---|
| `jours` des capteurs usuels | Détail quotidien du mois courant, jusqu’à hier |
| `mois_historique` | Totaux mensuels de l’année courante |
| `annees` | Totaux de chaque année conservée |
| `jours` du capteur Historique 2026, 2027… | Détail quotidien de l’année concernée |
| `mois` du capteur d’historique | Totaux mensuels de cette année |
| `collecte_reussie_a` | Date de préparation des données lors du passage réussi |
| `mois_recuperes` / `mois_attendus` | Progression du rattrapage |

Les entrées journalières utilisent les clés `date`, `electricite`, `abonnement`, `injection`, `consommation_kwh`, `injection_kwh`, `production_kwh` et `production_eur`.

**À retenir pour vos calculs :**

- `electricite` inclut déjà `abonnement` : ne l’ajoutez pas une seconde fois.
- `consommation_kwh` mesure l’import réseau, pas la consommation totale du logement.
- `production_eur` reprend la valorisation de Hello Watt ; ce n’est pas un revenu à ajouter automatiquement à `injection`.
- Une mesure absente reste `null`, un zéro réel reste `0`.

### Détail Tempo

Chaque journée peut contenir `tempo_eur` et `tempo_kwh`, avec ces clés :

```text
Tempo-red-HP     Tempo-red-HC
Tempo-white-HP   Tempo-white-HC
Tempo-blue-HP    Tempo-blue-HC
```

Ce détail se trouve dans `jours`, y compris dans les archives annuelles. Pour une ventilation mensuelle ou annuelle, additionnez les journées concernées. Les tarifs absents ne sont pas remplacés par des zéros supposés.

### Trouver les données dans les attributs

Un capteur Home Assistant contient deux choses différentes : son **état** (la valeur principale affichée) et ses **attributs** (les informations complémentaires).

Par exemple, un capteur « Électricité mensuelle » peut afficher `65.87` comme état, tandis que son attribut `jours` contient le coût de chaque journée. Le capteur « Historique 2026 » affiche un nombre de jours comme état : les montants sont dans ses attributs, pas dans ce nombre.

Pour consulter les données :

1. Ouvrez **Paramètres → Appareils et services → MQTT**, puis l’appareil **Hello Watt**.
2. Ouvrez le capteur souhaité et copiez son **identifiant d’entité**. Les noms peuvent varier selon votre installation.
3. Allez dans **Outils de développement → États** et recherchez cet identifiant.
4. Consultez la colonne ou la zone **Attributs**, notamment `jours`, `mois_historique` ou `mois`. Vous n’avez rien à modifier dans cet écran.

Exemple fictif de l’attribut `jours` :

```yaml
jours:
  - date: "2026-09-01"
    electricite: 4.35
    abonnement: 0.75
    injection: 0.82
    consommation_kwh: 24.6
    injection_kwh: 6.5
    production_kwh: 12.0
    production_eur: 1.70
  - date: "2026-09-02"
    electricite: 3.20
    abonnement: 0.75
    injection: 0
    consommation_kwh: 18.2
    injection_kwh: 0
    production_kwh: null
    production_eur: null
```

Chaque élément correspond à **une date**, avec plusieurs mesures. Ici, `electricite: 4.35` est le coût de cette journée, abonnement déjà compris. `injection: 0` est un revenu nul réel ; `production_kwh: null` signifie que la mesure manque.

**Quel capteur choisir ?**

| Graphique souhaité | Où lire les données |
|---|---|
| Jours du mois courant | `jours` d’un capteur usuel Hello Watt |
| Jours d’un ancien mois | `jours` du capteur Historique de l’année concernée ; filtrer les dates de ce mois |
| Mois de l’année courante | `mois_historique` d’un capteur usuel, ou `mois` de l’archive annuelle |
| Mois de 2026 après passage en 2027 | `mois` du capteur Historique 2026 |
| Totaux par année | `annees` d’un capteur usuel |

Une journée disponible dans les attributs n’apparaît pas automatiquement à sa date dans la courbe native du capteur : MQTT n’insère pas rétroactivement ces états dans l’historique Home Assistant. Le graphique doit donc **lire les attributs directement**.

### Préparer un graphique avec ApexCharts Card

[ApexCharts Card](https://github.com/RomRider/apexcharts-card) est une carte de dashboard facultative. **HACS est nécessaire pour cette méthode d’installation de la carte graphique, pas pour le collecteur Hello Watt.**

1. Dans HACS, recherchez **ApexCharts Card**, puis téléchargez-la.
2. Rechargez le navigateur si HACS le demande.
3. Ouvrez votre dashboard → **Modifier → Ajouter une carte → Manuelle**.
4. Collez l’un des exemples ci-dessous.
5. Remplacez chaque identifiant `sensor.votre_…` par celui copié à l’étape précédente.

Ne collez pas ces exemples dans la configuration de l’application Hello Watt : ils vont dans une **carte du dashboard**.

### Exemple 1 — coût et revenu d’injection par jour du mois courant

Remplacez les **deux occurrences** de `sensor.votre_capteur_hellowatt` par le même capteur Hello Watt disposant de l’attribut `jours`.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Hello Watt · Coûts quotidiens
  show_states: false
graph_span: 31d
span:
  start: month
all_series_config:
  type: column
  unit: €
  float_precision: 2
  show:
    legend_value: false
series:
  - entity: sensor.votre_capteur_hellowatt
    name: Électricité, abonnement inclus
    color: "#38bdf8"
    data_generator: |
      const jours = entity.attributes.jours;
      if (!Array.isArray(jours)) return [];
      const mois = start.getFullYear() + '-' +
        String(start.getMonth() + 1).padStart(2, '0');
      return jours
        .filter(j => typeof j.date === 'string' &&
          j.date.startsWith(mois + '-') &&
          typeof j.electricite === 'number' && Number.isFinite(j.electricite))
        .map(j => [new Date(j.date + 'T12:00:00').getTime(), j.electricite])
        .sort((a, b) => a[0] - b[0]);
  - entity: sensor.votre_capteur_hellowatt
    name: Revenu injection
    color: "#ec4899"
    data_generator: |
      const jours = entity.attributes.jours;
      if (!Array.isArray(jours)) return [];
      const mois = start.getFullYear() + '-' +
        String(start.getMonth() + 1).padStart(2, '0');
      return jours
        .filter(j => typeof j.date === 'string' &&
          j.date.startsWith(mois + '-') &&
          typeof j.injection === 'number' && Number.isFinite(j.injection))
        .map(j => [new Date(j.date + 'T12:00:00').getTime(), j.injection])
        .sort((a, b) => a[0] - b[0]);
```

Les deux barres d’une journée sont affichées côte à côte. Les revenus restent positifs ; ils ne sont pas additionnés au coût. Le graphique se met à jour lorsque MQTT actualise les attributs, sans recopier manuellement les journées.

La fenêtre couvre 31 jours depuis le premier du mois. Pour un mois plus court, quelques jours vides peuvent apparaître à droite ; le filtre empêche d’y afficher des valeurs du mois suivant. Le jour en cours reste vide puisque le collecteur ne l’estime pas.

### Comprendre et adapter le code

`data_generator` transforme les attributs en une liste de points **[date, valeur]**. C’est le mécanisme prévu par [la documentation ApexCharts Card](https://github.com/RomRider/apexcharts-card#data_generator-option) pour tracer des données déjà présentes dans un capteur.

- `entity.attributes.jours` lit les journées du capteur indiqué dans `entity`.
- `.filter(...)` sélectionne le mois et écarte les mesures absentes. Les vrais zéros sont conservés.
- `.map(...)` associe chaque date à sa mesure. Midi sert uniquement à placer la barre dans la journée ; ce n’est pas une heure de mesure.
- `.sort(...)` classe les dates dans l’ordre chronologique.

Pour changer la mesure, remplacez **toutes les occurrences du champ dans la série**, puis son `name` et son `unit` :

| À tracer | Champ | Unité |
|---|---|---|
| Coût, abonnement inclus | `electricite` | € |
| Abonnement seul | `abonnement` | € |
| Revenu injection | `injection` | € |
| Import réseau | `consommation_kwh` | kWh |
| Injection réseau | `injection_kwh` | kWh |
| Production solaire | `production_kwh` | kWh |
| Valorisation solaire | `production_eur` | € |

Par exemple, pour un graphique de production solaire quotidienne, conservez seulement la première série, remplacez ses trois occurrences de `j.electricite` par `j.production_kwh`, puis utilisez `name: Production solaire` et `unit: kWh`. Vous pouvez aussi remplacer l’unité dans `all_series_config` si toutes les séries sont en kWh. Évitez de mélanger euros et kWh sur un même axe.

### Exemple 2 — production solaire par mois d’une année

Choisissez le capteur **Historique de l’année courante** et remplacez `sensor.votre_historique_annee_courante`. Son attribut `mois` contient déjà les totaux mensuels : il n’est pas nécessaire de les recalculer depuis les journées.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Hello Watt · Production mensuelle
  show_states: false
graph_span: 366d
span:
  start: year
series:
  - entity: sensor.votre_historique_annee_courante
    name: Production solaire
    type: column
    unit: kWh
    color: "#fbbf24"
    float_precision: 1
    show:
      legend_value: false
    data_generator: |
      const mois = entity.attributes.mois;
      if (!Array.isArray(mois)) return [];
      const annee = String(start.getFullYear());
      return mois
        .filter(m => typeof m.mois === 'string' &&
          m.mois.startsWith(annee + '-') &&
          typeof m.production_kwh === 'number' && Number.isFinite(m.production_kwh))
        .map(m => [new Date(m.mois + '-15T12:00:00').getTime(), m.production_kwh])
        .sort((a, b) => a[0] - b[0]);
```

Le 15 du mois sert à positionner chaque barre mensuelle. Le mois en cours reste partiel. La fenêtre de 366 jours peut laisser un jour vide supplémentaire lors d’une année non bissextile.

Au changement d’année, choisissez le nouveau capteur d’archive. **Changer seulement l’entité pour Historique 2026 ne suffit pas à afficher 2026 si la fenêtre du graphique montre 2027** : la période affichée doit elle aussi couvrir les dates souhaitées. De même, pour un ancien mois, utilisez ses journées dans l’archive annuelle et adaptez la fenêtre temporelle ainsi que le filtre. Les exemples ci-dessus suivent volontairement le mois ou l’année en cours.

### Si le graphique est vide

1. Vérifiez que l’identifiant d’entité existe et que l’attribut attendu contient une liste.
2. Vérifiez que les dates de cette liste sont dans la période affichée par le graphique.
3. Vérifiez que le champ choisi a des valeurs numériques : `null` signifie qu’aucune mesure n’est disponible.
4. Si Home Assistant affiche « Custom element doesn't exist: apexcharts-card », terminez l’installation de la carte dans HACS, puis rechargez le navigateur.
5. Ne remplacez pas les données absentes par `0` pour remplir le graphique : cela fausserait les résultats.


## Relancer une collecte manuellement

Après une correction de configuration, ou pour tester sans attendre 8 h :

```yaml
run_on_start: true
retry_once: "essai-1"
```

Enregistrez puis redémarrez **uniquement l’application Hello Watt**. Utilisez une nouvelle valeur (`essai-2`, etc.) pour chaque essai supplémentaire. Après réussite, remettez `run_on_start: false` et `retry_once: ""`.

## Mise à jour et sauvegardes

Les nouvelles versions sont proposées dans le magasin lorsque la version du module augmente. Utilisez **Mettre à jour**, sans désinstaller l’application, pour conserver ses données.

La base locale est stockée dans `/data/hellowatt.sqlite`, à l’intérieur de l’application. Incluez l’application et ses données dans vos sauvegardes Home Assistant. Ne publiez pas cette base, les fichiers d’options ou vos identifiants sur GitHub.

**Passage d’une installation locale au dépôt GitHub :** il s’agit de deux applications distinctes, avec deux dossiers de données. La nouvelle installation ne récupère pas automatiquement la base de l’ancienne. Conservez l’ancienne et sa sauvegarde pour préparer la migration ; ne démarrez pas les deux collecteurs simultanément. Sans migration de la base, un nouveau rattrapage dépendra des données encore disponibles chez Hello Watt.

## Dépannage

| Symptôme | À vérifier |
|---|---|
| L’application n’apparaît pas | Dépôt ajouté avec la bonne URL, magasin actualisé, architecture ARM64 ou x86-64 |
| Échec pendant l’installation | Journaux de construction ; accès aux registres Docker, à PyPI et aux dépôts Alpine ; résolution DNS |
| Échec de connexion Hello Watt | Identifiants, connexion par e-mail/mot de passe et étape indiquée dans les journaux |
| Plusieurs logements détectés | Renseigner `home_id` avec le numéro voulu indiqué dans les journaux |
| Collecte réussie mais aucun capteur | Broker et intégration MQTT démarrés ; hôte, port et identifiants corrects |
| Pas de nouveau passage après un redémarrage | Une tentative a déjà eu lieu aujourd’hui ; utiliser un nouveau `retry_once` pour relancer |
| Données anciennes ou incomplètes | Dernière collecte réussie, progression du rattrapage et disponibilité réelle sur Hello Watt |
| Historique natif vide pour les anciens jours | Utiliser les attributs `jours` des capteurs d’historique dans votre graphique |

En cas d’erreur DNS, diagnostiquez la résolution depuis Home Assistant avant de modifier ses paramètres réseau. Le script ne change pas le DNS et ne pilote aucun équipement.

Pour demander de l’aide, ouvrez une [issue](https://github.com/elmomotito/homeassistant-hellowatt/issues) avec la version, l’architecture et un extrait de journal anonymisé. Ne joignez pas de mot de passe, cookie ou export HAR non nettoyé.

## Détails techniques et limites

- Python, Requests, SQLite et Paho MQTT ; image construite sur la machine lors de l’installation.
- Connexion HTTPS par formulaire et cookie CSRF. Les cookies restent en mémoire pendant la collecte ; aucun navigateur laissé ouvert n’est nécessaire.
- Détection via la liste authentifiée `/api/homes`. Si la réponse est ambiguë, invalide ou paginée, un choix manuel est demandé.
- Publications MQTT retenues, QoS 1 : `hellowatt/<home_id>/state`, `hellowatt/<home_id>/archives/<annee>` et découverte sous `homeassistant/sensor/…`.
- Durée maximale d’un passage : **600 secondes**. Chaque mois terminé est sauvegardé avant le suivant.
- Un import hors ligne avec `--import` exige toujours un `HELLOWATT_HOME_ID` explicite.
- TLS MQTT prend en charge les autorités de certification de l’image ; les certificats client et les autorités privées ne sont pas configurables.

Le module utilise les requêtes du site Hello Watt, qui peuvent évoluer. La connexion et la publication MQTT ont été validées pendant le développement ; la construction a été testée sur ARM64. Les tests hors ligne couvrent la conservation de l’historique, les corrections, les tarifs Tempo et la sélection du logement. La détection automatique connectée et l’installation depuis le dépôt restent à confirmer sur les installations utilisatrices ; x86-64 est déclaré compatible sans le même essai matériel.
