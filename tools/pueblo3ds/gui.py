"""Asistente de Windows de PuebloCTR: de tus imágenes de disco a UN .cia con todo dentro, listo para instalar.

Igual que el de The Rockport Blacklist (MostWanted3DS.exe): bienvenida -> discos -> opciones ->
progreso -> listo (-> instalar por Wi-Fi con un QR). El trabajo pesado lo hace PuebloPrep
(puebloprep-cli) en un proceso aparte, leido desde un hilo, para que la ventana no se congele.
"""

from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import PUEBLO_VERSION, __version__
from . import build as builder
from . import discs as dk
from . import i18n
from .i18n import _
from .qrcodegen import QrCode, QrSegment
from .serve import CiaServer

APP = "PuebloCTR"  # nombre del .cia
TITLE = "PuebloCTR"  # el que se ve
BG = "#121418"
PANEL = "#1B1E24"
FG = "#EEF0F3"
DIM = "#8A909A"
ACCENT = "#4FA3FF"
OK = "#5CD67A"
WARN = "#F2C14E"
BAD = "#F05A5A"
LEVEL = {"ok": OK, "warn": WARN, "bad": BAD, "dim": DIM}


def _font(size: int, bold: bool = False):
    family = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
    return (family, size, "bold" if bold else "normal")



def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


CARD_W = 584  # ancho de las tarjetas a 100 % (96 ppp): todo se multiplica por S
WIN_W, WIN_H = 640, 560  # la ventana a 100 %; el alto crece si lo que lleva no cabe
LINE = "#2A2F38"
S = 1.0  # escala de la pantalla (Windows a 125 % -> 1,25): las letras van en puntos y crecen solas


def px(n: float) -> int:
    """Pixeles a 100 % -> los de esta pantalla (sin esto, a 125 % o 150 % no cabia nada)."""
    return int(round(n * S))


