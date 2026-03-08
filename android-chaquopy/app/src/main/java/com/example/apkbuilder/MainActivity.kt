package com.example.apkbuilder

import android.content.ContentValues
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var canvasLayout: A4CanvasLayout
    private lateinit var statusText: TextView

    private val pickImages = registerForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(10)) { uris ->
        if (uris.isNullOrEmpty()) {
            setStatus("Keine Bilder gewählt.")
            return@registerForActivityResult
        }
        uris.forEach { canvasLayout.addPhoto(it) }
        setStatus("${uris.size} Bild(er) geladen. Ziehen mit 1 Finger. Größe/Rotation mit 2 Fingern.")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        canvasLayout = findViewById(R.id.canvasLayout)
        statusText = findViewById(R.id.statusText)

        findViewById<Button>(R.id.selectButton).setOnClickListener {
            pickImages.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }

        findViewById<Button>(R.id.exportButton).setOnClickListener {
            exportComposition()
        }

        findViewById<Button>(R.id.clearButton).setOnClickListener {
            canvasLayout.removeAllViews()
            setStatus("Leinwand geleert.")
        }

        setStatus("Wähle Fotos aus. Ziel: mehrere Bilder frei auf einer A4-Seite anordnen.")
    }

    private fun exportComposition() {
        try {
            val bitmap = canvasLayout.exportBitmap()
            val uri = saveBitmap(bitmap)
            setStatus("Export fertig: $uri")
            Toast.makeText(this, "Bild gespeichert", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            setStatus("Export fehlgeschlagen: ${e.message}")
        }
    }

    private fun saveBitmap(bitmap: Bitmap): Uri {
        val name = "foto_layout_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.png"
        val resolver = contentResolver
        val collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/FotoLayout")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
        }
        val uri = resolver.insert(collection, values) ?: throw IOException("MediaStore-Eintrag konnte nicht erstellt werden")
        resolver.openOutputStream(uri)?.use { out ->
            if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)) {
                throw IOException("PNG konnte nicht gespeichert werden")
            }
        } ?: throw IOException("Ausgabestrom konnte nicht geöffnet werden")

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        }
        return uri
    }

    private fun setStatus(text: String) {
        statusText.text = text
    }
}
