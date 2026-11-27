# Points à trancher — outil méthode SURYA

Version détaillée du 27/11/2026 (première version du 20/11/2026). Points relevés en portant dans l'outil :

- toutes les formules de l'Excel `2611111_outil_aide_test_methode-1.xlsx` (règles « version du
  27/10/2026 ») ;
- le document de la méthode SURYA « Méthode de l'audit de faisabilité d'actions d'adaptation » (version 01 du
  27/10/2026, © ACTEE et SURYA Ingénierie ; diffusion prévue sous licence Creative Commons BY-SA 4.0, pas encore
  déposée) ;
- le « Questionnaire confort estival » (version 01 du 11/11/2026).

Chaque point a été revérifié sur l'outil et par deux campagnes de tests (`docs/rapport_tests.md`,
`docs/rapport_tests_2.md`).

## Comment lire ce document

### Les huit catégories

| Catégorie | Ce qu'on demande | Qui peut trancher |
|---|---|---|
| **A. Erreurs de l'Excel** | Valider des corrections déjà faites dans l'outil | ACTEE, puis SURYA corrige l'Excel |
| **B. Règles de la méthode SURYA** | Choisir entre le libellé d'une règle et sa formule, ou traiter un cas non prévu | ACTEE avec SURYA |
| **C. Points mineurs** | Valider par écrit (libellés, numérotation) | SURYA |
| **D. Écarts entre l'Excel et le document de méthode** | Aligner les deux documents | ACTEE avec SURYA |
| **E. Questionnaire usagers** | Valider la matrice proposée et le contenu | ACTEE |
| **F. Questions issues des tests** | Comme B, cas trouvés par les tests | ACTEE avec SURYA |
| **G. Compte rendu orienté décision** | Valider des choix propres à l'outil | ACTEE |
| **H. Passage en travaux** | Visa et relecture juridique | ACTEE |

Pour chaque point : **le contexte** (à quoi sert la règle), **le problème**, **un exemple**, **les options**
avec leurs conséquences, **une recommandation**, et ce que fait **l'outil aujourd'hui**.

### Rappels sur le fonctionnement des règles

- **Six statuts** par solution et par lieu : *Recommandé* (absente, sans obstacle), *À optimiser* (présente
  mais défaillante ou mal réglée), *En place* (présente et satisfaisante), *Sous réserve* (possible sous
  réserve de vérification), *Non recommandé ou non adapté*, *Non concerné*.
- **Les règles d'une solution sont lues dans l'ordre : la première qui s'applique donne le statut.** La
  dernière règle d'un bloc (« Aucun cas précédent ») sert de valeur par défaut.
- **Donnée manquante** : si la règle retenue dépend d'une réponse non renseignée, le statut est « Sous
  réserve » et le compte rendu dit quelle question compléter.
- **Codes** : B-xx bâtiment, F-xx façades, L-xx local, MEX-xx murs et baies, PL-xx plafond, BA-xx
  équipements, CO / CQ occupation et équipements, E-xx espaces extérieurs. Une règle porte le code de sa
  solution : VN (ventilation naturelle), VM (ventilation mécanique), BS (brasseurs), PV / PH (protections
  verticales / horizontales), FS (films solaires), FT (fenêtres de toit), VV (vérandas, verrières), TT / CP /
  CA (toiture-terrasse, combles perdus, combles aménagés), OA (ombrage adossé), EX (ombrage de la cour), PR
  (préau).
