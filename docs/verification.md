# Vérification locale — 18 octobre 2026

Les résultats ci-dessous proviennent d'exécutions réelles sur cette machine, avec
des données **exclusivement synthétiques**. Ils ne prouvent ni une performance
commerciale, ni une adoption, ni une maturité de production.

## Environnement exécuté

- Windows/PowerShell, Python **3.12.3**, PostgreSQL **16.1** local, dépendances
  exactes dans `requirements.txt` et `requirements-dev.txt`.
- PostgreSQL isolé du service préexistant : `127.0.0.1:55432`, cluster sous
  `../.local/postgres`, accessible seulement en loopback avec authentification
  trust **réservée à ce contrôle synthétique local**. Ce réglage de test n'est pas
  un exemple de déploiement d'entreprise et n'est pas utilisé dans Compose.
- API native `http://127.0.0.1:8001`, interface native `http://127.0.0.1:8502`,
  worker local séparé. Docker Compose utilise par défaut 8000/8501.
- Docker Desktop 4.39 / Engine 28 : **build et lancement Compose validés**, avec
  Python **3.12.12** et PostgreSQL **16.10** dans les conteneurs. Après des
  téléchargements lents, le premier démarrage a exposé une URL de base malformée
  (hôte `db` absent) ; elle a été corrigée, puis le build/démarrage et les parcours
  ont été rejoués avec succès. La validation ne repose pas seulement sur `compose config`.
- Les processus natifs API/UI/worker ont été arrêtés après vérification pour ne
  conserver qu'une démonstration principale : **Docker sur http://localhost:8501**.
  Le PostgreSQL local de test reste disponible sur 55432.

## Contrôles et résultats

| Contrôle réellement exécuté | Résultat |
|---|---|
| `ruff check .` | passé |
| `ruff format --check .` | format conforme |
| `python -m pip check` | aucune dépendance cassée |
| `pytest -q` sur PostgreSQL jetable | **29 passed**, contrôle de cohérence Alembic inclus |
| Alembic initial sur base vide | passé |
| `deliveryguard smoke` via API HTTP et worker réel | 1 500 lignes importées, audit, entraînement, activation et deux prédictions : passé |
| Playwright avec Chrome installé, serveur Streamlit réel | parcours complet passé ; **0 erreur console/page** |
| Téléchargements navigateur | rejets, commandes BI et classement réellement téléchargés |
| Redémarrage réel API + worker + PostgreSQL | 1 500 lignes, version active et prédiction exacte conservées |
| `pg_dump` puis `pg_restore` vers base isolée + archive des fichiers | mêmes effectifs, version active et prédiction exacte : passé |
| Contrôle Git des fichiers exclus | `.env`, données, dumps et modèles ignorés |
| `docker compose --env-file .env.demo config --quiet` | passé ; ne valide pas le runtime des conteneurs |
| `docker compose --env-file .env.demo up --build -d --wait` | passé ; API saine, migration terminée avec code 0, UI/worker démarrés |
| `docker compose --env-file .env.demo exec -T api deliveryguard smoke` | parcours complet passé en conteneurs ; mêmes métriques synthétiques |
| Playwright sur API 8000 / UI 8501 Docker | parcours complet et téléchargements passés ; 0 erreur console/page |
| `compose down` sans suppression des volumes puis `up -d --wait` | effectifs, version active et prédiction exacte conservés |
| Sauvegarde Docker documentée puis restauration dans projet isolé `deliveryguard-restore` | dump et archive restaurés ; même version et prédiction exacte via API sur 8004 |

Un avertissement de dépréciation Starlette subsiste dans les tests : le client
`httpx` est encore accepté mais sa migration future vers `httpx2` est annoncée.
Il n'a pas été filtré ou masqué. Aucun échec de test ne reste sur la suite finale.
Les tests couvrent import valide/malformé, champs/mapping, doublons/réimport et
mises à jour, chronologie, nombres/statuts, ouverts/annulés, authentification,
volume insuffisant et cible mono-classe, absence de features de fuite,
entraînement avec/sans variables facultatives, activation, prédiction unitaire et
batch/catégories inconnues, verrou worker et reprise d'un job interrompu,
intégrité des modèles, contrat OpenAPI et exports avec protection des formules.

## Résultat ML synthétique réellement mesuré

Générateur : 1 500 lignes, graine 42. 1 376 livraisons observées, 84 ouvertes et
40 annulées. 397 livraisons en retard. Aucun résultat client ou donnée réelle.

