#!/usr/bin/env bash
# Compila y corre el Cliente Vigilante (Java + FlatLaf).
# Sin argumentos: modo demo (datos de ejemplo).
# Con nodos: se conecta al cluster y refresca en vivo.
#   ./scripts/correr-vigilante.sh 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
JAVA="$RAIZ/java"
JAR="$JAVA/lib/flatlaf-3.4.1.jar"

mkdir -p "$JAVA/out"
# compila el Vigilante Y el paquete raft (que el Vigilante importa)
javac -cp "$JAR" -d "$JAVA/out" \
  "$JAVA"/src/raft/*.java "$JAVA"/src/vigilante/*.java
java -cp "$JAVA/out:$JAR" vigilante.Vigilante "$@"
