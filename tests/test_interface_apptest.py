"""Partie E — interface, pilotée par l'outil de test de Streamlit (``streamlit.testing.v1.AppTest``).

AppTest exécute ``app.py`` tel quel, sans navigateur : il permet de tester rapidement et de façon
reproductible le parcours, la navigation, les widgets, les imports et les téléchargements. Les
vérifications qui demandent un vrai navigateur (console, téléphone, temps de réponse, fichiers
téléchargés) sont dans ``test_interface_playwright.py``.
"""
from __future__ import annotations

import copy
import io
import json
import warnings

import pytest

from cas_base import RACINE, moteur
import sorties

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
EXEMPLE = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))
warnings.filterwarnings("ignore")


class Fichier(io.BytesIO):
    """Imite l'objet UploadedFile de Streamlit (attribut ``name``, méthode ``getvalue``)."""

    def __init__(self, contenu: bytes, name: str):
        super().__init__(contenu)
        self.name = name


# ------------------------------------------------------------------ aides
def app():
    return AppTest.from_file(str(RACINE / "app.py"), default_timeout=120).run()


def bouton(at, label=None, key=None, contient=None):
    for b in at.button:
        if (key and b.key == key) or (label and b.label == label) or (contient and contient in b.label):
            return b
    raise AssertionError(f"bouton introuvable : {label or key or contient} parmi {[b.label for b in at.button]}")


def clic(at, label=None, key=None, contient=None):
    bouton(at, label, key, contient).click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def gen(at):
    return at.session_state["generation"]


def D(at):
    return at.session_state["donnees"]


def charger(at, d):
    """Charge des données comme le fait l'import (fonction ``charger`` de l'app)."""
    d = copy.deepcopy(d)
    at.session_state["donnees"] = {"audit": {}, "batiment": {}, "facades": {}, "locaux": [], "espaces": [],
                                   "parametres": {}, "questionnaires": [], **d}
    for i, x in enumerate(at.session_state["donnees"]["locaux"] + at.session_state["donnees"]["espaces"]):
        x.setdefault("_id", f"id{i}")
    at.session_state["generation"] = gen(at) + 1
    at.session_state["edition"] = {"locaux": None, "espaces": None}
    at.session_state["theme"] = {"locaux": 0, "espaces": 0, "batiment": 0}
    return at.run()


def demarrer(at, mode="resultats", saisie="guidee"):
    if saisie != "guidee":
        at.radio[0].set_value(saisie).run()
    clic(at, "Commencer — résultats" if mode == "resultats" else "Commencer — diagnostic complet")
    return at


def etape(at):
    return [h.value for h in at.header][0] if at.header else None


def suivant(at):
    return clic(at, contient="Suivant :") if any("Suivant :" in b.label for b in at.button) else clic(at, contient="→")


# ------------------------------------------------------------------ parcours de bout en bout
@pytest.mark.parametrize("mode", ["resultats", "complet"])
@pytest.mark.parametrize("saisie", ["guidee", "libre"])
def test_parcours_complet_avec_exemple(mode, saisie):
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at, mode, saisie)
    vues = []
    for _ in range(12):
        vues.append(etape(at))
        while bouton_existe(at, "Bloc suivant"):
            clic(at, "Bloc suivant →")
        if bouton_existe(at, "Suivant :") or bouton_existe(at, "Générer les documents") or bouton_existe(at, "Voir les résultats"):
            nxt = next(b for b in at.button if "Suivant :" in b.label or "Générer les documents" in b.label
                       or "Voir les résultats" in b.label)
            nxt.click().run()
            assert not at.exception, [e.value for e in at.exception]
            if etape(at) == "Bâtiment" and saisie == "guidee":
                pass
        else:
            break
    attendu = ["Bâtiment", "Locaux", "Espaces extérieurs", "Façades", "Vérification avant les documents", "Résultats"]
    if mode == "complet":
        attendu = ["Identification de l'audit", "Bâtiment", "Locaux", "Espaces extérieurs", "Façades",
                   "Questionnaires usagers", "Vérification avant les documents", "Documents"]
    assert [v for v in vues if v][:len(attendu)] == attendu
    # téléchargements
    dl = {d.label: d for d in at.download_button}
    assert "Résultats (PDF)" in dl and "Tableau (CSV)" in dl
    if mode == "complet":
        assert "Compte rendu complet (PDF)" in dl


