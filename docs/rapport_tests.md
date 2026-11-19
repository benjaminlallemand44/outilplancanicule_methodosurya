# Rapport de la campagne de tests n° 1 — outil méthode SURYA

Campagne menée le 19/11/2026 sur la branche `claude/fervent-hopper-qeizm3`, créée à partir de
`claude/laughing-faraday-kend7c` (commit `47b6b72`). Aucun fichier de `surya/` ni `app.py` n'a été
modifié : les correctifs sont proposés sous forme de diff (§ 7).

Sources de vérité, par ordre de priorité : méthode v01 du 27/10/2026 (« méthode », numéros de règle
§ III.x.y-n), Excel `outil_aide_test_methode.xlsx` (« Excel »), questionnaire v01 du 11/11/2026,
`docs/points_a_trancher.md` (« PàT »).

## 1. Résumé

| | |
|---|---|
| Tests écrits (fichiers `tests/test_*.py` + script Playwright) | **890 cas** exécutés par pytest (845 réussis), dont **45 « xfail »** qui reproduisent chacun une anomalie (`strict=True` : ils échouent tant que le défaut existe et signaleront sa correction) |
| Comparaison à l'Excel recalculé (LibreOffice) | 5 graines × 40 tirages (2 000 locaux, 1 000 espaces) : **0 écart** ; 5 cas pile sur un seuil : **5 cas en écart** (ANO-01, ANO-09) |
| Règles couvertes par un cas écrit à la main | **132 / 134** (121 règles + 13 alertes) ; VM-9 : statut vérifié mais règle jamais retenue ; VM-11 : inatteignable avec des données valides (QM-01) |
| Invariants vérifiés sur saisies aléatoires | 1 500 saisies (statuts, « Non concerné »), 300 (ordre, noms, indépendance des locaux), 400 (questions masquées, marqueur « donnée manquante »), matrice de dépendances sur 250 saisies |
| Interface | 4 combinaisons type d'audit × mode de saisie (AppTest) ; 7 scénarios dans Chromium réel (Playwright) : parcours, téléchargements, téléphone 375 px, écran 2560 px, 30 locaux / 5 espaces, questionnaire en ligne |

| Gravité | Nombre | Anomalies |
|---|---|---|
| **Bloquant** | 4 | ANO-26 (plantage import CSV), ANO-30 (plantage éditeur), ANO-07 (plantage Réglages + seuil ignoré), ANO-31 (données modifiées à l'affichage) |
| **Majeur** | 8 | ANO-01 (seuils en virgule flottante), ANO-02 (volume nul → « Recommandé »), ANO-10, ANO-17, ANO-19, ANO-20, ANO-22, ANO-27 |
| **Mineur** | 25 | ANO-03 à 06, 08, 09, 11 à 16, 18, 21, 23 à 25, 28, 29, 32 à 37 |
| **Question de méthode** | 10 | QM-01 à QM-10 |

**Aucun statut faux n'a été trouvé sur un cas courant** : les 174 cas « une règle » (plus 25 cas d'alertes),
les 73 bornes, les 26 priorités, les 214 cas de données manquantes et les 20 cas de questions masquées donnent le statut et la règle attendus par la méthode,
et le moteur est identique à l'Excel corrigé sur 3 000 entités tirées au hasard. Les statuts faux
trouvés sont des **cas limites** :

- **ANO-01** : une valeur pile sur un seuil calculé (2 vol/h, ratio 0,15, rapport 0,4, 0,8 m²/enfant)
  peut basculer du mauvais côté à cause de l'arithmétique flottante. Exemple réaliste : 243 m³/h pour
  45 m² × 2,70 m = 2 vol/h exactement → « Sous réserve » au lieu de « En place ». L'Excel donne le bon
  résultat.
- **ANO-02** : une surface ou une hauteur saisie à 0 donne « Recommandé » en ventilation mécanique (c'est
  d'ailleurs la seule façon d'obtenir ce statut, voir QM-01).

Les défauts les plus gênants avant diffusion sont du côté des **imports** (CSV du questionnaire : ANO-17,
ANO-20, ANO-26 ; JSON / Excel : ANO-07, ANO-27, ANO-30, ANO-31) et de **deux incohérences entre
documents** (ANO-10 : EX-AL absente du CSV ; ANO-28 : la documentation annonce un seul écart avec l'Excel
sur l'exemple, il y en a quatre).

### Rejouer la campagne

```bash
pip install -r requirements.txt pytest pdfplumber
```

```bash
python -m pytest tests -m "not excel and not interface"
```

```bash
python -m pytest tests -m "excel or interface"
```

```bash
for g in 1 2 3 4 5; do python tests/fuzz_excel.py 40 $g; done
```

```bash
python tests/couverture_regles.py
```

```bash
python tests/matrice_dependances.py 250
```

Le marqueur `excel` demande LibreOffice ; `interface` demande Node et le Playwright préinstallé
(`tests/interface_playwright.js`, lancé par `tests/test_interface_playwright.py`). `pdfplumber` sert à
lire les tableaux des PDF (en complément de `pdftotext -layout`).

### Fichiers de tests ajoutés

| Fichier | Partie | Contenu |
|---|---|---|
| `tests/cas_base.py` | B, C, D | profils « sans contrainte » écrits à la main et fonctions utilitaires |
| `tests/test_regles_methode.py` | B | un cas par règle (174 cas paramétrés), 25 cas d'alertes |
| `tests/test_cas_limites.py` | B | bornes, priorités, données manquantes (« vide » et « Non évalué »), questions masquées, choix contradictoires, murs, dépendances croisées |
| `tests/test_invariants.py` | B, C | invariants, matrice de dépendances, marqueur « donnée manquante », seuils modifiés |
| `tests/matrice_dependances.py` | C | calcul de la matrice questions → solutions |
| `tests/couverture_regles.py` | B | matrice de couverture des règles |
| `tests/test_sorties.py`, `tests/sorties.py` | D | écran / CSV / PDF Résultats / PDF Compte rendu, plan d'action, quantités, données manquantes, alertes, fiches, fuites, débordements |
| `tests/test_questionnaire_usagers.py` | F | import CSV, aller-retour, conditions, synthèse, matrice M1 à M8 |
| `tests/test_excel.py` | A | `corriger_classeur`, import de l'Excel de référence, bornes recalculées par LibreOffice, fuzz court |
| `tests/test_interface_apptest.py` | E | interface pilotée par `streamlit.testing.v1.AppTest` |
| `tests/test_interface_playwright.py`, `tests/interface_playwright.js` | E | navigateur réel |
| `tests/test_points_a_trancher.py` | — | comportements annoncés par PàT |
| `tests/conftest.py` | — | marqueurs `excel` et `interface` |

## 2. Anomalies

Les données d'entrée sont données en JSON minimal ; « base » désigne les profils de `tests/cas_base.py`
(bâtiment, façades, un local et un espace « sans contrainte »).

### 2.1 Bloquant

| Id | Domaine | Description | Entrée minimale | Attendu (source) | Obtenu | Test |
|---|---|---|---|---|---|---|
| ANO-26 | import | Plantage de l'import CSV du questionnaire (`csv.Error` non rattrapée, trace Python affichée) sur un fichier à fins de ligne CR seules (« CSV (Macintosh) » d'Excel) ou sur un fichier binaire renommé `.csv` (classeur, PDF). | fichier `Q4;Q5\rChaude;Confortable\r` | Réponses importées, ou message clair (consigne F : « jamais de plantage ») | `_csv.Error: new-line character seen in unquoted field` | `test_questionnaire_usagers.py::test_import_sans_plantage` |
| ANO-30 | interface / import | Une saisie importée (JSON, Excel) avec une valeur hors des bornes d'un champ numérique fait planter l'éditeur dès qu'on ouvre la fiche : E-30 > 4, ou toute valeur négative. | `{"espaces":[{"E-01":"Cour","E-02":["Préau"],"E-30":5}]}` puis « Modifier » | Fiche affichée, valeur signalée | `StreamlitAPIException: The value 5 is greater than the max_value 4` | `test_interface_apptest.py::test_import_valeur_hors_bornes_ne_fait_pas_planter_l_editeur` |
| ANO-07 | moteur / import | Un seuil importé sous forme de texte (`"parametres": {"P_HSP_MIN": "2,4"}`) : (1) l'onglet « Seuils des règles » plante ; (2) dans le moteur, toutes les comparaisons qui l'utilisent lèvent `TypeError`, rattrapée par `calcul` et traduite en « règle fausse » : statuts faux sans avertissement. | base + `{"locaux":[{"PL-03":2.2}], "parametres":{"P_HSP_MIN":"2,4"}}` | BS-1 « Non recommandé » (méthode III.a.ii-1) ou refus du seuil | BS-7 « Recommandé » ; Réglages : `could not convert string to float: '2,4'` | `test_invariants.py::test_seuil_texte_refuse_ou_converti`, `test_interface_apptest.py::test_import_seuil_texte_reglages` |
| ANO-31 | interface | Ouvrir la fiche d'un local ou d'un espace importé modifie silencieusement ses données : nombre décimal tronqué dans un champ entier (effectif 25,5 → 25), réponse absente de la liste effacée (« Salle de classe » pour L-02), mur vide ajouté. L'export JSON suivant n'est plus celui importé. | `{"locaux":[{"L-01":"A","L-04":25.5,"L-02":"Salle de classe"}]}` puis « Modifier » | Données inchangées tant que l'utilisateur ne les touche pas | L-04 = 25, L-02 supprimée, `murs: [{}]` | `test_interface_apptest.py::test_afficher_une_fiche_ne_modifie_pas_les_donnees` |

