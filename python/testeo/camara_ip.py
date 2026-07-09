# Camara IP: usa el CELULAR como camara (cumple "camara IP" del enunciado).
#
# El celular corre una app tipo "IP Webcam" (Android) que transmite su video por
# la red WiFi en una URL como  http://192.168.1.50:8080/video . Este script lee
# ese stream, la CNN reconoce lo que ve el celular, y cada deteccion se inserta al
# cluster Raft (que el Vigilante muestra).
#
# El reconocimiento es el mismo que la webcam: solo cambia la FUENTE del video (el
# celular en vez de la webcam de la lap).
#
# Uso:
#   python3 testeo/camara_ip.py <camaraId> <url_camara> <id:host:puerto> ...
#   ej: python3 testeo/camara_ip.py 1 http://192.168.1.50:8080/video \
#       1:192.168.1.108:9001 2:192.168.1.108:9002 3:192.168.1.108:9003
#
# Como preparar el celular:
#   1. Instala "IP Webcam" (Android) o "DroidCam".
#   2. Abrela, dale "Iniciar servidor". Te muestra una URL, ej. http://192.168.1.50:8080
#   3. La URL del video suele ser esa URL + /video  (IP Webcam) o la que indique la app.
#   4. El celular y la lap en la MISMA WiFi.
#
# Tecla q en la ventana para salir. Inserta cada 3s.

import os
import sys
import time
import numpy as np

sys.path.insert(0, ".")
from cnn.red import CNN, softmax
from raft.cliente import ClienteCluster, parsear_nodos
from testeo.visor import guardar_png

try:
    import cv2
except ImportError:
    print("Falta OpenCV. Instala:  pip3 install opencv-python-headless")
    sys.exit(1)


def cargar_modelo():
    if os.path.exists("datos/pesos_cifar.npz"):
        clases = [str(c) for c in np.load("datos/clases_cifar.npy")]
        red = CNN(len(clases), canales=3, tam=32)
        red.cargar("datos/pesos_cifar.npz")
        return red, clases
    print("No hay modelo CIFAR. Entrena con: python3 cnn/entrenar_cifar.py")
    sys.exit(1)


def frame_a_entrada(frame_bgr):
    # recorta el cuadro central y lo pasa a 32x32 RGB (lo que espera la CNN)
    h, w = frame_bgr.shape[:2]
    lado = min(h, w)
    y0, x0 = (h - lado) // 2, (w - lado) // 2
    centro = frame_bgr[y0:y0 + lado, x0:x0 + lado]
    rgb = cv2.cvtColor(centro, cv2.COLOR_BGR2RGB)
    chico = cv2.resize(rgb, (32, 32), interpolation=cv2.INTER_AREA)
    x = chico.astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))
    return x[np.newaxis, ...]


def main():
    if len(sys.argv) < 4:
        print("uso: python3 testeo/camara_ip.py <camaraId> <url_camara> <id:host:puerto> ...")
        print("ej:  python3 testeo/camara_ip.py 1 http://192.168.1.50:8080/video \\")
        print("     1:192.168.1.108:9001 2:192.168.1.108:9002 3:192.168.1.108:9003")
        return
    id_cam = int(sys.argv[1])
    url = sys.argv[2]
    cluster = ClienteCluster(parsear_nodos(sys.argv[3:]))
    red, clases = cargar_modelo()
    print("camara IP %d (celular): %s" % (id_cam, url), flush=True)
    print("modelo CIFAR-10 (%d clases): %s" % (len(clases), ", ".join(clases)), flush=True)

    cap = cv2.VideoCapture(url)   # el celular como fuente de video
    if not cap.isOpened():
        print("no pude conectar a la camara IP. Revisa la URL y que el cel este en la"
              " misma WiFi, con la app 'IP Webcam' corriendo.")
        return

    os.makedirs("datos/detecciones", exist_ok=True)
    ultimo = 0.0
    insertadas = 0
    print("leyendo del celular... (q para salir, inserta cada 3s)", flush=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("se perdio el stream del celular, reintentando...")
            time.sleep(0.5)
            continue

        x = frame_a_entrada(frame)
        probs = softmax(red.forward(x))[0]
        pred = int(np.argmax(probs))
        tipo = clases[pred]

        # cuadro central + etiqueta en la ventana
        h, w = frame.shape[:2]
        lado = min(h, w)
        cy0, cx0 = (h - lado) // 2, (w - lado) // 2
        cv2.rectangle(frame, (cx0, cy0), (cx0 + lado, cy0 + lado), (22, 118, 244), 3)
        cv2.putText(frame, "Detecto: %s (%.0f%%)" % (tipo, probs[pred] * 100),
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 157, 78), 2)
        cv2.imshow("Camara IP %d (celular)" % id_cam, frame)

        ahora = time.time()
        if ahora - ultimo >= 3.0:
            ultimo = ahora
            x32 = x[0]
            fecha = time.strftime("%d/%m/%Y %H:%M:%S")
            ref = os.path.abspath(
                "datos/detecciones/ip%d_%04d_%s.png" % (id_cam, insertadas + 1, tipo))
            guardar_png(x32, tipo, "Camara IP %d" % id_cam, ref)
            if cluster.insertar(tipo, ref, fecha, "Camara IP %d" % id_cam):
                insertadas += 1
                print("  [camara IP %d] detecto '%s' -> insertado (%d)"
                      % (id_cam, tipo, insertadas), flush=True)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("camara IP %d cerrada, %d detecciones insertadas" % (id_cam, insertadas))


if __name__ == "__main__":
    main()
