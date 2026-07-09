# Servidor de Testeo con CAMARA REAL (webcam en vivo).
#
# Esta es la version que el profe imagina: una camara real captura video, la CNN
# reconoce EN VIVO lo que ve, guarda la imagen de la deteccion y la inserta al
# cluster Raft (que la replica y la muestra en el Vigilante desktop/movil).
#
# Usa OpenCV solo para capturar de la webcam (la deteccion sigue siendo la CNN
# NumPy propia; la red y el consenso no dependen de OpenCV). Varios companeros
# usan OpenCV para la captura, el profe lo acepta.
#
# El modelo CIFAR-10 reconoce 10 objetos/animales reales. La webcam captura un
# frame, se redimensiona a 32x32 RGB (lo que la CNN espera), se clasifica, se
# guarda un PNG del frame anotado y se registra en el cluster.
#
# Uso:
#   python3 testeo/camara_real.py <camaraId> <host:puertoNodo> ...
#   ej: python3 testeo/camara_real.py 1 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
#
# Tecla q en la ventana para salir. Cada deteccion se inserta cada ~2s (o al
# presionar espacio para capturar a demanda).

import sys
import time
import numpy as np

sys.path.insert(0, ".")
from cnn.red import CNN
from raft.cliente import ClienteCluster, parsear_nodos
from testeo.visor import guardar_png

try:
    import cv2
except ImportError:
    print("Falta OpenCV. Instala:  pip3 install opencv-python-headless")
    sys.exit(1)


def cargar_modelo():
    import os
    if os.path.exists("datos/pesos_cifar.npz"):
        clases = [str(c) for c in np.load("datos/clases_cifar.npy")]
        red = CNN(len(clases), canales=3, tam=32)
        red.cargar("datos/pesos_cifar.npz")
        return red, clases
    print("No hay modelo CIFAR. Entrena con: python3 cnn/entrenar_cifar.py")
    sys.exit(1)


def frame_a_entrada(frame_bgr):
    # BGR (webcam) -> RGB, 32x32, [0,1], forma (1,3,32,32) que espera la CNN.
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    chico = cv2.resize(rgb, (32, 32), interpolation=cv2.INTER_AREA)
    x = chico.astype(np.float32) / 255.0        # (32,32,3)
    x = np.transpose(x, (2, 0, 1))              # (3,32,32)
    return x[np.newaxis, ...]                    # (1,3,32,32)


def main():
    if len(sys.argv) < 3:
        print("uso: python3 testeo/camara_real.py <camaraId> <id:host:puerto> ...")
        return
    id_cam = int(sys.argv[1])
    nodos = parsear_nodos(sys.argv[2:])
    cluster = ClienteCluster(nodos)
    red, clases = cargar_modelo()
    print("camara real %d lista, modelo CIFAR-10 (%d clases): %s"
          % (id_cam, len(clases), ", ".join(clases)), flush=True)

    cap = cv2.VideoCapture(0)   # webcam por defecto
    if not cap.isOpened():
        print("no pude abrir la webcam (permiso de camara?).")
        return

    ultimo = 0.0
    insertadas = 0
    import os
    os.makedirs("datos/detecciones", exist_ok=True)
    print("mirando por la camara... (q para salir, la deteccion es automatica cada 2s)", flush=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # reconocer en vivo
        x = frame_a_entrada(frame)
        pred = int(red.predecir(x)[0])
        tipo = clases[pred]

        # dibujar la etiqueta en el video (para ver el reconocimiento en vivo)
        cv2.rectangle(frame, (10, 10), (frame.shape[1] - 10, frame.shape[0] - 10),
                      (22, 118, 244), 3)
        cv2.putText(frame, "Detecto: %s" % tipo, (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 157, 78), 2)
        cv2.imshow("Camara %d - Servidor de Testeo" % id_cam, frame)

        # insertar al cluster cada 2 segundos
        ahora = time.time()
        if ahora - ultimo >= 2.0:
            ultimo = ahora
            # guardar el frame 32x32 anotado como PNG (lo que ve el Vigilante)
            x32 = x[0]                              # (3,32,32)
            fecha = time.strftime("%d/%m/%Y %H:%M:%S")
            ref = "datos/detecciones/cam%d_%04d_%s.png" % (id_cam, insertadas + 1, tipo)
            guardar_png(x32, tipo, "Camara %d" % id_cam, ref)
            if cluster.insertar(tipo, ref, fecha, "Camara %d" % id_cam):
                insertadas += 1
                print("  [camara %d] detecto '%s' -> insertado (%d)"
                      % (id_cam, tipo, insertadas), flush=True)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("camara %d cerrada, %d detecciones insertadas" % (id_cam, insertadas))


if __name__ == "__main__":
    main()
