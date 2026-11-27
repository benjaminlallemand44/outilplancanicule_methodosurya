"""Branchement Supabase : client, dépôts et parcours de l'application, contre un faux serveur."""
from __future__ import annotations

import copy
import io
import json

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from cas_base import RACINE
from faux_supabase import CLE, FauxSupabase
from surya import photos as PH
from surya import supabase as SB

URL = "https://projet-test.supabase.co"
ECOLE = json.loads((RACINE / "surya" / "exemple_ecole_sud.json").read_text(encoding="utf-8"))


@pytest.fixture
def serveur(monkeypatch):
    s = FauxSupabase()
    monkeypatch.setattr(SB.requests, "Session", lambda: s)
    return s


def client(serveur, email="a@ecole.fr", mdp="motdepasse1"):
    sb = SB.Supabase(URL, CLE)
    if email not in serveur.comptes:
        sb.inscription(email, mdp)
    sb.connexion(email, mdp)
    return sb


def jpeg():
    b = io.BytesIO()
    Image.new("RGB", (64, 48), "#0a17a6").save(b, "JPEG")
    return b.getvalue()


# ------------------------------------------------------------------ client et dépôts
def test_authentification(serveur):
    sb = SB.Supabase(URL, CLE)
    assert sb.inscription("a@ecole.fr", "motdepasse1") is False and sb.connecte
    with pytest.raises(SB.ErreurSupabase, match="existe déjà"):
        SB.Supabase(URL, CLE).inscription("a@ecole.fr", "motdepasse1")
    with pytest.raises(SB.ErreurSupabase, match="trop faible"):
        SB.Supabase(URL, CLE).inscription("b@ecole.fr", "court")
    with pytest.raises(SB.ErreurSupabase, match="incorrect"):
        SB.Supabase(URL, CLE).connexion("a@ecole.fr", "mauvais")
    serveur.confirmation = True
    assert SB.Supabase(URL, CLE).inscription("c@ecole.fr", "motdepasse1") is True  # confirmation par e-mail
    with pytest.raises(SB.ErreurSupabase, match="non confirmée"):
        SB.Supabase(URL, CLE).connexion("c@ecole.fr", "motdepasse1")
    sb.deconnexion()
    assert not sb.connecte


def test_audits_cloisonnes_par_auditeur(serveur):
    a, b = client(serveur, "a@ecole.fr"), client(serveur, "b@ecole.fr")
    d = copy.deepcopy(ECOLE)
    d["audit"]["code"] = "0123456789abcdef"
    ligne = SB.DepotAudits(a).enregistrer(d)
    assert ligne["code"] == "0123456789abcdef" and ligne["nom"] == d["audit"]["etablissement"]
    d["audit"]["etablissement"] = "Renommé"
    assert SB.DepotAudits(a).enregistrer(d, ligne["id"])["nom"] == "Renommé"
    assert [x["id"] for x in SB.DepotAudits(a).lister()] == [ligne["id"]]
    assert SB.DepotAudits(a).ouvrir(ligne["id"])["donnees"]["locaux"] == ECOLE["locaux"]
    assert SB.DepotAudits(b).lister() == []
    with pytest.raises(SB.ErreurSupabase, match="introuvable"):
        SB.DepotAudits(b).ouvrir(ligne["id"])
    with pytest.raises(SB.ErreurSupabase):
        SB.DepotAudits(b).enregistrer(d, ligne["id"])  # modification de l'audit d'un autre : refusée
    SB.DepotAudits(a).supprimer(ligne["id"])
    assert SB.DepotAudits(a).lister() == []


def test_reponses_usagers(serveur):
    a = client(serveur)
    d = copy.deepcopy(ECOLE)
    d["audit"]["code"] = "aaaabbbbccccdddd"
    SB.DepotAudits(a).enregistrer(d)
    anonyme = SB.DepotReponsesSupabase(SB.Supabase(URL, CLE))
    anonyme.ajouter("aaaabbbbccccdddd", {"Q4": "Chaude", "Q11": ["Stores"], "_id": "x", "vide": ""})
    with pytest.raises(SB.ErreurSupabase, match="pas valide"):
        anonyme.ajouter("code-inconnu", {"Q4": "Chaude"})
    assert anonyme.lister("aaaabbbbccccdddd") == []  # un anonyme ne lit rien
    reps = SB.DepotReponsesSupabase(a).lister("aaaabbbbccccdddd")
    assert len(reps) == 1 and reps[0]["Q11"] == ["Stores"] and reps[0]["source"] == "en ligne" and "vide" not in reps[0]
    # questionnaire clos : plus de dépôt
    serveur.audits[0]["questionnaire_ouvert"] = False
    with pytest.raises(SB.ErreurSupabase, match="clos"):
        anonyme.ajouter("aaaabbbbccccdddd", {"Q4": "Chaude"})
    SB.DepotReponsesSupabase(a).supprimer("aaaabbbbccccdddd", reps[0]["_id"])
    assert SB.DepotReponsesSupabase(a).lister("aaaabbbbccccdddd") == []


