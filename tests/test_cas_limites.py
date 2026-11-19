"""Partie B (suite) — valeurs limites, priorités, données manquantes, questions masquées, choix
multiples contradictoires, murs, dépendances croisées.

Les anomalies sont référencées ANO-xx, les questions de méthode QM-xx (docs/rapport_tests.md).
"""
from __future__ import annotations

import pytest

from cas_base import (BRASSEURS_EN_PLACE, DERNIER, FENETRE_DE_TOIT, LOCAL, ESPACE, SUPPR, VERANDA, donnees, evaluer,
                      fusion, moteur, mur, statuts)
from surya.questions import QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL, visible

R, AO, EP, SR, NR, NC = (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE, moteur.SOUS_RESERVE,
                         moteur.NON_RECOMMANDE, moteur.NON_CONCERNE)
BP = BRASSEURS_EN_PLACE
FLOTTANT = ()  # ANO-01 corrigée : rapports arrondis avant comparaison


def b(ident, bloc, attendu, marks=(), **kw):
    """attendu : (règle, statut)."""
    return pytest.param(bloc, attendu, kw, id=ident, marks=marks)


BORNES = [
    # Hauteur sous plafond (méthode III.a.ii-1 « moins de 2,40 », -3 « entre 2,40 inclus et 2,60 exclu »)
    b("HSP 2,39", "BS", ("BS-1", NR), local={"PL-03": 2.39}),
    b("HSP 2,40", "BS", ("BS-3", SR), local={"PL-03": 2.40}),
    b("HSP 2,41", "BS", ("BS-3", SR), local={"PL-03": 2.41}),
    b("HSP 2,59", "BS", ("BS-3", SR), local={"PL-03": 2.59}),
    b("HSP 2,60", "BS", ("BS-7", R), local={"PL-03": 2.60}),
    b("HSP 2,61", "BS", ("BS-7", R), local={"PL-03": 2.61}),
    # Plénum (III.a.ii-4 « supérieure à 70 cm » ; -7 « plénum ≤ 70 cm »)
    *[b(f"plénum {h}", "BS", attendu, local={"PL-01": "Faux plafond démontable (dalles sur ossature)", "PL-02": h})
      for h, attendu in ((0.69, ("BS-7", R)), (0.70, ("BS-7", R)), (0.71, ("BS-4", SR)))],
    # Pale-plafond / diamètre (III.a.i-3 « ≤ 0,15 ») : (300 − pale) / 200
    b("pale 0,145", "BP", ("BP-3", AO), local=dict(BP, **{"BA-12": 271})),
    b("pale 0,150", "BP", ("BP-3", AO), local=dict(BP, **{"BA-12": 270})),
    b("pale 0,155", "BP", ("BP-5", EP), local=dict(BP, **{"BA-12": 269})),
    b("pale 0,150 (2,45 m ; 221 cm ; Ø 160)", "BP", ("BP-3", AO), marks=FLOTTANT,
      local=dict(BP, **{"PL-03": 2.45, "BA-12": 221, "BA-09": 160, "BA-13": 300})),
    # Équation 1 : 0,2 < (Ø/100) / (√S / n) < 0,4 (III.a.i-4), S = 36 m², n = 1
    *[b(f"équation 1, Ø {d}", "BP", attendu, local=dict(BP, **{"L-03": 36, "BA-09": d, "BA-13": 400}))
      for d, attendu in ((119, ("BP-4", AO)), (120, ("BP-4", AO)), (121, ("BP-5", EP)), (239, ("BP-5", EP)),
                         (241, ("BP-4", AO)))],
    b("équation 1 = 0,4 (Ø 240, 36 m²)", "BP", ("BP-4", AO), marks=FLOTTANT,
      local=dict(BP, **{"L-03": 36, "BA-09": 240, "BA-13": 400})),
    b("équation 1 = 0,4 (2 brasseurs Ø 140, 49 m²)", "BP", ("BP-4", AO), marks=FLOTTANT,
      local=dict(BP, **{"L-03": 49, "BA-06": 2, "BA-09": 140, "BA-13": 400, "BA-14": 600})),
    # Assertion 1 : distance au mur > diamètre ; assertion 2 : entraxe > 2,5 × diamètre
    *[b(f"mur {m} cm / Ø 200", "BP", attendu, local=dict(BP, **{"BA-13": m}))
      for m, attendu in ((199, ("BP-4", AO)), (200, ("BP-4", AO)), (201, ("BP-5", EP)))],
    *[b(f"entraxe {e} cm / Ø 200", "BP", attendu, local=dict(BP, **{"BA-06": 2, "L-03": 240, "BA-14": e}))
      for e, attendu in ((499, ("BP-4", AO)), (500, ("BP-4", AO)), (501, ("BP-5", EP)))],
    # Distance vitrage-façade (III.c.i-2 « inférieure à 16 cm »)
    *[b(f"tableau {x} cm", "PV", attendu, local={"murs": [mur(MEX_05=x)]})
      for x, attendu in ((15, ("PV-2", SR)), (15.9, ("PV-2", SR)), (16, ("PV-8", R)), (17, ("PV-8", R)))],
    # Isolant toiture-terrasse (III.c.v « R ≥ 7,5 soit 30 cm » / « R < 7,5 »)
    *[b(f"terrasse {e} cm", "TT", attendu, bat={"B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": e}, local=DERNIER)
      for e, attendu in ((29, ("TT-3", SR)), (30, ("TT-2", EP)), (31, ("TT-2", EP)))],
    # Combles perdus (CP-3 « au moins 30 cm »)
    *[b(f"combles {e} cm", "CP", attendu, bat={"B-24": e}, local=DERNIER)
      for e, attendu in ((29, ("CP-7", R)), (30, ("CP-3", EP)), (31, ("CP-3", EP)))],
    # Rampants (CA-2 « moins de 20 cm », CA-3 « au moins 20 cm »)
    *[b(f"rampants {e} cm", "CA", attendu, bat={"B-22": "Sous pente", "B-24": e}, local=DERNIER)
      for e, attendu in ((19, ("CA-2", SR)), (20, ("CA-3", EP)), (21, ("CA-3", EP)))],
    # Bureau : 6 m² par occupant (CO-1 « inférieure à 6 m² »)
    *[b(f"bureau {s} m² / 4", "CO", attendu,
        local={"L-02": "Bureau, salle des maîtres, salle de réunion", "L-03": s, "L-04": 4})
      for s, attendu in ((23, ("CO-1", SR)), (24, ("CO-3", EP)), (25, ("CO-3", EP)))],
    # Classe : 1,5 m² par élève (CO-2)
    *[b(f"classe {s} m² / 25", "CO", attendu, local={"L-03": s, "L-04": 25})
      for s, attendu in ((37, ("CO-2", SR)), (37.5, ("CO-3", EP)), (38, ("CO-3", EP)))],
    # Débit de 2 vol/h (VM-7 « au moins 2 vol/h », VM-10 « inférieur à 2 vol/h ») : 60 m² × 3 m = 180 m³
    *[b(f"débit {q} m³/h", "VM", attendu, local={"BA-18": q})
      for q, attendu in ((359, ("VM-10", SR)), (360, ("VM-7", EP)), (361, ("VM-7", EP)))],
    b("débit 2 vol/h (243 m³/h ; 45 m² × 2,70 m)", "VM", ("VM-7", EP), marks=FLOTTANT,
      local={"BA-18": 243, "L-03": 45, "PL-03": 2.7}),
    b("débit 2 vol/h (245 m³/h ; 50 m² × 2,45 m)", "VM", ("VM-7", EP), marks=FLOTTANT,
      local={"BA-18": 245, "L-03": 50, "PL-03": 2.45}),
    # Préau (PR-5 « moins de 3 m », PR-3 « au moins deux côtés », PR-6 « ouvert sur au moins trois côtés »)
    *[b(f"préau tôle {h} m", "PR", attendu,
        espace={"E-26": "Bac acier ou tôle, non isolé", "E-29": h})
      for h, attendu in ((2.99, ("PR-5", AO)), (3, ("PR-6", EP)), (3.01, ("PR-6", EP)))],
    *[b(f"préau {n} côté(s) fermé(s)", "PR", attendu, espace={"E-30": n})
      for n, attendu in ((0, ("PR-6", EP)), (1, ("PR-6", EP)), (2, ("PR-3", AO)), (3, ("PR-3", AO)),
                         (4, ("PR-3", AO)))],
    # Effectif nul : pas de division par zéro, pas de statut « Sous réserve »
    b("classe effectif 0", "CO", ("CO-3", EP), local={"L-04": 0}),
    b("bureau effectif 0", "CO", ("CO-3", EP), local={"L-02": "Bureau, salle des maîtres, salle de réunion", "L-04": 0}),
]


