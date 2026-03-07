package com.example.apkbuilder

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.util.AttributeSet
import android.view.MotionEvent
import android.widget.FrameLayout
import androidx.appcompat.widget.AppCompatImageView
import kotlin.math.atan2
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

class A4CanvasLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : FrameLayout(context, attrs, defStyleAttr) {

    private val pagePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        style = Paint.Style.FILL
    }
    private val borderPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#BBBBBB")
        style = Paint.Style.STROKE
        strokeWidth = 3f
    }
    private val pageRect = RectF()

    init {
        setWillNotDraw(false)
        setBackgroundColor(Color.parseColor("#E9EEF5"))
        clipChildren = false
        clipToPadding = false
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        updatePageRect()
        canvas.drawRect(pageRect, pagePaint)
        canvas.drawRect(pageRect, borderPaint)
    }

    override fun onLayout(changed: Boolean, left: Int, top: Int, right: Int, bottom: Int) {
        super.onLayout(changed, left, top, right, bottom)
        updatePageRect()
        for (index in 0 until childCount) {
            val child = getChildAt(index)
            if (child is EditableImageView && !child.isInitializedOnCanvas) {
                child.post { child.centerInside(pageRect) }
            }
        }
    }

    private fun updatePageRect() {
        if (width <= 0 || height <= 0) return
        val margin = 32f
        val availableWidth = width - margin * 2f
        val availableHeight = height - margin * 2f
        val a4Ratio = 210f / 297f
        var pageWidth = availableWidth
        var pageHeight = pageWidth / a4Ratio
        if (pageHeight > availableHeight) {
            pageHeight = availableHeight
            pageWidth = pageHeight * a4Ratio
        }
        val left = (width - pageWidth) / 2f
        val top = (height - pageHeight) / 2f
        pageRect.set(left, top, left + pageWidth, top + pageHeight)
    }

    fun addPhoto(uri: Uri) {
        val imageView = EditableImageView(context)
        imageView.setImageURI(uri)
        val size = max(260, min(pageRect.width().toIntOrNullSafe(), pageRect.height().toIntOrNullSafe()) / 2)
        val params = LayoutParams(size, size)
        addView(imageView, params)
        imageView.bringToFront()
        imageView.post { imageView.centerInside(pageRect) }
    }

    fun exportBitmap(): Bitmap {
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        draw(canvas)
        val safeRect = RectF(pageRect)
        val outWidth = safeRect.width().toInt().coerceAtLeast(1)
        val outHeight = safeRect.height().toInt().coerceAtLeast(1)
        return Bitmap.createBitmap(bitmap, safeRect.left.toInt(), safeRect.top.toInt(), outWidth, outHeight)
    }

    private fun Float.toIntOrNullSafe(): Int = if (this.isFinite()) this.toInt() else 0
}

class EditableImageView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : AppCompatImageView(context, attrs, defStyleAttr) {

    private val matrixValues = FloatArray(9)
    private var mode = Mode.NONE
    private var startX = 0f
    private var startY = 0f
    private var previousDistance = 0f
    private var previousAngle = 0f
    var isInitializedOnCanvas = false
        private set

    init {
        scaleType = ScaleType.MATRIX
        adjustViewBounds = true
        imageMatrix = Matrix()
        setBackgroundColor(Color.TRANSPARENT)
    }

    fun centerInside(bounds: RectF) {
        val drawable = drawable ?: return
        if (width == 0 || height == 0) return
        val baseScale = min(bounds.width() / drawable.intrinsicWidth, bounds.height() / drawable.intrinsicHeight) * 0.55f
        val matrix = Matrix()
        matrix.postScale(baseScale, baseScale)
        val scaledWidth = drawable.intrinsicWidth * baseScale
        val scaledHeight = drawable.intrinsicHeight * baseScale
        val left = bounds.centerX() - scaledWidth / 2f
        val top = bounds.centerY() - scaledHeight / 2f
        matrix.postTranslate(left, top)
        imageMatrix = matrix
        isInitializedOnCanvas = true
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                parent.requestDisallowInterceptTouchEvent(true)
                bringToFront()
                startX = event.x
                startY = event.y
                mode = Mode.DRAG
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                if (event.pointerCount >= 2) {
                    previousDistance = spacing(event)
                    previousAngle = rotation(event)
                    mode = Mode.TRANSFORM
                }
            }
            MotionEvent.ACTION_MOVE -> {
                when (mode) {
                    Mode.DRAG -> {
                        val dx = event.x - startX
                        val dy = event.y - startY
                        imageMatrix = Matrix(imageMatrix).apply { postTranslate(dx, dy) }
                    }
                    Mode.TRANSFORM -> {
                        if (event.pointerCount >= 2) {
                            val newDistance = spacing(event)
                            val scale = if (previousDistance > 0f) newDistance / previousDistance else 1f
                            val newAngle = rotation(event)
                            val deltaAngle = newAngle - previousAngle
                            val px = (event.getX(0) + event.getX(1)) / 2f
                            val py = (event.getY(0) + event.getY(1)) / 2f
                            imageMatrix = Matrix(imageMatrix).apply {
                                postScale(scale, scale, px, py)
                                postRotate(deltaAngle, px, py)
                            }
                            previousDistance = newDistance
                            previousAngle = newAngle
                        }
                    }
                    else -> Unit
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP, MotionEvent.ACTION_CANCEL -> {
                mode = Mode.NONE
            }
        }
        return true
    }

    private fun spacing(event: MotionEvent): Float {
        if (event.pointerCount < 2) return 0f
        val x = event.getX(0) - event.getX(1)
        val y = event.getY(0) - event.getY(1)
        return sqrt(x * x + y * y)
    }

    private fun rotation(event: MotionEvent): Float {
        if (event.pointerCount < 2) return 0f
        val deltaX = event.getX(0) - event.getX(1)
        val deltaY = event.getY(0) - event.getY(1)
        return Math.toDegrees(atan2(deltaY, deltaX).toDouble()).toFloat()
    }

    private enum class Mode {
        NONE,
        DRAG,
        TRANSFORM,
    }
}
