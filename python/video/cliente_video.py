# Cliente del Servidor de Video: lo usa cada camara del Servidor de Testeo para
# pedir frames por socket TCP nativo. Devuelve la imagen (3,32,32) float32 y la
# etiqueta real (solo para medir el acierto; la CNN reconoce sola).

import socket
import numpy as np


class ClienteVideo:
    def __init__(self, host, puerto):
        self.host = host
        self.puerto = puerto
        self.sock = None
        self.f = None

    def conectar(self, timeout=5.0):
        self.sock = socket.create_connection((self.host, self.puerto),
                                             timeout=timeout)
        self.f = self.sock.makefile("rwb")

    def pedir_frame(self):
        # devuelve (img (3,32,32) float32, etiqueta str) o None si se corto
        self.f.write(b"PEDIR_FRAME\n")
        self.f.flush()
        cabecera = self.f.readline().decode("utf-8").strip()
        if not cabecera.startswith("FRAME|"):
            return None
        _, etiqueta, nbytes = cabecera.split("|")
        nbytes = int(nbytes)
        crudo = self._leer_exacto(nbytes)
        if crudo is None:
            return None
        img = np.frombuffer(crudo, dtype=np.float32).reshape(3, 32, 32)
        return img.copy(), etiqueta

    def _leer_exacto(self, n):
        # readinto en bucle: los sockets pueden entregar los bytes por partes
        buf = bytearray()
        while len(buf) < n:
            chunk = self.f.read(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def cerrar(self):
        try:
            if self.f:
                self.f.write(b"FIN\n")
                self.f.flush()
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
