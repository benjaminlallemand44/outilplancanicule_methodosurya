"""Partie A — comparaison avec l'Excel de référence.

* ``corriger_classeur`` ne modifie que les cellules des écarts documentés A1 à A3
  (docs/points_a_trancher.md) ;
* l'import de l'Excel de référence redonne l'onglet « Résultats », aux écarts documentés près ;
* tests lents (LibreOffice, marqueur ``excel``) : fuzz sur plusieurs graines, et valeurs pile sur
  les seuils recalculées par LibreOffice.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

import openpyxl
import pytest

import fuzz_excel
from cas_base import BRASSEURS_EN_PLACE, donnees, moteur, mur
from surya.import_excel import lire_classeur

REF = fuzz_excel.REF
soffice = pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice absent")


def test_corriger_classeur_ne_touche_que_les_ecarts_documentes():
    warnings.simplefilter("ignore")
    avant, apres = openpyxl.load_workbook(REF), openpyxl.load_workbook(REF)
    fuzz_excel.corriger_classeur(apres)
    modifiees = set()
    for ws in apres.worksheets:
        w0 = avant[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if c.value != w0[c.coordinate].value:
                    modifiees.add((ws.title, c.row))
    autorisees = ({("Calc_Locaux", r) for r in range(26, 38)}            # A1 : murs 2 à 4, MEX-04 à MEX-07
                  | {("Calc_Locaux", r) for r in range(76, 91)}          # A1 : NTYPES, NONFIXE, OSC, AUTRES
                  | {("Calc_Locaux", 15)}                                # A2 : MEX-17
                  | {("Calc_Locaux", 65)}                                # A3 : BA-18
                  | {("Règles_Locaux", 109)})                            # A2 : FT-7
    assert modifiees and modifiees <= autorisees, sorted(modifiees - autorisees)
    assert {t for t, _ in modifiees} == {"Calc_Locaux", "Règles_Locaux"}


def test_import_de_l_excel_de_reference_vs_onglet_resultats():
    """L'onglet « Résultats » de l'Excel (valeurs enregistrées, identiques à un recalcul LibreOffice) diffère du
    moteur sur QUATRE cellules, toutes dues aux corrections A1 et A2 (le recalcul de l'Excel corrigé donne 0
    écart, voir test suivant). points_a_trancher.md n'en annonce qu'une (VN de la Classe CM1) : ANO-28."""
    warnings.simplefilter("ignore")
    d = lire_classeur(REF)
    res = moteur.calculer(d)
    wr = openpyxl.load_workbook(REF, data_only=True)["Résultats"]
    ecarts = []
    for cle, lignes in (("locaux", range(6, 18)), ("espaces", range(22, 25))):
        for i, x in enumerate(res[cle]):
            for s, r in zip(x["solutions"], lignes):
                assert wr.cell(r, 2).value == s["solution"]
                xl = wr.cell(r, 4 + i).value
                if xl != s["statut"]:
                    ecarts.append((x["nom"], s["solution"], xl, s["statut"]))
    assert ecarts == [
        ("Classe CM1 (étage)", "Par ventilation naturelle nocturne", "Sous réserve", "Recommandé"),   # A1 (documenté)
        ("Classe CM1 (étage)", "Protections horizontales", "Sous réserve", "Recommandé"),            # A1 (non annoncé)
        ("Salle de motricité", "Protections horizontales", "Sous réserve", "À optimiser"),           # A1 (non annoncé)
        ("Salle de classe", "Sur fenêtres de toiture", "Recommandé", "Sous réserve"),                 # A2 (non annoncé)
    ]


@pytest.mark.excel
@soffice
def test_exemple_excel_corrige_recalcule_identique():
    assert _recalcul([lire_classeur(REF)]) == [[]]


def test_import_excel_copies_modifiees(tmp_path):
    """Copies modifiées de l'Excel : lignes de saisie modifiées, colonne vide intercalée, nombre en texte."""
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(REF)
    ws = wb["Saisie_Locaux"]
    plan = fuzz_excel.plan_feuille(ws)
    r03 = plan["questions"]["L-03"][0]
    ws.cell(r03, 4).value = "60"            # nombre saisi en texte
    ws.cell(plan["questions"]["L-02"][0], 5).value = "  Classe  "  # espaces autour
    wb.save(tmp_path / "copie.xlsx")
    d = lire_classeur(tmp_path / "copie.xlsx")
    assert d["locaux"][1]["L-02"] == "Classe"
    assert d["locaux"][0]["L-03"] == 60     # converti à l'import (correctif ANO-08)


