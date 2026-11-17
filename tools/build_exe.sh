#!/bin/bash
# Compila PuebloCTR.exe (asistente de Windows) con PyInstaller dentro de Wine
# (imagen Docker tobix/pywine), sin necesitar Windows. Igual que tools/build_exe.sh de MostWanted3DS.
#
# Requisitos: Docker y tools/runtime/ hecho (tools/make_runtime.sh). Python con Pillow para el icono.
# Uso: tools/build_exe.sh
# Salida: out/PuebloCTR.exe
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

# makerom 0.19.0: la misma version con la que PuebloCTR monta su .cia
MAKEROM_ZIP_URL=https://github.com/3DSGuy/Project_CTR/releases/download/makerom-v0.19.0/makerom-v0.19.0-win_x86_64.zip
MAKEROM_ZIP_SHA256=88df4455e60556374e202d507f54ee03fac7493ec9554ab853157524b6d69db0
PYWINE=mirror.gcr.io/tobix/pywine:3.11
PYINSTALLER=pyinstaller==6.11.1

docker info >/dev/null 2>&1 || { echo "ERROR: Docker no responde" >&2; exit 1; }
for f in re4.elf icon.smdh banner.bnr PuebloCTR.rsf puebloprep-cli.exe; do
    [ -s "tools/runtime/$f" ] || { echo "falta tools/runtime/$f: ejecuta antes tools/make_runtime.sh" >&2; exit 1; }
done
rm -f out/PuebloCTR.exe

# 1. makerom.exe oficial (MIT), verificado.
mkdir -p tools/.cache
ZIP=tools/.cache/makerom-v0.19.0-win_x86_64.zip
[ -s "$ZIP" ] || curl -sSL --fail -o "$ZIP" "$MAKEROM_ZIP_URL"
echo "$MAKEROM_ZIP_SHA256  $ZIP" | sha256sum -c -

# 2. Carpeta de trabajo nueva en build/exe (build/ no va al repo).
STAGE=build/exe-$(date +%s)
mkdir -p "$STAGE/runtime/licencias"
cp tools/runtime/{re4.elf,icon.smdh,banner.bnr,PuebloCTR.rsf,puebloprep-cli.exe} "$STAGE/runtime/"
python3 -m zipfile -e "$ZIP" "$STAGE/runtime/"
[ -f "$STAGE/runtime/makerom.exe" ] || { echo "el zip no trae makerom.exe" >&2; exit 1; }
cp LICENSE "$STAGE/runtime/licencias/asistente-LICENSE.txt"; cp NOTICE.md "$STAGE/runtime/licencias/asistente-NOTICE.md"
cp tools/runtime/PuebloCTR-LICENSE.txt tools/runtime/PuebloCTR-THIRD-PARTY.md "$STAGE/runtime/licencias/" 2>/dev/null || true
curl -sSL --fail -o "$STAGE/runtime/licencias/makerom-LICENSE.txt" \
    https://raw.githubusercontent.com/3DSGuy/Project_CTR/makerom-v0.19.0/makerom/LICENSE
cp -r tools/pueblo3ds tools/PuebloCTR.pyw "$STAGE/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -r {} +
python3 -c "
from PIL import Image
im = Image.open('meta/icon_256.png').convert('RGBA')
im.save('$STAGE/icon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])"

# 3. PyInstaller en Wine. En la nube, pip necesita el proxy y su certificado.
EXTRA=()
if [ -n "${HTTPS_PROXY:-}" ]; then
    EXTRA+=(--network host -e "HTTPS_PROXY=$HTTPS_PROXY" -e "HTTP_PROXY=$HTTPS_PROXY")
    if [ -f /root/.ccr/ca-bundle.crt ]; then
        cp /root/.ccr/ca-bundle.crt "$STAGE/ca.crt"
        EXTRA+=(-e 'PIP_CERT=Z:\src\ca.crt')
    fi
fi
docker run --rm "${EXTRA[@]}" -e WINEDEBUG=-all -v "$ROOT/$STAGE:/src" -w /src "$PYWINE" sh -c "
    wine python -m pip install -q $PYINSTALLER >/dev/null 2>&1 &&
    wine python -m PyInstaller --noconfirm --clean --onefile --windowed --name PuebloCTR \
        --icon icon.ico --add-data 'icon.ico;.' --add-data 'runtime;runtime' \
        --add-data 'pueblo3ds/assets;pueblo3ds/assets' PuebloCTR.pyw >/dev/null 2>&1"
[ -s "$STAGE/dist/PuebloCTR.exe" ] || { echo "PyInstaller no genero el .exe" >&2; exit 1; }

mkdir -p out
cp "$STAGE/dist/PuebloCTR.exe" out/
md5sum out/PuebloCTR.exe
