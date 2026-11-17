# Cambios

## 0.1.0 (sin publicar)

Primera versión, para PuebloCTR v0.1.0-beta1.

- Asistente para Windows (`PuebloCTR.exe`) y Linux (`PuebloCTR-Linux.tar.gz`), portátil: de las imágenes de tus dos discos de GameCube (ISO, GCM o RVZ de
  Dolphin; ediciones G4BP08 y G4BE08) a **un solo `PuebloCTR.cia` con todo el juego dentro**. No hay que copiar la carpeta
  `3ds/pueblo` a la SD.
- Linux: Ubuntu 22.04 o posterior, Debian 12, Mint 21, Fedora 36, Arch… (glibc 2.35 o posterior). Descarga el ffmpeg
  estático de johnvansickle.com si no hay uno con libx264, y los programas que lanza usan las bibliotecas del sistema.
- En español y en inglés, con un selector en la bienvenida: la primera vez, el idioma del PC; luego, el elegido.
- En el menú HOME, el icono dice «PuebloCTR · Compiled by VENOMSHiNE» (el nombre y la descripción siguen siendo
  los de PuebloCTR).
- Reconoce cada imagen antes de empezar: edición, número de disco, formatos que no sirven, discos cambiados o mezclados.
- Pack de texturas, vídeos (busca ffmpeg o lo descarga con un botón) y partidas `.gci` / `.gcs` dentro del `.cia`.
- El `.cia` se escribe por partes: unos 3,5 GB en unos segundos y con unos 100 MB de RAM (makerom necesitaba 3,5 GB).
- Motor de PuebloCTR con `patches/unico-cia.patch`: lee los discos, las texturas y los vídeos del romfs del `.cia`; las
  partidas, los ajustes y los informes de errores siguen en la SD.
- Instalación por Wi-Fi con un QR para FBI, md5 del `.cia`, tiempo restante según tu última vez, y modo sin ventana.
