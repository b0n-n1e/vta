package com.bonnie.vta.execute

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import androidx.recyclerview.widget.RecyclerView
import com.bonnie.vta.VtaSdk
import com.bonnie.vta.capture.StabilityDetector
import com.bonnie.vta.capture.ViewTreeCapture
import com.bonnie.vta.model.AgentCommand
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object ActionExecutor {

    private val mainHandler = Handler(Looper.getMainLooper())
    private var lastResult: JSONObject = JSONObject()

    fun execute(command: AgentCommand, rootView: View?): JSONObject {
        if (command.action == "health") return executeHealth()
        if (command.action == "screenshot") return executeScreenshot()

        // "wait" needs no action on main thread, just do stability wait + capture
        if (command.action == "wait") {
            val result = captureNewState(rootView, command.timeoutMs)
            lastResult = result
            return result
        }

        // Step 1: action on main thread (fast, no blocking)
        if (Looper.myLooper() != Looper.getMainLooper()) {
            val latch = CountDownLatch(1)
            val ref = AtomicReference<JSONObject>()
            mainHandler.post {
                ref.set(executeAction(command, rootView))
                latch.countDown()
            }
            latch.await(10, TimeUnit.SECONDS)
            val actionResult = ref.get()
            if (actionResult?.optString("result") == "error") {
                lastResult = actionResult
                return actionResult
            }
        } else {
            val actionResult = executeAction(command, rootView)
            if (actionResult.optString("result") == "error") {
                lastResult = actionResult
                return actionResult
            }
        }

        // Step 2: wait + capture on calling thread
        val result = captureNewState(rootView, command.timeoutMs)
        lastResult = result
        return result
    }

    fun getLastResult(): JSONObject = lastResult

    private fun executeAction(command: AgentCommand, rootView: View?): JSONObject {
        return try {
            when (command.action) {
                "click" -> executeClick(command, rootView)
                "click_text" -> executeClickText(command, rootView)
                "input" -> executeInput(command, rootView)
                "scroll" -> executeScroll(command, rootView)
                "scroll_to" -> executeScrollTo(command, rootView)
                "back" -> executeBack()
                else -> errorResult("Unknown action: ${command.action}")
            }
        } catch (e: Exception) {
            errorResult(e.message ?: "Unknown error")
        }
    }

    private fun executeClick(command: AgentCommand, rootView: View?): JSONObject {
        if (rootView == null) return errorResult("No active Activity")
        val targetId = command.target ?: return errorResult("Target id is required for click")
        val targetView = findClickableView(rootView, targetId, command.index ?: 0)
            ?: return errorResult("View not found: $targetId (index=${command.index ?: 0})")
        targetView.performClick()
        manageKeyboard(targetView)
        return okResult()
    }

    private fun executeClickText(command: AgentCommand, rootView: View?): JSONObject {
        if (rootView == null) return errorResult("No active Activity")
        val text = command.target ?: command.text
            ?: return errorResult("Text is required for click_text")
        val targetView = findClickableView(rootView, text, 0)
            ?: return errorResult("View with text '$text' not found")
        targetView.performClick()
        manageKeyboard(targetView)
        return okResult()
    }

    /** Find a view by target and resolve to the nearest actually-clickable ancestor. */
    private fun findClickableView(rootView: View, target: String, index: Int): View? {
        val found = findViewInTreeOrDialogs(rootView, target, index) ?: return null
        return resolveClickable(found)
    }

    /** Show keyboard if target is a text input; hide it otherwise. */
    private fun manageKeyboard(view: View) {
        val editText = when {
            view is EditText -> view
            view is ViewGroup -> findFirstEditText(view)
            else -> null
        }
        val imm = view.context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager ?: return
        if (editText != null) {
            editText.post {
                editText.requestFocus()
                imm.showSoftInput(editText, InputMethodManager.SHOW_IMPLICIT)
            }
        } else {
            imm.hideSoftInputFromWindow(view.windowToken, 0)
        }
    }

    private fun findFirstEditText(parent: ViewGroup): EditText? {
        for (i in 0 until parent.childCount) {
            val child = parent.getChildAt(i) ?: continue
            if (child is EditText) return child
            if (child is ViewGroup) {
                findFirstEditText(child)?.let { return it }
            }
        }
        return null
    }

    /** If the view itself isn't interactive, walk up to the nearest clickable ancestor (max 5 levels). */
    private fun resolveClickable(view: View): View {
        if (view.isClickable || view.isFocusable) return view
        var current: View? = view
        var steps = 0
        while (current != null && steps < 5) {
            val p = current.parent
            if (p is View) {
                if (p.isClickable || p.isFocusable) return p
                current = p
            } else {
                current = null
            }
            steps++
        }
        return view
    }

    /** Search the main view tree first, then fall back to tracked dialog views. */
    private fun findViewInTreeOrDialogs(rootView: View, target: String, index: Int): View? {
        CoordinateResolver.findViewByTarget(rootView, target, index)?.let { return it }
        for (dialogView in VtaSdk.currentDialogViews) {
            if (dialogView != null) {
                CoordinateResolver.findViewByTarget(dialogView, target, index)?.let { return it }
            }
        }
        return null
    }

    private fun executeInput(command: AgentCommand, rootView: View?): JSONObject {
        if (rootView == null) return errorResult("No active Activity")
        val targetId = command.target ?: return errorResult("Target is required for input")
        val text = command.text ?: return errorResult("Text is required for input")
        val targetView = CoordinateResolver.findViewByTarget(rootView, targetId)
            ?: return errorResult("Input field not found: $targetId")
        if (targetView is EditText) {
            targetView.setText(text)
            manageKeyboard(targetView)
        } else {
            return errorResult("Target is not an input field: $targetId")
        }
        return okResult()
    }

    private fun executeScroll(command: AgentCommand, rootView: View?): JSONObject {
        if (rootView == null) return errorResult("No active Activity")
        val direction = command.direction ?: "down"
        val targetView = if (command.target != null) {
            CoordinateResolver.findViewByTarget(rootView, command.target)
        } else {
            rootView
        } ?: return errorResult("Scroll target not found")
        val distance = 500
        val scrollX: Int
        val scrollY: Int
        when (direction.lowercase()) {
            "up" -> { scrollX = 0; scrollY = -distance }
            "down" -> { scrollX = 0; scrollY = distance }
            "left" -> { scrollX = -distance; scrollY = 0 }
            "right" -> { scrollX = distance; scrollY = 0 }
            else -> return errorResult("Invalid direction: $direction")
        }
        if (targetView is RecyclerView) {
            targetView.smoothScrollBy(scrollX, scrollY)
        } else {
            targetView.scrollBy(scrollX, scrollY)
        }
        return okResult()
    }

    private fun executeScrollTo(command: AgentCommand, rootView: View?): JSONObject {
        if (rootView == null) return errorResult("No active Activity")
        val targetId = command.target ?: return errorResult("Target is required for scroll_to")
        val position = command.position
            ?: return errorResult("Position is required for scroll_to")
        val targetView = CoordinateResolver.findViewByTarget(rootView, targetId)
            ?: return errorResult("Scroll target not found: $targetId")
        if (targetView !is RecyclerView)
            return errorResult("Target is not a RecyclerView: $targetId")
        targetView.scrollToPosition(position)
        return okResult()
    }

    private fun executeBack(): JSONObject {
        val activity = VtaSdk.activity
            ?: return errorResult("No active Activity for back")
        activity.onBackPressed()
        return okResult()
    }

    private fun executeHealth(): JSONObject {
        return JSONObject().apply {
            put("result", "ok")
            put("sdk", true)
            put("activity", VtaSdk.activity?.javaClass?.simpleName ?: "none")
        }
    }

    private fun executeScreenshot(): JSONObject {
        val path = "/data/local/tmp/vta_screenshot.png"
        lastResult = JSONObject().apply {
            put("result", "ok")
            put("path", path)
        }
        return lastResult
    }

    private fun captureNewState(rootView: View?, timeoutMs: Int): JSONObject {
        val stable = if (rootView != null) {
            // Quick content-stability check — but don't block too long.
            // Animations (shimmer, auto-scroll) are normal; Agent decides when to act.
            StabilityDetector.waitForContentStable(rootView, timeoutMs.coerceAtMost(2000))
        } else {
            StabilityDetector.StabilityResult(false, "no_root")
        }
        val state = ViewTreeCapture.capture(rootView, stableStatus = stable)
        return JSONObject().apply {
            put("result", "ok")
            put("newState", state)
        }
    }

    private fun okResult(): JSONObject {
        return JSONObject().apply { put("result", "ok") }
    }

    private fun errorResult(message: String): JSONObject {
        return JSONObject().apply {
            put("result", "error")
            put("error", message)
        }
    }
}