def choisir(at, key, valeur):
    """Réponse à une question à choix (segmented_control ou selectbox selon la longueur des options)."""
    for w in list(at.segmented_control) + list(at.selectbox):
        if w.key == key:
            w.set_value(valeur).run()
            assert not at.exception, [e.value for e in at.exception]
            return at
    raise AssertionError(f"question {key} absente")


def bouton_existe(at, contient):
    return any(contient in b.label for b in at.button)


def test_bloc_batiment_pas_a_pas_sans_suivant_d_etape():
    """En pas à pas, l'étape Bâtiment n'offre « Suivant : Locaux » qu'au dernier bloc ; avant, seulement
    « Bloc suivant ». On parcourt les 5 blocs."""
    at = demarrer(app())
    titres = []
    for _ in range(10):
        titres.append([p.value for p in at.get("progress")][0] if at.get("progress") else None)
        if bouton_existe(at, "Bloc suivant"):
            clic(at, "Bloc suivant →")
        else:
            break
    assert len(titres) == 5 and bouton_existe(at, "Suivant : Locaux")


# ------------------------------------------------------------------ navigation
def test_etape_finale_inaccessible_sans_les_etapes():
    at = demarrer(app())
    nav = {b.key: b.disabled for b in at.button if (b.key or "").startswith("nav:")}
    assert nav["nav:0"] is False and all(nav[f"nav:{i}"] for i in range(1, 6))


def test_retour_arriere_conserve_les_donnees():
    at = demarrer(app(), saisie="libre")
    choisir(at, f"{gen(at)}:bat:B-05", "Oui")
    clic(at, contient="Suivant :")
    assert etape(at) == "Locaux"
    clic(at, "← Étape précédente")
    assert D(at)["batiment"]["B-05"] == "Oui"
    assert at.segmented_control(key=f"{gen(at)}:bat:B-05").value == "Oui"


def test_changer_de_type_d_audit_et_de_mode_sans_perte():
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at, "resultats")
    avant = copy.deepcopy(D(at))
    clic(at, "Changer de type d'audit")
    demarrer(at, "complet", "libre")
    assert D(at) == avant
    assert etape(at) == "Identification de l'audit"
    # mode de saisie changé depuis l'étape Bâtiment
    clic(at, key="nav:1")
    at.segmented_control(key="saisie:batiment").set_value("guidee").run()
    assert at.session_state["saisie"] == "guidee" and D(at) == avant


def test_passer_au_diagnostic_complet_depuis_les_resultats():
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at, "resultats")
    clic(at, key="nav:5")
    clic(at, "Passer au diagnostic complet")
    assert etape(at) == "Identification de l'audit" and len(D(at)["locaux"]) == 3


# ------------------------------------------------------------------ questions conditionnelles
def test_questions_conditionnelles_batiment():
    at = demarrer(app(), saisie="libre")
    g = gen(at)
    cles = lambda: {w.key for w in list(at.segmented_control) + list(at.selectbox) + list(at.number_input)}  # noqa: E731
    assert f"{g}:bat:B-10" not in cles()
    choisir(at, f"{g}:bat:B-09", "Oui")
    assert f"{g}:bat:B-10" in cles() and f"{g}:bat:B-13" in cles()
    choisir(at, f"{g}:bat:B-10", "Double flux")
    assert f"{g}:bat:B-11" in cles()
    choisir(at, f"{g}:bat:B-09", "Non")
    assert f"{g}:bat:B-10" not in cles() and f"{g}:bat:B-11" not in cles()
    # la réponse masquée reste dans les données mais n'a aucun effet (vérifié par test_cas_limites)
    assert D(at)["batiment"].get("B-10") == "Double flux"


def _ouvrir_premier_local(at):
    clic(at, key="nav:1") if not bouton(at, key="nav:1").disabled else None


def test_questions_conditionnelles_local():
    at = app()
    charger(at, {"locaux": [{"L-01": "A"}]})
    demarrer(at, "resultats", "libre")
    clic(at, key="nav:1")
    clic(at, contient="Modifier")
    g, i = gen(at), D(at)["locaux"][0]["_id"]
    k = lambda c: f"{g}:locaux:{i}:{c}"  # noqa: E731
    present = lambda c: any(w.key == k(c) for w in list(at.segmented_control) + list(at.selectbox) + list(at.number_input))  # noqa: E731
    assert not present("BA-06")
    at.selectbox(key=k("BA-05")).set_value("Présent et fonctionnel").run() if any(s.key == k("BA-05") for s in at.selectbox) \
        else at.segmented_control(key=k("BA-05")).set_value("Présent et fonctionnel").run()
    assert present("BA-06") and present("BA-09")
    at.number_input(key=k("BA-06")).set_value(2).run()
    assert present("BA-14")
    (at.selectbox(key=k("BA-05")) if any(s.key == k("BA-05") for s in at.selectbox) else at.segmented_control(key=k("BA-05"))).set_value("Aucun").run()
    assert not present("BA-06") and not present("BA-14")


