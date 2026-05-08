---
name: vta
description: Android UI Agent — 通过结构化 View 树数据操控 Android App。获取可交互元素列表、执行点击/输入/滚动。比截图快 100 倍。
---

# VTA — View to Agent

操控已集成 VTA SDK 的 Android App。所有操作基于真实 View 树（非截图），精度到像素级。

## 可用命令

| 命令 | 说明 |
|------|------|
| `vta state` | 获取当前屏幕可交互元素（树状 JSON） |
| `vta click <id>` | 点击元素，用 resource-id 定位，支持 --index 去重 |
| `vta click-text <text>` | 按可见文字定位并点击 |
| `vta input <id> <text>` | 向输入框输入文本，自动拉起键盘 |
| `vta scroll <id> <direction>` | 滚动容器，direction: up/down/left/right |
| `vta scroll-to <id> <pos>` | RecyclerView 精确定位到 position |
| `vta back` | 按返回键 |
| `vta wait [-t ms]` | 等待 UI 稳定后返回状态 |
| `vta health` | 检查 SDK 是否运行 |

## 输出

每个 action 节点包含：
- `id`, `index` — 定位标识，index 用于同 ID 去重
- `type` — clickable / editable / scrollable
- `class` — 完整 Java 类名
- `text`, `hint`, `label` — 语义信息
- `bounds` — [left, top, right, bottom] 屏幕坐标
- `enabled`, `visibility`, `alpha`, `focused` — 状态
- `scroll_direction` — vertical / horizontal / both
- `descriptors` — 非可交互子 view 的文本标签
- `children` — 树状嵌套的可交互子元素
- `stable`, `stable_reason` — UI 是否稳定（frames_stable / timeout）

## 工作流

**验证/操作 UI**：
1. `vta state` 获取当前视图树
2. 从 actions 中定位目标：按 id、text、descriptors 匹配
3. `vta click` / `vta input` / `vta scroll` 执行操作
4. 每次操作后自动返回新状态（含 stable_reason）

**等待异步响应**（发送消息/网络请求后）：
1. `vta click` 触发操作 → 得到新状态
2. 等待 2-5 秒
3. `vta state` 轮询检查变化
4. 重复直到状态变化出现

## 定位元素的优先级

1. `id` 不为空 → 用 `vta click <id>`，配合 `--index` 去重
2. `text` 有值 → 用 `vta click-text <text>`
3. `descriptors` 有值 → 用 `vta click-text <descriptor_text>` 定位到父节点
4. `hint` 有值 → 用 `vta click-text <hint>` 定位输入框
5. 以上都为空 → 用 `class` + `bounds` 结合上下文推断

## 注意

- state 优先于 screenshot，结构化数据快 100 倍
- 每次 CLI 调用是独立同步的：发请求、等结果、输出 JSON、退出
- SDK 不会主动推送 UI 变化，异步操作必须轮询
- 非可交互的 TextView 文字会出现在父节点的 `descriptors` 数组中
