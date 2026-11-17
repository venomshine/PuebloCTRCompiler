"""Lo mismo que el .exe, desde el codigo: python tools/run.py build DISCO1 DISCO2 -o CARPETA"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pueblo3ds.cli import main  # noqa: E402

raise SystemExit(main(sys.argv[1:]))
