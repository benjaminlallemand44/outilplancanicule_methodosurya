"""Campagne de tests n° 2 (26/11/2026, version de ``main`` 15fd69d) : anomalies nouvelles.

Chaque anomalie ``C2-xx`` de ``docs/rapport_tests_2.md`` a ici un test qui la reproduit (``xfail``
strict tant qu'elle n'est pas corrigée), plus les vérifications de non-régression propres à la
campagne (corrections annoncées dans ``docs/suivi_corrections.md``).
"""
from __future__ import annotations

import copy
import io
import json
import random

import pytest
from PIL import Image

import fuzz_excel
from cas_base import BATIMENT, LOCAL, RACINE, SUPPR, donnees, evaluer, fusion, moteur, mur
from surya import photos as PH
from surya import travaux
from surya.import_excel import importer
from surya.rapport import generer_pdf
from surya.validation import valider

ECOLE = json.loads((RACINE / "surya" / "exemple_ecole_sud.json").read_text(encoding="utf-8"))
R, AO, EP, SR, NR = moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE, moteur.SOUS_RESERVE, moteur.NON_RECOMMANDE


def jpeg(l=64, h=48):
    b = io.BytesIO()
    Image.new("RGB", (l, h), "#0a17a6").save(b, "JPEG")
    return b.getvalue()


# ------------------------------------------------------------------ photos
@pytest.mark.xfail(strict=True, reason="C2-02 : une image de plus de 179 mégapixels lève DecompressionBombError, "
                                       "que l'interface ne rattrape pas (seule ValueError l'est) : plantage")
def test_image_geante_refusee_proprement():
    img = Image.new("1", (20000, 10000))
    b = io.BytesIO()
    img.save(b, "PNG")  # 0,6 Mo seulement
    with pytest.raises(ValueError):
        PH.preparer(b.getvalue())


def test_photos_formats_et_fichiers_invalides():
    for contenu in (b"", b"GIF89a", b"%PDF-1.4", jpeg()[:200]):
        with pytest.raises(ValueError):
            PH.preparer(contenu)
    j, infos = PH.preparer(jpeg(3000, 2000))
    assert max(infos["largeur"], infos["hauteur"]) == PH.COTE_MAX and j[:2] == b"\xff\xd8"


def test_zip_aller_retour_et_archives_invalides():
    d = copy.deepcopy(ECOLE)
    j, infos = PH.preparer(jpeg())
    ph = PH.nouvelle("batiment", infos, "Façade")
    d["photos"] = [ph]
    brut, contenus = PH.lire_zip(PH.exporter_zip(d, {ph["id"]: j}))
    assert brut == d and contenus == {ph["id"]: j}
    for mauvais in (b"", b"PK\x03\x04 pas un zip", PH.exporter_zip({}, {})[:30]):
        with pytest.raises(ValueError):
            PH.lire_zip(mauvais)


# ------------------------------------------------------------------ import : bloc « audit » non contrôlé
@pytest.mark.xfail(strict=True, reason="C2-03 : le bloc « audit » d'un JSON importé n'est pas contrôlé : "
                                       "« audit »: \"texte\" passe l'import puis fait planter le compte rendu "
                                       "(et l'étape Identification)")
def test_import_bloc_audit_invalide():
    d, notes = importer("x.json", json.dumps({"locaux": [{}], "audit": "École A"}).encode())
    generer_pdf(d)


# ------------------------------------------------------------------ passage en travaux
def test_repérage_amiante_propose_avant_1997():
    d = copy.deepcopy(ECOLE)
    d["batiment"]["B-01"] = "De 1948 à 1974"
    e = travaux.etat(d)
    assert any(travaux.est_travaux(o) for o in e["retenues"]) and 10 in e["pieces"]


@pytest.mark.xfail(strict=True, reason="C2-04 : période de construction inconnue (B-01 vide ou « Non renseigné ») : "
                                       "le repérage amiante avant travaux (CCTP 10) n'est pas proposé, alors que PR-AL3 "
                                       "traite ce cas comme une suspicion d'amiante")
