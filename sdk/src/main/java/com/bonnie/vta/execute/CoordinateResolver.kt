package com.bonnie.vta.execute

import android.view.View
import android.view.ViewGroup
import android.widget.EditText

object CoordinateResolver {

    data class ViewCoordinate(val view: View, val centerX: Int, val centerY: Int)

    fun resolve(targetId: String, rootView: View?, index: Int = 0): ViewCoordinate {
        requireNotNull(rootView) { "Root view is null — no active Activity?" }

        val result = findViewByTarget(rootView, targetId, index)
            ?: throw IllegalStateException("View not found for target: $targetId (index=$index)")

        val location = IntArray(2)
        result.getLocationOnScreen(location)
        val centerX = location[0] + result.width / 2
        val centerY = location[1] + result.height / 2

        return ViewCoordinate(result, centerX, centerY)
    }

    fun findViewByTarget(root: View, target: String, index: Int = 0): View? {
        val counter = IntArray(1)
        return findNthMatch(root, target, index, counter)
    }

    private fun findNthMatch(root: View, target: String, wantIndex: Int, counter: IntArray): View? {
        if (matches(root, target)) {
            // Only require isActionable for resource-ID matches (index alignment with ViewTreeCapture).
            // Text/content-desc/hint matches need to find non-actionable labels too.
            val isIdMatch = getResourceIdString(root).let { it.isNotEmpty() && it == target }
            if (!isIdMatch || isActionable(root)) {
                if (counter[0] == wantIndex) return root
                counter[0]++
            }
        }
        if (root is ViewGroup) {
            for (i in 0 until root.childCount) {
                root.getChildAt(i)?.let {
                    findNthMatch(it, target, wantIndex, counter)?.let { return it }
                }
            }
        }
        return null
    }

    private fun matches(view: View, target: String): Boolean {
        val resourceId = getResourceIdString(view)
        if (resourceId.isNotEmpty() && resourceId == target) return true
        // Class name matching — for targeting nested RecyclerViews without IDs
        val className = view.javaClass.name
        if (className == target || className.endsWith(".$target")) return true
        if (view is android.widget.TextView) {
            val text = view.text?.toString()?.trim() ?: ""
            if (text.isNotEmpty() && text.equals(target, ignoreCase = true)) return true
        }
        val desc = view.contentDescription?.toString()?.trim() ?: ""
        if (desc.isNotEmpty() && desc.equals(target, ignoreCase = true)) return true
        if (view is EditText) {
            val hint = view.hint?.toString()?.trim() ?: ""
            if (hint.isNotEmpty() && hint.equals(target, ignoreCase = true)) return true
        }
        return false
    }

    private fun getResourceIdString(view: View): String {
        val id = view.id
        if (id == View.NO_ID) return ""
        return try {
            val resources = view.resources
            val entryName = resources.getResourceEntryName(id)
            val packageName = resources.getResourcePackageName(id)
            "$packageName:id/$entryName"
        } catch (e: Exception) {
            ""
        }
    }

    // Must match ViewTreeCapture.isActionable to keep indices aligned
    private fun isActionable(view: View): Boolean =
        view.isClickable || view.isFocusable || view is EditText || isScrollableContainer(view)

    private fun isScrollableContainer(view: View): Boolean {
        val className = view.javaClass.name
        return className.contains("RecyclerView") ||
                className.contains("ScrollView") ||
                className.contains("ListView") ||
                className.contains("GridView") ||
                className.contains("ViewPager") ||
                className.contains("HorizontalScrollView") ||
                className.contains("NestedScrollView")
    }
}
