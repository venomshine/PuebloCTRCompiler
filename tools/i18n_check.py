"""Comprueba las traducciones: python3 tools/i18n_check.py

Saca del código todas las claves de _("...") (también las que van en varias líneas) y avisa de las que no tienen
traducción al inglés en tools/pueblo3ds/i18n.py, y de las traducciones que ya no se usan. Sale con 1 si falta algo.
Las claves que se pasan como variable (las ediciones de los discos) van en INDIRECT.
"""

import ast
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pueblo3ds.discs import EDITIONS, OTHER_RE4  # noqa: E402
from pueblo3ds.i18n import EN  # noqa: E402

# _(variable): los textos que pueden llegar ahí
INDIRECT = set(EDITIONS.values()) | set(OTHER_RE4.values())


def keys_in_code() -> dict[str, str]:
    found = {}
    for f in sorted((HERE / "pueblo3ds").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, f"{f.name}:{node.lineno}")
    for k in INDIRECT:
        found.setdefault(k, "INDIRECT")
    return found


def fields(text: str) -> set:
    return {name for _lit, name, _spec, _conv in string.Formatter().parse(text) if name}


def main() -> int:
    code = keys_in_code()
    missing = [(k, where) for k, where in code.items() if k not in EN]
    unused = [k for k in EN if k not in code]
    bad = [k for k in code if k in EN and fields(k) != fields(EN[k])]
    for k, where in missing:
        print(f"SIN TRADUCIR ({where}): {k!r}")
    for k in unused:
        print(f"SIN USO: {k!r}")
    for k in bad:
        print(f"CAMPOS DISTINTOS: {k!r} -> {EN[k]!r}")
    print(f"{len(code)} claves, {len(missing)} sin traducir, {len(unused)} sin uso, {len(bad)} con campos distintos")
    return 1 if missing or bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
