# Nodo Raft en Python, sobre sockets TCP crudos e hilos (socket + threading de la
# stdlib, sin frameworks). Habla EXACTAMENTE el mismo protocolo de texto que el
# nodo Java, asi los nodos de los tres lenguajes forman un solo cluster.
#
# Protocolo (una linea por mensaje, campos separados por |):
#   REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
#   VOTE|term|otorgado(1/0)
#   APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
#   APPEND_OK|term|exito(1/0)|matchIndex
#   NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara
#   LEER_REGISTRO / REGISTRO|det1;det2;...
#   REDIRECT|host:puerto / OK
#
# "entradas" son  term,comando  separadas por ; (vacio en heartbeats).

import socket
import threading
import time
import random

SEP_ENTRADAS = ";"


class Entrada:
    __slots__ = ("term", "comando")

    def __init__(self, term, comando):
        self.term = term
        self.comando = comando

    def serializar(self):
        return f"{self.term},{self.comando}"

    @staticmethod
    def deserializar(s):
        coma = s.index(",")
        return Entrada(int(s[:coma]), s[coma + 1:])


class NodoRaft:
    def __init__(self, mi_id, puerto, pares):
        # pares: lista de (id, host, puerto) de los OTROS nodos
        self.id = mi_id
        self.puerto = puerto
        self.pares = pares

        # estado persistente
        self.current_term = 0
        self.voted_for = None
        self.log = []  # log[0] es indice 1

        # estado volatil
        self.estado = "SEGUIDOR"
        self.commit_index = 0
        self.last_applied = 0
        self.lider_actual = None

        # estado de lider
        self.next_index = {}
        self.match_index = {}

        # maquina de estado: el registro de detecciones aplicado
        self.registro = []

        # tiempo
        self.ultimo_contacto = 0
        self.timeout_eleccion = self._nuevo_timeout()
        self.HEARTBEAT = 0.05

        self.lock = threading.RLock()
        self.corriendo = True
        self.servidor = None

    def _nuevo_timeout(self):
        return random.uniform(0.150, 0.300)  # 150-300 ms, rango del profe

    def _ahora(self):
        return time.time()

    # ------------------------------------------------------------------
    def iniciar(self):
        self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servidor.bind(("0.0.0.0", self.puerto))
        self.servidor.listen(50)
        self.ultimo_contacto = self._ahora()
        self._log(f"nodo {self.id} escuchando en puerto {self.puerto} (seguidor)")

        threading.Thread(target=self._bucle_aceptar, daemon=True).start()
        threading.Thread(target=self._bucle_tiempo, daemon=True).start()

    def detener(self):
        self.corriendo = False
        try:
            self.servidor.close()
        except Exception:
            pass

    def _bucle_aceptar(self):
        while self.corriendo:
            try:
                cli, _ = self.servidor.accept()
                threading.Thread(target=self._atender, args=(cli,), daemon=True).start()
            except OSError:
                if self.corriendo:
                    continue
                break

    def _bucle_tiempo(self):
        while self.corriendo:
            time.sleep(0.015)
            if self.estado == "LIDER":
                self._enviar_heartbeats()
                time.sleep(self.HEARTBEAT)
            else:
                if self._ahora() - self.ultimo_contacto >= self.timeout_eleccion:
                    self._iniciar_eleccion()

    # ------------------------------------------------------------------
    # ELECCION
    # ------------------------------------------------------------------
    def _iniciar_eleccion(self):
        with self.lock:
            self.estado = "CANDIDATO"
            self.current_term += 1
            self.voted_for = self.id
            self.lider_actual = None
            self.timeout_eleccion = self._nuevo_timeout()
            self.ultimo_contacto = self._ahora()
            term_eleccion = self.current_term
            ult_idx = len(self.log)
            ult_term = self.log[-1].term if self.log else 0
        self._log(f"inicia eleccion en term {term_eleccion}")

        votos = [1]
        mayoria = (len(self.pares) + 1) // 2 + 1
        hilos = []

        for (pid, host, pto) in self.pares:
            t = threading.Thread(target=self._pedir_voto,
                                 args=(host, pto, term_eleccion, ult_idx, ult_term, votos, mayoria),
                                 daemon=True)
            t.start()
            hilos.append(t)
        for t in hilos:
            t.join(0.2)

    def _pedir_voto(self, host, pto, term_eleccion, ult_idx, ult_term, votos, mayoria):
        resp = self._enviar(host, pto, self._unir("REQUEST_VOTE", term_eleccion, self.id, ult_idx, ult_term))
        if not resp:
            return
        c = resp.split("|")
        if c[0] != "VOTE":
            return
        term_resp = int(c[1])
        otorgado = c[2] == "1"
        with self.lock:
            if term_resp > self.current_term:
                self._volver_seguidor(term_resp)
                return
            if self.estado != "CANDIDATO" or self.current_term != term_eleccion:
                return
            if otorgado:
                votos[0] += 1
                if votos[0] >= mayoria:
                    self._volver_lider()

    def _volver_lider(self):
        if self.estado == "LIDER":
            return
        self.estado = "LIDER"
        self.lider_actual = self.id
        sig = len(self.log) + 1
        for (pid, _, _) in self.pares:
            self.next_index[pid] = sig
            self.match_index[pid] = 0
        self._log(f"*** soy LIDER en term {self.current_term} ***")
        self._enviar_heartbeats()

    def _volver_seguidor(self, term):
        self.current_term = term
        self.estado = "SEGUIDOR"
        self.voted_for = None
        self.ultimo_contacto = self._ahora()

    # ------------------------------------------------------------------
    # REPLICACION
    # ------------------------------------------------------------------
    def _enviar_heartbeats(self):
        for (pid, host, pto) in self.pares:
            threading.Thread(target=self._replicar_a, args=(pid, host, pto), daemon=True).start()

    def _replicar_a(self, pid, host, pto):
        with self.lock:
            if self.estado != "LIDER":
                return
            term = self.current_term
            ni = self.next_index.get(pid, len(self.log) + 1)
            prev_idx = ni - 1
            prev_term = self.log[prev_idx - 1].term if 0 < prev_idx <= len(self.log) else 0
            a_enviar = self.log[ni - 1:]
            commit = self.commit_index

        ent = SEP_ENTRADAS.join(e.serializar() for e in a_enviar)
        resp = self._enviar(host, pto, self._unir("APPEND", term, self.id, prev_idx, prev_term, commit, ent))
        if not resp:
            return
        c = resp.split("|")
        if c[0] != "APPEND_OK":
            return
        term_resp = int(c[1])
        exito = c[2] == "1"
        match = int(c[3])

        with self.lock:
            if term_resp > self.current_term:
                self._volver_seguidor(term_resp)
                return
            if self.estado != "LIDER" or term != self.current_term:
                return
            if exito:
                self.match_index[pid] = match
                self.next_index[pid] = match + 1
                self._recalcular_commit()
            else:
                ni = self.next_index.get(pid, len(self.log) + 1)
                self.next_index[pid] = max(1, ni - 1)

    def _recalcular_commit(self):
        for n in range(len(self.log), self.commit_index, -1):
            if self.log[n - 1].term != self.current_term:
                continue
            cuenta = 1
            for (pid, _, _) in self.pares:
                if self.match_index.get(pid, 0) >= n:
                    cuenta += 1
            if cuenta >= (len(self.pares) + 1) // 2 + 1:
                self.commit_index = n
                self._aplicar()
                break

    def _aplicar(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            cmd = self.log[self.last_applied - 1].comando
            self.registro.append(cmd)
            self._log(f"aplica[{self.last_applied}]: {cmd}")

    # ------------------------------------------------------------------
    # ATENCION DE MENSAJES
    # ------------------------------------------------------------------
    def _atender(self, cli):
        try:
            f = cli.makefile("rwb")
            linea = f.readline().decode("utf-8").rstrip("\n")
            if not linea:
                return
            resp = self._procesar(linea)
            if resp is not None:
                f.write((resp + "\n").encode("utf-8"))
                f.flush()
        except Exception:
            pass
        finally:
            try:
                cli.close()
            except Exception:
                pass

    def _procesar(self, linea):
        c = linea.split("|")
        tipo = c[0]
        if tipo == "REQUEST_VOTE":
            return self._on_request_vote(c)
        if tipo == "APPEND":
            return self._on_append(c)
        if tipo == "NUEVA_DETECCION":
            return self._on_nueva_deteccion(c)
        if tipo == "LEER_REGISTRO":
            return self._on_leer_registro()
        return None

    def _on_request_vote(self, c):
        term = int(c[1]); cand = int(c[2]); cand_idx = int(c[3]); cand_term = int(c[4])
        with self.lock:
            if term > self.current_term:
                self._volver_seguidor(term)
            otorgar = False
            if term >= self.current_term and (self.voted_for is None or self.voted_for == cand):
                mi_idx = len(self.log)
                mi_term = self.log[-1].term if self.log else 0
                al_menos = cand_term > mi_term or (cand_term == mi_term and cand_idx >= mi_idx)
                if al_menos:
                    otorgar = True
                    self.voted_for = cand
                    self.ultimo_contacto = self._ahora()
            return self._unir("VOTE", self.current_term, 1 if otorgar else 0)

    def _on_append(self, c):
        term = int(c[1]); lider = int(c[2]); prev_idx = int(c[3])
        prev_term = int(c[4]); commit_lider = int(c[5]); entradas_str = c[6]
        with self.lock:
            if term < self.current_term:
                return self._unir("APPEND_OK", self.current_term, 0, 0)
            if term > self.current_term:
                self._volver_seguidor(term)
            self.estado = "SEGUIDOR"
            self.lider_actual = lider
            self.ultimo_contacto = self._ahora()

            if prev_idx > 0:
                if len(self.log) < prev_idx or self.log[prev_idx - 1].term != prev_term:
                    return self._unir("APPEND_OK", self.current_term, 0, 0)

            if entradas_str:
                items = entradas_str.split(SEP_ENTRADAS)
                idx = prev_idx
                for it in items:
                    idx += 1
                    e = Entrada.deserializar(it)
                    if len(self.log) >= idx:
                        if self.log[idx - 1].term != e.term:
                            del self.log[idx - 1:]
                            self.log.append(e)
                    else:
                        self.log.append(e)

            if commit_lider > self.commit_index:
                self.commit_index = min(commit_lider, len(self.log))
                self._aplicar()
            return self._unir("APPEND_OK", self.current_term, 1, len(self.log))

    def _on_nueva_deteccion(self, c):
        with self.lock:
            if self.estado != "LIDER":
                if self.lider_actual is not None:
                    d = self._dir_de(self.lider_actual)
                    if d:
                        return self._unir("REDIRECT", d)
                return self._unir("REDIRECT", "?")
            self.log.append(Entrada(self.current_term, c[1]))
            self._log(f"cliente inserta: {c[1]} (indice {len(self.log)})")
        self._enviar_heartbeats()
        return "OK"

    def _on_leer_registro(self):
        with self.lock:
            if self.estado != "LIDER":
                if self.lider_actual is not None:
                    d = self._dir_de(self.lider_actual)
                    if d:
                        return self._unir("REDIRECT", d)
                return self._unir("REDIRECT", "?")
            return self._unir("REGISTRO", SEP_ENTRADAS.join(self.registro))

    def _dir_de(self, idb):
        if idb == self.id:
            return f"127.0.0.1:{self.puerto}"
        for (pid, host, pto) in self.pares:
            if pid == idb:
                return f"{host}:{pto}"
        return None

    # ------------------------------------------------------------------
    def _enviar(self, host, pto, mensaje):
        try:
            s = socket.create_connection((host, pto), timeout=0.15)
            s.settimeout(0.25)
            f = s.makefile("rwb")
            f.write((mensaje + "\n").encode("utf-8"))
            f.flush()
            resp = f.readline().decode("utf-8").rstrip("\n")
            s.close()
            return resp if resp else None
        except Exception:
            return None

    def _unir(self, *campos):
        return "|".join(str(x) for x in campos)

    def _log(self, m):
        print(f"[py-nodo {self.id}] {m}", flush=True)
