// Comando arrancar-nodo levanta un nodo Raft en Go. Se le pasa el id de este
// nodo y la lista de todos los nodos del cluster como id:host:puerto,
// exactamente igual que java.raft.ArrancarNodo (equivalente Go).
//
// Ejemplo (cluster de 3, en la misma maquina, mezclando lenguajes):
//
//	arrancar-nodo 3 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
//
// En LAN se cambian los 127.0.0.1 por las IP reales de cada PC.
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"raftgo/internal/raft"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println("uso: arrancar-nodo <miId> <id:host:puerto> ...")
		os.Exit(1)
	}

	miID, err := strconv.Atoi(os.Args[1])
	if err != nil {
		fmt.Println("miId invalido:", os.Args[1])
		os.Exit(1)
	}

	miPuerto := -1
	var pares []raft.Par
	for _, spec := range os.Args[2:] {
		p := strings.Split(spec, ":")
		if len(p) != 3 {
			fmt.Println("spec invalida (esperaba id:host:puerto):", spec)
			os.Exit(1)
		}
		id, err1 := strconv.Atoi(p[0])
		puerto, err2 := strconv.Atoi(p[2])
		if err1 != nil || err2 != nil {
			fmt.Println("spec invalida (esperaba id:host:puerto):", spec)
			os.Exit(1)
		}
		if id == miID {
			miPuerto = puerto
		} else {
			pares = append(pares, raft.Par{ID: id, Host: p[1], Puerto: puerto})
		}
	}
	if miPuerto < 0 {
		fmt.Printf("el id %d no aparece en la lista de nodos\n", miID)
		os.Exit(1)
	}

	nodo := raft.NuevoNodo(miID, miPuerto, pares)
	if err := nodo.Iniciar(); err != nil {
		fmt.Println("error al iniciar el nodo:", err)
		os.Exit(1)
	}
	select {} // el proceso se queda vivo mientras corren las goroutines
}
