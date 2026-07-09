# CNN implementada desde cero con NumPy (permitido por el profe). Sin frameworks
# de deep learning. Arquitectura chica pero real:
#
#   entrada 1x28x28
#   -> Conv 8 filtros 3x3  -> ReLU -> MaxPool 2x2   (8x13x13)
#   -> Conv 16 filtros 3x3 -> ReLU -> MaxPool 2x2   (16x5x5 aprox)
#   -> Flatten -> Densa -> Softmax (5 clases)
#
# Incluye forward y backward (backprop de verdad) y entrenamiento por mini-batches
# con descenso de gradiente. La convolucion usa im2col para que sea rapida en NumPy.

import numpy as np


# ---------- utilidades im2col ----------
def im2col(X, kh, kw, stride=1):
    # X: (N, C, H, W) -> columnas (N, C*kh*kw, salidaH*salidaW)
    N, C, H, W = X.shape
    oh = (H - kh) // stride + 1
    ow = (W - kw) // stride + 1
    cols = np.zeros((N, C, kh, kw, oh, ow), dtype=X.dtype)
    for i in range(kh):
        for j in range(kw):
            cols[:, :, i, j, :, :] = X[:, :, i:i + stride * oh:stride, j:j + stride * ow:stride]
    return cols.reshape(N, C * kh * kw, oh * ow), oh, ow


def col2im(cols, X_shape, kh, kw, oh, ow, stride=1):
    N, C, H, W = X_shape
    cols = cols.reshape(N, C, kh, kw, oh, ow)
    dX = np.zeros(X_shape, dtype=cols.dtype)
    for i in range(kh):
        for j in range(kw):
            dX[:, :, i:i + stride * oh:stride, j:j + stride * ow:stride] += cols[:, :, i, j, :, :]
    return dX


class Conv:
    def __init__(self, c_in, c_out, k, rng):
        # inicializacion He para que ReLU no muera
        self.W = rng.normal(0, np.sqrt(2.0 / (c_in * k * k)), (c_out, c_in, k, k)).astype(np.float32)
        self.b = np.zeros(c_out, dtype=np.float32)
        self.k = k

    def forward(self, X):
        self.X_shape = X.shape
        N, C, H, Wd = X.shape
        cols, oh, ow = im2col(X, self.k, self.k)
        self.cols = cols
        self.oh, self.ow = oh, ow
        Wcol = self.W.reshape(self.W.shape[0], -1)      # (c_out, C*k*k)
        out = np.einsum('oc,ncp->nop', Wcol, cols) + self.b[None, :, None]
        return out.reshape(N, self.W.shape[0], oh, ow)

    def backward(self, dout, lr):
        N = dout.shape[0]
        c_out = self.W.shape[0]
        dout_r = dout.reshape(N, c_out, -1)              # (N, c_out, oh*ow)
        Wcol = self.W.reshape(c_out, -1)
        # gradientes
        dW = np.einsum('nop,ncp->oc', dout_r, self.cols) / N
        db = dout_r.sum(axis=(0, 2)) / N
        dcols = np.einsum('nop,oc->ncp', dout_r, Wcol)
        dX = col2im(dcols, self.X_shape, self.k, self.k, self.oh, self.ow)
        # actualizacion
        self.W -= lr * dW.reshape(self.W.shape)
        self.b -= lr * db
        return dX


class ReLU:
    def forward(self, X):
        self.mask = X > 0
        return X * self.mask

    def backward(self, dout, lr):
        return dout * self.mask


class MaxPool:
    def __init__(self, k=2):
        self.k = k

    def forward(self, X):
        N, C, H, W = X.shape
        k = self.k
        oh, ow = H // k, W // k
        Xr = X[:, :, :oh * k, :ow * k].reshape(N, C, oh, k, ow, k)
        self.Xr_shape = X.shape
        out = Xr.max(axis=(3, 5))
        # guardo mascara de maximos para el backward
        self.argmax = (Xr == out[:, :, :, None, :, None])
        self.oh, self.ow = oh, ow
        return out

    def backward(self, dout, lr):
        N, C, oh, ow = dout.shape
        k = self.k
        dXr = self.argmax * dout[:, :, :, None, :, None]
        dX = np.zeros(self.Xr_shape, dtype=np.float32)
        dX[:, :, :oh * k, :ow * k] = dXr.reshape(N, C, oh * k, ow * k)
        return dX


class Densa:
    def __init__(self, n_in, n_out, rng):
        self.W = rng.normal(0, np.sqrt(2.0 / n_in), (n_in, n_out)).astype(np.float32)
        self.b = np.zeros(n_out, dtype=np.float32)

    def forward(self, X):
        self.X = X
        return X @ self.W + self.b

    def backward(self, dout, lr):
        dW = self.X.T @ dout / dout.shape[0]
        db = dout.mean(axis=0)
        dX = dout @ self.W.T
        self.W -= lr * dW
        self.b -= lr * db
        return dX


class Flatten:
    def forward(self, X):
        self.shape = X.shape
        return X.reshape(X.shape[0], -1)

    def backward(self, dout, lr):
        return dout.reshape(self.shape)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class CNN:
    # canales: 1 para escala de grises (figuras 28x28), 3 para RGB (CIFAR 32x32).
    # tam: lado de la imagen de entrada. La primera Conv se ajusta a los canales.
    def __init__(self, num_clases, semilla=0, canales=1, tam=28):
        rng = np.random.default_rng(semilla)
        self.canales = canales
        self.tam = tam
        self.capas = [
            Conv(canales, 8, 3, rng), ReLU(), MaxPool(2),
            Conv(8, 16, 3, rng), ReLU(), MaxPool(2),
            Flatten(),
        ]
        # calculo la dimension aplanada con un forward de prueba
        dummy = np.zeros((1, canales, tam, tam), dtype=np.float32)
        h = dummy
        for c in self.capas:
            h = c.forward(h)
        self.densa = Densa(h.shape[1], num_clases, rng)
        self.num_clases = num_clases

    def forward(self, X):
        h = X
        for c in self.capas:
            h = c.forward(h)
        logits = self.densa.forward(h)
        return logits

    def perdida_y_grad(self, X, y):
        logits = self.forward(X)
        probs = softmax(logits)
        N = X.shape[0]
        perdida = -np.log(probs[np.arange(N), y] + 1e-9).mean()
        dlogits = probs.copy()
        dlogits[np.arange(N), y] -= 1
        dlogits /= N
        return perdida, dlogits

    def paso(self, X, y, lr):
        perdida, dlogits = self.perdida_y_grad(X, y)
        d = self.densa.backward(dlogits, lr)
        for c in reversed(self.capas):
            d = c.backward(d, lr)
        return perdida

    def predecir(self, X):
        return self.forward(X).argmax(axis=1)

    # --- persistencia de pesos (formato .npz, todo local) ---
    def guardar(self, ruta):
        d = {}
        idx = 0
        for c in self.capas:
            if isinstance(c, Conv):
                d[f"conv{idx}_W"] = c.W
                d[f"conv{idx}_b"] = c.b
                idx += 1
        d["densa_W"] = self.densa.W
        d["densa_b"] = self.densa.b
        np.savez(ruta, **d)

    def cargar(self, ruta):
        d = np.load(ruta)
        idx = 0
        for c in self.capas:
            if isinstance(c, Conv):
                c.W = d[f"conv{idx}_W"]
                c.b = d[f"conv{idx}_b"]
                idx += 1
        self.densa.W = d["densa_W"]
        self.densa.b = d["densa_b"]
