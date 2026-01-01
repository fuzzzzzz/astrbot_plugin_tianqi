"""
智能天气助手 AstrBot 插件

这是一个为 AstrBot 平台设计的天气插件，提供全面的天气信息服务，
包括当前天气、预报、活动推荐和天气警报功能。
"""

__version__ = "1.0.0"
__author__ = "Weather Plugin Team"

from .plugin import WeatherPlugin
from .user_preferences import UserPreferences
from .cache import CacheManager
from .alert_manager import AlertManager

__all__ = ["WeatherPlugin", "UserPreferences", "CacheManager", "AlertManager"]