@pytest.mark.parametrize("bloc,attendu,kw", BORNES)
def test_bornes(bloc, attendu, kw):
    regle, statut, manquante, _ = evaluer(donnees(**kw), bloc)
    assert (regle, statut, manquante) == (*attendu, False)


EX_AL = [
    # III.d.i : « inférieur à 0,8 m² par enfant (élémentaire) »
    ((80, 100, ["Élémentaire"], None), 0), ((79, 100, ["Élémentaire"], None), 1), ((81, 100, ["Élémentaire"], None), 0),
    # « inférieure à 100 m² pour 5 classes ou moins, ou à 150 m² pour 6 classes ou plus (maternelle) »
    ((99, 100, ["Maternelle"], 5), 1), ((100, 100, ["Maternelle"], 5), 0), ((101, 100, ["Maternelle"], 5), 0),
    ((99, 100, ["Maternelle"], 4), 1), ((120, 100, ["Maternelle"], 5), 0), ((120, 100, ["Maternelle"], 6), 1),
    ((149, 100, ["Maternelle"], 6), 1), ((150, 100, ["Maternelle"], 6), 0), ((151, 100, ["Maternelle"], 7), 0),
    # Effectif nul : pas d'alerte, pas de plantage
    ((10, 0, ["Élémentaire"], None), 0),
]


