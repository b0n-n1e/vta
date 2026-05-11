package com.bonnie.vta.accessibility

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import com.bonnie.vta.VtaSdk

class VtaAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        VtaSdk.accessibilityService = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        when (event.eventType) {
            AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED -> {
                val texts = event.text
                if (texts != null && !texts.isEmpty()) {
                    VtaSdk.toastMessages.add(texts.joinToString(" "))
                    while (VtaSdk.toastMessages.size > 20) {
                        VtaSdk.toastMessages.poll()
                    }
                }
            }
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                val className = event.className?.toString() ?: ""
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
                    while (VtaSdk.dialogTitles.size > 10) {
                        VtaSdk.dialogTitles.poll()
                    }
                }
            }
        }
    }

    override fun onInterrupt() {}
}