def test_limite_de_debit(serveur):
    a = client(serveur)
    d = copy.deepcopy(ECOLE)
    d["audit"]["code"] = "1111222233334444"
    SB.DepotAudits(a).enregistrer(d)
    anonyme = SB.DepotReponsesSupabase(SB.Supabase(URL, CLE))
    for _ in range(60):
        anonyme.ajouter("1111222233334444", {"Q4": "Chaude"})
    with pytest.raises(SB.ErreurSupabase):
        anonyme.ajouter("1111222233334444", {"Q4": "Chaude"})


def test_photos_synchronisees_et_cloisonnees(serveur):
    a, b = client(serveur, "a@ecole.fr"), client(serveur, "b@ecole.fr")
    d = copy.deepcopy(ECOLE)
    ident = SB.DepotAudits(a).enregistrer(d)["id"]
    ph = PH.nouvelle("batiment", {}, "Façade")
    d["photos"] = [ph]
    supprimees = []
    assert SB.synchroniser_photos(SB.DepotPhotos(a), ident, d, {ph["id"]: jpeg()}, supprimees) == 1
    assert ph["envoyee"] and SB.synchroniser_photos(SB.DepotPhotos(a), ident, d, {ph["id"]: jpeg()}, supprimees) == 0
    assert SB.DepotPhotos(a).telecharger(ident, ph["id"]) == jpeg()
    with pytest.raises(SB.ErreurSupabase):
        SB.DepotPhotos(b).telecharger(ident, ph["id"])
    with pytest.raises(SB.ErreurSupabase):
        SB.DepotPhotos(b).envoyer(ident, "intrus", b"x")
    supprimees.append(ph["id"])
    SB.synchroniser_photos(SB.DepotPhotos(a), ident, {"photos": []}, {}, supprimees)
    assert not serveur.objets and supprimees == []


def test_configuration():
    assert SB.configuration({}) is None
    assert SB.configuration({"supabase": {"url": URL}}) is None
    assert SB.configuration({"supabase": {"url": URL, "cle_publique": CLE}}) == (URL, CLE)


def test_serveur_injoignable(monkeypatch):
    import requests

    class Coupe:
        def request(self, *a, **k):
            raise requests.ConnectionError("coupé")
    sb = SB.Supabase(URL, CLE, session=Coupe())
    with pytest.raises(SB.ErreurSupabase, match="injoignable"):
        sb.connexion("a@ecole.fr", "motdepasse1")


# ------------------------------------------------------------------ application
def app_connectee(serveur, email="a@ecole.fr", mdp="motdepasse1"):
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=120)
    at.secrets["supabase"] = {"url": URL, "cle_publique": CLE}
    at.run()
    assert not at.exception
    if email not in serveur.comptes:
        SB.Supabase(URL, CLE).inscription(email, mdp)
    at.text_input[0].set_value(email)
    at.text_input[1].set_value(mdp)
    next(b for b in at.button if getattr(b, "label", "") == "Se connecter").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_app_sans_configuration_reste_une_maquette():
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert not any("Se connecter" in e.label for e in at.expander)


def test_app_enregistre_et_rouvre_un_audit(serveur):
    at = app_connectee(serveur)
    assert any("Vos audits enregistrés" in m.value for m in at.markdown)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    # une photo du bâtiment
    j, infos = PH.preparer(jpeg())
    ph = PH.nouvelle("batiment", infos, "Façade")
    at.session_state["donnees"]["photos"].append(ph)
    at.session_state["photos_bin"] = {ph["id"]: j}
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()  # changement d'étape : enregistré
    assert not at.exception, [e.value for e in at.exception]
    assert len(serveur.audits) == 1 and serveur.audits[0]["nom"].startswith("Groupe scolaire Les Pins")
    assert serveur.audits[0]["donnees"]["photos"][0]["envoyee"] is True
    assert len(serveur.objets) == 1
    ident = serveur.audits[0]["id"]
    # nouvelle session : l'audit se rouvre avec ses photos
    at2 = app_connectee(serveur)
    next(b for b in at2.button if b.key == f"ouvrir:{ident}").click().run()
    assert not at2.exception, [e.value for e in at2.exception]
    d = at2.session_state["donnees"]
    assert len(d["locaux"]) == len(ECOLE["locaux"]) and d["photos"][0]["id"] == ph["id"]
    assert at2.session_state["photos_bin"][ph["id"]] == j
    assert at2.session_state["audit_id"] == ident


def test_questionnaire_en_ligne_enregistre(serveur):
    at = app_connectee(serveur)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()
    code = serveur.audits[0]["code"]
    usager = AppTest.from_file(str(RACINE / "app.py"), default_timeout=120)
    usager.secrets["supabase"] = {"url": URL, "cle_publique": CLE}
    usager.query_params["questionnaire"] = code
    usager.run()
    usager.radio[0].set_value(usager.radio[0].options[0]).run()
    next(b for b in usager.button if b.label == "Envoyer mes réponses").click().run()
    assert not usager.exception and any("Merci" in s.value for s in usager.success)
    assert len(serveur.reponses) == 1
    # code inconnu : refusé avec un message clair
    intrus = AppTest.from_file(str(RACINE / "app.py"), default_timeout=120)
    intrus.secrets["supabase"] = {"url": URL, "cle_publique": CLE}
    intrus.query_params["questionnaire"] = "ffffffffffffffff"
    intrus.run()
    intrus.radio[0].set_value(intrus.radio[0].options[0]).run()
    next(b for b in intrus.button if b.label == "Envoyer mes réponses").click().run()
    assert any("pas valide" in e.value for e in intrus.error) and len(serveur.reponses) == 1


