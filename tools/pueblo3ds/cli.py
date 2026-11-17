"""Sin ventana (para pruebas):

    PuebloCTR.exe build DISCO1.iso [DISCO2.iso] -o PuebloCTR.cia [--sin-texturas] [--sin-videos]
                  [--ffmpeg RUTA] [--partida F.gci ...]
    PuebloCTR.exe cia salida.cia          solo el motor en un .cia (sin el juego; para pruebas)
    PuebloCTR.exe info DISCO.iso ...      que imagen es
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import PUEBLO_VERSION, __version__
from . import build as builder
from . import discs as dk


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="PuebloCTR", description=f"Asistente {__version__} de PuebloCTR {PUEBLO_VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="de las imágenes de disco a un .cia con todo dentro")
    b.add_argument("discos", nargs="+", type=Path)
    b.add_argument("-o", "--out", type=Path, default=builder.default_output())
    b.add_argument("--sin-texturas", action="store_true")
    b.add_argument("--sin-videos", action="store_true")
    b.add_argument("--ffmpeg", default="")
    b.add_argument("--partida", action="append", type=Path, default=[])
    b.add_argument("--runtime", type=Path, default=None)
    c = sub.add_parser("cia", help="solo PuebloCTR.cia")
    c.add_argument("salida", type=Path)
    c.add_argument("--runtime", type=Path, default=None)
    i = sub.add_parser("info", help="qué imagen es")
    i.add_argument("discos", nargs="+", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "info":
        for p in a.discos:
            ok, txt, _ = dk.describe(dk.read_disc(p))
            print(f"{p}: {txt}")
        return 0
    runtime = a.runtime or builder.default_runtime()
    if a.cmd == "cia":
        builder.make_cia(runtime, a.salida)
        print(a.salida, a.salida.stat().st_size)
        return 0

    ds = [dk.read_disc(p) for p in a.discos[:2]]
    ok, txt, _ = dk.check_pair(ds[0], ds[1] if len(ds) > 1 else None)
    print(txt, flush=True)
    if not ok:
        return 2
    ff = ""
    if not a.sin_videos:
        ff = a.ffmpeg or builder.find_ffmpeg()
        if builder.ffmpeg_state(ff) != 2:
            print("ffmpeg no encontrado o sin libx264: usa --ffmpeg RUTA o --sin-videos", flush=True)
            return 2
    last = [""]

    def progress(text: str, frac: float) -> None:
        if text != last[0]:
            last[0] = text
            print(f"{100 * frac:5.1f} %  {text}", flush=True)

    try:
        r = builder.build([d.path for d in ds], a.out, runtime, textures=not a.sin_texturas,
                          movies=not a.sin_videos, ffmpeg=ff, saves=a.partida, progress=progress)
    except builder.BuildError as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    print(f"Listo en {r.seconds:.0f} s: {r.cia} ({r.cia.stat().st_size} bytes)")
    for w in r.warnings:
        print("aviso:", w)
    return 0
