"""
核心天气服务实现

集成缓存管理器和API客户端，提供统一的天气数据获取接口。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from .interfaces import IWeatherService, IWeatherAPIClient, ICacheManager, ILocationService, IUserPreferences
from .models import (
    WeatherData, ForecastData, HourlyForecastData, ForecastDay, 
    APIError, LocationError, CacheError, WeatherError
)
from .config import WeatherConfig


class CircuitBreakerState(Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 断开状态（停止调用）
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


class CircuitBreaker:
    """断路器模式实现"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """
        初始化断路器
        
        Args:
            failure_threshold: 失败阈值
            recovery_timeout: 恢复超时时间（秒）
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        """
        通过断路器调用函数
        
        Args:
            func: 要调用的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数调用结果
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise APIError("服务暂时不可用（断路器开启）")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置断路器"""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self):
        """成功调用时的处理"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """失败调用时的处理"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class WeatherService(IWeatherService):
    """核心天气服务实现"""
    
    def __init__(
        self,
        config: WeatherConfig,
        api_client: IWeatherAPIClient,
        cache_manager: ICacheManager,
        location_service: ILocationService,
        user_preferences: IUserPreferences
    ):
        """
        初始化天气服务
        
        Args:
            config: 天气配置
            api_client: API客户端
            cache_manager: 缓存管理器
            location_service: 位置服务
            user_preferences: 用户偏好管理
        """
        self.config = config
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.location_service = location_service
        self.user_preferences = user_preferences
        self.logger = logging.getLogger(__name__)
        
        # 初始化断路器
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.api_failure_threshold if hasattr(config, 'api_failure_threshold') else 5,
            recovery_timeout=config.api_recovery_timeout if hasattr(config, 'api_recovery_timeout') else 60
        )
    
    async def get_current_weather(self, location: str, user_id: str) -> WeatherData:
        """
        获取当前天气
        
        Args:
            location: 位置名称
            user_id: 用户ID
            
        Returns:
            WeatherData: 当前天气数据
            
        Raises:
            LocationError: 位置解析失败
            APIError: API调用失败
            WeatherError: 其他天气服务错误
        """
        try:
            # 解析和验证位置
            location_info = self.location_service.parse_location(location)
            normalized_location = location_info.name
            
            # 获取用户偏好
            user_prefs = self.user_preferences.get_user_preferences(user_id)
            units = user_prefs.units
            
            # 生成缓存键
            cache_key = self.cache_manager.generate_cache_key(
                normalized_location, 
                'weather',
                units=units
            )
            
            # 尝试从缓存获取
            cached_data = await self.cache_manager.get_cached_weather(cache_key)
            if cached_data:
                self.logger.debug(f"从缓存获取天气数据: {normalized_location}")
                return cached_data
            
            # 从API获取数据
            self.logger.debug(f"从API获取天气数据: {normalized_location}")
            
            # 使用断路器和重试机制获取数据
            async def api_call():
                return await self.circuit_breaker.call(
                    self.api_client.fetch_current_weather, 
                    normalized_location
                )
            
            raw_data = await self._handle_api_error_with_retry(api_call)
            
            # 转换为标准格式
            weather_data = self._convert_current_weather_data(raw_data, normalized_location, units)
            
            # 验证和清理数据
            if not self._validate_weather_data(weather_data):
                weather_data = self._sanitize_weather_data(weather_data)
                self.logger.warning(f"天气数据已清理: {normalized_location}")
            
            # 缓存数据
            await self.cache_manager.cache_weather_data(
                cache_key, 
                weather_data, 
                self.config.cache_ttl_current
            )
            
            return weather_data
            
        except LocationError:
            # 尝试位置拼写纠正
            suggestions = self.location_service.suggest_corrections(location)
            if suggestions:
                raise LocationError(f"位置 '{location}' 未找到，您是否想查询: {', '.join(suggestions[:3])}")
            else:
                raise LocationError(f"无法解析位置: {location}")
        
        except APIError as e:
            # API错误，尝试从缓存获取过期数据作为降级
            self.logger.warning(f"API调用失败，尝试降级策略: {e}")
            try:
                fallback_data = await self._fallback_to_stale_cache(location, user_id, 'weather')
                if fallback_data:
                    return fallback_data
            except Exception as fallback_error:
                self.logger.error(f"降级策略也失败: {fallback_error}")
            
            # 根据错误类型提供友好的错误消息
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise APIError(self._get_friendly_error_message("rate_limit"))
            elif "not found" in error_msg or "404" in error_msg:
                raise LocationError(self._get_friendly_error_message("location_not_found", location))
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                raise APIError(self._get_friendly_error_message("network_error"))
            elif "unauthorized" in error_msg or "401" in error_msg:
                raise APIError(self._get_friendly_error_message("auth_error"))
            elif "forbidden" in error_msg or "403" in error_msg:
                raise APIError(self._get_friendly_error_message("invalid_api_key"))
            elif "quota" in error_msg or "limit exceeded" in error_msg:
                raise APIError(self._get_friendly_error_message("quota_exceeded"))
            elif "maintenance" in error_msg or "503" in error_msg:
                raise APIError(self._get_friendly_error_message("maintenance"))
            elif "500" in error_msg or "internal server" in error_msg:
                raise APIError(self._get_friendly_error_message("server_error", location))
            else:
                raise APIError(self._get_friendly_error_message("api_unavailable", location))
        
        except Exception as e:
            self.logger.error(f"获取当前天气失败: {e}")
            raise WeatherError(f"获取天气数据时发生错误: {e}")
    
    async def get_forecast(self, location: str, days: int, user_id: str) -> ForecastData:
        """
        获取天气预报
        
        Args:
            location: 位置名称
            days: 预报天数
            user_id: 用户ID
            
        Returns:
            ForecastData: 预报数据
            
        Raises:
            LocationError: 位置解析失败
            APIError: API调用失败
            WeatherError: 其他天气服务错误
        """
        try:
            # 验证天数范围
            if days <= 0 or days > 16:
                raise ValueError("预报天数必须在 1-16 之间")
            
            # 解析和验证位置
            location_info = self.location_service.parse_location(location)
            normalized_location = location_info.name
            
            # 获取用户偏好
            user_prefs = self.user_preferences.get_user_preferences(user_id)
            units = user_prefs.units
            
            # 生成缓存键
            cache_key = self.cache_manager.generate_cache_key(
                normalized_location,
                'forecast',
                days=days,
                units=units
            )
            
            # 尝试从缓存获取
            cached_data = await self.cache_manager.get_cached_forecast(cache_key)
            if cached_data:
                self.logger.debug(f"从缓存获取预报数据: {normalized_location}, {days}天")
                return cached_data
            
            # 从API获取数据
            self.logger.debug(f"从API获取预报数据: {normalized_location}, {days}天")
            
            # 使用断路器和重试机制获取数据
            async def api_call():
                return await self.circuit_breaker.call(
                    self.api_client.fetch_forecast, 
                    normalized_location, 
                    days
                )
            
            raw_data = await self._handle_api_error_with_retry(api_call)
            
            # 转换为标准格式
            forecast_data = self._convert_forecast_data(raw_data, normalized_location, days, units)
            
            # 缓存数据
            await self.cache_manager.cache_forecast_data(
                cache_key,
                forecast_data,
                self.config.cache_ttl_forecast
            )
            
            return forecast_data
            
        except LocationError:
            # 尝试位置拼写纠正
            suggestions = self.location_service.suggest_corrections(location)
            if suggestions:
                raise LocationError(f"位置 '{location}' 未找到，您是否想查询: {', '.join(suggestions[:3])}")
            else:
                raise LocationError(f"无法解析位置: {location}")
        
        except APIError as e:
            # API错误，尝试从缓存获取过期数据作为降级
            self.logger.warning(f"API调用失败，尝试降级策略: {e}")
            try:
                fallback_data = await self._fallback_to_stale_cache(location, user_id, 'forecast', days=days)
                if fallback_data:
                    return fallback_data
            except Exception as fallback_error:
                self.logger.error(f"降级策略也失败: {fallback_error}")
            
            # 根据错误类型提供友好的错误消息
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise APIError(self._get_friendly_error_message("rate_limit"))
            elif "not found" in error_msg or "404" in error_msg:
                raise LocationError(self._get_friendly_error_message("location_not_found", location))
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                raise APIError(self._get_friendly_error_message("network_error"))
            elif "unauthorized" in error_msg or "401" in error_msg:
                raise APIError(self._get_friendly_error_message("auth_error"))
            elif "forbidden" in error_msg or "403" in error_msg:
                raise APIError(self._get_friendly_error_message("invalid_api_key"))
            elif "quota" in error_msg or "limit exceeded" in error_msg:
                raise APIError(self._get_friendly_error_message("quota_exceeded"))
            elif "maintenance" in error_msg or "503" in error_msg:
                raise APIError(self._get_friendly_error_message("maintenance"))
            elif "500" in error_msg or "internal server" in error_msg:
                raise APIError(self._get_friendly_error_message("server_error", location))
            else:
                raise APIError(self._get_friendly_error_message("api_unavailable", location))
        
        except Exception as e:
            self.logger.error(f"获取预报数据失败: {e}")
            raise WeatherError(f"获取预报数据时发生错误: {e}")
    
    async def get_hourly_forecast(self, location: str, hours: int, user_id: str) -> HourlyForecastData:
        """
        获取小时预报
        
        Args:
            location: 位置名称
            hours: 预报小时数
            user_id: 用户ID
            
        Returns:
            HourlyForecastData: 小时预报数据
            
        Raises:
            LocationError: 位置解析失败
            APIError: API调用失败
            WeatherError: 其他天气服务错误
        """
        try:
            # 验证小时数范围
            if hours <= 0 or hours > 48:
                raise ValueError("小时预报时长必须在 1-48 小时之间")
            
            # 解析和验证位置
            location_info = self.location_service.parse_location(location)
            normalized_location = location_info.name
            
            # 获取用户偏好
            user_prefs = self.user_preferences.get_user_preferences(user_id)
            units = user_prefs.units
            
            # 生成缓存键
            cache_key = self.cache_manager.generate_cache_key(
                normalized_location,
                'hourly',
                hours=hours,
                units=units
            )
            
            # 尝试从缓存获取（小时预报使用通用缓存方法）
            # 注意：这里需要扩展缓存管理器以支持小时预报，暂时使用预报缓存
            
            # 从API获取数据
            self.logger.debug(f"从API获取小时预报数据: {normalized_location}, {hours}小时")
            
            # 使用断路器和重试机制获取数据
            async def api_call():
                return await self.circuit_breaker.call(
                    self.api_client.fetch_hourly_forecast, 
                    normalized_location, 
                    hours
                )
            
            raw_data = await self._handle_api_error_with_retry(api_call)
            
            # 转换为标准格式
            hourly_data = self._convert_hourly_forecast_data(raw_data, normalized_location, hours, units)
            
            return hourly_data
            
        except LocationError:
            # 尝试位置拼写纠正
            suggestions = self.location_service.suggest_corrections(location)
            if suggestions:
                raise LocationError(f"位置 '{location}' 未找到，您是否想查询: {', '.join(suggestions[:3])}")
            else:
                raise LocationError(f"无法解析位置: {location}")
        
        except APIError as e:
            # API错误处理
            self.logger.warning(f"获取小时预报失败: {e}")
            
            # 根据错误类型提供友好的错误消息
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise APIError(self._get_friendly_error_message("rate_limit"))
            elif "not found" in error_msg or "404" in error_msg:
                raise LocationError(self._get_friendly_error_message("location_not_found", location))
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                raise APIError(self._get_friendly_error_message("network_error"))
            elif "unauthorized" in error_msg or "401" in error_msg:
                raise APIError(self._get_friendly_error_message("auth_error"))
            elif "forbidden" in error_msg or "403" in error_msg:
                raise APIError(self._get_friendly_error_message("invalid_api_key"))
            elif "quota" in error_msg or "limit exceeded" in error_msg:
                raise APIError(self._get_friendly_error_message("quota_exceeded"))
            elif "maintenance" in error_msg or "503" in error_msg:
                raise APIError(self._get_friendly_error_message("maintenance"))
            elif "500" in error_msg or "internal server" in error_msg:
                raise APIError(self._get_friendly_error_message("server_error", location))
            else:
                raise APIError(self._get_friendly_error_message("api_unavailable", location))
        
        except Exception as e:
            self.logger.error(f"获取小时预报失败: {e}")
            raise WeatherError(f"获取小时预报数据时发生错误: {e}")
    
    async def _fallback_to_stale_cache(
        self, 
        location: str, 
        user_id: str, 
        data_type: str, 
        **kwargs
    ) -> Optional[WeatherData]:
        """
        降级策略：尝试获取过期的缓存数据
        
        Args:
            location: 位置
            user_id: 用户ID
            data_type: 数据类型
            **kwargs: 额外参数
            
        Returns:
            过期的缓存数据或None
        """
        try:
            # 获取用户偏好
            user_prefs = self.user_preferences.get_user_preferences(user_id)
            units = user_prefs.units
            
            # 解析位置信息
            location_info = self.location_service.parse_location(location)
            normalized_location = location_info.name
            
            # 生成缓存键
            cache_key = self.cache_manager.generate_cache_key(
                normalized_location,
                data_type,
                units=units,
                **kwargs
            )
            
            # 尝试获取过期的缓存数据
            stale_data = await self._get_stale_cache_data(cache_key, data_type)
            if stale_data:
                self.logger.info(f"使用过期缓存数据作为降级: {normalized_location}")
                # 为过期数据添加警告标记
                if hasattr(stale_data, 'condition'):
                    stale_data.condition = f"[缓存数据] {stale_data.condition}"
                return stale_data
            
            # 尝试获取相似位置的缓存数据
            similar_data = await self._get_similar_location_cache(normalized_location, data_type, units, **kwargs)
            if similar_data:
                self.logger.info(f"使用相似位置缓存数据作为降级: {normalized_location}")
                if hasattr(similar_data, 'condition'):
                    similar_data.condition = f"[相似位置] {similar_data.condition}"
                return similar_data
            
            # 如果没有缓存数据，返回None让调用者处理
            self.logger.warning(f"无法获取降级数据，没有可用的缓存: {normalized_location}")
            return None
            
        except Exception as e:
            self.logger.error(f"降级策略失败: {e}")
            return None
    
    async def _get_stale_cache_data(self, cache_key: str, data_type: str) -> Optional[WeatherData]:
        """
        获取过期的缓存数据（忽略TTL）
        
        Args:
            cache_key: 缓存键
            data_type: 数据类型
            
        Returns:
            过期的缓存数据或None
        """
        try:
            # 这里需要直接访问数据库，绕过TTL检查
            # 由于当前缓存管理器不支持此功能，我们实现一个简单版本
            import sqlite3
            import json
            from datetime import datetime
            
            try:
                with sqlite3.connect(self.config.cache_db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("""
                        SELECT data_json FROM weather_cache 
                        WHERE cache_key = ? AND data_type = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (cache_key, data_type))
                    
                    row = cursor.fetchone()
                    if row:
                        data_dict = json.loads(row['data_json'])
                        if data_type == 'weather':
                            return WeatherData.from_dict(data_dict)
                        elif data_type == 'forecast':
                            return ForecastData.from_dict(data_dict)
                        
            except Exception as db_error:
                self.logger.debug(f"无法访问过期缓存: {db_error}")
                
            return None
            
        except Exception as e:
            self.logger.debug(f"获取过期缓存数据失败: {e}")
            return None
    
    async def _get_similar_location_cache(
        self, 
        location: str, 
        data_type: str, 
        units: str, 
        **kwargs
    ) -> Optional[WeatherData]:
        """
        获取相似位置的缓存数据作为降级策略
        
        Args:
            location: 目标位置
            data_type: 数据类型
            units: 单位系统
            **kwargs: 额外参数
            
        Returns:
            相似位置的缓存数据或None
        """
        try:
            import sqlite3
            import json
            from datetime import datetime, timedelta
            
            # 定义相似位置的搜索模式
            similar_patterns = [
                f"%{location}%",  # 包含目标位置名称
                f"{location[:2]}%",  # 相同前缀
            ]
            
            # 只查找最近24小时内的数据
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            try:
                with sqlite3.connect(self.config.cache_db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    
                    for pattern in similar_patterns:
                        cursor = conn.execute("""
                            SELECT data_json, cache_key FROM weather_cache 
                            WHERE cache_key LIKE ? AND data_type = ? 
                            AND created_at > ?
                            ORDER BY created_at DESC LIMIT 1
                        """, (pattern, data_type, cutoff_time.isoformat()))
                        
                        row = cursor.fetchone()
                        if row:
                            data_dict = json.loads(row['data_json'])
                            if data_type == 'weather':
                                data = WeatherData.from_dict(data_dict)
                                # 更新位置信息为目标位置
                                data.location = location
                                return data
                            elif data_type == 'forecast':
                                data = ForecastData.from_dict(data_dict)
                                data.location = location
                                return data
                        
            except Exception as db_error:
                self.logger.debug(f"无法访问相似位置缓存: {db_error}")
                
            return None
            
        except Exception as e:
            self.logger.debug(f"获取相似位置缓存数据失败: {e}")
            return None
    
    def _create_fallback_weather_data(self, location: str, units: str = "metric") -> WeatherData:
        """
        创建降级天气数据（当所有其他策略都失败时）
        
        Args:
            location: 位置名称
            units: 单位系统
            
        Returns:
            基础的天气数据
        """
        return WeatherData(
            location=location,
            temperature=20.0,  # 默认温度
            feels_like=20.0,
            humidity=50,  # 默认湿度
            wind_speed=0.0,
            wind_direction=0,
            pressure=1013.0,  # 标准大气压
            visibility=10.0,
            uv_index=0.0,
            condition="[服务不可用] 无法获取实时天气数据",
            condition_code="unknown",
            timestamp=datetime.now(),
            units=units
        )
    
    def _create_fallback_forecast_data(self, location: str, days: int, units: str = "metric") -> ForecastData:
        """
        创建降级预报数据（当所有其他策略都失败时）
        
        Args:
            location: 位置名称
            days: 预报天数
            units: 单位系统
            
        Returns:
            基础的预报数据
        """
        forecast_days = []
        base_date = datetime.now().date()
        
        for i in range(days):
            forecast_day = ForecastDay(
                date=base_date + timedelta(days=i),
                high_temp=25.0,  # 默认高温
                low_temp=15.0,   # 默认低温
                condition="[服务不可用] 无法获取预报数据",
                precipitation_chance=0,
                wind_speed=0.0,
                humidity=50
            )
            forecast_days.append(forecast_day)
        
        return ForecastData(
            location=location,
            days=forecast_days,
            units=units,
            generated_at=datetime.now()
        )
    
    def _get_friendly_error_message(self, error_type: str, location: str = "") -> str:
        """
        获取友好的错误消息
        
        Args:
            error_type: 错误类型
            location: 位置（可选）
            
        Returns:
            友好的错误消息
        """
        error_messages = {
            "api_unavailable": f"抱歉，天气服务暂时不可用。请稍后重试查询 {location} 的天气。我们正在努力恢复服务。",
            "location_not_found": f"未找到位置 '{location}'，请检查拼写或尝试使用更具体的地名（如：北京市、上海市浦东新区）。",
            "rate_limit": "请求过于频繁，请稍后再试。为了保证服务质量，我们限制了查询频率。",
            "network_error": "网络连接出现问题，请检查网络连接后重试。如果问题持续存在，请联系管理员。",
            "service_error": f"天气服务出现错误，无法获取 {location} 的天气信息。请稍后重试或联系技术支持。",
            "invalid_location": f"位置 '{location}' 无效，请提供有效的城市名称或坐标（如：北京、上海、40.7128,-74.0060）。",
            "data_error": "天气数据格式错误，我们已记录此问题并正在修复。请稍后重试。",
            "timeout_error": f"获取 {location} 天气信息超时，请检查网络连接或稍后重试。",
            "auth_error": "API认证失败，请检查配置或联系管理员。",
            "quota_exceeded": "今日查询次数已达上限，请明天再试或升级服务计划。",
            "maintenance": "天气服务正在维护中，预计很快恢复。感谢您的耐心等待。",
            "invalid_api_key": "API密钥无效或已过期，请联系管理员更新配置。",
            "server_error": f"天气服务器出现内部错误，无法处理 {location} 的请求。我们已收到错误报告。"
        }
        
        return error_messages.get(error_type, f"获取 {location} 天气信息时发生未知错误，请稍后重试。如问题持续，请联系技术支持。")
    
    async def _handle_api_error_with_retry(
        self, 
        api_call, 
        max_retries: int = 2, 
        retry_delay: float = 1.0
    ):
        """
        带重试机制的API调用处理
        
        Args:
            api_call: API调用函数
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            
        Returns:
            API调用结果
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await api_call()
            except APIError as e:
                last_error = e
                error_msg = str(e).lower()
                
                # 对于某些错误类型不进行重试
                non_retryable_errors = [
                    'invalid', '404', 'not found', 'unauthorized', '401',
                    'forbidden', '403', 'bad request', '400', 'quota',
                    'limit exceeded', 'api key'
                ]
                
                if any(keyword in error_msg for keyword in non_retryable_errors):
                    self.logger.info(f"不可重试的错误，直接抛出: {e}")
                    raise e
                
                if attempt < max_retries:
                    # 根据错误类型调整重试延迟
                    if "rate limit" in error_msg or "429" in error_msg:
                        # 速率限制错误，使用更长的延迟
                        actual_delay = retry_delay * 3
                    elif "timeout" in error_msg or "network" in error_msg:
                        # 网络错误，使用标准延迟
                        actual_delay = retry_delay
                    elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
                        # 服务器错误，使用较长延迟
                        actual_delay = retry_delay * 2
                    else:
                        actual_delay = retry_delay
                    
                    self.logger.warning(f"API调用失败，{actual_delay}秒后重试 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(actual_delay)
                    retry_delay *= 1.5  # 指数退避
                else:
                    self.logger.error(f"API调用最终失败，已重试 {max_retries} 次: {e}")
        
        raise last_error or APIError("API调用失败")
    
    def _validate_weather_data(self, data: WeatherData) -> bool:
        """
        验证天气数据的合理性
        
        Args:
            data: 天气数据
            
        Returns:
            数据是否有效
        """
        try:
            # 检查温度范围（-100°C 到 60°C）
            if not (-100 <= data.temperature <= 60):
                self.logger.warning(f"温度数据异常: {data.temperature}°C")
                return False
            
            # 检查湿度范围
            if not (0 <= data.humidity <= 100):
                self.logger.warning(f"湿度数据异常: {data.humidity}%")
                return False
            
            # 检查风速（不能为负数，且不应超过500 km/h）
            if data.wind_speed < 0 or data.wind_speed > 500:
                self.logger.warning(f"风速数据异常: {data.wind_speed}")
                return False
            
            # 检查气压范围（通常在800-1100 hPa之间）
            if not (800 <= data.pressure <= 1100):
                self.logger.warning(f"气压数据异常: {data.pressure} hPa")
                return False
            
            # 检查必要字段
            if not data.location or not data.condition:
                self.logger.warning("缺少必要的天气数据字段")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证天气数据时出错: {e}")
            return False
    
    def _sanitize_weather_data(self, data: WeatherData) -> WeatherData:
        """
        清理和修正天气数据
        
        Args:
            data: 原始天气数据
            
        Returns:
            清理后的天气数据
        """
        try:
            # 修正异常值
            if data.temperature < -100:
                data.temperature = -100
            elif data.temperature > 60:
                data.temperature = 60
            
            if data.humidity < 0:
                data.humidity = 0
            elif data.humidity > 100:
                data.humidity = 100
            
            if data.wind_speed < 0:
                data.wind_speed = 0
            elif data.wind_speed > 500:
                data.wind_speed = 500
            
            if data.pressure < 800:
                data.pressure = 800
            elif data.pressure > 1100:
                data.pressure = 1100
            
            # 确保风向在0-360度范围内
            data.wind_direction = data.wind_direction % 360
            
            # 清理文本字段
            if data.location:
                data.location = data.location.strip()
            if data.condition:
                data.condition = data.condition.strip()
            
            return data
            
        except Exception as e:
            self.logger.error(f"清理天气数据时出错: {e}")
            return data
    
    def _convert_current_weather_data(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        units: str
    ) -> WeatherData:
        """
        转换API原始数据为标准天气数据格式
        
        Args:
            raw_data: API原始数据
            location: 位置名称
            units: 单位系统
            
        Returns:
            WeatherData: 标准化的天气数据
        """
        try:
            if self.config.api_provider == "openweathermap":
                return self._convert_openweathermap_current(raw_data, location, units)
            elif self.config.api_provider == "weatherapi":
                return self._convert_weatherapi_current(raw_data, location, units)
            else:
                raise WeatherError(f"不支持的API提供商: {self.config.api_provider}")
                
        except KeyError as e:
            raise WeatherError(f"API数据格式错误，缺少字段: {e}")
        except Exception as e:
            raise WeatherError(f"数据转换失败: {e}")
    
    def _convert_openweathermap_current(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        units: str
    ) -> WeatherData:
        """转换OpenWeatherMap当前天气数据"""
        main = raw_data['main']
        weather = raw_data['weather'][0]
        wind = raw_data.get('wind', {})
        
        return WeatherData(
            location=location,
            temperature=float(main['temp']),
            feels_like=float(main['feels_like']),
            humidity=int(main['humidity']),
            wind_speed=float(wind.get('speed', 0)),
            wind_direction=int(wind.get('deg', 0)),
            pressure=float(main['pressure']),
            visibility=float(raw_data.get('visibility', 10000)) / 1000,  # 转换为公里
            uv_index=0.0,  # OpenWeatherMap基础版不提供UV指数
            condition=weather['description'],
            condition_code=weather['icon'],
            timestamp=datetime.now(),
            units=units
        )
    
    def _convert_weatherapi_current(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        units: str
    ) -> WeatherData:
        """转换WeatherAPI当前天气数据"""
        current = raw_data['current']
        condition = current['condition']
        
        return WeatherData(
            location=location,
            temperature=float(current['temp_c'] if units == 'metric' else current['temp_f']),
            feels_like=float(current['feelslike_c'] if units == 'metric' else current['feelslike_f']),
            humidity=int(current['humidity']),
            wind_speed=float(current['wind_kph'] if units == 'metric' else current['wind_mph']),
            wind_direction=int(current['wind_degree']),
            pressure=float(current['pressure_mb']),
            visibility=float(current['vis_km'] if units == 'metric' else current['vis_miles']),
            uv_index=float(current.get('uv', 0)),
            condition=condition['text'],
            condition_code=condition['icon'],
            timestamp=datetime.now(),
            units=units
        )
    
    def _convert_forecast_data(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        days: int, 
        units: str
    ) -> ForecastData:
        """
        转换API原始预报数据为标准预报数据格式
        
        Args:
            raw_data: API原始数据
            location: 位置名称
            days: 预报天数
            units: 单位系统
            
        Returns:
            ForecastData: 标准化的预报数据
        """
        try:
            if self.config.api_provider == "openweathermap":
                return self._convert_openweathermap_forecast(raw_data, location, days, units)
            elif self.config.api_provider == "weatherapi":
                return self._convert_weatherapi_forecast(raw_data, location, days, units)
            else:
                raise WeatherError(f"不支持的API提供商: {self.config.api_provider}")
                
        except KeyError as e:
            raise WeatherError(f"预报数据格式错误，缺少字段: {e}")
        except Exception as e:
            raise WeatherError(f"预报数据转换失败: {e}")
    
    def _convert_openweathermap_forecast(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        days: int, 
        units: str
    ) -> ForecastData:
        """转换OpenWeatherMap预报数据"""
        forecast_list = raw_data['list']
        
        # 按日期分组数据
        daily_data = {}
        for item in forecast_list:
            dt = datetime.fromtimestamp(item['dt'])
            date_key = dt.date()
            
            if date_key not in daily_data:
                daily_data[date_key] = []
            daily_data[date_key].append(item)
        
        # 转换为每日预报
        forecast_days = []
        for date_key in sorted(daily_data.keys())[:days]:
            day_items = daily_data[date_key]
            
            # 计算每日统计
            temps = [item['main']['temp'] for item in day_items]
            humidities = [item['main']['humidity'] for item in day_items]
            wind_speeds = [item.get('wind', {}).get('speed', 0) for item in day_items]
            
            # 获取主要天气条件（出现最多的）
            conditions = [item['weather'][0]['description'] for item in day_items]
            main_condition = max(set(conditions), key=conditions.count)
            
            # 计算降水概率（平均值）
            pops = [item.get('pop', 0) * 100 for item in day_items]
            avg_pop = sum(pops) / len(pops) if pops else 0
            
            forecast_day = ForecastDay(
                date=date_key,
                high_temp=max(temps),
                low_temp=min(temps),
                condition=main_condition,
                precipitation_chance=int(avg_pop),
                wind_speed=sum(wind_speeds) / len(wind_speeds),
                humidity=int(sum(humidities) / len(humidities))
            )
            
            forecast_days.append(forecast_day)
        
        return ForecastData(
            location=location,
            days=forecast_days,
            units=units,
            generated_at=datetime.now()
        )
    
    def _convert_weatherapi_forecast(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        days: int, 
        units: str
    ) -> ForecastData:
        """转换WeatherAPI预报数据"""
        forecast_days = []
        
        for day_data in raw_data['forecast']['forecastday'][:days]:
            day = day_data['day']
            date_str = day_data['date']
            
            forecast_day = ForecastDay(
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                high_temp=float(day['maxtemp_c'] if units == 'metric' else day['maxtemp_f']),
                low_temp=float(day['mintemp_c'] if units == 'metric' else day['mintemp_f']),
                condition=day['condition']['text'],
                precipitation_chance=int(day.get('daily_chance_of_rain', 0)),
                wind_speed=float(day['maxwind_kph'] if units == 'metric' else day['maxwind_mph']),
                humidity=int(day['avghumidity'])
            )
            
            forecast_days.append(forecast_day)
        
        return ForecastData(
            location=location,
            days=forecast_days,
            units=units,
            generated_at=datetime.now()
        )
    
    def _convert_hourly_forecast_data(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        hours: int, 
        units: str
    ) -> HourlyForecastData:
        """
        转换API原始小时预报数据为标准格式
        
        Args:
            raw_data: API原始数据
            location: 位置名称
            hours: 预报小时数
            units: 单位系统
            
        Returns:
            HourlyForecastData: 标准化的小时预报数据
        """
        try:
            if self.config.api_provider == "openweathermap":
                return self._convert_openweathermap_hourly(raw_data, location, hours, units)
            elif self.config.api_provider == "weatherapi":
                return self._convert_weatherapi_hourly(raw_data, location, hours, units)
            else:
                raise WeatherError(f"不支持的API提供商: {self.config.api_provider}")
                
        except KeyError as e:
            raise WeatherError(f"小时预报数据格式错误，缺少字段: {e}")
        except Exception as e:
            raise WeatherError(f"小时预报数据转换失败: {e}")
    
    def _convert_openweathermap_hourly(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        hours: int, 
        units: str
    ) -> HourlyForecastData:
        """转换OpenWeatherMap小时预报数据"""
        hourly_data = []
        
        for item in raw_data['list'][:hours]:
            dt = datetime.fromtimestamp(item['dt'])
            main = item['main']
            weather = item['weather'][0]
            wind = item.get('wind', {})
            
            hour_data = {
                'datetime': dt.isoformat(),
                'temperature': float(main['temp']),
                'feels_like': float(main['feels_like']),
                'humidity': int(main['humidity']),
                'wind_speed': float(wind.get('speed', 0)),
                'wind_direction': int(wind.get('deg', 0)),
                'pressure': float(main['pressure']),
                'condition': weather['description'],
                'condition_code': weather['icon'],
                'precipitation_chance': int(item.get('pop', 0) * 100)
            }
            
            hourly_data.append(hour_data)
        
        return HourlyForecastData(
            location=location,
            hours=hourly_data,
            units=units,
            generated_at=datetime.now()
        )
    
    def _convert_weatherapi_hourly(
        self, 
        raw_data: Dict[str, Any], 
        location: str, 
        hours: int, 
        units: str
    ) -> HourlyForecastData:
        """转换WeatherAPI小时预报数据"""
        hourly_data = []
        hour_count = 0
        
        for day_data in raw_data['forecast']['forecastday']:
            if hour_count >= hours:
                break
                
            for hour_data in day_data['hour']:
                if hour_count >= hours:
                    break
                
                dt = datetime.strptime(hour_data['time'], '%Y-%m-%d %H:%M')
                
                # 只包含未来的小时数据
                if dt > datetime.now():
                    hour_info = {
                        'datetime': dt.isoformat(),
                        'temperature': float(hour_data['temp_c'] if units == 'metric' else hour_data['temp_f']),
                        'feels_like': float(hour_data['feelslike_c'] if units == 'metric' else hour_data['feelslike_f']),
                        'humidity': int(hour_data['humidity']),
                        'wind_speed': float(hour_data['wind_kph'] if units == 'metric' else hour_data['wind_mph']),
                        'wind_direction': int(hour_data['wind_degree']),
                        'pressure': float(hour_data['pressure_mb']),
                        'condition': hour_data['condition']['text'],
                        'condition_code': hour_data['condition']['icon'],
                        'precipitation_chance': int(hour_data.get('chance_of_rain', 0))
                    }
                    
                    hourly_data.append(hour_info)
                    hour_count += 1
        
        return HourlyForecastData(
            location=location,
            hours=hourly_data,
            units=units,
            generated_at=datetime.now()
        )