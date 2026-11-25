"""Structures d'ingénierie locale qui peuvent (au moins en théorie) accompagner une commune pour le passage
en travaux, à partir de son code postal.

Trois sources, interrogées au moment de la recherche :

* **API Découpage administratif** (geo.api.gouv.fr) : commune, département, région, intercommunalité ;
* **API Annuaire de l'administration** (service-public.gouv.fr, DILA) : intercommunalité, CAUE, Espaces
  conseil France Rénov', conseil départemental, avec adresse, téléphone, courriel et site ;
* **API Recherche d'entreprises** (répertoire SIRENE) : syndicats d'énergie, agences techniques
  départementales, agences locales de l'énergie et du climat, sociétés publiques locales. SIRENE donne le
  nom et l'adresse du siège, pas le téléphone ni le courriel : ces résultats sont à vérifier.

S'y ajoute un fichier de contacts maintenu par ACTEE (``kit/structures_ingenierie.csv``) : centres de
ressources bâtiment durable, têtes de réseau nationales, et contacts vérifiés (par exemple des syndicats
d'énergie). Une entrée du fichier remplace un résultat SIRENE du même type dans le même département.

Aucune dépendance à Streamlit. Les appels réseau passent par ``http`` (``requests`` par défaut), que les
tests remplacent par un faux client.
"""
from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from pathlib import Path

FICHIER = Path(__file__).parent / "kit" / "structures_ingenierie.csv"
GEO = "https://geo.api.gouv.fr/communes"
ANNUAIRES = ["https://api-lannuaire.service-public.gouv.fr/api/explore/v2.1/catalog/datasets/"
             "api-lannuaire-administration/records",
             "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/"
             "api-lannuaire-administration/records"]
SIRENE = "https://recherche-entreprises.api.gouv.fr/search"
DELAI = 10

# type -> (libellé, ce qu'elle peut apporter, couleur RGB pour la carte). Ordre d'affichage.
TYPES = {
    "epci": ("Intercommunalité",
             "Peut disposer d'un service bâtiment ou énergie mutualisé, d'un conseiller en énergie partagé, ou "
             "porter un groupement de commandes pour les communes membres.", (10, 23, 166)),
    "sde": ("Syndicat départemental d'énergie (SDE)",
            "Accompagne souvent les communes sur leurs bâtiments : économe de flux ou conseil en énergie partagé, "
            "études, parfois maîtrise d'ouvrage déléguée et aides financières.", (255, 84, 0)),
    "atd": ("Agence technique départementale (ATD)",
            "Assistance à maîtrise d'ouvrage pour les communes adhérentes : programme, consultation de la "
            "maîtrise d'œuvre, suivi de l'opération.", (91, 186, 80)),
    "cd": ("Conseil départemental",
           "Porte souvent l'offre d'ingénierie territoriale pour les communes, directement ou par une agence : à "
           "interroger si aucune agence technique n'apparaît.", (120, 120, 120)),
    "caue": ("Conseil d'architecture, d'urbanisme et de l'environnement (CAUE)",
             "Conseil gratuit sur l'architecture et les espaces extérieurs (cour, ombrage, végétalisation), aide "
             "à la rédaction du programme et au choix de la maîtrise d'œuvre.", (13, 204, 204)),
    "alec": ("Agence locale de l'énergie et du climat (ALEC)",
             "Conseil neutre sur l'énergie et le confort d'été ; accompagne les collectivités adhérentes.",
             (255, 195, 0)),
    "fr_renov": ("Espace conseil France Rénov'",
                 "S'adresse surtout aux particuliers, mais est parfois porté par une ALEC ou le syndicat "
                 "d'énergie : peut orienter vers le bon interlocuteur.", (141, 200, 248)),
    "spl": ("Société publique locale (SPL)",
            "Si la commune en est actionnaire, elle peut lui confier des études ou des travaux sans mise en "
            "concurrence (quasi-régie).", (170, 60, 170)),
    "crbd": ("Centre de ressources bâtiment durable",
             "Retours d'expérience, ressources techniques et mise en relation ; n'accompagne pas une opération en "
             "général.", (90, 90, 160)),
    "national": ("Tête de réseau nationale",
                 "Pour trouver la structure locale si elle n'apparaît pas ci-dessus.", (60, 60, 60)),
}

