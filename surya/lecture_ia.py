"""Lecture d'un rapport de diagnostic par IA pour pré-remplir la saisie « diagnostic existant ».

Le PDF du rapport (par exemple un diagnostic « plan canicule » réalisé par un bureau d'études hors de la méthode
ACTEE-SURYA) est envoyé à l'API Claude (Anthropic) avec la liste des actions du catalogue, les codes d'alerte et
les questions sur le bâtiment. Le modèle répond en remplissant un outil dont le schéma correspond exactement aux
champs de la saisie (``tool_choice`` forcé) : la réponse est donc directement exploitable.

Tout ce qui est pré-rempli est marqué « proposé par l'IA » avec l'extrait du rapport et la page : l'auditeur
vérifie avant de passer au pré-programme. Les préconisations sans équivalent dans le catalogue sont rendues à
part, pour être classées par une personne.

Configuration (secrets Streamlit, jamais dans le dépôt) ::

    [anthropic]
    cle = "sk-ant-..."
    modele = "claude-sonnet-5-5"   # facultatif

Aucune dépendance à Streamlit. Les appels réseau passent par ``http`` (``requests`` par défaut), que les tests
remplacent par un faux client.
"""
from __future__ import annotations

import base64
import datetime as dt

from . import travaux
from .moteur import REFERENTIEL, REGLES

API = "https://api.anthropic.com/v1/messages"
VERSION_API = "2023-06-01"
MODELE_DEFAUT = "claude-sonnet-5-5"
TAILLE_MAX = 30 * 1024 * 1024  # la requête complète est limitée à 32 Mo (PDF encodé compris)
DELAI = 180
OUTIL = "saisir_diagnostic"

CHAMPS_BATIMENT = ["B-01", "B-04", "B-05", "B-06", "B-08", "B-09", "B-10", "B-14", "B-15", "B-18", "B-21", "B-22", "B-26"]


class LectureImpossible(Exception):
    """Erreur présentable à l'utilisateur (clé absente, fichier trop lourd, service indisponible…)."""


def _question(code: str) -> dict:
    def chercher(o):
        if isinstance(o, dict):
            if o.get("code") == code:
                return o
            for v in o.values():
                r = chercher(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = chercher(v)
                if r:
                    return r
    return chercher(REFERENTIEL) or {}


def _alertes() -> list[str]:
    return sorted({a for v in travaux.ALERTES_PAR_SOLUTION.values() for a in v})


# ------------------------------------------------------------------ schéma et consignes
def schema() -> dict:
    """Schéma JSON de l'outil : les champs de la saisie « diagnostic existant »."""
    batiment = {}
    for code in CHAMPS_BATIMENT:
        q = _question(code)
        if q.get("options"):
            batiment[code] = {"type": "string", "enum": q["options"],
                              "description": q.get("libelle") or q.get("question") or code}
    texte = {"type": "string"}
    liste = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "properties": {
            "ecole": {"type": "object", "properties": {
                "etablissement": texte, "adresse": texte, "commune": texte, "moa": {**texte, "description": "Maître d'ouvrage (commune, communauté…)"},
                "date_visite": {**texte, "description": "Date de la visite, jj/mm/aaaa"}}},
            "diagnostic": {"type": "object", "properties": {
                "source": {**texte, "description": "Bureau d'études et nature du diagnostic, ex. « Inddigo – diagnostic confort estival »"},
                "date": {**texte, "description": "Date du rapport ou de sa validation, jj/mm/aaaa"}}},
            "batiment": {"type": "object", "properties": batiment,
                         "description": "Ne renseigner que ce que le rapport dit explicitement."},
            "operations": {"type": "array", "items": {"type": "object", "properties": {
                "solution": {"type": "string", "enum": list(travaux.CATALOGUE)},
                "locaux": {**liste, "description": "Locaux ou espaces où le rapport préconise l'action, tels que nommés dans le rapport"},
                "a_confirmer": {**liste, "description": "Locaux où le rapport émet une réserve ou demande une vérification"},
                "alertes": {"type": "array", "items": {"type": "string", "enum": _alertes()}},
                "hauteur_limite": {"type": "boolean", "description": "Brasseurs : hauteur sous plafond limite ou faux plafond"},
                "vigilances": {**liste, "description": "Points de vigilance et prochaines étapes du rapport, une phrase courte chacun"},
                "commentaire": texte,
                "extrait": {**texte, "description": "Courte citation du rapport (moins de 25 mots) justifiant l'action"},
                "page": {"type": "integer", "description": "Page du PDF où figure la préconisation"}},
                "required": ["solution", "extrait"]}},
            "hors_catalogue": {"type": "array", "items": {"type": "object", "properties": {
                "intitule": texte, "description": texte, "page": {"type": "integer"}}, "required": ["intitule"]},
                "description": "Préconisations du rapport sans équivalent dans la liste des solutions"},
        },
        "required": ["operations"],
    }


