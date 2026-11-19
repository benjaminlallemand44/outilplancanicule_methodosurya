# Suivi des corrections — campagne de tests n° 1

Réponse au rapport `docs/rapport_tests.md` (campagne du 19/11/2026). Corrections faites le 20/11/2026.
Chaque anomalie corrigée a un test qui passe ; ses marqueurs « xfail » ont été retirés.

## Bloquant

| Id | Correction |
|---|---|
| ANO-26 | Import CSV robuste : fins de ligne CR (« CSV Macintosh »), fichier binaire (classeur, PDF) → message clair, jamais de plantage. |
| ANO-30 | Import contrôlé (`surya/validation.py`) : une valeur hors bornes (E-30 > 4, valeur négative) est retirée et signalée. L'éditeur n'impose plus de bornes à une valeur importée et l'affiche avec un avertissement. |
| ANO-07 | Seuils importés en texte (« 2,4 ») convertis ; un seuil inexploitable garde la valeur de la méthode. L'onglet Seuils ne plante plus. |
| ANO-31 | Ouvrir une fiche ne modifie plus les données : nombre décimal conservé, réponse hors liste conservée (avec avertissement) tant que l'utilisateur ne la change pas, plus de mur vide ajouté. |

## Majeur

| Id | Correction |
|---|---|
| ANO-01 | Rapports calculés arrondis avant comparaison aux seuils (comme un tableur) : 243 m³/h pour 45 m² × 2,70 m donne bien « En place ». |
| ANO-02 | Surface, hauteur, diamètre ou nombre de brasseurs nul : donnée invalide → « Sous réserve » (au lieu de « Recommandé »). Écart volontaire avec l'Excel, documenté (PàT A4). |
| ANO-10 | EX-AL rattachée à la solution « Ombrage autoportant ou végétal de la cour » : présente dans le CSV, les marqueurs des tableaux et tous les documents. |
| ANO-17 | Séparateur du CSV choisi selon les en-têtes « Qn » reconnus (les virgules des libellés ne l'emportent plus). |
| ANO-19 | Réponses à des questions masquées retirées à l'import (avec avertissement) et non comptées dans la synthèse. |
| ANO-20 | CSV enregistré par Excel sous Windows (Windows-1252) lu correctement. |
| ANO-22, ANO-23 | M8 : « Non évaluable » en dessous de 3 réponses ou sans local. |
| ANO-27 | Import Excel : « oui » lu comme « Oui » ; une réponse hors liste est retirée (donnée manquante) et signalée, au lieu de rendre la règle fausse. |

## Mineur

| Id | Correction |
|---|---|
| ANO-03 | Barre d'étapes sur une seule ligne, défilable horizontalement sur téléphone. |
| ANO-04 | Libellés courts dans la barre d'étapes (« Espaces ext. », « Questionnaires »), libellé complet en infobulle. |
| ANO-05 | Libellés des questions sans balisage (« · L-01 » en texte simple). |
| ANO-06 | Légende des statuts dans le même ordre à l'écran et dans les PDF. |
| ANO-08 | Nombres saisis en texte dans l'Excel (« 60 », « 2,5 ») convertis. |
| ANO-09 | Un nombre de baies égal à 0 compte le type de baie comme présent, comme l'Excel. |
| ANO-11 | Quantités : un nombre de baies nul n'affiche plus « NO : ». |
| ANO-13 | Fiches : la distance vitrage-façade n'apparaît que si elle a un objet. |
| ANO-14 | Décimales à la française dans les PDF. |
| ANO-15 | Numérotation continue du compte rendu sans local ni espace. |
| ANO-16 | Emojis et caractères non affichables retirés des PDF (plus de carrés noirs). |
| ANO-18 | Colonnes inconnues d'un CSV signalées. |
| ANO-21 | M6 : minimum de 3 réponses vérifié pour chaque indicateur. |
| ANO-24 | « à partir de 30 % » au lieu de « au-delà de 30 % ». |
| ANO-25 | « ... » reconnu comme « … » à l'import. |
| ANO-28 | Les quatre écarts entre l'outil et l'Excel actuel sur l'exemple sont listés (PàT § A). |
| ANO-29 | Messages d'import en clair (« ce classeur n'est pas un Excel de la méthode SURYA… »). |
| ANO-32 | Les réponses de l'exemple et des imports ont un identifiant : « Supprimer cette réponse » fonctionne. |
| ANO-33 | Noms de locaux ou d'espaces en double signalés (liste et vérification). |
| ANO-34 | Toiture sans cas applicable avec une saisie complète : « configuration non prévue par les règles », plus présentée comme une donnée manquante. |
| ANO-35 | « À compléter » ne cite que les questions restées sans réponse. |
| ANO-36 | Nombre de questions annoncé exact (24). |
| ANO-37 | Vérification des façades : libellés des questions au lieu des codes. |

## Non corrigé (décision de méthode)

| Id | Raison |
|---|---|
| ANO-12 | E-20 « Aucune » + une orientation : comportement de l'Excel conservé ; réglé si « Aucun » devient exclusif (PàT B6, à trancher). |
| QM-01 à QM-10 | Questions de méthode : reprises dans `docs/points_a_trancher.md`, § F1 à F10 (QM-02 → F2, etc.). |
| C1 | B-07 sans effet : documenté (PàT C1). |
