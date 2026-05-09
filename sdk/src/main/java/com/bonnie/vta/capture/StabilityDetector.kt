package com.bonnie.vta.capture

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.widget.TextView
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

object StabilityDetector {

    private const val DEFAULT_STABLE_FRAMES = 3
    private const val DEFAULT_TIMEOUT_MS = 5000L

    data class StabilityResult(
        val stable: Boolean,
        val reason: String  // "frames_stable", "content_stable", "timeout", "no_root", "interrupted"
    )

    /** Full stability: layout + position + alpha all unchanged. */
    fun waitForStable(rootView: View?, timeoutMs: Int = DEFAULT_TIMEOUT_MS.toInt()): StabilityResult {
        return waitForStableInternal(rootView, timeoutMs, hashMode = "full")
    }

    /** Content stability: only structure and text matter. Ignores pixel-level animation noise (alpha, shimmer, position tweaks). */
    fun waitForContentStable(rootView: View?, timeoutMs: Int = DEFAULT_TIMEOUT_MS.toInt()): StabilityResult {
        return waitForStableInternal(rootView, timeoutMs, hashMode = "content")
    }

    private fun waitForStableInternal(
        rootView: View?,
        timeoutMs: Int,
        hashMode: String
    ): StabilityResult {
        if (rootView == null) return StabilityResult(false, "no_root")

        val timeout = if (timeoutMs > 0) timeoutMs.toLong() else DEFAULT_TIMEOUT_MS
        val latch = CountDownLatch(1)
        var stable = false
        val stableReason = if (hashMode == "content") "content_stable" else "frames_stable"
        var reason = "timeout"

        val preDrawListener = ViewTreeObserver.OnPreDrawListener { true }
        rootView.viewTreeObserver.addOnPreDrawListener(preDrawListener)

        val stableFramesNeeded = DEFAULT_STABLE_FRAMES
        var stableFrameCount = 0
        var lastHash = ""

        val frameCallback = object : Choreographer.FrameCallback {
            override fun doFrame(frameTimeNanos: Long) {
                val currentHash = if (hashMode == "content") {
                    computeContentHash(rootView)
                } else {
                    computeViewTreeHash(rootView)
                }
                if (currentHash == lastHash) {
                    stableFrameCount++
                    if (stableFrameCount >= stableFramesNeeded) {
                        stable = true
                        reason = stableReason
                        latch.countDown()
                        return
                    }
                } else {
                    stableFrameCount = 0
                    lastHash = currentHash
                }
                Choreographer.getInstance().postFrameCallback(this)
            }
        }

        Handler(Looper.getMainLooper()).post {
            Choreographer.getInstance().postFrameCallback(frameCallback)
        }

        try {
            val completed = latch.await(timeout, TimeUnit.MILLISECONDS)
            if (!completed) {
                stable = false
                reason = "timeout"
                Choreographer.getInstance().removeFrameCallback(frameCallback)
            }
        } catch (e: InterruptedException) {
            Thread.currentThread().interrupt()
            Choreographer.getInstance().removeFrameCallback(frameCallback)
            rootView.viewTreeObserver.removeOnPreDrawListener(preDrawListener)
            return StabilityResult(false, "interrupted")
        } finally {
            rootView.viewTreeObserver.removeOnPreDrawListener(preDrawListener)
        }

        return StabilityResult(stable, reason)
    }

    // ── Full hash: includes pixel-level properties (alpha, position) ──────

    private fun computeViewTreeHash(root: View): String {
        val sb = StringBuilder()
        appendViewHash(root, sb)
        return sb.toString()
    }

    private fun appendViewHash(view: View, sb: StringBuilder) {
        if (!view.isShown) return

        sb.append(view.javaClass.simpleName)
        sb.append(':')
        sb.append(view.width)
        sb.append(',')
        sb.append(view.height)
        sb.append(',')
        sb.append(view.x.toInt())
        sb.append(',')
        sb.append(view.y.toInt())
        sb.append(',')
        sb.append((view.alpha * 10).toInt())
        sb.append(',')
        sb.append(view.visibility)
        sb.append(';')

        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                view.getChildAt(i)?.let { appendViewHash(it, sb) }
            }
        }
    }

    // ── Content hash: only structure + text, ignores animation noise ──────

    private fun computeContentHash(root: View): String {
        val sb = StringBuilder()
        appendContentHash(root, sb)
        return sb.toString()
    }

    private fun appendContentHash(view: View, sb: StringBuilder) {
        if (!view.isShown) return

        sb.append(view.javaClass.simpleName)
        sb.append(':')
        sb.append(view.width)
        sb.append(',')
        sb.append(view.height)
        sb.append(',')
        sb.append(view.visibility)

        // Include text content for semantic change detection
        if (view is TextView) {
            val t = view.text?.toString()?.trim() ?: ""
            if (t.isNotEmpty()) {
                sb.append(",t=")
                sb.append(t.take(40))
            }
        }

        sb.append(';')

        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                view.getChildAt(i)?.let { appendContentHash(it, sb) }
            }
        }
    }
}
