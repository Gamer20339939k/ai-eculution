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
    private lateinit var adapter: ArrayAdapter<String>

    private lateinit var module: PyObject
    private var entries = JSONArray()
    private var currentPath = ""
    private var selectedPath: String? = null
    private var sortMode = "size"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        requestStoragePermissionsIfNeeded()

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        pathText = findViewById(R.id.pathText)
        outputText = findViewById(R.id.outputText)
        listView = findViewById(R.id.listView)
        searchEdit = findViewById(R.id.searchEdit)
        sortButton = findViewById(R.id.sortButton)

        val rootButton = findViewById<Button>(R.id.rootButton)
        val upButton = findViewById<Button>(R.id.upButton)
        val refreshButton = findViewById<Button>(R.id.refreshButton)
        val deleteButton = findViewById<Button>(R.id.deleteButton)

        adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, mutableListOf())
        listView.adapter = adapter

        val py = Python.getInstance()
        module = py.getModule("storage_manager_android")

        rootButton.setOnClickListener {
            currentPath = callString("set_root")
            refresh()
        }
        upButton.setOnClickListener {
            currentPath = callString("go_up", currentPath)
            refresh()
        }
        refreshButton.setOnClickListener { refresh() }
        deleteButton.setOnClickListener {
            val p = selectedPath
            outputText.text = if (p.isNullOrBlank()) "Keine Datei gewählt" else callString("delete_entry", p)
            refresh()
        }

        sortButton.setOnClickListener {
            sortMode = if (sortMode == "size") "name" else "size"
            sortButton.text = if (sortMode == "size") "Sort: Größe" else "Sort: Name"
            refresh()
        }

        listView.setOnItemClickListener { _, _, position, _ ->
            val item = entries.optJSONObject(position) ?: return@setOnItemClickListener
            val path = item.optString("path", "")
            val isDir = item.optBoolean("is_dir", false)
            selectedPath = path
            if (isDir) {
                currentPath = callString("set_path", path)
                refresh()
            } else {
                outputText.text = "Datei gewählt: ${item.optString("name")}" 
            }
        }

        currentPath = callString("set_root")
        refresh()
    }

    private fun refresh() {
        val query = searchEdit.text?.toString() ?: ""
        val raw = callString("list_entries", currentPath, query, sortMode)
        val obj = JSONObject(raw)
        currentPath = obj.optString("path", currentPath)
        entries = obj.optJSONArray("entries") ?: JSONArray()
        pathText.text = currentPath

        val lines = mutableListOf<String>()
        for (i in 0 until entries.length()) {
            val e = entries.optJSONObject(i) ?: continue
            val icon = if (e.optBoolean("is_dir", false)) "📁" else "📄"
            lines.add("$icon ${e.optString("name", "?")}  (${e.optString("size_h", "-")})")
        }
        adapter.clear()
        adapter.addAll(lines)
        adapter.notifyDataSetChanged()
        outputText.text = obj.optString("status", "OK")
    }

    private fun callString(name: String, vararg args: Any): String {
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
