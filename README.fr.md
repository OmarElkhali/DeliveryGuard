# DeliveryGuard · v0.1.0

[![Vérifications](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml)

**Auditer les historiques de livraison et prioriser les nouvelles commandes selon leur risque de retard.**

Un pilote auto-hébergeable, une instance par entreprise, avec interface française.
Contrôler la qualité d'un CSV, analyser les retards, évaluer un modèle puis l'activer
après revue. Python · pandas · PostgreSQL · FastAPI · scikit-learn · Streamlit · Plotly.
Aucun compte externe, service payant ou clé API externe nécessaire.

**Version pilote. Exemples synthétiques uniquement ; aucune valeur prédictive réelle
ni adoption client revendiquée.** [English](README.md).

[![Ouvrir la démonstration réelle enregistrée dans le navigateur](docs/screenshots/07-risk-ranking.png)](https://raw.githubusercontent.com/OmarElkhali/DeliveryGuard/main/docs/demo.gif)

*Cliquer sur l'image pour le GIF : charger → auditer → évaluer → activer → classer.*
[Parcours illustré complet et résultats mesurés](docs/walkthrough.fr.md).

## Démarrer la démonstration

Prérequis : Docker Engine avec Compose v2 et environ 3 Go d'espace libre.

```sh
git clone https://github.com/OmarElkhali/DeliveryGuard.git
cd DeliveryGuard
docker compose --env-file .env.demo up --build -d --wait
```

Ouvrir **http://localhost:8501** et cliquer sur **Charger la démonstration**. Examiner
**Qualité** et **Analyse des livraisons**, puis créer un entraînement dans
**Modèles et évaluation**. Actualiser jusqu'à la fin, lire les résultats et limites,
puis activer soi-même la version. Dans **Commandes à surveiller**, charger
[examples/new_orders.csv](examples/new_orders.csv) et calculer les risques.

API/OpenAPI : **http://localhost:8000/docs**. Disponibilité : `/health/ready`.
Le worker séparé conserve les états queued/running/succeeded/failed en base.

```sh
# Parcours API complet, avec activation explicite du modèle :
docker compose --env-file .env.demo exec api deliveryguard smoke
# Arrêter en conservant les données :
docker compose --env-file .env.demo down
```

Les identifiants de démo sont volontairement publics et les ports restent locaux.
Le serveur accepte **uniquement l'historique fourni de 1 500 lignes, graine 42** :
les imports arbitraires et mises à jour sont refusés. Cette instance partagée
n'est pas une configuration d'hébergement public.

## Exemple de résultat

Sur le test synthétique enregistré, le modèle détecte **78 retards sur 83**, en
manque **5** et produit **79 fausses alertes**. F1 final : **0,6500** ; average
precision : **0,6522**. Cela démontre le pipeline et le coût des interventions,
sans valider une politique d'entreprise. Les scores ne sont pas des probabilités calibrées.

| Commande synthétique | Score de risque | Classe au seuil 0,20 |
|---|---:|---|
| `NEW-001` | 0,5662 | À examiner |
| `NEW-002` | 0,0749 | Priorité moindre |

[Évaluation enregistrée](docs/results/synthetic-evaluation.json) ·
[Périodes, baselines, métriques et graphiques](docs/walkthrough.fr.md#résultats-mesurés-sur-la-démonstration-synthétique).

## Utiliser des données d'entreprise

Choisir des **volumes neufs séparés**, `DG_DEMO=false` et des secrets indépendants.
Suivre le [guide entreprise](docs/walkthrough.fr.md#importer-ses-propres-données).
Retirer les colonnes personnelles et fournir les **variables réellement connues à
la commande**, dont la promesse initiale. Une mise à jour opérationnelle ne remplace
jamais cet instantané. Les corrections sont déclarées ; les instantanés contestés
sont exclus du ML.

**Installation existante :** sauvegarder avant migration. La révision `0002`
conserve les anciennes lignes, exclut leurs variables initiales non vérifiables
et désactive les anciens modèles. Voir la [procédure de mise à niveau](docs/operations.md#upgrading-from-schema-0001).

Une clé partagée donne encore tous les droits métier. Le périmètre reste un pilote
local contrôlé : identités/droits distincts, évaluation réelle autorisée et HTTPS
géré seront nécessaires pour un usage élargi en entreprise.

## Documentation

| Besoin | Guide |
|---|---|
| Captures, GIF et rapport complet | [Parcours illustré](docs/walkthrough.fr.md) |
| Schéma CSV, instantanés et corrections | [Contrat de données](docs/data-contract.md) |
| Installation Python et contrôles | [Développement et tests](docs/walkthrough.fr.md#installation-python-et-tests) |
| Vérifications exécutées et limites | [Rapport de vérification](docs/verification.md) |
| Exemples API et exports BI | [Intégration](docs/integration.md) · [Power BI](docs/power-bi.md) |
| Hypothèses du modèle | [Model card](MODEL_CARD.md) · [Limites du pilote](docs/limits.md) |
| Exploitation, sauvegardes et diagnostic | [Opérations](docs/operations.md) · [Architecture](docs/architecture.md) |

Auteur : **Omar Elkhali**, Master 2 BDIO — ENSAM Casablanca.
[GitHub](https://github.com/OmarElkhali/) · [LinkedIn](https://www.linkedin.com/in/omar-elkhali-2bb683270/).
[MIT](LICENSE) pour le code et les exemples générés, sans droits sur les datasets tiers.
[Contribuer](CONTRIBUTING.md) · [Sécurité](SECURITY.md).
