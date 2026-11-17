#!/bin/bash
# Prepara tools/runtime/: lo que el .exe lleva dentro para no compilar nada en el PC del usuario.
#   - re4.elf, icon.smdh, banner.bnr, PuebloCTR.rsf: el motor de PuebloCTR con patches/unico-cia.patch (lee el juego
#     del romfs del .cia), build de release en su imagen Docker
#   - puebloprep-cli.exe: PuebloPrep de consola para Windows (mingw-w64)
# Uso: tools/make_runtime.sh [carpeta_de_PuebloCTR]   (sin carpeta: lo clona en build/PuebloCTR, en PUEBLO_REF)
# Requisitos: Docker, cmake, ninja, g++-mingw-w64-x86-64-posix, python3.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PUEBLO_URL=https://github.com/lonelyversemaker/PuebloCTR.git
PUEBLO_REF=${PUEBLO_REF:-02306866b2ebe4ebdea22493d6ea56ecd4901a2c}  # v0.1.0-beta1
VERSION=$(python3 -c "import sys; sys.path.insert(0, 'tools'); from pueblo3ds import PUEBLO_VERSION; print(PUEBLO_VERSION)")

P=${1:-$ROOT/build/PuebloCTR}
if [ -z "${1:-}" ]; then
    [ -d "$P/.git" ] || git clone -q "$PUEBLO_URL" "$P"
    git -C "$P" fetch -q origin "$PUEBLO_REF" && git -C "$P" -c advice.detachedHead=false checkout -q "$PUEBLO_REF"
fi
P=$(cd "$P" && pwd)
bash "$P/tools/fetch_cubeevil4.sh"
# El motor que lee el juego de su propio romfs (todo en un .cia): patches/unico-cia.patch sobre overlay/ de PuebloCTR
if git -C "$P" apply --check "$ROOT/patches/unico-cia.patch" 2>/dev/null; then
    git -C "$P" apply "$ROOT/patches/unico-cia.patch"
elif ! git -C "$P" apply --reverse --check "$ROOT/patches/unico-cia.patch" 2>/dev/null; then
    echo "patches/unico-cia.patch no encaja en esta version de PuebloCTR ($PUEBLO_REF)" >&2; exit 1
fi

# 1. El motor, en la imagen de PuebloCTR. En la nube (proxy de salida) la imagen necesita el certificado del
#    proxy y apt por HTTPS: se usa una copia del Dockerfile con eso anadido (el original no se toca).
CTX=$P/docker; DF=$P/docker/Dockerfile; EXTRA=()
if [ -n "${HTTPS_PROXY:-}" ]; then
    CTX=$ROOT/build/docker; mkdir -p "$CTX"
    cp "${PROXY_CA:-/root/.ccr/ca-bundle.crt}" "$CTX/ca.crt"
    awk '{gsub("http://apt.llvm.org","https://apt.llvm.org"); print}
         /^FROM /{print "COPY ca.crt /usr/local/share/ca-certificates/proxy.crt";
                  print "RUN mkdir -p /etc/ssl/certs && cat /usr/local/share/ca-certificates/proxy.crt >> /etc/ssl/certs/ca-certificates.crt && sed -i s,http://,https://,g /etc/apt/sources.list.d/* /etc/apt/sources.list 2>/dev/null; true";
                  print "ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt"}' \
        "$P/docker/Dockerfile" > "$CTX/Dockerfile"
    DF=$CTX/Dockerfile
    EXTRA=(--network host --build-arg "HTTPS_PROXY=$HTTPS_PROXY" --build-arg "HTTP_PROXY=$HTTPS_PROXY"
           --build-arg "https_proxy=$HTTPS_PROXY" --build-arg "http_proxy=$HTTPS_PROXY")
fi
docker build "${EXTRA[@]}" -t puebloctr-build -f "$DF" "$CTX"
docker run --rm -v "$P":/work/repo -w /work/repo -e VERSION="$VERSION" puebloctr-build bash -c '
    set -e; git config --global --add safe.directory "*"
    bash tools/build.sh --release --version "$VERSION" --jobs "$(nproc)"
    bash tools/build_cia.sh "$VERSION"'
O=$P/build/tree/port/build/3ds-release
R=tools/runtime
mkdir -p "$R"
cp "$O/re4.elf" "$O/icon.smdh" "$O/banner.bnr" "$P/build/tree/port/whole/3ds/cia/PuebloCTR.rsf" "$R/"
# El icono del HOME Menu: el nombre y la descripción de PuebloCTR, y en el editor «PuebloCTR · Compiled by VENOMSHiNE»
# (su creador y quien compila; se ve arriba al pasar por el icono). Lo demás, igual que su tools/build_cia.sh.
docker run --rm -v "$P/build/tree/port/whole/3ds/cia":/cia:ro -v "$ROOT/$R":/o puebloctr-build \
    bannertool makesmdh -s "PuebloCTR" -l "Unofficial New 3DS port, $VERSION" -p "PuebloCTR · Compiled by VENOMSHiNE" \
    -i /cia/icon.png -o /o/icon.smdh >/dev/null

# 2. PuebloPrep de consola para Windows (y el de Linux, para las pruebas)
T=$ROOT/build/pp-tree
python3 "$P/tools/make_tree.py" "$P/external/CubeEvil4" "$P" "$T"
cmake -G Ninja -S "$T/port/puebloprep" -B build/pp-win -DCMAKE_BUILD_TYPE=Release -DPUEBLOPREP_VERSION="$VERSION" \
    -DCMAKE_TOOLCHAIN_FILE="$P/tools/mingw-w64-x86_64.cmake" >/dev/null
cmake --build build/pp-win --parallel
cp build/pp-win/puebloprep-cli.exe "$R/"
cmake -G Ninja -S "$T/port/puebloprep" -B build/pp-linux -DCMAKE_BUILD_TYPE=Release -DPUEBLOPREP_VERSION="$VERSION" >/dev/null
cmake --build build/pp-linux --parallel
cp build/pp-linux/puebloprep-cli "$R/"
docker run --rm -v "$ROOT/$R":/o puebloctr-build cp /usr/local/bin/makerom /o/makerom
cp "$P/LICENSE" "$R/PuebloCTR-LICENSE.txt"; cp "$P/THIRD-PARTY.md" "$R/PuebloCTR-THIRD-PARTY.md"
ls -la "$R"
