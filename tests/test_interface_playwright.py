"""Partie E — interface dans un vrai navigateur (Chromium + Playwright préinstallés, script Node
``interface_playwright.js``). Lance Streamlit sur un port libre, joue les scénarios, puis vérifie les
fichiers réellement téléchargés (PDF, CSV) par rapport au moteur.

Lent (≈ 1 min) : marqueur ``interface``. ``python -m pytest tests -m interface``.
"""
from __future__ import annotations

import copy
import json
import shutil
import socket
import subprocess
import time
import urllib.request

import pytest

import sorties
from cas_base import RACINE, moteur
from surya import questionnaire as QU
from surya.rapport import donnee_manquante

pytestmark = [pytest.mark.interface,
              pytest.mark.skipif(not shutil.which("node") or not shutil.which("streamlit"), reason="node ou streamlit absent")]
EXEMPLE = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))
# Erreurs de console dues à l'environnement de test (pas d'accès réseau pour les statistiques de Streamlit)
BRUIT = ("ERR_TUNNEL_CONNECTION_FAILED", "metrics config", "Failed to fetch", "ERR_NAME_NOT_RESOLVED")


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory):
    out = tmp_path_factory.mktemp("playwright")
    from test_sorties import _trente_locaux
    (out / "trente.json").write_text(json.dumps(_trente_locaux(), ensure_ascii=False), encoding="utf-8")
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    srv = subprocess.Popen(["streamlit", "run", str(RACINE / "app.py"), "--server.headless", "true", "--server.port",
                            str(port), "--browser.gatherUsageStats", "false"], cwd=RACINE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://localhost:{port}"
        for _ in range(60):
            try:
                urllib.request.urlopen(url, timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        subprocess.run(["node", str(RACINE / "tests" / "interface_playwright.js"), url, str(out)], check=True,
                       timeout=900, capture_output=True)
        yield json.loads((out / "resultats.json").read_text()), out
    finally:
        srv.terminate()
        srv.wait(timeout=20)


NOMS = ["complet_pas_a_pas", "resultats_onglets", "telephone", "grand_ecran", "trente_locaux", "questionnaire_usager",
        "imports_invalides"]


@pytest.mark.parametrize("nom", NOMS)
def test_scenario_sans_erreur(scenarios, nom):
    r = scenarios[0][nom]
    assert r["ok"], r.get("erreur")
    assert not r["exceptions"], r["exceptions"]
    assert not r["erreurs_page"], r["erreurs_page"]
    assert not [e for e in r["erreurs_console"] if not any(b in e for b in BRUIT)]


def test_parcours_complet_et_documents_telecharges(scenarios):
    r, out = scenarios
    d = r["complet_pas_a_pas"]["details"]
    assert d["etapes"] == ["Identification de l'audit", "Bâtiment", "Locaux", "Espaces extérieurs", "Façades",
                           "Questionnaires usagers", "Vérification avant les documents", "Documents"]
    pdf = (out / "cr.pdf").read_bytes()
    assert pdf.startswith(b"%PDF") and "Pages:" in sorties.info(pdf)
    lignes = sorties.export_csv(moteur.calculer(EXEMPLE))
    lu = (out / "resultats.csv").read_bytes().decode("utf-8-sig")
    import csv
    import io
    assert list(csv.DictReader(io.StringIO(lu), delimiter=";")) == lignes
    assert "6. Ressenti des usagers" in sorties.texte(pdf)


def test_resultats_onglets(scenarios):
    d = scenarios[0]["resultats_onglets"]["details"]
    assert d["etape6_desactivee"] is True
    assert d["nom_affiche"] >= 1 and d["nom_conserve"] >= 1


def test_telephone_sans_defilement_horizontal(scenarios):
    d = scenarios[0]["telephone"]["details"]
    assert d["debordement_depart"] <= 0 and d["debordement_resultats"] <= 0 and d["debordement_locaux"] <= 0


def test_temps_de_reponse_trente_locaux(scenarios):
    d = scenarios[0]["trente_locaux"]["details"]
    assert d["saisie_ms"] < 3000 and d["ouvrir_local_ms"] < 3000 and d["liste_locaux_ms"] < 5000
    assert d["pdf_cr"]["ms"] < 20000 and d["pdf_res"]["ms"] < 10000


def test_questionnaire_en_ligne_aller_retour(scenarios):
    r, out = scenarios
    d = r["questionnaire_usager"]["details"]
    assert d["q12_visible_avant"] == 0 and d["q12_visible_apres"] == 1
    reps, av = QU.lire_csv((out / "reponse_usager.csv").read_bytes())
    assert not av and len(reps) == 1
    rep = reps[0]
    assert rep["Q4"] == "Chaude" and rep["Q11"] == ["Rideaux"]
    assert rep["Q24"] == "Trop chaud l’après-midi ; « vraiment », merci"
    # import dans l'audit : la réponse est comptée dans la synthèse
    m = QU.matrice(reps, moteur.calculer(EXEMPLE))
    assert m["synthese"]["repondants"] == 1


def test_import_invalide_message_clair(scenarios):
    d = scenarios[0]["imports_invalides"]["details"]
    assert d["message"] and d["message"][0].startswith("Import impossible")


@pytest.mark.xfail(strict=True, reason="ANO-03 : sur téléphone (375 px), les 7 ou 8 boutons d'étapes empilés occupent "
                                       "l'écran : le titre de l'étape commence au-delà de 600 px")
def test_telephone_contenu_visible_sans_defiler(scenarios):
    assert scenarios[0]["telephone"]["details"]["titre_y"] < 400


@pytest.mark.xfail(strict=True, reason="ANO-04 : libellés d'étapes tronqués à 1440 px (« 4. Espaces extér… », "
                                       "« 6. Questionnair… »)")
def test_libelles_d_etapes_lisibles(scenarios):
    assert not scenarios[0]["complet_pas_a_pas"]["details"]["etapes_tronquees"]


@pytest.mark.xfail(strict=True, reason="ANO-05 : le nom accessible des infobulles contient la syntaxe « :gray[· L-01] »")
def test_infobulles_sans_balisage(scenarios):
    assert not scenarios[0]["complet_pas_a_pas"]["details"]["aria_balisage"]
