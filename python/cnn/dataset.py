# Genera un dataset de imagenes en escala de grises con figuras geometricas.
# Son imagenes reales de pixeles (no vectores de numeros sueltos): la CNN tiene que
# aprender los patrones espaciales de cada figura. Todo local, sin internet.
#
# Clases (n=5): circulo, cuadrado, triangulo, cruz, linea.
# Cada imagen es 28x28, con la figura en posicion, tamano y grosor variados, mas
# un poco de ruido. Asi la red tiene que generalizar de verdad.

import numpy as np

TAM = 28
CLASES = ["circulo", "cuadrado", "triangulo", "cruz", "linea"]
NUM_CLASES = len(CLASES)


def _lienzo():
    return np.zeros((TAM, TAM), dtype=np.float32)


def _circulo(img, cx, cy, r, grosor):
    ys, xs = np.ogrid[:TAM, :TAM]
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    img[np.abs(dist - r) <= grosor] = 1.0


def _cuadrado(img, cx, cy, lado, grosor):
    x0, x1 = int(cx - lado / 2), int(cx + lado / 2)
    y0, y1 = int(cy - lado / 2), int(cy + lado / 2)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(TAM - 1, x1), min(TAM - 1, y1)
    img[y0:y0 + grosor, x0:x1 + 1] = 1.0
    img[y1 - grosor + 1:y1 + 1, x0:x1 + 1] = 1.0
    img[y0:y1 + 1, x0:x0 + grosor] = 1.0
    img[y0:y1 + 1, x1 - grosor + 1:x1 + 1] = 1.0


def _triangulo(img, cx, cy, lado, grosor):
    # triangulo apuntando hacia arriba: recorro los tres lados
    h = int(lado * 0.87)
    apex = (cx, cy - h // 2)
    izq = (cx - lado // 2, cy + h // 2)
    der = (cx + lado // 2, cy + h // 2)
    for (x0, y0), (x1, y1) in [(apex, izq), (apex, der), (izq, der)]:
        _linea_seg(img, x0, y0, x1, y1, grosor)


def _cruz(img, cx, cy, lado, grosor):
    r = lado // 2
    img[cy - grosor // 2:cy + grosor // 2 + 1, cx - r:cx + r + 1] = 1.0
    img[cy - r:cy + r + 1, cx - grosor // 2:cx + grosor // 2 + 1] = 1.0


def _linea(img, cx, cy, lado, grosor):
    r = lado // 2
    _linea_seg(img, cx - r, cy, cx + r, cy, grosor)


def _linea_seg(img, x0, y0, x1, y1, grosor):
    n = max(abs(x1 - x0), abs(y1 - y0)) + 1
    for t in np.linspace(0, 1, n * 2):
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        for dx in range(-(grosor // 2), grosor // 2 + 1):
            for dy in range(-(grosor // 2), grosor // 2 + 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < TAM and 0 <= yy < TAM:
                    img[yy, xx] = 1.0


_DIBUJANTES = [_circulo, _cuadrado, _triangulo, _cruz, _linea]


def generar(muestras_por_clase, semilla=0):
    """Devuelve X (N,1,28,28) y y (N,) con las etiquetas 0..4."""
    rng = np.random.default_rng(semilla)
    X, Y = [], []
    for clase in range(NUM_CLASES):
        for _ in range(muestras_por_clase):
            img = _lienzo()
            cx = rng.integers(11, 18)
            cy = rng.integers(11, 18)
            lado = rng.integers(12, 18)
            grosor = rng.integers(1, 3)
            if clase == 0:
                _circulo(img, cx, cy, lado // 2, grosor)
            else:
                _DIBUJANTES[clase](img, cx, cy, lado, grosor)
            # ruido leve para que no sea trivial
            img += rng.normal(0, 0.06, img.shape).astype(np.float32)
            img = np.clip(img, 0, 1)
            X.append(img[np.newaxis, :, :])  # canal 1
            Y.append(clase)
    X = np.array(X, dtype=np.float32)
    Y = np.array(Y, dtype=np.int64)
    # barajar
    idx = rng.permutation(len(X))
    return X[idx], Y[idx]


if __name__ == "__main__":
    X, y = generar(20, semilla=1)
    print("dataset:", X.shape, y.shape)
    print("clases:", CLASES)
    # imprime una figura de cada clase en ascii para verla
    for c in range(NUM_CLASES):
        i = np.where(y == c)[0][0]
        print(f"\n=== {CLASES[c]} ===")
        for fila in X[i, 0]:
            print("".join("#" if v > 0.4 else "." for v in fila))
