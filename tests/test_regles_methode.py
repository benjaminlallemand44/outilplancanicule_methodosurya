"""Partie B — exactitude du moteur au regard du document de méthode.

Un cas écrit à la main par règle : à partir des profils « sans contrainte » de ``cas_base``, on ne
modifie que les réponses qui doivent déclencher la règle. On vérifie la règle retenue
(``blocs[...]["regle"]``), le statut de la solution et l'absence de marqueur « donnée manquante ».

Références : méthode = « Méthode de l'audit de faisabilité d'actions d'adaptation », v01 du
27/10/2026 (§ III.a à III.d, règles numérotées dans l'ordre de lecture). Les anomalies sont
référencées ANO-xx (voir docs/rapport_tests.md).
"""
from __future__ import annotations

import pytest

from cas_base import (BRASSEURS_EN_PLACE, DERNIER, FENETRE_DE_TOIT, SUPPR, VERANDA, donnees, evaluer, fusion, moteur,
                      mur, solution, statuts, LOCAL, ESPACE)

R, AO, EP, SR, NR, NC = (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE, moteur.SOUS_RESERVE,
                         moteur.NON_RECOMMANDE, moteur.NON_CONCERNE)
BP = BRASSEURS_EN_PLACE
FT = FENETRE_DE_TOIT
VV = VERANDA
TERRASSE = {"B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": 30}
RAMPANTS = {"B-22": "Sous pente", "B-24": 20}
ISOLE_LOCAL = {"MEX-26": SUPPR}  # PV-4 / PH-7 : à défaut de MEX-26, B-03 et B-04
PREAU_FONCE_TRANSLUCIDE = {"E-26": "Polycarbonate ou verrière", "E-27": "Oui", "E-28": "Foncée"}


def c(ident, bloc, regle, statut, bat=None, fac=None, local=None, espace=None, param=None, ref=""):
    return pytest.param(bloc, regle, statut, bat, fac, local, espace, param, id=ident, marks=())


