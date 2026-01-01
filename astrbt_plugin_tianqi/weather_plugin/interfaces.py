"""
核心接口定义

定义天气插件各组件的抽象接口，确保组件间的松耦合和可测试性。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import (
    WeatherData, ForecastData, HourlyForecastData, UserPrefs,
    WeatherCommand, WeatherAlert, Activity, LocationInfo, Coordinates,
    CommandType, AlertType, Season
)


class IWeatherAPIClient(ABC):
    """天气 API 客户端接口"""
    
    @abstractmethod
    async def fetch_current_weather(self, location: str) -> Dict[str, Any]:
        """获取当前天气数据"""
        pass
    
    @abstractmethod
    async def fetch_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """获取天气预报数据"""
        pass
    
    @abstractmethod
    async def fetch_hourly_forecast(self, location: str, hours: int) -> Dict[str, Any]:
        """获取小时预报数据"""
        pass
    
    @abstractmethod
    def check_rate_limit(self) -> bool:
        """检查 API 速率限制"""
        pass


class ICacheManager(ABC):
    """缓存管理器接口"""
    
    @abstractmethod
    async def get_cached_weather(self, cache_key: str) -> Optional[WeatherData]:
        """获取缓存的天气数据"""
        pass
    
    @abstractmethod
    async def cache_weather_data(self, cache_key: str, data: WeatherData, ttl: int) -> None:
        """缓存天气数据"""
        pass
    
    @abstractmethod
    async def get_cached_forecast(self, cache_key: str) -> Optional[ForecastData]:
        """获取缓存的预报数据"""
        pass
    
    @abstractmethod
    async def cache_forecast_data(self, cache_key: str, data: ForecastData, ttl: int) -> None:
        """缓存预报数据"""
        pass
    
    @abstractmethod
    def generate_cache_key(self, location: str, data_type: str, **kwargs) -> str:
        """生成缓存键"""
        pass
    
    @abstractmethod
    def cleanup_expired_cache(self) -> None:
        """清理过期缓存"""
        pass


class ILocationService(ABC):
    """位置服务接口"""
    
    @abstractmethod
    def parse_location(self, location_input: str) -> LocationInfo:
        """解析位置输入"""
        pass
    
    @abstractmethod
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """验证坐标有效性"""
        pass
    
    @abstractmethod
    def suggest_corrections(self, invalid_location: str) -> List[str]:
        """建议位置拼写纠正"""
        pass
    
    @abstractmethod
    async def geocode_location(self, location: str) -> Optional[Coordinates]:
        """地理编码位置"""
        pass


class IUserPreferences(ABC):
    """用户偏好管理接口"""
    
    @abstractmethod
    def get_user_preferences(self, user_id: str) -> UserPrefs:
        """获取用户偏好"""
        pass
    
    @abstractmethod
    def set_default_location(self, user_id: str, location: str) -> None:
        """设置默认位置"""
        pass
    
    @abstractmethod
    def set_units(self, user_id: str, units: str) -> None:
        """设置单位偏好"""
        pass
    
    @abstractmethod
    def get_alert_subscriptions(self, user_id: str) -> List[AlertType]:
        """获取警报订阅"""
        pass
    
    @abstractmethod
    def update_alert_subscriptions(self, user_id: str, alert_types: List[AlertType]) -> None:
        """更新警报订阅"""
        pass


class ICommandParser(ABC):
    """命令解析器接口"""
    
    @abstractmethod
    def parse_command(self, message: str) -> Optional[WeatherCommand]:
        """解析天气命令"""
        pass
    
    @abstractmethod
    def extract_location(self, text: str) -> Optional[str]:
        """提取位置信息"""
        pass
    
    @abstractmethod
    def detect_command_type(self, text: str) -> CommandType:
        """检测命令类型"""
        pass


class IWeatherService(ABC):
    """天气服务接口"""
    
    @abstractmethod
    async def get_current_weather(self, location: str, user_id: str) -> WeatherData:
        """获取当前天气"""
        pass
    
    @abstractmethod
    async def get_forecast(self, location: str, days: int, user_id: str) -> ForecastData:
        """获取天气预报"""
        pass
    
    @abstractmethod
    async def get_hourly_forecast(self, location: str, hours: int, user_id: str) -> HourlyForecastData:
        """获取小时预报"""
        pass


class IActivityRecommender(ABC):
    """活动推荐器接口"""
    
    @abstractmethod
    def recommend_activities(self, weather: WeatherData, season: Season) -> List[Activity]:
        """推荐活动"""
        pass
    
    @abstractmethod
    def get_safety_recommendations(self, weather: WeatherData) -> List[str]:
        """获取安全建议"""
        pass
    
    @abstractmethod
    def filter_by_weather_conditions(self, activities: List[Activity], weather: WeatherData) -> List[Activity]:
        """根据天气条件过滤活动"""
        pass


class IAlertManager(ABC):
    """警报管理器接口"""
    
    @abstractmethod
    async def check_weather_alerts(self, location: str) -> List[WeatherAlert]:
        """检查天气警报"""
        pass
    
    @abstractmethod
    async def send_alert(self, user_id: str, alert: WeatherAlert) -> None:
        """发送警报"""
        pass
    
    @abstractmethod
    def subscribe_user(self, user_id: str, alert_types: List[AlertType]) -> None:
        """订阅用户警报"""
        pass
    
    @abstractmethod
    def should_send_alert(self, alert: WeatherAlert, user_prefs: UserPrefs) -> bool:
        """判断是否应该发送警报"""
        pass


class IWeatherPlugin(ABC):
    """天气插件主接口"""
    
    @abstractmethod
    async def on_message(self, event: Any) -> Optional[str]:
        """处理消息事件"""
        pass
    
    @abstractmethod
    async def on_command(self, command: str, args: List[str], user_id: str) -> str:
        """处理命令"""
        pass
    
    @abstractmethod
    def reload_config(self) -> None:
        """重新加载配置"""
        pass