@pytest.mark.parametrize("entree,attendu", EX_AL, ids=[f"{e[0]}m²/{e[1]}p/{e[2][0][:4]}/{e[3]}cl" for e, _ in EX_AL])
def test_bornes_ex_al(entree, attendu):
    s, n, public, cl = entree
    e = {"E-14": s, "E-06": n, "E-04": public}
    if cl is not None:
        e["E-07"] = cl
    assert moteur.calculer(donnees(espace=e))["espaces"][0]["EX-AL"] == attendu


@pytest.mark.parametrize("s,n", [(22.4, 28), (9.6, 12), (40.8, 51)])
def test_ex_al_pile_0_8_par_enfant(s, n):
    assert moteur.calculer(donnees(espace={"E-14": s, "E-06": n}))["espaces"][0]["EX-AL"] == 0


# ------------------------------------------------------------------ ordre de priorité
PRIORITES = [
    b("BS-1 avant BS-2", "BS", ("BS-1", NR), local={"PL-03": 2.2, "BA-19": ["Baffles acoustiques"]}),
    b("BS-2 avant BS-3", "BS", ("BS-2", SR), local={"PL-03": 2.5, "ECL-02": ["Suspendu"]}),
    b("BP-1 avant BP-3", "BP", ("BP-1", AO), local=dict(BP, **{"BA-05": "Présent, hors service", "BA-12": 290})),
    b("VN-1 avant tout", "VN", ("VN-1", NR), bat={"B-08": "Oui"}, local={"aucune_baie": True, "MEX-37": "Oui"}),
    b("VN-2 avant VN-3", "VN", ("VN-2", NR),
      local={"murs": [mur(baies={"Vitrage fixe": 1})], "MEX-29": ["Stores"], "MEX-30": "Non (pleins)"}),
    b("VN-3 avant VN-7", "VN", ("VN-3", SR),
      local={"murs": [mur(), mur(orientation="N")], "MEX-29": ["Volets roulants"], "MEX-30": "Non (pleins)"}),
    b("VN-6 avant VN-7 (oscillo sur 2 murs)", "VN", ("VN-6", SR),
      local={"murs": [mur(baies={"Fenêtre oscillo-battante": 1}), mur(orientation="N", baies={"Fenêtre oscillo-battante": 1})]}),
    b("VM-1 avant VM-3", "VM", ("VM-1", NR), bat={"B-13": "Filtres encrassés"}, local={"BA-15": "Non"}),
    b("PV-1 avant PV-3", "PV", ("PV-1", NR), bat={"B-05": "Oui"}, local={"murs": [mur(MEX_04="Nu extérieur")]}),
    b("PV-2 avant PV-5", "PV", ("PV-2", SR), fac={"S": {"F-03": "Non"}}, local={"murs": [mur(MEX_05=5)]}),
    b("PH-1 avant PH-4", "PH", ("PH-1", EP), fac={"S": {"F-02": "Oui"}},
      local={"L-09": "RDC", "murs": [mur(MEX_07="Important")]}),
    b("PH-1 un mur S important, un SO faible", "PH", ("PH-1", EP),
      local={"murs": [mur(orientation="SO", MEX_07="Faible"), mur(MEX_07="Important")]}),
    b("PH-3 avant PH-5", "PH", ("PH-3", NR), bat={"B-05": "Oui"}, local={"murs": [mur(orientation="N")]}),
    b("FS-1 avant FS-2", "FS", ("FS-1", AO), local={"MEX-32": "Sur toutes les baies", "MEX-33": "État détérioré"}),
    b("FT-2 avant FT-5", "FT", ("FT-2", AO), bat={"B-05": "Oui"},
      local=dict(FENETRE_DE_TOIT, **{"MEX-18": ["Volet extérieur"], "MEX-19": "Hors service ou dégradée"})),
    b("VV-4 avant VV-6", "VV", ("VV-4", AO), bat={"B-05": "Oui"}, local=dict(VERANDA, **{"MEX-16": "Non"})),
    b("TT prioritaire sur combles (B3)", "TT", ("TT-2", EP),
      bat={"B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": 40, "B-23": ["Tassée"]}, local=DERNIER),
    b("CP-1 avant CP-3", "CP", ("CP-1", AO), bat={"B-23": ["Tassée"], "B-24": 40}, local=DERNIER),
    b("CP-2 avant CP-4", "CP", ("CP-2", AO), bat={"B-25": "Non", "B-26": "Non"}, local=DERNIER),
    b("CQ-1 avant CQ-2", "CQ", ("CQ-1", SR), local={"L-10": ["Autre"], "L-11": "Non"}),
    b("OA-1 avant OA-5", "OA", ("OA-1", NR), bat={"B-05": "Oui"}, espace={"E-20": ["NE"]}),
    b("OA-2 avant OA-4", "OA", ("OA-2", EP), fac={"S": {"F-02": "Oui"}},
      espace={"E-21": "En bon état, couvre l'essentiel de la zone d'usage"}),
    b("PR-2 avant PR-3", "PR", ("PR-2", AO), espace={"E-26": "Polycarbonate ou verrière", "E-27": "Non", "E-30": 3}),
    b("PR-3 avant PR-4", "PR", ("PR-3", AO), espace={"E-30": 2, "E-28": "Foncée"}),
    b("OC-1 avant OC-3", "OC", ("OC-1", EP), bat={"B-05": "Oui"}, espace={"E-09": "Entre 50 et 75 %"}),
    b("OC-2 avant OC-4", "OC", ("OC-2", AO),
      espace={"E-10": ["Arbres"], "E-12": "Dégradé", "E-32": "Faible épaisseur de terre"}),
]


