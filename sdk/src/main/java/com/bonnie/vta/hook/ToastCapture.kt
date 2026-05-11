package com.bonnie.vta.hook

import android.os.IBinder
import com.bonnie.vta.VtaSdk
import java.lang.reflect.InvocationHandler
import java.lang.reflect.Proxy

/**
 * Captures Toast text by proxying INotificationManager.enqueueToast().
 * Works on all devices — no AccessibilityService required.
 *
 * Calls VtaSdk.toastMessages.add() automatically.
 */
object ToastCapture {

    private var installed = false

    fun install() {
        if (installed) return
        try {
            val sm = Class.forName("android.os.ServiceManager")
            val getService = sm.getDeclaredMethod("getService", String::class.java)
            val original = getService.invoke(null, "notification") as IBinder
            val proxy = Proxy.newProxyInstance(
                original.javaClass.classLoader,
                arrayOf(Class.forName("android.app.INotificationManager")),
                Handler(original)
            ) as IBinder

            val sCacheField = sm.getDeclaredField("sCache")
            sCacheField.isAccessible = true
            @Suppress("UNCHECKED_CAST")
            val sCache = sCacheField.get(null) as MutableMap<String, IBinder>
            sCache["notification"] = proxy

            installed = true
        } catch (_: Exception) {}
    }

    private class Handler(private val delegate: IBinder) : InvocationHandler {
        override fun invoke(proxy: Any, method: java.lang.reflect.Method, args: Array<out Any?>?): Any? {
            if (method.name == "enqueueToast" && args != null && args.size >= 3) {
                val text = args[2]?.toString() ?: ""
                if (text.isNotBlank()) {
                    VtaSdk.toastMessages.add(text)
                    while (VtaSdk.toastMessages.size > 20) VtaSdk.toastMessages.poll()
                }
            }
            return method.invoke(delegate, *(args ?: emptyArray()))
        }
    }
}
