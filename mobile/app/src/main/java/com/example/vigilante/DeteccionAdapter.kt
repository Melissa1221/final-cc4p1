package com.example.vigilante

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

// Adapter del RecyclerView que muestra el registro de detecciones. Cada fila
// muestra tipo, camara y fecha/hora. La imagen del objeto se guarda en el
// servidor (imagenRef); en el movil se muestra la referencia (en una version
// con servidor de imagenes se cargaria el PNG por HTTP, pero eso saldria del
// alcance de "solo sockets nativos", asi que aca mostramos el dato del registro).
class DeteccionAdapter(
    private var items: List<Deteccion>
) : RecyclerView.Adapter<DeteccionAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tipo: TextView = v.findViewById(R.id.txtTipo)
        val camara: TextView = v.findViewById(R.id.txtCamara)
        val fecha: TextView = v.findViewById(R.id.txtFecha)
        val imagen: TextView = v.findViewById(R.id.txtImagen)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_deteccion, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val d = items[position]
        holder.tipo.text = d.tipo
        holder.camara.text = d.camara
        holder.fecha.text = d.fechaHora
        holder.imagen.text = d.imagenRef.substringAfterLast('/')
    }

    override fun getItemCount(): Int = items.size

    fun actualizar(nuevos: List<Deteccion>) {
        items = nuevos
        notifyDataSetChanged()
    }
}