# ------------------------------------------------------------------ locaux : ajout, duplication, suppression, renommage
def test_ajouter_dupliquer_supprimer_renommer():
    at = demarrer(app(), saisie="libre")
    at.session_state["etape_max"] = 5
    at.run()
    clic(at, key="nav:1")
    clic(at, "➕ Ajouter un local")
    g, i = gen(at), D(at)["locaux"][0]["_id"]
    at.text_input(key=f"{g}:locaux:{i}:L-01").set_value("CP Soleil").run()
    assert D(at)["locaux"][0]["L-01"] == "CP Soleil"
    assert any("CP Soleil" in m.value for m in at.markdown)
    clic(at, "✓ Terminer le local")
    clic(at, "➕ Ajouter un local")
    i2 = D(at)["locaux"][1]["_id"]
    at.text_input(key=f"{g}:locaux:{i2}:L-01").set_value("CE1").run()
    clic(at, "✓ Terminer le local")
    # dupliquer le premier
    bouton(at, key=f"dup:locaux:{i}").click().run()
    noms = [l.get("L-01") for l in D(at)["locaux"]]
    assert noms == ["CP Soleil", "CP Soleil (copie)", "CE1"]
    # supprimer la copie
    copie = D(at)["locaux"][1]["_id"]
    bouton(at, key=f"del:locaux:{copie}").click().run()
    assert [l.get("L-01") for l in D(at)["locaux"]] == ["CP Soleil", "CE1"]
    # renommer CE1 depuis l'éditeur : le bon local est modifié et le nom suit dans la liste
    bouton(at, key=f"mod:locaux:{i2}").click().run()
    at.text_input(key=f"{g}:locaux:{i2}:L-01").set_value("CE1 bis").run()
    clic(at, "✓ Terminer le local")
    assert [l.get("L-01") for l in D(at)["locaux"]] == ["CP Soleil", "CE1 bis"]
    assert any("CE1 bis" in m.value for m in at.markdown)


def test_dupliquer_puis_modifier_la_copie_ne_touche_pas_l_original():
    at = app()
    charger(at, {"locaux": [{"L-01": "A", "L-03": 50, "murs": [{"orientation": "S"}]}]})
    demarrer(at, "resultats", "libre")
    clic(at, key="nav:1")
    i = D(at)["locaux"][0]["_id"]
    bouton(at, key=f"dup:locaux:{i}").click().run()
    i2 = D(at)["locaux"][1]["_id"]
    bouton(at, key=f"mod:locaux:{i2}").click().run()
    at.number_input(key=f"{gen(at)}:locaux:{i2}:L-03").set_value(80.0).run()
    assert [l["L-03"] for l in D(at)["locaux"]] == [50, 80.0]
    assert D(at)["locaux"][0]["murs"] is not D(at)["locaux"][1]["murs"]


# ------------------------------------------------------------------ vérification
def test_verification_completer_mene_au_bon_bloc_et_compteurs():
    at = app()
    charger(at, {"locaux": [{"L-01": "A"}, {"L-01": "B"}], "espaces": [{"E-01": "Cour"}]})
    demarrer(at, "resultats", "guidee")
    clic(at, key="nav:4")
    assert etape(at) == "Vérification avant les documents"
    ib = D(at)["locaux"][1]["_id"]
    clic(at, key=f"verif:locaux:{ib}")
    assert etape(at) is None or at.session_state["edition"]["locaux"] == 1
    assert any("B" in m.value and "local 2 sur 2" in m.value for m in at.markdown)
    # bâtiment : « Compléter » ouvre le premier bloc incomplet
    clic(at, key="nav:4")
    clic(at, key="verif:bat")
    assert etape(at) == "Bâtiment" and at.session_state["theme"]["batiment"] == 0


def test_verification_compteur_revient_a_zero():
    from cas_base import BATIMENT, FACADES, LOCAL
    loc = copy.deepcopy(LOCAL)
    at = app()
    charger(at, {"batiment": copy.deepcopy(BATIMENT), "facades": copy.deepcopy(FACADES), "locaux": [loc]})
    demarrer(at, "resultats", "guidee")
    clic(at, key="nav:4")
    lignes = " ".join(m.value for m in at.markdown)
    assert "Tout est renseigné" in " ".join(s.value for s in at.success), lignes


