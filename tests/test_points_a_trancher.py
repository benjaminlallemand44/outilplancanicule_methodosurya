"""Vérifie que l'outil se comporte comme l'annonce docs/points_a_trancher.md (sans juger le choix)."""
from __future__ import annotations

from cas_base import DERNIER, SUPPR, donnees, evaluer, moteur, mur, solution
from surya.rapport import TYPES_ALERTE

R, AO, EP, SR, NR, NC = (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE, moteur.SOUS_RESERVE,
                         moteur.NON_RECOMMANDE, moteur.NON_CONCERNE)


def test_a3_debit_non_renseigne_sous_reserve():
    # annoncé « Sous réserve (VM-9) » : le statut est bon, mais la règle retenue est VM-7 (QM-01)
    assert evaluer(donnees(local={"BA-18": SUPPR}), "VM")[1] == SR


def test_b1_deux_murs_meme_orientation():
    assert evaluer(donnees(local={"murs": [mur(), mur()]}), "VN")[:2] == ("VN-7", R)


def test_b2_toiture_sans_bloc():
    for bat in ({"B-21": "Non"}, {"B-18": "Autre", "B-21": "Non"}, {"B-22": "Autre"}):
        x = moteur.calculer(donnees(bat=bat, local=DERNIER))["locaux"][0]
        s = solution(x, "Toiture")
        assert (s["statut"], s["blocs"]) == (SR, [])


def test_b3_terrasse_prioritaire():
    x = moteur.calculer(donnees(bat={"B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": 35}, local=DERNIER))["locaux"][0]
    assert solution(x, "Toiture")["blocs"] == ["TT"]


def test_b4_tt_ca_sans_defaut_et_ca_ignore_b23_b25_b27():
    x = moteur.calculer(donnees(bat={"B-18": "Toiture-terrasse", "B-19": SUPPR}, local=DERNIER))["locaux"][0]
    assert x["blocs"]["TT"]["regle"] == "TT-1" and x["blocs"]["TT"]["manquante"]
    ca = {"B-22": "Sous pente", "B-24": 25}
    a = evaluer(donnees(bat=ca, local=DERNIER), "CA")[:2]
    b = evaluer(donnees(bat=dict(ca, **{"B-23": ["Tassée"], "B-25": "Non", "B-27": "Oui"}), local=DERNIER), "CA")[:2]
    assert a == b == ("CA-3", EP)
    assert evaluer(donnees(bat={"B-24": 29}, local=DERNIER), "CP")[:2] == ("CP-7", R)       # combles : Recommandé
    assert evaluer(donnees(bat=dict(ca, **{"B-24": 19}), local=DERNIER), "CA")[:2] == ("CA-2", SR)  # rampants : SR


def test_b5_fenetre_de_toit_et_veranda_partagent_les_reponses():
    loc = {"MEX-14": "Oui", "MEX-15": ["Fenêtre de toit (type Velux)", "Véranda"], "MEX-16": "Non",
           "MEX-18": ["Store extérieur"], "MEX-19": "Hors service ou dégradée", "MEX-20": "Marque et modèle identifiables",
           "MEX-21": "Oui", "MEX-22": "Oui", "MEX-24": "Oui"}
    x = moteur.calculer(donnees(local=loc))["locaux"][0]
    assert (x["blocs"]["FT"]["regle"], x["blocs"]["VV"]["regle"]) == ("FT-2", "VV-2")


def test_b7_regle_indeterminee_masque_les_suivantes():
    d = donnees(local={"murs": [mur(MEX_07=SUPPR), mur(orientation="SO", MEX_07="Faible")]})
    assert evaluer(d, "PH")[:3] == ("PH-1", SR, True)


def test_b8_nu_exterieur_avec_debord():
    d = donnees(local={"murs": [mur(MEX_04="Nu extérieur", MEX_05=SUPPR, MEX_07="Faible")]})
    assert evaluer(d, "PV")[:2] == ("PV-8", R)


def test_b9_sous_sol_traite_comme_un_etage():
    assert evaluer(donnees(local={"L-09": "Sous-sol"}, fac={"S": {"F-03": "Non"}}), "PV")[:2] == ("PV-5", SR)


def test_b11_mutualisation_sans_rattachement():
    from cas_base import LOCAL, fusion
    rdc = fusion(LOCAL, {"L-09": "RDC", "L-01": "Local d'en face"})
    x = moteur.calculer(donnees(locaux=[rdc]))["espaces"][0]
    assert "OA-AL1" in {a for s in x["solutions"] for a in s["alertes"]}


def test_b12_occupation_et_effectif_adultes():
    assert evaluer(donnees(local={"L-02": "Salle polyvalente", "L-03": 10, "L-04": 50}), "CO")[:2] == ("CO-3", EP)
    # EX-AL divise par E-06, adultes compris : 60 m² pour 70 élèves + 10 adultes → 0,75 < 0,8
    assert moteur.calculer(donnees(espace={"E-14": 60, "E-06": 80}))["espaces"][0]["EX-AL"] == 1


def test_b13_br_al_toujours_et_d1_types():
    x = moteur.calculer(donnees(local={"PL-03": 2.0}))["locaux"][0]
    assert solution(x, "Mise en place de brasseurs d'air plafonniers")["alertes"] == ["BR-AL"]
    assert TYPES_ALERTE == {"BR-AL": "VA", "VN-AL1": "VA", "VN-AL2": "INFO", "FT-AL": "INFO", "VV-AL": "AL",
                            "EX-AL": "INFO", "OA-AL1": "INFO", "OA-AL2": "AL", "OA-AL3": "AL", "PR-AL1": "AL",
                            "PR-AL2": "AL", "PR-AL3": "AL", "PR-AL4": "INFO"}


def test_c4_c6_c7():
    from surya.questions import SECTIONS_LOCAL
    codes = [q["code"] for s in SECTIONS_LOCAL for q in s["questions"]]
    assert "MEX-25b" in codes
    f = {q["code"]: q["options"] for q in moteur.REFERENTIEL["facades"]}
    assert "Non évalué" in f["F-05"] and all("Non évalué" not in f[k] for k in ("F-02", "F-03", "F-04"))
    assert moteur.NB_MURS_MAX == 4
