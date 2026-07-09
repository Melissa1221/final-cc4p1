package main

import (
	"os"
)

func main() {
	puerto := "8080"
	if len(os.Args) > 1 {
		puerto = os.Args[1]
	}

	// IPs de los nodos en Java y Python
	peers := []string{"192.168.1.10:8081", "192.168.1.11:8082"}

	nodo := NuevoNodoRaft(puerto, peers)

	go nodo.IniciarServidor()

	// Evita que el programa termine
	select {}
}
