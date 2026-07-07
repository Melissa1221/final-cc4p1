// Package raft: nodo Raft en Go sobre sockets TCP crudos y goroutines (net +
// sync de la stdlib, sin frameworks). Habla el MISMO protocolo de texto que los
// nodos Java y Python, asi los tres forman un solo cluster heterogeneo.
//
// Protocolo (una linea por mensaje, campos separados por |):
//
//	REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
//	VOTE|term|otorgado(1/0)
//	APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
//	APPEND_OK|term|exito(1/0)|matchIndex
//	NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara
//	LEER_REGISTRO / REGISTRO|det1;det2;...
//	REDIRECT|host:puerto / OK
package raft

import (
	"bufio"
	"fmt"
	"math/rand"
	"net"
	"strconv"
	"strings"
	"sync"
	"time"
)

const sepEntradas = ";"

// Entrada del log replicado.
type Entrada struct {
	Term    int
	Comando string
}

func (e Entrada) serializar() string {
	return strconv.Itoa(e.Term) + "," + e.Comando
}

func deserializar(s string) Entrada {
	coma := strings.Index(s, ",")
	t, _ := strconv.Atoi(s[:coma])
	return Entrada{Term: t, Comando: s[coma+1:]}
}

// Par: un nodo del cluster.
type Par struct {
	ID     int
	Host   string
	Puerto int
}

func (p Par) dir() string { return fmt.Sprintf("%s:%d", p.Host, p.Puerto) }

// Nodo Raft.
type Nodo struct {
	id     int
	puerto int
	pares  []Par

	mu          sync.Mutex
	currentTerm int
	votedFor    int // -1 = nadie
	log         []Entrada

	estado         string // SEGUIDOR, CANDIDATO, LIDER
	commitIndex    int
	lastApplied    int
	liderActual    int // -1 = ninguno
	nextIndex      map[int]int
	matchIndex     map[int]int
	registro       []string
	ultimoContacto time.Time
	timeoutElec    time.Duration

	corriendo bool
	ln        net.Listener
}

func NuevoNodo(id, puerto int, pares []Par) *Nodo {
	return &Nodo{
		id: id, puerto: puerto, pares: pares,
		votedFor: -1, liderActual: -1, estado: "SEGUIDOR",
		nextIndex: map[int]int{}, matchIndex: map[int]int{},
		corriendo: true, timeoutElec: nuevoTimeout(),
	}
}

func nuevoTimeout() time.Duration {
	return time.Duration(150+rand.Intn(151)) * time.Millisecond // 150-300 ms
}

// Iniciar arranca el listener y el bucle de tiempo.
func (n *Nodo) Iniciar() error {
	ln, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", n.puerto))
	if err != nil {
		return err
	}
	n.ln = ln
	n.ultimoContacto = time.Now()
	n.logf("nodo %d escuchando en puerto %d (seguidor)", n.id, n.puerto)
	go n.bucleAceptar()
	go n.bucleTiempo()
	return nil
}

func (n *Nodo) Detener() {
	n.mu.Lock()
	n.corriendo = false
	n.mu.Unlock()
	if n.ln != nil {
		n.ln.Close()
	}
}

func (n *Nodo) bucleAceptar() {
	for {
		c, err := n.ln.Accept()
		if err != nil {
			n.mu.Lock()
			corriendo := n.corriendo
			n.mu.Unlock()
			if !corriendo {
				return
			}
			continue
		}
		go n.atender(c)
	}
}

func (n *Nodo) bucleTiempo() {
	for {
		time.Sleep(15 * time.Millisecond)
		n.mu.Lock()
		if !n.corriendo {
			n.mu.Unlock()
			return
		}
		est := n.estado
		venc := time.Since(n.ultimoContacto) >= n.timeoutElec
		n.mu.Unlock()

		if est == "LIDER" {
			n.enviarHeartbeats()
			time.Sleep(50 * time.Millisecond)
		} else if venc {
			n.iniciarEleccion()
		}
	}
}

// ------------------------------------------------------------------ ELECCION
func (n *Nodo) iniciarEleccion() {
	n.mu.Lock()
	n.estado = "CANDIDATO"
	n.currentTerm++
	n.votedFor = n.id
	n.liderActual = -1
	n.timeoutElec = nuevoTimeout()
	n.ultimoContacto = time.Now()
	termElec := n.currentTerm
	ultIdx := len(n.log)
	ultTerm := 0
	if ultIdx > 0 {
		ultTerm = n.log[ultIdx-1].Term
	}
	n.mu.Unlock()
	n.logf("inicia eleccion en term %d", termElec)

	var votos int32 = 1
	mayoria := (len(n.pares)+1)/2 + 1
	var wg sync.WaitGroup
	var vmu sync.Mutex

	for _, p := range n.pares {
		wg.Add(1)
		go func(p Par) {
			defer wg.Done()
			resp := n.enviar(p, unir("REQUEST_VOTE", termElec, n.id, ultIdx, ultTerm))
			if resp == "" {
				return
			}
			c := strings.Split(resp, "|")
			if c[0] != "VOTE" {
				return
			}
			termResp, _ := strconv.Atoi(c[1])
			otorgado := c[2] == "1"
			n.mu.Lock()
			defer n.mu.Unlock()
			if termResp > n.currentTerm {
				n.volverSeguidor(termResp)
				return
			}
			if n.estado != "CANDIDATO" || n.currentTerm != termElec {
				return
			}
			if otorgado {
				vmu.Lock()
				votos++
				alcanzo := int(votos) >= mayoria
				vmu.Unlock()
				if alcanzo {
					n.volverLider()
				}
			}
		}(p)
	}
	esperarConTimeout(&wg, 200*time.Millisecond)
}

