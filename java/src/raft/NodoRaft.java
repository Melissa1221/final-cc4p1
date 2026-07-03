package raft;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

// Nodo Raft en Java sobre sockets TCP crudos y hilos. Implementa los tres
// subproblemas del material del profe: eleccion de lider, replicacion de log y
// seguridad. Cada nodo mantiene su log replicado y su maquina de estado (el
// registro de detecciones).
//
// Estados: SEGUIDOR, CANDIDATO, LIDER.
// Cada peticion entrante se atiende en su propio hilo (un socket por conexion).
// Un hilo aparte corre el bucle de tiempo (heartbeats si es lider, o disparar
// eleccion si es seguidor y vence el timeout).
public class NodoRaft {

    enum Estado { SEGUIDOR, CANDIDATO, LIDER }

    // --- identidad y cluster ---
    final int id;
    final int puerto;
    final List<Par> pares;              // los OTROS nodos (no me incluyo)

    // --- estado persistente de Raft ---
    int currentTerm = 0;
    Integer votedFor = null;            // a quien vote en el term actual
    final List<Entrada> log = new ArrayList<>();   // log[0] es indice 1

    // --- estado volatil ---
    volatile Estado estado = Estado.SEGUIDOR;
    int commitIndex = 0;                // mayor indice cometido
    int lastApplied = 0;                // mayor indice aplicado a la maquina de estado
    volatile Integer liderActual = null;

    // --- estado del lider (por seguidor) ---
    final Map<Integer, Integer> nextIndex = new HashMap<>();
    final Map<Integer, Integer> matchIndex = new HashMap<>();

    // --- maquina de estado: el registro de detecciones ya aplicado ---
    final List<String> registro = new ArrayList<>();

    // --- control de tiempo ---
    final Random rnd = new Random();
    volatile long ultimoContacto = 0;   // ultima vez que oimos al lider o votamos
    int timeoutEleccion;                // aleatorio 150-300 ms (rango del profe)
    static final int HEARTBEAT_MS = 50;

    final Object lock = new Object();    // protege todo el estado mutable
    volatile boolean corriendo = true;
    ServerSocket servidor;

    public NodoRaft(int id, int puerto, List<Par> pares) {
        this.id = id;
        this.puerto = puerto;
        this.pares = pares;
        nuevoTimeout();
    }

    void nuevoTimeout() {
        timeoutEleccion = 150 + rnd.nextInt(151); // [150, 300]
    }

    // ---------------------------------------------------------------
    // Arranque: un hilo escucha conexiones, otro corre el bucle de tiempo.
    // ---------------------------------------------------------------
    public void iniciar() throws IOException {
        servidor = new ServerSocket(puerto);
        ultimoContacto = ahora();
        log("nodo " + id + " escuchando en puerto " + puerto + " (seguidor)");

        Thread aceptador = new Thread(this::bucleAceptar, "raft-accept-" + id);
        aceptador.setDaemon(true);
        aceptador.start();

        Thread reloj = new Thread(this::bucleTiempo, "raft-timer-" + id);
        reloj.setDaemon(true);
        reloj.start();
    }

    public void detener() {
        corriendo = false;
        try { if (servidor != null) servidor.close(); } catch (IOException ignore) {}
    }

    long ahora() { return System.currentTimeMillis(); }

    void bucleAceptar() {
        while (corriendo) {
            try {
                Socket s = servidor.accept();
                Thread t = new Thread(() -> atender(s), "raft-conn-" + id);
                t.setDaemon(true);
                t.start();
            } catch (IOException e) {
                if (corriendo) log("error aceptando: " + e.getMessage());
            }
        }
    }

    // ---------------------------------------------------------------
    // Bucle de tiempo: heartbeats como lider, o disparar eleccion como seguidor.
    // ---------------------------------------------------------------
    void bucleTiempo() {
        while (corriendo) {
            try { Thread.sleep(15); } catch (InterruptedException e) { return; }
            Estado est = estado;
            if (est == Estado.LIDER) {
                enviarHeartbeats();
                dormir(HEARTBEAT_MS);
            } else {
                if (ahora() - ultimoContacto >= timeoutEleccion) {
                    iniciarEleccion();
                }
            }
        }
    }

