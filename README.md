# VTA — View to Agent

将任何 Android App 的 UI 实时翻译成结构化 JSON，供 AI Agent 精准操控。

```
Agent → vta state → 获取 UI 树 → 决策 → vta click/input/scroll → 操控设备
```

## 1. 接入 Android App

`build.gradle.kts` 加一行：

```kotlin
dependencies {
    implementation("com.github.b0n-n1e:vta:v0.1.1")
}
```

`settings.gradle.kts` 加 JitPack 仓库：

```kotlin
repositories {
    maven { url = uri("https://jitpack.io") }
}
```

编译运行。无需改 AndroidManifest。

## 2. 安装 CLI + 注册 Skill

```bash
pip install git+https://github.com/b0n-n1e/vta.git#subdirectory=cli
vta install skill
```

Agent 自动发现 vta 命令，无需额外配置。

## 3. 开始使用

确保设备通过 adb 连接，App 已安装运行。

```bash
# 查看当前界面
vta state

# 点击元素（通过 resource-id）
vta click <package>:id/<element_id>

# 点击元素（通过文字）
vta click-text "搜索"

# 输入文字
vta input <package>:id/<input_field> "你好"

# 滚动
vta scroll <package>:id/<recycler_view> down

# 返回
vta back

# 等待 UI 稳定
vta wait
```

## 示例

```bash
$ vta state
{
  "ok": true,
  "data": {
    "package": "com.example.app",
    "activity": ".MainActivity",
    "actions": [
      {
        "id": "com.example:id/btn_login",
        "type": "clickable",
        "text": "登录",
        "bounds": [120, 800, 360, 920],
        "children": []
      },
      {
        "id": "com.example:id/input_phone",
        "type": "editable",
        "hint": "请输入手机号",
        "bounds": [40, 500, 500, 580],
        "focused": false
      }
    ]
  }
}

$ vta input com.example:id/input_phone "13800138000"
$ vta click com.example:id/btn_login
```

## 要求

- Android 7.0+
- Python 3.10+
- adb 已连接设备
