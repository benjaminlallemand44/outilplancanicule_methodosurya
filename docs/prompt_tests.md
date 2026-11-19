# Prompt — campagne de tests de l'outil méthode SURYA

> À copier tel quel dans une **nouvelle** session Claude Code ouverte sur le dépôt
> `outilplancanicule_methodosurya`, à partir de la branche `claude/laughing-faraday-kend7c`.

---

Tu es chargé de tester à fond une application avant sa diffusion à des auditeurs. Ton objectif n'est
pas de prouver qu'elle marche, mais de **trouver tout ce qui ne va pas** : erreurs, plantages,
incohérences d'interface, et surtout **résultats faux ou incohérents**. Un statut de faisabilité
faux est le défaut le plus grave : il conduirait une collectivité à engager ou écarter des travaux
à tort.

## 1. Contexte

L'application (Streamlit, Python) remplace un Excel : à partir des relevés de visite d'une école
(bâtiment, façades, locaux, espaces extérieurs), elle attribue à chaque solution de confort d'été
(brasseurs d'air, ventilation nocturne, protections solaires, toiture, charges internes, ombrage des
cours…) un statut : Recommandé, À optimiser, En place, Sous réserve, Non recommandé ou non adapté,
Non concerné. Elle produit un tableau à l'écran, un PDF « Résultats », un PDF « Compte rendu
complet » et un CSV.

