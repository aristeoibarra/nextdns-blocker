package com.ndb.blocker

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
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
        holder.name.setOnClickListener {
            val intent = it.context.packageManager.getLaunchIntentForPackage(app.packageName)
            if (intent != null) it.context.startActivity(intent)
        }
        holder.name.setOnLongClickListener {
            onLongPress(app)
            true
        }
    }

    override fun getItemCount() = items.size

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvAppName)
    }
}
