"""
核心数据模型定义

定义天气插件使用的所有数据结构，包括天气数据、用户偏好、
命令类型和其他核心数据类型。
"""

from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class CommandType(Enum):
    """命令类型枚举"""
    CURRENT_WEATHER = "current"
    FORECAST = "forecast"
    HOURLY_FORECAST = "hourly"
    SET_LOCATION = "set_location"
    SET_UNITS = "set_units"
    HELP = "help"
    ALERTS = "alerts"
    ACTIVITIES = "activities"


class AlertType(Enum):
    """警报类型枚举"""
    SEVERE_WEATHER = "severe"
    TEMPERATURE_CHANGE = "temperature"
    PRECIPITATION = "precipitation"
    WIND = "wind"
    UV_INDEX = "uv"


class Season(Enum):
    """季节枚举"""
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


@dataclass
class Coordinates:
    """地理坐标"""
    latitude: float
    longitude: float
    
    def __post_init__(self):
        """验证坐标范围"""
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"纬度必须在 -90 到 90 之间，得到: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"经度必须在 -180 到 180 之间，得到: {self.longitude}")


@dataclass
class LocationInfo:
    """位置信息"""
    name: str
    coordinates: Optional[Coordinates] = None
    country: Optional[str] = None
    region: Optional[str] = None


@dataclass
class WeatherData:
    """天气数据模型"""
    location: str
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    wind_direction: int
    pressure: float
    visibility: float
    uv_index: float
    condition: str
    condition_code: str
    timestamp: datetime
    units: str
    
    def __post_init__(self):
        """验证数据范围"""
        if not (0 <= self.humidity <= 100):
            raise ValueError(f"湿度必须在 0-100 之间，得到: {self.humidity}")
        if self.wind_speed < 0:
            raise ValueError(f"风速不能为负数，得到: {self.wind_speed}")
        if not (0 <= self.wind_direction <= 360):
            raise ValueError(f"风向必须在 0-360 度之间，得到: {self.wind_direction}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherData':
        """从字典创建实例"""
        data = data.copy()
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ForecastDay:
    """单日预报数据"""
    date: date
    high_temp: float
    low_temp: float
    condition: str
    precipitation_chance: int
    wind_speed: float
    humidity: int
    
    def __post_init__(self):
        """验证数据"""
        if self.high_temp < self.low_temp:
            raise ValueError(f"最高温度不能低于最低温度: {self.high_temp} < {self.low_temp}")
        if not (0 <= self.precipitation_chance <= 100):
            raise ValueError(f"降水概率必须在 0-100 之间，得到: {self.precipitation_chance}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['date'] = self.date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForecastDay':
        """从字典创建实例"""
        data = data.copy()
        if isinstance(data['date'], str):
            data['date'] = date.fromisoformat(data['date'])
        return cls(**data)


@dataclass
class ForecastData:
    """预报数据模型"""
    location: str
    days: List[ForecastDay]
    units: str
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'location': self.location,
            'days': [day.to_dict() for day in self.days],
            'units': self.units,
            'generated_at': self.generated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForecastData':
        """从字典创建实例"""
        data = data.copy()
        if isinstance(data['generated_at'], str):
            data['generated_at'] = datetime.fromisoformat(data['generated_at'])
        data['days'] = [ForecastDay.from_dict(day_data) for day_data in data['days']]
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class HourlyForecastData:
    """小时预报数据模型"""
    location: str
    hours: List[Dict[str, Any]]  # 包含每小时的详细数据
    units: str
    generated_at: datetime


@dataclass
class UserPrefs:
    """用户偏好设置"""
    user_id: str
    default_location: Optional[str] = None
    units: str = "metric"  # 'metric' 或 'imperial'
    alert_subscriptions: List[AlertType] = None
    language: str = "zh"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.alert_subscriptions is None:
            self.alert_subscriptions = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        
        # 验证单位
        if self.units not in ["metric", "imperial"]:
            raise ValueError(f"单位必须是 'metric' 或 'imperial'，得到: {self.units}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'default_location': self.default_location,
            'units': self.units,
            'alert_subscriptions': [alert.value for alert in self.alert_subscriptions],
            'language': self.language,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPrefs':
        """从字典创建实例"""
        data = data.copy()
        if data.get('created_at') and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('updated_at') and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'alert_subscriptions' in data:
            data['alert_subscriptions'] = [AlertType(alert) for alert in data['alert_subscriptions']]
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def update_location(self, location: str) -> None:
        """更新默认位置"""
        self.default_location = location
        self.updated_at = datetime.now()
    
    def update_units(self, units: str) -> None:
        """更新单位偏好"""
        if units not in ["metric", "imperial"]:
            raise ValueError(f"单位必须是 'metric' 或 'imperial'，得到: {units}")
        self.units = units
        self.updated_at = datetime.now()
    
    def add_alert_subscription(self, alert_type: AlertType) -> None:
        """添加警报订阅"""
        if alert_type not in self.alert_subscriptions:
            self.alert_subscriptions.append(alert_type)
            self.updated_at = datetime.now()
    
    def remove_alert_subscription(self, alert_type: AlertType) -> None:
        """移除警报订阅"""
        if alert_type in self.alert_subscriptions:
            self.alert_subscriptions.remove(alert_type)
            self.updated_at = datetime.now()


@dataclass
class WeatherCommand:
    """天气命令模型"""
    command_type: CommandType
    location: Optional[str] = None
    time_period: Optional[str] = None
    additional_params: Dict[str, Any] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.additional_params is None:
            self.additional_params = {}


@dataclass
class WeatherAlert:
    """天气警报模型"""
    alert_type: AlertType
    title: str
    description: str
    severity: str
    location: str
    start_time: datetime
    end_time: Optional[datetime] = None
    advice: List[str] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.advice is None:
            self.advice = []


@dataclass
class Activity:
    """活动推荐模型"""
    name: str
    description: str
    category: str
    suitable_weather: List[str]
    season: Optional[Season] = None
    indoor: bool = False
    safety_notes: List[str] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.safety_notes is None:
            self.safety_notes = []


class WeatherError(Exception):
    """天气服务异常基类"""
    pass


class APIError(WeatherError):
    """API 调用异常"""
    pass


class LocationError(WeatherError):
    """位置解析异常"""
    pass


class CacheError(WeatherError):
    """缓存操作异常"""
    pass


class ConfigurationError(WeatherError):
    """配置异常"""
    pass