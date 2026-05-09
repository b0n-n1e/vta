---
name: vta
description: Android UI Agent — 通过结构化 View 树数据操控 Android App。获取可交互元素列表、执行点击/输入/滚动。比截图快 100 倍。
---

# VTA — View to Agent

操控已集成 VTA SDK 的 Android App。基于真实 View 树（非截图），精度到像素级。

## 命令

| 命令 | 说明 |
|------|------|
| `vta state` | 当前屏幕可交互元素（树状 JSON） |
| `vta click <id>` | 点击，支持 `--index` 去重，支持按 class name 定位 |
| `vta click-text <text>` | 按可见文字点击 |
| `vta input <id> <text>` | 输入文本，自动拉起键盘 |
| `vta scroll <id> <direction>` | 滚动 (up/down/left/right)，支持 `--index` |
| `vta scroll-to <id> <pos>` | RecyclerView 精确定位 |
| `vta back` | 返回键 |
| `vta watch [-t sec] [-i ms]` | 连续轮询，输出 NDJSON 快照流 |
| `vta diff [-t sec] [-i ms]` | 等待内容变化，输出差异 |
| `vta health` | 检查 SDK |

## 输出字段

每个节点: `id` `index` `type` `class` `text` `hint` `bounds` `enabled` `visibility` `alpha` `focused` `scroll_direction` `item_count` `children`

顶级: `activity` `package` `fragments` `source` `stable` `stable_reason`

`type` 取值: `clickable` / `editable` / `scrollable` / `label`（非可交互文本标签，嵌入在树中正确位置）

## 核心工作流：直到达成目标，绝不放弃

### 第一步：从源码出发

目标明确后，**先读源码**，不要凭 VTA 猜测。

```
1. 从 activity name 定位 Activity/Fragment 源码
2. 读 layout XML → 知道有哪些组件、它们的 id、可见性条件
3. 读 Fragment/ViewHolder 代码 → 知道点击后的行为、异步依赖
```

### 第二步：VTA 验证当前状态

```bash
vta state  # 对比源码中的组件，确认哪些可见、哪些 enabled
```

关键检查点：
- `fragments` 数组 — 当前页面的 Fragment，用于定位源码文件
- 目标 view 的 `enabled` / `visibility` / `alpha`
- 列表容器的 `item_count` 和 `scroll_direction`

### 第三步：执行操作 + 验证结果

```bash
vta click <target>       # 返回的 JSON 包含 action + target + newState
```

操作后自动返回新状态。检查 `newState` 确认变化。

**如果操作失败（"View not found"）**：
1. 读取错误消息中的 `Did you mean: ...` 建议
2. 回到源码，检查 id 是否正确、view 是否在另一个 Fragment/Window 里
3. 尝试 `vta click-text <文字>` 作为备选
4. 对于无 id 的嵌套列表，用 class name: `vta scroll RecyclerView --index 1 right`

### 第四步：等待异步响应

触发网络请求或 AI 回复后，**不要假设立即生效**。

```bash
# 方式 A: 轮询差异
vta diff -t 60   # 等待 rv_messages 出现新子节点

# 方式 B: 持续监控
vta watch -t 120 -i 1000  # 每秒快照，Agent 逐行读取并决策
```

判定标准（从源码已知）：
- 空态 → 对话态: `rv_messages` 的 children 从 ViewPager2 变成消息卡片
- 加载中 → 完成: 消息卡片的 `descriptors` 从 "预计还需X分钟" 消失
- 推荐列表出现: `rv_messages` 的子节点中出现 `scrollable` + `item_count > 0`

### 第五步：未达目标时回溯

如果操作后状态不符合预期：
1. **读返回的 newState** — 检查目标 view 是否改变了
2. **读源码** — 检查是否有前置条件（权限、WebSocket 状态、feature flag）
3. **尝试备选路径** — 换一个 id、换文字匹配、换 class name
4. **不要放弃** — 除非源码表明确实不可达，否则持续尝试不同方式

## 定位优先级

1. `id` 不为空 → `vta click <package>:id/xxx`，配合 `--index` 去重
2. `text` 有值 → `vta click-text <text>`
3. `type: label` 的文字 → `vta click-text <label_text>`
4. 无 id 的嵌套容器 → `vta scroll RecyclerView --index N <direction>`
5. 错误提示里的 `Did you mean` → 尝试建议的 id
