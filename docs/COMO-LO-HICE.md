# Cómo se construyó el sistema (bitácora técnica)

Este documento explica, paso a paso, cómo se armó el sistema completo del examen
final, para poder retomarlo o explicarlo después. Se va llenando conforme avanza el
trabajo. Rama de desarrollo: `e2e-completo`.

Objetivo del examen: sistema distribuido que reconoce objetos con IA (entrenada
antes), tolerante a fallos con consenso Raft, en tres lenguajes (Java, Python, Go),
solo con sockets nativos e hilos, sin frameworks.

Reparto:
- Java (Melissa): núcleo Raft + entrenamiento distribuido base + Cliente Vigilante.
- Python (Andrew): CNN de reconocimiento + Servidor de Testeo + nodo Raft.
- Go (Junior): máquina de estado del registro + nodo Raft.

---

## Parte 1 — La CNN de reconocimiento (Python + NumPy)

Esta es la pieza de IA que el enunciado pone en negrita ("requiere entrenamiento
previo"). Se hizo una red convolucional **desde cero con NumPy**, sin TensorFlow ni
PyTorch, porque el profe pide librerías base y despliegue sin internet.

### 1.1 El dataset (`python/cnn/dataset.py`)

En vez de descargar un dataset (no hay internet en la demo), se generan imágenes de
figuras geométricas: **círculo, cuadrado, triángulo, cruz, línea** (5 clases, n=5).

- Cada imagen es 28x28 en escala de grises, con la figura en posición, tamaño y
  grosor variables, más ruido gaussiano leve.
- Son imágenes reales de píxeles, así que la CNN tiene que aprender patrones
  espaciales de verdad (no es un problema trivial de vectores separables).
- Correr `python3 cnn/dataset.py` imprime una figura de cada clase en ASCII para
  verificar que se ven bien. Salieron nítidas y reconocibles.

### 1.2 La red (`python/cnn/red.py`)

Arquitectura chica pero real:

```
entrada 1x28x28
  -> Conv 8 filtros 3x3  -> ReLU -> MaxPool 2x2
  -> Conv 16 filtros 3x3 -> ReLU -> MaxPool 2x2
  -> Flatten -> Densa -> Softmax (5 clases)
```

Detalles de implementación:
- **Convolución con im2col**: en vez de bucles lentos, se reordena la imagen en
  columnas y la convolución se vuelve una multiplicación de matrices (rápido en
  NumPy). El backward usa `col2im` para devolver el gradiente a la forma original.
- **Forward y backward de verdad** (backprop) en cada capa: Conv, ReLU, MaxPool
  (con máscara de máximos), Densa, Flatten, Softmax + entropía cruzada.
- **Inicialización He** en las capas con ReLU para que las neuronas no "mueran".
- **Persistencia**: `guardar()` y `cargar()` usan `.npz` (formato NumPy, local).
  Cumple "persistencia y accesibilidad de los pesos".

### 1.3 Entrenamiento de referencia (`python/cnn/entrenar.py`)

Entrenamiento en un solo proceso, para fijar los hiperparámetros:
- 20 épocas, mini-batches de 32, learning rate 0.08 con **decaimiento** (agresivo al
  inicio, fino al final: `lr * 0.5^(época/8)`), 600 muestras por clase.

Resultado medido:
```
epoca  1/20  acc_test=45.80%   (arranca casi al azar)
...
epoca 20/20  acc_test=97.20%
entrenamiento: 11.0s, accuracy final = 97.20%
```

La pérdida baja monótona y la accuracy sube de forma estable: señal de que el
backprop está bien. **97.20%** sobre 5 clases es un resultado sólido para una CNN
hecha a mano.

Primer intento dio 84% (8 épocas, lr 0.05). Subir a 20 épocas + lr con decay + más
datos lo llevó a 97%.

### 1.4 Entrenamiento distribuido (`python/cnn/entrenar_distribuido.py`)

Esto es lo que el enunciado premia: repartir la carga entre nodos, en paralelo tipo
CPU.

- Esquema **data-parallel** (el mismo de los frameworks reales): cada mini-batch se
  parte en shards, un **worker por shard** calcula el gradiente de su parte, y los
  gradientes se **promedian** (all-reduce) antes de actualizar los pesos.
- Se usa **multiprocessing** (procesos, no hilos) a propósito: en Python el GIL
  impide que los hilos usen varios núcleos para cómputo puro. Con procesos el
  reparto es paralelo de verdad.

Resultado con 4 workers:
```
distribuido: 4.7s, accuracy final = 97.20%
```

Dos cosas importantes que esto demuestra:
1. **Misma accuracy que el single-thread (97.20%)** → el promediado de gradientes es
   correcto, no se pierde calidad al distribuir.
2. **Más rápido (4.7s vs 11.0s)** → el paralelismo aprovecha los núcleos de verdad.

---

---

## Parte 2 — Nodo Raft en Python (`python/raft/`)

Se replicó la misma máquina de estados de Raft del Java, en Python con `socket` +
`threading` de la stdlib (sin frameworks). La clave: **habla el mismo protocolo de
texto byte a byte**, así los nodos Java y Python forman un solo cluster.

- `nodo.py` — estados Seguidor/Candidato/Líder, elección con timeout aleatorio
  150-300 ms, RequestVote con restricción de elección, AppendEntries con Log
  Matching + nextIndex, commit por mayoría (solo entradas del term actual).
- `arrancar.py` — lanza un nodo con los mismos argumentos que el Java.
- `cliente.py` — cliente que maneja REDIRECT al líder.

**Prueba de interop Java + Python:** levanté 2 nodos Java + 1 Python. El nodo Python
fue elegido líder, aceptó inserciones, y **los nodos Java aplicaron las mismas
entradas en el mismo orden**. Consenso cruzando lenguajes: funciona.

## Parte 3 — Servidor de Testeo (`python/testeo/servidor_testeo.py`)

Usa la CNN entrenada para reconocer figuras e insertar detecciones al cluster.

- Carga los pesos persistidos (`datos/pesos_cnn.npz`).
- Simula `c` cámaras, **una por hilo** (escalable). Cada cámara toma frames, la CNN
  los reconoce sola, se guarda una imagen de la detección, y se inserta el registro
  al líder Raft.
- Reporta la accuracy de reconocimiento por cámara (salió 92-100% en las pruebas).
- En la demo real, la fuente de frames se cambia por la cámara IP; el resto no cambia.

## Parte 4 — Nodo Raft + registro en Go (`go/`)

Tercer lenguaje, mismo protocolo, con `net` + goroutines + `sync.Mutex` (sin
frameworks).

- `raft/nodo.go` — la misma máquina de estados, la máquina de estado del registro
  protegida con mutex (evita corrupción por concurrencia, que el enunciado pide).
- `main.go` — lanza el nodo con los mismos argumentos.
- `go.mod` — módulo `finalcc4p1`, Go 1.24.

## Parte 5 — End-to-end cruzando los tres lenguajes

`scripts/e2e-completo.sh` orquesta todo:

1. Levanta un cluster **heterogéneo** (nodo 1 Java, nodo 2 Python, nodo 3 Go).
2. Corre el Servidor de Testeo: la CNN reconoce figuras e inserta al cluster.
3. Lee el registro replicado y verifica que los **tres nodos aplicaron lo mismo**.

Resultado medido:
```
lider = go-nodo 3 (rota entre lenguajes en cada corrida)
camara 1: 25/25 insertadas, reconocimiento 100%
camara 2: 25/25 insertadas, reconocimiento  92%
camara 3: 25/25 insertadas, reconocimiento  92%
registro: 75 detecciones
entradas aplicadas -> Java:75  Python:75  Go:75   (idénticas)
```

**Prueba de failover** (lo que el enunciado pide: si un nodo cae, los demás siguen):
- Con Python de líder, lo maté a mitad de camino.
- **Go fue reelegido** líder (term 2).
- Las detecciones previas sobrevivieron (registro consistente).
- Insertar con el nuevo líder siguió funcionando.

### Bugs que encontré y corregí durante las pruebas

- El `logf` de Go pasaba mal los argumentos variádicos → separé el prefijo del
  nodo del formato.
- `PPID` es variable de solo lectura en zsh → renombré las variables de los scripts
  de prueba (era error del script, no del código).
- Un par de veces el "cluster no eligió líder" resultó ser que pasaba la lista de
  nodos sin comillas en bash y los espacios se colapsaban. El código estaba bien.

### Lo que es honesto aclarar del alcance

- El dataset son **figuras geométricas generadas**, no fotos de objetos reales. Es
  visión real sobre píxeles (la CNN aprende de verdad), reproducible sin internet.
  Para la demo con cámaras reales se cambia la fuente de frames; la CNN, el Raft y
  el registro no cambian.
- El cluster se probó en una sola máquina (localhost). Para la entrega hay que
  correrlo en **varias PCs en LAN/WIFI y en dos SO** (cambiar los 127.0.0.1 por las
  IP reales). El código ya escucha en `0.0.0.0`, así que está listo para eso.
