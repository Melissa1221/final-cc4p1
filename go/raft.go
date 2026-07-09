package main

import (
	"sync"
)

type EstadoRaft int

const (
	Seguidor EstadoRaft = iota
	Candidato
	Lider
)

type NodoRaft struct {
	mu sync.Mutex

	currentTerm int
	votedFor    string
	log         []LogEntry

	commitIndex int
	lastApplied int
	estado      EstadoRaft

	maquina *MaquinaEstado

	puerto string
	peers  []string
}

func NuevoNodoRaft(puerto string, peers []string) *NodoRaft {
	return &NodoRaft{
		estado:  Seguidor,
		puerto:  puerto,
		peers:   peers,
		maquina: NuevaMaquinaEstado(),
		log:     make([]LogEntry, 0),
	}
}

func (n *NodoRaft) IniciarEleccion() {
	// Lógica de timeout aleatorio (150-300ms) y envío de RequestVote
}
