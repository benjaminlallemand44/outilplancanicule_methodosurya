# Rapport de la campagne de tests n° 2 — outil méthode SURYA

> **Suite donnée (27/11/2026)** : toutes les anomalies C2-01 à C2-12 sont corrigées, voir `docs/suivi_corrections.md` (campagne n° 2). Les questions QM2-01 à QM2-03, et les choix faits pour C2-04 et C2-05, sont ajoutés à `docs/points_a_trancher.md` (F11, G4, G5, H1, H2).

Campagne menée le 26/11/2026 sur la dernière version de `main` (commit `15fd69d`, branche de travail
`claude/fervent-hopper-qeizm3` repartie de `main`). Aucun fichier de `surya/`, `app.py` ni `supabase/`
n'a été modifié : les correctifs sont proposés au § 6.

Depuis la campagne n° 1 (`docs/rapport_tests.md`), l'outil a beaucoup grandi : corrections des
37 anomalies (`docs/suivi_corrections.md`), contrôle des imports (`surya/validation.py`), photos avec
floutage des visages, compte rendu orienté décision (synthèse, plan simplifié, étapes), troisième parcours
« Passer à l'action » (pré-programme, accompagnement, CCTP, diagnostic externe et lecture par IA),
branchement Supabase (comptes, audits, questionnaire en ligne, photos, purge de conservation).

La campagne a deux volets : **non-régression** (toute la campagne n° 1 rejouée sur `main`) et
**nouveautés** (nouveaux tests dans `tests/test_campagne2.py` et `tests/interface_playwright_c2.js`).

## 1. Résumé

| | |
|---|---|
| Suite complète sur `main` avant la campagne | **977 tests réussis**, 1 « xfail » (C1, B-07 sans effet : documenté) |
| Comparaison à l'Excel recalculé (LibreOffice) | 5 graines × 40 tirages (3 000 locaux et espaces) : **0 écart** |
| Corrections de la campagne n° 1 | **36 / 37 vérifiées** (ANO-12 laissée en attente de la décision B6, comme annoncé) |
| Nouveaux tests | `tests/test_campagne2.py` : 22 cas, dont **15 « xfail » stricts** qui reproduisent les anomalies ; scénario navigateur `interface_playwright_c2.js` |
| Suite complète après la campagne | **1 000 tests** : 984 réussis, 16 « xfail » (15 anomalies de la campagne n° 2 + C1) |

| Gravité | Nombre | Anomalies |
|---|---|---|
| **Bloquant** | 4 | C2-01 (photos perdues à l'ouverture d'un audit), C2-02, C2-03, C2-08 (plantages sur fichier ou réponse hors norme) |
| **Majeur** | 3 | C2-04 (repérage amiante non proposé si la période est inconnue), C2-05 (étape différente selon le document), C2-12 (petits visages non floutés) |
| **Mineur** | 5 | C2-06, C2-07, C2-09, C2-10, C2-11 |
| **Question de méthode** | 3 | QM2-01 à QM2-03 |

**Le moteur reste juste.** Toute la campagne n° 1 (règle par règle, bornes, priorités, données
manquantes, questions masquées, invariants, cohérence écran / CSV / PDF, questionnaire et matrice) passe
sur `main`, et la recherche systématique des valeurs pile sur un seuil, refaite indépendamment
(≈ 170 cas réalistes : 2 vol/h, ratio 0,15, rapport 0,4, 0,8 m²/enfant), ne trouve plus aucun écart.

**Les défauts nouveaux sont dans les fonctions ajoutées** :

- **C2-01 (bloquant)** : à l'ouverture d'un audit enregistré, une photo que le stockage ne renvoie pas
  (coupure réseau, erreur passagère) est retirée de l'audit, qui est aussitôt réenregistré : la photo est
  perdue pour de bon.
- **C2-12 (majeur, données personnelles)** : les visages sont détectés après réduction de la photo à
  1 600 px. Un visage de 90 à 120 px dans une photo de téléphone de 4 000 px (un élève au fond de la
  classe) n'est plus détecté, donc pas flouté, alors qu'il l'est sur l'image d'origine.
