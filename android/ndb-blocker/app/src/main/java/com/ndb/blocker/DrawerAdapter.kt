package com.ndb.blocker

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Filter
import android.widget.Filterable
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class DrawerAdapter(
    private val onTap: (String) -> Unit,
    private val onLongPress: (AppModel, View) -> Unit
) : RecyclerView.Adapter<DrawerAdapter.VH>(), Filterable {

    private var allItems: List<AppModel> = emptyList()
    private var filtered: List<AppModel> = emptyList()

    fun submit(apps: List<AppModel>) {
        allItems = apps
        filtered = apps
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_drawer_app, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val app = filtered[position]
        holder.name.text = app.label
        holder.itemView.setOnClickListener { onTap(app.packageName) }
        holder.itemView.setOnLongClickListener {
            onLongPress(app, it)
            true
        }
    }

    override fun getItemCount() = filtered.size

    override fun getFilter(): Filter = object : Filter() {
        override fun performFiltering(query: CharSequence?): FilterResults {
            val q = query?.toString()?.lowercase() ?: ""
            val list = if (q.isEmpty()) allItems
            else allItems.filter { it.label.lowercase().contains(q) }
            return FilterResults().apply { values = list }
        }

        @Suppress("UNCHECKED_CAST")
        override fun publishResults(query: CharSequence?, results: FilterResults?) {
            filtered = results?.values as? List<AppModel> ?: allItems
            notifyDataSetChanged()
        }
    }

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvAppName)
    }
}
