package com.thilo.evocreatureai

import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import java.io.File

object AndroidBridge {
    private lateinit var appContext: Context

    @JvmStatic
    fun init(context: Context) {
        appContext = context.applicationContext
    }

    private fun ensureReady() {
        if (!::appContext.isInitialized) {
            throw IllegalStateException("AndroidBridge nicht initialisiert")
        }
    }

    private fun safeFileName(fileName: String): String {
        return fileName.replace(Regex("[^a-zA-Z0-9._-]"), "_")
    }

    @JvmStatic
    fun showToast(text: String): String {
        ensureReady()
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(appContext, text, Toast.LENGTH_SHORT).show()
        }
        return "OK"
    }

    @JvmStatic
    fun saveText(fileName: String, content: String): String {
        ensureReady()
        val safe = safeFileName(fileName)
        val f = File(appContext.filesDir, safe)
        f.writeText(content)
        return f.absolutePath
    }

    @JvmStatic
    fun readText(fileName: String): String {
        ensureReady()
        val safe = safeFileName(fileName)
        val f = File(appContext.filesDir, safe)
        if (!f.exists()) return ""
        return f.readText()
    }

    @JvmStatic
    fun listFiles(): String {
        ensureReady()
        val names = appContext.filesDir.list()?.sorted() ?: emptyList()
        return names.joinToString("\n")
    }

    @JvmStatic
    fun getDeviceInfo(): String {
        ensureReady()
        return "android=${Build.VERSION.RELEASE}, sdk=${Build.VERSION.SDK_INT}, model=${Build.MODEL}"
    }
}
