package raft;

import java.util.*;

// Arranca un nodo Raft. Se le pasa el id de este nodo y la lista de todos los
// nodos del cluster como  id:host:puerto.
//
// Ejemplo (cluster de 3, en la misma maquina):
//   java raft.ArrancarNodo 1  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
//   java raft.ArrancarNodo 2  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
//   java raft.ArrancarNodo 3  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
//
// En LAN se cambian los 127.0.0.1 por las IP reales de cada PC.
public class ArrancarNodo {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.out.println("uso: java raft.ArrancarNodo <miId> <id:host:puerto> ...");
            return;
        }
        int miId = Integer.parseInt(args[0]);
        int miPuerto = -1;
        List<Par> pares = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            String[] p = args[i].split(":");
            int id = Integer.parseInt(p[0]);
            String host = p[1];
            int puerto = Integer.parseInt(p[2]);
            if (id == miId) miPuerto = puerto;
            else pares.add(new Par(id, host, puerto));
        }
        if (miPuerto < 0) {
            System.out.println("el id " + miId + " no aparece en la lista de nodos");
            return;
        }
        NodoRaft nodo = new NodoRaft(miId, miPuerto, pares);
        nodo.iniciar();
        // el proceso se queda vivo mientras corran los hilos daemon
        Thread.currentThread().join();
    }
}
