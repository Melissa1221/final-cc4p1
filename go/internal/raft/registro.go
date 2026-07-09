package raft

import "sync"

// RegistroDetecciones es la maquina de estado replicada: el registro de
// detecciones ya aplicado (solo entradas del log que el cluster ya cometio
// por mayoria). Es la pieza que le sirve datos consistentes al Vigilante.
// Un mutex propio evita que una lectura concurrente vea un estado a medio
// escribir mientras el nucleo Raft aplica una nueva entrada.
type RegistroDetecciones struct {
	mu          sync.Mutex
	detecciones []string
}

// Aplicar agrega un comando ya cometido, en orden. Debe llamarse una sola
// vez por indice de log y siempre en orden creciente (lo garantiza NodoRaft).
func (r *RegistroDetecciones) Aplicar(comando string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.detecciones = append(r.detecciones, comando)
}

// Snapshot devuelve una copia del registro tal cual esta en este instante,
// para servir una lectura consistente sin bloquear al que sigue aplicando.
func (r *RegistroDetecciones) Snapshot() []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]string, len(r.detecciones))
	copy(out, r.detecciones)
	return out
}

// Len devuelve cuantas detecciones hay aplicadas.
func (r *RegistroDetecciones) Len() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.detecciones)
}
