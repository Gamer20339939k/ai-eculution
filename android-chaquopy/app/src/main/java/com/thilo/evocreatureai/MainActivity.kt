package com.thilo.evocreatureai

import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject

class MainActivity : AppCompatActivity() {
    private val uiHandler = Handler(Looper.getMainLooper())
    private lateinit var creatureView: CreatureView
    private lateinit var output: TextView
    private lateinit var module: PyObject
    private var visualRunning = false

    private val visualTick = object : Runnable {
        override fun run() {
            if (!visualRunning) return
            refreshVisualization()
            uiHandler.postDelayed(this, 90L)
        }
    }

    private fun loadPythonModule(py: Python): PyObject {
        val moduleCandidates = listOf(
            "ai_lern_walk_android",
            "ai_lern_walk_android_spezial",
            "game_core",
            "app_logic",
            "ai_leanr_walk"
        )
        var lastError: Exception? = null
        for (name in moduleCandidates) {
            try {
                return py.getModule(name)
            } catch (e: Exception) {
                lastError = e
            }
        }
        throw RuntimeException("Kein Python-Modul ladbar", lastError)
    }

    private fun parseColorSafe(hex: String): Int {
        return try {
            Color.parseColor(hex)
        } catch (_: Exception) {
            Color.parseColor("#7dd3fc")
        }
    }

    private fun parseFrame(rawJson: String): CreatureView.FrameData {
        val obj = JSONObject(rawJson)
        val worldW = obj.optDouble("w", 1200.0).toFloat()
        val worldH = obj.optDouble("h", 760.0).toFloat()
        val groundY = obj.optDouble("ground_y", 640.0).toFloat()

        val creaturesJson = obj.optJSONArray("creatures")
        val creatures = mutableListOf<CreatureView.CreatureShape>()

        if (creaturesJson != null) {
            for (i in 0 until creaturesJson.length()) {
                val c = creaturesJson.optJSONObject(i) ?: continue
                val nodesJson = c.optJSONArray("nodes")
                val bonesJson = c.optJSONArray("bones")
                val nodes = mutableListOf<Pair<Float, Float>>()
                val bones = mutableListOf<Pair<Int, Int>>()

                if (nodesJson != null) {
                    for (j in 0 until nodesJson.length()) {
                        val n = nodesJson.optJSONArray(j) ?: continue
                        val x = n.optDouble(0, 0.0).toFloat()
                        val y = n.optDouble(1, 0.0).toFloat()
                        nodes.add(Pair(x, y))
                    }
                }

                if (bonesJson != null) {
                    for (j in 0 until bonesJson.length()) {
                        val b = bonesJson.optJSONArray(j) ?: continue
                        bones.add(Pair(b.optInt(0, 0), b.optInt(1, 0)))
                    }
                }

                creatures.add(
                    CreatureView.CreatureShape(
                        color = parseColorSafe(c.optString("color", "#7dd3fc")),
                        nodes = nodes,
                        bones = bones,
                        leader = c.optBoolean("leader", false)
                    )
                )
            }
        }

        return CreatureView.FrameData(worldW, worldH, groundY, creatures)
    }

    private fun refreshVisualization() {
        try {
            val raw = module.callAttr("get_visual_frame").toString()
            creatureView.setFrame(parseFrame(raw))
        } catch (e: Exception) {
            output.text = "Visual Fehler: ${e.message}"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        AndroidBridge.init(applicationContext)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        output = findViewById(R.id.outputText)
        creatureView = findViewById(R.id.creatureView)
        val runButton = findViewById<Button>(R.id.runButton)
        val resetButton = findViewById<Button>(R.id.resetButton)

        val py = Python.getInstance()
        module = loadPythonModule(py)

        output.text = try {
            module.callAttr("get_status").toString()
        } catch (e: Exception) {
            "Fehler bei get_status: ${e.message}"
        }

        runButton.setOnClickListener {
            output.text = try {
                val result: PyObject = module.callAttr("run_epoch")
                refreshVisualization()
                result.toString()
            } catch (e: Exception) {
                "Fehler bei run_epoch: ${e.message}"
            }
        }

        resetButton.setOnClickListener {
            output.text = try {
                module.callAttr("reset_training")
                module.callAttr("reset_visualization")
                refreshVisualization()
                "Zurückgesetzt."
            } catch (e: Exception) {
                "Reset Fehler: ${e.message}"
            }
        }

        refreshVisualization()
    }

    override fun onResume() {
        super.onResume()
        visualRunning = true
        uiHandler.post(visualTick)
    }

    override fun onPause() {
        visualRunning = false
        uiHandler.removeCallbacks(visualTick)
        super.onPause()
    }
}
