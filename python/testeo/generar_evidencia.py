# Genera imagenes PNG reales del reconocimiento, para la evidencia del informe y
# las diapositivas. Carga la CNN entrenada, toma frames, los reconoce, y guarda:
#   - PNGs individuales por deteccion (con su etiqueta reconocida)
#   - una hoja de contacto con varias detecciones en una sola imagen
#
# Uso: python3 testeo/generar_evidencia.py

import sys
import numpy as np

sys.path.insert(0, ".")
from cnn.dataset import generar, CLASES
from cnn.red import CNN
from testeo.visor import guardar_png, hoja_contacto


def main():
    red = CNN(len(CLASES))
    red.cargar("datos/pesos_cnn.npz")

    # tomar unos frames de cada clase
    X, y = generar(3, semilla=7)  # 3 por clase = 15 frames
    frames, tipos, camaras = [], [], []
    aciertos = 0
    for i in range(len(X)):
        pred = int(red.predecir(X[i:i + 1])[0])
        tipo = CLASES[pred]
        cam = f"Camera {i % 3 + 1}"
        frames.append(X[i]); tipos.append(tipo); camaras.append(cam)
        if pred == y[i]:
            aciertos += 1
        # guardar los primeros como PNG individual
        if i < 6:
            guardar_png(X[i], tipo, cam, f"datos/evidencia/det_{i+1:02d}_{tipo}.png")

    hoja_contacto(frames, tipos, camaras, "datos/evidencia/hoja_detecciones.png")
    acc = 100.0 * aciertos / len(X)
    print(f"evidencia generada en datos/evidencia/ ({len(X)} frames, "
          f"reconocimiento {acc:.1f}%)")
    print("  - PNGs individuales: det_01..06")
    print("  - hoja de contacto: hoja_detecciones.png")


if __name__ == "__main__":
    main()
