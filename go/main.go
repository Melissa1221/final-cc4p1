// Arranca un nodo Raft en Go. Mismos argumentos que Java y Python:
//
//	go run . <miId> id:host:puerto id:host:puerto ...
//
// Ejemplo (nodo 3 de un cluster de 3):
//
//	go run . 3  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"finalcc4p1/raft"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println("uso: go run . <miId> id:host:puerto ...")
		return
	}
	miID, _ := strconv.Atoi(os.Args[1])
	miPuerto := -1
	var pares []raft.Par
	for _, spec := range os.Args[2:] {
		p := strings.Split(spec, ":")
		id, _ := strconv.Atoi(p[0])
		pto, _ := strconv.Atoi(p[2])
		if id == miID {
			miPuerto = pto
		} else {
			pares = append(pares, raft.Par{ID: id, Host: p[1], Puerto: pto})
		}
	}
	if miPuerto < 0 {
		fmt.Printf("el id %d no esta en la lista\n", miID)
		return
	}
	nodo := raft.NuevoNodo(miID, miPuerto, pares)
	if err := nodo.Iniciar(); err != nil {
		fmt.Println("error al iniciar:", err)
		return
	}
	select {} // se queda vivo
}
