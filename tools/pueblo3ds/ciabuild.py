"""Un .cia con todos los datos dentro (romfs de varios GB) sin cargarlo en memoria.

makerom monta el romfs entero en la RAM (3,5 GB de datos = 3,5 GB de RAM). Aqui makerom solo hace
un .cia pequeno (motor, icono, banner, permisos) con un romfs de relleno, y este modulo lo reescribe
por partes:

  - el romfs de verdad (IVFC: cabecera, hash maestro, nivel 3 = el sistema de archivos, niveles 1
    y 2 = los hashes SHA-256 de cada bloque de 4 KB), igual byte a byte que el de makerom
    (romfs_gen.c de Project_CTR makerom 0.19.0: mismo orden de entradas, mismas tablas hash);
  - la cabecera NCCH (tamano, tamano del romfs, hash de su superbloque);
  - la TMD (tamano y SHA-256 del contenido, hash de los registros) y la cabecera del CIA.

Las firmas de makerom no valen en una consola sin parchear de todos modos (como en cualquier .cia
casero): Luma3DS no las comprueba, y aqui quedan como las deja makerom.
"""

from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path
from typing import Callable

BLOCK = 0x1000
UNUSED = 0xFFFFFFFF
IVFC_HDR = 0x5C  # sizeof(ivfc_hdr)
IVFC_HDR_AL = 0x60  # align(sizeof(ivfc_hdr), 0x10)


def al(x: int, a: int) -> int:
    return (x + a - 1) // a * a


# --- el sistema de archivos (nivel 3) --------------------------------------------------------------

class _Dir:
    def __init__(self, path: Path | None, name: str):
        self.path, self.name = path, name
        self.dirs: list[_Dir] = []
        self.files: list[tuple[Path, str, int]] = []  # (ruta, nombre, tamano)
        self.offset = 0


def _scan(path: Path, name: str) -> _Dir:
    """Como OpenRootDir de makerom: en el orden del sistema (readdir / os.listdir), sin . ni .."""
    d = _Dir(path, name)
    for n in os.listdir(path):
        if n.endswith(".part"):  # (lo que PuebloPrep deja a medias si algo falla)
            continue
        p = path / n
        if p.is_dir():
            d.dirs.append(_scan(p, n))
        elif p.is_file():
            d.files.append((p, n, p.stat().st_size))
    return d


def _wanted(d: _Dir) -> bool:
    """IsDirWanted: una carpeta sin ningun archivo debajo no entra."""
    return bool(d.files) or any(_wanted(c) for c in d.dirs)


def _filter(d: _Dir) -> None:
    d.dirs = [c for c in d.dirs if _wanted(c)]
    for c in d.dirs:
        _filter(c)


def _u16(name: str) -> bytes:
    return name.encode("utf-16-le")


def _hash_table_count(n: int) -> int:
    c = n
    if n < 3:
        c = 3
    elif c < 19:
        c |= 1
    else:
        while any(c % p == 0 for p in (2, 3, 5, 7, 11, 13, 17)):
            c += 1
    return c


def _path_hash(parent: int, name: bytes) -> int:
    h = parent ^ 123456789
    for (ch,) in struct.iter_unpack("<H", name):
        h = ((h >> 5) | (h << 27)) & 0xFFFFFFFF
        h ^= ch
    return h


