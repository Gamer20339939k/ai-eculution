package com.thilo.evocreatureai

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity() {
    private val storagePermissionReq = 1207
    private val uiHandler = Handler(Looper.getMainLooper())
    private lateinit var creatureView: CreatureView
    private lateinit var output: TextView
    private lateinit var module: PyObject

    private var visualRunning = false
    private var editMode = false
    private val selectedNodes = linkedSetOf<Int>()

    private val visualTick = object : Runnable {
        override fun run() {
            if (!visualRunning) return
            if (editMode) refreshTemplate() else refreshVisualization()
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
                val nodes = parseNodes(c.optJSONArray("nodes"))
                val bones = parseEdges(c.optJSONArray("bones"))
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

    private fun parseTemplate(rawJson: String): CreatureView.TemplateData {
        val obj = JSONObject(rawJson)
        val worldW = obj.optDouble("w", 1200.0).toFloat()
        val worldH = obj.optDouble("h", 760.0).toFloat()
        val groundY = obj.optDouble("ground_y", 640.0).toFloat()
        val name = obj.optString("name", "Template")
        val nodes = parseNodes(obj.optJSONArray("nodes"))
        val bones = parseEdges(obj.optJSONArray("bones"))
        val muscles = parseEdges(obj.optJSONArray("muscles"))
        return CreatureView.TemplateData(worldW, worldH, groundY, name, nodes, bones, muscles, selectedNodes.toSet())
    }

    private fun parseNodes(arr: JSONArray?): List<Pair<Float, Float>> {
        val nodes = mutableListOf<Pair<Float, Float>>()
        if (arr != null) {
            for (j in 0 until arr.length()) {
                val n = arr.optJSONArray(j) ?: continue
                nodes.add(Pair(n.optDouble(0, 0.0).toFloat(), n.optDouble(1, 0.0).toFloat()))
            }
        }
        return nodes
    }

    private fun parseEdges(arr: JSONArray?): List<Pair<Int, Int>> {
        val out = mutableListOf<Pair<Int, Int>>()
        if (arr != null) {
            for (j in 0 until arr.length()) {
                val e = arr.optJSONArray(j) ?: continue
                out.add(Pair(e.optInt(0, 0), e.optInt(1, 0)))
            }
        }
        return out
    }

    private fun callStatus(name: String, vararg args: Any): String {
        return try {
            val r = if (args.isEmpty()) module.callAttr(name) else module.callAttr(name, *args)
            r.toString()
        } catch (e: Exception) {
            "$name Fehler: ${e.message}"
        }
    }

    private fun refreshVisualization() {
        try {
            val raw = module.callAttr("get_visual_frame").toString()
            creatureView.setFrame(parseFrame(raw))
        } catch (e: Exception) {
            output.text = "Visual Fehler: ${e.message}"
        }
    }

    private fun refreshTemplate() {
        try {
            val raw = module.callAttr("get_template_frame").toString()
            creatureView.setTemplate(parseTemplate(raw))
        } catch (e: Exception) {
            output.text = "Template Fehler: ${e.message}"
        }
    }

    private fun setMode(edit: Boolean, modeButton: Button) {
        editMode = edit
        creatureView.setEditMode(edit)
        selectedNodes.clear()
        modeButton.text = if (editMode) "Modus: EDIT" else "Modus: SIM"
        if (editMode) refreshTemplate() else refreshVisualization()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        AndroidBridge.init(applicationContext)
        requestStoragePermissionsIfNeeded()

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        output = findViewById(R.id.outputText)
        creatureView = findViewById(R.id.creatureView)
        val modeButton = findViewById<Button>(R.id.modeButton)
        val runButton = findViewById<Button>(R.id.runButton)
        val resetButton = findViewById<Button>(R.id.resetButton)
        val boneButton = findViewById<Button>(R.id.boneButton)
        val muscleButton = findViewById<Button>(R.id.muscleButton)
        val autoMuscleButton = findViewById<Button>(R.id.autoMuscleButton)
        val saveButton = findViewById<Button>(R.id.saveButton)
        val loadButton = findViewById<Button>(R.id.loadButton)
        val clearButton = findViewById<Button>(R.id.clearButton)
        val popDownButton = findViewById<Button>(R.id.popDownButton)
        val popUpButton = findViewById<Button>(R.id.popUpButton)
        val timeDownButton = findViewById<Button>(R.id.timeDownButton)
        val timeUpButton = findViewById<Button>(R.id.timeUpButton)
        val mutDownButton = findViewById<Button>(R.id.mutDownButton)
        val mutUpButton = findViewById<Button>(R.id.mutUpButton)
        val selectButton = findViewById<Button>(R.id.selectButton)

        val py = Python.getInstance()
        module = loadPythonModule(py)
        output.text = callStatus("get_status")

        setMode(false, modeButton)

        creatureView.setOnTouchListener { _, event ->
            if (!editMode) return@setOnTouchListener false
            if (event.actionMasked == MotionEvent.ACTION_DOWN) {
                val idx = creatureView.findNodeAtScreen(event.x, event.y)
                if (idx >= 0) {
                    if (selectedNodes.contains(idx)) selectedNodes.remove(idx) else {
                        if (selectedNodes.size >= 2) {
                            val it = selectedNodes.iterator()
                            if (it.hasNext()) {
                                it.next()
                                it.remove()
                            }
                        }
                        selectedNodes.add(idx)
                    }
                    output.text = "Node ausgewählt: ${selectedNodes.joinToString(",")}".ifBlank { "Auswahl leer" }
                    refreshTemplate()
                } else {
                    val world = creatureView.screenToWorld(event.x, event.y)
                    output.text = callStatus("template_add_node", world.first, world.second)
                    selectedNodes.clear()
                    refreshTemplate()
                }
                true
            } else {
                true
            }
        }

        modeButton.setOnClickListener {
            setMode(!editMode, modeButton)
            output.text = if (editMode) "Edit aktiv: Tippen = Node setzen/auswählen" else callStatus("get_status")
        }

        runButton.setOnClickListener {
            if (editMode) {
                output.text = "Im Edit-Modus: erst auf SIM wechseln"
            } else {
                output.text = callStatus("run_epoch")
                refreshVisualization()
            }
        }

        resetButton.setOnClickListener {
            output.text = if (editMode) {
                selectedNodes.clear()
                callStatus("template_default")
            } else {
                callStatus("reset_training")
            }
            if (editMode) refreshTemplate() else refreshVisualization()
        }

        boneButton.setOnClickListener {
            if (!editMode) {
                output.text = "Bone nur im Edit-Modus"
                return@setOnClickListener
            }
            if (selectedNodes.size < 2) {
                output.text = "Wähle 2 Knoten"
                return@setOnClickListener
            }
            val ids = selectedNodes.toList()
            output.text = callStatus("template_add_bone", ids[0], ids[1])
            refreshTemplate()
        }

        muscleButton.setOnClickListener {
            if (!editMode) {
                output.text = "Muscle nur im Edit-Modus"
                return@setOnClickListener
            }
            if (selectedNodes.size < 2) {
                output.text = "Wähle 2 Knoten"
                return@setOnClickListener
            }
            val ids = selectedNodes.toList()
            output.text = callStatus("template_add_muscle_by_nodes", ids[0], ids[1])
            refreshTemplate()
        }

        autoMuscleButton.setOnClickListener {
            if (!editMode) {
                output.text = "Auto-Muscle nur im Edit-Modus"
                return@setOnClickListener
            }
            output.text = callStatus("template_auto_muscles")
            refreshTemplate()
        }

        saveButton.setOnClickListener {
            output.text = callStatus("template_save", "android_slot")
        }

        loadButton.setOnClickListener {
            selectedNodes.clear()
            output.text = callStatus("template_load", "android_slot")
            if (editMode) refreshTemplate() else refreshVisualization()
        }

        clearButton.setOnClickListener {
            if (!editMode) {
                output.text = "Clear nur im Edit-Modus"
                return@setOnClickListener
            }
            selectedNodes.clear()
            output.text = callStatus("template_clear")
            refreshTemplate()
        }

        popDownButton.setOnClickListener { output.text = callStatus("adjust_config", "population", -1) }
        popUpButton.setOnClickListener { output.text = callStatus("adjust_config", "population", 1) }
        timeDownButton.setOnClickListener { output.text = callStatus("adjust_config", "time", -1) }
        timeUpButton.setOnClickListener { output.text = callStatus("adjust_config", "time", 1) }
        mutDownButton.setOnClickListener { output.text = callStatus("adjust_config", "mutation", -1) }
        mutUpButton.setOnClickListener { output.text = callStatus("adjust_config", "mutation", 1) }
        selectButton.setOnClickListener { output.text = callStatus("toggle_selection_mode") }
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


    private fun requestStoragePermissionsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33) {
            return
        }
        val needsRead = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.READ_EXTERNAL_STORAGE
        ) != PackageManager.PERMISSION_GRANTED

        val needsWrite = Build.VERSION.SDK_INT <= 28 && ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.WRITE_EXTERNAL_STORAGE
        ) != PackageManager.PERMISSION_GRANTED

        val list = mutableListOf<String>()
        if (needsRead) list.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        if (needsWrite) list.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        if (list.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, list.toTypedArray(), storagePermissionReq)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != storagePermissionReq) return
        val ok = grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }
        if (!ok) {
            output.text = "Hinweis: Speicherrechte abgelehnt. Datei-Funktionen ggf. eingeschr?nkt."
        }
    }

}