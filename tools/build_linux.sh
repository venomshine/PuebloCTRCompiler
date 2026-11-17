#!/bin/bash
# Compila la versión de Linux: out/PuebloCTR-Linux.tar.gz (dentro, la carpeta PuebloCTR/ con el ejecutable PuebloCTR).
# Todo dentro de Ubuntu 22.04 (Docker): glibc 2.35, para que funcione en Ubuntu 22.04 o posterior, Debian 12 o posterior,
# Mint 21 o posterior, Fedora 36 o posterior, Arch... PuebloPrep y makerom se compilan ahí también (los de make_runtime.sh son del sistema de la nube).
#
# Requisitos: Docker y tools/runtime/ hecho con tools/make_runtime.sh (de ahí: re4.elf, icon.smdh, banner.bnr, el .rsf
# y build/pp-tree, el código de PuebloPrep).
# Uso: tools/build_linux.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
IMAGE=mirror.gcr.io/library/ubuntu:22.04
PYINSTALLER=pyinstaller==6.11.1
MAKEROM_REF=makerom-v0.19.0  # la misma versión que el .exe y que PuebloCTR

docker info >/dev/null 2>&1 || { echo "ERROR: Docker no responde" >&2; exit 1; }
for f in re4.elf icon.smdh banner.bnr PuebloCTR.rsf; do
    [ -s "tools/runtime/$f" ] || { echo "falta tools/runtime/$f: ejecuta antes tools/make_runtime.sh" >&2; exit 1; }
done
[ -f build/pp-tree/port/puebloprep/CMakeLists.txt ] || { echo "falta build/pp-tree: ejecuta antes tools/make_runtime.sh" >&2; exit 1; }
rm -f out/PuebloCTR-Linux.tar.gz

STAGE=build/linux-$(date +%s)
mkdir -p "$STAGE/runtime/licencias"
cp tools/runtime/{re4.elf,icon.smdh,banner.bnr,PuebloCTR.rsf} "$STAGE/runtime/"
cp LICENSE "$STAGE/runtime/licencias/asistente-LICENSE.txt"; cp NOTICE.md "$STAGE/runtime/licencias/asistente-NOTICE.md"
cp tools/runtime/PuebloCTR-LICENSE.txt tools/runtime/PuebloCTR-THIRD-PARTY.md "$STAGE/runtime/licencias/" 2>/dev/null || true
curl -sSL --fail -o "$STAGE/runtime/licencias/makerom-LICENSE.txt" \
    "https://raw.githubusercontent.com/3DSGuy/Project_CTR/$MAKEROM_REF/makerom/LICENSE"
cp -r tools/pueblo3ds tools/PuebloCTR.pyw "$STAGE/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -r {} +

# En la nube: el proxy y su certificado (apt por HTTPS, pip y git)
EXTRA=()
if [ -n "${HTTPS_PROXY:-}" ]; then
    cp "${PROXY_CA:-/root/.ccr/ca-bundle.crt}" "$STAGE/ca.crt"
    EXTRA+=(--network host -e "HTTPS_PROXY=$HTTPS_PROXY" -e "HTTP_PROXY=$HTTPS_PROXY" -e "https_proxy=$HTTPS_PROXY"
            -e "http_proxy=$HTTPS_PROXY" -e PROXY_CA=/src/ca.crt)
fi
docker run --rm "${EXTRA[@]}" -v "$ROOT/$STAGE:/src" -v "$ROOT/build/pp-tree:/pp:ro" -w /src "$IMAGE" bash -c "
set -euo pipefail
if [ -n \"\${PROXY_CA:-}\" ]; then
    echo 'Acquire::https::CaInfo \"/src/ca.crt\";' > /etc/apt/apt.conf.d/99proxy-ca
    sed -i 's,http://,https://,g' /etc/apt/sources.list
    export PIP_CERT=/src/ca.crt GIT_SSL_CAINFO=/src/ca.crt SSL_CERT_FILE=/src/ca.crt
fi
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends python3 python3-tk python3-venv \
    python3-dev binutils g++ make git ninja-build ca-certificates >/dev/null
python3 -m venv /venv
/venv/bin/pip install -q $PYINSTALLER cmake==3.31.6
# PuebloPrep de consola (el mismo código que el .exe: build/pp-tree)
/venv/bin/cmake -G Ninja -S /pp/port/puebloprep -B /tmp/pp -DCMAKE_BUILD_TYPE=Release \
    -DPUEBLOPREP_VERSION=\$(python3 -c 'import sys; sys.path.insert(0, \"/src\"); from pueblo3ds import PUEBLO_VERSION; print(PUEBLO_VERSION)') >/dev/null
/venv/bin/cmake --build /tmp/pp --parallel >/dev/null
strip /tmp/pp/puebloprep-cli && cp /tmp/pp/puebloprep-cli runtime/
# makerom
git -c advice.detachedHead=false clone -q --depth 1 --branch $MAKEROM_REF https://github.com/3DSGuy/Project_CTR.git /tmp/ctr
make -C /tmp/ctr/makerom deps -j\$(nproc) >/dev/null 2>&1 && make -C /tmp/ctr/makerom -j\$(nproc) >/dev/null 2>&1
strip /tmp/ctr/makerom/bin/makerom && cp /tmp/ctr/makerom/bin/makerom runtime/
chmod 755 runtime/puebloprep-cli runtime/makerom
# el ejecutable
/venv/bin/python -m PyInstaller --noconfirm --clean --onefile --windowed --name PuebloCTR \
    --add-data 'runtime:runtime' --add-data 'pueblo3ds/assets:pueblo3ds/assets' --hidden-import tkinter \
    PuebloCTR.pyw >/dev/null 2>&1
chown -R $(id -u):$(id -g) /src
"
[ -s "$STAGE/dist/PuebloCTR" ] || { echo "PyInstaller no genero el ejecutable" >&2; exit 1; }

mkdir -p out "$STAGE/pack/PuebloCTR"
cp "$STAGE/dist/PuebloCTR" "$STAGE/pack/PuebloCTR/"
chmod 755 "$STAGE/pack/PuebloCTR/PuebloCTR"
tar -C "$STAGE/pack" --owner=0 --group=0 -czf out/PuebloCTR-Linux.tar.gz PuebloCTR
md5sum "$STAGE/pack/PuebloCTR/PuebloCTR" out/PuebloCTR-Linux.tar.gz