# (identifiant, bloc, règle attendue, statut attendu, patchs…). Référence méthode dans l'identifiant.
CAS = [
    # --- III.a.i Brasseurs en place (BP) -----------------------------------------------------------
    c("BP-1 hors service", "BP", "BP-1", AO, local=dict(BP, **{"BA-05": "Présent, hors service"})),
    c("BP-2 commande", "BP", "BP-2", AO, local=dict(BP, **{"BA-11": "Non"})),
    c("BP-3 pales trop proches", "BP", "BP-3", AO, local=dict(BP, **{"BA-12": 275})),  # 25/200 = 0,125
    c("BP-4 équation 1", "BP", "BP-4", AO, local=dict(BP, **{"BA-09": 100, "BA-13": 250})),  # 1/√60 = 0,13
    c("BP-4 assertion 1 (mur)", "BP", "BP-4", AO, local=dict(BP, **{"BA-13": 150})),
    c("BP-4 assertion 2 (entraxe)", "BP", "BP-4", AO,
      local=dict(BP, **{"BA-06": 2, "L-03": 240, "BA-14": 400})),  # 400 ≤ 2,5 × 200
    c("BP-5 défaut", "BP", "BP-5", EP, local=BP),
    c("BP-5 deux brasseurs bien placés", "BP", "BP-5", EP, local=dict(BP, **{"BA-06": 2, "L-03": 240, "BA-14": 600})),
    # --- III.a.ii Brasseurs à créer (BS) -----------------------------------------------------------
    c("BS-1 HSP < 2,40", "BS", "BS-1", NR, local={"PL-03": 2.3}),
    c("BS-2 baffles", "BS", "BS-2", SR, local={"BA-19": ["Baffles acoustiques"]}),
    c("BS-2 gaines", "BS", "BS-2", SR, local={"BA-19": ["Gaines de ventilation"]}),
    c("BS-2 décoration", "BS", "BS-2", SR, local={"BA-19": ["Décoration"]}),
    c("BS-2 éclairage suspendu", "BS", "BS-2", SR, local={"ECL-02": ["Suspendu"]}),
    c("BS-3 HSP 2,50", "BS", "BS-3", SR, local={"PL-03": 2.5}),
    c("BS-4 plénum 0,80 béton", "BS", "BS-4", SR,
      local={"PL-01": "Faux plafond démontable (dalles sur ossature)", "PL-02": 0.8}),
    c("BS-5 faux plafond sur bois", "BS", "BS-5", SR,
      local={"PL-01": "Faux plafond fixe (plaques de plâtre, enduit)", "PL-02": 0.3, "PL-05": "Plafond bois horizontal"}),
    c("BS-6 plafond bois", "BS", "BS-6", SR, local={"PL-01": "Plafond bois, lambris, rampants ou charpente apparente"}),
    c("BS-6 autre", "BS", "BS-6", SR, local={"PL-01": "Autre"}),
    c("BS-7 dalle béton", "BS", "BS-7", R),
    c("BS-7 faux plafond plénum 0,50 béton", "BS", "BS-7", R,
      local={"PL-01": "Faux plafond démontable (dalles sur ossature)", "PL-02": 0.5}),
    # --- III.b.i Ventilation naturelle nocturne (VN) ------------------------------------------------
    c("VN-1 aucune baie", "VN", "VN-1", NR, local={"aucune_baie": True}),
    c("VN-2 vitrage fixe seul", "VN", "VN-2", NR, local={"murs": [mur(baies={"Vitrage fixe": 3})]}),
    c("VN-2 mur-rideau seul", "VN", "VN-2", NR, local={"murs": [mur(baies={"Façade vitrée continue (mur-rideau)": 1})]}),
    c("VN-2 fixe sur deux murs", "VN", "VN-2", NR,
      local={"murs": [mur(baies={"Vitrage fixe": 1}), mur(orientation="N", baies={"Vitrage fixe": 2})]}),
    c("VN-3 volets pleins", "VN", "VN-3", SR, local={"MEX-29": ["Volets roulants"], "MEX-30": "Non (pleins)"}),
    c("VN-3 stores pleins", "VN", "VN-3", SR, local={"MEX-29": ["Stores"], "MEX-30": "Non (pleins)"}),
    c("VN-4 alarme", "VN", "VN-4", SR, bat={"B-08": "Oui"}, local={"MEX-37": "Oui"}),
    c("VN-5 menuiserie dégradée", "VN", "VN-5", SR,
      local={"murs": [mur(MEX_06="Dégradé (manœuvre difficile, pièces cassées, pourriture ou corrosion)")]}),
    c("VN-5 très dégradée", "VN", "VN-5", SR, local={"murs": [mur(MEX_06="Très dégradé, remplacement à envisager")]}),
    c("VN-6 oscillo-battant seul", "VN", "VN-6", SR, local={"murs": [mur(baies={"Fenêtre oscillo-battante": 2})]}),
    c("VN-6 soufflet + fixe", "VN", "VN-6", SR,
      local={"murs": [mur(baies={"Imposte en soufflet": 2, "Vitrage fixe": 1})]}),
    c("VN-7 traversant S/N", "VN", "VN-7", R, local={"murs": [mur(), mur(orientation="N")]}),
    c("VN-7 angle S/E", "VN", "VN-7", R, local={"murs": [mur(), mur(orientation="E")]}),
    c("VN-8 façade + toiture ouvrante", "VN", "VN-8", R, local=dict(FT, **{"MEX-16": "Oui", "MEX-17": "Manuelle"})),
    c("VN-9 porte standard", "VN", "VN-9", R, local={"MEX-34": "Oui", "MEX-35": "Oui, porte standard"}),
    c("VN-9 coupe-feu ventouse", "VN", "VN-9", R,
      local={"MEX-34": "Oui", "MEX-35": "Oui, porte coupe-feu avec ventouse asservie à la détection incendie"}),
    c("VN-10 mono-orienté", "VN", "VN-10", SR),
    c("VN-10 porte coupe-feu fermée", "VN", "VN-10", SR,
      local={"MEX-34": "Oui", "MEX-35": "Non, porte coupe-feu ou à fermeture automatique"}),
    # --- III.b.ii Ventilation mécanique nocturne (VM) ----------------------------------------------
    c("VM-1 pas de VMC", "VM", "VM-1", NR, bat={"B-09": "Non"}),
    c("VM-1 local non desservi", "VM", "VM-1", NR, local={"BA-15": "Non"}),
    c("VM-2 simple flux sans surdébit", "VM", "VM-2", NR, bat={"B-14": "Non"}),
    c("VM-3 à l'arrêt", "VM", "VM-3", AO, bat={"B-13": "À l'arrêt ou hors service"}),
    c("VM-3 filtres", "VM", "VM-3", AO, bat={"B-13": "Filtres encrassés"}),
    c("VM-4 by-pass non activé", "VM", "VM-4", AO, bat={"B-10": "Double flux", "B-11": "Oui", "B-12": "Non"}),
    c("VM-5 pas de programmation", "VM", "VM-5", AO, bat={"B-15": "Non"}),
    c("VM-6 mode nocturne non programmé", "VM", "VM-6", AO, bat={"B-16": "Non"}),
    c("VM-7 en place simple flux", "VM", "VM-7", EP),  # 500 / (60 × 3) = 2,8 vol/h
    c("VM-7 en place double flux by-pass actif", "VM", "VM-7", EP,
      bat={"B-10": "Double flux", "B-11": "Oui", "B-12": "Oui"}),
    c("VM-8 double flux sans by-pass", "VM", "VM-8", SR, bat={"B-10": "Double flux", "B-11": "Non"}),
    c("VM-10 débit insuffisant", "VM", "VM-10", SR, local={"BA-18": 300}),  # 1,7 vol/h
    # --- III.c.i Protections verticales (PV) -------------------------------------------------------
    c("PV-0 aucune baie", "PV", "PV-0", NC, local={"aucune_baie": True}),
    c("PV-1 nu extérieur sans débord", "PV", "PV-1", NR, local={"murs": [mur(MEX_04="Nu extérieur", MEX_05=SUPPR)]}),
    c("PV-2 tableau 15 cm", "PV", "PV-2", SR, local={"murs": [mur(MEX_05=15)]}),
    c("PV-2 tunnel 10 cm", "PV", "PV-2", SR, local={"murs": [mur(MEX_04="En tunnel", MEX_05=10)]}),
    c("PV-3 monument historique", "PV", "PV-3", SR, bat={"B-05": "Oui"}),
    c("PV-3 abords", "PV", "PV-3", SR, bat={"B-06": "Oui"}),
    c("PV-4 ITE (MEX-26)", "PV", "PV-4", SR,
      local={"MEX-26": "Isolation par l'extérieur (enduit sur isolant, bardage ventilé)"}),
    c("PV-4 ossature (MEX-26)", "PV", "PV-4", SR, local={"MEX-26": "Ossature légère avec bardage ou vêture"}),
    c("PV-4 à défaut B-03", "PV", "PV-4", SR, bat={"B-03": "Ossature légère"}, local=ISOLE_LOCAL),
    c("PV-4 à défaut B-04", "PV", "PV-4", SR, bat={"B-04": "ITE (isolation par l'extérieur)"}, local=ISOLE_LOCAL),
    c("PV-5 étage sans accès nacelle", "PV", "PV-5", SR, fac={"S": {"F-03": "Non"}}),
    c("PV-6 obstacle", "PV", "PV-6", SR, fac={"S": {"F-04": "Oui"}}),
    c("PV-7 désordre", "PV", "PV-7", SR, fac={"S": {"F-05": "Oui"}}),
    c("PV-8 défaut", "PV", "PV-8", R),
    # --- III.c.ii Protections horizontales (PH) ----------------------------------------------------
    c("PH-0 aucune baie", "PH", "PH-0", NC, local={"aucune_baie": True}),
    c("PH-1 débord important au sud", "PH", "PH-1", EP, local={"murs": [mur(MEX_07="Important")]}),
    c("PH-1 débord important SE", "PH", "PH-1", EP, local={"murs": [mur(orientation="SE", MEX_07="Important")]}),
    c("PH-2 débord faible SO", "PH", "PH-2", AO, local={"murs": [mur(orientation="SO", MEX_07="Faible")]}),
    c("PH-3 pas de mur sud", "PH", "PH-3", NR, local={"murs": [mur(orientation="N")]}),
    c("PH-3 est et ouest", "PH", "PH-3", NR, local={"murs": [mur(orientation="E"), mur(orientation="O")]}),
    c("PH-4 RDC alignement", "PH", "PH-4", NR, fac={"S": {"F-02": "Oui"}}, local={"L-09": "RDC"}),
    c("PH-4 plain-pied alignement", "PH", "PH-4", NR, fac={"S": {"F-02": "Oui"}},
      local={"L-09": "RDC et dernier niveau (plain-pied)"}),
    c("PH-5 patrimoine", "PH", "PH-5", SR, bat={"B-06": "Oui"}),
    c("PH-6 étage alignement", "PH", "PH-6", SR, fac={"S": {"F-02": "Oui"}}),
    c("PH-7 ITE", "PH", "PH-7", SR, local={"MEX-26": "Ossature légère avec bardage ou vêture"}),
    c("PH-8 sans accès nacelle", "PH", "PH-8", SR, fac={"S": {"F-03": "Non"}}),
    c("PH-9 obstacle", "PH", "PH-9", SR, fac={"S": {"F-04": "Oui"}}),
    c("PH-10 désordre", "PH", "PH-10", SR, fac={"S": {"F-05": "Oui"}}),
    c("PH-11 défaut", "PH", "PH-11", R),
    # --- III.c.iii Films solaires (FS) -------------------------------------------------------------
    c("FS-0 aucune baie", "FS", "FS-0", NC, local={"aucune_baie": True}),
    c("FS-1 film dégradé", "FS", "FS-1", AO, local={"MEX-32": "Sur une partie des baies", "MEX-33": "État détérioré"}),
    c("FS-2 film partout bon état", "FS", "FS-2", EP, local={"MEX-32": "Sur toutes les baies", "MEX-33": "Bon état"}),
    c("FS-3 aucun film", "FS", "FS-3", R),
    c("FS-3 film partiel bon état", "FS", "FS-3", R, local={"MEX-32": "Sur une partie des baies", "MEX-33": "Bon état"}),
    # --- III.c.iv Fenêtres de toiture (FT) ---------------------------------------------------------
    c("FT-1 pas de baie en plafond", "FT", "FT-1", NC),
    c("FT-1 verrière seule", "FT", "FT-1", NC, local=dict(VV, **{"MEX-15": ["Verrière"]})),
    c("FT-2 volet extérieur HS", "FT", "FT-2", AO,
      local=dict(FT, **{"MEX-18": ["Volet extérieur"], "MEX-19": "Hors service ou dégradée"})),
    c("FT-3 store intérieur seul", "FT", "FT-3", AO, local=dict(FT, **{"MEX-18": ["Store intérieur"]})),
    c("FT-4 store extérieur bon état", "FT", "FT-4", EP,
      local=dict(FT, **{"MEX-18": ["Store extérieur"], "MEX-19": "Bon état"})),
    c("FT-5 patrimoine", "FT", "FT-5", SR, bat={"B-05": "Oui"}, local=FT),
    c("FT-6 fenêtre non identifiable", "FT", "FT-6", SR, local=dict(FT, **{"MEX-20": "Non identifiables"})),
    c("FT-6 très ancienne", "FT", "FT-6", SR, local=dict(FT, **{"MEX-20": "Fenêtre très ancienne"})),
    c("FT-7 hors d'atteinte, fixe", "FT", "FT-7", SR, local=dict(FT, **{"MEX-21": "Non"})),
    c("FT-7 hors d'atteinte, manuelle", "FT", "FT-7", SR,
      local=dict(FT, **{"MEX-21": "Non", "MEX-16": "Oui", "MEX-17": "Manuelle"})),
    c("FT-8 hors d'atteinte mais électrique", "FT", "FT-8", R,
      local=dict(FT, **{"MEX-21": "Non", "MEX-16": "Oui", "MEX-17": "Électrique"})),
    c("FT-8 défaut", "FT", "FT-8", R, local=FT),
    c("FT-8 lanterneau", "FT", "FT-8", R, local=dict(FT, **{"MEX-15": ["Lanterneau"]})),
    # --- III.c.vi Vérandas et verrières (VV) -------------------------------------------------------
    c("VV-1 pas de véranda", "VV", "VV-1", NC),
    c("VV-1 fenêtre de toit seule", "VV", "VV-1", NC, local=FT),
    c("VV-2 store extérieur HS", "VV", "VV-2", AO,
      local=dict(VV, **{"MEX-18": ["Store extérieur"], "MEX-19": "Hors service ou dégradée"})),
    c("VV-3 protection intérieure seule", "VV", "VV-3", AO, local=dict(VV, **{"MEX-18": ["Store intérieur"]})),
    c("VV-4 aucun ouvrant", "VV", "VV-4", AO, local=dict(VV, **{"MEX-16": "Non"})),
    c("VV-5 en place", "VV", "VV-5", EP, local=dict(VV, **{"MEX-18": ["Volet extérieur"], "MEX-19": "Bon état"})),
    c("VV-6 patrimoine", "VV", "VV-6", SR, bat={"B-05": "Oui"}, local=VV),
    c("VV-7 toiture non accessible", "VV", "VV-7", SR, local=dict(VV, **{"MEX-22": "Non"})),
    c("VV-8 pas de séparation", "VV", "VV-8", SR, local=dict(VV, **{"MEX-24": "Non"})),
    c("VV-9 défaut véranda", "VV", "VV-9", R, local=VV),
    c("VV-9 verrière", "VV", "VV-9", R, local=dict(VV, **{"MEX-15": ["Verrière"]})),
    c("VV-9 atrium", "VV", "VV-9", R, local=dict(VV, **{"MEX-15": ["Puits de lumière, atrium"]})),
    # --- III.c.v Toiture (TO, TT, CP, CA) ----------------------------------------------------------
    c("TO-0 étage intermédiaire", "TO", "TO-0", NC),
    c("TO-0 RDC", "TO", "TO-0", NC, local={"L-09": "RDC"}),
    c("TO-0 sous-sol", "TO", "TO-0", NC, local={"L-09": "Sous-sol"}),
    c("TT-1 terrasse non isolée", "TT", "TT-1", SR, bat=dict(TERRASSE, **{"B-19": "Non isolée"}), local=DERNIER),
    c("TT-2 terrasse 30 cm", "TT", "TT-2", EP, bat=TERRASSE, local=DERNIER),
    c("TT-3 terrasse 29 cm", "TT", "TT-3", SR, bat=dict(TERRASSE, **{"B-20": 29}), local=DERNIER),
    c("TT-2 bac acier plain-pied", "TT", "TT-2", EP, bat=dict(TERRASSE, **{"B-18": "Bac acier ou fibro-ciment"}),
      local={"L-09": "RDC et dernier niveau (plain-pied)"}),
    c("CP-1 isolant tassé", "CP", "CP-1", AO, bat={"B-23": ["Tassée"]}, local=DERNIER),
    c("CP-1 isolant discontinu", "CP", "CP-1", AO, bat={"B-23": ["Discontinue ou partiellement déplacée"]},
      local=DERNIER),
    c("CP-2 combles non ventilés", "CP", "CP-2", AO, bat={"B-25": "Non"}, local=DERNIER),
    c("CP-3 30 cm bon état", "CP", "CP-3", EP, bat={"B-24": 30}, local=DERNIER),
    c("CP-4 non accessibles", "CP", "CP-4", SR, bat={"B-26": "Non"}, local=DERNIER),
    c("CP-5 humidité", "CP", "CP-5", SR, bat={"B-27": "Oui"}, local=DERNIER),
    c("CP-6 spots", "CP", "CP-6", SR, bat={"B-28": ["Spots encastrés"]}, local=DERNIER),
    c("CP-6 amiante", "CP", "CP-6", SR, bat={"B-28": ["Matériaux suspects d'amiante"]}, local=DERNIER),
    c("CP-7 isolant 20 cm", "CP", "CP-7", R, local=DERNIER),
    c("CA-1 épaisseur inconnue", "CA", "CA-1", SR, bat=dict(RAMPANTS, **{"B-24": "inconnu"}), local=DERNIER),
    c("CA-2 rampants 15 cm", "CA", "CA-2", SR, bat=dict(RAMPANTS, **{"B-24": 15}), local=DERNIER),
    c("CA-3 rampants 20 cm", "CA", "CA-3", EP, bat=RAMPANTS, local=DERNIER),
    # --- III.c.vii Charges internes (CO, CE, CQ) ---------------------------------------------------
    c("CO-1 bureau 5 m²/pers", "CO", "CO-1", SR,
      local={"L-02": "Bureau, salle des maîtres, salle de réunion", "L-03": 20, "L-04": 4}),
    c("CO-2 classe 1,2 m²/élève", "CO", "CO-2", SR, local={"L-03": 30, "L-04": 25}),
    c("CO-3 classe 2,4 m²/élève", "CO", "CO-3", EP),
    c("CO-3 dortoir dense", "CO", "CO-3", EP, local={"L-02": "Dortoir ou salle de repos", "L-03": 10, "L-04": 25}),
    c("CE-1 non LED", "CE", "CE-1", R, local={"ECL-01": "Non LED (tubes fluorescents, halogène, incandescence)"}),
    c("CE-1 mixte", "CE", "CE-1", R, local={"ECL-01": "Mixte (LED et non LED)"}),
    c("CE-2 LED", "CE", "CE-2", EP),
    c("CQ-1 copieurs", "CQ", "CQ-1", SR, local={"L-10": ["Copieurs, imprimantes"]}),
    c("CQ-1 cuisson", "CQ", "CQ-1", SR, local={"L-10": ["Appareils de cuisson"]}),
    c("CQ-2 postes allumés", "CQ", "CQ-2", AO, local={"L-11": "Non"}),
    c("CQ-3 défaut", "CQ", "CQ-3", EP),
    c("CQ-3 équipement mais local inoccupé", "CQ", "CQ-3", EP, local={"L-10": ["Autre"], "L-04": 0}),
    # --- III.d.ii Ombrage adossé (OA) -------------------------------------------------------------
    c("OA-1 façade nord", "OA", "OA-1", NR, espace={"E-20": ["N"]}),
    c("OA-1 aucune façade", "OA", "OA-1", NR, espace={"E-20": ["Aucune"]}),
    c("OA-2 structure en place", "OA", "OA-2", EP, espace={"E-21": "En bon état, couvre l'essentiel de la zone d'usage"}),
    c("OA-3 couvre une partie", "OA", "OA-3", AO, espace={"E-21": "En bon état, couvre une partie de la zone d'usage"}),
    c("OA-3 dégradée", "OA", "OA-3", AO, espace={"E-21": "Hors service ou dégradée"}),
    c("OA-4 alignement", "OA", "OA-4", NR, fac={"S": {"F-02": "Oui"}}),
    c("OA-5 patrimoine", "OA", "OA-5", SR, bat={"B-05": "Oui"}),
    c("OA-6 bardage", "OA", "OA-6", SR, espace={"E-22": "Bardage"}),
    c("OA-6 non identifiable", "OA", "OA-6", SR, espace={"E-22": "Non identifiable"}),
    c("OA-7 issue de secours", "OA", "OA-7", SR, espace={"E-23": "Oui"}),
    c("OA-7 accès pompiers", "OA", "OA-7", SR, espace={"E-31": "Oui"}),
    c("OA-8 mâts à créer", "OA", "OA-8", SR, espace={"E-24": "Aucun existant, mâts ou poteaux à créer"}),
    c("OA-9 aucun ancrage", "OA", "OA-9", SR, espace={"E-24": "Aucun possible"}),
    c("OA-10 recommandé", "OA", "OA-10", R),
    c("OA-11 espace encombré", "OA", "OA-11", SR, espace={"E-25": "Non"}),
    # --- III.d.iii Préau (PR) ----------------------------------------------------------------------
    c("PR-1 pas de préau", "PR", "PR-1", NC, espace={"E-02": ["Cour de récréation"]}),
    c("PR-2 translucide", "PR", "PR-2", AO, espace={"E-26": "Polycarbonate ou verrière", "E-27": "Non"}),
    c("PR-3 deux côtés fermés", "PR", "PR-3", AO, espace={"E-30": 2}),
    c("PR-4 teinte foncée", "PR", "PR-4", AO, espace={"E-28": "Foncée"}),
    c("PR-4 teinte moyenne", "PR", "PR-4", AO, espace={"E-26": "Bac acier ou tôle, isolé", "E-28": "Moyenne"}),
    c("PR-5 tôle basse", "PR", "PR-5", AO, espace={"E-26": "Bac acier ou tôle, non isolé", "E-29": 2.9}),
    c("PR-6 ouvert tuiles", "PR", "PR-6", EP),
    c("PR-6 ouvert claire", "PR", "PR-6", EP, espace={"E-26": "Bac acier ou tôle, isolé", "E-30": 0}),
    c("PR-7 défaut", "PR", "PR-7", SR, espace=PREAU_FONCE_TRANSLUCIDE),
    # --- III.d.iv Ombrage de la cour (OC) ---------------------------------------------------------
    c("OC-1 ombre 25-50 %", "OC", "OC-1", EP, espace={"E-09": "Entre 25 et 50 %"}),
    c("OC-1 arbres en bon état", "OC", "OC-1", EP,
      espace={"E-09": "Entre 75 et 100 %", "E-10": ["Arbres"], "E-12": "Bon"}),
    c("OC-2 arbres dégradés", "OC", "OC-2", AO,
      espace={"E-09": "Entre 25 et 50 %", "E-10": ["Arbres"], "E-12": "Dégradé"}),
    c("OC-2 voiles < 25 %", "OC", "OC-2", AO,
      espace={"E-09": "Entre 0 et 25 %", "E-10": ["Voiles d'ombrage"], "E-15": "Bon état"}),
    c("OC-2 pergola HS", "OC", "OC-2", AO,
      espace={"E-09": "Entre 50 et 75 %", "E-10": ["Pergola ou treille végétalisée"], "E-15": "Hors service ou dégradé"}),
    c("OC-3 patrimoine", "OC", "OC-3", SR, bat={"B-05": "Oui"}),
    c("OC-4 dalle sur parking", "OC", "OC-4", SR, espace={"E-32": "Dalle sur ouvrage ou parking souterrain"}),
    c("OC-4 faible épaisseur", "OC", "OC-4", SR, espace={"E-32": "Faible épaisseur de terre"}),
    c("OC-5 voie pompiers", "OC", "OC-5", SR, espace={"E-31": "Oui"}),
    c("OC-6 défaut", "OC", "OC-6", R),
]


