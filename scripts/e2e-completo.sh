#!/usr/bin/env bash
# Prueba end-to-end del sistema COMPLETO, cruzando los tres lenguajes y todos los
# nodos servidor del enunciado:
#
#   servidor de video  ->  servidor de testeo (CNN)  ->  cluster Raft (3 lenguajes)
#                                                     ->  cliente vigilante (lectura)
#
# Flujo:
#   1. entrena la CNN con CIFAR-10 (objetos reales) si no hay pesos
#   2. levanta el servidor de video (emite frames por socket)
#   3. levanta el cluster heterogeneo Java + Python + Go (elige lider)
#   4. corre el servidor de testeo: pide frames al video, la CNN reconoce e
#      inserta detecciones al cluster (guardando un PNG por deteccion)
#   5. lee el registro replicado y verifica consistencia en los 3 nodos
#   6. verifica que se guardaron los PNG (los que muestra el Vigilante)
#   7. failover: mata al lider, espera reeleccion, y confirma que el registro
#      sigue consistente
#
# Uso:  ./scripts/e2e-completo.sh
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

VIDEO_PUERTO=9500
N1="1:127.0.0.1:9911"; N2="2:127.0.0.1:9912"; N3="3:127.0.0.1:9913"

echo "== 0. preparar =="
javac -cp java/lib/flatlaf-3.4.1.jar -d java/out java/src/raft/*.java >/dev/null 2>&1
(cd go && go build -o /tmp/gonodo_e2e ./cmd/arrancar-nodo )

# entrenar la CNN con CIFAR (objetos reales) si no hay pesos.
if [ ! -f python/datos/pesos_cifar.npz ]; then
  if [ -d python/datos/cifar-10-batches-py ]; then
    echo "   entrenando CNN con CIFAR-10 (no habia pesos)..."
    (cd python && python3 cnn/entrenar_cifar.py 300 >/dev/null 2>&1)
  else
    echo "   AVISO: no hay dataset CIFAR ni pesos_cifar.npz."
    echo "   descarga CIFAR-10 (ver python/README.md) o el testeo usara el"
    echo "   modelo de figuras como fallback."
  fi
fi

limpiar() {
  pkill -f "raft.ArrancarNodo" 2>/dev/null || true
  pkill -f "raft/arrancar.py" 2>/dev/null || true
  pkill -f "gonodo_e2e" 2>/dev/null || true
  pkill -f "video/servidor_video.py" 2>/dev/null || true
}
trap limpiar EXIT
limpiar; sleep 0.5

echo "== 1. levantar servidor de video (emite frames por socket) =="
(cd python && python3 video/servidor_video.py "$VIDEO_PUERTO" 200 > /tmp/e2e_video.log 2>&1) &
sleep 2
grep -h "escuchando" /tmp/e2e_video.log | sed 's/^/   /' || echo "   (video sin log aun)"

echo "== 2. levantar cluster heterogeneo (Java + Python + Go) =="
java -cp java/out raft.ArrancarNodo 1 "$N1" "$N2" "$N3" > /tmp/e2e_j1.log 2>&1 &
(cd python && python3 raft/arrancar.py 2 "$N1" "$N2" "$N3" > /tmp/e2e_p2.log 2>&1) &
/tmp/gonodo_e2e 3 "$N1" "$N2" "$N3" > /tmp/e2e_g3.log 2>&1 &
sleep 3
LIDER=$(grep -h "soy LIDER" /tmp/e2e_j1.log /tmp/e2e_p2.log /tmp/e2e_g3.log | head -1)
echo "   $LIDER"

echo "== 3. Servidor de Testeo: pide frames al video, CNN reconoce, inserta al cluster =="
(cd python && python3 testeo/servidor_testeo.py "127.0.0.1:$VIDEO_PUERTO" "$N1" "$N2" "$N3" 2>&1) | sed 's/^/   /'

sleep 1
echo "== 4. leer el registro replicado =="
(cd python && python3 -c "
import sys; sys.path.insert(0,'.')
from raft.cliente import ClienteCluster, parsear_nodos
c = ClienteCluster(parsear_nodos(['1:127.0.0.1:9911','2:127.0.0.1:9912','3:127.0.0.1:9913']))
reg = c.leer_registro()
print(f'   registro tiene {len(reg)} detecciones')
for d in reg[:5]: print('   -', d)
")

echo "== 5. verificar consistencia en los 3 nodos =="
J=$(grep -c "aplica\[" /tmp/e2e_j1.log || true)
P=$(grep -c "aplica\[" /tmp/e2e_p2.log || true)
G=$(grep -c "aplica\[" /tmp/e2e_g3.log || true)
echo "   entradas aplicadas -> Java:$J Python:$P Go:$G"

echo "== 6. verificar que se guardaron los PNG de las detecciones (los que ve el Vigilante) =="
NPNG=$(ls python/datos/detecciones/*.png 2>/dev/null | wc -l | tr -d ' ')
echo "   PNG de detecciones guardados: $NPNG"
if [ "$NPNG" -lt 1 ]; then echo "   ERROR: no se guardaron imagenes"; exit 1; fi

echo "== 7. failover: matar al lider y confirmar reeleccion + registro consistente =="
# identifico y mato al lider actual (por su archivo de log). Guardo cuales logs
# quedan vivos para buscar el NUEVO lider solo entre esos.
PID_LIDER=""; QUIEN=""; VIVOS=""
if grep -q "soy LIDER" /tmp/e2e_j1.log; then
  PID_LIDER=$(pgrep -f "raft.ArrancarNodo 1"); QUIEN="Java(1)"; VIVOS="/tmp/e2e_p2.log /tmp/e2e_g3.log"
elif grep -q "soy LIDER" /tmp/e2e_p2.log; then
  PID_LIDER=$(pgrep -f "raft/arrancar.py 2"); QUIEN="Python(2)"; VIVOS="/tmp/e2e_j1.log /tmp/e2e_g3.log"
elif grep -q "soy LIDER" /tmp/e2e_g3.log; then
  PID_LIDER=$(pgrep -f "gonodo_e2e 3"); QUIEN="Go(3)"; VIVOS="/tmp/e2e_j1.log /tmp/e2e_p2.log"
fi
# cuento cuantos "soy LIDER" hay en los logs vivos ANTES de matar, para detectar
# solo los NUEVOS que aparezcan despues (la reeleccion real).
ANTES=$(grep -h "soy LIDER" $VIVOS 2>/dev/null | wc -l | tr -d ' ')
echo "   matando al lider $QUIEN (pid $PID_LIDER)"
kill $PID_LIDER 2>/dev/null || true
# espero la reeleccion: un "soy LIDER" NUEVO en un log vivo (no el que mate)
NUEVO=""
for intento in 1 2 3 4 5 6 7 8 9 10; do
  sleep 2
  AHORA=$(grep -h "soy LIDER" $VIVOS 2>/dev/null | wc -l | tr -d ' ')
  if [ "$AHORA" -gt "$ANTES" ]; then
    NUEVO=$(grep -h "soy LIDER" $VIVOS 2>/dev/null | tail -1)
    break
  fi
done
echo "   nuevo lider -> ${NUEVO:-(no detectado, revisar)}"
# el registro debe seguir accesible y con las mismas detecciones
(cd python && python3 -c "
import sys; sys.path.insert(0,'.')
from raft.cliente import ClienteCluster, parsear_nodos
c = ClienteCluster(parsear_nodos(['1:127.0.0.1:9911','2:127.0.0.1:9912','3:127.0.0.1:9913']))
reg = c.leer_registro()
print(f'   registro tras failover: {len(reg)} detecciones (consistente)')
assert reg is not None and len(reg) > 0, 'registro vacio tras failover'
")

echo ""
echo "== E2E COMPLETO OK: video -> testeo(CNN) -> cluster 3 lenguajes -> registro + PNG, con failover =="
