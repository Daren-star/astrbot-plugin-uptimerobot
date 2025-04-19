import asyncio
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain # 导入消息链和纯文本组件

# 第三方库
import requests
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# UptimeRobot 状态码到中文描述的映射
STATUS_MAP = {
    0: "暂停",
    1: "未检查",
    2: "正常",
    8: "疑似宕机",
    9: "宕机"
}

@register(
    "uptimerobot_monitor", # 插件唯一名称
    "YourName/AI",          # 你的名字或 AI
    "一个用于对接 UptimeRobot API 以监控网站状态的插件", # 插件描述
    "1.0.0"             # 插件版本
    # repo_url="可选的仓库地址"      # 可选
)
class UptimeRobotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.polling_task: Optional[asyncio.Task] = None
        self.data_path: Optional[Path] = None
        self.last_monitor_states_file: Optional[Path] = None
        # 假设 Context 或 Star 实例提供了获取数据目录的方法
        # 如果 AstrBot 有标准方式获取插件数据目录，请替换下面的逻辑
        try:
            # 尝试一种可能的方式获取数据目录
            # 注意：这只是一个猜测，实际方法可能不同
            plugin_metadata = self.context.get_registered_star("uptimerobot_monitor")
            if plugin_metadata and hasattr(plugin_metadata, 'data_path'):
                 self.data_path = Path(plugin_metadata.data_path)
            else:
                # 如果上面方法不行，尝试基于当前文件路径创建
                self.data_path = Path(__file__).parent / "data"
                logger.warning(f"无法通过 context 获取插件数据目录，使用默认路径: {self.data_path}")

            if self.data_path:
                self.data_path.mkdir(parents=True, exist_ok=True) # 确保目录存在
                self.last_monitor_states_file = self.data_path / "last_monitor_states.json"
                logger.info(f"插件数据文件路径设置为: {self.last_monitor_states_file}")
            else:
                 logger.error("未能确定插件数据目录路径。")

        except Exception as e:
             logger.error(f"初始化数据目录时出错: {e}", exc_info=True)


        logger.info("UptimeRobot 插件初始化完成。")

    async def initialize(self):
        """插件初始化，启动轮询任务"""
        logger.info("UptimeRobot 插件异步初始化开始...")
        # +++ Add config logging in initialize +++
        try:
             config_init = self.context.get_config()
             logger.info(f"initialize: self.context.get_config() returned type={type(config_init)}")
             print(f"PRINT initialize: self.context.get_config() returned type={type(config_init)}")
             if isinstance(config_init, dict):
                 logger.info("获取到的配置字典内容 (initialize):")
                 print("PRINT 获取到的配置字典内容 (initialize):")
                 if config_init:
                     for key, value in config_init.items():
                         logger.info(f"  key='{key}', value='{value}', type={type(value)}")
                         print(f"  PRINT key='{key}', value='{value}', type={type(value)}")
                 else:
                      logger.info("  配置字典为空 {}。")
                      print("  PRINT 配置字典为空 {}。")
             else:
                 logger.info(f"获取到的配置不是字典或为 None。 Value: {config_init}")
                 print(f"PRINT 获取到的配置不是字典或为 None。 Value: {config_init}")
        except Exception as e:
            logger.error(f"在 initialize 中获取或打印配置时出错: {e}", exc_info=True)
            print(f"PRINT 在 initialize 中获取或打印配置时出错: {e}")
        # +++ End config logging +++

        # 注意：API Key 和其他配置的检查将在轮询循环内部或需要时进行

        # 将轮询任务的启动移到方法末尾
        if self.polling_task is None or self.polling_task.done():
                self.polling_task = asyncio.create_task(self._polling_loop())
                logger.info("轮询任务已创建并启动。")
        else:
                logger.warning("轮询任务已在运行中，跳过重复创建。")

    # --- 辅助函数将在后续步骤实现 ---
    def _get_status_description(self, status_code: int) -> str:
        """获取状态码的中文描述"""
        return STATUS_MAP.get(status_code, f"未知状态({status_code})")

    def _read_last_states(self) -> Dict[str, Any]:
        """读取上次保存的监控状态"""
        if not self.last_monitor_states_file:
            logger.error("上次状态文件路径未设置，无法读取。")
            return {}
        try:
            if self.last_monitor_states_file.exists():
                with open(self.last_monitor_states_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content: # 处理空文件情况
                        return {}
                    return json.loads(content)
            else:
                logger.info("上次状态文件不存在，将返回空状态。")
                return {}
        except FileNotFoundError:
            logger.info("上次状态文件不存在 (FileNotFoundError)。")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"解析上次状态文件失败: {e}. 文件内容可能已损坏。", exc_info=True)
            # 考虑在这里备份或删除损坏的文件
            return {}
        except Exception as e:
            logger.error(f"读取上次状态文件时发生未知错误: {e}", exc_info=True)
            return {}

    def _write_current_states(self, states: Dict[str, Any]):
        """将当前监控状态写入文件"""
        if not self.last_monitor_states_file:
            logger.error("上次状态文件路径未设置，无法写入。")
            return
        try:
            with open(self.last_monitor_states_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, ensure_ascii=False, indent=4)
            # logger.debug(f"当前状态已成功写入: {self.last_monitor_states_file}") # 调试时可取消注释
        except IOError as e:
            logger.error(f"写入当前状态文件时发生 IO 错误: {e}", exc_info=True)
        except TypeError as e:
             logger.error(f"序列化当前状态为 JSON 时发生类型错误: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"写入当前状态文件时发生未知错误: {e}", exc_info=True)

    async def _call_uptimerobot_api(self, method: str, data: dict = None) -> Dict[str, Any]:
        """调用 UptimeRobot API"""
        # --- 在需要时检查和获取配置 ---
        config = self.context.get_config()
        # +++ Enhanced INFO Logging +++
        logger.info(f"_call_uptimerobot_api: self.context.get_config() returned type={type(config)}")
        if isinstance(config, dict):
             logger.info("获取到的配置字典内容 (_call_uptimerobot_api):")
             print("PRINT 获取到的配置字典内容 (_call_uptimerobot_api):") # +++ Add print
             if config:
                 for key, value in config.items():
                     logger.info(f"  key='{key}', value='{value}', type={type(value)}")
                     print(f"  PRINT key='{key}', value='{value}', type={type(value)}")
             else:
                  logger.info("  配置字典为空 {}。")
                  print("  PRINT 配置字典为空 {}。") # +++ Add print
        else:
            logger.info(f"获取到的配置不是字典或为 None。 Value: {config}")
            print(f"PRINT 获取到的配置不是字典或为 None。 Value: {config}") # +++ Add print
        # +++ End Enhanced Logging +++

        if not config or not isinstance(config, dict):
            logger.error("插件配置无法通过 self.context.get_config() 获取或类型错误，无法调用 API。")
            return {"stat": "fail", "error": {"message": "Plugin configuration cannot be loaded or is invalid"}}

        api_key = config.get('api_key')
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
             logger.error("API Key 未在插件配置中设置、为空或类型错误，无法调用 UptimeRobot API。")
             return {"stat": "fail", "error": {"message": "API Key not configured correctly in plugin"}}
        # --- 配置检查结束 ---

        api_url = f"https://api.uptimerobot.com/v2/{method}"
        payload = {
            'api_key': api_key,
            'format': 'json'
        }
        if data:
            payload.update(data)

        try:
            # 使用 asyncio.to_thread 在异步环境中运行同步的 requests 代码
            # 设置合理的超时时间，例如 15 秒
            response = await asyncio.to_thread(
                requests.post, api_url, data=payload, timeout=15
            )

            response.raise_for_status() # 对 >= 400 的状态码抛出 HTTPError

            json_response = response.json()

            # 检查 UptimeRobot API 返回的业务状态
            if json_response.get('stat') == 'fail':
                error_message = json_response.get('error', {}).get('message', 'Unknown API error')
                logger.error(f"UptimeRobot API 调用失败 ({method}): {error_message} | 请求数据: {data}")
                return json_response # 返回包含错误信息的原始响应
            
            # logger.debug(f"UptimeRobot API 调用成功 ({method}).") # 调试时可取消注释
            return json_response

        except requests.exceptions.Timeout:
            logger.error(f"调用 UptimeRobot API ({method}) 超时。 URL: {api_url}")
            return {"stat": "fail", "error": {"type": "timeout", "message": "Request timed out"}}
        except requests.exceptions.RequestException as e:
            logger.error(f"调用 UptimeRobot API ({method}) 时发生网络错误: {e}", exc_info=True)
            return {"stat": "fail", "error": {"type": "network_error", "message": str(e)}}
        except json.JSONDecodeError as e:
             logger.error(f"解析 UptimeRobot API ({method}) 响应 JSON 时失败: {e}. 响应内容: {response.text[:500]}", exc_info=True)
             return {"stat": "fail", "error": {"type": "json_decode_error", "message": "Failed to decode API response"}}
        except Exception as e:
            logger.error(f"调用 UptimeRobot API ({method}) 时发生未知错误: {e}", exc_info=True)
            return {"stat": "fail", "error": {"type": "unknown", "message": str(e)}}

    # --- 指令处理函数 ---
    @filter.command("uptime_status")
    async def uptime_status(self, event: AstrMessageEvent):
        """获取并显示当前 UptimeRobot 监控状态"""
        # --- 在需要时检查和获取配置 ---
        config = self.context.get_config()
        if not config or not isinstance(config, dict):
             yield event.plain_result("错误：无法加载插件配置。请检查 AstrBot 配置或日志。")
             logger.error("无法获取插件配置 (uptime_status)。")
             return

        api_key = config.get('api_key')
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            yield event.plain_result("错误：UptimeRobot API Key 未在插件配置中正确设置。请在 AstrBot UI 中配置。")
            logger.error("未找到或无效的 API Key (uptime_status)。")
            return
        # --- 配置检查结束 ---

        logger.info(f"收到用户 {event.get_sender_name()} 的 /uptime_status 请求。")
        # API 调用会自动检查 api_key (通过 _call_uptimerobot_api 内部的逻辑)
        api_response = await self._call_uptimerobot_api('getMonitors')

        if api_response.get('stat') == 'fail':
            error_msg = api_response.get('error', {}).get('message', '未知 API 错误')
            logger.error(f"获取监控状态失败: {error_msg}")
            yield event.plain_result(f"获取监控状态失败: {error_msg}。请检查日志或 API Key。")
            return

        monitors = api_response.get('monitors', [])
        if not monitors:
            yield event.plain_result("当前没有配置任何 UptimeRobot 监控项，或 API 返回为空。")
            return

        status_lines = ["【当前 UptimeRobot 监控状态】"]
        for monitor in monitors:
            monitor_name = monitor.get('friendly_name', f"ID: {monitor.get('id', '未知')}")
            status_code = monitor.get('status')
            status_desc = self._get_status_description(status_code)
            status_lines.append(f"- {monitor_name}: {status_desc}")
        
        total_monitors = api_response.get('pagination', {}).get('total', len(monitors))
        limit = api_response.get('pagination', {}).get('limit', 50) # API 默认 limit 是 50
        if total_monitors > limit:
            status_lines.append(f"\n(注意: API 默认最多返回 {limit} 个监控项，总共有 {total_monitors} 个)")

        output_message = "\n".join(status_lines)
        yield event.plain_result(output_message)
        logger.info(f"已向用户 {event.get_sender_name()} 回复监控状态。")

    # --- 后台轮询任务 ---
    async def _polling_loop(self):
        """后台轮询检查状态变化"""
        logger.info("轮询循环已启动。")
        # +++ Simplified initial call +++
        logger.info("尝试获取一次初始监控状态...")
        initial_response = await self._call_uptimerobot_api('getMonitors')
        if initial_response.get('stat') == 'ok':
            self._write_current_states(initial_response)
            logger.info("初始监控状态获取成功并已保存。")
        else:
            error_msg = initial_response.get('error', {}).get('message', '未知 API 错误')
            logger.error(f"获取初始监控状态失败: {error_msg}")
        # +++ End Simplified initial call +++

        # 初始等待一个较短时间，以防配置尚未完全就绪
        # await asyncio.sleep(5) # Removed initial sleep

        while True:
            polling_interval = 60 # 默认间隔，如果配置读取失败则使用
            config = None # 重置配置变量
            try:
                logger.debug("执行一次轮询检查...")
                # --- 在需要时检查和获取配置 ---
                config = self.context.get_config()
                # +++ Enhanced INFO Logging +++
                logger.info(f"_polling_loop: self.context.get_config() returned type={type(config)}")
                if isinstance(config, dict):
                    logger.info("获取到的配置字典内容 (_polling_loop):")
                    print("PRINT 获取到的配置字典内容 (_polling_loop):") # +++ Add print
                    if config:
                        for key, value in config.items():
                            logger.info(f"  key='{key}', value='{value}', type={type(value)}")
                            print(f"  PRINT key='{key}', value='{value}', type={type(value)}")
                    else:
                        logger.info("  配置字典为空 {}。")
                        print("  PRINT 配置字典为空 {}。") # +++ Add print
                else:
                    logger.info(f"获取到的配置不是字典或为 None。 Value: {config}")
                    print(f"PRINT 获取到的配置不是字典或为 None。 Value: {config}") # +++ Add print
                # +++ End Enhanced Logging +++

                if not config or not isinstance(config, dict):
                    logger.warning("无法加载插件配置或配置类型错误，跳过本次轮询。")
                    await asyncio.sleep(polling_interval) # 使用默认间隔
                    continue

                api_key = config.get('api_key')
                if not api_key or not isinstance(api_key, str) or not api_key.strip():
                    logger.warning("API Key 未在插件配置中正确设置，跳过本次轮询。")
                    # 尝试读取轮询间隔用于休眠
                    try: polling_interval = int(config.get('polling_interval', 60))
                    except (ValueError, TypeError): polling_interval = 60
                    if polling_interval < 10: polling_interval = 10
                    await asyncio.sleep(polling_interval)
                    continue

                # 读取当前轮询间隔 (每次循环都读，允许动态修改)
                try:
                    polling_interval = int(config.get('polling_interval', 60))
                except (ValueError, TypeError):
                    logger.warning(f"配置中的 polling_interval 值无效，使用默认值 60。原始值: {config.get('polling_interval')}")
                    polling_interval = 60
                if polling_interval < 10:
                    logger.warning(f"配置的 polling_interval ({polling_interval}) 小于最小值 10，将使用 10。")
                    polling_interval = 10
                # --- 配置检查结束 ---

                # 获取当前状态 (API 调用会使用检查过的 api_key)
                current_response = await self._call_uptimerobot_api('getMonitors')
                if current_response.get('stat') != 'ok':
                    error_msg = current_response.get('error', {}).get('message', '未知 API 错误')
                    logger.error(f"轮询时获取监控状态失败: {error_msg}")
                    # 出错时也等待，使用已读取的 polling_interval
                    await asyncio.sleep(polling_interval) 
                    continue
                
                # 获取上次状态
                last_states_data = self._read_last_states()
                last_monitors_dict = {m['id']: m for m in last_states_data.get('monitors', []) if 'id' in m}

                # 状态比较
                current_monitors = current_response.get('monitors', [])
                changed_monitors = []
                # current_states_dict = {} # 不再需要在循环外定义

                for monitor in current_monitors:
                    monitor_id = monitor.get('id')
                    if monitor_id is None:
                        logger.warning(f"发现一个没有 ID 的监控项: {monitor}")
                        continue
                    
                    # current_states_dict[monitor_id] = monitor # 不再需要存储整个状态
                    current_status = monitor.get('status')
                    monitor_name = monitor.get('friendly_name', f"ID: {monitor_id}")

                    last_monitor = last_monitors_dict.get(monitor_id)
                    if last_monitor:
                        last_status = last_monitor.get('status')
                        if current_status is not None and last_status is not None and current_status != last_status:
                            logger.info(f"检测到状态变化: 监控项 '{monitor_name}' (ID: {monitor_id}) 从 {last_status} 变为 {current_status}")
                            changed_monitors.append({
                                'id': monitor_id,
                                'name': monitor_name,
                                'old_status': last_status,
                                'new_status': current_status
                            })
                    
                # 发送通知
                if changed_monitors:
                    # --- 在需要时获取配置 ---
                    notification_targets = [] # Default to empty list
                    if config: # Ensure config was loaded successfully earlier in the loop
                        targets_from_config = config.get('notification_targets', [])
                        if isinstance(targets_from_config, list):
                            # 过滤并转换为字符串
                            notification_targets = [str(t).strip() for t in targets_from_config if isinstance(t, (str, int)) and str(t).strip()]
                            # 移除空字符串目标
                            notification_targets = [t for t in notification_targets if t]
                        else:
                            logger.warning(f"配置中的 notification_targets 不是列表 (类型: {type(targets_from_config)})，本次不发送通知。")
                    else:
                         logger.warning("配置未加载，无法获取 notification_targets，本次不发送通知。")
                    # --- 配置获取结束 ---

                    if notification_targets:
                        logger.info(f"准备向 {len(notification_targets)} 个目标发送 {len(changed_monitors)} 条状态变更通知。")
                        for change in changed_monitors:
                            old_status_desc = self._get_status_description(change['old_status'])
                            new_status_desc = self._get_status_description(change['new_status'])
                            notify_message = f"【UptimeRobot 状态变更】\n监控项: {change['name']}\n状态: {old_status_desc} -> {new_status_desc}"
                            message_list = [Plain(text=notify_message)] 

                            for target_session_id in notification_targets:
                                try:
                                    sent = await self.context.send_message(target_session_id, message_list) 
                                    if sent:
                                         logger.info(f"已成功向 {target_session_id} 发送通知: {change['name']}")
                                    else:
                                         logger.warning(f"发送通知到 {target_session_id} 失败 (平台不支持或未找到会话)。")
                                except Exception as send_error:
                                    logger.error(f"向 {target_session_id} 发送通知时出错: {send_error}", exc_info=True)
                    else:
                        logger.info("检测到状态变化，但未配置通知目标 (notification_targets)，不发送通知。")

                # 保存当前状态 (无论是否变化都要保存最新状态)
                self._write_current_states(current_response)

            except asyncio.CancelledError:
                logger.info("轮询任务被取消。")
                break
            except Exception as e:
                logger.error(f"轮询循环中发生未捕获的错误: {e}", exc_info=True)
                # 避免因为未知错误导致CPU占用过高，增加短暂休眠
                await asyncio.sleep(5)
            finally:
                # 确保即使出错也有休眠，防止CPU空转
                # 使用在 try 块开始时获取的 polling_interval (或默认值)
                # logger.debug(f"轮询结束，等待 {polling_interval} 秒...") # 调试时可取消注释
                await asyncio.sleep(polling_interval)
        logger.info("轮询循环已结束。")


    async def terminate(self):
        """插件卸载/停用时调用，用于清理资源"""
        logger.info("UptimeRobot 插件终止...")
        if self.polling_task and not self.polling_task.done():
            logger.info("正在取消轮询任务...")
            self.polling_task.cancel()
            try:
                await self.polling_task # 等待任务实际完成取消
                logger.info("轮询任务已成功取消。")
            except asyncio.CancelledError:
                logger.info("轮询任务取消确认。") # 正常取消
            except Exception as e:
                logger.error(f"等待轮询任务取消时发生错误: {e}", exc_info=True)
        else:
             logger.info("轮询任务不存在或已完成，无需取消。")