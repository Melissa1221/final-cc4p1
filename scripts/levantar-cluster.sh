#!/usr/bin/env bash
# Levanta un cluster Raft de 3 nodos Java en la misma maquina (para pruebas).
# En LAN, cambia los 127.0.0.1 por las IP reales de cada PC y corre un nodo por PC.
# Uso: ./scripts/levantar-cluster.sh
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$RAIZ/java/out"
JAR="$RAIZ/java/lib/flatlaf-3.4.1.jar"

# compilar si hace falta
mkdir -p "$OUT"
javac -cp "$JAR" -d "$OUT" "$RAIZ"/java/src/raft/*.java "$RAIZ"/java/src/entrenamiento/*.java "$RAIZ"/java/src/vigilante/*.java

NODOS="1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003"

echo "levantando 3 nodos..."
for id in 1 2 3; do
  java -cp "$OUT" raft.ArrancarNodo $id $NODOS &
  echo "  nodo $id (pid $!)"
done
echo ""
echo "cluster arriba. Para el Vigilante en otra terminal:"
echo "  java -cp java/out:java/lib/flatlaf-3.4.1.jar vigilante.Vigilante $NODOS"
echo ""
echo "Ctrl+C para detener todos los nodos."
wait
