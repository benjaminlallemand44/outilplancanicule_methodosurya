"""Module « passage en travaux » : opérations, verdict MOE, validation humaine, CCTP et PDF."""
from __future__ import annotations

import copy
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from surya import cctp, rapport_travaux, travaux
from surya.validation import valider

RACINE = Path(__file__).resolve().parent.parent
EXEMPLES = ["exemple.json", "exemple_ecole_sud.json"]


def charger(nom):
    return json.loads((RACINE / "surya" / nom).read_text(encoding="utf-8"))


@pytest.fixture(params=EXEMPLES)
def donnees(request):
    return charger(request.param)


def test_chaque_operation_a_fiche_niveau_horizon_et_pieces(donnees):
    e = travaux.etat(donnees)
    assert e["operations"]
    for o in e["operations"]:
        assert o["fiche"] in travaux.FICHES
        assert o["niveau"] in "ABC" and o["horizon"] in (1, 2, 3)
        assert all(c in travaux.CCTP for c in o["cctp"])
        assert o["a_engager"] or o["a_valider"]
        if o["niveau"] == "C":
            assert o["horizon"] == 3
        if e["moe"] and travaux.est_travaux(o) and o["retenue"]:
            assert o in e["pieces"]["MOE"]["operations"]
        if o["niveau"] == "B":
            assert o["horizon"] >= 2
        if o["cout"]:
            assert 0 <= o["cout"]["bas"] <= o["cout"]["haut"]


def test_toutes_les_solutions_du_moteur_sont_au_catalogue():
    from surya import moteur
    res = moteur.calculer(charger("exemple_ecole_sud.json"))
    noms = {s["solution"] for x in res["locaux"] + res["espaces"] for s in x["solutions"]}
    assert noms <= set(travaux.CATALOGUE)


def test_alerte_moe_impose_le_niveau_c():
    e = travaux.etat(charger("exemple_ecole_sud.json"))
    adosse = next(o for o in e["operations"] if o["solution"] == "Ombrage rapporté adossé au bâtiment")
    assert adosse["niveau"] == "C" and any("OA-AL2" in r for r in adosse["raisons_niveau"])


def test_patrimoine_passe_les_facades_en_niveau_c():
    d = charger("exemple_ecole_sud.json")
    d["batiment"]["B-06"] = "Oui"
    e = travaux.etat(d)
    pv = next(o for o in e["operations"] if o["solution"] == "Protections verticales")
    assert pv["niveau"] == "C" and e["contexte"]["patrimoine"]
    assert any(r.startswith("M4") for r in e["raisons_moe"])


def test_films_proposes_en_repli_quand_les_locaux_sont_proteges():
    e = travaux.etat(charger("exemple_ecole_sud.json"))
    films = next(o for o in e["operations"] if o["solution"] == "Films solaires")
    assert films["retenue"] is False and films["motif"]
    assert not any("Films" in a for a in e["anomalies"])


def test_retrait_sans_motif_est_une_anomalie_et_bloque_la_validation():
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"operations": {"Éclairage": {"retenue": False, "motif": ""}},
                    "validation": {"auditeur": "A", "date_revue": "01/12/2026", "visa": "B", "date_visa": "02/12/2026"}}
    e = travaux.etat(d)
    assert any("sans motif" in a for a in e["anomalies"]) and not e["valide"]
    d["travaux"]["operations"]["Éclairage"]["motif"] = "Déjà programmé en 2027"
    e = travaux.etat(d)
    assert e["valide"] and "Éclairage" not in {o["solution"] for o in e["retenues"]}


def test_moe_oui_vers_non_exige_motif_et_visa():
    d = charger("exemple_ecole_sud.json")
    assert travaux.etat(d)["moe_auto"]
    d["travaux"] = {"moe": {"choix": "non", "motif": ""}}
    e = travaux.etat(d)
    assert not e["moe"]
    assert any("sans motif" in a for a in e["anomalies"]) and any("sans visa" in a for a in e["anomalies"])
    d["travaux"] = {"moe": {"choix": "non", "motif": "Services techniques en capacité"},
                    "validation": {"auditeur": "A", "date_revue": "x", "visa": "B", "date_visa": "y"}}
    assert travaux.etat(d)["valide"]


def test_seuil_moe_modifiable():
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"seuil_moe": 10_000_000}
    assert not any(r.startswith("M5") for r in travaux.etat(d)["raisons_moe"])


def test_feuille_de_route_couvre_chaque_operation_retenue(donnees):
    e = travaux.etat(donnees)
    texte = " ".join(t["quoi"] for t in e["feuille_de_route"])
    for o in e["retenues"]:
        assert o["action"] in texte
    assert e["feuille_de_route"][0]["phase"] == "Décider"
    if e["contexte"]["amiante"]:
        assert "amiante" in texte


