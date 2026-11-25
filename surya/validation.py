"""Contrôle et normalisation d'une saisie importée (JSON ou Excel).

Un fichier retouché à la main ou un Excel saisi hors des listes peut contenir des nombres en texte
(« 2,5 »), des réponses hors liste (« oui »), des valeurs négatives ou hors bornes. ``valider`` :

* convertit ce qui peut l'être sans ambiguïté (« 2,5 » → 2.5, « oui » → « Oui ») ;
* retire ce qui ne peut pas l'être : la question redevient sans réponse, donc « donnée manquante »
  (« Sous réserve »), jamais une réponse fausse ;
* renvoie la liste des corrections, à afficher à l'utilisateur.
"""
from __future__ import annotations

import copy
import re
import unicodedata

from . import questionnaire as QU
from .moteur import NB_MURS_MAX, ORIENTATIONS, REFERENTIEL, parametres

BORNES = {"E-30": (0, 4)}  # bornes particulières ; tous les autres nombres doivent être positifs ou nuls


def _cle(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).lower().replace("’", "'").replace("...", "…")
    return re.sub(r"\s+", " ", s).strip()


def _option(v, options):
    """Option correspondante (à la casse, aux espaces et aux apostrophes près), ou None."""
    if v in options:
        return v
    k = _cle(v)
    return next((o for o in options if _cle(o) == k), None)


