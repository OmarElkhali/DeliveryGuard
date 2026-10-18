# DeliveryGuard ? v0.1.0

[![V?rifications](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml)

**Auditer les historiques de livraison et prioriser les nouvelles commandes selon leur risque de retard.**

Un pilote auto-h?bergeable, une instance par entreprise, avec interface fran?aise.
Contr?ler la qualit? d'un CSV, analyser les retards, ?valuer un mod?le puis l'activer
apr?s revue. Python ? pandas ? PostgreSQL ? FastAPI ? scikit-learn ? Streamlit ? Plotly.
Aucun compte externe, service payant ou cl? API externe n?cessaire.

**Version pilote. Exemples synth?tiques uniquement ; aucune valeur pr?dictive r?elle
ni adoption client revendiqu?e.** [English](README.md).

[![Ouvrir la d?monstration r?elle enregistr?e dans le navigateur](docs/screenshots/07-risk-ranking.png)](https://raw.githubusercontent.com/OmarElkhali/DeliveryGuard/main/docs/demo.gif)

*Cliquer sur l'image pour le GIF : charger ? auditer ? ?valuer ? activer ? classer.*
[Parcours illustr? complet et r?sultats mesur?s](docs/walkthrough.fr.md).

## D?marrer la d?monstration

Pr?requis : Docker Engine avec Compose v2 et environ 3 Go d'espace libre.

```sh
git clone https://github.com/OmarElkhali/DeliveryGuard.git
cd DeliveryGuard
docker compose --env-file .env.demo up --build -d --wait
```

Ouvrir **http://localhost:8501** et cliquer sur **Charger la d?monstration**. Examiner
**Qualit?** et **Analyse des livraisons**, puis cr?er un entra?nement dans
**Mod?les et ?valuation**. Actualiser jusqu'? la fin, lire les r?sultats et limites,
puis activer soi-m?me la version. Dans **Commandes ? surveiller**, charger
[examples/new_orders.csv](examples/new_orders.csv) et calculer les risques.

API/OpenAPI : **http://localhost:8000/docs**. Disponibilit? : `/health/ready`.
Le worker s?par? conserve les ?tats queued/running/succeeded/failed en base.

```sh
# Parcours API complet, avec activation explicite du mod?le :
docker compose --env-file .env.demo exec api deliveryguard smoke
# Arr?ter en conservant les donn?es :
docker compose --env-file .env.demo down
```

Les identifiants de d?mo sont volontairement publics et les ports restent locaux.
Le serveur accepte **uniquement l'historique fourni de 1 500 lignes, graine 42** :
les imports arbitraires et mises ? jour sont refus?s. Cette instance partag?e
n'est pas une configuration d'h?bergement public.

## Exemple de r?sultat

Sur le test synth?tique enregistr?, le mod?le d?tecte **78 retards sur 83**, en
manque **5** et produit **79 fausses alertes**. F1 final : **0,6500** ; average
precision : **0,6522**. Cela d?montre le pipeline et le co?t des interventions,
sans valider une politique d'entreprise. Les scores ne sont pas des probabilit?s calibr?es.

| Commande synth?tique | Score de risque | Classe au seuil 0,20 |
|---|---:|---|
| `NEW-001` | 0,5662 | ? examiner |
| `NEW-002` | 0,0749 | Priorit? moindre |

[?valuation enregistr?e](docs/results/synthetic-evaluation.json) ?
[P?riodes, baselines, m?triques et graphiques](docs/walkthrough.fr.md#r?sultats-mesur?s-sur-la-d?monstration-synth?tique).

## Utiliser des donn?es d'entreprise

Choisir des **volumes neufs s?par?s**, `DG_DEMO=false` et des secrets ind?pendants.
Suivre le [guide entreprise](docs/walkthrough.fr.md#importer-ses-propres-donn?es).
Retirer les colonnes personnelles et fournir les **variables r?ellement connues ?
la commande**, dont la promesse initiale. Une mise ? jour op?rationnelle ne remplace
jamais cet instantan?. Les corrections sont d?clar?es ; les instantan?s contest?s
sont exclus du ML.

**Installation existante :** sauvegarder avant migration. La r?vision `0002`
conserve les anciennes lignes, exclut leurs variables initiales non v?rifiables
et d?sactive les anciens mod?les. Voir la [proc?dure de mise ? niveau](docs/operations.md#upgrading-from-schema-0001).

Une cl? partag?e donne encore tous les droits m?tier. Le p?rim?tre reste un pilote
local contr?l? : identit?s/droits distincts, ?valuation r?elle autoris?e et HTTPS
g?r? seront n?cessaires pour un usage ?largi en entreprise.

## Documentation

| Besoin | Guide |
|---|---|
| Captures, GIF et rapport complet | [Parcours illustr?](docs/walkthrough.fr.md) |
| Sch?ma CSV, instantan?s et corrections | [Contrat de donn?es](docs/data-contract.md) |
| Installation Python et contr?les | [D?veloppement et tests](docs/walkthrough.fr.md#installation-python-et-tests) |
| V?rifications ex?cut?es et limites | [Rapport de v?rification](docs/verification.md) |
| Exemples API et exports BI | [Int?gration](docs/integration.md) ? [Power BI](docs/power-bi.md) |
| Hypoth?ses du mod?le | [Model card](MODEL_CARD.md) ? [Limites du pilote](docs/limits.md) |
| Exploitation, sauvegardes et diagnostic | [Op?rations](docs/operations.md) ? [Architecture](docs/architecture.md) |

Auteur : **Omar Elkhali**, Master 2 BDIO ? ENSAM Casablanca.
[GitHub](https://github.com/OmarElkhali/) ? [LinkedIn](https://www.linkedin.com/in/omar-elkhali-2bb683270/).
[MIT](LICENSE) pour le code et les exemples g?n?r?s, sans droits sur les datasets tiers.
[Contribuer](CONTRIBUTING.md) ? [S?curit?](SECURITY.md).