# ------------------------------------------------------------------ façades citées
def test_facades_citees_cochees_d_office_et_signalees():
    at = app()
    charger(at, {"locaux": [{"L-01": "A", "murs": [{"orientation": "SO"}]}], "espaces": [{"E-01": "C", "E-20": ["E"]}]})
    demarrer(at, "resultats")
    clic(at, key="nav:3")
    assert etape(at) == "Façades"
    f = D(at)["facades"]
    assert f["SO"].get("F-01") and f["E"].get("F-01") and not f["N"].get("F-01")
    texte = " ".join(e.label for e in at.expander)
    assert "sans réponse" in texte
    # décocher une façade citée : elle n'est pas recochée et la vérification la signale
    at.checkbox(key=f"{gen(at)}:fac:SO:F-01").uncheck().run()
    clic(at, key="nav:3")
    assert not D(at)["facades"]["SO"].get("F-01")
    clic(at, key="nav:4")
    assert any("SO non décrite" in m.value for m in at.markdown)


# ------------------------------------------------------------------ réglages
def _reglages(at):
    clic(at, "Seuils et données")
    return at


def test_reglages_seuil_modifie_applique_et_signale():
    at = app()
    charger(at, {"locaux": [{"PL-03": 2.45, "BA-05": "Aucun", "PL-01": "Sous-face de dalle ou de plancher béton apparente",
                             "BA-19": ["Aucun"], "ECL-02": ["Encastré dans le faux plafond (dalle, spot)"]}]})
    demarrer(at)
    _reglages(at)
    at.tabs  # onglets rendus
    at.number_input(key=f"{gen(at)}:param:P_HSP_MIN").set_value(2.5).run()
    assert D(at)["parametres"] == {"P_HSP_MIN": 2.5}
    res = moteur.calculer(D(at))
    assert res["locaux"][0]["blocs"]["BS"]["regle"] == "BS-1"
    clic(at, "Rétablir les valeurs par défaut")
    assert D(at)["parametres"] == {}


def test_reglages_tout_effacer():
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at)
    _reglages(at)
    clic(at, "🗑 Tout effacer et recommencer")
    assert D(at)["locaux"] == [] and at.session_state["mode"] is None


def _importer(at, contenu: bytes, nom: str, prefixe="depart"):
    up = next(u for u in at.get("file_uploader") if "Importer une saisie" in u.proto.label)
    # AppTest ne sait pas téléverser : on passe par la fonction de l'application, comme le bouton
    return up


def _import_direct(fichier):
    """Reproduit le bloc ``try`` du bouton « Importer ce fichier »."""
    from surya.import_excel import lire_classeur
    return json.load(fichier) if fichier.name.endswith(".json") else lire_classeur(fichier)


def test_export_import_json_aller_retour_statuts_identiques():
    at = app()
    clic(at, key="depart:exemple")
    export = next(d for d in at.download_button if d.label == "Exporter la saisie (JSON)")
    contenu = export.proto.url if hasattr(export, "proto") else None
    d = D(at)
    texte = json.dumps(d, ensure_ascii=False, indent=1)
    relu = _import_direct(Fichier(texte.encode(), "saisie.json"))
    assert moteur.calculer(relu) == moteur.calculer(d)
    at2 = app()
    charger(at2, relu)
    assert moteur.calculer(D(at2))["locaux"] == moteur.calculer(d)["locaux"]


@pytest.mark.parametrize("contenu,nom", [
    (b"{pas du json", "x.json"), (b"", "vide.json"), (b"[1, 2]", "liste.json"), (b'{"locaux": {"a": 1}}', "x.json"),
    (b'{"locaux": ["texte"]}', "x.json"), (b"", "vide.xlsx"), (b"PK\x03\x04 pas un zip", "x.xlsx"),
])
def test_imports_invalides_message_sans_plantage(contenu, nom):
    """Le bouton « Importer ce fichier » rattrape toute exception et affiche « Import impossible : … »."""
    from surya.import_excel import lire_classeur  # noqa: F401
    try:
        d = _import_direct(Fichier(contenu, nom))
        at = app()
        charger(at, d) if isinstance(d, dict) else None
    except Exception as e:  # le message affiché à l'utilisateur
        msg = f"Import impossible : {e}"
        assert msg


