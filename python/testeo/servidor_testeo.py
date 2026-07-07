# Servidor de Testeo (parte de Andrew, Python).
#
# Carga la CNN ya entrenada (sus pesos persistidos) y simula "c" camaras. Cada
# camara corre en su propio hilo: toma frames (imagenes con figuras), la red las
# reconoce autonomamente, se guarda una imagen de la deteccion, y se inserta un
# registro en el cluster Raft (via el lider). Cumple:
#   - la camara n-esima usa el modelo entrenado y reconoce sola
#   - guarda imagen + registra tipo, fecha/hora y camara
#   - escalable a c camaras (un hilo por camara)
#   - todo va al registro replicado por Raft
#
# Aqui los "frames" se generan con el mismo dataset (figuras), asi el testeo es
# reproducible sin camaras fisicas. En la demo real se reemplaza la fuente de
# frames por la camara IP; el resto (inferencia + insercion) no cambia.

import sys
import os
import time
import threading
import numpy as np

sys.path.insert(0, ".")
from cnn.dataset import generar, CLASES
from cnn.red import CNN
from raft.cliente import ClienteCluster, parsear_nodos


class ServidorTesteo:
    def __init__(self, ruta_pesos, cluster, carpeta_img="datos/detecciones"):
        self.red = CNN(len(CLASES))
        self.red.cargar(ruta_pesos)
        self.cluster = cluster
        self.carpeta_img = carpeta_img
        os.makedirs(carpeta_img, exist_ok=True)
        self._contador = 0
        self._lock = threading.Lock()

    def _guardar_imagen(self, img, tipo, camara):
        # guarda el frame como texto ASCII simple (sin librerias de imagen). En la
        # demo real seria un .png; aqui basta para demostrar "guarda una imagen".
        with self._lock:
            self._contador += 1
            nombre = f"{self.carpeta_img}/det_{self._contador:04d}_{tipo}_{camara}.txt"
        with open(nombre, "w") as f:
            for fila in img[0]:
                f.write("".join("#" if v > 0.4 else "." for v in fila) + "\n")
        return os.path.basename(nombre)

    def _camara(self, id_camara, frames_por_clase, semilla):
        # cada camara procesa sus frames y va insertando detecciones.
        # generar(k) produce k imagenes POR CLASE, asi que son k*5 frames.
        X, y = generar(frames_por_clase, semilla=semilla)  # frames variados
        insertadas = 0
        aciertos = 0
        for i in range(len(X)):
            frame = X[i:i + 1]                    # (1,1,28,28)
            pred = int(self.red.predecir(frame)[0])
            tipo = CLASES[pred]
            if pred == y[i]:
                aciertos += 1
            fecha_hora = time.strftime("%d/%m/%Y %H:%M:%S")
            img_ref = self._guardar_imagen(frame[0], tipo, f"Cam{id_camara}")
            ok = self.cluster.insertar(tipo, img_ref, fecha_hora, f"Camara {id_camara}")
            if ok:
                insertadas += 1
            time.sleep(0.05)  # ritmo de camara
        acc = 100.0 * aciertos / len(X)
        print(f"[camara {id_camara}] {insertadas}/{len(X)} detecciones insertadas, "
              f"reconocimiento correcto {acc:.1f}%", flush=True)

    def correr(self, num_camaras=3, frames_por_camara=5):
        print(f"servidor de testeo: {num_camaras} camaras, "
              f"{frames_por_camara} frames c/u", flush=True)
        hilos = []
        for cam in range(1, num_camaras + 1):
            t = threading.Thread(target=self._camara,
                                 args=(cam, frames_por_camara, cam * 10), daemon=True)
            t.start()
            hilos.append(t)
        for t in hilos:
            t.join()
        print("servidor de testeo: terminado", flush=True)


def main():
    if len(sys.argv) < 2:
        print("uso: python3 testeo/servidor_testeo.py id:host:puerto ...")
        return
    nodos = parsear_nodos(sys.argv[1:])
    cluster = ClienteCluster(nodos)
    srv = ServidorTesteo("datos/pesos_cnn.npz", cluster)
    srv.correr(num_camaras=3, frames_por_camara=5)


if __name__ == "__main__":
    main()
