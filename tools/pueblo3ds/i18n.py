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
    "Salir": "Exit",
    "Volver": "Go back",
    "Elegir…": "Browse…",
    "Cambiar…": "Change…",
    "Todos": "All files",
    "Error desconocido.": "Unknown error.",
    "Aviso: {w}": "Warning: {w}",
    "La consola está descargando el .cia. Si sales ahora, se corta.\n\n¿Salir de todos modos?":
        "The console is downloading the .cia. If you exit now, it will be cut off.\n\nExit anyway?",
    "Se está creando el .cia. Si sales ahora, se cancela (lo ya hecho se aprovecha la próxima vez).\n\n"
    "¿Salir de todos modos?":
        "The .cia is being created. If you exit now, it's cancelled (what's already done is reused next time)."
        "\n\nExit anyway?",
    # --- tus discos ---
    "Tus discos": "Your discs",
    "Las imágenes de los dos discos de la misma edición. El orden da igual.":
        "The images of both discs of the same edition. The order doesn't matter.",
    "DISCO 1": "DISC 1",
    "DISCO 2  (opcional: sin él se juega hasta la isla)": "DISC 2  (optional: without it you can play up to the island)",
    "¿Otro formato (CISO, GCZ, WIA)? En Dolphin: clic derecho en el juego → Convertir archivo → ISO o RVZ.":
        "Another format (CISO, GCZ, WIA)? In Dolphin: right-click the game → Convert File → ISO or RVZ.",
    "No existe ese archivo.": "That file doesn't exist.",
    "Imagen del disco {n}": "Disc {n} image",
    "Imágenes de GameCube": "GameCube images",
    # discs.py
    "No es un disco de GameCube.": "It's not a GameCube disc.",
    "Es un WIA: conviértelo a ISO o RVZ con Dolphin (clic derecho → Convertir archivo).":
        "It's a WIA: convert it to ISO or RVZ with Dolphin (right-click → Convert File).",
    "Ese formato comprimido no se lee: conviértelo a ISO o RVZ con Dolphin.":
        "That compressed format can't be read: convert it to ISO or RVZ with Dolphin.",
    "No se puede leer: {err}": "Can't read it: {err}",
    "Es la edición de {ed} ({id}): solo valen la europea y la americana.":
        "It's the {ed} edition ({id}): only the European and US editions work.",
    "Ese disco no es el del juego: {name}.": "That disc isn't the game: {name}.",
    "Número de disco raro ({n}).": "Unexpected disc number ({n}).",
    "Disco {n} · {ed} ({id}) · {kind}": "Disc {n} · {ed} ({id}) · {kind}",
    "parece recortado: puede que falten archivos.": "it looks trimmed: some files may be missing.",
    "Elige la imagen del disco 1.": "Choose the disc 1 image.",
    "Las dos imágenes son el disco {n}.": "Both images are disc {n}.",
    "Los discos son de ediciones distintas (uno europeo y otro americano).":
        "The discs are from different editions (one European and one US).",
    "Falta el disco 1: el juego arranca de él.": "Disc 1 is missing: the game starts from it.",
    "{ed}: solo el disco 1. Se puede jugar hasta que el juego pida el disco 2 (la isla).":
        "{ed}: disc 1 only. You can play until the game asks for disc 2 (the island).",
    "Edición de {ed} ({id}) · los dos discos": "{ed} edition ({id}) · both discs",
    "Europa": "Europe",
    "EE. UU.": "US",
    "Japón": "Japan",
    # --- opciones ---
    "Opciones": "Options",
    "Lo marcado es lo recomendado.": "What's ticked is what we recommend.",
    "QUÉ LLEVA": "WHAT GOES IN",
    "Pack de texturas (unos 350 MB; sin él, tirones al aparecer texturas nuevas)":
        "Texture pack (about 350 MB; without it, stutters when new textures appear)",
    "Vídeos del juego (unos 220 MB; los convierte ffmpeg)": "The game's movies (about 220 MB; ffmpeg converts them)",
    "Descargar": "Download",
    "Comprobando ffmpeg…": "Checking ffmpeg…",
    "ffmpeg funciona, con libx264": "ffmpeg works, with libx264",
    "Ese ffmpeg no trae libx264 (es demasiado mínimo): descarga el completo.":
        "That ffmpeg has no libx264 (it's too minimal): download the full one.",
    "No se encuentra ffmpeg: descárgalo (unos {mb} MB, una sola vez) o elígelo.":
        "ffmpeg not found: download it (about {mb} MB, just once) or choose it.",
    "Sin vídeos: el juego va, pero sus vídeos no se ven.": "No movies: the game works, but its movies won't show.",
    "Descargando ffmpeg…": "Downloading ffmpeg…",
    "Descargando ffmpeg: {done} de {total} MB": "Downloading ffmpeg: {done} of {total} MB",
    "Descargando ffmpeg: {done} MB": "Downloading ffmpeg: {done} MB",
    "No se pudo descargar: {err}": "Couldn't download it: {err}",
    "PARTIDAS DE GAMECUBE  (opcional: .gci / .gcs de Dolphin o de una tarjeta)":
        "GAMECUBE SAVES  (optional: .gci / .gcs from Dolphin or a memory card)",
    "Ninguna (la tarjeta de memoria del port se crea vacía).": "None (the port's memory card starts empty).",
    "Quitar": "Remove",
    "Añadir…": "Add…",
    "Partidas de GameCube": "GameCube saves",
    "Partidas": "Saves",
    "GUARDAR EL .CIA EN  (unos 3,5 GB; mientras se crea, el doble libre en ese disco)":
        "SAVE THE .CIA TO  (about 3.5 GB; twice that free on that drive while it's made)",
    "Está conectada la SD de una 3DS ({sd}).": "A 3DS SD card is connected ({sd}).",
    "Guardarlo en la SD": "Save it to the SD card",
    "Guardar el .cia": "Save the .cia",
    "CIA de 3DS": "3DS CIA",
    "Crear el .cia": "Create the .cia",
    # --- creando el .cia ---
    "Creando el .cia": "Creating the .cia",
    "Convirtiendo tus discos. Puedes seguir usando el PC.": "Converting your discs. You can keep using your PC.",
    "Calculando…": "Calculating…",
    "Llevas {t}": "Elapsed {t}",
    "total ~{m} min": "total ~{m} min",
    "Ya casi está": "Almost done",
    "Quedan unos {m} min": "About {m} min left",
    "Queda 1 min": "1 min left",
    "según tu última compilación": "based on your last build",
    "Preparando…": "Getting ready…",
    "Discos": "Discs",
    "Texturas": "Textures",
    "Vídeos": "Movies",
    "El .cia": "The .cia",
    "Detalles": "Details",
    "listos": "done",
    "hecho": "done",
    "hechos": "done",
    "no se incluye": "not included",
    "montándolo": "building it",
    "comprobándolo": "checking it",
    "metiendo el juego: {pct}": "adding the game: {pct}",
    "leyendo": "reading",
    "Discos: {estado}": "Discs: {estado}",
    "archivos sacados": "files extracted",
    "Pack de texturas para la GPU de la 3DS": "Texture pack for the 3DS GPU",
    "Vídeos (H.264 para la 3DS)": "Movies (H.264 for the 3DS)",
    "El .cia, con todo el juego dentro": "The .cia, with the whole game inside",
    # build.py: el avance
    "Leyendo los discos": "Reading the discs",
    "descomprimiendo el RVZ {n}": "unpacking RVZ {n}",
    "Descomprimiendo el RVZ {n} de {total}: {pct} %": "Unpacking RVZ {n} of {total}: {pct} %",
    "disco {n}: {pct} %": "disc {n}: {pct} %",
    "Sacando los archivos del disco {n}: {pct} %": "Extracting the files of disc {n}: {pct} %",
    "disco {n}: {files} archivos": "disc {n}: {files} files",
    "Disco {n}: {files} archivos": "Disc {n}: {files} files",
    "Pack de texturas: {pct} %": "Texture pack: {pct} %",
    "Pack de texturas hecho": "Texture pack done",
    "{n} de {total}": "{n} of {total}",
    "Vídeos: {n} de {total}": "Movies: {n} of {total}",
    "Vídeos: convirtiendo {name} ({n} de {total})": "Movies: converting {name} ({n} of {total})",
    "Metiendo las partidas en la tarjeta de memoria": "Adding the saves to the memory card",
    "Montando el .cia (makerom)": "Building the .cia (makerom)",
    "Metiendo el juego en el .cia: {done} de {total} MB": "Adding the game to the .cia: {done} of {total} MB",
    "Calculando el hash del .cia: {pct} %": "Calculating the .cia's hash: {pct} %",
    "Listo": "Done",
    # build.py: los errores
    "No hay espacio suficiente en {where}: hacen falta unos {need} GB libres mientras se crea el .cia (hay {have} GB). "
    "Elige otro disco para el .cia.":
        "Not enough space on {where}: about {need} GB free is needed while the .cia is created ({have} GB "
        "available). Choose another drive for the .cia.",
    "No hay espacio suficiente en el disco de destino (hacen falta unos 4 GB, 7 GB con RVZ).":
        "Not enough space on the destination drive (about 4 GB needed, 7 GB with RVZ).",
    "Una de las imágenes no es un disco de GameCube que se pueda leer.":
        "One of the images isn't a GameCube disc that can be read.",
    "Una de las imágenes no es un disco de GameCube.": "One of the images isn't a GameCube disc.",
    "Has elegido dos veces el mismo disco.": "You chose the same disc twice.",
    "Los discos son de ediciones distintas.": "The discs are from different editions.",
    "Falta el disco 1.": "Disc 1 is missing.",
    "Esa edición no la juega esta versión (solo Europa G4BP08 y EE. UU. G4BE08).":
        "This version doesn't play that edition (only Europe G4BP08 and US G4BE08).",
    "ffmpeg no pudo convertir un vídeo (¿es una versión con libx264?).":
        "ffmpeg couldn't convert a movie (is it a build with libx264?).",
    "Un nombre de archivo no cabe en FAT32 (la SD).": "A file name doesn't fit in FAT32 (the SD card).",
    "No se pudo escribir: ¿el disco o la SD están llenos?": "Couldn't write: is the drive or the SD card full?",
    "no se encuentra {name} en {dir}": "{name} not found in {dir}",
    "falta {name} en {dir}": "{name} is missing in {dir}",
    "el zip de ffmpeg no trae bin/ffmpeg.exe": "the ffmpeg zip has no bin/ffmpeg.exe",
    "el paquete de ffmpeg no trae el ejecutable ffmpeg": "the ffmpeg package has no ffmpeg program",
    "makerom falló:": "makerom failed:",
    "{file}: {size} bytes, y un disco completo tiene {full}: ¿es una imagen recortada?":
        "{file}: {size} bytes, and a full disc has {full}: is it a trimmed image?",
    "Sin el disco 2: se juega hasta que el juego pida el segundo disco (la isla).":
        "No disc 2: you can play until the game asks for the second disc (the island).",
    "Los discos no traen el vídeo {name}.": "The discs don't have the movie {name}.",
    "puebloprep-cli terminó con el código {code}": "puebloprep-cli ended with code {code}",
    # --- listo ---
    "No se pudo crear el .cia": "The .cia couldn't be created",
    "El registro completo está en puebloprep.log (botón de abajo).": "The full log is in puebloprep.log (button below).",
    "Ver el registro": "View the log",
    "texturas": "textures",
    "sin texturas": "no textures",
    "{n} vídeos": "{n} movies",
    "sin vídeos": "no movies",
    "Archivo": "File",
    "Tamaño": "Size",
    "Es un solo archivo con todo el juego dentro: no hay que copiar nada más a la SD.":
        "It's a single file with the whole game inside: nothing else to copy to the SD card.",
    "Ya está en la SD: en la consola, FBI → SD → cia → PuebloCTR.cia → Install CIA.":
        "It's already on the SD card: on the console, FBI → SD → cia → PuebloCTR.cia → Install CIA.",
    "Cópialo a la SD (por ejemplo a la carpeta cia) y en la consola: FBI → SD → cia → PuebloCTR.cia → Install CIA.":
        "Copy it to the SD card (for example to the cia folder) and on the console: FBI → SD → cia → PuebloCTR.cia "
        "→ Install CIA.",
    "Hacen falta unos 3,5 GB libres en la SD para instalarlo; luego puedes borrar el .cia.":
        "You need about 3.5 GB free on the SD card to install it; afterwards you can delete the .cia.",
    "Por Wi-Fi (QR) no hay que copiar nada, pero tarda bastante más: son 3,5 GB.":
        "Over Wi-Fi (QR) there's nothing to copy, but it takes much longer: it's 3.5 GB.",
    "Partidas dentro del .cia: {names} (pasan a la SD al arrancar la primera vez, si allí no hay ya una tarjeta "
    "de memoria).":
        "Saves inside the .cia: {names} (they go to the SD card on first start, if there's no memory card there yet).",
    "No se pudieron importar: {names} (mira el registro).": "Couldn't import: {names} (see the log).",
    "Lo de tus discos es solo para tu consola: no lo compartas.": "What comes from your discs is for your console only: "
                                                                  "don't share it.",
    "Instalar por Wi-Fi (QR)": "Install over Wi-Fi (QR)",
    "Abrir la carpeta": "Open the folder",
    # --- instalar por Wi-Fi ---
    "Instalar por Wi-Fi": "Install over Wi-Fi",
    "No se pudo abrir el servidor: {exc}": "Couldn't start the server: {exc}",
    "En la consola, abre FBI.": "On the console, open FBI.",
    "Apunta la cámara a este QR.": "Point the camera at this QR code.",
    "Acepta la instalación.": "Accept the installation.",
    "Probar otra IP": "Try another IP",
    "El PC y la consola tienen que estar en la misma Wi-Fi. Si Windows pregunta por el firewall, permite el acceso "
    "en redes privadas.":
        "The PC and the console must be on the same Wi-Fi. If Windows asks about the firewall, allow access on "
        "private networks.",
    "No se detecta la red local: conecta el PC a la Wi-Fi.": "No local network found: connect the PC to the Wi-Fi.",
    "Enviado. Termina la instalación en FBI.": "Sent. Finish the installation in FBI.",
    "Enviando a la consola: {pct} %  ({sent} de {total} MB)": "Sending to the console: {pct} %  ({sent} of {total} MB)",
    "La consola ha conectado. Esperando a que empiece la descarga…":
        "The console has connected. Waiting for the download to start…",
    "Esperando a la consola…": "Waiting for the console…",
    "La consola no llega al PC.": "The console can't reach the PC.",
    "1) Mira si hay un aviso del Firewall de Windows (puede estar detrás de esta ventana) y permite el acceso en "
    "redes privadas.  2) Comprueba que la consola y el PC están en la misma Wi-Fi.  3) Si el PC tiene VPN o varias "
    "redes, pulsa «Probar otra IP».  Si nada funciona, copia el .cia a la SD e instálalo con FBI.":
        "1) Look for a Windows Firewall prompt (it may be behind this window) and allow access on private networks.  "
        "2) Check that the console and the PC are on the same Wi-Fi.  3) If the PC has a VPN or several networks, "
        "press \u201cTry another IP\u201d.  If nothing works, copy the .cia to the SD card and install it with FBI.",
    # --- sin ventana (cli.py) ---
    "Asistente {version} de PuebloCTR {pueblo}": "PuebloCTR {pueblo} wizard {version}",
    "de las imágenes de disco a un .cia con todo dentro": "from the disc images to a .cia with everything inside",
    "solo el motor en un .cia (sin el juego; para pruebas)": "only the engine in a .cia (no game; for testing)",
    "qué imagen es": "what image it is",
    "ffmpeg no encontrado o sin libx264: usa --ffmpeg RUTA o --sin-videos":
        "ffmpeg not found or without libx264: use --ffmpeg PATH or --sin-videos",
    "Listo en {s} s: {cia} ({size} bytes)": "Done in {s} s: {cia} ({size} bytes)",
    "aviso:": "warning:",
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
