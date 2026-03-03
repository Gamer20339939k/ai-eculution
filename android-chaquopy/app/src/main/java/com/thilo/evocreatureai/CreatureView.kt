package com.thilo.evocreatureai

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.max

class CreatureView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    data class CreatureShape(
        val color: Int,
        val nodes: List<Pair<Float, Float>>,
        val bones: List<Pair<Int, Int>>,
        val leader: Boolean
    )

    data class FrameData(
        val worldW: Float,
        val worldH: Float,
        val groundY: Float,
        val creatures: List<CreatureShape>
    )

    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#0f172a") }
    private val groundPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#6b4f2d") }
    private val bonePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#94a3b8")
        strokeWidth = 4f
    }
    private val nodePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#7dd3fc") }
    private val leaderOutlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 3f
        color = Color.WHITE
    }

    private var frame: FrameData = FrameData(
        worldW = 1200f,
        worldH = 760f,
        groundY = 640f,
        creatures = emptyList()
    )

    fun setFrame(data: FrameData) {
        frame = data
        invalidate()
    }

    fun clearFrame() {
        frame = frame.copy(creatures = emptyList())
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat().coerceAtLeast(1f)
        val h = height.toFloat().coerceAtLeast(1f)

        canvas.drawRect(0f, 0f, w, h, bgPaint)

        val sx = w / max(1f, frame.worldW)
        val sy = h / max(1f, frame.worldH)
        val gy = frame.groundY * sy
        canvas.drawRect(0f, gy, w, h, groundPaint)

        for (c in frame.creatures) {
            nodePaint.color = c.color

            for (b in c.bones) {
                val a = b.first
                val d = b.second
                if (a !in c.nodes.indices || d !in c.nodes.indices) continue
                val na = c.nodes[a]
                val nb = c.nodes[d]
                canvas.drawLine(na.first * sx, na.second * sy, nb.first * sx, nb.second * sy, bonePaint)
            }

            for (n in c.nodes) {
                val px = n.first * sx
                val py = n.second * sy
                canvas.drawCircle(px, py, 6f, nodePaint)
                if (c.leader) {
                    canvas.drawCircle(px, py, 8f, leaderOutlinePaint)
                }
            }
        }
    }
}
