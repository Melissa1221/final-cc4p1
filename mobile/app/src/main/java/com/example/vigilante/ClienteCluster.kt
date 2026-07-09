package com.example.vigilante

import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets

// Cliente del cluster Raft por sockets TCP nativos (sin frameworks). Es el mismo
// protocolo que usan el Vigilante de escritorio (Java) y el Servidor de Testeo
// (Python): una linea por mensaje, campos separados por |. Aca solo leemos el
// registro (LEER_REGISTRO). Maneja el REDIRECT al lider igual que los otros.
//
// Este cliente se reusa del patron de sockets de la PC4 (ChatClient): abrir
// socket, escribir una linea, leer la respuesta, cerrar. La lectura de red NUNCA
// va en el hilo principal de Android (ver VigilanteViewModel / MainActivity).

// una deteccion parseada del registro: tipo,imagenRef,fechaHora,camara
data class Deteccion(
    val tipo: String,
    val imagenRef: String,
    val fechaHora: String,
    val camara: String
)

class ClienteCluster(private val nodos: List<Triple<Int, String, Int>>) {

    // recordamos al ultimo lider para no reintentar desde cero
    private var ultimoLider: Triple<Int, String, Int>? = null

    // Lee el registro cometido del cluster. Devuelve la lista de detecciones,
    // o null si no se pudo contactar a nadie (cluster caido o en eleccion).
    fun leerRegistro(): List<Deteccion>? {
        val resp = pedir("LEER_REGISTRO") ?: return null
        val c = resp.split("|")
        if (c.isEmpty() || c[0] != "REGISTRO") return emptyList()
        if (c.size < 2 || c[1].isEmpty()) return emptyList()
        return c[1].split(";").mapNotNull { parsearDeteccion(it) }
    }

    private fun parsearDeteccion(s: String): Deteccion? {
        val campos = s.split(",")
        if (campos.isEmpty()) return null
        return Deteccion(
            tipo = campos.getOrElse(0) { "?" },
            imagenRef = campos.getOrElse(1) { "" },
            fechaHora = campos.getOrElse(2) { "" },
            camara = campos.getOrElse(3) { "" }
        )
    }

    // Envia un mensaje probando nodos hasta dar con el lider (siguiendo REDIRECT).
    // Recalcula el orden en cada intento para priorizar al lider conocido.
    private fun pedir(mensaje: String): String? {
        val intentosMax = nodos.size * 2 + 4
        for (intento in 0 until intentosMax) {
            val orden = ArrayList<Triple<Int, String, Int>>()
            ultimoLider?.let { orden.add(it) }
            for (n in nodos) {
                if (ultimoLider == null || n.first != ultimoLider!!.first) orden.add(n)
            }

            var redirigido = false
            for (n in orden) {
                val resp = enviar(n.second, n.third, mensaje) ?: continue
                val c = resp.split("|")
                if (c[0] == "REDIRECT") {
                    val lider = porDireccion(c.getOrElse(1) { "" })
                    if (lider != null &&
                        (ultimoLider == null || lider.first != ultimoLider!!.first)) {
                        ultimoLider = lider
                        redirigido = true
                        break
                    }
                    continue
                }
                ultimoLider = n
                return resp
            }
            if (!redirigido) {
                try { Thread.sleep(80) } catch (e: InterruptedException) { return null }
            }
        }
        return null
    }

    private fun porDireccion(dir: String): Triple<Int, String, Int>? {
        for (n in nodos) if ("${n.second}:${n.third}" == dir) return n
        return null
    }

    // Abre socket, manda una linea, lee la respuesta, cierra. Timeouts cortos
    // para que un nodo caido no cuelgue la app.
    private fun enviar(host: String, puerto: Int, mensaje: String): String? {
        var socket: Socket? = null
        return try {
            socket = Socket()
            socket.connect(InetSocketAddress(host, puerto), 300)
            socket.soTimeout = 600
            val out = BufferedWriter(
                OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))
            val input = BufferedReader(
                InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
            out.write(mensaje)
            out.write("\n")
            out.flush()
            input.readLine()
        } catch (e: Exception) {
            null
        } finally {
            try { socket?.close() } catch (e: Exception) {}
        }
    }

    companion object {
        // parsea specs "id:host:puerto" separados por coma o espacio
        fun parsearNodos(texto: String): List<Triple<Int, String, Int>> {
            return texto.split(Regex("[,\\s]+"))
                .filter { it.isNotBlank() }
                .mapNotNull { spec ->
                    val p = spec.split(":")
                    if (p.size != 3) return@mapNotNull null
                    val id = p[0].toIntOrNull() ?: return@mapNotNull null
                    val puerto = p[2].toIntOrNull() ?: return@mapNotNull null
                    Triple(id, p[1], puerto)
                }
        }
    }
}
