"""
天气插件主类

AstrBot 插件的入口点，处理消息事件和命令路由。
"""

from typing import Dict, Any, Optional, List, Union
import logging
import re
from .interfaces import IWeatherPlugin
from .config import ConfigManager, WeatherConfig
from .models import WeatherCommand, ConfigurationError, CommandType, Season
from .localization import localization_manager
from .command_parser import CommandParser
from .help_system import help_system
from .weather_service import WeatherService
from .api_client import WeatherAPIClient
from .cache import CacheManager
from .location_service import LocationService
from .user_preferences import UserPreferences
from .activity_recommender import ActivityRecommender
from .alert_manager import AlertManager


class WeatherPlugin(IWeatherPlugin):
    """智能天气助手插件主类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化插件"""
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        
        try:
            # 加载配置
            if config:
                # 如果提供了配置字典，创建临时配置对象
                self.config = WeatherConfig(**config)
                self.config.validate()
            else:
                # 从文件加载配置
                self.config = self.config_manager.load_config()
            
            # 设置本地化语言
            localization_manager.set_language(self.config.default_language)
            
            # 初始化所有服务组件
            self._init_services()
            
            # 初始化命令解析器
            self.command_parser = CommandParser()
            
            # 初始化命令模式（保持向后兼容）
            self._init_command_patterns()
            
            self.logger.info(f"天气插件初始化成功，使用 API 提供商: {self.config.api_provider}")
            
        except ConfigurationError as e:
            self.logger.error(f"配置错误: {e}")
            raise
        except Exception as e:
            self.logger.error(f"插件初始化失败: {e}")
            raise
    
    def _init_services(self):
        """初始化所有服务组件"""
        try:
            # 初始化缓存管理器
            self.cache_manager = CacheManager(self.config)
            
            # 初始化API客户端
            self.api_client = WeatherAPIClient(self.config)
            
            # 初始化位置服务
            self.location_service = LocationService(self.config)
            
            # 初始化用户偏好管理
            self.user_preferences = UserPreferences()
            
            # 初始化天气服务（核心服务）
            self.weather_service = WeatherService(
                config=self.config,
                api_client=self.api_client,
                cache_manager=self.cache_manager,
                location_service=self.location_service,
                user_preferences=self.user_preferences
            )
            
            # 初始化活动推荐器
            self.activity_recommender = ActivityRecommender()
            
            # 初始化警报管理器
            self.alert_manager = AlertManager()
            
            self.logger.info("所有服务组件初始化成功")
            
        except Exception as e:
            self.logger.error(f"初始化服务组件失败: {e}")
            raise
    
    def _init_command_patterns(self):
        """初始化命令匹配模式"""
        self.command_patterns = {
            'weather': [
                r'(?:天气|weather)\s*(.+)',
                r'(.+)(?:的天气|天气怎么样|天气如何)',
                r'今天(.*)天气',
            ],
            'forecast': [
                r'(?:预报|forecast)\s*(.+)',
                r'(.+)(?:的预报|预报怎么样)',
                r'明天(.*)天气',
                r'后天(.*)天气',
            ],
            'help': [
                r'(?:帮助|help|使用说明)',
                r'天气(?:帮助|命令)',
            ]
        }
    
    async def on_message(self, event: Any) -> Optional[str]:
        """
        处理消息事件
        
        Args:
            event: AstrBot 消息事件对象
            
        Returns:
            Optional[str]: 回复消息，如果不需要回复则返回 None
        """
        try:
            # 提取消息内容和用户信息
            message_text = self._extract_message_text(event)
            user_id = self._extract_user_id(event)
            
            if not message_text:
                return None
            
            self.logger.debug(f"收到消息: {message_text} (用户: {user_id})")
            
            # 使用新的命令解析器
            weather_command = self.command_parser.parse_command(message_text)
            if weather_command:
                return await self._handle_weather_command_object(weather_command, user_id)
            
            # 检查是否是帮助请求
            if help_system.is_help_request(message_text):
                return help_system.get_help_message()
            
            # 尝试提供命令建议
            suggestion = help_system.suggest_command(message_text)
            if suggestion:
                return suggestion
            
            # 检查是否是天气相关的自然语言查询（备用方法）
            if self._is_weather_message(message_text):
                return await self._handle_natural_language_query(message_text, user_id)
            
            return None
            
        except Exception as e:
            self.logger.error(f"处理消息时发生错误: {e}")
            return localization_manager.format_error('processing_error')
    
    async def on_command(self, command: str, args: List[str], user_id: str) -> str:
        """
        处理命令
        
        Args:
            command: 命令名称
            args: 命令参数
            user_id: 用户ID
            
        Returns:
            str: 命令执行结果
        """
        try:
            self.logger.debug(f"收到命令: {command} {args} (用户: {user_id})")
            
            # 标准化命令名称
            normalized_command = self._normalize_command(command)
            
            if normalized_command in ['weather', 'w', '天气']:
                return await self._handle_weather_command(args, user_id)
            elif normalized_command in ['forecast', 'f', '预报']:
                return await self._handle_forecast_command(args, user_id)
            elif normalized_command in ['help', 'h', '帮助', 'weather-help', 'wh']:
                return help_system.get_help_message()
            elif normalized_command in ['config', 'cfg', '配置']:
                return await self._handle_config_command(args, user_id)
            else:
                return localization_manager.format_error('unknown_command', command=command)
                
        except Exception as e:
            self.logger.error(f"处理命令时发生错误: {e}")
            return localization_manager.format_error('command_error')
    
    def reload_config(self) -> None:
        """重新加载配置"""
        try:
            # 关闭现有服务（如果存在）
            if hasattr(self, 'cache_manager'):
                self.cache_manager.close()
            
            if hasattr(self, 'api_client'):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.api_client.close())
                    else:
                        loop.run_until_complete(self.api_client.close())
                except Exception as e:
                    self.logger.debug(f"关闭API客户端时出错: {e}")
            
            # 重新加载配置
            self.config = self.config_manager.reload_config()
            
            # 更新本地化语言
            localization_manager.set_language(self.config.default_language)
            
            # 重新初始化服务组件
            self._init_services()
            
            # 重新初始化命令模式
            self._init_command_patterns()
            
            self.logger.info("配置重新加载成功")
            
        except Exception as e:
            self.logger.error(f"重新加载配置失败: {e}")
            raise
    
    def _extract_message_text(self, event: Any) -> str:
        """从事件中提取消息文本"""
        # 支持多种事件格式
        if hasattr(event, 'message'):
            return str(event.message).strip()
        elif hasattr(event, 'text'):
            return str(event.text).strip()
        elif hasattr(event, 'content'):
            return str(event.content).strip()
        elif isinstance(event, str):
            return event.strip()
        elif isinstance(event, dict):
            return event.get('message', event.get('text', event.get('content', ''))).strip()
        else:
            return str(event).strip()
    
    def _extract_user_id(self, event: Any) -> str:
        """从事件中提取用户ID"""
        if hasattr(event, 'user_id'):
            return str(event.user_id)
        elif hasattr(event, 'sender_id'):
            return str(event.sender_id)
        elif hasattr(event, 'from_user'):
            return str(event.from_user)
        elif isinstance(event, dict):
            return str(event.get('user_id', event.get('sender_id', event.get('from_user', 'unknown'))))
        else:
            return 'unknown'
    
    def _parse_message_as_command(self, message: str) -> Optional[tuple]:
        """尝试将消息解析为命令"""
        message = message.strip()
        
        # 检查是否以命令前缀开始
        if message.startswith('/') or message.startswith('!'):
            parts = message[1:].split()
            if parts:
                return (parts[0], parts[1:])
        
        # 使用正则表达式匹配命令模式
        for command_type, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.match(pattern, message, re.IGNORECASE)
                if match:
                    location = match.group(1).strip() if match.groups() else ""
                    return (command_type, [location] if location else [])
        
        return None
    
    def _normalize_command(self, command: str) -> str:
        """标准化命令名称"""
        command = command.lower().strip()
        
        # 命令别名映射
        alias_map = {
            'w': 'weather',
            '天气': 'weather',
            'f': 'forecast',
            '预报': 'forecast',
            'h': 'help',
            '帮助': 'help',
            'wh': 'help',
            '天气帮助': 'help',
            'weather-help': 'help',
            'cfg': 'config',
            '配置': 'config',
        }
        
        return alias_map.get(command, command)
    
    def _is_weather_message(self, message: str) -> bool:
        """检查消息是否与天气相关"""
        weather_keywords = [
            '天气', '气温', '温度', '下雨', '晴天', '阴天', '多云', '雨天', '雪天',
            '风速', '湿度', '预报', '今天', '明天', '后天', '大后天',
            '热不热', '冷不冷', '会下雨吗', '会下雪吗', '需要带伞吗',
            'weather', 'temperature', 'rain', 'sunny', 'cloudy', 'forecast',
            'hot', 'cold', 'warm', 'cool', 'humid', 'dry'
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in weather_keywords)
    
    async def _handle_natural_language_query(self, message: str, user_id: str) -> str:
        """处理自然语言天气查询"""
        try:
            self.logger.debug(f"处理自然语言查询: {message}")
            
            # 尝试提取位置信息
            location = self._extract_location_from_message(message)
            
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return localization_manager.format_prompt('ask_location')
            
            # 判断查询类型
            message_lower = message.lower()
            if any(word in message_lower for word in ['预报', '明天', '后天', '未来', 'forecast']):
                # 预报查询
                days = 5  # 默认5天
                if '明天' in message_lower:
                    days = 2
                elif '后天' in message_lower:
                    days = 3
                
                forecast_data = await self.weather_service.get_forecast(location, days, user_id)
                return self._format_forecast_response(forecast_data)
            else:
                # 当前天气查询
                weather_data = await self.weather_service.get_current_weather(location, user_id)
                return self._format_weather_response(weather_data)
                
        except Exception as e:
            self.logger.error(f"处理自然语言查询失败: {e}")
            return localization_manager.format_error('processing_error')
    
    def _extract_location_from_message(self, message: str) -> Optional[str]:
        """从消息中提取位置信息"""
        # 简单的位置提取逻辑，将在后续任务中完善
        # 匹配常见的城市名称模式
        location_patterns = [
            r'(.+?)(?:的天气|天气怎么样|天气如何)',
            r'(?:在|去|到)(.+?)(?:的天气|天气)',
            r'今天(.+?)天气',
            r'明天(.+?)天气',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message)
            if match:
                location = match.group(1).strip()
                # 过滤掉一些无意义的词
                if location and location not in ['今天', '明天', '后天', '这里', '那里']:
                    return location
        
        return None
    
    async def _handle_weather_command(self, args: List[str], user_id: str) -> str:
        """处理天气命令"""
        try:
            location = args[0] if args else None
            
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return localization_manager.format_prompt('provide_location_weather')
            
            # 获取当前天气
            weather_data = await self.weather_service.get_current_weather(location, user_id)
            return self._format_weather_response(weather_data)
            
        except Exception as e:
            self.logger.error(f"处理天气命令失败: {e}")
            return localization_manager.format_error('weather_query_failed', error=str(e))
    
    async def _handle_forecast_command(self, args: List[str], user_id: str) -> str:
        """处理预报命令"""
        try:
            location = args[0] if args else None
            
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return localization_manager.format_prompt('provide_location_forecast')
            
            # 获取天气预报
            forecast_data = await self.weather_service.get_forecast(location, 5, user_id)
            return self._format_forecast_response(forecast_data)
            
        except Exception as e:
            self.logger.error(f"处理预报命令失败: {e}")
            return localization_manager.format_error('forecast_query_failed', error=str(e))
    
    async def _handle_config_command(self, args: List[str], user_id: str) -> str:
        """处理配置命令"""
        if not args:
            return self._get_config_info()
        
        subcommand = args[0].lower()
        if subcommand in ['reload', '重载']:
            try:
                self.reload_config()
                return localization_manager.format_status('config_reloaded')
            except Exception as e:
                return localization_manager.format_status('config_reload_failed', error=str(e))
        elif subcommand in ['info', '信息']:
            return self._get_config_info()
        else:
            return localization_manager.format_message('config_commands.available')
    
    def _get_config_info(self) -> str:
        """获取配置信息"""
        provider_config = self.config.get_provider_config()
        
        return localization_manager.format_message('config_info',
            provider=provider_config.name if provider_config else self.config.api_provider,
            api_key_status=localization_manager.format_status('api_key_configured') if self.config.api_key else localization_manager.format_status('api_key_not_configured'),
            cache_status=localization_manager.format_status('cache_enabled') if self.config.cache_enabled else localization_manager.format_status('cache_disabled'),
            cache_current=self.config.cache_ttl_current,
            cache_forecast=self.config.cache_ttl_forecast,
            units=self.config.default_units,
            language=self.config.default_language,
            rate_minute=self.config.rate_limit_per_minute,
            rate_day=self.config.rate_limit_per_day
        )
    
    async def _handle_weather_command_object(self, command: WeatherCommand, user_id: str) -> str:
        """
        处理WeatherCommand对象
        
        Args:
            command: 解析出的天气命令对象
            user_id: 用户ID
            
        Returns:
            str: 命令执行结果
        """
        try:
            self.logger.debug(f"处理天气命令: {command.command_type} (用户: {user_id})")
            
            if command.command_type == CommandType.CURRENT_WEATHER:
                return await self._handle_current_weather_command(command, user_id)
            elif command.command_type == CommandType.FORECAST:
                return await self._handle_forecast_weather_command(command, user_id)
            elif command.command_type == CommandType.HOURLY_FORECAST:
                return await self._handle_hourly_forecast_command(command, user_id)
            elif command.command_type == CommandType.HELP:
                return help_system.get_help_message()
            elif command.command_type == CommandType.SET_LOCATION:
                return await self._handle_set_location_command(command, user_id)
            elif command.command_type == CommandType.SET_UNITS:
                return await self._handle_set_units_command(command, user_id)
            elif command.command_type == CommandType.ALERTS:
                return await self._handle_alerts_command(command, user_id)
            elif command.command_type == CommandType.ACTIVITIES:
                return await self._handle_activities_command(command, user_id)
            else:
                return localization_manager.format_error('unknown_command', command=str(command.command_type))
                
        except Exception as e:
            self.logger.error(f"处理天气命令时发生错误: {e}")
            return localization_manager.format_error('command_error')
    
    async def _handle_current_weather_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理当前天气命令"""
        try:
            location = command.location
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return localization_manager.format_prompt('provide_location_weather')
            
            # 获取当前天气
            weather_data = await self.weather_service.get_current_weather(location, user_id)
            
            # 格式化天气信息
            return self._format_weather_response(weather_data)
            
        except Exception as e:
            self.logger.error(f"处理当前天气命令失败: {e}")
            return localization_manager.format_error('weather_query_failed', error=str(e))
    
    async def _handle_forecast_weather_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理预报天气命令"""
        try:
            location = command.location
            days = command.additional_params.get('days', 5)  # 默认5天预报
            
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return localization_manager.format_prompt('provide_location_forecast')
            
            # 获取天气预报
            forecast_data = await self.weather_service.get_forecast(location, days, user_id)
            
            # 格式化预报信息
            return self._format_forecast_response(forecast_data)
            
        except Exception as e:
            self.logger.error(f"处理预报天气命令失败: {e}")
            return localization_manager.format_error('forecast_query_failed', error=str(e))
    
    async def _handle_hourly_forecast_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理小时预报命令"""
        try:
            location = command.location
            hours = command.additional_params.get('hours', 24)  # 默认24小时预报
            
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return "请提供要查询的位置，例如：小时预报 北京"
            
            # 获取小时预报
            hourly_data = await self.weather_service.get_hourly_forecast(location, hours, user_id)
            
            # 格式化小时预报信息
            return self._format_hourly_response(hourly_data, hours)
            
        except Exception as e:
            self.logger.error(f"处理小时预报命令失败: {e}")
            return f"获取小时预报失败: {str(e)}"
    
    async def _handle_set_location_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理设置位置命令"""
        try:
            location = command.location
            if not location:
                return "请提供要设置的位置，例如：设置位置 北京"
            
            # 验证位置是否有效
            try:
                location_info = self.location_service.parse_location(location)
                normalized_location = location_info.name
            except Exception as e:
                return f"位置 '{location}' 无效: {str(e)}"
            
            # 设置用户默认位置
            self.user_preferences.set_default_location(user_id, normalized_location)
            
            return f"已将默认位置设置为: {normalized_location}"
            
        except Exception as e:
            self.logger.error(f"处理设置位置命令失败: {e}")
            return f"设置位置失败: {str(e)}"
    
    async def _handle_set_units_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理设置单位命令"""
        try:
            units = command.additional_params.get('units')
            if not units:
                return "请指定温度单位，例如：设置单位 摄氏度 或 设置单位 华氏度"
            
            # 标准化单位
            if units in ['摄氏度', 'celsius', 'metric', 'c']:
                normalized_units = 'metric'
                unit_name = "摄氏度"
            elif units in ['华氏度', 'fahrenheit', 'imperial', 'f']:
                normalized_units = 'imperial'
                unit_name = "华氏度"
            else:
                return "不支持的单位类型，请使用 '摄氏度' 或 '华氏度'"
            
            # 设置用户单位偏好
            self.user_preferences.set_units(user_id, normalized_units)
            
            return f"已将温度单位设置为: {unit_name}"
            
        except Exception as e:
            self.logger.error(f"处理设置单位命令失败: {e}")
            return f"设置单位失败: {str(e)}"
    
    async def _handle_alerts_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理警报命令"""
        try:
            location = command.location
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return "请提供要查询警报的位置，例如：天气警报 北京"
            
            # 检查天气警报
            alerts = await self.alert_manager.check_weather_alerts(location)
            
            if not alerts:
                return f"{location} 当前没有天气警报"
            
            # 格式化警报信息
            return self._format_alerts_response(alerts, location)
            
        except Exception as e:
            self.logger.error(f"处理警报命令失败: {e}")
            return f"查询天气警报失败: {str(e)}"
    
    async def _handle_activities_command(self, command: WeatherCommand, user_id: str) -> str:
        """处理活动推荐命令"""
        try:
            location = command.location
            if not location:
                # 尝试从用户偏好获取默认位置
                user_prefs = self.user_preferences.get_user_preferences(user_id)
                if user_prefs.default_location:
                    location = user_prefs.default_location
                else:
                    return "请提供位置以获取活动推荐，例如：活动推荐 上海"
            
            # 获取当前天气
            weather_data = await self.weather_service.get_current_weather(location, user_id)
            
            # 获取当前季节
            current_season = self.activity_recommender.get_current_season()
            
            # 获取活动推荐
            activities = self.activity_recommender.recommend_activities(weather_data, current_season)
            
            # 获取安全建议
            safety_recommendations = self.activity_recommender.get_safety_recommendations(weather_data)
            
            # 格式化活动推荐信息
            return self._format_activities_response(activities, safety_recommendations, location, weather_data)
            
        except Exception as e:
            self.logger.error(f"处理活动推荐命令失败: {e}")
            return f"获取活动推荐失败: {str(e)}"
    
    def _get_help_message(self) -> str:
        """获取帮助信息（向后兼容方法）"""
        return help_system.get_help_message()


    def _format_weather_response(self, weather_data) -> str:
        """格式化天气响应"""
        try:
            temp_unit = "°C" if weather_data.units == "metric" else "°F"
            wind_unit = "km/h" if weather_data.units == "metric" else "mph"
            
            response = f"📍 {weather_data.location}\n"
            response += f"🌡️ 温度: {weather_data.temperature:.1f}{temp_unit} (体感 {weather_data.feels_like:.1f}{temp_unit})\n"
            response += f"☁️ 天气: {weather_data.condition}\n"
            response += f"💧 湿度: {weather_data.humidity}%\n"
            response += f"💨 风速: {weather_data.wind_speed:.1f} {wind_unit}\n"
            response += f"🔍 能见度: {weather_data.visibility:.1f} km\n"
            
            if weather_data.uv_index > 0:
                response += f"☀️ 紫外线指数: {weather_data.uv_index:.1f}\n"
            
            response += f"📊 气压: {weather_data.pressure:.1f} hPa"
            
            return response
            
        except Exception as e:
            self.logger.error(f"格式化天气响应失败: {e}")
            return f"天气数据格式化失败: {str(e)}"
    
    def _format_forecast_response(self, forecast_data) -> str:
        """格式化预报响应"""
        try:
            temp_unit = "°C" if forecast_data.units == "metric" else "°F"
            
            response = f"📍 {forecast_data.location} - {len(forecast_data.days)}天预报\n\n"
            
            for day in forecast_data.days:
                date_str = day.date.strftime("%m月%d日")
                weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.date.weekday()]
                
                response += f"📅 {date_str} ({weekday})\n"
                response += f"🌡️ {day.low_temp:.1f}{temp_unit} ~ {day.high_temp:.1f}{temp_unit}\n"
                response += f"☁️ {day.condition}\n"
                
                if day.precipitation_chance > 0:
                    response += f"🌧️ 降水概率: {day.precipitation_chance}%\n"
                
                response += f"💧 湿度: {day.humidity}%\n\n"
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"格式化预报响应失败: {e}")
            return f"预报数据格式化失败: {str(e)}"
    
    def _format_hourly_response(self, hourly_data, hours: int) -> str:
        """格式化小时预报响应"""
        try:
            temp_unit = "°C" if hourly_data.units == "metric" else "°F"
            
            response = f"📍 {hourly_data.location} - {min(len(hourly_data.hours), hours)}小时预报\n\n"
            
            for i, hour in enumerate(hourly_data.hours[:hours]):
                from datetime import datetime
                dt = datetime.fromisoformat(hour['datetime'])
                time_str = dt.strftime("%H:%M")
                
                response += f"🕐 {time_str}: {hour['temperature']:.1f}{temp_unit} - {hour['condition']}"
                
                if hour['precipitation_chance'] > 0:
                    response += f" (降水 {hour['precipitation_chance']}%)"
                
                response += "\n"
                
                # 每6小时添加一个分隔符
                if (i + 1) % 6 == 0 and i < len(hourly_data.hours) - 1:
                    response += "\n"
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"格式化小时预报响应失败: {e}")
            return f"小时预报数据格式化失败: {str(e)}"
    
    def _format_alerts_response(self, alerts, location: str) -> str:
        """格式化警报响应"""
        try:
            response = f"⚠️ {location} 天气警报 ({len(alerts)}条)\n\n"
            
            for alert in alerts:
                severity_emoji = {
                    'low': '🟡',
                    'medium': '🟠', 
                    'high': '🔴'
                }.get(alert.severity.lower(), '⚠️')
                
                response += f"{severity_emoji} {alert.title}\n"
                response += f"📝 {alert.description}\n"
                
                if alert.advice:
                    response += f"💡 建议: {', '.join(alert.advice)}\n"
                
                response += "\n"
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"格式化警报响应失败: {e}")
            return f"警报信息格式化失败: {str(e)}"
    
    def _format_activities_response(self, activities, safety_recommendations, location: str, weather_data) -> str:
        """格式化活动推荐响应"""
        try:
            temp_unit = "°C" if weather_data.units == "metric" else "°F"
            
            response = f"🎯 {location} 活动推荐\n"
            response += f"🌡️ 当前: {weather_data.temperature:.1f}{temp_unit} - {weather_data.condition}\n\n"
            
            if activities:
                response += "🎪 推荐活动:\n"
                for i, activity in enumerate(activities[:5], 1):  # 显示前5个推荐
                    indoor_emoji = "🏠" if activity.indoor else "🌳"
                    response += f"{i}. {indoor_emoji} {activity.name} - {activity.description}\n"
                
                response += "\n"
            
            if safety_recommendations:
                response += "⚠️ 安全提醒:\n"
                for recommendation in safety_recommendations[:3]:  # 显示前3个建议
                    response += f"• {recommendation}\n"
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"格式化活动推荐响应失败: {e}")
            return f"活动推荐格式化失败: {str(e)}"
    
    def close(self):
        """关闭插件，清理资源"""
        try:
            # 关闭缓存管理器
            if hasattr(self, 'cache_manager'):
                self.cache_manager.close()
            
            # 关闭API客户端
            if hasattr(self, 'api_client'):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，创建任务
                        loop.create_task(self.api_client.close())
                    else:
                        # 如果事件循环未运行，直接运行
                        loop.run_until_complete(self.api_client.close())
                except Exception as e:
                    self.logger.debug(f"关闭API客户端时出错: {e}")
            
            self.logger.info("天气插件已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭插件时发生错误: {e}")
    
    def __del__(self):
        """析构函数"""
        try:
            self.close()
        except:
            pass


# AstrBot 插件入口点
def create_plugin(config: Dict[str, Any]) -> WeatherPlugin:
    """创建插件实例"""
    return WeatherPlugin(config)