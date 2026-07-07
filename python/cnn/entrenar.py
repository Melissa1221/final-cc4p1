# Entrena la CNN y reporta accuracy. Este es el entrenamiento de referencia
# (un solo proceso). El entrenamiento DISTRIBUIDO esta en entrenar_distribuido.py.

import sys
import time
import numpy as np

sys.path.insert(0, ".")
from cnn.dataset import generar, CLASES, NUM_CLASES
from cnn.red import CNN


def evaluar(red, X, y):
    pred = red.predecir(X)
    return (pred == y).mean()


def entrenar(epocas=20, lr=0.08, batch=32, por_clase=600, semilla=0, verbose=True):
    Xtr, ytr = generar(por_clase, semilla=semilla)
    Xte, yte = generar(por_clase // 4, semilla=semilla + 100)

    red = CNN(NUM_CLASES, semilla=semilla)
    N = len(Xtr)
    rng = np.random.default_rng(semilla)

    t0 = time.time()
    for ep in range(epocas):
        # decaimiento del learning rate: agresivo al inicio, fino al final
        lr_ep = lr * (0.5 ** (ep / 8))
        orden = rng.permutation(N)
        perdidas = []
        for i in range(0, N, batch):
            idx = orden[i:i + batch]
            p = red.paso(Xtr[idx], ytr[idx], lr_ep)
            perdidas.append(p)
        if verbose:
            acc = evaluar(red, Xte, yte)
            print(f"epoca {ep+1}/{epocas}  lr={lr_ep:.4f}  perdida={np.mean(perdidas):.4f}  acc_test={acc*100:.2f}%")
    dur = time.time() - t0

    acc = evaluar(red, Xte, yte)
    if verbose:
        print(f"\nentrenamiento: {dur:.1f}s, accuracy final = {acc*100:.2f}%")
    return red, acc


if __name__ == "__main__":
    red, acc = entrenar()
    red.guardar("datos/pesos_cnn.npz")
    print("pesos guardados en datos/pesos_cnn.npz")