@pytest.mark.parametrize("b01", [SUPPR, "Non renseigné"])
def test_reperage_amiante_si_periode_inconnue(b01):
    d = copy.deepcopy(ECOLE)
    if b01 is SUPPR:
        d["batiment"].pop("B-01", None)
    else:
        d["batiment"]["B-01"] = b01
    e = travaux.etat(d)
    assert any(travaux.est_travaux(o) for o in e["retenues"])
    assert 10 in e["pieces"]


# ------------------------------------------------------------------ Supabase : ouverture d'un audit
@pytest.mark.xfail(strict=True, reason="C2-01 : si une photo ne peut pas être téléchargée à l'ouverture d'un audit "
                                       "(coupure réseau, erreur du stockage), sa description est retirée puis "
                                       "l'audit est réenregistré aussitôt : la photo disparaît définitivement de l'audit")
def test_ouvrir_un_audit_ne_perd_pas_les_photos_si_le_telechargement_echoue(monkeypatch):
    from faux_supabase import FauxSupabase, Reponse
    from surya import supabase as SB
    from test_supabase import app_connectee
    serveur = FauxSupabase()
    monkeypatch.setattr(SB.requests, "Session", lambda: serveur)
    at = app_connectee(serveur)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    j, infos = PH.preparer(jpeg())
    ph = PH.nouvelle("batiment", infos, "Façade")
    at.session_state["donnees"]["photos"].append(ph)
    at.session_state["photos_bin"] = {ph["id"]: j}
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()
    assert serveur.audits[0]["donnees"]["photos"][0]["id"] == ph["id"]
    # le stockage répond en erreur pendant l'ouverture
    origine = serveur._stockage
    serveur._stockage = lambda m, c, *a: Reponse(503, {"message": "indisponible"}) if m == "GET" else origine(m, c, *a)
    at2 = app_connectee(serveur)
    next(b for b in at2.button if b.key == f"ouvrir:{serveur.audits[0]['id']}").click().run()
    assert [p["id"] for p in serveur.audits[0]["donnees"]["photos"]] == [ph["id"]]


# ------------------------------------------------------------------ lecture par IA
@pytest.mark.xfail(strict=True, reason="C2-08 : une réponse de l'IA non conforme au schéma (bloc « ecole » ou « locaux » "
                                       "d'un mauvais type) fait lever une exception à vers_saisie, que l'interface ne "
                                       "rattrape pas (seule LectureImpossible l'est)")
@pytest.mark.parametrize("proposition", [
    {"ecole": "Groupe scolaire", "operations": []},
    {"operations": [{"solution": "Films solaires", "extrait": "x", "locaux": "Classe A"},
                    {"solution": "Films solaires", "extrait": "y", "locaux": ["Classe B"]}]},
], ids=["ecole texte", "locaux texte en double"])
def test_lecture_ia_reponse_non_conforme(proposition):
    from surya import lecture_ia as IA
    saisie, remarques = IA.vers_saisie(proposition, "rapport.pdf")
    travaux.etat(saisie)


def test_lecture_ia_reponse_conforme():
    from surya import lecture_ia as IA
    p = {"ecole": {"etablissement": "École A", "commune": "Tours"}, "batiment": {"B-01": "Avant 1948", "B-03": "Bois"},
         "operations": [{"solution": "Films solaires", "extrait": "poser des films", "locaux": ["CM1"], "page": 4},
                        {"solution": "Inventée", "extrait": "x"},
                        {"solution": "Films solaires", "extrait": "y", "locaux": ["CM2"]}],
         "hors_catalogue": [{"intitule": "Peindre la cour en blanc", "page": 7}]}
    s, rem = IA.vers_saisie(p, "r.pdf")
    assert s["batiment"] == {"B-01": "Avant 1948"}  # B-03 hors des champs lus, ignoré
    ops = s["diagnostic_externe"]["operations"]
    assert len(ops) == 1 and ops[0]["locaux"] == ["CM1", "CM2"] and ops[0]["origine"] == "ia"
    assert any("Inventée" in r for r in rem) and any("Peindre la cour" in r for r in rem)
    e = travaux.etat(s)
    assert [o["solution"] for o in e["operations"]] == ["Films solaires"]


