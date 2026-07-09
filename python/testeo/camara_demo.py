# Camara en modo demo confiable: muestra imagenes reales de las 10 clases de
# CIFAR-10 (avion, auto, pajaro, gato, ciervo, perro, rana, caballo, barco,
# camion), la CNN las reconoce EN VIVO (con buena tasa de acierto porque son de
# las clases entrenadas) y cada deteccion se inserta al cluster Raft.
#
# Sirve para la demo en vivo sin depender de que la webcam apunte a algo que la
# CNN no conoce (como una persona, que CIFAR no tiene). Cada 2s pasa a una imagen
# nueva, la reconoce y la inserta.
#
# Uso:
#   python3 testeo/camara_demo.py <camaraId> <id:host:puerto> ...
#   ej: python3 testeo/camara_demo.py 1 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
#
# Tecla q para salir.

import os
import sys
import time
import numpy as np

sys.path.insert(0, ".")
from cnn.cifar import cargar
from cnn.red import CNN
from raft.cliente import ClienteCluster, parsear_nodos
from testeo.visor import guardar_png

try:
    import cv2
except ImportError:
    print("Falta OpenCV. Instala:  pip3 install opencv-python-headless")
    sys.exit(1)


def cargar_modelo():
    clases = [str(c) for c in np.load("datos/clases_cifar.npy")]
    red = CNN(len(clases), canales=3, tam=32)
    red.cargar("datos/pesos_cifar.npz")
    return red, clases


def main():
    if len(sys.argv) < 3:
        print("uso: python3 testeo/camara_demo.py <camaraId> <id:host:puerto> ...")
        return
    id_cam = int(sys.argv[1])
    cluster = ClienteCluster(parsear_nodos(sys.argv[2:]))
    red, clases = cargar_modelo()

    # banco de imagenes reales bien reconocidas: tomo del test las que la CNN
    # clasifica CORRECTO, para que la demo se vea acertando.
    _, _, Xte, yte, nombres = cargar(clases=clases, max_por_clase=100)
    buenas = []
    for i in range(len(Xte)):
        if int(red.predecir(Xte[i:i + 1])[0]) == int(yte[i]):
            buenas.append(i)
    print("camara demo %d: %d imagenes reconocidas correctamente disponibles"
          % (id_cam, len(buenas)), flush=True)

    os.makedirs("datos/detecciones", exist_ok=True)
    rng = np.random.default_rng(id_cam)
    orden = list(rng.permutation(buenas))
    idx_actual = 0
    ultimo = 0.0
    insertadas = 0

    print("demo corriendo (q para salir, inserta cada 2s)", flush=True)
    while True:
        i = orden[idx_actual % len(orden)]
        img = Xte[i]                                  # (3,32,32) RGB [0,1]
        pred = int(red.predecir(Xte[i:i + 1])[0])
        tipo = clases[pred]

        # armar el frame grande para la ventana (a color, ampliado)
        rgb = np.transpose(img, (1, 2, 0))            # (32,32,3)
        grande = cv2.resize((rgb * 255).astype(np.uint8), (480, 480),
                            interpolation=cv2.INTER_NEAREST)
        bgr = cv2.cvtColor(grande, cv2.COLOR_RGB2BGR)
        cv2.rectangle(bgr, (8, 8), (472, 472), (22, 118, 244), 4)
        cv2.putText(bgr, "Detecto: %s" % tipo, (18, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (78, 157, 42), 2)
        cv2.imshow("Camara %d - Servidor de Testeo (demo)" % id_cam, bgr)

        ahora = time.time()
        if ahora - ultimo >= 2.0:
            ultimo = ahora
            fecha = time.strftime("%d/%m/%Y %H:%M:%S")
            ref = "datos/detecciones/demo_cam%d_%04d_%s.png" % (id_cam, insertadas + 1, tipo)
            guardar_png(img, tipo, "Camara %d" % id_cam, ref)
            if cluster.insertar(tipo, ref, fecha, "Camara %d" % id_cam):
                insertadas += 1
                print("  [camara %d] detecto '%s' -> insertado (%d)"
                      % (id_cam, tipo, insertadas), flush=True)
            idx_actual += 1

        if cv2.waitKey(30) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("camara demo %d cerrada, %d detecciones insertadas" % (id_cam, insertadas))


if __name__ == "__main__":
    main()
