"""Interface Streamlit de la méthode SURYA — parcours guidé (maquette).

Lancement : streamlit run app.py

L'utilisateur choisit d'abord le type d'audit (résultats de faisabilité, équivalent de l'Excel, ou
diagnostic complet avec compte rendu) et la façon de saisir les locaux, puis suit les étapes dans
l'ordre ; les documents sont générés à la dernière étape.

Les réponses vivent dans ``st.session_state.donnees`` (aucune base de données) ; le calcul est
délégué à ``surya.moteur`` et le PDF à ``surya.rapport``, qui ne dépendent pas de l'interface.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import base64
import html
import io
import json
import unicodedata
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Streamlit Cloud peut garder en mémoire l'ancienne version des modules « surya » après une mise à jour du dépôt
# (seul app.py est relu). On compare une signature des fichiers du moteur et on recharge tout s'ils ont changé.
import sys as _sys  # noqa: E402

_SIGNATURE = max((f.stat().st_mtime_ns, f.stat().st_size) for f in (Path(__file__).parent / "surya").rglob("*")
                 if f.is_file() and f.suffix in (".py", ".json", ".md", ".csv"))
if "surya" in _sys.modules and getattr(_sys.modules["surya"], "_signature", None) != _SIGNATURE:
    for _nom in [n for n in _sys.modules if n == "surya" or n.startswith("surya.")]:
        del _sys.modules[_nom]
import surya as _surya  # noqa: E402

_surya._signature = _SIGNATURE
from surya import cctp as CC
from surya import ingenierie as IG
from surya import lecture_ia as IA
from surya import moteur, plan, rapport_preprogramme, rapport_travaux, travaux, version
from surya import photos as PH
from surya import supabase as SB
from surya import questionnaire as QU
from surya.import_excel import ImportImpossible, importer
from surya.stockage import DepotMemoire
from surya.moteur import NB_MURS_MAX, ORIENTATIONS, REFERENTIEL, REGLES
from surya.questions import (QUESTIONS_FACADE, QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL,
                             visible)
from surya.rapport import CHAMPS_AUDIT, QUESTIONS_DU_CAS, generer_pdf
from surya.rapport import donnee_manquante as _manquante

RACINE = Path(__file__).parent

MODES = {
    "resultats": {
        "titre": "Résultats de faisabilité",
        "court": "Résultats",
        "etapes": ["Bâtiment", "Locaux", "Espaces extérieurs", "Façades", "Vérification", "Résultats"],
    },
    "complet": {
        "titre": "Diagnostic complet",
        "court": "Diagnostic complet",
        "etapes": ["Identification", "Bâtiment", "Locaux", "Espaces extérieurs", "Façades", "Questionnaires usagers",
                   "Vérification", "Documents"],
    },
    # 3e parcours : passage en travaux, à partir de l'audit en cours (diagnostic complet) ou d'un diagnostic existant
    "travaux": {
        "titre": "Passage en travaux",
        "court": "Travaux",
        "etapes": ["Pré-programme", "Accompagnement", "Mise en œuvre", "Consultations"],
    },
    "externe": {
        "titre": "Passage en travaux — diagnostic existant",
        "court": "Travaux",
        "etapes": ["Diagnostic existant", "Pré-programme", "Accompagnement", "Mise en œuvre", "Consultations"],
    },
}
PARCOURS_TRAVAUX = ("travaux", "externe")
COURTS = {"Espaces extérieurs": "Espaces ext.", "Questionnaires usagers": "Questionnaires",
          "Accompagnement": "Accompagnement"}  # barre d'étapes
SAISIES = {
    "guidee": ("Pas à pas",
               "Le bâtiment puis chaque local et chaque espace sont remplis bloc par bloc (usages, ouvertures en "
               "plafond, murs et baies, équipements, éclairage…), un écran à la fois, avec « Suivant ». Le plus "
               "simple pendant ou juste après la visite, en suivant l'ordre du carnet."),
    "libre": ("Fiches à onglets",
              "Le bâtiment, chaque local et chaque espace sont des fiches dont tous les blocs sont accessibles par "
              "onglets, dans l'ordre de votre choix. Pratique pour reprendre ou corriger une saisie, ou si vous "
              "connaissez bien la grille."),
}
# statut -> (fond, texte)
# Statuts aux couleurs de la charte ACTEE (contrastes de la charte : texte noir sur couleurs claires,
# texte blanc sur brun). Même ordre et mêmes couleurs que dans les PDF (surya/rapport.py).
from surya.rapport import COULEURS  # noqa: E402
# Aides à la saisie tirées du document de méthode (SURYA, version 01 du 27/10/2026)
AIDES = {
    "MEX-07": "Estimé à l'œil ou sur photo, sans mesure. Aucun ; Faible : profondeur inférieure à la moitié de la "
              "hauteur de la baie, ou débord nettement au-dessus de la baie ; Important : profondeur au moins égale à "
              "la moitié de la hauteur de la baie et débord juste au-dessus.",
    "MEX-05": "16 cm n'est pas une valeur de dimensionnement : c'est la profondeur de tableau qui permet d'envisager "
              "une protection solaire parallèle au vitrage posée en tableau.",
    "MEX-32": "La pose de films solaires est la dernière solution à envisager, du fait de sa faible efficacité.",
}

st.set_page_config(page_title="ACTEE — Audit de faisabilité d'actions d'adaptation",
                   page_icon=str(RACINE / "static" / "logos" / "actee-favicon.png"), layout="wide",
                   initial_sidebar_state="collapsed")
LOGO = RACINE / "static" / "logos" / "actee-fnccr-couleur.png"
LOGO_CEE = RACINE / "static" / "logos" / "cee.png"  # logo CEE officiel (modèle PowerPoint ACTEE)
LOGO_SURYA = RACINE / "static" / "logos" / "surya.png"  # logo SURYA Ingénierie (document de méthode SURYA)
BADGE_CC = RACINE / "static" / "logos" / "cc-by-sa.png"  # badge Creative Commons BY-SA 4.0 (document de méthode)
BLEU, ORANGE, NOIR = "#0a17a6", "#ff5400", "#000000"


def charte():
    """Charte ACTEE : titres en Bitter Black avec séparateur, labeur en Schibsted Grotesk, angles droits."""
    st.html("""<style>
    h1, h2 { font-family: Bitter, Georgia, serif !important; font-weight: 900 !important; color: #000 !important; }
    h1 { border-bottom: 8px solid #000; padding-bottom: .25em !important; margin-bottom: .6em !important; }
    h2 { border-bottom: 5px solid #000; padding-bottom: .2em !important; margin-bottom: .5em !important; }
    h3, h4, h5 { font-family: "Schibsted Grotesk", Arial, sans-serif !important; font-weight: 800 !important; color: #000 !important; }
    .actee-chapo { font-weight: 800; font-size: 1.05rem; }
    .actee-mode { color: #0a17a6; }
    [data-testid="stExpander"] details, [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 0 !important; }
    </style>""")


def logo(cee: bool = False):
    """Logo ACTEE + FNCCR officiel, en haut à gauche (jamais centré) ; ``cee`` : avec le logo CEE
    (« Programme financé par »), comme le demande la charte sur les supports de communication."""
    if not cee:
        st.image(str(LOGO), width=190)
        return
    c1, c2, _ = st.columns([1.15, 1.1, 4], vertical_alignment="center")
    c1.image(str(LOGO), width=190)
    with c2:
        st.caption("Programme financé par")
        st.image(str(LOGO_CEE), width=120)


def _img64(chemin: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(chemin.read_bytes()).decode()
ss = st.session_state


# ------------------------------------------------------------------ état
def donnees_vides() -> dict:
    return {"audit": {}, "batiment": {}, "facades": {}, "locaux": [], "espaces": [], "parametres": {},
            "questionnaires": [], "photos": [], "travaux": {}, "diagnostic_externe": {}}


def charger(d: dict, contenus: dict | None = None):
    """Remplace toutes les données (exemple, import) et réinitialise les champs affichés.
    ``contenus`` : photos {id: jpeg} (import d'une archive ZIP)."""
    base = donnees_vides()
    base.update({k: v for k, v in d.items() if k in base})
    for x in base["locaux"] + base["espaces"] + base["questionnaires"]:
        x.setdefault("_id", uuid.uuid4().hex[:8])
    ss.donnees = base
    ss.audit_id = None  # nouvel audit, pas encore enregistré (ouvrir_audit le renseigne)
    ss.photos_supprimees = []
    ss.photos_bin = dict(contenus or {})
    base["photos"] = [ph for ph in base["photos"] if ph.get("id") in ss.photos_bin]  # description sans image : retirée
    ss.generation = ss.get("generation", 0) + 1
    ss.edition = {"locaux": None, "espaces": None}
    ss.theme = {"locaux": 0, "espaces": 0, "batiment": 0}


if "donnees" not in ss:
    charger(donnees_vides())
for k, v in (("mode", None), ("saisie", "guidee"), ("etape", 0), ("etape_max", 0), ("vue", "parcours"),
             ("message", None), ("haut", False), ("photos_bin", {})):
    ss.setdefault(k, v)
D = ss.donnees
D.setdefault("photos", [])  # saisies antérieures aux photos
D.setdefault("travaux", {})  # saisies antérieures au module passage en travaux
for k, v in (("audit_id", None), ("photos_supprimees", []), ("enregistre_le", None)):
    ss.setdefault(k, v)
SB_CONF = SB.configuration(st.secrets)  # None : mode maquette, rien n'est enregistré sur un serveur
if SB_CONF and "sb" not in ss:
    ss.sb = SB.Supabase(*SB_CONF)


def connecte() -> bool:
    return bool(SB_CONF) and ss.sb.connecte


def enregistrer(silencieux: bool = False) -> bool:
    """Enregistre l'audit (et ses photos) dans Supabase si l'auditeur est connecté."""
    if not connecte():
        return False
    try:
        code_audit()
        depot = SB.DepotAudits(ss.sb)
        if ss.audit_id is None:  # première fois : créer la ligne pour obtenir l'identifiant du dossier photos
            ss.audit_id = depot.enregistrer(D)["id"]
        SB.synchroniser_photos(SB.DepotPhotos(ss.sb), ss.audit_id, D, ss.photos_bin, ss.photos_supprimees)
        depot.enregistrer(D, ss.audit_id)
        ss.enregistre_le = __import__("datetime").datetime.now().strftime("%H:%M")
        return True
    except SB.ErreurSupabase as e:
        if not silencieux:
            st.error(f"Enregistrement impossible : {e}")
        else:
            st.toast(f"Enregistrement automatique impossible : {e}", icon="⚠️")
        return False


def ouvrir_audit(id_audit: str):
    from surya.validation import valider
    ligne = SB.DepotAudits(ss.sb).ouvrir(id_audit)
    d, _ = valider(ligne["donnees"])
    d["audit"] = dict(d.get("audit") or {}, code=ligne["code"])
    depot, contenus = SB.DepotPhotos(ss.sb), {}
    for ph in d.get("photos") or []:
        try:
            contenus[ph["id"]] = depot.telecharger(id_audit, ph["id"])
        except SB.ErreurSupabase:
            pass
    charger(d, contenus)
    ss.audit_id = id_audit
    enregistrer(silencieux=True)  # ouvrir un audit le conserve 3 ans de plus (date de dernière modification)


def cle(*parts) -> str:
    return ":".join(str(p) for p in (ss.generation, *parts))


def etapes() -> list[str]:
    return MODES[ss.mode]["etapes"] if ss.mode else []


def aller(etape: str | int):
    """Change d'étape du parcours (et remonte en haut de page)."""
    n = etapes().index(etape) if isinstance(etape, str) else etape
    enregistrer(silencieux=True)
    ss.etape = n
    ss.etape_max = max(ss.etape_max, n)
    ss.vue = "parcours"
    ss.haut = True
    st.rerun()


def doublons(cle_liste: str) -> list[str]:
    """Noms portés par plusieurs locaux (ou espaces) : indiscernables dans les tableaux et documents."""
    noms = [x.get(ENTITES[cle_liste]["code_nom"]) for x in D[cle_liste]]
    return sorted({n for n in noms if n and noms.count(n) > 1})


def nom_entite(x: dict, i: int, cle_liste: str) -> str:
    cfg = ENTITES[cle_liste]
    return x.get(cfg["code_nom"]) or f"{cfg['defaut']} {i + 1}"


# ------------------------------------------------------------------ champs de saisie
def _etiquette(q) -> str:
    unite = f" ({q['unite']})" if q.get("unite") else ""
    code = "MEX-01" if q["code"] == "orientation" else q["code"].removesuffix("b")
    return f"{q['libelle']}{unite} · {code}"


def champ(q: dict, d: dict, prefixe: str):
    """Affiche le champ d'une question et range la réponse dans ``d``."""
    code, typ, k = q["code"], q["type"], cle(prefixe, q["code"])
    aide = AIDES.get(code) or ("Question informative : elle n'entre pas dans le calcul des statuts." if q.get("info") else None)
    actuel = d.get(code)
    if typ == "choix":
        opts = q["options"]
        hors_liste = actuel if actuel is not None and actuel not in opts else None
        if hors_liste is not None:
            actuel = None
        if sum(len(o) for o in opts) <= 26:
            v = st.segmented_control(_etiquette(q), opts, default=actuel, key=k, help=aide)
        else:
            v = st.selectbox(_etiquette(q), opts, index=opts.index(actuel) if actuel else None,
                             placeholder="Choisir…", key=k, help=aide)
        if hors_liste is not None and v is None:  # valeur importée hors liste : conservée tant qu'on ne la change pas
            st.caption(f"⚠️ Réponse importée hors liste : « {hors_liste} ». Choisissez une réponse de la liste.")
            v = hors_liste
    elif typ == "multi":
        st.markdown(f":small[{_etiquette(q)} :gray[— plusieurs réponses possibles]]", help=aide)
        v = [o for n, o in enumerate(q["options"])
             if st.checkbox(o, value=o in (actuel or []), key=f"{k}:{n}")] or None
    elif typ == "nombre":
        v = _champ_nombre(q, d, k, aide)
    else:
        v = st.text_input(_etiquette(q), value=actuel or "", key=k, help=aide).strip() or None
    if v is None:
        d.pop(code, None)
    else:
        d[code] = v


def _champ_nombre(q, d, k, aide):
    actuel, unite = d.get(q["code"]), q.get("unite", "")
    if q["code"] == "B-24":  # nombre en cm ou « inconnu »
        inconnu = st.checkbox("Épaisseur d'isolant inconnue (non visible) · B-24", value=actuel == "inconnu",
                              key=k + ":inconnu")
        if inconnu:
            return "inconnu"
    if not isinstance(actuel, (int, float)) or isinstance(actuel, bool):
        actuel = None
    haut = 4 if unite == "0 à 4" else None
    hors_bornes = actuel is not None and (actuel < 0 or (haut is not None and actuel > haut))
    if hors_bornes:
        st.caption(f"⚠️ Valeur importée hors des valeurs possibles : {actuel}.")
    entier = actuel is None or float(actuel).is_integer()
    if unite in ("", "pers.", "0 à 4") and entier and not hors_bornes:
        return st.number_input(_etiquette(q), min_value=0, max_value=haut, step=1,
                               value=None if actuel is None else int(actuel), placeholder="—", key=k, help=aide)
    if hors_bornes:  # pas de bornes imposées : la valeur importée reste affichée telle quelle
        return st.number_input(_etiquette(q), value=float(actuel), key=k, help=aide)
    pas, fmt = (0.1, "%.2f") if unite == "m" else (1.0, "%.1f")
    return st.number_input(_etiquette(q), min_value=0.0, step=pas, format=fmt,
                           value=None if actuel is None else float(actuel), placeholder="—", key=k, help=aide)


def section(s: dict, d: dict, etats, cb: dict, prefixe: str):
    """Questions visibles d'une section, sur deux colonnes. ``etats`` est recalculé avant chaque
    question pour qu'une question conditionnelle apparaisse dès que sa condition est remplie."""
    cols = st.columns(2, gap="large")
    i = 0
    for q in s["questions"]:
        if visible(q["code"], etats(), d, cb):
            with cols[i % 2]:
                champ(q, d, prefixe)
            i += 1


def sans_reponse(sections, d: dict, etats, cb: dict) -> list[dict]:
    """Questions affichées, utiles au calcul, et restées sans réponse."""
    out = []
    for s in sections:
        for q in s["questions"]:
            if q.get("info") or q["type"] == "case":
                continue
            if visible(q["code"], etats(), d, cb) and d.get(q["code"]) in (None, "", []):
                out.append(q)
    return out


def murs_incomplets(l: dict) -> list[str]:
    if l.get("aucune_baie"):
        return []
    murs = [m for m in (l.get("murs") or []) if m]
    if not murs:
        return ["aucun mur extérieur décrit (ou cocher « Aucune baie en façade »)"]
    out = []
    for i, m in enumerate(murs, start=1):
        manque = [lib for k, lib in (("orientation", "orientation"), ("MEX-04", "position des baies"),
                                     ("MEX-06", "état des menuiseries"), ("MEX-07", "débord"), ("baies", "types de baie"))
                  if not m.get(k)]
        if m.get("MEX-04") in ("Nu intérieur", "En tunnel") and m.get("MEX-05") is None:
            manque.append("distance vitrage-façade")
        if manque:
            out.append(f"mur {i} : " + ", ".join(manque))
    return out


def avertir(questions: list[dict], autres: list[str] = ()):
    """Signale ce qui reste à renseigner, sans bloquer."""
    items = [f"{q['libelle']} ({q['code'].removesuffix('b')})" for q in questions] + list(autres)
    if not items:
        st.caption("✅ Tout est renseigné ici.")
        return
    with st.expander(f"⚠️ {len(items)} élément(s) sans réponse — vous pouvez continuer, la solution concernée "
                     "passera « Sous réserve »"):
        st.markdown("\n".join(f"- {html.escape(t)}" for t in items))


def pastille(statut: str) -> str:
    if not statut:
        return "<span style='color:#999'>—</span>"
    fond, texte = COULEURS.get(statut, ("#eee", "#333"))
    return (f"<span class='actee-statut' style='background:{fond};color:{texte};padding:2px 10px;"
            f"font-size:0.85em;font-weight:600;white-space:nowrap'>{html.escape(statut)}</span>")


def remonter():
    """Remonte en haut de la page après un changement d'étape."""
    if ss.haut:
        ss.haut = False
        ss.nonce = ss.get("nonce", 0) + 1
        components.html(f"<script>/*{ss.nonce}*/const m=window.parent.document.querySelector('[data-testid=\"stMain\"]');"
                        "if(m){m.scrollTo(0,0);}window.parent.scrollTo(0,0);</script>", height=0)


CB = moteur.etats_batiment(D["batiment"], D["facades"])


# ------------------------------------------------------------------ écran de départ
def ecran_depart():
    logo(cee=True)
    st.title("Audit de faisabilité d'actions d'adaptation")
    st.markdown("Méthode SURYA (ACTEE et SURYA Ingénierie) — plan rafraîchissement des écoles. À partir des relevés de visite, "
                "l'outil établit pour chaque local et chaque espace extérieur le **statut de faisabilité** de chaque "
                "solution de confort d'été.")

    if SB_CONF:
        bloc_compte()

    if D["locaux"] or D["espaces"] or D["batiment"]:
        st.info(f"Une saisie est en cours ({len(D['locaux'])} local(aux), {len(D['espaces'])} espace(s) extérieur(s)) : "
                "elle sera conservée quel que soit votre choix.", icon="💾")

    st.subheader("1. Comment voulez-vous remplir le questionnaire ?")
    choix = st.radio("Mode de saisie", list(SAISIES), index=list(SAISIES).index(ss.saisie),
                     format_func=lambda k: SAISIES[k][0], captions=[SAISIES[k][1] for k in SAISIES],
                     label_visibility="collapsed", key="choix_saisie")
    ss.saisie = choix
    st.caption("Vous pourrez changer de mode à tout moment depuis les étapes Bâtiment, Locaux et Espaces extérieurs.")

    st.subheader("2. Que voulez-vous produire ?")
    c1, c2 = st.columns(2, gap="large")
    with c1.container(border=True, height="stretch"):
        st.markdown("### Résultats de faisabilité")
        st.markdown("L'équivalent de l'Excel de la méthode SURYA : vous saisissez le bâtiment, les façades, les locaux et "
                    "les espaces extérieurs, et vous obtenez les statuts de chaque solution.")
        st.markdown("**À la fin :** tableau des statuts à l'écran, **PDF des résultats** (2 à 3 pages), export CSV.")
        st.markdown(f":gray[{len(MODES['resultats']['etapes'])} étapes : "
                    f"{' → '.join(MODES['resultats']['etapes'])}]")
        if st.button("Commencer — résultats", type="primary", width="stretch"):
            demarrer("resultats")
    with c2.container(border=True, height="stretch"):
        st.markdown("### Diagnostic complet")
        st.markdown("Même saisie, avec en plus l'identification de l'audit (établissement, auditeur, date), vos "
                    "observations par local et espace, les **questionnaires usagers** (confort estival) et un "
                    "commentaire général.")
        st.markdown("**À la fin :** le **compte rendu complet** (synthèse en une page, présentation du bâtiment, "
                    "ressenti des usagers, pistes d'action, détail en annexes) et le PDF des résultats.")
        st.markdown(f":gray[{len(MODES['complet']['etapes'])} étapes : {' → '.join(MODES['complet']['etapes'])}]")
        if st.button("Commencer — diagnostic complet", type="primary", width="stretch"):
            demarrer("complet")

    st.subheader("3. Passer à l'action")
    with st.container(border=True):
        st.markdown("### Passage en travaux")
        st.markdown("Une fois le diagnostic fait : **pré-programme** à présenter aux élus, **accompagnement** "
                    "(maîtrise d'œuvre, ingénierie du territoire), **mise en œuvre** (CCTP de maîtrise d'œuvre ou "
                    "fiches travaux) et **consultations** (CCTP des prestataires et des travaux).")
        st.markdown(f":gray[{len(MODES['travaux']['etapes'])} étapes : {' → '.join(MODES['travaux']['etapes'])}]")
        audit_en_cours = bool(D["locaux"] or D["espaces"])
        b1, b2 = st.columns(2)
        with b1:
            if st.button("À partir de l'audit en cours", type="primary", width="stretch", disabled=not audit_en_cours,
                         help=None if audit_en_cours else "Faites d'abord un diagnostic complet, ou ouvrez un audit "
                                                          "enregistré ou un exemple."):
                demarrer("travaux")
            st.caption("Diagnostic complet fait avec l'outil (méthode SURYA)." if audit_en_cours else
                       "Disponible dès qu'un audit est en cours (diagnostic complet, audit enregistré ou exemple).")
        with b2:
            if st.button("À partir d'un diagnostic existant", width="stretch"):
                demarrer("externe")
            st.caption("Diagnostic réalisé hors de la méthode SURYA (par exemple « plan canicule » de la Banque des "
                       "Territoires) : vous reportez ses préconisations, puis les mêmes étapes s'appliquent.")
            if st.button("Essayer avec un diagnostic Inddigo (école de Bretignolles-sur-Mer)", width="stretch"):
                charger(json.loads((RACINE / "surya" / "exemple_diagnostic_externe.json").read_text(encoding="utf-8")))
                demarrer("externe")
                st.rerun()

    with st.expander("Reprendre une saisie existante ou essayer avec un exemple"):
        bloc_donnees(prefixe="depart")
    with st.expander("Notice d'utilisation : vos données, l'hébergement, le lien avec l'Excel"):
        notice()
    st.divider()
    st.html(f"<div style='display:flex;align-items:center;gap:22px;flex-wrap:wrap'>"
            f"<img src='{_img64(LOGO_SURYA)}' alt='SURYA Ingénierie' style='height:54px'>"
            f"<a href='https://creativecommons.org/licenses/by-sa/4.0/deed.fr' target='_blank'>"
            f"<img src='{_img64(BADGE_CC)}' alt='Licence Creative Commons BY-SA 4.0' style='height:26px'></a>"
            f"<div style='font-size:0.85rem;color:#000;max-width:640px'>Méthode SURYA — © 2026 ACTEE et SURYA "
            f"Ingénierie, diffusée sous licence Creative Commons BY-SA 4.0. {html.escape(REFERENTIEL['version'])}.</div></div>")
    st.caption("Maquette : sans compte, les données ne sont pas enregistrées sur un serveur ; exportez la saisie pour la "
               "conserver.")


def bloc_compte():
    """Connexion de l'auditeur et liste de ses audits enregistrés (si Supabase est configuré)."""
    if not ss.sb.connecte:
        with st.expander("🔐 Se connecter pour enregistrer et retrouver vos audits", expanded=False):
            st.caption("Sans compte, l'outil fonctionne comme une maquette : la saisie n'est pas enregistrée, "
                       "exportez-la pour la conserver.")
            t1, t2 = st.tabs(["Connexion", "Créer un compte"])
            for onglet, creer in ((t1, False), (t2, True)):
                with onglet, st.form(f"compte:{creer}"):
                    email = st.text_input("Adresse e-mail")
                    mdp = st.text_input("Mot de passe" + (" (8 caractères au moins)" if creer else ""), type="password")
                    if st.form_submit_button("Créer le compte" if creer else "Se connecter", type="primary"):
                        try:
                            if creer:
                                if ss.sb.inscription(email.strip(), mdp):
                                    st.success("Compte créé : confirmez votre adresse avec le lien reçu par e-mail, "
                                               "puis connectez-vous.")
                                else:
                                    st.rerun()
                            else:
                                ss.sb.connexion(email.strip(), mdp)
                                st.rerun()
                        except SB.ErreurSupabase as e:
                            st.error(str(e))
        return
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.markdown(f"**Vos audits enregistrés** · :gray[{html.escape((ss.sb.utilisateur or {}).get('email', ''))}]")
    if c2.button("Se déconnecter", width="stretch"):
        ss.sb.deconnexion()
        st.rerun()
    try:
        audits = SB.DepotAudits(ss.sb).lister()
    except SB.ErreurSupabase as e:
        st.error(f"Liste des audits indisponible : {e}")
        return
    if not audits:
        st.caption("Aucun audit enregistré : choisissez un type d'audit ci-dessous ; il sera enregistré à chaque "
                   "étape.")
    for a in audits[:20]:
        with st.container(border=True):
            l1, l2, l3 = st.columns([4, 1, 1], vertical_alignment="center")
            courant = " · :blue[en cours]" if a["id"] == ss.audit_id else ""
            fin, proche = SB.suppression_prevue(a["modifie_le"])
            l1.markdown(f"**{html.escape(a['nom'])}** :gray[· modifié le {a['modifie_le'][8:10]}/{a['modifie_le'][5:7]}/"
                        f"{a['modifie_le'][:4]} · suppression prévue le {fin}]{courant}")
            if proche:
                l1.warning(f"Cet audit sera supprimé le {fin} (3 ans sans modification). Ouvrez-le pour le "
                           "conserver 3 ans de plus, ou exportez-le.", icon="🕑")
            if l2.button("Ouvrir", key=f"ouvrir:{a['id']}", width="stretch"):
                try:
                    ouvrir_audit(a["id"])
                    ss.message = f"Audit « {a['nom']} » ouvert."
                    ss.etape_max = len(MODES["complet"]["etapes"]) - 1
                    st.rerun()
                except SB.ErreurSupabase as e:
                    st.error(str(e))
            if l3.button("Supprimer", key=f"suppr:{a['id']}", width="stretch"):
                ss.a_supprimer = a["id"]
            if ss.get("a_supprimer") == a["id"]:
                st.warning("Supprimer définitivement cet audit, ses photos et les réponses des usagers ?")
                o1, o2 = st.columns(2)
                if o1.button("Oui, supprimer", key=f"confirmer:{a['id']}", type="primary"):
                    try:
                        ids = [ph["id"] for ph in SB.DepotAudits(ss.sb).ouvrir(a["id"])["donnees"].get("photos") or []]
                        SB.DepotPhotos(ss.sb).supprimer(a["id"], ids)
                        SB.DepotAudits(ss.sb).supprimer(a["id"])
                    except SB.ErreurSupabase as e:
                        st.error(str(e))
                    if ss.audit_id == a["id"]:
                        ss.audit_id = None
                    ss.a_supprimer = None
                    st.rerun()
                if o2.button("Annuler", key=f"annuler:{a['id']}"):
                    ss.a_supprimer = None
                    st.rerun()
    if ss.message:
        st.success(ss.message)
        ss.message = None


def notice():
    texte = (RACINE / "docs" / "notice_utilisation.md").read_text(encoding="utf-8")
    st.markdown(texte.split("\n", 1)[1].replace("\n## ", "\n#### "))


def demarrer(mode: str):
    ss.mode = mode
    ss.etape, ss.etape_max = 0, 0
    d = ss.donnees  # et non D : un exemple vient peut-être d'être chargé dans ce même passage
    if d["locaux"] or d["espaces"] or (mode == "externe" and travaux.externe(d)):  # saisie reprise
        ss.etape_max = len(etapes()) - 1
    aller(0)


def bloc_donnees(prefixe: str):
    """Exemple, import, export, effacement."""
    c1, c2, c3 = st.columns(3)
    for col, fichier_ex, cle_ex, libelle, msg in (
            (c1, "exemple.json", "exemple", "Charger l'exemple de l'Excel",
             "Exemple de l'Excel chargé : 3 locaux, 1 espace extérieur"),
            (c2, "exemple_ecole_sud.json", "ecole_sud", "Charger l'école type du Sud",
             "École type du Sud chargée (fictive, ≈ 1 000 m²) : 6 locaux, 1 espace extérieur")):
        if col.button(libelle, width="stretch", key=f"{prefixe}:{cle_ex}"):
            exemple = json.loads((RACINE / "surya" / fichier_ex).read_text(encoding="utf-8"))
            exemple["questionnaires"] = [dict(r, source="exemple (fictif)") for r in
                                         QU.lire_csv((RACINE / "surya" / "exemple_questionnaires.csv").read_bytes())[0]]
            charger(exemple)
            ss.message = msg + " et 14 questionnaires usagers fictifs."
            ss.etape_max = len(etapes()) - 1 if ss.mode else 0
            st.rerun()
    if D.get("photos"):
        c3.download_button("Exporter la saisie et les photos (ZIP)", PH.exporter_zip(D, ss.photos_bin),
                           file_name="saisie_surya.zip", mime="application/zip", width="stretch", key=f"{prefixe}:export")
    else:
        c3.download_button("Exporter la saisie (JSON)", json.dumps(D, ensure_ascii=False, indent=1),
                           file_name="saisie_surya.json", mime="application/json", width="stretch", key=f"{prefixe}:export")
    fichier = st.file_uploader("Importer une saisie (JSON, ou ZIP avec photos) ou un Excel de la méthode SURYA déjà rempli "
                               "(.xlsx)", type=["json", "zip", "xlsx"], key=cle(prefixe, "import"))
    if fichier is not None and st.button("Importer ce fichier", type="primary", key=f"{prefixe}:importer"):
        contenus = {}
        try:
            if fichier.name.lower().endswith(".zip"):
                brut, contenus = PH.lire_zip(fichier.getvalue())
                d, notes = importer("saisie.json", json.dumps(brut).encode("utf-8"))
            else:
                d, notes = importer(fichier.name, fichier.getvalue())
        except ValueError as e:
            st.error(f"Import impossible : {e}")
        except ImportImpossible as e:
            st.error(f"Import impossible : {e}")
        except Exception:  # cas non prévu : message générique plutôt qu'une trace Python
            st.error("Import impossible : fichier illisible. Utilisez un fichier exporté par l'outil (.json) ou "
                     "l'Excel de la méthode SURYA (.xlsx).")
        else:
            charger(d, contenus)
            ss.message = (f"Fichier importé : {len(D['locaux'])} local(aux), {len(D['espaces'])} espace(s) extérieur(s)"
                          + (f", {len(D['photos'])} photo(s)." if D["photos"] else "."))
            ss.notes_import = notes
            ss.etape_max = len(etapes()) - 1 if ss.mode else 0
            st.rerun()
    if ss.message:
        st.success(ss.message)
        ss.message = None
    notes = ss.pop("notes_import", None)
    if notes:
        with st.expander(f"⚠️ {len(notes)} correction(s) apportée(s) au fichier importé", expanded=True):
            st.markdown("\n".join(f"- {html.escape(n)}" for n in notes))


# ------------------------------------------------------------------ en-tête et navigation
def entete():
    c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
    with c1:
        l1, l2 = st.columns([1, 4.2], vertical_alignment="center")
        with l1:
            logo()
        l2.markdown(f"<div style='font-family:Bitter,Georgia,serif;font-weight:900;font-size:1.35rem;line-height:1.2'>"
                    f"Audit de faisabilité d'actions d'adaptation<br><span class='actee-mode'>"
                    f"{MODES[ss.mode]['titre']}</span></div>", unsafe_allow_html=True)
    with c2.popover("⚙️ Réglages", width="stretch"):
        if connecte():
            if st.button("💾 Enregistrer", width="stretch", type="primary"):
                if enregistrer():
                    st.toast("Audit enregistré.", icon="✅")
            st.caption(f"Connecté : {(ss.sb.utilisateur or {}).get('email', '')}"
                       + (f" · enregistré à {ss.enregistre_le}" if ss.enregistre_le else " · pas encore enregistré"))
        if st.button("Seuils et données", width="stretch"):
            ss.vue = "reglages"
            st.rerun()
        if st.button("Changer de type d'audit", width="stretch", help="Revenir à l'écran de départ ; la saisie est conservée."):
            ss.mode = None
            st.rerun()
    # Barre d'étapes : sur une seule ligne, défilable horizontalement sur téléphone
    st.html("<style>.st-key-etapes [data-testid='stHorizontalBlock']{flex-wrap:nowrap;overflow-x:auto;gap:.4rem}"
            ".st-key-etapes [data-testid='stColumn']{min-width:max-content;flex:1 0 auto}"
            ".st-key-etapes button p{white-space:nowrap}</style>")
    with st.container(key="etapes"):
        cols = st.columns(len(etapes()))
        for i, (col, nom) in enumerate(zip(cols, etapes())):
            fait = "✓ " if i < ss.etape_max and i != ss.etape else ""
            if col.button(f"{fait}{i + 1}. {COURTS.get(nom, nom)}", key=f"nav:{i}", width="stretch",
                          disabled=i > ss.etape_max, type="primary" if i == ss.etape else "secondary", help=nom):
                ss.edition = {"locaux": None, "espaces": None}
                aller(i)


def pied(suivant_label: str | None = None, precedent: bool = True):
    """Boutons Précédent / Suivant du parcours."""
    st.divider()
    c1, _, c3 = st.columns([1, 2, 1.3])
    if precedent and ss.etape > 0 and c1.button("← Étape précédente", width="stretch"):
        aller(ss.etape - 1)
    if ss.mode == "travaux" and ss.etape == 0 and c1.button("← Documents du diagnostic", width="stretch"):
        ss.mode = "complet"
        ss.etape_max = len(MODES["complet"]["etapes"]) - 1
        aller("Documents")
    if ss.etape < len(etapes()) - 1:
        lib = suivant_label or f"Suivant : {etapes()[ss.etape + 1]} →"
        if c3.button(lib, type="primary", width="stretch"):
            aller(ss.etape + 1)


# ------------------------------------------------------------------ photos
def ajouter_photos(fichiers, cible: str) -> list[str]:
    """Prépare et ajoute des photos ; renvoie les messages (visages floutés, fichiers illisibles)."""
    messages = []
    for f in fichiers:
        try:
            jpeg, infos = PH.preparer(f.getvalue(), flouter_visages=True)
        except ValueError as e:
            messages.append(f"{f.name} : {e}")
            continue
        ph = PH.nouvelle(cible, infos, etiquette=PH.premiere_attendue(D, cible) if cible else "Autre")
        D["photos"].append(ph)
        ss.photos_bin[ph["id"]] = jpeg
        if infos["visages_floutes"]:
            messages.append(f"{getattr(f, 'name', 'Photo')} : {infos['visages_floutes']} visage(s) flouté(s).")
    return messages


def vignette(ph: dict, pid: str, cibles: list[str] | None = None):
    """Une photo : image, étiquette, légende, (rattachement), suppression."""
    img = ss.photos_bin.get(ph["id"])
    if img:
        st.image(img, width="stretch")
    meta = [ph["prise_le"]] if ph.get("prise_le") else []
    if ph.get("visages_floutes"):
        meta.append(f"{ph['visages_floutes']} visage(s) flouté(s)")
    if meta:
        st.caption(" · ".join(meta))
    if cibles is not None:
        c = st.selectbox("Rattacher à", cibles, index=cibles.index(ph["cible"]) if ph["cible"] in cibles else 0,
                         format_func=lambda k: PH.libelle_cible(D, k), key=cle(pid, ph["id"], "cible"))
        if c != ph["cible"]:
            ph["cible"] = c
            st.rerun()
    e = st.selectbox("Étiquette", PH.ETIQUETTES, index=PH.ETIQUETTES.index(ph.get("etiquette", "Autre")),
                     key=cle(pid, ph["id"], "etiquette"))
    ph["etiquette"] = e
    lg = st.text_input("Légende", value=ph.get("legende", ""), key=cle(pid, ph["id"], "legende"),
                       placeholder="Ce que montre la photo").strip()
    ph["legende"] = lg
    if st.button("Supprimer la photo", key=cle(pid, ph["id"], "suppr"), width="stretch"):
        D["photos"].remove(ph)
        ss.photos_bin.pop(ph["id"], None)
        if ph.get("envoyee"):
            ss.photos_supprimees.append(ph["id"])
        st.rerun()


def bloc_photos(cible: str, pid: str):
    """Ajout (fichiers ou caméra), liste de contrôle des photos attendues et vignettes d'une cible."""
    genre = cible.split(":")[0]
    attendues = PH.ATTENDUES.get(genre, [])
    manquantes = PH.attendues_manquantes(D, cible)
    if attendues:
        st.markdown("**Photos attendues** : " + " · ".join(
            f"{'✅' if a not in manquantes else '⬜'} {a}" for a in attendues))
    st.caption("Sur téléphone, « Ajouter des photos » propose l'appareil photo ou la galerie. Les photos sont réduites "
               "(1 600 px), redressées, et les visages détectés sont floutés. Évitez de photographier des enfants.")
    n = ss.setdefault("photos_gen", {}).get(cible, 0)
    fichiers = st.file_uploader("Ajouter des photos", type=PH.FORMATS, accept_multiple_files=True,
                                key=cle(pid, "photos", n))
    if st.toggle("Prendre une photo avec la caméra de l'appareil", key=cle(pid, "camera", n)):
        prise = st.camera_input("Photo", key=cle(pid, "camera_input", n), label_visibility="collapsed")
        if prise is not None:
            fichiers = list(fichiers or []) + [prise]
    if fichiers:
        msgs = ajouter_photos(fichiers, cible)
        ss.photos_gen[cible] = n + 1
        ss.message_photos = msgs
        st.rerun()
    for m in ss.pop("message_photos", None) or []:
        st.info(m, icon="📷")
    liste = PH.de_la_cible(D, cible)
    cols = st.columns(3)
    for k, ph in enumerate(liste):
        with cols[k % 3].container(border=True):
            vignette(ph, pid)


def import_groupe():
    """Import de toutes les photos de la visite, puis rattachement de chacune."""
    with st.expander(f"📷 Importer les photos de la visite en une fois"
                     + (f" — {len(PH.de_la_cible(D, ''))} à rattacher" if PH.de_la_cible(D, "") else "")):
        st.caption("Pratique après la visite : déposez toutes les photos, puis rattachez chacune au bâtiment, à un "
                   "local ou à un espace. Elles sont rangées par heure de prise de vue.")
        n = ss.setdefault("photos_gen", {}).get("groupe", 0)
        fichiers = st.file_uploader("Photos de la visite", type=PH.FORMATS, accept_multiple_files=True,
                                    key=cle("groupe", "photos", n))
        if fichiers:
            ss.message_photos = ajouter_photos(fichiers, "")
            ss.photos_gen["groupe"] = n + 1
            st.rerun()
        a_rattacher = sorted(PH.de_la_cible(D, ""), key=lambda ph: ph.get("prise_le") or "")
        cibles = [""] + PH.cibles(D)
        cols = st.columns(3)
        for k, ph in enumerate(a_rattacher):
            with cols[k % 3].container(border=True):
                vignette(ph, "groupe", cibles)


# ------------------------------------------------------------------ étapes
def etape_identification():
    st.header("Identification de l'audit")
    st.markdown("Ces informations figurent en page de garde du compte rendu. Elles n'interviennent pas dans le calcul.")
    a = D["audit"]
    cols = st.columns(2, gap="large")
    for n, (k, lib) in enumerate(CHAMPS_AUDIT):
        v = cols[n % 2].text_input(lib, value=a.get(k, ""), key=cle("audit", k)).strip()
        if v:
            a[k] = v
        else:
            a.pop(k, None)
    manque = [lib for k, lib in CHAMPS_AUDIT if not a.get(k)]
    avertir([], [f"{lib}" for lib in manque])
    st.subheader("Photos générales du bâtiment")
    st.markdown("Façade principale, vue d'ensemble, cour : la photo étiquetée « Façade » illustre la synthèse du "
                "compte rendu.")
    bloc_photos("batiment", "batiment")
    import_groupe()
    pied()


def selecteur_saisie(cle_widget: str):
    """Permet de changer de mode de saisie (pas à pas / fiches à onglets)."""
    mode = st.segmented_control("Mode de saisie", list(SAISIES), default=ss.saisie,
                                format_func=lambda k: SAISIES[k][0], key=f"saisie:{cle_widget}",
                                help=" · ".join(f"{v[0]} : {v[1]}" for v in SAISIES.values()))
    if mode and mode != ss.saisie:
        ss.saisie = mode
        st.rerun()


def _bloc_batiment(s, b, etats):
    if s["titre"] == "Ventilation mécanique":
        st.caption("Cas technique : sans compétence suffisante, laissez les champs non évalués ; la ventilation "
                   "mécanique nocturne passera alors « Sous réserve ».")
    section(s, b, etats, CB, "bat")
    avertir(sans_reponse([s], b, etats, CB))


def premier_bloc_batiment_incomplet() -> int:
    b = D["batiment"]
    etats = lambda: moteur.etats_batiment(b, D["facades"])  # noqa: E731
    for k, s in enumerate(SECTIONS_BATIMENT):
        if sans_reponse([s], b, etats, CB):
            return k
    return 0


def etape_batiment():
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    c1.header("Bâtiment")
    with c2:
        selecteur_saisie("batiment")
    st.markdown("Données générales du bâtiment. Certaines questions n'apparaissent que si elles ont un objet.")
    b = D["batiment"]
    etats = lambda: moteur.etats_batiment(b, D["facades"])  # noqa: E731
    secs = SECTIONS_BATIMENT
    if ss.saisie == "guidee":
        t = min(ss.theme.get("batiment", 0), len(secs) - 1)
        choix = st.segmented_control("Bloc", range(len(secs)), default=t, key=f"bloc_bat:{t}", width="stretch",
                                     format_func=lambda k: f"{k + 1}. {secs[k]['titre']}", label_visibility="collapsed")
        if choix is not None and choix != t:
            ss.theme["batiment"] = choix
            ss.haut = True
            st.rerun()
        st.progress((t + 1) / len(secs), text=f"Bloc {t + 1} sur {len(secs)} : **{secs[t]['titre']}**")
        with st.container(border=True):
            _bloc_batiment(secs[t], b, etats)
        if t < len(secs) - 1:
            n1, _, n3 = st.columns([1, 1.5, 1.2])
            if t > 0 and n1.button("← Bloc précédent", width="stretch"):
                ss.theme["batiment"] = t - 1
                ss.haut = True
                st.rerun()
            if n3.button("Bloc suivant →", type="primary", width="stretch", help=secs[t + 1]["titre"]):
                ss.theme["batiment"] = t + 1
                ss.haut = True
                st.rerun()
            st.divider()
            if ss.etape > 0 and st.button("← Étape précédente"):
                aller(ss.etape - 1)
            return
        if st.button("← Bloc précédent"):
            ss.theme["batiment"] = t - 1
            ss.haut = True
            st.rerun()
    else:
        onglets = st.tabs([f"{k + 1}. {s['titre']}" for k, s in enumerate(secs)])
        for onglet, s in zip(onglets, secs):
            with onglet:
                _bloc_batiment(s, b, etats)
    pied()


def orientations_utilisees() -> dict[str, list[str]]:
    """Orientations citées par les murs des locaux et les espaces extérieurs."""
    out: dict[str, list[str]] = {}
    for i, l in enumerate(D["locaux"]):
        if l.get("aucune_baie"):
            continue
        for m in l.get("murs") or []:
            if m.get("orientation"):
                out.setdefault(m["orientation"], []).append(nom_entite(l, i, "locaux"))
    for i, e in enumerate(D["espaces"]):
        for o in e.get("E-20") or []:
            if o in ORIENTATIONS:
                out.setdefault(o, []).append(nom_entite(e, i, "espaces"))
    return out


def _ligne_facade(o, f, autres, f01, citee=""):
    with st.container(border=bool(f.get("F-01"))):
        cols = st.columns([1.4] + [2] * len(autres))
        decrite = cols[0].checkbox(f"Façade **{o}**", value=bool(f.get("F-01")), key=cle("fac", o, "F-01"),
                                   help=f01["libelle"])
        if citee:
            cols[0].caption(citee)
        if decrite:
            f["F-01"] = True
            for col, q in zip(cols[1:], autres):
                with col:
                    champ({**q, "type": "choix"}, f, f"fac:{o}")
        else:
            f.pop("F-01", None)


def etape_facades():
    st.header("Façades")
    st.markdown("Décrivez les façades du bâtiment qui portent les baies des locaux visités ou qui bordent un espace "
                "extérieur. Les règles des locaux (protections solaires) et des espaces (ombrage adossé) utilisent "
                "la façade de **même orientation** que le mur ou l'espace.")
    utilisees = orientations_utilisees()
    f01, autres = QUESTIONS_FACADE[0], QUESTIONS_FACADE[1:]
    for o in ORIENTATIONS:
        D["facades"].setdefault(o, {})
        deja = ss.setdefault("facades_cochees", set())
        if o in utilisees and (ss.generation, o) not in deja:
            D["facades"][o]["F-01"] = True  # façade citée : cochée d'office (une seule fois), à décrire
            deja.add((ss.generation, o))
    citees = [o for o in ORIENTATIONS if o in utilisees]
    if citees:
        st.subheader("Façades citées par vos locaux et espaces")
        for o in citees:
            _ligne_facade(o, D["facades"][o], autres, f01, "citée par " + ", ".join(dict.fromkeys(utilisees[o])))
    else:
        st.info("Aucun mur de local ni espace extérieur n'indique d'orientation pour l'instant.")
    reste = [o for o in ORIENTATIONS if o not in utilisees]
    with st.expander("Autres façades", expanded=not citees or any(D["facades"][o].get("F-01") for o in reste)):
        for o in reste:
            _ligne_facade(o, D["facades"][o], autres, f01)
    oublis = [f"façade {o} citée par {', '.join(dict.fromkeys(n))} mais non décrite" for o, n in utilisees.items()
              if not (D["facades"].get(o) or {}).get("F-01")]
    incompletes = [f"façade {o} : {q['libelle']}" for o, f in D["facades"].items() if f.get("F-01")
                   for q in autres if not f.get(q["code"])]
    avertir([], oublis + incompletes)
    pied()


# --- locaux et espaces --------------------------------------------------------------------
ENTITES = {
    "locaux": {"code_nom": "L-01", "defaut": "Local", "un": "un local", "le": "le local", "titre": "Locaux",
               "sections": SECTIONS_LOCAL, "etats": lambda x: moteur.etats_local(x, CB)},
    "espaces": {"code_nom": "E-01", "defaut": "Espace", "un": "un espace extérieur", "le": "l'espace",
                "titre": "Espaces extérieurs", "sections": SECTIONS_ESPACE, "etats": lambda x: moteur.etats_espace(x)},
}


def themes(cle_liste: str) -> list[tuple]:
    th = [("section", s["titre"], s) for s in ENTITES[cle_liste]["sections"]]
    if cle_liste == "locaux":
        th.insert(2, ("murs", "Murs et baies en façade", None))
    if ss.mode == "complet":
        th.append(("observations", "Observations", None))
        th.append(("photos", "Photos", None))
    return th


def manques_theme(cle_liste: str, x: dict, th: tuple) -> tuple[list[dict], list[str]]:
    kind, _, s = th
    if kind == "section":
        return sans_reponse([s], x, lambda: ENTITES[cle_liste]["etats"](x), CB), []
    if kind == "murs":
        return [], murs_incomplets(x)
    return [], []


def nb_manques(cle_liste: str, x: dict) -> int:
    return sum(len(a) + len(b) for a, b in (manques_theme(cle_liste, x, th) for th in themes(cle_liste)))


def etape_entites(cle_liste: str):
    i = ss.edition[cle_liste]
    if i is not None and i < len(D[cle_liste]):
        editeur(cle_liste, i)
    else:
        ss.edition[cle_liste] = None
        liste_entites(cle_liste)


def liste_entites(cle_liste: str):
    cfg, liste = ENTITES[cle_liste], D[cle_liste]
    st.header(cfg["titre"])
    if cle_liste == "locaux":
        st.markdown("Ajoutez chaque local visité (classe, dortoir, salle de motricité, bureau…). Pour chacun, "
                    "les statuts sont calculés en direct.")
    else:
        st.markdown("Ajoutez chaque espace extérieur (cour, préau, jardin…). S'il n'y en a pas, passez à l'étape suivante.")
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    with c2:
        selecteur_saisie(cle_liste)
    for n in doublons(cle_liste):
        st.warning(f"Plusieurs {cfg['titre'].lower()} portent le même nom « {n} » : donnez-leur des noms distincts "
                   "pour les reconnaître dans les tableaux et les documents.", icon="⚠️")
    if ss.message:
        st.success(ss.message)
        ss.message = None

    if not liste:
        st.info(f"Aucun {cfg['defaut'].lower()} pour l'instant.")
    else:
        res = moteur.calculer(D)[cle_liste]
        cols = st.columns(3)
        for i, x in enumerate(liste):
            with cols[i % 3].container(border=True):
                st.markdown(f"**{html.escape(nom_entite(x, i, cle_liste))}**")
                sous_titre = x.get("L-02") if cle_liste == "locaux" else ", ".join(x.get("E-02") or [])
                st.caption(sous_titre or "type non renseigné")
                n = nb_manques(cle_liste, x)
                st.markdown("✅ Complet" if n == 0 else f"⚠️ {n} élément(s) sans réponse")
                compte = {}
                for s in res[i]["solutions"]:
                    compte[s["statut"]] = compte.get(s["statut"], 0) + 1
                st.markdown(" ".join(f"{pastille(s)}&nbsp;<b>{compte[s]}</b>" for s in COULEURS if s in compte),
                            unsafe_allow_html=True)
                b1, b2, b3 = st.columns([1.4, 1, 1])
                if b1.button("✏️ Modifier", key=f"mod:{cle_liste}:{x['_id']}", width="stretch"):
                    ouvrir(cle_liste, i)
                if b2.button("⧉", key=f"dup:{cle_liste}:{x['_id']}", width="stretch", help="Dupliquer"):
                    copie = json.loads(json.dumps(x))
                    copie["_id"] = uuid.uuid4().hex[:8]
                    copie[cfg["code_nom"]] = f"{nom_entite(x, i, cle_liste)} (copie)"
                    liste.insert(i + 1, copie)
                    st.rerun()
                if b3.button("🗑", key=f"del:{cle_liste}:{x['_id']}", width="stretch", help="Supprimer"):
                    liste.pop(i)
                    PH.orphelines(D)  # ses photos restent, « à rattacher »
                    st.rerun()
    if st.button(f"➕ Ajouter {cfg['un']}", type="primary" if not liste else "secondary"):
        liste.append({"_id": uuid.uuid4().hex[:8]})
        ouvrir(cle_liste, len(liste) - 1)
    if ss.mode == "complet":
        import_groupe()
    pied()


def ouvrir(cle_liste: str, i: int, theme: int = 0):
    ss.edition[cle_liste] = i
    ss.theme[cle_liste] = theme
    ss.haut = True
    st.rerun()


def fermer(cle_liste: str, i: int):
    x = D[cle_liste][i]
    ss.message = f"« {nom_entite(x, i, cle_liste)} » enregistré. Ajoutez-en un autre ou passez à l'étape suivante."
    ss.edition[cle_liste] = None
    ss.haut = True
    st.rerun()


def editeur(cle_liste: str, i: int):
    cfg, x = ENTITES[cle_liste], D[cle_liste][i]
    pid, nom_avant = f"{cle_liste}:{x['_id']}", x.get(cfg["code_nom"])
    th = themes(cle_liste)
    c1, c2 = st.columns([1.3, 4], vertical_alignment="center")
    if c1.button(f"← Liste des {cfg['titre'].lower()}", width="stretch"):
        ss.edition[cle_liste] = None
        st.rerun()
    c2.markdown(f"### {html.escape(nom_entite(x, i, cle_liste))} :gray[· {cfg['defaut'].lower()} {i + 1} sur {len(D[cle_liste])}]")

    gauche, droite = st.columns([2.6, 1], gap="large")
    with gauche:
        if ss.saisie == "guidee":
            t = min(ss.theme[cle_liste], len(th) - 1)
            choix = st.segmented_control("Thème", range(len(th)), default=t, key=f"theme:{pid}:{t}",
                                         format_func=lambda k: f"{k + 1}. {th[k][1]}", label_visibility="collapsed",
                                         width="stretch")
            if choix is not None and choix != t:
                ouvrir(cle_liste, i, choix)
            st.progress((t + 1) / len(th), text=f"Thème {t + 1} sur {len(th)} : **{th[t][1]}**")
            with st.container(border=True):
                afficher_theme(cle_liste, x, pid, th[t])
            n1, _, n3 = st.columns([1, 1.5, 1.2])
            if t > 0 and n1.button("← Thème précédent", width="stretch"):
                ouvrir(cle_liste, i, t - 1)
            if t < len(th) - 1:
                if n3.button("Thème suivant →", type="primary", width="stretch", help=th[t + 1][1]):
                    ouvrir(cle_liste, i, t + 1)
            elif n3.button(f"✓ Terminer {cfg['le']}", type="primary", width="stretch"):
                fermer(cle_liste, i)
        else:
            onglets = st.tabs([f"{k + 1}. {t[1]}" for k, t in enumerate(th)])
            for onglet, t in zip(onglets, th):
                with onglet:
                    afficher_theme(cle_liste, x, pid, t)
            if st.button(f"✓ Terminer {cfg['le']}", type="primary"):
                fermer(cle_liste, i)
    with droite:
        n = nb_manques(cle_liste, x)
        st.markdown("✅ Tout est renseigné" if n == 0 else f"⚠️ {n} élément(s) sans réponse")
        res = moteur.calculer(D)[cle_liste][i]
        st.markdown("**Statuts (calcul en direct)**")
        st.markdown("".join(f"<div style='margin:0 0 9px 0;font-size:0.88em'>{html.escape(s['solution'])}<br>"
                            f"{pastille(s['statut'])}</div>" for s in res["solutions"]), unsafe_allow_html=True)
    if x.get(cfg["code_nom"]) != nom_avant:  # le nom vient de changer : met à jour l'en-tête
        st.rerun()


def afficher_theme(cle_liste: str, x: dict, pid: str, th: tuple):
    kind, titre, s = th
    if kind == "section":
        section(s, x, lambda: ENTITES[cle_liste]["etats"](x), CB, pid)
    elif kind == "murs":
        _murs(x, pid)
    elif kind == "photos":
        bloc_photos(PH.cible_de(cle_liste, x), pid)
    else:
        _observations(x, pid)
    q, autres = manques_theme(cle_liste, x, th)
    avertir(q, autres)


def _murs(l: dict, pid: str):
    """Baies en façade : jusqu'à 4 murs extérieurs, un par orientation."""
    st.caption("Décrivez chaque mur extérieur du local qui porte des baies (4 au maximum), un bloc par orientation.")
    aucune = st.checkbox("Aucune baie en façade :gray[· MEX-01]", value=bool(l.get("aucune_baie")), key=cle(pid, "aucune"))
    if aucune:
        l["aucune_baie"] = True
        return
    l.pop("aucune_baie", None)
    murs = l.get("murs") or []
    if not murs:  # mur affiché pour la saisie, enregistré seulement s'il est rempli
        murs = [{}]
    q_baies = next(q for q in QUESTIONS_MUR if q["type"] == "baies")
    for i, m in enumerate(murs):
        with st.container(border=True):
            st.markdown(f"**Mur extérieur {i + 1}**")
            cols = st.columns(2, gap="large")
            for j, q in enumerate(q for q in QUESTIONS_MUR if q["type"] != "baies"):
                if q["code"] == "MEX-05" and m.get("MEX-04") not in ("Nu intérieur", "En tunnel"):
                    continue
                with cols[j % 2]:
                    champ(q, m, f"{pid}:mur{i}")
            ori = m.get("orientation")
            if ori and not (D["facades"].get(ori) or {}).get("F-01"):
                st.caption(f"ℹ️ La façade {ori} sera à décrire à l'étape Façades (alignement, accès, obstacles, "
                           "désordres), après les espaces extérieurs.")
            anciens = m.get("baies") or {}
            types = st.multiselect("Types de baie présents sur ce mur :gray[· MEX-08]", q_baies["options"],
                                   default=[t for t in q_baies["options"] if t in anciens],
                                   placeholder="Choisir un ou plusieurs types…", key=cle(pid, f"mur{i}", "types"))
            baies = {}
            if types:
                colsn = st.columns(4)
                for n, t in enumerate(t for t in q_baies["options"] if t in types):
                    prec = anciens.get(t)
                    nb = colsn[n % 4].number_input(f"Nombre — {t}", min_value=1, step=1, placeholder="non compté",
                                                   value=int(prec) if isinstance(prec, (int, float)) else None,
                                                   key=cle(pid, f"mur{i}", "nb", t))
                    baies[t] = nb if nb is not None else "x"
            if baies:
                m["baies"] = baies
            else:
                m.pop("baies", None)
    if l.get("murs") is not murs and any(murs):  # le mur affiché vient d'être rempli : on l'enregistre
        l["murs"] = murs
    c1, c2, _ = st.columns([1.5, 1.8, 4])
    if len(murs) < NB_MURS_MAX and c1.button("➕ Ajouter un mur", key=cle(pid, "addmur")):
        l["murs"] = murs
        murs.append({})
        st.rerun()
    if len(murs) > 1 and c2.button("🗑 Supprimer le dernier mur", key=cle(pid, "delmur")):
        murs.pop()
        st.rerun()


def _observations(x: dict, pid: str):
    st.caption("Texte libre repris dans la fiche du compte rendu. Les éléments décisifs restent saisis dans les "
               "questions fermées : ce champ ne modifie aucun statut.")
    v = st.text_area("Observations de l'auditeur", value=x.get("observations", ""), height=160,
                     key=cle(pid, "observations")).strip()
    if v:
        x["observations"] = v
    else:
        x.pop("observations", None)


def premier_theme_incomplet(cle_liste: str, x: dict) -> int:
    for k, th in enumerate(themes(cle_liste)):
        q, autres = manques_theme(cle_liste, x, th)
        if q or autres:
            return k
    return 0


# --- vérification ---------------------------------------------------------------------------
def etape_verification():
    st.header("Vérification avant les documents")
    st.markdown("Récapitulatif de ce qui n'est pas renseigné. Vous pouvez générer les documents dès maintenant : "
                "une donnée manquante fait passer la solution concernée « Sous réserve », comme dans la méthode SURYA.")
    if not D["locaux"] and not D["espaces"]:
        st.error("Aucun local ni espace extérieur : ajoutez-en au moins un pour obtenir des résultats.")
        b1, b2 = st.columns(2)
        if b1.button("Ajouter des locaux"):
            aller("Locaux")
        if b2.button("Ajouter des espaces extérieurs"):
            aller("Espaces extérieurs")
        pied(precedent=True)
        return
    res = moteur.calculer(D)
    total = 0

    def ligne(cle_ligne, titre, n, detail, action):
        nonlocal total
        total += n
        c1, c2, c3 = st.columns([3, 4, 1.3], vertical_alignment="center")
        c1.markdown(f"{'✅' if n == 0 else '⚠️'} **{html.escape(titre)}**")
        c2.markdown(html.escape(detail) if n else ":gray[complet]")
        if n and c3.button("Compléter", key=f"verif:{cle_ligne}", width="stretch"):
            action()

    with st.container(border=True):
        if ss.mode == "complet":
            manque = [lib for k, lib in CHAMPS_AUDIT if not D["audit"].get(k)]
            ligne("audit", "Identification", len(manque), ", ".join(manque), lambda: aller("Identification"))
        q = sans_reponse(SECTIONS_BATIMENT, D["batiment"], lambda: moteur.etats_batiment(D["batiment"], D["facades"]), CB)
        def vers_batiment():
            ss.theme["batiment"] = premier_bloc_batiment_incomplet()
            aller("Bâtiment")
        ligne("bat", "Bâtiment", len(q), f"{len(q)} question(s) sans réponse", vers_batiment)
        oublis = [f"{o} non décrite" for o in orientations_utilisees() if not (D["facades"].get(o) or {}).get("F-01")]
        oublis += [f"{o} : « {q['libelle']} » sans réponse" for o, f in D["facades"].items() if f.get("F-01")
                   for q in QUESTIONS_FACADE[1:] if not f.get(q["code"])]
        ligne("fac", "Façades", len(oublis), " · ".join(oublis), lambda: aller("Façades"))
        for cle_liste in ("locaux", "espaces"):
            for i, x in enumerate(D[cle_liste]):
                n = nb_manques(cle_liste, x)
                reserves = [s["solution"] for s in res[cle_liste][i]["solutions"] if _manquante(res[cle_liste][i], s)]
                detail = f"{n} élément(s) sans réponse" + (f" · « Sous réserve » faute de données : {', '.join(reserves)}"
                                                          if reserves else "")

                def action(c=cle_liste, k=i, xx=x):
                    ss.edition[c] = k
                    ss.theme[c] = premier_theme_incomplet(c, xx)
                    aller(ENTITES[c]["titre"])
                ligne(f"{cle_liste}:{x['_id']}", nom_entite(x, i, cle_liste), n, detail, action)
    if ss.mode == "complet":
        n = len(D["questionnaires"])
        c1, c2, c3 = st.columns([3, 4, 1.3], vertical_alignment="center")
        c1.markdown(f"{'✅' if n >= QU.MIN_REPONDANTS else 'ℹ️'} **Questionnaires usagers**")
        c2.markdown(f"{n} réponse(s)" + ("" if n >= QU.MIN_REPONDANTS else
                                           f" — facultatif ; la synthèse demande au moins {QU.MIN_REPONDANTS} réponses"))
        if n < QU.MIN_REPONDANTS and c3.button("Ajouter", key="verif:quest", width="stretch"):
            aller("Questionnaires usagers")
    if ss.mode == "complet":
        bilan = PH.bilan_attendues(D)
        a_rattacher = len(PH.de_la_cible(D, ""))
        c1, c2, c3 = st.columns([3, 4, 1.3], vertical_alignment="center")
        c1.markdown(f"{'✅' if not bilan and not a_rattacher else 'ℹ️'} **Photos** ({len(D['photos'])})")
        detail = " · ".join(f"{n} : {', '.join(m)}" for n, m in bilan[:6]) + (" …" if len(bilan) > 6 else "")
        c2.markdown((f"{a_rattacher} photo(s) à rattacher. " if a_rattacher else "")
                    + (f"Photos attendues manquantes — {html.escape(detail)}" if bilan else "Toutes les photos attendues sont là.")
                    + " :gray[(facultatif)]")
    for c in ("locaux", "espaces"):
        for n in doublons(c):
            st.warning(f"Plusieurs {ENTITES[c]['titre'].lower()} portent le même nom « {n} » : renommez-les pour les "
                       "distinguer dans les documents.", icon="⚠️")
    if total == 0:
        st.success("Tout est renseigné.")
    pied(suivant_label="Générer les documents →" if ss.mode == "complet" else "Voir les résultats →")


# --- questionnaires usagers ---------------------------------------------------------------------
def code_audit() -> str:
    a = D["audit"]
    if not a.get("code"):
        a["code"] = uuid.uuid4().hex[:10]
    return a["code"]


def formulaire_usager(r: dict, prefixe: str):
    """Les questions du questionnaire confort estival, avec leurs conditions. Remplit ``r``."""
    theme = None
    for q in QU.QUESTIONS:
        if not QU.visible(q["code"], r):
            r.pop(q["code"], None)
            continue
        if q["theme"] != theme:
            theme = q["theme"]
            st.markdown(f"##### {QU.THEMES[theme]}")
        k = f"{prefixe}:{q['code']}"
        lib = f"**{q['code'].removeprefix('Q')}.** {q['libelle']}"
        if q["type"] == "texte":
            v = (st.text_area if q["code"] == "Q24" else st.text_input)(lib, value=r.get(q["code"], ""), key=k).strip()
        elif q["type"] == "choix":
            v = st.radio(lib, q["options"], index=q["options"].index(r[q["code"]]) if r.get(q["code"]) in q["options"] else None,
                         key=k)
        else:
            st.markdown(lib + " :gray[(plusieurs réponses possibles)]")
            v = [o for n, o in enumerate(q["options"]) if st.checkbox(o, value=o in (r.get(q["code"]) or []), key=f"{k}:{n}")]
        if v:
            r[q["code"]] = v
        else:
            r.pop(q["code"], None)


def page_usager(code: str):
    """Questionnaire en ligne, tel qu'un usager le voit (lien ?questionnaire=<code>)."""
    logo()
    st.title("Questionnaire confort estival")
    st.markdown("Ce questionnaire, anonyme, prend 5 minutes. Il porte sur la **période estivale** (mai, juin et "
                "septembre) et sur le **local que vous occupez principalement**. Vos réponses aideront à choisir les "
                "solutions pour limiter la chaleur dans l'école.")
    if not SB_CONF:
        st.info("Maquette : vos réponses ne sont pas encore envoyées automatiquement. À la fin, téléchargez le fichier "
                "de votre réponse et transmettez-le à la personne qui réalise l'audit.", icon="ℹ️")
    else:
        st.caption("Vos réponses sont enregistrées de façon anonyme pour l'audit de votre établissement.")
    if ss.get("usager_envoye"):
        st.success("Merci pour votre participation !")
        st.download_button("Télécharger ma réponse (CSV)", QU.vers_csv([ss.usager_envoye]).encode("utf-8-sig"),
                           file_name=f"reponse_questionnaire_{code}.csv", mime="text/csv",
                           type="secondary" if SB_CONF else "primary")
        if st.button("Répondre à nouveau"):
            ss.usager_envoye, ss.usager_r = None, {}
            ss.usager_n = ss.get("usager_n", 0) + 1
            st.rerun()
        return
    r = ss.setdefault("usager_r", {})
    formulaire_usager(r, f"usager:{ss.get('usager_n', 0)}")
    if st.button("Envoyer mes réponses", type="primary"):
        if not any(k.startswith("Q") for k in r):
            st.error("Le questionnaire est vide.")
        else:
            reponse = dict(r, horodatage=__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"))
            if SB_CONF:  # dépôt anonyme : accepté seulement pour un questionnaire ouvert (règles de la base)
                try:
                    SB.DepotReponsesSupabase(SB.Supabase(*SB_CONF)).ajouter(code, dict(reponse, source="en ligne"))
                except SB.ErreurSupabase as e:
                    st.error(str(e))
                    return
            ss.usager_envoye = reponse
            st.rerun()


def etape_questionnaires():
    st.header("Questionnaires usagers")
    st.markdown(f"Le questionnaire confort estival ({len(QU.QUESTIONS)} questions, 5 minutes) recueille le ressenti des occupants : "
                "ressenti thermique, gênes, pratiques d'adaptation, moments d'inconfort. Ses résultats sont "
                "**indicatifs** (enquête déclarative) et servent à vérifier la cohérence des préconisations. "
                "La synthèse est faite pour tout l'établissement. Cette étape est facultative.")
    depot = DepotMemoire(D["questionnaires"])
    code = code_audit()
    t1, t2, t3 = st.tabs(["Questionnaire en ligne", "Importer des réponses (CSV)", "Saisir un questionnaire papier"])
    with t1:
        st.markdown("Lien à diffuser aux enseignants et au personnel :")
        base = (getattr(st.context, "url", None) or "<adresse de l'application>").split("?")[0].rstrip("/")
        st.code(f"{base}/?questionnaire={code}", language=None)
        st.link_button("Ouvrir le questionnaire tel que le voient les usagers", f"?questionnaire={code}")
        if connecte():
            if ss.audit_id is None:
                enregistrer(silencieux=True)  # le lien n'accepte des réponses que pour un audit enregistré
            st.caption("Le lien accepte des réponses pendant 90 jours après la création de l'audit. Elles sont "
                       "enregistrées dans la base, anonymes, et conservées 12 mois ; une fois récupérées ici, elles "
                       "suivent la durée de l'audit.")
            if st.button("Récupérer les réponses en ligne", type="primary"):
                try:
                    distantes = SB.DepotReponsesSupabase(ss.sb).lister(code)
                    connues = {r.get("_id") for r in D["questionnaires"]}
                    nouvelles = [r for r in distantes if r["_id"] not in connues]
                    D["questionnaires"].extend(nouvelles)
                    ss.message = f"{len(nouvelles)} nouvelle(s) réponse(s) en ligne."
                    st.rerun()
                except SB.ErreurSupabase as e:
                    st.error(str(e))
        elif SB_CONF:
            st.caption("Connectez-vous (écran de départ) pour que ce lien enregistre les réponses et que vous les "
                       "récupériez ici.")
        else:
            st.caption("Maquette : les réponses données par ce lien ne sont pas enregistrées sur un serveur. "
                       "Chaque usager peut télécharger sa réponse (CSV) et vous l'envoyer ; vous l'importez dans "
                       "l'onglet suivant.")
    with t2:
        st.markdown("Fichier CSV au format du questionnaire en ligne : une ligne par répondant, une colonne par "
                    "question (`Q1` à `Q24`), réponses multiples séparées par « ; ». Les exports de formulaires "
                    "dont les en-têtes commencent par le numéro de question (« Q4 - … ») sont aussi acceptés.")
        st.download_button("Télécharger le modèle de fichier", QU.modele_csv().encode("utf-8-sig"),
                           file_name="modele_questionnaire_confort.csv", mime="text/csv")
        fichiers = st.file_uploader("Fichiers de réponses (CSV)", type=["csv"], accept_multiple_files=True,
                                    key=cle("quest", "import"))
        if fichiers and st.button("Importer ces réponses", type="primary"):
            total, avert = 0, []
            for f in fichiers:
                reps, av = QU.lire_csv(f.getvalue())
                for r in reps:
                    depot.ajouter(code, dict(r, source="import"))
                total += len(reps)
                avert += [f"{f.name} — {a}" for a in av]
            ss.message = f"{total} réponse(s) importée(s)."
            ss.avert_import = avert
            st.rerun()
    with t3:
        st.caption("Pour reporter un questionnaire rempli sur papier.")
        n = ss.get("papier_n", 0)
        r = ss.setdefault("papier_r", {})
        with st.container(border=True):
            formulaire_usager(r, cle("papier", n))
        if st.button("Ajouter ce questionnaire", type="primary"):
            if any(k.startswith("Q") for k in r):
                depot.ajouter(code, dict(r, source="papier"))
                ss.papier_r, ss.papier_n = {}, n + 1
                ss.message = "Questionnaire ajouté."
                st.rerun()
            st.error("Le questionnaire est vide.")
    if ss.message:
        st.success(ss.message)
        ss.message = None
    for a in ss.pop("avert_import", []) or []:
        st.warning(a)

    reponses = depot.lister(code)
    st.subheader(f"Réponses recueillies : {len(reponses)}")
    if reponses:
        lignes = [{"N°": k + 1, "Source": r.get("source", ""), "Reçue le": r.get("horodatage", ""),
                   "Local (Q1)": r.get("Q1", ""), "Ressenti (Q4)": r.get("Q4", ""), "Ambiance (Q5)": r.get("Q5", "")}
                  for k, r in enumerate(reponses)]
        st.dataframe(lignes, hide_index=True, width="stretch")
        c1, c2, c3 = st.columns([1.2, 1, 1.3], vertical_alignment="bottom")
        k = c1.selectbox("Réponse", range(len(reponses)), format_func=lambda i: f"N° {i + 1}")
        if c2.button("Supprimer cette réponse"):
            if reponses[k].get("source") == "en ligne" and connecte():
                try:
                    SB.DepotReponsesSupabase(ss.sb).supprimer(code, reponses[k].get("_id", ""))
                except SB.ErreurSupabase as e:
                    st.error(str(e))
            depot.supprimer(code, reponses[k].get("_id", ""))
            st.rerun()
        c3.download_button("Exporter toutes les réponses (CSV)", QU.vers_csv(reponses).encode("utf-8-sig"),
                           file_name="reponses_questionnaire_confort.csv", mime="text/csv")
        afficher_synthese_usagers(reponses)
    pied()


def afficher_synthese_usagers(reponses):
    m = QU.matrice(reponses, moteur.calculer(D))
    syn = m["synthese"]
    st.subheader("Synthèse (tout l'établissement)")
    if syn["repondants"] < QU.MIN_REPONDANTS:
        st.info(f"Au moins {QU.MIN_REPONDANTS} réponses sont nécessaires pour une synthèse interprétable.")
    i = syn["indicateurs"]
    c = st.columns(4)
    s = i["sensation_moyenne"]
    c[0].metric("Sensation moyenne (Q4)", "—" if s is None else f"{s:+.1f}", help="Échelle de −3 (très froide) à +3 (très chaude).")
    for col, cle_i in zip(c[1:], ("inconfort", "trop_chaud_souvent", "soleil_gene")):
        v = i[cle_i]["part"]
        col.metric(QU.LIBELLES_INDICATEURS[cle_i].split(" (")[0], "—" if v is None else f"{v:.0%}")
    st.markdown("**Matrice de correspondance ressenti / préconisations** :gray[(proposition, à valider)]")
    st.dataframe([{"Croisement": f"{l['id']} — {l['ressenti']}", "Usagers": l["usagers"], "Audit": l["audit"],
                   "Résultat": l["resultat"], "Commentaire": l["commentaire"]} for l in m["lignes"]],
                 hide_index=True, width="stretch")
    if m["indicateur"] is not None:
        st.markdown(f"**Indicateur de cohérence : {m['indicateur']:.0%}** "
                    f"({m['evalues'] - m['a_verifier']} croisement(s) sans incohérence sur {m['evalues']} évalué(s))")


# --- résultats / documents -------------------------------------------------------------------
def _tableau(entites, defaut):
    """Tableau HTML solutions x entités."""
    noms = [html.escape(x["nom"] or f"{defaut} {i + 1}") for i, x in enumerate(entites)]
    th = "".join(f"<th style='text-align:center;padding:6px 10px'>{n}</th>" for n in noms)
    lignes, groupe_prec = "", None
    for j, s in enumerate(entites[0]["solutions"]):
        if s["groupe"] != groupe_prec:
            lignes += (f"<tr><td colspan='{len(noms) + 1}' style='padding:10px 6px 4px 0;font-weight:700;"
                       f"border-bottom:1px solid #8884'>{html.escape(s['groupe'])}</td></tr>")
            groupe_prec = s["groupe"]
        cellules = ""
        for x in entites:
            sx = x["solutions"][j]
            marque = " <span title='Donnée manquante'>❓</span>" if _manquante(x, sx) else ""
            alerte = " <span title='Alerte(s)'>⚠️</span>" if sx["alertes"] else ""
            cellules += f"<td style='text-align:center;padding:5px 10px'>{pastille(sx['statut'])}{marque}{alerte}</td>"
        lignes += f"<tr><td style='padding:5px 16px 5px 12px'>{html.escape(s['solution'])}</td>{cellules}</tr>"
    st.markdown(f"<div style='overflow-x:auto'><table style='border-collapse:collapse'>"
                f"<tr><th></th>{th}</tr>{lignes}</table></div>", unsafe_allow_html=True)
    st.caption("❓ statut « Sous réserve » dû à une donnée manquante · ⚠️ alerte associée")


def _detail(x, s):
    """Détail d'une solution : règle retenue, données manquantes, alertes, toutes les règles du bloc."""
    st.markdown(f"**{html.escape(s['solution'])}** &nbsp; {pastille(s['statut'])}", unsafe_allow_html=True)
    if not s["blocs"]:
        if s["statut"] == moteur.NON_CONCERNE:
            st.caption("La solution ne concerne pas cet espace (ce n'est pas une cour de récréation).")
        else:
            st.info(f"Cas non déterminé faute de données. À renseigner : {QUESTIONS_DU_CAS.get(s['solution'], '')}.", icon="❓")
    for b in s["blocs"]:
        bl = x["blocs"][b]
        code = bl["regle"]
        if code is None:
            st.info("Aucune règle n'a pu être vérifiée avec les données disponibles.", icon="❓")
            continue
        r = REGLES[code]
        st.markdown(f"Règle retenue **{code}** : {r['regle']}")
        if bl["manquante"]:
            st.info(f"Donnée manquante : la règle {code} n'a pas pu être tranchée. "
                    f"Questions à compléter : {r['questions'] or '—'}.", icon="❓")
    for code in s["alertes"]:
        st.warning(f"**{code}** — {REGLES[code]['regle']}", icon="⚠️")
    for b in s["blocs"]:
        with st.popover(f"Toutes les règles du bloc {b}"):
            symbole = {1: "✅ vraie", 0: "— fausse", 0.5: "❓ indéterminée"}
            st.dataframe([{"Règle": c, "Statut": REGLES[c]["statut"], "Évaluation": symbole[v], "Libellé": REGLES[c]["regle"]}
                          for c, v in x["blocs"][b]["valeurs"].items()], hide_index=True, width=900)


def _export_csv(res) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Type", "Nom", "Groupe", "Solution", "Statut", "Règle retenue", "Donnée manquante", "Alertes"])
    for typ, cle_, defaut in (("Local", "locaux", "Local"), ("Espace extérieur", "espaces", "Espace")):
        for i, x in enumerate(res[cle_]):
            for s in x["solutions"]:
                w.writerow([typ, x["nom"] or f"{defaut} {i + 1}", s["groupe"], s["solution"], s["statut"],
                            ", ".join(x["blocs"][b]["regle"] or "(aucune)" for b in s["blocs"]),
                            "oui" if _manquante(x, s) else "non", ", ".join(s["alertes"])])
    return out.getvalue()


@st.cache_data(max_entries=20, show_spinner="Préparation du document…")
def _pdf(donnees_json: str, complet: bool, photos: tuple = ()) -> bytes:
    return generer_pdf(json.loads(donnees_json), complet=complet, photos=dict(photos))


def etape_documents():
    complet = ss.mode == "complet"
    st.header("Documents" if complet else "Résultats")
    res = moteur.calculer(D)
    if not res["locaux"] and not res["espaces"]:
        st.info("Ajoutez au moins un local ou un espace extérieur pour obtenir des résultats.")
        pied()
        return
    a = D["audit"]
    base = unicodedata.normalize("NFKD", a.get("etablissement", "audit")).encode("ascii", "ignore").decode()
    suffixe = "".join(c if c.isalnum() else "_" for c in base).strip("_") + ".pdf"
    with st.container(border=True):
        if complet:
            st.subheader("Vos documents")
            v = st.text_area("Commentaire général de l'auditeur (facultatif, repris dans le compte rendu)",
                             value=a.get("synthese", ""), key=cle("audit", "synthese")).strip()
            if v:
                a["synthese"] = v
            else:
                a.pop("synthese", None)
        else:
            st.subheader("Télécharger les résultats")
        donnees_json = json.dumps(D, ensure_ascii=False, sort_keys=True)
        cols = st.columns([1.3, 1, 0.7] if complet else [1, 0.6, 1.4])
        if complet:
            utiles = tuple((ph["id"], ss.photos_bin[ph["id"]]) for ph in D["photos"] if ph["id"] in ss.photos_bin)
            cols[0].download_button("Compte rendu complet (PDF)", _pdf(donnees_json, True, utiles),
                                    file_name="compte_rendu_" + suffixe, mime="application/pdf", type="primary",
                                    width="stretch")
            cols[0].caption("Synthèse en une page, bâtiment, ressenti des usagers, pistes d'action et points à lever ; détail en annexes.")
            k_res, k_csv = 1, 2
        else:
            k_res, k_csv = 0, 1
        cols[k_res].download_button("Résultats (PDF)", _pdf(donnees_json, False), file_name="resultats_" + suffixe,
                                    mime="application/pdf", type="secondary" if complet else "primary", width="stretch")
        cols[k_res].caption("Statuts, alertes et données manquantes (2 à 3 pages).")
        cols[k_csv].download_button("Tableau (CSV)", _export_csv(res).encode("utf-8-sig"),
                                    file_name="resultats_surya.csv", mime="text/csv", width="stretch")
        if not complet:
            with cols[2]:
                st.caption("Besoin du compte rendu complet (synthèse, bâtiment, pistes d'action, annexes) ?")
                if st.button("Passer au diagnostic complet", width="stretch"):
                    ss.mode = "complet"
                    ss.etape_max = len(etapes()) - 1
                    ss.message = None
                    aller("Identification")
    if complet:
        with st.container(border=True):
            st.subheader("Et maintenant : passer à l'action")
            st.markdown("Le **passage en travaux** reprend cet audit pour préparer le pré-programme à présenter aux élus, "
                        "choisir l'accompagnement (maîtrise d'œuvre, ingénierie du territoire) et produire les pièces "
                        "de consultation (CCTP).")
            if st.button("Préparer le passage en travaux →", type="primary", key="vers_travaux"):
                enregistrer(silencieux=True)
                ss.mode = "travaux"
                ss.etape, ss.etape_max = 0, len(MODES["travaux"]["etapes"]) - 1
                ss.vue, ss.haut = "parcours", True
                st.rerun()
    schema = plan.svg(D, res)
    if schema:
        st.subheader("Plan simplifié")
        img = base64.b64encode(schema.encode("utf-8")).decode()
        st.html(f"<img alt='Plan simplifié' style='width:100%;max-width:900px' src='data:image/svg+xml;base64,{img}'>")
    st.markdown(" ".join(pastille(s) for s in COULEURS), unsafe_allow_html=True)
    for titre, cle_, defaut in (("Locaux", "locaux", "Local"), ("Espaces extérieurs", "espaces", "Espace")):
        entites = res[cle_]
        if not entites:
            continue
        st.subheader(titre)
        _tableau(entites, defaut)
        for i, x in enumerate(entites):
            with st.expander(f"Détail des règles — {x['nom'] or f'{defaut} {i + 1}'}"):
                for s in x["solutions"]:
                    with st.container(border=True):
                        _detail(x, s)
    pied()


# ------------------------------------------------------------------ passage en travaux
COULEURS_NIVEAU = {"A": "#5bba50", "B": "#ffc300", "C": "#ff5400"}


@st.cache_data(max_entries=20, show_spinner="Préparation du plan d'action…")
def _pdf_travaux(donnees_json: str) -> bytes:
    return rapport_travaux.generer_pdf(json.loads(donnees_json))


@st.cache_data(max_entries=20, show_spinner="Préparation des CCTP…")
def _zip_cctp(donnees_json: str) -> bytes:
    return CC.dossier(json.loads(donnees_json))


@st.cache_data(max_entries=20, show_spinner="Préparation du pré-programme…")
def _pdf_preprogramme(donnees_json: str) -> bytes:
    return rapport_preprogramme.generer_pdf(json.loads(donnees_json))


@st.cache_data(max_entries=40, show_spinner="Préparation du CCTP…")
def _docx_piece(donnees_json: str, n) -> bytes:
    d = json.loads(donnees_json)
    e = travaux.etat(d)
    mention = "Généré par l'outil ACTEE à partir du diagnostic (" + ("version validée" if e["valide"] else
                                                                    "PROJET non validé") + "). Modèle à adapter."
    return CC.docx(CC.remplir(n, d, e), mention)


def _euros(c) -> str:
    if not c:
        return "à chiffrer"
    if c["haut"] == 0:
        return "sans coût"
    if c["bas"] == c["haut"]:
        return f"env. {c['bas']:,.0f} € HT".replace(",", " ")
    return f"{c['bas']:,.0f} à {c['haut']:,.0f} € HT".replace(",", " ")


def _travaux_contexte():
    """Résultats, choix et état du module ; None (avec message) s'il n'y a ni local ni espace."""
    if travaux.externe(D):
        res = None
    elif ss.mode == "externe":
        st.info("Indiquez au moins une action préconisée par le diagnostic à l'étape « Diagnostic existant ».")
        pied()
        return None
    else:
        res = moteur.calculer(D)
        if not res["locaux"] and not res["espaces"]:
            st.info("Ajoutez au moins un local ou un espace extérieur pour préparer le passage en travaux.")
            pied()
            return None
    T = D.setdefault("travaux", {})
    return res, T, travaux.etat(D, res)


def _suffixe() -> str:
    base = unicodedata.normalize("NFKD", D["audit"].get("etablissement", "ecole")).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in base).strip("_") or "ecole"


def _pastille(texte, couleur):
    return (f"<span style='background:{couleur};padding:.1em .5em;font-weight:700;font-size:.8em;"
            f"white-space:nowrap'>{html.escape(texte)}</span>")


COULEURS_HORIZON = {1: "#5bba50", 2: "#0dcccc", 3: "#8dc8f8"}


def _vue_par_local(e) -> list[dict]:
    ordre = [x.get("L-01") or x.get("E-01") for x in D.get("locaux", []) + D.get("espaces", [])]
    par_nom = {}
    for o in e["retenues"]:
        for x in o["a_engager"] + o["a_valider"]:
            r = par_nom.setdefault(x["nom"], {"ops": [], "vig": {}})
            r["ops"].append(rapport_preprogramme.court(o) + (" (à confirmer)" if x in o["a_valider"] else ""))
            r["vig"].update(dict(x["vigilances"]))
    return [{"Local ou espace": n, "Opérations prévues": " · ".join(par_nom[n]["ops"]),
             "À vérifier": " · ".join(par_nom[n]["vig"].values()) or "—"}
            for n in sorted(par_nom, key=lambda n: ordre.index(n) if n in ordre else 999)]


# ------------------------------------------------------------------ étape : diagnostic existant
CHAMPS_BATIMENT_EXTERNE = [
    ("B-01", "Période de construction (le bâtiment le plus ancien concerné par les travaux)"),
    ("B-05", "Bâtiment classé ou inscrit au titre des monuments historiques"),
    ("B-06", "Abords de monument historique, site patrimonial remarquable ou repérage patrimonial"),
    ("B-04", "Isolation des murs"),
    ("B-08", "Alarme anti-intrusion"),
    ("B-09", "Ventilation mécanique existante"),
    ("B-10", "Type de ventilation mécanique"),
    ("B-14", "La ventilation peut-elle passer en grande vitesse ?"),
    ("B-15", "Programmation horaire possible (horloge, GTB)"),
    ("B-18", "Type de toiture au-dessus du dernier niveau"),
    ("B-21", "Combles ou espace non aménagé sous la toiture"),
    ("B-22", "Isolation des combles"),
    ("B-26", "Combles accessibles (trappe)"),
]


def _options_question(code: str) -> list[str]:
    def chercher(o):
        if isinstance(o, dict):
            if o.get("code") == code and o.get("options"):
                return o["options"]
            for v in o.values():
                r = chercher(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = chercher(v)
                if r:
                    return r
    return chercher(REFERENTIEL) or []


def _lignes(texte: str) -> list[str]:
    return [x.strip(" -•\t") for x in (texte or "").splitlines() if x.strip(" -•\t")]


def _config_ia() -> tuple[str | None, str | None]:
    try:
        conf = st.secrets["anthropic"]
        return conf.get("cle"), conf.get("modele")
    except Exception:
        return None, None


@st.cache_data(max_entries=10, ttl=86400, show_spinner="Lecture du rapport par l'IA : une à deux minutes…")
def _lecture_ia(pdf: bytes, modele: str | None) -> dict:
    return IA.analyser(pdf, _config_ia()[0], modele)


# Lecture des rapports par IA : désactivée en attendant la solution prévue pour février 2027 (le code est conservé).
LECTURE_IA_DISPONIBLE = False


def bloc_lecture_ia(de: dict):
    """Dépôt du PDF du rapport et pré-remplissage de la saisie par l'IA."""
    st.subheader("Pré-remplir à partir du rapport (IA)")
    if not LECTURE_IA_DISPONIBLE:
        st.info("**Bientôt disponible.** La lecture automatique du rapport de diagnostic par l'IA n'est pas encore "
                "proposée : une solution est en cours de développement, prévue pour **février 2027**. En attendant, "
                "reportez les préconisations du rapport dans la saisie ci-dessous.", icon="🕑")
        return
    cle_ia, modele = _config_ia()
    st.caption("Déposez le PDF du rapport : l'IA propose l'école, le bâtiment et les actions préconisées, avec pour "
               "chacune l'extrait du rapport et la page. Tout reste modifiable et doit être vérifié avant de continuer. "
               "Le rapport est envoyé au service d'IA (API Claude d'Anthropic) pour l'analyse.")
    if not cle_ia:
        st.info("Le module IA n'est pas encore configuré sur cette application : remplissez la saisie ci-dessous à la "
                "main, ou ajoutez la clé d'accès dans les réglages de l'application (section « anthropic » des secrets).")
        return
    fichier = st.file_uploader("PDF du rapport de diagnostic", type=["pdf"], key=cle("ext", "pdf"))
    if fichier is None:
        return
    libelle = "Remplacer la saisie par la lecture de l'IA" if de.get("operations") else "Lire le rapport et pré-remplir"
    if st.button(libelle, type="primary", key=cle("ext", "lire")):
        try:
            proposition = _lecture_ia(fichier.getvalue(), modele)
        except IA.LectureImpossible as err:
            st.error(str(err))
            return
        saisie, remarques = IA.vers_saisie(proposition, fichier.name)
        for k, v in saisie["audit"].items():
            if not D["audit"].get(k):
                D["audit"][k] = v
        for k, v in saisie["batiment"].items():
            D["batiment"].setdefault(k, v)
        D["diagnostic_externe"] = saisie["diagnostic_externe"]
        ss.remarques_ia = remarques
        ss.generation += 1  # les champs affichent les nouvelles valeurs
        st.rerun()


def etape_diagnostic_externe():
    """Saisie simplifiée d'un diagnostic réalisé hors de la méthode SURYA."""
    st.header("Diagnostic existant")
    st.markdown("<p class='actee-chapo'>Reportez ici les préconisations d'un diagnostic de confort d'été réalisé hors de "
                "la méthode SURYA. L'outil leur applique ensuite les mêmes règles que pour un diagnostic complet : "
                "niveau de mise en œuvre, maîtrise d'œuvre, prestations préalables, CCTP. L'auditeur reste responsable "
                "de la traduction du rapport : en cas de doute, cochez « à confirmer ».</p>", unsafe_allow_html=True)
    de = D.setdefault("diagnostic_externe", {})
    a = D.setdefault("audit", {})
    bloc_lecture_ia(de)
    li = de.get("lecture_ia")
    if li:
        st.warning(f"**Saisie pré-remplie par l'IA** à partir de « {li.get('fichier', '')} » le {li.get('date', '')}. "
                   "Vérifiez chaque champ et chaque action avec l'extrait cité avant de passer au pré-programme.",
                   icon="🤖")
        for r in ss.get("remarques_ia") or [f"À classer à la main (sans équivalent dans la liste) : {h}"
                                             for h in li.get("hors_catalogue", [])]:
            st.caption("• " + r)

    st.subheader("1. Le diagnostic d'origine et l'école")
    c1, c2 = st.columns(2)
    de["source"] = c1.text_input("Diagnostic d'origine (bureau d'études, programme)", value=de.get("source", ""),
                                 placeholder="Ex. : Inddigo – diagnostic confort estival (Banque des Territoires)",
                                 key=cle("ext", "source")).strip()
    de["date"] = c2.text_input("Date du rapport", value=de.get("date", ""), placeholder="jj/mm/aaaa",
                               key=cle("ext", "date")).strip()
    for k, lib in (("etablissement", "Établissement"), ("adresse", "Adresse"), ("commune", "Commune"),
                   ("moa", "Maître d'ouvrage")):
        a[k] = (c1 if k in ("etablissement", "commune") else c2).text_input(lib, value=a.get(k, ""),
                                                                             key=cle("ext", k)).strip()
    a.setdefault("auditeur", de.get("source", ""))
    a["date_visite"] = c2.text_input("Date de la visite du diagnostic", value=a.get("date_visite", ""),
                                     placeholder="jj/mm/aaaa", key=cle("ext", "visite")).strip()

    st.subheader("2. Le bâtiment")
    st.caption("Ces informations modifient le niveau des opérations et le contenu des CCTP (amiante, patrimoine, "
               "ventilation, toiture). Laissez « non renseigné » si le rapport ne le dit pas.")
    b = D.setdefault("batiment", {})
    cols = st.columns(2)
    for i, (code, lib) in enumerate(CHAMPS_BATIMENT_EXTERNE):
        if code == "B-10" and b.get("B-09") != "Oui":
            continue
        if code in ("B-14", "B-15") and b.get("B-09") != "Oui":
            continue
        if code in ("B-22", "B-26") and b.get("B-21") != "Oui":
            continue
        opts = [""] + _options_question(code)
        val = b.get(code, "")
        choix_b = cols[i % 2].selectbox(lib, opts, index=opts.index(val) if val in opts else 0,
                                        format_func=lambda x: x or "Non renseigné", key=cle("ext", code))
        if choix_b:
            b[code] = choix_b
        else:
            b.pop(code, None)

    st.subheader("3. Les actions préconisées par le diagnostic")
    st.caption("Cochez chaque action du rapport et indiquez où elle s'applique. Une action sans équivalent dans la liste "
               "peut être décrite dans le commentaire de l'action la plus proche.")
    actuelles = {x["solution"]: x for x in de.get("operations") or []}
    nouvelles = []
    ordre = list(travaux.LEVIERS)
    par_groupe = {}
    for sol in travaux.CATALOGUE:
        par_groupe.setdefault(travaux.GROUPES.get(sol, "Autres"), []).append(sol)
    for g in sorted(par_groupe, key=lambda g: ordre.index(g) if g in ordre else 99):
        st.markdown(f"#### {travaux.LEVIERS.get(g, (g,))[0]}")
        for sol in par_groupe[g]:
            x = actuelles.get(sol, {})
            c = travaux.CATALOGUE[sol]
            with st.container(border=True):
                coche = st.checkbox(f"**{c['action']}**", value=bool(x), key=cle("ext", sol, "on"),
                                    help=f"Fiche {c['fiche']} du kit · {c['prestataire']}")
                if not coche:
                    continue
                if x.get("origine") == "ia":
                    st.caption("🤖 Proposé par l'IA" + (f" — p. {x['page']}" if x.get("page") else "")
                               + (f" : « {x['extrait']} »" if x.get("extrait") else "") + " — à vérifier")
                c1, c2 = st.columns(2)
                locaux = c1.text_area("Locaux ou espaces concernés (un par ligne)", value="\n".join(x.get("locaux", [])),
                                      key=cle("ext", sol, "locaux"), height=90)
                conf = c2.text_area("À confirmer (un par ligne)", value="\n".join(x.get("a_confirmer", [])),
                                    key=cle("ext", sol, "conf"), height=90,
                                    help="Locaux où le diagnostic émet une réserve ou manque d'une donnée.")
                y = {"solution": sol, "locaux": _lignes(locaux), "a_confirmer": _lignes(conf)}
                y.update({k: x[k] for k in ("origine", "extrait", "page") if x.get(k)})
                alertes = travaux.ALERTES_PAR_SOLUTION.get(sol, [])
                if alertes:
                    y["alertes"] = st.multiselect("Points d'alerte relevés", alertes, default=[a_ for a_ in x.get("alertes", [])
                                                                                          if a_ in alertes],
                                                  format_func=lambda k: f"{k} — {REGLES[k]['regle'][:110]}",
                                                  key=cle("ext", sol, "alertes"))
                if sol == "Mise en place de brasseurs d'air plafonniers":
                    y["hauteur_limite"] = st.checkbox("Hauteur sous plafond limite ou faux plafond à traverser",
                                                      value=x.get("hauteur_limite", False), key=cle("ext", sol, "h"))
                vig = st.text_area("Points de vigilance du rapport (un par ligne)", value="\n".join(x.get("vigilances", [])),
                                   key=cle("ext", sol, "vig"), height=70)
                y["vigilances"] = _lignes(vig)
                c3, c4 = st.columns([1, 2])
                niv = c3.selectbox("Niveau", ["", "A", "B", "C"], index=["", "A", "B", "C"].index(x.get("niveau", "")),
                                   format_func=lambda k: k or "Proposé par l'outil", key=cle("ext", sol, "niv"))
                if niv:
                    y["niveau"] = niv
                com = c4.text_input("Commentaire", value=x.get("commentaire", ""), key=cle("ext", sol, "com")).strip()
                if com:
                    y["commentaire"] = com
                nouvelles.append(y)
    de["operations"] = nouvelles
    if de.get("lecture_ia") and not nouvelles:
        de.pop("lecture_ia", None)
    if nouvelles:
        st.success(f"{len(nouvelles)} action(s) reportée(s). Le pré-programme les reprend à l'étape suivante.")
    pied("Suivant : Pré-programme →")


# ------------------------------------------------------------------ étape : pré-programme
def etape_preprogramme():
    """Ce que l'on propose de faire, pourquoi, où, pour quel coût : relu par l'auditeur, téléchargeable en PDF."""
    st.header("Pré-programme")
    ctx_t = _travaux_contexte()
    if not ctx_t:
        return
    res, T, e = ctx_t
    st.markdown("<p class='actee-chapo'>Le pré-programme traduit le diagnostic en <b>opérations</b> : ce que la "
                "collectivité peut faire pour protéger les occupants de la chaleur, <b>pourquoi</b>, <b>où</b>, "
                "<b>quand</b> et pour quel <b>coût indicatif</b>. L'auditeur relit chaque opération et peut la "
                "retirer, avec un motif. Le PDF est le document à présenter aux élus.</p>", unsafe_allow_html=True)
    if not e["operations"]:
        st.success("Le diagnostic ne fait ressortir aucune opération à engager.")
        pied()
        return

    st.subheader("1. Ce que nous proposons, et pourquoi")
    st.caption("Dans l'ordre de la démarche : empêcher la chaleur d'entrer, l'évacuer la nuit, rendre la chaleur "
               "restante supportable.")
    ops_choix = T.setdefault("operations", {})
    ordre = list(travaux.LEVIERS)
    for g in sorted({o["groupe"] for o in e["operations"]}, key=lambda g: ordre.index(g) if g in ordre else 99):
        titre, pourquoi = travaux.LEVIERS.get(g, (g, ""))
        st.markdown(f"#### {titre}")
        st.caption(pourquoi)
        for o in [o for o in e["operations"] if o["groupe"] == g]:
            with st.container(border=True):
                st.markdown(f"**{html.escape(o['action'])}** &nbsp; "
                            + _pastille(travaux.HORIZONS[o["horizon"]], COULEURS_HORIZON[o["horizon"]]) + " &nbsp; "
                            + _pastille(f"niveau {o['niveau']}", COULEURS_NIVEAU[o["niveau"]]),
                            unsafe_allow_html=True)
                ou = [x["nom"] for x in o["a_engager"]] + [f"{x['nom']} (à confirmer)" for x in o["a_valider"]]
                st.caption(f"Où : {', '.join(ou)}")
                retenue = st.checkbox("Retenir cette opération", value=o["retenue"], key=cle("trav", o["id"], "ret"))
                motif = o["motif"]
                if not retenue:
                    motif = st.text_input("Motif du retrait (obligatoire)", value=o["motif"],
                                          key=cle("trav", o["id"], "motif"),
                                          placeholder="Déjà programmé, refus de la commune, solution de repli inutile…")
                    if not motif.strip():
                        st.warning("Indiquez le motif du retrait.")
                ops_choix[o["id"]] = {"retenue": retenue, "motif": motif.strip()}
                with st.expander("Ce que le diagnostic a constaté"):
                    st.markdown(f"*{rapport_preprogramme._bref(o['fiche'], o['solution'])}*")
                    for x in o["a_engager"] + o["a_valider"]:
                        vig = "".join(f"  \n⚠️ {html.escape(t)}" for a, t in x["vigilances"])
                        st.markdown(f"**{html.escape(x['nom'])}** — {x['statut']}"
                                    + (f" : {html.escape(x['libelle_regle'])}" if x["libelle_regle"] else "") + vig)
                    if o["raisons_niveau"]:
                        st.caption("Niveau " + o["niveau"] + " : " + " ; ".join(o["raisons_niveau"]))
                    if o["hypotheses"]:
                        st.caption("Quantité estimée pour les CCTP : " + " ; ".join(o["hypotheses"]))
    e = travaux.etat(D, res)

    st.subheader("2. Local par local")
    st.caption("Les opérations prévues dans chaque local ou espace, et ce qu'il faut vérifier avant les travaux.")
    st.dataframe(_vue_par_local(e), hide_index=True, width="stretch")
    if e["completer"]:
        st.info("Données à compléter : " + " ; ".join(f"**{n}** ({', '.join(s)})" for n, s in e["completer"].items()))

    st.subheader("3. Calendrier")
    st.metric("Opérations retenues", len(e["retenues"]))
    for h in (1, 2, 3):
        ops = [o for o in e["retenues"] if o["horizon"] == h]
        if ops:
            st.markdown(_pastille(travaux.HORIZONS[h], COULEURS_HORIZON[h]) + " &nbsp; "
                        + html.escape(", ".join(rapport_preprogramme.court(o) for o in ops)), unsafe_allow_html=True)
    st.info(travaux.MESSAGE_COUTS)

    st.subheader("4. Le document à présenter")
    st.download_button("Télécharger le pré-programme (PDF)", _pdf_preprogramme(json.dumps(D, ensure_ascii=False,
                                                                                       sort_keys=True)),
                       file_name=f"pre_programme_{_suffixe()}.pdf", mime="application/pdf", type="primary")
    st.caption("Quoi, pourquoi, où, comment ; local par local ; études préalables ; prochaines étapes. Il porte la "
               "mention « projet » tant que la validation (étape suivante) n'est pas faite.")
    pied("Suivant : maîtrise d'œuvre et accompagnement →")


# ------------------------------------------------------------------ étape : accompagnement
def etape_accompagnement():
    """Maîtrise d'œuvre en priorité, mise en garde, ingénierie du territoire ; validation du pré-programme."""
    st.header("Accompagnement")
    ctx_t = _travaux_contexte()
    if not ctx_t:
        return
    res, T, e = ctx_t
    st.markdown("<p class='actee-chapo'>Avant de consulter des prestataires, la collectivité choisit comment elle "
                "conduit son projet : avec une <b>maîtrise d'œuvre</b>, recommandée dès que les travaux touchent "
                "le bâtiment, et avec l'appui d'une <b>structure d'ingénierie</b> si elle n'a pas de service "
                "technique.</p>", unsafe_allow_html=True)

    st.subheader("1. Maîtrise d'œuvre")
    m = T.setdefault("moe", {"choix": "auto", "motif": ""})
    if e["moe_auto"]:
        st.error("**Une maîtrise d'œuvre est fortement recommandée pour cette école.**  \n"
                 + "  \n".join(f"- {r.split(' — ', 1)[-1]}" for r in e["raisons_moe"]))
        st.markdown("Elle conçoit l'ensemble des travaux, vérifie leur faisabilité (structure, urbanisme, sécurité "
                    "incendie), consulte les entreprises et suit le chantier. **Toutes les opérations de travaux lui "
                    "sont confiées**, quel que soit leur niveau, pour qu'un seul professionnel en soit responsable.")
    else:
        st.info("Au vu des opérations retenues, une maîtrise d'œuvre n'est pas indispensable. Elle reste utile si la "
                "collectivité veut confier la conception et le suivi à un professionnel.")
    with st.container(border=True):
        st.markdown("**⚠️ Faire sans maîtrise d'œuvre expose à des risques :**")
        st.markdown("\n".join(f"- {r}" for r in travaux.RISQUES_SANS_MOE))
    options = {"auto": "Suivre la proposition de l'outil", "oui": "Recommander une maîtrise d'œuvre",
               "non": "Ne pas recommander de maîtrise d'œuvre"}
    m["choix"] = st.radio("Verdict retenu par l'auditeur", list(options), format_func=options.get,
                          index=list(options).index(m.get("choix", "auto")), key=cle("trav", "moe"), horizontal=True)
    if m["choix"] != "auto":
        m["motif"] = st.text_input("Motif (obligatoire si le verdict diffère de la proposition)", value=m.get("motif", ""),
                                   key=cle("trav", "moe_motif")).strip()
        if e["moe_auto"] and m["choix"] == "non":
            st.warning("Écarter la maîtrise d'œuvre recommandée demande un motif et le visa du chargé de mission ou "
                       "de l'économe de flux (section 3).")
    with st.expander("Règles de l'outil (M1 à M5)"):
        st.caption("M1 : opération de niveau C · M2 : plusieurs familles touchent l'enveloppe, la toiture ou les "
                   "extérieurs · M3 : alerte de structure · M4 : bâtiment protégé avec travaux de façade · M5 : coût "
                   "au-delà du seuil, **inactive tant que la base de données de coûts n'existe pas**. Propositions "
                   "ACTEE, à valider.")
        seuil = st.number_input("Seuil de coût de la règle M5 (€ HT)", min_value=0, step=10000,
                                value=int(e["choix"]["seuil_moe"]), key=cle("trav", "seuil"))
    if seuil != travaux.SEUIL_MOE_DEFAUT:
        T["seuil_moe"] = seuil
    else:
        T.pop("seuil_moe", None)
    e = travaux.etat(D, res)

    st.subheader("2. Ingénierie de la collectivité")
    a = T.setdefault("accompagnement", {"ingenierie": ""})
    choix_ing = {"": "Non renseigné", "oui": "Oui", "non": "Non", "nsp": "Ne sait pas"}
    a["ingenierie"] = st.radio("La collectivité dispose-t-elle d'un service technique capable de piloter les études "
                               "et les travaux ?", list(choix_ing), format_func=choix_ing.get,
                               index=list(choix_ing).index(a.get("ingenierie", "")), key=cle("trav", "ing"),
                               horizontal=True)
    if a["ingenierie"] in ("non", "nsp"):
        st.info("**Nous recommandons de se faire accompagner par une structure d'ingénierie du territoire**, pour "
                "préparer les consultations, choisir les prestataires et suivre les travaux.")
    structures_locales(a, e)
    e = travaux.etat(D, res)

    st.subheader("3. Validation du pré-programme")
    v = T.setdefault("validation", {})
    c1, c2 = st.columns(2)
    v["auditeur"] = c1.text_input("Revue par (auditeur)", value=v.get("auditeur", D["audit"].get("auditeur", "")),
                                  key=cle("trav", "auditeur")).strip()
    v["date_revue"] = c2.text_input("Date de la revue", value=v.get("date_revue", ""), placeholder="jj/mm/aaaa",
                                    key=cle("trav", "date_revue")).strip()
    v["visa"] = c1.text_input("Visa (chargé de mission ou économe de flux)", value=v.get("visa", ""),
                              key=cle("trav", "visa")).strip()
    v["date_visa"] = c2.text_input("Date du visa", value=v.get("date_visa", ""), placeholder="jj/mm/aaaa",
                                   key=cle("trav", "date_visa")).strip()
    e = travaux.etat(D, res)
    for x in e["anomalies"]:
        st.error(x)
    if e["valide"]:
        st.success("Pré-programme validé : les documents ne portent plus la mention « projet ».")
    else:
        st.caption("Tant que la revue, le visa et leurs dates ne sont pas renseignés (et sans anomalie), les documents "
                   "portent la mention « projet ».")
    st.download_button("Télécharger le pré-programme (PDF)", _pdf_preprogramme(json.dumps(D, ensure_ascii=False,
                                                                                       sort_keys=True)),
                       file_name=f"pre_programme_{_suffixe()}.pdf", mime="application/pdf",
                       key="pdf_pp_accompagnement")
    pied("Suivant : " + ("recruter la maîtrise d'œuvre →" if e["moe"] else "fiches travaux →"))


# ------------------------------------------------------------------ structures d'ingénierie locale
@st.cache_data(ttl=86400, max_entries=200, show_spinner="Recherche de la commune…")
def _communes(cp: str) -> list[dict]:
    return IG.communes(cp)


@st.cache_data(ttl=86400, max_entries=200, show_spinner="Recherche des structures du territoire…")
def _structures(commune_json: str) -> dict:
    return IG.rechercher(json.loads(commune_json))


def _carte(commune: dict, structures: list[dict]):
    """Carte : la commune et les structures géolocalisées (une couleur par type)."""
    points = [{"lat": commune["lat"], "lon": commune["lon"], "nom": f"{commune['nom']} (commune)",
               "type": "Commune", "couleur": [0, 0, 0, 230], "rayon": 1400}] if commune.get("lat") else []
    for x in structures:
        if x.get("lat") is not None and x.get("lon") is not None:
            lib, _, rgb = IG.TYPES.get(x["type"], (x["type"], "", (90, 90, 90)))
            points.append({"lat": x["lat"], "lon": x["lon"], "nom": x["nom"], "type": lib,
                           "couleur": [*rgb, 220], "rayon": 1000})
    if not points:
        return
    try:
        import pydeck as pdk
        couche = pdk.Layer("ScatterplotLayer", data=points, get_position="[lon, lat]", get_fill_color="couleur",
                           get_radius="rayon", radius_min_pixels=6, radius_max_pixels=14, pickable=True,
                           stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1)
        vue = pdk.ViewState(latitude=commune.get("lat") or points[0]["lat"],
                            longitude=commune.get("lon") or points[0]["lon"], zoom=8.2)
        st.pydeck_chart(pdk.Deck(layers=[couche], initial_view_state=vue, map_provider="carto",
                                 map_style=getattr(pdk.map_styles, "CARTO_LIGHT", "light"),
                                 tooltip={"text": "{nom}\n{type}"}), height=380)
    except Exception:  # pydeck indisponible : carte simple
        import pandas as pd
        st.map(pd.DataFrame(points)[["lat", "lon"]], height=380)
    vus = []
    for p in points:
        if p["type"] not in [v[0] for v in vus]:
            vus.append((p["type"], p["couleur"]))
    st.markdown(" ".join(f"<span style='display:inline-block;width:.8em;height:.8em;border-radius:50%;"
                         f"background:rgb({c[0]},{c[1]},{c[2]});margin:0 .3em 0 .8em'></span>{html.escape(t)}"
                         for t, c in vus), unsafe_allow_html=True)


def _carte_structure(x: dict):
    tel = x["telephone"]
    liens = []
    if tel:
        liens.append("📞 " + " / ".join(f"[{t.strip()}](tel:{re.sub(r'[^0-9+]', '', t)})" for t in tel.split("/")))
    if x["courriel"]:
        liens.append("✉️ " + " / ".join(f"[{c.strip()}](mailto:{c.strip()})" for c in x["courriel"].split("/")))
    if x["site"]:
        liens.append(f"🌐 [{'fiche SIRENE' if 'annuaire-entreprises' in x['site'] else 'site'}]({x['site']})")
    with st.container(border=True):
        st.markdown(f"**{x['nom']}**" + (" &nbsp; :orange[à vérifier]" if x.get("a_verifier") else "")
                    + (f" &nbsp; :gray[{x['distance_km']:g} km]" if x.get("distance_km") is not None else ""))
        if x.get("adresse"):
            st.caption(x["adresse"])
        st.markdown(" &nbsp;·&nbsp; ".join(liens) if liens else ":gray[Coordonnées non disponibles en données ouvertes.]")


def structures_locales(a: dict, e: dict):
    """Recherche par code postal des structures qui peuvent accompagner la commune, avec carte et contacts."""
    st.markdown("#### Qui peut vous accompagner sur votre territoire ?")
    st.caption("Saisissez le code postal de la commune : l'outil cherche les structures d'ingénierie qui peuvent, au "
               "moins en théorie, l'accompagner (intercommunalité, syndicat d'énergie, agence technique, CAUE, ALEC, "
               "SPL, centre de ressources…). Contactez-les pour leur demander si elles peuvent vous aider sur le "
               "passage en travaux.")
    c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
    cp = c1.text_input("Code postal de la commune", value=a.get("code_postal", ""), max_chars=5,
                       key=cle("trav", "cp")).strip()
    choisie = None
    if cp:
        try:
            liste = _communes(cp)
        except ValueError as err:
            st.warning(str(err))
            liste = []
        except Exception:
            st.error("Le service de recherche des communes ne répond pas. Réessayez dans un instant.")
            liste = []
        if cp and liste:
            noms = [f"{c['nom']} ({c['code']})" for c in liste]
            defaut = next((i for i, c in enumerate(liste) if c["code"] == a.get("code_insee")), 0)
            i = c2.selectbox("Commune", range(len(liste)), format_func=lambda i: noms[i], index=defaut,
                             key=cle("trav", "commune")) if len(liste) > 1 else 0
            choisie = liste[i or 0]
        elif cp and len(re.sub(r"\D", "", cp)) == 5:
            st.warning("Aucune commune trouvée pour ce code postal.")
    if not choisie:
        return
    if c2.button("Rechercher les structures", type="primary", key=cle("trav", "chercher")) or (
            a.get("code_insee") == choisie["code"] and a.get("structures")):
        if a.get("code_insee") != choisie["code"] or not a.get("structures"):
            r = _structures(json.dumps(choisie, sort_keys=True))
            a.update({"code_postal": cp, "code_insee": choisie["code"], "commune": choisie["nom"],
                      "structures": r["structures"], "date_recherche": dt.date.today().strftime("%d/%m/%Y")})
            for err in r["erreurs"]:
                st.warning(err)
        structures = a.get("structures") or []
        if not structures:
            st.info("Aucune structure trouvée.")
            return
        st.markdown(f"**{len(structures)} structures** autour de {html.escape(a.get('commune', ''))} "
                    f"(recherche du {a.get('date_recherche', '')}).")
        _carte(choisie, structures)
        for t, (lib, pourquoi, _) in IG.TYPES.items():
            xs = [x for x in structures if x["type"] == t]
            if not xs:
                continue
            st.markdown(f"**{lib}**")
            st.caption(pourquoi)
            for x in xs:
                _carte_structure(x)
        with st.expander("Modèle de message à envoyer"):
            st.code(IG.message(a.get("commune", ""), D["audit"].get("etablissement", ""), e["moe"]), language=None)
        st.caption("Sources : annuaire de l'administration (service-public.gouv.fr), répertoire SIRENE (API Recherche "
                   "d'entreprises) et fichier de contacts ACTEE. « À vérifier » : structure repérée automatiquement dans "
                   "SIRENE, dont il faut confirmer le rôle et chercher les coordonnées sur son site. La liste figure "
                   "dans le PDF du pré-programme.")
        if st.button("Relancer la recherche", key=cle("trav", "relancer")):
            a.pop("structures", None)
            _structures.clear()
            st.rerun()


# ------------------------------------------------------------------ étape : mise en œuvre
def _fiche_ui(o, e):
    f = travaux.FICHES[o["fiche"]]
    with st.container(border=True):
        st.markdown(f"**{html.escape(o['action'])}** &nbsp; "
                    + _pastille(travaux.HORIZONS[o["horizon"]], COULEURS_HORIZON[o["horizon"]]),
                    unsafe_allow_html=True)
        pieces = ", ".join(travaux.pieces_operation(o, e)) or "fiche du kit seule"
        st.caption(f"Prestataire : {o['prestataire']} · Fiche {o['fiche']} « {f['titre']} » · {pieces}")
        with st.expander("Rôle du maître d'ouvrage, étape par étape"):
            if travaux.sans_fiche(o):
                st.markdown(travaux.sans_fiche(o))
            else:
                st.markdown("\n".join(f"{i}. **{t}** — {txt}" for i, (t, txt) in enumerate(f["etapes"], 1)))
            if o.get("commentaire"):
                st.caption("Note du diagnostic : " + o["commentaire"])
            vig_site = [(x["nom"], t) for x in o["a_engager"] + o["a_valider"] for a, t in x["vigilances"]]
            if vig_site:
                st.markdown("**Points de vigilance propres à l'école**")
                st.markdown("\n".join(f"- {html.escape(n)} : {html.escape(t)}" for n, t in vig_site))
            if f.get("vigilances") and not travaux.sans_fiche(o):
                st.markdown("**Vigilances générales**  \n" + " ".join(f["vigilances"]))


def etape_mise_en_oeuvre():
    """Avec MOE : le CCTP de maîtrise d'œuvre ; sans MOE : les fiches travaux."""
    st.header("Mise en œuvre")
    ctx_t = _travaux_contexte()
    if not ctx_t:
        return
    res, T, e = ctx_t
    dj = json.dumps(D, ensure_ascii=False, sort_keys=True)
    if e["moe"]:
        st.subheader("Recruter la maîtrise d'œuvre")
        st.markdown("<p class='actee-chapo'>Le cahier des charges de maîtrise d'œuvre est construit à partir du "
                    "pré-programme : <b>toutes les opérations de travaux</b> sont confiées à l'équipe, et chaque "
                    "famille d'opérations active un <b>volet</b> de la mission (compétences, relevés, choix à "
                    "justifier, points d'arrêt de chantier).</p>", unsafe_allow_html=True)
        volets = sorted({travaux._volet(o) for o in e["ops_moe"]})
        st.markdown("**Volets activés** : " + ", ".join(CC.VOLETS[v] for v in volets))
        st.markdown("**Opérations confiées** :  \n" + "  \n".join(f"- {o['action']}" for o in e["ops_moe"]))
        c1, c2 = st.columns(2)
        c1.download_button("CCTP de maîtrise d'œuvre (Word)", _docx_piece(dj, "MOE"),
                           file_name=f"CCTP_MOE_{_suffixe()}.docx", type="primary", width="stretch",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        c1.caption("Modifiable ; les champs à compléter sont surlignés.")
        c2.download_button("Plan d'action (PDF)", _pdf_travaux(dj), file_name=f"plan_action_{_suffixe()}.pdf",
                           mime="application/pdf", width="stretch")
        c2.caption("Opérations, fiches et feuille de route du maître d'ouvrage.")
        with st.expander("Aperçu du CCTP de maîtrise d'œuvre"):
            st.markdown(CC.remplir("MOE", D, e))
        if e["ops_moa"]:
            st.markdown("#### À engager tout de suite par la collectivité")
            st.caption("Actions d'organisation ou de réglage, sans travaux : elles n'attendent pas la maîtrise d'œuvre.")
            for o in e["ops_moa"]:
                _fiche_ui(o, e)
    else:
        st.subheader("Fiches travaux")
        st.markdown("<p class='actee-chapo'>Sans maîtrise d'œuvre, la collectivité conduit elle-même chaque "
                    "opération. Chaque fiche dit ce qu'elle doit faire, étape par étape, avec les points de "
                    "vigilance relevés dans cette école. Les cahiers des charges sont à l'étape suivante.</p>",
                    unsafe_allow_html=True)
        for h in (1, 2, 3):
            ops = [o for o in e["retenues"] if o["horizon"] == h]
            if ops:
                st.markdown(f"#### {travaux.HORIZONS[h]}")
                for o in ops:
                    _fiche_ui(o, e)
        st.download_button("Plan d'action avec les fiches (PDF)", _pdf_travaux(dj),
                           file_name=f"plan_action_{_suffixe()}.pdf", mime="application/pdf", type="primary")
    pied("Suivant : cahiers des charges →")


# ------------------------------------------------------------------ étape : consultations
def etape_consultations():
    """Prestations préalables puis CCTP travaux, et le dossier complet en ZIP."""
    st.header("Consultations")
    ctx_t = _travaux_contexte()
    if not ctx_t:
        return
    res, T, e = ctx_t
    dj = json.dumps(D, ensure_ascii=False, sort_keys=True)
    st.markdown("<p class='actee-chapo'>Les cahiers des charges sont pré-remplis avec les données du diagnostic. "
                "Ils sont à relire et à compléter (champs surlignés en jaune) avant envoi.</p>", unsafe_allow_html=True)
    if e["pieces"]:
        st.download_button("Tout le dossier (ZIP de fichiers Word)", _zip_cctp(dj), file_name=f"cctp_{_suffixe()}.zip",
                           mime="application/zip", type="primary")
    pourquoi = {
        6: "L'installation de ventilation ne permet peut-être pas le mode été par simple réglage.",
        7: "Connaître l'état de la toiture et de son isolant avant de choisir une solution.",
        10: "Obligatoire avant travaux dans un bâtiment construit avant juillet 1997.",
        11: "Vérifier que les supports peuvent porter ou ancrer les équipements prévus.",
        12: "Travaux qui chargent la structure ou touchent à la sécurité incendie d'un établissement recevant du public.",
        13: "Obligatoire dès que plusieurs entreprises interviennent.",
    }
    sections = [("prealable", "1. Prestations préalables",
                 "Diagnostics, contrôle et coordination, commandés directement par la collectivité."),
                ("travaux", "2. Travaux et commandes", "Un CCTP par prestataire."),
                ("reference", "2. CCTP travaux, base pour la maîtrise d'œuvre",
                 "La maîtrise d'œuvre rédige les pièces de consultation des entreprises ; ces CCTP du kit lui sont "
                 "transmis comme base.")]
    for cat, titre, aide in sections:
        pcs = [(n, x) for n, x in e["pieces"].items() if x["categorie"] == cat]
        if not pcs:
            continue
        st.subheader(titre)
        st.caption(aide)
        for n, x in pcs:
            with st.container(border=True):
                c1, c2 = st.columns([0.75, 0.25], vertical_alignment="center")
                c1.markdown(f"**{travaux.CCTP[n]}**")
                c1.caption((pourquoi.get(n, "") + " " if cat == "prealable" else "") + "Pour : "
                           + ", ".join(rapport_preprogramme.court(o) for o in x["operations"]))
                c2.download_button("Word", _docx_piece(dj, n), file_name=f"{CC.nom_fichier(n)}_{_suffixe()}.docx",
                                   key=f"docx_{n}", width="stretch",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                with st.expander("Aperçu"):
                    st.markdown(CC.remplir(n, D, e))
    st.subheader("Feuille de route du maître d'ouvrage")
    st.dataframe([{"Phase": t["phase"], "Ce qu'il faut faire": t["quoi"], "Qui": t["qui"], "Quand": t["quand"],
                   "Ce qui en sort": t["sortie"]} for t in e["feuille_de_route"]], hide_index=True, width="stretch")
    pied()

# ------------------------------------------------------------------ réglages
def vue_reglages():
    if st.button("← Retour à l'audit"):
        ss.vue = "parcours"
        st.rerun()
    st.title("Réglages")
    t1, t2, t3 = st.tabs(["Données", "Seuils des règles", "Notice d'utilisation"])
    with t3:
        notice()
    with t1:
        st.caption("Maquette : rien n'est enregistré sur un serveur. Exportez la saisie (JSON) pour la conserver et "
                   "la réimporter plus tard.")
        bloc_donnees(prefixe="reglages")
        st.divider()
        if st.button("🗑 Tout effacer et recommencer", help="Nouvel audit vide (un audit déjà enregistré reste en base)."):
            charger(donnees_vides())
            ss.mode, ss.vue = None, "parcours"
            st.rerun()
    with t2:
        st.caption("Valeurs de l'onglet « Paramètres » de l'Excel. Toute modification s'applique immédiatement aux "
                   "règles citées et est signalée dans le compte rendu.")
        p = D["parametres"]
        if st.button("Rétablir les valeurs par défaut"):
            p.clear()
            ss.generation += 1
            st.rerun()
        for q in REFERENTIEL["parametres"]:
            c1, c2 = st.columns([1, 3], vertical_alignment="center")
            v = c1.number_input(f"{q['nom']} ({q['unite']})" if q["unite"] else q["nom"],
                                value=float(moteur.parametres(p)[q["nom"]]), step=0.05 if q["valeur"] < 1 else 0.5,
                                key=cle("param", q["nom"]))
            c2.markdown(f"{q['signification']}  \n:gray[Règles : {q['regles']}]")
            if v != q["valeur"]:
                p[q["nom"]] = v
            else:
                p.pop(q["nom"], None)


# ------------------------------------------------------------------ aiguillage
ETAPES = {"Diagnostic existant": lambda: etape_diagnostic_externe(), "Identification": etape_identification, "Bâtiment": etape_batiment, "Façades": etape_facades,
          "Locaux": lambda: etape_entites("locaux"), "Espaces extérieurs": lambda: etape_entites("espaces"),
          "Questionnaires usagers": etape_questionnaires,
          "Vérification": etape_verification, "Résultats": etape_documents, "Documents": etape_documents,
          "Pré-programme": lambda: etape_preprogramme(), "Accompagnement": lambda: etape_accompagnement(),
          "Mise en œuvre": lambda: etape_mise_en_oeuvre(), "Consultations": lambda: etape_consultations()}

charte()
if st.query_params.get("questionnaire"):
    page_usager(st.query_params["questionnaire"])
elif ss.mode is None:
    ecran_depart()
elif ss.vue == "reglages":
    entete()
    vue_reglages()
else:
    ss.etape = min(ss.etape, len(etapes()) - 1)
    entete()
    ETAPES[etapes()[ss.etape]]()
st.html(f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:2rem;"
        f"font-size:0.8rem;color:#000'><div style='display:flex;align-items:center;gap:10px'>"
        f"<span>Programme financé par</span><img src='{_img64(LOGO_CEE)}' alt='Les certificats d’économies d’énergie (CEE)' "
        f"style='height:36px'></div><div>{version.libelle()}</div></div>")
remonter()
