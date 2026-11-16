# Points à trancher suite à la lecture de l'Excel

Relevé établi en reprenant toutes les formules de `2611111_outil_aide_test_methode-1.xlsx`
(règles « version du 27/10/2026 ») pour les porter dans l'outil.

Trois catégories :

- **A. Erreurs de l'Excel** : des références cassées. La correction ne fait pas débat, mais elle change
  des résultats ; à valider.
- **B. Points de méthode à trancher** : le libellé d'une règle et sa formule ne disent pas la même
  chose, ou un cas n'est pas prévu.
- **C. Points mineurs** : cohérence des libellés, questions sans effet.

Pour chaque point, la colonne « Dans l'outil » indique ce que fait la maquette aujourd'hui.

## A. Erreurs de l'Excel (corrigées dans l'outil)

| N° | Constat | Où | Dans l'outil |
|---|---|---|---|
| A1 | Les formules des **murs extérieurs 2, 3 et 4** lisent `Saisie_Locaux` une ligne trop bas : pour le mur 2, MEX-04 lit la ligne 61 (la distance MEX-05) au lieu de la ligne 60, et ainsi de suite jusqu'aux types de baie. Un type de baie est en `#REF!`. Seul le mur 1 est donc correctement pris en compte. | `Calc_Locaux`, lignes 26 à 37 et 76 à 90 | Les 4 murs sont lus correctement. |
| A2 | **MEX-17** (type de commande des baies en plafond) est en `#REF!` : la question est passée de cases à cocher à une liste, les formules n'ont pas suivi. La règle FT-7 est cassée dès que MEX-16 = Oui. | `Calc_Locaux` ligne 15, `Règles_Locaux` ligne 109 | FT-7 teste « MEX-17 n'est ni Électrique ni Automatique ». |
| A3 | **BA-18** (débit maximal de ventilation) est utilisée par VM-7, VM-9 et VM-10 mais n'a aucune ligne de saisie (`#REF!`). Dans l'Excel, ces trois règles sont en erreur et ignorées : un local ventilé mécaniquement ressort « Recommandé » sans que le débit soit jamais vérifié. | `Calc_Locaux` ligne 65 | Question ajoutée, en m³/h (unité confirmée). Débit non renseigné : « Sous réserve » (VM-9). |

Conséquence sur l'exemple fourni dans l'Excel : la « Classe CM1 » passe de « Sous réserve » à
« Recommandé » en ventilation naturelle nocturne (A1).

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
équipement même si « Aucun » est coché). **À trancher** : rendre « Aucun » exclusif dans l'outil ?
(Recommandé ; simple à faire.)

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
orientation que le mur du local ou que l'espace. Si cette façade n'est pas cochée en F-01, elles
restent indéterminées. L'outil affiche un avertissement sur le mur concerné. **À trancher** : rendre
la description de la façade obligatoire dès qu'un mur ou un espace la cite ?

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
**Dans l'outil** : toutes affichées, BR-AL toujours.

## C. Points mineurs

| N° | Constat |
|---|---|
| C1 | **B-07** (local de repli plus frais) n'est utilisée par aucune règle et n'est pas marquée `[info]`. |
| C2 | MEX-17 : les réponses annoncées (« Electrique / manuelle / Automatique ») ne sont pas écrites comme celles de la liste déroulante (« Électrique », « Manuelle », « Automatique (sans action humaine) »). |
| C3 | CO-1 : le libellé de condition cite quatre intitulés de L-02 (« Bureaux », « Bureau », « …salle des professeurs… ») ; un seul existe dans la liste. |
| C4 | Deux questions portent le code **MEX-25** (lignes 104 et 105 de `Saisie_Locaux`). L'outil nomme la seconde `MEX-25b` en interne. |
| C5 | La numérotation a des trous (B-02, B-17, L-05 à L-08, MEX-02, MEX-03, MEX-09 à MEX-13, MEX-23, MEX-27, MEX-28, MEX-31, PL-04, BA-07, BA-08, BA-10, BA-16, BA-17, E-03, E-05, E-08, E-13, E-18) : questions du carnet de visite non reprises. À confirmer qu'aucune ne manque. |
| C6 | Limites de l'Excel : 10 locaux, 5 espaces, 4 murs par local. L'outil garde la limite de 4 murs ; à confirmer. |
| C7 | F-05 propose « Non évalué », pas F-02 à F-04. |

## Décisions déjà prises

| Point | Décision |
|---|---|
| BA-18 | Débit en m³/h — confirmé. |
