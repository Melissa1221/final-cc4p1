// Package raft implementa el nucleo Raft y el registro de detecciones del
// nodo Go (Junior). Ver PLANIFICACION.md.
package raft

import (
	"fmt"
	"strings"
)

// Protocolo Raft en texto plano sobre TCP crudo. Un mensaje por linea, campos
// separados por |. Sin frameworks, solo sockets (net.Listen / net.Dial).
// Este formato lo comparten los tres lenguajes (Java, Python, Go) y esta
// documentado en java/src/raft/Protocolo.java (Melissa, referencia).
//
// Mensajes de Raft (entre nodos):
//
//	REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
//	VOTE|term|otorgado(1/0)
//	APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
//	APPEND_OK|term|exito(1/0)|matchIndex
//
//	"entradas" va vacio en los heartbeats. Si trae datos, es una lista de
//	entradas separadas por ; y cada entrada es  term,comando  (el comando a
//	su vez usa comas internas escapadas por el que arma la deteccion).
//
// Mensajes de cliente (servidor de testeo / vigilante hacia el cluster):
//
//	NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara     -> inserta una deteccion
//	LEER_REGISTRO                                        -> pide todo el registro
//	REGISTRO|det1;det2;det3;...                          -> respuesta al vigilante
//	REDIRECT|hostLider:puertoLider                       -> si contactaron un seguidor
//	OK                                                   -> insercion aceptada
const (
	SepEntradas     = ";"
	SepCampoEntrada = ","

	RequestVote    = "REQUEST_VOTE"
	Vote           = "VOTE"
	Append         = "APPEND"
	AppendOk       = "APPEND_OK"
	NuevaDeteccion = "NUEVA_DETECCION"
	LeerRegistro   = "LEER_REGISTRO"
	Registro       = "REGISTRO"
	Redirect       = "REDIRECT"
	Ok             = "OK"
)

// Partir separa una linea del protocolo en sus campos (por |).
func Partir(linea string) []string {
	return strings.Split(linea, "|")
}

// Unir arma una linea del protocolo a partir de sus campos.
func Unir(campos ...any) string {
	var sb strings.Builder
	for i, c := range campos {
		if i > 0 {
			sb.WriteByte('|')
		}
		sb.WriteString(toString(c))
	}
	return sb.String()
}

func toString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}
