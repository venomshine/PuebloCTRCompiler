# Cambios

## 0.1.0 — 17 de noviembre de 2026

Primera versión, para PuebloCTR v0.1.0-beta1 (el port de Resident Evil 4 de GameCube a la New 3DS).

- De las imágenes de tus dos discos (ISO, GCM o RVZ de Dolphin; ediciones G4BP08 y G4BE08) a **un solo `PuebloCTR.cia`
  con todo el juego dentro**. No hay que copiar la carpeta `3ds/pueblo` a la SD.
- Para Windows (`PuebloCTR.exe`) y Linux (`PuebloCTR-Linux.tar.gz`; probado en Debian 12 y Fedora 40). No instala nada.
- En español y en inglés, con un selector en la primera pantalla: la primera vez, el idioma del PC; luego, el elegido.
- Comprueba cada imagen antes de empezar: edición, número de disco, discos cambiados o mezclados y formatos que no sirven.
- Pack de texturas, vídeos (busca ffmpeg o lo descarga con un botón) y partidas `.gci` / `.gcs` dentro del `.cia`.
- Progreso con el tiempo que queda, md5 del `.cia` e instalación por Wi-Fi con un QR para FBI.
- En el menú HOME, el icono dice «PuebloCTR · Compiled by VENOMSHiNE» (el nombre y la descripción siguen siendo los de
  PuebloCTR).
- Motor de PuebloCTR con `patches/unico-cia.patch`: lee el juego del `.cia`; las partidas, los ajustes y los informes de
  errores siguen en la SD.