# ------------------------------------------------------------------ conservation des données
def test_date_de_suppression_et_rappel():
    import datetime as dt
    jour = dt.datetime(2026, 11, 26, tzinfo=dt.timezone.utc)
    assert SB.suppression_prevue("2026-11-26T10:00:00+00:00", jour) == ("25/11/2029", False)
    assert SB.suppression_prevue("2023-12-10T10:00:00Z", jour) == ("09/12/2026", True)  # dans le mois
    assert SB.suppression_prevue("pas une date", jour) == ("", False)


def test_ouvrir_un_audit_le_conserve(serveur):
    """Ouvrir un audit met à jour sa date de dernière modification (le délai de 3 ans repart)."""
    at = app_connectee(serveur)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()
    serveur.audits[0]["modifie_le"] = "2024-01-01T00:00:00+00:00"
    at2 = app_connectee(serveur)
    assert any("suppression prévue le 31/12/2026" in m.value for m in at2.markdown)
    next(b for b in at2.button if b.key == f"ouvrir:{serveur.audits[0]['id']}").click().run()
    assert not at2.exception and serveur.audits[0]["modifie_le"] > "2026"


# ------------------------------------------------------------------ plusieurs audits
def test_filtrer_audits():
    audits = [{"nom": "École Jules Ferry", "code": "a1"}, {"nom": "Groupe scolaire Les Pins", "code": "b2"}]
    assert [a["code"] for a in SB.filtrer_audits(audits, "ecole ferry")] == ["a1"]  # sans accent ni casse
    assert [a["code"] for a in SB.filtrer_audits(audits, "PINS")] == ["b2"]
    assert SB.filtrer_audits(audits, "b2") == [audits[1]] and SB.filtrer_audits(audits, "  ") == audits
    assert SB.filtrer_audits(audits, "ferry pins") == []


def test_nouvel_audit_garde_le_precedent(serveur):
    at = app_connectee(serveur)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.key == "nouveau:entete").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(serveur.audits) == 1 and serveur.audits[0]["nom"].startswith("Groupe scolaire Les Pins")
    assert at.session_state["donnees"]["locaux"] == [] and at.session_state["audit_id"] is None
    assert at.session_state["mode"] is None and not at.warning  # connecté : pas de confirmation
    assert any(f"ouvrir:{serveur.audits[0]['id']}" == b.key for b in at.button)
    next(b for b in at.button if b.key == "depart:exemple").click().run()
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()
    assert len(serveur.audits) == 2


def test_recherche_dans_les_audits(serveur):
    sb = SB.Supabase(URL, CLE)
    sb.inscription("a@ecole.fr", "motdepasse1")
    sb.connexion("a@ecole.fr", "motdepasse1")
    for nom in ("École maternelle Jules Ferry", "École Victor Hugo", "Collège Camus", "École des Pins",
                "Groupe scolaire Pasteur", "École du Port"):
        SB.DepotAudits(sb).enregistrer({"audit": {"etablissement": nom}})
    at = app_connectee(serveur)
    ouvrir = lambda: [b for b in at.button if (b.key or "").startswith("ouvrir:")]
    assert len(ouvrir()) == 6
    at.text_input(key="recherche_audit").set_value("ecole p").run()
    assert {serveur_nom(serveur, b.key) for b in ouvrir()} == {"École des Pins", "École du Port"}
    at.text_input(key="recherche_audit").set_value("lycée").run()
    assert not ouvrir() and any("Aucun audit ne correspond" in c.value for c in at.caption)


def serveur_nom(serveur, cle_bouton):
    return next(a["nom"] for a in serveur.audits if a["id"] == cle_bouton.split(":", 1)[1])


def test_ouvrir_un_audit_ne_l_ecrase_pas(serveur):
    """Ouvrir un audit le réenregistre (délai de conservation) : avec ses propres données, pas avec la saisie
    affichée avant l'ouverture (défaut trouvé en corrigeant C2-01 : l'audit était écrasé par une saisie vide)."""
    at = app_connectee(serveur)
    next(b for b in at.button if b.key == "depart:ecole_sud").click().run()
    next(b for b in at.button if b.label == "Commencer — diagnostic complet").click().run()
    next(b for b in at.button if b.label.startswith("Suivant :")).click().run()
    n = len(serveur.audits[0]["donnees"]["locaux"])
    at2 = app_connectee(serveur)  # nouvelle session : saisie vide à l'écran
    next(b for b in at2.button if b.key == f"ouvrir:{serveur.audits[0]['id']}").click().run()
    assert not at2.exception and len(serveur.audits) == 1
    assert len(serveur.audits[0]["donnees"]["locaux"]) == n > 0
