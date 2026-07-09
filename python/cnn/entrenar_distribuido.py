# Entrenamiento DISTRIBUIDO de la CNN, tipo CPU, con varios workers.
#
# Esquema data-parallel (el mismo que usan los frameworks reales): en cada paso el
# mini-batch se parte en shards, un worker por shard calcula el gradiente sobre su
# parte, y luego se promedian los gradientes (all-reduce) para actualizar los
# pesos. Asi la carga de computo se reparte entre nucleos.
#
# Se usa multiprocessing (procesos, no hilos) porque en Python el GIL impide que
# los hilos aprovechen varios nucleos para computo puro; con procesos el trabajo
# es paralelo de verdad. El enunciado pide justamente repartir la carga entre nodos.
#
# Para mantenerlo claro y sin dependencias raras, cada worker recibe su shard y los
# pesos actuales, y devuelve los gradientes de su shard. El proceso principal los
# promedia y aplica la actualizacion.

import sys
import time
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, ".")
from cnn.dataset import generar, NUM_CLASES
from cnn.red import CNN, softmax


# --- El worker necesita reconstruir la red desde pesos planos y sacar gradientes.
# Para no serializar objetos complejos, mandamos los arrays de pesos y el shard.

_RED_GLOBAL = None  # cada proceso worker cachea su propia CNN


def _init_worker(semilla):
    global _RED_GLOBAL
    _RED_GLOBAL = CNN(NUM_CLASES, semilla=semilla)


def _grad_worker(args):
    # calcula los gradientes de un shard con los pesos actuales
    pesos, Xs, ys = args
    red = _RED_GLOBAL
    _cargar_pesos(red, pesos)
    return _gradientes(red, Xs, ys), len(Xs)


def _lista_pesos(red):
    ps = []
    for c in red.capas:
        if hasattr(c, "W"):
            ps.append(c.W.copy()); ps.append(c.b.copy())
    ps.append(red.densa.W.copy()); ps.append(red.densa.b.copy())
    return ps


def _cargar_pesos(red, ps):
    it = iter(ps)
    for c in red.capas:
        if hasattr(c, "W"):
            c.W = next(it); c.b = next(it)
    red.densa.W = next(it); red.densa.b = next(it)


def _gradientes(red, X, y):
    # forward + backward pero devolviendo los gradientes en vez de aplicarlos.
    # Reusamos las capas guardando dW/db temporalmente.
    logits = red.forward(X)
    probs = softmax(logits)
    N = X.shape[0]
    dlogits = probs.copy()
    dlogits[np.arange(N), y] -= 1
    dlogits /= N

    grads = []
    # densa
    dW = red.densa.X.T @ dlogits / N
    db = dlogits.mean(axis=0)
    d = dlogits @ red.densa.W.T
    dens_grad = (dW, db)

    capa_grads = []
    for c in reversed(red.capas):
        if hasattr(c, "W"):
            Nb = d.shape[0]
            if c.__class__.__name__ == "Conv":
                c_out = c.W.shape[0]
                dout_r = d.reshape(Nb, c_out, -1)
                Wcol = c.W.reshape(c_out, -1)
                dWc = np.einsum('nop,ncp->oc', dout_r, c.cols) / Nb
                dbc = dout_r.sum(axis=(0, 2)) / Nb
                from cnn.red import col2im
                dcols = np.einsum('nop,oc->ncp', dout_r, Wcol)
                d = col2im(dcols, c.X_shape, c.k, c.k, c.oh, c.ow)
                capa_grads.append((dWc.reshape(c.W.shape), dbc))
            else:
                d = c.backward(d, 0.0)  # no actualiza (lr 0), solo propaga
        else:
            d = c.backward(d, 0.0)
    capa_grads.reverse()
    return {"densa": dens_grad, "capas": capa_grads}


def _aplicar(red, grad_prom, lr):
    dW, db = grad_prom["densa"]
    red.densa.W -= lr * dW
    red.densa.b -= lr * db
    it = iter(grad_prom["capas"])
    for c in red.capas:
        if c.__class__.__name__ == "Conv":
            dWc, dbc = next(it)
            c.W -= lr * dWc
            c.b -= lr * dbc


def _promediar(resultados):
    # promedio ponderado por tamano de shard
    total = sum(n for _, n in resultados)
    dW_d = sum(g["densa"][0] * n for g, n in resultados) / total
    db_d = sum(g["densa"][1] * n for g, n in resultados) / total
    capas = []
    num_conv = len(resultados[0][0]["capas"])
    for k in range(num_conv):
        dWc = sum(g["capas"][k][0] * n for g, n in resultados) / total
        dbc = sum(g["capas"][k][1] * n for g, n in resultados) / total
        capas.append((dWc, dbc))
    return {"densa": (dW_d, db_d), "capas": capas}


def entrenar_distribuido(num_workers=4, epocas=20, lr=0.08, batch=64,
                         por_clase=600, semilla=0):
    Xtr, ytr = generar(por_clase, semilla=semilla)
    Xte, yte = generar(por_clase // 4, semilla=semilla + 100)
    red = CNN(NUM_CLASES, semilla=semilla)
    N = len(Xtr)
    rng = np.random.default_rng(semilla)

    print(f"entrenamiento distribuido: {N} muestras, {num_workers} workers, "
          f"batch {batch}, {epocas} epocas")
    t0 = time.time()
    with Pool(num_workers, initializer=_init_worker, initargs=(semilla,)) as pool:
        for ep in range(epocas):
            lr_ep = lr * (0.5 ** (ep / 8))
            orden = rng.permutation(N)
            for i in range(0, N, batch):
                idx = orden[i:i + batch]
                Xb, yb = Xtr[idx], ytr[idx]
                # parto el batch en num_workers shards
                pesos = _lista_pesos(red)
                shards = np.array_split(np.arange(len(Xb)), num_workers)
                tareas = [(pesos, Xb[s], yb[s]) for s in shards if len(s) > 0]
                resultados = pool.map(_grad_worker, tareas)
                grad_prom = _promediar(resultados)
                _aplicar(red, grad_prom, lr_ep)
            acc = (red.predecir(Xte) == yte).mean()
            print(f"epoca {ep+1}/{epocas}  lr={lr_ep:.4f}  acc_test={acc*100:.2f}%")
    dur = time.time() - t0

    acc = (red.predecir(Xte) == yte).mean()
    print(f"\ndistribuido: {dur:.1f}s, accuracy final = {acc*100:.2f}%")
    red.guardar("datos/pesos_cnn.npz")
    print("pesos guardados en datos/pesos_cnn.npz")
    return red, acc


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    entrenar_distribuido(num_workers=nw)
