# DeliveryGuard · v0.1.0

[![Vérifications](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml)

**Auditer les historiques de livraison et prioriser les nouvelles commandes par risque de retard.**

Application auto-hébergeable, une instance par entreprise. Python, pandas, SQL,
FastAPI, PostgreSQL, scikit-learn, Streamlit et Plotly. Aucun compte externe,
service payant ou clé API externe nécessaire. L'interface est en français.
Il s'agit d'une **version pilote**, sans affirmation de maturité pour la production.
Les exemples et captures utilisent exclusivement des **données synthétiques**.

**[English](README.md) · [Parcours illustré](#parcours-illustré--du-csv-au-classement) ·
[Résultats mesurés](#résultats-mesurés-sur-la-démonstration-synthétique) ·
[Démarrage](#démonstration-locale) · [Model card](MODEL_CARD.md) ·
[Preuves de vérification](docs/verification.md)**

## Problème et démarche

Un historique de livraison peut mélanger des commandes livrées, ouvertes ou
annulées, des dates incohérentes et des identifiants en double. Entraîner directement
un modèle sur ce fichier peut donner des scores trompeurs : cible mal définie,
commandes non terminées considérées à l'heure ou informations du futur utilisées.

DeliveryGuard rend le parcours explicite : **charger → associer les colonnes →
auditer → analyser → entraîner et évaluer → activer après revue → classer**.
Les commandes ouvertes dont la promesse est dépassée restent des alertes
opérationnelles, séparées des prédictions du modèle.

![Écran d'accueil réel de DeliveryGuard avec indication du mode synthétique et étapes du parcours](docs/screenshots/01-demo.png)

### Démonstration enregistrée

Cliquer sur l'aperçu pour ouvrir la capture animée du navigateur réel : chargement,
évaluation, activation explicite et prédictions. Toutes les commandes montrées sont
synthétiques. L'aperçu reste lisible pendant le téléchargement de l'animation.

[![Ouvrir la démonstration enregistrée de DeliveryGuard](docs/screenshots/07-risk-ranking.png)](https://raw.githubusercontent.com/OmarElkhali/DeliveryGuard/main/docs/demo.gif)

## Parcours illustré — du CSV au classement

### 1. Charger un historique et associer les colonnes

Charger un CSV UTF-8, choisir le champ DeliveryGuard correspondant à chaque colonne
source, puis prévisualiser l'audit avant de confirmer l'écriture. Les colonnes
renommées sont prises en charge ; les colonnes hors schéma sont refusées pour
éviter d'archiver silencieusement des informations personnelles.

![Chargement CSV et mapping configurable des colonnes dans l'application](docs/screenshots/02-import.png)

L'historique exige `order_id`, `ordered_at`, `promised_delivery_at` et `status`.
`delivered_at` est requis pour une livraison terminée. Transporteur, zone,
catégorie, poids et montant restent facultatifs. Voir l'[exemple de mapping](examples/mapping.json)
et le [contrat de données](docs/data-contract.md).

### 2. Comprendre la qualité et télécharger les rejets

Le rapport donne les compteurs, les motifs, des exemples et des actions suggérées.
Il contrôle notamment les doublons, dates invalides, chronologies impossibles,
statuts incompatibles et nombres négatifs. Les lignes rejetées et leurs motifs
sont téléchargeables. Le fichier synthétique montré ci-dessous est valide ; cela
ne signifie pas que tous les CSV d'entreprise passeront ces contrôles.

![Rapport qualité réel : 1500 commandes synthétiques, aucun rejet et avertissement sur le biais de sélection](docs/screenshots/03-quality.png)

La source originale reste dans le volume privé. Un réimport identique retrouve le
reçu initial ; une mise à jour contradictoire exige une option explicite. Les
commandes ouvertes ou annulées ne deviennent jamais automatiquement « à l'heure ».

### 3. Analyser les retards observés et les alertes

La démonstration enregistrée contient **1 500 commandes**, **1 376 livraisons
terminées**, **84 commandes ouvertes**, **40 annulations** et **397 retards observés**.
Le taux est **397 / 1 376 = 28,85 %** : les commandes ouvertes et annulées sont
exclues de son dénominateur.

![Analyse réelle des livraisons et compteurs de la démonstration synthétique](docs/screenshots/04-analytics.png)

Une commande ouverte dépassant sa promesse apparaît dans les **alertes constatées**,
même sans modèle. Le classement ML répond à une autre question : quelles commandes
présentent un risque plus élevé d'après les seules informations connues à la commande ?

![Alertes sur les commandes ouvertes, distinctes du classement ML](docs/screenshots/06-predictions.png)

### 4. Entraîner, examiner les résultats et activer une version

L'entraînement est enregistré dans PostgreSQL puis traité par un worker local.
L'interface présente son état persistant. La fiche conserve périodes, effectifs,
paramètres des candidats, métriques, features autorisées, versions des dépendances
et empreintes du dataset et du modèle.

![Évaluation du modèle avec métriques de validation, test final et matrice de confusion](docs/screenshots/05-model.png)

L'activation exige une évaluation valable, un modèle dépassant la baseline Dummy
sur validation et une revue humaine explicite. Les limites sont affichées près de
l'action. Aucun réentraînement ni aucune activation automatique.

![Associations des variables, limites du modèle et contrôle d'activation explicite](docs/screenshots/08-model-limits.png)

### 5. Classer de nouvelles commandes et exporter les scores

Charger les informations disponibles à la commande ou appeler `/predict` et
`/predict/batch`. La réponse est triée par risque et fournit la version du modèle,
le seuil retenu et la limite du score : **ce n'est pas une probabilité calibrée**.
Le CSV de classement conserve version et seuil pour la traçabilité BI.

![Classement réel de deux commandes synthétiques, version du modèle et export CSV](docs/screenshots/07-risk-ranking.png)

| Commande exemple | Score de risque | Classe au seuil 0,20 |
|---|---:|---|
| `NEW-001` | 0,5662 | À examiner |
| `NEW-002` | 0,0749 | Priorité moindre |

Il s'agit d'exemples synthétiques mesurés, sans garantie sur la livraison. Leur
[CSV d'entrée est fourni](examples/new_orders.csv).

## Résultats mesurés sur la démonstration synthétique

Les graphiques reposent sur le [snapshot d'évaluation publié](docs/results/synthetic-evaluation.json)
du run `7af27c9c-8a80-458b-a74f-1bd88bf97cab`. Le script a comparé tous les champs
des commandes stockées au générateur déterministe de **1 500 lignes, graine 42**
avant la capture. Aucun résultat inventé ni donnée d'entreprise n'est utilisé.

### Découpage chronologique et prévention des fuites

Seules les livraisons dont l'issue est observable entrent dans la classification.
Les commandes de même instant restent dans le même split. Les issues inconnues
au début de la période suivante sont purgées : **21 livraisons** sont écartées.
Le prétraitement est ajusté sur train seulement ; modèle et seuil sont choisis sur
validation. Le test final reste hors de ces deux décisions.

| Split après purge | Commandes | Retards | Période de commande UTC |
|---|---:|---:|---|
| Train | 815 | 221 | 2024-01-01 → 2024-08-08 |
| Validation | 264 | 83 | 2024-08-09 → 2024-10-26 |
| Test final | 276 | 83 | 2024-10-27 → 2025-01-09 |

![Effectifs des splits chronologiques et répartition des retards observés](docs/results/01-chronological-split.png)

### Comparaison des candidats sur validation

Cinq candidats utilisent le même prétraitement ajusté sur train : Dummy, deux
régressions logistiques et deux Random Forest. Le choix maximise l'**average
precision sur validation**, sans utiliser le F1 du test final.

| Candidat | Average precision sur validation |
|---|---:|
| Baseline Dummy | 0,3144 |
| Régression logistique, C=0,1 | 0,7378 |
| Régression logistique, C=1 | 0,7376 |
| **Random Forest, profondeur 5 — retenu** | **0,7383** |
| Random Forest, profondeur 10 | 0,7201 |

![Comparaison des cinq candidats sur validation uniquement](docs/results/02-model-comparison.png)

Le très faible écart entre les meilleurs candidats ne prouve pas une supériorité
statistique. Cette démonstration valide le parcours de sélection ; elle ne permet
pas de recommander universellement Random Forest pour les données réelles.

### Métriques du test final et interprétation opérationnelle

Le modèle retenu est `forest_depth5`. Le seuil **0,20** maximise le F1 sur la grille
de validation documentée. Le modèle n'est pas réajusté sur validation avant le test.

| Métrique | Validation | Test final |
|---|---:|---:|
| Précision | 0,5500 | 0,4968 |
| Rappel | 0,9277 | 0,9398 |
| F1 | 0,6906 | 0,6500 |
| Average precision | 0,7383 | 0,6522 |
| ROC-AUC | 0,8589 | 0,8292 |

![Comparaison des métriques de validation et du test final au seuil fixé](docs/results/04-evaluation-metrics.png)

Sur les 276 livraisons du test, **78 retards sur 83** sont détectés, **5** sont
manqués et **79 fausses alertes** sont déclenchées sur des livraisons à l'heure.
Le rappel élevé implique donc un coût opérationnel : environ la moitié des commandes
signalées sont des faux positifs dans ce test synthétique. Une entreprise doit
définir le coût d'intervention et celui des retards manqués avant de retenir un seuil.

![Matrice du test final : 114 vrais négatifs, 79 faux positifs, 5 faux négatifs et 78 vrais positifs](docs/results/03-confusion-matrix.png)

### Importance des variables : des associations, pas des causes

L'importance par permutation est mesurée sur validation avec trois répétitions.
Le générateur introduit volontairement une association transporteur/zone que le
modèle peut retrouver. Elle ne prouve ni causalité ni transférabilité à une autre
entreprise. Les importances faibles ou négatives peuvent refléter du bruit et la
variabilité d'un échantillon limité.

![Importance par permutation sur validation, avec variabilité des trois répétitions](docs/results/05-feature-associations.png)

### Ce qui a réellement été vérifié

| Contrôle | Résultat local enregistré |
|---|---|
| Suite pytest sur PostgreSQL | **29 tests réussis**, un avertissement de dépréciation signalé |
| Lint et formatage Ruff | Réussis |
| Build, migration et démarrage Docker Compose | Réussis |
| Parcours navigateur et téléchargements | Réussis, **0 erreur console/page** |
| Recréation des conteneurs avec volumes persistants | Mêmes commandes, modèle actif et prédiction exacte |
| Sauvegarde/restauration isolée native et Docker | Mêmes effectifs, modèle actif et prédiction exacte |

Le [rapport détaillé](docs/verification.md) donne commandes, environnements et
limites. Le badge en tête renvoie à l'état actuel des exécutions GitHub Actions.
Aucune validation sur données d'entreprise, mesure de charge, connexion Power BI
Desktop ou revue de sécurité indépendante n'est revendiquée.

Pour régénérer les cinq graphiques à partir du snapshot, après installation des
dépendances de développement et d'un navigateur Playwright :

```sh
python scripts/build_report.py --snapshot
```

## Démonstration locale

Prérequis : Docker avec Compose v2 et environ 3 Go d'espace disque libre.
Depuis un terminal ; si le dépôt est déjà cloné, exécuter uniquement Compose :

```sh
git clone https://github.com/OmarElkhali/DeliveryGuard.git
cd DeliveryGuard
docker compose --env-file .env.demo up --build -d --wait
```

Ouvrir **http://localhost:8501**, cliquer sur **Charger la démonstration** puis :

1. Examiner le rapport **Qualité** et télécharger les rejets.
2. Consulter **Analyse des livraisons** : les commandes ouvertes ou annulées ne sont
   jamais comptées comme des livraisons à l'heure.
3. Dans **Modèles et évaluation**, créer un entraînement. Le worker le traite ;
   cliquer sur **Actualiser les entraînements** pour consulter son état persistant.
4. Examiner les périodes, les effectifs, les métriques et les limites. Cocher la
   confirmation de revue, puis **Activer cette version**.
5. Dans **Commandes à surveiller**, charger `examples/new_orders.csv`, calculer les
   risques et télécharger le classement. Les alertes de promesse dépassée restent séparées.

API et contrats : **http://localhost:8000/docs**.
Contrôle automatisé du parcours API, avec activation explicite par cette commande :

```sh
docker compose --env-file .env.demo exec api deliveryguard smoke
```

Arrêt conservant les volumes :

```sh
docker compose --env-file .env.demo down
```

Le fichier `.env.demo` contient des identifiants publics réservés à la démo ; les
endpoints métier n'exigent pas de clé dans ce mode explicite. Les ports sont liés
à l'interface locale. N'y importer aucune donnée d'entreprise.

## Importer ses propres données

Utiliser un projet Compose et des volumes distincts de ceux de la démonstration.
Copier `.env.example` vers `.env`, garder `DG_DEMO=false`, définir un mot de passe
PostgreSQL aléatoire et une clé `DG_API_KEY` indépendante d'au moins 32 caractères.
Génération locale possible, une fois pour chaque secret :

```sh
python -c "import secrets; print(secrets.token_hex(32))"
docker compose -p deliveryguard-company up --build -d --wait
```

Arrêter d'abord la démo si les ports sont identiques. Dans l'interface, saisir la
clé dans la barre latérale. Charger un CSV UTF-8 à virgules, associer toutes les
colonnes, prévisualiser l'audit puis valider explicitement. Les colonnes hors schéma
sont refusées : retirer noms, téléphones, emails et adresses avant import.

Les variables facultatives manquantes n'empêchent pas les fonctions de base.
Une livraison est en retard si `delivered_at > promised_delivery_at`. Le ML ne
reçoit que les informations connues au moment de la commande ; les dates de
livraison et statuts ne sont pas des features. Son score n'est pas une probabilité
calibrée. Une évaluation insuffisante bloque l'activation.

## Installation Python et tests

Python **3.12**, PostgreSQL **16**. Depuis le dépôt :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install --no-deps -e .
# Configurer .env : DG_DATABASE_URL, DG_API_KEY, DG_DEMO=false
deliveryguard migrate
uvicorn deliveryguard.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Dans deux autres terminaux utilisant le même environnement :

```sh
deliveryguard worker
streamlit run ui/app.py --server.address=127.0.0.1
```

Créer une base jetable `deliveryguard_test` puis :

```powershell
$env:DG_TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/deliveryguard_test'
ruff check .
ruff format --check .
pytest -q
# Démonstration Compose démarrée :
python -m playwright install chromium
python scripts/browser_check.py
```

Les tests vident leur base dédiée. Le contrôle navigateur produit de vraies
captures et une courte vidéo WebM dans `artifacts/video/`. Le [rapport de vérification](docs/verification.md)
distingue les commandes réellement exécutées des outils non vérifiés.

[Voir la démonstration locale enregistrée (GIF)](docs/demo.gif).
Si les téléchargements Playwright sont indisponibles : `PW_CHANNEL=chrome` utilise
Chrome installé ; `PW_NO_VIDEO=1` enregistre une véritable capture animée GIF du
navigateur sans FFmpeg, avec les mêmes vérifications du parcours.

## Documentation et limites

- [Contrat de données](docs/data-contract.md) : dates UTC, rejets, doublons, réimport et mise à jour.
- [Intégration API et Python](docs/integration.md), [architecture](docs/architecture.md).
- [Exploitation, sauvegarde et restauration](docs/operations.md), [sécurité](SECURITY.md).
- [Model card](MODEL_CARD.md), [hypothèses et limites](docs/limits.md), [Power BI](docs/power-bi.md).

Limites : une clé partagée, pas de rôles utilisateurs, 5 Mio par import, 20 000
lignes (5 000 en démo), 1 000 commandes par batch, un entraînement simultané.
Aucun réentraînement automatique. Ni performance client, ni adoption, ni expérience
professionnelle ne sont revendiquées. Pas de fichier PBIX fabriqué.

Prochaines priorités : valider les données et coûts opérationnels d'une entreprise ;
ajouter identité par acteur et journal d'audit derrière HTTPS ; mesurer volumes,
dérive et objectifs de reprise avant extension.

**Omar Elkhali** — Master 2 BDIO, ENSAM Casablanca.
[GitHub](https://github.com/OmarElkhali/) · [LinkedIn](https://www.linkedin.com/in/omar-elkhali-2bb683270/).
Licence MIT ; les droits des datasets tiers restent à vérifier par leurs utilisateurs.