class RomFs:
    """El plan del romfs de una carpeta: la metadata del nivel 3 hecha, los datos por leer."""

    def __init__(self, root: Path):
        self.root = _scan(Path(root), "")
        _filter(self.root)
        if not _wanted(self.root):
            raise ValueError(f"{root}: no hay archivos")
        # tamanos (CalcRomfsSize / CalcDirSize)
        self.dir_len = self.file_len = self.data_len = 0
        self.dir_num, self.file_num = 1, 0

        def size(d: _Dir, top: bool):
            self.dir_len += 0x18 if top else 0x18 + al(len(_u16(d.name)), 4)
            for _, n, s in d.files:
                self.file_len += 0x20 + al(len(_u16(n)), 4)
                if s:
                    self.data_len = al(self.data_len, 0x10) + s
            for c in d.dirs:
                size(c, False)
            self.file_num += len(d.files)
            self.dir_num += len(d.dirs)

        size(self.root, True)
        self.dir_ht = _hash_table_count(self.dir_num)
        self.file_ht = _hash_table_count(self.file_num)
        self._build_meta()
        # los niveles IVFC
        self.l3_size = len(self.meta) + self.data_len
        self.l2_size = al(self.l3_size, BLOCK) // BLOCK * 32
        self.l1_size = al(self.l2_size, BLOCK) // BLOCK * 32
        self.master_size = al(self.l1_size, BLOCK) // BLOCK * 32
        self.l0_size = self.master_size + IVFC_HDR_AL
        self.off_l3 = al(self.l0_size, BLOCK)
        self.off_l1 = self.off_l3 + al(self.l3_size, BLOCK)
        self.off_l2 = self.off_l1 + al(self.l1_size, BLOCK)
        self.size = self.off_l2 + al(self.l2_size, BLOCK)
        self.header_size = self.l0_size  # romfsHeaderSize

    def _build_meta(self):
        dir_tab = bytearray()
        file_tab = bytearray()
        dir_hash = [UNUSED] * self.dir_ht
        file_hash = [UNUSED] * self.file_ht
        self.order: list[tuple[Path, int, int]] = []  # (ruta, posicion en los datos, tamano), en orden
        data = [0]

        def add_dir(d: _Dir, parent: int, sibling: int):
            off = len(dir_tab)
            name = _u16(d.name)
            idx = _path_hash(parent, name) % self.dir_ht
            dir_tab.extend(struct.pack("<6I", parent, sibling, UNUSED, UNUSED, dir_hash[idx], len(name)))
            dir_tab.extend(name.ljust(al(len(name), 4), b"\0"))
            dir_hash[idx] = off
            d.offset = off

        def add_file(path: Path, n: str, s: int, parent: int, sibling: int):
            off = len(file_tab)
            name = _u16(n)
            idx = _path_hash(parent, name) % self.file_ht
            if s:
                data[0] = al(data[0], 0x10)
                doff = data[0]
                self.order.append((path, doff, s))
                data[0] += s
            else:
                doff = 0
            file_tab.extend(struct.pack("<IIQQII", parent, sibling, doff, s, file_hash[idx], len(name)))
            file_tab.extend(name.ljust(al(len(name), 4), b"\0"))
            file_hash[idx] = off

        def add_children(d: _Dir, dir_off: int):
            if d.files:
                struct.pack_into("<I", dir_tab, dir_off + 12, len(file_tab))
                for i, (p, n, s) in enumerate(d.files):
                    sib = UNUSED if i >= len(d.files) - 1 else len(file_tab) + 0x20 + al(len(_u16(n)), 4)
                    add_file(p, n, s, dir_off, sib)
            if d.dirs:
                struct.pack_into("<I", dir_tab, dir_off + 8, len(dir_tab))
                for i, c in enumerate(d.dirs):
                    sib = UNUSED if i >= len(d.dirs) - 1 else len(dir_tab) + 0x18 + al(len(_u16(c.name)), 4)
                    add_dir(c, dir_off, sib)
                for c in d.dirs:
                    add_children(c, c.offset)

        add_dir(self.root, 0, UNUSED)
        add_children(self.root, 0)
        assert len(dir_tab) == self.dir_len and len(file_tab) == self.file_len and data[0] == self.data_len

        pos = 0x28
        sections = []
        for i, (tab_len) in enumerate((self.dir_ht * 4, len(dir_tab), self.file_ht * 4, len(file_tab))):
            if i in (1, 3) and tab_len == 0:
                sections.append((0, 0))
            else:
                sections.append((pos, tab_len))
                pos += tab_len
        data_off = al(pos, 0x10)
        meta = bytearray(struct.pack("<I", 0x28))
        for o, s in sections:
            meta += struct.pack("<II", o, s)
        meta += struct.pack("<I", data_off)
        meta += struct.pack(f"<{self.dir_ht}I", *dir_hash) + dir_tab
        meta += struct.pack(f"<{self.file_ht}I", *file_hash) + file_tab
        self.meta = bytes(meta.ljust(data_off, b"\0"))

    def ivfc_header(self, master: bytes) -> bytes:
        lo2 = al(self.l1_size, BLOCK)
        lo3 = al(lo2 + self.l2_size, BLOCK)
        h = b"IVFC" + struct.pack("<II", 0x10000, self.master_size)
        for lo, sz in ((0, self.l1_size), (lo2, self.l2_size), (lo3, self.l3_size)):
            h += struct.pack("<QQII", lo, sz, 12, 0)
        h += struct.pack("<II", IVFC_HDR, 0)
        assert len(h) == IVFC_HDR
        return h.ljust(IVFC_HDR_AL, b"\0") + master

    def write(self, out, base: int, progress: Callable[[int, int], None] | None = None) -> bytes:
        """Escribe el romfs en el archivo abierto `out` a partir de `base`. Devuelve el superbloque
        (cabecera IVFC + hash maestro) para el hash de la cabecera NCCH."""
        l2 = bytearray()
        buf = bytearray()
        done = [0]
        out.seek(base + self.off_l3)

        def push(data):
            buf.extend(data)
            n = len(buf) // BLOCK * BLOCK
            if n:
                mv = memoryview(buf)[:n]
                out.write(mv)
                for i in range(0, n, BLOCK):
                    l2.extend(hashlib.sha256(mv[i:i + BLOCK]).digest())
                mv.release()
                del buf[:n]

        push(self.meta)
        pos = 0
        for path, doff, size in self.order:
            if doff > pos:
                push(b"\0" * (doff - pos))
            with open(path, "rb") as f:
                left = size
                while left:
                    chunk = f.read(min(left, 4 << 20))
                    if not chunk:
                        raise OSError(f"{path}: el archivo ha cambiado mientras se leía")
                    push(chunk)
                    left -= len(chunk)
                    done[0] += len(chunk)
                    if progress:
                        progress(done[0], self.data_len)
            pos = doff + size
        if buf:
            push(b"\0" * (BLOCK - len(buf)))  # el ultimo bloque, con ceros (como el calloc de makerom)

        def level(data: bytes) -> bytes:
            data = data.ljust(al(len(data), BLOCK), b"\0")
            return b"".join(hashlib.sha256(data[i:i + BLOCK]).digest() for i in range(0, len(data), BLOCK))

        l2 = bytes(l2)
        assert len(l2) == self.l2_size
        l1 = level(l2)
        master = level(l1)
        out.seek(base + self.off_l1)
        out.write(l1.ljust(al(len(l1), BLOCK), b"\0"))
        out.seek(base + self.off_l2)
        out.write(l2.ljust(al(len(l2), BLOCK), b"\0"))
        sb = self.ivfc_header(master)
        out.seek(base)
        out.write(sb.ljust(self.off_l3, b"\0"))
        return sb