- **C2-04 (majeur)** : quand la période de construction n'est pas renseignée, le passage en travaux ne
  propose jamais le repérage amiante avant travaux (CCTP 10), alors que l'alerte PR-AL3 traite ce même
  cas comme une suspicion d'amiante. 55 saisies aléatoires sur 400 sont concernées.
- **C2-05 (majeur)** : la même action est placée à l'« étape 1 — Dès maintenant » dans le compte rendu et
  à l'horizon 2 ou 3 dans le pré-programme (60 saisies aléatoires sur 150), par exemple des brasseurs à
  remettre en service sous un faux plafond.

### Rejouer la campagne

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

```bash
python -m pytest tests/test_campagne2.py -m "not interface"
```

```bash
python -m pytest tests/test_campagne2.py -m interface
```

```bash
python -m pytest tests
```

```bash
for g in 1 2 3 4 5; do python tests/fuzz_excel.py 40 $g; done
```

Le test « vrai portrait » utilise `tests/donnees/portrait_nasa.jpg` (portrait officiel d'une astronaute,
NASA, domaine public, fourni par scikit-image), seule façon de vérifier la détection YuNet sur un vrai
visage : les tests existants simulent la détection.

## 2. Anomalies

### 2.1 Bloquant

| Id | Domaine | Description | Déclencheur | Attendu | Obtenu | Test |
|---|---|---|---|---|---|---|
| C2-01 | Supabase / photos | `ouvrir_audit` (app.py) télécharge les photos en ignorant les erreurs, `charger` retire les descriptions sans image, puis `enregistrer` réécrit l'audit : la photo disparaît de l'audit enregistré (le fichier reste orphelin dans le stockage jusqu'à la purge). | Coupure réseau ou erreur du stockage pendant l'ouverture d'un audit | Photo conservée dans l'audit, signalée « non disponible » | Description supprimée et enregistrée | `test_ouvrir_un_audit_ne_perd_pas_les_photos_si_le_telechargement_echoue` |
| C2-02 | photos | Une image de plus de 179 mégapixels lève `DecompressionBombError` (Pillow) ; l'ajout de photo ne rattrape que `ValueError` : trace Python à l'écran. | Fichier image hors norme (0,6 Mo de PNG suffit) | Message « image trop grande » | Plantage | `test_image_geante_refusee_proprement` |
| C2-03 | import | Le bloc `audit` d'un JSON importé n'est pas contrôlé par `validation.valider` : `"audit": "École A"` passe l'import, puis fait planter le compte rendu et l'étape Identification (`'str' object has no attribute 'get'`). | JSON retouché à la main | Bloc ignoré ou normalisé, avec avertissement | Plantage | `test_import_bloc_audit_invalide` |
| C2-08 | lecture par IA | `IA.vers_saisie` suppose que la réponse respecte le schéma imposé ; un bloc `ecole` en texte ou des `locaux` en texte (avec une solution citée deux fois) lèvent une exception que l'interface ne rattrape pas (seule `LectureImpossible` l'est). | Réponse du modèle non conforme au schéma (rare) | « Réponse de l'IA inexploitable, remplissez à la main » | Plantage | `test_lecture_ia_reponse_non_conforme` |

### 2.2 Majeur

