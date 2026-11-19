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

Dans la barre latérale, menu **Données** : charger l'exemple de l'Excel, importer un Excel de la
méthode déjà rempli (`.xlsx`), exporter / réimporter une saisie (`.json`).

## Ce que fait l'outil

Un **parcours guidé**. Au départ, l'utilisateur choisit :

- **ce qu'il veut produire** :
  - *Résultats de faisabilité* (équivalent de l'Excel) : Bâtiment → Façades → Locaux → Espaces
    extérieurs → Vérification → Résultats (tableau, PDF des résultats, CSV) ;
  - *Diagnostic complet* : Identification → Bâtiment → Façades → Locaux → Espaces extérieurs →
    Vérification → Documents (compte rendu complet en PDF, PDF des résultats, CSV), avec en plus les
    observations par local et espace et un commentaire général ;
- **comment saisir les locaux et espaces** : *pas à pas* (un thème par écran, « Thème suivant ») ou
  *fiches à onglets* (tous les thèmes accessibles librement). Modifiable à tout moment.

On avance avec « Suivant » ; les étapes déjà vues restent accessibles dans la barre d'étapes. Rien
n'est bloquant : chaque écran signale les questions sans réponse, et l'étape Vérification récapitule
tout ce qui manque avec un bouton « Compléter ». Les documents se génèrent à la dernière étape.

Le menu **⚙️ Réglages** (discret, en haut à droite) regroupe les seuils des règles (onglet
`Paramètres` de l'Excel), l'exemple, l'import (JSON ou Excel de la méthode) et l'export de la saisie.

**Compte rendu PDF** : page de garde, cadre de l'audit et statuts, synthèse, plan d'action par
solution (engageable / à valider / en place / exclue, avec quantités relevées), alertes typées AL / VA,
données manquantes, fiche détaillée de chaque local et espace, seuils utilisés. Il est généré par
`surya/rapport.py` (reportlab), sans dépendance à l'interface.

Les questions conditionnelles (« - si B-09 = Oui : … ») ne s'affichent que lorsqu'elles ont un objet.

## Organisation du code

```
app.py                      interface Streamlit (aucune règle métier)
surya/moteur.py             moteur de calcul : états des réponses, règles, statuts
surya/questions.py          questionnaire et conditions d'affichage
surya/import_excel.py       lecture d'un Excel de la méthode
surya/rapport.py            compte rendu PDF
surya/referentiel.json      textes extraits de l'Excel (questions, options, règles, seuils)
surya/exemple.json          jeu d'exemple (celui de l'Excel)
outils/extraire_referentiel.py   régénère referentiel.json depuis l'Excel
reference/                  Excel d'origine et document de méthode (PDF)
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

```bash
python -m pytest tests
```

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

Contenu de la méthode : © 2026 ACTEE et SURYA Ingénierie,
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr).
