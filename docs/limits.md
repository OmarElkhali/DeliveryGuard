# Hypothèses, limites et adoption pilote

v0.1 est un pilote local, pas une certification de production. L'installation
demande des téléchargements de dépendances/images ; l'exécution métier n'appelle
aucun service externe. Une entreprise, une devise, dates normalisées UTC, un
schéma de commande stable et des codes non personnels sont supposés.

L'utilisateur doit garantir que les features étaient connues à la commande. Les
variables facultatives absentes sont gérées, mais leur manque peut réduire le
signal. Des imports contradictoires ne sont jamais « réparés » silencieusement.
Les commandes en attente peuvent être systématiquement plus lentes ; l'évaluation
sur les seules livraisons observées reste biaisée malgré la purge temporelle.

Limites techniques : traitement en mémoire, imports plafonnés par fichier (pas de
quota total de base), une transaction d'import sérialisée et une requête de lecture
par identifiant, modèles chargés depuis disque à chaque requête, analyses et liste
des alertes sans pagination, un entraînement à la fois. Aucun benchmark de volume
ou test de charge d'entreprise n'est revendiqué. La progression représente un état
persistant, pas un pourcentage artificiel. Rafraîchissement manuel de l'interface.

Le test final est conservé hors sélection du modèle et du seuil ; la vérification
de présence de deux classes dans les splits est un contrôle de validité. Des
expériences répétées sur le même historique peuvent néanmoins conduire à une
sélection humaine indirecte sur test. Aucun monitoring de dérive ou intervalle de
confiance. Le seuil F1 de démonstration ignore les coûts métier réels. Les scores
doivent être validés sur une période ultérieure représentative avant décisions.

Sécurité/exploitation : clé partagée tous droits, pas de journal d'acteurs ni SSO,
rate limiting/TLS à fournir par le reverse proxy, sauvegardes et rétention à
organiser, secret de la base dans l'environnement des conteneurs. Pas d'import de
modèle sérialisé utilisateur. Pas de données personnelles dans le schéma ; cela
n'établit pas une conformité réglementaire automatique. Les fichiers source,
rejets et snapshots peuvent être sensibles et sont hors Git.

Avant un pilote : définir propriétaire des données, accès réseau, règle de
conservation, coûts des faux positifs/négatifs et protocole de validation ; tester
le restore dans l'infrastructure cible et mesurer volumes/résilience. Aucun
déploiement public, push Git, package publié, connexion Power BI, adoption client
ou performance sur données réelles n'est inclus sans demande distincte.

Les trois améliorations prioritaires :

1. **Validation métier réelle** : holdout futur, coûts d'intervention, analyse des
   sous-groupes et de la censure ; calibration seulement si vérifiée séparément.
2. **Accès et traçabilité** : clés/identité par acteur, rôles import/train/activation,
   journal append-only et reverse proxy HTTPS géré par l'entreprise.
3. **Mesure et reprise** : volumétrie pilote, pagination, suivi de dérive, tests de
   charge et restauration automatisée avant automatisation des entraînements.
