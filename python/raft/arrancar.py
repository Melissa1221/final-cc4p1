# Arranca un nodo Raft en Python. Mismos argumentos que el ArrancarNodo de Java:
#   python3 raft/arrancar.py <miId> id:host:puerto id:host:puerto ...
#
# Ejemplo (nodo 2 de un cluster de 3):
#   python3 raft/arrancar.py 2  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003

import sys
import time

sys.path.insert(0, ".")
from raft.nodo import NodoRaft


def main():
    if len(sys.argv) < 3:
        print("uso: python3 raft/arrancar.py <miId> id:host:puerto ...")
        return
    mi_id = int(sys.argv[1])
    mi_puerto = None
    pares = []
    for spec in sys.argv[2:]:
        pid, host, pto = spec.split(":")
        pid, pto = int(pid), int(pto)
        if pid == mi_id:
            mi_puerto = pto
        else:
            pares.append((pid, host, pto))
    if mi_puerto is None:
        print(f"el id {mi_id} no esta en la lista")
        return
    nodo = NodoRaft(mi_id, mi_puerto, pares)
    nodo.iniciar()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        nodo.detener()


if __name__ == "__main__":
    main()
