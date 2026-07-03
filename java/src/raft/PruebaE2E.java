package raft;

import java.util.*;

// Prueba end-to-end del nucleo Raft, sin interfaz. Levanta un cluster de 3 nodos
// en el mismo proceso (cada uno con su socket), y verifica:
//   1. Se elige un lider.
//   2. Un cliente inserta detecciones y se replican (aparecen en el registro).
//   3. Se mata al lider -> se elige uno nuevo -> el registro sigue consistente.
//   4. Se pueden insertar mas detecciones con el nuevo lider.
//
// Si todo pasa, imprime OK y termina con codigo 0. Si algo falla, codigo 1.
public class PruebaE2E {

    static NodoRaft[] nodos;
    static List<Par> todos;

    public static void main(String[] args) throws Exception {
        int base = 9401;
        todos = Arrays.asList(
                new Par(1, "127.0.0.1", base),
                new Par(2, "127.0.0.1", base + 1),
                new Par(3, "127.0.0.1", base + 2));

        nodos = new NodoRaft[3];
        for (int i = 0; i < 3; i++) {
            Par yo = todos.get(i);
            List<Par> otros = new ArrayList<>();
            for (Par p : todos) if (p.id != yo.id) otros.add(p);
            nodos[i] = new NodoRaft(yo.id, yo.puerto, otros);
            nodos[i].iniciar();
        }

        ClienteCluster cli = new ClienteCluster(new ArrayList<>(todos));
        int fallos = 0;

        // 1. esperar a que haya lider
        NodoRaft lider = esperarLider(3000);
        if (lider == null) { System.out.println("FALLO: no se eligio lider"); System.exit(1); }
        System.out.println("PASO 1: lider elegido = nodo " + lider.id);

        // 2. insertar 3 detecciones y verificar replicacion
        cli.insertar("Carro", "img1.png", "05/11/2025 14:00", "Camara 1");
        cli.insertar("Loro", "img2.png", "03/11/2025 02:30", "Camara 3");
        cli.insertar("Naranja", "img3.png", "01/11/2025 15:20", "Camara 2");
        Thread.sleep(600);

        List<String> reg = cli.leerRegistro();
        if (reg.size() != 3) { System.out.println("FALLO: esperaba 3 detecciones, hay " + reg.size()); fallos++; }
        else System.out.println("PASO 2: 3 detecciones replicadas y cometidas");

        if (!replicadoEnMayoria(3)) { System.out.println("FALLO: no replicado en la mayoria"); fallos++; }
        else System.out.println("PASO 2b: registro presente en la mayoria de nodos");

        // 3. matar al lider y verificar reeleccion + consistencia
        int idLiderViejo = lider.id;
        lider.detener();
        System.out.println("... se mata al lider (nodo " + idLiderViejo + ")");
        NodoRaft nuevo = esperarNuevoLider(idLiderViejo, 4000);
        if (nuevo == null) { System.out.println("FALLO: no se reeligio lider tras la caida"); System.exit(1); }
        System.out.println("PASO 3: nuevo lider = nodo " + nuevo.id);

        List<String> regTrasCaida = cli.leerRegistro();
        if (regTrasCaida.size() != 3) { System.out.println("FALLO: registro inconsistente tras caida (" + regTrasCaida.size() + ")"); fallos++; }
        else System.out.println("PASO 3b: las 3 detecciones siguen consistentes tras la caida");

        // 4. insertar con el nuevo lider
        cli.insertar("Mujer", "img4.png", "01/11/2025 03:25", "Camara 1");
        Thread.sleep(600);
        List<String> regFinal = cli.leerRegistro();
        if (regFinal.size() != 4) { System.out.println("FALLO: esperaba 4 tras nueva insercion, hay " + regFinal.size()); fallos++; }
        else System.out.println("PASO 4: insercion con el nuevo lider OK (4 detecciones)");

        System.out.println();
        for (String d : regFinal) System.out.println("  registro: " + d);
        System.out.println();

        for (NodoRaft n : nodos) n.detener();

        if (fallos == 0) { System.out.println("=== E2E OK: todo funciona ==="); System.exit(0); }
        else { System.out.println("=== E2E con " + fallos + " fallo(s) ==="); System.exit(1); }
    }

    static NodoRaft esperarLider(long ms) throws InterruptedException {
        long fin = System.currentTimeMillis() + ms;
        while (System.currentTimeMillis() < fin) {
            for (NodoRaft n : nodos)
                if (n.corriendo && n.estado == NodoRaft.Estado.LIDER) return n;
            Thread.sleep(50);
        }
        return null;
    }

    static NodoRaft esperarNuevoLider(int idViejo, long ms) throws InterruptedException {
        long fin = System.currentTimeMillis() + ms;
        while (System.currentTimeMillis() < fin) {
            for (NodoRaft n : nodos)
                if (n.corriendo && n.id != idViejo && n.estado == NodoRaft.Estado.LIDER) return n;
            Thread.sleep(50);
        }
        return null;
    }

    // Verifica que al menos la mayoria de nodos vivos tenga N entradas cometidas.
    static boolean replicadoEnMayoria(int n) {
        int ok = 0;
        for (NodoRaft nodo : nodos)
            if (nodo.corriendo && nodo.registro.size() >= n) ok++;
        return ok >= 2;
    }
}
