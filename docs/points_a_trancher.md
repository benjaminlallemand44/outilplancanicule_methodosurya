# Points à trancher — outil méthode SURYA

Mise à jour du 20/11/2026, après la campagne de tests n° 1 (`docs/rapport_tests.md`). Relevé établi en
portant dans l'outil :

- toutes les formules de l'Excel `2611111_outil_aide_test_methode-1.xlsx` (règles « version du
  27/10/2026 ») ;
- le document « Méthode de l'audit de faisabilité d'actions d'adaptation » (version 01 du 27/10/2026) ;
- le « Questionnaire confort estival » (version 01 du 11/11/2026).

Chaque point a été revérifié sur l'outil, et par la campagne de tests. Six catégories :

- **A. Erreurs de l'Excel** : des références cassées. La correction ne fait pas débat, mais elle change
  des résultats ; à valider.
- **B. Points de méthode à trancher** : le libellé d'une règle et sa formule ne disent pas la même
  chose, ou un cas n'est pas prévu.
- **C. Points mineurs** : cohérence des libellés, questions sans effet.
- **D. Écarts entre l'Excel et le document de méthode.**
- **E. Questionnaire usagers** : matrice de correspondance proposée et points à préciser.
- **F. Questions de méthode issues de la campagne de tests.**

Les décisions déjà prises sont regroupées à la fin.

Pour chaque point, la colonne « Dans l'outil » indique ce que fait la maquette aujourd'hui.

## A. Erreurs de l'Excel (corrigées dans l'outil)

