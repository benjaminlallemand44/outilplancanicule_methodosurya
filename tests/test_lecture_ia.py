"""Lecture d'un rapport par IA (API simulée : pas de réseau pendant les tests)."""
from __future__ import annotations

import base64
import json

import pytest

from surya import lecture_ia as IA
from surya import travaux

PDF = b"%PDF-1.4\n% faux rapport\n"


class Rep:
    def __init__(self, data, code=200):
        self.data, self.status_code = data, code

    def json(self):
        return self.data


class FauxClaude:
    def __init__(self, reponse=None, code=200):
        self.reponse, self.code, self.requetes = reponse, code, []

    def post(self, url, json=None, timeout=None, headers=None):
        self.requetes.append((url, json, headers))
        return Rep(self.reponse, self.code)


PROPOSITION = {
    "ecole": {"etablissement": "École Benjamin Rabier", "commune": "Bretignolles-sur-Mer", "date_visite": "27/07/2026"},
    "diagnostic": {"source": "Inddigo – diagnostic confort estival", "date": "18/09/2026"},
    "batiment": {"B-01": "De 1975 à 1997", "B-09": "Oui", "B-10": "Simple flux", "B-18": "Inventée"},
    "operations": [
        {"solution": "Protections verticales", "locaux": ["Salles façade est"], "extrait": "Ajout de protections solaires "
         "mobiles extérieures", "page": 8, "vigilances": ["Arbitrer le type de protection"]},
        {"solution": "Mise en place de brasseurs d'air plafonniers", "locaux": ["Salles de classe"], "alertes": ["BR-AL"],
         "hauteur_limite": True, "extrait": "Mise en place de brasseurs d'air plafonniers", "page": 27},
        {"solution": "Protections verticales", "locaux": ["Salles façade ouest"], "extrait": "idem", "page": 9},
        {"solution": "Climatisation centrale", "extrait": "x"},
    ],
    "hors_catalogue": [{"intitule": "Gardiennage de nuit", "page": 50}],
}


def reponse_api(entree, stop="tool_use"):
    return {"content": [{"type": "tool_use", "name": IA.OUTIL, "input": entree}], "stop_reason": stop}


def test_requete_envoyee_a_l_api():
    http = FauxClaude(reponse_api(PROPOSITION))
    sortie = IA.analyser(PDF, "cle-test", http=http)
    assert sortie["diagnostic"]["source"].startswith("Inddigo")
    url, corps, entetes = http.requetes[0]
    assert url == IA.API and entetes["x-api-key"] == "cle-test" and entetes["anthropic-version"]
    assert corps["model"] == IA.MODELE_DEFAUT
    assert corps["tool_choice"] == {"type": "tool", "name": IA.OUTIL}
    doc = corps["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(doc["source"]["data"]) == PDF
    schema = corps["tools"][0]["input_schema"]
    assert set(schema["properties"]["operations"]["items"]["properties"]["solution"]["enum"]) == set(travaux.CATALOGUE)
    assert "De 1975 à 1997" in schema["properties"]["batiment"]["properties"]["B-01"]["enum"]
    assert "Ne reporte aucun coût" in corps["system"]
    json.dumps(corps)  # sérialisable


@pytest.mark.parametrize("pdf,cle,message", [(PDF, "", "pas configuré"), (b"pas un pdf", "k", "PDF lisible")])
def test_erreurs_avant_envoi(pdf, cle, message):
    with pytest.raises(IA.LectureImpossible, match=message):
        IA.analyser(pdf, cle, http=FauxClaude())


def test_erreurs_du_service():
    with pytest.raises(IA.LectureImpossible, match="401"):
        IA.analyser(PDF, "k", http=FauxClaude({"error": {"message": "invalid x-api-key"}}, 401))
    with pytest.raises(IA.LectureImpossible, match="incomplète"):
        IA.analyser(PDF, "k", http=FauxClaude({"content": [{"type": "text", "text": "Bonjour"}]}))
    sortie = IA.analyser(PDF, "k", http=FauxClaude(reponse_api({"operations": []}, stop="max_tokens")))
    assert "tronquée" in sortie["_avertissement"]


def test_conversion_en_saisie_et_etat():
    saisie, remarques = IA.vers_saisie(PROPOSITION, "rapport.pdf")
    assert saisie["audit"]["commune"] == "Bretignolles-sur-Mer" and saisie["audit"]["auditeur"].startswith("Inddigo")
    assert saisie["batiment"] == {"B-01": "De 1975 à 1997", "B-09": "Oui", "B-10": "Simple flux"}  # valeur inventée écartée
    ops = saisie["diagnostic_externe"]["operations"]
    assert [o["solution"] for o in ops] == ["Protections verticales", "Mise en place de brasseurs d'air plafonniers"]
    assert ops[0]["locaux"] == ["Salles façade est", "Salles façade ouest"]  # doublon fusionné
    assert ops[0]["origine"] == "ia" and ops[0]["page"] == 8 and ops[0]["extrait"]
    assert any("Climatisation centrale" in r for r in remarques)
    assert any("Gardiennage de nuit" in r for r in remarques)
    assert saisie["diagnostic_externe"]["lecture_ia"]["fichier"] == "rapport.pdf"
    # la saisie pré-remplie alimente directement le module
    d = {"audit": saisie["audit"], "batiment": saisie["batiment"], "diagnostic_externe": saisie["diagnostic_externe"]}
    e = travaux.etat(d)
    assert {o["solution"] for o in e["operations"]} == {"Protections verticales", "Mise en place de brasseurs d'air plafonniers"}
    # et passe le contrôle d'import (export / réimport de la saisie)
    t, notes = travaux.valider_externe(saisie["diagnostic_externe"])
    assert not notes and t["operations"][0]["origine"] == "ia" and t["lecture_ia"]["fichier"] == "rapport.pdf"
