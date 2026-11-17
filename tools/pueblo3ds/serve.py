"""Servidor HTTP minimo para instalar el .cia con FBI desde la red local.

FBI -> Remote Install -> Scan QR Code lee una URL y descarga el archivo. Este
servidor solo sirve ese archivo (nada mas del PC) y cuenta lo enviado para
mostrar el progreso en el asistente.
"""

from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

CHUNK = 256 * 1024


def _private(ip: str) -> bool:
    a, b = (int(x) for x in ip.split(".")[:2])
    return a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def local_ips() -> list[str]:
    """Todas las IP de red local de este PC, la de la ruta por defecto primero.
    Con una VPN o un adaptador virtual, la primera puede no ser la de la Wi-Fi."""
    ips = [local_ip()]
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and _private(ip):
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")] or ips


def local_ip() -> str:
    """IP de este PC en la red local (sin enviar nada: UDP no conecta de verdad)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class CiaServer:
    def __init__(self, cia: Path, port: int = 8080):
        self.cia = Path(cia)
        self.size = self.cia.stat().st_size
        self.name = self.cia.name
        self.sent = 0
        self.downloads = 0
        self.last_activity = 0.0
        self.requests = 0  # cualquier peticion: dice si la consola llega al PC
        self.finished = False
        self.lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # sin consola
                pass

            def _check(self) -> bool:
                with server.lock:
                    server.requests += 1
                if self.path.split("?", 1)[0] not in ("/" + quote(server.name), "/" + server.name):
                    self.send_error(404)
                    return False
                return True

            def do_HEAD(self):
                if self._check():
                    self._headers()

            def _headers(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(server.size))
                self.send_header("Content-Disposition", f'attachment; filename="{server.name}"')
                self.end_headers()

            def do_GET(self):
                if not self._check():
                    return
                self._headers()
                with server.lock:
                    server.downloads += 1
                    server.sent = 0
                    server.finished = False
                sent = 0
                with server.cia.open("rb") as f:
                    while True:
                        block = f.read(CHUNK)
                        if not block:
                            break
                        try:
                            self.wfile.write(block)
                        except (ConnectionError, OSError):
                            return  # la consola cancelo
                        sent += len(block)
                        with server.lock:
                            server.sent = sent
                            server.last_activity = time.monotonic()
                with server.lock:
                    server.finished = sent == server.size

        self.httpd = None
        last_error = None
        for p in range(port, port + 20):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", p), Handler)
                break
            except OSError as exc:
                last_error = exc
        if self.httpd is None:
            raise OSError(f"no hay ningun puerto libre a partir del {port}: {last_error}")
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.ips = local_ips()
        self.ip = self.ips[0]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}/{quote(self.name)}"

    def start(self) -> "CiaServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def next_ip(self) -> str:
        """Pasa a la siguiente IP de red local (para el boton "Probar otra IP")."""
        self.ip = self.ips[(self.ips.index(self.ip) + 1) % len(self.ips)]
        return self.ip

    def status(self) -> tuple[int, int, bool, int]:
        """(enviados, total, terminado, descargas iniciadas)."""
        with self.lock:
            return self.sent, self.size, self.finished, self.downloads
