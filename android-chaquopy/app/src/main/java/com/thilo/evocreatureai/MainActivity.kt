package com.thilo.evocreatureai

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        val output = findViewById<TextView>(R.id.outputText)
        val runButton = findViewById<Button>(R.id.runButton)
        val py = Python.getInstance()
        val module = py.getModule("ai_leanr_walk")

        output.text = module.callAttr("get_status").toString()

        runButton.setOnClickListener {
            val result: PyObject = module.callAttr("run_epoch")
            output.text = result.toString()
        }
    }
}
