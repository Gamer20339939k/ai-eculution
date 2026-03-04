package com.thilo.evocreatureai

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ListView
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

    private lateinit var pathText: TextView
    private lateinit var outputText: TextView
    private lateinit var listView: ListView
    private lateinit var searchEdit: EditText
    private lateinit var sortButton: Button
    private lateinit var rootButton: Button
    private lateinit var upButton: Button
    private lateinit var refreshButton: Button
    private lateinit var deleteButton: Button
    private lateinit var adapter: ArrayAdapter<String>

    private lateinit var module: PyObject
    private var entries = JSONArray()
    private var currentPath = ""
    private val selectedPaths = linkedSetOf<String>()
    private var sortMode = "size"
    private var lastRenderKey = ""
    private var appReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        requestStoragePermissionsIfNeeded()

        pathText = findViewById(R.id.pathText)
        outputText = findViewById(R.id.outputText)
        listView = findViewById(R.id.listView)
        searchEdit = findViewById(R.id.searchEdit)
        sortButton = findViewById(R.id.sortButton)
        rootButton = findViewById(R.id.rootButton)
        upButton = findViewById(R.id.upButton)
        refreshButton = findViewById(R.id.refreshButton)
        deleteButton = findViewById(R.id.deleteButton)

        adapter = ArrayAdapter(this, android.R.layout.simple_list_item_multiple_choice, mutableListOf())
        listView.adapter = adapter
        listView.choiceMode = ListView.CHOICE_MODE_MULTIPLE

        setControlsEnabled(false)
        outputText.text = "Starte App..."
        pathText.text = "Bitte warten"

        Thread {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val py = Python.getInstance()
                module = py.getModule("storage_manager_android")
                runOnUiThread {
                    bindUiActions()
                    appReady = true
                    setControlsEnabled(true)
                    currentPath = callString("set_root")
                    refresh(forceRender = true)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    outputText.text = "Python-Startfehler: ${e.message}"
                }
            }
        }.start()
    }

    private fun bindUiActions() {
        rootButton.setOnClickListener {
            selectedPaths.clear()
            currentPath = callString("set_root")
            refresh(forceRender = true)
        }

        upButton.setOnClickListener {
            selectedPaths.clear()
            currentPath = callString("go_up", currentPath)
            refresh(forceRender = true)
        }

        refreshButton.setOnClickListener {
            refresh(forceRender = true)
        }

        deleteButton.setOnClickListener {
            if (selectedPaths.isEmpty()) {
                outputText.text = "Datei oder Ordner markieren (lang tippen)"
                return@setOnClickListener
            }

            var ok = 0
            var fail = 0
            val copy = selectedPaths.toList()
            for (p in copy) {
                val result = callString("delete_entry", p)
                if (result.startsWith("Loeschen fehlgeschlagen")) {
                    fail += 1
                } else {
                    ok += 1
                }
            }
            outputText.text = "Geloescht: $ok | Fehler: $fail"
            selectedPaths.clear()
            refresh(forceRender = true)
        }

        sortButton.setOnClickListener {
            sortMode = if (sortMode == "size") "name" else "size"
            sortButton.text = if (sortMode == "size") "Sort: Groesse" else "Sort: Name"
            refresh(forceRender = true)
        }

        listView.setOnItemClickListener { _, _, position, _ ->
            val item = entries.optJSONObject(position) ?: return@setOnItemClickListener
            val path = item.optString("path", "")
            val isDir = item.optBoolean("is_dir", false)

            if (isDir) {
                selectedPaths.clear()
                listView.clearChoices()
                currentPath = callString("set_path", path)
                refresh(forceRender = true)
            } else {
                toggleSelection(path)
                listView.setItemChecked(position, selectedPaths.contains(path))
                outputText.text = "Markiert: ${selectedPaths.size}"
            }
        }

        listView.setOnItemLongClickListener { _, _, position, _ ->
            val item = entries.optJSONObject(position) ?: return@setOnItemLongClickListener false
            val path = item.optString("path", "")
            if (path.isBlank()) return@setOnItemLongClickListener false

            toggleSelection(path)
            listView.setItemChecked(position, selectedPaths.contains(path))
            outputText.text = "Zum Loeschen markiert: ${selectedPaths.size}"
            true
        }
    }

    private fun toggleSelection(path: String) {
        if (selectedPaths.contains(path)) {
            selectedPaths.remove(path)
        } else {
            selectedPaths.add(path)
        }
    }

    private fun setControlsEnabled(enabled: Boolean) {
        rootButton.isEnabled = enabled
        upButton.isEnabled = enabled
        refreshButton.isEnabled = enabled
        deleteButton.isEnabled = enabled
        sortButton.isEnabled = enabled
        searchEdit.isEnabled = enabled
        listView.isEnabled = enabled
    }

    private fun refresh(forceRender: Boolean = false) {
        if (!appReady) {
            outputText.text = "Start laeuft..."
            return
        }
        try {
            val query = searchEdit.text?.toString() ?: ""
            val raw = callString("list_entries", currentPath, query, sortMode)
            val obj = JSONObject(raw)

            currentPath = obj.optString("path", currentPath)
            pathText.text = currentPath

            val revision = obj.optString("revision", "")
            val renderKey = "$currentPath|$query|$sortMode|$revision"
            val cacheHit = obj.optBoolean("cache_hit", false)
            if (!forceRender && renderKey == lastRenderKey) {
                outputText.text = if (cacheHit) {
                    "Unveraendert (Cache)"
                } else {
                    obj.optString("status", "OK")
                }
                return
            }

            entries = obj.optJSONArray("entries") ?: JSONArray()

            val lines = mutableListOf<String>()
            val visiblePaths = hashSetOf<String>()
            for (i in 0 until entries.length()) {
                val e = entries.optJSONObject(i) ?: continue
                val icon = if (e.optBoolean("is_dir", false)) "[DIR]" else "[FILE]"
                val name = e.optString("name", "?")
                val sizeH = e.optString("size_h", "-")
                lines.add("$icon $name  ($sizeH)")
                visiblePaths.add(e.optString("path", ""))
            }

            adapter.clear()
            adapter.addAll(lines)
            adapter.notifyDataSetChanged()

            selectedPaths.retainAll(visiblePaths)
            listView.clearChoices()
            for (i in 0 until entries.length()) {
                val e = entries.optJSONObject(i) ?: continue
                val path = e.optString("path", "")
                if (selectedPaths.contains(path)) {
                    listView.setItemChecked(i, true)
                }
            }

            outputText.text = obj.optString("status", "OK")
            lastRenderKey = renderKey
        } catch (e: Exception) {
            adapter.clear()
            adapter.notifyDataSetChanged()
            listView.clearChoices()
            outputText.text = "Refresh-Fehler: ${e.message}"
        }
    }

    private fun callString(name: String, vararg args: Any): String {
        if (!this::module.isInitialized) {
            return "Python wird geladen..."
        }
        return try {
            if (args.isEmpty()) module.callAttr(name).toString() else module.callAttr(name, *args).toString()
        } catch (e: Exception) {
            "Fehler $name: ${e.message}"
        }
    }

    private fun requestStoragePermissionsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33) return
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
}