| Split après purge | Effectif | Retards | Période de commande UTC |
|---|---:|---:|---|
| Train | 815 | 221 | 2024-01-01 00:00 → 2024-08-08 12:00 |
| Validation | 264 | 83 | 2024-08-09 18:00 → 2024-10-26 06:00 |
| Test | 276 | 83 | 2024-10-27 00:00 → 2025-01-09 18:00 |

21 livraisons ont été purgées parce que leur issue n'était pas encore connue au
début du split suivant. Modèle choisi sur validation : `forest_depth5`. Seuil choisi
sur validation : **0,20**. Test final : précision **0,496815**, rappel **0,939759**,
F1 **0,65**, average precision **0,652236**, ROC-AUC **0,829203**. Matrice de confusion
`[[114,79],[5,78]]`, lignes = réel à l'heure/retard, colonnes = prédit à l'heure/retard.
Ce seuil privilégie le rappel et produit de nombreux faux positifs ; il ne
représente pas une politique d'intervention métier validée. Score non calibré.

## Reproduire les contrôles dans ce workspace

Depuis `D:\SetupGame\Desktop\DATA ECOMERCE PROJECT\deliveryguard` ; l'environnement
Python créé pour cette session se trouve dans `..\.venv` :

```powershell
$env:DG_TEST_DATABASE_URL='postgresql+psycopg://deliveryguard@127.0.0.1:55432/deliveryguard_test'
..\.venv\Scripts\ruff.exe check .
..\.venv\Scripts\ruff.exe format --check .
..\.venv\Scripts\python.exe -m pytest -q
# .env privé local contient l'URL de l'API native et DG_DEMO=true.
..\.venv\Scripts\python.exe -m deliveryguard.cli smoke
$env:DG_API_URL='http://127.0.0.1:8001'
$env:DG_UI_URL='http://127.0.0.1:8502'
$env:PW_CHANNEL='chrome'
$env:PW_NO_VIDEO='1'
..\.venv\Scripts\python.exe scripts/browser_check.py
```

Pour redémarrer les processus natifs, utiliser trois terminaux avec ce même `.env` :

```powershell
..\.venv\Scripts\python.exe -m uvicorn deliveryguard.api:app --host 127.0.0.1 --port 8001 --no-access-log
..\.venv\Scripts\python.exe -m deliveryguard.cli worker
..\.venv\Scripts\python.exe -m streamlit run ui/app.py --server.address=127.0.0.1 --server.port=8502
```

Ces trois commandes sont trois processus longs distincts. La base locale doit
être démarrée. La procédure portable pour un nouveau clone est dans les README.
Le test de persistance peut être rejoué : `python scripts/check_persistence.py
record`, redémarrage réel des services, puis `python scripts/check_persistence.py
verify`. Ne lancer ni nouvel entraînement/activation ni import entre les deux.

## Preuves visuelles et limites de vérification

[Huit captures réelles](screenshots/), [cinq graphiques de résultats](results/) et
[capture animée GIF réelle](demo.gif). Les graphiques reposent sur
`results/synthetic-evaluation.json` ; `scripts/build_report.py` vérifie les champs
de la base contre le générateur synthétique avant de capturer un nouveau snapshot.
L'option `--snapshot` régénère les graphiques sans dépendre de l'API locale.
Le téléchargement de Chromium/FFmpeg a échoué (timeouts, DNS/ECONNRESET) ; le
contrôle a utilisé Chrome installé et son screencast CDP, encodé en GIF avec Pillow.
Aucune vidéo WebM n'est revendiquée. Les CSV téléchargés et résultats JSON détaillés
locaux sont sous `artifacts/`, volontairement hors Git, dont
`docker-smoke-result.json`, `docker-persistence-result.json` et
`docker-restore-result.json`. Les sauvegardes sont sous `backups/`, également
ignoré. La GIF et les PNG finaux montrent l'instance Docker et ne contiennent que
la démonstration synthétique.

Les exécutions hébergées sont consultables dans
[GitHub Actions](https://github.com/OmarElkhali/DeliveryGuard/actions).
Les résultats détaillés ci-dessus décrivent les contrôles locaux datés, distincts
du statut CI courant affiché dans les README. Power BI Desktop,
la connexion d'une vraie entreprise, HTTPS/reverse proxy, charge, tests de sécurité
indépendants et déploiement public ne sont pas validés. Les restaurations native
et Docker ont été réellement vérifiées ; cela ne mesure pas un RPO/RTO d'entreprise.
Ces contrôles locaux ont précédé la publication initiale du dépôt.
