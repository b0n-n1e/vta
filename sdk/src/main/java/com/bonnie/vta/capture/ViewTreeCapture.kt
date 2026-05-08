package com.bonnie.vta.capture

import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject

object ViewTreeCapture {

    fun capture(
        rootView: View?,
        activityName: String? = null,
        stableStatus: StabilityDetector.StabilityResult? = null
    ): JSONObject {
        val result = JSONObject()
        val data = JSONObject()

        if (rootView == null) {
            result.put("ok", true)
            result.put("data", JSONObject().apply {
                put("package", "")
                put("activity", "")
                put("stable", false)
                put("stable_reason", "no_root")
                put("actions", JSONArray())
                put("dialogs", JSONArray())
                put("toasts", JSONArray())
            })
            return result
        }

        val context = rootView.context
        val packageName = context.packageName
        val resolvedActivity = activityName
            ?: com.bonnie.vta.VtaSdk.activity?.javaClass?.name
            ?: context.javaClass.name

        val actions = JSONArray()
        val dialogs = JSONArray()
        val rect = android.graphics.Rect()
        rootView.getWindowVisibleDisplayFrame(rect)

        collectActionableViews(rootView, actions)
        collectDialogViews(rootView, dialogs)
        collectTrackedDialogs(dialogs)

        val stability = stableStatus ?: StabilityDetector.StabilityResult(true, "direct_query")

        data.put("package", packageName)
        data.put("activity", resolvedActivity)
        data.put("stable", stability.stable)
        data.put("stable_reason", stability.reason)
        data.put("resolution", JSONObject().apply {
            put("width", rect.width())
            put("height", rect.height())
        })
        data.put("actions", actions)
        data.put("dialogs", dialogs)
        data.put("toasts", JSONArray())

        result.put("ok", true)
        result.put("data", data)
        return result
    }

    private fun collectDialogViews(root: View, dialogs: JSONArray) {
        if (root is ViewGroup) {
            for (i in 0 until root.childCount) {
                val child = root.getChildAt(i) ?: continue
                val className = child.javaClass.name.lowercase()

                if ((className.contains("dialog") ||
                     className.contains("popup") ||
                     className.contains("bottomsheet"))
                    && child is ViewGroup
                    && child.width > 100 && child.height > 100) {
                    dialogs.put(extractDialogInfo(child))
                } else {
                    collectDialogViews(child, dialogs)
                }
            }
        }
    }

    private fun extractDialogInfo(dialogView: ViewGroup): JSONObject {
        val info = JSONObject()
        val titleCandidates = mutableListOf<String>()
        val messageCandidates = mutableListOf<String>()
        val buttonTexts = mutableListOf<String>()
        var hasPositive = false
        var positiveText = ""
        var hasNegative = false
        var negativeText = ""
        var dialogType = "dialog"

        extractDialogContent(dialogView, titleCandidates, messageCandidates, buttonTexts)

        // First non-empty text that's not a button label is the title
        val allButtons = buttonTexts.toSet()
        info.put("title", titleCandidates.firstOrNull { it !in allButtons } ?: "")
        info.put("message", messageCandidates.joinToString("\n") { it }.trim())

        // Classify buttons
        for (btn in buttonTexts) {
            val lower = btn.lowercase()
            if (lower in listOf("ok", "yes", "confirm", "allow", "确定", "确认", "允许")) {
                hasPositive = true
                positiveText = btn
            } else if (lower in listOf("cancel", "no", "deny", "取消", "拒绝")) {
                hasNegative = true
                negativeText = btn
            }
        }
        info.put("type", dialogType)
        info.put("has_positive", hasPositive)
        info.put("positive_text", positiveText)
        info.put("has_negative", hasNegative)
        info.put("negative_text", negativeText)

        val location = IntArray(2)
        dialogView.getLocationOnScreen(location)
        info.put("bounds", JSONArray(listOf(
            location[0], location[1],
            location[0] + dialogView.width,
            location[1] + dialogView.height
        )))

        return info
    }

