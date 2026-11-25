"""Recherche des structures d'ingénierie locale (APIs simulées : pas de réseau pendant les tests)."""
from __future__ import annotations

import json

import pytest

from surya import ingenierie as IG


class Rep:
    def __init__(self, data, code=200):
        self.data, self.code = data, code

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.code >= 400:
            raise RuntimeError(f"HTTP {self.code}")


def adresse(lat, lon, cp, ville):
    return json.dumps([{"type_adresse": "Adresse", "numero_voie": "1 place de la Mairie", "code_postal": cp,
                        "nom_commune": ville, "latitude": str(lat), "longitude": str(lon)}])


class FauxHttp:
    """Répond comme geo.api.gouv.fr, l'annuaire (champs en texte JSON) et l'API Recherche d'entreprises."""

    def __init__(self, panne=()):
        self.appels, self.panne = [], set(panne)

    def get(self, url, params=None, timeout=None, headers=None):
        self.appels.append((url, params))
        if "geo.api" in url:
            return Rep([{"nom": "Bourges", "code": "18033", "codeDepartement": "18", "codeRegion": "24",
                         "codeEpci": "241800507", "epci": {"code": "241800507", "nom": "CA Bourges Plus"},
                         "centre": {"type": "Point", "coordinates": [2.39, 47.08]}, "population": 64000}])
        if "lannuaire" in url:
            if "annuaire" in self.panne:
                return Rep({}, 503)
            w = params["where"]
            if '"epci"' in w:
                return Rep({"results": [{"nom": "Communauté d'agglomération Bourges Plus",
                                         "telephone": json.dumps([{"valeur": "02 48 57 80 00"}]),
                                         "adresse_courriel": json.dumps(["contact@agglo-bourgesplus.fr"]),
                                         "site_internet": json.dumps([{"libelle": "", "valeur": "https://www.agglo.fr"}]),
                                         "adresse": adresse(47.08, 2.40, "18000", "Bourges")}]})
            if '"caue"' in w:
                return Rep({"results": [{"nom": "CAUE du Cher", "telephone": [{"valeur": "02 48 00 00 00"}],
                                         "adresse_courriel": ["caue18@exemple.fr"], "site_internet": [],
                                         "adresse": adresse(47.09, 2.39, "18000", "Bourges")}]})
            if '"cg"' in w:
                return Rep({"results": [{"nom": "Maison du Département - Vierzon", "adresse": adresse(47.2, 2.0, "18100", "Vierzon")},
                                        {"nom": "Conseil départemental du Cher", "adresse": adresse(47.08, 2.39, "18000", "Bourges")}]})
            if '"fr_renov"' in w:
                return Rep({"results": [{"nom": f"Espace conseil France Rénov' {i}",
                                         "adresse": adresse(47.08 + i / 10, 2.39, "18000", "Bourges")} for i in range(5)]})
            return Rep({"results": []})
        if "recherche-entreprises" in url:
            if "sirene" in self.panne:
                raise ConnectionError("pas de réseau")
            q = params["q"]
            if "agence technique" in q:
                return Rep({"results": [{"siren": "200000001", "nom_complet": "AGENCE TECHNIQUE DEPARTEMENTALE DU CHER",
                                         "siege": {"adresse": "Bourges", "latitude": "47.1", "longitude": "2.4"}},
                                        {"siren": "200000002", "nom_complet": "BOULANGERIE DU CHER",
                                         "siege": {"adresse": "Bourges"}}]})
            if "agence locale" in q:
                return Rep({"results": [{"siren": "300000001", "nom_complet": "ALEC DU CHER",
                                         "siege": {"latitude": "47.0", "longitude": "2.3"}}]})
            return Rep({"results": []})
        raise AssertionError(url)


def test_communes_par_code_postal():
    c = IG.communes("18000", FauxHttp())
    assert c[0]["code"] == "18033" and c[0]["departement"] == "18" and c[0]["epci_siren"] == "241800507"
    assert c[0]["lat"] == 47.08 and c[0]["lon"] == 2.39
    with pytest.raises(ValueError):
        IG.communes("180", FauxHttp())


def test_recherche_complete_et_coordonnees():
    http = FauxHttp()
    c = IG.communes("18000", http)[0]
    r = IG.rechercher(c, http)
    assert not r["erreurs"]
    par_type = {}
    for s in r["structures"]:
        par_type.setdefault(s["type"], []).append(s)
    epci = par_type["epci"][0]
    assert epci["telephone"] == "02 48 57 80 00" and epci["courriel"] == "contact@agglo-bourgesplus.fr"
    assert epci["site"] == "https://www.agglo.fr" and epci["distance_km"] is not None
    assert par_type["caue"][0]["courriel"] == "caue18@exemple.fr"  # champs déjà en liste : aussi lus
    assert par_type["cd"][0]["nom"] == "Conseil départemental du Cher"  # le siège plutôt qu'une antenne
    assert len(par_type["fr_renov"]) == IG.LIMITE_FR_RENOV and par_type["fr_renov"][0]["nom"].endswith(" 0")
    # syndicat d'énergie du Cher : contact vérifié du fichier ACTEE, pas de recherche SIRENE
    assert par_type["sde"][0]["telephone"] == "02 48 50 85 40" and not par_type["sde"][0]["a_verifier"]
    assert not any("syndicat energie" in (p or {}).get("q", "") for _, p in http.appels)
    # SIRENE : agence technique trouvée, boulangerie écartée, résultat marqué « à vérifier »
    assert [s["nom"] for s in par_type["atd"]] == ["Agence Technique Departementale Du Cher"]
    assert par_type["atd"][0]["a_verifier"] and "annuaire-entreprises" in par_type["atd"][0]["site"]
    assert par_type["alec"][0]["nom"] == "Alec Du Cher"
    assert par_type["crbd"] and par_type["national"]  # centres de ressources de la région et têtes de réseau
    ordre = [s["type"] for s in r["structures"]]
    assert ordre.index("epci") < ordre.index("sde") < ordre.index("caue") < ordre.index("national")


def test_une_source_en_panne_n_empeche_pas_les_autres():
    http = FauxHttp(panne={"annuaire", "sirene"})
    c = IG.communes("18000", http)[0]
    r = IG.rechercher(c, http)
    assert r["erreurs"]
    types = {s["type"] for s in r["structures"]}
    assert {"sde", "crbd", "national"} <= types  # fichier ACTEE toujours disponible


def test_fichier_actee_bien_forme():
    import csv
    with open(IG.FICHIER, encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    assert lignes
    for r in lignes:
        assert r["type"] in IG.TYPES and r["nom"] and r["source"]
        assert r["perimetre"] == "FR" or r["perimetre"][:2] in ("D:", "R:")
        if r["perimetre"].startswith("R:"):
            assert r["perimetre"][2:] in IG.REGIONS


def test_message_type():
    m = IG.message("Bourges", "École Jean Moulin", moe=True)
    assert "Bourges" in m and "École Jean Moulin" in m and "maîtrise d'œuvre" in m
    assert "recrutement de la maîtrise d'œuvre" not in IG.message("Bourges", "École", moe=False)
