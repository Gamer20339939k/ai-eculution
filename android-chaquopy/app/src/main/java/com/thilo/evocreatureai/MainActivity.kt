package com.thilo.evocreatureai

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        val output = findViewById<TextView>(R.id.outputText)
        val runButton = findViewById<Button>(R.id.runButton)
        val py = Python.getInstance()
        val module = loadPythonModule(py)

        output.text = try {
            module.callAttr("get_status").toString()
        } catch (e: Exception) {
            "Fehler bei get_status: ${e.message}"
        }

        runButton.setOnClickListener {
            output.text = try {
                val result: PyObject = module.callAttr("run_epoch")
                result.toString()
            } catch (e: Exception) {
                "Fehler bei run_epoch: ${e.message}"
            }
        }
    }
}