| N° | Constat | Où | Dans l'outil |
|---|---|---|---|
| A1 | Les formules des **murs extérieurs 2, 3 et 4** lisent `Saisie_Locaux` une ligne trop bas : pour le mur 2, MEX-04 lit la ligne 61 (la distance MEX-05) au lieu de la ligne 60, et ainsi de suite jusqu'aux types de baie. Un type de baie est en `#REF!`. Seul le mur 1 est donc correctement pris en compte. | `Calc_Locaux`, lignes 26 à 37 et 76 à 90 | Les 4 murs sont lus correctement. |
| A2 | **MEX-17** (type de commande des baies en plafond) est en `#REF!` : la question est passée de cases à cocher à une liste, les formules n'ont pas suivi. La règle FT-7 est cassée dès que MEX-16 = Oui. | `Calc_Locaux` ligne 15, `Règles_Locaux` ligne 109 | FT-7 teste « MEX-17 n'est ni Électrique ni Automatique ». |
| A3 | **BA-18** (débit maximal de ventilation) est utilisée par VM-7, VM-9 et VM-10 mais n'a aucune ligne de saisie (`#REF!`). Dans l'Excel, ces trois règles sont en erreur et ignorées : un local ventilé mécaniquement ressort « Recommandé » sans que le débit soit jamais vérifié. | `Calc_Locaux` ligne 65 | Question ajoutée, en m³/h (unité confirmée). Débit non renseigné : « Sous réserve » (par VM-7 indéterminée, et non VM-9 : voir F1). |
| A4 | **Cas limites traités autrement que dans l'Excel** (corrigés après la campagne de tests) : (1) une valeur pile sur un seuil calculé (2 vol/h, ratio 0,15, rapport 0,4, 0,8 m²/enfant) pouvait basculer du mauvais côté à cause de l'arithmétique des ordinateurs : les rapports sont maintenant arrondis avant comparaison, comme le fait un tableur ; (2) une surface, une hauteur, un diamètre ou un nombre de brasseurs égal à 0 rendait la règle « fausse » (dans l'Excel aussi) et menait à « Recommandé » en ventilation mécanique : c'est maintenant une donnée invalide, donc « Sous réserve ». | `Règles_Locaux`, `Règles_Extérieurs` | Arrondi des rapports ; division par zéro → « Sous réserve ». |

Conséquence sur l'exemple fourni dans l'Excel : **quatre statuts** diffèrent de l'onglet `Résultats`
de l'Excel actuel, tous dus à A1 et A2 :

| Local | Solution | Excel actuel | Outil |
|---|---|---|---|
| Classe CM1 (étage) | Ventilation naturelle nocturne | Sous réserve | Recommandé |
| Classe CM1 (étage) | Protections horizontales | Sous réserve | Recommandé |
| Salle de motricité | Protections horizontales | Sous réserve | À optimiser |
| Salle de classe | Sur fenêtres de toiture | Recommandé | Sous réserve |

Avec les références réparées, l'Excel recalculé donne exactement les résultats de l'outil.

## B. Points de méthode à trancher

### B1. VN-7 : « orientations différentes » n'est pas vérifié

- **Libellé** : baies ouvrantes sur au moins deux murs extérieurs *d'orientations différentes*.
- **Formule** : compte les murs ayant une baie ouvrante, sans comparer leurs orientations. Deux murs
  saisis « S » suffisent à obtenir « Recommandé ».
- L'exemple de l'Excel est dans ce cas : la Classe CM1 a quatre murs, tous « S ».
- **À trancher** : suivre le libellé (compter les orientations distinctes) ou la formule ? Faut-il
  interdire de saisir deux murs de même orientation ?
- **Dans l'outil** : comme la formule.

### B2. Toiture : cas sans statut déterminable

Le statut « Toiture » d'un local du dernier niveau dépend d'un des trois blocs : toiture-terrasse ou
bac acier (TT), combles perdus (CP), combles aménagés (CA). Aucun bloc ne s'applique, et le statut
reste « Sous réserve » même avec une saisie complète, dans ces cas :

- toiture à pentes **sans combles** (B-18 = Toiture à pentes, B-21 = Non) ;
- B-18 = Autre sans combles ;
- combles avec isolation B-22 = Autre.

**À trancher** : quel statut pour ces cas (« Sous réserve » assumé, « Non concerné », nouvelle règle) ?

### B3. Toiture : priorité quand deux cas s'appliquent

Si B-18 = Toiture-terrasse (ou bac acier) **et** B-21 = Oui (combles), seul le bloc TT est évalué :
les combles sont ignorés. **À trancher** : cette priorité est-elle voulue ?

### B4. Toiture : blocs sans règle par défaut, et écart de statut

- Les blocs TT et CA n'ont pas de règle « Aucun cas précédent ». Ce n'est pas bloquant (la donnée
  manquante donne « Sous réserve »), mais c'est différent des autres blocs.
- Isolant insuffisant : « Recommandé » en combles perdus (CP-7, moins de 30 cm), mais « Sous
  réserve » en rampants (CA-2, moins de 20 cm) et en toiture-terrasse (TT-1, TT-3). **À trancher** :
  différence voulue ?
- En combles aménagés, l'état de l'isolant (B-23), la ventilation (B-25) et les traces d'humidité
  (B-27) sont demandés mais ne servent à aucune règle CA.

### B5. Fenêtres de toit et vérandas partagent les mêmes réponses

MEX-16 (ouvrantes), MEX-18 (protection) et MEX-19 (état) sont posées une seule fois pour toutes les
baies en plafond. Si un local a à la fois une fenêtre de toit et une verrière, les blocs FT et VV
lisent les mêmes réponses et ne peuvent pas les distinguer. **À trancher** : acceptable, ou faut-il
dédoubler les questions ?

### B6. Réponses contradictoires dans les choix multiples

Rien n'empêche de cocher « Aucun » avec une autre option (L-10, MEX-18, MEX-29, MEX-36, BA-19, E-10,
E-20, B-28). Les règles donnent alors la priorité à l'option cochée (par exemple CQ-1 voit un
équipement même si « Aucun » est coché), **sauf pour E-20** : « Aucune » y masque les questions E-21 à
E-25, et l'ombrage adossé tombe sur OA-11 « Sous réserve » (comme dans l'Excel). **À trancher** :
rendre « Aucun » exclusif dans l'outil ? (Recommandé ; simple à faire, et règle le cas E-20.)

### B7. Une règle indéterminée masque les règles suivantes

Principe général de l'Excel : la première règle *non fausse* l'emporte, même si elle est seulement
indéterminée faute de donnée. Exemple : débord inconnu sur un mur sud et débord « Faible » sur un
autre → PH-1 est indéterminée et donne « Sous réserve », alors que PH-2 (« À optimiser ») est
certaine. **À trancher** : garder ce principe (prudent) ou retenir la première règle *certaine* en
signalant la donnée manquante ?

### B8. Protections verticales : baies au nu extérieur avec débord