# ------------------------------------------------------------------ cohérence compte rendu / pré-programme
def _ecarts_d_etape(d):
    out = []
    for o in travaux.etat(d)["operations"]:
        etape_cr = min(e["phase"] for e in o["a_engager"] + o["a_valider"])
        if etape_cr != o["horizon"]:
            out.append((o["solution"], etape_cr, o["horizon"], o["niveau"]))
    return out


@pytest.mark.xfail(strict=True, reason="C2-05 : une même action est placée à l'étape 1 « Dès maintenant » dans le "
                                       "compte rendu et à l'horizon 2 ou 3 dans le pré-programme (ex. brasseurs à "
                                       "remettre en service sous faux plafond, casquettes à réparer)")
def test_meme_etape_dans_le_compte_rendu_et_le_pre_programme():
    d = donnees(local=dict(**{"BA-05": "Présent, hors service", "BA-06": 1, "BA-09": 120,
                                                 "PL-01": "Faux plafond démontable (dalles sur ossature)", "PL-02": 0.3}))
    assert not _ecarts_d_etape(d)


def test_ecarts_d_etape_frequents_sur_tirages():
    """Mesure (pas un défaut à elle seule) : fréquence des écarts sur 150 saisies aléatoires."""
    n = sum(bool(_ecarts_d_etape(fuzz_excel.tirage(random.Random(k)))) for k in range(150))
    assert n > 50


@pytest.mark.xfail(strict=True, reason="C2-11 : la surface d'ombre à créer (quantité de l'opération « ombrage de la "
                                       "cour ») utilise 0,8 m²/enfant, 100 / 150 m² et 6 classes écrits en dur, sans "
                                       "suivre les seuils modifiés dans les Réglages")
def test_quantite_ombrage_suit_les_seuils():
    from cas_base import ESPACE
    base = donnees(espace={"E-09": "0 %", "E-14": 20, "E-06": 100})
    q0 = next(o["quantite"] for o in travaux.operations(base) if o["solution"] == "Ombrage autoportant ou végétal de la cour")
    mod = dict(base, parametres={"P_OMBRE_ELEM": 1.0})
    q1 = next(o["quantite"] for o in travaux.operations(mod) if o["solution"] == "Ombrage autoportant ou végétal de la cour")
    assert q1 > q0


# ------------------------------------------------------------------ sécurité et maintenance
@pytest.mark.xfail(strict=True, reason="C2-06 : la fonction de purge (supabase/functions/purge-conservation) ne "
                                       "vérifie pas l'appelant : n'importe qui muni de la clé publique peut la déclencher")
def test_purge_reservee_a_la_tache_planifiee():
    src = (RACINE / "supabase" / "functions" / "purge-conservation" / "index.ts").read_text(encoding="utf-8")
    assert "req.headers" in src or "request.headers" in src


@pytest.mark.xfail(strict=True, reason="C2-07 : l'identifiant d'une photo importée n'est pas contrôlé ; il sert "
                                       "pourtant de nom de fichier dans le stockage et dans l'archive ZIP")
def test_identifiant_de_photo_controle():
    notes = []
    out = PH.valider([{"id": "../../autre-audit/x", "cible": "batiment"}], notes)
    assert not out or all(c.isalnum() for c in out[0]["id"])


@pytest.mark.xfail(strict=True, reason="C2-09 : st.components.v1.html, utilisé par l'app, est annoncé supprimé après "
                                       "le 01/06/2026 (avertissement de Streamlit à chaque page) : une mise à jour de "
                                       "Streamlit cassera le retour en haut de page")
