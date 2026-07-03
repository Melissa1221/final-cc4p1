package vigilante;

import com.formdev.flatlaf.FlatLightLaf;
import raft.ClienteCluster;
import raft.Par;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

// Cliente Vigilante - la interfaz que ve el registro de detecciones del cluster.
// Se conecta al cluster Raft por sockets (via ClienteCluster) y refresca la tabla
// cada segundo leyendo el registro cometido del lider. Si no se le pasan nodos,
// arranca en modo demo con datos de ejemplo (solo para ver el diseno).
public class Vigilante extends JFrame {

    // Escala de espaciado base 8px. Todo margen o separacion es multiplo de esto.
    static final int GAP = 8;

    // Paleta sobria. FlatLaf ya da el look plano; aca solo los acentos.
    static final Color ACENTO = new Color(37, 99, 235);   // azul de acento
    static final Color VIVO = new Color(22, 163, 74);      // verde "en vivo"
    static final Color TEXTO_TENUE = new Color(107, 114, 128);
    static final Color LINEA = new Color(229, 231, 235);

    private final DefaultTableModel modelo;
    private final ClienteCluster cluster;   // null en modo demo
    private JLabel estadoConexion;

    public Vigilante(ClienteCluster cluster) {
        this.cluster = cluster;
        setTitle("Cliente Vigilante - CC4P1");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(720, 480);
        setMinimumSize(new Dimension(560, 360));
        setLocationRelativeTo(null);

        setLayout(new BorderLayout());
        add(cabecera(), BorderLayout.NORTH);

        modelo = new DefaultTableModel(new Object[]{"Tipo", "Camara", "Fecha y hora"}, 0) {
            @Override public boolean isCellEditable(int r, int c) { return false; }
        };
        add(tabla(), BorderLayout.CENTER);
        add(pie(), BorderLayout.SOUTH);

        if (cluster == null) {
            cargarEjemplo();
        } else {
            iniciarRefresco();
        }
    }

    // Refresca el registro leyendo del cluster cada segundo, en un hilo aparte.
    // El acceso a la tabla se hace en el hilo de Swing con invokeLater.
    private void iniciarRefresco() {
        Thread t = new Thread(() -> {
            while (true) {
                List<String> dets = cluster.leerRegistro();
                boolean conectado = dets != null;
                SwingUtilities.invokeLater(() -> pintar(dets, conectado));
                try { Thread.sleep(1000); } catch (InterruptedException e) { return; }
            }
        }, "vigilante-refresco");
        t.setDaemon(true);
        t.start();
    }

    // Reemplaza el contenido de la tabla con el registro recibido.
    private void pintar(List<String> detecciones, boolean conectado) {
        modelo.setRowCount(0);
        if (detecciones != null) {
            for (String d : detecciones) {
                // formato del comando:  tipo,imagenRef,fechaHora,camara
                String[] campos = d.split(",", -1);
                String tipo = campos.length > 0 ? campos[0] : "?";
                String fechaHora = campos.length > 2 ? campos[2] : "";
                String camara = campos.length > 3 ? campos[3] : "";
                modelo.addRow(new Object[]{tipo, camara, fechaHora});
            }
        }
        contador.setText(modelo.getRowCount() + " detecciones");
        if (estadoConexion != null) {
            estadoConexion.setText(conectado ? "●  en vivo" : "●  sin conexion");
            estadoConexion.setForeground(conectado ? VIVO : new Color(220, 38, 38));
        }
    }

