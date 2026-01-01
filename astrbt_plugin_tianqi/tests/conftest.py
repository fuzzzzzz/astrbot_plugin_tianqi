"""
pytest 配置和共享 fixtures
"""

import pytest
import tempfile
import os
from typing import Dict, Any
from weather_plugin.config import WeatherConfig
from weather_plugin.plugin import WeatherPlugin


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
api_provider: "openweathermap"
api_key: "test_api_key"
cache_enabled: true
default_units: "metric"
default_language: "zh"
        """)
        temp_path = f.name
    
    yield temp_path
    
    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """测试配置"""
    return {
        'api_provider': 'openweathermap',
        'api_key': 'test_api_key',
        'cache_enabled': True,
        'default_units': 'metric',
        'default_language': 'zh',
        'cache_ttl_current': 600,
        'cache_ttl_forecast': 3600,
        'cache_ttl_hourly': 1800,
    }


@pytest.fixture
def weather_config(test_config) -> WeatherConfig:
    """天气配置对象"""
    return WeatherConfig(**test_config)


@pytest.fixture
def weather_plugin(test_config) -> WeatherPlugin:
    """天气插件实例"""
    return WeatherPlugin(test_config)


class MockMessageEvent:
    """模拟消息事件"""
    def __init__(self, message: str, user_id: str = "test_user"):
        self.message = message
        self.user_id = user_id


@pytest.fixture
def mock_message_event():
    """模拟消息事件 fixture"""
    def _create_event(message: str, user_id: str = "test_user"):
        return MockMessageEvent(message, user_id)
    return _create_event