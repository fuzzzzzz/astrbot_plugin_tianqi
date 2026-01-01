"""
天气 API 客户端实现

实现与 OpenWeatherMap API 的集成，包括错误处理和速率限制检查。
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .interfaces import IWeatherAPIClient
from .models import APIError, ConfigurationError
from .config import WeatherConfig


class WeatherAPIClient(IWeatherAPIClient):
    """天气 API 客户端实现"""
    
    def __init__(self, config: WeatherConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_tracker = {
            'requests': [],
            'daily_count': 0,
            'daily_reset': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        }
        
        # 获取提供商配置
        provider_config = config.get_provider_config()
        if not provider_config:
            raise ConfigurationError(f"未找到 API 提供商配置: {config.api_provider}")
        
        self.provider_config = provider_config
        self.base_url = config.api_base_url or provider_config.base_url
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保 HTTP 会话已创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': f'{self.config.plugin_name}/{self.config.plugin_version}',
                    'Accept': 'application/json'
                }
            )
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def check_rate_limit(self) -> bool:
        """检查 API 速率限制"""
        now = datetime.now()
        
        # 检查是否需要重置每日计数
        if now >= self._rate_limit_tracker['daily_reset']:
            self._rate_limit_tracker['daily_count'] = 0
            self._rate_limit_tracker['daily_reset'] = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
        
        # 清理过期的分钟级请求记录
        minute_ago = now - timedelta(minutes=1)
        self._rate_limit_tracker['requests'] = [
            req_time for req_time in self._rate_limit_tracker['requests']
            if req_time > minute_ago
        ]
        
        # 检查分钟级限制
        if len(self._rate_limit_tracker['requests']) >= self.config.rate_limit_per_minute:
            return False
        
        # 检查每日限制
        if self._rate_limit_tracker['daily_count'] >= self.config.rate_limit_per_day:
            return False
        
        return True
    
    def _record_request(self):
        """记录 API 请求"""
        now = datetime.now()
        self._rate_limit_tracker['requests'].append(now)
        self._rate_limit_tracker['daily_count'] += 1
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发起 API 请求"""
        if not self.check_rate_limit():
            raise APIError("API 速率限制已达到，请稍后再试")
        
        await self._ensure_session()
        
        # 添加 API 密钥到参数
        if self.provider_config.api_key_required:
            if self.config.api_provider == "openweathermap":
                params['appid'] = self.config.api_key
            elif self.config.api_provider == "weatherapi":
                params['key'] = self.config.api_key
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            self._record_request()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise APIError("API 密钥无效或已过期")
                elif response.status == 404:
                    raise APIError("请求的位置未找到")
                elif response.status == 429:
                    raise APIError("API 请求频率过高，请稍后再试")
                elif response.status >= 500:
                    raise APIError(f"API 服务器错误: {response.status}")
                else:
                    error_text = await response.text()
                    raise APIError(f"API 请求失败: {response.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise APIError(f"网络请求失败: {e}")
        except asyncio.TimeoutError:
            raise APIError("API 请求超时")
    
    async def fetch_current_weather(self, location: str) -> Dict[str, Any]:
        """获取当前天气数据"""
        if self.config.api_provider == "openweathermap":
            return await self._fetch_openweathermap_current(location)
        elif self.config.api_provider == "weatherapi":
            return await self._fetch_weatherapi_current(location)
        else:
            raise APIError(f"不支持的 API 提供商: {self.config.api_provider}")
    
    async def _fetch_openweathermap_current(self, location: str) -> Dict[str, Any]:
        """获取 OpenWeatherMap 当前天气"""
        params = {
            'q': location,
            'units': self.config.default_units,
            'lang': 'zh_cn' if self.config.default_language == 'zh' else 'en'
        }
        
        return await self._make_request('weather', params)
    
    async def _fetch_weatherapi_current(self, location: str) -> Dict[str, Any]:
        """获取 WeatherAPI 当前天气"""
        params = {
            'q': location,
            'aqi': 'yes'  # 包含空气质量数据
        }
        
        return await self._make_request('current.json', params)
    
    async def fetch_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """获取天气预报数据"""
        if days <= 0 or days > 16:
            raise APIError("预报天数必须在 1-16 之间")
        
        if self.config.api_provider == "openweathermap":
            return await self._fetch_openweathermap_forecast(location, days)
        elif self.config.api_provider == "weatherapi":
            return await self._fetch_weatherapi_forecast(location, days)
        else:
            raise APIError(f"不支持的 API 提供商: {self.config.api_provider}")
    
    async def _fetch_openweathermap_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """获取 OpenWeatherMap 预报数据"""
        params = {
            'q': location,
            'cnt': days * 8,  # OpenWeatherMap 5天预报，每3小时一个数据点
            'units': self.config.default_units,
            'lang': 'zh_cn' if self.config.default_language == 'zh' else 'en'
        }
        
        return await self._make_request('forecast', params)
    
    async def _fetch_weatherapi_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """获取 WeatherAPI 预报数据"""
        params = {
            'q': location,
            'days': min(days, 10),  # WeatherAPI 免费版最多10天
            'aqi': 'yes',
            'alerts': 'yes'
        }
        
        return await self._make_request('forecast.json', params)
    
    async def fetch_hourly_forecast(self, location: str, hours: int) -> Dict[str, Any]:
        """获取小时预报数据"""
        if hours <= 0 or hours > 48:
            raise APIError("小时预报时长必须在 1-48 小时之间")
        
        if self.config.api_provider == "openweathermap":
            return await self._fetch_openweathermap_hourly(location, hours)
        elif self.config.api_provider == "weatherapi":
            return await self._fetch_weatherapi_hourly(location, hours)
        else:
            raise APIError(f"不支持的 API 提供商: {self.config.api_provider}")
    
    async def _fetch_openweathermap_hourly(self, location: str, hours: int) -> Dict[str, Any]:
        """获取 OpenWeatherMap 小时预报"""
        # OpenWeatherMap 的 5天预报包含小时数据
        params = {
            'q': location,
            'cnt': min(hours, 40),  # 最多40个数据点（5天 * 8个/天）
            'units': self.config.default_units,
            'lang': 'zh_cn' if self.config.default_language == 'zh' else 'en'
        }
        
        return await self._make_request('forecast', params)
    
    async def _fetch_weatherapi_hourly(self, location: str, hours: int) -> Dict[str, Any]:
        """获取 WeatherAPI 小时预报"""
        # WeatherAPI 通过预报接口获取小时数据
        days = min((hours + 23) // 24, 3)  # 计算需要的天数，最多3天
        params = {
            'q': location,
            'days': days,
            'aqi': 'yes',
            'alerts': 'yes'
        }
        
        return await self._make_request('forecast.json', params)


class MockWeatherAPIClient(IWeatherAPIClient):
    """模拟天气 API 客户端（用于测试）"""
    
    def __init__(self, config: WeatherConfig):
        self.config = config
        self._request_count = 0
        self._last_request_time = None
        self._rate_limit_tracker = {
            'requests': [],
            'daily_count': 0,
            'daily_reset': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        }
    
    def _record_request(self):
        """记录 API 请求"""
        now = datetime.now()
        self._rate_limit_tracker['requests'].append(now)
        self._rate_limit_tracker['daily_count'] += 1
        self._last_request_time = time.time()
    
    def check_rate_limit(self) -> bool:
        """检查速率限制（模拟）"""
        now = datetime.now()
        
        # 检查是否需要重置每日计数
        if now >= self._rate_limit_tracker['daily_reset']:
            self._rate_limit_tracker['daily_count'] = 0
            self._rate_limit_tracker['daily_reset'] = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
        
        # 清理过期的分钟级请求记录
        minute_ago = now - timedelta(minutes=1)
        self._rate_limit_tracker['requests'] = [
            req_time for req_time in self._rate_limit_tracker['requests']
            if req_time > minute_ago
        ]
        
        # 检查分钟级限制
        if len(self._rate_limit_tracker['requests']) >= self.config.rate_limit_per_minute:
            return False
        
        # 检查每日限制
        if self._rate_limit_tracker['daily_count'] >= self.config.rate_limit_per_day:
            return False
        
        return True
    
    async def fetch_current_weather(self, location: str) -> Dict[str, Any]:
        """获取模拟当前天气数据"""
        if not self.check_rate_limit():
            raise APIError("模拟速率限制")
        
        self._request_count += 1
        self._last_request_time = time.time()
        
        return {
            "coord": {"lon": 116.4074, "lat": 39.9042},
            "weather": [{"id": 800, "main": "Clear", "description": "晴朗", "icon": "01d"}],
            "base": "stations",
            "main": {
                "temp": 25.0,
                "feels_like": 27.0,
                "temp_min": 22.0,
                "temp_max": 28.0,
                "pressure": 1013,
                "humidity": 60
            },
            "visibility": 10000,
            "wind": {"speed": 3.5, "deg": 180},
            "clouds": {"all": 0},
            "dt": int(time.time()),
            "sys": {"country": "CN", "sunrise": 1640995200, "sunset": 1641030000},
            "timezone": 28800,
            "id": 1816670,
            "name": location,
            "cod": 200
        }
    
    async def fetch_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """获取模拟预报数据"""
        if not self.check_rate_limit():
            raise APIError("模拟速率限制")
        
        self._request_count += 1
        self._last_request_time = time.time()
        
        forecast_list = []
        base_time = int(time.time())
        
        for i in range(days * 8):  # 每天8个数据点
            forecast_list.append({
                "dt": base_time + (i * 3 * 3600),  # 每3小时
                "main": {
                    "temp": 25.0 + (i % 10) - 5,
                    "feels_like": 27.0 + (i % 10) - 5,
                    "temp_min": 22.0 + (i % 8) - 4,
                    "temp_max": 28.0 + (i % 8) - 4,
                    "pressure": 1013 + (i % 20) - 10,
                    "humidity": 60 + (i % 40) - 20
                },
                "weather": [{"id": 800, "main": "Clear", "description": "晴朗", "icon": "01d"}],
                "clouds": {"all": i % 50},
                "wind": {"speed": 3.5 + (i % 10) / 10, "deg": 180 + (i % 360)},
                "visibility": 10000,
                "pop": (i % 100) / 100,
                "dt_txt": datetime.fromtimestamp(base_time + (i * 3 * 3600)).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return {
            "cod": "200",
            "message": 0,
            "cnt": len(forecast_list),
            "list": forecast_list,
            "city": {
                "id": 1816670,
                "name": location,
                "coord": {"lat": 39.9042, "lon": 116.4074},
                "country": "CN",
                "population": 11716620,
                "timezone": 28800,
                "sunrise": 1640995200,
                "sunset": 1641030000
            }
        }
    
    async def fetch_hourly_forecast(self, location: str, hours: int) -> Dict[str, Any]:
        """获取模拟小时预报数据"""
        # 复用预报数据，但限制小时数
        forecast_data = await self.fetch_forecast(location, (hours + 7) // 8)
        forecast_data["list"] = forecast_data["list"][:hours]
        forecast_data["cnt"] = len(forecast_data["list"])
        return forecast_data