package com.bonnie.vta.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.view.accessibility.AccessibilityEvent
import com.bonnie.vta.VtaSdk
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Captures system-level UI events that are invisible to ViewTreeCapture:
 * Toast messages via NOTIFICATION_STATE_CHANGED, and dialog/window changes.
 *
 * Collected data is exposed through [VtaSdk.toastMessages] and
 * [VtaSdk.dialogTitles] for the ContentProvider to include in /state responses.
 */
class VtaAccessibilityService : AccessibilityService() {

    companion object {
        private const val MAX_TOASTS = 20
        private const val MAX_DIALOGS = 10

        /** Build the service-info for xml-less configuration (API 24+). */
        fun buildServiceInfo(): AccessibilityServiceInfo {
            return AccessibilityServiceInfo().apply {
                eventTypes = AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED or
                        AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                        AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
                feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
                flags = AccessibilityServiceInfo.DEFAULT
                notificationTimeout = 100 // ms
            }
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        serviceInfo = buildServiceInfo()
        VtaSdk.accessibilityService = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        when (event.eventType) {
            AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED -> {
                val texts = event.text
                if (texts != null && !texts.isEmpty()) {
                    val toast = texts.joinToString(" ")
                    VtaSdk.toastMessages.add(toast)
                    // Trim oldest if over limit
                    while (VtaSdk.toastMessages.size > MAX_TOASTS) {
                        VtaSdk.toastMessages.poll()
                    }
                }
            }

            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                val packageName = event.packageName?.toString() ?: ""
                val className = event.className?.toString() ?: ""
                // Detect alert dialogs (AlertDialog, Dialog, BottomSheetDialogFragment)
                if (className.contains("Dialog") || className.contains("Alert") ||
                    className.contains("BottomSheet") || className.contains("Popup")
                ) {
                    val text = event.text?.joinToString(" ") ?: ""
                    VtaSdk.dialogTitles.add(
                        VtaSdk.DialogInfo(
                            className = className.substringAfterLast('.'),
                            text = text
                        )
                    )
                    while (VtaSdk.dialogTitles.size > MAX_DIALOGS) {
                        VtaSdk.dialogTitles.poll()
                    }
                }
            }
        }
    }

    override fun onInterrupt() {}
}
