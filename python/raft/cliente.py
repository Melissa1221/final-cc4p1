# Cliente para hablar con el cluster Raft desde Python (lo usa el Servidor de
# Testeo para insertar detecciones). Maneja REDIRECT al lider igual que el cliente
# Java: recalcula el orden priorizando al lider conocido en cada intento.

import socket
import time


class ClienteCluster:
    def __init__(self, nodos):
        # nodos: lista de (id, host, puerto)
        self.nodos = nodos
        self.ultimo_lider = None  # (id, host, puerto)

    def insertar(self, tipo, imagen_ref, fecha_hora, camara):
        cmd = f"{tipo},{imagen_ref},{fecha_hora},{camara}"
        resp = self._pedir(f"NUEVA_DETECCION|{cmd}")
        return resp == "OK"

    def leer_registro(self):
        resp = self._pedir("LEER_REGISTRO")
        if not resp:
            return []
        c = resp.split("|")
        if c[0] != "REGISTRO" or not c[1]:
            return []
        return c[1].split(";")

    def _pedir(self, mensaje):
        for _ in range(len(self.nodos) * 2 + 4):
            orden = []
            if self.ultimo_lider:
                orden.append(self.ultimo_lider)
            for n in self.nodos:
                if not self.ultimo_lider or n[0] != self.ultimo_lider[0]:
                    orden.append(n)

            redirigido = False
            for (nid, host, pto) in orden:
                resp = self._enviar(host, pto, mensaje)
                if resp is None:
                    continue
                c = resp.split("|")
                if c[0] == "REDIRECT":
                    lider = self._por_dir(c[1])
                    if lider and (not self.ultimo_lider or lider[0] != self.ultimo_lider[0]):
                        self.ultimo_lider = lider
                        redirigido = True
                        break
                    continue
                self.ultimo_lider = (nid, host, pto)
                return resp
            if not redirigido:
                time.sleep(0.08)
        return None

    def _por_dir(self, d):
        for n in self.nodos:
            if f"{n[1]}:{n[2]}" == d:
                return n
        return None

    def _enviar(self, host, pto, mensaje):
        try:
            s = socket.create_connection((host, pto), timeout=0.15)
            s.settimeout(0.4)
            f = s.makefile("rwb")
            f.write((mensaje + "\n").encode("utf-8"))
            f.flush()
            resp = f.readline().decode("utf-8").rstrip("\n")
            s.close()
            return resp if resp else None
        except Exception:
            return None


def parsear_nodos(specs):
    out = []
    for spec in specs:
        pid, host, pto = spec.split(":")
        out.append((int(pid), host, int(pto)))
    return out