@pytest.mark.parametrize("bloc,attendu,kw", PRIORITES)
def test_priorites(bloc, attendu, kw):
    regle, statut, manquante, _ = evaluer(donnees(**kw), bloc)
    assert (regle, statut, manquante) == (*attendu, False)


# ------------------------------------------------------------------ données manquantes
import re  # noqa: E402

from test_regles_methode import CAS  # noqa: E402

TYPES = {q["code"]: q for s in SECTIONS_BATIMENT + SECTIONS_LOCAL + SECTIONS_ESPACE for q in s["questions"]}
# Clés de patch qui ne sont pas « nécessaires » à la règle visée (leur absence donne légitimement un
# autre statut certain) : (identifiant du cas, clé)
NON_NECESSAIRES = {
    # Conditions « ou » : une autre branche certaine suffit à trancher la règle
    ("BP-4 équation 1", "BA-13"), ("BP-4 assertion 1 (mur)", "BA-06"), ("BP-4 assertion 2 (entraxe)", "BA-13"),
    ("BP-4 assertion 2 (entraxe)", "L-03"), ("OC-2 arbres dégradés", "E-09"), ("OC-2 voiles < 25 %", "E-15"),
    ("OC-2 pergola HS", "E-09"),
    # « à défaut » prévu par la règle : MEX-26 vide → B-03 / B-04
    ("PV-4 ITE (MEX-26)", "MEX-26"), ("PV-4 ossature (MEX-26)", "MEX-26"), ("PH-7 ITE", "MEX-26"),
    # B-18 vide avec combles perdus décrits : le bloc CP s'applique (QM-03, lié au point B3)
    ("TT-1 terrasse non isolée", "B-18"),
}


def _cas_manquants():
    for p in CAS:
        bloc, regle, statut, bat, fac, local, espace, param = p.values
        for cible, patch in (("bat", bat), ("local", local), ("espace", espace)):
            necessaires = set(re.findall(r"[A-Z]{1,3}-\d+", moteur.REGLES[regle]["questions"]))
            for k, v in (patch or {}).items():
                if v is SUPPR or k not in necessaires or (p.id, k) in NON_NECESSAIRES:
                    continue
                if TYPES.get(k, {}).get("info"):
                    continue
                for remplacement, lib in ((SUPPR, "vide"), ("Non évalué", "non évalué")):
                    q = TYPES.get(k, {})
                    if lib == "non évalué":
                        if "Non évalué" not in (q.get("options") or []):
                            continue
                        if q.get("type") == "multi":
                            remplacement = ["Non évalué"]
                    yield pytest.param(bloc, bat, fac, local, espace, cible, k, remplacement, id=f"{p.id} · {k} {lib}")


