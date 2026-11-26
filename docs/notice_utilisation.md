# Notice d'utilisation — outil d'audit de faisabilité d'actions d'adaptation

Outil de test de la méthode SURYA Ingénierie / ACTEE (plan rafraîchissement des écoles). **Maquette** :
il sert à éprouver la méthode SURYA et le parcours de saisie, pas encore à conduire des audits officiels.

## Vos données

- La saisie (bâtiment, locaux, espaces, questionnaires usagers, photos) reste **en mémoire pendant votre
  session** sur le serveur de l'application. Elle n'est écrite ni sur disque ni en base de données et
  disparaît quand l'onglet est fermé ou la session expire.
- Pour la conserver : **Réglages → Exporter la saisie** (fichier JSON, ou ZIP si vous avez ajouté des
  photos), puis réimportez-la plus tard.
- Si la base de données est activée et que vous êtes connecté, l'audit est enregistré dans votre espace
  (hébergé à Paris) à chaque changement d'étape ; vous seul y avez accès. Les réponses au questionnaire
  en ligne sont anonymes.
- Ne saisissez pas de données personnelles inutiles (noms d'élèves, coordonnées). Évitez de
  photographier des personnes : les visages détectés sur les photos sont floutés automatiquement, mais
  la détection n'est pas infaillible.

- Passage en travaux : la recherche des structures d'ingénierie interroge des services publics (API
  Découpage administratif, Annuaire de l'administration, Recherche d'entreprises) avec le code postal de la
  commune. La lecture automatique d'un rapport de diagnostic par IA n'est pas encore disponible : une solution
  est en cours de développement, prévue pour février 2027.

## Combien de temps vos données sont conservées

Avec la base de données (compte connecté) :

- **audits et photos** : 3 ans après la dernière modification ; ouvrir un audit le conserve 3 ans de plus, et la
  date de suppression prévue est affichée dans « Vos audits enregistrés » ;
- **questionnaire en ligne** : ouvert 90 jours ; les réponses brutes sont conservées 12 mois ;
- **comptes** : supprimés après 3 ans sans connexion, avec leurs audits.

Les suppressions sont automatiques, une fois par semaine.

## Hébergement et mesure d'audience

L'application est hébergée gratuitement sur **Streamlit Community Cloud** (société Snowflake, traitement
possible hors de l'Union européenne). Cette plateforme ajoute à chaque page ses propres outils de mesure
d'audience (**Google Tag Manager** et **Segment**) et un passage par son service d'authentification
(share.streamlit.io). L'outil lui-même n'envoie aucune donnée à des tiers et sa télémétrie Streamlit est
désactivée, mais il n'a pas la main sur ces traceurs. Avant tout usage institutionnel, prévoir un
hébergement maîtrisé et une notice RGPD complète.

## Lien avec l'Excel de la méthode SURYA

L'outil reprend toutes les formules de l'Excel « Outil d'aide au test de la méthode d'audit de
faisabilité d'actions d'adaptation » (règles du 27/10/2026). Il donne **les mêmes résultats**, sauf là où
l'Excel contient des erreurs de références, corrigées dans l'outil :

| Écart | Effet |
|---|---|
| Murs extérieurs 2, 3 et 4 lus une ligne trop bas dans l'Excel | protections solaires et ventilation naturelle des locaux à plusieurs murs |
| MEX-17 (commande des baies en plafond) en `#REF!` | règle FT-7 des fenêtres de toit |
| BA-18 (débit de ventilation) sans ligne de saisie | règles VM-7, VM-9, VM-10 |
| Valeurs pile sur un seuil ou nulles (surface, hauteur, diamètre) | arrondi avant comparaison ; valeur nulle traitée comme invalide (« Sous réserve ») |

Sur l'exemple fourni dans l'Excel, **quatre statuts** diffèrent pour ces raisons. Avec ses références
réparées, l'Excel recalculé donne exactement les résultats de l'outil (vérifié sur 3 000 cas tirés au
hasard). Détail : document « Points à trancher », partie A.

## Ce que l'outil ajoute à la méthode SURYA (propositions à valider)

- le type des alertes : AL (étude de maîtrise d'œuvre) ou VA (validation ponctuelle) ;
- la matrice de correspondance entre le questionnaire usagers et les résultats de la visite ;
- l'ordre de mise en œuvre en trois étapes et le classement des solutions principales ;
- le plan simplifié de l'établissement.

Ces choix sont décrits dans « Points à trancher » (parties D, E et G).

## Version

Le numéro de version et le commit déployé sont affichés en bas de chaque page de l'application.