Les trois derniers demandent un fichier importé hors normes (JSON retouché, Excel saisi hors des listes) ;
ils sont classés Bloquant selon la grille (plantage, perte de données), mais aucun ne survient en saisie
normale dans l'interface.

### 2.2 Majeur

| Id | Domaine | Description | Entrée minimale | Attendu (source) | Obtenu | Test |
|---|---|---|---|---|---|---|
| ANO-01 | moteur | Comparaisons de seuils faites en virgule flottante sans tolérance : un calcul qui tombe pile sur le seuil peut basculer. Cas réalistes trouvés par recherche systématique (72 cas pour BP-3, 76 pour EX-AL, 9 pour BP-4, 5 pour VM). L'Excel (recalculé par LibreOffice) donne le résultat attendu ; la comparaison aléatoire ne l'avait pas détecté. | (a) base + `{"BA-18":243,"L-03":45,"PL-03":2.7}` ; (b) brasseur Ø 140 ×2, 49 m², BA-13 300, BA-14 500 ; (c) PL-03 2,45, BA-12 221, BA-09 160 ; (d) espace `{"E-14":22.4,"E-06":28}` | (a) VM-7 « En place » : « débit d'au moins 2 vol/h » (III.b.ii-7) ; (b) BP-4 « À optimiser » : équation 1 « 0,2 < … < 0,4 » non vérifiée à 0,4 (III.a.i-4, colonne Condition de l'Excel) ; (c) BP-3 « À optimiser » (≤ 0,15) ; (d) pas d'EX-AL (« inférieur à 0,8 », III.d.i) | (a) VM-10 « Sous réserve » (243 / 121,500…01 = 1,999…) ; (b) BP-5 « En place » ; (c) BP-4 au lieu de BP-3 ; (d) EX-AL et PR-AL4 déclenchées | `test_cas_limites.py::test_bornes[… ANO-01]`, `::test_ex_al_pile_0_8_par_enfant`, `test_excel.py::test_bornes_recalculees_par_libreoffice` |
| ANO-02 | moteur | Surface ou hauteur égale à 0 : la division par zéro est traitée comme « règle fausse » ; VM-7 et VM-10 sont fausses et le local tombe sur VM-11 « Recommandé ». L'interface accepte 0 (minimum 0). L'Excel fait de même (il ignore l'erreur), mais la méthode demande « Sous réserve » quand une donnée nécessaire est inconnue (§ III). | base + `{"locaux":[{"L-03":0}]}` | « Sous réserve » (donnée invalide) | VM-11 « Recommandé » | `test_regles_methode.py::test_vm_volume_nul_ne_donne_pas_recommande` |
| ANO-10 | sorties | L'alerte EX-AL (surface d'ombrage insuffisante) figure dans le PDF (partie Alertes) mais pas dans le CSV, ni dans les marqueurs « (!) » / ⚠️ des tableaux de statuts, quand l'espace n'a pas de préau (avec un préau, PR-AL4 la duplique). | espace `{"E-02":["Cour de récréation"],"E-14":20,"E-06":100,"E-04":["Élémentaire"]}` | Même alerte dans tous les documents (D : « les alertes listées sont exactement celles déclenchées ») | Colonne Alertes du CSV vide | `test_sorties.py::test_ex_al_dans_toutes_les_sorties` |
| ANO-17 | import | En-têtes « Q4 - libellé » (format annoncé à l'écran) avec séparateur « ; » : le séparateur est déduit de la seule ligne d'en-tête, où les virgules des libellés l'emportent ; le fichier est lu avec « , », tout part dans Q1, **sans avertissement**. C'est le format d'un export de formulaire ouvert puis enregistré par Excel en français. | en-têtes `Q1 - Quelle pièce…;Q2 - À quel étage…;…` | Réponses importées (F : « en-têtes Q4 - libellé ») | 1 réponse dont Q1 = toute la ligne, aucun avertissement | `test_questionnaire_usagers.py::test_entetes_avec_libelle_separateur_point_virgule` |
| ANO-19 | import / synthèse | Les réponses à des questions masquées (Q12 à Q15 si Q11 = Aucune ou Je ne sais pas, Q13 si Q12 ≠ Jamais/Rarement, Q17) sont conservées à l'import CSV et comptées dans la synthèse et la matrice (M6). Le formulaire en ligne, lui, les retire. | CSV `Q11;Q12;Q15` / `Aucune;Jamais;Pas du tout efficaces` | Réponses masquées ni conservées ni comptées (F ; PàT E4) | Q12 et Q15 importées et comptées | `test_questionnaire_usagers.py::test_reponse_masquee_ni_conservee_ni_comptee` |
| ANO-20 | import | Un CSV enregistré par Excel (« CSV séparateur point-virgule », encodage Windows-1252, cas par défaut sous Windows en français) : décodé en UTF-8 avec remplacement, toutes les réponses accentuées (« Très chaude », « Légèrement… ») sont rejetées « hors liste ». | `Q4;Q5` / `Très chaude;Légèrement inconfortable` encodé en cp1252 | Réponses importées | Réponses ignorées, avertissements « Tr�s chaude » | `test_questionnaire_usagers.py::test_csv_excel_windows_1252` |
| ANO-22 | matrice | M8 est évalué avec une seule réponse : il suffit qu'un usager déclare un équipement non relevé pour obtenir « À vérifier » (et faire baisser l'indicateur de cohérence). | 1 réponse `Q20 = Oui, un climatiseur mobile`, aucun BA-02 relevé | « Non évaluable » : « En dessous de 3 réponses, rien n'est évalué » (PàT E1) | « À vérifier » | `test_questionnaire_usagers.py::test_matrice_m8_minimum_trois_reponses` |
| ANO-27 | import | L'import Excel accepte sans avertissement une réponse hors liste (« oui » en minuscules, ancienne option, valeur collée sans validation). Le moteur la traite comme une réponse « autre » (la règle devient **fausse**, pas indéterminée), puis l'interface l'efface dès que la fiche est affichée (ANO-31). | `Saisie_Bâtiment!D` B-05 = « oui » | Avertissement à l'import, ou valeur normalisée « Oui » | PV-8 « Recommandé » au lieu de PV-3 « Sous réserve » (patrimoine ignoré) | `test_excel.py::test_import_excel_reponse_hors_liste_signalee` |

