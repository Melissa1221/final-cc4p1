package main

import (
	"sync"
	"time"
)

type Deteccion struct {
	Tipo       string    `json:"tipo"`
	Referencia string    `json:"referencia_imagen"`
	FechaHora  time.Time `json:"fecha_hora"`
	CamaraID   string    `json:"camara_id"`
}

type LogEntry struct {
	Term      int
	Deteccion Deteccion
}

type MaquinaEstado struct {
	mu       sync.RWMutex
	registro []Deteccion
}

func NuevaMaquinaEstado() *MaquinaEstado {
	return &MaquinaEstado{
		registro: make([]Deteccion, 0),
	}
}

func (m *MaquinaEstado) AplicarEntrada(d Deteccion) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.registro = append(m.registro, d)
}

func (m *MaquinaEstado) ObtenerRegistro() []Deteccion {
	m.mu.RLock()
	defer m.mu.RUnlock()

	copia := make([]Deteccion, len(m.registro))
	copy(copia, m.registro)
	return copia
}
