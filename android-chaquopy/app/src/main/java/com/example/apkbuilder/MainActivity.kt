package com.example.apkbuilder

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        val status = findViewById<TextView>(R.id.statusText)
        val runButton = findViewById<Button>(R.id.runButton)
        val bridge = Python.getInstance().getModule("bridge")

        status.text = bridge.callAttr("get_status").toString()
        runButton.setOnClickListener {
            status.text = bridge.callAttr("run_epoch").toString()
        }
    }
}