@pytest.mark.parametrize("bloc,regle,statut,bat,fac,local,espace,param", CAS)
def test_une_regle(bloc, regle, statut, bat, fac, local, espace, param):
    d = donnees(bat=bat, fac=fac, local=local, espace=espace, param=param)
    obtenu_regle, obtenu_statut, manquante, s = evaluer(d, bloc)
    assert bloc in s["blocs"] or (bloc in ("TO",) and s["blocs"] == ["TO"]), (bloc, s["blocs"])
    assert (obtenu_regle, obtenu_statut, manquante) == (regle, statut, False)


# ------------------------------------------------------------------ cas qui révèlent un écart
@pytest.mark.parametrize("patch", [{"L-03": 0}, {"PL-03": 0}], ids=["surface 0", "hauteur 0"])
def test_vm_volume_nul_ne_donne_pas_recommande(patch):
    regle, statut, manquante, _ = evaluer(donnees(local=patch), "VM")
    assert statut != R, (regle, statut)


def test_vm11_inatteignable_avec_des_donnees_valides():
    """VM-11 (« Recommandé ») ne peut être retenue : B-16 = Oui mène à VM-7 ou VM-10, B-16 ≠ Oui à VM-5 /
    VM-6 (question de méthode QM-01). On parcourt toutes les combinaisons des réponses bâtiment."""
    import itertools
    vues = set()
    choix = {k: ["Oui", "Non", None] for k in ("B-09", "B-11", "B-12", "B-14", "B-15", "B-16")}
    choix["B-10"] = ["Double flux", "Simple flux", None]
    choix["B-13"] = ["En fonctionnement", "Filtres encrassés", None]
    for valeurs in itertools.product(*choix.values()):
        bat = {k: (SUPPR if v is None else v) for k, v in zip(choix, valeurs)}
        for debit in (100, 500, SUPPR):
            vues.add(evaluer(donnees(bat=bat, local={"BA-18": debit}), "VM")[0])
    assert "VM-11" not in vues and "VM-9" not in vues
    assert {"VM-1", "VM-2", "VM-3", "VM-4", "VM-5", "VM-6", "VM-7", "VM-8", "VM-10"} <= vues