@pytest.mark.parametrize("bloc,bat,fac,local,espace,cible,k,remplacement", list(_cas_manquants()))
def test_donnee_necessaire_manquante(bloc, bat, fac, local, espace, cible, k, remplacement):
    """Méthode § III : « Si une donnée nécessaire à l'établissement d'une règle est inconnue (non évaluée ou
    non renseignée) alors la règle fait passer la solution en statut sous réserve »."""
    kw = {"bat": bat, "fac": fac, "local": local, "espace": espace}
    kw[cible] = dict(kw[cible] or {}, **{k: remplacement})
    d = donnees(**kw)
    regle, statut, manquante, s = evaluer(d, bloc)
    assert statut == SR, (regle, statut)
    from surya.rapport import donnee_manquante
    x = moteur.calculer(d)["espaces" if bloc in ("OA", "PR", "OC") else "locaux"][0]
    assert donnee_manquante(x, s), (regle, statut, manquante)


@pytest.mark.parametrize("cle_mur", ["orientation", "MEX-04", "MEX-06", "MEX-07", "baies"])
def test_donnee_de_mur_manquante(cle_mur):
    """Un mur incomplet laisse au moins une solution de façade « Sous réserve » faute de donnée."""
    m = mur()
    m.pop(cle_mur)
    x = moteur.calculer(donnees(local={"murs": [m]}))["locaux"][0]
    from surya.rapport import donnee_manquante
    touchees = {s["solution"] for s in x["solutions"] if donnee_manquante(x, s)}
    assert touchees, statuts(x)


def test_mex05_manquant_donne_sous_reserve():
    regle, statut, manquante, _ = evaluer(donnees(local={"murs": [mur(MEX_05=SUPPR)]}), "PV")
    assert (regle, statut, manquante) == ("PV-2", SR, True)


def test_facade_non_decrite_donne_sous_reserve():
    """B10 (documenté) : façade du mur non décrite → PV-5 / PH-6 indéterminées."""
    d = donnees(fac={"S": {"F-01": SUPPR}})
    assert evaluer(d, "PV")[:3] == ("PV-5", SR, True)
    assert evaluer(d, "PH")[:3] == ("PH-4", SR, True) or evaluer(d, "PH")[1] == SR


def test_ex_al_indeterminee_n_est_pas_affichee():
    """EX-AL vaut 0,5 quand l'effectif manque : rangée « à vérifier » mais ni déclenchée ni affichée (QM-05,
    PàT F5 : question de méthode)."""
    x = moteur.calculer(donnees(espace={"E-06": SUPPR}))["espaces"][0]
    assert x["EX-AL"] == 0.5
    assert not any("EX-AL" in s["alertes"] for s in x["solutions"])


# ------------------------------------------------------------------ questions masquées
def _cb(d):
    return moteur.etats_batiment(d.get("batiment") or {}, d.get("facades") or {})


def nettoyer_masquees(d: dict) -> dict:
    """Retire toutes les réponses aux questions masquées (point fixe : les conditions s'enchaînent)."""
    import copy
    d = copy.deepcopy(d)
    for _ in range(4):
        b = d.get("batiment") or {}
        cb = _cb(d)
        for s in SECTIONS_BATIMENT:
            for q in s["questions"]:
                if not visible(q["code"], cb, b, cb):
                    b.pop(q["code"], None)
        cb = _cb(d)
        for l in d.get("locaux") or []:
            c = moteur.etats_local(l, cb)
            for s in SECTIONS_LOCAL:
                for q in s["questions"]:
                    if not visible(q["code"], c, l, cb):
                        l.pop(q["code"], None)
            if l.get("aucune_baie"):
                l.pop("murs", None)
            for m in l.get("murs") or []:
                if m.get("MEX-04") not in ("Nu intérieur", "En tunnel"):
                    m.pop("MEX-05", None)
        for e in d.get("espaces") or []:
            c = moteur.etats_espace(e)
            for s in SECTIONS_ESPACE:
                for q in s["questions"]:
                    if not visible(q["code"], c, e, cb):
                        e.pop(q["code"], None)
        for o, f in (d.get("facades") or {}).items():
            if not f.get("F-01"):
                d["facades"][o] = {}
    return d


def _tous_statuts(d):
    res = moteur.calculer(d)
    return [(s["solution"], s["statut"], tuple(s["alertes"])) for x in res["locaux"] + res["espaces"]
            for s in x["solutions"]] + [x.get("EX-AL") for x in res["espaces"]]


