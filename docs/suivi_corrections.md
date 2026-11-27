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

---

# Suivi des corrections — campagne de tests n° 2

Réponse au rapport `docs/rapport_tests_2.md` (campagne du 26/11/2026 sur `main` 15fd69d). Corrections
faites le 27/11/2026. Les tests de `tests/test_campagne2.py` qui reproduisaient chaque anomalie (« xfail »
strict) passent tous ; leurs marqueurs ont été retirés.

## Bloquant

| Id | Correction | Choix retenu |
|---|---|---|
| C2-01 | Une photo enregistrée dont l'image ne se télécharge pas à l'ouverture d'un audit reste dans l'audit (`charger(..., garder_sans_image=True)`), l'auditeur est prévenu et la fiche affiche « image non disponible ». | La photo est gardée plutôt que retirée : une erreur passagère ne doit jamais supprimer de données. Une archive importée (ZIP, JSON) garde l'ancien comportement : une description sans image y est retirée. |
| — | **Défaut plus grave trouvé en corrigeant C2-01** : l'enregistrement utilisait la saisie lue au début du passage (`D`) et non celle qu'on vient de charger. Ouvrir un audit le réenregistrait donc avec la saisie affichée avant l'ouverture : avec un écran vide, l'audit en base était vidé. `enregistrer()` et `code_audit()` lisent désormais `ss.donnees`. Test : `test_ouvrir_un_audit_ne_l_ecrase_pas`. | Base de la maquette vérifiée le 27/11/2026 : les deux audits remplis sont intacts (6 locaux chacun). |
| C2-02 | Image de plus de 179 mégapixels : message « image trop grande » au lieu d'un plantage. | — |
| C2-03 | Bloc « audit » d'un JSON importé contrôlé : s'il n'est pas un dictionnaire, il est ignoré avec un avertissement ; seuls les textes et nombres courts sont gardés. | — |
| C2-08 | `lecture_ia.vers_saisie` accepte une réponse hors schéma (école ou locaux en texte, listes mal formées) : ce qui est lisible est gardé, le reste écarté avec une remarque ; filet de sécurité dans l'interface (« réponse inexploitable, remplissez à la main »). | — |

## Majeur

| Id | Correction | Choix retenu |
|---|---|---|
| C2-04 | Repérage amiante avant travaux (CCTP 10) proposé dès que la période de construction n'est pas « Après 1997 », donc aussi quand elle est inconnue. | Prudence, comme PR-AL3 et la règle du doute. Ajouté aux points à trancher (F11) pour confirmation. |
| C2-05 | L'étape du compte rendu est bornée par le niveau d'accompagnement du pré-programme : niveau B → étape 2 au moins, niveau C → étape 3 (`rapport._borner_phases`). Plus aucun écart sur 150 saisies aléatoires (60 avant). | Les élus lisent la même étape dans les deux documents. Proposition ajoutée aux points à trancher (G4). |
| C2-12 | Visages cherchés sur l'image d'origine (ramenée au plus à 4 096 px), puis floutés sur l'image réduite à 1 600 px. Les visages de 90 et 120 px d'une photo de 4 000 px sont floutés. | Pas de découpage en tuiles : 4 096 px couvrent les photos de téléphone courantes (12 Mpx). |

## Mineur

| Id | Correction | Choix retenu |
|---|---|---|
| C2-06 | La fonction `purge-conservation` exige le secret partagé `purge_secret` (en-tête `x-purge-secret`), tiré au hasard dans la base, rangé dans le coffre et vérifié par `public.verifier_secret_purge` (rôle de service seulement). Migration `20261127000000_purge_secret.sql` appliquée, fonction redéployée, vérifiée (401 sans secret, 200 pour la tâche). | Le secret ne passe ni par le dépôt ni par une personne : il naît et reste dans la base. |
| C2-07 | Identifiant de photo importé : lettres et chiffres seulement (1 à 40), sinon la photo est ignorée et signalée. | — |
| C2-09 | `st.iframe` remplace `st.components.v1.html` pour le retour en haut de page. | — |
| C2-10 | Passage en travaux : seules les étapes déjà vues sont ouvertes et cochées ; la dernière étape vue est gardée dans la saisie (`travaux.etape_vue`). | — |
| C2-11 | Surface d'ombre à créer calculée avec les seuils de la méthode, y compris ceux modifiés dans les Réglages (`P_OMBRE_ELEM`, `P_OMBRE_MAT_CL`, `P_OMBRE_MAT_1`, `P_OMBRE_MAT_2`). | — |

## Observations

| Constat | Suite |
|---|---|
| PDF de 84 Mo avec 60 photos | Photos réduites à leur taille d'affichage (environ 200 dpi) dans le compte rendu. |
| Archive ZIP sans limite globale | Au plus 300 photos et 300 Mo de photos, saisie de 20 Mo au plus ; au-delà, message clair. |
| JSON très abîmé refusé en bloc | Comportement jugé acceptable, inchangé. |

## Points à trancher (non tranchés par l'outil)

| Id | Où |
|---|---|
| QM2-01 (visa du pré-programme) | PàT H1. Inchangé dans l'outil. |
| QM2-02 (chiffres de la synthèse) | PàT G5. Libellé « dans au moins un lieu » proposé dans l'outil. |
| QM2-03 (rappel réglementaire) | PàT H2. Relecture par un juriste. |
| C2-04, C2-05 | PàT F11 et G4 : correction appliquée à titre de proposition, à confirmer. |