def test_vm9_debit_inconnu_donne_sous_reserve_par_vm7():
    """Méthode VM-9 : débit inconnu → « Sous réserve ». Le statut est bon, mais la règle retenue est
    VM-7 (indéterminée), pas VM-9 (QM-01)."""
    regle, statut, manquante, _ = evaluer(donnees(local={"BA-18": SUPPR}), "VM")
    assert (regle, statut, manquante) == ("VM-7", SR, True)


# ------------------------------------------------------------------ alertes
def alertes(d, quoi="locaux", i=0):
    x = moteur.calculer(d)[quoi][i]
    return {a for s in x["solutions"] for a in s["alertes"]}, x


@pytest.mark.parametrize("ident,attendu,kw", [
    ("BR-AL toujours", {"BR-AL"}, {}),
    ("BR-AL même si non recommandé", {"BR-AL"}, {"local": {"PL-03": 2.2}}),
    ("VN-AL1 sans grilles", {"BR-AL", "VN-AL1"}, {"local": {"MEX-36": ["Moustiquaire"]}}),
    ("VN-AL1 aucun", {"BR-AL", "VN-AL1"}, {"local": {"MEX-36": ["Aucun"]}}),
    ("VN-AL1 pas si VN non recommandé", {"BR-AL"}, {"local": {"MEX-36": ["Aucun"], "aucune_baie": True}}),
    ("VN-AL1 ventelles", {"BR-AL"}, {"local": {"MEX-36": ["Ventelles"]}}),
    ("VN-AL2 si VN recommandé", {"BR-AL", "VN-AL2"}, {"local": {"murs": [mur(), mur(orientation="N")]}}),
    ("FT-AL ouvrante", {"BR-AL", "FT-AL", "VN-AL2"}, {"local": dict(FT, **{"MEX-16": "Oui", "MEX-17": "Électrique"})}),
    ("FT-AL fixe", {"BR-AL"}, {"local": FT}),
    ("VV-AL véranda", {"BR-AL", "VV-AL", "VN-AL2"}, {"local": VV}),
    ("VV-AL verrière", {"BR-AL", "VV-AL", "VN-AL2"}, {"local": dict(VV, **{"MEX-15": ["Verrière"]})}),
])
def test_alertes_locaux(ident, attendu, kw):
    assert alertes(donnees(**kw))[0] == attendu