PV-1 (« Non recommandé ») ne vise que le nu extérieur **sans** débord. Un local dont les baies sont au
nu extérieur avec un débord faible ou important tombe dans la règle par défaut PV-8 « Recommandé »,
dont le libellé parle pourtant de « tunnel ou nu intérieur, distance ≥ 16 cm ». **À trancher** :
voulu ?

### B9. Locaux en sous-sol

« Sous-sol » est traité comme un étage : PV-5 et PH-8 (façade sans accès pour un moyen d'élévation)
et PH-6 peuvent s'y appliquer. **À trancher** : assimiler le sous-sol au RDC pour ces règles ?

### B10. Façades non décrites

Les règles PV-5 à PV-7, PH-4, PH-6, PH-8 à PH-10 et OA-4 lisent la façade du bâtiment de même
orientation que le mur du local ou que l'espace. Si cette façade n'est pas décrite, elles restent
indéterminées (« Sous réserve »).
**Dans l'outil** (depuis le parcours guidé) : l'étape Façades vient après les locaux et les espaces ;
les façades qu'ils citent sont cochées d'office et l'étape Vérification signale celles qui restent
incomplètes. **À trancher** : rendre leur description obligatoire, ou garder un simple avertissement ?

### B11. Alerte de mutualisation OA-AL1

L'alerte se déclenche dès qu'un local du RDC, *n'importe lequel*, a un mur de même orientation qu'une
façade bordant l'espace. Rien ne vérifie que ce local donne bien sur cet espace. **À trancher** :
suffisant, ou faut-il rattacher les locaux aux espaces ?

### B12. Occupation : effectif pris en compte

- CO-1 et CO-2 ne visent que les bureaux et les classes : tout autre local (dortoir, restauration,
  salle polyvalente) ressort toujours « En place ».
- EX-AL (élémentaire) divise la surface d'ombrage par E-06, l'effectif total présent, adultes
  compris, alors que le seuil est exprimé « par enfant ».

### B13. Alertes absentes de l'onglet Résultats

L'Excel calcule 14 alertes mais ne les affiche que dans les onglets de règles. BR-AL (validation par
un électricien) est « toujours » vraie, y compris quand les brasseurs sont non recommandés.
**À trancher** : quelles alertes afficher dans la restitution, et BR-AL dans tous les cas ?
**Dans l'outil** : toutes affichées à l'écran et dans les deux PDF, typées AL / VA / point d'attention
(voir D1) ; BR-AL affichée dans tous les cas.

## C. Points mineurs

| N° | Constat |
|---|---|
| C1 | **B-07** (local de repli plus frais) n'est utilisée par aucune règle et n'est pas marquée `[info]`. |
| C2 | MEX-17 : les réponses annoncées (« Electrique / manuelle / Automatique ») ne sont pas écrites comme celles de la liste déroulante (« Électrique », « Manuelle », « Automatique (sans action humaine) »). |
| C3 | CO-1 : le libellé de condition cite quatre intitulés de L-02 (« Bureaux », « Bureau », « …salle des professeurs… ») ; un seul existe dans la liste. |
| C4 | Deux questions portent le code **MEX-25** (lignes 104 et 105 de `Saisie_Locaux`). L'outil nomme la seconde `MEX-25b` en interne. |
| C5 | La numérotation a des trous (B-02, B-17, L-05 à L-08, MEX-02, MEX-03, MEX-09, MEX-11 à MEX-13, MEX-23, MEX-27, MEX-28, MEX-31, PL-04, BA-07, BA-08, BA-10, BA-16, BA-17, E-03, E-05, E-08, E-13, E-18) : questions du carnet de visite non reprises. À confirmer qu'aucune ne manque. |
| C6 | Limites de l'Excel : 10 locaux, 5 espaces, 4 murs par local. L'outil n'a pas de limite de locaux ni d'espaces, mais garde 4 murs par local ; à confirmer. |
| C7 | F-05 propose « Non évalué », pas F-02 à F-04. |

## D. Écarts entre l'Excel et le document de méthode

Relevés en comparant l'Excel au document « Méthode de l'audit de faisabilité d'actions d'adaptation »
(SURYA, version 01 du 27/10/2026, copie dans `reference/`). Les règles sont pour l'essentiel identiques
dans les deux documents (exceptions : voir F2) ; les autres écarts portent sur le cadre de l'audit.

### D1. Type des alertes (AL / VA) non renseigné dans l'Excel