    // Cabecera: titulo a la izquierda, estado "en vivo" a la derecha.
    private JComponent cabecera() {
        JPanel barra = new JPanel(new BorderLayout());
        barra.setBorder(new EmptyBorder(GAP * 2, GAP * 2, GAP * 2, GAP * 2));

        JLabel titulo = new JLabel("Registro de detecciones");
        titulo.setFont(titulo.getFont().deriveFont(Font.BOLD, 18f));

        estadoConexion = new JLabel("●  en vivo");
        estadoConexion.setForeground(VIVO);
        estadoConexion.setFont(estadoConexion.getFont().deriveFont(Font.BOLD, 12f));

        barra.add(titulo, BorderLayout.WEST);
        barra.add(estadoConexion, BorderLayout.EAST);

        JPanel wrap = new JPanel(new BorderLayout());
        wrap.add(barra, BorderLayout.CENTER);
        wrap.add(separador(), BorderLayout.SOUTH);
        return wrap;
    }

    private JComponent separador() {
        JPanel s = new JPanel();
        s.setPreferredSize(new Dimension(0, 1));
        s.setBackground(LINEA);
        return s;
    }

    // Tabla: filas altas, sin lineas verticales, cabecera discreta.
    private JComponent tabla() {
        JTable t = new JTable(modelo);
        t.setRowHeight(44);
        t.setShowVerticalLines(false);
        t.setShowHorizontalLines(true);
        t.setGridColor(LINEA);
        t.setFillsViewportHeight(true);
        t.setFont(t.getFont().deriveFont(14f));
        t.getTableHeader().setFont(t.getTableHeader().getFont().deriveFont(Font.BOLD, 12f));
        t.getTableHeader().setForeground(TEXTO_TENUE);

        DefaultTableCellRenderer pad = new DefaultTableCellRenderer();
        pad.setBorder(new EmptyBorder(0, GAP * 2, 0, GAP * 2));
        for (int c = 0; c < t.getColumnCount(); c++) {
            t.getColumnModel().getColumn(c).setCellRenderer(pad);
        }
        t.getColumnModel().getColumn(0).setPreferredWidth(200);
        t.getColumnModel().getColumn(1).setPreferredWidth(120);

        JScrollPane sc = new JScrollPane(t);
        sc.setBorder(new EmptyBorder(0, GAP, 0, GAP));
        return sc;
    }

    // Pie: contador de registros, alineado y discreto.
    private JLabel contador;
    private JComponent pie() {
        JPanel p = new JPanel(new BorderLayout());
        p.add(separador(), BorderLayout.NORTH);
        contador = new JLabel("0 detecciones");
        contador.setForeground(TEXTO_TENUE);
        contador.setBorder(new EmptyBorder(GAP + 4, GAP * 2, GAP + 4, GAP * 2));
        p.add(contador, BorderLayout.WEST);
        return p;
    }

    // Agrega una deteccion al registro. Esto es lo que llamara el lector del cluster.
    public void agregar(String tipo, String camara, String fechaHora) {
        modelo.addRow(new Object[]{tipo, camara, fechaHora});
        contador.setText(modelo.getRowCount() + " detecciones");
    }

    private void cargarEjemplo() {
        List<String[]> datos = List.of(
            new String[]{"Mujer", "Camara 1", "01/11/2025 03:25"},
            new String[]{"Naranja", "Camara 2", "01/11/2025 15:20"},
            new String[]{"Loro", "Camara 3", "03/11/2025 02:30"},
            new String[]{"Carro", "Camara 1", "05/11/2025 14:00"}
        );
        for (String[] d : datos) agregar(d[0], d[1], d[2]);
    }

    // Sin argumentos: modo demo (datos de ejemplo).
    // Con nodos  id:host:puerto ...: se conecta al cluster y refresca en vivo.
    //   java vigilante.Vigilante 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
    public static void main(String[] args) {
        FlatLightLaf.setup();
        final ClienteCluster cluster;
        if (args.length == 0) {
            cluster = null;
            System.out.println("Vigilante en modo demo (sin cluster). Pasa nodos para conectar.");
        } else {
            List<Par> nodos = ClienteCluster.parsearNodos(args, 0);
            cluster = new ClienteCluster(nodos);
        }
        SwingUtilities.invokeLater(() -> new Vigilante(cluster).setVisible(true));
    }
}
