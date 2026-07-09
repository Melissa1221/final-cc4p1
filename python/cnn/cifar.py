# Carga el dataset CIFAR-10 (objetos y animales reales 32x32 RGB) desde los
# batches que ya se descargaron a disco. Todo local, SIN internet en runtime:
# la descarga se hace una sola vez (ver README), aca solo se leen los archivos.
#
# CIFAR-10 tiene 10 clases reales: avion, auto, pajaro, gato, ciervo, perro,
# rana, caballo, barco, camion. El profe da como ejemplo perros y gatos; aca
# usamos las 10 clases para que n sea mayor (mayor n = mas nota).
#
# Se puede pedir un subconjunto de clases (para entrenar mas rapido en NumPy
# puro) pasando una lista de indices. Las imagenes se devuelven como
# (N, 3, 32, 32) normalizadas a [0,1], que es lo que espera la CNN adaptada.

import os
import pickle
import numpy as np

# nombres de las 10 clases de CIFAR-10, en el orden oficial (0..9)
CLASES = ["avion", "auto", "pajaro", "gato", "ciervo",
          "perro", "rana", "caballo", "barco", "camion"]
NUM_CLASES = len(CLASES)

# carpeta donde quedan los batches tras descomprimir el .tar.gz
_CARPETA = "datos/cifar-10-batches-py"


def _cargar_batch(ruta):
    with open(ruta, "rb") as f:
        d = pickle.load(f, encoding="bytes")
    datos = d[b"data"]                    # (10000, 3072) uint8, RGB aplanado
    etiquetas = np.array(d[b"labels"], dtype=np.int64)
    # el formato es 3072 = 3 canales * 32 * 32, canal primero
    imgs = datos.reshape(-1, 3, 32, 32).astype(np.float32) / 255.0
    return imgs, etiquetas


def _existe():
    return os.path.isdir(_CARPETA)


def cargar(clases=None, max_por_clase=None):
    """Devuelve (Xtr, ytr, Xte, yte, nombres).

    - clases: lista de indices 0..9 a usar (None = las 10). Las etiquetas de
      salida se re-mapean a 0..len(clases)-1 para que la red tenga esa cantidad
      de neuronas de salida.
    - max_por_clase: recorta cuantas muestras de train se usan por clase (util
      para entrenar mas rapido en NumPy puro). None = todas.
    Las imagenes salen como (N, 3, 32, 32) en [0,1].
    """
    if not _existe():
        raise FileNotFoundError(
            "no encuentro " + _CARPETA + ". Descarga CIFAR-10 primero "
            "(ver python/README.md). Corre desde la carpeta python/.")

    # train: 5 batches; test: 1 batch
    Xtr_l, ytr_l = [], []
    for i in range(1, 6):
        x, y = _cargar_batch(os.path.join(_CARPETA, "data_batch_%d" % i))
        Xtr_l.append(x); ytr_l.append(y)
    Xtr = np.concatenate(Xtr_l); ytr = np.concatenate(ytr_l)
    Xte, yte = _cargar_batch(os.path.join(_CARPETA, "test_batch"))

    if clases is None:
        clases = list(range(NUM_CLASES))
    # acepta indices (0..9) o nombres ("gato", "perro", ...)
    clases = [CLASES.index(c) if isinstance(c, str) else int(c) for c in clases]
    nombres = [CLASES[c] for c in clases]

    # filtra las clases pedidas y re-mapea las etiquetas a 0..k-1
    remap = {c: nuevo for nuevo, c in enumerate(clases)}

    def _filtrar(X, y, tope):
        Xs, ys = [], []
        contados = {c: 0 for c in clases}
        for i in range(len(y)):
            c = int(y[i])
            if c not in remap:
                continue
            if tope is not None and contados[c] >= tope:
                continue
            Xs.append(X[i]); ys.append(remap[c]); contados[c] += 1
        return np.array(Xs, dtype=np.float32), np.array(ys, dtype=np.int64)

    Xtr, ytr = _filtrar(Xtr, ytr, max_por_clase)
    # el test siempre con el conjunto oficial (sin recorte por clase)
    Xte, yte = _filtrar(Xte, yte, None)

    # barajar train
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(Xtr))
    return Xtr[idx], ytr[idx], Xte, yte, nombres


if __name__ == "__main__":
    Xtr, ytr, Xte, yte, nombres = cargar(max_por_clase=50)
    print("clases:", nombres)
    print("train:", Xtr.shape, ytr.shape)
    print("test :", Xte.shape, yte.shape)
    print("rango de pixeles:", Xtr.min(), Xtr.max())
