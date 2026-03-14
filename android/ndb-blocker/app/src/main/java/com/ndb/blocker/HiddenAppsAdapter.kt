package com.ndb.blocker

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class HiddenAppsAdapter(
    private val onLongPress: (AppModel) -> Unit
) : RecyclerView.Adapter<HiddenAppsAdapter.VH>() {

    private var items: List<AppModel> = emptyList()

    fun submit(apps: List<AppModel>) {
        items = apps
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_hidden_app, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val app = items[position]
        holder.name.text = app.label
        holder.icon.setImageDrawable(app.icon)
        holder.itemView.setOnLongClickListener {
            onLongPress(app)
            true
        }
    }

    override fun getItemCount() = items.size

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val icon: ImageView = view.findViewById(R.id.ivAppIcon)
        val name: TextView = view.findViewById(R.id.tvAppName)
    }
}