La méthode distingue l'**alerte maîtrise d'œuvre (AL)**, qui exige une étude avant de consulter, et le
**point de validation ponctuelle (VA)**, qu'un professionnel peut lever (§ I.e). L'Excel ne type pas ses
alertes. Le compte rendu PDF les classe ainsi, d'après le tableau du § I.e. **Proposition à valider :**

| Alerte | Objet | Type proposé |
|---|---|---|
| BR-AL | Électricien + capacité de la structure à porter les brasseurs | VA |
| VN-AL1 | Pas de grilles ni de ventelles (sûreté) | VA |
| VN-AL2 | Protection contre la pluie | Point d'attention |
| FT-AL | Fenêtre de toit ouvrante, intérêt pour la ventilation | Point d'attention |
| VV-AL | Tenue structurelle de la véranda ou verrière | AL |
| EX-AL | Surface d'ombrage insuffisante | Point d'attention |
| OA-AL1 | Solution mutualisable locaux / extérieur | Point d'attention |
| OA-AL2 | Prise au vent de la voile (façade, mâts) | AL |
| OA-AL3 | Sécurité incendie de la toile | AL |
| PR-AL1 | Patrimoine : avis de l'ABF | AL |
| PR-AL2 | Charpente du préau : charge supplémentaire | AL |
| PR-AL3 | Amiante (fibrociment avant 1997) | AL |
| PR-AL4 | Préau petit au regard des effectifs | Point d'attention |

Dans le plan d'action du compte rendu, une solution Recommandée ou À optimiser portant une alerte AL
passe dans « À valider avant de consulter ».

**À trancher aussi :** la méthode classe en AL le « réglementaire et patrimonial ». Les règles PV-3,
PH-5, FT-5, VV-6, OA-5 et OC-3 (monument historique, abords) donnent « Sous réserve » mais ne
déclenchent pas d'alerte. Faut-il ajouter une alerte AL patrimoine sur ces solutions ?

### D2. Photos normées obligatoires

Principe de traçabilité (§ I.c) : « photos normées obligatoires sur les questions décisives ». Ni
l'Excel ni l'outil ne prévoient de photos. **À trancher :** quelles questions exigent une photo ?
L'outil pourra les recueillir et les insérer dans le compte rendu une fois la base de données
(Supabase) en place ; la maquette n'en stocke pas.

### D3. CO-1 : « occupé en continu » n'est pas relevé

La règle vise un bureau « occupé en continu », mais aucune question ne relève la durée d'occupation :
tout bureau de moins de 6 m² par occupant est concerné.

### D4. CQ-1 : les réfrigérateurs ne figurent pas dans L-10

La règle cite les réfrigérateurs parmi les équipements à forte dissipation ; L-10 ne propose que
copieurs, baies informatiques, appareils de cuisson, aucun, autre.

### D5. Règle du doute et option « Non évalué »

La méthode demande de cocher « non évaluable » en cas d'hésitation (§ I.f). Ces questions à choix
n'ont pas d'option « Non évalué » : B-03, B-04, B-07, B-18, B-22, B-26, L-02, L-09, MEX-14, MEX-16,
MEX-17, MEX-20, MEX-21, MEX-24, PL-01, BA-05, E-15, E-21, E-24, E-25, E-26, E-27, E-28. Dans l'outil,
laisser la question vide revient au même (donnée inconnue). À ajouter dans la grille de visite ?

## E. Questionnaire usagers

### E1. Matrice de correspondance et indicateur de cohérence (proposition)

Le questionnaire (§ I.a, 4e objectif) prévoit de « vérifier l'adéquation entre préconisations et
ressenti grâce à une matrice de correspondance item / préconisation et à un indicateur de
cohérence », sans les définir. **Proposition, programmée dans l'outil et à valider :**

Principe : la synthèse est faite pour tout l'établissement (décision prise). Un ressenti est jugé
**signalé** quand au moins **30 %** des répondants le déclarent. Il est rapproché des statuts de
l'audit sur l'ensemble des locaux. En dessous de **3 réponses**, rien n'est évalué.

