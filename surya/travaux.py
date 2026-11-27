"""Module « passage en travaux » : du diagnostic au plan d'action du maître d'ouvrage.

À partir des résultats du moteur (statuts, règles retenues, alertes par local et par espace), le module :

* regroupe les solutions en **opérations** à l'échelle du bâtiment (une opération = une solution, avec
  les locaux ou espaces où elle est à engager ou à valider) ;
* attribue à chaque opération une **fiche du kit**, un ou plusieurs **CCTP types**, un **niveau** de mise
  en œuvre (A : régie ou devis ; B : consultation avec le CCTP du kit ; C : maîtrise d'œuvre d'abord), un
  **horizon** (étapes du compte rendu, ``rapport.phase``) et un **coût indicatif** ;
* rend un **verdict maîtrise d'œuvre** (règles M1 à M5, modifiable par l'auditeur avec motif) ;
* produit la **feuille de route** du maître d'ouvrage et la liste des **données à compléter** ;
* gère la **validation humaine** : l'auditeur retient ou retire chaque opération (motif obligatoire pour un
  retrait), confirme ou modifie le verdict MOE ; un chargé de mission ou un économe de flux vise.

Les choix de l'auditeur sont stockés dans ``donnees["travaux"]`` (exporté avec la saisie). Aucune
dépendance à Streamlit. Aucun coût n'est donné pour l'instant : les ordres de grandeur seront fournis par une
base de données de coûts (voir ``_cout``). Les niveaux A/B/C, les horizons et les règles M1 à M5 sont des propositions
ACTEE (pas des éléments de la méthode SURYA), à valider.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import moteur
from .moteur import A_OPTIMISER, RECOMMANDE, REGLES, SOUS_RESERVE

KIT = Path(__file__).parent / "kit"
FICHES = {int(k): v for k, v in json.loads((KIT / "fiches.json").read_text(encoding="utf-8")).items()
          if not k.startswith("_")}

# ------------------------------------------------------------------ hypothèses de chiffrage
SURFACE_BAIE_TYPE = 2.0      # m² par baie, faute de métré (le diagnostic compte les baies, il ne les mesure pas)
LARGEUR_BAIE_TYPE = 1.2      # m linéaire de casquette par baie
SEUIL_MOE_DEFAUT = 100_000   # € HT : au-delà, la règle M5 recommande une MOE (à fixer par ACTEE)

COUTS_DISPONIBLES = False  # passera à True quand la base de données de coûts sera branchée (voir _cout)
MESSAGE_COUTS = ("Coûts à estimer : les ordres de grandeur seront stabilisés par une base de données de coûts, "
                 "en cours de constitution. Aucun montant n'est donné à ce stade.")

NIVEAUX = {
    "A": "Régie ou devis simples, à partir de la fiche du kit",
    "B": "Consultation d'entreprises avec le CCTP type du kit",
    "C": "Étude ou maîtrise d'œuvre d'abord",
}
HORIZONS = {
    1: "Dès maintenant",
    2: "Petits travaux, avant l'été",
    3: "Travaux sur le bâtiment, à programmer",
}
CCTP = {
    1: "CCTP 1 — Électricité : brasseurs d'air et éclairage LED",
    2: "CCTP 2 — Protections solaires extérieures mobiles",
    3: "CCTP 3 — Films solaires",
    4: "CCTP 4 — Sécurisation de la ventilation naturelle nocturne",
    5: "CCTP 5 — Commande au mainteneur : mode été de la ventilation",
    6: "CCTP 6 — Audit de régulation de la ventilation",
    7: "CCTP 7 — Diagnostic de toiture",
    8: "CCTP 8 — Isolation de combles perdus par soufflage",
    9: "CCTP 9 — Voiles d'ombrage de la cour",
    10: "CCTP 10 — Repérage amiante (et plomb) avant travaux",
    11: "CCTP 11 — Diagnostic de structure",
    12: "CCTP 12 — Contrôle technique : solidité et sécurité incendie",
    13: "CCTP 13 — Coordination sécurité et protection de la santé (CSPS)",
    "MOE": "CCTP MOE — Maîtrise d'œuvre pour l'adaptation (volets activés selon les opérations)",
}
# Catégorie de chaque pièce : prestation préalable (diagnostic, contrôle, coordination) ou travaux.
CATEGORIE = {6: "prealable", 7: "prealable", 10: "prealable", 11: "prealable", 12: "prealable", 13: "prealable",
             "MOE": "moe"}
CATEGORIES = {
    "moe": "Maîtrise d'œuvre",
    "prealable": "Prestations préalables (diagnostics, contrôle, coordination)",
    "travaux": "Travaux et commandes du maître d'ouvrage",
    "reference": "CCTP travaux du kit, à transmettre à la maîtrise d'œuvre comme base",
}
# Actions d'organisation ou de réglage, sans travaux : toujours conduites par le maître d'ouvrage, même avec
# une maîtrise d'œuvre (la ventilation naturelle nocturne seulement au niveau A, c'est-à-dire sans équipement).
NON_TRAVAUX = ("Occupation", "Équipements", "Par ventilation mécanique nocturne", "Adaptation des usages")
# Opérations qui chargent ou percent la structure, ou modifient les abords d'un ERP.
STRUCTURE = ("Protections horizontales", "Sur vérandas et/ou verrières", "Ombrage rapporté adossé au bâtiment",
             "Adaptation d'un préau existant")
ALERTES_STRUCTURE = ("BR-AL", "VV-AL", "OA-AL2", "PR-AL2")

FACADE = ("Protections verticales", "Protections horizontales", "Sur fenêtres de toiture",
          "Sur vérandas et/ou verrières", "Ombrage rapporté adossé au bâtiment")

# Leviers d'action, dans l'ordre de la démarche (protéger, décharger, rafraîchir les occupants) : texte
# pédagogique repris dans le pré-programme et l'interface.
LEVIERS = {
    "Protections solaires extérieures": (
        "Arrêter le soleil avant la vitre",
        "Le soleil qui entre par les fenêtres est la première source de surchauffe. Une protection placée à "
        "l'extérieur arrête la chaleur avant qu'elle n'entre ; à l'intérieur, elle est déjà dans la pièce."),
    "Réduction de la surchauffe par la toiture": (
        "Limiter la chaleur qui traverse la toiture",
        "Sous une toiture mal isolée ou très exposée, les locaux du dernier niveau chauffent fortement. Traiter la "
        "toiture apporte aussi un gain en hiver, mais suppose un diagnostic préalable."),
    "Décharge thermique nocturne": (
        "Évacuer la nuit la chaleur accumulée le jour",
        "La nuit, l'air extérieur est plus frais : ventiler à ce moment-là vide le bâtiment de la chaleur du jour, "
        "à condition de pouvoir le faire en sécurité (intrusion, pluie, alarme)."),
    "Brasseurs d'air plafonniers": (
        "Rendre la chaleur supportable",
        "Le brasseur ne refroidit pas l'air, mais l'air en mouvement donne une sensation de fraîcheur pour une "
        "consommation très faible. Il complète les protections, il ne les remplace pas."),
    "Réduction des charges internes": (
        "Réduire la chaleur produite à l'intérieur",
        "Éclairage ancien, appareils qui chauffent, forte densité d'occupants : ces apports s'ajoutent à ceux du "
        "soleil. Ce sont souvent des actions simples, parfois sans travaux."),
    "Adaptation des espaces extérieurs": (
        "Créer de l'ombre dans la cour",
        "Une cour ombragée offre une zone refuge pour les récréations et protège les façades qui la bordent. Les "
        "dispositifs rapides (voiles, préau) préparent les solutions durables (arbres)."),
    "Rafraîchissement actif": (
        "Rafraîchir un local refuge, en dernier recours",
        "Un rafraîchissement actif ne s'envisage qu'une fois les apports solaires traités et la décharge nocturne "
        "organisée ; il se limite en général à un local refuge, avec une consigne raisonnable."),
    "Organisation et usages": (
        "Adapter l'organisation pendant les épisodes de chaleur",
        "Gestes, horaires, local refuge : ces mesures d'organisation ne relèvent pas de travaux, mais complètent "
        "les opérations sur le bâtiment."),
}

RISQUES_SANS_MOE = [
    "des travaux conçus séparément peuvent se contrarier : isoler une toiture sans protéger les baies ni permettre "
    "la décharge nocturne, par exemple, enferme la chaleur ;",
    "la collectivité porte seule la conception, le choix des solutions et la coordination des entreprises ;",
    "les vérifications de structure, d'urbanisme et de sécurité incendie risquent d'être oubliées ou faites trop tard ;",
    "sans estimation ni analyse des offres par un professionnel, les écarts de prix et les dérives de coût sont plus "
    "fréquents.",
]

# Structures qui peuvent accompagner une collectivité sans ingénierie interne (annuaire local à venir).
ACCOMPAGNEMENT = [
    "l'économe de flux ou le conseiller en énergie partagé (CEP) du territoire, s'il existe ;",
    "l'agence technique départementale ;",
    "le conseil d'architecture, d'urbanisme et de l'environnement (CAUE) ;",
    "l'agence locale de l'énergie et du climat (ALEC) ;",
    "le syndicat départemental d'énergie.",
]

# solution -> paramètres. « niveau » : niveau de base, ajusté par ``_niveau``.
CATALOGUE = {
    "Mise en place de brasseurs d'air plafonniers": dict(
        fiche=1, niveau="A", prestataire="Électricien", action="Installer des brasseurs d'air plafonniers", cout=None),
    "Par ventilation naturelle nocturne": dict(
        fiche=5, niveau="A", prestataire="Régie, puis menuisier ou serrurier si équipement",
        action="Ventiler la nuit en sécurité (protocole, puis grilles ou persiennes)", cout=None),
    "Par ventilation mécanique nocturne": dict(
        fiche=6, niveau="A", prestataire="Mainteneur de l'installation",
        action="Régler la ventilation en mode été (by-pass, surventilation nocturne)", cout=None),
    "Protections verticales": dict(
        fiche=2, niveau="B", prestataire="Entreprise de fermetures et protections solaires",
        action="Poser des protections solaires extérieures mobiles (stores, BSO)", cout=None),
    "Protections horizontales": dict(
        fiche=3, niveau="C", prestataire="Maîtrise d'œuvre, puis serrurier-métallier",
        action="Poser ou prolonger des casquettes au-dessus des baies sud", cout=None),
    "Films solaires": dict(
        fiche=4, niveau="A", prestataire="Poseur de films agréé",
        action="Poser des films solaires (solution provisoire ou de repli)", cout=None),
    "Sur fenêtres de toiture": dict(
        fiche=2, niveau="B", prestataire="Couvreur ou menuisier",
        action="Protéger les fenêtres de toit par l'extérieur", cout=None),
    "Sur vérandas et/ou verrières": dict(
        fiche=3, niveau="C", prestataire="Maîtrise d'œuvre, puis entreprise spécialisée",
        action="Occulter ou protéger la verrière", cout=None),
    "Toiture": dict(
        fiche=7, niveau="C", prestataire="Bureau d'études (diagnostic), puis couvreur, étancheur ou isolateur",
        action="Réduire la surchauffe par la toiture (diagnostic puis isolation)", cout=None),
    "Occupation": dict(
        fiche=10, niveau="A", prestataire="Collectivité et direction d'école",
        action="Réorganiser l'occupation (densité, horaires)", cout=None),
    "Éclairage": dict(
        fiche=10, niveau="A", prestataire="Électricien", action="Passer l'éclairage en LED", cout=None),
    "Équipements": dict(
        fiche=10, niveau="A", prestataire="Collectivité",
        action="Déplacer ou mettre en veille les équipements qui chauffent", cout=None),
    "Ombrage rapporté adossé au bâtiment": dict(
        fiche=8, niveau="B", prestataire="Entreprise de structures textiles",
        action="Poser une voile d'ombrage adossée à la façade", cout=None),
    "Adaptation d'un préau existant": dict(
        fiche=8, niveau="B", prestataire="Couvreur, bureau d'études structure",
        action="Adapter le préau (toiture claire, occultation)", cout=None),
    "Ombrage autoportant ou végétal de la cour": dict(
        fiche=8, niveau="B", prestataire="Entreprise de structures textiles ; paysagiste à terme",
        action="Ombrager la cour (voiles sur mâts, puis arbres)", cout=None),
    # Solutions que la méthode SURYA ne produit pas, mais que proposent des diagnostics externes
    # (par exemple les diagnostics « plan canicule » financés par la Banque des Territoires).
    "Végétalisation et désimperméabilisation de la cour": dict(
        fiche=9, niveau="C", prestataire="Maîtrise d'œuvre paysagiste, puis entreprises de terrassement et de paysage",
        action="Végétaliser et désimperméabiliser la cour", cout=None),
    "Création d'une ventilation mécanique": dict(
        fiche=6, niveau="C", prestataire="Bureau d'études fluides (faisabilité), puis entreprise de génie climatique",
        action="Créer une ventilation mécanique (par exemple double flux décentralisée)", cout=None,
        bref="Une ventilation mécanique assure d'abord la qualité de l'air ; avec une surventilation nocturne ou un "
             "free-cooling, elle aide aussi à évacuer la chaleur la nuit. Elle ne produit pas de froid. Une étude de "
             "faisabilité (acoustique, percements, électricité, maintenance) précède les travaux."),
    "Rafraîchissement d'un local refuge": dict(
        fiche=6, niveau="B", prestataire="Entreprise de génie climatique",
        action="Rafraîchir un local refuge (pompe à chaleur air-air)", cout=None,
        bref="Un équipement limité à un local refuge permet d'accueillir les enfants pendant une canicule. À "
             "n'envisager qu'après les protections solaires et la décharge nocturne, avec une consigne raisonnable "
             "et en vérifiant la puissance électrique disponible."),
    "Protections solaires intérieures": dict(
        fiche=2, niveau="A", prestataire="Fournisseur-poseur de stores intérieurs",
        action="Poser des protections solaires intérieures (à défaut de protection extérieure)", cout=None,
        bref="Un store intérieur clair réduit l'éblouissement et une partie des apports, mais laisse la chaleur entrer "
             "dans la pièce : c'est une solution d'appoint, pour des façades déjà bien protégées ou en attendant une "
             "protection extérieure."),
    "Adaptation des usages": dict(
        fiche=10, niveau="A", prestataire="Collectivité et direction d'école",
        action="Adapter l'organisation en période de chaleur (gestes, horaires, local refuge)", cout=None,
        bref="Gestes, horaires adaptés, local refuge, information des familles : une organisation formalisée pour les "
             "épisodes de chaleur, sans travaux, qui s'appuie sur les ressources existantes (commune, académie)."),
}

# Famille (levier) de chaque solution, pour les diagnostics externes (avec la méthode SURYA, elle vient du moteur).
GROUPES = {
    "Mise en place de brasseurs d'air plafonniers": "Brasseurs d'air plafonniers",
    "Par ventilation naturelle nocturne": "Décharge thermique nocturne",
    "Par ventilation mécanique nocturne": "Décharge thermique nocturne",
    "Création d'une ventilation mécanique": "Décharge thermique nocturne",
    "Protections verticales": "Protections solaires extérieures",
    "Protections horizontales": "Protections solaires extérieures",
    "Films solaires": "Protections solaires extérieures",
    "Sur fenêtres de toiture": "Protections solaires extérieures",
    "Sur vérandas et/ou verrières": "Protections solaires extérieures",
    "Protections solaires intérieures": "Protections solaires extérieures",
    "Toiture": "Réduction de la surchauffe par la toiture",
    "Occupation": "Réduction des charges internes",
    "Éclairage": "Réduction des charges internes",
    "Équipements": "Réduction des charges internes",
    "Ombrage rapporté adossé au bâtiment": "Adaptation des espaces extérieurs",
    "Adaptation d'un préau existant": "Adaptation des espaces extérieurs",
    "Ombrage autoportant ou végétal de la cour": "Adaptation des espaces extérieurs",
    "Végétalisation et désimperméabilisation de la cour": "Adaptation des espaces extérieurs",
    "Rafraîchissement d'un local refuge": "Rafraîchissement actif",
    "Adaptation des usages": "Organisation et usages",
}
# Horizon par défaut (diagnostics externes) : 1 dès maintenant, 2 avant l'été, 3 à programmer.
HORIZON_DEFAUT = {s: 1 for s in ("Occupation", "Équipements", "Adaptation des usages")} | {
    s: 3 for s in ("Protections horizontales", "Sur vérandas et/ou verrières", "Toiture", "Ombrage rapporté adossé au bâtiment",
                   "Adaptation d'un préau existant", "Végétalisation et désimperméabilisation de la cour",
                   "Création d'une ventilation mécanique")}
# Alertes de la méthode proposées à la saisie d'un diagnostic externe, par solution.
ALERTES_PAR_SOLUTION = {
    "Mise en place de brasseurs d'air plafonniers": ["BR-AL"],
    "Par ventilation naturelle nocturne": ["VN-AL1", "VN-AL2"],
    "Sur fenêtres de toiture": ["FT-AL"],
    "Sur vérandas et/ou verrières": ["VV-AL"],
    "Ombrage rapporté adossé au bâtiment": ["OA-AL2", "OA-AL3"],
    "Adaptation d'un préau existant": ["PR-AL1", "PR-AL2", "PR-AL3"],
    "Ombrage autoportant ou végétal de la cour": ["EX-AL"],
    "Toiture": ["PR-AL3"],
}


# ------------------------------------------------------------------ utilitaires
def _n(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _oui(b: dict, code: str) -> bool:
    return b.get(code) == "Oui"


def contexte(donnees: dict) -> dict:
    """Indicateurs du bâtiment utiles aux niveaux, aux CCTP et à la feuille de route."""
    b = donnees.get("batiment") or {}
    return {
        # C2-04 : période inconnue = suspicion d'amiante, comme PR-AL3 (règle du doute) ; seul « Après 1997 » l'écarte
        "amiante": b.get("B-01") != "Après 1997",
        "plomb": b.get("B-01") == "Avant 1948",
        "periode": b.get("B-01") or "non renseignée",
        "patrimoine": _oui(b, "B-05") or _oui(b, "B-06"),
        "ite": b.get("B-04") == "ITE (isolation par l'extérieur)",
        "alarme": _oui(b, "B-08"),
        "ventilation": b.get("B-10") if _oui(b, "B-09") else None,
        "double_flux": _oui(b, "B-09") and b.get("B-10") == "Double flux",
        "simple_flux": _oui(b, "B-09") and b.get("B-10") == "Simple flux",
        "automate_limite": b.get("B-15") == "Non" or b.get("B-14") == "Non",
        "toiture": b.get("B-18"),
        "combles_perdus": b.get("B-21") == "Oui" and b.get("B-22") == "En comble perdu",
        "combles_accessibles": b.get("B-26") == "Oui",
    }


def _baies(entree: dict, orientations=None) -> int:
    """Nombre de baies relevées dans le local (tous murs, ou orientations données)."""
    total = 0
    for m in (entree.get("murs") or [])[:moteur.NB_MURS_MAX]:
        if orientations and m.get("orientation") not in orientations:
            continue
        for n in (m.get("baies") or {}).values():
            if _n(n):
                total += int(n)
    return total


def _types_alertes(alertes) -> set:
    from .rapport import TYPES_ALERTE
    return {TYPES_ALERTE.get(a, "INFO") for a in alertes}


# ------------------------------------------------------------------ quantités et coûts
def _quantite(solution: str, entites: list[dict], donnees: dict, ctx: dict) -> tuple[float | None, str, list[str]]:
    """Quantité estimée pour le chiffrage : (valeur, unité, hypothèses)."""
    hyp = []
    if solution == "Mise en place de brasseurs d'air plafonniers":
        q = sum(1 for e in entites if e["statut"] != A_OPTIMISER)  # brasseurs existants à remettre en service : non chiffré
        hyp.append("nombre de locaux à équiper ; nombre d'appareils par local défini par l'entreprise (calepinage)")
        return (q or None), "local équipé", hyp
    if solution in ("Protections verticales", "Films solaires"):
        orients = None if solution == "Films solaires" else ("E", "SE", "S", "SO", "O")
        n = sum(_baies(e["entree"], orients) for e in entites)
        hyp.append(f"{n} baie(s) relevée(s) × {SURFACE_BAIE_TYPE:g} m² par baie, à remplacer par le métré")
        return (n * SURFACE_BAIE_TYPE or None), "m²", hyp
    if solution == "Protections horizontales":
        n = sum(_baies(e["entree"], ("SE", "S", "SO")) for e in entites)
        hyp.append(f"{n} baie(s) au sud × {LARGEUR_BAIE_TYPE:g} m de casquette, à remplacer par le métré")
        return (round(n * LARGEUR_BAIE_TYPE, 1) or None), "m linéaire", hyp
    if solution in ("Toiture", "Éclairage"):
        s = sum(_n(e["entree"].get("L-03")) or 0 for e in entites)
        hyp.append("surface au sol des locaux concernés" + (" (sous toiture)" if solution == "Toiture" else ""))
        return (s or None), "m²", hyp
    if solution == "Ombrage autoportant ou végétal de la cour":
        manque = 0.0
        p = moteur.parametres(donnees.get("parametres"))  # C2-11 : mêmes seuils que EX-AL, y compris ceux modifiés dans les Réglages
        for e in entites:
            x = e["entree"]
            eff, ombre = _n(x.get("E-06")), _n(x.get("E-14")) or 0
            cible = p["P_OMBRE_ELEM"] * eff if eff else 0
            if "Maternelle" in (x.get("E-04") or []):
                cible = max(cible, p["P_OMBRE_MAT_2"] if (_n(x.get("E-07")) or 0) > p["P_OMBRE_MAT_CL"]
                            else p["P_OMBRE_MAT_1"])
            manque += max(0.0, cible - ombre)
        hyp.append(f"écart à {p['P_OMBRE_ELEM']:g} m² d'ombre par enfant ({p['P_OMBRE_MAT_1']:g} ou "
                   f"{p['P_OMBRE_MAT_2']:g} m² en maternelle), ombre existante hors végétaux déduite")
        return (round(manque) or None), "m²", hyp
    if solution in ("Par ventilation mécanique nocturne", "Occupation", "Équipements"):
        return 1, "forfait", hyp
    return None, "", hyp


def _cout(solution: str, qte, ctx: dict) -> dict | None:
    """Coût indicatif : aucun pour l'instant. Les ordres de grandeur ont été retirés ; ils seront fournis par
    une base de données de coûts (à constituer), à brancher ici : {"bas", "haut", "source", "unitaire"}."""
    return None


# ------------------------------------------------------------------ niveaux et CCTP
def _niveau(solution: str, entites: list[dict], ctx: dict) -> tuple[str, list[str]]:
    """Niveau A, B ou C et ses raisons."""
    niv, raisons = CATALOGUE[solution]["niveau"], []
    regles = {e["regle"] for e in entites if e["regle"]}
    alertes = {a for e in entites for a in e["alertes"]}
    if solution == "Mise en place de brasseurs d'air plafonniers":
        if any(e["entree"].get("PL-01") in moteur.FAUX_PLAFONDS for e in entites) or "BS-3" in regles:
            niv = "B"
            raisons.append("faux plafond ou hauteur limite : ancrage et hauteur à faire vérifier")
    if solution == "Par ventilation naturelle nocturne":
        if "VN-AL1" in alertes or regles & {"VN-3", "VN-4"}:
            niv = "B"
            raisons.append("équipements de sécurisation ou adaptation de l'alarme nécessaires")
    if solution == "Par ventilation mécanique nocturne" and ctx["automate_limite"]:
        raisons.append("automate limité : audit de régulation à prévoir si le réglage ne suffit pas")
    if solution == "Toiture" and ctx["combles_perdus"] and ctx["combles_accessibles"]:
        niv = "B"
        raisons.append("combles perdus accessibles : isolation par soufflage possible après diagnostic")
    if solution == "Ombrage autoportant ou végétal de la cour" and any(e["statut"] == A_OPTIMISER for e in entites):
        raisons.append("structures ou arbres existants à compléter")
    if "AL" in _types_alertes(alertes):
        niv = "C"
        raisons.append("alerte maîtrise d'œuvre : " + ", ".join(sorted(a for a in alertes
                                                                         if _types_alertes([a]) == {"AL"})))
    if ctx["patrimoine"] and solution in FACADE and niv != "C":
        niv = "C"
        raisons.append("bâtiment protégé ou en abords de monument historique")
    return niv, raisons


def _cctp(solution: str, niveau: str, ctx: dict) -> list:
    """CCTP du kit propres à l'opération (la maîtrise d'œuvre et les prestations préalables communes à
    plusieurs opérations sont ajoutées par ``pieces``)."""
    if niveau == "C":
        return [7] if solution == "Toiture" else []
    return {
        "Mise en place de brasseurs d'air plafonniers": [1],
        "Éclairage": [1],
        "Protections verticales": [2],
        "Sur fenêtres de toiture": [2],
        "Films solaires": [3],
        "Par ventilation naturelle nocturne": [4] if niveau == "B" else [],
        "Par ventilation mécanique nocturne": [5] + ([6] if ctx["automate_limite"] else []),
        "Toiture": [7] + ([8] if ctx["combles_perdus"] else []),
        "Ombrage rapporté adossé au bâtiment": [9],
        "Ombrage autoportant ou végétal de la cour": [9],
    }.get(solution, [])


# ------------------------------------------------------------------ opérations
def _horizon(entites: list[dict], niveau: str) -> int:
    """Étape du compte rendu (``rapport.phase``) la plus précoce, bornée par le niveau : une consultation
    (B) ne se fait pas « dès maintenant », une maîtrise d'œuvre (C) se programme."""
    h = min(e["phase"] for e in entites)
    return 3 if niveau == "C" else max(h, 2) if niveau == "B" else h


