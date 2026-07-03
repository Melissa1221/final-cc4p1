# Final CC4P1 — Reconocimiento de objetos distribuido con Raft

Sistema distribuido para reconocer objetos, animales o personas con un modelo de IA
entrenado, tolerante a fallos mediante consenso Raft. Curso CC4P1, ciclo 2026-1.

Grupo: Melissa Iman (Java), Andrew Inga (Python), Junior Ortega (Go).

La distribucion del trabajo de cada uno esta en [PLANIFICACION.md](PLANIFICACION.md).

## Estructura

```
java/        Nodo de entrenamiento + Cliente Vigilante (UI) + nodo Raft  (Melissa)
  src/raft/          nucleo Raft: eleccion, replicacion, commit por mayoria
  src/entrenamiento/ entrenamiento distribuido con hilos + persistencia de pesos
  src/vigilante/     interfaz Swing + FlatLaf conectada al cluster
python/      Servidor de Testeo + CNN (NumPy) + nodo Raft                (Andrew)
go/          Maquina de estado del registro + nodo Raft                  (Junior)
scripts/     Scripts para levantar cada parte
docs/        Diagramas, informe y presentacion
```

## Parte de Java (ya funciona end-to-end)

El nucleo Raft, el entrenamiento distribuido y el Vigilante ya estan implementados
y probados. Todo con sockets TCP crudos e hilos, sin frameworks.

Probar el nucleo Raft de una (levanta 3 nodos en un proceso, inserta detecciones,
mata al lider, verifica reeleccion y consistencia):

```bash
cd java && javac -cp lib/flatlaf-3.4.1.jar -d out src/raft/*.java && java -cp out raft.PruebaE2E
```

Levantar el cluster de 3 nodos (procesos separados) y conectar el Vigilante:

```bash
./scripts/levantar-cluster.sh
# en otra terminal:
java -cp java/out:java/lib/flatlaf-3.4.1.jar vigilante.Vigilante \
  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

Probar el entrenamiento distribuido (reparte 10000 muestras entre 4 hilos, guarda
y recarga los pesos):

```bash
cd java && java -cp out entrenamiento.Entrenador
```

El protocolo Raft en texto que comparten los tres lenguajes esta documentado
arriba de `java/src/raft/Protocolo.java`. Andrew y Junior deben respetar ese
formato para que sus nodos interoperen con los de Java.

## Requisitos

- Java 8 o superior (probado en OpenJDK 26).
- Python 3 con NumPy.
- Go 1.x.

Todo corre en local, sin internet en tiempo de ejecucion. El unico JAR externo es
FlatLaf (el look de la interfaz), que ya viene versionado en `java/lib/` — no se
descarga nada al correr.

## Correr el Cliente Vigilante (interfaz)

Es la ventana que muestra el registro de detecciones. Tiene dos modos:

- Sin argumentos: modo demo con datos de ejemplo, solo para ver el diseno.
- Con la lista de nodos: se conecta al cluster y refresca el registro en vivo cada
  segundo (el indicador de arriba pasa a "sin conexion" en rojo si el cluster no
  responde).

Modo demo, en Linux o Mac:

```bash
./scripts/correr-vigilante.sh
```

En Windows:

```bat
scripts\correr-vigilante.bat
```

Conectado al cluster (ver la seccion de arriba para levantar los nodos primero):

```bash
java -cp java/out:java/lib/flatlaf-3.4.1.jar vigilante.Vigilante \
  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

Abre una ventana con la tabla de detecciones (tipo, camara, fecha y hora), un
titulo, el indicador de conexion y el contador de registros abajo.

## Por que Swing + FlatLaf

El curso suele pedir la interfaz en Java desktop. Swing solo se ve anticuado, asi
que le sumamos FlatLaf: un look plano y moderno con un solo JAR local, sin internet.
El archivo `java/src/vigilante/Vigilante.java` es la referencia de estilo del grupo
(espaciado en multiplos de 8, jerarquia de tipografia, paleta sobria, filas
alineadas). Toda la UI del proyecto debe seguir ese estandar.

## Siguientes pasos

Cada quien arranca su parte segun [PLANIFICACION.md](PLANIFICACION.md). Lo primero
es el Bloque 0: acordar entre los tres el protocolo Raft en texto, el formato de la
deteccion y los puertos de cada nodo.
