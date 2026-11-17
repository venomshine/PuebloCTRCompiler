"""De las imagenes de disco a UN solo archivo: PuebloCTR.cia, con el juego dentro (nada que copiar a la SD).

1. PuebloPrep (puebloprep-cli, el de PuebloCTR, compilado para Windows) saca los archivos de los
   discos, hace el pack de texturas para la GPU de la 3DS y convierte los videos con ffmpeg, en
   una carpeta temporal (TEMP/3ds/pueblo/, como en la SD).
2. Si hay partidas (.gci / .gcs), PuebloPrep las mete en la tarjeta de memoria (saves/memcard.bin).
3. makerom monta un .cia pequeno con el motor (re4.elf: el de PuebloCTR con unico-cia.patch, que lee
   los datos del romfs del titulo), el icono y el banner; ciabuild.py le pone la carpeta temporal
   como romfs (varios GB, por partes: sin cargarlo en memoria). La carpeta temporal se borra.

El motor, makerom y puebloprep-cli van en la carpeta "runtime" que acompana a la herramienta
(dentro del .exe; ver tools/build_exe.sh).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import PUEBLO_VERSION

APP = "PuebloCTR"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: sin consolas negras

# Lo que pesa cada parte en la barra (mas o menos lo que tarda en un PC normal)
W_RVZ = 0.11  # descomprimir un RVZ (cada disco)
W_DISC = 0.10  # sacar los archivos de un disco
W_TEX = 0.30
W_MOVIES = 0.27
W_CIA = 0.12  # escribir el .cia (3,5 GB) y leerlo otra vez para su hash
MOVIES = ("adaend_c", "adaend_m", "demo0", "demo1", "ending", "opening", "r214_ev", "r229_ev", "r333_ev")

# Estado para la ventana: lo que hace cada fase ahora (lo lee la ventana cada medio segundo)
STATE: dict = {}


class BuildError(Exception):
    pass


@dataclass
class BuildReport:
    out: Path
    cia: Path | None = None
    seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)
    edition: str = ""
    textures: bool = False
    movies: int = 0
    saves: list[str] = field(default_factory=list)
    saves_failed: list[str] = field(default_factory=list)
    log: Path | None = None


# --- donde esta cada cosa -----------------------------------------------------------------------

def default_runtime() -> Path:
    """Carpeta runtime dentro del .exe (PyInstaller) o junto a tools/."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "runtime"
    return Path(__file__).resolve().parents[1] / "runtime"


def data_dir() -> Path:
    """Los datos de la herramienta (el registro, ffmpeg descargado, los tiempos): no en el Escritorio."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    d = Path(base) / "PuebloCTR" if base else Path.home() / ".puebloctr"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path.cwd()
    return d


def _exe(runtime: Path, name: str) -> Path:
    names = [name + ".exe", name] if os.name == "nt" else [name, name + ".exe"]
    for n in names:
        p = runtime / n
        if p.is_file():
            return p
    found = shutil.which(name)
    if found:
        return Path(found)
    raise BuildError(f"no se encuentra {name} en {runtime}")


def find_puebloprep(runtime: Path) -> Path:
    return _exe(runtime, "puebloprep-cli")


def find_makerom(runtime: Path) -> Path:
    return _exe(runtime, "makerom")


# --- ffmpeg (para los videos) ------------------------------------------------------------------

FFMPEG_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"  # el que recomienda PuebloCTR


def downloaded_ffmpeg() -> Path:
    return data_dir() / "ffmpeg" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")


def find_ffmpeg() -> str:
    """Donde lo pone la gente: junto al .exe, el que bajo esta herramienta, C:\\ffmpeg\\bin, el PATH."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    cands = [here / name, here / "bin" / name, downloaded_ffmpeg()]
    if os.name == "nt":
        cands.append(Path("C:/ffmpeg/bin/ffmpeg.exe"))
    else:
        cands += [Path("/opt/homebrew/bin/ffmpeg"), Path("/usr/local/bin/ffmpeg"), Path("/usr/bin/ffmpeg")]
    for c in cands:
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg") or ""


