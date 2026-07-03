package raft;

// Protocolo Raft en texto plano sobre TCP crudo.
// Un mensaje por linea, campos separados por |. Sin frameworks, solo sockets.
// Este formato lo comparten los tres lenguajes (Java, Python, Go), asi que hay
// que respetarlo tal cual. Melissa lo documenta porque el nodo Java es la referencia.
//
// Mensajes de Raft (entre nodos):
//   REQUEST_VOTE|term|candidatoId|ultimoLogIndex|ultimoLogTerm
//   VOTE|term|otorgado(1/0)
//   APPEND|term|liderId|prevLogIndex|prevLogTerm|commitIndex|entradas
//   APPEND_OK|term|exito(1/0)|matchIndex
//
//   "entradas" va vacio en los heartbeats. Si trae datos, es una lista de
//   entradas separadas por ; y cada entrada es  term,comando  (el comando a su
//   vez usa comas internas escapadas por el que arma la deteccion).
//
// Mensajes de cliente (servidor de testeo / vigilante hacia el cluster):
//   NUEVA_DETECCION|tipo,imagenRef,fechaHora,camara     -> inserta una deteccion
//   LEER_REGISTRO                                        -> pide todo el registro
//   REGISTRO|det1;det2;det3;...                          -> respuesta al vigilante
//   REDIRECT|hostLider:puertoLider                       -> si contactaron un seguidor
//   OK                                                   -> insercion aceptada
public final class Protocolo {

    public static final String SEP = "\\|";       // para split (| es especial en regex)
    public static final String J = "|";            // para join

    // separadores internos de la lista de entradas del log
    public static final String SEP_ENTRADAS = ";";
    public static final String SEP_CAMPO_ENTRADA = ",";

    // tipos de mensaje
    public static final String REQUEST_VOTE = "REQUEST_VOTE";
    public static final String VOTE = "VOTE";
    public static final String APPEND = "APPEND";
    public static final String APPEND_OK = "APPEND_OK";
    public static final String NUEVA_DETECCION = "NUEVA_DETECCION";
    public static final String LEER_REGISTRO = "LEER_REGISTRO";
    public static final String REGISTRO = "REGISTRO";
    public static final String REDIRECT = "REDIRECT";
    public static final String OK = "OK";

    private Protocolo() {}

    public static String[] partir(String linea) {
        return linea.split(SEP, -1);
    }

    public static String unir(Object... campos) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < campos.length; i++) {
            if (i > 0) sb.append(J);
            sb.append(campos[i]);
        }
        return sb.toString();
    }
}