### 2.3 Mineur

| Id | Domaine | Description | Attendu / source | Test |
|---|---|---|---|---|
| ANO-03 | interface | Sur téléphone (375 px), les 7 ou 8 boutons d'étapes s'empilent en tête de chaque écran : le titre de l'étape commence vers 640 px, il faut défiler à chaque changement d'étape. Pas de défilement horizontal (vérifié). | Contenu visible sans défiler | `test_interface_playwright.py::test_telephone_contenu_visible_sans_defiler` |
| ANO-04 | interface | Libellés d'étapes tronqués à 1440 px de large : « 4. Espaces extér… », « 6. Questionnair… ». | Libellés lisibles | `::test_libelles_d_etapes_lisibles` |
| ANO-05 | interface | Le nom accessible des infobulles contient la syntaxe Markdown : « Help for Nom de la pièce :gray[· L-01] » (lecteurs d'écran). | Texte propre | `::test_infobulles_sans_balisage` |
| ANO-06 | interface / sorties | Légende des statuts dans un ordre différent à l'écran (Recommandé, En place, À optimiser…) et dans les PDF (Recommandé, À optimiser, En place…). | Même ordre partout | `test_interface_apptest.py::test_legende_meme_ordre_que_les_pdf` |
| ANO-08 | import | Nombre saisi en texte dans l'Excel (« 60 », « 2,5 ») : importé tel quel, sans conversion ni avertissement ; la règle passe « Sous réserve » (comme dans l'Excel, qui teste `ISNUMBER`). | Conversion ou avertissement | `test_excel.py::test_import_excel_nombre_en_texte_converti` |
| ANO-09 | moteur / import | Un nombre de baies égal à 0 (import JSON ou Excel ; l'interface impose ≥ 1) : le moteur ignore le type de baie, l'Excel le compte comme présent. Écart à l'Excel recalculé (VN-7 « Recommandé » dans l'Excel, VN-6 « Sous réserve » ici). | Même résultat que l'Excel, ou 0 refusé à l'import | `test_cas_limites.py::test_zero_baie_comme_l_excel`, `test_excel.py::test_bornes_recalculees_par_libreoffice` |
| ANO-11 | sorties | Même cas : la colonne « Quantités relevées » affiche « NO : » (orientation sans texte). | « NO : 0 baie » ou rien | `test_sorties.py::test_quantites_zero_baie` |
| ANO-12 | moteur | E-20 = « Aucune » + « S » : contrairement à ce qu'annonce B6 (« priorité à l'option cochée »), « Aucune » masque E-21 à E-25 et l'ombrage adossé tombe sur OA-11 « Sous réserve » sans donnée manquante, alors que OA-1 voit bien la façade S. | Comportement uniforme (et « Aucun » exclusif, recommandé par B6) | `test_cas_limites.py::test_aucun_coche_avec_une_autre_option[E-20]` |
| ANO-13 | sorties | Le tableau des murs des fiches affiche la distance vitrage-façade (MEX-05) même quand la question est masquée (baies au nu extérieur). | Aucune question masquée dans les fiches (D) | `test_sorties.py::test_tableau_des_murs_sans_question_masquee` |
| ANO-14 | sorties | Décimales avec un point dans les PDF : « 0.15 », « 2.5 vol/h (modifié) », « +0.6 », « 2.45 m ». | Virgule décimale | `test_sorties.py::test_decimales_a_la_francaise` |
| ANO-15 | sorties | Sans local ni espace, le compte rendu saute de « 1. Cadre » à « 6. Fiches détaillées ». | Numérotation continue | `test_sorties.py::test_numerotation_sans_entite` |
| ANO-16 | sorties | Emojis et caractères hors Windows-1252 (noms, observations, établissement) : carrés noirs dans les PDF, « ? » dans le pied de page. Visible sur les captures (`pdftoppm`). | Texte lisible ou caractère retiré | `test_sorties.py::test_emojis_lisibles_dans_les_pdf` |
| ANO-18 | import | Colonne inconnue d'un CSV (« Commentaire », « Q99 ») ignorée sans être signalée. | Signalée (F) | `test_questionnaire_usagers.py::test_colonne_inconnue_signalee` |
| ANO-21 | matrice | M6 vérifie le minimum de 3 réponses sur le plus grand des deux dénominateurs (Q12, Q15) : 1 seule réponse à Q15 « Peu efficaces » (100 %) suffit à « À vérifier ». | Minimum par indicateur (PàT E1) | `::test_matrice_m6_minimum_par_indicateur` |
| ANO-23 | matrice | M8 sans aucun local dans l'audit : « À vérifier » au lieu de « Non évaluable » (aucun local concerné). | « Non évaluable » (PàT E1) | `::test_matrice_m8_sans_local` |
| ANO-24 | sorties | Le PDF annonce un ressenti « signalé au-delà de 30% » alors que le calcul retient « au moins 30 % » (≥, comme PàT E1) ; « au-delà » se lit « strictement plus de ». | « à partir de 30 % » | `::test_libelle_seuil_coherent_avec_le_calcul` |
| ANO-25 | import | « ... » au lieu de « … » à l'intérieur d'une option (Q18) la rend « hors liste ». | Normalisé comme les apostrophes | `::test_points_de_suspension_non_reconnus` |
| ANO-28 | documentation | PàT (§ A, « Conséquence sur l'exemple ») et le README n'annoncent qu'un écart entre l'outil et l'onglet Résultats de l'Excel sur l'exemple (VN de la Classe CM1). Il y en a **quatre**, tous dus à A1 et A2 : PH de la Classe CM1 (SR → Recommandé), PH de la Salle de motricité (SR → À optimiser), fenêtres de toit de la Salle de classe (Recommandé → Sous réserve). L'Excel corrigé recalculé donne bien 0 écart. | Liste complète dans PàT (un auditeur qui compare à l'Excel le constatera) | `test_excel.py::test_import_de_l_excel_de_reference_vs_onglet_resultats` |
| ANO-29 | import | Messages d'import techniques, en anglais : « Import impossible : Expecting property name enclosed in double quotes: line 1 column 2 (char 1) », « 'Worksheet Saisie_Bâtiment does not exist.' ». Pas de plantage. | Message en clair (« ce fichier n'est pas une saisie SURYA ») | `test_interface_apptest.py::test_import_autre_excel_message_peu_clair`, Playwright `test_import_invalide_message_clair` |
| ANO-32 | interface | « Supprimer cette réponse » ne fait rien pour les réponses de l'exemple ou d'un JSON importé (pas d'identifiant `_id`), sans message. | Réponse supprimée | `test_interface_apptest.py::test_supprimer_une_reponse_de_l_exemple` |
| ANO-33 | interface | Deux locaux de même nom ne sont pas signalés : leurs colonnes sont indiscernables à l'écran, dans le CSV et les PDF. | Avertissement | `::test_noms_en_double_ecrasent_les_colonnes` |
| ANO-34 | sorties | Toiture à pentes sans combles (cas B2) avec une saisie complète : la solution est listée en « Données manquantes » et demande de « renseigner L-09, puis B-18, B-21 et B-22 », déjà renseignées. L'utilisateur ne peut pas lever la réserve. | Ne pas la présenter comme une donnée manquante | `test_sorties.py::test_toiture_sans_bloc_n_est_pas_une_donnee_manquante` |
| ANO-35 | sorties / ergonomie | « À compléter » cite toutes les questions de la règle, y compris celles déjà renseignées (VM-7 : « compléter B-16, B-10, B-12, BA-18, L-03, PL-03 » quand seul BA-18 manque). | Ne citer que les questions vides | `test_sorties.py::test_a_completer_ne_cite_que_les_questions_vides` |
| ANO-36 | interface | L'étape Questionnaires annonce « 23 questions » ; il y en a 24 (Q24 ajoutée, PàT E2). | Nombre exact | `test_interface_apptest.py::test_nombre_de_questions_annonce` |
| ANO-37 | interface | L'étape Vérification cite les questions de façade par leur code (« S : F-03 sans réponse ») alors que l'étape Façades n'affiche que les libellés. | Libellé de la question | `::test_verification_facades_en_clair` |

### 2.4 Questions de méthode

| Id | Constat | Test |
|---|---|---|
| QM-01 | **VM-9 et VM-11 ne sont jamais retenues.** B-16 = Oui mène toujours à VM-7 (si le débit est connu et suffisant) ou VM-10 ; B-16 = Non à VM-6 ; B-16 inconnu à VM-5/VM-6 indéterminées. Avec un débit inconnu, c'est VM-7 indéterminée qui donne « Sous réserve » (principe B7), pas VM-9. VM-11 « Recommandé » n'est atteinte qu'avec une surface ou une hauteur nulle (ANO-02). Parcours exhaustif des combinaisons de B-09 à B-16. Faut-il revoir l'ordre (VM-9 avant VM-7) et préciser dans quel cas la ventilation mécanique nocturne est « Recommandé » ? PàT A3 annonce « Débit non renseigné : Sous réserve (VM-9) » : le statut est juste, la règle citée ne l'est pas. | `test_regles_methode.py::test_vm11_inatteignable_avec_des_donnees_valides`, `::test_vm9_debit_inconnu_donne_sous_reserve_par_vm7` |
| QM-02 | PV-0, PH-0, FS-0 (« Non concerné » sans baie) et la condition « et MEX-14 = Non » de VN-1 et FS-0 n'existent que dans l'Excel ; la méthode n'a pas de règle « aucune baie » pour les protections et les films (sans elles, un local aveugle serait « Recommandé »). PàT § D affirme que « les règles elles-mêmes sont identiques dans les deux documents ». À reporter dans la méthode. | `test_invariants.py::test_un_statut_parmi_six_et_non_concerne_prevu` |
| QM-03 | B-18 vide avec des combles perdus décrits : le bloc CP s'applique avec un statut certain, alors qu'une toiture-terrasse, prioritaire (B3), n'est pas exclue. Lié à B3. | `test_cas_limites.py` (NON_NECESSAIRES, cas TT-1 / B-18) |
| QM-04 | OA-AL2 et OA-AL3 (prévues pour un statut OA « Recommandé ou Sous réserve ») ne sont pas déclenchées quand OA est « Sous réserve » faute de donnée (et OA-AL1 non plus). Comportement identique à l'Excel. Voulu ? | `test_regles_methode.py::test_alertes_espaces` |
| QM-05 | EX-AL vaut 0,5 quand l'effectif ou la surface manque : ni l'écran, ni les PDF, ni PR-AL4 ne le signalent (l'alerte disparaît). Une alerte indéterminée doit-elle apparaître « à vérifier » ? | `test_cas_limites.py::test_ex_al_indeterminee_n_est_signalee_nulle_part` |
| QM-06 | VV-AL (tenue structurelle) n'est déclenchée que pour une véranda ou une verrière, pas pour un « puits de lumière, atrium », pourtant concerné par le bloc VV (VV-1, méthode III.c.vi-1 « toiture vitrée, atrium, puits de lumière »). | `test_regles_methode.py::CAS` « VV-9 atrium » |
| QM-07 | Matrice : « Sous réserve » compte comme une préconisation. Un audit sans aucune donnée (tout « Sous réserve ») est « Cohérent » sur M1 à M5 dès que le ressenti est signalé, indicateur 100 % : conclusion trompeuse pour un lecteur. Exclure les « Sous réserve » faute de donnée ? | `test_questionnaire_usagers.py::test_audit_vide_tout_sous_reserve_juge_coherent` |
| QM-08 | M8 n'applique pas le seuil de 30 % : 1 usager sur 20 déclarant un équipement non relevé suffit à « À vérifier ». L'en-tête de la colonne « Ressenti (signalé si ≥ 30 %) » de PàT E1 laisse penser le contraire. | `::test_matrice_m8_ignore_le_seuil_de_30_pourcent` |
| QM-09 | CP-6 cite B-01 (période de construction) dans la colonne « Questions », mais ni l'Excel ni l'outil ne l'utilisent ; la méthode parle de « suspicion d'amiante ». Faut-il déduire la suspicion d'une construction d'avant 1997 (comme PR-AL3) ? | matrice de dépendances (B-01 sans effet sur Toiture) |
| QM-10 | Les comparaisons de seuil supposent l'équation 1 stricte aux deux bornes (« non [0,2 < … < 0,4] » de l'Excel) ; l'image de la méthode (III.a.i-4) ne permet pas de lire si les bornes sont incluses. À confirmer avec ANO-01. | `test_cas_limites.py::test_bornes` (équation 1) |

## 3. Matrice de couverture des règles

Générée par `python tests/couverture_regles.py` (cas « une règle », bornes et priorités qui retiennent la
règle avec une donnée complète). Chaque règle qui cite des questions a en outre un cas « donnée manquante » (vide et, quand la
question le propose, « Non évalué ») dans `test_cas_limites.py::test_donnee_necessaire_manquante`.

| Règle | Statut | Couverte | Cas (nombre et exemples) |
|---|---|---|---|
| BP-1 | À optimiser | oui | 2 : BP-1 hors service; BP-1 avant BP-3 |
| BP-2 | À optimiser | oui | 1 : BP-2 commande |
| BP-3 | À optimiser | oui | 3 : BP-3 pales trop proches; pale 0,145; pale 0,150 |
| BP-4 | À optimiser | oui | 10 : BP-4 équation 1; BP-4 assertion 1 (mur); BP-4 assertion 2 (entraxe) |
| BP-5 | En place | oui | 10 : BP-5 défaut; BP-5 deux brasseurs bien placés; pale 0,155 |
| BS-1 | Non recommandé ou non adapté | oui | 3 : BS-1 HSP < 2,40; HSP 2,39; BS-1 avant BS-2 |
| BS-2 | Sous réserve | oui | 5 : BS-2 baffles; BS-2 gaines; BS-2 décoration |
| BS-3 | Sous réserve | oui | 4 : BS-3 HSP 2,50; HSP 2,40; HSP 2,41 |
| BS-4 | Sous réserve | oui | 2 : BS-4 plénum 0,80 béton; plénum 0.71 |
| BS-5 | Sous réserve | oui | 1 : BS-5 faux plafond sur bois |
| BS-6 | Sous réserve | oui | 2 : BS-6 plafond bois; BS-6 autre |
| BS-7 | Recommandé | oui | 6 : BS-7 dalle béton; BS-7 faux plafond plénum 0,50 béton; HSP 2,60 |
| BR-AL | alerte | oui | BR-AL toujours ; même si non recommandé |
| VN-1 | Non recommandé ou non adapté | oui | 2 : VN-1 aucune baie; VN-1 avant tout |
| VN-2 | Non recommandé ou non adapté | oui | 4 : VN-2 vitrage fixe seul; VN-2 mur-rideau seul; VN-2 fixe sur deux murs |
| VN-3 | Sous réserve | oui | 3 : VN-3 volets pleins; VN-3 stores pleins; VN-3 avant VN-7 |
| VN-4 | Sous réserve | oui | 1 : VN-4 alarme |
| VN-5 | Sous réserve | oui | 2 : VN-5 menuiserie dégradée; VN-5 très dégradée |
| VN-6 | Sous réserve | oui | 3 : VN-6 oscillo-battant seul; VN-6 soufflet + fixe; VN-6 avant VN-7 (oscillo sur 2 murs) |
| VN-7 | Recommandé | oui | 2 : VN-7 traversant S/N; VN-7 angle S/E |
| VN-8 | Recommandé | oui | 1 : VN-8 façade + toiture ouvrante |
| VN-9 | Recommandé | oui | 2 : VN-9 porte standard; VN-9 coupe-feu ventouse |
| VN-10 | Sous réserve | oui | 2 : VN-10 mono-orienté; VN-10 porte coupe-feu fermée |
| VN-AL1 | alerte | oui | VN-AL1 sans grilles / aucun / pas si VN NR / ventelles |
| VN-AL2 | alerte | oui | VN-AL2 si VN recommandé |
| VM-1 | Non recommandé ou non adapté | oui | 3 : VM-1 pas de VMC; VM-1 local non desservi; VM-1 avant VM-3 |
| VM-2 | Non recommandé ou non adapté | oui | 1 : VM-2 simple flux sans surdébit |
| VM-3 | À optimiser | oui | 2 : VM-3 à l'arrêt; VM-3 filtres |
| VM-4 | À optimiser | oui | 1 : VM-4 by-pass non activé |
| VM-5 | À optimiser | oui | 1 : VM-5 pas de programmation |
| VM-6 | À optimiser | oui | 1 : VM-6 mode nocturne non programmé |
| VM-7 | En place | oui | 4 : VM-7 en place simple flux; VM-7 en place double flux by-pass actif; débit 360 m³/h |
| VM-8 | Sous réserve | oui | 1 : VM-8 double flux sans by-pass |
| VM-9 | Sous réserve | statut vérifié | 0 :  — jamais retenue : VM-7 indéterminée passe avant (QM-01) ; statut vérifié par test_vm9_… |
| VM-10 | Sous réserve | oui | 4 : VM-10 débit insuffisant; débit 359 m³/h; débit 2 vol/h (243 m³/h ; 45 m² × 2,70 m) |
| VM-11 | Recommandé | non | 0 :  — atteinte seulement avec une surface ou une hauteur nulle (ANO-02, QM-01) |
| PV-0 | Non concerné | oui | 1 : PV-0 aucune baie |
| PV-1 | Non recommandé ou non adapté | oui | 2 : PV-1 nu extérieur sans débord; PV-1 avant PV-3 |
| PV-2 | Sous réserve | oui | 5 : PV-2 tableau 15 cm; PV-2 tunnel 10 cm; tableau 15 cm |
| PV-3 | Sous réserve | oui | 2 : PV-3 monument historique; PV-3 abords |
| PV-4 | Sous réserve | oui | 4 : PV-4 ITE (MEX-26); PV-4 ossature (MEX-26); PV-4 à défaut B-03 |
| PV-5 | Sous réserve | oui | 1 : PV-5 étage sans accès nacelle |
| PV-6 | Sous réserve | oui | 1 : PV-6 obstacle |
| PV-7 | Sous réserve | oui | 1 : PV-7 désordre |
| PV-8 | Recommandé | oui | 3 : PV-8 défaut; tableau 16 cm; tableau 17 cm |
| PH-0 | Non concerné | oui | 1 : PH-0 aucune baie |
| PH-1 | En place | oui | 4 : PH-1 débord important au sud; PH-1 débord important SE; PH-1 avant PH-4 |
| PH-2 | À optimiser | oui | 1 : PH-2 débord faible SO |
| PH-3 | Non recommandé ou non adapté | oui | 3 : PH-3 pas de mur sud; PH-3 est et ouest; PH-3 avant PH-5 |
| PH-4 | Non recommandé ou non adapté | oui | 2 : PH-4 RDC alignement; PH-4 plain-pied alignement |
| PH-5 | Sous réserve | oui | 1 : PH-5 patrimoine |
| PH-6 | Sous réserve | oui | 1 : PH-6 étage alignement |
| PH-7 | Sous réserve | oui | 1 : PH-7 ITE |
| PH-8 | Sous réserve | oui | 1 : PH-8 sans accès nacelle |
| PH-9 | Sous réserve | oui | 1 : PH-9 obstacle |
| PH-10 | Sous réserve | oui | 1 : PH-10 désordre |
| PH-11 | Recommandé | oui | 1 : PH-11 défaut |
| FS-0 | Non concerné | oui | 1 : FS-0 aucune baie |
| FS-1 | À optimiser | oui | 2 : FS-1 film dégradé; FS-1 avant FS-2 |
| FS-2 | En place | oui | 1 : FS-2 film partout bon état |
| FS-3 | Recommandé | oui | 2 : FS-3 aucun film; FS-3 film partiel bon état |
| FT-1 | Non concerné | oui | 2 : FT-1 pas de baie en plafond; FT-1 verrière seule |
| FT-2 | À optimiser | oui | 2 : FT-2 volet extérieur HS; FT-2 avant FT-5 |
| FT-3 | À optimiser | oui | 1 : FT-3 store intérieur seul |
| FT-4 | En place | oui | 1 : FT-4 store extérieur bon état |
| FT-5 | Sous réserve | oui | 1 : FT-5 patrimoine |
| FT-6 | Sous réserve | oui | 2 : FT-6 fenêtre non identifiable; FT-6 très ancienne |
| FT-7 | Sous réserve | oui | 2 : FT-7 hors d'atteinte, fixe; FT-7 hors d'atteinte, manuelle |
| FT-8 | Recommandé | oui | 3 : FT-8 hors d'atteinte mais électrique; FT-8 défaut; FT-8 lanterneau |
| FT-AL | alerte | oui | FT-AL ouvrante / fixe |
| VV-1 | Non concerné | oui | 2 : VV-1 pas de véranda; VV-1 fenêtre de toit seule |
| VV-2 | À optimiser | oui | 1 : VV-2 store extérieur HS |
| VV-3 | À optimiser | oui | 1 : VV-3 protection intérieure seule |
| VV-4 | À optimiser | oui | 2 : VV-4 aucun ouvrant; VV-4 avant VV-6 |
| VV-5 | En place | oui | 1 : VV-5 en place |
| VV-6 | Sous réserve | oui | 1 : VV-6 patrimoine |
| VV-7 | Sous réserve | oui | 1 : VV-7 toiture non accessible |
| VV-8 | Sous réserve | oui | 1 : VV-8 pas de séparation |
| VV-9 | Recommandé | oui | 3 : VV-9 défaut véranda; VV-9 verrière; VV-9 atrium |
| VV-AL | alerte | oui | VV-AL véranda / verrière |
| TO-0 | Non concerné | oui | 3 : TO-0 étage intermédiaire; TO-0 RDC; TO-0 sous-sol |
| TT-1 | Sous réserve | oui | 1 : TT-1 terrasse non isolée |
| TT-2 | En place | oui | 5 : TT-2 terrasse 30 cm; TT-2 bac acier plain-pied; terrasse 30 cm |
| TT-3 | Sous réserve | oui | 2 : TT-3 terrasse 29 cm; terrasse 29 cm |
| CP-1 | À optimiser | oui | 3 : CP-1 isolant tassé; CP-1 isolant discontinu; CP-1 avant CP-3 |
| CP-2 | À optimiser | oui | 2 : CP-2 combles non ventilés; CP-2 avant CP-4 |
| CP-3 | En place | oui | 3 : CP-3 30 cm bon état; combles 30 cm; combles 31 cm |
| CP-4 | Sous réserve | oui | 1 : CP-4 non accessibles |
| CP-5 | Sous réserve | oui | 1 : CP-5 humidité |
| CP-6 | Sous réserve | oui | 2 : CP-6 spots; CP-6 amiante |
| CP-7 | Recommandé | oui | 2 : CP-7 isolant 20 cm; combles 29 cm |
| CA-1 | Sous réserve | oui | 1 : CA-1 épaisseur inconnue |
| CA-2 | Sous réserve | oui | 2 : CA-2 rampants 15 cm; rampants 19 cm |
| CA-3 | En place | oui | 3 : CA-3 rampants 20 cm; rampants 20 cm; rampants 21 cm |
| CO-1 | Sous réserve | oui | 2 : CO-1 bureau 5 m²/pers; bureau 23 m² / 4 |
| CO-2 | Sous réserve | oui | 2 : CO-2 classe 1,2 m²/élève; classe 37 m² / 25 |
| CO-3 | En place | oui | 8 : CO-3 classe 2,4 m²/élève; CO-3 dortoir dense; bureau 24 m² / 4 |
| CE-1 | Recommandé | oui | 2 : CE-1 non LED; CE-1 mixte |
| CE-2 | En place | oui | 1 : CE-2 LED |
| CQ-1 | Sous réserve | oui | 3 : CQ-1 copieurs; CQ-1 cuisson; CQ-1 avant CQ-2 |
| CQ-2 | À optimiser | oui | 1 : CQ-2 postes allumés |
| CQ-3 | En place | oui | 2 : CQ-3 défaut; CQ-3 équipement mais local inoccupé |
| EX-AL | alerte | oui | 13 bornes EX-AL + 3 cas pile 0,8 (ANO-01) |
| OA-1 | Non recommandé ou non adapté | oui | 3 : OA-1 façade nord; OA-1 aucune façade; OA-1 avant OA-5 |
| OA-2 | En place | oui | 2 : OA-2 structure en place; OA-2 avant OA-4 |
| OA-3 | À optimiser | oui | 2 : OA-3 couvre une partie; OA-3 dégradée |
| OA-4 | Non recommandé ou non adapté | oui | 1 : OA-4 alignement |
| OA-5 | Sous réserve | oui | 1 : OA-5 patrimoine |
| OA-6 | Sous réserve | oui | 2 : OA-6 bardage; OA-6 non identifiable |
| OA-7 | Sous réserve | oui | 2 : OA-7 issue de secours; OA-7 accès pompiers |
| OA-8 | Sous réserve | oui | 1 : OA-8 mâts à créer |
| OA-9 | Sous réserve | oui | 1 : OA-9 aucun ancrage |
| OA-10 | Recommandé | oui | 1 : OA-10 recommandé |
| OA-11 | Sous réserve | oui | 1 : OA-11 espace encombré |
| OA-AL1 | alerte | oui | test_oa_al1_mutualisation (5 cas) |
| OA-AL2 | alerte | oui | OA recommandé / sous réserve / à optimiser / NR |
| OA-AL3 | alerte | oui | idem OA-AL2 |
| PR-1 | Non concerné | oui | 1 : PR-1 pas de préau |
| PR-2 | À optimiser | oui | 2 : PR-2 translucide; PR-2 avant PR-3 |
| PR-3 | À optimiser | oui | 5 : PR-3 deux côtés fermés; préau 2 côté(s) fermé(s); préau 3 côté(s) fermé(s) |
| PR-4 | À optimiser | oui | 2 : PR-4 teinte foncée; PR-4 teinte moyenne |
| PR-5 | À optimiser | oui | 2 : PR-5 tôle basse; préau tôle 2.99 m |
| PR-6 | En place | oui | 6 : PR-6 ouvert tuiles; PR-6 ouvert claire; préau tôle 3 m |
| PR-7 | Sous réserve | oui | 1 : PR-7 défaut |
| PR-AL1 | alerte | oui | PR-AL1 patrimoine |
| PR-AL2 | alerte | oui | PR-AL2 préau à optimiser |
| PR-AL3 | alerte | oui | fibrociment 1975-1997 / après 1997 / date inconnue |
| PR-AL4 | alerte | oui | EX-AL avec et sans préau |
| OC-1 | En place | oui | 3 : OC-1 ombre 25-50 %; OC-1 arbres en bon état; OC-1 avant OC-3 |
| OC-2 | À optimiser | oui | 4 : OC-2 arbres dégradés; OC-2 voiles < 25 %; OC-2 pergola HS |
| OC-3 | Sous réserve | oui | 1 : OC-3 patrimoine |
| OC-4 | Sous réserve | oui | 2 : OC-4 dalle sur parking; OC-4 faible épaisseur |
| OC-5 | Sous réserve | oui | 1 : OC-5 voie pompiers |
| OC-6 | Recommandé | oui | 1 : OC-6 défaut |

## 4. Matrice de dépendances questions → solutions

Générée par `python tests/matrice_dependances.py 250` : pour chaque question, toutes ses réponses
possibles (options, vide, nombres) sont essayées sur 250 saisies aléatoires ; une solution est
« touchée » si son statut ou ses alertes changent. « Attendues » = colonne « Questions » des règles de
l'Excel, plus les questions qui choisissent le cas (BA-05, L-09, B-18, B-21, B-22, E-02), les questions
« mères » des questions conditionnelles, et la dépendance de l'ombrage adossé aux questions des
protections horizontales via l'alerte OA-AL1.

**Aucune dépendance inattendue.** Les questions marquées `[info]` sont toutes sans effet. Les cases
« attendues mais sans effet » sont, sauf deux, des combinaisons trop rares dans les tirages ; leur effet est
démontré par un cas écrit à la main : B-04 → protections verticales (« PV-4 à défaut B-04 »), B-05 / B-06
→ vérandas (« VV-6 patrimoine »), MEX-17 → fenêtres de toit (FT-7), MEX-22 / MEX-24 → vérandas (VV-7,
VV-8), MEX-35 → VN (VN-9), PL-05 → brasseurs (BS-5), E-29 → préau (PR-5), MEX-26 et F-03 → ombrage
adossé (via OA-AL1). Restent réellement sans effet : **B-01 sur la toiture** (QM-09) et **B-07** (C1,
documenté).

| Question | info | Solutions touchées (observé) | **Inattendues** | Attendues mais sans effet |
|---|---|---|---|---|
| B-01 |  | Préau |  | Toiture |
| B-03 |  | Ombrage adossé, Prot. horizontales, Prot. verticales |  |  |
| B-04 |  | Ombrage adossé, Prot. horizontales |  | Prot. verticales |
| B-05 |  | Fenêtres de toit, Ombrage adossé, Ombrage cour, Prot. horizontales, Prot. verticales, Préau |  | Vérandas |
| B-06 |  | Fenêtres de toit, Ombrage adossé, Ombrage cour, Prot. horizontales, Prot. verticales, Préau |  | Vérandas |
| B-07 |  | — |  |  |
| B-08 |  | VN nocturne |  |  |
| B-09 |  | VM nocturne |  |  |
| B-10 |  | VM nocturne |  |  |
| B-11 |  | VM nocturne |  |  |
| B-12 |  | VM nocturne |  |  |
| B-13 |  | VM nocturne |  |  |
| B-14 |  | VM nocturne |  |  |
| B-15 |  | VM nocturne |  |  |
| B-16 |  | VM nocturne |  |  |
| B-18 |  | Toiture |  |  |
| B-19 |  | Toiture |  |  |
| B-20 |  | Toiture |  |  |
| B-21 |  | Toiture |  |  |
| B-22 |  | Toiture |  |  |
| B-23 |  | Toiture |  |  |
| B-24 |  | Toiture |  |  |
| B-25 |  | Toiture |  |  |
| B-26 |  | Toiture |  |  |
| B-27 |  | Toiture |  |  |
| B-28 |  | Toiture |  |  |
| L-01 | oui | — |  |  |
| L-02 |  | Occupation |  |  |
| L-03 |  | Brasseurs, Occupation, VM nocturne |  |  |
| L-04 |  | Occupation, Équipements |  |  |
| L-09 |  | Ombrage adossé, Prot. horizontales, Prot. verticales, Toiture |  |  |
| L-10 |  | Équipements |  |  |
| L-11 |  | Équipements |  |  |
| MEX-14 |  | Fenêtres de toit, Films, VN nocturne, Vérandas |  |  |
| MEX-15 |  | Fenêtres de toit, Vérandas |  |  |
| MEX-16 |  | Fenêtres de toit, VN nocturne, Vérandas |  |  |
| MEX-17 |  | — |  | Fenêtres de toit |
| MEX-18 |  | Fenêtres de toit, Vérandas |  |  |
| MEX-19 |  | Fenêtres de toit, Vérandas |  |  |
| MEX-20 |  | Fenêtres de toit |  |  |
| MEX-21 |  | Fenêtres de toit |  |  |
| MEX-22 |  | — |  | Vérandas |
| MEX-24 |  | — |  | Vérandas |
| MEX-25 | oui | — |  |  |
| MEX-25b | oui | — |  |  |
| MEX-26 |  | Prot. horizontales, Prot. verticales |  | Ombrage adossé |
| MEX-29 |  | VN nocturne |  |  |
| MEX-30 |  | VN nocturne |  |  |
| MEX-32 |  | Films |  |  |
| MEX-33 |  | Films |  |  |
| MEX-34 |  | VN nocturne |  |  |
| MEX-35 |  | — |  | VN nocturne |
| MEX-36 |  | VN nocturne |  |  |
| MEX-37 |  | VN nocturne |  |  |
| PL-01 |  | Brasseurs |  |  |
| PL-02 |  | Brasseurs |  |  |
| PL-03 |  | Brasseurs, VM nocturne |  |  |
| PL-05 |  | — |  | Brasseurs |
| BA-01 | oui | — |  |  |
| BA-02 | oui | — |  |  |
| BA-03 | oui | — |  |  |
| BA-04 | oui | — |  |  |
| BA-05 |  | Brasseurs |  |  |
| BA-06 |  | Brasseurs |  |  |
| BA-09 |  | Brasseurs |  |  |
| BA-11 |  | Brasseurs |  |  |
| BA-12 |  | Brasseurs |  |  |
| BA-13 |  | Brasseurs |  |  |
| BA-14 |  | Brasseurs |  |  |
| BA-15 |  | VM nocturne |  |  |
| BA-18 |  | VM nocturne |  |  |
| BA-19 |  | Brasseurs |  |  |
| ECL-01 |  | Éclairage |  |  |
| ECL-02 |  | Brasseurs |  |  |
| E-01 | oui | — |  |  |
| E-02 |  | Ombrage cour, Préau |  |  |
| E-04 |  | Préau |  |  |
| E-06 |  | Préau |  |  |
| E-07 |  | Préau |  |  |
| E-09 |  | Ombrage cour |  |  |
| E-10 |  | Ombrage cour |  |  |
| E-11 | oui | — |  |  |
| E-12 |  | Ombrage cour |  |  |
| E-14 |  | Préau |  |  |
| E-15 |  | Ombrage cour |  |  |
| E-16 | oui | — |  |  |
| E-17 | oui | — |  |  |
| E-19 | oui | — |  |  |
| E-20 |  | Ombrage adossé |  |  |
| E-21 |  | Ombrage adossé |  |  |
| E-22 |  | Ombrage adossé |  |  |
| E-23 |  | Ombrage adossé |  |  |
| E-24 |  | Ombrage adossé |  |  |
| E-25 |  | Ombrage adossé |  |  |
| E-26 |  | Préau |  |  |
| E-27 |  | Préau |  |  |
| E-28 |  | Préau |  |  |
| E-29 |  | — |  | Préau |
| E-30 |  | Préau |  |  |
| E-31 |  | Ombrage adossé, Ombrage cour |  |  |
| E-32 |  | Ombrage cour |  |  |
| F-01 |  | Ombrage adossé, Prot. horizontales, Prot. verticales |  |  |
| F-02 |  | Ombrage adossé, Prot. horizontales |  |  |
| F-03 |  | Prot. horizontales, Prot. verticales |  | Ombrage adossé |
| F-04 |  | Ombrage adossé, Prot. horizontales, Prot. verticales |  |  |
| F-05 |  | Ombrage adossé, Prot. horizontales, Prot. verticales |  |  |
| MEX-01 |  | Films, Ombrage adossé, Prot. horizontales, Prot. verticales, VN nocturne |  |  |
| MEX-04 |  | Prot. verticales |  |  |
| MEX-05 |  | Prot. verticales |  |  |
| MEX-06 |  | VN nocturne |  |  |
| MEX-07 |  | Ombrage adossé, Prot. horizontales, Prot. verticales |  |  |
| MEX-08 |  | VN nocturne |  |  |

## 5. Points de `docs/points_a_trancher.md` vérifiés

| Point | Annoncé | Vérifié | Test |
|---|---|---|---|
| A1 | Les 4 murs sont lus correctement | Oui (0 écart sur 3 000 entités avec l'Excel corrigé). Mais l'effet sur l'exemple est sous-estimé : ANO-28 | `test_excel.py` |
| A2 | FT-7 teste « MEX-17 n'est ni Électrique ni Automatique » | Oui | `CAS` FT-7, FT-8 « électrique » |
| A3 | BA-18 ajoutée en m³/h ; débit inconnu → SR (VM-9) | Statut oui ; règle retenue VM-7, pas VM-9 (QM-01) | `test_points_a_trancher.py::test_a3…` |
| B1 | VN-7 compte les murs, pas les orientations | Oui | `test_b1…` |
| B2 | Pentes sans combles, Autre sans combles, B-22 Autre → SR | Oui (et présenté à tort comme donnée manquante : ANO-34) | `test_b2…` |
| B3 | Terrasse prioritaire sur les combles | Oui | `test_b3…` |
| B4 | TT et CA sans défaut ; CA ignore B-23, B-25, B-27 ; isolant insuffisant R en CP, SR en CA | Oui | `test_b4…` |
| B5 | FT et VV lisent les mêmes MEX-16, 18, 19 | Oui | `test_b5…` |
| B6 | « Aucun » + une option : l'option l'emporte | Oui pour L-10, MEX-18, MEX-29, MEX-36, BA-19, E-10, B-28 ; **non pour E-20** (ANO-12) | `test_aucun_coche_avec_une_autre_option` |
| B7 | Règle indéterminée masque les suivantes | Oui (exemple de PàT reproduit) | `test_b7…` |
| B8 | Nu extérieur avec débord → PV-8 | Oui | `test_b8…` |
| B9 | Sous-sol traité comme un étage | Oui | `test_b9…` |
| B10 | Façade non décrite → SR ; façades citées cochées d'office, signalées si incomplètes | Oui (moteur et interface) | `test_facade_non_decrite…`, `test_facades_citees…` |
| B11 | OA-AL1 sans rattachement local / espace | Oui | `test_b11…` |
| B12 | CO limité aux bureaux et classes ; EX-AL divise par l'effectif total | Oui | `test_b12…` |
| B13 | Toutes les alertes affichées, BR-AL toujours | Oui, sauf EX-AL hors du CSV (ANO-10) | `test_b13…`, `test_donnees_manquantes_et_alertes` |
| C1 | B-07 sans effet, non `[info]` | Oui | `test_toute_question_non_info_a_un_effet` (xfail) |
| C4, C6, C7 | MEX-25b ; 4 murs ; « Non évalué » seulement en F-05 | Oui (un 5e mur importé est ignoré sans avertissement) | `test_c4_c6_c7`, `test_cinquieme_mur_ignore` |
| D1 | Types AL / VA / point d'attention ; Recommandé ou À optimiser avec AL → « À valider » | Oui | `test_b13…`, `test_plan_d_action` |
| D5 | Question vide = « Non évalué » | Oui (214 cas « vide » et « non évalué ») | `test_donnee_necessaire_manquante` |
| E1 | Matrice M1 à M8, seuil 30 % (≥), minimum 3, indicateur ; exemple : 7 évalués, 1 « À vérifier » (M7), 86 % | Oui pour M1 à M7 et l'exemple ; écarts sur M6 et M8 (ANO-21, 22, 23) | `test_matrice_*`, `test_exemple_documente_e1` |
| E2 | Q24 ajoutée | Oui (mais « 23 questions » à l'écran : ANO-36) | — |
| E3 | Q2 : RDC à « 3e étage ou plus » | Oui | — |
| E4 | Conditions de Q12 à Q15 et Q17 | Oui dans le formulaire ; non appliquées à l'import (ANO-19) | `test_visibilite`, Playwright |
| E5 | Q20 à réponse unique | Oui | — |
| Décisions | Avertir sans bloquer ; Vérification ; ordre des étapes ; Réglages ; aucune donnée stockée | Oui | `test_interface_*` |

## 6. Ce qui n'a pas pu être testé, et pourquoi

- **Microsoft Excel** : l'Excel est recalculé par LibreOffice. Les deux tableurs peuvent différer sur
  des cas d'arrondi (ANO-01) ; nous n'avons pas pu le vérifier.
- **Import d'un fichier par le bouton de l'interface** : fait dans le navigateur pour un JSON (valide et
  invalide). Pour les fichiers Excel et CSV, l'outil de test de Streamlit ne sait pas téléverser : la
  fonction appelée par le bouton est testée directement, et le bouton « Importer ces réponses » n'a pas
  été cliqué avec un vrai fichier.
- **Questionnaire en ligne multi-utilisateur** : la maquette ne stocke rien sur un serveur (voulu) ;
  seul l'aller-retour « réponse → CSV téléchargé → import » a été testé.
- **Photos normées** (PàT D2) : absentes de l'outil.
- **Contrôle visuel** : quelques pages seulement (résultats et plan d'action, noms spéciaux, 30 locaux) ;
  le débordement de texte est contrôlé automatiquement (caractères hors page ou hors cellule) sur toutes
  les pages des 22 PDF de la partie D, sans défaut trouvé.
- **Accessibilité complète** (contraste, navigation au clavier), autres navigateurs que Chromium, saisie
  tactile réelle.
- **Montée en charge** au-delà de 30 locaux et 5 espaces (temps mesurés : ouverture d'un local 0,6 s,
  saisie 0,6 s, compte rendu de 30 locaux 2,4 s, PDF des résultats 0,9 s).

## 7. Correctifs proposés (non appliqués)

**ANO-01** — arrondir les rapports calculés avant comparaison (`surya/moteur.py`) :

```diff
+def _r(x):
+    """Rapport calculé, arrondi pour neutraliser l'arithmétique flottante (2,7 × 45 = 121,50000000000001)."""
+    return round(x, 9)
+
@@ regles_local
-        ("BP-3", calcul(lambda h, pale, d: (h * 100 - pale) / d <= p["P_PALE_PLAFOND"], c["PL-03"], c["BA-12"], c["BA-09"])),
+        ("BP-3", calcul(lambda h, pale, d: _r((h * 100 - pale) / d) <= p["P_PALE_PLAFOND"], c["PL-03"], c["BA-12"], c["BA-09"])),
@@
-            calcul(lambda d, s, n: not (p["P_DIAM_MIN"] < (d / 100) / (math.sqrt(s) / n) < p["P_DIAM_MAX"]),
+            calcul(lambda d, s, n: not (p["P_DIAM_MIN"] < _r((d / 100) / (math.sqrt(s) / n)) < p["P_DIAM_MAX"]),
@@
-    debit = lambda test: calcul(lambda q, s, h: test(q / (s * h)), c["BA-18"], c["L-03"], c["PL-03"])  # noqa: E731
+    debit = lambda test: calcul(lambda q, s, h: test(_r(q / (s * h))), c["BA-18"], c["L-03"], c["PL-03"])  # noqa: E731
@@ (CO-1, CO-2 et EX-AL : même chose pour s / n)
-                     calcul(lambda s, n: n > 0 and s / n < p["P_BUREAU_M2"], c["L-03"], c["L-04"]))),
+                     calcul(lambda s, n: n > 0 and _r(s / n) < p["P_BUREAU_M2"], c["L-03"], c["L-04"]))),
```

**ANO-02** — une division par zéro est une donnée invalide, donc indéterminée :

```diff
 def calcul(test, *etats):
@@
     try:
         return 1 if test(*etats) else 0
-    except (ZeroDivisionError, TypeError, ValueError):
+    except ZeroDivisionError:
+        return 0.5
+    except (TypeError, ValueError):
         return 0
```

**ANO-26, ANO-20, ANO-17** — lecture CSV robuste (`surya/questionnaire.py`, `lire_csv`) :

```diff
     if isinstance(contenu, bytes):
-        contenu = contenu.decode("utf-8-sig", errors="replace")
+        try:
+            contenu = contenu.decode("utf-8-sig")
+        except UnicodeDecodeError:
+            contenu = contenu.decode("cp1252", errors="replace")  # CSV enregistré par Excel sous Windows
@@
-    try:
-        dialecte = csv.Sniffer().sniff(contenu.splitlines()[0], delimiters=";,\t")
-        delim = dialecte.delimiter
-    except csv.Error:
-        delim = ";"
-    lignes = list(csv.reader(io.StringIO(contenu), delimiter=delim))
+    premiere = contenu.splitlines()[0]
+    # séparateur qui isole le plus d'en-têtes « Qn » (les libellés contiennent des virgules)
+    delim = max(";,\t", key=lambda s: sum(bool(re.match(r'^\s*"?\s*Q\s*\d+', h, re.I)) for h in premiere.split(s)))
+    try:
+        lignes = list(csv.reader(io.StringIO(contenu, newline=""), delimiter=delim))
+    except csv.Error:
+        return [], ["Fichier illisible : enregistrez-le au format CSV (UTF-8) à partir du modèle fourni."]
```

**ANO-19** — appliquer les conditions d'affichage à l'import (fin de la boucle de `lire_csv`) :

```diff
+        masquees = [k for k in r if k in PAR_CODE and not visible(k, r)]
+        for k in masquees:
+            del r[k]
+            avert.append(f"Ligne {n}, {k} : sans objet d'après les réponses précédentes, ignorée.")
         if any(k != "horodatage" for k in r):
```

**ANO-22, ANO-23** — M8 (`matrice`) :

```diff
-    if sum(declares.values()) == 0 and len([r for r in reponses if r.get("Q20")]) < minimum:
+    if len([r for r in reponses if r.get("Q20")]) < minimum or not res["locaux"]:
         ajouter("M8", "Équipements de rafraîchissement", "—", "relevé BA-01 à BA-05", NON_EVALUABLE,
-                "Moins de %d réponses." % minimum)
+                "Moins de %d réponses." % minimum if res["locaux"] else "Aucun local dans l'audit.")
```

**ANO-10** — EX-AL dans le CSV (`app.py`, `_export_csv`) :

```diff
-                            "oui" if _manquante(x, s) else "non", ", ".join(s["alertes"])])
+                            "oui" if _manquante(x, s) else "non",
+                            ", ".join(s["alertes"] + (["EX-AL"] if x.get("EX-AL") == 1 and s is x["solutions"][0] else []))])
```

**ANO-32** — identifiants des réponses chargées (`app.py`, `charger`) :

```diff
     for x in base["locaux"] + base["espaces"]:
         x.setdefault("_id", uuid.uuid4().hex[:8])
+    for r in base["questionnaires"]:
+        r.setdefault("_id", uuid.uuid4().hex[:8])
```

**ANO-13** — fiche des murs (`surya/rapport.py`, `_table_murs`) :

```diff
-        data.append([Paragraph(str(i), S["cellule"])] + [Paragraph(_t(_reponse(m.get(q["code"]))), S["cellule"]) for q in qs]
+        vis = lambda q: q["code"] != "MEX-05" or m.get("MEX-04") in ("Nu intérieur", "En tunnel")  # noqa: E731
+        data.append([Paragraph(str(i), S["cellule"])]
+                    + [Paragraph(_t(_reponse(m.get(q["code"]) if vis(q) else None)), S["cellule"]) for q in qs]
```

**ANO-11** — `_baies_par_orientation` : ignorer les nombres nuls (`if isinstance(n, (int, float)) and n > 0`).

ANO-07, ANO-27, ANO-30, ANO-31 demandent une **validation des données à l'import** (types, bornes,
valeurs des listes) avec un rapport d'import, plutôt qu'un correctif ponctuel : à arbitrer.