- **Alertes** : messages ajoutés au statut (exemple : « faire valider l'électricité par un électricien »).
  Leur type, AL (étude de maîtrise d'œuvre) ou VA (validation ponctuelle), est traité en D1.

---

## A. Erreurs de l'Excel (corrigées dans l'outil)

Ces quatre points sont des erreurs de construction de l'Excel, pas des choix de méthode : des cellules qui
pointent au mauvais endroit, ou qui sont cassées (`#REF!`). L'outil les a corrigées. **Valider A, c'est
accepter que l'outil s'écarte de l'Excel actuel sur ces points, et demander à SURYA de réparer l'Excel**
pour que les deux donnent les mêmes résultats.

### A1. Les murs 2, 3 et 4 sont mal lus

**Contexte.** Un local peut avoir jusqu'à quatre murs extérieurs. Pour chacun, on relève l'orientation, la
position des baies (en tunnel, au nu intérieur, au nu extérieur), le retrait du vitrage, le débord
au-dessus, l'état des menuiseries et les types de baies. Ces réponses alimentent les protections solaires
(PV, PH), la ventilation naturelle (VN) et les films solaires (FS).

**Le problème.** Dans l'onglet `Calc_Locaux` (lignes 26 à 37 et 76 à 90), les formules des murs 2, 3 et 4
lisent l'onglet `Saisie_Locaux` **une ligne trop bas**. Pour le mur 2, la question « position des baies »
(MEX-04) lit en réalité la ligne de la distance (MEX-05), la distance lit l'état, et ainsi de suite ; un type
de baie tombe sur `#REF!`. Seul le mur 1 est lu correctement.

**Exemple.** La Classe CM1 de l'exemple de l'Excel a quatre murs au sud, baies en tunnel avec un retrait de
22 cm. L'Excel ne « voit » correctement que le premier mur. Résultat : la ventilation naturelle nocturne et
les protections horizontales ressortent « Sous réserve » dans l'Excel, « Recommandé » dans l'outil.

**Décision demandée.** Valider la lecture correcte des quatre murs (pas d'autre option raisonnable).

**Dans l'outil :** les quatre murs sont lus correctement.

### A2. La commande des fenêtres de toit est cassée (MEX-17)

**Contexte.** La règle FT-7 met « Sous réserve » la protection solaire d'une fenêtre de toit **hors
d'atteinte depuis le sol et sans commande à distance**. La protection garde son intérêt ; ce qui est à
vérifier, c'est son type : un store à manœuvrer à la main serait difficile à utiliser au quotidien, il faut
alors prévoir une commande motorisée ou une protection qui ne se manœuvre pas (store extérieur fixe, film).
MEX-17 relève le type de commande de la fenêtre.

**Le problème.** MEX-17 est passée de cases à cocher à une liste déroulante, mais les formules n'ont pas
suivi : la cellule est en `#REF!` (`Calc_Locaux` ligne 15, `Règles_Locaux` ligne 109). Dès qu'un local a des
fenêtres de toit ouvrantes (MEX-16 = Oui), FT-7 est en erreur et l'Excel passe à la règle suivante.

**Exemple.** La « Salle de classe » de l'exemple a une fenêtre de toit à commande **manuelle**. L'Excel
donne « Recommandé » (FT-7 ignorée) ; l'outil donne « Sous réserve » par FT-7 : la fenêtre est en hauteur et sa
commande est manuelle ; le type de protection est à choisir en conséquence.

**Décision demandée.** Valider que FT-7 teste « MEX-17 n'est ni Électrique ni Automatique ».

**Dans l'outil :** FT-7 appliquée ainsi.

### A3. Le débit de la ventilation mécanique n'a pas de question (BA-18)

**Contexte.** La ventilation mécanique nocturne n'est efficace que si elle renouvelle l'air au moins
**2 fois par heure** (2 vol/h). Les règles VM-7 (« En place » si le débit est suffisant), VM-9 (« Sous
réserve » si le débit maximal est inconnu) et VM-10 (« Sous réserve » si le débit est trop faible) ont besoin
du débit maximal de l'installation : la question BA-18.

**Le problème.** BA-18 n'a aucune ligne de saisie dans l'Excel (`#REF!`, `Calc_Locaux` ligne 65). Les trois
règles sont en erreur et ignorées : un local ventilé mécaniquement peut ressortir « Recommandé » sans que le
débit soit jamais vérifié.

**Exemple.** Une salle de 45 m² sous 2,70 m (121,5 m³) avec une ventilation de 150 m³/h : 1,2 vol/h, trop peu
pour une surventilation nocturne. L'Excel ne peut pas le voir ; l'outil le détecte (VM-10, « Sous réserve »).

**Décision demandée.** Valider l'ajout de la question BA-18 en m³/h (unité déjà confirmée) et le statut
« Sous réserve » quand le débit n'est pas renseigné.

**Dans l'outil :** question ajoutée. Débit non renseigné : « Sous réserve » (la règle citée est VM-7, voir F1).

### A4. Valeurs pile sur un seuil, et valeurs nulles

**Contexte.** Plusieurs règles comparent un rapport à un seuil : 2 vol/h (ventilation mécanique), ratio
0,15 (surface des baies), rapport 0,4 (brasseurs), 0,8 m² d'ombre par enfant (cour).

**Le problème, en deux parties.**

1. **Arithmétique des ordinateurs.** Un calcul comme 243 / 121,5 donne en interne 1,99999… et non 2 : la
   valeur pile sur le seuil passait du mauvais côté. Un tableur arrondit l'affichage ; le programme ne le
   faisait pas.
2. **Division par zéro.** Une surface, une hauteur, un diamètre ou un nombre de brasseurs égal à 0 rendait
   la règle « fausse » (dans l'Excel aussi), et la solution tombait sur la règle par défaut, souvent
   « Recommandé ».

**Exemples.** (1) Salle de 45 m² × 2,70 m avec 243 m³/h : exactement 2 vol/h, doit être « En place » ; l'outil
donnait « Sous réserve » avant correction. (2) Surface saisie « 0 » par erreur : la ventilation mécanique
ressortait « Recommandé ».

**Décision demandée.** Valider (1) l'arrondi des rapports avant comparaison, comme un tableur ; (2) qu'une
valeur nulle soit traitée comme une donnée invalide, donc « Sous réserve » avec un message à l'auditeur.

**Dans l'outil :** les deux corrections sont faites.

### Conséquence sur l'exemple de l'Excel

Quatre statuts de l'exemple fourni avec l'Excel changent, tous à cause de A1 et A2 :

| Local | Solution | Excel actuel | Outil | Cause |
|---|---|---|---|---|
| Classe CM1 (étage) | Ventilation naturelle nocturne | Sous réserve | Recommandé | A1 : murs 2 à 4 enfin lus |
| Classe CM1 (étage) | Protections horizontales | Sous réserve | Recommandé | A1 |
| Salle de motricité | Protections horizontales | Sous réserve | À optimiser | A1 : débord faible lu sur tous les murs |
| Salle de classe | Sur fenêtres de toiture | Recommandé | Sous réserve | A2 : commande manuelle |

Avec ses références réparées, l'Excel recalculé donne exactement les résultats de l'outil (vérifié sur
3 000 locaux et espaces tirés au hasard).

---

## B. Règles de la méthode SURYA à trancher

Dans ces cas, le libellé d'une règle (ce que la méthode veut dire) et sa formule dans l'Excel (ce qui est
calculé) ne disent pas la même chose, ou un cas n'est pas prévu. **Ce sont les décisions qui changent des
statuts.**

### B1. Ventilation traversante : « orientations différentes » n'est pas vérifié (VN-7)

**Contexte.** La ventilation naturelle nocturne consiste à ouvrir les fenêtres la nuit pour évacuer la
chaleur accumulée. Elle marche bien quand l'air **traverse** le local : il entre par une façade et sort par
une autre. Les règles, dans l'ordre :

| Règle | Cas | Statut |
|---|---|---|
| VN-1, VN-2 | aucune baie, ou que des baies fixes | Non recommandé |
| VN-3 à VN-6 | volets pleins, alarme, baies dégradées, oscillo-battants seuls | Sous réserve |
| **VN-7** | baies ouvrantes sur **au moins deux murs d'orientations différentes** | **Recommandé** |
| VN-8 | baie en façade et ouvrant en toiture | Recommandé |
| VN-9 | baie ouvrante et porte vers un local voisin lui-même ouvrant | Recommandé |
| VN-10 | aucun de ces cas : une seule orientation | Sous réserve |

**Le problème.** La formule de VN-7 compte les murs qui ont une baie ouvrante, sans regarder leur
orientation. Deux murs saisis « Sud » suffisent. Or deux fenêtres au sud ne font pas de courant d'air
traversant : selon le libellé, le local devrait tomber en VN-10, « Sous réserve ».

**Exemple.** La grille sert aussi à décrire des baies différentes sur une même façade : une longue façade sud
est souvent saisie en deux ou trois « murs » orientés S. C'est le cas de la Classe CM1 de l'exemple de
l'Excel (quatre murs, tous au sud) : « Recommandé » avec la formule, « Sous réserve » avec le libellé.

**Options.**

1. **Suivre le libellé** : compter les orientations distinctes. Fidèle à l'intention physique ; certains
   statuts baissent (la Classe CM1 passe en « Sous réserve »).
2. **Suivre la formule** et corriger le libellé (« au moins deux murs avec baies ouvrantes ») : on garde les
   résultats actuels, mais on recommande une ventilation traversante impossible.
3. En complément : signaler à la saisie deux murs de même orientation (sans l'interdire, la grille en a
   besoin pour décrire des baies différentes).

**Recommandation :** option 1, avec l'avertissement de l'option 3.

**Dans l'outil :** comme la formule de l'Excel, en attendant la décision (modification d'une ligne).

### B2. Toiture : cas où aucun statut n'est possible

**Contexte.** Pour un local du dernier niveau, le statut « Toiture » vient d'un des trois blocs : toiture-
terrasse ou bac acier (TT), combles perdus (CP), combles aménagés ou rampants (CA). Le bloc est choisi
d'après le type de toiture (B-18) et la présence de combles (B-21).

**Le problème.** Dans trois cas, aucun bloc ne s'applique et le statut reste « Sous réserve » même avec une
saisie complète :

- toiture à pentes **sans combles** (B-18 = Toiture à pentes, B-21 = Non) ;
- type de toiture « Autre » sans combles ;
- combles avec une isolation « Autre » (B-22).

**Exemple.** Une salle de motricité sous une toiture à deux pentes, plafond en sous-face directe de la
charpente (pas de combles). C'est un cas fréquent dans les gymnases et les extensions. L'outil ne sait pas
quoi conclure.

**Options.**

1. Traiter la toiture à pentes sans combles comme des **rampants** (bloc CA) : c'est physiquement proche
   (isolant sous la couverture, épaisseur à vérifier).
2. « Sous réserve » assumé, avec un message « configuration à examiner au cas par cas ».
3. Écrire une règle dédiée.

**Recommandation :** option 1 pour les pentes sans combles ; option 2 pour « Autre ».

**Dans l'outil :** « Sous réserve » avec le message « configuration non prévue par les règles », distinct
d'une donnée manquante.

### B3. Toiture : terrasse et combles à la fois

**Contexte.** Un bâtiment peut avoir une partie en toiture-terrasse et une partie en combles (extension,
préau intégré).

**Le problème.** Si B-18 = Toiture-terrasse et B-21 = Oui (combles), seul le bloc TT est évalué : les combles
sont ignorés. Voir aussi F3 (B-18 non renseigné avec des combles décrits).

**Exemple.** École des années 1970 : bâtiment principal en terrasse, extension avec combles perdus non isolés.
Le statut ne parle que de la terrasse ; l'isolation des combles, souvent la mesure la plus rentable, n'est
pas proposée.

**Options.** (1) Garder la priorité à la terrasse et **signaler les combles** dans la fiche du local ;
(2) évaluer les deux blocs et retenir le statut le plus favorable à l'action ; (3) faire décrire la toiture
**par local** plutôt que pour tout le bâtiment.

**Recommandation :** option 1 tout de suite ; option 3 si les visites montrent des bâtiments mixtes fréquents.

**Dans l'outil :** priorité à la terrasse, comme l'Excel.

### B4. Toiture : seuils d'isolant différents selon le type

**Le problème, en trois parties.**

1. **Statut d'un isolant insuffisant.** En combles perdus, moins de 30 cm d'isolant donne « Recommandé »
   (CP-7). En rampants (CA-2, moins de 20 cm) et en terrasse (TT-3, moins de 30 cm), c'est « Sous réserve ».
2. Les blocs TT et CA n'ont pas de règle par défaut « Aucun cas précédent », contrairement aux autres.
3. En combles aménagés, l'état de l'isolant (B-23), la ventilation (B-25) et les traces d'humidité (B-27)
   sont demandés mais ne servent à aucune règle.

**Exemple.** Deux écoles avec 10 cm d'isolant : celle en combles perdus reçoit « Recommandé » (on peut isoler
dès maintenant), celle en terrasse « Sous réserve » (à vérifier).

**Lecture possible.** La différence peut être voulue : isoler des combles perdus est simple (soufflage d'isolant
sur le plancher), alors qu'isoler une terrasse ou des rampants demande des travaux d'étanchéité ou de
couverture. Si c'est le cas, il faut l'écrire dans le document de méthode.

**Décisions demandées.** (1) Confirmer que la différence est voulue, et pourquoi ; (2) ajouter une règle
par défaut aux blocs TT et CA ; (3) utiliser B-23, B-25 et B-27 en combles aménagés, ou les retirer de la
grille.

**Dans l'outil :** comme l'Excel.

### B5. Fenêtres de toit et verrières partagent les mêmes réponses

**Le problème.** Les questions « ouvrantes » (MEX-16), « protection existante » (MEX-18) et « état » (MEX-19)
sont posées une seule fois pour toutes les baies en plafond. Si un local a à la fois une fenêtre de toit et
une verrière, les blocs FT et VV lisent les mêmes réponses.

**Exemple.** Un hall avec une verrière fixe et deux fenêtres de toit ouvrantes : « ouvrantes = Oui » vaut aussi
pour la verrière.

**Options.** (1) Garder (cas rare) ; (2) dédoubler les trois questions (une série par type de baie en plafond).

**Recommandation :** garder pour l'instant ; dédoubler si les visites le demandent.

**Dans l'outil :** comme l'Excel.

### B6. « Aucun » coché avec une autre réponse

**Le problème.** Dans les questions à choix multiple, rien n'empêche de cocher « Aucun » avec une autre option
(L-10, MEX-18, MEX-29, MEX-36, BA-19, E-10, E-20, B-28). Les règles donnent alors la priorité à l'option
cochée, **sauf pour E-20** (orientations des façades bordant l'espace) : « Aucune » y masque les questions
E-21 à E-25, et l'ombrage adossé tombe sur la règle par défaut OA-11, « Sous réserve ».

**Exemple.** L-10 « Équipements à forte dissipation » : « Aucun » et « Copieurs » cochés ; la règle CQ-1 voit
un copieur et met « Sous réserve ». Pour E-20, « Aucune » et « Sud » cochés : l'ombrage adossé n'est pas
évalué.

**Options.** (1) Rendre « Aucun » exclusif dans la saisie (cocher « Aucun » décoche le reste, et l'inverse) ;
(2) garder et signaler la contradiction à l'étape Vérification.

**Recommandation :** option 1 : simple, et règle aussi le cas E-20 (anomalie ANO-12 des tests).

**Dans l'outil :** comme l'Excel (priorité à l'option cochée).

### B7. Une règle indéterminée masque les suivantes

**Contexte.** Principe général de l'Excel, repris par l'outil : la première règle **non fausse** l'emporte,
même si elle est seulement indéterminée faute de donnée.

**Exemple.** Protections horizontales d'un local avec deux murs sud : débord **inconnu** sur l'un, débord
**faible** sur l'autre. PH-1 (« débord important » → En place) est indéterminée : le statut est « Sous
réserve », alors que PH-2 (« débord faible » → À optimiser) est certaine.

**Options.**

1. **Garder** (prudent) : un statut ne repose jamais sur une hypothèse ; le compte rendu dit quoi compléter.
2. **Retenir la première règle certaine** et signaler la donnée manquante : plus informatif, mais le statut
   peut changer quand la donnée arrive, et cela touche toutes les solutions.

**Recommandation :** garder (option 1), conforme à la règle du doute de la méthode (§ I.f).

**Dans l'outil :** option 1.

### B8. Protections verticales : baies au nu extérieur avec débord

**Contexte.** Les protections verticales (stores extérieurs, brise-soleil orientables) se posent devant les
baies. PV-1 met « Non recommandé » une baie **au nu extérieur sans débord** (rien pour fixer ni abriter le
store) ; PV-2 met « Sous réserve » une baie en tunnel trop peu profonde (moins de 16 cm).

**Le problème.** Une baie au nu extérieur **avec** un débord (faible ou important) n'est visée par aucune
règle et tombe sur la règle par défaut PV-8, « Recommandé », dont le libellé parle pourtant de « tunnel ou nu
intérieur, distance ≥ 16 cm ».

**Exemple.** Façade avec fenêtres au nu extérieur sous un balcon : « Recommandé », alors que le libellé de la
règle retenue décrit une autre situation.

**Options.** (1) C'est voulu (le débord permet de fixer le store) : corriger le libellé de PV-8 ; (2) écrire
une règle dédiée avec son propre statut (par exemple « Sous réserve » : fixation à vérifier).

**Recommandation :** à arbitrer par SURYA, qui connaît la mise en œuvre.

**Dans l'outil :** comme l'Excel.

### B9. Locaux en sous-sol

**Le problème.** « Sous-sol » est traité comme un étage : les règles PV-5, PH-8 (façade sans accès pour une
nacelle) et PH-6 (façade à l'alignement du domaine public) peuvent s'y appliquer, alors qu'elles visent les
baies en hauteur.

**Exemple.** Une salle en rez-de-jardin d'un bâtiment en pente, saisie « sous-sol » : ses protections
ressortent « Sous réserve » faute d'accès pour une nacelle, alors que les baies sont au niveau du sol.

**Recommandation :** assimiler le sous-sol au rez-de-chaussée pour ces trois règles.

**Dans l'outil :** comme l'Excel.

### B10. Façades non décrites

**Contexte.** Plusieurs règles (PV-5 à PV-7, PH-4, PH-6, PH-8 à PH-10, OA-4) lisent la description de la
façade du bâtiment qui a la même orientation que le mur du local (accès d'une nacelle, alignement sur la
rue, obstacles).

**Le problème.** Si cette façade n'est pas décrite, ces règles restent indéterminées (« Sous réserve »).

**Options.** (1) Rendre la description des façades citées **obligatoire** avant les documents ; (2) garder un
avertissement non bloquant.

**Recommandation :** option 2 : l'outil évite déjà l'oubli (voir ci-dessous) et le principe « avertir sans
bloquer » est décidé.

**Dans l'outil :** l'étape Façades vient après les locaux et les espaces ; les façades qu'ils citent sont
cochées d'office ; l'étape Vérification signale celles qui restent incomplètes.

### B11. Alerte « solution mutualisable » (OA-AL1)

**Contexte.** OA-AL1 signale qu'une même structure d'ombrage (voile, pergola) peut protéger à la fois les
baies d'un local du rez-de-chaussée et l'espace extérieur devant.

**Le problème.** L'alerte se déclenche dès qu'**un local du RDC, n'importe lequel**, a un mur de même
orientation qu'une façade bordant l'espace. Rien ne vérifie que ce local donne sur cet espace.

**Exemple.** Cour au sud du bâtiment A ; une classe du bâtiment B, à l'autre bout du site, a aussi un mur sud :
l'alerte se déclenche quand même.

**Options.** (1) Suffisant (l'auditeur juge sur place) ; (2) rattacher les locaux aux espaces qu'ils bordent
(une question de plus par local).

**Recommandation :** option 1 pour l'instant ; option 2 si la saisie est enrichie plus tard.

### B12. Occupation : quels locaux et quel effectif

**Le problème, en deux parties.**

1. CO-1 (« bureau occupé en continu, moins de 6 m² par occupant ») et CO-2 (« classe, moins de 1,5 m² par
   élève ») ne visent que les bureaux et les classes. Tout autre local (dortoir, restauration, salle
   polyvalente) ressort toujours « En place » pour l'occupation.
2. L'alerte EX-AL (ombre de la cour en élémentaire) divise la surface d'ombre par E-06, l'effectif **total**
   présent, adultes compris, alors que le seuil est exprimé « par enfant ».

**Exemple.** Un dortoir de 30 m² accueillant 25 enfants (1,2 m² par enfant) : « En place ». Une cour de
150 élèves et 8 adultes : la surface est divisée par 158 au lieu de 150.

**Options.** (1) Étendre CO aux autres locaux occupés, avec un seuil par type ; (2) relever l'effectif d'enfants
à part pour EX-AL ; (3) garder.

**Recommandation :** (1) au moins pour les dortoirs et la restauration ; (2) sans urgence (écart faible).

### B13. Quelles alertes afficher, et quand

**Le problème.** L'Excel calcule 14 alertes mais ne les affiche que dans les onglets de règles, pas dans
l'onglet `Résultats`. BR-AL (« faire valider l'électricité et la tenue de la structure ») est « toujours
vraie », même quand les brasseurs sont non recommandés.

**Exemple.** Local à 2,30 m sous plafond : brasseurs « Non recommandé », et pourtant l'alerte « faire valider
l'installation électrique des brasseurs » apparaît.

**Recommandation :** afficher toutes les alertes dans la restitution, typées (D1) ; n'afficher BR-AL que si
les brasseurs sont envisagés (Recommandé, À optimiser ou Sous réserve).

**Dans l'outil :** toutes les alertes affichées et typées ; BR-AL affichée dans tous les cas.

---

## C. Points mineurs

À valider par écrit, sans débat en réunion. Proposition : envoyer ce tableau à SURYA après la réunion.

| N° | Constat | Proposition |
|---|---|---|
| C1 | **B-07** (local de repli plus frais) n'alimente aucune règle et n'est pas marquée « info ». | La marquer « info » (utile au compte rendu), ou l'utiliser dans une règle d'occupation. |
| C2 | MEX-17 : les réponses annoncées (« Electrique / manuelle / Automatique ») ne sont pas écrites comme dans la liste (« Électrique », « Manuelle », « Automatique (sans action humaine) »). | Aligner le libellé sur la liste. |
| C3 | CO-1 cite quatre intitulés de L-02 (« Bureaux », « Bureau », « …salle des professeurs… ») ; un seul existe dans la liste. | Citer l'intitulé exact. |
| C4 | Deux questions portent le code **MEX-25** (lignes 104 et 105 de `Saisie_Locaux`). | Renuméroter (l'outil nomme la seconde MEX-25b). |
| C5 | Trous de numérotation (B-02, B-17, L-05 à L-08, MEX-02, MEX-03, MEX-09, MEX-11 à MEX-13, MEX-23, MEX-27, MEX-28, MEX-31, PL-04, BA-07, BA-08, BA-10, BA-16, BA-17, E-03, E-05, E-08, E-13, E-18). | Confirmer qu'aucune question du carnet de visite ne manque. |
| C6 | L'Excel limite à 10 locaux, 5 espaces et 4 murs par local ; l'outil n'a pas de limite de locaux ni d'espaces mais garde 4 murs. | Confirmer 4 murs au maximum. |
| C7 | « Non évalué » proposé sur F-05 seulement. | L'étendre à F-02, F-03 et F-04. |

---

## D. Écarts entre l'Excel et le document de la méthode SURYA

Relevés en comparant l'Excel au document de méthode (version 01 du 27/10/2026, copie dans `reference/`).
Les règles sont pour l'essentiel identiques dans les deux documents (exception : F2) ; les écarts portent
sur le cadre de l'audit.

### D1. Type des alertes : maîtrise d'œuvre (AL) ou validation ponctuelle (VA)

**Contexte.** La méthode (§ I.e) distingue l'**alerte maîtrise d'œuvre (AL)**, qui exige une étude avant de
consulter des entreprises, et le **point de validation ponctuelle (VA)**, qu'un professionnel peut lever
(électricien, couvreur). La différence est concrète pour la collectivité : une AL veut dire un marché d'études
avant les travaux, donc du temps et un coût en plus.

**Le problème.** L'Excel ne type pas ses alertes. L'outil propose un classement, d'après le tableau du § I.e :

| Alerte | Objet | Type proposé |
|---|---|---|
| BR-AL | Électricien et capacité de la structure à porter les brasseurs | VA |
| VN-AL1 | Pas de grilles ni de ventelles pour ouvrir la nuit en sécurité | VA |
| VN-AL2 | Protection contre la pluie | Point d'attention |
| FT-AL | Fenêtre de toit ouvrante : intérêt pour la ventilation | Point d'attention |
| VV-AL | Tenue structurelle de la véranda ou de la verrière | AL |
| EX-AL | Surface d'ombre insuffisante dans la cour | Point d'attention |
| OA-AL1 | Solution mutualisable locaux / extérieur | Point d'attention |
| OA-AL2 | Prise au vent de la voile (façade, mâts) | AL |
| OA-AL3 | Sécurité incendie de la toile | AL |
| PR-AL1 | Patrimoine : avis de l'architecte des bâtiments de France | AL |
| PR-AL2 | Charpente du préau : charge supplémentaire | AL |
| PR-AL3 | Amiante (fibrociment posé avant 1997) | AL |
| PR-AL4 | Préau petit au regard des effectifs | Point d'attention |

**Effet dans le compte rendu.** Une solution « Recommandé » ou « À optimiser » qui porte une alerte AL passe
dans « À valider avant de consulter » au lieu de « À engager ».

**Exemple.** Ombrage adossé « Recommandé » dans la cour de l'école type du Sud, avec OA-AL2 et OA-AL3 : il
figure dans « À valider avant de consulter » (étude de la voile et de sa fixation).

**Décisions demandées.** (1) Valider ce classement ; (2) la méthode range en AL le « réglementaire et
patrimonial ». Les règles PV-3, PH-5, FT-5, VV-6, OA-5 et OC-3 (monument historique, abords) donnent « Sous
réserve » mais ne déclenchent pas d'alerte. Faut-il leur ajouter une alerte AL « patrimoine » ?

**Recommandation :** valider le classement et ajouter l'alerte patrimoine.

### D2. Photos « normées obligatoires »

**Contexte.** Principe de traçabilité (§ I.c) : « photos normées obligatoires sur les questions décisives ».
L'Excel n'en prévoit pas.

**Dans l'outil :** photos prises ou chargées pour le bâtiment, chaque local et chaque espace, visages floutés
automatiquement, insérées dans le compte rendu ; une liste de photos attendues est affichée, sans bloquer :
façade (bâtiment) ; vue d'ensemble, baies et protections, plafond (local) ; vue d'ensemble, ombrages existants
(espace).

**Décision demandée.** Quelles questions exigent une photo, et la liste proposée convient-elle ? Faut-il la
rendre bloquante avant les documents ?

**Recommandation :** valider la liste ; rester non bloquant pour la phase de test.

### D3. Occupation : « occupé en continu » n'est pas relevé (CO-1)

**Le problème.** CO-1 vise un bureau « occupé en continu », mais aucune question ne relève la durée
d'occupation : tout bureau de moins de 6 m² par occupant est concerné, même occupé une heure par jour.

**Options.** (1) Ajouter la question « occupé en continu (Oui / Non) » ; (2) retirer « en continu » du libellé.

**Recommandation :** option 2 (plus simple ; la surface par occupant suffit à repérer un bureau surchargé).

### D4. Équipements : les réfrigérateurs ne sont pas dans L-10 (CQ-1)

**Le problème.** CQ-1 cite les réfrigérateurs parmi les équipements à forte dissipation ; L-10 ne propose que
copieurs, baies informatiques, appareils de cuisson, aucun, autre.

**Recommandation :** ajouter « Réfrigérateurs » à L-10 (fréquents en salle des maîtres et en office).

### D5. Règle du doute et option « Non évalué »

**Contexte.** La méthode (§ I.f) demande de cocher « non évaluable » en cas d'hésitation, pour que le doute
mène à « Sous réserve » plutôt qu'à une conclusion hasardeuse.

**Le problème.** Ces 23 questions à choix n'ont pas d'option « Non évalué » : B-03, B-04, B-07, B-18, B-22,
B-26, L-02, L-09, MEX-14, MEX-16, MEX-17, MEX-20, MEX-21, MEX-24, PL-01, BA-05, E-15, E-21, E-24, E-25, E-26,
E-27, E-28. L'auditeur qui hésite doit choisir une réponse ou laisser vide.

**Options.** (1) Ajouter « Non évalué » à ces questions de la grille ; (2) considérer qu'une question laissée
vide vaut « Non évalué » (c'est déjà l'effet dans l'outil) et l'écrire dans la méthode.

**Recommandation :** option 1 pour la grille papier ; l'outil fonctionne déjà comme l'option 2.

---

## E. Questionnaire usagers

### E1. Matrice de correspondance et indicateur de cohérence (proposition)

**Contexte.** Le questionnaire (§ I.a, 4e objectif) doit permettre de « vérifier l'adéquation entre
préconisations et ressenti grâce à une matrice de correspondance item / préconisation et à un indicateur de
cohérence », sans les définir. L'outil propose les définitions suivantes.

**Principe.** La synthèse est faite pour tout l'établissement (décision prise). Un ressenti est **signalé**
quand au moins **30 %** des répondants le déclarent. En dessous de **3 réponses**, rien n'est évalué. Chaque
ressenti signalé est rapproché des statuts de l'audit sur l'ensemble des locaux.

| Croisement | Ressenti des usagers (signalé si ≥ 30 %) | Solutions de l'audit rapprochées |
|---|---|---|
| M1 | Soleil direct souvent ou très souvent, et au moins assez gênant (Q8, Q9) | Protections solaires (verticales, horizontales, films, fenêtres de toit, vérandas) |
| M2 | Air lourd ou stagnant souvent ou très souvent (Q10) | Ventilation nocturne naturelle et mécanique, brasseurs d'air |
| M3 | Chaleur dès l'arrivée le matin ou toute la journée (Q22) | Ventilation nocturne (décharge de la chaleur stockée) |
| M4 | Chaleur l'après-midi ou toute la journée (Q22) | Protections solaires et toiture |
| M5 | Ambiance inconfortable à extrêmement inconfortable (Q5) | Toutes les solutions |
| M6 | Protections utilisées jamais ou rarement (Q12), ou jugées peu efficaces (Q15) | Protections relevées « En place » |
| M7 | Fenêtres ne pouvant pas rester ouvertes la nuit (Q18) | Ventilation naturelle nocturne « Recommandé » |
| M8 | Équipements de rafraîchissement déclarés (Q20) | Équipements relevés (BA-01, BA-02, BA-04, BA-05) |

**Résultat de chaque croisement :**

- **Cohérent** : ressenti signalé et au moins une solution correspondante préconisée, ou ni l'un ni l'autre ;
- **À vérifier** : ressenti signalé sans solution correspondante ; protection « En place » mais peu utilisée
  ou jugée peu efficace (M6) ; ventilation naturelle recommandée alors que les fenêtres ne peuvent pas rester
  ouvertes la nuit (M7) ; équipement déclaré par les usagers mais relevé nulle part (M8) ;
- **Non corroboré** : solution préconisée sans ressenti signalé. Ce n'est pas une incohérence : la solution
  reste valable, mais le ressenti ne la confirme pas ;
- **Non évaluable** : moins de 3 réponses, ou aucun local concerné.

**Indicateur de cohérence** = part des croisements évalués qui ne sont pas « À vérifier ».

**Exemple.** École type du Sud, 14 réponses fictives : 7 croisements évalués, 1 « À vérifier » (M7 : 71 % des
usagers disent que les fenêtres ne peuvent pas rester ouvertes la nuit, alors que la ventilation naturelle
nocturne est recommandée dans 2 locaux). Indicateur : 6 / 7 = 86 %. Le compte rendu en tire une piste : avant
de compter sur la ventilation nocturne, régler ce qui empêche d'ouvrir (sûreté, alarme, bruit).

**Décisions demandées.** Valider les 8 croisements, le seuil de 30 %, le minimum de 3 réponses, la définition
de l'indicateur et le sens de « Non corroboré ». Voir aussi F7 et F8.

### E2. Question ouverte annoncée mais absente

La méthode (§ I.b) annonce « une seule question ouverte facultative pour les remarques libres », absente de
la liste. **Dans l'outil :** ajoutée en Q24 « Remarques libres (facultatif) ». **À confirmer.**

### E3. Étage et orientation moins détaillés que la grille

Q2 propose « RDC / 1er étage / 2ème étage / etc. » ; l'outil propose RDC, 1er, 2e, 3e étage ou plus. Q3 ne
propose que 4 orientations (contre 8 dans la grille d'audit) et pas de « Je ne sais pas ». **Sans incidence
tant que la synthèse est faite pour tout l'établissement** ; à revoir si l'on rattache un jour les réponses
aux locaux. **Recommandation :** garder, ajouter « Je ne sais pas » à Q3.

### E4. Questions conditionnelles

« Si vous en avez » (Q12, Q14, Q15) : posées seulement si Q11 cite au moins une protection. Q13 : seulement si
Q12 = Jamais ou Rarement. Q17 « si vous ouvrez peu ou pas » : interprété comme Q16 = Jamais ou un seul moment
d'ouverture. Cela raccourcit le questionnaire pour ceux qui n'ont pas de protection. **À confirmer.**

### E5. Q20 : une seule réponse possible

Q20 n'admet qu'un équipement de rafraîchissement, alors qu'un local peut avoir un ventilateur et un
climatiseur mobile. **Recommandation :** passer en choix multiple (le croisement M8 en tire alors une
information plus juste).

### E6. Public visé

La méthode indique « échelle à 7 points (ISO 7730 / ISO 10551) pour les adultes ». Le questionnaire
s'adresse-t-il seulement aux adultes (enseignants, personnel) ? Une version élèves est-elle prévue ?
**Recommandation :** adultes pour la phase de test ; version élèves à instruire (vocabulaire, échelle à
5 points, autorisation des familles).

### E7. Collecte en ligne : données personnelles

La collecte en ligne fonctionne : réponses anonymes, questionnaire ouvert 90 jours, réponses brutes conservées
12 mois (décision du 26/11/2026). **Reste à décider avant un usage réel :** registre de traitement et mention
d'information (RGPD), limitation du nombre de réponses par lien (aujourd'hui : 60 par 10 minutes et 2 000 par
audit). Voir `docs/supabase.md`.

---

## F. Questions sur la méthode SURYA issues des campagnes de tests

L'outil se comporte comme l'Excel sur ces points (sauf F11) ; ils demandent une décision sur la méthode.

### F1. Ventilation mécanique : deux règles jamais retenues (VM-9, VM-11)

**Le problème.** (1) Débit inconnu : c'est VM-7 (« En place si débit ≥ 2 vol/h », indéterminée) qui donne
« Sous réserve », avant VM-9 (« débit maximal inconnu »). Le statut est juste, mais la règle citée dans le
compte rendu ne l'est pas. (2) VM-11 « Recommandé » (« aucun cas précédent ») n'est atteinte par aucune saisie
valide : dès que l'installation est décrite, VM-6, VM-7 ou VM-10 s'appliquent avant.

**Exemple.** Ventilation double flux avec by-pass, débit non relevé : le compte rendu dit « VM-7 indéterminée »
au lieu de « débit maximal inconnu, à relever ».

**Décisions demandées.** (1) Placer VM-9 avant VM-7 (recommandé : la règle citée devient la bonne) ; (2) dans
quel cas la ventilation mécanique nocturne doit-elle être « Recommandé » ? (par exemple : installation
existante, programmable, mais mode nocturne jamais mis en place ?)

### F2. Règles « aucune baie » présentes dans l'Excel seulement

PV-0, PH-0 et FS-0 (« Non concerné » quand le local n'a aucune baie), ainsi que la condition « et MEX-14 = Non »
de VN-1, n'existent que dans l'Excel. Sans elles, un local aveugle (réserve, sanitaire) serait « Recommandé »
pour des protections solaires. **À reporter dans le document de la méthode.**

### F3. Toiture : type non renseigné et combles décrits

Si B-18 (type de toiture) n'est pas renseigné mais que des combles perdus sont décrits, le bloc « combles
perdus » s'applique avec un statut certain, alors qu'une toiture-terrasse, prioritaire (B3), n'est pas exclue.
**À traiter avec B3** (proposition : « Sous réserve » tant que B-18 n'est pas renseigné).

### F4. Alertes de l'ombrage adossé quand le statut vient d'une donnée manquante

OA-AL1, OA-AL2 et OA-AL3 sont prévues pour un ombrage adossé « Recommandé ou Sous réserve ». Elles ne se
déclenchent pas quand ce « Sous réserve » vient d'une donnée manquante. **Exemple :** façade non décrite, la
voile n'est ni écartée ni confirmée, et rien ne signale la prise au vent ni le risque incendie.
**Recommandation :** les déclencher aussi, par prudence.

### F5. Alerte d'ombre de la cour indéterminée (EX-AL)

Quand l'effectif ou la surface d'ombre manque, EX-AL n'est ni déclenchée ni signalée « à vérifier ».
**Recommandation :** la signaler « à vérifier », comme les autres données manquantes.

### F6. Tenue structurelle et puits de lumière (VV-AL)

L'alerte de tenue structurelle (VV-AL) ne vise que les vérandas et verrières, pas les « puits de lumière,
atrium », pourtant traités par le même bloc VV. **Recommandation :** étendre l'alerte.

### F7. Matrice usagers : « Sous réserve » compté comme une préconisation

Un audit presque vide (tout « Sous réserve » faute de données) est jugé « Cohérent » sur M1 à M5 dès que le
ressenti est signalé, avec un indicateur à 100 % : conclusion trompeuse. **Recommandation :** exclure du
croisement les « Sous réserve » dus à une donnée manquante.

### F8. Matrice usagers : M8 sans seuil de 30 %

M8 conclut « À vérifier » dès qu'un seul usager déclare un équipement non relevé (sur au moins 3 réponses).
**Exemple :** 1 ventilateur personnel déclaré sur 20 réponses suffit. **Recommandation :** appliquer aussi le
seuil de 30 %.

### F9. Combles perdus : la période de construction n'est pas utilisée (CP-6)

La colonne « Questions » de CP-6 cite B-01 (période de construction), que ni l'Excel ni l'outil n'utilisent ;
la méthode parle de « suspicion d'amiante ». **Recommandation :** déduire la suspicion d'une construction
d'avant 1997, comme PR-AL3 (voir F11).

### F10. Brasseurs : bornes de l'équation incluses ou non ?

L'Excel lit « 0,2 < diamètre / (√surface / nombre) < 0,4 » avec des bornes exclues ; l'image de l'équation dans
la méthode (III.a.i-4) ne permet pas de le confirmer. **Exemple :** 2 brasseurs de 1,20 m dans 36 m² donnent
exactement 0,4 (1,20 / (6 / 2)) : conforme ou pas ? **À confirmer par SURYA.**

### F11. Repérage amiante quand la période de construction est inconnue (campagne n° 2)

Quand B-01 n'est pas renseignée, le passage en travaux ne proposait pas le repérage amiante avant travaux
(CCTP 10), alors que l'alerte PR-AL3 traite ce même cas comme une suspicion d'amiante. Le repérage est
obligatoire avant travaux pour un permis antérieur au 1ᵉʳ juillet 1997.
**Dans l'outil (depuis le 27/11/2026) :** par prudence (règle du doute), le repérage est proposé dès que la
période n'est pas « Après 1997 ». **À confirmer.**

---

## G. Compte rendu orienté décision (propositions de l'outil)

Le compte rendu complet commence par cinq parties courtes pensées pour la décision : synthèse en une page,
bâtiment et plan simplifié, ressenti des usagers, pistes d'action dans l'ordre de mise en œuvre, ce qu'il
reste à lever avant de consulter. Le détail (statuts, plan d'action par local, fiches, seuils) passe en
annexes. Les choix ci-dessous sont des propositions de l'outil, absentes de la méthode.

### G1. Ordre de mise en œuvre en trois étapes

**Contexte.** La méthode classe des solutions par lieu ; elle ne dit pas par quoi commencer. Les élus
demandent un ordre.

| Étape | Contenu | Solutions |
|---|---|---|
| 1. Dès maintenant | Usages, réglages et remise en état : par l'exploitant ou en régie, coût nul ou faible, effet dès l'été qui vient | Occupation, équipements (extinction, déplacement) ; ventilation naturelle nocturne sans grilles à poser (consignes d'ouverture) ; ventilation mécanique nocturne (programmation) ; tout équipement « À optimiser » déjà présent : brasseurs, protections solaires, protections des fenêtres de toit et vérandas (réparer, régler, remettre en service) |
| 2. Petits travaux | Équipements légers sans intervention sur la structure : consultation simple, pendant les vacances d'été | Brasseurs d'air (pose), films solaires, éclairage LED, protections des fenêtres de toit, ventilation naturelle avec grilles ou ventelles à poser, ombrage autoportant ou végétal de la cour |
| 3. Travaux sur le bâtiment | Enveloppe, toiture, structures : à programmer, souvent avec une maîtrise d'œuvre | Protections verticales et horizontales (pose), vérandas et verrières, toiture, ombrage adossé, adaptation du préau |

Une solution « à valider » garde l'étape qu'elle aurait une fois validée. Dans chaque étape, les solutions sont
classées par nombre de personnes concernées. Voir aussi G4 : l'étape est bornée par le niveau d'accompagnement.

**Exemple.** École type du Sud : étape 1, occupation et équipements (réorganiser, éteindre) ; étape 2, films
solaires dans 6 locaux, brasseurs d'air, ventilation nocturne avec grilles à poser, éclairage LED, ombrage de
la cour ; étape 3, protections extérieures, toiture-terrasse, ombrage adossé et préau.

**Décisions demandées.** (1) Le classement de chaque solution, notamment les plantations (étape 2, mais effet
sur plusieurs années : à lancer tôt ?) et les stores extérieurs (étape 3, ou étape 2 s'ils se posent sans
maîtrise d'œuvre ?) ; (2) le critère de classement dans une étape : effectif seul, ou aussi la sensibilité du
public (maternelle, dortoir), l'exposition (dernier niveau, plein sud) et le ressenti des usagers ; (3) l'ajout
d'ordres de grandeur de coût et d'efficacité, qui permettraient une vraie priorisation.

### G2. Solutions principales de la synthèse

La page 1 retient les 7 couples « solution × étape » qui concernent le plus de personnes, rangés par étape,
puis 3 solutions à valider, en citant pour chacune les 3 lieux les plus fréquentés. **À valider** (on peut
aussi choisir 5 ou 10).

### G3. Plan simplifié

Schéma de principe, sans géométrie réelle : une ligne par niveau, une boîte par local de largeur
proportionnelle à la surface, couleur selon le nombre de solutions à engager, trait orange sur les côtés qui
ont des baies (N en haut, S en bas, E à droite, O à gauche), disque orange en cas d'alerte maîtrise d'œuvre ;
les espaces extérieurs forment la dernière ligne. Un plan réel demanderait la position des locaux ou l'import
d'un plan de l'établissement. **À valider** ; visible page 3 du compte rendu de l'école type du Sud.

### G4. Même étape dans le compte rendu et dans le pré-programme (campagne n° 2)

**Le problème.** Une même action était placée à l'étape 1 « Dès maintenant » dans le compte rendu et à
l'horizon 2 ou 3 dans le pré-programme du passage en travaux (60 saisies aléatoires sur 150). Les deux
documents vont aux mêmes élus.

**Exemple.** Brasseurs présents mais hors service sous un faux plafond : « remise en état », étape 1, dans le
compte rendu ; mais le faux plafond oblige à vérifier l'ancrage (niveau B, consultation d'un professionnel)
dans le pré-programme.

**Options.** (1) Borner l'étape du compte rendu par le niveau d'accompagnement : consultation (B) → étape 2 au
moins, maîtrise d'œuvre (C) → étape 3 ; (2) garder l'étape 1 dans le compte rendu et expliquer le décalage
dans le pré-programme.

**Recommandation :** option 1 (une seule étape pour une même action).

**Dans l'outil (depuis le 27/11/2026, proposition) :** option 1.

### G5. Chiffres de la synthèse (campagne n° 2)

**Le problème.** Sur l'école type du Sud, la synthèse annonçait « 7 solutions à engager » et « 8 solutions à
valider », mais trois solutions sont dans les deux (à engager dans un local, à valider dans un autre). Un
lecteur peut additionner 15, alors que 12 solutions existent.

**Options.** (1) Préciser « dans au moins un lieu » ; (2) compter des couples « solution × lieu » (plus
grands nombres, mais additionnables).

**Dans l'outil (depuis le 27/11/2026, proposition) :** option 1.

---

## H. Passage en travaux (campagne n° 2)

### H1. Visa du pré-programme

**Le problème.** Le pré-programme passe au statut « validé » dès que quatre champs texte sont remplis
(auditeur, date de revue, visa, date du visa). Rien n'empêche l'auditeur de viser son propre travail, ni de
saisir une date mal formée.

**Décision demandée.** Qui vise (un chargé de mission ACTEE, un référent de la collectivité ?) ; avec les
comptes de l'outil, le visa pourrait être rattaché au compte de la personne qui vise.

**Dans l'outil :** inchangé pour la maquette.

### H2. Rappel réglementaire des seuils de procédure

Le pré-programme et le plan d'action rappellent que les travaux de moins de 100 000 € HT et les études ou la
maîtrise d'œuvre de moins de 60 000 € HT sont dispensés de procédure de publicité et de mise en concurrence
(décret n° 2025-1386). Ce rappel n'a pas été vérifié par les tests. **À faire :** relecture par un juriste
avant toute diffusion.

---

## Décisions déjà prises

| Point | Décision |
|---|---|
| BA-18 | Débit en m³/h. |
| Interface | Parcours guidé ; choix au départ entre « Résultats de faisabilité » (équivalent de l'Excel) et « Diagnostic complet » (compte rendu) ; choix du mode de saisie (pas à pas ou fiches à onglets). |
| Contrôle de saisie | Avertir sans bloquer ; étape Vérification avant les documents. |
| Ordre des étapes | Bâtiment (bloc par bloc en pas à pas), Locaux, Espaces extérieurs, puis Façades. |
| Réglages | Seuils et import / export dans un menu « Réglages » discret. |
| Questionnaire usagers | Collecte par questionnaire en ligne, ou import d'un fichier au même format ; synthèse globale pour l'établissement (pas de rattachement aux locaux) ; matrice de correspondance proposée par l'outil (E1). |
| Compte rendu complet | Orienté décision : synthèse en une page, présentation du bâtiment, rapprochement usagers / visite, détail en annexe. |
| Base de données | Supabase, offre gratuite pour la phase de maquette et de test ; sans compte, rien n'est enregistré (`docs/supabase.md`, `docs/base_de_donnees.md`). |
| Comptes | Inscriptions ouvertes à tous (26/11/2026). |
| Conservation (26/11/2026) | Audits et photos : 3 ans après la dernière modification (ouvrir un audit le conserve 3 ans de plus, rappel un mois avant). Questionnaire ouvert 90 jours ; réponses brutes conservées 12 mois. Comptes inactifs : supprimés après 3 ans sans connexion. Purge hebdomadaire des seules données dont le délai est dépassé. |
| Passage en travaux | Troisième parcours, proposé depuis les documents du diagnostic (pré-programme, CCTP, ingénierie) ; il accepte aussi un diagnostic externe. |
| Lecture par IA d'un diagnostic externe | Annoncée pour février 2027 ; saisie manuelle en attendant. |
| Nom et licence | « Méthode SURYA » partout ; diffusion prévue sous licence Creative Commons BY-SA 4.0 (pas encore déposée : le bandeau est prêt), logo SURYA sur l'écran de départ de l'outil et la couverture des présentations. |
