"""Photos de la visite : préparation, rattachement, photos attendues, archive ZIP.

Une photo est décrite dans la saisie (``donnees["photos"]``, liste de dictionnaires) ; son contenu
(JPEG) est gardé à part, dans un dictionnaire ``{id: bytes}``, pour que la saisie reste un JSON léger.

Description d'une photo :

* ``id`` : identifiant ;
* ``cible`` : ``"batiment"``, ``"locaux:<_id du local>"``, ``"espaces:<_id de l'espace>"`` ou ``""``
  (pas encore rattachée, après un import groupé) ;
* ``etiquette`` : une valeur de ``ETIQUETTES`` ; ``legende`` : texte libre ;
* ``prise_le`` : date et heure de prise de vue (« 2026-06-15 14:32 »), lue dans la photo si possible ;
* ``visages_floutes`` : nombre de visages détectés et floutés.

Le rattachement par identifiant (et non par position) résiste au réordonnancement et à la
suppression des locaux.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import uuid
import zipfile
from pathlib import Path

ETIQUETTES = ["Vue d'ensemble", "Façade", "Baies et protections", "Plafond", "Équipements", "Ombrages existants",
              "Désordre", "Point d'alerte", "Autre"]
# Photos attendues (liste de contrôle, non bloquante)
ATTENDUES = {
    "batiment": ["Façade"],
    "locaux": ["Vue d'ensemble", "Baies et protections", "Plafond"],
    "espaces": ["Vue d'ensemble", "Ombrages existants"],
}
COTE_MAX = 1600       # px : côté le plus long après réduction
QUALITE = 80          # JPEG
MODELE_VISAGES = Path(__file__).resolve().parent / "modeles" / "face_detection_yunet_2023mar.onnx"
FORMATS = ["jpg", "jpeg", "png", "webp"]


# ------------------------------------------------------------------ préparation d'une image
def _date_exif(img) -> str:
    try:
        exif = img.getexif()
        brut = exif.get_ifd(0x8769).get(36867) or exif.get(36867) or exif.get(306)  # DateTimeOriginal, DateTime
        if brut:
            return dt.datetime.strptime(str(brut).strip()[:19], "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return ""


def detecter_visages(img) -> list[tuple[int, int, int, int]]:
    """Rectangles (x, y, l, h) des visages détectés (YuNet, OpenCV) ; [] si OpenCV est absent."""
    try:
        import cv2
        import numpy as np
    except ImportError:  # pragma: no cover - dépendance facultative
        return []
    if not MODELE_VISAGES.exists():
        return []
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:  # pragma: no cover
        pass
    rgb = np.asarray(img.convert("RGB"))
    bgr = rgb[:, :, ::-1].copy()
    h, w = bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(str(MODELE_VISAGES), "", (w, h), 0.75, 0.3, 5000)
    _, faces = det.detect(bgr)
    if faces is None:
        return []
    return [tuple(int(v) for v in f[:4]) for f in faces]


def flouter(img, zones) -> None:
    """Floute (pixellisation forte) les zones données, élargies de 25 %."""
    from PIL import ImageFilter
    for x, y, l, h in zones:
        mx, my = int(l * 0.25), int(h * 0.25)
        boite = (max(0, x - mx), max(0, y - my), min(img.width, x + l + mx), min(img.height, y + h + my))
        if boite[2] <= boite[0] or boite[3] <= boite[1]:
            continue
        zone = img.crop(boite)
        petit = zone.resize((max(1, zone.width // 12), max(1, zone.height // 12)))
        zone = petit.resize(zone.size).filter(ImageFilter.GaussianBlur(radius=max(2, zone.width // 30)))
        img.paste(zone, boite)


def preparer(contenu: bytes, flouter_visages: bool = True) -> tuple[bytes, dict]:
    """Photo prête à stocker : redressée, réduite, JPEG ; visages floutés.

    Renvoie (jpeg, infos) avec infos = {prise_le, largeur, hauteur, visages_floutes}.
    Lève ``ValueError`` si le fichier n'est pas une image lisible.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(contenu))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("Ce fichier n'est pas une image lisible (formats acceptés : JPEG, PNG, WebP).") from e
    prise_le = _date_exif(img)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((COTE_MAX, COTE_MAX))
    zones = detecter_visages(img) if flouter_visages else []
    if zones:
        flouter(img, zones)
    sortie = io.BytesIO()
    img.save(sortie, "JPEG", quality=QUALITE, optimize=True)
    return sortie.getvalue(), {"prise_le": prise_le, "largeur": img.width, "hauteur": img.height,
                               "visages_floutes": len(zones)}