def consignes() -> str:
    lignes = [
        "Tu lis un rapport de diagnostic de confort d'été d'une école, réalisé par un bureau d'études. Tu dois "
        f"reporter son contenu dans l'outil « {OUTIL} », qui alimente un outil de passage en travaux pour la collectivité.",
        "",
        "Règles :",
        "- Ne reporte que ce que le rapport dit. N'invente rien, ne complète pas avec des connaissances générales.",
        "- Une opération par solution du catalogue préconisée par le rapport, avec les locaux concernés tels que "
        "nommés dans le rapport (une entrée par local ou par groupe de locaux cité).",
        "- Si une préconisation ne correspond à aucune solution du catalogue, mets-la dans « hors_catalogue » plutôt "
        "que de la forcer dans une solution voisine.",
        "- Pour chaque opération, donne une courte citation du rapport (moins de 25 mots) et la page du PDF.",
        "- Ne reporte aucun coût ni montant : les coûts seront estimés par ailleurs.",
        "- Les points de vigilance sont des phrases courtes, reformulées, utiles à la collectivité.",
        "- Bâtiment : ne renseigne un champ que si le rapport le dit explicitement ; la période de construction est "
        "celle du bâtiment le plus ancien concerné par les travaux.",
        "",
        "Catalogue des solutions (nom exact → ce que cela recouvre) :",
    ]
    for sol, c in travaux.CATALOGUE.items():
        lignes.append(f"- « {sol} » → {c['action']}")
    lignes += ["", "Codes d'alerte possibles (à ne cocher que si le rapport signale ce point) :"]
    for a in _alertes():
        lignes.append(f"- {a} : {REGLES.get(a, {}).get('regle', '')}")
    return "\n".join(lignes)


