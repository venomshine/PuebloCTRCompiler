"""Idiomas del asistente: español e inglés.

Como en las apps de 3DS de VENOMSHiNE, la clave es el texto en español: _("Texto en español") devuelve la
traducción del idioma elegido, o el propio texto en español. Los datos que cambian van como {nombre} en el texto y
se pasan aparte: _("Disco {n}", n=1). Nunca dentro de la clave ya formateada.

El idioma: el que se eligió la última vez (ajustes.json, junto a los tiempos y el registro) o, la primera vez,
el del sistema: español si el sistema está en español, inglés si no.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

LANGS = {"es": "Español", "en": "English"}
SETTINGS = "ajustes.json"

_lang = "es"

# Las traducciones al inglés, por la clave en español.
EN: dict[str, str] = {
    # --- comunes ---
    "hecho por VENOMSHiNE": "made by VENOMSHiNE",
    "Atrás": "Back",
    "Continuar": "Continue",
    "Idioma": "Language",
    # --- bienvenida ---
    "{pueblo}  ·  asistente {version}\nel port de lonelyversemaker":
        "{pueblo}  ·  wizard {version}\nthe port by lonelyversemaker",
    "Convierte tus discos de GameCube en un solo .cia con todo el juego dentro: se instala y listo, sin copiar nada "
    "más a la SD. No instala nada en tu PC.":
        "Turns your GameCube discs into a single .cia with the whole game inside: install it and you're done, "
        "nothing else to copy to the SD card. Nothing is installed on your PC.",
    "Eliges las imágenes de tus dos discos (ISO, GCM o RVZ de Dolphin).":
        "Pick the images of your two discs (ISO, GCM or Dolphin RVZ).",
    "Eliges un par de opciones y dónde guardar el .cia.":
        "Choose a couple of options and where to save the .cia.",
    "Se crea PuebloCTR.cia (unos 3,5 GB), listo para instalar con FBI (o por Wi-Fi con un QR).":
        "PuebloCTR.cia is created (about 3.5 GB), ready to install with FBI (or over Wi-Fi with a QR code).",
    "Necesitas tu propia copia del juego: edición europea (G4BP08) o americana (G4BE08). Lo que sale de tus discos "
    "es solo para tu consola: no se comparte.":
        "You need your own copy of the game: the European (G4BP08) or US (G4BE08) edition. What comes out of your "
        "discs is for your console only: don't share it.",
    "Empezar": "Start",
}


def _(text: str, **kw) -> str:
    t = EN.get(text, text) if _lang == "en" else text
    return t.format(**kw) if kw else t


def get_lang() -> str:
    return _lang


def set_lang(lang: str, save: bool = True) -> None:
    global _lang
    if lang in LANGS:
        _lang = lang
        if save:
            _save({"idioma": lang})


def system_lang() -> str:
    """El idioma del sistema: "es" si es español, si no "en"."""
    if os.name == "nt":
        try:
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "es" if lid & 0x3FF == 0x0A else "en"  # LANG_SPANISH: todas las variantes (es-ES, es-MX...)
        except (AttributeError, OSError):
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return "es" if v.lower().startswith("es") else "en"
    return "en"


def _path() -> Path:
    from .build import data_dir  # (aquí dentro: build también usa este módulo)
    return data_dir() / SETTINGS


def _load() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(values: dict) -> None:
    d = _load()
    d.update(values)
    try:
        p = _path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def init() -> str:
    """Al arrancar: el idioma guardado o el del sistema (sin guardarlo: se guarda cuando se elige)."""
    saved = _load().get("idioma")
    set_lang(saved if saved in LANGS else system_lang(), save=False)
    return _lang
