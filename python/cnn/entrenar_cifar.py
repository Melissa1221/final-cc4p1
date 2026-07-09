# Entrena la CNN con CIFAR-10 (OBJETOS Y ANIMALES REALES 32x32 RGB).
#
# El enunciado permite "entrenamiento previo" y desplegar sin internet: aca se
# entrena UNA vez con el dataset ya descargado en disco, y se guardan los pesos
# (.npz). En runtime el Servidor de Testeo carga esos pesos SIN internet.
#
# La CNN es la misma de siempre (NumPy puro, sin frameworks), pero la primera
# capa Conv se ajusta a 3 canales (RGB) y la entrada a 32x32.
#
# Nota honesta: una CNN chica hecha a mano en NumPy no llega al 90% en CIFAR-10;
# lo normal es 40-60%. Eso ya es muy por encima del azar (10% con 10 clases) y
# son objetos reales, que es lo que pide el enunciado. Se reporta la accuracy
# real que salga, sin inventar.

import os
import sys
import time
import numpy as np

sys.path.insert(0, ".")
from cnn.cifar import cargar
from cnn.red import CNN


def evaluar(red, X, y, batch=200):
    # evalua por lotes para no cargar toda la memoria de golpe
    aciertos = 0
    for i in range(0, len(X), batch):
        pred = red.predecir(X[i:i + batch])
        aciertos += int((pred == y[i:i + batch]).sum())
    return aciertos / len(X)


def entrenar(epocas=12, lr=0.02, batch=64, max_por_clase=800,
             clases=None, semilla=0, verbose=True):
    Xtr, ytr, Xte, yte, nombres = cargar(clases=clases,
                                         max_por_clase=max_por_clase)
    num_clases = len(nombres)
    if verbose:
        print("clases (%d):" % num_clases, nombres)
        print("train:", Xtr.shape, " test:", Xte.shape, flush=True)

    red = CNN(num_clases, semilla=semilla, canales=3, tam=32)
    N = len(Xtr)
    rng = np.random.default_rng(semilla)

    t0 = time.time()
    for ep in range(epocas):
        lr_ep = lr * (0.5 ** (ep / 6))
        orden = rng.permutation(N)
        perdidas = []
        for i in range(0, N, batch):
            idx = orden[i:i + batch]
            p = red.paso(Xtr[idx], ytr[idx], lr_ep)
            perdidas.append(p)
        if verbose:
            acc = evaluar(red, Xte, yte)
            print("epoca %d/%d  lr=%.4f  perdida=%.4f  acc_test=%.2f%%"
                  % (ep + 1, epocas, lr_ep, np.mean(perdidas), acc * 100),
                  flush=True)
    dur = time.time() - t0

    acc = evaluar(red, Xte, yte)
    if verbose:
        print("\nentrenamiento CIFAR: %.1fs, accuracy final = %.2f%%"
              % (dur, acc * 100))
    return red, acc, nombres


if __name__ == "__main__":
    # por defecto: 10 clases, subconjunto para que sea tratable en NumPy puro.
    # se puede pasar max_por_clase por CLI para subir/bajar el tamano.
    max_pc = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    red, acc, nombres = entrenar(max_por_clase=max_pc)
    os.makedirs("datos", exist_ok=True)
    red.guardar("datos/pesos_cifar.npz")
    # guardo tambien las clases usadas, para que el testeo sepa los nombres
    np.save("datos/clases_cifar.npy", np.array(nombres))
    print("pesos guardados en datos/pesos_cifar.npz")
    print("clases guardadas en datos/clases_cifar.npy")