func (n *Nodo) volverLider() {
	if n.estado == "LIDER" {
		return
	}
	n.estado = "LIDER"
	n.liderActual = n.id
	sig := len(n.log) + 1
	for _, p := range n.pares {
		n.nextIndex[p.ID] = sig
		n.matchIndex[p.ID] = 0
	}
	n.logf("*** soy LIDER en term %d ***", n.currentTerm)
	go n.enviarHeartbeats()
}

func (n *Nodo) volverSeguidor(term int) {
	n.currentTerm = term
	n.estado = "SEGUIDOR"
	n.votedFor = -1
	n.ultimoContacto = time.Now()
}

// -------------------------------------------------------------- REPLICACION
func (n *Nodo) enviarHeartbeats() {
	for _, p := range n.pares {
		go n.replicarA(p)
	}
}

func (n *Nodo) replicarA(p Par) {
	n.mu.Lock()
	if n.estado != "LIDER" {
		n.mu.Unlock()
		return
	}
	term := n.currentTerm
	ni := n.nextIndex[p.ID]
	if ni == 0 {
		ni = len(n.log) + 1
	}
	prevIdx := ni - 1
	prevTerm := 0
	if prevIdx > 0 && prevIdx <= len(n.log) {
		prevTerm = n.log[prevIdx-1].Term
	}
	var aEnviar []Entrada
	if ni <= len(n.log) {
		aEnviar = append(aEnviar, n.log[ni-1:]...)
	}
	commit := n.commitIndex
	n.mu.Unlock()

	partes := make([]string, len(aEnviar))
	for i, e := range aEnviar {
		partes[i] = e.serializar()
	}
	ent := strings.Join(partes, sepEntradas)

	resp := n.enviar(p, unir("APPEND", term, n.id, prevIdx, prevTerm, commit, ent))
	if resp == "" {
		return
	}
	c := strings.Split(resp, "|")
	if c[0] != "APPEND_OK" {
		return
	}
	termResp, _ := strconv.Atoi(c[1])
	exito := c[2] == "1"
	match, _ := strconv.Atoi(c[3])

	n.mu.Lock()
	defer n.mu.Unlock()
	if termResp > n.currentTerm {
		n.volverSeguidor(termResp)
		return
	}
	if n.estado != "LIDER" || term != n.currentTerm {
		return
	}
	if exito {
		n.matchIndex[p.ID] = match
		n.nextIndex[p.ID] = match + 1
		n.recalcularCommit()
	} else {
		if n.nextIndex[p.ID] > 1 {
			n.nextIndex[p.ID]--
		}
	}
}

func (n *Nodo) recalcularCommit() {
	for idx := len(n.log); idx > n.commitIndex; idx-- {
		if n.log[idx-1].Term != n.currentTerm {
			continue
		}
		cuenta := 1
		for _, p := range n.pares {
			if n.matchIndex[p.ID] >= idx {
				cuenta++
			}
		}
		if cuenta >= (len(n.pares)+1)/2+1 {
			n.commitIndex = idx
			n.aplicar()
			break
		}
	}
}

func (n *Nodo) aplicar() {
	for n.lastApplied < n.commitIndex {
		n.lastApplied++
		cmd := n.log[n.lastApplied-1].Comando
		n.registro = append(n.registro, cmd)
		n.logf("aplica[%d]: %s", n.lastApplied, cmd)
	}
}

// ------------------------------------------------------------- MENSAJES
func (n *Nodo) atender(c net.Conn) {
	defer c.Close()
	r := bufio.NewReader(c)
	linea, err := r.ReadString('\n')
	if err != nil && linea == "" {
		return
	}
	linea = strings.TrimRight(linea, "\n")
	if linea == "" {
		return
	}
	resp := n.procesar(linea)
	if resp != "" {
		c.Write([]byte(resp + "\n"))
	}
}

func (n *Nodo) procesar(linea string) string {
	c := strings.Split(linea, "|")
	switch c[0] {
	case "REQUEST_VOTE":
		return n.onRequestVote(c)
	case "APPEND":
		return n.onAppend(c)
	case "NUEVA_DETECCION":
		return n.onNuevaDeteccion(c)
	case "LEER_REGISTRO":
		return n.onLeerRegistro()
	}
	return ""
}

