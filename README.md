# VTA — View to Agent

一行 Gradle 注入任意 Android App，AI Agent 即可通过命令行实时读取 UI 树、执行点击、输入、滚动操作。**零截图，纯结构化数据。**

```
Agent → vta state (获取 UI 树) → 决策 → vta click/input/scroll → 设备执行
```

## 接入

**Android 侧** — `build.gradle.kts` 加一行依赖：

```kotlin
dependencies {
    implementation("com.github.b0n-n1e:vta:v0.2.4")
}
```

`settings.gradle.kts` 加 JitPack 仓库：

```kotlin
repositories {
    maven { url = uri("https://jitpack.io") }
}
```

编译运行。无需改 AndroidManifest。

**Agent 侧** — 安装 CLI：

```bash
pip install git+https://github.com/b0n-n1e/vta.git#subdirectory=cli
vta install skill
```

Agent 自动发现 vta 命令。

## 命令

| 命令 | 说明 |
|------|------|
| `vta state` | 获取当前屏幕 UI 树（JSON） |
| `vta click <id>` | 点击元素，支持 `--index` 去重 |
| `vta click-text <text>` | 按可见文字点击 |
| `vta input <id> <text>` | 输入文本，自动拉起键盘 |
| `vta scroll <id> <direction>` | 滚动容器，direction: up/down/left/right |
| `vta scroll-to <id> <pos>` | RecyclerView 精确定位 |
| `vta tap <x> <y>` | 按屏幕坐标注入真实触摸事件（绕过 performClick 限制） |
| `vta swipe <x1> <y1> <x2> <y2>` | 注入真实滑动手势（DOWN→MOVE→UP） |
| `vta back` | 返回键 |
| `vta wait [-t ms]` | 等 UI 稳定后返回状态 |
| `vta health` | 检查 SDK 运行状态 |

每次操作后自动返回新状态。

## 示例

```bash
$ vta state
```

```json
{
  "ok": true,
  "data": {
    "package": "com.example.app",
    "activity": ".MainActivity",
    "stable": true,
    "stable_reason": "frames_stable",
    "resolution": {"width": 1440, "height": 3040},
    "actions": [
      {
        "id": "com.example:id/rv_list",
        "type": "scrollable",
        "class": "androidx.recyclerview.widget.RecyclerView",
        "bounds": [0, 120, 1440, 2800],
        "scroll_direction": "vertical",
        "children": [
          {
            "id": "",
            "type": "clickable",
            "class": "android.widget.LinearLayout",
            "bounds": [0, 120, 1440, 280],
            "descriptors": ["商品标题文本"],
            "children": [
              {
                "id": "com.example:id/btn_buy",
                "index": 0,
                "type": "clickable",
                "class": "android.widget.Button",
                "text": "购买",
                "bounds": [1200, 180, 1360, 260]
              }
            ]
          }
        ]
      },
      {
        "id": "com.example:id/input_search",
        "type": "editable",
        "class": "android.widget.EditText",
        "hint": "搜索",
        "bounds": [40, 60, 1400, 120],
        "focused": false
      }
    ]
  }
}
```

```bash
$ vta input com.example:id/input_search "手机"
$ vta click com.example:id/btn_buy
```

## 输出字段

每个 action 节点：

| 字段 | 说明 |
|------|------|
| `id` | resource-id，定位用（空字符串 = 无 id） |
| `index` | 同 id 去重序号（0 不输出） |
| `type` | clickable / editable / scrollable |
| `class` | 完整 Java 类名 |
| `text` | 可见文本 |
| `hint` | 输入框 placeholder |
| `label` | contentDescription 或文本 |
| `bounds` | [left, top, right, bottom] |
| `enabled` | 是否可交互 |
| `visibility` | visible / invisible / gone |
| `alpha` | 透明度 0.0 - 1.0 |
| `focused` | 是否持有焦点 |
| `scroll_direction` | vertical / horizontal / both |
| `descriptors` | 非可交互子 View 的文字（用于语义匹配） |
| `children` | 树状嵌套的子元素 |

全局：

| 字段 | 说明 |
|------|------|
| `stable` | UI 是否稳定 |
| `stable_reason` | frames_stable（真实稳定）/ timeout（超时兜底）/ direct_query（直接查询） |

## 要求

- Android 7.0+
- Python 3.10+
- adb 已连接设备
