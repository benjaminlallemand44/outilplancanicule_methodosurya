"""Photos de la visite : préparation, floutage, rattachement, photos attendues, archive ZIP, PDF."""
from __future__ import annotations

import copy
import io
import json

import pytest
from PIL import Image, ImageDraw

import sorties
from cas_base import RACINE, moteur
from surya import photos as PH
from surya.rapport import generer_pdf
from surya.validation import valider

ECOLE = json.loads((RACINE / "surya" / "exemple_ecole_sud.json").read_text(encoding="utf-8"))


def jpeg(l=2400, h=1600, couleur="#0a17a6", exif=None) -> bytes:
    im = Image.new("RGB", (l, h), couleur)
    ImageDraw.Draw(im).rectangle((0, 0, l // 4, h // 4), fill="white")  # repère en haut à gauche
    b = io.BytesIO()
    im.save(b, "JPEG", exif=exif) if exif is not None else im.save(b, "JPEG")
    return b.getvalue()


def test_reduction_et_format():
    j, infos = PH.preparer(jpeg(4000, 3000))
    im = Image.open(io.BytesIO(j))
    assert im.format == "JPEG" and max(im.size) == PH.COTE_MAX and im.size == (1600, 1200)
    assert (infos["largeur"], infos["hauteur"]) == im.size and infos["visages_floutes"] == 0
    assert len(j) < 400_000


def test_png_transparent_et_petite_image_conservee():
    im = Image.new("RGBA", (300, 200), (255, 0, 0, 0))
    b = io.BytesIO()
    im.save(b, "PNG")
    j, infos = PH.preparer(b.getvalue())
    assert Image.open(io.BytesIO(j)).size == (300, 200)  # jamais agrandie


def test_orientation_et_date_exif():
    ex = Image.Exif()
    ex[0x0112] = 6  # rotation de 90° à l'affichage
    ex[306] = "2026:06:15 14:32:10"
    j, infos = PH.preparer(jpeg(2000, 1000, exif=ex))
    assert Image.open(io.BytesIO(j)).size == (800, 1600)  # redressée : portrait
    assert infos["prise_le"] == "2026-06-15 14:32"


def test_fichier_illisible():
    with pytest.raises(ValueError, match="image lisible"):
        PH.preparer(b"%PDF-1.4 pas une image")


def test_floutage_des_zones_detectees(monkeypatch):
    monkeypatch.setattr(PH, "detecter_visages", lambda img: [(600, 400, 300, 300)])
    j, infos = PH.preparer(jpeg(1600, 1200, couleur="#000000"))
    assert infos["visages_floutes"] == 1
    sans, _ = PH.preparer(jpeg(1600, 1200, couleur="#000000"), flouter_visages=False)
    a, b = Image.open(io.BytesIO(j)), Image.open(io.BytesIO(sans))
    assert a.getpixel((10, 10)) == b.getpixel((10, 10))  # hors zone : inchangé


def test_detection_sans_visage():
    img = Image.new("RGB", (640, 480), "#0dcccc")
    assert PH.detecter_visages(img) == []


def donnees_avec_photos():
    d = copy.deepcopy(ECOLE)
    for i, x in enumerate(d["locaux"] + d["espaces"]):
        x["_id"] = f"id{i}"
    contenus, d["photos"] = {}, []
    for cible, etiquette in (("batiment", "Façade"), ("locaux:id0", "Vue d'ensemble"), ("locaux:id0", "Plafond"),
                             ("espaces:id6", "Point d'alerte"), ("", "Autre")):
        j, infos = PH.preparer(jpeg(1200, 800))
        ph = PH.nouvelle(cible, infos, etiquette, f"légende {etiquette}")
        d["photos"].append(ph)
        contenus[ph["id"]] = j
    return d, contenus


def test_rattachement_et_photos_attendues():
    d, _ = donnees_avec_photos()
    assert PH.libelle_cible(d, "locaux:id0") == d["locaux"][0]["L-01"]
    assert PH.libelle_cible(d, "") == "Non rattachée"
    assert PH.attendues_manquantes(d, "batiment") == []
    assert PH.attendues_manquantes(d, "locaux:id0") == ["Baies et protections"]
    assert PH.premiere_attendue(d, "locaux:id0") == "Baies et protections"
    bilan = dict(PH.bilan_attendues(d))
    assert bilan[d["locaux"][0]["L-01"]] == ["Baies et protections"] and "Bâtiment" not in bilan
    d["locaux"].pop(0)
    PH.orphelines(d)
    assert [ph["cible"] for ph in d["photos"]].count("") == 3  # photos du local supprimé : à rattacher


def test_archive_zip_aller_retour():
    d, contenus = donnees_avec_photos()
    brut, lus = PH.lire_zip(PH.exporter_zip(d, contenus))
    assert lus == contenus
    v, notes = valider(brut)
    assert [ph["id"] for ph in v["photos"]] == [ph["id"] for ph in d["photos"]]
    assert v["locaux"][0]["_id"] == "id0" and not [n for n in notes if "photo" in n.lower()]


def test_archive_zip_invalide():
    with pytest.raises(ValueError):
        PH.lire_zip(b"pas un zip")
    b = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("autre.txt", "x")
    with pytest.raises(ValueError, match="saisie.json"):
        PH.lire_zip(b.getvalue())


def test_validation_des_descriptions():
    notes = []
    out = PH.valider([{"id": "a", "cible": "locaux:x", "etiquette": "Inconnue"}, {"cible": "batiment"}, "x"], notes)
    assert out == [{"id": "a", "cible": "locaux:x", "legende": "", "etiquette": "Autre"}]
    assert len(notes) == 2


def test_compte_rendu_avec_photos():
    d, contenus = donnees_avec_photos()
    pdf = generer_pdf(d, photos=contenus)
    p = sorties.pages(pdf)
    t = sorties.texte(pdf)
    assert "1. Synthèse" in p[1] and "Points de vigilance" in p[1]  # la photo ne casse pas la page de synthèse
    assert "Photos de la visite" in t and "Photos des points à lever" in t
    assert t.count("légende Plafond") >= 1 and "légende Autre" not in t  # photo non rattachée : absente
    assert not sorties.debordements(pdf)
    with io.BytesIO(pdf) as f:
        import pdfplumber
        with pdfplumber.open(f) as doc:
            assert sum(len(pg.images) for pg in doc.pages) >= 4
    # sans le contenu des images, aucune photo (et aucun plantage)
    assert "Photos de la visite" not in sorties.texte(generer_pdf(d))
    assert "Photos" not in sorties.texte(generer_pdf(d, complet=False))
