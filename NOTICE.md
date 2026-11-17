# PuebloCTR Compiler — aviso de copyright y términos adicionales

Copyright (C) 2026 VENOMSHiNE — https://github.com/venomshine/PuebloCTRCompiler

PuebloCTR Compiler es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la
**GNU General Public License versión 3** (archivo [LICENSE](LICENSE)), publicada por la Free Software Foundation.

Se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA GARANTÍA**; ni siquiera la garantía implícita
de COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO PARTICULAR. Consulta la GNU General Public License para más detalles.

## Términos adicionales (sección 7 de la GPL-3.0)

Conforme a la sección 7 de la GNU GPL v3, se añaden estos términos a todo el código de PuebloCTR Compiler:

1. **Atribución obligatoria (sección 7b).** Toda obra que incluya o se base en código de PuebloCTR Compiler, total o
   parcialmente, debe mostrar de forma visible el aviso:

   > Basado en PuebloCTR Compiler de VENOMSHiNE — https://github.com/venomshine/PuebloCTRCompiler

   - en el README o la documentación principal del proyecto, y
   - en la propia aplicación, en una pantalla de créditos o «Acerca de» si la tiene.

   Este aviso no puede eliminarse ni ocultarse.

2. **Origen y versiones modificadas (sección 7c).** No se puede presentar el código como obra propia ni ocultar su origen.
   Las versiones modificadas deben indicar claramente que lo son y no pueden presentarse como la versión original de
   PuebloCTR Compiler.

3. **Nombres (sección 7e).** Esta licencia no concede derecho a usar los nombres «PuebloCTR Compiler» ni «VENOMSHiNE» para
   promocionar obras derivadas ni para dar a entender que el autor las respalda, más allá del aviso de atribución anterior.

## Código de terceros

Las siguientes partes conservan sus propias licencias:

- [PuebloCTR](https://github.com/lonelyversemaker/PuebloCTR) de lonelyversemaker — licencia MIT (con el alcance que indica
  su `LICENSE`). `patches/unico-cia.patch` modifica cuatro de sus archivos (`overlay/port/whole/3ds/`); esas partes siguen
  bajo su licencia MIT. Su `LICENSE` y su `THIRD-PARTY.md` van dentro de `PuebloCTR.exe`.
- El motor que lleva `PuebloCTR.exe` (`re4.elf`) es PuebloCTR compilado, sobre [CubeEvil4](https://github.com/Andiweli/CubeEvil4-Android)
  (su `LICENSE`: CC0 1.0 para sus scripts y herramientas). El código reconstruido del juego, del SDK y del middleware sigue
  siendo de Capcom, Nintendo y CRI Middleware, como en el `.cia` que publica PuebloCTR. **No se incluye ningún dato del
  juego:** se crean en el PC de cada uno a partir de sus propios discos.
- `puebloprep-cli.exe` (PuebloPrep de PuebloCTR, MIT), con el decodificador de zstd (BSD-3-Clause) y el lector de RVZ de CubeEvil4.
- `makerom.exe` — [makerom](https://github.com/3DSGuy/Project_CTR) 0.19.0 de Project_CTR, licencia MIT (su licencia va dentro del `.exe`).
- `tools/pueblo3ds/qrcodegen.py` — [QR Code generator](https://github.com/nayuki/QR-Code-generator) de Project Nayuki, licencia MIT.
- `meta/` — el icono, el banner y su sonido, y el `.rsf` de PuebloCTR (MIT; el texto de los dibujos usa Noto Serif JP, SIL OFL 1.1).
- [Python](https://www.python.org/) (licencia PSF) y [PyInstaller](https://pyinstaller.org/) (GPL-2.0 con excepción para
  programas empaquetados) para hacer el `.exe`.

PuebloCTR Compiler no está afiliado a Nintendo, Capcom ni CRI Middleware, ni lo respaldan.

---

## English summary

PuebloCTR Compiler is free software licensed under the **GNU GPL v3** (see [LICENSE](LICENSE)), with these additional terms
under section 7: (b) any work that uses or is based on its code must visibly show *"Based on PuebloCTR Compiler by VENOMSHiNE —
https://github.com/venomshine/PuebloCTRCompiler"* in its README/documentation and in the app's credits or About screen, if it
has one; (c) the origin must not be misrepresented, and modified versions must be clearly marked as such; (e) no rights are
granted to use the names "PuebloCTR Compiler" or "VENOMSHiNE" to promote derivative works. PuebloCTR (MIT), makerom (MIT)
and the other third-party parts keep their own licenses. No game data is included.
