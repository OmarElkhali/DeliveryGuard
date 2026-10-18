# Contrat de données v0.1

CSV UTF-8 (BOM accepté), séparateur virgule, en-tête unique, un enregistrement par
commande, maximum 5 Mio / 20 000 lignes. En démo, seul le fichier fourni de 1 500
lignes, graine 42, est accepté (plafond de parsing : 5 000). Toutes les colonnes
sources doivent être mappées une seule fois vers un champ reconnu. Les colonnes
hors schéma sont refusées, y compris celles qui seraient simplement ignorées.
`examples/mapping.json` est un exemple source → canonique.

| Champ | Historique | Prédiction | Règle |
|---|---|---|---|
| order_id | obligatoire | obligatoire | chaîne non vide, 128 caractères maximum |
| ordered_at | obligatoire | obligatoire | ISO 8601, date de commande passée ou présente |
| promised_delivery_at | obligatoire | obligatoire | >= ordered_at |
| delivered_at | requis seulement si livré | interdit | nullable sinon ; >= ordered_at et <= maintenant |
| status | obligatoire | interdit | open, delivered, cancelled (minuscules exactes) |
| carrier | facultatif | facultatif | code/catégorie, <=128 caractères, connu à la commande |
| destination_zone | facultatif | facultatif | zone agrégée, jamais une adresse |
| product_category | facultatif | facultatif | catégorie connue à la commande, <=128 caractères |
| weight_kg | facultatif | facultatif | nombre fini >=0, point décimal |
| order_amount | facultatif | facultatif | nombre fini >=0, même devise pour toute l'instance |

Les chaînes sont nettoyées de leurs espaces externes ; les cellules facultatives
vides deviennent null. Aucun zéro n'est substitué à une donnée source manquante.
Les catégories manquantes sont imputées à `missing` dans le pipeline ; médiane
numérique calculée sur train seulement, zéro sklearn si la colonne train est
entièrement vide. Les catégories inconnues sont acceptées par OneHotEncoder.

## Temps et issues

Dates admises : `2025-01-31`, `2025-01-31T10:30:00`, `2025-01-31T10:30:00Z`,
`2025-01-31T11:30:00+01:00`. Sans offset signifie **UTC**, une date seule signifie
minuit UTC. Les dates ambiguës telles que `01/02/2025`, les timestamps numériques,
les noms de fuseau et les secondes intercalaires sont refusés. Stockage en
PostgreSQL `timestamptz`, normalisation UTC. Convertir les exports locaux en amont,
avec leur décalage historique ; ne pas supposer un offset fixe pour Casablanca.

`delivered` exige `delivered_at`. `open` et `cancelled` interdisent cette date.
Retard observé strict : livraison > **promesse initiale**. L'égalité est à l'heure. Ouvert et
annulé ne sont jamais codés comme à l'heure. Les ouverts dont la promesse est
opérationnelle actuelle dépassée apparaissent dans les alertes, même sans modèle. Une commande future ou
une livraison future prétendue observée est rejetée, sans correction silencieuse.

## Rejets et import

Erreurs de structure (encodage, CSV malformé, colonnes absentes/dupliquées,
mapping incomplet) : rejet de tout le fichier, HTTP 422, aucune écriture.
Erreurs métier : rejet de la ligne ; le reste peut être importé après confirmation.
Les motifs détaillent les champs et règles, avec numéro de ligne logique (en-tête = 1).
Les exemples sont limités à cinq dans le rapport ; le CSV de rejet contient toutes
les lignes rejetées et leurs motifs. Si plusieurs occurrences d'un identifiant
existent dans **le fichier**, toutes sont rejetées, même si elles sont identiques.

La prévisualisation ne conserve rien. L'import confirmé conserve le fichier source
original et les rejets dans le volume privé, hors Git. Un import sans ligne valide
peut être conservé via API pour son audit ; l'interface empêche sa confirmation.
Les exports destinés aux tableurs préfixent les cellules commençant par un signe
de formule avec une apostrophe. La source privée reste byte pour byte identique.

## Réimport et mise à jour

Empreinte SHA-256 de source + mapping + option update + correction_code + version
de la politique d'instantané. Le même contenu et les mêmes
options retournent le reçu initial sans réappliquer les écritures : c'est un reçu
idempotent, même si la base a changé depuis. Un nouveau contenu est réévalué.
Identifiants déjà en base : valeurs identiques = inchangé ; valeurs différentes =
conflit rejeté par défaut. `update=true` autorise une évolution **opérationnelle**
des colonnes courantes (facultatifs omis = null) ; `ordered_at` reste immuable et
une issue terminée ne peut pas changer de statut. Cela ne remplace jamais les
variables connues à la commande ni la promesse initiale.

Au premier import accepté, tous les champs de `NewOrder` sont copiés dans
`initial_snapshot` : dates de commande/promesse, transporteur, zone, catégorie,
poids et montant, y compris les nulls. Un trigger PostgreSQL interdit tout
remplacement de cet instantané, même via une écriture SQL directe. L'entreprise
doit fournir les valeurs réellement disponibles à la commande : le logiciel ne
peut pas reconstruire une promesse déjà écrasée dans son ERP avant le premier import.
Les features ML proviennent de cet instantané ; seules l'issue et la date de
livraison suivent les mises à jour. Le taux global utilise également cette
promesse et ce transporteur initiaux. L'audit qualité d'un CSV décrit ses valeurs
sources courantes, pas une réévaluation ML de la base entière.

Pour une **correction de données**, fournir `update=true` et `correction_code`,
un code de 3 à 64 caractères `[A-Z][A-Z0-9_]{2,63}`, par exemple `STATUS_ERROR`.
Pas de texte libre personnel. Le reçu et la source immuable consignent cette
correction ; elle peut rectifier un statut terminal erroné ou sa date de livraison.
Ces deux changements sont refusés en mise à jour opérationnelle simple. Si les champs
d'entrée de cette correction diffèrent de l'instantané, celui-ci est contesté :
la commande est exclue des futurs entraînements et du taux de retard initial.
Cette exclusion est irréversible dans l'API et protégée en base ; le logiciel ne
substitue pas une valeur corrigée tardivement à une ancienne prédiction.
Le modèle déjà actif reste une version historique : réévaluer manuellement après
une correction importante. Aucun acteur individuel n'est identifié par la clé partagée.

`GET /orders/{order_id}/initial-snapshot` expose les valeurs conservées et leur
éligibilité. Les exports distinguent les colonnes opérationnelles, `initial_*`,
`initial_snapshot_eligible` et `observed_late`. Ce dernier reste null pour une
issue non livrée, un ancien instantané absent ou un instantané contesté.

Aucune suppression par import. Les écritures sont transactionnelles et sérialisées.
La prévisualisation ne modifie ni état courant ni instantané ni éligibilité.
En démo, les mises à jour et corrections sont refusées côté serveur, y compris CLI.

Les sources et modèles antérieurs restent intacts après mise à jour ; un nouveau
modèle requiert un nouvel entraînement manuel. Les métriques qualité décrivent
l'import, pas nécessairement la totalité de la base courante.

La migration `0002` laisse les instantanés des lignes anciennes à null : les
valeurs déjà modifiables ne constituent pas une preuve du passé. Elle désactive
les anciens modèles sans supprimer leurs rapports. Voir [la mise à niveau](operations.md#upgrading-from-schema-0001).
