package com.bonnie.vta.capture

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import com.bonnie.vta.VtaSdk
import org.json.JSONArray
import org.json.JSONObject

object AccessibilityTreeCapture {

    fun capture(): JSONObject {
        val result = JSONObject()
        val service = VtaSdk.accessibilityService
        if (service == null) {
            result.put("ok", false)
            result.put("error", "accessibility_service_not_available")
            return result
        }

        val root = service.rootInActiveWindow
        if (root == null) {
            result.put("ok", false)
            result.put("error", "no_active_window")
            return result
        }

        val nodes = JSONArray()
        try {
            traverseNode(root, nodes)
            result.put("ok", true)
            result.put("nodes", nodes)
            result.put("node_count", nodes.length())
        } finally {
            root.recycle()
        }

        return result
    }

    private fun traverseNode(node: AccessibilityNodeInfo, out: JSONArray) {
        val obj = JSONObject()
        val className = node.className?.toString() ?: ""

        obj.put("class", className)

        val contentDesc = node.contentDescription?.toString()?.trim() ?: ""
        val text = node.text?.toString()?.trim() ?: ""

        // Lynx puts visible text in content-desc
        val displayText = contentDesc.ifEmpty { text }
        obj.put("text", displayText)
        obj.put("content_desc", contentDesc)
        obj.put("resource_id", node.viewIdResourceName ?: "")
        obj.put("clickable", node.isClickable)
        obj.put("focusable", node.isFocusable)
        obj.put("scrollable", node.isScrollable)
        obj.put("enabled", node.isEnabled)
        obj.put("checked", node.isChecked)
        obj.put("selected", node.isSelected)

        val isLynx = className.contains("lynx", ignoreCase = true)
        obj.put("is_lynx", isLynx)

        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() > 0 || rect.height() > 0) {
            obj.put("bounds", JSONArray(listOf(rect.left, rect.top, rect.right, rect.bottom)))
        }

        val childArr = JSONArray()
        for (i in 0 until node.childCount) {
            val child = node.getChild(i)
            if (child != null) {
                traverseNode(child, childArr)
                child.recycle()
            }
        }
        if (childArr.length() > 0) {
            obj.put("children", childArr)
        }

        out.put(obj)
    }
}