def nouvelle(cible: str, infos: dict, etiquette: str = "", legende: str = "") -> dict:
    return {"id": uuid.uuid4().hex[:10], "cible": cible, "etiquette": etiquette or "Autre", "legende": legende,
            **{k: infos[k] for k in ("prise_le", "visages_floutes") if infos.get(k) not in (None, "")}}


# ------------------------------------------------------------------ rattachement
def cible_de(cle_liste: str, entite: dict) -> str:
    return f"{cle_liste}:{entite.get('_id', '')}"


def de_la_cible(donnees: dict, cible: str) -> list[dict]:
    return [p for p in donnees.get("photos") or [] if p.get("cible") == cible]


def libelle_cible(donnees: dict, cible: str) -> str:
    if cible == "batiment":
        return "Bâtiment"
    if not cible:
        return "Non rattachée"
    cle_liste, _, ident = cible.partition(":")
    defaut, champ = ("Local", "L-01") if cle_liste == "locaux" else ("Espace", "E-01")
    for i, x in enumerate(donnees.get(cle_liste) or []):
        if x.get("_id") == ident:
            return x.get(champ) or f"{defaut} {i + 1}"
    return "Non rattachée"


def cibles(donnees: dict) -> list[str]:
    """Toutes les cibles possibles, dans l'ordre : bâtiment, locaux, espaces."""
    return ["batiment"] + [cible_de(c, x) for c in ("locaux", "espaces") for x in donnees.get(c) or [] if x.get("_id")]


def orphelines(donnees: dict) -> None:
    """Les photos d'un local ou d'un espace supprimé redeviennent « non rattachées »."""
    valides = set(cibles(donnees))
    for p in donnees.get("photos") or []:
        if p.get("cible") and p["cible"] not in valides:
            p["cible"] = ""


def attendues_manquantes(donnees: dict, cible: str) -> list[str]:
    genre = cible.split(":")[0] if cible else ""
    presentes = {p.get("etiquette") for p in de_la_cible(donnees, cible)}
    return [e for e in ATTENDUES.get(genre, []) if e not in presentes]


def bilan_attendues(donnees: dict) -> list[tuple[str, list[str]]]:
    """[(libellé de la cible, photos attendues manquantes)] pour les cibles incomplètes."""
    return [(libelle_cible(donnees, c), m) for c in cibles(donnees) if (m := attendues_manquantes(donnees, c))]


def premiere_attendue(donnees: dict, cible: str) -> str:
    m = attendues_manquantes(donnees, cible)
    return m[0] if m else "Autre"


# ------------------------------------------------------------------ archive ZIP (saisie + photos)
def exporter_zip(donnees: dict, contenus: dict[str, bytes]) -> bytes:
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("saisie.json", json.dumps(donnees, ensure_ascii=False, indent=1))
        for p in donnees.get("photos") or []:
            if p.get("id") in contenus:
                z.writestr(f"photos/{p['id']}.jpg", contenus[p["id"]])
    return sortie.getvalue()


def lire_zip(contenu: bytes) -> tuple[dict, dict[str, bytes]]:
    """(saisie brute, {id: jpeg}) ; ``ValueError`` si l'archive n'est pas une saisie de l'outil."""
    try:
        z = zipfile.ZipFile(io.BytesIO(contenu))
    except zipfile.BadZipFile as e:
        raise ValueError("Cette archive ZIP est illisible.") from e
    with z:
        if "saisie.json" not in z.namelist():
            raise ValueError("Cette archive ne contient pas de saisie de l'outil (saisie.json absent).")
        donnees = json.loads(z.read("saisie.json").decode("utf-8-sig"))
        contenus = {}
        for nom in z.namelist():
            if nom.startswith("photos/") and nom.endswith(".jpg"):
                info = z.getinfo(nom)
                if info.file_size > 20 * 1024 * 1024:  # garde-fou : une photo préparée fait moins de 1 Mo
                    continue
                contenus[Path(nom).stem] = z.read(nom)
    return donnees, contenus


def valider(photos, notes: list[str]) -> list[dict]:
    """Descriptions de photos normalisées (import)."""
    out = []
    for i, p in enumerate(photos if isinstance(photos, list) else [], start=1):
        if not isinstance(p, dict) or not p.get("id"):
            notes.append(f"Photo {i} sans identifiant, ignorée.")
            continue
        q = {"id": str(p["id"])[:40], "cible": str(p.get("cible") or ""), "legende": str(p.get("legende") or "")[:300]}
        e = p.get("etiquette")
        q["etiquette"] = e if e in ETIQUETTES else "Autre"
        for k in ("prise_le", "visages_floutes", "envoyee"):
            if p.get(k) not in (None, ""):
                q[k] = p[k]
        out.append(q)
    return out