def _entite(e: dict) -> dict:
    x, s = e["x"], e["s"]
    regle = next((x["blocs"][b]["regle"] for b in s["blocs"] if x["blocs"][b]["regle"]), None)
    return {"nom": e["nom"], "statut": e["statut"], "phase": e["phase"], "entree": e["entree"],
            "regle": regle, "libelle_regle": REGLES[regle]["regle"] if regle in REGLES else "",
            "alertes": list(s["alertes"]),
            "vigilances": [(a, REGLES[a]["regle"] if a in REGLES else a) for a in s["alertes"]]}


def operations(donnees: dict, res: dict | None = None) -> list[dict]:
    """Opérations proposées par l'outil, avant les choix de l'auditeur, dans l'ordre des horizons."""
    if externe(donnees):
        return _operations_externes(donnees)
    from .rapport import _bilan
    res = res or moteur.calculer(donnees)
    ctx = contexte(donnees)
    ops = []
    for b in _bilan(res, donnees):
        sol = b["solution"]
        if sol not in CATALOGUE:
            continue
        a_engager = [_entite(e) for e in b["engager"]]
        a_valider = [_entite(e) for e in b["valider"]]
        entites = a_engager + a_valider
        if not entites:
            continue
        niv, raisons = _niveau(sol, entites, ctx)
        qte, unite, hyp = _quantite(sol, entites, donnees, ctx)
        c = CATALOGUE[sol]
        ops.append({
            "id": sol, "solution": sol, "libelle": b["libelle"], "groupe": b["groupe"], "action": c["action"],
            "fiche": c["fiche"], "titre_fiche": FICHES[c["fiche"]]["titre"], "prestataire": c["prestataire"],
            "niveau": niv, "raisons_niveau": raisons, "cctp": _cctp(sol, niv, ctx),
            "horizon": _horizon(entites, niv),
            "a_engager": a_engager, "a_valider": a_valider,
            "completer": [e["nom"] for e in b["completer"]],
            "quantite": qte, "unite": unite, "hypotheses": hyp, "cout": _cout(sol, qte, ctx),
        })
    ops.sort(key=lambda o: (o["horizon"], "ABC".index(o["niveau"]), o["fiche"]))
    _films_en_repli(ops)
    return ops