| Croisement | Ressenti des usagers (signalé si ≥ 30 %) | Solutions de l'audit rapprochées |
|---|---|---|
| M1 | Soleil direct souvent ou très souvent, et au moins assez gênant (Q8, Q9) | Protections solaires (verticales, horizontales, films, fenêtres de toit, vérandas) |
| M2 | Air lourd ou stagnant souvent ou très souvent (Q10) | Ventilation nocturne naturelle et mécanique, brasseurs d'air |
| M3 | Chaleur dès l'arrivée le matin ou toute la journée (Q22) | Ventilation nocturne (décharge thermique) |
| M4 | Chaleur l'après-midi ou toute la journée (Q22) | Protections solaires et toiture |
| M5 | Ambiance inconfortable à extrêmement inconfortable (Q5) | Toutes les solutions |
| M6 | Protections utilisées jamais ou rarement (Q12), ou jugées peu efficaces (Q15) | Protections relevées « En place » |
| M7 | Fenêtres ne pouvant pas rester ouvertes la nuit (Q18) | Ventilation naturelle nocturne « Recommandé » |
| M8 | Équipements de rafraîchissement déclarés (Q20) | Relevé des équipements BA-01, BA-02, BA-04, BA-05 |

Résultat de chaque croisement :

- **Cohérent** : ressenti signalé et au moins une solution correspondante préconisée (Recommandé,
  À optimiser ou Sous réserve), ou ni l'un ni l'autre ;
- **À vérifier** : ressenti signalé sans solution correspondante préconisée ; protection relevée
  « En place » mais peu utilisée ou jugée peu efficace (M6) ; ventilation naturelle recommandée alors
  que les fenêtres ne peuvent pas rester ouvertes la nuit (M7) ; équipement déclaré par les usagers
  mais relevé dans aucun local (M8) ;
- **Non corroboré** : solution préconisée sans ressenti signalé. Ce n'est pas une incohérence : la
  solution reste valable (sans regret), mais le ressenti ne la confirme pas ;
- **Non évaluable** : moins de 3 réponses, ou aucun local concerné.

**Indicateur de cohérence** = part des croisements évalués qui ne sont pas « À vérifier ».

Sur l'exemple (14 réponses fictives), 7 croisements sont évalués et 1 est « À vérifier » (M7 :
71 % des usagers indiquent que les fenêtres ne peuvent pas rester ouvertes la nuit, alors que la
ventilation naturelle nocturne est recommandée dans 2 locaux). L'indicateur vaut donc 86 %.

**À trancher :** les croisements retenus, le seuil de 30 %, le minimum de 3 réponses, la définition
de l'indicateur, et le traitement des « Non corroboré ».

### E2. Question ouverte annoncée mais non rédigée

La méthode du questionnaire (§ I.b) annonce « une seule question ouverte facultative pour les
remarques libres », qui ne figure pas dans la liste. **Dans l'outil** : ajoutée en Q24 « Remarques
libres (facultatif) ». À confirmer.

### E3. Contexte : étage et orientation

- Q2 propose « RDC / 1er étage / 2ème étage / etc. ». **Dans l'outil** : RDC, 1er étage, 2e étage,
  3e étage ou plus.
- Q3 ne propose que 4 orientations (Sud, Ouest, Nord, Est), contre 8 dans la grille d'audit. Pas de
  « Je ne sais pas ». Sans incidence tant que la synthèse est globale.

### E4. Questions conditionnelles

« Si vous en avez » (Q12, Q14, Q15) : **dans l'outil**, posées seulement si Q11 cite au moins une
protection (ni « Aucune » ni « Je ne sais pas » seuls). Q13 : seulement si Q12 = Jamais ou
Rarement. Q17 « si vous ouvrez peu ou pas » : interprété comme Q16 = Jamais ou un seul moment
d'ouverture. À confirmer.

### E5. Q20 : une seule réponse possible

Q20 n'admet qu'un équipement, alors qu'un local peut en avoir plusieurs (ventilateur et climatiseur
mobile). Passer en choix multiple ?

### E6. Public visé

La méthode du questionnaire indique « échelle à 7 points (ISO 7730 / ISO 10551) pour les adultes ».
Le questionnaire s'adresse-t-il uniquement aux adultes (enseignants, personnel) ? Une version
élèves est-elle prévue ?

### E7. Collecte en ligne : données personnelles

Pour la version avec base de données (Supabase) : anonymat des répondants, durée de conservation,
hébergement des données (RGPD), limitation du nombre de réponses par lien. Voir `docs/supabase.md`.

## F. Questions de méthode issues de la campagne de tests

Relevées par la campagne de tests n° 1 (`docs/rapport_tests.md`, § 2.4). L'outil se comporte comme
l'Excel sur tous ces points ; ils demandent une décision de méthode.

