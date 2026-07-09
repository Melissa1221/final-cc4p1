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
    # recorta el CUADRO CENTRAL del frame (donde se pone el objeto) y lo pasa a
    # 32x32 RGB. Mirar solo el centro evita que el fondo (pared, cara, monitor)
    # confunda a la CNN. Coloca el objeto en el centro de la camara.
    h, w = frame_bgr.shape[:2]
    lado = min(h, w)
    y0 = (h - lado) // 2
    x0 = (w - lado) // 2
    centro = frame_bgr[y0:y0 + lado, x0:x0 + lado]   # cuadrado central
    rgb = cv2.cvtColor(centro, cv2.COLOR_BGR2RGB)
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

        # reconocer en vivo (con probabilidades para ver la confianza)
        from cnn.red import softmax
        x = frame_a_entrada(frame)
        probs = softmax(red.forward(x))[0]
        orden_p = np.argsort(probs)[::-1]
        pred = int(orden_p[0])
        tipo = clases[pred]

        # dibujar el CUADRO CENTRAL: pon el objeto AHI (es lo que mira la CNN)
        h, w = frame.shape[:2]
        lado = min(h, w)
        cy0, cx0 = (h - lado) // 2, (w - lado) // 2
        cv2.rectangle(frame, (cx0, cy0), (cx0 + lado, cy0 + lado), (22, 118, 244), 3)
        cv2.putText(frame, "pon el objeto aqui", (cx0 + 10, cy0 + lado - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (22, 118, 244), 2)
        # top-3 con confianza, arriba a la izquierda
        cv2.putText(frame, "Detecto: %s (%.0f%%)" % (tipo, probs[pred] * 100),
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 157, 78), 2)
        for k in range(1, 3):
            c = int(orden_p[k])
            cv2.putText(frame, "  %s %.0f%%" % (clases[c], probs[c] * 100),
                        (20, 40 + k * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (150, 150, 150), 2)
        cv2.imshow("Camara %d - Servidor de Testeo" % id_cam, frame)

        # insertar al cluster automaticamente cada 3 segundos
        ahora = time.time()
        if ahora - ultimo >= 3.0:
            ultimo = ahora
            # guardar el frame 32x32 como PNG (ruta ABSOLUTA para que el Vigilante
            # lo encuentre corra desde donde corra) e insertar al cluster.
            x32 = x[0]                              # (3,32,32)
            fecha = time.strftime("%d/%m/%Y %H:%M:%S")
            ref = os.path.abspath(
                "datos/detecciones/cam%d_%04d_%s.png" % (id_cam, insertadas + 1, tipo))
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