# --- el .cia ---------------------------------------------------------------------------------------

def _cia_layout(b: bytes) -> dict:
    hs, _typ, _ver, cs, ts, ms, mts, cos = struct.unpack_from("<IHHIIIIQ", b, 0)
    o_cert = al(hs, 64)
    o_tik = o_cert + al(cs, 64)
    o_tmd = o_tik + al(ts, 64)
    o_con = o_tmd + al(ms, 64)
    o_meta = o_con + al(cos, 64)
    return dict(hdr=hs, o_tmd=o_tmd, tmd=ms, o_con=o_con, content=cos, o_meta=o_meta, meta=mts)


def build_cia(template: Path, romfs_dir: Path, out: Path,
              progress: Callable[[str, int, int], None] | None = None) -> None:
    """`template`: el .cia de makerom (con un romfs de relleno); `romfs_dir`: lo que va en romfs:/."""
    t = Path(template).read_bytes()
    L = _cia_layout(t)
    tmd = bytearray(t[L["o_tmd"]:L["o_tmd"] + L["tmd"]])
    sig = struct.unpack(">I", tmd[:4])[0]
    if sig != 0x10004:
        raise ValueError(f"TMD con una firma inesperada ({sig:#x})")
    H = 0x140
    count = struct.unpack_from(">H", tmd, H + 0x9E)[0]
    chunk = H + 0xC4 + 0x900
    if count != 1 or struct.unpack_from(">H", tmd, chunk + 6)[0] & 1:
        raise ValueError("el .cia de makerom no es de un contenido sin cifrar")
    ncch = t[L["o_con"]:L["o_con"] + L["content"]]
    if ncch[0x100:0x104] != b"NCCH":
        raise ValueError("el contenido no es un NCCH")
    mu = 0x200 << ncch[0x188 + 6]
    romfs_off = struct.unpack_from("<I", ncch, 0x1B0)[0] * mu
    if not romfs_off:
        raise ValueError("el .cia de makerom no lleva romfs")
    meta = t[L["o_meta"]:L["o_meta"] + L["meta"]]

    rf = RomFs(romfs_dir)
    ncch_size = al(romfs_off + al(rf.size, mu), mu)
    hdr = bytearray(ncch[:romfs_off])
    struct.pack_into("<I", hdr, 0x104, ncch_size // mu)
    struct.pack_into("<I", hdr, 0x1B4, al(rf.size, mu) // mu)
    hash_size = al(rf.header_size, mu)
    struct.pack_into("<I", hdr, 0x1B8, hash_size // mu)
    o_con = L["o_con"]
    o_meta = o_con + al(ncch_size, 64)

    tmp = Path(str(out) + ".part")
    with open(tmp, "w+b") as f:
        f.truncate(o_meta + len(meta))
        # el romfs (lo largo), luego la cabecera NCCH con el hash de su superbloque
        sb = rf.write(f, o_con + romfs_off, (lambda d, n: progress("romfs", d, n)) if progress else None)
        hdr[0x1E0:0x200] = hashlib.sha256(sb.ljust(hash_size, b"\0")).digest()
        f.seek(o_con)
        f.write(hdr)
        # el SHA-256 del contenido entero (una pasada mas, leyendo lo escrito)
        h = hashlib.sha256()
        f.seek(o_con)
        left = ncch_size
        while left:
            d = f.read(min(left, 8 << 20))
            if not d:
                raise OSError("el .cia se ha quedado corto")
            h.update(d)
            left -= len(d)
            if progress:
                progress("hash", ncch_size - left, ncch_size)
        struct.pack_into(">Q", tmd, chunk + 8, ncch_size)
        tmd[chunk + 0x10:chunk + 0x30] = h.digest()
        tmd[H + 0xC4 + 4:H + 0xC4 + 0x24] = hashlib.sha256(tmd[chunk:chunk + 0x30 * count]).digest()
        tmd[H + 0xA4:H + 0xC4] = hashlib.sha256(tmd[H + 0xC4:H + 0xC4 + 0x900]).digest()
        # la cabecera del CIA, los certificados, el ticket y la TMD, y los metadatos al final
        head = bytearray(t[:L["o_tmd"]])
        struct.pack_into("<Q", head, 0x18, ncch_size)
        f.seek(0)
        f.write(head)
        f.write(bytes(tmd).ljust(o_con - L["o_tmd"], b"\0"))
        f.seek(o_meta)
        f.write(meta)
    os.replace(tmp, out)
