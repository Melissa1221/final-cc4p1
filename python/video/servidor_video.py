# Servidor de Video (parte del enunciado: "iniciar los nodos servidor de video,
# servidor de testeo y servidor de entrenamiento").
#
# Emite frames a las camaras por un socket TCP nativo (sin frameworks). Cada
# camara del Servidor de Testeo se conecta aca y pide frames; el servidor
# responde con una imagen del dataset (aca CIFAR-10, objetos reales). En
# produccion esto se reemplaza por camaras IP reales que empujan sus frames; el
# resto del sistema (inferencia CNN + insercion al cluster Raft) no cambia.
#
# Concurrencia: un hilo por camara conectada (varias camaras piden frames a la
# vez). El acceso al indice de reparto de frames va con un lock.
#
# Protocolo del canal de video (texto + binario, una peticion por linea):
#   camara -> servidor:  PEDIR_FRAME\n
#   servidor -> camara:  FRAME|<etiqueta>|<nbytes>\n  seguido de <nbytes> crudos
#                        (la imagen es float32, shape (3,32,32), en orden C)
#   camara -> servidor:  FIN\n   (cierra)
# La etiqueta real se manda solo para que el testeo pueda medir su acierto; la
# CNN NO la usa para reconocer, reconoce sola desde los pixeles.

import os
import socket
import sys
import threading
import numpy as np

sys.path.insert(0, ".")


class ServidorVideo:
    def __init__(self, host, puerto, max_por_clase=200):
        self.host = host
        self.puerto = puerto
        # banco de frames. Prioriza CIFAR (objetos reales); si no esta descargado,
        # cae a las figuras geometricas para que el pipeline sea probable sin
        # internet. La CNN del testeo carga el modelo que corresponda.
        if os.path.isdir("datos/cifar-10-batches-py"):
            from cnn.cifar import cargar
            # sirve solo las clases con las que se entreno el modelo (si existe
            # clases_cifar.npy), para que el reconocimiento en vivo sea coherente.
            clases = None
            if os.path.exists("datos/clases_cifar.npy"):
                import numpy as _np
                clases = [str(c) for c in _np.load("datos/clases_cifar.npy")]
            _, _, Xte, yte, self.nombres = cargar(clases=clases,
                                                  max_por_clase=max_por_clase)
            self.frames = Xte           # (N, 3, 32, 32) float32
            self.etiquetas = yte
            self.fuente = "cifar"
        else:
            from cnn.dataset import generar, CLASES
            X, y = generar(max(1, max_por_clase // 5))   # generar da k por clase
            self.frames = X             # (N, 1, 28, 28) float32
            self.etiquetas = y
            self.nombres = list(CLASES)
            self.fuente = "figuras"
        self._idx = 0
        self._lock = threading.Lock()
        self._servidor = None

    def _siguiente_frame(self):
        # reparte frames en round-robin entre todas las camaras
        with self._lock:
            i = self._idx % len(self.frames)
            self._idx += 1
        return self.frames[i], int(self.etiquetas[i])

    def _atender(self, conn, addr):
        try:
            f = conn.makefile("rwb")
            while True:
                linea = f.readline()
                if not linea:
                    break
                msg = linea.decode("utf-8").strip()
                if msg == "PEDIR_FRAME":
                    img, etq = self._siguiente_frame()
                    crudo = np.ascontiguousarray(img, dtype=np.float32).tobytes()
                    # la cabecera lleva la forma para que el cliente reconstruya
                    # el frame sin saber de antemano si es RGB 32 o gris 28.
                    forma = "x".join(str(d) for d in img.shape)
                    cabecera = "FRAME|%s|%s|%d\n" % (
                        self.nombres[etq], forma, len(crudo))
                    f.write(cabecera.encode("utf-8"))
                    f.write(crudo)
                    f.flush()
                elif msg == "FIN" or msg == "":
                    break
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def correr(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.puerto))
        s.listen(16)
        self._servidor = s
        print("servidor de video escuchando en %s:%d (%d frames en banco)"
              % (self.host, self.puerto, len(self.frames)), flush=True)
        try:
            while True:
                conn, addr = s.accept()
                # un hilo por camara conectada
                t = threading.Thread(target=self._atender, args=(conn, addr),
                                     daemon=True)
                t.start()
        except OSError:
            pass  # socket cerrado, salimos

    def cerrar(self):
        if self._servidor:
            try:
                self._servidor.close()
            except Exception:
                pass


def main():
    host = "127.0.0.1"
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 9500
    max_pc = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    srv = ServidorVideo(host, puerto, max_por_clase=max_pc)
    srv.correr()


if __name__ == "__main__":
    main()
