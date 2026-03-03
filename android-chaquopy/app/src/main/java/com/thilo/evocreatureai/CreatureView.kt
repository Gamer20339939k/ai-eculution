package com.thilo.evocreatureai

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.max
import kotlin.math.min

class CreatureView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private val bodyPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#7dd3fc") }
    private val limbPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#94a3b8")
        strokeWidth = 8f
    }
    private val groundPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#6b4f2d") }

    private var x = 200f
    private var y = 260f
    private var vx = 0f
    private var vy = 0f
    private var moveDir = 0f
    private var jumpRequested = false

    fun setMoveDir(dir: Float) {
        moveDir = dir
    }

    fun requestJump() {
        jumpRequested = true
    }

    fun resetCreature() {
        x = 200f
        y = 260f
        vx = 0f
        vy = 0f
    }

    fun step(dt: Float = 1f / 60f) {
        val h = height.toFloat().coerceAtLeast(1f)
        val w = width.toFloat().coerceAtLeast(1f)
        val floorY = h - 80f

        val accel = 900f
        val gravity = 1700f
        val friction = 0.86f

        vx += moveDir * accel * dt
        vx = vx.coerceIn(-550f, 550f)
        vy += gravity * dt

        val bodyRadius = 28f
        val onGround = y + bodyRadius >= floorY - 0.5f
        if (jumpRequested && onGround) {
            vy = -760f
        }
        jumpRequested = false

        x += vx * dt
        y += vy * dt

        if (y + bodyRadius > floorY) {
            y = floorY - bodyRadius
            vy = 0f
            vx *= friction
        }

        x = min(max(bodyRadius + 8f, x), w - bodyRadius - 8f)
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val h = height.toFloat()
        val w = width.toFloat()
        val floorY = h - 80f

        canvas.drawColor(Color.parseColor("#0f172a"))
        canvas.drawRect(0f, floorY, w, h, groundPaint)

        val r = 28f
        val hipLeftX = x - 14f
        val hipRightX = x + 14f
        val hipY = y + 16f
        val footY = floorY

        val phase = (System.currentTimeMillis() % 700L) / 700f * (Math.PI * 2.0)
        val swing = (kotlin.math.sin(phase).toFloat()) * 18f * (if (kotlin.math.abs(vx) > 10f) 1f else 0.15f)

        canvas.drawLine(hipLeftX, hipY, hipLeftX - swing, footY, limbPaint)
        canvas.drawLine(hipRightX, hipY, hipRightX + swing, footY, limbPaint)
        canvas.drawCircle(x, y, r, bodyPaint)
    }
}