    private fun extractDialogContent(
        view: View,
        titles: MutableList<String>,
        messages: MutableList<String>,
        buttons: MutableList<String>
    ) {
        if (view is Button) {
            view.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { buttons.add(it) }
            return
        }

        if (view is TextView && view !is Button) {
            val text = view.text?.toString()?.trim() ?: ""
            if (text.isNotEmpty()) {
                if (view.textSize > view.resources.displayMetrics.density * 18f) {
                    titles.add(text)
                } else {
                    messages.add(text)
                }
            }
        }

        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                view.getChildAt(i)?.let { extractDialogContent(it, titles, messages, buttons) }
            }
        }
    }

    private val idCounter = mutableMapOf<String, Int>()

    /**
     * Build an actionable-only tree from the View hierarchy.
     * Non-actionable ViewGroups (ConstraintLayout, LinearLayout, etc.) are transparent:
     * their actionable children are hoisted up to the nearest actionable ancestor.
     */
    private fun collectActionableViews(root: View, out: JSONArray) {
        idCounter.clear()
        // Delegate to the root — decorView itself is never actionable
        collectChildrenOf(root, out)
    }

    /** Collect actionable descendants of a (potentially non-actionable) View. */
    private fun collectChildrenOf(view: View, out: JSONArray) {
        if (view !is ViewGroup) return
        for (i in 0 until view.childCount) {
            val child = view.getChildAt(i) ?: continue
            if (!child.isShown) continue
            if (child.alpha <= 0f) continue
            if (isActionable(child)) {
                out.put(buildActionNode(child))
            } else {
                collectChildrenOf(child, out)
            }
        }
    }

    /** Build a JSON tree node for an actionable View, recursively adding children. */
    private fun buildActionNode(view: View): JSONObject {
        val action = JSONObject()
        val resourceId = getResourceIdString(view)
        val index = idCounter.getOrDefault(resourceId, 0)
        idCounter[resourceId] = index + 1
        action.put("id", resourceId)
        if (index > 0) action.put("index", index)

        val type = when {
            view is EditText -> "editable"
            isScrollableContainer(view) -> "scrollable"
            view.isClickable -> "clickable"
            view.isFocusable -> "clickable"
            else -> "clickable"
        }
        action.put("type", type)
        action.put("class", view.javaClass.name)
        action.put("enabled", view.isEnabled)
        action.put("visibility", when (view.visibility) {
            View.VISIBLE -> "visible"
            View.INVISIBLE -> "invisible"
            else -> "gone"
        })
        action.put("alpha", view.alpha.toDouble())
        action.put("focused", view.isFocused)

        val contentDesc = view.contentDescription?.toString()?.trim() ?: ""
        action.put("label", contentDesc)
        val hint = if (view is EditText) view.hint?.toString()?.trim() ?: "" else ""
        action.put("hint", hint)

        val location = IntArray(2)
        view.getLocationOnScreen(location)
        val bounds = JSONArray().apply {
            put(location[0]); put(location[1])
            put(location[0] + view.width); put(location[1] + view.height)
        }
        action.put("bounds", bounds)

        if (view is EditText) {
            val t = view.text?.toString() ?: ""
            action.put("text", if (t.isNotEmpty()) t else JSONObject.NULL)
        } else if (view is TextView) {
            val t = view.text?.toString()?.trim() ?: ""
            if (t.isNotEmpty()) {
                action.put("text", t)
                if (contentDesc.isEmpty()) action.put("label", t)
            }
        }

        if (isScrollableContainer(view)) {
            val canScrollVert = view.canScrollVertically(1) || view.canScrollVertically(-1)
            val canScrollHoriz = view.canScrollHorizontally(1) || view.canScrollHorizontally(-1)
            if (canScrollVert && canScrollHoriz) {
                action.put("scroll_direction", "both")
            } else if (canScrollVert) {
                action.put("scroll_direction", "vertical")
            } else if (canScrollHoriz) {
                action.put("scroll_direction", "horizontal")
            }
            // If neither direction is scrollable (all content fits), omit scroll_direction
        }

        // Build children array
        val childArr = JSONArray()
        collectChildrenOf(view, childArr)
        if (childArr.length() > 0) action.put("children", childArr)

        // Collect descriptor text from non-actionable TextViews
        val descriptors = JSONArray()
        collectDescriptors(view, descriptors)
        if (descriptors.length() > 0) action.put("descriptors", descriptors)

        return action
    }

    /** Walk non-actionable descendants to find TextViews with meaningful text. */
    private fun collectDescriptors(view: View, out: JSONArray) {
        if (view !is ViewGroup) return
        for (i in 0 until view.childCount) {
            val child = view.getChildAt(i) ?: continue
            if (!child.isShown) continue
            if (isActionable(child)) continue
            if (child is TextView && child !is Button) {
                val t = child.text?.toString()?.trim() ?: ""
                if (t.isNotEmpty()) {
                    out.put(JSONObject().apply {
                        put("text", t)
                        put("class", child.javaClass.name)
                    })
                }
            }
            if (child is ViewGroup) {
                collectDescriptors(child, out)
            }
        }
    }

    private fun isActionable(view: View): Boolean =
        view.isClickable || view.isFocusable || view is EditText || isScrollableContainer(view)

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

    private fun collectTrackedDialogs(dialogs: JSONArray) {
        for (view in com.bonnie.vta.VtaSdk.currentDialogViews) {
            if (view is ViewGroup && view.width > 0 && view.height > 0) {
                dialogs.put(extractDialogInfo(view))
            }
        }
    }
}