| Id | Domaine | Description | Entrée minimale | Attendu (source) | Obtenu | Test |
|---|---|---|---|---|---|---|
| C2-04 | passage en travaux | `travaux.contexte` ne retient l'amiante que pour une période de construction renseignée avant 1997. Période vide ou « Non renseigné » : aucun repérage amiante (CCTP 10) dans le dossier ni dans la feuille de route. Incohérent avec PR-AL3 (période inconnue = suspicion) et avec l'obligation de repérage avant travaux des bâtiments dont le permis est antérieur au 1ᵉʳ juillet 1997. | `exemple_ecole_sud.json` sans B-01 | CCTP 10 proposé (principe de prudence, règle du doute § I.f) | Absent | `test_reperage_amiante_si_periode_inconnue` |
| C2-05 | sorties | L'étape d'une action dans le compte rendu (`rapport.phase`, par local) et son horizon dans le pré-programme (`travaux._horizon`, borné par le niveau : B → au moins 2, C → 3) divergent : brasseurs à remettre en service sous faux plafond (étape 1 / horizon 2), ventilation nocturne avec grilles, casquettes ou vérandas à réparer (étape 1 / horizon 3). Les deux documents sont destinés aux mêmes élus. | brasseur présent hors service, faux plafond démontable | Même étape dans les deux documents, ou explication du décalage | Étape 1 dans le compte rendu, horizon 2 dans le pré-programme | `test_meme_etape_dans_le_compte_rendu_et_le_pre_programme` (fréquence : `test_ecarts_d_etape_frequents_sur_tirages`) |
| C2-12 | photos (données personnelles) | La détection YuNet se fait après la réduction à 1 600 px. Visage de 120 px ou 90 px dans une photo de 4 000 × 3 000 px : détecté sur l'image d'origine, plus après réduction, donc **non flouté**. Un visage de 160 px ou plus l'est bien. L'interface conseille d'éviter de photographier des enfants, mais une photo de classe prise du fond en contient. | portrait de 120 px collé dans une image de 4 000 × 3 000 px | 1 visage flouté | 0 | `test_petit_visage_floute` |

### 2.3 Mineur

| Id | Domaine | Description | Test |
|---|---|---|---|
| C2-06 | sécurité | La fonction `purge-conservation` ne vérifie pas l'appelant : la tâche planifiée l'appelle avec la clé publique, donc n'importe qui peut la déclencher. Effet limité (elle ne supprime que des données arrivées à échéance), mais appels répétés possibles. Réserver l'appel à un secret partagé (en-tête vérifié dans la fonction). | `test_purge_reservee_a_la_tache_planifiee` |
| C2-07 | photos / import | L'identifiant d'une photo importée n'est pas contrôlé (`"../../autre-audit/x"` accepté) alors qu'il sert de nom de fichier dans le stockage et dans le ZIP. Les règles RLS empêchent l'accès à un autre audit, mais un identifiant hexadécimal devrait être exigé. | `test_identifiant_de_photo_controle` |
| C2-09 | maintenance | `st.components.v1.html` (retour en haut de page) est annoncé supprimé par Streamlit « après le 2026-06-01 » (avertissement à chaque page) : une mise à jour de Streamlit cassera cette fonction. | `test_pas_d_api_streamlit_obsolete` |
| C2-10 | interface | « Passer à l'action » à partir de l'audit en cours : les étapes 2 et 3 sont cochées « ✓ » avant d'avoir été vues. | `test_etapes_non_vues_non_cochees` |
| C2-11 | passage en travaux | La surface d'ombre à créer (quantité de l'opération « ombrage de la cour ») utilise 0,8 m²/enfant, 100 / 150 m² et 6 classes écrits en dur : elle ne suit pas les seuils modifiés dans les Réglages, contrairement à EX-AL. | `test_quantite_ombrage_suit_les_seuils` |

### 2.4 Questions de méthode et observations

