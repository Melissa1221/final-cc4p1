#!/usr/bin/env bash
# Compila y corre el Cliente Vigilante (Java + FlatLaf).
# Uso: ./scripts/correr-vigilante.sh   (desde la raiz del repo)
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
JAVA="$RAIZ/java"
JAR="$JAVA/lib/flatlaf-3.4.1.jar"

mkdir -p "$JAVA/out"
javac -cp "$JAR" -d "$JAVA/out" "$JAVA/src/vigilante/Vigilante.java"
java -cp "$JAVA/out:$JAR" vigilante.Vigilante