L'interface est un **parcours guidé**. Au départ, on choisit « Résultats de faisabilité »
(Bâtiment → Locaux → Espaces extérieurs → Façades → Vérification → Résultats) ou « Diagnostic
complet » (Identification → Bâtiment → Locaux → Espaces extérieurs → Façades → Questionnaires
usagers → Vérification → Documents), et un mode de saisie (pas à pas ou fiches à onglets). Le
diagnostic complet intègre un **questionnaire usagers** (confort estival, Q1 à Q24) : questionnaire
en ligne (lien `?questionnaire=<code>`), import CSV au même format, saisie de questionnaires papier,
synthèse globale et **matrice de correspondance** ressenti / préconisations avec un indicateur de
cohérence. C'est une maquette : **aucune donnée n'est stockée sur un serveur** (pas de base de
données, c'est voulu ; voir `docs/supabase.md`).

Sources de vérité, par ordre de priorité :

1. `reference/methode_audit_SURYA_v01_2026-10-27.pdf` : le document de méthode (règles en
   langage clair, statuts, alertes AL / VA, principes de l'audit) ;
2. `reference/outil_aide_test_methode.xlsx` : l'Excel d'origine (onglets `Règles_Locaux`,
   `Règles_Extérieurs`, `Paramètres`) ;
3. `reference/questionnaire_confort_v01_2026-11-11.pdf` : le questionnaire usagers ;
4. `docs/points_a_trancher.md` : écarts **déjà connus** entre l'Excel, la méthode et l'outil, et
   propositions en attente de validation (dont la matrice de correspondance, § E1).
   Ne les signale pas comme nouveaux défauts ; indique seulement si l'outil fait bien ce que ce
   document annonce.

Code :

- `surya/moteur.py` : calcul (logique à trois valeurs, 1 / 0 / 0,5 ; première règle non fausse
  retenue ; donnée manquante → « Sous réserve ») ;
- `surya/questions.py` : questionnaire et conditions d'affichage ;
- `surya/rapport.py` : PDF ;
- `surya/import_excel.py` : import d'un Excel rempli ;
- `surya/questionnaire.py` : questionnaire usagers (questions, format CSV, synthèse, matrice) ;
- `surya/stockage.py` : interface de stockage des réponses (en mémoire pour la maquette) ;
- `app.py` : interface en parcours guidé ;
- `tests/` : tests existants, dont `fuzz_excel.py`, qui compare le moteur à l'Excel recalculé par
  LibreOffice.

## 2. Règles du jeu

- Travaille sur une **branche dédiée** (par exemple `tests/campagne-1`) créée à partir de
  `claude/laughing-faraday-kend7c`, pour ne pas interférer avec le développement en cours.
- **Ne corrige rien dans `surya/` ni `app.py` sans le signaler.** Ta mission est de tester et de
  documenter. Si un correctif est évident et sans ambiguïté, propose-le dans le rapport sous forme
  de diff, mais ne l'applique pas.
- Écris tous tes tests dans `tests/` (pytest pour le moteur et les PDF, Playwright pour
  l'interface), de façon qu'ils soient **rejouables**. Chaque anomalie doit avoir un test qui la
  reproduit.
- Pour chaque résultat que tu juges faux, cite la règle de la méthode (section et numéro) ou la
  ligne de l'Excel qui fonde ton attente. Si la méthode est ambiguë, classe le point en « question
  de méthode », pas en défaut.
- Chromium et Playwright sont préinstallés (`require('playwright')`) ; ne les réinstalle pas.
  LibreOffice (`soffice`) sert au recalcul de l'Excel.

## 3. Mise en route

```bash
pip install -r requirements.txt pytest
python -m pytest -q tests
python tests/fuzz_excel.py 40 1
streamlit run app.py --server.headless true --server.port 8501
```

Lis le README, le document de méthode et `docs/points_a_trancher.md` avant de commencer.

## 4. Ce qu'il faut tester

### A. Exactitude du moteur au regard de l'Excel

1. Relance `tests/fuzz_excel.py` sur plusieurs graines (au moins 5 graines × 40 tirages). Tout
   écart est un défaut majeur.
2. Vérifie que la comparaison couvre bien chaque règle : aucune règle ne doit être absente des
   tirages ou toujours fausse. Liste les règles jamais retenues.
3. Relis `corriger_classeur` (corrections apportées à l'Excel pour la comparaison) : chaque
   correction doit correspondre à un écart documenté dans `points_a_trancher.md`, et à rien d'autre.

### B. Exactitude du moteur au regard du document de méthode (le plus important)

Construis un **jeu de cas écrits à la main**, un par règle (environ 130 règles : BP, BS, VN, VM, PV,
PH, FS, FT, VV, TO, TT, CP, CA, CO, CE, CQ, EX, OA, PR, OC et toutes les alertes). Pour chaque cas :
le minimum de réponses qui doit déclencher la règle, le statut attendu, et la règle retenue attendue
(`blocs[...]["regle"]` dans le résultat du moteur). Mets-le sous forme de tableau paramétré
(pytest `parametrize`).

Ajoute ensuite :

- **Valeurs limites**, juste en dessous, pile et juste au-dessus de chaque seuil :
  - hauteur sous plafond 2,40 m et 2,60 m ; plénum 0,70 m ;
  - ratio pale-plafond / diamètre 0,15 ; rapport diamètre 0,2 et 0,4 ; entraxe 2,5 × le diamètre ;
    distance au mur égale au diamètre ;
  - distance vitrage-façade 16 cm ;
  - isolant 30 cm (toiture-terrasse et combles perdus) et 20 cm (rampants) ;
  - 6 m² par occupant (bureau) et 1,5 m² par élève (classe) ;
  - 0,8 m² par enfant ; 100 m² et 150 m² ; 5 et 6 classes de maternelle ;
  - préau : 3 m de hauteur, 2 côtés fermés, 1 côté fermé ;
  - débit de 2 volumes par heure ; effectif nul.

  Compare le sens de chaque inégalité (< ou ≤) au texte de la méthode.
- **Ordre de priorité** : des cas où plusieurs règles sont vraies à la fois. Seule la plus
  prioritaire doit être retenue.
- **Données manquantes** : pour chaque règle, la même situation avec une donnée nécessaire laissée
  vide, puis « Non évalué ». Attendu : « Sous réserve », signalé comme donnée manquante.
- **Questions masquées** : réponds à une question conditionnelle, puis change la réponse dont elle
  dépend pour la masquer (exemple : BA-05 = Présent puis Aucun, avec BA-06 et BA-09 déjà remplis).
  Une réponse devenue sans objet ne doit **jamais** influencer un statut.
- **Choix multiples contradictoires** : « Aucun » coché avec une autre option (L-10, MEX-18,
  MEX-29, MEX-36, BA-19, E-10, E-20, B-28). Décris le comportement obtenu.
- **Murs** : 0 à 4 murs ; « Aucune baie » cochée alors que des murs sont remplis ; deux murs de
  même orientation ; mur sans orientation ; baies comptées ou non comptées (« x ») ; uniquement
  des baies fixes ; uniquement des oscillo-battants.
- **Dépendances croisées** : bâtiment → locaux (patrimoine, alarme, ventilation, toiture),
  façades → locaux et espaces, locaux au RDC → alerte OA-AL1 des espaces.
- **Seuils modifiés** : changer chaque paramètre doit déplacer la limite correspondante, et
  uniquement celle-là.

### C. Invariants (tests de propriétés)

Sur des milliers de saisies aléatoires (tu peux réutiliser `tests/fuzz_excel.py::tirage`) :

- chaque solution a exactement un statut, pris parmi les six ;
- « Non concerné » n'apparaît que pour les solutions qui le prévoient (fenêtres de toit, vérandas,
  toiture, préau, ombrage de la cour) ;
- le calcul est déterministe, et ne dépend ni de l'ordre des locaux ni de leurs noms ;
- un local ne change pas les statuts d'un autre local, sauf l'alerte OA-AL1 des espaces ;
- **matrice de dépendances** : pour chaque question, fais varier sa réponse et note les solutions
  dont le statut change. Compare avec la colonne « Questions » de chaque règle de l'Excel. Toute
  dépendance inattendue, ou toute question sans effet alors qu'elle devrait en avoir, est un défaut
  à documenter (les questions marquées « info » sont normalement sans effet) ;
- répondre à une question qui manquait ne doit jamais laisser le marqueur « donnée manquante » sur
  la règle qu'elle tranche.

### D. Cohérence des sorties

Pour une dizaine de saisies variées (l'exemple de l'Excel, un cas complet, un cas presque vide,
30 locaux, des noms avec accents, apostrophes, « & », « < », emojis et textes très longs, des
seuils modifiés) :

- le tableau à l'écran, le CSV, le PDF Résultats et le PDF Compte rendu donnent **exactement les
  mêmes statuts**. Extrais le texte des PDF avec `pdftotext -layout` et compare ;
- les totaux de la synthèse du compte rendu correspondent au nombre de statuts ;
- dans le **plan d'action** :
  - « Engageable » contient uniquement des statuts Recommandé ou À optimiser sans alerte AL ;
  - « À valider » contient les statuts Sous réserve et ceux qui portent une alerte AL ;
  - « En place » et « Exclue » correspondent aux statuts du même nom ;
  - « Non concerné » n'apparaît pas ;
- les **quantités** (baies par orientation, surfaces, effectifs, hauteurs) correspondent aux
  valeurs saisies. Vérifie à la main la somme des baies ;
- la partie **Données manquantes** liste exactement les solutions « Sous réserve » dues à une donnée
  manquante, avec les bonnes questions à compléter ;
- les **alertes** listées sont exactement celles déclenchées, chacune avec son type et les bons
  locaux ou espaces ;
- les **fiches** reprennent toutes les réponses saisies, et aucune question masquée ;
- la page de garde reprend l'identification ; un seuil modifié est signalé en annexe ;
- aucune fuite technique dans les sorties : pas de `None`, `nan`, `#SO`, `#INC`, `True`, `[...]`,
  `{...}`, ni de code de règle sans libellé ;
- les PDF s'ouvrent (`pdfinfo`) et le texte ne déborde pas des tableaux. Contrôle visuellement
  quelques pages converties en images avec `pdftoppm`.

### E. Interface (Playwright, navigateur réel)

Combine les deux types d'audit (Résultats de faisabilité, Diagnostic complet) avec les deux modes de
saisie (Pas à pas, Fiches à onglets). Teste :

- le parcours complet de bout en bout, avec téléchargement des documents en fin de parcours ;
- l'impossibilité d'atteindre l'étape finale sans être passé par les étapes ; le retour en
  arrière doit conserver les données ;
- le changement de type d'audit et de mode de saisie en cours de route, sans perte de données ;
- l'apparition et la disparition des questions conditionnelles au fil des réponses ;
- l'ajout, la duplication, la suppression et le renommage de locaux et d'espaces : le bon local
  doit être modifié et les noms suivre partout ;
- l'étape Vérification : chaque bouton « Compléter » doit mener au bon bloc, et les compteurs
  doivent revenir à zéro une fois complétés ;
- les façades citées par les locaux et espaces : cochées d'office, signalées si incomplètes ;
- le menu Réglages : modification des seuils, exemple, import JSON et Excel, export, « Tout
  effacer » ;
- un **aller-retour export JSON → import** : statuts strictement identiques ;
- l'import de l'Excel de référence : les résultats doivent correspondre à l'onglet `Résultats`,
  aux écarts documentés près. Teste aussi des copies modifiées de l'Excel ;
- les imports invalides (JSON mal formé, autre Excel, fichier vide, nombres sous forme de texte) :
  un message clair, jamais de plantage ;
- les erreurs dans la console du navigateur et les exceptions Streamlit affichées à l'écran ;
- l'affichage sur téléphone (375 px de large) et sur grand écran ;
- les temps de réponse : saisie, puis génération des PDF avec 30 locaux et 5 espaces.

### F. Questionnaire usagers et matrice de cohérence

- **Import CSV** : le modèle fourni, puis des variantes : séparateur « , » ou « ; », BOM, en-têtes
  « Q4 - libellé » ou « Q4. libellé », colonnes dans le désordre ou manquantes, colonnes inconnues,
  accents et apostrophes typographiques, réponses hors liste, réponses multiples séparées par « ; »
  dont une option contient elle-même une virgule, lignes vides, fichier vide, mauvais fichier.
  Attendu : les réponses valides sont importées, les autres signalées, jamais de plantage.
- **Aller-retour** : réponse donnée sur la page usager → CSV téléchargé → import dans l'audit →
  réponse identique ; export de toutes les réponses → réimport → synthèse identique.
- **Questions conditionnelles** (Q12 à Q15, Q17) : elles apparaissent et disparaissent selon Q11, Q12
  et Q16, et une réponse masquée n'est ni conservée ni comptée.
- **Synthèse** : sur un petit jeu de 5 à 10 réponses construit à la main, recalcule chaque
  indicateur (sensation moyenne de −3 à +3, parts en %, dénominateurs) et compare à l'écran et au PDF.
- **Matrice** (§ E1 de `points_a_trancher.md`) : pour chaque croisement M1 à M8, construis des cas
  donnant chacun des résultats possibles (Cohérent, À vérifier, Non corroboré, Non évaluable).
  Teste les bornes : exactement 30 % de répondants, exactement 3 réponses, aucun local concerné.
  Vérifie le calcul de l'indicateur de cohérence. Signale toute conclusion qui te paraîtrait
  trompeuse pour un lecteur, en classant ces points en « question de méthode ».
- **Compte rendu** : la partie « Ressenti des usagers » n'apparaît qu'avec des réponses ; la
  numérotation des parties suit ; les chiffres sont ceux de l'écran.

### G. Ergonomie et cohérence des textes

Signale tout libellé ambigu, toute incohérence entre l'écran, le PDF et la méthode, toute question
posée deux fois, toute aide manquante sur une question décisive, et toute étape où l'utilisateur
ne sait pas quoi faire ensuite.

## 5. Livrables

1. Les nouveaux tests dans `tests/`, qui passent ou échouent de façon reproductible. Les tests qui
   révèlent un défaut sont marqués `xfail` avec la référence de l'anomalie.
2. Un rapport `docs/rapport_tests.md` contenant :
   - un résumé : nombre de cas exécutés, de règles couvertes, d'anomalies par gravité ;
   - un **tableau des anomalies** : identifiant ; gravité (Bloquant / Majeur / Mineur / Question
     de méthode) ; domaine (moteur, sorties, interface, import) ; description ; données d'entrée
     minimales en JSON ; attendu, avec sa source (méthode § / Excel cellule) ; obtenu ; test
     associé ; correctif proposé ;
   - la matrice de couverture des règles : chaque règle, testée ou non, et par quel cas ;
   - la matrice de dépendances questions → solutions, avec les dépendances inattendues en évidence ;
   - les points de `docs/points_a_trancher.md` vérifiés, en confirmant que l'outil se comporte
     comme annoncé ;
   - ce qui n'a pas pu être testé, et pourquoi.
3. Un commit sur la branche, avec un message clair. Pas de pull request.

Gravité :

- **Bloquant** : plantage, perte de données, statut faux sur un cas courant ;
- **Majeur** : statut faux sur un cas limite, sortie incohérente entre deux documents, alerte
  manquante ;
- **Mineur** : affichage, libellé, ergonomie ;
- **Question de méthode** : la méthode ou l'Excel ne permet pas de trancher.

Commence par la partie B, puis C, D et F : ce sont elles qui valident la cohérence des résultats.
