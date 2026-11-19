"""Outils d'extraction des sorties (CSV de l'interface, PDF) pour la partie D de la campagne de tests.

* ``export_csv(res)`` : exécute la fonction ``_export_csv`` d'``app.py`` telle qu'elle est écrite (sans
  lancer Streamlit) ;
* ``tableaux(pdf)`` : tableaux du PDF (pdfplumber, d'après les filets des tableaux) ;
* ``texte(pdf)`` : texte du PDF par ``pdftotext -layout``.
"""
from __future__ import annotations

import ast
import csv
import html
import io
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from surya.rapport import donnee_manquante  # noqa: E402


def fonction_de_app(nom: str, **globales):
    """Compile une fonction de premier niveau d'app.py sans exécuter le reste du module."""
    arbre = ast.parse((RACINE / "app.py").read_text(encoding="utf-8"))
    noeud = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
    noeud.decorator_list = []
    module = ast.Module(body=[noeud], type_ignores=[])
    ns = dict(globales)
    exec(compile(module, "app.py", "exec"), ns)
    return ns[nom]


def export_csv(res) -> list[dict]:
    f = fonction_de_app("_export_csv", csv=csv, io=io, _manquante=donnee_manquante)
    contenu = f(res)
    return list(csv.DictReader(io.StringIO(contenu), delimiter=";"))


def texte(pdf: bytes, premiere=None, derniere=None) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(pdf)
        t.flush()
        cmd = ["pdftotext", "-layout"]
        if premiere:
            cmd += ["-f", str(premiere)]
        if derniere:
            cmd += ["-l", str(derniere)]
        return subprocess.run(cmd + [t.name, "-"], capture_output=True, check=True).stdout.decode("utf-8")


def pages(pdf: bytes) -> list[str]:
    return texte(pdf).split("\f")


def info(pdf: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(pdf)
        t.flush()
        return subprocess.run(["pdfinfo", t.name], capture_output=True, check=True).stdout.decode()


def tableaux(pdf: bytes) -> list[tuple[int, list[list[str | None]]]]:
    """[(numéro de page, lignes)] ; les cellules sont normalisées (retours à la ligne → espaces)."""
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        for k, page in enumerate(p.pages, start=1):
            for t in page.extract_tables():
                out.append((k, [[None if c is None else " ".join(c.split()) for c in ligne] for ligne in t]))
    return out


def debordements(pdf: bytes, marge=8) -> list[str]:
    """Caractères hors de la page, ou hors de la cellule qui les contient (texte qui déborde d'un tableau)."""
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        for k, page in enumerate(p.pages, start=1):
            for ch in page.chars:
                if ch["x0"] < marge or ch["x1"] > page.width - marge or ch["bottom"] > page.height - 2:
                    out.append(f"p.{k} hors page : {ch['text']!r} x={ch['x0']:.0f}")
                    break
            for t in page.find_tables():
                for ligne in t.rows:
                    for cell in ligne.cells:
                        if cell is None:
                            continue
                        x0, top, x1, bottom = cell
                        dedans = [c for c in page.chars if c["top"] >= top - 1 and c["bottom"] <= bottom + 1
                                  and c["x0"] >= x0 - 1 and c["x0"] < x1 - 1]
                        trop = [c for c in dedans if c["x1"] > x1 + 1.5]
                        if trop:
                            mot = "".join(c["text"] for c in dedans)[:40]
                            out.append(f"p.{k} débordement de cellule : {mot!r}")
    return out


def tableau_statuts(tabs, entetes_noms: list[str]) -> dict:
    """Reconstitue {(nom, solution): texte de la cellule} à partir des tableaux « Solution × entités »."""
    out = {}
    for _, t in tabs:
        if not t or not t[0] or t[0][0] != "Solution" or len(t[0]) < 2:
            continue
        noms = t[0][1:]
        if not set(noms) <= set(entetes_noms):
            continue
        for ligne in t[1:]:
            if ligne[1] is None:
                continue  # ligne de groupe
            for nom, cellule in zip(noms, ligne[1:]):
                out[(nom, ligne[0])] = cellule
    return out


def echapper(s: str) -> str:
    return html.escape(s)
