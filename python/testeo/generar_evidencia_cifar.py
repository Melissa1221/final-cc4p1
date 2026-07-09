# Genera imagenes PNG de reconocimiento con el modelo CIFAR (objetos reales),
# para la evidencia del informe y las diapositivas. Carga la CNN entrenada,
# toma frames del test de CIFAR, los reconoce, y guarda:
#   - PNGs individuales por deteccion (con su etiqueta reconocida)
#   - una hoja de contacto con varias detecciones en una sola imagen
#
# Uso: python3 testeo/generar_evidencia_cifar.py

import sys
import numpy as np

sys.path.insert(0, ".")
from cnn.cifar import cargar
from cnn.red import CNN
from testeo.visor import guardar_png, hoja_contacto


def main():
    clases = list(np.load("datos/clases_cifar.npy"))
    red = CNN(len(clases), canales=3, tam=32)
    red.cargar("datos/pesos_cifar.npz")

    # tomar unos frames del test (objetos reales que la red no vio al entrenar)
    _, _, Xte, yte, _ = cargar(max_por_clase=50)
    rng = np.random.default_rng(3)
    idx = rng.permutation(len(Xte))[:15]

    frames, tipos, camaras = [], [], []
    aciertos = 0
    for k, i in enumerate(idx):
        pred = int(red.predecir(Xte[i:i + 1])[0])
        tipo = clases[pred]
        cam = "Camera %d" % (k % 3 + 1)
        frames.append(Xte[i]); tipos.append(tipo); camaras.append(cam)
        if pred == int(yte[i]):
            aciertos += 1
        if k < 6:
            guardar_png(Xte[i], tipo, cam,
                        "datos/evidencia/cifar_det_%02d_%s.png" % (k + 1, tipo))

    hoja_contacto(frames, tipos, camaras,
                  "datos/evidencia/cifar_hoja_detecciones.png")
    acc = 100.0 * aciertos / len(idx)
    print("evidencia CIFAR generada en datos/evidencia/ (%d frames, "
          "reconocimiento %.1f%%)" % (len(idx), acc))
    print("  - PNGs individuales: cifar_det_01..06")
    print("  - hoja de contacto: cifar_hoja_detecciones.png")


if __name__ == "__main__":
    main()
