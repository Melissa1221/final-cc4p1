# Final CC4P1 — Reconocimiento de objetos distribuido con Raft

Sistema distribuido para reconocer objetos, animales o personas con un modelo de IA
entrenado, tolerante a fallos mediante consenso Raft. Curso CC4P1, ciclo 2026-1.

Grupo: Melissa Iman (Java), Andrew Inga (Python), Junior Ortega (Go).

La distribucion del trabajo de cada uno esta en [PLANIFICACION.md](PLANIFICACION.md).

## Estructura

```
java/        Nodo de entrenamiento + Cliente Vigilante (UI) + nodo Raft  (Melissa)
python/      Servidor de Testeo + CNN (NumPy) + nodo Raft                (Andrew)
go/          Maquina de estado del registro + nodo Raft                  (Junior)
scripts/     Scripts para levantar cada parte
docs/        Diagramas, informe y presentacion
```

## Requisitos

- Java 8 o superior (probado en OpenJDK 26).
- Python 3 con NumPy.
- Go 1.x.

Todo corre en local, sin internet en tiempo de ejecucion. El unico JAR externo es
FlatLaf (el look de la interfaz), que ya viene versionado en `java/lib/` — no se
descarga nada al correr.

## Correr el Cliente Vigilante (interfaz)

Es la ventana que muestra el registro de detecciones. Ahora trae datos de ejemplo
para ver el diseno; luego se conecta al cluster.

En Linux o Mac:

```bash
./scripts/correr-vigilante.sh
```

En Windows:

```bat
scripts\correr-vigilante.bat
```

Debe abrir una ventana con la tabla de detecciones (tipo, camara, fecha y hora),
un titulo, el indicador "en vivo" y el contador de registros abajo.

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
