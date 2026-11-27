"""Export des données de tous les comptes, pour l'analyse et les visualisations (administrateur ACTEE).

    SUPABASE_URL=https://<projet>.supabase.co SUPABASE_SERVICE_ROLE_KEY=<clé de service> \\
        python scripts/export_analyse.py <dossier de sortie>

La clé de service (Supabase : Project Settings > API) passe outre les règles d'accès : elle lit les audits de
tous les auditeurs. Elle ne doit jamais être mise dans l'application, dans le dépôt ni dans un fichier partagé.

Les statuts ne sont pas stockés dans la base : ils sont recalculés ici avec le moteur de l'outil, à partir de la
saisie de chaque audit, pour tous les audits avec la même version des règles. Le script écrit, en UTF-8 avec
séparateur « ; » (ouverture directe dans Excel) :

* ``audits.csv`` : un audit par ligne (établissement, commune, dates, bâtiment, nombres de locaux, d'espaces...) ;
* ``lieux.csv`` : un local ou un espace extérieur par ligne (type, surface, effectif, niveau) ;
* ``statuts.csv`` : une solution par lieu et par ligne (statut, règle retenue, alertes) ;
* ``reponses_usagers.csv`` : une réponse au questionnaire en ligne par ligne (questions en colonnes).

Aucune donnée personnelle des comptes (adresse e-mail) n'est exportée : l'auditeur est désigné par un numéro
stable (``auditeur_1``, ``auditeur_2``...) propre à l'export.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from surya import moteur  # noqa: E402
from surya.validation import valider  # noqa: E402

CHAMPS_AUDIT = ["etablissement", "commune", "moa", "date_visite"]
CHAMPS_BATIMENT = {"B-01": "periode_construction", "B-03": "structure", "B-04": "isolation_murs",
                   "B-06": "abords_monument", "B-09": "ventilation_mecanique"}
CHAMPS_LOCAL = {"L-01": "nom", "L-02": "type", "L-03": "surface_m2", "L-04": "effectif", "L-09": "niveau"}
CHAMPS_ESPACE = {"E-01": "nom", "E-04": "public", "E-06": "effectif", "E-14": "ombre_m2"}


def _texte(v) -> str:
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return "" if v is None else str(v)


def lignes(audits: list[dict], reponses: list[dict]) -> dict[str, list[dict]]:
    """Tables à plat à partir des lignes brutes de la base (``audits`` et ``reponses_usagers``)."""
    numeros: dict[str, str] = {}
    out = {"audits": [], "lieux": [], "statuts": [], "reponses_usagers": []}
    code_vers_id = {}
    for a in audits:
        d, _ = valider(a.get("donnees") or {})
        auditeur = numeros.setdefault(a.get("proprietaire") or "?", f"auditeur_{len(numeros) + 1}")
        code_vers_id[a.get("code")] = a["id"]
        out["audits"].append({
            "audit_id": a["id"], "auditeur": auditeur, "nom": a.get("nom", ""),
            **{k: _texte((d.get("audit") or {}).get(k)) for k in CHAMPS_AUDIT},
            **{v: _texte(d["batiment"].get(k)) for k, v in CHAMPS_BATIMENT.items()},
            "nb_locaux": len(d["locaux"]), "nb_espaces": len(d["espaces"]),
            "nb_photos": len(d.get("photos") or []), "nb_questionnaires_saisis": len(d.get("questionnaires") or []),
            "passage_en_travaux": "oui" if (d.get("travaux") or {}).get("operations") else "non",
            "diagnostic_externe": "oui" if (d.get("diagnostic_externe") or {}).get("operations") else "non",
            "cree_le": a.get("cree_le", ""), "modifie_le": a.get("modifie_le", ""),
        })
        res = moteur.calculer(d)
        for cle, champs, genre in (("locaux", CHAMPS_LOCAL, "Local"), ("espaces", CHAMPS_ESPACE, "Espace")):
            for i, (entree, x) in enumerate(zip(d[cle], res[cle]), start=1):
                lieu = f"{a['id']}:{cle}:{i}"
                out["lieux"].append({"lieu_id": lieu, "audit_id": a["id"], "genre": genre, "rang": i,
                                     **{v: _texte(entree.get(k)) for k, v in champs.items()}})
                for s in x["solutions"]:
                    regle = next((x["blocs"][b]["regle"] for b in s["blocs"] if x["blocs"][b]["regle"]), "")
                    out["statuts"].append({"lieu_id": lieu, "audit_id": a["id"], "genre": genre,
                                           "groupe": s["groupe"], "solution": s["solution"], "statut": s["statut"],
                                           "regle": regle or "", "alertes": " | ".join(s["alertes"])})
    questions = sorted({q for r in reponses for q in (r.get("reponses") or {})},
                       key=lambda q: (len(q), q))
    for r in reponses:
        out["reponses_usagers"].append({"reponse_id": r.get("id", ""),
                                        "audit_id": code_vers_id.get(r.get("audit_code"), ""),
                                        "recue_le": r.get("recue_le", ""),
                                        **{q: _texte((r.get("reponses") or {}).get(q)) for q in questions}})
    return out


def ecrire(tables: dict[str, list[dict]], dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = []
    for nom, rangs in tables.items():
        chemin = dossier / f"{nom}.csv"
        colonnes = list(dict.fromkeys(k for r in rangs for k in r)) or ["(vide)"]
        with chemin.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=colonnes, delimiter=";")
            w.writeheader()
            w.writerows(rangs)
        fichiers.append(chemin)
    return fichiers


def lire_base(url: str, cle_service: str, session=None) -> tuple[list[dict], list[dict]]:
    """Toutes les lignes, page par page (la clé de service passe outre les règles d'accès)."""
    import requests
    http = session or requests.Session()
    entetes = {"apikey": cle_service, "Authorization": f"Bearer {cle_service}"}

    def tout(table, colonnes):
        rangs, debut = [], 0
        while True:
            r = http.request("GET", f"{url.rstrip('/')}/rest/v1/{table}", params={"select": colonnes, "order": "id"},
                             headers={**entetes, "Range": f"{debut}-{debut + 999}"}, timeout=60)
            if r.status_code >= 300:
                raise SystemExit(f"Lecture de {table} impossible ({r.status_code}) : vérifiez l'adresse et la clé.")
            page = r.json()
            rangs += page
            if len(page) < 1000:
                return rangs
            debut += 1000

    return (tout("audits", "id,code,proprietaire,nom,donnees,cree_le,modifie_le"),
            tout("reponses_usagers", "id,audit_code,reponses,recue_le"))


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    url, cle = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not cle:
        raise SystemExit("Renseignez SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY (variables d'environnement).")
    audits, reponses = lire_base(url, cle)
    for f in ecrire(lignes(audits, reponses), Path(argv[1])):
        print(f)


if __name__ == "__main__":
    main(sys.argv)
