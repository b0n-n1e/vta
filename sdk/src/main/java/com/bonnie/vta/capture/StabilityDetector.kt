package com.bonnie.vta.capture

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

object StabilityDetector {

    private const val DEFAULT_STABLE_FRAMES = 3
    private const val DEFAULT_TIMEOUT_MS = 5000L

    data class StabilityResult(
        val stable: Boolean,
        val reason: String  // "frames_stable", "timeout", "no_root", "interrupted"
    )

    fun waitForStable(rootView: View?, timeoutMs: Int = DEFAULT_TIMEOUT_MS.toInt()): StabilityResult {
        if (rootView == null) return StabilityResult(false, "no_root")

        val timeout = if (timeoutMs > 0) timeoutMs.toLong() else DEFAULT_TIMEOUT_MS
        val latch = CountDownLatch(1)
        var stable = false
        var reason = "timeout"

        val preDrawListener = ViewTreeObserver.OnPreDrawListener { true }
        rootView.viewTreeObserver.addOnPreDrawListener(preDrawListener)

        val stableFramesNeeded = DEFAULT_STABLE_FRAMES
        var stableFrameCount = 0
        var lastHash = ""

        val frameCallback = object : Choreographer.FrameCallback {
            override fun doFrame(frameTimeNanos: Long) {
                val currentHash = computeViewTreeHash(rootView)
                if (currentHash == lastHash) {
                    stableFrameCount++
                    if (stableFrameCount >= stableFramesNeeded) {
                        stable = true
                        reason = "frames_stable"
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
}
