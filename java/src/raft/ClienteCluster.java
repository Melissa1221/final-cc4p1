package raft;

import java.io.*;
import java.net.*;
import java.util.*;

// Cliente para hablar con el cluster Raft desde cualquier lenguaje/proceso.
// Lo usa el Servidor de Testeo (para insertar detecciones) y el Cliente Vigilante
// (para leer el registro). Maneja el REDIRECT: si contacto un seguidor, me manda
// al lider y reintento alli.
public class ClienteCluster {

    private final List<Par> nodos;
    private Par ultimoLider;   // recuerdo al lider para no reintentar desde cero

    public ClienteCluster(List<Par> nodos) {
        this.nodos = nodos;
    }

    // Inserta una deteccion. Devuelve true si el cluster la acepto.
    public boolean insertar(String tipo, String imagenRef, String fechaHora, String camara) {
        String cmd = tipo + "," + imagenRef + "," + fechaHora + "," + camara;
        String resp = pedir(Protocolo.unir(Protocolo.NUEVA_DETECCION, cmd));
        return resp != null && resp.equals(Protocolo.OK);
    }

    // Lee el registro cometido. Devuelve la lista de detecciones (cada una es el
    // string  tipo,imagenRef,fechaHora,camara ).
    public List<String> leerRegistro() {
        String resp = pedir(Protocolo.LEER_REGISTRO);
        List<String> out = new ArrayList<>();
        if (resp == null) return out;
        String[] c = Protocolo.partir(resp);
        if (!c[0].equals(Protocolo.REGISTRO)) return out;
        if (c[1].isEmpty()) return out;
        for (String d : c[1].split(Protocolo.SEP_ENTRADAS, -1)) out.add(d);
        return out;
    }

    // Envia un mensaje probando nodos hasta dar con el lider (siguiendo REDIRECT).
    // En cada intento se recalcula el orden para priorizar al lider conocido, asi
    // que un REDIRECT en el intento N ya se aprovecha en el intento N+1.
    private String pedir(String mensaje) {
        for (int intento = 0; intento < nodos.size() * 2 + 4; intento++) {
            // arma el orden con el lider conocido primero
            List<Par> orden = new ArrayList<>();
            if (ultimoLider != null) orden.add(ultimoLider);
            for (Par p : nodos) if (ultimoLider == null || p.id != ultimoLider.id) orden.add(p);

            boolean redirigido = false;
            for (Par p : orden) {
                String resp = enviar(p, mensaje);
                if (resp == null) continue;
                String[] c = Protocolo.partir(resp);
                if (c[0].equals(Protocolo.REDIRECT)) {
                    Par lider = porDireccion(c[1]);
                    if (lider != null && (ultimoLider == null || lider.id != ultimoLider.id)) {
                        ultimoLider = lider;
                        redirigido = true;
                        break; // reintento de una vez contra el lider correcto
                    }
                    // REDIRECT a "?" o al mismo: sigo probando otros nodos
                    continue;
                }
                ultimoLider = p;
                return resp;
            }
            if (!redirigido) dormir(80); // el cluster puede estar en eleccion
        }
        return null;
    }

    private Par porDireccion(String dir) {
        for (Par p : nodos) if (p.direccion().equals(dir)) return p;
        return null;
    }

    private String enviar(Par p, String mensaje) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(p.host, p.puerto), 150);
            s.setSoTimeout(400);
            BufferedWriter out = new BufferedWriter(new OutputStreamWriter(s.getOutputStream()));
            BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream()));
            out.write(mensaje); out.write("\n"); out.flush();
            return in.readLine();
        } catch (IOException e) {
            return null;
        }
    }

    private void dormir(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignore) {}
    }

    public static List<Par> parsearNodos(String[] specs, int desde) {
        List<Par> nodos = new ArrayList<>();
        for (int i = desde; i < specs.length; i++) {
            String[] p = specs[i].split(":");
            nodos.add(new Par(Integer.parseInt(p[0]), p[1], Integer.parseInt(p[2])));
        }
        return nodos;
    }
}