MASQUEES = [
    ("BA-05 Présent puis Aucun", {"local": dict(BP, **{"BA-05": "Aucun", "BA-12": 290, "BA-13": 10})}),
    ("B-09 Non avec B-10..B-16 remplis", {"bat": {"B-09": "Non", "B-10": "Double flux", "B-11": "Non", "B-13": "Filtres encrassés"},
                                          "local": {"BA-15": "Non", "BA-18": 10}}),
    ("B-08 Non avec MEX-37 = Oui", {"local": {"MEX-37": "Oui"}}),
    ("MEX-14 Non avec fenêtre de toit remplie", {"local": dict(FENETRE_DE_TOIT, **{"MEX-14": "Non", "MEX-16": "Oui",
                                                                                    "MEX-17": "Manuelle", "MEX-21": "Non"})}),
    ("MEX-29 sans volets avec MEX-30 pleins", {"local": {"MEX-29": ["Persiennes"], "MEX-30": "Non (pleins)"}}),
    ("MEX-32 Aucun avec MEX-33 détérioré", {"local": {"MEX-32": "Aucun", "MEX-33": "État détérioré"}}),
    ("MEX-34 Non avec MEX-35 porte standard", {"local": {"MEX-34": "Non", "MEX-35": "Oui, porte standard"}}),
    ("Nu extérieur avec MEX-05 = 5", {"local": {"murs": [mur(MEX_04="Nu extérieur", MEX_07="Faible", MEX_05=5)]}}),
    ("Aucune baie avec murs remplis", {"local": {"aucune_baie": True, "murs": [mur(MEX_06="Très dégradé, remplacement à envisager")]}}),
    ("PL-01 béton avec PL-02 = 2", {"local": {"PL-02": 2}}),
    ("B-18 pentes avec B-19/B-20", {"bat": {"B-19": "Non isolée", "B-20": 5}, "local": DERNIER}),
    ("B-21 Non avec combles remplis", {"bat": {"B-21": "Non", "B-23": ["Tassée"], "B-27": "Oui"}, "local": DERNIER}),
    ("B-22 sous pente avec B-26/B-28", {"bat": {"B-22": "Sous pente", "B-26": "Non", "B-28": ["Spots encastrés"]}, "local": DERNIER}),
    ("E-02 sans préau avec E-26..E-30", {"espace": {"E-02": ["Cour de récréation"], "E-26": "Fibrociment", "E-30": 3}}),
    ("E-04 sans maternelle avec E-07", {"espace": {"E-07": 9, "E-14": 120}}),
    ("E-10 sans arbres avec E-12 dégradé", {"espace": {"E-10": ["Voiles d'ombrage"], "E-12": "Dégradé", "E-09": "Entre 25 et 50 %"}}),
    ("E-20 Aucune avec E-21..E-25", {"espace": {"E-20": ["Aucune"], "E-21": "Hors service ou dégradée", "E-24": "Aucun possible"}}),
    ("E-02 sans cour avec E-32", {"espace": {"E-02": ["Préau"], "E-32": "Faible épaisseur de terre"}}),
    ("Façade non décrite avec F-03 = Non", {"fac": {"S": {"F-01": SUPPR, "F-03": "Non"}}}),
    ("BA-06 = 1 avec BA-14 = 10", {"local": dict(BP, **{"BA-14": 10})}),
]


@pytest.mark.parametrize("kw", [m[1] for m in MASQUEES], ids=[m[0] for m in MASQUEES])
def test_reponse_masquee_sans_effet(kw):
    d = donnees(**kw)
    assert _tous_statuts(d) == _tous_statuts(nettoyer_masquees(d))


def test_reponses_masquees_sans_effet_tirages():
    """Sur 400 saisies aléatoires : retirer les réponses masquées ne change aucun statut ni alerte."""
    import random
    import fuzz_excel
    rnd = random.Random(11)
    for _ in range(400):
        d = fuzz_excel.tirage(rnd)
        assert _tous_statuts(d) == _tous_statuts(nettoyer_masquees(d))


