package raft;

// Una entrada del log replicado. Cada entrada guarda el term en que se creo y el
// comando (para nuestro caso, una deteccion serializada como texto).
// El indice es la posicion en el log (1-based, como en el paper del profe).
public class Entrada {
    public final int term;
    public final String comando;

    public Entrada(int term, String comando) {
        this.term = term;
        this.comando = comando;
    }

    // serializa a  term,comando  (el comando ya viene sin ; ni | conflictivos)
    public String serializar() {
        return term + Protocolo.SEP_CAMPO_ENTRADA + comando;
    }

    public static Entrada deserializar(String s) {
        int coma = s.indexOf(Protocolo.SEP_CAMPO_ENTRADA);
        int t = Integer.parseInt(s.substring(0, coma));
        String cmd = s.substring(coma + 1);
        return new Entrada(t, cmd);
    }
}