def test_choix_exportes_et_reimportes():
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"operations": {"Éclairage": {"retenue": False, "motif": "x"}, "Inconnue": {"retenue": True}},
                    "moe": {"choix": "bizarre"}, "validation": {"visa": "B"}, "seuil_moe": "50000"}
    out, notes = valider(d)
    assert out["travaux"]["operations"] == {"Éclairage": {"retenue": False, "motif": "x"}}
    assert out["travaux"]["moe"]["choix"] == "auto" and out["travaux"]["validation"]["visa"] == "B"
    assert out["travaux"]["seuil_moe"] == 50000 and any("Inconnue" in n for n in notes)


# ------------------------------------------------------------------ CCTP
def test_moteur_de_gabarit():
    g = "A {{x}}\n[SI f]\nB\n[SI g ou h]\nC\n[FIN SI]\n[FIN SI]\n[SI z]\nD\n[FIN SI]\n{{absente}}"
    assert cctp.appliquer(g, {"x": "1"}, {"f", "h"}) == "A 1\nB\nC\n[À COMPLÉTER]\n"
    assert cctp.appliquer(g, {"x": "1"}, set()) == "A 1\n[À COMPLÉTER]\n"


@pytest.mark.parametrize("nom", EXEMPLES)
def test_cctp_remplis_sans_reste_de_gabarit(nom):
    d = charger(nom)
    e = travaux.etat(d)
    for n in range(1, 10):
        t = cctp.remplir(n, d, e)
        assert "{{" not in t and "[SI" not in t and "[FIN SI]" not in t, n
        assert t.startswith(f"# CCTP {n} ")


def test_cctp_blocs_conditionnels_suivent_le_diagnostic():
    d = charger("exemple_ecole_sud.json")
    t1 = cctp.remplir(1, d)
    assert "BR-AL" in t1 and "Dortoir" in t1 and "Salle de motricité" in t1
    assert "Salle de motricité (ouest)) ; remplacement" in t1  # brasseurs existants à remettre en service
    assert "antérieur à juillet 1997" in t1  # bâtiment 1948-1974
    d["batiment"]["B-01"] = "Après 1997"
    assert "antérieur à juillet 1997" not in cctp.remplir(1, d)


def test_dossier_zip_docx():
    d = charger("exemple_ecole_sud.json")
    z = zipfile.ZipFile(io.BytesIO(cctp.dossier(d)))
    noms = z.namelist()
    assert "LISEZMOI.txt" in noms and "3_Travaux_base_pour_la_MOE/CCTP_1.docx" in noms
    from docx import Document
    doc = Document(io.BytesIO(z.read("3_Travaux_base_pour_la_MOE/CCTP_1.docx")))
    assert doc.paragraphs[0].text.startswith("CCTP 1") and doc.tables
    assert "PROJET" in z.read("LISEZMOI.txt").decode()


# ------------------------------------------------------------------ PDF
def test_pdf_plan_action(donnees):
    import pdfplumber
    pdf = rapport_travaux.generer_pdf(donnees)
    assert pdf[:4] == b"%PDF"
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        texte = "\n".join(pg.extract_text() or "" for pg in p.pages)
    assert "Plan d'action" in texte and "PROJET" in texte and "Feuille de route" in texte


def test_pdf_valide_sans_mention_projet():
    import pdfplumber
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"validation": {"auditeur": "A. Auditeur", "date_revue": "01/12/2026", "visa": "C. Mission",
                                   "date_visa": "02/12/2026"}}
    with pdfplumber.open(io.BytesIO(rapport_travaux.generer_pdf(d))) as p:
        texte = "\n".join(pg.extract_text() or "" for pg in p.pages)
    assert "PROJET" not in texte and "C. Mission" in texte


def test_saisie_vide():
    d = {"audit": {}, "batiment": {}, "facades": {}, "locaux": [], "espaces": []}
    e = travaux.etat(d)
    assert e["operations"] == [] and not e["moe"]
    assert rapport_travaux.generer_pdf(d)[:4] == b"%PDF"


