# Nodo Python — Servidor de Testeo + CNN + nodo Raft

Parte de Andrew. Todo con la stdlib + NumPy, sin frameworks.

## Estructura

```
cnn/       CNN desde cero con NumPy (dataset, red, entrenamiento)
raft/      nodo Raft en Python (mismo protocolo que Java y Go)
testeo/    Servidor de Testeo: usa la CNN e inserta detecciones al cluster
datos/     pesos entrenados + imagenes de detecciones (generados, no se versionan)
```

## Entrenar la CNN

```bash
cd python
python3 cnn/entrenar.py                 # entrenamiento normal (~97% accuracy)
python3 cnn/entrenar_distribuido.py 4   # distribuido, 4 workers en paralelo
```

Los pesos quedan en `datos/pesos_cnn.npz`.

## Correr un nodo Raft

```bash
cd python
python3 raft/arrancar.py 2  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

## Correr el Servidor de Testeo (necesita el cluster arriba y los pesos)

```bash
cd python
python3 testeo/servidor_testeo.py  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

Levanta 3 camaras (un hilo por camara), reconoce figuras con la CNN e inserta cada
deteccion al cluster.

## Ver el detalle de como esta hecho

`docs/COMO-LO-HICE.md` en la raiz del repo explica la CNN, el nodo Raft y las
pruebas paso a paso.