def test_pas_d_api_streamlit_obsolete():
    assert "components.html(" not in (RACINE / "app.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ interface
@pytest.mark.xfail(strict=True, reason="C2-10 : dans « Passer à l'action » à partir de l'audit en cours, les étapes "
                                       "2 et 3 sont cochées « ✓ » avant d'avoir été vues")
def test_etapes_non_vues_non_cochees():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=120).run()
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    next(b for b in at.button if b.label == "À partir de l'audit en cours").click().run()
    assert not at.exception
    nav = [b.label for b in at.button if (b.key or "").startswith("nav:")]
    assert not any(l.startswith("✓") for l in nav[1:]), nav


# ------------------------------------------------------------------ floutage des visages (photo réelle)
PORTRAIT = RACINE / "tests" / "donnees" / "portrait_nasa.jpg"


def _photo_de_classe(taille_visage: int) -> bytes:
    fond = Image.new("RGB", (4000, 3000), "#888888")  # photo de téléphone 12 Mpx
    fond.paste(Image.open(PORTRAIT).resize((taille_visage, taille_visage)), (1800, 1400))
    b = io.BytesIO()
    fond.save(b, "JPEG")
    return b.getvalue()


def test_visage_detecte_et_floute_sur_un_vrai_portrait():
    j, infos = PH.preparer(PORTRAIT.read_bytes())
    assert infos["visages_floutes"] == 1
    j, infos = PH.preparer(_photo_de_classe(200))
    assert infos["visages_floutes"] == 1


@pytest.mark.xfail(strict=True, reason="C2-12 : la détection des visages est faite après réduction à 1 600 px : un "
                                       "visage de 90 à 120 px dans une photo de 4 000 px (élève au fond d'une classe) "
                                       "n'est plus détecté, donc pas flouté, alors qu'il l'est sur l'image d'origine")
@pytest.mark.parametrize("taille", [120, 90])
def test_petit_visage_floute(taille):
    contenu = _photo_de_classe(taille)
    assert len(PH.detecter_visages(Image.open(io.BytesIO(contenu)))) == 1  # détecté à pleine résolution
    assert PH.preparer(contenu)[1]["visages_floutes"] == 1


# ------------------------------------------------------------------ navigateur réel (lent)
@pytest.mark.interface
def test_nouveautes_dans_le_navigateur(tmp_path):
    """3ᵉ parcours sur téléphone (375 px) ; photo avec visage, export ZIP et réimport (1 440 px)."""
    import shutil
    import socket
    import subprocess
    import time
    import urllib.request
    if not shutil.which("node"):
        pytest.skip("node absent")
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    srv = subprocess.Popen(["streamlit", "run", str(RACINE / "app.py"), "--server.headless", "true", "--server.port",
                            str(port), "--browser.gatherUsageStats", "false"], cwd=RACINE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        subprocess.run(["node", str(RACINE / "tests" / "interface_playwright_c2.js"), f"http://localhost:{port}",
                        str(tmp_path), str(PORTRAIT)], check=True, timeout=900, capture_output=True)
    finally:
        srv.terminate()
        srv.wait(timeout=20)
    r = json.loads((tmp_path / "resultats_c2.json").read_text())
    bruit = ("ERR_TUNNEL_CONNECTION_FAILED", "metrics config", "Failed to fetch", "ERR_NAME_NOT_RESOLVED")
    for nom, x in r.items():
        assert x["ok"], (nom, x.get("erreur"))
        assert not x["exceptions"] and not x["erreurs_page"], nom
        assert not [e for e in x["erreurs_console"] if not any(b in e for b in bruit)], nom
    etapes = r["travaux_telephone"]["details"]["etapes"]
    assert [e["titre"] for e in etapes] == ["Pré-programme", "Accompagnement", "Mise en œuvre", "Consultations"]
    assert all(e["debord"] <= 0 for e in etapes)
    assert "1 visage(s) flouté(s)" in " ".join(r["photos_zip"]["details"]["messages"])
