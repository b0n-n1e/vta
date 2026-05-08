package com.bonnie.vta.model

data class ActionSpace(
    val ok: Boolean = true,
    val data: ActionData? = null
)

data class ActionData(
    val packageName: String = "",
    val activity: String = "",
    val stable: Boolean = false,
    val resolution: Resolution? = null,
    val actions: List<UiAction> = emptyList(),
    val dialogs: List<DialogInfo> = emptyList(),
    val toasts: List<String> = emptyList()
)

data class Resolution(val width: Int, val height: Int)

data class UiAction(
    val id: String = "",
    val index: Int? = null,
    val type: String = "",
    val className: String = "",
    val label: String = "",
    val hint: String = "",
    val bounds: List<Int> = emptyList(),
    val enabled: Boolean = true,
    val visibility: String = "visible",
    val alpha: Double? = null,
    val focused: Boolean = false,
    val text: String? = null,
    val scrollDirection: String? = null,
    val adapterInfo: AdapterInfo? = null,
    val children: List<UiAction>? = null
)

data class AdapterInfo(
    val totalItems: Int = 0,
    val visibleRange: List<Int> = emptyList()
)

data class DialogInfo(
    val title: String = "",
    val message: String = ""
)

data class AgentCommand(
    val action: String,
    val target: String? = null,
    val text: String? = null,
    val direction: String? = null,
    val position: Int? = null,
    val index: Int? = null,
    val timeoutMs: Int = 5000
)
