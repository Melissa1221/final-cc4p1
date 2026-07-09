package com.example.vigilante

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlin.concurrent.thread

// Cliente Vigilante MOVIL (Android nativo). Se conecta al cluster Raft por
// socket (mismo protocolo LEER_REGISTRO que el vigilante de escritorio) y
// muestra el registro de detecciones, refrescando cada segundo.
//
// El campo "nodos" acepta specs id:host:puerto separados por coma, por ejemplo:
//   1:10.0.2.2:9911, 2:10.0.2.2:9912, 3:10.0.2.2:9913
// (10.0.2.2 es el localhost de la maquina host visto desde el emulador de Android)
class MainActivity : AppCompatActivity() {

    private lateinit var txtNodos: EditText
    private lateinit var btnConectar: Button
    private lateinit var txtEstado: TextView
    private lateinit var lista: RecyclerView
    private lateinit var adapter: DeteccionAdapter

    private var cluster: ClienteCluster? = null
    private var refrescando = false
    private val hiloUi = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        txtNodos = findViewById(R.id.txtNodos)
        btnConectar = findViewById(R.id.btnConectar)
        txtEstado = findViewById(R.id.txtEstado)
        lista = findViewById(R.id.listaDetecciones)

        adapter = DeteccionAdapter(emptyList())
        lista.layoutManager = LinearLayoutManager(this)
        lista.adapter = adapter

        // valor por defecto util para el emulador
        txtNodos.setText("1:10.0.2.2:9911, 2:10.0.2.2:9912, 3:10.0.2.2:9913")

        btnConectar.setOnClickListener { conectar() }
    }

    private fun conectar() {
        val nodos = ClienteCluster.parsearNodos(txtNodos.text.toString())
        if (nodos.isEmpty()) {
            txtEstado.text = "Nodos invalidos (usa id:host:puerto)"
            return
        }
        cluster = ClienteCluster(nodos)
        txtEstado.text = "Conectando..."
        if (!refrescando) {
            refrescando = true
            iniciarRefresco()
        }
    }

    // Un hilo lee el registro del cluster cada segundo; la UI se toca solo desde
    // el hilo principal (runOnUiThread). Igual que en la PC4, la red no va en el
    // hilo de UI.
    private fun iniciarRefresco() {
        thread(isDaemon = true) {
            while (refrescando) {
                val c = cluster
                if (c != null) {
                    val dets = c.leerRegistro()
                    runOnUiThread { pintar(dets) }
                }
                try { Thread.sleep(1000) } catch (e: InterruptedException) { break }
            }
        }
    }

    private fun pintar(dets: List<Deteccion>?) {
        if (dets == null) {
            txtEstado.text = "sin conexion"
            return
        }
        txtEstado.text = "en vivo - ${dets.size} detecciones"
        adapter.actualizar(dets)
    }

    override fun onDestroy() {
        refrescando = false
        super.onDestroy()
    }
}