# Codes INSEE des régions (pour le fichier de contacts : périmètre « R:84 »).
REGIONS = {"84": "Auvergne-Rhône-Alpes", "27": "Bourgogne-Franche-Comté", "53": "Bretagne",
           "24": "Centre-Val de Loire", "94": "Corse", "44": "Grand Est", "01": "Guadeloupe", "03": "Guyane",
           "32": "Hauts-de-France", "11": "Île-de-France", "04": "La Réunion", "02": "Martinique",
           "06": "Mayotte", "28": "Normandie", "75": "Nouvelle-Aquitaine", "76": "Occitanie",
           "52": "Pays de la Loire", "93": "Provence-Alpes-Côte d'Azur"}

# Recherche SIRENE : (requête, motif que le nom doit contenir, motif à exclure)
REQUETES_SIRENE = {
    "sde": [("syndicat energie", r"ENERG|ELECTRI", r"COPROPRI|SALARIES|CGT|CFDT|FO |PROFESSIONN"),
            ("territoire d'energie", r"ENERG", r"COPROPRI|SALARIES")],
    "atd": [("agence technique departementale", r"AGENCE TECHNIQUE|INGENIERIE", r"ROUTI"),
            ("ingenierie departementale", r"INGENIERIE", r"SARL|SAS|CONSEIL EN")],
    "alec": [("agence locale energie climat", r"AGENCE LOCALE|ALEC|\bALE\b", r"IMMOBILI")],
    "spl": [("societe publique locale energie", r"SPL|SOCIETE PUBLIQUE LOCALE", r"TOURIS|EAU|TRANSPORT|PORT"),
            ("SPL renovation", r"SPL|SOCIETE PUBLIQUE LOCALE", r"TOURIS|EAU|TRANSPORT|PORT")],
}
LIMITE_SIRENE = 3
LIMITE_FR_RENOV = 3


# ------------------------------------------------------------------ utilitaires
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


def _json(v):
    """Champs de l'annuaire : liste, dictionnaire, ou texte JSON selon l'export."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def _liste(v) -> list:
    v = _json(v)
    if v in (None, "", []):
        return []
    return v if isinstance(v, list) else [v]


def _valeurs(v) -> list[str]:
    out = []
    for x in _liste(v):
        if isinstance(x, dict):
            x = x.get("valeur") or x.get("value") or ""
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _flottant(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def distance_km(a, b) -> float | None:
    if not a or not b or None in (*a, *b):
        return None
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2
         + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return round(12742 * math.asin(math.sqrt(h)), 1)


def _get(http, url, params):
    r = http.get(url, params=params, timeout=DELAI, headers={"User-Agent": "outil-plan-canicule-actee"})
    r.raise_for_status()
    return r.json()


def _http(http):
    if http is not None:
        return http
    import requests
    return requests.Session()


# ------------------------------------------------------------------ commune
def communes(code_postal: str, http=None) -> list[dict]:
    """Communes d'un code postal : nom, code INSEE, département, région, intercommunalité, centre."""
    cp = re.sub(r"\D", "", code_postal or "")
    if len(cp) != 5:
        raise ValueError("Le code postal doit comporter 5 chiffres.")
    data = _get(_http(http), GEO, {"codePostal": cp, "fields": "nom,code,codeDepartement,codeRegion,codeEpci,epci,"
                                   "centre,population", "format": "json"})
    out = []
    for c in data or []:
        epci = c.get("epci") if isinstance(c.get("epci"), dict) else {}
        coords = ((c.get("centre") or {}).get("coordinates") or [None, None])
        out.append({"nom": c.get("nom"), "code": c.get("code"), "departement": c.get("codeDepartement"),
                    "region": c.get("codeRegion"), "epci_siren": c.get("codeEpci") or epci.get("code"),
                    "epci_nom": epci.get("nom"), "lat": coords[1], "lon": coords[0],
                    "population": c.get("population"), "code_postal": cp})
    return sorted(out, key=lambda c: -(c.get("population") or 0))


