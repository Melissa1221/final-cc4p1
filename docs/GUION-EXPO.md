# Guion de exposicion (12-15 min, por diapositiva)

Presentacion en ingles (slides.pdf, 15 diapositivas). Reparto entre los 3, con lo
que dice cada uno y el tiempo aproximado. La demo en vivo va al final (slides
9-13). Total: ~13 min de expo + ~4 min de demo.

## Reparto general

| Bloque | Slides | Quien |
|---|---|---|
| Intro + problema + arquitectura | 1-5 | Melissa |
| Raft (consenso) + protocolo | 6-7 | Junior |
| Modelo de IA (CNN) | 8 | Andrew |
| Resultados + demo en vivo | 9-13 | los 3 (Melissa conduce) |
| Cierre | 14-15 | Melissa |

---

## Slide 1 — Portada (Melissa, 20 seg)
"Buenas, somos Melissa, Junior y Andrew. Nuestro proyecto es un sistema distribuido
de reconocimiento de objetos con IA y el algoritmo de consenso Raft, para el curso
de Concurrente y Distribuida."

## Slide 2 — The problem (Melissa, 1 min)
"El objetivo es reconocer objetos, animales o personas con un modelo de IA
entrenado, y que todo el registro sea consistente y tolerante a fallos usando Raft.
El sistema tiene cuatro partes: servidor de entrenamiento, servidor de testeo con
las camaras, el cliente vigilante, y el modulo de consenso."

## Slide 3 — Hard constraints (Melissa, 1 min)
"El profe puso reglas estrictas: solo sockets nativos, nada de websocket, MQ ni
frameworks, asi que Raft lo implementamos a mano sobre TCP. Tres lenguajes, uno por
integrante. Dos sistemas operativos. Hilos. Despliegue local sin internet. Y solo
librerias base, con NumPy permitido para la red neuronal."

## Slide 4 — Team and languages (Melissa, 40 seg)
"Cada uno tomo un lenguaje: yo Java con el nucleo de Raft, el entrenamiento y la
interfaz; Junior Go con su nodo Raft y la maquina de estado del registro; y Andrew
Python con la CNN y el servidor de testeo. Lo clave: los tres nodos hablan el mismo
protocolo de texto, asi que forman un solo cluster aunque sean lenguajes distintos."

## Slide 5 — System architecture (Melissa, 1 min)
"Este es el flujo: las camaras alimentan al servidor de testeo, que corre la CNN.
Cada deteccion se manda al lider del cluster Raft, que la replica en los tres nodos.
El cliente vigilante lee ese registro replicado. Toda escritura pasa por el lider y
se confirma cuando la mayoria la copio."
-> Aqui Melissa pasa la palabra a Junior.

## Slide 6 — Raft: leader election and log replication (Junior, 2 min)
"Raft resuelve como varias maquinas se ponen de acuerdo aunque una falle. Hay tres
estados: seguidor, candidato y lider. Se elige lider con un timeout aleatorio de
150 a 300 ms para evitar empates. El lider recibe cada deteccion, la mete en su log
y la replica; una entrada se confirma solo cuando esta en la mayoria. Si el lider
cae, los otros reeligen uno nuevo. Implementamos esto a mano, siguiendo el paper de
Raft que vimos en clase."

## Slide 7 — The text protocol (Junior, 1.5 min)
"Todo va por este protocolo de texto, una linea por mensaje con campos separados
por barra. RequestVote y AppendEntries para el consenso; NUEVA_DETECCION para
insertar; LEER_REGISTRO para que el vigilante lea. Como Java, Python y Go usan
exactamente este formato, un lider Python puede replicar en un seguidor Java o Go
sin ninguna traduccion."
-> Junior pasa la palabra a Andrew.

## Slide 8 — The CNN (Andrew, 2 min)
"La IA es una red convolucional que escribimos desde cero con NumPy, sin
TensorFlow ni PyTorch. Reconoce 10 clases reales de CIFAR-10: avion, auto, gato,
perro, barco, camion, etc. Tiene dos capas convolucionales, pooling y una capa
densa con softmax, con forward y backward implementados a mano. La entrenamos antes
y guardamos los pesos, asi corre sin internet. Da 40.9% en el test, que para una
red chica hecha a mano sobre objetos reales es cuatro veces mejor que el azar.
Ademas el entrenamiento es distribuido: repartimos la carga entre varios procesos
en paralelo."
-> Andrew pasa la palabra a Melissa para la demo.

## Slides 9-13 — Resultados y DEMO EN VIVO (los 3, Melissa conduce, ~4 min)

Aqui NO solo leen las slides: hacen la demo real. Melissa conduce y va mostrando.

**Slide 9 (End-to-end) + Slide 10 (Fault tolerance):** mientras se levantan los nodos.
"Vamos a mostrarlo corriendo. Cada uno levanta su nodo." (los 3 corren su comando
del GUION-DEMO). "Ya eligieron lider. Ahora el servidor de video y la camara..."

**Slide 11 (Recognition) + Slide 12 (Watcher desktop):**
"La camara reconoce los objetos en vivo y cada deteccion aparece aca en el vigilante,
con su foto, tipo, camara y hora." (mostrar el Vigilante con las detecciones).

**Slide 13 (Mobile):** "Y el mismo registro se ve desde la app movil." (mostrar el
movil o el emulador).

**El momento estrella (failover):** "Ahora matamos el nodo lider..." (el del lider
corta con Ctrl+C). "...y vean: otro nodo es reelegido lider y el registro sigue
intacto. Eso es la tolerancia a fallos del consenso Raft, funcionando entre tres
maquinas distintas."

## Slide 14 — (parte del cierre, Melissa, 30 seg)
"En resumen: cumplimos las tres partes: reconocimiento con IA entrenada, consenso
Raft tolerante a fallos, y tres lenguajes interoperando solo con sockets nativos."

## Slide 15 — Thank you (Melissa, 15 seg)
"Gracias, quedamos atentos a sus preguntas."

---

## Reglas para que salga bien

- **Ensayen la demo una vez antes.** Que cada uno sepa su comando de memoria
  (ver docs/GUION-DEMO.md).
- **Melissa conduce la demo** (tiene la camara, el video y el vigilante). Junior y
  Andrew solo levantan su nodo y, en el momento del failover, el que sea lider corta.
- Si la demo falla en vivo: usar el modo seguro (`camara_demo.py`) o correr los 3
  nodos en una sola laptop con `127.0.0.1`. Nunca se queden en blanco: tienen los
  slides de respaldo.
- **Tiempo:** si van cortos, la demo se recorta a: levantar nodos -> mostrar
  vigilante con detecciones -> matar lider. Eso es lo que mas evalua el profe.

## Posibles preguntas del profe y como responder

- "Por que solo 40.9%?" -> "Es una CNN chica hecha a mano en NumPy sobre CIFAR-10,
  sin frameworks ni pre-entrenamiento. 40.9% es honesto; el azar es 10%."
- "Como se que no usaron frameworks?" -> mostrar el codigo del socket crudo y el
  protocolo de texto.
- "Y si caen dos nodos?" -> "Con 3 nodos, Raft tolera 1 caida (mayoria de 2). Con 5
  nodos toleraria 2. Es configurable."
- "Corre en dos sistemas operativos?" -> "Si, los nodos escuchan en 0.0.0.0; en la
  demo corren en Mac y Windows/Linux."