| Id | Constat |
|---|---|
| QM2-01 | **Visa du pré-programme** : le statut « validé » demande seulement quatre champs texte remplis (auditeur, date, visa, date du visa). Rien n'empêche l'auditeur de viser son propre travail ni de saisir une date au mauvais format. Avec les comptes Supabase, le visa pourrait être rattaché à un compte de chargé de mission. |
| QM2-02 | **Chiffres de la synthèse** : « 7 solutions à engager » et « 8 solutions à valider » sur l'exemple de l'école du Sud comptent trois fois les mêmes solutions (brasseurs, ventilation naturelle, protections verticales sont à engager dans un local et à valider dans un autre). Un lecteur peut les additionner (15) alors que 12 solutions existent. Préciser « dans au moins un local » ? |
| QM2-03 | **Rappel réglementaire** du pré-programme et du plan d'action (« travaux sous 100 000 € HT et études ou maîtrise d'œuvre sous 60 000 € HT dispensés de procédure, décret n° 2025-1386 ») : non vérifié par cette campagne, à faire relire par un juriste avant diffusion. |
| Observation | Compte rendu avec 60 photos très détaillées (1 Mo chacune) : PDF de 84 Mo en 19 s. Les photos sont intégrées en pleine définition (1 600 px) même en vignette de 42 mm ; une réduction à la taille d'affichage diviserait la taille du PDF. |
| Observation | L'archive ZIP importée n'a pas de limite globale (nombre de photos, taille de `saisie.json`) ; chaque photo est limitée à 20 Mo. |
| Observation | Un JSON dont la structure est très abîmée (liste à la place d'un dictionnaire…) est refusé en bloc avec le message générique « fichier illisible » : pas de plantage, comportement acceptable. |

## 3. Non-régression : campagne n° 1 rejouée sur `main`

| Partie | Résultat sur `main` |
|---|---|
| A. Excel | `fuzz_excel.py` : 5 × 40 tirages, 0 écart. Les écarts volontaires (A4 : arrondi des rapports, division par zéro → « Sous réserve ») sont documentés dans PàT. |
| B. Méthode | 174 cas « une règle », bornes, priorités, 214 cas de données manquantes, questions masquées : tout passe. ANO-01 et ANO-02 corrigées ; recherche indépendante de ≈ 170 cas pile sur un seuil : 0 écart. |
| C. Invariants | Tout passe ; matrice de dépendances inchangée (EX-AL désormais rattachée à l'ombrage de la cour). |
| D. Sorties | Écran = CSV = PDF ; plan d'action, données manquantes, alertes, fiches, débordements : tout passe sur la nouvelle structure du compte rendu (annexes A à H). |
| E. Interface | AppTest et Playwright : tout passe (barre d'étapes défilante sur téléphone, libellés courts, infobulles propres). |
| F. Questionnaire | Imports CSV robustes (CR, Windows-1252, « Q4 - libellé » + « ; », colonnes inconnues signalées, questions masquées retirées), matrice M6 / M8 conformes à E1 : tout passe. |

Les 37 anomalies de la campagne n° 1 sont corrigées comme l'annonce `docs/suivi_corrections.md`, sauf
ANO-12, laissée volontairement en attente de la décision B6. Le seul « xfail » restant de la campagne
n° 1 est C1 (B-07 sans effet, documenté).

## 4. Nouveautés testées et résultats

| Fonction | Ce qui a été testé | Résultat |
|---|---|---|
| Contrôle des imports (`validation.valider`) | 800 saisies aléatoires : jamais de plantage, résultat stable si on valide deux fois, statuts inchangés quand rien n'est hors bornes ; 3 000 saisies aux types déformés | Correct, sauf le bloc `audit` (C2-03) |
| Photos | Formats, fichiers invalides, réduction, redressement EXIF, ZIP aller-retour et archives invalides, détection sur un vrai portrait (petit, moyen, couché), image géante, poids du PDF | C2-02, C2-07, C2-12 ; détection correcte au-delà de 160 px de visage |
| Supabase | Ouverture d'un audit avec un stockage en erreur (faux serveur), relecture des migrations (RLS, fonctions privées, limites de débit) et de la fonction de purge | C2-01, C2-06 ; règles RLS cohérentes (chaque auditeur ne voit que ses audits, dépôt anonyme limité à un questionnaire ouvert) |
| Passage en travaux | 400 saisies aléatoires : opérations = locaux à engager ou à valider du compte rendu, niveau C → horizon 3, niveau B → horizon ≥ 2, alerte AL → niveau C, patrimoine + façade → niveau C, MOE → CCTP MOE ; documents (pré-programme, plan d'action, dossier ZIP de CCTP Word) générés sans erreur ni balise non remplacée | C2-04, C2-05, C2-11 |
| Lecture par IA | 3 000 réponses simulées, conformes ou non au schéma ; fusion des solutions citées deux fois ; actions hors catalogue | C2-08 |
| Interface « Passer à l'action » | Deux départs (audit en cours, diagnostic existant), toutes les étapes, recherche d'ingénierie hors ligne (message clair), téléphone 375 px (aucun défilement horizontal), photo et ZIP dans Chromium | C2-09, C2-10 |

## 5. Ce qui n'a pas pu être testé

- **Supabase réel** : tout passe par le faux serveur des tests (`tests/faux_supabase.py`), qui reproduit
  les règles RLS ; les migrations SQL et la fonction de purge ont été relues, pas exécutées.
- **API Claude réelle** (lecture d'un vrai rapport PDF) et **API publiques** de recherche d'ingénierie
  (geo.api.gouv.fr, annuaire, SIRENE) : hors d'atteinte depuis l'environnement de test (réseau fermé) ;
  seuls les faux clients et le message hors ligne ont été vérifiés.
- **Floutage sur de vraies photos de classe** : un seul portrait libre de droits ; les visages de profil,
  masqués ou en groupe n'ont pas été testés.
- **Caméra de l'appareil** (`st.camera_input`) et appareils mobiles réels.
- **Rappel réglementaire** des seuils de procédure (QM2-03).

## 6. Correctifs proposés (non appliqués)

**C2-01** — ne pas retirer une photo dont l'image n'a pas pu être téléchargée (`app.py`, `charger` et
`ouvrir_audit`) :

```diff
-    base["photos"] = [ph for ph in base["photos"] if ph.get("id") in ss.photos_bin]  # description sans image : retirée
+    # description sans image : conservée si elle est déjà enregistrée dans la base (téléchargement en échec)
+    base["photos"] = [ph for ph in base["photos"] if ph.get("id") in ss.photos_bin or ph.get("envoyee")]
```

et, dans `ouvrir_audit`, prévenir l'utilisateur des photos non téléchargées plutôt que de les ignorer.

**C2-12** — détecter les visages sur l'image d'origine, puis flouter sur l'image réduite (`surya/photos.py`) :

```diff
     img = ImageOps.exif_transpose(img).convert("RGB")
+    zones = detecter_visages(img) if flouter_visages else []   # pleine résolution
+    echelle = min(1.0, COTE_MAX / max(img.size))
     img.thumbnail((COTE_MAX, COTE_MAX))
-    zones = detecter_visages(img) if flouter_visages else []
+    zones = [tuple(round(v * echelle) for v in z) for z in zones]
```

(pour une image très grande, découper en tuiles de 1 600 px avec recouvrement plutôt que d'agrandir le
modèle).

**C2-02** — dans `photos.preparer`, rattraper aussi l'image trop grande :

```diff
-    except (UnidentifiedImageError, OSError) as e:
+    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
```

**C2-03** — contrôler le bloc `audit` dans `validation.valider` :

```diff
-    out = {k: d.get(k) for k in ("audit",) if k in d}
+    a = d.get("audit")
+    if a is not None and not isinstance(a, dict):
+        notes.append("Bloc « audit » illisible, ignoré.")
+    out = {"audit": {k: str(v)[:300] for k, v in (a if isinstance(a, dict) else {}).items()
+                     if isinstance(v, (str, int, float)) and not isinstance(v, bool)}}
```

**C2-04** — période inconnue = suspicion d'amiante (`surya/travaux.py`, `contexte`) :

```diff
-        "amiante": b.get("B-01") in ("Avant 1948", "De 1948 à 1974", "De 1975 à 1997"),
+        "amiante": b.get("B-01") != "Après 1997",   # période inconnue : repérage par prudence (comme PR-AL3)
```

**C2-08** — rattraper toute erreur de conversion de la réponse de l'IA (`app.py`) :

```diff
-        saisie, remarques = IA.vers_saisie(proposition, fichier.name)
+        try:
+            saisie, remarques = IA.vers_saisie(proposition, fichier.name)
+        except Exception:
+            st.error("La réponse du service d'IA est inexploitable : réessayez ou remplissez la saisie à la main.")
+            return
```

**C2-07** — `photos.valider` : n'accepter que `re.fullmatch(r"[0-9a-f]{6,40}", id)`.

**C2-11** — `travaux._quantite` : lire `moteur.parametres(donnees.get("parametres"))` pour P_OMBRE_ELEM,
P_OMBRE_MAT_CL, P_OMBRE_MAT_1 et P_OMBRE_MAT_2.

**C2-05** et **C2-06** demandent une décision : aligner l'étape du compte rendu sur l'horizon du
pré-programme (ou l'inverse, en expliquant le décalage dans le pré-programme) ; protéger la fonction de
purge par un secret partagé vérifié dans `index.ts` et stocké dans le coffre (Vault).