def nombre(v):
    """Nombre, ou texte « 2,5 » / « 60 » converti ; None si inexploitable."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        x = float(str(v).strip().replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return int(x) if x.is_integer() and re.fullmatch(r"\s*-?\d+\s*", str(v)) else x


def _questions(sections):
    return {q["code"]: q for s in sections for q in s["questions"]}


QUESTIONS = {
    "batiment": _questions(REFERENTIEL["batiment"]),
    "locaux": {**_questions(REFERENTIEL["locaux"]),
               "BA-18": {"code": "BA-18", "type": "nombre", "libelle": "Débit maximal de ventilation mécanique"}},
    "espaces": _questions(REFERENTIEL["espaces"]),
}
MUR = {q["code"]: q for q in REFERENTIEL["mur"]}


def _valeur(q: dict, v, ou: str, notes: list[str]):
    """Valeur normalisée de la question ``q``, ou ``None`` pour la retirer."""
    code, typ = q["code"], q["type"]
    if v in (None, "", []):
        return None
    if typ == "choix":
        o = _option(v, q["options"]) if isinstance(v, str) else None
        if o is None:
            notes.append(f"{ou} : réponse « {v} » hors liste pour {code}, retirée (donnée manquante).")
        elif o != v:
            notes.append(f"{ou} : « {v} » lu comme « {o} » pour {code}.")
        return o
    if typ == "multi":
        vals = v if isinstance(v, list) else [x for x in re.split(r"\s*;\s*", str(v)) if x]
        bons = []
        for x in vals:
            o = _option(x, q["options"]) if isinstance(x, str) else None
            if o is None:
                notes.append(f"{ou} : option « {x} » hors liste pour {code}, retirée.")
            elif o not in bons:
                bons.append(o)
        return [o for o in q["options"] if o in bons] or None
    if typ == "nombre":
        if code == "B-24" and isinstance(v, str) and _cle(v) == "inconnu":
            return "inconnu"
        x = nombre(v)
        bas, haut = BORNES.get(code, (0, None))
        if x is None:
            notes.append(f"{ou} : « {v} » n'est pas un nombre pour {code}, retiré (donnée manquante).")
            return None
        if x < bas or (haut is not None and x > haut):
            notes.append(f"{ou} : {code} = {v} hors des valeurs possibles, retiré (donnée manquante).")
            return None
        if x != v:
            notes.append(f"{ou} : « {v} » lu comme {x} pour {code}.")
        return x
    if typ == "case":
        return bool(v) or None
    return str(v).strip() or None


def _entite(d: dict, questions: dict, ou: str, notes: list[str], garder=("_id", "observations", "aucune_baie", "murs")):
    out = {}
    for k, v in (d or {}).items():
        if k in garder:
            out[k] = v
        elif k in questions:
            v2 = _valeur(questions[k], v, ou, notes)
            if v2 is not None:
                out[k] = v2
        else:
            notes.append(f"{ou} : champ « {k} » inconnu, ignoré.")
    return out


def _murs(murs, ou: str, notes: list[str]):
    if not isinstance(murs, list):
        return []
    if len(murs) > NB_MURS_MAX:
        notes.append(f"{ou} : {len(murs)} murs extérieurs ; seuls les {NB_MURS_MAX} premiers sont pris en compte.")
    out = []
    q_baies = MUR["MEX-08"]["options"]
    for i, m in enumerate(murs[:NB_MURS_MAX], start=1):
        m2 = {}
        for k, v in (m or {}).items():
            if k == "baies":
                baies = {}
                for t, n in (v or {}).items():
                    t2 = _option(t, q_baies)
                    if t2 is None:
                        notes.append(f"{ou}, mur {i} : type de baie « {t} » inconnu, ignoré.")
                        continue
                    if isinstance(n, str) and _cle(n) == "x":
                        baies[t2] = "x"
                        continue
                    x = nombre(n)
                    if x is None or x < 0:
                        notes.append(f"{ou}, mur {i} : nombre de baies « {n} » invalide pour {t2}, compté comme non relevé.")
                        baies[t2] = "x"
                    else:
                        baies[t2] = x
                if baies:
                    m2["baies"] = baies
            elif k in MUR:
                v2 = _valeur(MUR[k], v, f"{ou}, mur {i}", notes)
                if v2 is not None:
                    m2[k] = v2
        out.append(m2)
    return out


def valider(donnees: dict) -> tuple[dict, list[str]]:
    """Saisie normalisée et liste des corrections apportées."""
    d, notes = copy.deepcopy(donnees or {}), []
    out = {k: d.get(k) for k in ("audit",) if k in d}
    out["batiment"] = _entite(d.get("batiment") or {}, QUESTIONS["batiment"], "Bâtiment", notes, garder=())
    facades = {}
    q_fac = {q["code"]: q for q in REFERENTIEL["facades"][1:]}
    for o, f in (d.get("facades") or {}).items():
        if o not in ORIENTATIONS:
            notes.append(f"Façade « {o} » inconnue, ignorée.")
            continue
        f2 = {"F-01": True} if (f or {}).get("F-01") else {}
        for k, v in (f or {}).items():
            if k in q_fac:
                v2 = _valeur({**q_fac[k], "type": "choix"}, v, f"Façade {o}", notes)
                if v2 is not None:
                    f2[k] = v2
        facades[o] = f2
    out["facades"] = facades
    for cle, nom in (("locaux", "Local"), ("espaces", "Espace")):
        liste = []
        for i, x in enumerate(d.get(cle) or [], start=1):
            ou = f"{nom} {i}" + (f" « {x.get('L-01') or x.get('E-01')} »" if (x.get("L-01") or x.get("E-01")) else "")
            x2 = _entite(x, QUESTIONS[cle], ou, notes)
            if "murs" in x2:
                x2["murs"] = _murs(x2["murs"], ou, notes)
            liste.append(x2)
        out[cle] = liste
    params = {}
    for k, v in (d.get("parametres") or {}).items():
        x = nombre(v)
        if k not in parametres(None):
            notes.append(f"Seuil « {k} » inconnu, ignoré.")
        elif x is None:
            notes.append(f"Seuil {k} = « {v} » n'est pas un nombre : valeur de la méthode conservée.")
        else:
            params[k] = x
    out["parametres"] = params
    reps = []
    for i, r in enumerate(d.get("questionnaires") or [], start=1):
        r2 = {k: v for k, v in r.items() if k in ("_id", "source", "horodatage")}
        for k, v in r.items():
            if k in QU.PAR_CODE:
                v2 = _valeur(QU.PAR_CODE[k], v, f"Questionnaire {i}", notes)
                if v2 is not None:
                    r2[k] = v2
        reps.append(r2)
    out["questionnaires"] = reps
    if d.get("photos"):
        from .photos import valider as valider_photos
        out["photos"] = valider_photos(d["photos"], notes)
    if d.get("diagnostic_externe"):
        from .travaux import valider_externe
        out["diagnostic_externe"], n_e = valider_externe(d["diagnostic_externe"])
        notes += n_e
    if d.get("travaux"):
        from .travaux import valider_saisie
        out["travaux"], n_t = valider_saisie(d["travaux"])
        notes += n_t
    return out, notes
