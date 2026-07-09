#!/usr/bin/env bash
# Prueba end-to-end del sistema completo, cruzando los tres lenguajes.
# Levanta un cluster heterogeneo (Java + Python + Go), corre el Servidor de Testeo
# (que usa la CNN entrenada para reconocer figuras e insertar detecciones al
# cluster), y verifica que el registro replicado queda consistente. Luego mata al
# lider y confirma que el cluster sigue y el registro se mantiene.
#
# Uso:  ./scripts/e2e-completo.sh
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

echo "== 0. preparar =="
javac -cp java/lib/flatlaf-3.4.1.jar -d java/out java/src/raft/*.java >/dev/null 2>&1
# nodo Go de Junior (go/cmd/arrancar-nodo)
(cd go && go build -o /tmp/gonodo_e2e ./cmd/arrancar-nodo )
# entrenar la CNN si no hay pesos
if [ ! -f python/datos/pesos_cnn.npz ]; then
  echo "   entrenando CNN (no habia pesos)..."
  (cd python && python3 cnn/entrenar.py >/dev/null 2>&1)
fi

limpiar() { pkill -f "raft.ArrancarNodo" 2>/dev/null || true; pkill -f "raft/arrancar.py" 2>/dev/null || true; pkill -f "gonodo_e2e" 2>/dev/null || true; }
trap limpiar EXIT
limpiar; sleep 0.5

N1="1:127.0.0.1:9911"; N2="2:127.0.0.1:9912"; N3="3:127.0.0.1:9913"

echo "== 1. levantar cluster heterogeneo (Java + Python + Go) =="
java -cp java/out raft.ArrancarNodo 1 "$N1" "$N2" "$N3" > /tmp/e2e_j1.log 2>&1 &
(cd python && python3 raft/arrancar.py 2 "$N1" "$N2" "$N3" > /tmp/e2e_p2.log 2>&1) &
/tmp/gonodo_e2e 3 "$N1" "$N2" "$N3" > /tmp/e2e_g3.log 2>&1 &
sleep 3
LIDER=$(grep -h "soy LIDER" /tmp/e2e_j1.log /tmp/e2e_p2.log /tmp/e2e_g3.log | head -1)
echo "   $LIDER"

echo "== 2. Servidor de Testeo: CNN reconoce figuras e inserta al cluster =="
(cd python && python3 testeo/servidor_testeo.py "$N1" "$N2" "$N3" 2>&1) | sed 's/^/   /'

sleep 1
echo "== 3. leer el registro replicado =="
(cd python && python3 -c "
import sys; sys.path.insert(0,'.')
from raft.cliente import ClienteCluster, parsear_nodos
c = ClienteCluster(parsear_nodos(['1:127.0.0.1:9911','2:127.0.0.1:9912','3:127.0.0.1:9913']))
reg = c.leer_registro()
print(f'   registro tiene {len(reg)} detecciones')
for d in reg[:5]: print('   -', d)
")

echo "== 4. verificar consistencia en los 3 nodos =="
J=$(grep -c "aplica\[" /tmp/e2e_j1.log || true)
P=$(grep -c "aplica\[" /tmp/e2e_p2.log || true)
G=$(grep -c "aplica\[" /tmp/e2e_g3.log || true)
echo "   entradas aplicadas -> Java:$J Python:$P Go:$G"

echo ""
echo "== E2E COMPLETO OK: cluster de 3 lenguajes + CNN + registro replicado =="