# ------------------------------------------------------------------ annuaire de l'administration
def _annuaire(http, where: str, limite: int = 100) -> list[dict]:
    derniere = None
    for base in ANNUAIRES:
        try:
            return _get(http, base, {"where": where, "limit": limite}).get("results") or []
        except Exception as e:  # nouvelle adresse indisponible : ancienne adresse
            derniere = e
    raise derniere


def _depuis_annuaire(r: dict, type_: str, origine) -> dict:
    adresses = [a for a in _liste(r.get("adresse")) if isinstance(a, dict)]
    a = next((x for x in adresses if x.get("type_adresse") in ("Adresse", "Adresse physique")), adresses[0] if adresses else {})
    lignes = [a.get(k) for k in ("numero_voie", "complement1", "complement2", "service_distribution") if a.get(k)]
    ville = " ".join(x for x in (a.get("code_postal"), a.get("nom_commune")) if x)
    lat, lon = _flottant(a.get("latitude")), _flottant(a.get("longitude"))
    sites = _valeurs(r.get("site_internet"))
    return {"type": type_, "nom": r.get("nom") or "", "telephone": " / ".join(_valeurs(r.get("telephone"))[:2]),
            "courriel": " / ".join(_valeurs(r.get("adresse_courriel"))[:2]), "site": sites[0] if sites else "",
            "adresse": ", ".join([*lignes, ville]) if (lignes or ville) else "", "lat": lat, "lon": lon,
            "distance_km": distance_km(origine, (lat, lon)) if lat is not None else None,
            "source": "Annuaire de l'administration (service-public.gouv.fr)", "a_verifier": False}


def _par_departement(http, pivot: str, dep: str) -> list[dict]:
    return _annuaire(http, f'pivot like "{pivot}" and startswith(code_insee_commune, "{dep}")')


# ------------------------------------------------------------------ SIRENE
def _sirene(http, type_: str, dep: str, origine) -> list[dict]:
    vus, out = set(), []
    for q, garder, exclure in REQUETES_SIRENE[type_]:
        data = _get(http, SIRENE, {"q": q, "departement": dep, "etat_administratif": "A", "per_page": 10})
        for r in data.get("results") or []:
            nom = r.get("nom_complet") or r.get("nom_raison_sociale") or ""
            n = _norm(nom)
            if r.get("siren") in vus or not re.search(garder, n) or (exclure and re.search(exclure, n)):
                continue
            vus.add(r.get("siren"))
            s = r.get("siege") or {}
            lat, lon = _flottant(s.get("latitude")), _flottant(s.get("longitude"))
            out.append({"type": type_, "nom": nom.title() if nom.isupper() else nom, "telephone": "", "courriel": "",
                        "site": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{r.get('siren')}",
                        "adresse": s.get("adresse") or "", "lat": lat, "lon": lon,
                        "distance_km": distance_km(origine, (lat, lon)) if lat is not None else None,
                        "source": "Répertoire SIRENE (API Recherche d'entreprises) : nom et siège, coordonnées à "
                                  "chercher sur le site de la structure", "a_verifier": True})
    out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))
    return out[:LIMITE_SIRENE]