def externe(donnees: dict) -> dict | None:
    """Diagnostic réalisé hors de la méthode SURYA (saisie simplifiée), ou None."""
    de = donnees.get("diagnostic_externe")
    return de if isinstance(de, dict) and de.get("operations") else None


def _entite_externe(nom: str, statut: str, sol: str, x: dict) -> dict:
    alertes = [a for a in x.get("alertes") or [] if a in REGLES]
    vig = [(a, REGLES[a]["regle"]) for a in alertes] + [("Diagnostic", v) for v in x.get("vigilances") or [] if v]
    regle = "BS-3" if x.get("hauteur_limite") and sol == "Mise en place de brasseurs d'air plafonniers" else None
    return {"nom": nom, "statut": statut, "phase": int(x.get("horizon") or HORIZON_DEFAUT.get(sol, 2)),
            "entree": {}, "regle": regle, "libelle_regle": REGLES[regle]["regle"] if regle in REGLES else "",
            "alertes": alertes, "vigilances": vig}


def _operations_externes(donnees: dict) -> list[dict]:
    """Opérations d'un diagnostic externe : mêmes niveaux, horizons, CCTP et validation que la méthode SURYA."""
    ctx = contexte(donnees)
    ops = []
    for x in externe(donnees)["operations"]:
        sol = x.get("solution")
        if sol not in CATALOGUE:
            continue
        a_engager = [_entite_externe(n, RECOMMANDE, sol, x) for n in x.get("locaux") or []]
        a_valider = [_entite_externe(n, SOUS_RESERVE, sol, x) for n in x.get("a_confirmer") or []]
        if not (a_engager or a_valider):
            a_engager = [_entite_externe("Bâtiment (non précisé)", RECOMMANDE, sol, x)]
        entites = a_engager + a_valider
        niv, raisons = _niveau(sol, entites, ctx)
        if x.get("niveau") in NIVEAUX and x["niveau"] != niv:
            raisons = raisons + [f"niveau fixé à la saisie du diagnostic ({x['niveau']})"]
            niv = x["niveau"]
        c = CATALOGUE[sol]
        ops.append({
            "id": sol, "solution": sol, "libelle": x.get("libelle") or sol, "groupe": GROUPES.get(sol, "Autres"),
            "action": c["action"], "fiche": c["fiche"], "titre_fiche": FICHES[c["fiche"]]["titre"],
            "prestataire": c["prestataire"], "niveau": niv, "raisons_niveau": raisons, "cctp": _cctp(sol, niv, ctx),
            "horizon": _horizon(entites, niv), "a_engager": a_engager, "a_valider": a_valider,
            "completer": [], "quantite": None, "unite": "", "hypotheses": [], "cout": None,
            "commentaire": x.get("commentaire") or "",
        })
    ops.sort(key=lambda o: (o["horizon"], "ABC".index(o["niveau"]), o["fiche"]))
    _films_en_repli(ops)
    return ops


