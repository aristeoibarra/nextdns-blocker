package com.ndb.blocker

import android.animation.ValueAnimator
import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.widget.LinearLayout
import android.widget.TextView

class CollapsibleSection(context: Context) : LinearLayout(context) {

    private val header: View
    private val titleTv: TextView
    private val countTv: TextView
    private val arrowTv: TextView
    private val colorBar: View
    private val content: LinearLayout
    private var expanded = false

    init {
        orientation = VERTICAL
        layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)

        LayoutInflater.from(context).inflate(R.layout.view_collapsible_section, this, true)

        header = findViewById(R.id.sectionHeader)
        titleTv = findViewById(R.id.sectionTitle)
        countTv = findViewById(R.id.sectionCount)
        arrowTv = findViewById(R.id.sectionArrow)
        colorBar = findViewById(R.id.sectionColorBar)
        content = findViewById(R.id.sectionContent)

        header.setOnClickListener { toggle() }
    }

    fun setTitle(title: String) {
        titleTv.text = title
    }

    fun setCount(count: Int) {
        countTv.text = count.toString()
    }

    fun setBarColor(color: Int) {
        colorBar.setBackgroundColor(color)
    }

    fun getContentContainer(): LinearLayout = content

    fun toggle() {
        if (expanded) collapse() else expand()
    }

    fun expand() {
        expanded = true
        content.visibility = View.VISIBLE
        content.alpha = 0f
        content.animate().alpha(1f).setDuration(200).setInterpolator(DecelerateInterpolator()).start()
        arrowTv.animate().rotation(180f).setDuration(200).start()
    }

    fun collapse() {
        expanded = false
        content.animate().alpha(0f).setDuration(150).setInterpolator(DecelerateInterpolator()).withEndAction {
            content.visibility = View.GONE
        }.start()
        arrowTv.animate().rotation(0f).setDuration(200).start()
    }

    fun isExpanded(): Boolean = expanded
}
