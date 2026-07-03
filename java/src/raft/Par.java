package raft;

// Direccion host:puerto de un nodo del cluster. Simple, sin librerias.
public class Par {
    public final int id;
    public final String host;
    public final int puerto;

    public Par(int id, String host, int puerto) {
        this.id = id;
        this.host = host;
        this.puerto = puerto;
    }

    public String direccion() {
        return host + ":" + puerto;
    }
}