# ------------------------------------------------------------------ choix multiples contradictoires (B6)
CONTRADICTOIRES = [
    # (question, patch, bloc, résultat observé) — « Aucun » coché avec une autre option : l'option l'emporte
    ("L-10", {"local": {"L-10": ["Aucun", "Copieurs, imprimantes"]}}, "CQ", ("CQ-1", SR)),
    ("MEX-18", {"local": dict(FENETRE_DE_TOIT, **{"MEX-18": ["Aucune", "Store extérieur"], "MEX-19": "Bon état"})}, "FT", ("FT-4", EP)),
    ("MEX-29", {"local": {"MEX-29": ["Aucune", "Volets roulants"], "MEX-30": "Non (pleins)"}}, "VN", ("VN-3", SR)),
    ("MEX-36", {"local": {"MEX-36": ["Aucun", "Grilles"]}}, None, set()),
    ("BA-19", {"local": {"BA-19": ["Aucun", "Baffles acoustiques"]}}, "BS", ("BS-2", SR)),
    ("E-10", {"espace": {"E-10": ["Aucune", "Arbres"], "E-12": "Dégradé"}}, "OC", ("OC-2", AO)),
    ("E-20", {"espace": {"E-20": ["Aucune", "S"]}}, "OA", ("OA-11", SR)),
    ("B-28", {"bat": {"B-28": ["Aucun", "Spots encastrés"]}, "local": DERNIER}, "CP", ("CP-6", SR)),
]


@pytest.mark.parametrize("q,kw,bloc,observe", CONTRADICTOIRES, ids=[c[0] for c in CONTRADICTOIRES])
def test_aucun_coche_avec_une_autre_option(q, kw, bloc, observe):
    """Comportement documenté (B6) : l'option cochée l'emporte sur « Aucun ». Pour E-20, « Aucune »
    masque au contraire E-21 à E-25 (l'ombrage adossé tombe sur OA-11 « Sous réserve » sans donnée
    manquante), alors que la façade S est bien citée : voir ANO-12."""
    d = donnees(**kw)
    if bloc is None:
        assert "VN-AL1" not in {a for s in moteur.calculer(d)["locaux"][0]["solutions"] for a in s["alertes"]}
        return
    regle, statut, manquante, _ = evaluer(d, bloc)
    assert (regle, statut) == observe


# ------------------------------------------------------------------ murs
def test_aucun_mur_decrit():
    x = moteur.calculer(donnees(local={"murs": []}))["locaux"][0]
    for nom in ("Par ventilation naturelle nocturne", "Protections verticales", "Protections horizontales", "Films solaires"):
        s = next(s for s in x["solutions"] if s["solution"] == nom)
        assert s["statut"] == SR and x["blocs"][s["blocs"][0]]["manquante"], nom


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_un_a_quatre_murs(n):
    oris = ["S", "N", "E", "O"][:n]
    regle, statut, _, _ = evaluer(donnees(local={"murs": [mur(orientation=o) for o in oris]}), "VN")
    assert (regle, statut) == (("VN-10", SR) if n == 1 else ("VN-7", R))


def test_cinquieme_mur_ignore():
    """Au-delà de 4 murs (import JSON), le 5e est ignoré sans avertissement."""
    murs = [mur(orientation=o) for o in ("N", "N", "N", "N")] + [mur(orientation="S", MEX_07="Important")]
    regle, statut, _, _ = evaluer(donnees(local={"murs": murs}), "PH")
    assert (regle, statut) == ("PH-3", NR)


def test_aucune_baie_cochee_avec_murs_remplis():
    d1 = donnees(local={"aucune_baie": True, "murs": [mur(MEX_04="Nu extérieur", MEX_06="Très dégradé, remplacement à envisager")]})
    d2 = donnees(local={"aucune_baie": True, "murs": []})
    assert _tous_statuts(d1) == _tous_statuts(d2)
    assert statuts(moteur.calculer(d1)["locaux"][0])["Protections verticales"] == NC


def test_deux_murs_meme_orientation():
    """B1 (documenté) : deux murs « S » suffisent pour VN-7 « Recommandé » (le libellé dit
    « orientations différentes »). L'outil fait comme la formule de l'Excel."""
    regle, statut, _, _ = evaluer(donnees(local={"murs": [mur(), mur()]}), "VN")
    assert (regle, statut) == ("VN-7", R)


def test_mur_sans_orientation_ignore():
    d = donnees(local={"murs": [mur(), mur(orientation=SUPPR, MEX_06="Très dégradé, remplacement à envisager")]})
    assert _tous_statuts(d) == _tous_statuts(donnees())


def test_mur_seul_sans_orientation():
    regle, statut, manquante, _ = evaluer(donnees(local={"murs": [mur(orientation=SUPPR)]}), "PV")
    assert statut == SR and manquante


def test_baies_comptees_ou_non():
    a = _tous_statuts(donnees(local={"murs": [mur(baies={"Fenêtre à la française": "x"})]}))
    b2 = _tous_statuts(donnees(local={"murs": [mur(baies={"Fenêtre à la française": 7})]}))
    assert a == b2


