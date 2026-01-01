"""
天气服务测试

测试核心天气服务的功能和集成。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date

from weather_plugin.weather_service import WeatherService, CircuitBreaker, CircuitBreakerState
from weather_plugin.config import WeatherConfig
from weather_plugin.models import (
    WeatherData, ForecastData, ForecastDay, HourlyForecastData,
    APIError, LocationError, WeatherError, LocationInfo, UserPrefs, AlertType
)
from weather_plugin.api_client import MockWeatherAPIClient
from weather_plugin.cache import CacheManager
from weather_plugin.location_service import LocationService
from weather_plugin.user_preferences import UserPreferences


class TestWeatherService:
    """天气服务基础测试"""
    
    @pytest.fixture
    def weather_config(self):
        """测试配置"""
        return WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key",
            cache_enabled=True,
            default_units="metric",
            default_language="zh",
            cache_ttl_current=600,
            cache_ttl_forecast=3600,
            cache_ttl_hourly=1800,
            cache_db_path=":memory:"
        )
    
    @pytest.fixture
    def mock_api_client(self, weather_config):
        """模拟API客户端"""
        return MockWeatherAPIClient(weather_config)
    
    @pytest.fixture
    def cache_manager(self, weather_config):
        """缓存管理器"""
        return CacheManager(weather_config)
    
    @pytest.fixture
    def location_service(self, weather_config):
        """位置服务"""
        return LocationService(weather_config)
    
    @pytest.fixture
    def user_preferences(self):
        """用户偏好管理"""
        return UserPreferences(db_path=":memory:")
    
    @pytest.fixture
    def weather_service(self, weather_config, mock_api_client, cache_manager, location_service, user_preferences):
        """天气服务实例"""
        return WeatherService(
            config=weather_config,
            api_client=mock_api_client,
            cache_manager=cache_manager,
            location_service=location_service,
            user_preferences=user_preferences
        )
    
    def test_weather_service_initialization(self, weather_service):
        """测试天气服务初始化"""
        assert weather_service is not None
        assert weather_service.config is not None
        assert weather_service.api_client is not None
        assert weather_service.cache_manager is not None
        assert weather_service.location_service is not None
        assert weather_service.user_preferences is not None
        assert weather_service.circuit_breaker is not None
    
    @pytest.mark.asyncio
    async def test_get_current_weather_success(self, weather_service):
        """测试成功获取当前天气"""
        # 使用模拟的方式避免数据库依赖
        from unittest.mock import patch, AsyncMock
        
        # 模拟用户偏好
        mock_prefs = UserPrefs(user_id="test_user", units="metric", default_location="北京")
        
        with patch.object(weather_service.user_preferences, 'get_user_preferences', return_value=mock_prefs):
            # 获取天气数据
            weather_data = await weather_service.get_current_weather("北京", "test_user")
            
            assert weather_data is not None
            assert isinstance(weather_data, WeatherData)
            assert weather_data.location == "北京"
            assert weather_data.temperature is not None
            assert weather_data.units == "metric"
    
    @pytest.mark.asyncio
    async def test_get_forecast_success(self, weather_service):
        """测试成功获取预报数据"""
        from unittest.mock import patch
        
        # 模拟用户偏好
        mock_prefs = UserPrefs(user_id="test_user", units="metric")
        
        with patch.object(weather_service.user_preferences, 'get_user_preferences', return_value=mock_prefs):
            # 获取预报数据
            forecast_data = await weather_service.get_forecast("北京", 3, "test_user")
            
            assert forecast_data is not None
            assert isinstance(forecast_data, ForecastData)
            assert forecast_data.location == "北京"
            assert len(forecast_data.days) <= 3
            assert forecast_data.units == "metric"
    
    @pytest.mark.asyncio
    async def test_get_hourly_forecast_success(self, weather_service):
        """测试成功获取小时预报"""
        from unittest.mock import patch
        
        # 模拟用户偏好
        mock_prefs = UserPrefs(user_id="test_user", units="metric")
        
        with patch.object(weather_service.user_preferences, 'get_user_preferences', return_value=mock_prefs):
            # 获取小时预报数据
            hourly_data = await weather_service.get_hourly_forecast("北京", 12, "test_user")
            
            assert hourly_data is not None
            assert isinstance(hourly_data, HourlyForecastData)
            assert hourly_data.location == "北京"
            assert len(hourly_data.hours) <= 12
            assert hourly_data.units == "metric"
    
    @pytest.mark.asyncio
    async def test_invalid_forecast_days(self, weather_service):
        """测试无效的预报天数"""
        with pytest.raises(WeatherError, match="预报天数必须在 1-16 之间"):
            await weather_service.get_forecast("北京", 0, "test_user")
        
        with pytest.raises(WeatherError, match="预报天数必须在 1-16 之间"):
            await weather_service.get_forecast("北京", 20, "test_user")
    
    @pytest.mark.asyncio
    async def test_invalid_hourly_hours(self, weather_service):
        """测试无效的小时数"""
        with pytest.raises(WeatherError, match="小时预报时长必须在 1-48 小时之间"):
            await weather_service.get_hourly_forecast("北京", 0, "test_user")
        
        with pytest.raises(WeatherError, match="小时预报时长必须在 1-48 小时之间"):
            await weather_service.get_hourly_forecast("北京", 50, "test_user")
    
    def test_validate_weather_data_valid(self, weather_service):
        """测试有效天气数据验证"""
        weather_data = WeatherData(
            location="北京",
            temperature=25.0,
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        assert weather_service._validate_weather_data(weather_data) is True
    
    def test_validate_weather_data_invalid_temperature(self, weather_service):
        """测试无效温度数据验证"""
        weather_data = WeatherData(
            location="北京",
            temperature=100.0,  # 异常高温
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        assert weather_service._validate_weather_data(weather_data) is False
    
    def test_sanitize_weather_data(self, weather_service):
        """测试天气数据清理"""
        # 创建一个有效的基础数据，然后修改需要清理的字段
        weather_data = WeatherData(
            location="北京",
            temperature=25.0,  # 先用有效值
            feels_like=27.0,
            humidity=60,  # 先用有效值
            wind_speed=10.0,  # 先用有效值
            wind_direction=180,  # 先用有效值
            pressure=1013.0,  # 先用有效值
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        # 手动设置异常值（绕过验证）
        weather_data.temperature = 100.0  # 异常高温
        weather_data.humidity = 150  # 异常湿度
        weather_data.wind_speed = -10.0  # 负风速
        weather_data.wind_direction = 400  # 超出范围的风向
        weather_data.pressure = 500.0  # 异常气压
        
        sanitized = weather_service._sanitize_weather_data(weather_data)
        
        assert sanitized.temperature == 60.0  # 修正为最大值
        assert sanitized.humidity == 100  # 修正为最大值
        assert sanitized.wind_speed == 0.0  # 修正为0
        assert sanitized.wind_direction == 40  # 400 % 360 = 40
        assert sanitized.pressure == 800.0  # 修正为最小值
    
    def test_get_friendly_error_message(self, weather_service):
        """测试友好错误消息"""
        assert "暂时不可用" in weather_service._get_friendly_error_message("api_unavailable", "北京")
        assert "未找到位置" in weather_service._get_friendly_error_message("location_not_found", "北京")
        assert "请求过于频繁" in weather_service._get_friendly_error_message("rate_limit")
        assert "网络连接" in weather_service._get_friendly_error_message("network_error")


class TestCircuitBreaker:
    """断路器测试"""
    
    def test_circuit_breaker_initialization(self):
        """测试断路器初始化"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """测试断路器成功调用"""
        cb = CircuitBreaker()
        
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """测试断路器失败阈值"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        # 第一次失败
        with pytest.raises(Exception):
            await cb.call(failing_func)
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED
        
        # 第二次失败，触发断路器
        with pytest.raises(Exception):
            await cb.call(failing_func)
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN
        
        # 断路器开启时，直接抛出异常
        with pytest.raises(APIError, match="服务暂时不可用"):
            await cb.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """测试断路器恢复"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # 触发断路器
        with pytest.raises(Exception):
            await cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        
        # 等待恢复时间
        await asyncio.sleep(0.2)
        
        # 成功调用应该重置断路器
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


class TestWeatherServiceIntegration:
    """天气服务集成测试"""
    
    @pytest.fixture
    def weather_config(self):
        """测试配置"""
        return WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key",
            cache_enabled=True,
            default_units="metric",
            default_language="zh",
            cache_ttl_current=600,
            cache_ttl_forecast=3600,
            cache_ttl_hourly=1800,
            cache_db_path=":memory:"
        )
    
    @pytest.fixture
    def weather_service_with_mocks(self, weather_config):
        """带模拟组件的天气服务"""
        # 创建模拟组件
        mock_api_client = Mock()
        mock_cache_manager = Mock()
        mock_location_service = Mock()
        mock_user_preferences = Mock()
        
        # 配置模拟行为
        mock_location_service.parse_location.return_value = LocationInfo(name="北京")
        mock_user_preferences.get_user_preferences.return_value = UserPrefs(
            user_id="test_user",
            units="metric",
            default_location="北京"
        )
        
        return WeatherService(
            config=weather_config,
            api_client=mock_api_client,
            cache_manager=mock_cache_manager,
            location_service=mock_location_service,
            user_preferences=mock_user_preferences
        )
    
    @pytest.mark.asyncio
    async def test_cache_hit_scenario(self, weather_service_with_mocks):
        """测试缓存命中场景"""
        service = weather_service_with_mocks
        
        # 配置缓存返回数据
        cached_weather = WeatherData(
            location="北京",
            temperature=25.0,
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        service.cache_manager.get_cached_weather = AsyncMock(return_value=cached_weather)
        
        # 调用服务
        result = await service.get_current_weather("北京", "test_user")
        
        # 验证结果
        assert result == cached_weather
        service.cache_manager.get_cached_weather.assert_called_once()
        # API客户端不应该被调用
        service.api_client.fetch_current_weather.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_api_call_with_cache_miss(self, weather_service_with_mocks):
        """测试缓存未命中时的API调用"""
        service = weather_service_with_mocks
        
        # 配置缓存未命中
        service.cache_manager.get_cached_weather = AsyncMock(return_value=None)
        service.cache_manager.cache_weather_data = AsyncMock()
        
        # 配置API返回数据
        api_response = {
            "main": {
                "temp": 25.0,
                "feels_like": 27.0,
                "humidity": 60,
                "pressure": 1013.0
            },
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 10.0, "deg": 180},
            "visibility": 10000
        }
        
        service.api_client.fetch_current_weather = AsyncMock(return_value=api_response)
        
        # 调用服务
        result = await service.get_current_weather("北京", "test_user")
        
        # 验证结果
        assert isinstance(result, WeatherData)
        assert result.location == "北京"
        assert result.temperature == 25.0
        
        # 验证调用
        service.cache_manager.get_cached_weather.assert_called_once()
        service.cache_manager.cache_weather_data.assert_called_once()