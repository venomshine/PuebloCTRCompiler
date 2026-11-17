"""Punto de entrada de PuebloCTR.exe (Windows) y PuebloCTR (Linux).

Sin argumentos abre el asistente. Con argumentos funciona como la linea de ordenes
(por ejemplo "PuebloCTR.exe build disco1.rvz disco2.rvz -o E:\\") y, como el .exe
no tiene consola, la salida va a PuebloCTR.log junto al programa.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if len(sys.argv) > 1:
        from pueblo3ds.cli import main as cli_main

        if getattr(sys, "frozen", False):
            # El programa no tiene consola (y en Wine la salida no llega a ningun sitio).
            log = open(Path(sys.executable).parent / "PuebloCTR.log", "w", encoding="utf-8")
            sys.stdout = sys.stderr = log
        raise SystemExit(cli_main(sys.argv[1:]))

    from pueblo3ds.gui import main

    raise SystemExit(main())