### F1. Ventilation mécanique : VM-9 et VM-11 ne sont jamais retenues

Avec un débit inconnu, c'est VM-7 (indéterminée, faute de débit) qui donne « Sous réserve », avant
VM-9 (« débit maximal inconnu ») : le statut est juste, mais la règle citée ne l'est pas. VM-11
« Recommandé » n'est atteinte par aucune saisie valide : dès que B-16 est renseignée, VM-6, VM-7 ou
VM-10 s'appliquent. **À trancher** : placer VM-9 avant VM-7 ? Dans quel cas la ventilation mécanique
nocturne doit-elle être « Recommandé » ?

### F2. Règles « aucune baie » présentes dans l'Excel seulement

PV-0, PH-0 et FS-0 (« Non concerné » quand le local n'a aucune baie), ainsi que la condition « et
MEX-14 = Non » de VN-1, n'existent que dans l'Excel. Sans elles, un local aveugle serait
« Recommandé » pour des protections solaires. **À reporter dans le document de méthode.**

### F3. Toiture : B-18 vide avec des combles perdus décrits

Le bloc « combles perdus » s'applique avec un statut certain, alors qu'une toiture-terrasse,
prioritaire (B3), n'est pas exclue. À traiter avec B3.

### F4. Alertes de l'ombrage adossé quand le statut est « Sous réserve » faute de donnée

OA-AL1, OA-AL2 et OA-AL3 (prévues pour un statut « Recommandé ou Sous réserve ») ne se déclenchent
pas quand ce « Sous réserve » vient d'une donnée manquante. Voulu ?

### F5. EX-AL indéterminée

Quand l'effectif ou la surface d'ombrage manque, EX-AL n'est ni déclenchée ni signalée « à vérifier ».
Une alerte indéterminée doit-elle apparaître ?

### F6. VV-AL et les puits de lumière

L'alerte de tenue structurelle (VV-AL) ne vise que les vérandas et verrières, pas les « puits de
lumière, atrium », pourtant concernés par le bloc VV. Étendre l'alerte ?

### F7. Matrice : « Sous réserve » compté comme une préconisation

Un audit vide (tout « Sous réserve » faute de données) est jugé « Cohérent » sur M1 à M5 dès que le
ressenti est signalé, avec un indicateur à 100 % : conclusion trompeuse. Exclure les « Sous réserve »
dus à une donnée manquante du croisement ?

### F8. Matrice : M8 sans seuil de 30 %

M8 conclut « À vérifier » dès qu'un seul usager déclare un équipement non relevé (sur au moins 3
réponses). Appliquer aussi le seuil de 30 % ?

### F9. CP-6 et la période de construction

La colonne « Questions » de CP-6 cite B-01 (période de construction), que ni l'Excel ni l'outil
n'utilisent ; la méthode parle de « suspicion d'amiante ». Déduire la suspicion d'une construction
d'avant 1997, comme PR-AL3 ?

### F10. Équation 1 des brasseurs : bornes incluses ou non ?

L'Excel lit « 0,2 < diamètre / (√surface / nombre) < 0,4 » avec des bornes exclues ; l'image de
l'équation dans la méthode (III.a.i-4) ne permet pas de le confirmer.

## Décisions déjà prises

| Point | Décision |
|---|---|
| BA-18 | Débit en m³/h. |
| Interface | Parcours guidé ; choix au départ entre « Résultats de faisabilité » (équivalent de l'Excel) et « Diagnostic complet » (compte rendu) ; choix du mode de saisie (pas à pas ou fiches à onglets). |
| Contrôle de saisie | Avertir sans bloquer ; étape Vérification avant les documents. |
| Ordre des étapes | Bâtiment (bloc par bloc en pas à pas), Locaux, Espaces extérieurs, puis Façades. |
| Réglages | Seuils et import / export dans un menu « Réglages » discret. |
| Questionnaire usagers | Collecte par questionnaire en ligne, ou import d'un fichier au même format ; synthèse globale pour l'établissement (pas de rattachement aux locaux) ; matrice de correspondance proposée par l'outil (E1). |
| Base de données | Supabase dans une étape ultérieure ; la maquette ne stocke aucune donnée, mais le code est prêt (`surya/stockage.py`, `docs/supabase.md`). |
