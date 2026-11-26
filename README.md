# Outil méthode SURYA — audit de faisabilité d'actions d'adaptation

Maquette (preuve de concept) qui remplace l'Excel *« Outil d'aide au test de la méthode d'audit de
faisabilité d'actions d'adaptation »* par une interface Streamlit. Toute la logique de l'Excel est
reprise en Python ; rien n'est enregistré en base pour l'instant.

## Lancer

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

Menu **Réglages** (en haut à droite) : charger un exemple, importer un Excel de la méthode déjà rempli
(`.xlsx`), exporter / réimporter une saisie (`.json`, ou `.zip` avec les photos), notice d'utilisation.

## Passage en travaux (3ᵉ parcours)

Après le diagnostic : **pré-programme** à présenter aux élus (opérations par levier, niveaux, horizons),
**accompagnement** (maîtrise d'œuvre, structures d'ingénierie du territoire trouvées à partir du code
postal), **mise en œuvre** (CCTP de maîtrise d'œuvre ou fiches travaux) et **consultations** (CCTP des
prestations préalables et des travaux, archive ZIP). Accessible depuis l'étape Documents du diagnostic
complet, ou depuis l'écran de départ, à partir de l'audit en cours ou d'un diagnostic existant réalisé
hors de la méthode (saisie simplifiée, lecture du rapport par IA facultative). Détail :
`docs/passage_en_travaux.md` ; code : `surya/travaux.py`, `surya/cctp.py`, `surya/ingenierie.py`,
`surya/lecture_ia.py`, `surya/rapport_preprogramme.py`, `surya/rapport_travaux.py`, `surya/kit/`.

## Base de données (Supabase)

Facultative : sans la section `[supabase]` dans les secrets Streamlit, l'outil reste une maquette.
Avec elle : comptes des auditeurs, audits enregistrés automatiquement à chaque étape, questionnaire en
ligne enregistré dans la base, photos dans un stockage privé. Mise en service, sécurité (RLS) et points
à décider : `docs/supabase.md` ; schéma : `supabase/migrations/`.

## Version, déploiement et gouvernance

- **Branche de référence : `main`.** L'application Streamlit Cloud doit être déployée depuis `main`.
  Les versions sont taguées (`v0.1-poc`, …) ; le numéro (`VERSION`) et le commit déployé sont affichés
  en bas de chaque page de l'application.
- **Dépendances figées** dans `requirements.txt` ; outils de test dans `requirements-dev.txt`.
- **Intégration continue** (`.github/workflows/tests.yml`) : à chaque push, les tests hors recalcul de
  l'Excel par LibreOffice et hors navigateur réel (`pytest -m "not excel and not interface"`).
- **Page de présentation** statique dans `site/`, publiée par GitHub Pages
  (`.github/workflows/pages.yml`).
- **Notice d'utilisation** : `docs/notice_utilisation.md` (données, hébergement et mesure d'audience
  de la plateforme, écarts avec l'Excel), aussi affichée dans l'application.
- **Licences** : code sous licence MIT (`LICENSE`) ; contenu de la méthode © ACTEE et SURYA
  Ingénierie, diffusion prévue sous CC BY-SA 4.0 (licence pas encore déposée) ; polices Bitter et Schibsted Grotesk sous SIL OFL 1.1
  (`static/fonts/OFL-*.txt`) ; logos ACTEE et FNCCR hors licence MIT.

## Ce que fait l'outil

Un **parcours guidé**. Au départ, l'utilisateur choisit :

