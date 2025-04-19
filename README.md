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

本插件使用 AstrBot 的插件配置系统。请在 AstrBot 管理面板中进行以下操作：

1.  找到已安装的 `uptimerobot_monitor` 插件。
2.  点击 "插件配置"按钮。
3.  在配置界面中，您需要填写以下信息：
    *   **UptimeRobot API Key (api_key):** (必需) 填入您从 UptimeRobot 获取的 API Key。强烈建议使用 **Read-Only API Key**。
    *   **轮询间隔 (秒) (polling_interval):** (可选) 检查状态更新的间隔时间（秒）。默认为 60 秒。请勿设置过低（建议不低于 10 秒）以免触发 API 速率限制。
    *   **通知目标列表 (notification_targets):** (可选) 点击 "添加" 按钮可以添加一个或多个接收状态变更通知的目标会话 ID。格式为 `平台:ID`，例如 `qq:123456789` 或 `group:987654321`。具体平台名和 ID 获取方式请参考 AstrBot 的文档或适配器说明。
4.  点击 "保存"。

配置保存后，插件通常会自动重载。如果未生效，您可以尝试手动重载插件。

**重要提示:**

*   `api_key` 是必需的。请务必填写。

## 使用方法

*   发送指令 `/uptime_status` 给机器人，即可收到当前所有监控项的状态列表。

## 注意事项

*   **QQ 官方接口限制:** 根据 AstrBot 的 `Context.send_message` 文档，该方法不支持 `qq_official` 平台。这意味着如果您使用 QQ 官方接口适配器，可能无法接收到来自此插件的被动状态变更通知。主动查询 `/uptime_status` 功能不受影响。
*   **API 速率限制:** UptimeRobot 对 API 调用有频率限制（免费计划为每分钟 10 次请求）。请合理设置 `polling_interval` 以避免超出限制。
*   **数据存储:** 插件会在其数据目录下创建一个 `last_monitor_states.json` 文件，用于存储上次检查的状态，以便检测变化。 
