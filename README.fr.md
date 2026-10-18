# DeliveryGuard · v0.1.0

**Auditer les historiques de livraison et prioriser les nouvelles commandes par risque de retard.**

Application auto-hébergeable, une instance par entreprise. Python, pandas, SQL,
FastAPI, PostgreSQL, scikit-learn, Streamlit et Plotly. Aucun compte externe,
service payant ou clé API externe nécessaire. L'interface est en français.
Il s'agit d'une **version pilote**, sans affirmation de maturité pour la production.
Les exemples et captures utilisent exclusivement des **données synthétiques**.

## Démonstration locale

Prérequis : Docker avec Compose v2 et environ 3 Go d'espace disque libre.
Depuis le dossier du dépôt :

```sh
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