- **ce qu'il veut produire** :
  - *Résultats de faisabilité* (équivalent de l'Excel) : Bâtiment → Locaux → Espaces extérieurs →
    Façades → Vérification → Résultats (tableau, PDF des résultats, CSV) ;
  - *Diagnostic complet* : Identification → Bâtiment → Locaux → Espaces extérieurs → Façades →
    Questionnaires usagers → Vérification → Documents (compte rendu complet en PDF, PDF des résultats, CSV), avec en plus les
    observations par local et espace et un commentaire général ;
- **comment remplir le questionnaire** (bâtiment, locaux, espaces) : *pas à pas* (un bloc par écran,
  « Suivant ») ou *fiches à onglets* (tous les blocs accessibles librement). Modifiable à tout moment.

On avance avec « Suivant » ; les étapes déjà vues restent accessibles dans la barre d'étapes. Rien
n'est bloquant : chaque écran signale les questions sans réponse, et l'étape Vérification récapitule
tout ce qui manque avec un bouton « Compléter ». Les documents se génèrent à la dernière étape.

Le menu **⚙️ Réglages** (discret, en haut à droite) regroupe les seuils des règles (onglet
`Paramètres` de l'Excel), l'exemple, l'import (JSON ou Excel de la méthode) et l'export de la saisie.

**Compte rendu PDF** : page de garde, cadre de l'audit et statuts, synthèse, plan d'action par
solution (engageable / à valider / en place / exclue, avec quantités relevées), alertes typées AL / VA,
données manquantes, fiche détaillée de chaque local et espace, seuils utilisés. Il est généré par
`surya/rapport.py` (reportlab), sans dépendance à l'interface.

**Questionnaire usagers** (diagnostic complet) : questionnaire confort estival (Q1 à Q24) en ligne
(lien `?questionnaire=<code>`), import CSV au même format, saisie de questionnaires papier, synthèse
globale et matrice de correspondance ressenti / préconisations (proposition, voir
`docs/points_a_trancher.md` § E1). Maquette : aucune réponse n'est stockée sur un serveur ; le passage
à Supabase est préparé (`surya/stockage.py`, `docs/supabase.md`).

**Photos** (diagnostic complet) : photos générales du bâtiment (étape Identification) et photos de
chaque local et espace (thème « Photos » de leur fiche), par fichier ou caméra de l'appareil, ou en
une fois après la visite puis rattachées une à une. Chaque photo est réduite (1 600 px), redressée,
datée d'après la prise de vue, et les visages détectés sont floutés (modèle YuNet, `surya/modeles`).
Étiquettes et légendes ; liste de contrôle des photos attendues (non bloquante) ; export / import
`.zip` (saisie + photos). Le compte rendu les reprend : façade dans la synthèse, planche en partie 2,
points à lever en partie 5, toutes les photos dans les fiches. Code : `surya/photos.py`.

Les questions conditionnelles (« - si B-09 = Oui : … ») ne s'affichent que lorsqu'elles ont un objet.

## Organisation du code

```
app.py                      interface Streamlit (aucune règle métier)
surya/moteur.py             moteur de calcul : états des réponses, règles, statuts
surya/questions.py          questionnaire et conditions d'affichage
surya/import_excel.py       lecture d'un Excel de la méthode
surya/rapport.py            compte rendu PDF
surya/questionnaire.py      questionnaire usagers : questions, CSV, synthèse, matrice
surya/validation.py         contrôle et normalisation des saisies importées (JSON, Excel)
surya/stockage.py           stockage des réponses (mémoire ; Supabase plus tard)
surya/referentiel.json      textes extraits de l'Excel (questions, options, règles, seuils)
surya/exemple.json          jeu d'exemple (celui de l'Excel)
outils/extraire_referentiel.py   régénère referentiel.json depuis l'Excel
reference/                  Excel d'origine, document de méthode, questionnaire usagers (PDF)
tests/                      tests
```

Le moteur est indépendant de l'interface : `moteur.calculer(donnees)` prend un dictionnaire
(`batiment`, `facades`, `locaux`, `espaces`, `parametres`) et renvoie les statuts. Ce dictionnaire est
exactement ce qu'il faudra stocker plus tard (par exemple une colonne JSON par audit dans Supabase).

### Logique reprise de l'Excel

- Chaque réponse a un état : valeur saisie, `#SO` (question sans objet) ou `#INC` (inconnue : vide ou
  « Non évalué »).
- Chaque règle vaut 1 (vraie), 0 (fausse) ou 0,5 (indéterminée, donnée manquante) ; ET = min, OU = max.
- Dans un bloc, la première règle non fausse, par ordre de priorité, est retenue. Si elle est
  indéterminée, le statut est « Sous réserve ».

## Vérification

Environ 890 tests (pytest), issus de la campagne de tests n° 1 : rapport dans `docs/rapport_tests.md`,
corrections dans `docs/suivi_corrections.md`, prompt de campagne dans `docs/prompt_tests.md`.

```bash
pip install -r requirements.txt pytest pdfplumber
```

```bash
python -m pytest tests -m "not excel and not interface"
```

```bash
python -m pytest tests -m "excel or interface"
```

Le marqueur `excel` demande LibreOffice ; `interface` demande Node et Playwright.

```bash
python tests/fuzz_excel.py 80
```

`fuzz_excel.py` (nécessite LibreOffice) écrit des réponses aléatoires dans une copie de l'Excel, fait
recalculer les formules par LibreOffice et compare au moteur Python la valeur de **chaque règle**, le
statut de chaque bloc, les alertes et l'onglet Résultats. Dernier passage : 80 tirages, soit 800 locaux
et 400 espaces, 0 écart.

## Écarts avec l'Excel

L'Excel de référence contient des erreurs de références. Le moteur applique la logique voulue par la
méthode (libellés des règles) ; la comparaison ci-dessus est faite avec une copie de l'Excel où ces
références sont réparées (`corriger_classeur` dans `tests/fuzz_excel.py`). **Sur ces points, l'outil
ne donne donc pas le même résultat que l'Excel actuel.**

1. **Murs extérieurs 2, 3 et 4** (`Calc_Locaux`, lignes 26 à 37 et 76 à 90) : les formules lisent
   `Saisie_Locaux` une ligne trop bas (MEX-04 du mur 2 lit la ligne 61 au lieu de 60, etc.) et un type
   de baie est en `#REF!`. Dans l'Excel, seul le mur 1 est donc correctement pris en compte.
2. **MEX-17, type de commande** (`Calc_Locaux` ligne 15 et règle FT-7) : `#REF!`. Ici, FT-7 teste
   « MEX-17 n'est ni Électrique ni Automatique ».
3. **BA-18, débit maximal de ventilation** (`Calc_Locaux` ligne 65, règles VM-7, VM-9, VM-10) : la
   question n'a pas de ligne de saisie dans l'Excel (`#REF!`). Elle est ajoutée dans l'outil (m³/h),
   affichée si le local est desservi par la ventilation mécanique.

Autres différences, sans effet sur les statuts : le nombre de locaux et d'espaces n'est pas limité
(10 et 5 dans l'Excel) ; les alertes sont affichées dans les résultats (l'onglet `Résultats` de l'Excel
ne les montre pas).

À noter : la règle VN-7 parle de baies ouvrantes sur deux murs « d'orientations différentes », mais la
formule de l'Excel compte les murs sans comparer leurs orientations. Le moteur fait comme la formule.

## Suite possible

- Persistance (Supabase) : comptes, liste des audits, enregistrement du dictionnaire de saisie.
- Points de méthode à trancher : voir `docs/points_a_trancher.md`.
- Rattachement au diagnostic confort d'été global.
- Photos par question décisive, insérées dans le compte rendu.

## Licence

Contenu de la méthode : © 2026 ACTEE et SURYA Ingénierie. Diffusion prévue sous licence
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) : la licence n'est pas encore déposée,
le bandeau de l'application est prêt pour ce dépôt.
