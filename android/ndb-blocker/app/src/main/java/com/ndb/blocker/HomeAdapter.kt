package com.ndb.blocker

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class HomeAdapter(
    private val onTap: (String) -> Unit,
    private val onLongPress: (String, String) -> Unit
) : RecyclerView.Adapter<HomeAdapter.VH>() {

    private var items: List<AppModel> = emptyList()

    fun submit(apps: List<AppModel>) {
        items = apps.sortedWith(compareBy({ it.label.length }, { it.label.lowercase() }))
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_home_app, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val app = items[position]
        holder.name.text = app.label
        holder.name.setOnClickListener { onTap(app.packageName) }
        holder.name.setOnLongClickListener {
            onLongPress(app.packageName, app.label)
            true
        }
    }

    override fun getItemCount() = items.size

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvAppName)
    }
}