@pytest.mark.parametrize("ident,attendu,ex_al,kw", [
    ("base", {"OA-AL2", "OA-AL3"}, 0, {}),
    ("OA non recommandé : pas d'alerte OA", set(), 0, {"espace": {"E-20": ["N"]}}),
    ("OA sous réserve : OA-AL2/3", {"OA-AL2", "OA-AL3"}, 0, {"espace": {"E-25": "Non"}}),
    ("OA à optimiser : pas d'alerte", set(), 0, {"espace": {"E-21": "Hors service ou dégradée"}}),
    ("EX-AL élémentaire 0,7 m²/enfant + PR-AL4", {"OA-AL2", "OA-AL3", "PR-AL4"}, 1,
     {"espace": {"E-14": 70, "E-06": 100}}),
    ("EX-AL maternelle 5 classes 99 m²", {"OA-AL2", "OA-AL3", "PR-AL4"}, 1,
     {"espace": {"E-04": ["Maternelle"], "E-07": 5, "E-14": 99}}),
    ("EX-AL maternelle 6 classes 149 m²", {"OA-AL2", "OA-AL3", "PR-AL4"}, 1,
     {"espace": {"E-04": ["Maternelle"], "E-07": 6, "E-14": 149}}),
    ("EX-AL maternelle 6 classes 150 m²", {"OA-AL2", "OA-AL3"}, 0,
     {"espace": {"E-04": ["Maternelle"], "E-07": 6, "E-14": 150}}),
    ("PR-AL4 sans préau : EX-AL seule", {"OA-AL2", "OA-AL3"}, 1,
     {"espace": {"E-14": 70, "E-02": ["Cour de récréation"]}}),
    ("PR-AL1 patrimoine", {"OA-AL2", "OA-AL3", "PR-AL1"}, 0, {"bat": {"B-06": "Oui"}}),
    ("PR-AL2 préau à optimiser", {"OA-AL2", "OA-AL3", "PR-AL2"}, 0, {"espace": {"E-30": 2}}),
    ("PR-AL3 fibrociment 1975-1997", {"OA-AL2", "OA-AL3", "PR-AL3"}, 0,
     {"bat": {"B-01": "De 1975 à 1997"}, "espace": {"E-26": "Fibrociment"}}),
    ("PR-AL3 fibrociment après 1997", {"OA-AL2", "OA-AL3"}, 0,
     {"bat": {"B-01": "Après 1997"}, "espace": {"E-26": "Fibrociment"}}),
    ("PR-AL3 fibrociment date inconnue", {"OA-AL2", "OA-AL3", "PR-AL3"}, 0,
     {"bat": {"B-01": "Non renseigné"}, "espace": {"E-26": "Fibrociment"}}),
])
def test_alertes_espaces(ident, attendu, ex_al, kw):
    a, x = alertes(donnees(**kw), "espaces")
    # EX-AL est rattachée à la solution « Ombrage autoportant ou végétal de la cour » (correctif ANO-10)
    assert (a - {"EX-AL"}, x["EX-AL"]) == (attendu, ex_al)
    assert ("EX-AL" in a) == (ex_al == 1)


def test_oa_al1_mutualisation():
    """OA-AL1 : OA recommandé et local du RDC, même orientation, protection horizontale recommandée."""
    rdc = fusion(LOCAL, {"L-09": "RDC"})
    a, _ = alertes(donnees(locaux=[rdc]), "espaces")
    assert "OA-AL1" in a
    a, _ = alertes(donnees(locaux=[fusion(LOCAL, {})]), "espaces")  # local à l'étage
    assert "OA-AL1" not in a
    a, _ = alertes(donnees(locaux=[fusion(rdc, {"murs": [mur(orientation="E")]})]), "espaces")  # autre orientation
    assert "OA-AL1" not in a
    a, _ = alertes(donnees(locaux=[fusion(rdc, {"murs": [mur(MEX_07="Important")]})]), "espaces")  # PH en place
    assert "OA-AL1" not in a
    a, _ = alertes(donnees(locaux=[rdc], espace={"E-25": "Non"}), "espaces")  # OA sous réserve
    assert "OA-AL1" in a
