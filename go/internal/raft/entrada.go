package raft

import (
	"strconv"
	"strings"
)

// Entrada es una entrada del log replicado: el term en que se creo y el
// comando (una deteccion serializada como texto). El indice es la posicion
// en el log (1-based, como en el paper del profe) y vive fuera de la
// entrada, en la posicion dentro del slice.
type Entrada struct {
	Term    int
	Comando string
}

// Serializar produce  term,comando  (el comando ya viene sin ; ni | conflictivos).
func (e Entrada) Serializar() string {
	return strconv.Itoa(e.Term) + SepCampoEntrada + e.Comando
}

// DeserializarEntrada interpreta el formato de Serializar.
func DeserializarEntrada(s string) Entrada {
	coma := strings.Index(s, SepCampoEntrada)
	term, _ := strconv.Atoi(s[:coma])
	return Entrada{Term: term, Comando: s[coma+1:]}
}