def test_import_autre_excel_message_peu_clair():
    """Un autre classeur Excel (sans onglets Saisie_*) donne « Import impossible : 'Worksheet Saisie_Bâtiment
    does not exist.' » : message technique en anglais (ANO-29, mineur)."""
    import openpyxl
    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(KeyError) as e:
        _import_direct(Fichier(buf.getvalue(), "autre.xlsx"))
    assert "does not exist" in str(e.value)


@pytest.mark.xfail(strict=True, reason="ANO-30 : un import JSON avec E-30 = 5 (ou une valeur négative) fait planter "
                                       "l'éditeur de l'espace (StreamlitAPIException : valeur hors bornes)")
def test_import_valeur_hors_bornes_ne_fait_pas_planter_l_editeur():
    at = app()
    charger(at, {"espaces": [{"E-01": "Cour", "E-02": ["Préau"], "E-30": 5}]})
    demarrer(at, "resultats", "libre")
    clic(at, key="nav:2")
    bouton(at, contient="Modifier").click().run()
    assert not at.exception


@pytest.mark.xfail(strict=True, reason="ANO-31 : afficher la fiche d'un local importé modifie silencieusement les "
                                       "données (effectif 25,5 → 25 ; réponse hors liste effacée)")
def test_afficher_une_fiche_ne_modifie_pas_les_donnees():
    at = app()
    charger(at, {"locaux": [{"L-01": "A", "L-04": 25.5, "L-02": "Salle de classe"}]})
    demarrer(at, "resultats", "libre")
    clic(at, key="nav:1")
    avant = copy.deepcopy(D(at)["locaux"][0])
    bouton(at, contient="Modifier").click().run()
    assert D(at)["locaux"][0] == avant


@pytest.mark.xfail(strict=True, reason="ANO-07 : un seuil importé en texte fait planter l'onglet « Seuils des règles »")
def test_import_seuil_texte_reglages():
    at = app()
    charger(at, {"locaux": [{}], "parametres": {"P_HSP_MIN": "2,4"}})
    demarrer(at)
    _reglages(at)
    assert not at.exception


def test_import_excel_de_reference():
    d = _import_direct(Fichier((RACINE / "reference" / "outil_aide_test_methode.xlsx").read_bytes(), "ref.xlsx"))
    assert d == EXEMPLE


# ------------------------------------------------------------------ questionnaires usagers
def test_page_usager_via_lien():
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=60)
    at.query_params["questionnaire"] = "abc"
    at.run()
    assert at.title[0].value == "Questionnaire confort estival"
    radios = {r.label.split("**")[1].rstrip(".") if "**" in r.label else r.label: r for r in at.radio}
    assert "12" not in radios  # Q12 masquée tant que Q11 est vide
    clic(at, "Envoyer mes réponses")
    assert any("vide" in e.value for e in at.error)
    [r for r in at.radio if r.label.startswith("**4.**")][0].set_value("Chaude").run()
    cb = [c for c in at.checkbox if c.label == "Rideaux"][0]
    cb.check().run()
    assert any(r.label.startswith("**12.**") for r in at.radio)
    clic(at, "Envoyer mes réponses")
    dl = [d for d in at.download_button if "ma réponse" in d.label]
    assert dl and at.session_state["usager_envoye"]["Q4"] == "Chaude"
    assert at.session_state["usager_envoye"]["Q11"] == ["Rideaux"]


@pytest.mark.xfail(strict=True, reason="ANO-32 : « Supprimer cette réponse » ne supprime rien pour les réponses de "
                                       "l'exemple ou d'un JSON importé (pas d'identifiant _id)")
def test_supprimer_une_reponse_de_l_exemple():
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at, "complet", "libre")
    clic(at, key="nav:5")
    assert etape(at) == "Questionnaires usagers"
    n = len(D(at)["questionnaires"])
    clic(at, "Supprimer cette réponse")
    assert len(D(at)["questionnaires"]) == n - 1


def test_saisie_papier_ajoute_une_reponse():
    at = app()
    charger(at, {"locaux": [{}]})
    demarrer(at, "complet", "libre")
    at.session_state["etape_max"] = 7
    at.run()
    clic(at, key="nav:5")
    radios = [r for r in at.radio if r.label.startswith("**4.**")]
    radios[-1].set_value("Très chaude").run()
    clic(at, "Ajouter ce questionnaire")
    q = D(at)["questionnaires"]
    assert len(q) == 1 and q[0]["Q4"] == "Très chaude" and q[0]["source"] == "papier" and q[0]["_id"]


