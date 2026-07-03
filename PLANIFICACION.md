# Planificacion — quien hace que

Grupo de 3. Cada uno es dueno de un lenguaje y un subsistema, pero los tres
implementan su propia copia del nucleo Raft en su lenguaje, porque el enunciado
pide que el consenso corra en un cluster multi-lenguaje.

No hay reparto por dias. El orden es por dependencias: primero el Bloque 0 y el
nucleo Raft (todo depende de eso), y de ahi cada uno avanza en paralelo.

## Reglas duras del profe (si se rompen, es cero en ese modulo)

- Solo sockets nativos de cada lenguaje. Nada de websocket, socketio, frameworks,
  RabbitMQ, MQ ni librerias de comunicacion. Raft se implementa a mano sobre TCP.
- Tres lenguajes, un nodo por alumno (Java, Python, Go).
- Dos sistemas operativos distintos (Linux y Windows) corriendo los mismos lenguajes.
- El modulo de entrenamiento minimo en Java 8 o superior.
- Minimo 3 camaras IP identificando objetos todo el tiempo.
- Hilos para el rendimiento y para no corromper el registro.
- Desplegar en local sin internet, en LAN y WIFI, en varias PCs reales.
- Solo librerias base del lenguaje. NumPy si esta permitido para la CNN.

## Bloque 0 — lo primero, los tres juntos

Antes de codear nada por separado, acordar entre los tres:

- El protocolo Raft en texto: como se ven los mensajes RequestVote y AppendEntries,
  identicos entre Java, Python y Go.
- El formato de una deteccion: tipo, referencia a la imagen, fecha y hora, camara.
- Los puertos de cada nodo y el mapa del cluster.

Melissa documenta el protocolo porque su nodo Java es la referencia.

## Melissa — Java

- Cliente Vigilante (la interfaz, Swing + FlatLaf). Ya hay una version base en
  `java/src/vigilante/Vigilante.java` que sirve de estandar de UI para el grupo.
- Nodo de entrenamiento: desarrollar el modelo y sus pesos, repartir la carga de
  entrenamiento entre nodos con hilos (paralelo tipo CPU), y persistir los pesos.
- Nucleo Raft en Java: estados, terms, eleccion con timeout aleatorio (150-300 ms),
  replicacion y commit por mayoria. Es la referencia del protocolo.
- En el informe: arquitectura, Raft y entrenamiento distribuido. Diagrama de protocolo.

## Andrew — Python

- CNN propia con NumPy, entrenada desde cero con 4 o 5 clases (imagenes chicas,
  32x32). Guardar los pesos a disco.
- Servidor de Testeo: cargar los pesos, procesar los frames de las camaras,
  reconocer solo los objetos entrenados, recortar y guardar la imagen, y por cada
  deteccion mandar el comando al lider del cluster.
- Manejar 3 camaras con un hilo por camara.
- Nucleo Raft en Python (socket + threading de la stdlib), interoperando con Java y Go.
- En el informe: vision e IA, y el benchmark de eficiencia por camara.

## Junior — Go

- Maquina de estado del registro (net + goroutines + mutex para no corromper datos):
  aplicar las entradas cometidas en orden y servir lecturas consistentes al Vigilante.
- Nucleo Raft en Go: eleccion y replicacion, interoperando con Java y Python.
- Nota: la interfaz del Vigilante la hace Melissa en Java (asi suele ser en el curso).
  Tu parte es el registro y el consenso del lado Go, mas tu nodo Raft.
- En el informe: cliente vigilante, registro y la demo de tolerancia a fallos.
  Diagrama de arquitectura.

## Bloque de integracion — los tres

- Levantar el cluster completo (mejor 5 nodos, tolera 2 caidas).
- Demo de tolerancia: matar el lider y ver la reeleccion; matar un nodo de testeo y
  ver que el registro sigue consistente.
- Correr en LAN y WIFI con varias PCs, y en dos sistemas operativos.
- Verificar el consenso con las 3 camaras detectando todo el tiempo.

## Entregables — los tres

- Fuentes por lenguaje, limpias (sin binarios, sin el motor del lenguaje, sin temporales).
- PDF de informe (cada uno su seccion) y PDF de presentacion.
- Diagrama de arquitectura y diagrama de protocolo.
- Todo comprimido y subido a Univirtual.
