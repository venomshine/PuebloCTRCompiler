"""Comprueba un PuebloCTR.cia sin la consola.

    python3 tests/verificar_cia.py PuebloCTR.cia [CARPETA]

- el hash del contenido (TMD), el del superbloque del romfs (cabecera NCCH) y los tres niveles
  del árbol IVFC, bloque a bloque (lo que la consola comprueba al leer);
- con CARPETA (lo que tiene que ir en romfs:/, p. ej. la de PuebloPrep: 3ds/pueblo), busca cada
  archivo en el romfs como lo hace libctru (por las tablas hash) y lo compara byte a byte.

Escrito aparte de tools/pueblo3ds/ciabuild.py a proposito: no comparte codigo con lo que comprueba.
"""

import hashlib
import os
import struct
import sys


def al(x, a):
    return (x + a - 1) // a * a


def main(cia, ref=None):
    f = open(cia, "rb")
    hs, _, _, cs, ts, ms, mts, cos = struct.unpack("<IHHIIIIQ", f.read(0x20))
    o_tmd = al(hs, 64) + al(cs, 64) + al(ts, 64)
    o_con = o_tmd + al(ms, 64)
    f.seek(o_tmd)
    tmd = f.read(ms)
    chunk = 0x140 + 0xC4 + 0x900
    f.seek(o_con)
    n = f.read(0x200)
    mu = 0x200 << n[0x188 + 6]
    roff, _rsize, rhash = [x * mu for x in struct.unpack_from("<III", n, 0x1B0)]
    R = o_con + roff
    ok = True

    def rd(off, k):
        f.seek(R + off)
        return f.read(k)

    def say(text, good):
        nonlocal ok
        ok &= good
        print(("OK   " if good else "MAL  ") + text)

    h = hashlib.sha256()
    f.seek(o_con)
    left = cos
    while left:
        d = f.read(min(left, 8 << 20))
        h.update(d)
        left -= len(d)
    say("hash del contenido (TMD)", h.digest() == tmd[chunk + 0x10:chunk + 0x30])
    iv = rd(0, 0x60)
    say("cabecera IVFC", iv[:4] == b"IVFC")
    msize = struct.unpack_from("<I", iv, 8)[0]
    lv = [struct.unpack_from("<QQI", iv, 0x0C + 24 * i) for i in range(3)]
    master = rd(0x60, msize)
    say("hash del superbloque (cabecera NCCH)", hashlib.sha256(rd(0, rhash)).digest() == n[0x1E0:0x200])
    off3 = al(0x60 + msize, 0x1000)
    off1 = off3 + al(lv[2][1], 0x1000)
    off2 = off1 + al(lv[0][1], 0x1000)

    def check(data_off, size, hashes_off, hashes):
        good = True
        for i in range(al(size, 0x1000) // 0x1000):
            got = hashlib.sha256(rd(data_off + i * 0x1000, 0x1000).ljust(0x1000, b"\0")).digest()
            good &= got == (hashes[i * 32:(i + 1) * 32] if hashes is not None else rd(hashes_off + i * 32, 32))
        return good

    say("nivel 1 contra el hash maestro", check(off1, lv[0][1], None, master))
    say("nivel 2 contra el nivel 1", check(off2, lv[1][1], off1, None))
    say("nivel 3 contra el nivel 2", check(off3, lv[2][1], off2, None))
    if ref:
        L3 = off3
        hd = struct.unpack("<10I", rd(L3, 40))

        def phash(parent, name):
            x = parent ^ 123456789
            for ch in name:
                x = (((x >> 5) | (x << 27)) & 0xFFFFFFFF) ^ ord(ch)
            return x

        def find(table, parent, name, dirs):
            ht, hn, tab = (hd[1], hd[2], hd[3]) if dirs else (hd[5], hd[6], hd[7])
            at = struct.unpack("<I", rd(L3 + ht + (phash(parent, name) % (hn // 4)) * 4, 4))[0]
            while at != 0xFFFFFFFF:
                if dirs:
                    p, _, _, _, nxt, nb = struct.unpack("<6I", rd(L3 + tab + at, 0x18))
                    nm = rd(L3 + tab + at + 0x18, nb)
                    if p == parent and nm.decode("utf-16-le") == name:
                        return at
                else:
                    p, _, off, size, nxt, nb = struct.unpack("<IIQQII", rd(L3 + tab + at, 0x20))
                    nm = rd(L3 + tab + at + 0x20, nb)
                    if p == parent and nm.decode("utf-16-le") == name:
                        return off, size
                at = nxt
            return None

        count = bad = 0
        for root, _dirs, files in os.walk(ref):
            rel = os.path.relpath(root, ref)
            d = 0
            for part in [] if rel == "." else rel.split(os.sep):
                d = find(None, d, part, True)
                if d is None:
                    break
            for fn in files:
                count += 1
                r = find(None, d, fn, False) if d is not None else None
                with open(os.path.join(root, fn), "rb") as src:
                    if r is None or rd(L3 + hd[9] + r[0], r[1]) != src.read():
                        bad += 1
                        print("MAL  " + os.path.join(rel, fn))
        say(f"{count} archivos buscados como libctru y comparados ({bad} distintos)", bad == 0)
    print("TODO OK" if ok else "HAY FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
