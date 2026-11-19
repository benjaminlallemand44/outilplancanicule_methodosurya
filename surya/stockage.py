"""Stockage des réponses au questionnaire usagers.

Maquette : ``DepotMemoire`` garde les réponses dans la session de l'utilisateur, rien n'est
enregistré sur un serveur. Pour passer en production, il suffira d'écrire une classe
``DepotSupabase`` qui respecte la même interface (voir ``docs/supabase.md``) et de la passer à
l'application à la place de ``DepotMemoire`` : ni le moteur, ni le questionnaire, ni le PDF ne changent.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Protocol


class DepotReponses(Protocol):
    """Interface commune à tous les stockages de réponses usagers."""

    def ajouter(self, code_audit: str, reponse: dict) -> dict: ...

    def lister(self, code_audit: str) -> list[dict]: ...

    def supprimer(self, code_audit: str, id_reponse: str) -> None: ...

    def vider(self, code_audit: str) -> None: ...


class DepotMemoire:
    """Réponses gardées dans une liste Python (la session Streamlit) : aucun enregistrement serveur."""

    def __init__(self, reponses: list[dict]):
        self._reponses = reponses

    def ajouter(self, code_audit: str, reponse: dict) -> dict:
        r = {k: v for k, v in reponse.items() if v not in (None, "", [])}
        r.setdefault("_id", uuid.uuid4().hex[:8])
        r.setdefault("horodatage", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        self._reponses.append(r)
        return r

    def lister(self, code_audit: str) -> list[dict]:
        return list(self._reponses)

    def supprimer(self, code_audit: str, id_reponse: str) -> None:
        self._reponses[:] = [r for r in self._reponses if r.get("_id") != id_reponse]

    def vider(self, code_audit: str) -> None:
        self._reponses.clear()
