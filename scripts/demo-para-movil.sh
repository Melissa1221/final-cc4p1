#!/usr/bin/env bash
# Levanta el cluster + video + testeo y LO DEJA CORRIENDO para que el cliente
# movil (o el Vigilante desktop) se conecte. Los nodos escuchan en 0.0.0.0, asi
# que el emulador de Android puede llegar por la IP de la Mac (o 10.0.2.2).
#
# Uso:  ./scripts/demo-para-movil.sh
# Corta con Ctrl+C cuando termines.
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

echo "== preparando =="
javac -cp java/lib/flatlaf-3.4.1.jar -d java/out java/src/raft/*.java java/src/vigilante/*.java >/dev/null 2>&1
(cd go && go build -o /tmp/gonodo_movil ./cmd/arrancar-nodo)

limpiar() {
  pkill -f "raft.ArrancarNodo" 2>/dev/null || true
  pkill -f "raft/arrancar.py" 2>/dev/null || true
  pkill -f "gonodo_movil" 2>/dev/null || true
  pkill -f "video/servidor_video.py" 2>/dev/null || true
}
trap limpiar EXIT
limpiar; sleep 0.5

# escuchan en 0.0.0.0; el cluster se anuncia con la IP de la Mac para que el
# emulador de Android pueda alcanzarlo.
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)
N1="1:$IP:9001"; N2="2:$IP:9002"; N3="3:$IP:9003"

echo "== levantando cluster (Java + Python + Go) en $IP =="
java -cp java/out raft.ArrancarNodo 1 "$N1" "$N2" "$N3" > /tmp/dm_j.log 2>&1 &
(cd python && python3 raft/arrancar.py 2 "$N1" "$N2" "$N3" > /tmp/dm_p.log 2>&1) &
/tmp/gonodo_movil 3 "$N1" "$N2" "$N3" > /tmp/dm_g.log 2>&1 &
sleep 3

echo "== servidor de video + testeo (llena el registro) =="
(cd python && python3 video/servidor_video.py 9500 > /tmp/dm_v.log 2>&1) &
sleep 2
(cd python && python3 testeo/servidor_testeo.py "$IP:9500" "$N1" "$N2" "$N3" > /tmp/dm_t.log 2>&1) &
sleep 6

echo ""
echo "======================================================================"
echo " CLUSTER CORRIENDO. Para el cliente movil, en la app pon estos nodos:"
echo ""
echo "   1:$IP:9001, 2:$IP:9002, 3:$IP:9003"
echo ""
echo " (si el emulador no llega por esa IP, prueba con 10.0.2.2 en vez de $IP)"
echo ""
echo " Para el Vigilante DESKTOP, en otra terminal:"
echo "   java -cp java/out:java/lib/flatlaf-3.4.1.jar vigilante.Vigilante $N1 $N2 $N3"
echo ""
echo " Ctrl+C para apagar todo."
echo "======================================================================"

# mantener vivo
while true; do sleep 5; done