def _round_rect(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    """Un rectangulo con las esquinas redondeadas en un Canvas (un poligono suavizado)."""
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
           x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


class Card(tk.Canvas):
    """Una tarjeta: fondo PANEL con las esquinas redondeadas y su contenido en .inner (un Frame).
    Se ajusta sola al alto de lo que lleva."""

    def __init__(self, parent, width=None, pad=16, outline=None, bg_parent=BG):
        width = width or px(CARD_W)
        pad = px(pad)
        super().__init__(parent, width=width, height=40, bg=bg_parent, highlightthickness=0, bd=0)
        self.pad, self.w, self.outline = pad, width, outline
        self.inner = tk.Frame(self, bg=PANEL)
        self.create_window(pad, pad, anchor="nw", window=self.inner, width=width - 2 * pad)
        self.inner.bind("<Configure>", self._fit)

    def _fit(self, _event=None):
        h = self.inner.winfo_reqheight() + 2 * self.pad
        self.configure(height=h)
        self.delete("bg")
        _round_rect(self, 1, 1, self.w - 2, h - 2, px(12), fill=PANEL, outline=self.outline or PANEL, width=1,
                    tags="bg")
        self.tag_lower("bg")

    def set_outline(self, color):
        self.outline = color
        self._fit()


def _dot(parent, state: str, bg=PANEL, size=18) -> tk.Canvas:
    """El circulo de una fase o un paso: hecho (verde con ✓), ahora (azul) o pendiente (gris)."""
    size = px(size)
    c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
    c.size = size
    _paint_dot(c, state)
    return c


def _paint_dot(c: tk.Canvas, state: str):
    size = c.size
    c.delete("all")
    if state == "hecho":
        c.create_oval(1, 1, size - 1, size - 1, fill=OK, outline=OK)
        c.create_text(size / 2, size / 2 + 1, text="✓", fill="#0A1E10", font=_font(8, True))
    elif state == "ahora":
        d, r = px(2), px(3)
        c.create_oval(d, d, size - d, size - d, outline=ACCENT, width=d)
        c.create_oval(size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r, fill=ACCENT, outline=ACCENT)
    elif state.isdigit():  # un paso numerado
        c.create_oval(1, 1, size - 1, size - 1, fill=ACCENT, outline=ACCENT)
        c.create_text(size / 2, size / 2, text=state, fill="#0B1220", font=_font(9, True))
    else:
        d = px(2)
        c.create_oval(d, d, size - d, size - d, outline="#464C56", width=d)


def _mmss(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


def _left_text(s: float) -> str:
    if s < 50:
        return "Ya casi está"
    m = int(round(s / 60))
    return f"Quedan unos {m} min" if m >= 2 else "Queda 1 min"


TIMES_FILE = "PuebloCTR-tiempos.json"  # junto al exe: cuanto tardo la ultima vez (el tiempo que queda)


class Eta:
    """El tiempo que queda (pedido de VENOMSHiNE: antes subia y subia y solo bajaba al final).
    Con la vez anterior guardada (TIMES_FILE: el avance segundo a segundo), lo que falta segun
    aquella, a la velocidad de esta; sin ella, el ritmo de los ultimos 90 s. Lo que se ve baja
    con el reloj y se corrige poco a poco (no salta)."""

    def __init__(self, path: Path):
        self.path = path
        self.prev = None
        try:
            import json
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("v") == 1 and len(d["curve"]) > 5 and d["total"] > 30:
                self.prev = d
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.t0 = time.monotonic()
        self.samples: list = []  # (t, frac)
        self.shown = None
        self.last = self.t0
        self.from_prev = False

    def _prev_t(self, frac: float) -> float:
        cur = self.prev["curve"]
        for (t0, f0), (t1, f1) in zip(cur, cur[1:]):
            if f1 >= frac:
                return t0 + (t1 - t0) * ((frac - f0) / (f1 - f0) if f1 > f0 else 0.0)
        return cur[-1][0]

    def update(self, frac: float) -> tuple[float | None, float]:
        now = time.monotonic()
        t = now - self.t0
        if not self.samples or frac > self.samples[-1][1] + 0.002 or now - self.last > 5:
            self.samples.append((t, frac))
        est = None
        if self.prev and frac > 0.01:
            tp = self._prev_t(frac)
            speed = t / tp if tp > 5 else 1.0  # esta vez va mas rapida o mas lenta que la otra
            speed = min(2.0, max(0.5, speed))
            est = max(0.0, (self.prev["total"] - tp) * speed)
            self.from_prev = True
        elif t > 15 and frac > 0.02:
            old = next(((ts, fs) for ts, fs in self.samples if ts >= t - 90), self.samples[0])
            if frac > old[1] and t > old[0]:
                est = (1.0 - frac) / ((frac - old[1]) / (t - old[0]))
        dt = now - self.last
        self.last = now
        if est is not None:
            if self.shown is None:
                self.shown = est
            else:
                self.shown = max(0.0, self.shown - dt)
                self.shown += (est - self.shown) * min(1.0, dt / 6.0)
        return self.shown, t

    def save(self):
        """Al terminar: el avance de esta vez para la proxima."""
        try:
            import json
            t = time.monotonic() - self.t0
            cur = [[round(a, 1), round(b, 4)] for a, b in self.samples] + [[round(t, 1), 1.0]]
            self.path.write_text(json.dumps({"v": 1, "total": round(t, 1), "curve": cur[::max(1, len(cur) // 400)]
                                             + [cur[-1]]}), encoding="utf-8")
        except OSError:
            pass


def _times_path() -> Path:
    """Donde se guarda cuanto tardo la ultima vez: en los datos de la herramienta (no en el Escritorio)."""
    return builder.data_dir() / TIMES_FILE


def _asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for p in (base / "pueblo3ds" / "assets" / name, Path(__file__).resolve().parent / "assets" / name, base / name):
        if p.is_file():
            return p
    return Path(name)


class Wizard(tk.Tk):
    def __init__(self, runtime: Path | None = None):
        super().__init__()
        i18n.init()  # el idioma de la última vez, o el del sistema
        self.runtime = runtime or builder.default_runtime()
        self.title(TITLE)
        self.configure(bg=BG)
        # el icono del juego (no la pluma de Tk), en la barra y en la de tareas
        try:
            if os.name == "nt" and _asset("icon.ico").is_file():
                self.iconbitmap(default=str(_asset("icon.ico")))
            self._icon = tk.PhotoImage(file=str(_asset("app_icon.png")))
            self.iconphoto(True, self._icon)
        except (tk.TclError, OSError):
            self._icon = None
        global S
        S = max(1.0, self.winfo_fpixels("1i") / 96.0)  # 96 ppp = 100 % en Windows
        self.win_w, self.win_h = px(WIN_W), px(WIN_H)
        self.geometry(f"{self.win_w}x{self.win_h}")
        self.resizable(False, False)
        self.placed = False

        self.disc1 = tk.StringVar()
        self.disc2 = tk.StringVar()
        sd = builder.sd_cards()
        self.sd = sd[0] if sd else None
        self.out = tk.StringVar(value=str(builder.default_output()))
        self.textures = tk.BooleanVar(value=True)
        self.movies = tk.BooleanVar(value=True)
        self.ffmpeg = tk.StringVar(value=builder.find_ffmpeg())
        self.ffmpeg.trace_add("write", lambda *a: self.after(400, self._ff_typed))
        self.ff_state = None  # None comprobando; 0, 1, 2 como builder.ffmpeg_state
        self.ff_checked = None
        self.ff_download = None  # texto del avance mientras se descarga
        self.saves: list[Path] = []
        self.events: queue.Queue = queue.Queue()
        self.report = None
        self.working = False

        self._style()
        # el pie primero (abajo): si algo no cabe, que no sea el boton de seguir
        self.footer = tk.Frame(self, bg=BG)
        self.footer.pack(side="bottom", fill="x", padx=px(28), pady=px(18))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(side="top", fill="both", expand=True, padx=px(28), pady=(px(22), 0))
        self.sign = tk.Label(self.footer, text=_("hecho por VENOMSHiNE"), bg=BG, fg=DIM, font=_font(9))
        self.sign.pack(side="left")
        self.next_btn = ttk.Button(self.footer, text=_("Continuar"), style="Accent.TButton")
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(self.footer, text=_("Atrás"), style="Plain.TButton", command=self._back)
        self.back_btn.pack(side="right", padx=(0, px(8)))
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.server = None
        self.pages = [self._page_welcome, self._page_discs, self._page_options, self._page_progress, self._page_done,
                      self._page_qr]
        self.page = 0
        # El alto: el de la pantalla de progreso (la mas alta de las fijas), medido antes de ensenarla
        self.withdraw()
        self.page = 3
        self._page_progress()
        self._fit()
        self._clear()
        self._show(0)
        self.deiconify()
        self._check_ffmpeg()

    # --- estilo --------------------------------------------------------------------------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Accent.TButton", background=ACCENT, foreground="#0B1220", font=_font(10, True),
                    borderwidth=0, padding=(px(18), px(8)), focusthickness=0, focuscolor=ACCENT)
        s.map("Accent.TButton", background=[("disabled", "#2A3A52"), ("active", "#6DB4FF")],
              foreground=[("disabled", "#56657A")])
        s.configure("Plain.TButton", background="#262B34", foreground=FG, font=_font(10), borderwidth=0,
                    padding=(px(14), px(8)), focusthickness=0, focuscolor=PANEL)
        s.map("Plain.TButton", background=[("active", "#323844"), ("disabled", BG)],
              foreground=[("disabled", "#3A3F48")])
        s.configure("TCheckbutton", background=BG, foreground=FG, font=_font(10), indicatorbackground=PANEL,
                    indicatorforeground=ACCENT, indicatorrelief="flat", indicatormargin=(0, 0, px(8), 0),
                    indicatordiameter=px(12), indicatorsize=px(12))
        s.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", PANEL)])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG,
                    bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL, padding=px(6))
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.font", _font(10))
        s.configure("Card.TCheckbutton", background=PANEL, foreground=FG, font=_font(10), indicatorbackground="#101318",
                    indicatorforeground=ACCENT, indicatorrelief="flat", indicatormargin=(0, 0, px(8), 0),
                    indicatordiameter=px(12), indicatorsize=px(12))
        s.map("Card.TCheckbutton", background=[("active", PANEL)], indicatorbackground=[("selected", "#101318")])
        s.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT, borderwidth=0,
                    thickness=px(10))

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, bg="#101318", fg=FG, insertbackground=FG, relief="flat",
                        font=_font(10), highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _title(self, text: str, sub: str = ""):
        tk.Label(self.body, text=text, bg=BG, fg=FG, font=_font(17, True), anchor="w", justify="left",
                 wraplength=px(CARD_W) - px(4)).pack(fill="x", pady=(0, 0 if sub else px(14)))
        if sub:
            tk.Label(self.body, text=sub, bg=BG, fg=DIM, font=_font(10), anchor="w", justify="left",
                     wraplength=px(CARD_W) - px(4)).pack(fill="x", pady=(px(4), px(14)))

    def _card(self, pady=(0, 12), outline=None) -> tk.Frame:
        c = Card(self.body, outline=outline)
        c.pack(anchor="w", pady=tuple(px(p) for p in pady))
        return c.inner

    @staticmethod
    def _inner_w() -> int:
        """Lo que cabe dentro de una tarjeta."""
        return px(CARD_W) - 2 * px(16)

    def _step_rows(self, parent, steps):
        for i, t in enumerate(steps, 1):
            row = tk.Frame(parent, bg=PANEL)
            row.pack(fill="x", pady=px(4))
            _dot(row, str(i), size=22).pack(side="left", anchor="n")
            tk.Label(row, text=t, bg=PANEL, fg=FG, font=_font(10), anchor="w", justify="left",
                     wraplength=self._inner_w() - px(22 + 12)).pack(side="left", padx=px(12))

    def _section(self, parent, text, wrap=None):
        tk.Label(parent, text=text, bg=PANEL, fg=DIM, font=_font(9, True), anchor="w", justify="left",
                 wraplength=wrap or self._inner_w() - px(4)).pack(fill="x", pady=(0, px(6)))

    def _text(self, text: str, color: str = FG, size: int = 10, pady=(0, 6)):
        lbl = tk.Label(self.body, text=text, bg=BG, fg=color, font=_font(size), anchor="w", justify="left",
                       wraplength=px(CARD_W) - px(4))
        lbl.pack(fill="x", pady=tuple(px(p) for p in pady))
        return lbl

    def _show(self, i: int):
        self.page = i
        self._clear()
        self.back_btn.configure(state="normal" if 0 < i < 3 else "disabled", command=self._back)
        self.pages[i]()
        self._fit()

    def _fit(self):
        """La ventana, del alto de lo que lleva (crece, no encoge: que no salte de una pantalla a
        otra) y sin salirse de la pantalla."""
        self.update_idletasks()
        need = max(self.win_h, self.winfo_reqheight())
        top = max(0, self.winfo_screenheight() - px(48))  # la barra de tareas
        h = min(need, top)
        if h != self.win_h or not self.placed:
            self.win_h = h
            if not self.placed:  # en el centro
                self.placed = True
                x = max(0, (self.winfo_screenwidth() - self.win_w) // 2)
                y = max(0, (top - h) // 2)
                self.geometry(f"{self.win_w}x{h}+{x}+{y}")
            else:
                y = self.winfo_y()
                if y + h > top:
                    y = max(0, top - h)
                self.geometry(f"{self.win_w}x{h}+{self.winfo_x()}+{y}")

    def _back(self):
        if 0 < self.page < 3:
            self._show(self.page - 1)

    def _close(self):
        from tkinter import messagebox
        if self.server is not None:
            sent, total, finished, _downloads = self.server.status()
            if 0 < sent < total and not finished:
                if not messagebox.askyesno(TITLE, "La consola está descargando el .cia. Si sales ahora, se corta.\n\n"
                                                "¿Salir de todos modos?"):
                    return
            self.server.stop()
        if self.working:
            if not messagebox.askyesno(TITLE, "Se está preparando el juego. Si sales ahora, se cancela (lo ya hecho "
                                            "se aprovecha la próxima vez).\n\n¿Salir de todos modos?"):
                return
            builder.cancel()
            os._exit(0)
        self.destroy()

    # --- pantallas -----------------------------------------------------------------------
    def _page_welcome(self):
        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x", pady=(0, px(14)))
        icon_w = 0
        if getattr(self, "_icon", None) is not None:
            k = max(1, int(round(256 / px(64))))  # 256 -> 64 a 100 %
            self._icon_small = self._icon.subsample(k)
            tk.Label(head, image=self._icon_small, bg=BG).pack(side="left", padx=(0, px(14)))
            icon_w = 256 // k + px(14)
        # el idioma, arriba a la derecha (solo aquí: cambia todo al momento)
        lang = tk.Frame(head, bg=BG)
        lang.pack(side="right", anchor="n")
        self.lang_var = tk.StringVar(value=i18n.LANGS[i18n.get_lang()])
        box = ttk.Combobox(lang, textvariable=self.lang_var, values=list(i18n.LANGS.values()), state="readonly",
                           width=9, font=_font(10))
        box.pack(anchor="e")
        box.bind("<<ComboboxSelected>>", lambda e: self._set_lang())
        lang_w = box.winfo_reqwidth() + px(12)
        txt = tk.Frame(head, bg=BG)
        txt.pack(side="left", fill="x")
        wrap = px(CARD_W) - icon_w - lang_w
        tk.Label(txt, text=TITLE, bg=BG, fg=FG, font=_font(19, True), anchor="w", justify="left",
                 wraplength=wrap).pack(fill="x")
        tk.Label(txt, text=_("{pueblo}  ·  asistente {version}\nel port de lonelyversemaker", pueblo=PUEBLO_VERSION,
                             version=__version__),
                 bg=BG, fg=DIM, font=_font(10), anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        card = self._card()
        tk.Label(card, text=_("Convierte tus discos de GameCube en un solo .cia con todo el juego dentro: se instala "
                              "y listo, sin copiar nada más a la SD. No instala nada en tu PC."),
                 bg=PANEL, fg=FG, font=_font(10), anchor="w", justify="left",
                 wraplength=self._inner_w() - px(4)).pack(fill="x", pady=(0, px(10)))
        self._step_rows(card, (_("Eliges las imágenes de tus dos discos (ISO, GCM o RVZ de Dolphin)."),
                               _("Eliges un par de opciones y dónde guardar el .cia."),
                               _("Se crea PuebloCTR.cia (unos 3,5 GB), listo para instalar con FBI "
                                 "(o por Wi-Fi con un QR).")))
        self._text(_("Necesitas tu propia copia del juego: edición europea (G4BP08) o americana (G4BE08). "
                     "Lo que sale de tus discos es solo para tu consola: no se comparte."), DIM, 9)
        self.next_btn.configure(text=_("Empezar"), state="normal", command=lambda: self._show(1))

    def _set_lang(self):
        """El idioma elegido en la bienvenida: se guarda y se redibuja todo al momento."""
        code = next((c for c, name in i18n.LANGS.items() if name == self.lang_var.get()), "es")
        if code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.sign.configure(text=_("hecho por VENOMSHiNE"))
        self.back_btn.configure(text=_("Atrás"))
        self._show(self.page)

    def _disc_row(self, parent, label: str, var: tk.StringVar, optional: bool):
        self._section(parent, label)
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        self._entry(row, var).pack(side="left", fill="x", expand=True, ipady=px(7))
        ttk.Button(row, text="Elegir…", style="Plain.TButton",
                   command=lambda: self._pick_disc(var, label)).pack(side="left", padx=(px(8), 0))
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=(px(8), px(4)))
        dot = _dot(line, "pendiente")
        dot.pack(side="left", anchor="n")
        status = tk.Label(line, text="", bg=PANEL, fg=DIM, font=_font(9), anchor="w", justify="left",
                          wraplength=self._inner_w() - px(18 + 10))
        status.pack(side="left", padx=px(10), fill="x")
        return dot, status

    def _page_discs(self):
        self._title("Tus discos", "Las imágenes de los dos discos de la misma edición. El orden da igual.")
        card = self._card()
        w1 = self._disc_row(card, "DISCO 1", self.disc1, False)
        tk.Frame(card, bg=PANEL, height=px(6)).pack(fill="x")
        w2 = self._disc_row(card, "DISCO 2  (opcional: sin él se juega hasta la isla)", self.disc2, True)
        pair = tk.Label(self.body, text="", bg=BG, fg=DIM, font=_font(10), anchor="w", justify="left",
                        wraplength=px(CARD_W) - px(4))
        pair.pack(fill="x", pady=(0, px(6)))
        self._text("¿Otro formato (CISO, GCZ, WIA)? En Dolphin: clic derecho en el juego → Convertir archivo → ISO "
                   "o RVZ.", DIM, 9)

        def refresh(*_args):
            if not pair.winfo_exists():
                return
            ds = []
            for var, (dot, status) in ((self.disc1, w1), (self.disc2, w2)):
                p = var.get().strip('" ')
                if not p:
                    status.configure(text="—", fg=DIM)
                    _paint_dot(dot, "pendiente")
                    ds.append(None)
                    continue
                d = dk.read_disc(Path(p)) if Path(p).is_file() else dk.Disc(Path(p), error="No existe ese archivo.")
                ok, text, lvl = dk.describe(d)
                status.configure(text=text, fg=LEVEL[lvl] if not ok or lvl != "ok" else FG)
                _paint_dot(dot, "hecho" if ok else "pendiente")
                ds.append(d)
            ok, text, lvl = dk.check_pair(*ds)
            pair.configure(text=text, fg=LEVEL[lvl])
            self.discs = [d.path for d in ds if d is not None]
            self.edition = next((d.edition for d in ds if d is not None and d.edition), "")
            self.next_btn.configure(state="normal" if ok else "disabled")
            self._fit()

        if not getattr(self, "_traced", False):
            for v in (self.disc1, self.disc2):
                v.trace_add("write", lambda *a: self._refresh_discs())
            self._traced = True
        self._refresh_discs = refresh
        refresh()
        self.next_btn.configure(text="Continuar", command=lambda: self._show(2))

    def _pick_disc(self, var: tk.StringVar, label: str):
        f = filedialog.askopenfilename(title=f"Imagen del {label.split('  ')[0].lower()}",
                                       filetypes=[("Imágenes de GameCube", "*.iso *.gcm *.rvz"), ("Todos", "*.*")])
        if f:
            var.set(str(Path(f)))

    # ffmpeg: se comprueba en un hilo (arrancarlo tarda un poco) cada vez que cambia la ruta
    def _check_ffmpeg(self):
        path = self.ffmpeg.get()
        if path == self.ff_checked:
            return
        self.ff_checked, self.ff_state = path, None

        def job():
            st = builder.ffmpeg_state(path)
            self.events.put(("ffmpeg", path, st))

        threading.Thread(target=job, daemon=True).start()
        self.after(100, self._poll)

    def _ff_typed(self):
        if self.ffmpeg.get() != self.ff_checked:
            self._check_ffmpeg()
            self._ff_refresh()

    def _ff_text(self) -> tuple[str, str]:
        if self.ff_download is not None:
            return self.ff_download, ACCENT
        if self.ff_state is None:
            return "Comprobando ffmpeg…", DIM
        if self.ff_state == 2:
            return "✓  ffmpeg funciona, con libx264", OK
        if self.ff_state == 1:
            return "Ese ffmpeg no trae libx264 (es demasiado mínimo): descarga el completo.", WARN
        size = "unos 100 MB" if os.name == "nt" else "unos 40 MB"
        return f"No se encuentra ffmpeg: descárgalo ({size}, una sola vez) o elígelo.", BAD

    def _page_options(self):
        self._title("Opciones", "Lo marcado es lo recomendado.")
        card = self._card(pady=(0, 10))
        self._section(card, "QUÉ LLEVA")
        ttk.Checkbutton(card, text="Pack de texturas (unos 350 MB; sin él, tirones al aparecer texturas nuevas)",
                        variable=self.textures, style="Card.TCheckbutton").pack(anchor="w", pady=px(2))
        ttk.Checkbutton(card, text="Vídeos del juego (unos 220 MB; los convierte ffmpeg)", variable=self.movies,
                        style="Card.TCheckbutton", command=lambda: self._ff_refresh()).pack(anchor="w", pady=px(2))
        ffrow = tk.Frame(card, bg=PANEL)
        ffrow.pack(fill="x", pady=(px(6), 0), padx=(px(20), 0))
        self.ff_entry = self._entry(ffrow, self.ffmpeg)
        self.ff_entry.pack(side="left", fill="x", expand=True, ipady=px(5))
        self.ff_pick = ttk.Button(ffrow, text="Elegir…", style="Plain.TButton", command=self._pick_ffmpeg)
        self.ff_pick.pack(side="left", padx=(px(8), 0))
        self.ff_dl = ttk.Button(ffrow, text="Descargar", style="Plain.TButton", command=self._download_ffmpeg)
        self.ff_dl.pack(side="left", padx=(px(8), 0))
        self.ff_lbl = tk.Label(card, text="", bg=PANEL, fg=DIM, font=_font(9), anchor="w", justify="left",
                               wraplength=self._inner_w() - px(24))
        self.ff_lbl.pack(fill="x", padx=(px(20), 0), pady=(px(4), 0))

        card2 = self._card(pady=(0, 10))
        self._section(card2, "PARTIDAS DE GAMECUBE  (opcional: .gci / .gcs de Dolphin o de una tarjeta)")
        srow = tk.Frame(card2, bg=PANEL)
        srow.pack(fill="x")
        self.saves_lbl = tk.Label(srow, text="", bg=PANEL, fg=FG, font=_font(9), anchor="w", justify="left",
                                  wraplength=self._inner_w() - px(240))
        self.saves_lbl.pack(side="left", fill="x", expand=True)
        ttk.Button(srow, text="Quitar", style="Plain.TButton", command=self._clear_saves).pack(side="right")
        ttk.Button(srow, text="Añadir…", style="Plain.TButton", command=self._add_saves).pack(side="right",
                                                                                          padx=(0, px(8)))
        self._saves_text()

        card3 = self._card(pady=(0, 0))
        self._section(card3, "GUARDAR EL .CIA EN  (unos 3,5 GB; mientras se crea, el doble libre en ese disco)")
        row = tk.Frame(card3, bg=PANEL)
        row.pack(fill="x")
        self._entry(row, self.out).pack(side="left", fill="x", expand=True, ipady=px(7))
        ttk.Button(row, text="Cambiar…", style="Plain.TButton", command=self._pick_out).pack(side="left",
                                                                                             padx=(px(8), 0))
        if self.sd is not None:
            sdrow = tk.Frame(card3, bg=PANEL)
            sdrow.pack(fill="x", pady=(px(8), 0))
            tk.Label(sdrow, text=f"Está conectada la SD de una 3DS ({self.sd}).", bg=PANEL, fg=DIM,
                     font=_font(9), anchor="w").pack(side="left")
            ttk.Button(sdrow, text="Guardarlo en la SD", style="Plain.TButton",
                       command=lambda: self.out.set(str(self.sd / "cia" / "PuebloCTR.cia"))).pack(side="right")
        self.next_btn.configure(text="Crear el .cia", command=self._start)
        self._ff_refresh()

    def _ff_refresh(self):
        if not hasattr(self, "ff_lbl") or not self.ff_lbl.winfo_exists():
            return
        on = self.movies.get()
        busy = self.ff_download is not None
        for w in (self.ff_pick, self.ff_dl):
            w.configure(state="normal" if on and not busy else "disabled")
        self.ff_entry.configure(state="normal" if on and not busy else "disabled")
        text, color = self._ff_text() if on else ("Sin vídeos: el juego va, pero sus vídeos no se ven.", DIM)
        self.ff_lbl.configure(text=text, fg=color)
        ready = not on or self.ff_state == 2
        self.next_btn.configure(state="normal" if ready and not busy else "disabled")
        self._fit()

    def _pick_ffmpeg(self):
        f = filedialog.askopenfilename(title="ffmpeg.exe", filetypes=[("ffmpeg", "ffmpeg.exe ffmpeg"),
                                                                      ("Todos", "*.*")])
        if f:
            self.ffmpeg.set(builder.ffmpeg_in(f))
            self._check_ffmpeg()
            self._ff_refresh()

    def _download_ffmpeg(self):
        self.ff_download = "Descargando ffmpeg…"
        self._ff_refresh()

        def job():
            def prog(done, total):
                t = f"Descargando ffmpeg: {done / 1048576:.0f}" + (f" de {total / 1048576:.0f} MB" if total else " MB")
                self.events.put(("ffdl", t))
            try:
                path = builder.download_ffmpeg(prog)
                self.events.put(("ffdl_done", path, ""))
            except Exception as exc:  # se ensena en la linea de ffmpeg
                self.events.put(("ffdl_done", "", str(exc)))

        threading.Thread(target=job, daemon=True).start()
        self.after(100, self._poll)

    def _saves_text(self):
        if not self.saves:
            self.saves_lbl.configure(text="Ninguna (la tarjeta de memoria del port se crea vacía).", fg=DIM)
        else:
            names = ", ".join(p.name for p in self.saves[:4]) + ("…" if len(self.saves) > 4 else "")
            self.saves_lbl.configure(text=f"{len(self.saves)}: {names}", fg=FG)
        self._fit()

    def _add_saves(self):
        fs = filedialog.askopenfilenames(title="Partidas de GameCube", filetypes=[("Partidas", "*.gci *.gcs"),
                                                                                 ("Todos", "*.*")])
        for f in fs:
            p = Path(f)
            if p not in self.saves:
                self.saves.append(p)
        self._saves_text()

    def _clear_saves(self):
        self.saves = []
        self._saves_text()

    def _pick_out(self):
        f = filedialog.asksaveasfilename(title="Guardar el .cia", defaultextension=".cia",
                                         initialfile=Path(self.out.get()).name, filetypes=[("CIA de 3DS", "*.cia")])
        if f:
            self.out.set(str(Path(f)))

    def _page_progress(self):
        self._title("Creando el .cia", "Convirtiendo tus discos. Puedes seguir usando el PC.")
        card = self._card(pady=(0, 12))
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x")
        self.pct = tk.Label(top, text="0 %", bg=PANEL, fg=FG, font=_font(28, True), anchor="w")
        self.pct.pack(side="left")
        r = tk.Frame(top, bg=PANEL)
        r.pack(side="right")
        self.left_lbl = tk.Label(r, text="Calculando…", bg=PANEL, fg=FG, font=_font(13, True), anchor="e")
        self.left_lbl.pack(anchor="e")
        self.time_lbl = tk.Label(r, text="Llevas 0:00", bg=PANEL, fg=DIM, font=_font(9), anchor="e")
        self.time_lbl.pack(anchor="e")
        self.bar = tk.Canvas(card, height=px(16), bg=PANEL, highlightthickness=0, bd=0)
        self.bar.pack(fill="x", pady=(px(12), px(10)))
        self.status = tk.Label(card, text="Preparando…", bg=PANEL, fg=FG, font=_font(10), anchor="w",
                               justify="left", wraplength=self._inner_w() - px(4))
        self.status.pack(fill="x")
        self.eta_src = tk.Label(card, text="", bg=PANEL, fg=DIM, font=_font(8), anchor="e")
        self.eta_src.pack(fill="x")
        # las fases
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=(0, px(12)))
        self.phase_w = {}
        names = [("discs", "Discos"), ("tex", "Texturas"), ("mov", "Vídeos"), ("cia", "El .cia")]
        gap = px(8)
        cw = (px(CARD_W) - 3 * gap) // 4
        for i, (key, name) in enumerate(names):
            c = Card(row, width=cw, pad=12)
            c.pack(side="left", padx=(0 if i == 0 else gap, 0), anchor="n")
            head = tk.Frame(c.inner, bg=PANEL)
            head.pack(fill="x")
            dot = _dot(head, "pendiente")
            dot.pack(side="left")
            lbl = tk.Label(head, text=name, bg=PANEL, fg=DIM, font=_font(9, True), anchor="w")
            lbl.pack(side="left", padx=px(6))
            sub = tk.Label(c.inner, text="—", bg=PANEL, fg=DIM, font=_font(8), anchor="nw", justify="left",
                           wraplength=cw - 2 * px(12), height=2)
            sub.pack(fill="x", pady=(px(6), 0))
            self.phase_w[key] = (c, dot, lbl, sub)
        tk.Label(self.body, text="Detalles", bg=BG, fg=DIM, font=_font(9, True), anchor="w").pack(fill="x")
        logc = self._card(pady=(4, 0))
        self.log = tk.Text(logc, height=6, bg=PANEL, fg=DIM, relief="flat", font=_font(9), highlightthickness=0,
                           wrap="word", bd=0)
        self.log.pack(fill="both", expand=True)
        self.log.configure(spacing1=2, spacing3=2)
        self.log.tag_configure("ok", foreground=OK)
        self.log.tag_configure("now", foreground=ACCENT)
        self.log.tag_configure("dim", foreground=DIM)
        self.log.tag_configure("cur", foreground=FG)
        self.log_lines = []  # [clave, texto, hecho]
        self.eta = Eta(_times_path())
        self.frac = 0.0
        self.next_btn.configure(text="Continuar", state="disabled")
        self._tick()

    def _draw_bar(self, frac):
        c = self.bar
        w = max(10, c.winfo_width())
        h = px(16)
        c.delete("all")
        _round_rect(c, 0, 1, w - 1, h - 1, h // 2 - 1, fill="#0E1014", outline="#0E1014")
        x = max(h - 2, int((w - 1) * frac))
        if frac > 0:
            _round_rect(c, 0, 1, x, h - 1, h // 2 - 1, fill=ACCENT, outline=ACCENT)
            _round_rect(c, 0, 1, x, h // 2 - 1, h // 2 - 2, fill="#6EB6FF", outline="#6EB6FF")

    def _log(self, key: str, text: str, done: bool = False):
        """Una linea por paso (no la misma repetida): la anterior del mismo paso se cambia."""
        for ln in self.log_lines:
            if ln[0] == key:
                ln[1], ln[2] = text, done or ln[2]
                break
        else:
            self.log_lines.append([key, text, done])
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        for k, t, d in self.log_lines:
            self.log.insert("end", "✓  " if d else "•  ", "ok" if d else "now")
            self.log.insert("end", t + "\n", "dim" if d else "cur")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_phase(self, key, state, sub):
        c, dot, lbl, subl = self.phase_w[key]
        if subl.cget("text") == (sub or "—") and lbl.cget("fg") == (DIM if state == "pendiente" else FG) \
                and c.outline == (ACCENT if state == "ahora" else None):
            return  # sin cambios: no repintar cada medio segundo
        _paint_dot(dot, state)
        lbl.configure(fg=DIM if state == "pendiente" else FG)
        subl.configure(text=sub or "—")
        c.set_outline(ACCENT if state == "ahora" else None)

    def _phases(self):
        st = builder.STATE
        if not st:
            return
        d = st.get("discs", "")
        self._set_phase("discs", "hecho" if st.get("discs_done") else ("ahora" if d else "pendiente"),
                        "listos" if st.get("discs_done") else d)
        for key, on, sub_done in (("tex", "tex_on", "hecho"), ("mov", "mov_on", "hechos")):
            if not st.get(on):
                self._set_phase(key, "pendiente", "no se incluye")
                continue
            now = st.get(key, "")
            done = st.get(key + "_done")
            self._set_phase(key, "hecho" if done else ("ahora" if now else "pendiente"), sub_done if done else now)
        cia = st.get("cia")
        self._set_phase("cia", "ahora" if cia else "pendiente",
                        ("montándolo" if cia == "makerom" else f"metiendo el juego: {cia}") if cia else "")
        # el registro: una linea por paso
        if d:
            self._log("discs", "Discos: " + ("archivos sacados" if st.get("discs_done") else d),
                      bool(st.get("discs_done")))
        if st.get("tex_on") and (st.get("tex") or st.get("tex_done")):
            self._log("tex", "Pack de texturas para la GPU de la 3DS" + ("" if st.get("tex_done")
                                                                         else f": {st.get('tex', '')}"),
                      bool(st.get("tex_done")))
        if st.get("mov_on") and (st.get("mov") or st.get("mov_done")):
            self._log("mov", "Vídeos (H.264 para la 3DS)" + ("" if st.get("mov_done") else f": {st.get('mov', '')}"),
                      bool(st.get("mov_done")))
        if st.get("cia"):
            self._log("cia", "El .cia, con todo el juego dentro")

    def _tick(self):
        """Cada medio segundo: el reloj, el tiempo que queda y las fases."""
        if self.page != 3:
            return
        left, t = self.eta.update(self.frac)
        self.time_lbl.configure(text=f"Llevas {_mmss(t)}" + (f"  ·  total ~{int(round((t + left) / 60))} min"
                                                            if left is not None and t + left > 90 else ""))
        self.left_lbl.configure(text=_left_text(left) if left is not None else "Calculando…")
        self.eta_src.configure(text="según tu última compilación" if self.eta.from_prev else "")
        self._draw_bar(self.frac)
        self._phases()
        self.after(500, self._tick)

    def _page_done(self):
        r = self.report
        if r is None or r.cia is None:
            self._title("No se pudo preparar", "")
            card = self._card()
            tk.Label(card, text=getattr(self, "error", "Error desconocido."), bg=PANEL, fg=BAD, font=_font(10),
                     anchor="w", justify="left", wraplength=self._inner_w() - px(4)).pack(fill="x")
            log = builder.data_dir() / "puebloprep.log"
            if log.is_file():
                self._text("El registro completo está en puebloprep.log (botón de abajo).", DIM, 9, pady=(6, 0))
                ttk.Button(self.body, text="Ver el registro", style="Plain.TButton",
                           command=lambda: self._open_folder(log)).pack(anchor="w", pady=(px(8), 0))
            self.next_btn.configure(text="Volver", state="normal", command=lambda: self._show(2))
            self.back_btn.configure(state="disabled")
            return
        size = r.cia.stat().st_size / 1048576
        on_sd = builder.is_sd_root(Path(r.cia.anchor)) if r.cia.anchor else False
        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x", pady=(0, px(14)))
        _dot(head, "hecho", bg=BG, size=34).pack(side="left", padx=(0, px(12)))
        txt = tk.Frame(head, bg=BG)
        txt.pack(side="left")
        tk.Label(txt, text="Listo", bg=BG, fg=FG, font=_font(19, True), anchor="w").pack(fill="x")
        what = [getattr(self, "edition", "") or r.edition, "texturas" if r.textures else "sin texturas",
                f"{r.movies} vídeos" if r.movies else "sin vídeos", f"{_mmss(r.seconds)} min"]
        tk.Label(txt, text="  ·  ".join(w for w in what if w), bg=BG, fg=DIM, font=_font(10), anchor="w").pack(fill="x")
        card = self._card()
        rows = (("Archivo", str(r.cia)), ("Tamaño", f"{size / 1024:.2f} GB" if size > 1024 else f"{size:.1f} MB"),
                ("md5", md5_file(r.cia)))
        for k, v in rows:
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x", pady=px(3))
            key = tk.Label(row, text=k, bg=PANEL, fg=DIM, font=_font(9), width=8, anchor="nw")
            key.pack(side="left", anchor="n")
            tk.Label(row, text=v, bg=PANEL, fg=FG, font=_font(9), anchor="w", justify="left",
                     wraplength=self._inner_w() - key.winfo_reqwidth() - px(4)).pack(side="left", fill="x")
        notes = [("Es un solo archivo con todo el juego dentro: no hay que copiar nada más a la SD. "
                  + ("Ya está en la SD: en la consola, FBI → SD → cia → PuebloCTR.cia → Install CIA. "
                     if on_sd else "Cópialo a la SD (por ejemplo a la carpeta cia) y en la consola: FBI → SD → cia → "
                                   "PuebloCTR.cia → Install CIA. ")
                  + "Hacen falta unos 3,5 GB libres en la SD para instalarlo; luego puedes borrar el .cia.", FG),
                 ("Por Wi-Fi (QR) no hay que copiar nada, pero tarda bastante más: son 3,5 GB.", DIM)]
        if r.saves:
            notes.append((f"Partidas dentro del .cia: {', '.join(r.saves)} (pasan a la SD al arrancar la primera vez, "
                          "si allí no hay ya una tarjeta de memoria).", DIM))
        if r.saves_failed:
            notes.append((f"No se pudieron importar: {', '.join(r.saves_failed)} (mira el registro).", WARN))
        for w in r.warnings[:3]:
            notes.append((f"Aviso: {w}", WARN))
        notes.append(("Lo de tus discos es solo para tu consola: no lo compartas.", DIM))
        for t, col in notes:
            self._text(t, col, 9)
        btns = tk.Frame(self.body, bg=BG)
        btns.pack(fill="x", pady=(px(8), 0))
        b = [ttk.Button(btns, text="Instalar por Wi-Fi (QR)", style="Accent.TButton", command=lambda: self._show(5)),
             ttk.Button(btns, text="Abrir la carpeta", style="Plain.TButton",
                        command=lambda: self._open_folder(r.cia.parent))]
        if r.log is not None and r.log.is_file():
            b.append(ttk.Button(btns, text="Ver el registro", style="Plain.TButton",
                                command=lambda: self._open_folder(r.log)))
        one_row = sum(x.winfo_reqwidth() for x in b) + px(8) * (len(b) - 1) <= px(CARD_W)
        for i, x in enumerate(b):
            if one_row or i == 0:
                x.grid(row=0, column=i, sticky="w", padx=(0 if i == 0 else px(8), 0))
            else:
                x.grid(row=1, column=i - 1, sticky="w", padx=(0 if i == 1 else px(8), 0), pady=(px(8), 0))
        self.next_btn.configure(text="Salir", state="normal", command=self.destroy)
        self.back_btn.configure(state="disabled")

    def _page_qr(self):
        self._title("Instalar por Wi-Fi", "")
        if self.server is None:
            try:
                self.server = CiaServer(self.report.cia).start()
            except OSError as exc:
                self._text(f"No se pudo abrir el servidor: {exc}", BAD)
                self.next_btn.configure(text="Volver", state="normal", command=lambda: self._show(4))
                return
        card = self._card()
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x")
        self.qr_canvas = tk.Canvas(row, bg="white", highlightthickness=0)
        self.qr_canvas.pack(side="left")
        info = tk.Frame(row, bg=PANEL)
        info.pack(side="left", fill="both", expand=True, padx=(px(22), 0))
        wrap = self._inner_w() - self._qr_side() - px(22)
        steps = ("En la consola, abre FBI.", "Remote Install → Scan QR Code.", "Apunta la cámara a este QR.",
                 "Acepta la instalación.")
        for i, t in enumerate(steps, 1):
            line = tk.Frame(info, bg=PANEL)
            line.pack(fill="x", pady=px(3))
            _dot(line, str(i), size=20).pack(side="left", anchor="n")
            tk.Label(line, text=t, bg=PANEL, fg=FG, font=_font(10), anchor="w", justify="left",
                     wraplength=wrap - px(20 + 8)).pack(side="left", padx=px(8))
        self.qr_url = tk.Label(info, text="", bg=PANEL, fg=DIM, font=_font(9), wraplength=wrap, justify="left",
                               anchor="w")
        self.qr_url.pack(fill="x", pady=(px(10), 0))
        if len(self.server.ips) > 1:
            ttk.Button(info, text="Probar otra IP", style="Plain.TButton",
                       command=self._qr_other_ip).pack(anchor="w", pady=(px(6), 0))
        self.qr_status = tk.Label(info, text="", bg=PANEL, fg=DIM, font=_font(10, True), anchor="w", justify="left",
                                  wraplength=wrap)
        self.qr_status.pack(fill="x", pady=(px(10), 0))
        self.qr_help = self._text("El PC y la consola tienen que estar en la misma Wi-Fi. Si Windows pregunta por "
                                  "el firewall, permite el acceso en redes privadas.", DIM, 9, pady=(14, 0))
        self.next_btn.configure(text="Salir", state="normal", command=self._close)
        self.back_btn.configure(state="normal", command=self._qr_back)
        self._qr_draw()
        self.qr_since = time.monotonic()
        if self.server.ip.startswith("127."):
            self.qr_status.configure(text="No se detecta la red local: conecta el PC a la Wi-Fi.", fg=BAD)
        self._qr_poll()

    def _qr_code(self):
        # Version minima 4: los QR muy pequenos cuestan a la camara de la consola.
        return QrCode.encode_segments(QrSegment.make_segments(self.server.url), QrCode.Ecc.MEDIUM, minversion=4)

    def _qr_side(self) -> int:
        """Lo que ocupa el QR: el de ahora (si se cambia de IP, la direccion puede alargarse un poco)."""
        return (self._qr_code().get_size() + 8) * max(4, px(6))

    def _qr_draw(self):
        qr = self._qr_code()
        n, cell, border = qr.get_size(), max(4, px(6)), 4
        side = (n + 2 * border) * cell
        c = self.qr_canvas
        c.delete("all")
        c.configure(width=side, height=side)
        for y in range(n):
            for x in range(n):
                if qr.get_module(x, y):
                    x0, y0 = (x + border) * cell, (y + border) * cell
                    c.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill="black", width=0)
        self.qr_url.configure(text=self.server.url)

    def _qr_other_ip(self):
        self.server.next_ip()
        self.qr_since = time.monotonic()
        self._qr_draw()

    def _qr_back(self):
        self.back_btn.configure(command=self._back)
        self._show(4)

    def _qr_poll(self):
        if self.page != 5 or self.server is None:
            return
        sent, total, finished, downloads = self.server.status()
        if finished:
            self.qr_status.configure(text="✓  Enviado. Termina la instalación en FBI.", fg=OK)
        elif downloads and sent:
            self.qr_status.configure(text=f"Enviando a la consola: {100 * sent / total:.0f} %  "
                                          f"({sent / 1048576:.1f} de {total / 1048576:.1f} MB)", fg=ACCENT)
        elif self.server.requests:
            self.qr_status.configure(text="La consola ha conectado. Esperando a que empiece la descarga…", fg=DIM)
        elif not self.server.ip.startswith("127."):
            waited = time.monotonic() - self.qr_since
            if waited < 20:
                self.qr_status.configure(text="Esperando a la consola…", fg=DIM)
            else:
                # Nada en 20 s: la consola no llega al PC (no es un problema del .cia).
                self.qr_status.configure(text="La consola no llega al PC.", fg=WARN)
                self.qr_help.configure(
                    text="1) Mira si hay un aviso del Firewall de Windows (puede estar detrás de esta ventana) "
                         "y permite el acceso en redes privadas.  2) Comprueba que la consola y el PC están en "
                         "la misma Wi-Fi.  3) Si el PC tiene VPN o varias redes, pulsa «Probar otra IP».  "
                         "Si nada funciona, copia el .cia a la SD e instálalo con FBI.", fg=WARN)
        self._fit()
        self.after(250, self._qr_poll)

    @staticmethod
    def _open_folder(path: Path):
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)], env=builder.child_env())

    # --- trabajo ---------------------------------------------------------------------------
    def _start(self):
        out = Path(self.out.get().strip('" '))
        self._show(3)
        self.working = True
        args = (list(self.discs), out, self.textures.get(), self.movies.get(), self.ffmpeg.get(), list(self.saves))
        threading.Thread(target=self._work, args=args, daemon=True).start()
        self.after(100, self._poll)

    def _work(self, discs, out, textures, movies, ffmpeg, saves):
        try:
            report = builder.build(discs, out, self.runtime, textures=textures, movies=movies, ffmpeg=ffmpeg,
                                   saves=saves, progress=lambda t, f: self.events.put(("progress", t, f)))
            self.events.put(("done", report))
        except Exception as exc:  # se muestra en la pantalla final
            self.events.put(("error", str(exc)))

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "progress":
                    _kind, text, frac = ev
                    self.frac = frac
                    self.pct.configure(text=f"{100 * self.frac:.0f} %")
                    self.status.configure(text=text[:80])
                elif ev[0] == "ffmpeg":
                    if ev[1] == self.ff_checked:
                        self.ff_state = ev[2]
                        self._ff_refresh()
                elif ev[0] == "ffdl":
                    self.ff_download = ev[1]
                    self._ff_refresh()
                elif ev[0] == "ffdl_done":
                    self.ff_download = None
                    if ev[1]:
                        self.ffmpeg.set(ev[1])
                        self._check_ffmpeg()
                    else:
                        self.ff_state = 0
                        self.ff_download = f"No se pudo descargar: {ev[2][:120]}"
                        self._ff_refresh()
                        self.ff_download = None
                        continue
                    self._ff_refresh()
                elif ev[0] == "done":
                    self.working = False
                    self.report = ev[1]
                    if getattr(self, "eta", None) is not None and self.report is not None and self.report.cia:
                        self.eta.save()  # para que la proxima vez el tiempo que queda sea el de verdad
                    self._show(4)
                    return
                elif ev[0] == "error":
                    self.working = False
                    self.report = None
                    self.error = ev[1]
                    self._show(4)
                    return
        except queue.Empty:
            pass
        if self.working or self.ff_state is None or self.ff_download is not None:
            self.after(100, self._poll)


def main() -> int:
    Wizard().mainloop()
    return 0
