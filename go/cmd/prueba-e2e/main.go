// Prueba end-to-end del nucleo Raft en Go, sin interfaz (equivalente a
// java.raft.PruebaE2E). Levanta un cluster de 3 nodos Go en el mismo
// proceso (cada uno con su socket) y verifica:
//  1. Se elige un lider.
//  2. Un cliente inserta detecciones y se replican (aparecen en el registro).
//  3. Se mata al lider -> se elige uno nuevo -> el registro sigue consistente.
//  4. Se pueden insertar mas detecciones con el nuevo lider.
//
// Si todo pasa, imprime OK y termina con codigo 0. Si algo falla, codigo 1.
package main

import (
	"fmt"
	"os"
	"time"

	"raftgo/internal/raft"
)

func main() {
	const base = 9501
	todos := []raft.Par{
		{ID: 1, Host: "127.0.0.1", Puerto: base},
		{ID: 2, Host: "127.0.0.1", Puerto: base + 1},
		{ID: 3, Host: "127.0.0.1", Puerto: base + 2},
	}

	nodos := make([]*raft.NodoRaft, 3)
	for i, yo := range todos {
		var otros []raft.Par
		for _, p := range todos {
			if p.ID != yo.ID {
				otros = append(otros, p)
			}
		}
		nodos[i] = raft.NuevoNodo(yo.ID, yo.Puerto, otros)
		if err := nodos[i].Iniciar(); err != nil {
			fmt.Println("FALLO: no se pudo iniciar nodo", yo.ID, ":", err)
			os.Exit(1)
		}
	}

	cli := raft.NuevoClienteCluster(todos)
	fallos := 0

	// 1. esperar a que haya lider
	lider := esperarLider(nodos, 3*time.Second)
	if lider == nil {
		fmt.Println("FALLO: no se eligio lider")
		os.Exit(1)
	}
	fmt.Println("PASO 1: lider elegido = nodo", lider.ID())

	// 2. insertar 3 detecciones y verificar replicacion
	cli.Insertar("Carro", "img1.png", "05/11/2025 14:00", "Camara 1")
	cli.Insertar("Loro", "img2.png", "03/11/2025 02:30", "Camara 3")
	cli.Insertar("Naranja", "img3.png", "01/11/2025 15:20", "Camara 2")
	time.Sleep(600 * time.Millisecond)

	reg := cli.LeerRegistro()
	if len(reg) != 3 {
		fmt.Println("FALLO: esperaba 3 detecciones, hay", len(reg))
		fallos++
	} else {
		fmt.Println("PASO 2: 3 detecciones replicadas y cometidas")
	}

	if !replicadoEnMayoria(nodos, 3) {
		fmt.Println("FALLO: no replicado en la mayoria")
		fallos++
	} else {
		fmt.Println("PASO 2b: registro presente en la mayoria de nodos")
	}

	// 3. matar al lider y verificar reeleccion + consistencia
	idLiderViejo := lider.ID()
	lider.Detener()
	fmt.Println("... se mata al lider (nodo", idLiderViejo, ")")
	nuevo := esperarNuevoLider(nodos, idLiderViejo, 4*time.Second)
	if nuevo == nil {
		fmt.Println("FALLO: no se reeligio lider tras la caida")
		os.Exit(1)
	}
	fmt.Println("PASO 3: nuevo lider = nodo", nuevo.ID())

	regTrasCaida := cli.LeerRegistro()
	if len(regTrasCaida) != 3 {
		fmt.Println("FALLO: registro inconsistente tras caida (", len(regTrasCaida), ")")
		fallos++
	} else {
		fmt.Println("PASO 3b: las 3 detecciones siguen consistentes tras la caida")
	}

	// 4. insertar con el nuevo lider
	cli.Insertar("Mujer", "img4.png", "01/11/2025 03:25", "Camara 1")
	time.Sleep(600 * time.Millisecond)
	regFinal := cli.LeerRegistro()
	if len(regFinal) != 4 {
		fmt.Println("FALLO: esperaba 4 tras nueva insercion, hay", len(regFinal))
		fallos++
	} else {
		fmt.Println("PASO 4: insercion con el nuevo lider OK (4 detecciones)")
	}

	fmt.Println()
	for _, d := range regFinal {
		fmt.Println("  registro:", d)
	}
	fmt.Println()

	for _, n := range nodos {
		n.Detener()
	}

	if fallos == 0 {
		fmt.Println("=== E2E OK: todo funciona ===")
		os.Exit(0)
	}
	fmt.Println("=== E2E con", fallos, "fallo(s) ===")
	os.Exit(1)
}

func esperarLider(nodos []*raft.NodoRaft, plazo time.Duration) *raft.NodoRaft {
	fin := time.Now().Add(plazo)
	for time.Now().Before(fin) {
		for _, n := range nodos {
			if n.Corriendo() && n.EstadoActual() == raft.Lider {
				return n
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	return nil
}

func esperarNuevoLider(nodos []*raft.NodoRaft, idViejo int, plazo time.Duration) *raft.NodoRaft {
	fin := time.Now().Add(plazo)
	for time.Now().Before(fin) {
		for _, n := range nodos {
			if n.Corriendo() && n.ID() != idViejo && n.EstadoActual() == raft.Lider {
				return n
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	return nil
}

// replicadoEnMayoria verifica que al menos la mayoria de nodos vivos tenga
// n detecciones cometidas.
func replicadoEnMayoria(nodos []*raft.NodoRaft, n int) bool {
	ok := 0
	for _, nodo := range nodos {
		if nodo.Corriendo() && nodo.Registro().Len() >= n {
			ok++
		}
	}
	return ok >= 2
}
