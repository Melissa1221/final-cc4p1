package main

import (
	"encoding/json"
	"fmt"
	"net"
)

func (n *NodoRaft) IniciarServidor() {
	listener, err := net.Listen("tcp", ":"+n.puerto)
	if err != nil {
		fmt.Printf("Error al iniciar TCP en puerto %s: %v\n", n.puerto, err)
		return
	}
	defer listener.Close()
	fmt.Printf("Nodo Raft (Go) escuchando en el puerto %s...\n", n.puerto)

	for {
		conn, err := listener.Accept()
		if err != nil {
			continue
		}
		go n.manejarConexion(conn)
	}
}

func (n *NodoRaft) manejarConexion(conn net.Conn) {
	defer conn.Close()

	decoder := json.NewDecoder(conn)
	var mensaje map[string]interface{}

	if err := decoder.Decode(&mensaje); err != nil {
		return
	}

	tipoMsg, ok := mensaje["tipo"].(string)
	if !ok {
		return
	}

	n.mu.Lock()
	defer n.mu.Unlock()

	switch tipoMsg {
	case "RequestVote":
		fmt.Println("Petición de voto recibida")
	case "AppendEntries":
		fmt.Println("Heartbeat o nueva entrada recibida")
	}
}