def _films_en_repli(ops: list[dict]):
    """Fiche 4 : le film solaire est une solution de repli. Si chaque local concerné reçoit aussi une
    protection extérieure, l'outil propose de ne pas retenir les films (l'auditeur peut revenir dessus)."""
    films = next((o for o in ops if o["solution"] == "Films solaires"), None)
    if not films:
        return
    proteges = {e["nom"] for o in ops if o["solution"] in ("Protections verticales", "Protections horizontales")
                for e in o["a_engager"] + o["a_valider"]}
    locaux = {e["nom"] for e in films["a_engager"] + films["a_valider"]}
    films["couverts"] = sorted(locaux & proteges)
    if locaux and locaux <= proteges:
        films["defaut"] = {"retenue": False, "motif": "Proposition de l'outil : tous les locaux reçoivent une "
                           "protection extérieure ; le film n'est utile qu'en provisoire (fiche 4)."}


# ------------------------------------------------------------------ verdict MOE
def verdict_moe(retenues: list[dict], ctx: dict, seuil: float = SEUIL_MOE_DEFAUT) -> tuple[bool, list[str]]:
    """Règles M1 à M5 (référentiel ACTEE) appliquées aux opérations retenues."""
    raisons = []
    c = [o for o in retenues if o["niveau"] == "C"]
    if c:
        raisons.append("M1 — opération(s) de niveau C : " + ", ".join(o["libelle"] for o in c))
    familles = {o["groupe"] for o in retenues if o["niveau"] in ("B", "C") and o["groupe"] in (
        "Protections solaires extérieures", "Réduction de la surchauffe par la toiture",
        "Adaptation des espaces extérieurs") and o["solution"] != "Films solaires"}
    if len(familles) >= 2:
        raisons.append("M2 — plusieurs familles touchent l'enveloppe, la toiture ou les extérieurs : "
                       + ", ".join(sorted(familles)))
    from .rapport import TYPES_ALERTE
    structure = sorted({a for o in retenues for e in o["a_engager"] + o["a_valider"] for a in e["alertes"]
                        if a in ("VV-AL", "OA-AL2", "PR-AL2")})
    if structure:
        raisons.append("M3 — alerte de structure : " + ", ".join(structure))
    if ctx["patrimoine"] and any(o["solution"] in FACADE for o in retenues):
        raisons.append("M4 — bâtiment protégé ou en abords de monument historique, avec des travaux de façade")
    haut = sum((o["cout"] or {}).get("haut", 0) for o in retenues)
    if COUTS_DISPONIBLES and haut > seuil:
        raisons.append(f"M5 — coût haut estimé ({_euros(haut)}) supérieur au seuil de {_euros(seuil)}")
    return bool(raisons), raisons


