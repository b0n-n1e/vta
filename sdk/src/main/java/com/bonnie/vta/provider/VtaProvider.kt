package com.bonnie.vta.provider

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.Handler
import android.os.Looper
import com.bonnie.vta.VtaSdk
import com.bonnie.vta.capture.ViewTreeCapture
import com.bonnie.vta.execute.ActionExecutor
import com.bonnie.vta.model.AgentCommand
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class VtaProvider : ContentProvider() {

    companion object {
        private const val COLUMN_JSON = "_json"
    }

    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onCreate(): Boolean {
        mainHandler.post { context?.let { VtaSdk.ensureInstalled(it) } }
        return true
    }

    /** Run a callable on the main thread and return its result. */
    private fun <T> runOnMain(block: () -> T): T? {
        if (Looper.myLooper() == Looper.getMainLooper()) return block()
        val latch = CountDownLatch(1)
        val ref = AtomicReference<T?>()
        mainHandler.post {
            ref.set(block())
            latch.countDown()
        }
        latch.await(15, TimeUnit.SECONDS)
        return ref.get()
    }

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?
    ): Cursor? {
        val path = uri.path ?: return null

        val json = when {
            path == "/toasts" || path == "toasts" -> {
                val arr = org.json.JSONArray(VtaSdk.toastMessages.toList())
                org.json.JSONObject().apply {
                    put("toasts", arr)
                    put("count", arr.length())
                }.toString()
            }
            path == "/state" || path == "state" -> {
                runOnMain {
                    val state = ViewTreeCapture.capture(VtaSdk.decorView)
                    // Attach toast/dialog data from AccessibilityService
                    val toasts = VtaSdk.toastMessages.toList()
                    val dialogs = VtaSdk.dialogTitles.toList()
                    if (toasts.isNotEmpty() || dialogs.isNotEmpty()) {
                        state.put("toasts", org.json.JSONArray(toasts))
                        state.put("dialogs", org.json.JSONArray(dialogs.map {
                            org.json.JSONObject().apply {
                                put("class", it.className)
                                put("text", it.text)
                            }
                        }))
                    }
                    state.toString()
                } ?: "{}"
            }
            path == "/execute" || path == "execute" -> {
                val command = AgentCommand(
                    action = uri.getQueryParameter("action") ?: "",
                    target = uri.getQueryParameter("target"),
                    text = uri.getQueryParameter("text"),
                    direction = uri.getQueryParameter("direction"),
                    position = uri.getQueryParameter("position")?.toIntOrNull(),
                    index = uri.getQueryParameter("index")?.toIntOrNull(),
                    timeoutMs = uri.getQueryParameter("timeout_ms")?.toIntOrNull() ?: 5000
                )
                ActionExecutor.execute(command, VtaSdk.decorView).toString()
            }
            path == "/result" || path == "result" -> {
                ActionExecutor.getLastResult().toString()
            }
            else -> return null
        }

        val cursor = MatrixCursor(arrayOf(COLUMN_JSON))
        cursor.addRow(arrayOf<Any>(json))
        return cursor
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? {
        val path = uri.path ?: return null
        if (path != "/execute" && path != "execute") return null

        if (values == null) return null

        val command = AgentCommand(
            action = values.getAsString("action") ?: "",
            target = values.getAsString("target"),
            text = values.getAsString("text"),
            direction = values.getAsString("direction"),
            position = values.getAsInteger("position"),
            index = values.getAsInteger("index"),
            timeoutMs = values.getAsInteger("timeout_ms") ?: 5000
        )

        val decorView = VtaSdk.decorView
        ActionExecutor.execute(command, decorView)

        // Return a URI that the CLI can use to poll the result
        val authority = (context?.packageName ?: "com.bonnie.vta") + ".vta"
        return Uri.parse("content://$authority/result")
    }

    override fun getType(uri: Uri): String? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<out String>?
    ): Int = 0
}
