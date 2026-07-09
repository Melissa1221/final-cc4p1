package raft

import (
	"bufio"
	"log"
	"math/rand"
	"net"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Estado de un nodo Raft.
type Estado int

const (
	Seguidor Estado = iota
	Candidato
	Lider
)

const (
	heartbeatMS = 50 * time.Millisecond
	bucleTickMS = 15 * time.Millisecond
	dialTimeout = 120 * time.Millisecond
	rpcTimeout  = 200 * time.Millisecond
)

// NodoRaft es el nucleo Raft en Go sobre sockets TCP crudos (net.Listen /
// net.Dial) y goroutines. Implementa eleccion de lider, replicacion de log y
// seguridad, igual que java/src/raft/NodoRaft.java (la referencia del
// protocolo) y debe interoperar con los nodos Java y Python del cluster.
//
// Cada conexion entrante se atiende en su propia goroutine. Una goroutine
// aparte corre el bucle de tiempo (heartbeats si es lider, o dispara
// eleccion si es seguidor y vence el timeout). El mutex mu protege todo el
// estado mutable de Raft para que no se corrompa con el acceso concurrente.
type NodoRaft struct {
	id     int
	puerto int
	pares  []Par

	mu          sync.Mutex
	currentTerm int
	votedFor    *int
	logEntradas []Entrada // logEntradas[0] es indice 1

	estado          Estado
	commitIndex     int
	lastApplied     int
	liderActual     *int
	nextIndex       map[int]int
	matchIndex      map[int]int
	timeoutEleccion time.Duration
	ultimoContacto  time.Time

	registro *RegistroDetecciones

	rnd *rand.Rand

	corriendoMu sync.Mutex
	corriendo   bool
	listener    net.Listener
}

// NuevoNodo crea un nodo Raft. pares son los OTROS nodos del cluster (no se
// incluye a si mismo).
func NuevoNodo(id, puerto int, pares []Par) *NodoRaft {
	n := &NodoRaft{
		id:         id,
		puerto:     puerto,
		pares:      pares,
		estado:     Seguidor,
		nextIndex:  make(map[int]int),
		matchIndex: make(map[int]int),
		registro:   &RegistroDetecciones{},
		rnd:        rand.New(rand.NewSource(time.Now().UnixNano() + int64(id))),
	}
	n.nuevoTimeout()
	return n
}

// Registro expone la maquina de estado (para servir lecturas al Vigilante
// aun fuera del protocolo de texto, si hiciera falta desde el mismo proceso).
func (n *NodoRaft) Registro() *RegistroDetecciones { return n.registro }

func (n *NodoRaft) nuevoTimeout() {
	n.timeoutEleccion = time.Duration(150+n.rnd.Intn(151)) * time.Millisecond // [150,300]
}

// Iniciar abre el socket de escucha y arranca las goroutines de aceptar
// conexiones y del bucle de tiempo.
func (n *NodoRaft) Iniciar() error {
	l, err := net.Listen("tcp", ":"+strconv.Itoa(n.puerto))
	if err != nil {
		return err
	}
	n.listener = l

	n.mu.Lock()
	n.ultimoContacto = time.Now()
	n.mu.Unlock()

	n.corriendoMu.Lock()
	n.corriendo = true
	n.corriendoMu.Unlock()

	n.logf("nodo %d escuchando en puerto %d (seguidor)", n.id, n.puerto)

	go n.bucleAceptar()
	go n.bucleTiempo()
	return nil
}

// Detener cierra el socket de escucha y para las goroutines del nodo.
func (n *NodoRaft) Detener() {
	n.corriendoMu.Lock()
	n.corriendo = false
	n.corriendoMu.Unlock()
	if n.listener != nil {
		_ = n.listener.Close()
	}
}

func (n *NodoRaft) estaCorriendo() bool {
	n.corriendoMu.Lock()
	defer n.corriendoMu.Unlock()
	return n.corriendo
}

// Corriendo indica si el nodo sigue vivo (no se le llamo Detener).
func (n *NodoRaft) Corriendo() bool { return n.estaCorriendo() }

// Estado expone el estado actual (para pruebas y demos).
func (n *NodoRaft) EstadoActual() Estado {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.estado
}

func (n *NodoRaft) ID() int { return n.id }

func (n *NodoRaft) bucleAceptar() {
	for n.estaCorriendo() {
		conn, err := n.listener.Accept()
		if err != nil {
			if n.estaCorriendo() {
				n.logf("error aceptando: %v", err)
			}
			continue
		}
		go n.atender(conn)
	}
}

// ---------------------------------------------------------------------
// Bucle de tiempo: heartbeats como lider, o disparar eleccion como seguidor.
// ---------------------------------------------------------------------
func (n *NodoRaft) bucleTiempo() {
	for n.estaCorriendo() {
		time.Sleep(bucleTickMS)
		n.mu.Lock()
		est := n.estado
		n.mu.Unlock()

		if est == Lider {
			n.enviarHeartbeats()
			time.Sleep(heartbeatMS)
		} else {
			n.mu.Lock()
			vencido := time.Since(n.ultimoContacto) >= n.timeoutEleccion
			n.mu.Unlock()
			if vencido {
				n.iniciarEleccion()
			}
		}
	}
}

// ---------------------------------------------------------------------
// ELECCION: incremento term, voto por mi, pido votos en paralelo.
// ---------------------------------------------------------------------
func (n *NodoRaft) iniciarEleccion() {
	n.mu.Lock()
	n.estado = Candidato
	n.currentTerm++
	yo := n.id
	n.votedFor = &yo
	n.liderActual = nil
	n.nuevoTimeout()
	n.ultimoContacto = time.Now()
	termEleccion := n.currentTerm
	ultIdx := len(n.logEntradas)
	ultTerm := 0
	if ultIdx > 0 {
		ultTerm = n.logEntradas[ultIdx-1].Term
	}
	pares := n.pares
	n.mu.Unlock()

	n.logf("inicia eleccion en term %d", termEleccion)

	var mu sync.Mutex
	votos := 1 // el mio
	mayoria := (len(pares)+1)/2 + 1
	var wg sync.WaitGroup

	for _, p := range pares {
		p := p
		wg.Add(1)
		go func() {
			defer wg.Done()
			resp, ok := n.enviar(p, Unir(RequestVote, termEleccion, n.id, ultIdx, ultTerm))
			if !ok {
				return
			}
			c := Partir(resp)
			if len(c) < 3 || c[0] != Vote {
				return
			}
			termResp, err := strconv.Atoi(c[1])
			if err != nil {
				return
			}
			otorgado := c[2] == "1"

			n.mu.Lock()
			defer n.mu.Unlock()
			if termResp > n.currentTerm {
				n.volverSeguidorLocked(termResp)
				return
			}
			if n.estado != Candidato || n.currentTerm != termEleccion {
				return
			}
			if otorgado {
				mu.Lock()
				votos++
				gano := votos >= mayoria
				mu.Unlock()
				if gano {
					n.volverLiderLocked()
				}
			}
		}()
	}
	wg.Wait()
}

// volverLiderLocked asume que n.mu ya esta tomado.
func (n *NodoRaft) volverLiderLocked() {
	if n.estado == Lider {
		return
	}
	n.estado = Lider
	yo := n.id
	n.liderActual = &yo
	siguiente := len(n.logEntradas) + 1
	for _, p := range n.pares {
		n.nextIndex[p.ID] = siguiente
		n.matchIndex[p.ID] = 0
	}
	n.logf("*** soy LIDER en term %d ***", n.currentTerm)
	go n.enviarHeartbeats()
}

// volverSeguidorLocked asume que n.mu ya esta tomado.
func (n *NodoRaft) volverSeguidorLocked(term int) {
	n.currentTerm = term
	n.estado = Seguidor
	n.votedFor = nil
	n.ultimoContacto = time.Now()
}

// ---------------------------------------------------------------------
// HEARTBEATS / REPLICACION: el lider manda AppendEntries a cada seguidor.
// ---------------------------------------------------------------------
// No espera a que terminen las replicaciones (igual que la referencia Java):
// el bucle de tiempo no se debe frenar por un par lento o caido.
func (n *NodoRaft) enviarHeartbeats() {
	n.mu.Lock()
	pares := n.pares
	n.mu.Unlock()
	for _, p := range pares {
		go n.replicarA(p)
	}
}

func (n *NodoRaft) replicarA(p Par) {
	n.mu.Lock()
	if n.estado != Lider {
		n.mu.Unlock()
		return
	}
	term := n.currentTerm
	ni, ok := n.nextIndex[p.ID]
	if !ok {
		ni = len(n.logEntradas) + 1
	}
	prevIdx := ni - 1
	prevTerm := 0
	if prevIdx > 0 && prevIdx <= len(n.logEntradas) {
		prevTerm = n.logEntradas[prevIdx-1].Term
	}
	var aEnviar []Entrada
	for i := ni; i <= len(n.logEntradas); i++ {
		aEnviar = append(aEnviar, n.logEntradas[i-1])
	}
	commit := n.commitIndex
	n.mu.Unlock()

	partes := make([]string, len(aEnviar))
	for i, e := range aEnviar {
		partes[i] = e.Serializar()
	}
	entradasStr := strings.Join(partes, SepEntradas)

	resp, ok2 := n.enviar(p, Unir(Append, term, n.id, prevIdx, prevTerm, commit, entradasStr))
	if !ok2 {
		return
	}
	c := Partir(resp)
	if len(c) < 4 || c[0] != AppendOk {
		return
	}
	termResp, err1 := strconv.Atoi(c[1])
	match, err2 := strconv.Atoi(c[3])
	if err1 != nil || err2 != nil {
		return
	}
	exito := c[2] == "1"

	n.mu.Lock()
	defer n.mu.Unlock()
	if termResp > n.currentTerm {
		n.volverSeguidorLocked(termResp)
		return
	}
	if n.estado != Lider || term != n.currentTerm {
		return
	}
	if exito {
		n.matchIndex[p.ID] = match
		n.nextIndex[p.ID] = match + 1
		n.recalcularCommitLocked()
	} else {
		ni := n.nextIndex[p.ID]
		if ni == 0 {
			ni = len(n.logEntradas) + 1
		}
		if ni > 1 {
			n.nextIndex[p.ID] = ni - 1
		} else {
			n.nextIndex[p.ID] = 1
		}
	}
}

// Un indice se comete cuando esta en la mayoria Y es del term actual del
// lider (regla del profe: no cometer entradas de terms pasados contando
// replicas). Asume que n.mu ya esta tomado.
func (n *NodoRaft) recalcularCommitLocked() {
	for idx := len(n.logEntradas); idx > n.commitIndex; idx-- {
		if n.logEntradas[idx-1].Term != n.currentTerm {
			continue
		}
		cuenta := 1 // yo
		for _, p := range n.pares {
			if n.matchIndex[p.ID] >= idx {
				cuenta++
			}
		}
		if cuenta >= (len(n.pares)+1)/2+1 {
			n.commitIndex = idx
			n.aplicarLocked()
			break
		}
	}
}

// Aplica a la maquina de estado (el registro) todo lo cometido y no
// aplicado. Asume que n.mu ya esta tomado.
func (n *NodoRaft) aplicarLocked() {
	for n.lastApplied < n.commitIndex {
		n.lastApplied++
		comando := n.logEntradas[n.lastApplied-1].Comando
		n.registro.Aplicar(comando)
		n.logf("aplica[%d]: %s", n.lastApplied, comando)
	}
}

// ---------------------------------------------------------------------
// ATENCION DE MENSAJES ENTRANTES (una conexion = una goroutine).
// ---------------------------------------------------------------------
func (n *NodoRaft) atender(conn net.Conn) {
	defer conn.Close()
	r := bufio.NewReader(conn)
	linea, err := r.ReadString('\n')
	if err != nil && linea == "" {
		return
	}
	linea = trimEOL(linea)
	if linea == "" {
		return
	}
	resp := n.procesar(linea)
	if resp != "" {
		_, _ = conn.Write([]byte(resp + "\n"))
	}
}

func trimEOL(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}

func (n *NodoRaft) procesar(linea string) string {
	c := Partir(linea)
	if len(c) == 0 {
		return ""
	}
	switch c[0] {
	case RequestVote:
		return n.onRequestVote(c)
	case Append:
		return n.onAppend(c)
	case NuevaDeteccion:
		return n.onNuevaDeteccion(c)
	case LeerRegistro:
		return n.onLeerRegistro()
	default:
		return ""
	}
}

// REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
func (n *NodoRaft) onRequestVote(c []string) string {
	term, _ := strconv.Atoi(c[1])
	cand, _ := strconv.Atoi(c[2])
	candUltIdx, _ := strconv.Atoi(c[3])
	candUltTerm, _ := strconv.Atoi(c[4])

	n.mu.Lock()
	defer n.mu.Unlock()

	if term > n.currentTerm {
		n.volverSeguidorLocked(term)
	}
	otorgar := false
	if term >= n.currentTerm && (n.votedFor == nil || *n.votedFor == cand) {
		miUltIdx := len(n.logEntradas)
		miUltTerm := 0
		if miUltIdx > 0 {
			miUltTerm = n.logEntradas[miUltIdx-1].Term
		}
		alMenosActual := candUltTerm > miUltTerm ||
			(candUltTerm == miUltTerm && candUltIdx >= miUltIdx)
		if alMenosActual {
			otorgar = true
			n.votedFor = &cand
			n.ultimoContacto = time.Now()
		}
	}
	otorgadoInt := 0
	if otorgar {
		otorgadoInt = 1
	}
	return Unir(Vote, n.currentTerm, otorgadoInt)
}

// APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
func (n *NodoRaft) onAppend(c []string) string {
	term, _ := strconv.Atoi(c[1])
	lider, _ := strconv.Atoi(c[2])
	prevIdx, _ := strconv.Atoi(c[3])
	prevTerm, _ := strconv.Atoi(c[4])
	commitLider, _ := strconv.Atoi(c[5])
	entradasStr := ""
	if len(c) > 6 {
		entradasStr = c[6]
	}

	n.mu.Lock()
	defer n.mu.Unlock()

	if term < n.currentTerm {
		return Unir(AppendOk, n.currentTerm, 0, 0)
	}
	if term > n.currentTerm {
		n.volverSeguidorLocked(term)
	}
	n.estado = Seguidor
	n.liderActual = &lider
	n.ultimoContacto = time.Now()

	// verificacion de consistencia (Log Matching)
	if prevIdx > 0 {
		if len(n.logEntradas) < prevIdx || n.logEntradas[prevIdx-1].Term != prevTerm {
			return Unir(AppendOk, n.currentTerm, 0, 0)
		}
	}

	// aplico las entradas nuevas a partir de prevIdx+1
	if entradasStr != "" {
		items := strings.Split(entradasStr, SepEntradas)
		idx := prevIdx
		for _, it := range items {
			idx++
			e := DeserializarEntrada(it)
			if len(n.logEntradas) >= idx {
				if n.logEntradas[idx-1].Term != e.Term {
					n.logEntradas = n.logEntradas[:idx-1]
					n.logEntradas = append(n.logEntradas, e)
				}
				// si coincide, no hago nada (idempotente)
			} else {
				n.logEntradas = append(n.logEntradas, e)
			}
		}
	}

	// avanzo mi commit hasta lo que diga el lider
	if commitLider > n.commitIndex {
		if commitLider < len(n.logEntradas) {
			n.commitIndex = commitLider
		} else {
			n.commitIndex = len(n.logEntradas)
		}
		n.aplicarLocked()
	}
	return Unir(AppendOk, n.currentTerm, 1, len(n.logEntradas))
}

// NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara (un cliente inserta)
func (n *NodoRaft) onNuevaDeteccion(c []string) string {
	n.mu.Lock()
	if n.estado != Lider {
		lider := n.liderActual
		n.mu.Unlock()
		if lider != nil {
			p := n.buscarPar(*lider)
			if p != nil {
				return Unir(Redirect, p.Direccion())
			}
		}
		return Unir(Redirect, "?")
	}
	comando := c[1]
	n.logEntradas = append(n.logEntradas, Entrada{Term: n.currentTerm, Comando: comando})
	n.logf("cliente inserta: %s (indice %d)", comando, len(n.logEntradas))
	n.mu.Unlock()

	go n.enviarHeartbeats() // empuja la replicacion de una vez
	return Ok
}

// LEER_REGISTRO -> devuelvo la maquina de estado (solo lo cometido y aplicado)
func (n *NodoRaft) onLeerRegistro() string {
	n.mu.Lock()
	if n.estado != Lider {
		lider := n.liderActual
		n.mu.Unlock()
		if lider != nil {
			p := n.buscarPar(*lider)
			if p != nil {
				return Unir(Redirect, p.Direccion())
			}
		}
		return Unir(Redirect, "?")
	}
	n.mu.Unlock()

	cuerpo := strings.Join(n.registro.Snapshot(), SepEntradas)
	return Unir(Registro, cuerpo)
}

func (n *NodoRaft) buscarPar(idBuscado int) *Par {
	if idBuscado == n.id {
		return &Par{ID: n.id, Host: "127.0.0.1", Puerto: n.puerto}
	}
	for _, p := range n.pares {
		if p.ID == idBuscado {
			pp := p
			return &pp
		}
	}
	return nil
}

// ---------------------------------------------------------------------
// Envio de un mensaje a un par y lectura de su respuesta (una linea).
// ---------------------------------------------------------------------
func (n *NodoRaft) enviar(p Par, mensaje string) (string, bool) {
	conn, err := net.DialTimeout("tcp", p.Direccion(), dialTimeout)
	if err != nil {
		return "", false
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(rpcTimeout))
	if _, err := conn.Write([]byte(mensaje + "\n")); err != nil {
		return "", false
	}
	r := bufio.NewReader(conn)
	linea, err := r.ReadString('\n')
	if err != nil && linea == "" {
		return "", false
	}
	return trimEOL(linea), true
}

func (n *NodoRaft) logf(formato string, args ...any) {
	log.Printf("[nodo %d] "+formato, append([]any{n.id}, args...)...)
}
