# Module « passage en travaux » (prototype)

Proposition d'un collègue d'ACTEE (base : commit `b094911`), intégrée à l'outil le 25/11/2026 sous la forme
d'un **3ᵉ parcours, « Passage en travaux »**, à côté de « Résultats de faisabilité » et « Diagnostic
complet ». Le diagnostic complet s'arrête à l'étape Documents, qui propose « Préparer le passage en
travaux → » ; le passage en travaux propose en retour « ← Documents du diagnostic ».

## Deux façons d'y arriver

- à partir de l'**audit en cours** (diagnostic complet ACTEE-SURYA, audit enregistré ou exemple) : depuis
  l'étape Documents, ou depuis l'écran de départ (« Passer à l'action », « À partir de l'audit en cours ») ;
- directement, à partir d'un **diagnostic existant** réalisé hors de la méthode (par exemple un diagnostic
  « plan canicule » financé par la Banque des Territoires) : mode « Passage en travaux à partir d'un
  diagnostic existant » sur l'écran de départ. L'auditeur reporte le diagnostic d'origine, quelques données
  du bâtiment (période de construction, patrimoine, ventilation, toiture) et chaque action préconisée, avec
  les locaux concernés, les locaux à confirmer, les alertes et les points de vigilance du rapport
  (`donnees["diagnostic_externe"]`, contrôlé par `travaux.valider_externe`). Les mêmes règles s'appliquent
  ensuite (niveaux, maîtrise d'œuvre, prestations préalables, CCTP). Le catalogue comprend des actions que
  la méthode SURYA ne produit pas : végétalisation de la cour, création d'une ventilation mécanique,
  rafraîchissement d'un local refuge, protections intérieures, adaptation des usages. Exemple :
  `surya/exemple_diagnostic_externe.json` (diagnostic Inddigo de l'école de Bretignolles-sur-Mer).

### Lecture du rapport par IA (facultatif)

> **Désactivée dans l'application** (`LECTURE_IA_DISPONIBLE = False` dans `app.py`) : un message indique
> qu'une solution est en cours de développement, prévue pour février 2027. Le code ci-dessous est conservé.

À l'étape « Diagnostic existant », le PDF du rapport peut être lu par l'API Claude (`surya/lecture_ia.py`) :
l'école, le bâtiment et les actions sont pré-remplis, chaque action avec un extrait du rapport et sa page,
marquée « proposée par l'IA, à vérifier ». Les préconisations sans équivalent dans le catalogue sont listées à
part. Configuration dans les secrets Streamlit (section `[anthropic]`, clé `cle`, `modele` facultatif) ; sans
clé, la saisie se fait à la main. Le rapport est envoyé au service d'IA pour l'analyse.

## Coûts

Aucun coût n'est donné pour l'instant : les ordres de grandeur ont été retirés et seront fournis par une base de
données de coûts, à brancher dans `travaux._cout`. La règle M5 (coût au-delà d'un seuil) est inactive en
attendant (`travaux.COUTS_DISPONIBLES`).

## Les quatre étapes

1. **Pré-programme** : ce que l'on propose de faire, pourquoi, où, quand et pour quel coût.
   - Chaque solution « à engager » ou « à valider » (classement du compte rendu, `rapport._bilan`) devient une
     opération à l'échelle du bâtiment, présentée par levier (protéger du soleil, toiture, décharge nocturne,
     brasseurs, charges internes, cour), avec un **niveau** A/B/C, un **horizon** 1 à 3, les **constats et
     vigilances par local** et ses **points de vigilance**.
   - L'auditeur retient ou retire chaque opération (motif obligatoire pour un retrait).
   - Vue **local par local** et PDF **pré-programme** pédagogique (`surya/rapport_preprogramme.py`).
2. **Accompagnement** :
   - **maîtrise d'œuvre en priorité** : verdict des règles M1 à M5, mise en garde sur les risques de faire
     sans, choix de l'auditeur (motif ; passage de « oui » à « non » soumis au visa) ;
   - **ingénierie** : si la collectivité n'a pas de service technique, recommandation d'une structure
     d'ingénierie du territoire ;
   - **structures à contacter** (`surya/ingenierie.py`) : à partir du code postal, l'outil cherche les
     structures qui peuvent, au moins en théorie, accompagner la commune, les place sur une carte et donne
     leurs coordonnées, avec un modèle de message. Sources interrogées en direct :
     - API Découpage administratif (geo.api.gouv.fr) : commune, département, région, intercommunalité ;
     - API Annuaire de l'administration (service-public.gouv.fr) : intercommunalité, CAUE, conseil
       départemental, Espaces conseil France Rénov', avec téléphone, courriel et site ;
     - API Recherche d'entreprises (SIRENE) : syndicat d'énergie, agence technique départementale, ALEC, SPL
       (nom et siège seulement : marqués « à vérifier ») ;
     - fichier `surya/kit/structures_ingenierie.csv`, maintenu par ACTEE : centres de ressources bâtiment
       durable, têtes de réseau, contacts vérifiés (une entrée remplace la recherche SIRENE du même type dans
       le département). Colonnes : type, perimetre (`D:18`, `R:24` ou `FR`), nom, telephone, courriel, site,
       adresse, source.
     La liste est enregistrée avec la saisie et reprise dans le PDF du pré-programme ;
   - **validation** : revue de l'auditeur et visa ; sinon, mention « projet » sur les documents.
3. **Mise en œuvre** :
   - avec maîtrise d'œuvre : **CCTP MOE** ; toutes les opérations de travaux lui sont confiées, quel que soit
     leur niveau ; la collectivité garde les actions sans travaux (occupation, équipements, réglages par le
     mainteneur, protocole de ventilation nocturne) ;
   - sans maîtrise d'œuvre : **fiches travaux** (rôle du maître d'ouvrage étape par étape, vigilances du site).
4. **Consultations** :
   - **prestations préalables** : repérage amiante et plomb (CCTP 10), diagnostic de structure (11, sans MOE),
     contrôle technique solidité et sécurité incendie (12), coordination SPS (13), diagnostic de toiture (7)
     et audit de régulation (6) ;
   - **CCTP travaux** (1 à 9) : pièces de consultation sans MOE, base transmise à la MOE sinon ;
   - archive ZIP rangée par catégorie, feuille de route du maître d'ouvrage.

Les choix sont enregistrés dans `donnees["travaux"]`, exportés et réimportés avec la saisie (contrôlés par
`travaux.valider_saisie`).

## Fichiers ajoutés

```
surya/travaux.py            opérations, niveaux, coûts, verdict MOE, feuille de route, validation
surya/cctp.py               remplissage des gabarits, conversion Word, archive ZIP
surya/rapport_travaux.py    PDF « Plan d'action — passage en travaux »
surya/rapport_preprogramme.py  PDF « Pré-programme d'adaptation à la chaleur »
surya/ingenierie.py         structures d'ingénierie locale (APIs publiques et fichier ACTEE)
surya/kit/structures_ingenierie.csv  contacts maintenus par ACTEE
surya/kit/fiches.json       fiches du kit, version condensée (étapes du MOA, vigilances)
surya/kit/cctp/cctp_N.md    gabarits des CCTP 1 à 13 et du CCTP MOE
tests/test_travaux.py       tests du module
```

## Gabarits de CCTP

Markdown simple, avec `{{variable}}`, `{{tableau:locaux|baies|espaces}}` et des blocs
`[SI condition]` … `[FIN SI]`. Conditions : `alerte CODE`, `regle CODE`, ou un indicateur (`amiante`,
`abf`, `ite`, `double_flux`, `simple_flux`, `lot1`, `lot2`, `option_bp`, `dortoir`, `motricite`,
`fenetres_toit`, `adosse`, `combles_perdus`), combinables avec ` ou `. Une variable absente devient
`[À COMPLÉTER]`, surligné en jaune dans le Word.

## Hypothèses de chiffrage (à consolider)

- Le diagnostic compte les baies sans les mesurer : 2 m² par baie et 1,2 m de casquette par baie, en
  attendant un métré.
- 1 brasseur pour 20 m² de local.
- Ombre manquante : 0,8 m² par enfant (élémentaire), 100 ou 150 m² (maternelle), ombre existante hors
  végétaux déduite.
- Prix unitaires : trois audits de 2026 (diag flash CDC, école Françoise Dolto ; maquette ACTEE et
  Inddigo, école de Sécheras). Voir `CATALOGUE` dans `surya/travaux.py`.

## Ce qui reste à faire

- Cahier des charges de maîtrise d'œuvre (version de Claire), décliné en volets façade, toiture,
  paysage, fluides.
- Consolidation des coûts unitaires avec les BE ; métré des baies dans la saisie (surface par mur).
- Champs de saisie utiles aux CCTP : espace linteau-dormant, plénum, accès nacelle, type de vitrage.
- Relecture juridique des CCTP et des mentions de responsabilité.
- Tests d'interface (AppTest, Playwright) : à relancer dans un environnement où Streamlit est installé.