# ------------------------------------------------------------------ fichier ACTEE
def statiques(dep: str, region: str, chemin: Path = FICHIER) -> list[dict]:
    out = []
    with open(chemin, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = (r.get("perimetre") or "").strip()
            if p in (f"D:{dep}", f"R:{region}", "FR"):
                out.append({"type": r["type"], "nom": r["nom"], "telephone": r.get("telephone") or "",
                            "courriel": r.get("courriel") or "", "site": r.get("site") or "",
                            "adresse": r.get("adresse") or "", "lat": None, "lon": None, "distance_km": None,
                            "source": r.get("source") or "Fichier ACTEE", "a_verifier": False})
    return out


# ------------------------------------------------------------------ recherche complète
def rechercher(commune: dict, http=None) -> dict:
    """Structures pour une commune (issue de ``communes``) : {"structures": [...], "erreurs": [...]}.
    Une source en échec n'empêche pas les autres."""
    http = _http(http)
    dep, reg = commune["departement"], commune["region"]
    origine = (commune.get("lat"), commune.get("lon"))
    res, erreurs = [], []

    def essai(libelle, f):
        try:
            res.extend(f())
        except Exception as e:  # réseau, quota, format : on continue avec les autres sources
            erreurs.append(f"{libelle} : source indisponible ({type(e).__name__}).")

    if commune.get("epci_siren"):
        essai("Intercommunalité", lambda: [_depuis_annuaire(r, "epci", origine) for r in
                                            _annuaire(http, f'pivot like "epci" and siren = "{commune["epci_siren"]}"')][:1]
              or [{"type": "epci", "nom": commune.get("epci_nom") or "Intercommunalité", "telephone": "",
                   "courriel": "", "site": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{commune['epci_siren']}",
                   "adresse": "", "lat": None, "lon": None, "distance_km": None,
                   "source": "API Découpage administratif (coordonnées absentes de l'annuaire)", "a_verifier": True}])
    statique = statiques(dep, reg)
    types_statiques = {s["type"] for s in statique if s["type"] in REQUETES_SIRENE}
    for t in ("sde", "atd"):
        if t not in types_statiques:
            essai(TYPES[t][0], lambda t=t: _sirene(http, t, dep, origine))
    essai("Conseil départemental", lambda: _cd(http, dep, origine))
    essai("CAUE", lambda: [_depuis_annuaire(r, "caue", origine) for r in _par_departement(http, "caue", dep)][:1])
    for t in ("alec", "spl"):
        if t not in types_statiques:
            essai(TYPES[t][0], lambda t=t: _sirene(http, t, dep, origine))
    essai("France Rénov'", lambda: sorted((_depuis_annuaire(r, "fr_renov", origine)
                                           for r in _par_departement(http, "fr_renov", dep)),
                                          key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))[:LIMITE_FR_RENOV])
    res.extend(statique)
    vus, uniques = set(), []
    for s in res:
        cle = (s["type"], _norm(s["nom"]))
        if cle not in vus:
            vus.add(cle)
            uniques.append(s)
    ordre = list(TYPES)
    uniques.sort(key=lambda s: (ordre.index(s["type"]), s["distance_km"] is None, s["distance_km"] or 0))
    return {"structures": uniques, "erreurs": erreurs}


def _cd(http, dep, origine) -> list[dict]:
    recs = [_depuis_annuaire(r, "cd", origine) for r in _par_departement(http, "cg", dep)]
    principal = [r for r in recs if _norm(r["nom"]).startswith(("CONSEIL DEPARTEMENTAL", "DEPARTEMENT",
                                                                "COLLECTIVITE"))]
    return (principal or recs)[:1]


# ------------------------------------------------------------------ message type
def message(commune: str, etablissement: str, moe: bool) -> str:
    return (
        f"Objet : demande d'accompagnement – adaptation de l'école {etablissement or '[nom de l’école]'} aux vagues "
        f"de chaleur\n\n"
        f"Madame, Monsieur,\n\n"
        f"La commune de {commune or '[commune]'} a fait réaliser un diagnostic de confort d'été de l'école "
        f"{etablissement or '[nom de l’école]'} dans le cadre du plan canicule des écoles. Ce diagnostic a abouti à un "
        f"pré-programme de travaux, que nous vous joignons.\n\n"
        + ("Une maîtrise d'œuvre nous est recommandée. " if moe else "")
        + "Nous souhaiterions savoir si votre structure peut nous accompagner pour la phase de passage en travaux : "
        "préparation des consultations"
        + (", recrutement de la maîtrise d'œuvre" if moe else "")
        + ", suivi des études et des travaux, ou orientation vers le bon interlocuteur.\n\n"
        "Pourriez-vous nous indiquer si cet accompagnement est possible, à quelles conditions (adhésion, "
        "convention, coût) et dans quels délais ?\n\n"
        "Nous vous remercions par avance.\n\n[Nom, fonction, téléphone]"
    )