func (n *Nodo) onRequestVote(c []string) string {
	term, _ := strconv.Atoi(c[1])
	cand, _ := strconv.Atoi(c[2])
	candIdx, _ := strconv.Atoi(c[3])
	candTerm, _ := strconv.Atoi(c[4])
	n.mu.Lock()
	defer n.mu.Unlock()
	if term > n.currentTerm {
		n.volverSeguidor(term)
	}
	otorgar := false
	if term >= n.currentTerm && (n.votedFor == -1 || n.votedFor == cand) {
		miIdx := len(n.log)
		miTerm := 0
		if miIdx > 0 {
			miTerm = n.log[miIdx-1].Term
		}
		alMenos := candTerm > miTerm || (candTerm == miTerm && candIdx >= miIdx)
		if alMenos {
			otorgar = true
			n.votedFor = cand
			n.ultimoContacto = time.Now()
		}
	}
	g := 0
	if otorgar {
		g = 1
	}
	return unir("VOTE", n.currentTerm, g)
}

func (n *Nodo) onAppend(c []string) string {
	term, _ := strconv.Atoi(c[1])
	lider, _ := strconv.Atoi(c[2])
	prevIdx, _ := strconv.Atoi(c[3])
	prevTerm, _ := strconv.Atoi(c[4])
	commitLider, _ := strconv.Atoi(c[5])
	entradasStr := c[6]

	n.mu.Lock()
	defer n.mu.Unlock()
	if term < n.currentTerm {
		return unir("APPEND_OK", n.currentTerm, 0, 0)
	}
	if term > n.currentTerm {
		n.volverSeguidor(term)
	}
	n.estado = "SEGUIDOR"
	n.liderActual = lider
	n.ultimoContacto = time.Now()

	if prevIdx > 0 {
		if len(n.log) < prevIdx || n.log[prevIdx-1].Term != prevTerm {
			return unir("APPEND_OK", n.currentTerm, 0, 0)
		}
	}

	if entradasStr != "" {
		items := strings.Split(entradasStr, sepEntradas)
		idx := prevIdx
		for _, it := range items {
			idx++
			e := deserializar(it)
			if len(n.log) >= idx {
				if n.log[idx-1].Term != e.Term {
					n.log = n.log[:idx-1]
					n.log = append(n.log, e)
				}
			} else {
				n.log = append(n.log, e)
			}
		}
	}

	if commitLider > n.commitIndex {
		if commitLider < len(n.log) {
			n.commitIndex = commitLider
		} else {
			n.commitIndex = len(n.log)
		}
		n.aplicar()
	}
	return unir("APPEND_OK", n.currentTerm, 1, len(n.log))
}

func (n *Nodo) onNuevaDeteccion(c []string) string {
	n.mu.Lock()
	if n.estado != "LIDER" {
		d := n.dirDe(n.liderActual)
		n.mu.Unlock()
		if d != "" {
			return unir("REDIRECT", d)
		}
		return unir("REDIRECT", "?")
	}
	n.log = append(n.log, Entrada{Term: n.currentTerm, Comando: c[1]})
	n.logf("cliente inserta: %s (indice %d)", c[1], len(n.log))
	n.mu.Unlock()
	n.enviarHeartbeats()
	return "OK"
}

func (n *Nodo) onLeerRegistro() string {
	n.mu.Lock()
	defer n.mu.Unlock()
	if n.estado != "LIDER" {
		d := n.dirDe(n.liderActual)
		if d != "" {
			return unir("REDIRECT", d)
		}
		return unir("REDIRECT", "?")
	}
	return unir("REGISTRO", strings.Join(n.registro, sepEntradas))
}

func (n *Nodo) dirDe(idb int) string {
	if idb == -1 {
		return ""
	}
	if idb == n.id {
		return fmt.Sprintf("127.0.0.1:%d", n.puerto)
	}
	for _, p := range n.pares {
		if p.ID == idb {
			return p.dir()
		}
	}
	return ""
}

// Estado / Registro exportan lo minimo para pruebas.
func (n *Nodo) Estado() string {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.estado
}

func (n *Nodo) Term() int {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.currentTerm
}

func (n *Nodo) Registro() []string {
	n.mu.Lock()
	defer n.mu.Unlock()
	return append([]string{}, n.registro...)
}

func (n *Nodo) Corriendo() bool {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.corriendo
}

// ------------------------------------------------------------- red util
func (n *Nodo) enviar(p Par, mensaje string) string {
	c, err := net.DialTimeout("tcp", p.dir(), 120*time.Millisecond)
	if err != nil {
		return ""
	}
	defer c.Close()
	c.SetDeadline(time.Now().Add(250 * time.Millisecond))
	c.Write([]byte(mensaje + "\n"))
	r := bufio.NewReader(c)
	resp, _ := r.ReadString('\n')
	return strings.TrimRight(resp, "\n")
}

func unir(campos ...interface{}) string {
	partes := make([]string, len(campos))
	for i, c := range campos {
		partes[i] = fmt.Sprintf("%v", c)
	}
	return strings.Join(partes, "|")
}

func esperarConTimeout(wg *sync.WaitGroup, d time.Duration) {
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(d):
	}
}

func (n *Nodo) logf(f string, a ...interface{}) {
	fmt.Printf("[go-nodo %d] ", n.id)
	fmt.Printf(f+"\n", a...)
}
