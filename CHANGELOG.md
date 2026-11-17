# Cambios

## 0.1.0 (sin publicar)

Primera versión, para PuebloCTR v0.1.0-beta1.

- Asistente de Windows (`PuebloCTR.exe`, portátil): de las imágenes de tus dos discos de GameCube (ISO, GCM o RVZ de
  Dolphin; ediciones G4BP08 y G4BE08) a **un solo `PuebloCTR.cia` con todo el juego dentro**. No hay que copiar la carpeta
  `3ds/pueblo` a la SD.
- Reconoce cada imagen antes de empezar: edición, número de disco, formatos que no sirven, discos cambiados o mezclados.
- Pack de texturas, vídeos (busca ffmpeg o lo descarga con un botón) y partidas `.gci` / `.gcs` dentro del `.cia`.
- El `.cia` se escribe por partes: unos 3,5 GB en unos segundos y con unos 100 MB de RAM (makerom necesitaba 3,5 GB).
- Motor de PuebloCTR con `patches/unico-cia.patch`: lee los discos, las texturas y los vídeos del romfs del `.cia`; las
  partidas, los ajustes y los informes de errores siguen en la SD.
- Instalación por Wi-Fi con un QR para FBI, md5 del `.cia`, tiempo restante según tu última vez, y modo sin ventana.
