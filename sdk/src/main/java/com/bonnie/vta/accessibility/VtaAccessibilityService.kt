package com.bonnie.vta.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import com.bonnie.vta.VtaSdk

class VtaAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "VTA-A11y"
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.i(TAG, "connected")
        serviceInfo = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED or
                         AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                         AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 100
        }
        VtaSdk.accessibilityService = this
        Log.i(TAG, "serviceInfo set, VtaSdk notified")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        Log.d(TAG, "event: type=${event.eventType}")

        if (event.eventType == AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED) {
            val texts = event.text
            Log.d(TAG, "toast texts: $texts")
            if (texts != null && !texts.isEmpty()) {
                VtaSdk.toastMessages.add(texts.joinToString(" "))
                while (VtaSdk.toastMessages.size > 20) {
                    VtaSdk.toastMessages.poll()
                }
            }
        }
    }

    override fun onInterrupt() {
        Log.w(TAG, "interrupted")
    }

    override fun onDestroy() {
        Log.w(TAG, "destroyed")
        super.onDestroy()
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        Log.w(TAG, "unbound")
        return super.onUnbind(intent)
    }
}
