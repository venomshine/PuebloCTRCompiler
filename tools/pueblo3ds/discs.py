"""Reconoce una imagen de disco de GameCube (ISO / GCM o RVZ de Dolphin) sin descomprimirla.

Solo para avisar en la ventana antes de empezar: la comprobacion de verdad la hace PuebloPrep
(puebloprep-cli), que lee la tabla de archivos entera.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .i18n import _

GC_MAGIC = 0xC2339F3D  # en el byte 0x1C de la cabecera de un disco de GameCube
GC_DISC_BYTES = 1459978240  # un disco de GameCube completo
RVZ_MAGIC = b"RVZ\x01"
WIA_MAGIC = b"WIA\x01"
WIA_DHEAD = 0x48 + 16  # la cabecera del disco dentro de un RVZ / WIA (tras wia_file_head_t y 4 campos)

EDITIONS = {"G4BP08": "Europa", "G4BE08": "EE. UU."}
OTHER_RE4 = {"G4BJ08": "Japón"}


@dataclass
class Disc:
    path: Path
    kind: str = ""  # "ISO" o "RVZ"
    game_id: str = ""
    disc_no: int = -1  # 0 = disco 1
    title: str = ""
    size: int = 0
    error: str = ""

    @property
    def edition(self) -> str:
        return EDITIONS.get(self.game_id, "")

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.edition) and self.disc_no in (0, 1)


def _from_header(d: Disc, head: bytes) -> Disc:
    if len(head) < 0x40 or struct.unpack(">I", head[0x1C:0x20])[0] != GC_MAGIC:
        d.error = _("No es un disco de GameCube.")
        return d
    d.game_id = head[0:6].decode("ascii", "replace")
    d.disc_no = head[6]
    d.title = head[0x20:0x60].split(b"\0", 1)[0].decode("latin-1", "replace").strip()
    return d


def read_disc(path: Path) -> Disc:
    d = Disc(Path(path))
    try:
        d.size = d.path.stat().st_size
        with d.path.open("rb") as f:
            head = f.read(0x440)
            if head[:4] in (RVZ_MAGIC, WIA_MAGIC):
                d.kind = head[:3].decode()
                if head[:4] == WIA_MAGIC:
                    d.error = _("Es un WIA: conviértelo a ISO o RVZ con Dolphin (clic derecho → Convertir archivo).")
                    return d
                return _from_header(d, head[WIA_DHEAD:WIA_DHEAD + 0x80])
            if head[:4] == b"CISO" or head[:4] == b"\x01\xC0\x0B\xB1":  # CISO, GCZ
                d.error = _("Ese formato comprimido no se lee: conviértelo a ISO o RVZ con Dolphin.")
                return d
            d.kind = "ISO"
            return _from_header(d, head)
    except OSError as exc:
        d.error = _("No se puede leer: {err}", err=exc.strerror or exc)
        return d


def describe(d: Disc) -> tuple[bool, str, str]:
    """(valida, texto, nivel) para una imagen: nivel "ok", "warn" o "bad"."""
    if d.error:
        return False, d.error, "bad"
    if d.game_id in OTHER_RE4:
        return False, _("Es la edición de {ed} ({id}): solo valen la europea y la americana.",
                        ed=_(OTHER_RE4[d.game_id]), id=d.game_id), "bad"
    if not d.edition:
        name = f"«{d.title}» ({d.game_id})" if d.title else d.game_id
        return False, _("Ese disco no es el del juego: {name}.", name=name), "bad"
    if d.disc_no not in (0, 1):
        return False, _("Número de disco raro ({n}).", n=d.disc_no + 1), "bad"
    txt = _("Disco {n} · {ed} ({id}) · {kind}", n=d.disc_no + 1, ed=_(d.edition), id=d.game_id, kind=d.kind)
    if d.kind == "ISO" and d.size < GC_DISC_BYTES:
        return True, txt + " · " + _("parece recortado: puede que falten archivos."), "warn"
    return True, txt, "ok"


def check_pair(first: Disc | None, second: Disc | None) -> tuple[bool, str, str]:
    """La pareja: hace falta el disco 1; el 2 es opcional pero de la misma edicion."""
    discs = [d for d in (first, second) if d is not None]
    if not discs:
        return False, _("Elige la imagen del disco 1."), "dim"
    for d in discs:
        ok, txt, _level = describe(d)
        if not ok:
            return False, f"{d.path.name}: {txt}", "bad"
    if len(discs) == 2:
        a, b = discs
        if a.disc_no == b.disc_no:
            return False, _("Las dos imágenes son el disco {n}.", n=a.disc_no + 1), "bad"
        if a.game_id != b.game_id:
            return False, _("Los discos son de ediciones distintas (uno europeo y otro americano)."), "bad"
    if not any(d.disc_no == 0 for d in discs):
        return False, _("Falta el disco 1: el juego arranca de él."), "bad"
    ed = _(discs[0].edition)
    if len(discs) == 1:
        return True, _("{ed}: solo el disco 1. Se puede jugar hasta que el juego pida el disco 2 (la isla).", ed=ed), "warn"
    return True, _("Edición de {ed} ({id}) · los dos discos", ed=ed, id=discs[0].game_id), "ok"