def ffmpeg_in(path: str) -> str:
    """Una carpeta elegida para ffmpeg: su ffmpeg, o bin/ffmpeg (un zip de Windows descomprimido)."""
    p = Path(path.strip('" '))
    if p.is_dir():
        name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        for c in (p / name, p / "bin" / name):
            if c.is_file():
                return str(c)
    return str(p) if path.strip() else ""


def ffmpeg_state(path: str) -> int:
    """0 no esta (o no arranca), 1 sin libx264, 2 bien (como puebloprep_ffmpeg_check)."""
    path = ffmpeg_in(path)
    if not path:
        return 0
    try:
        res = subprocess.run([path, "-hide_banner", "-encoders"], capture_output=True, text=True,
                             errors="replace", timeout=20, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return 0
    return 2 if "libx264" in res.stdout else 1


def download_ffmpeg(progress: Callable[[int, int], None] | None = None) -> str:
    """Baja el ffmpeg de gyan.dev (con libx264) y deja solo ffmpeg.exe en los datos de la herramienta."""
    import urllib.request
    import zipfile

    dest = downloaded_ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / "ffmpeg.zip.part"
    req = urllib.request.Request(FFMPEG_ZIP, headers={"User-Agent": "PuebloCTR-asistente"})
    with urllib.request.urlopen(req, timeout=60) as r, tmp.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            f.write(block)
            done += len(block)
            if progress:
                progress(done, total)
    with zipfile.ZipFile(tmp) as z:
        member = next((n for n in z.namelist() if n.lower().endswith("/bin/ffmpeg.exe")), None)
        if member is None:
            raise BuildError("el zip de ffmpeg no trae bin/ffmpeg.exe")
        with z.open(member) as src, (dest.parent / "ffmpeg.exe.part").open("wb") as out:
            shutil.copyfileobj(src, out)
    os.replace(dest.parent / "ffmpeg.exe.part", dest)
    tmp.unlink(missing_ok=True)
    return str(dest)


# --- la tarjeta SD ---------------------------------------------------------------------------------

def sd_cards() -> list[Path]:
    """Las tarjetas SD de una 3DS conectadas al PC (llevan la carpeta «Nintendo 3DS»)."""
    roots = []
    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase[3:]:  # de la D: en adelante
            r = Path(f"{letter}:/")
            try:
                if (r / "Nintendo 3DS").is_dir():
                    roots.append(r)
            except OSError:
                pass
    else:
        for base in (Path("/media"), Path("/run/media"), Path("/Volumes")):
            try:
                for r in list(base.glob("*")) + list(base.glob("*/*")):
                    if (r / "Nintendo 3DS").is_dir():
                        roots.append(r)
            except OSError:
                pass
    return roots


def is_sd_root(path: Path) -> bool:
    try:
        return (Path(path) / "Nintendo 3DS").is_dir()
    except OSError:
        return False


def default_output() -> Path:
    for base in (Path.home() / "Desktop", Path.home() / "Escritorio", Path.home()):
        if base.is_dir():
            return base / f"{APP}.cia"
    return Path(f"{APP}.cia").resolve()


def work_dir(out: Path) -> Path:
    """La carpeta temporal: junto al .cia (el mismo disco: sin copiar de un disco a otro), salvo si el .cia va
    a la SD de la consola (lenta y pequena): entonces en la carpeta temporal del PC."""
    out = Path(out)
    if is_sd_root(Path(out.anchor)) if out.anchor else False:
        import tempfile
        return Path(tempfile.gettempdir()) / "PuebloCTR-temporal"
    return out.parent / "PuebloCTR-temporal"


def free_bytes(path: Path) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return 0


# --- el .cia -------------------------------------------------------------------------------------

def make_cia(runtime: Path, out: Path, romfs: Path | None = None) -> None:
    """makerom: el .cia con el motor; `romfs` una carpeta para romfs:/ (pequena: makerom la carga en memoria)."""
    for name in ("re4.elf", "PuebloCTR.rsf", "icon.smdh", "banner.bnr"):
        if not (runtime / name).is_file():
            raise BuildError(f"falta {name} en {runtime}")
    makerom = find_makerom(runtime)
    out.parent.mkdir(parents=True, exist_ok=True)
    rsf = runtime / "PuebloCTR.rsf"
    if romfs is not None:
        text = rsf.read_text(encoding="utf-8")
        rsf = out.parent / "PuebloCTR-romfs.rsf"
        rsf.write_text(text + "\nRomFs:\n  RootPath                : $(APP_ROMFS)\n", encoding="utf-8")
    cmd = [
        str(makerom), "-f", "cia", "-o", str(out),
        "-elf", str(runtime / "re4.elf"),
        "-rsf", str(rsf),
        "-icon", str(runtime / "icon.smdh"),
        "-banner", str(runtime / "banner.bnr"),
        "-target", "t",
    ]
    if romfs is not None:
        cmd.append(f"-DAPP_ROMFS={romfs}")
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
    if romfs is not None:
        rsf.unlink(missing_ok=True)
    if res.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise BuildError("makerom falló:\n" + (res.stderr or res.stdout)[-2000:])


def make_full_cia(runtime: Path, data: Path, out: Path, progress: Callable[[str, int, int], None] | None = None):
    """El .cia con `data` (lo de 3ds/pueblo: data/, textures.pak, movie/, saves/) dentro, en romfs:/."""
    from . import ciabuild

    tmpdir = out.parent / (out.name + ".plantilla")
    shutil.rmtree(tmpdir, ignore_errors=True)
    (tmpdir / "relleno").mkdir(parents=True)
    (tmpdir / "relleno" / "relleno").write_bytes(b"\0")
    try:
        make_cia(runtime, tmpdir / "plantilla.cia", romfs=tmpdir / "relleno")
        ciabuild.build_cia(tmpdir / "plantilla.cia", data, out, progress)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- PuebloPrep ------------------------------------------------------------------------------------

class Prep:
    """puebloprep-cli en marcha: lee lo que dice linea a linea y lo traduce a avance."""

    def __init__(self, exe: Path, args: list[str], cwd: Path, on_line: Callable[[str], None]):
        self.proc = subprocess.Popen([str(exe), *args], cwd=str(cwd), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                     encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WINDOW)
        RUNNING.append(self.proc)
        self.lines: list[str] = []
        try:
            for raw in self.proc.stdout:
                line = raw.rstrip("\r\n")
                if line:
                    self.lines.append(line)
                    on_line(line)
            self.code = self.proc.wait()
        finally:
            RUNNING.remove(self.proc)

    def error(self) -> str:
        errs = [ln[len("error: "):] for ln in self.lines if ln.startswith("error: ")]
        if errs:
            return errs[-1]
        return "\n".join(self.lines[-6:]) or f"puebloprep-cli terminó con el código {self.code}"


RUNNING: list = []  # los procesos en marcha (para cortarlos si se cierra la ventana)


def cancel() -> None:
    for p in RUNNING:
        try:
            p.kill()
        except OSError:
            pass


def _translate(err: str) -> str:
    """Los errores de PuebloPrep que mas salen, en espanol (el original va detras)."""
    table = [
        ("not enough room", "No hay espacio suficiente en el disco de destino (hacen falta unos 4 GB, 7 GB con RVZ)."),
        ("no GameCube disc header", "Una de las imágenes no es un disco de GameCube que se pueda leer."),
        ("is no GameCube disc", "Una de las imágenes no es un disco de GameCube."),
        ("given twice", "Has elegido dos veces el mismo disco."),
        ("different editions", "Los discos son de ediciones distintas."),
        ("disc 1 is missing", "Falta el disco 1."),
        ("is not played by this beta", "Esa edición no la juega esta versión (solo Europa G4BP08 y EE. UU. G4BE08)."),
        ("ffmpeg could not", "ffmpeg no pudo convertir un vídeo (¿es una versión con libx264?)."),
        ("FAT32", "Un nombre de archivo no cabe en FAT32 (la SD)."),
        ("the card full", "No se pudo escribir: ¿el disco o la SD están llenos?"),
    ]
    for key, es in table:
        if key in err:
            return f"{es}\n\n({err})"
    return err


def build(
    discs: list[Path],
    out: Path,
    runtime: Path,
    textures: bool = True,
    movies: bool = True,
    ffmpeg: str = "",
    saves: list[Path] | None = None,
    progress: Callable[[str, float], None] | None = None,
) -> BuildReport:
    t0 = time.monotonic()
    cia = Path(out).resolve()
    out = work_dir(cia)  # la carpeta temporal (lo de la SD), se borra al terminar
    runtime = Path(runtime).resolve()
    discs = [Path(d).resolve() for d in discs]
    saves = [Path(s).resolve() for s in saves or []]
    report = BuildReport(out=cia, textures=textures)
    STATE.clear()
    STATE.update({"discs": "", "tex_on": textures, "mov_on": movies})
    prep = find_puebloprep(runtime)
    logdir = data_dir()
    report.log = logdir / "puebloprep.log"
    try:  # un registro por vez (PuebloPrep lo abre para anadir)
        report.log.unlink(missing_ok=True)
    except OSError:
        pass

    rvz = [d for d in discs if _is_rvz(d)]
    weights = {"rvz": W_RVZ * len(rvz), "disc": W_DISC * len(discs), "tex": W_TEX if textures else 0.0,
               "mov": W_MOVIES if movies else 0.0, "cia": W_CIA}
    total_w = sum(weights.values())
    done_w = {k: 0.0 for k in weights}  # lo hecho de cada parte, de 0 a su peso

    def say(text: str) -> None:
        if progress:
            progress(text, min(0.999, sum(done_w.values()) / total_w))

    st = {"rvz_i": -1, "movie_i": 0}

    def on_line(line: str) -> None:
        m = re.match(r"RVZ:\s+(\d+) %", line)
        if " RVZ of " in line:
            st["rvz_i"] += 1
            STATE["discs"] = f"descomprimiendo el RVZ {st['rvz_i'] + 1}"
        if m:
            done_w["rvz"] = W_RVZ * (st["rvz_i"] + int(m.group(1)) / 100)
            say(f"Descomprimiendo el RVZ {st['rvz_i'] + 1} de {len(rvz)}: {m.group(1)} %")
            return
        m = re.match(r"disc (\d): +(\d+) %", line)
        if m:
            n = int(m.group(1))
            done_w["rvz"] = weights["rvz"]
            done_w["disc"] = W_DISC * (min(n - 1, len(discs) - 1) + int(m.group(2)) / 100)
            STATE["discs"] = f"disco {n}: {m.group(2)} %"
            say(f"Sacando los archivos del disco {n}: {m.group(2)} %")
            return
        m = re.match(r"disc (\d): (\d+) files ->", line)
        if m:
            n = int(m.group(1))
            done_w["disc"] = W_DISC * min(n, len(discs))
            STATE["discs"] = f"disco {n}: {m.group(2)} archivos"
            if done_w["disc"] >= weights["disc"] - 1e-6:
                STATE["discs_done"] = True
            say(f"Disco {n}: {m.group(2)} archivos")
            return
        m = re.match(r"textures: +(\d+) %", line)
        if m:
            STATE["discs_done"] = True
            done_w["tex"] = W_TEX * int(m.group(1)) / 100
            STATE["tex"] = f"{m.group(1)} %"
            say(f"Pack de texturas: {m.group(1)} %")
            return
        if line.startswith("textures: ") and line.rstrip().endswith("textures.pak"):
            done_w["tex"] = weights["tex"]
            STATE["tex_done"] = True
            say("Pack de texturas hecho")
            return
        m = re.match(r"movies: (\w+): (\d+) frames", line)
        if m:
            st["movie_i"] += 1
            done_w["mov"] = W_MOVIES * st["movie_i"] / len(MOVIES)
            STATE["mov"] = f"{st['movie_i']} de {len(MOVIES)}"
            report.movies = st["movie_i"]
            say(f"Vídeos: {st['movie_i']} de {len(MOVIES)}")
            return
        m = re.match(r"movies: (\w+)$", line)
        if m:
            STATE["discs_done"] = True
            STATE["tex_done"] = STATE.get("tex_done") or not textures
            STATE["mov"] = f"{st['movie_i']} de {len(MOVIES)}"
            say(f"Vídeos: convirtiendo {m.group(1)} ({st['movie_i'] + 1} de {len(MOVIES)})")
            return
        if line.startswith("movies: ") and " of " in line and " in " in line:
            done_w["mov"] = weights["mov"]
            STATE["mov_done"] = True
            return
        if line.startswith("warning: "):
            w = line[len("warning: "):]
            for d in discs:
                w = w.replace(str(d), d.name)
            report.warnings.append(w)
            return
        m = re.match(r".*?: (.+?), disc (\d), \"", line)
        if m and not report.edition:
            report.edition = m.group(1)

    # el espacio: la carpeta temporal y el .cia (unos 3,5 GB cada uno; los RVZ, 1,4 GB mas cada uno mientras)
    need = sum(Path(d).stat().st_size if not _is_rvz(d) else 1_459_978_240 for d in discs) + (400 << 20) + (230 << 20)
    have = free_bytes(cia.parent)
    if 0 < have < need * 2 and work_dir(cia).parent == cia.parent:
        raise BuildError(f"No hay espacio suficiente en {cia.anchor or cia.parent}: hacen falta unos "
                         f"{need * 2 / 1e9:.0f} GB libres mientras se prepara (hay {have / 1e9:.1f} GB). "
                         "Elige otro disco para el .cia.")
    out.mkdir(parents=True, exist_ok=True)
    args = []
    for d in discs:
        args += ["--in", str(d)]
    args += ["--out", str(out)]
    if textures:
        args.append("--textures")
    if movies:
        args += ["--movies", "--ffmpeg", ffmpeg_in(ffmpeg) or "ffmpeg"]
    say("Leyendo los discos")
    STATE["discs"] = "leyendo"
    p = _run(prep, args, logdir, on_line)
    if p.code != 0:
        raise BuildError(_translate(p.error()))
    STATE.update({"discs_done": True, "tex_done": True, "mov_done": True})

    # las partidas, a la tarjeta de memoria del port
    if saves:
        say("Metiendo las partidas en la tarjeta de memoria")
        args = ["--out", str(out)]
        (out / "3ds" / "pueblo" / "saves" / "memcard.bin").unlink(missing_ok=True)  # solo las de esta vez
        for s in saves:
            args += ["--import-gci", str(s)]
        p = _run(prep, args, logdir, lambda ln: None)
        for s in saves:
            name = str(s)
            if any(ln.startswith(f"gci: {name} imported") for ln in p.lines):
                report.saves.append(Path(s).name)
            else:
                report.saves_failed.append(Path(s).name)

    else:
        (out / "3ds" / "pueblo" / "saves" / "memcard.bin").unlink(missing_ok=True)

    # el .cia: makerom con el motor y, dentro, todo lo de 3ds/pueblo
    STATE["cia"] = "makerom"
    say("Montando el .cia (makerom)")

    def cia_progress(stage: str, done: int, total: int) -> None:
        f = done / max(1, total)
        done_w["cia"] = W_CIA * (0.75 * f if stage == "romfs" else 0.75 + 0.25 * f)
        STATE["cia"] = f"{100 * f:.0f} %" if stage == "romfs" else "comprobando"
        if stage == "romfs":
            say(f"Metiendo el juego en el .cia: {done / 1048576:.0f} de {total / 1048576:.0f} MB")
        else:
            say(f"Calculando el hash del .cia: {100 * f:.0f} %")

    cia.parent.mkdir(parents=True, exist_ok=True)
    make_full_cia(runtime, out / "3ds" / "pueblo", cia, cia_progress)
    done_w["cia"] = W_CIA
    report.cia = cia
    shutil.rmtree(out, ignore_errors=True)  # la carpeta temporal: ya esta todo en el .cia
    report.seconds = time.monotonic() - t0
    if progress:
        progress("Listo", 1.0)
    return report


def _run(exe: Path, args: list[str], cwd: Path, on_line) -> Prep:
    return Prep(exe, args, cwd, on_line)


def _is_rvz(path: Path) -> bool:
    try:
        with Path(path).open("rb") as f:
            return f.read(4) == b"RVZ\x01"
    except OSError:
        return False


def version_text() -> str:
    return PUEBLO_VERSION


__all__ = ["build", "BuildError", "BuildReport", "STATE", "default_runtime", "find_ffmpeg", "ffmpeg_state",
           "download_ffmpeg", "sd_cards", "is_sd_root", "default_output", "cancel"]
