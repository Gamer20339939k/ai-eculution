package com.thilo.evocreatureai

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.hypot
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

    data class TemplateData(
        val worldW: Float,
        val worldH: Float,
        val groundY: Float,
        val name: String,
        val nodes: List<Pair<Float, Float>>,
        val bones: List<Pair<Int, Int>>,
        val muscles: List<Pair<Int, Int>>,
        val selectedNodes: Set<Int> = emptySet()
    )

    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#0f172a") }
    private val groundPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#6b4f2d") }
    private val bonePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#94a3b8")
        strokeWidth = 4f
    }
    private val musclePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#fb923c")
        strokeWidth = 4f
    }
    private val nodePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#7dd3fc") }
    private val leaderOutlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 3f
        color = Color.WHITE
    }
    private val selectedPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 4f
        color = Color.parseColor("#facc15")
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#e5e7eb")
        textSize = 26f
    }

    private var frame: FrameData = FrameData(1200f, 760f, 640f, emptyList())
    private var template: TemplateData = TemplateData(1200f, 760f, 640f, "Template", emptyList(), emptyList(), emptyList())
    private var editMode = false

    fun setFrame(data: FrameData) {
        frame = data
        invalidate()
    }

    fun setTemplate(data: TemplateData) {
        template = data
        invalidate()
    }

    fun setEditMode(enabled: Boolean) {
        editMode = enabled
        invalidate()
    }

    fun isEditMode(): Boolean = editMode

    fun screenToWorld(screenX: Float, screenY: Float): Pair<Float, Float> {
        val srcW = if (editMode) template.worldW else frame.worldW
        val srcH = if (editMode) template.worldH else frame.worldH
        val sx = width.toFloat().coerceAtLeast(1f) / max(1f, srcW)
        val sy = height.toFloat().coerceAtLeast(1f) / max(1f, srcH)
        return Pair(screenX / sx, screenY / sy)
    }

    fun findNodeAtScreen(screenX: Float, screenY: Float, maxRadiusPx: Float = 28f): Int {
        if (!editMode) return -1
        val sx = width.toFloat().coerceAtLeast(1f) / max(1f, template.worldW)
        val sy = height.toFloat().coerceAtLeast(1f) / max(1f, template.worldH)
        var best = -1
        var bestDist = maxRadiusPx.toDouble()
        for (i in template.nodes.indices) {
            val n = template.nodes[i]
            val px = n.first * sx
            val py = n.second * sy
            val d = hypot((px - screenX).toDouble(), (py - screenY).toDouble())
            if (d <= bestDist) {
                best = i
                bestDist = d
            }
        }
        return best
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat().coerceAtLeast(1f)
        val h = height.toFloat().coerceAtLeast(1f)

        canvas.drawRect(0f, 0f, w, h, bgPaint)

        if (editMode) {
            drawTemplate(canvas, w, h)
        } else {
            drawSimulation(canvas, w, h)
        }
    }

    private fun drawSimulation(canvas: Canvas, w: Float, h: Float) {
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
                if (c.leader) canvas.drawCircle(px, py, 8f, leaderOutlinePaint)
            }
        }
        canvas.drawText("SIM", 14f, 28f, textPaint)
    }

    private fun drawTemplate(canvas: Canvas, w: Float, h: Float) {
        val sx = w / max(1f, template.worldW)
        val sy = h / max(1f, template.worldH)
        val gy = template.groundY * sy
        canvas.drawRect(0f, gy, w, h, groundPaint)

        for (b in template.bones) {
            if (b.first !in template.nodes.indices || b.second !in template.nodes.indices) continue
            val na = template.nodes[b.first]
            val nb = template.nodes[b.second]
            canvas.drawLine(na.first * sx, na.second * sy, nb.first * sx, nb.second * sy, bonePaint)
        }

        for (m in template.muscles) {
            if (m.first !in template.bones.indices || m.second !in template.bones.indices) continue
            val b1 = template.bones[m.first]
            val b2 = template.bones[m.second]
            if (b1.first !in template.nodes.indices || b1.second !in template.nodes.indices) continue
            if (b2.first !in template.nodes.indices || b2.second !in template.nodes.indices) continue
            val a1 = template.nodes[b1.first]
            val a2 = template.nodes[b1.second]
            val c1 = template.nodes[b2.first]
            val c2 = template.nodes[b2.second]
            val m1x = (a1.first + a2.first) * 0.5f
            val m1y = (a1.second + a2.second) * 0.5f
            val m2x = (c1.first + c2.first) * 0.5f
            val m2y = (c1.second + c2.second) * 0.5f
            canvas.drawLine(m1x * sx, m1y * sy, m2x * sx, m2y * sy, musclePaint)
        }

        for (i in template.nodes.indices) {
            val n = template.nodes[i]
            val px = n.first * sx
            val py = n.second * sy
            canvas.drawCircle(px, py, 8f, nodePaint)
            if (i in template.selectedNodes) {
                canvas.drawCircle(px, py, 13f, selectedPaint)
            }
        }
        canvas.drawText("EDIT: ${template.name}", 14f, 28f, textPaint)
    }
}
