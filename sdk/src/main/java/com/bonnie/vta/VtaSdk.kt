package com.bonnie.vta

import android.accessibilityservice.AccessibilityService
import android.app.Activity
import android.app.Application
import android.app.Dialog
import android.content.Context
import android.os.Bundle
import android.view.View
import java.lang.ref.WeakReference
import java.util.concurrent.ConcurrentLinkedQueue

object VtaSdk {

    private var application: Application? = null
    private var currentActivity: WeakReference<Activity>? = null
    private val dialogDecorViews = mutableListOf<WeakReference<View>>()
    private var sdkPresent = false
    private var installed = false

    val app: Application? get() = application
    val activity: Activity?
        get() = currentActivity?.get() ?: findActivityViaReflection()
    val decorView: View? get() = activity?.window?.decorView
    val currentDialogViews: List<View?>
        get() = dialogDecorViews.mapNotNull { it.get() }

    // ── AccessibilityService bridge ──────────────────────────────────

    var accessibilityService: AccessibilityService? = null

    /** Recent Toast messages collected by VtaAccessibilityService. */
    val toastMessages: ConcurrentLinkedQueue<String> = ConcurrentLinkedQueue()

    /** Recent dialog/window events collected by VtaAccessibilityService. */
    val dialogTitles: ConcurrentLinkedQueue<DialogInfo> = ConcurrentLinkedQueue()

    data class DialogInfo(
        val className: String = "",
        val text: String = ""
    )

    fun markPresent() {
        sdkPresent = true
    }

    fun ensureInstalled(context: Context) {
        if (installed) return
        val app = context.applicationContext as Application
        // Must post to main thread: registerActivityLifecycleCallbacks
        // silently fails when called from Binder threads (ContentProvider)
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            install(app)
        }
    }

    private fun install(app: Application) {
        if (installed) return
        installed = true
        application = app
        app.registerActivityLifecycleCallbacks(object : Application.ActivityLifecycleCallbacks {
            override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {}
            override fun onActivityStarted(activity: Activity) {}
            override fun onActivityResumed(activity: Activity) {
                currentActivity = WeakReference(activity)
            }
            override fun onActivityPaused(activity: Activity) {}
            override fun onActivityStopped(activity: Activity) {}
            override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
            override fun onActivityDestroyed(activity: Activity) {
                dialogDecorViews.clear()
            }
        })
    }

    /**
     * Fallback: use reflection to find the current Activity when lifecycle callbacks fail.
     * Accesses ActivityThread.mActivities which contains all running Activity instances.
     */
    private fun findActivityViaReflection(): Activity? {
        return try {
            val atCls = Class.forName("android.app.ActivityThread")
            val at = atCls.getMethod("currentActivityThread").invoke(null)
            val activitiesField = atCls.getDeclaredField("mActivities")
            activitiesField.isAccessible = true
            @Suppress("UNCHECKED_CAST")
            val activities = activitiesField.get(at) as? Map<*, *> ?: return null
            // ActivityClientRecord.paused=false means the activity is currently visible
            for ((_, record) in activities) {
                try {
                    val recordCls = record?.javaClass ?: continue
                    val pausedField = recordCls.getDeclaredField("paused")
                    pausedField.isAccessible = true
                    if (pausedField.getBoolean(record)) continue
                    val activityField = recordCls.getDeclaredField("activity")
                    activityField.isAccessible = true
                    val act = activityField.get(record) as? Activity
                    if (act != null && !act.isFinishing && !act.isDestroyed) {
                        currentActivity = WeakReference(act)
                        return act
                    }
                } catch (_: Exception) { }
            }
            null
        } catch (_: Exception) {
            null
        }
    }

    fun trackDialog(dialog: Dialog) {
        dialog.setOnShowListener {
            dialogDecorViews.add(WeakReference(dialog.window?.decorView))
        }
        dialog.setOnDismissListener {
            dialogDecorViews.removeAll { it.get() == null || it.get() == dialog.window?.decorView }
        }
    }
}