def test_cctp_moe_volets_selon_operations():
    d = charger("exemple_ecole_sud.json")
    t = cctp.remplir("MOE", d)
    assert "{{" not in t and "[SI" not in t
    for v in ("façade", "toiture", "espaces extérieurs", "ventilation", "équipements intérieurs"):
        assert f"### Volet {v}" in t  # toutes les opérations de travaux sont confiées, A et B compris
    assert "OA-AL3" in t and "OPC" in t  # alerte feu et plusieurs volets
    assert "Actions conservées par le maître d'ouvrage" in t  # occupation, équipements : sans travaux
    assert "consultation anticipée" in t  # opérations d'horizon 2 réalisables avant l'été
    assert "CCTP 10" in t and "CCTP 13" in t  # intervenants recrutés directement par la collectivité
    # ne garder que l'ombrage de la cour : seul le volet espaces extérieurs reste
    e = travaux.etat(d)
    d["travaux"] = {"operations": {o["id"]: {"retenue": False, "motif": "test"} for o in e["operations"]
                                   if o["solution"] != "Ombrage autoportant ou végétal de la cour"},
                    "moe": {"choix": "oui", "motif": "test"}}
    t2 = cctp.remplir("MOE", d)
    assert "### Volet espaces extérieurs" in t2
    assert all(f"### Volet {v}" not in t2 for v in ("toiture", "façade", "ventilation", "équipements intérieurs"))
    assert "simulation thermique dynamique" not in t2.split("## Article 6")[0].lower()
    z = zipfile.ZipFile(io.BytesIO(cctp.dossier(d)))
    assert "1_Maitrise_d_oeuvre/CCTP_MOE_adaptation.docx" in z.namelist()


def test_pieces_avec_et_sans_maitrise_d_oeuvre():
    d = charger("exemple_ecole_sud.json")
    e = travaux.etat(d)
    assert e["moe"]
    cat = {n: x["categorie"] for n, x in e["pieces"].items()}
    assert cat["MOE"] == "moe" and cat[10] == cat[12] == cat[13] == "prealable"
    assert 11 not in cat and 7 not in cat  # structure et toiture : faits par la maîtrise d'œuvre
    assert all(c == "reference" for n, c in cat.items() if n in (1, 2, 4, 9))
    assert {o["solution"] for o in e["ops_moa"]} == {"Occupation", "Équipements"}
    d["travaux"] = {"moe": {"choix": "non", "motif": "test"}, "validation": {"visa": "X"}}
    e = travaux.etat(d)
    cat = {n: x["categorie"] for n, x in e["pieces"].items()}
    assert "MOE" not in cat and cat[11] == cat[7] == "prealable"
    assert all(c == "travaux" for n, c in cat.items() if n in (1, 2, 4, 9))
    assert any("bureau d'études ou un architecte" in t["quoi"] for t in e["feuille_de_route"])


@pytest.mark.parametrize("n", [10, 11, 12, 13])
def test_cctp_prestations_prealables(n):
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"moe": {"choix": "non", "motif": "test"}}
    t = cctp.remplir(n, d)
    assert "{{" not in t and "[SI" not in t and "[FIN SI]" not in t
    assert "| Opération |" in t  # tableau des opérations qui déclenchent la prestation


def test_accompagnement_ingenierie():
    d = charger("exemple_ecole_sud.json")
    d["travaux"] = {"accompagnement": {"ingenierie": "non"}}
    t, notes = travaux.valider_saisie(d["travaux"])
    assert t["accompagnement"]["ingenierie"] == "non" and not notes
    e = travaux.etat(d)
    assert any("ingénierie du territoire" in x["quoi"] for x in e["feuille_de_route"])


def test_pdf_preprogramme(donnees):
    import pdfplumber
    from surya import rapport_preprogramme
    d = copy.deepcopy(donnees)
    d["travaux"] = {"accompagnement": {"ingenierie": "non"}}
    pdf = rapport_preprogramme.generer_pdf(d)
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        texte = "\n".join(page.extract_text() or "" for page in p.pages)
    for titre in ("L'essentiel", "Ce que nous proposons, et pourquoi", "Local par local",
                  "Comment nous allons le faire", "Les prochaines étapes"):
        assert titre in texte
    assert "PROJET" in texte and "ingénierie du territoire" in texte.replace("\n", " ")
    assert "Niveau C :" not in texte  # mentions internes retirées des résumés de fiches


