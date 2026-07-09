# Servidor de Testeo (parte de Andrew, Python).
#
# Carga la CNN ya entrenada (sus pesos persistidos, SIN internet) y simula "c"
# camaras. Cada camara corre en su propio hilo: pide frames al SERVIDOR DE VIDEO
# por socket, la red los reconoce autonomamente, se guarda un PNG de la deteccion
# y se inserta un registro en el cluster Raft (via el lider). Cumple:
#   - la camara n-esima usa el modelo entrenado y reconoce sola
#   - guarda imagen (PNG) + registra tipo, fecha/hora y camara
#   - escalable a c camaras (un hilo por camara)
#   - los frames vienen del servidor de video (nodo aparte del enunciado)
#   - todo va al registro replicado por Raft
#
# Por defecto usa el modelo CIFAR-10 (objetos reales: avion, auto, gato, perro,
# etc.). Si no hay pesos CIFAR, cae al modelo de figuras geometricas (compat).

import sys
import os
import time
import threading
import numpy as np

sys.path.insert(0, ".")
from cnn.red import CNN
from raft.cliente import ClienteCluster, parsear_nodos
from video.cliente_video import ClienteVideo
from testeo.visor import guardar_png


class ServidorTesteo:
    def __init__(self, cluster, video_host, video_puerto,
                 carpeta_img="datos/detecciones"):
        self.cluster = cluster
        self.video_host = video_host
        self.video_puerto = video_puerto
        self.carpeta_img = carpeta_img
        os.makedirs(carpeta_img, exist_ok=True)
        self._contador = 0
        self._lock = threading.Lock()
        self._cargar_modelo()

    def _cargar_modelo(self):
        # prioriza el modelo CIFAR (objetos reales); si no, usa figuras.
        if os.path.exists("datos/pesos_cifar.npz"):
            self.clases = list(np.load("datos/clases_cifar.npy"))
            self.red = CNN(len(self.clases), canales=3, tam=32)
            self.red.cargar("datos/pesos_cifar.npz")
            self.modelo = "cifar"
            print("modelo: CIFAR-10 (%d clases reales)" % len(self.clases),
                  flush=True)
        else:
            from cnn.dataset import CLASES
            self.clases = list(CLASES)
            self.red = CNN(len(self.clases), canales=1, tam=28)
            self.red.cargar("datos/pesos_cnn.npz")
            self.modelo = "figuras"
            print("modelo: figuras geometricas (fallback)", flush=True)

    def _nombre_png(self, tipo, camara):
        with self._lock:
            self._contador += 1
            n = self._contador
        # ruta absoluta para que el Vigilante la encuentre corra desde donde corra
        return os.path.abspath(
            "%s/det_%04d_%s_%s.png" % (self.carpeta_img, n, tipo, camara))

    def _guardar_imagen(self, img, tipo, camara):
        # guarda un PNG real de la deteccion (lo muestra el Vigilante).
        ruta = self._nombre_png(tipo, camara)
        guardar_png(img, tipo, camara, ruta)
        # la ruta que va al registro es relativa a la raiz del repo, para que el
        # Vigilante (que corre desde la raiz) pueda abrir el PNG.
        return "python/" + ruta

    def _camara(self, id_camara, num_frames):
        # cada camara pide sus frames al servidor de video y va insertando.
        vid = ClienteVideo(self.video_host, self.video_puerto)
        try:
            vid.conectar()
        except Exception as e:
            print("[camara %d] no pude conectar al video: %s"
                  % (id_camara, e), flush=True)
            return
        insertadas = 0
        aciertos = 0
        procesadas = 0
        for _ in range(num_frames):
            r = vid.pedir_frame()
            if r is None:
                break
            img, etiqueta_real = r          # img (3,32,32) o (1,28,28)
            frame = img[np.newaxis, ...]    # (1,C,H,W)
            pred = int(self.red.predecir(frame)[0])
            tipo = self.clases[pred]
            procesadas += 1
            if tipo == etiqueta_real:
                aciertos += 1
            fecha_hora = time.strftime("%d/%m/%Y %H:%M:%S")
            img_ref = self._guardar_imagen(img, tipo, "Cam%d" % id_camara)
            ok = self.cluster.insertar(tipo, img_ref, fecha_hora,
                                       "Camara %d" % id_camara)
            if ok:
                insertadas += 1
            time.sleep(0.05)  # ritmo de camara
        vid.cerrar()
        acc = 100.0 * aciertos / procesadas if procesadas else 0.0
        print("[camara %d] %d/%d detecciones insertadas, "
              "reconocimiento correcto %.1f%%"
              % (id_camara, insertadas, procesadas, acc), flush=True)

    def correr(self, num_camaras=3, frames_por_camara=8):
        print("servidor de testeo: %d camaras, %d frames c/u (fuente: video)"
              % (num_camaras, frames_por_camara), flush=True)
        hilos = []
        for cam in range(1, num_camaras + 1):
            t = threading.Thread(target=self._camara,
                                 args=(cam, frames_por_camara), daemon=True)
            t.start()
            hilos.append(t)
        for t in hilos:
            t.join()
        print("servidor de testeo: terminado", flush=True)


def main():
    # uso: python3 testeo/servidor_testeo.py VIDEO_HOST:VIDEO_PUERTO nodo1 nodo2 ...
    if len(sys.argv) < 3:
        print("uso: python3 testeo/servidor_testeo.py video_host:puerto "
              "id:host:puerto ...")
        return
    vhost, vpuerto = sys.argv[1].split(":")
    nodos = parsear_nodos(sys.argv[2:])
    cluster = ClienteCluster(nodos)
    srv = ServidorTesteo(cluster, vhost, int(vpuerto))
    srv.correr(num_camaras=3, frames_por_camara=8)


if __name__ == "__main__":
    main()
