"""Identifiant de la version déployée : numéro (fichier VERSION) et commit Git s'il est disponible.

Affiché en pied de page de l'application pour savoir quel déploiement un utilisateur regarde.
"""
from __future__ import annotations

import functools
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def version() -> dict:
    numero = (RACINE / "VERSION").read_text(encoding="utf-8").strip() if (RACINE / "VERSION").exists() else "?"
    commit = date = ""
    try:
        sortie = subprocess.run(["git", "log", "-1", "--format=%h %cs"], cwd=RACINE, capture_output=True, text=True,
                                timeout=3, check=True).stdout.split()
        commit, date = sortie[0], sortie[1]
    except Exception:  # pas de dépôt Git (archive, image) : numéro seul
        pass
    return {"numero": numero, "commit": commit, "date": date}


def libelle() -> str:
    v = version()
    txt = f"Version {v['numero']}"
    if v["commit"]:
        j = v["date"].split("-")
        txt += f" · commit {v['commit']}" + (f" du {j[2]}/{j[1]}/{j[0]}" if len(j) == 3 else "")
    return txt