def test_import_excel_nombre_en_texte_converti(tmp_path):
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(REF)
    ws = wb["Saisie_Locaux"]
    ws.cell(fuzz_excel.plan_feuille(ws)["questions"]["PL-03"][0], 4).value = "2,5"
    wb.save(tmp_path / "copie.xlsx")
    assert lire_classeur(tmp_path / "copie.xlsx")["locaux"][0]["PL-03"] == 2.5


def test_import_excel_reponse_hors_liste_signalee(tmp_path):
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(REF)
    ws = wb["Saisie_Bâtiment"]
    ws.cell(fuzz_excel.plan_feuille(ws, fin=47)["questions"]["B-05"][0], 4).value = "oui"
    wb.save(tmp_path / "copie.xlsx")
    d = lire_classeur(tmp_path / "copie.xlsx")
    x = moteur.calculer(d)["locaux"][0]
    assert x["blocs"]["PV"]["regle"] == "PV-3" or d["batiment"].get("B-05") == "Oui"


def _recalcul(cas):
    warnings.simplefilter("ignore")
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for i, d in enumerate(cas):
            wb = openpyxl.load_workbook(REF)
            fuzz_excel.corriger_classeur(wb)
            fuzz_excel.ecrire(wb, d)
            wb.save(t / f"c{i}.xlsx")
        subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(t / "r"),
                        *[str(t / f"c{i}.xlsx") for i in range(len(cas))]], check=True, capture_output=True, timeout=600)
        return [fuzz_excel.comparer(openpyxl.load_workbook(t / "r" / f"c{i}.xlsx", data_only=True), d)
                for i, d in enumerate(cas)]


BORNES_EXCEL = {
    "BP-3 = 0,15 (2,45 m ; 221 cm ; Ø 160)": donnees(local=dict(BRASSEURS_EN_PLACE, **{"PL-03": 2.45, "BA-12": 221,
                                                                                         "BA-09": 160, "BA-13": 300})),
    "équation 1 = 0,4 (2 × Ø 140 ; 49 m²)": donnees(local=dict(BRASSEURS_EN_PLACE, **{"BA-09": 140, "L-03": 49, "BA-06": 2,
                                                                                       "BA-14": 500, "BA-13": 300})),
    "2 vol/h (243 m³/h ; 45 m² × 2,70 m)": donnees(local={"BA-18": 243, "L-03": 45, "PL-03": 2.7}),
    "EX-AL 0,8 m²/enfant (22,4 m² ; 28)": donnees(espace={"E-14": 22.4, "E-06": 28}),
    "baies : nombre 0": donnees(local={"murs": [mur(baies={"Fenêtre à la française": 0}), mur(orientation="N")]}),
}


@pytest.mark.excel
@soffice
def test_bornes_recalculees_par_libreoffice():
    ecarts = _recalcul(list(BORNES_EXCEL.values()))
    assert not any(ecarts), dict(zip(BORNES_EXCEL, ecarts))


@pytest.mark.excel
@soffice
@pytest.mark.parametrize("graine", [11, 12])
def test_fuzz_excel(graine):
    """Version courte du fuzz (10 tirages par graine). Campagne complète : python tests/fuzz_excel.py 40 <graine>."""
    assert fuzz_excel.main(10, graine) == 0
