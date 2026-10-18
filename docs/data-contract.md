# Contrat de données v0.1

CSV UTF-8 (BOM accepté), séparateur virgule, en-tête unique, un enregistrement par
commande, maximum 5 Mio / 20 000 lignes (5 000 en mode démo). Toutes les colonnes
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
Retard observé strict : livraison > promesse. L'égalité est à l'heure. Ouvert et
annulé ne sont jamais codés comme à l'heure. Les ouverts dont la promesse est
dépassée apparaissent dans les alertes, même sans modèle. Une commande future ou
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

Empreinte SHA-256 de source + mapping + option update. Le même contenu et les mêmes
options retournent le reçu initial sans réappliquer les écritures : c'est un reçu
idempotent, même si la base a changé depuis. Un nouveau contenu est réévalué.
Identifiants déjà en base : valeurs identiques = inchangé ; valeurs différentes =
conflit rejeté par défaut. `update=true` autorise le remplacement complet des champs
(les facultatifs omis deviennent null), mais `ordered_at` reste immuable et une
issue terminée ne peut pas changer de statut. Une correction livré → livré est
possible explicitement. Aucune suppression par import. Vérifier les conflits avant
de cocher le remplacement. Les écritures sont transactionnelles et sérialisées.

Les sources et modèles antérieurs restent intacts après mise à jour ; un nouveau
modèle requiert un nouvel entraînement manuel. Les métriques qualité décrivent
l'import, pas nécessairement la totalité de la base courante.
