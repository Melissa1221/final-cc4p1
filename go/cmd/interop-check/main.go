// Utilidad temporal para verificar interoperabilidad manual con nodos Java o
// Python ya levantados: se le pasa la lista de nodos del cluster (mismo
// formato que arrancar-nodo) y hace un ciclo insertar + leer.
package main

import (
	"fmt"
	"os"
	"time"

	"raftgo/internal/raft"
)

func main() {
	nodos := raft.ParsearNodos(os.Args[1:])
	cli := raft.NuevoClienteCluster(nodos)

	ok := cli.Insertar("Perro", "img-go.png", "09/07/2026 10:00", "Camara Go")
	fmt.Println("insertar desde Go:", ok)

	time.Sleep(600 * time.Millisecond)

	reg := cli.LeerRegistro()
	fmt.Println("registro leido (", len(reg), "detecciones ):")
	for _, d := range reg {
		fmt.Println(" -", d)
	}
}
