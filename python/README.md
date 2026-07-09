# Nodo Python — Servidor de Testeo + CNN + nodo Raft

Parte de Python. Todo con la stdlib + NumPy, sin frameworks. Habla el mismo
protocolo de texto que Java y Go (documentado en `java/src/raft/Protocolo.java`),
asi que interopera en el mismo cluster.

## Estructura

```
cnn/       CNN desde cero con NumPy (dataset figuras, cifar, red, entrenamiento)
raft/      nodo Raft en Python (mismo protocolo que Java y Go)
video/     Servidor de Video: emite frames por socket a las camaras
testeo/    Servidor de Testeo: pide frames al video, la CNN reconoce e inserta
datos/     dataset CIFAR + pesos entrenados + PNG de detecciones (no se versionan)
```

## Dataset CIFAR-10 (objetos reales)

La CNN reconoce OBJETOS Y ANIMALES REALES (avion, auto, pajaro, gato, ciervo,
perro, rana, caballo, barco, camion) usando CIFAR-10. Se descarga UNA vez con
internet; luego el sistema corre SIN internet cargando los pesos de disco.

```bash
cd python
mkdir -p datos && cd datos
curl -LO https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz
tar xzf cifar-10-python.tar.gz     # crea datos/cifar-10-batches-py/
```

El dataset (170MB) y los pesos (.npz) NO se versionan (ver .gitignore).

## Entrenar la CNN

```bash
cd python
# con OBJETOS REALES (CIFAR-10). El argumento es muestras por clase.
python3 cnn/entrenar_cifar.py 800      # -> datos/pesos_cifar.npz + clases_cifar.npy

# (opcional) version antigua con figuras geometricas
python3 cnn/entrenar.py                 # -> datos/pesos_cnn.npz
python3 cnn/entrenar_distribuido.py 4   # distribuido, 4 workers en paralelo
```

El Servidor de Testeo usa `pesos_cifar.npz` si existe; si no, cae a las figuras.

## Correr el Servidor de Video

```bash
cd python
python3 video/servidor_video.py 9500    # emite frames por socket en el puerto 9500
```

## Correr un nodo Raft

```bash
cd python
python3 raft/arrancar.py 2  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

## Correr el Servidor de Testeo (necesita cluster + video + pesos)

```bash
cd python
# primer argumento: host:puerto del servidor de video. Luego los nodos del cluster.
python3 testeo/servidor_testeo.py 127.0.0.1:9500  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

Levanta 3 camaras (un hilo por camara). Cada camara pide frames al Servidor de
Video por socket, la CNN los reconoce sola, guarda un PNG de la deteccion e
inserta el registro al cluster.

## Ver el detalle de como esta hecho

`docs/COMO-LO-HICE.md` en la raiz del repo explica la CNN, el nodo Raft y las
pruebas paso a paso.
