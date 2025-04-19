# AstrBot UptimeRobot Monitor Plugin

**版本:** 1.0.0
**作者:** YourName/AI

这是一个为 AstrBot 设计的插件，用于对接 UptimeRobot API，监控您的网站或其他服务的在线状态。

## 功能

*   **主动查询状态:** 使用 `/uptime_status` 指令获取您所有 UptimeRobot 监控项的当前状态。
*   **被动状态通知:** 当监控项的状态发生变化时（例如从"正常"变为"宕机"或反之），插件会自动向预先配置好的聊天会话发送通知。

## 依赖

本插件需要 `requests` 库来与 UptimeRobot API 进行通信。请确保您的 AstrBot 环境中安装了此库。插件加载时会自动尝试通过 `requirements.txt` 安装。

`requirements.txt`:
```
requests
```

## 配置

在使用此插件之前，您需要在 AstrBot 的主配置文件（通常是 `config.yaml`）中添加以下配置段：

```yaml
plugin:
  uptimerobot:
    # --- 必需 ---
    api_key: "YOUR_UPTIMEROBOT_READ_ONLY_API_KEY" # 请在此处填入您的 UptimeRobot API Key (建议使用 Read-Only Key)

    # --- 可选 ---
    polling_interval: 60  # 检查状态更新的间隔时间（秒）。默认 60 秒。请勿设置过低以免触发 API 速率限制（免费版为 10 次/分钟）。最低强制为 10 秒。
    notification_targets: # 接收状态变更通知的目标会话 ID 列表。格式为 "平台:ID"。
      - "qq:123456789"    # 示例：QQ 用户
      - "group:987654321" # 示例：QQ 群组
      # - "telegram_user:11223344" # 示例：Telegram 用户
      # - "telegram_chat:-55667788" # 示例：Telegram 群组
```

**重要提示:**

*   `api_key` 是必需的。您可以从 UptimeRobot 网站的 "My Settings" 页面获取。为了安全起见，强烈建议您生成并使用 **Read-Only API Key**，因为此插件的核心功能（查询状态和基于状态变化的通知）不需要修改权限。
*   `notification_targets` 是一个列表，包含了希望接收状态变化通知的会话的唯一标识符。您需要知道目标用户或群组在相应平台（如 QQ、Telegram 等）上的 ID，并按照 `"平台名:ID"` 的格式填写。具体平台名和 ID 获取方式请参考 AstrBot 的文档或适配器说明。

配置完成后，请重启 AstrBot 或在管理面板中重载此插件以使配置生效。

## 使用方法

*   发送指令 `/uptime_status` 给机器人，即可收到当前所有监控项的状态列表。

## 注意事项

*   **QQ 官方接口限制:** 根据 AstrBot 的 `Context.send_message` 文档，该方法不支持 `qq_official` 平台。这意味着如果您使用 QQ 官方接口适配器，可能无法接收到来自此插件的被动状态变更通知。主动查询 `/uptime_status` 功能不受影响。
*   **API 速率限制:** UptimeRobot 对 API 调用有频率限制（免费计划为每分钟 10 次请求）。请合理设置 `polling_interval` 以避免超出限制。
*   **数据存储:** 插件会在其数据目录下创建一个 `last_monitor_states.json` 文件，用于存储上次检查的状态，以便检测变化。 