def _euros(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


# ------------------------------------------------------------------ feuille de route
def feuille_de_route(retenues: list[dict], moe: bool, ctx: dict, completer: dict,
                     accompagnement: dict | None = None) -> list[dict]:
    """Tâches du maître d'ouvrage : {phase, quoi, qui, quand, sortie}."""
    t, accompagnement = [], accompagnement or {}

    def ajout(phase, quoi, qui, quand, sortie):
        t.append({"phase": phase, "quoi": quoi, "qui": qui, "quand": quand, "sortie": sortie})

    ajout("Décider", "Présenter le pré-programme aux élus et arrêter les opérations retenues", "Élu référent",
          "Sous 1 mois", "Décision de principe")
    ajout("Décider", "Désigner un référent travaux à la collectivité et un correspondant à l'école", "Collectivité",
          "Sous 1 mois", "Référents nommés")
    ajout("Décider", "Inscrire les crédits (fonctionnement pour la régie et les réglages, investissement pour "
          "les travaux)", "Finances", "Budget de l'année", "Lignes budgétaires")
    if completer:
        ajout("Vérifier", "Compléter les données manquantes : " + " ; ".join(
            f"{n} ({', '.join(s)})" for n, s in completer.items()), "Services techniques", "Sous 1 mois",
            "Statuts « sous réserve » levés")
    sols = {o["solution"] for o in retenues}
    alertes = {a for o in retenues for e in o["a_engager"] + o["a_valider"] for a in e["alertes"]}
    p = pieces(retenues, moe, ctx)
    if accompagnement.get("structures"):
        ajout("Décider", "Contacter les structures d'ingénierie du territoire listées dans le pré-programme pour leur "
              "demander si elles peuvent accompagner le passage en travaux", "Élu référent ou secrétaire de mairie",
              "Sous 1 mois", "Réponses et, le cas échéant, convention d'accompagnement")
    elif accompagnement.get("ingenierie") in ("non", "nsp"):
        ajout("Décider", "Se faire accompagner par une structure d'ingénierie du territoire (économe de flux ou "
              "conseiller en énergie partagé, agence technique départementale, CAUE, agence locale de l'énergie, "
              "syndicat d'énergie) pour piloter la suite", "Élu référent", "Sous 1 mois", "Accompagnement en place")
    if moe:
        ajout("Décider", "Recruter une maîtrise d'œuvre avec le CCTP MOE du kit ; lui confier toutes les opérations "
              "de travaux (volets : " + ", ".join(sorted({_volet(o) for o in p.get("MOE", {}).get("operations", [])})
                                                 or ["à préciser"]) + ")",
              "Collectivité", "Consultation dans les 3 mois", "MOE notifiée")
    if 10 in p:
        ajout("Vérifier", "Faire réaliser le repérage amiante avant travaux (CCTP 10)"
              + (" et la recherche de plomb" if ctx["plomb"] else ""), "Collectivité, opérateur certifié",
              "Avant la consultation des entreprises", "Rapport de repérage")
    if 11 in p:
        ajout("Vérifier", "Faire vérifier la structure par un bureau d'études (CCTP 11)", "Bureau d'études structure",
              "Avant la consultation des entreprises", "Note de vérification")
    if 12 in p:
        ajout("Vérifier", "Désigner un contrôleur technique, missions solidité et sécurité incendie (CCTP 12)",
              "Collectivité", "Avant la conception détaillée", "Contrôleur désigné")
    if 13 in p:
        ajout("Vérifier", "Désigner un coordonnateur SPS : plusieurs entreprises interviendront, même successivement (CCTP 13)",
              "Collectivité", "Avant la consultation des entreprises", "Coordonnateur désigné")
    if sols & {"Protections verticales", "Protections horizontales", "Sur vérandas et/ou verrières",
               "Ombrage rapporté adossé au bâtiment"}:
        ajout("Vérifier", "Déposer la déclaration préalable pour les travaux qui modifient l'aspect extérieur"
              + (" ; consulter l'architecte des Bâtiments de France" if ctx["patrimoine"] else ""),
              "Secrétariat de mairie", "Avant la consultation", "Récépissé ou arrêté")
    if "BR-AL" in alertes:
        ajout("Vérifier", "Faire vérifier par un électricien l'installation et l'ancrage des brasseurs",
              "Électricien", "Avant la consultation", "Note de faisabilité")
    if "VN-AL1" in alertes or "Par ventilation naturelle nocturne" in sols:
        ajout("Vérifier", "Obtenir l'accord écrit de l'assureur sur l'ouverture nocturne et adapter l'alarme",
              "Collectivité, assureur", "Avant l'été", "Accord écrit")
    if sols & {"Ombrage rapporté adossé au bâtiment", "Ombrage autoportant ou végétal de la cour"}:
        ajout("Vérifier", "Déclarer les travaux à proximité des réseaux (DT) avant tout scellement de mât",
              "Collectivité", "Avant les travaux", "Récépissés DT")
    confiees = p.get("MOE", {}).get("operations", [])
    for h in (1, 2, 3):
        for o in [o for o in retenues if o["horizon"] == h]:
            pieces_op = ", ".join(CCTP[c].split(" — ")[0] for c in o["cctp"]) or "fiche du kit"
            if o in confiees:
                ajout(HORIZONS[h], f"{o['action']} : confiée à la maîtrise d'œuvre"
                      + (" (tranche rapide possible avant l'été)" if h < 3 else ""), "Maîtrise d'œuvre",
                      "Selon le calendrier de la MOE", "Travaux réceptionnés")
                continue
            if o["niveau"] == "A":
                quoi, quand = f"{o['action']} : en régie ou sur devis ({pieces_op})", (
                    "Dès maintenant" if h == 1 else "Commande avant avril, réalisation aux vacances de printemps")
            elif o["niveau"] == "B":
                quoi, quand = f"{o['action']} : consulter avec {pieces_op}", "Consultation d'ici mars, travaux l'été"
            else:
                quoi, quand = (f"{o['action']} : faire concevoir par un bureau d'études ou un architecte avant de consulter "
                               "(maîtrise d'œuvre non retenue)", "Programmation pluriannuelle")
            ajout(HORIZONS[h], quoi, o["prestataire"], quand, "Commande, puis PV de réception")
    ajout("Mesurer", "Relever les températures dans deux locaux témoins l'été avant et l'été après, et les "
          "transmettre à l'économe de flux", "Correspondant école", "Chaque été", "Gain mesuré")
    return t


def _volet(o: dict) -> str:
    if o["groupe"] == "Réduction de la surchauffe par la toiture":
        return "toiture"
    if o["groupe"] == "Adaptation des espaces extérieurs":
        return "paysage"
    if o["groupe"] in ("Décharge thermique nocturne", "Rafraîchissement actif"):
        return "fluides"
    if o["groupe"] in ("Brasseurs d'air plafonniers", "Réduction des charges internes"):
        return "intérieur"
    return "façade"


def est_travaux(o: dict) -> bool:
    """Vrai pour une opération de travaux (confiée à la maîtrise d'œuvre s'il y en a une)."""
    return not (o["solution"] in NON_TRAVAUX
                or (o["solution"] == "Par ventilation naturelle nocturne" and o["niveau"] == "A"))


def _alertes(o: dict) -> set:
    return {a for e in o["a_engager"] + o["a_valider"] for a in e["alertes"]}


def pieces(retenues: list[dict], moe: bool, ctx: dict) -> dict:
    """Pièces du dossier : {pièce: {"categorie", "operations"}}, dans l'ordre maîtrise d'œuvre, prestations
    préalables, travaux, référence.

    Avec une maîtrise d'œuvre, toutes les opérations de travaux lui sont confiées, quel que soit leur niveau ;
    elle réalise elle-même les diagnostics de toiture, de régulation et de structure. Le maître d'ouvrage
    garde les actions sans travaux et recrute directement le repérage amiante, le contrôle technique et la
    coordination SPS."""
    trav = [o for o in retenues if est_travaux(o)]
    out = {}

    def ajout(n, cat, ops):
        x = out.setdefault(n, {"categorie": cat, "operations": []})
        x["operations"] += [o for o in ops if o not in x["operations"]]

    if moe and trav:
        ajout("MOE", "moe", trav)
    bat = [o for o in trav if o["solution"] != "Ombrage autoportant ou végétal de la cour"]
    if bat and (ctx["amiante"] or any("PR-AL3" in _alertes(o) for o in bat)):
        ajout(10, "prealable", bat)
    struct = [o for o in trav if o["solution"] in STRUCTURE or _alertes(o) & set(ALERTES_STRUCTURE)]
    if struct and not moe:
        ajout(11, "prealable", struct)
    ct = [o for o in trav if o["solution"] in STRUCTURE or "OA-AL3" in _alertes(o)
          or (o["solution"] == "Toiture" and o["niveau"] == "C")]
    if ct:
        ajout(12, "prealable", ct)
    lots = set()
    for o in trav:
        lots |= {c for c in o["cctp"] if c not in CATEGORIE} or {o["id"]}
    if len(lots) >= 2:
        ajout(13, "prealable", trav)
    for o in retenues:
        for c in o["cctp"]:
            if CATEGORIE.get(c) == "prealable":
                if not (moe and est_travaux(o)):
                    ajout(c, "prealable", [o])
            else:
                ajout(c, "reference" if moe and est_travaux(o) else "travaux", [o])
    ordre = {"moe": 0, "prealable": 1, "travaux": 2, "reference": 3}
    return dict(sorted(out.items(), key=lambda kv: (ordre[kv[1]["categorie"]], str(kv[0]).zfill(3))))


# ------------------------------------------------------------------ choix de l'auditeur et validation
def choix(donnees: dict) -> dict:
    """Choix enregistrés (``donnees["travaux"]``), avec les valeurs par défaut."""
    t = donnees.get("travaux") or {}
    return {"operations": dict(t.get("operations") or {}),
            "moe": {"choix": "auto", "motif": "", **(t.get("moe") or {})},
            "validation": {"auditeur": "", "date_revue": "", "visa": "", "date_visa": "", **(t.get("validation") or {})},
            "accompagnement": {"ingenierie": "", **(t.get("accompagnement") or {})},
            "seuil_moe": _n(t.get("seuil_moe")) or SEUIL_MOE_DEFAUT}


def etat(donnees: dict, res: dict | None = None) -> dict:
    """Tout ce que l'interface et les documents affichent : opérations, verdict MOE, feuille de route,
    anomalies de validation et statut (projet ou validé)."""
    if not externe(donnees):
        res = res or moteur.calculer(donnees)
    ctx = contexte(donnees)
    ch = choix(donnees)
    ops = operations(donnees, res)
    anomalies = []
    for o in ops:
        c = ch["operations"].get(o["id"]) or o.get("defaut") or {}
        o["retenue"] = c.get("retenue", True)
        o["motif"] = (c.get("motif") or "").strip()
        if not o["retenue"] and not o["motif"]:
            anomalies.append(f"Opération retirée sans motif : {o['libelle']}")
    retenues = [o for o in ops if o["retenue"]]
    auto, raisons = verdict_moe(retenues, ctx, ch["seuil_moe"])
    moe = auto if ch["moe"]["choix"] == "auto" else ch["moe"]["choix"] == "oui"
    if ch["moe"]["choix"] != "auto" and moe != auto:
        if not ch["moe"]["motif"].strip():
            anomalies.append("Verdict maîtrise d'œuvre modifié sans motif")
        if auto and not moe and not ch["validation"]["visa"].strip():
            anomalies.append("Passage de la maîtrise d'œuvre de « oui » à « non » sans visa du chargé de mission")
    completer = {}
    for o in ops:
        for n in o["completer"]:
            completer.setdefault(n, []).append(o["libelle"])
    v = ch["validation"]
    valide = bool(v["auditeur"].strip() and v["date_revue"].strip() and v["visa"].strip()
                  and v["date_visa"].strip()) and not anomalies
    total = {k: sum((o["cout"] or {}).get(k, 0) for o in retenues) for k in ("bas", "haut")}
    non_chiffrees = [o["libelle"] for o in retenues if o["cout"] is None]
    p = pieces(retenues, moe, ctx)
    confiees = p.get("MOE", {}).get("operations", [])
    return {"contexte": ctx, "operations": ops, "retenues": retenues, "moe": moe, "moe_auto": auto,
            "raisons_moe": raisons, "choix": ch, "anomalies": anomalies, "valide": valide,
            "completer": completer, "total": total, "non_chiffrees": non_chiffrees,
            "ops_moe": confiees, "ops_moa": [o for o in retenues if o not in confiees],
            "pieces": p, "cctp": list(p),
            "feuille_de_route": feuille_de_route(retenues, moe, ctx, completer, ch["accompagnement"])}


def sans_fiche(o: dict) -> str:
    """Pour une action sans fiche détaillée dans le kit (solutions des diagnostics externes), le texte qui remplace
    les étapes de la fiche ; chaîne vide sinon."""
    if not CATALOGUE[o["solution"]].get("bref"):
        return ""
    f = FICHES[o["fiche"]]
    return ("Le kit n'a pas encore de fiche détaillée pour cette action : suivre les prochaines étapes indiquées par le "
            f"diagnostic d'origine et les points de vigilance relevés. Fiche la plus proche : fiche {o['fiche']} "
            f"« {f['titre']} ».")


def valider_externe(de) -> tuple[dict, list[str]]:
    """Normalise ``donnees["diagnostic_externe"]`` importé : solutions connues, listes de textes, alertes connues."""
    notes, out = [], {}
    if not isinstance(de, dict):
        return {}, (["Bloc « diagnostic_externe » illisible, ignoré."] if de else [])
    for k in ("source", "date", "reference", "commentaire"):
        if de.get(k):
            out[k] = str(de[k])[:300]

    def textes(v, n=60):
        return [str(t).strip()[:200] for t in (v if isinstance(v, list) else []) if str(t).strip()][:n]

    ops = []
    for x in de.get("operations") or []:
        if not isinstance(x, dict) or x.get("solution") not in CATALOGUE:
            notes.append(f"Opération du diagnostic externe « {(x or {}).get('solution') if isinstance(x, dict) else x} » "
                         "inconnue, ignorée.")
            continue
        y = {"solution": x["solution"], "locaux": textes(x.get("locaux")), "a_confirmer": textes(x.get("a_confirmer")),
             "alertes": [a for a in textes(x.get("alertes"), 20) if a in REGLES],
             "vigilances": textes(x.get("vigilances"), 20), "hauteur_limite": bool(x.get("hauteur_limite"))}
        for k in ("libelle", "commentaire", "extrait"):
            if x.get(k):
                y[k] = str(x[k])[:500]
        if x.get("origine") == "ia":
            y["origine"] = "ia"
        if isinstance(x.get("page"), int) and not isinstance(x.get("page"), bool) and 0 < x["page"] < 2000:
            y["page"] = x["page"]
        if x.get("niveau") in NIVEAUX:
            y["niveau"] = x["niveau"]
        if str(x.get("horizon")) in ("1", "2", "3"):
            y["horizon"] = int(x["horizon"])
        ops.append(y)
    out["operations"] = ops
    li = de.get("lecture_ia")
    if isinstance(li, dict):
        out["lecture_ia"] = {"fichier": str(li.get("fichier") or "")[:200], "date": str(li.get("date") or "")[:20],
                             "hors_catalogue": textes(li.get("hors_catalogue"), 40)}
    return out, notes


def pieces_operation(o: dict, e: dict) -> list[str]:
    """Pièces du dossier qui concernent une opération (libellés courts), pour l'affichage."""
    out = []
    for n, x in e["pieces"].items():
        if o in x["operations"]:
            nom = "CCTP MOE" if n == "MOE" else CCTP[n].split(" — ")[0]
            out.append(nom + (" (base pour la MOE)" if x["categorie"] == "reference" else ""))
    return out


def valider_saisie(t) -> tuple[dict, list[str]]:
    """Normalise ``donnees["travaux"]`` importé (JSON) : types et clés connues seulement."""
    notes, out = [], {}
    if not isinstance(t, dict):
        return {}, (["Bloc « travaux » illisible, ignoré."] if t else [])
    ops = {}
    for k, v in (t.get("operations") or {}).items():
        if k in CATALOGUE and isinstance(v, dict):
            ops[k] = {"retenue": bool(v.get("retenue", True)), "motif": str(v.get("motif") or "")}
        else:
            notes.append(f"Opération « {k} » inconnue, ignorée.")
    out["operations"] = ops
    m = t.get("moe") or {}
    out["moe"] = {"choix": m.get("choix") if m.get("choix") in ("auto", "oui", "non") else "auto",
                  "motif": str(m.get("motif") or "")}
    a = t.get("accompagnement") or {}
    out["accompagnement"] = {"ingenierie": a.get("ingenierie") if a.get("ingenierie") in ("oui", "non", "nsp") else ""}
    for k in ("code_postal", "code_insee", "commune", "date_recherche"):
        if a.get(k):
            out["accompagnement"][k] = str(a[k])[:80]
    champs = ("type", "nom", "telephone", "courriel", "site", "adresse", "source")
    structures = []
    for x in (a.get("structures") or [])[:80] if isinstance(a.get("structures"), list) else []:
        if isinstance(x, dict) and x.get("nom"):
            y = {k: str(x.get(k) or "")[:300] for k in champs}
            y["a_verifier"] = bool(x.get("a_verifier"))
            for k in ("lat", "lon", "distance_km"):
                y[k] = x.get(k) if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool) else None
            structures.append(y)
    if structures:
        out["accompagnement"]["structures"] = structures
    v = t.get("validation") or {}
    out["validation"] = {k: str(v.get(k) or "") for k in ("auditeur", "date_revue", "visa", "date_visa")}
    from .validation import nombre
    seuil = nombre(t.get("seuil_moe"))
    if seuil is not None and seuil >= 0:
        out["seuil_moe"] = seuil
    elif t.get("seuil_moe") not in (None, ""):
        notes.append(f"Seuil de maîtrise d'œuvre « {t['seuil_moe']} » illisible : valeur par défaut conservée.")
    ev = nombre(t.get("etape_vue"))
    if ev is not None and 0 <= ev <= 4:
        out["etape_vue"] = int(ev)
    return out, notes