def test_structures_locales_dans_le_preprogramme():
    import pdfplumber
    from surya import rapport_preprogramme
    d = charger("exemple_ecole_sud.json")
    brut = {"accompagnement": {"ingenierie": "non", "code_postal": "18000", "code_insee": "18033",
                               "commune": "Bourges", "date_recherche": "24/11/2026",
                               "structures": [{"type": "sde", "nom": "SDE 18", "telephone": "02 48 50 85 40",
                                               "courriel": "info@sde18.com", "site": "", "adresse": "Bourges",
                                               "lat": 47.1, "lon": 2.4, "distance_km": 1.2, "a_verifier": False,
                                               "source": "test"},
                                              {"nom": "", "type": "x"}, "pas un dictionnaire"]}}
    t, _ = travaux.valider_saisie(brut)
    assert len(t["accompagnement"]["structures"]) == 1 and t["accompagnement"]["code_insee"] == "18033"
    d["travaux"] = t
    e = travaux.etat(d)
    assert any("Contacter les structures" in x["quoi"] for x in e["feuille_de_route"])
    with pdfplumber.open(io.BytesIO(rapport_preprogramme.generer_pdf(d))) as p:
        texte = "\n".join(page.extract_text() or "" for page in p.pages)
    assert "Les structures à contacter" in texte and "02 48 50 85 40" in texte


def test_aucun_cout_tant_que_la_base_n_existe_pas(donnees):
    """Les ordres de grandeur ont été retirés : aucun montant dans l'état, les PDF ni les CCTP."""
    import pdfplumber
    from surya import rapport_preprogramme
    e = travaux.etat(donnees)
    assert all(o["cout"] is None for o in e["operations"]) and e["total"] == {"bas": 0, "haut": 0}
    assert not any(r.startswith("M5") for r in e["raisons_moe"])  # règle M5 inactive sans base de coûts
    for gen in (rapport_preprogramme.generer_pdf, rapport_travaux.generer_pdf):
        with pdfplumber.open(io.BytesIO(gen(donnees))) as p:
            texte = "\n".join(page.extract_text() or "" for page in p.pages)
        assert "base de données de coûts" in texte.replace("\n", " ")
        # seuls montants admis : seuils de la commande publique
        montants = re.findall(r"\d[\d  ]*\d{3} ?€", texte)
        assert all(m.replace(" ", "").replace(" ", "") in ("100000€", "60000€") for m in montants), montants
    for n in e["cctp"]:
        assert "€" not in cctp.remplir(n, donnees, e).replace("[À COMPLÉTER] € HT", "")


# ------------------------------------------------------------------ diagnostic externe
def test_diagnostic_externe_bretignolles():
    """Diagnostic d'un bureau d'études (hors méthode SURYA) reporté dans la saisie simplifiée : mêmes règles, mêmes documents."""
    import pdfplumber
    from surya import rapport_preprogramme
    d = charger("exemple_diagnostic_externe.json")
    v, notes = valider(d)
    assert not notes and len(v["diagnostic_externe"]["operations"]) == 9
    e = travaux.etat(d)
    sols = {o["solution"] for o in e["operations"]}
    assert {"Création d'une ventilation mécanique", "Rafraîchissement d'un local refuge",
            "Végétalisation et désimperméabilisation de la cour", "Adaptation des usages"} <= sols
    assert e["moe"] and any(r.startswith("M1") for r in e["raisons_moe"])
    assert 10 in e["pieces"]  # bâtiment de 1979 : repérage amiante
    assert {o["solution"] for o in e["ops_moa"]} == {"Adaptation des usages"}  # sans travaux : gardée par la commune
    brasseurs = next(o for o in e["operations"] if o["solution"] == "Mise en place de brasseurs d'air plafonniers")
    assert brasseurs["niveau"] == "B"  # hauteur limite cochée à la saisie
    assert any(c == "Diagnostic" for x in brasseurs["a_engager"] for c, _ in x["vigilances"])
    with pdfplumber.open(io.BytesIO(rapport_preprogramme.generer_pdf(d))) as p:
        texte = " ".join((page.extract_text() or "") for page in p.pages).replace("\n", " ")
    assert "bureau d'études" in texte and "hors de la méthode SURYA" in texte
    assert "pompe à chaleur" in texte and "mode été" not in texte.split("Rafraîchir un local refuge")[1][:400]
    z = zipfile.ZipFile(io.BytesIO(cctp.dossier(d)))
    assert "1_Maitrise_d_oeuvre/CCTP_MOE_adaptation.docx" in z.namelist()
    assert "{{" not in cctp.remplir("MOE", d)


def test_diagnostic_externe_saisie_inconnue_ignoree():
    t, notes = travaux.valider_externe({"source": "BE", "operations": [
        {"solution": "Inconnue"}, {"solution": "Films solaires", "locaux": ["Classe 1", ""], "alertes": ["ZZ", "BR-AL"],
                                   "niveau": "D", "horizon": "2"}]})
    assert len(t["operations"]) == 1 and notes
    op = t["operations"][0]
    assert op["locaux"] == ["Classe 1"] and op["alertes"] == ["BR-AL"] and "niveau" not in op and op["horizon"] == 2
    assert travaux.externe({"diagnostic_externe": {"operations": []}}) is None