# ------------------------------------------------------------------ appel à l'API
def analyser(pdf: bytes, cle: str, modele: str | None = None, http=None) -> dict:
    """Envoie le PDF à l'API Claude et renvoie les champs proposés (entrée de l'outil)."""
    if not cle:
        raise LectureImpossible("Le module IA n'est pas configuré : la clé d'accès à l'API est absente des réglages "
                                "de l'application.")
    if not pdf or not pdf.startswith(b"%PDF"):
        raise LectureImpossible("Le fichier n'est pas un PDF lisible.")
    if len(pdf) * 4 / 3 > TAILLE_MAX:
        raise LectureImpossible("Le PDF est trop lourd pour être analysé (plus de 20 Mo environ) : compressez-le ou "
                                "envoyez seulement les pages de préconisations.")
    if http is None:
        import requests
        http = requests.Session()
    corps = {
        "model": modele or MODELE_DEFAUT,
        "max_tokens": 8000,
        "system": consignes(),
        "tools": [{"name": OUTIL, "description": "Reporter le contenu du rapport de diagnostic dans la saisie.",
                   "input_schema": schema()}],
        "tool_choice": {"type": "tool", "name": OUTIL},
        "messages": [{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.standard_b64encode(pdf).decode("ascii")}},
            {"type": "text", "text": "Voici le rapport de diagnostic. Reporte son contenu avec l'outil."}]}],
    }
    try:
        r = http.post(API, json=corps, timeout=DELAI,
                      headers={"x-api-key": cle, "anthropic-version": VERSION_API, "content-type": "application/json"})
    except Exception as e:
        raise LectureImpossible(f"Le service d'IA ne répond pas ({type(e).__name__}). Réessayez dans un instant.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise LectureImpossible(f"Le service d'IA a refusé la demande (code {r.status_code})" + (f" : {msg}" if msg else "."))
    data = r.json()
    bloc = next((b for b in data.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == OUTIL), None)
    if not bloc or not isinstance(bloc.get("input"), dict):
        raise LectureImpossible("La réponse du service d'IA est incomplète : réessayez ou remplissez la saisie à la main.")
    if data.get("stop_reason") == "max_tokens":
        bloc["input"].setdefault("_avertissement", "Réponse tronquée : le rapport est long, vérifiez qu'aucune action ne manque.")
    return bloc["input"]


# ------------------------------------------------------------------ conversion en saisie
def vers_saisie(proposition: dict, nom_fichier: str = "") -> tuple[dict, list[str]]:
    """Convertit la proposition de l'IA en ``{"audit", "batiment", "diagnostic_externe"}`` contrôlés, et renvoie
    les remarques (actions hors catalogue, champs écartés)."""
    remarques = []
    ecole = proposition.get("ecole") or {}
    audit = {k: str(ecole[k]).strip()[:200] for k in ("etablissement", "adresse", "commune", "moa", "date_visite")
             if ecole.get(k)}
    batiment = {}
    for code, v in (proposition.get("batiment") or {}).items():
        if code in CHAMPS_BATIMENT and v in (_question(code).get("options") or []):
            batiment[code] = v
    diag = proposition.get("diagnostic") or {}
    brut = {"source": diag.get("source") or "", "date": diag.get("date") or "", "operations": []}
    vus = set()
    for x in proposition.get("operations") or []:
        if not isinstance(x, dict) or x.get("solution") not in travaux.CATALOGUE:
            remarques.append(f"Action non reconnue écartée : {x.get('solution') if isinstance(x, dict) else x}.")
            continue
        if x["solution"] in vus:  # une même solution citée deux fois : on fusionne les locaux
            op = next(o for o in brut["operations"] if o["solution"] == x["solution"])
            for k in ("locaux", "a_confirmer", "vigilances", "alertes"):
                op[k] = list(dict.fromkeys((op.get(k) or []) + (x.get(k) or [])))
            continue
        vus.add(x["solution"])
        brut["operations"].append({**x, "origine": "ia"})
    externe, notes = travaux.valider_externe(brut)
    remarques += notes
    if audit:
        audit.setdefault("auditeur", externe.get("source", ""))
    for h in proposition.get("hors_catalogue") or []:
        if isinstance(h, dict) and h.get("intitule"):
            remarques.append(f"À classer à la main (sans équivalent dans la liste) : {h['intitule']}"
                             + (f" — {h['description']}" if h.get("description") else "")
                             + (f" (p. {h['page']})" if h.get("page") else ""))
    if proposition.get("_avertissement"):
        remarques.append(proposition["_avertissement"])
    externe["lecture_ia"] = {"fichier": nom_fichier[:200], "date": dt.date.today().strftime("%d/%m/%Y"),
                             "hors_catalogue": [str(h.get("intitule"))[:200] for h in proposition.get("hors_catalogue") or []
                                                if isinstance(h, dict) and h.get("intitule")]}
    return {"audit": audit, "batiment": batiment, "diagnostic_externe": externe}, remarques