    void dormir(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignore) {}
    }

    // ---------------------------------------------------------------
    // ELECCION: incremento term, voto por mi, pido votos en paralelo.
    // ---------------------------------------------------------------
    void iniciarEleccion() {
        int termEleccion;
        int ultIdx, ultTerm;
        synchronized (lock) {
            estado = Estado.CANDIDATO;
            currentTerm++;
            votedFor = id;
            liderActual = null;
            nuevoTimeout();
            ultimoContacto = ahora();
            termEleccion = currentTerm;
            ultIdx = log.size();
            ultTerm = ultIdx > 0 ? log.get(ultIdx - 1).term : 0;
        }
        log("inicia eleccion en term " + termEleccion);

        // 1 voto (el mio). Cuento votos de forma concurrente.
        final int[] votos = {1};
        final int mayoria = (pares.size() + 1) / 2 + 1;
        List<Thread> hilos = new ArrayList<>();

        for (Par p : pares) {
            Thread t = new Thread(() -> {
                String resp = enviar(p, Protocolo.unir(
                        Protocolo.REQUEST_VOTE, termEleccion, id, ultIdx, ultTerm));
                if (resp == null) return;
                String[] c = Protocolo.partir(resp);
                if (!c[0].equals(Protocolo.VOTE)) return;
                int termResp = Integer.parseInt(c[1]);
                boolean otorgado = c[2].equals("1");
                synchronized (lock) {
                    if (termResp > currentTerm) { volverSeguidor(termResp); return; }
                    if (estado != Estado.CANDIDATO || currentTerm != termEleccion) return;
                    if (otorgado) {
                        votos[0]++;
                        if (votos[0] >= mayoria) volverLider();
                    }
                }
            });
            t.setDaemon(true);
            t.start();
            hilos.add(t);
        }
        // no bloqueo el bucle de tiempo mas de lo necesario
        for (Thread t : hilos) {
            try { t.join(200); } catch (InterruptedException ignore) {}
        }
    }

    void volverLider() {
        if (estado == Estado.LIDER) return;
        estado = Estado.LIDER;
        liderActual = id;
        int sig = log.size() + 1;
        for (Par p : pares) {
            nextIndex.put(p.id, sig);
            matchIndex.put(p.id, 0);
        }
        log("*** soy LIDER en term " + currentTerm + " ***");
        enviarHeartbeats();
    }

    void volverSeguidor(int term) {
        currentTerm = term;
        estado = Estado.SEGUIDOR;
        votedFor = null;
        ultimoContacto = ahora();
    }

    // ---------------------------------------------------------------
    // HEARTBEATS / REPLICACION: el lider manda AppendEntries a cada seguidor.
    // ---------------------------------------------------------------
    void enviarHeartbeats() {
        for (Par p : pares) {
            Thread t = new Thread(() -> replicarA(p), "repl-" + p.id);
            t.setDaemon(true);
            t.start();
        }
    }

    void replicarA(Par p) {
        int term, prevIdx, prevTerm, commit;
        List<Entrada> aEnviar;
        synchronized (lock) {
            if (estado != Estado.LIDER) return;
            term = currentTerm;
            int ni = nextIndex.getOrDefault(p.id, log.size() + 1);
            prevIdx = ni - 1;
            prevTerm = prevIdx > 0 && prevIdx <= log.size() ? log.get(prevIdx - 1).term : 0;
            aEnviar = new ArrayList<>();
            for (int i = ni; i <= log.size(); i++) aEnviar.add(log.get(i - 1));
            commit = commitIndex;
        }

        StringBuilder ent = new StringBuilder();
        for (int i = 0; i < aEnviar.size(); i++) {
            if (i > 0) ent.append(Protocolo.SEP_ENTRADAS);
            ent.append(aEnviar.get(i).serializar());
        }

        String resp = enviar(p, Protocolo.unir(
                Protocolo.APPEND, term, id, prevIdx, prevTerm, commit, ent.toString()));
        if (resp == null) return;

        String[] c = Protocolo.partir(resp);
        if (!c[0].equals(Protocolo.APPEND_OK)) return;
        int termResp = Integer.parseInt(c[1]);
        boolean exito = c[2].equals("1");
        int match = Integer.parseInt(c[3]);

        synchronized (lock) {
            if (termResp > currentTerm) { volverSeguidor(termResp); return; }
            if (estado != Estado.LIDER || term != currentTerm) return;
            if (exito) {
                matchIndex.put(p.id, match);
                nextIndex.put(p.id, match + 1);
                recalcularCommit();
            } else {
                // el seguidor rechazo: retrocedo nextIndex y reintentare
                int ni = nextIndex.getOrDefault(p.id, log.size() + 1);
                nextIndex.put(p.id, Math.max(1, ni - 1));
            }
        }
    }

    // Un indice se comete cuando esta en la mayoria Y es del term actual del lider
    // (regla del profe: no cometer entradas de terms pasados contando replicas).
    void recalcularCommit() {
        for (int n = log.size(); n > commitIndex; n--) {
            if (log.get(n - 1).term != currentTerm) continue;
            int cuenta = 1; // yo
            for (Par p : pares) if (matchIndex.getOrDefault(p.id, 0) >= n) cuenta++;
            if (cuenta >= (pares.size() + 1) / 2 + 1) {
                commitIndex = n;
                aplicar();
                break;
            }
        }
    }

    // Aplica a la maquina de estado (el registro) todo lo cometido y no aplicado.
    void aplicar() {
        while (lastApplied < commitIndex) {
            lastApplied++;
            String comando = log.get(lastApplied - 1).comando;
            registro.add(comando);
            log("aplica[" + lastApplied + "]: " + comando);
        }
    }

    // ---------------------------------------------------------------
    // ATENCION DE MENSAJES ENTRANTES (una conexion = un hilo).
    // ---------------------------------------------------------------
    void atender(Socket s) {
        try (Socket sk = s;
             BufferedReader in = new BufferedReader(new InputStreamReader(sk.getInputStream()));
             BufferedWriter out = new BufferedWriter(new OutputStreamWriter(sk.getOutputStream()))) {
            String linea = in.readLine();
            if (linea == null) return;
            String resp = procesar(linea);
            if (resp != null) { out.write(resp); out.write("\n"); out.flush(); }
        } catch (IOException e) {
            // conexion caida: normal cuando un nodo muere
        }
    }

    String procesar(String linea) {
        String[] c = Protocolo.partir(linea);
        switch (c[0]) {
            case "REQUEST_VOTE": return onRequestVote(c);
            case "APPEND":       return onAppend(c);
            case "NUEVA_DETECCION": return onNuevaDeteccion(c);
            case "LEER_REGISTRO":   return onLeerRegistro();
            default: return null;
        }
    }

    // REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
    String onRequestVote(String[] c) {
        int term = Integer.parseInt(c[1]);
        int cand = Integer.parseInt(c[2]);
        int candUltIdx = Integer.parseInt(c[3]);
        int candUltTerm = Integer.parseInt(c[4]);
        synchronized (lock) {
            if (term > currentTerm) volverSeguidor(term);
            boolean otorgar = false;
            if (term >= currentTerm && (votedFor == null || votedFor == cand)) {
                // restriccion de eleccion: el log del candidato debe estar al menos
                // tan actualizado como el mio (ultimo term, luego longitud).
                int miUltIdx = log.size();
                int miUltTerm = miUltIdx > 0 ? log.get(miUltIdx - 1).term : 0;
                boolean alMenosActual = candUltTerm > miUltTerm
                        || (candUltTerm == miUltTerm && candUltIdx >= miUltIdx);
                if (alMenosActual) {
                    otorgar = true;
                    votedFor = cand;
                    ultimoContacto = ahora();
                }
            }
            return Protocolo.unir(Protocolo.VOTE, currentTerm, otorgar ? 1 : 0);
        }
    }

    // APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
    String onAppend(String[] c) {
        int term = Integer.parseInt(c[1]);
        int lider = Integer.parseInt(c[2]);
        int prevIdx = Integer.parseInt(c[3]);
        int prevTerm = Integer.parseInt(c[4]);
        int commitLider = Integer.parseInt(c[5]);
        String entradasStr = c[6];

        synchronized (lock) {
            if (term < currentTerm) {
                return Protocolo.unir(Protocolo.APPEND_OK, currentTerm, 0, 0);
            }
            if (term > currentTerm) volverSeguidor(term);
            estado = Estado.SEGUIDOR;
            liderActual = lider;
            ultimoContacto = ahora();

            // verificacion de consistencia (Log Matching)
            if (prevIdx > 0) {
                if (log.size() < prevIdx || log.get(prevIdx - 1).term != prevTerm) {
                    return Protocolo.unir(Protocolo.APPEND_OK, currentTerm, 0, 0);
                }
            }

            // aplico las entradas nuevas a partir de prevIdx+1
            if (!entradasStr.isEmpty()) {
                String[] items = entradasStr.split(Protocolo.SEP_ENTRADAS, -1);
                int idx = prevIdx;
                for (String it : items) {
                    idx++;
                    Entrada e = Entrada.deserializar(it);
                    if (log.size() >= idx) {
                        // si hay conflicto (mismo indice, distinto term), trunco
                        if (log.get(idx - 1).term != e.term) {
                            while (log.size() >= idx) log.remove(log.size() - 1);
                            log.add(e);
                        }
                        // si coincide, no hago nada (idempotente)
                    } else {
                        log.add(e);
                    }
                }
            }

            // avanzo mi commit hasta lo que diga el lider
            if (commitLider > commitIndex) {
                commitIndex = Math.min(commitLider, log.size());
                aplicar();
            }
            return Protocolo.unir(Protocolo.APPEND_OK, currentTerm, 1, log.size());
        }
    }

    // NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara  (un cliente inserta)
    String onNuevaDeteccion(String[] c) {
        synchronized (lock) {
            if (estado != Estado.LIDER) {
                if (liderActual != null) {
                    Par l = buscarPar(liderActual);
                    if (l != null) return Protocolo.unir(Protocolo.REDIRECT, l.direccion());
                }
                return Protocolo.unir(Protocolo.REDIRECT, "?");
            }
            // soy lider: agrego al log y dejo que la replicacion lo comprometa
            log.add(new Entrada(currentTerm, c[1]));
            log("cliente inserta: " + c[1] + " (indice " + log.size() + ")");
        }
        enviarHeartbeats(); // empuja la replicacion de una vez
        return Protocolo.OK;
    }

    // LEER_REGISTRO -> devuelvo la maquina de estado (solo lo cometido y aplicado)
    String onLeerRegistro() {
        synchronized (lock) {
            if (estado != Estado.LIDER) {
                if (liderActual != null) {
                    Par l = buscarPar(liderActual);
                    if (l != null) return Protocolo.unir(Protocolo.REDIRECT, l.direccion());
                }
                return Protocolo.unir(Protocolo.REDIRECT, "?");
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < registro.size(); i++) {
                if (i > 0) sb.append(Protocolo.SEP_ENTRADAS);
                sb.append(registro.get(i));
            }
            return Protocolo.unir(Protocolo.REGISTRO, sb.toString());
        }
    }

    Par buscarPar(int idBuscado) {
        if (idBuscado == id) return new Par(id, "127.0.0.1", puerto);
        for (Par p : pares) if (p.id == idBuscado) return p;
        return null;
    }

    // ---------------------------------------------------------------
    // Envio de un mensaje a un par y lectura de su respuesta (una linea).
    // ---------------------------------------------------------------
    String enviar(Par p, String mensaje) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(p.host, p.puerto), 120);
            s.setSoTimeout(200);
            BufferedWriter out = new BufferedWriter(new OutputStreamWriter(s.getOutputStream()));
            BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream()));
            out.write(mensaje); out.write("\n"); out.flush();
            return in.readLine();
        } catch (IOException e) {
            return null; // par caido o inalcanzable
        }
    }

    void log(String m) {
        System.out.println("[nodo " + id + "] " + m);
    }
}
