package raft

import "strconv"

// Par es la direccion host:puerto de otro nodo del cluster. Simple, sin
// librerias externas (equivalente a Par.java).
type Par struct {
	ID     int
	Host   string
	Puerto int
}

func (p Par) Direccion() string {
	return p.Host + ":" + strconv.Itoa(p.Puerto)
}