def test_zero_baie_comme_l_excel():
    regle, statut, _, _ = evaluer(donnees(local={"murs": [mur(baies={"Fenêtre à la française": 0})]}), "VN")
    assert (regle, statut) == ("VN-10", SR)  # résultat de l'Excel recalculé


def test_uniquement_fixes_et_uniquement_oscillo():
    assert evaluer(donnees(local={"murs": [mur(baies={"Vitrage fixe": 4})]}), "VN")[:2] == ("VN-2", NR)
    assert evaluer(donnees(local={"murs": [mur(baies={"Fenêtre oscillo-battante": 4})]}), "VN")[:2] == ("VN-6", SR)
    # fixe sur un mur, ouvrant sur l'autre : une seule orientation ouvrante
    m = [mur(baies={"Vitrage fixe": 2}), mur(orientation="N")]
    assert evaluer(donnees(local={"murs": m}), "VN")[:2] == ("VN-10", SR)


# ------------------------------------------------------------------ dépendances croisées
def test_patrimoine_touche_toutes_les_solutions_prevues():
    base = moteur.calculer(donnees(local=dict(FENETRE_DE_TOIT, **{"MEX-15": ["Fenêtre de toit (type Velux)", "Véranda"],
                                                                   "MEX-22": "Oui", "MEX-24": "Oui"})))
    pat = moteur.calculer(donnees(bat={"B-05": "Oui"}, local=dict(FENETRE_DE_TOIT, **{
        "MEX-15": ["Fenêtre de toit (type Velux)", "Véranda"], "MEX-22": "Oui", "MEX-24": "Oui"})))
    regles = {b["regle"] for x in pat["locaux"] + pat["espaces"] for b in x["blocs"].values()}
    assert {"PV-3", "PH-5", "FT-5", "OA-5", "OC-3"} <= regles
    alertes = {a for s in pat["espaces"][0]["solutions"] for a in s["alertes"]}
    assert "PR-AL1" in alertes
    change = {s["solution"] for x0, x1 in zip(base["locaux"] + base["espaces"], pat["locaux"] + pat["espaces"])
              for s0, s in zip(x0["solutions"], x1["solutions"]) if s0["statut"] != s["statut"]}
    assert change == {"Protections verticales", "Protections horizontales", "Sur fenêtres de toiture",
                      "Ombrage rapporté adossé au bâtiment", "Ombrage autoportant ou végétal de la cour"}


def test_facade_ne_touche_que_les_entites_de_meme_orientation():
    loc_s, loc_n = fusion(LOCAL, {"L-01": "S"}), fusion(LOCAL, {"L-01": "N", "murs": [mur(orientation="N")]})
    esp_n = fusion(ESPACE, {"E-20": ["N", "E"]})
    d0 = donnees(locaux=[loc_s, loc_n], espaces=[esp_n])
    d1 = donnees(locaux=[loc_s, loc_n], espaces=[esp_n], fac={"S": {"F-02": "Oui", "F-03": "Non", "F-04": "Oui"}})
    r0, r1 = moteur.calculer(d0), moteur.calculer(d1)
    assert statuts(r0["locaux"][1]) == statuts(r1["locaux"][1])
    assert statuts(r0["espaces"][0]) == statuts(r1["espaces"][0])
    assert statuts(r0["locaux"][0]) != statuts(r1["locaux"][0])


def test_ventilation_batiment_vers_local():
    assert evaluer(donnees(bat={"B-09": "Non"}, local={"BA-15": "Oui"}), "VM")[:2] == ("VM-1", NR)


def test_toiture_ne_concerne_que_le_dernier_niveau():
    d = donnees(bat={"B-18": "Toiture-terrasse", "B-19": "Non isolée"},
                locaux=[fusion(LOCAL, {"L-09": n}) for n in ("Sous-sol", "RDC", "Étage intermédiaire", "Dernier niveau",
                                                              "RDC et dernier niveau (plain-pied)")])
    assert [statuts(x)["Toiture"] for x in moteur.calculer(d)["locaux"]] == [NC, NC, NC, SR, SR]


def test_toiture_cas_non_prevus_b2():
    """B2 (documenté) : toiture à pentes sans combles → « Sous réserve » sans bloc applicable."""
    x = moteur.calculer(donnees(bat={"B-21": "Non"}, local=DERNIER))["locaux"][0]
    s = next(s for s in x["solutions"] if s["solution"] == "Toiture")
    assert s["statut"] == SR and s["blocs"] == []