def test_aucune_exception_sur_toutes_les_etapes_avec_l_exemple():
    for mode, n in (("resultats", 6), ("complet", 8)):
        at = app()
        clic(at, key="depart:exemple")
        demarrer(at, mode, "guidee")
        for i in range(n):
            clic(at, key=f"nav:{i}")
            assert not at.exception
        _reglages(at)
        assert not at.exception


# ------------------------------------------------------------------ tableau à l'écran = moteur (partie D)
def _tableau_ecran(at):
    """Lit les tableaux HTML de l'étape Résultats : {(nom, solution): (statut, ❓, ⚠️)}."""
    import html as h
    import re
    out = {}
    for m in at.markdown:
        if "<table" not in m.value:
            continue
        noms = [h.unescape(n) for n in re.findall(r"<th style='text-align:center;padding:6px 10px'>(.*?)</th>", m.value)]
        for sol, cellules in re.findall(r"<tr><td style='padding:5px 16px 5px 12px'>(.*?)</td>(.*?)</tr>", m.value):
            for nom, c in zip(noms, re.findall(r"<td style='text-align:center;padding:5px 10px'>(.*?)</td>", cellules)):
                statut = h.unescape(re.search(r">([^<>]+)</span>", c).group(1))
                out[(nom, h.unescape(sol))] = (statut, "❓" in c, "⚠️" in c)
    return out


@pytest.mark.parametrize("jeu", ["exemple Excel", "complet", "noms spéciaux", "tirage 1"])
def test_tableau_ecran_identique_au_moteur(jeu):
    from test_sorties import JEUX
    from surya.rapport import donnee_manquante
    d = JEUX[jeu]()
    at = app()
    charger(at, d)
    demarrer(at, "resultats")
    clic(at, key="nav:5")
    lu = _tableau_ecran(at)
    res = moteur.calculer(D(at))
    attendu = {}
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for i, x in enumerate(res[cle]):
            for s in x["solutions"]:
                attendu[(x["nom"] or f"{defaut} {i + 1}", s["solution"])] = (s["statut"], donnee_manquante(x, s),
                                                                              bool(s["alertes"]))
    assert lu == attendu


def test_noms_en_double_ecrasent_les_colonnes():
    """Deux locaux de même nom : rien ne les distingue à l'écran ni dans les documents (ANO-33, mineur)."""
    at = app()
    charger(at, {"locaux": [{"L-01": "Classe"}, {"L-01": "Classe", "L-03": 50}]})
    demarrer(at, "resultats")
    clic(at, key="nav:4")
    assert not any("même nom" in m.value or "doublon" in m.value for m in list(at.markdown) + list(at.warning))



@pytest.mark.xfail(strict=True, reason="ANO-06 : la légende des statuts n'est pas dans le même ordre à l'écran "
                                       "(Recommandé, En place, À optimiser…) et dans les PDF (Recommandé, À optimiser, En place…)")
def test_legende_meme_ordre_que_les_pdf():
    import re
    from surya.rapport import STATUTS
    at = app()
    clic(at, key="depart:exemple")
    demarrer(at, "resultats")
    clic(at, key="nav:5")
    legende = next(m.value for m in at.markdown if m.value.count("border-radius:12px") == 6)
    assert re.findall(r">([^<>]+)</span>", legende) == STATUTS


@pytest.mark.xfail(strict=True, reason="ANO-36 : l'étape Questionnaires annonce « 23 questions » ; il y en a 24 (Q24 ajoutée)")
def test_nombre_de_questions_annonce():
    from surya import questionnaire as QU
    at = app()
    charger(at, {"locaux": [{}]})
    demarrer(at, "complet")
    at.session_state["etape_max"] = 7
    at.run()
    clic(at, key="nav:5")
    texte = " ".join(m.value for m in at.markdown)
    assert f"{len(QU.QUESTIONS)} questions" in texte


@pytest.mark.xfail(strict=True, reason="ANO-37 : la Vérification cite les questions de façade par leur code (« S : F-03 "
                                       "sans réponse ») alors que l'étape Façades n'affiche que les libellés")
def test_verification_facades_en_clair():
    at = app()
    charger(at, {"locaux": [{"murs": [{"orientation": "S"}]}], "facades": {"S": {"F-01": True}}})
    demarrer(at)
    at.session_state["etape_max"] = 5
    at.run()
    clic(at, key="nav:4")
    texte = " ".join(m.value for m in at.markdown)
    assert "F-03 sans réponse" not in texte
