package raft

import (
	"bufio"
	"net"
	"strconv"
	"strings"
	"time"
)

// ParsearNodos interpreta specs id:host:puerto (mismo formato que usa
// arrancar-nodo) y arma la lista de pares del cluster.
func ParsearNodos(specs []string) []Par {
	nodos := make([]Par, 0, len(specs))
	for _, spec := range specs {
		p := strings.Split(spec, ":")
		if len(p) != 3 {
			continue
		}
		id, err1 := strconv.Atoi(p[0])
		puerto, err2 := strconv.Atoi(p[2])
		if err1 != nil || err2 != nil {
			continue
		}
		nodos = append(nodos, Par{ID: id, Host: p[1], Puerto: puerto})
	}
	return nodos
}

// ClienteCluster habla con el cluster Raft desde fuera (equivalente a
// java/src/raft/ClienteCluster.java). Sirve para probar el nucleo Go y,
// eventualmente, para cualquier proceso Go que necesite insertar detecciones
// o leer el registro sin ser el nodo mismo. Maneja el REDIRECT: si contacta
// a un seguidor, sigue al lider y reintenta ahi.
type ClienteCluster struct {
	nodos       []Par
	ultimoLider *Par
}

func NuevoClienteCluster(nodos []Par) *ClienteCluster {
	return &ClienteCluster{nodos: nodos}
}

// Insertar agrega una deteccion. Devuelve true si el cluster la acepto.
func (c *ClienteCluster) Insertar(tipo, imagenRef, fechaHora, camara string) bool {
	cmd := strings.Join([]string{tipo, imagenRef, fechaHora, camara}, SepCampoEntrada)
	resp, ok := c.pedir(Unir(NuevaDeteccion, cmd))
	return ok && resp == Ok
}

// LeerRegistro devuelve las detecciones cometidas (cada una es el string
// tipo,imagenRef,fechaHora,camara).
func (c *ClienteCluster) LeerRegistro() []string {
	resp, ok := c.pedir(LeerRegistro)
	if !ok {
		return nil
	}
	campos := Partir(resp)
	if len(campos) < 2 || campos[0] != Registro {
		return nil
	}
	if campos[1] == "" {
		return nil
	}
	return strings.Split(campos[1], SepEntradas)
}

// pedir envia un mensaje probando nodos hasta dar con el lider (siguiendo
// REDIRECT). En cada intento se prioriza al ultimo lider conocido.
func (c *ClienteCluster) pedir(mensaje string) (string, bool) {
	intentosMax := len(c.nodos)*2 + 4
	for intento := 0; intento < intentosMax; intento++ {
		orden := c.ordenConLiderPrimero()

		redirigido := false
		for _, p := range orden {
			resp, ok := enviarACluster(p, mensaje)
			if !ok {
				continue
			}
			campos := Partir(resp)
			if campos[0] == Redirect {
				lider := c.porDireccion(campos[1])
				if lider != nil && (c.ultimoLider == nil || lider.ID != c.ultimoLider.ID) {
					c.ultimoLider = lider
					redirigido = true
					break // reintento de una vez contra el lider correcto
				}
				continue // REDIRECT a "?" o al mismo: sigo probando otros nodos
			}
			p := p
			c.ultimoLider = &p
			return resp, true
		}
		if !redirigido {
			time.Sleep(80 * time.Millisecond) // el cluster puede estar en eleccion
		}
	}
	return "", false
}

func (c *ClienteCluster) ordenConLiderPrimero() []Par {
	orden := make([]Par, 0, len(c.nodos))
	if c.ultimoLider != nil {
		orden = append(orden, *c.ultimoLider)
	}
	for _, p := range c.nodos {
		if c.ultimoLider == nil || p.ID != c.ultimoLider.ID {
			orden = append(orden, p)
		}
	}
	return orden
}

func (c *ClienteCluster) porDireccion(dir string) *Par {
	for _, p := range c.nodos {
		if p.Direccion() == dir {
			pp := p
			return &pp
		}
	}
	return nil
}

func enviarACluster(p Par, mensaje string) (string, bool) {
	conn, err := net.DialTimeout("tcp", p.Direccion(), 150*time.Millisecond)
	if err != nil {
		return "", false
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(400 * time.Millisecond))
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
